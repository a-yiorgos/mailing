import os
import re
import sys
import time
import smtplib
import logging
import mailbox
import tempfile
from datetime import datetime
from email.message import Message

# Logging setup to stdout
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    stream=sys.stdout
)
logger = logging.getLogger("mailing")

# Configuration
MAILING_LIST = "picolisp@software-lab.de"
SPOOL_FILE = "/var/mail/picolisp"
MAILING_DOMAIN = "software-lab.de"
MAILINGS_FILE = "Mailings"
SMTP_HOST = "smtp.strato.de"
SMTP_PORT = 465
SMTP_USER = "picolisp@software-lab.de"
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

                messages.append({
                    'from_env': from_env,
                    'headers': headers,
                    'body_lines': body_lines,
                    'mbox_msg': mbox_msg
                })
        finally:
            mbox.close()

    return True, messages


def format_outgoing_message(msg_data, mailing_list=MAILING_LIST, reply_to_list=REPLY_TO_LIST):
    """
    Formats outgoing email headers and body using standard email.message.Message.
    Returns full message string.
    """
    headers = msg_data['headers']
    from_env = msg_data['from_env']
    src = headers.get('from', '')
    subject = headers.get('subject', '')

    # Determine From: header
    match = re.match(r'^(.*?)\s*<([^>]+)>$', src)
    if match:
        display_name = match.group(1).strip()
        from_header = f"{display_name} <{mailing_list}>"
    else:
        from_header = mailing_list

    reply_to = mailing_list if reply_to_list else (src or from_env)

    msg = Message()
    msg['From'] = from_header
    msg['Sender'] = src or from_env
    msg['Reply-To'] = reply_to
    msg['To'] = mailing_list
    msg['Subject'] = subject
    msg['List-Subscribe'] = f"<mailto:{mailing_list}?subject=Subscribe>"
    msg['List-Unsubscribe'] = f"<mailto:{mailing_list}?subject=Unsubscribe>"

    optional_headers = [
        ('date', 'Date'),
        ('message-id', 'Message-ID'),
        ('in-reply-to', 'In-Reply-To'),
        ('mime-version', 'MIME-Version'),
        ('content-type', 'Content-Type'),
        ('content-transfer-encoding', 'Content-Transfer-Encoding'),
        ('content-disposition', 'Content-Disposition'),
        ('user-agent', 'User-Agent'),
    ]

    for key, name in optional_headers:
        if key in headers:
            msg[name] = headers[key]

    # Body prefix based on subject
    sub_subj = subject.strip().lower()
    body_prefix = ""
    if sub_subj == "subscribe":
        sender_name = src or from_env
        body_prefix = f"Hello {sender_name} :-)\r\nYou are now subscribed\r\n****\r\n\r\n"
    elif sub_subj == "unsubscribe":
        sender_name = src or from_env
        body_prefix = f"Good bye {sender_name} :-(\r\nYou are now unsubscribed\r\n****\r\n\r\n"

    body = "".join(msg_data['body_lines'])
    msg.set_payload(body_prefix + body)

    # Format headers with CRLF line endings
    header_str = msg.as_string().split("\n\n", 1)[0].replace("\n", "\r\n") + "\r\n\r\n"
    return header_str + body_prefix + body


def send_smtp_message(recipients, raw_message, smtp_host=SMTP_HOST, smtp_port=SMTP_PORT,
                      smtp_user=SMTP_USER, smtp_pw=SMTP_PW, mailing_domain=MAILING_DOMAIN,
                      mailing_list=MAILING_LIST):
    """Connects to SMTP host via SSL and sends the message to recipient addresses."""
    try:
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
