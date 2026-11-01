# Mailing List Manager - Python Rewrite

A faithful Python rewrite of the original Picolisp mailing list manager (`mailing.l`) by Alexander Burger. This implementation provides a simple yet fully functional mailing list system with modern features and improvements.

## Features

### Core Functionality
- Monitors a mail spool file (mbox format) for incoming messages
- Parses email headers and processes messages accordingly
- Forwards emails from subscribers to all list members via SMTP
- Handles subscribe/unsubscribe requests automatically
- Maintains a list of subscribers in a simple text file

### Enhanced Features
- **Proper Email Headers**: Adds standard list headers (List-Id, List-Subscribe, List-Unsubscribe, List-Help, List-Post, List-Owner)
- **Configurable Reply-To**: Option to set Reply-To to list address or sender's address via `REPLY_TO_LIST` boolean
- **From Header with GECOS**: From: address is the list address with sender's name + " via {list_name}" in GECOS field
- **X-Original-From Header**: Preserves original sender information in a custom header
- **No Message Footers**: Original message body remains unaltered

### Subscription Management
- Automatic subscription via email with subject "subscribe"
- Automatic unsubscription via email with subject "unsubscribe"
- List manager receives notifications for all subscription changes
- **Subscription History**: Mailings file tracks subscription and unsubscribe dates

### Logging
- **Systemd-Compatible**: Logs written to stdout for journalctl capture
- **Structured Format**: Each log line includes timestamp, email, and decision (ACCEPT, DISCARD, SUBSCRIBE, UNSUBSCRIBE)
- Format: `YYYY-MM-DD HH:MM:SS <email> <DECISION>`

### SMTP Support
- **Port 465**: Implicit SSL/TLS (traditional SMTP with SSL)
- **Port 587**: STARTTLS support for Amazon SES and other providers
- Automatic detection based on `SMTP_PORT` configuration

