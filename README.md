# PicoLisp Mailing List Service

This repository provides a Python 3 service to manage and process mailing list subscriptions and incoming emails from a spool file.

## Attribution & Credits

This project is a Python port based on the original PicoLisp mailing list manager (`mailing.l`) created by Alexander Burger / Software Lab ([PicoLisp Project](https://picolisp.com)).

## Non-Root Execution & Username Derivation

For security, this service is designed to run as a non-privileged system user rather than `root`.

The service username is derived from the spool file path (`SPOOL_FILE = "/var/mail/picolisp"` in `mailing.py`), taking the filename component: `picolisp`.

## Systemd Installation Guide

Follow these steps to set up and run the mailing list service under systemd as a non-root user:

### 1. Create System User and Group

Create a dedicated system user and group named `picolisp`:

```bash
sudo useradd --system --user-group --shell /usr/sbin/nologin picolisp
```

### 2. Deploy Application Files

Copy the application directory to `/opt/mailing` (or your preferred location, adjusting `WorkingDirectory` and `ExecStart` in `mailing.service` accordingly):

```bash
sudo mkdir -p /opt/mailing
sudo cp mailing.py Mailings /opt/mailing/
sudo chown -R picolisp:picolisp /opt/mailing
sudo chmod 700 /opt/mailing
```

### 3. Set Up Spool File Permissions

Ensure the mail spool directory and file exist and are accessible by the `picolisp` user:

```bash
sudo touch /var/mail/picolisp
sudo chown picolisp:picolisp /var/mail/picolisp
sudo chmod 600 /var/mail/picolisp
```

### 4. Install and Enable systemd Service

Copy the systemd unit file to `/etc/systemd/system/`, reload the systemd manager configuration, enable, and start the service:

```bash
sudo cp mailing.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now mailing.service
```

### 5. Managing the Service

* **Check service status:**
  ```bash
  sudo systemctl status mailing.service
  ```

* **View service logs:**
  ```bash
  journalctl -u mailing.service -f
  ```

* **Restart service:**
  ```bash
  sudo systemctl restart mailing.service
  ```
