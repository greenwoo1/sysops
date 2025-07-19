#!/usr/bin/env python3

import subprocess
import time
import re
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_user_input():
    """Gets the necessary input from the user."""
    main_server = input("Enter the main server IP: ")
    backup_servers = input("Enter backup server IPs (comma-separated): ").split(',')
    domains = input("Enter domain names (comma-separated): ").split(',')
    return main_server, backup_servers, domains

def run_remote_command(server, command, user="root"):
    """Runs a command on a remote server via SSH."""
    ssh_command = ["ssh", f"{user}@{server}", command]
    try:
        logging.info(f"Running command '{' '.join(ssh_command)}'")
        result = subprocess.run(ssh_command, check=True, capture_output=True, text=True)
        logging.info(f"Successfully ran '{command}' on {server}")
        return result
    except subprocess.CalledProcessError as e:
        logging.error(f"Error running command on {server}: {e}")
        logging.error(f"Stderr: {e.stderr}")
        exit(1)

def stop_bind_on_backups(backup_servers):
    """Stops the BIND service on backup servers."""
    for server in backup_servers:
        run_remote_command(server, "systemctl stop bind9.service")

def issue_certificate(main_server, domains):
    """Issues a certificate using acme.sh and returns the TXT records."""
    domain_args = " -d " + " -d ".join(domains)
    command = f" -u acme /home/acme/bin/acme.sh --issue --dns{domain_args} --keylength 2048 --yes-I-know-dns-manual-mode-enough-go-ahead-please"

    result = run_remote_command(main_server, command, user="acme")
    txt_records = re.findall(r"Domain: '([^']+)'.*?TXT value: '([^']+)'", result.stdout, re.DOTALL)
    if not txt_records:
        logging.error("Could not find TXT records in acme.sh output.")
        exit(1)
    return txt_records

def update_dns_records(main_server, txt_records):
    """Updates the DNS records on the main server."""
    for domain, txt_value in txt_records:
        zone_file_path = f"/floppy/var/cache/bind/{domain}.db"

        txt_record_line = f"_acme-challenge.{domain}. IN TXT \"{txt_value}\"\n"
        command = f"echo '{txt_record_line}' >> {zone_file_path}"
        run_remote_command(main_server, command)

        serial_update_command = f"sed -i 's/\\([0-9]\\+\\) ; serial/$(date +%Y%m%d%H) ; serial/' {zone_file_path}"
        run_remote_command(main_server, serial_update_command)

    run_remote_command(main_server, "rndc flush")
    run_remote_command(main_server, "rndc reload")

def verify_dns_propagation(domains, txt_records):
    """Verifies that the DNS records have propagated."""
    logging.info("Waiting for 60 seconds for DNS propagation...")
    time.sleep(60)

    for domain, expected_txt in txt_records:
        fqdn = f"_acme-challenge.{domain}"
        try:
            logging.info(f"Verifying TXT record for {fqdn}")
            result = subprocess.run(['dig', '@8.8.8.8', fqdn, 'TXT', '+short'], check=True, capture_output=True, text=True)
            retrieved_txt = result.stdout.strip().replace('"', '')
            if retrieved_txt == expected_txt:
                logging.info(f"Successfully verified TXT record for {fqdn}")
            else:
                logging.error(f"Error: TXT record mismatch for {fqdn}")
                logging.error(f"Expected: {expected_txt}")
                logging.error(f"Got: {retrieved_txt}")
                exit(1)
        except subprocess.CalledProcessError as e:
            logging.error(f"Error verifying TXT record for {fqdn}: {e}")
            exit(1)

def renew_certificate(main_server, domains):
    """Renews the certificate using acme.sh."""
    domain_args = " -d " + " -d ".join(domains)
    command = f" -u acme /home/acme/bin/acme.sh --renew --dns{domain_args} --keylength 2048 --yes-I-know-dns-manual-mode-enough-go-ahead-please"

    result = run_remote_command(main_server, command, user="acme")
    if "Cert success" not in result.stdout:
        logging.error("Error: Certificate renewal failed.")
        logging.error(f"Stdout: {result.stdout}")
        logging.error(f"Stderr: {result.stderr}")
        exit(1)
    logging.info("Certificate renewed successfully.")

def reload_nginx(main_server):
    """Reloads the Nginx service on the main server."""
    run_remote_command(main_server, "nginx -t")
    run_remote_command(main_server, "nginx -s reload")

def check_bind_status(server):
    """Checks the status of the BIND service on a server."""
    try:
        result = run_remote_command(server, "systemctl is-active bind9.service")
        return result.stdout.strip() == "active"
    except subprocess.CalledProcessError:
        return False

def start_bind_on_backups(backup_servers):
    """Starts the BIND service on backup servers."""
    for server in backup_servers:
        run_remote_command(server, "systemctl start bind9.service")

if __name__ == "__main__":
    try:
        main_server, backup_servers, domains = get_user_input()
        if not check_bind_status(main_server):
            logging.error(f"BIND is not running on the main server ({main_server}). Please start it and try again.")
            exit(1)

        stop_bind_on_backups(backup_servers)

        try:
            txt_records = issue_certificate(main_server, domains)
            update_dns_records(main_server, txt_records)
            verify_dns_propagation(domains, txt_records)
            renew_certificate(main_server, domains)
            reload_nginx(main_server)
        finally:
            start_bind_on_backups(backup_servers)

        logging.info("Certificate renewal process completed successfully!")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        exit(1)
