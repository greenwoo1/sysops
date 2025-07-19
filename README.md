# 🔐 ACME DNS Certificate Renewal Script

This Python script automates TLS/SSL certificate renewal using [`acme.sh`](https://github.com/acmesh-official/acme.sh) in manual DNS mode. It's designed for an infrastructure where a **main server** manages DNS zones, and one or more **backup servers** run BIND (`bind9`).

---

## ✨ Features

- Interactive CLI prompts:
  - Main server IP/hostname
  - Backup server IPs (can be multiple)
  - List of domains to renew certificates for
- Connects to **backup servers** and stops `bind9` service
- Connects to **main server**, switches to `acme` user, and runs `acme.sh --issue` in manual DNS mode
- Parses required `_acme-challenge` TXT records from output
- Edits zone files:
  - `/floppy/var/cache/bind/dom`
  - `/floppy/var/cache/bind/dom_NA`
  - Appends new TXT records
  - Updates zone serial (format: `YYYYMMDDHH`)
- Runs `rndc flush` and `rndc reload` on main server
- Waits 60 seconds for DNS propagation
- Verifies DNS TXT records via `dig`
- If all records match — runs `acme.sh --renew`
- Validates nginx configuration (`nginx -t`)
- Reloads nginx if syntax is OK (`nginx -s reload`)
- Displays errors and halts if any step fails

---

## 📦 Requirements

- Python 3.6+
- `ssh` access to main and backup servers as root
- `acme.sh` installed in `~/bin/` for user `acme` on the main server
- `bind9` (BIND DNS) configured on servers
- Zone files located at `/floppy/var/cache/bind/`
- Passwordless `su - acme` allowed (configured via `sudoers` or `pam`)
- Public SSH keys set up for root access between source machine and remote servers

---

## 🚀 Usage

```bash
sudo python3 renew_cert.py