### Configuration
All configuration is done via constants at the top of `mailing.py`:
- `MAILING_LIST`: List email address
- `LIST_MANAGER`: Manager email for notifications
- `SPOOL_FILE`: Path to mail spool file
- `MAILING_DOMAIN`: Domain for HELO/EHLO command
- `SMTP_HOST`: SMTP server hostname
- `SMTP_PORT`: SMTP server port (465 for SSL, 587 for STARTTLS)
- `SMTP_USER`: SMTP authentication username
- `SMTP_PW`: SMTP authentication password
- `REPLY_TO_LIST`: Boolean to control Reply-To header (True = list address, False = sender's address)

### Mailings File Format
The `Mailings` file stores subscribers with subscription history:

```
# New subscription
# 2024-01-15
user1@example.com

# User subscribed, then unsubscribed
# 2024-02-20
# user2@example.com
# 2024-03-01 unsubscribed

# User re-subscribed later
# 2024-03-20
user2@example.com
```

- Lines starting with `#` are comments
- Active subscribers: plain email addresses
- Unsubscribed users: commented out email addresses with unsubscribe date
- Subscription dates: comment lines with `YYYY-MM-DD` format
- Re-subscriptions: new entries with new dates (history preserved)
- Pre-existing entries without dates are still supported

## Requirements

- Python 3.6+ (uses only standard library modules)
- No external dependencies required

## Installation

### 1. Clone or Download
```bash
cd /path/to/project
git clone <repository-url>
cd mailing
```

### 2. Configure
Edit the configuration section at the top of `mailing.py`:

```python
# Configuration
MAILING_LIST = "your-list@example.com"
LIST_MANAGER = "manager@example.com"
SPOOL_FILE = "/var/mail/maillist"
MAILING_DOMAIN = "example.com"
SMTP_HOST = "smtp.example.com"  # For Amazon SES: email-smtp.us-east-1.amazonaws.com
SMTP_PORT = 587  # 465 for SSL, 587 for STARTTLS (Amazon SES)
SMTP_USER = "your-smtp-username"
SMTP_PW = "your-smtp-password"
REPLY_TO_LIST = True  # True: Reply-To = list address, False: Reply-To = sender
```

### 3. Create Mailings File
```bash
touch Mailings
chmod 644 Mailings
```

### 4. Set Up Spool File
Ensure the spool file exists and is writable by the mailing list user:
```bash
touch /var/mail/maillist
chmod 660 /var/mail/maillist
```

## Usage

### Manual Execution
```bash
# Test syntax
python3 -m py_compile mailing.py

# Run the mailing list manager
python3 mailing.py

# Run in background with nohup
nohup python3 mailing.py > mailing.log 2>&1 &
```

### Systemd Service
An example systemd service file is provided (`mailing-list.service`):

```bash
# Install the service
sudo cp mailing-list.service /etc/systemd/system/

# Edit the service file to match your paths
sudo nano /etc/systemd/system/mailing-list.service

# Create a dedicated user
sudo useradd -r -s /usr/sbin/nologin mailing-list

# Set permissions
sudo chown mailing-list:mailing-list /var/mail/maillist
sudo chown -R mailing-list:mailing-list /path/to/mailing

# Enable and start the service
sudo systemctl daemon-reload
sudo systemctl enable mailing-list.service
sudo systemctl start mailing-list.service

# Check status
sudo systemctl status mailing-list.service

# View logs
journalctl -u mailing-list.service -f
```

### Subscribing
Send an email to the mailing list address with the subject: `subscribe`

### Unsubscribing
Send an email to the mailing list address with the subject: `unsubscribe`

### Sending to the List
Any subscriber can send an email to the mailing list address, and it will be forwarded to all subscribers.

## Logging

The mailing list manager logs all important events to stdout, which systemd captures:

```
YYYY-MM-DD HH:MM:SS user@example.com ACCEPT
YYYY-MM-DD HH:MM:SS user@example.com DISCARD
YYYY-MM-DD HH:MM:SS user@example.com SUBSCRIBE
YYYY-MM-DD HH:MM:SS user@example.com UNSUBSCRIBE
```

View logs with:
```bash
journalctl -u mailing-list.service
journalctl -u mailing-list.service -f  # Follow logs in real-time
```

## Files

- `mailing.py`: Main mailing list manager script
- `Mailings`: List of subscribers (auto-generated)
- `Mailings.example`: Example format for Mailings file
- `mailing-list.service`: Example systemd service file
- `requirements.txt`: Dependencies (currently only standard library)
- `.gitignore`: Git ignore patterns
- `setup_venv.sh`: Helper to create virtual environment
- `README.md`: This documentation

## Example Email Flow

### Incoming Email from Subscriber
1. Email arrives in spool file
2. Script detects new email
3. Extracts headers (From, Subject, etc.)
4. Checks if sender is in Mailings list
5. If yes: forwards to all subscribers
6. If no and subject is "subscribe": adds to list, sends confirmation
7. If no and subject is "unsubscribe": removes from list, sends confirmation
8. If no and not a subscribe request: discards email

### Forwarded Email Format
```
From: "John Doe via list" <list@example.com>
To: list@example.com
Subject: Original Subject
X-Original-From: John Doe <john@example.com>
Sender: John Doe <john@example.com>
Reply-To: list@example.com  (or john@example.com if REPLY_TO_LIST=False)
List-Id: <list@example.com>
List-Subscribe: <mailto:list@example.com?subject=subscribe>
List-Unsubscribe: <mailto:list@example.com?subject=unsubscribe>
List-Help: <mailto:list@example.com?subject=help>
List-Post: <mailto:list@example.com>
List-Owner: <mailto:list@example.com>

[Original message body]
```

## Configuration Examples

### Amazon SES (Port 587)
```python
SMTP_HOST = "email-smtp.us-east-1.amazonaws.com"
SMTP_PORT = 587
SMTP_USER = "your-ses-smtp-username"
SMTP_PW = "your-ses-smtp-password"
```

### Traditional SMTP with SSL (Port 465)
```python
SMTP_HOST = "smtp.your-provider.com"
SMTP_PORT = 465
SMTP_USER = "your-username"
SMTP_PW = "your-password"
```

### Reply-To Set to Sender
```python
REPLY_TO_LIST = False  # Replies go to the original sender
```

## Security Notes

- SMTP passwords are stored in plain text in the script
- Consider using environment variables for production
- The Mailings file contains email addresses
- Use appropriate file permissions
- The script runs as a dedicated user with minimal privileges

## Differences from Original Picolisp Version

- Python implementation using standard library
- Added list headers (List-Id, List-Subscribe, etc.)
- Configurable Reply-To behavior
- Support for port 587 with STARTTLS
- Structured logging for systemd
- Subscription history tracking
- Proper GECOS handling in From: header
- X-Original-From header preservation
- No message footer (uses headers instead)

## License

This is a rewrite of the original Picolisp code. The original code is copyright Alexander Burger, Software Lab.

## Contributing

This implementation was created as a faithful rewrite with enhancements. Contributions are welcome.
