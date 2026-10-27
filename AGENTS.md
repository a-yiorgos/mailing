# Repository Instructions for AI Agents (Jules)

## Core Directive
This repository contains a modernized Python 3 mailing list daemon (`mailing.py`) that has fully replaced a legacy PicoLisp implementation. 

## Strict Constraints & Guidelines

### 1. Ignore Legacy PicoLisp Code (`mailing.l`)
- **Do not read, parse, or reference `mailing.l`**. 
- The PicoLisp file (`mailing.l`) is preserved purely for historical/archival reasons. It must not be consulted, ported from, or updated under any circumstances. All future enhancements, bug fixes, or refactoring must be performed strictly within the modern Python implementation.

### 2. Architecture & Runtime Rules
- **Language:** Python 3 only.
- **Reception:** Incoming email is always received and placed on file via Postfix.
- **Delivery:** Outbound email routing uses Amazon SES via SSL (`smtplib.SMTP_SSL`) on port `465`.
- **MIME & Body Integrity:** Do not mutate or append text strings to the email body. Use the `List-Unsubscribe` header instead of body footers.
- **Privacy Policy:** Administrative commands (`subscribe` / `unsubscribe`) must never broadcast notifications to the mailing list; replies must be sent exclusively to the requesting user and the list administrator.

### 3. Access Control
- The mailing list is closed. Unauthorized mail from non-members must be silently discarded and logged.
- `subscribe` or `unsubscribe` requests should also be logged.
