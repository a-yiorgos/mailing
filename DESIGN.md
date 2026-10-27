# Architecture & Design Specifications

This document outlines the architectural decisions, design patterns, and operational constraints implemented in the Python 3 Mailing List Service (`mailing.py`).

---

## 1. High-Level Architecture & Background

### 1.1 Legacy Transition & Software Foundation
The mailing list manager was originally implemented in PicoLisp (`mailing.l`). It has been completely re-architected into a modern, pure Python 3 daemon (`mailing.py`).

- **Language:** Python 3.12+ standard library (`mailbox`, `email`, `smtplib`, `logging`). No external third-party package dependencies.
- **Legacy Code (`mailing.l`):** Preserved strictly for historical reference. The system operates exclusively on `mailing.py`.
- **Attribution:** Based on the original PicoLisp mailing list manager designed by Alexander Burger / Software Lab ([PicoLisp Project](https://picolisp.com)).

---

## 2. Infrastructure & Mail Pipeline

```
┌──────────────┐     ┌──────────────────┐     ┌──────────────────┐     ┌────────────────┐
│ Incoming     │     │ Postfix MTA      │     │ mailing.py       │     │ Outbound       │
│ SMTP Email   │ ──> │ Mail Spool       │ ──> │ Processing Loop  │ ──> │ Amazon SES     │
└──────────────┘     │ (/var/mail/...)  │     │ (Every 240s)     │     │ (SMTP SSL/465) │
                     └──────────────────┘     └──────────────────┘     └────────────────┘
```

### 2.1 Ingestion Model
- **Reception:** Postfix receives incoming messages for the domain and appends them to the system mail spool at `/var/mail/picolisp`.
- **Parsing:** The daemon uses standard library `mailbox.mbox` (via temporary spool file abstraction) to parse standard Unix mbox streams.
- **Spool Lifecycle:**
  1. Spool presence and size checked.
  2. Mbox structure validated (ensuring initial non-empty line begins with `From `).
  3. Individual messages parsed into message data structures.
  4. Spool file truncated (`open(spool_file, "w").close()`) following batch processing.

### 2.2 Outbound Delivery Model
- **Transport:** Outbound messages are delivered over SMTP via SSL (`smtplib.SMTP_SSL`) on port `465` (e.g. Amazon SES or relay server `smtp.example.com`).
- **HELO Handshake:** HELO/EHLO domain configured via `MAILING_DOMAIN` (`example.com`).

---

## 3. Process Execution & Security

### 3.1 Non-Root Execution Strategy
For principle of least privilege:
- **System User:** Service runs under a non-privileged system user (`picolisp`) and group (`picolisp`).
- **Username Derivation:** User name is derived directly from the spool file path (`SPOOL_FILE = "/var/mail/picolisp"` -> `picolisp`).
- **File System Permissions:**
  - Spool file (`/var/mail/picolisp`): `600` ownership `picolisp:picolisp`.
  - Application directory (`/opt/mailing`): `700` ownership `picolisp:picolisp`.

### 3.2 Systemd Integration
Managed via systemd unit file (`mailing.service`):
- `Type=simple`
- `Restart=always` with 10-second delay (`RestartSec=10`).
- Standard output (`stdout`) captured directly into `journalctl`.

---

## 4. Message Integrity & MIME Compliance

### 4.1 Header Formatting
Outgoing header construction strictly enforces RFC 5322 and RFC 2369 standards:
- **`From:` Header:** Rewritten to `"{GECOS or LHS} via {mailing_list}" <{mailing_list}>`.
  - Display name prefers GECOS / real name if present; falls back to the left-hand side (LHS) of the sender's email address.
- **`X-Original-From:` Header:** Preserves original `From:` line or envelope sender.
- **`Sender:` Header:** Set to sender's address.
- **`Reply-To:` Header:** Configurable via global `REPLY_TO_LIST` boolean setting:
  - If `True` (default): Set to mailing list address (`MAILING_LIST`).
  - If `False`: Retains original sender address.
- **`List-Subscribe` / `List-Unsubscribe` Headers:** Standard headers appended (`<mailto:{mailing_list}?subject=Subscribe>`, etc.).

### 4.2 Body & Payload Preservation
- **No Body Footers:** Subscription or unsubscription instructions are never appended to message bodies. List management instructions reside solely in headers (`List-Unsubscribe`).
- **MIME Integrity:** Multipart boundaries, HTML bodies, attachments, and line encodings are preserved without modification using `copy.deepcopy` of standard `email.message.Message` objects.
- **Line Endings:** All outgoing formatted raw messages strictly enforce standard CRLF (`\r\n`) line endings.

---

## 5. Access Control & Membership Management

### 5.1 Closed List Authorization
- Subscriptions are persisted in plain-text file `Mailings` (one email address per line).
- Incoming non-member messages (not subject to `Subscribe`) are silently rejected and logged without notification.

### 5.2 Administrative Commands
- Messages with case-insensitive `Subject: Subscribe` or `Subject: Unsubscribe`:
  - `Subscribe`: Adds envelope sender address (`from_env`) to `Mailings`.
  - `Unsubscribe`: Removes envelope sender address (`from_env`) from `Mailings`.
- **Privacy Policy:** Auto-response confirmation messages (welcome/farewell) are sent **only** to the individual requesting user, never broadcast to list members.

---

## 6. Observability & Logging Specs

Logging uses Python's `logging` module configured to `sys.stdout`.

- **Event Format:** `** YYYY-MM-DD HH:MM:SS <sender_email> <accepted|discarded>`
- **SMTP/Mbox Errors:** Prefixed with `!! ` (e.g., `!! Can't connect to SMTP server`, `!! Bad mbox file`).
