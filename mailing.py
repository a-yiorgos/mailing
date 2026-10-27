import os
import re
import sys
import time
import smtplib
import logging
import mailbox
import tempfile
from datetime import datetime
import copy
from email.message import Message
from email.utils import parseaddr, formataddr

# Logging setup to stdout
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    stream=sys.stdout
)
logger = logging.getLogger("mailing")

# Configuration
MAILING_LIST = "list@example.com"
SPOOL_FILE = "/var/mail/list"
MAILING_DOMAIN = "example.com"
MAILINGS_FILE = "Mailings"
SMTP_HOST = "smtp.example.com"
SMTP_PORT = 465
SMTP_USER = "list@example.com"
SMTP_PW = "XXXX"
REPLY_TO_LIST = True


def load_mailings(filename=MAILINGS_FILE):
    """Load list of subscribed email addresses from file."""
    if not os.path.exists(filename):
        return []
    with open(filename, "r", encoding="utf-8", errors="replace") as f:
        return [line.strip() for line in f if line.strip()]


def save_mailings(mailings, filename=MAILINGS_FILE):
    """Save list of subscribed email addresses to file."""
    with open(filename, "w", encoding="utf-8") as f:
        for addr in mailings:
            f.write(f"{addr}\n")


def parse_mbox_stream(f):
    """
    Parses an mbox input stream using standard library mailbox module.
    Returns (valid_mbox, list_of_messages).
    If the first non-empty line does not start with 'From ', valid_mbox is False.
    """
    content = f.read()
    if not content:
        return True, []

    lines = content.splitlines(True)
    idx = 0
    while idx < len(lines) and not lines[idx].strip():
        idx += 1

    if idx >= len(lines):
        return True, []

    if not lines[idx].startswith("From "):
        return False, []

    # Create temporary directory and file for cross-platform mailbox.mbox parsing
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_file_path = os.path.join(temp_dir, "spool.mbox")
        with open(temp_file_path, "w", encoding="utf-8", errors="replace") as temp_file:
            temp_file.write(content)

        mbox = mailbox.mbox(temp_file_path)
        messages = []
        try:
            for mbox_msg in mbox:
                from_line = mbox_msg.get_from() or ""
                parts = from_line.split(" ")
                from_env = parts[0].lower() if parts else ""

                headers = {k.lower(): str(v) for k, v in mbox_msg.items()}

                if mbox_msg.is_multipart():
                    payload_parts = []
                    for part in mbox_msg.walk():
                        if part.get_content_maintype() == "text":
                            decoded = part.get_payload(decode=True)
                            if isinstance(decoded, bytes):
                                payload_parts.append(decoded.decode("utf-8", errors="replace"))
                            elif isinstance(decoded, str):
                                payload_parts.append(decoded)
                    payload_str = "".join(payload_parts)
                else:
                    payload = mbox_msg.get_payload()
                    if isinstance(payload, list):
                        payload_str = "".join(str(m.get_payload()) if hasattr(m, 'get_payload') else str(m) for m in payload)
                    else:
                        payload_str = payload if isinstance(payload, str) else str(payload or "")

                body_lines = payload_str.splitlines(True)

                # Clone original message to preserve entire structure (multipart, HTML, boundaries, etc.)
                msg_copy = copy.deepcopy(mbox_msg)

                messages.append({
                    'from_env': from_env,
                    'headers': headers,
                    'body_lines': body_lines,
                    'mbox_msg': msg_copy
                })
        finally:
            mbox.close()

    return True, messages


def format_outgoing_message(msg_data, mailing_list=MAILING_LIST, reply_to_list=REPLY_TO_LIST):
    """
    Formats outgoing email headers and body using standard email.message.Message while preserving
    multipart MIME boundaries and HTML formatting.
    Returns full message string formatted with CRLF line endings.
    """
    mbox_msg = msg_data.get('mbox_msg')
    headers = msg_data.get('headers', {})
    from_env = msg_data.get('from_env', '')

    orig_from = mbox_msg.get('From') if mbox_msg and 'From' in mbox_msg else headers.get('from', '')
    sender_info = orig_from or from_env

    # Determine GECOS field and From header
    realname, addr = parseaddr(sender_info)
    sender_addr = addr or from_env
    if realname.strip():
        gecos = realname.strip()
    else:
        gecos = sender_addr.split('@')[0] if '@' in sender_addr else sender_addr

    gecos_via = f"{gecos} via {mailing_list}"
    from_header = formataddr((gecos_via, mailing_list))

    reply_to = mailing_list if reply_to_list else sender_info

    subject = mbox_msg.get('Subject') if mbox_msg and 'Subject' in mbox_msg else headers.get('subject', '')
    sub_subj = (subject or "").strip().lower()

    if sub_subj in ("subscribe", "unsubscribe"):
        # For subscribe / unsubscribe administrative auto-replies, construct plain-text response
        sender_name = sender_info
        if sub_subj == "subscribe":
            body_prefix = f"Hello {sender_name} :-)\r\nYou are now subscribed\r\n****\r\n\r\n"
        else:
            body_prefix = f"Good bye {sender_name} :-(\r\nYou are now unsubscribed\r\n****\r\n\r\n"

        body = "".join(msg_data.get('body_lines', []))
        msg = Message()
        msg['From'] = from_header
        msg['X-Original-From'] = orig_from or sender_info
        msg['Sender'] = sender_info
        msg['Reply-To'] = reply_to
        msg['To'] = mailing_list
        msg['Subject'] = subject or ""
        msg['List-Subscribe'] = f"<mailto:{mailing_list}?subject=Subscribe>"
        msg['List-Unsubscribe'] = f"<mailto:{mailing_list}?subject=Unsubscribe>"
        msg.set_payload(body_prefix + body)
        raw_str = msg.as_string()
    else:
        # Clone message to preserve original MIME structure, attachments, boundaries, HTML content
        if mbox_msg is not None:
            msg = copy.deepcopy(mbox_msg)
        else:
            msg = Message()
            header_name_map = {
                'message-id': 'Message-ID',
                'mime-version': 'MIME-Version',
                'in-reply-to': 'In-Reply-To',
                'content-type': 'Content-Type',
                'content-transfer-encoding': 'Content-Transfer-Encoding',
                'content-disposition': 'Content-Disposition',
                'user-agent': 'User-Agent',
            }
            for k, v in headers.items():
                name = header_name_map.get(k.lower(), k.title())
                msg[name] = v
            body = "".join(msg_data.get('body_lines', []))
            msg.set_payload(body)

        # Set / update required headers
        msg['X-Original-From'] = orig_from or sender_info
        if 'From' in msg:
            del msg['From']
        msg['From'] = from_header

        if 'Sender' in msg:
            del msg['Sender']
        msg['Sender'] = sender_info

        if 'Reply-To' in msg:
            del msg['Reply-To']
        msg['Reply-To'] = reply_to

        if 'To' in msg:
            del msg['To']
        msg['To'] = mailing_list

        if 'List-Subscribe' in msg:
            del msg['List-Subscribe']
        msg['List-Subscribe'] = f"<mailto:{mailing_list}?subject=Subscribe>"

        if 'List-Unsubscribe' in msg:
            del msg['List-Unsubscribe']
        msg['List-Unsubscribe'] = f"<mailto:{mailing_list}?subject=Unsubscribe>"

        raw_str = msg.as_string()

    # Ensure CRLF line endings throughout message
    lines = raw_str.splitlines()
    return "\r\n".join(lines) + "\r\n"


