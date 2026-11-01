# Project: mailing.py

A closed mailing list manager inspired by the PicoLisp `mailing.l` and implemented in Python

## Commands, Tech stack, Coding Style and Conventions:
- The program is written in Python
- If needed, it works via a virtual environment
- It should use as few external dependencies as possible
- The program should be written in a way that systemd can manage it
- Logging should use the Python logger

## Architecture notes
- Email is delivered to the mailbox by Postfix
- Email is sent via Amazon Simple Email Service
- This is a closed mailing list.  Submissions by non-members should be discarded without notifying the sender
