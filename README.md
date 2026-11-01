# Mailing List Manager - Python Rewrite

This is a faithful Python rewrite of the original Picolisp mailing list manager (`mailing.l`) by Alexander Burger.

## Overview

A simple mailing list manager that:
- Monitors a mail spool file (mbox format)
- Processes incoming emails
- Handles subscribe/unsubscribe requests
- Forwards emails to all subscribers via SMTP

## Configuration

Edit the configuration variables at the top of `mailing.py`:
- `MAILING_LIST`: The mailing list email address
- `SPOOL_FILE`: Path to the mail spool file (typically `/var/mail/<username>`)
- `MAILING_DOMAIN`: Domain for HELO command
- `SMTP_HOST`: SMTP server hostname
- `SMTP_PORT`: SMTP server port (465 for SSL)
- `SMTP_USER`: SMTP authentication username
- `SMTP_PW`: SMTP authentication password

## Requirements

- Python 3.6+ (uses only standard library modules)
- No external dependencies required

## Installation

### Using Virtual Environment (Recommended)

```bash
# Create and activate virtual environment
./setup_venv.sh

# Or manually:
python3 -m venv venv
source venv/bin/activate
```

## Usage

### Running the Mailing List Manager

```bash
# Direct execution
python3 mailing.py

# With virtual environment
source venv/bin/activate
python mailing.py
```

The script runs continuously, checking the spool file every 4 minutes.

### Subscribing

Send an email to the mailing list address with the subject `subscribe`.

### Unsubscribing

Send an email to the mailing list address with the subject `unsubscribe`.

Or click the unsubscribe link in the email footer.

## Files

- `mailing.py`: Main mailing list manager script
- `Mailings`: List of subscribers (auto-generated, one email per line)
- `Mailings.example`: Example format for Mailings file
- `requirements.txt`: Lists dependencies (currently only standard library)
- `.gitignore`: Git ignore patterns
- `setup_venv.sh`: Helper script to create virtual environment

## Behavior

1. **Incoming Email Processing**:
   - Emails from non-subscribers are discarded (unless subject is "subscribe")
   - Emails from mailer-daemon are ignored
   - Valid emails are forwarded to all subscribers

2. **Subscribe Request**:
   - Sender is added to the Mailings file
   - Confirmation email is sent

3. **Unsubscribe Request**:
   - Sender is removed from the Mailings file
   - Confirmation email is sent

4. **Email Forwarding**:
   - Original headers are preserved
   - Footer with unsubscribe link is added
   - All subscribers receive the email

## Security Notes

- The `Mailings` file contains email addresses and is excluded from git
- The SMTP password is stored in plain text in the script (consider using environment variables in production)
- The script uses SSL for SMTP connections

## Differences from Original Picolisp Version

- Uses Python's standard library instead of Picolisp built-ins
- Socket handling uses Python's `socket` and `ssl` modules
- Base64 encoding uses Python's `base64` module
- File I/O uses standard Python file operations
- Maintains the same logic flow and functionality

## License

This is a rewrite of the original Picolisp code. The original code is copyright Alexander Burger, Software Lab.