def send_smtp_message(recipients, raw_message, smtp_host=SMTP_HOST, smtp_port=SMTP_PORT,
                      smtp_user=SMTP_USER, smtp_pw=SMTP_PW, mailing_domain=MAILING_DOMAIN,
                      mailing_list=MAILING_LIST):
    """Connects to SMTP host via SSL (port 465) or STARTTLS (port 587) and sends the message to recipient addresses."""
    try:
        if smtp_port == 587:
            smtp = smtplib.SMTP(smtp_host, smtp_port)
            smtp.starttls()
        else:
            smtp = smtplib.SMTP_SSL(smtp_host, smtp_port)
    except Exception:
        logger.error("!! Can't connect to SMTP server")
        return False

    try:
        smtp.helo(mailing_domain)
        smtp.login(smtp_user, smtp_pw)
    except Exception:
        logger.error("!! Can't HELO")
        try:
            smtp.quit()
        except Exception:
            pass
        return False

    try:
        refused = smtp.sendmail(mailing_list, recipients, raw_message)
        if refused:
            for recipient in refused:
                logger.error(f"{recipient} can't mail")
    except Exception as e:
        logger.error(f"!! Can't mail: {e}")
        try:
            smtp.quit()
        except Exception:
            pass
        return False

    try:
        smtp.quit()
    except Exception:
        pass

    return True


def process_spool(spool_file=SPOOL_FILE, mailings_file=MAILINGS_FILE,
                  mailing_list=MAILING_LIST, smtp_host=SMTP_HOST,
                  smtp_port=SMTP_PORT, smtp_user=SMTP_USER, smtp_pw=SMTP_PW,
                  mailing_domain=MAILING_DOMAIN, smtp_sender=send_smtp_message,
                  reply_to_list=REPLY_TO_LIST):
    """Processes messages from spool file and clears spool when finished."""
    if not os.path.exists(spool_file) or os.path.getsize(spool_file) == 0:
        return

    mailings = load_mailings(mailings_file)

    with open(spool_file, "r", encoding="utf-8", errors="replace") as f:
        valid_mbox, messages = parse_mbox_stream(f)

    if not valid_mbox:
        logger.error("!! Bad mbox file")
        return

    for msg_data in messages:
        from_env = msg_data['from_env']
        subject = msg_data['headers'].get('subject', '')
        sub_subj = subject.strip().lower()

        is_member = from_env in mailings
        is_subscribe = (sub_subj == "subscribe")

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if not is_member and not is_subscribe:
            logger.info(f"** {timestamp} {from_env} discarded")
            continue

        logger.info(f"** {timestamp} {from_env} accepted")

        if is_subscribe:
            if from_env not in mailings:
                mailings.append(from_env)
                save_mailings(mailings, mailings_file)

        # Handle unsubscribe side-effect on mailings list
        if sub_subj == "unsubscribe":
            if from_env in mailings:
                mailings.remove(from_env)
                save_mailings(mailings, mailings_file)

        if is_subscribe or sub_subj == "unsubscribe":
            recipients = [from_env]
        else:
            recipients = list(mailings)

        full_msg = format_outgoing_message(msg_data, mailing_list, reply_to_list=reply_to_list)

        smtp_sender(
            recipients=recipients,
            raw_message=full_msg,
            smtp_host=smtp_host,
            smtp_port=smtp_port,
            smtp_user=smtp_user,
            smtp_pw=smtp_pw,
            mailing_domain=mailing_domain,
            mailing_list=mailing_list
        )

    # Truncate spool file after processing
    open(spool_file, "w").close()


def main_loop():
    """Main execution loop for mailing service."""
    while True:
        try:
            process_spool()
        except Exception as e:
            logger.error(f"!! Error: {e}")
        time.sleep(240)


if __name__ == "__main__":
    main_loop()
