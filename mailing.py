#!/usr/bin/env python3
# Mailing list manager - Python rewrite of mailing.l
# Original Picolisp code by Alexander Burger

import os
import sys
import time
import socket
import ssl
import base64
from pathlib import Path

# Configuration
MAILING_LIST = "list@example.com"
LIST_MANAGER = "manager@example.com"
SPOOL_FILE = "/var/mail/maillist"
MAILING_DOMAIN = "example.com"
SMTP_HOST = "mail.example.com"
SMTP_PORT = 465  # Port 465 for SSL, or 587 for STARTTLS (Amazon SES)
SMTP_USER = "list@example.com"
SMTP_PW = "password"
REPLY_TO_LIST = True

# Load mailings (subscribers) from Mailings file
MAILINGS_FILE = "Mailings"

def load_mailings():
    """Load subscriber list from Mailings file"""
    mailings = []
    if os.path.exists(MAILINGS_FILE):
        with open(MAILINGS_FILE, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    mailings.append(line)
    return mailings

def save_mailings(mailings):
    """Save subscriber list to Mailings file"""
    with open(MAILINGS_FILE, 'w') as f:
        for email in mailings:
            f.write(email + '\n')

def log_message(msg, prefix='** '):
    """Print a message with prefix"""
    print(f"{prefix}{msg}")

def log_error(msg):
    """Print an error message"""
    print(f"!! {msg}", file=sys.stderr)

def get_file_size(filepath):
    """Get file size"""
    try:
        return os.path.getsize(filepath)
    except OSError:
        return 0

def parse_headers(file_obj):
    """Parse email headers from file object"""
    headers = {
        'From': None,
        'Subject': None,
        'Date': None,
        'Message-ID': None,
        'In-Reply-To': None,
        'MIME-Version': None,
        'Content-Type': None,
        'Content-Transfer-Encoding': None,
        'Content-Disposition': None,
        'User-Agent': None,
        'Src': None
    }
    
    # Skip first line (From in mbox format)
    first_line = file_obj.readline()
    if not first_line.startswith('From '):
        return None, "Bad mbox file"
    
    # Read blank line after From
    file_obj.readline()
    
    current_header = None
    current_value = None
    
    while True:
        line = file_obj.readline()
        if not line or line.strip() == '':
            break
        
        # Check for continuation line (starts with space or tab)
        if line[0] in (' ', '\t'):
            if current_header:
                current_value += ' ' + line.strip()
            continue
        
        # Parse header line
        if ':' in line:
            # Save previous header
            if current_header and current_value is not None:
                headers[current_header] = current_value.strip()
            
            # Parse new header
            parts = line.split(':', 1)
            current_header = parts[0].strip()
            current_value = parts[1].strip()
        else:
            # Not a header line, break
            break
    
    # Save last header
    if current_header and current_value is not None:
        headers[current_header] = current_value.strip()
    
    # Map to variable names used in original
    headers['Src'] = headers.get('From', '')
    headers['From'] = headers.get('From', '')
    
    return headers, None

def read_email_body(file_obj):
    """Read the email body"""
    body = []
    while True:
        line = file_obj.readline()
        if not line:
            break
        body.append(line)
    return ''.join(body)

def send_email_via_smtp(to_addrs, from_addr, headers, body, is_subscribe=False, is_unsubscribe=False, to_email=None):
    """Send email via SMTP with SSL or STARTTLS"""
    
    # Connect to SMTP server
    try:
        sock = socket.create_connection((SMTP_HOST, SMTP_PORT))
        sock_file = sock.makefile('rb')
        
        # Read welcome message
        welcome = sock_file.readline().decode('utf-8', errors='ignore')
        if not welcome.startswith('220 '):
            log_error(f"Unexpected SMTP welcome: {welcome}")
            sock.close()
            return False
        
        # For port 587, use STARTTLS; for port 465, use implicit SSL
        if SMTP_PORT == 587:
            # Send EHLO
            sock.sendall(f"EHLO {MAILING_DOMAIN}\r\n".encode())
            response = sock_file.readline().decode('utf-8', errors='ignore')
            if not response.startswith('250 '):
                log_error(f"EHLO failed: {response}")
                sock.close()
                return False
            
            # Issue STARTTLS command
            sock.sendall(b"STARTTLS\r\n")
            response = sock_file.readline().decode('utf-8', errors='ignore')
            if not response.startswith('220 '):
                log_error(f"STARTTLS failed: {response}")
                sock.close()
                return False
            
            # Wrap socket with SSL
            context = ssl.create_default_context()
            ssl_sock = context.wrap_socket(sock, server_hostname=SMTP_HOST)
            sock_file = ssl_sock.makefile('rb')
            
            # Re-send EHLO after STARTTLS
            ssl_sock.sendall(f"EHLO {MAILING_DOMAIN}\r\n".encode())
            response = sock_file.readline().decode('utf-8', errors='ignore')
            if not response.startswith('250 '):
                log_error(f"EHLO after STARTTLS failed: {response}")
                ssl_sock.close()
                return False
        else:
            # Port 465: implicit SSL
            context = ssl.create_default_context()
            ssl_sock = context.wrap_socket(sock, server_hostname=SMTP_HOST)
            sock_file = ssl_sock.makefile('rb')
            
            # Send HELO for implicit SSL
            ssl_sock.sendall(f"HELO {MAILING_DOMAIN}\r\n".encode())
            response = sock_file.readline().decode('utf-8', errors='ignore')
            if not response.startswith('250 '):
                log_error(f"HELO failed: {response}")
                ssl_sock.close()
                return False
    except Exception as e:
        log_error(f"Can't connect to SMTP server: {e}")
        try:
            sock.close()
        except:
            pass
        return False
    
    try:
        # Authentication
        auth_string = f"\x00{SMTP_USER}\x00{SMTP_PW}"
        auth_base64 = base64.b64encode(auth_string.encode()).decode()
        
        ssl_sock.sendall(f"AUTH PLAIN {auth_base64}\r\n".encode())
        response = ssl_sock.makefile('rb').readline().decode('utf-8', errors='ignore')
        if not response.startswith('235 '):
            log_error(f"AUTH failed: {response}")
            return False
        
        # Send MAIL FROM
        ssl_sock.sendall(f"MAIL FROM:<{MAILING_LIST}>\r\n".encode())
        response = ssl_sock.makefile('rb').readline().decode('utf-8', errors='ignore')
        if not response.startswith('250 '):
            log_error(f"MAIL FROM failed: {response}")
            return False
        
        # Send RCPT TO for each recipient
        for to_addr in to_addrs:
            ssl_sock.sendall(f"RCPT TO:<{to_addr}>\r\n".encode())
            response = ssl_sock.makefile('rb').readline().decode('utf-8', errors='ignore')
            if not response.startswith('250 '):
                log_message(f"{to_addr} can't mail")
        
        # Send DATA
        ssl_sock.sendall(b"DATA\r\n")
        response = ssl_sock.makefile('rb').readline().decode('utf-8', errors='ignore')
        if not response.startswith('354 '):
            log_error(f"DATA command failed: {response}")
            return False
        
        # Build message
        message = b""
        
        # From header
        src = headers.get('Src', from_addr)
        
        # Extract list name from MAILING_LIST (local part before @)
        list_name = MAILING_LIST.split('@')[0]
        
        # Parse original From to get name (GECOS) and email
        original_from = src or from_addr
        geos = None
        original_email = None
        if '<' in original_from and '>' in original_from:
            geos = original_from.split('<')[0].strip()
            original_email = original_from.split('<')[1].split('>')[0].strip()
        else:
            # No GECOS, use local part of email
            if '@' in original_from:
                original_email = original_from
                geos = original_from.split('@')[0]
            else:
                original_email = original_from
                geos = original_from
        
        # Build new GECOS with " via {list_name}"
        if geos and geos.strip():
            new_gecos = f"{geos} via {list_name}"
        else:
            # Fallback: use local part of original email
            local_part = original_email.split('@')[0] if '@' in original_email else original_email
            new_gecos = f"{local_part} via {list_name}"
        
        # From: uses list address with modified GECOS
        message += f"From: {new_gecos} <{MAILING_LIST}>\r\n".encode()
        
        # Add X-Original-From header
        message += f"X-Original-From: {original_from}\r\n".encode()
        
        message += f"Sender: {src or from_addr}\r\n".encode()
        reply_to = MAILING_LIST if REPLY_TO_LIST else (src or from_addr)
        message += f"Reply-To: {reply_to}\r\n".encode()
        message += f"To: {to_email or MAILING_LIST}\r\n".encode()
        
        # Subject
        subject = headers.get('Subject', '')
        message += f"Subject: {subject}\r\n".encode()
        
        # Other headers
        for header_name in ['Date', 'Message-ID', 'In-Reply-To', 'MIME-Version', 
                           'Content-Type', 'Content-Transfer-Encoding', 
                           'Content-Disposition', 'User-Agent']:
            value = headers.get(header_name)
            if value:
                message += f"{header_name}: {value}\r\n".encode()
        
        # List headers
        message += f"List-Id: <{MAILING_LIST}>\r\n".encode()
        message += f"List-Subscribe: <mailto:{MAILING_LIST}?subject=subscribe>\r\n".encode()
        message += f"List-Unsubscribe: <mailto:{MAILING_LIST}?subject=unsubscribe>\r\n".encode()
        message += f"List-Help: <mailto:{MAILING_LIST}?subject=help>\r\n".encode()
        message += f"List-Post: <mailto:{MAILING_LIST}>\r\n".encode()
        message += f"List-Owner: <mailto:{MAILING_LIST}>\r\n".encode()
        
        message += b"\r\n"
        
        # Body based on subject
        if is_subscribe:
            message += f"Hello {src or from_addr} :-)\r\n".encode()
            message += b"You are now subscribed\r\n"
            message += b"****\r\n\r\n"
        elif is_unsubscribe:
            message += f"Good bye {src or from_addr} :-(\r\n".encode()
            message += b"You are now unsubscribed\r\n"
            message += b"****\r\n\r\n"
        else:
            # Original message body
            message += body.encode('utf-8', errors='replace')
        
        # End of DATA
        message += b".\r\n"
        
        ssl_sock.sendall(message)
        
        # Read response
        response = ssl_sock.makefile('rb').readline().decode('utf-8', errors='ignore')
        
        # Send QUIT
        ssl_sock.sendall(b"QUIT\r\n")
        response = ssl_sock.makefile('rb').readline().decode('utf-8', errors='ignore')
        
        return True
        
    finally:
        ssl_sock.close()

def process_spool_file(spool_path, mailings):
    """Process the mail spool file"""
    
    if not os.path.exists(spool_path):
        return mailings
    
    file_size = get_file_size(spool_path)
    if file_size == 0:
        return mailings
    
    try:
        with open(spool_path, 'r') as f:
            while True:
                # Check if we're at the end
                pos = f.tell()
                if pos >= file_size:
                    break
                
                # Parse email
                headers, error = parse_headers(f)
                if error:
                    log_error(error)
                    break
                
                if headers is None:
                    break
                
                from_addr = headers.get('From', '').lower()
                subject = headers.get('Subject', '').lower()
                
                # Skip mailer-daemon
                if from_addr == 'mailer-daemon':
                    continue
                
                # Check if this is a subscribe request
                if subject == 'subscribe':
                    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                    if from_addr not in mailings:
                        mailings.append(from_addr)
                        save_mailings(mailings)
                        log_message(f"{timestamp} {from_addr} SUBSCRIBE")
                    
                    # Send confirmation to user
                    send_email_via_smtp(
                        [from_addr], 
                        from_addr, 
                        headers, 
                        "", 
                        is_subscribe=True,
                        to_email=from_addr
                    )
                    # Notify list manager
                    send_email_via_smtp(
                        [LIST_MANAGER],
                        from_addr,
                        {'Subject': f'Subscription notification for {from_addr}'},
                        f"{from_addr} has subscribed to the mailing list.",
                        to_email=LIST_MANAGER
                    )
                    continue
                
                # Check if this is an unsubscribe request
                if subject == 'unsubscribe':
                    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                    if from_addr in mailings:
                        mailings.remove(from_addr)
                        save_mailings(mailings)
                        log_message(f"{timestamp} {from_addr} UNSUBSCRIBE")
                    
                    # Send confirmation to user
                    send_email_via_smtp(
                        [from_addr], 
                        from_addr, 
                        headers, 
                        "", 
                        is_unsubscribe=True,
                        to_email=from_addr
                    )
                    # Notify list manager
                    send_email_via_smtp(
                        [LIST_MANAGER],
                        from_addr,
                        {'Subject': f'Unsubscription notification for {from_addr}'},
                        f"{from_addr} has unsubscribed from the mailing list.",
                        to_email=LIST_MANAGER
                    )
                    continue
                
                # Check if sender is in mailing list
                if from_addr not in mailings:
                    # Discard email from non-subscriber
                    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                    log_message(f"{timestamp} {from_addr} DISCARD")
                    continue
                
                # Process valid email
                timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                log_message(f"{timestamp} {from_addr} ACCEPT")
                
                # Read body
                body = read_email_body(f)
                
                # Send to all subscribers
                send_email_via_smtp(
                    mailings, 
                    from_addr, 
                    headers, 
                    body
                )
        
        # Truncate the spool file (simulate rewind)
        with open(spool_path, 'w') as f:
            pass
        
    except Exception as e:
        log_error(f"Error processing spool: {e}")
    
    return mailings

def main():
    """Main function - mailing list processor"""
    
    # Load initial mailings
    mailings = load_mailings()
    
    log_message("Starting mailing list processor")
    
    # Main loop
    while True:
        try:
            # Process spool file
            mailings = process_spool_file(SPOOL_FILE, mailings)
            
            # Wait 4 minutes (matching original: (* 4 60 1000) = 240000 ms = 4 min)
            time.sleep(240)
            
        except KeyboardInterrupt:
            log_message("Shutting down")
            break
        except Exception as e:
            log_error(f"Main loop error: {e}")
            time.sleep(60)  # Wait before retrying

if __name__ == "__main__":
    main()
