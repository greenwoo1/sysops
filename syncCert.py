import subprocess
import os

class Sync:

    def get_main_ip(self):
        main_ip = input("Please enter the IP address of the MAIN server: ")
        return main_ip

    def get_reserv_ip(self):
        reserv_ip = input("Please enter the IP addresses of reserv servers (separated by commas or spaces): ")
        IP_RESERV = [ip.strip() for ip in reserv_ip.replace(',', ' ').split()]
        return IP_RESERV

    def get_domain_name(self):
        domain_name = input("Please enter domain names (separated by commas or spaces): ")
        DOMAIN_NAME = [name.strip() for name in domain_name.replace(',', ' ').split()]
        return DOMAIN_NAME

    def check_container_state(self, reserv_ips):
        print("Checking container state on reserv servers...")

        failed_ips = []

        for ip in reserv_ips:
            try:
                command = ["ssh", f"root@{ip}", "test", "-e", "/dev/mapper/floppy"]
                result = subprocess.run(command, check=True, timeout=30)

                if result.returncode == 0:
                    print(f"Container exists on {ip}")
                else:
                    raise subprocess.CalledProcessError(result.returncode, command)

            except subprocess.TimeoutExpired:
                print(f"Error: Connection to {ip} timed out")
                failed_ips.append(ip)

            except subprocess.CalledProcessError as e:
                print(f"Container not found on {ip}")
                failed_ips.append(ip)

        for failed_ip in failed_ips:
            reserv_ips.remove(failed_ip)

    def get_cert_dir(self, main_ip, domains):
        print("Downloading certificates from the main server...")

        for item in domains:
            try:
                command = ["rsync", "-arvhP", f"root@{main_ip}:/floppy/home/acme/.acme.sh/{item}", "."]
                result = subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print(f"Status: OK for {item}")

            except subprocess.CalledProcessError as e:
                print(f"Status: Failed for {item}. Error: {e}")

    def sync_to_reserv(self, domains, reserv_ips):
        print("Synchronization to reserves")

        for ip in reserv_ips:
            for domain in domains:
                try:
                    command = ["rsync", "-arvhP", f"{domain}", f"root@{ip}:/floppy/home/acme/.acme.sh/"]
                    result = subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    print(f"Status: OK for {domain} on {ip}")

                except subprocess.CalledProcessError as e:
                    print(f"Status: Failed for {domain} on {ip}. Error: {e}")

    def change_owner(self, domains, reserv_ips):
        print("Changing ownership to user 'acme'")

        for ip in reserv_ips:
            for domain in domains:
                try:
                    command = f"ssh root@{ip} 'chown -R acme:acme /floppy/home/acme/.acme.sh/{domain}'"
                    result = subprocess.run(command, check=True, shell=True)
                    print(f"Status: OK on {ip}")

                except subprocess.CalledProcessError as e:
                    print(f"Status: Failed on {ip}. Error: {e}")

    def reload_bind(self, reserv_ips):
        print("Reloading bind9 on reserv servers...")
        
        failed_ips = []

        for ip in reserv_ips:
            try:
                command = ["ssh", f"root@{ip}", "systemctl", "restart", "bind9.service"]
                result = subprocess.run(command, check=True)

                if result.returncode == 0:
                    print(f"Successfully reloaded bind9 on {ip}")
                else:
                    raise subprocess.CalledProcessError(result.returncode, command)

            except subprocess.CalledProcessError as e:
                print(f"Failed to reload bind9 on {ip}. Error: {e}")
                failed_ips.append(ip)

        for failed_ip in failed_ips:
            reserv_ips.remove(failed_ip)

    def check_nginx_conf(self, reserv_ips):
        print("Checking NGINX configuration on reserv servers...")

        failed_ips = []

        for ip in reserv_ips:
            try: 
                command = ["ssh", f"root@{ip}", "nginx", "-t"]
                result = subprocess.run(command, check=True, capture_output=True, text=True)

                stdout = result.stdout.strip()
                stderr = result.stderr.strip()

                if "syntax is ok" in stdout and "test is successful" in stdout:
                    print(f"NGINX configuration is valid on {ip}")
                elif "test failed" in stderr:
                    print(f"Failed to validate NGINX configuration on {ip}. Error: {stderr}")
                    failed_ips.append(ip)
                else:
                    print(f"Unexpected output from NGINX on {ip}. Output: {stdout} {stderr}")

            except subprocess.CalledProcessError as e:
                error_message = e.stderr.strip() if e.stderr else "No error message available"
                print(f"Error executing command on {ip}. Error: {error_message}")
                failed_ips.append(ip)

        for failed_ip in failed_ips:
            reserv_ips.remove(failed_ip)

    def reload_nginx(self, reserv_ips):
        print("Reloading nginx service...")

        for ip in reserv_ips:
            try:
                command = ["ssh", f"root@{ip}", "nginx", "-t"]
                result = subprocess.run(command, check=True, capture_output=True, text=True)
                print(f"Status: OK for {ip}")
            except subprocess.CalledProcessError as e:
                print(f"Error reloading nginx on {ip}. Error: {e.stderr.strip()}")


if __name__ == "__main__":
    sync = Sync()
    main_ip = sync.get_main_ip()
    reserv_ips = sync.get_reserv_ip()
    domains = sync.get_domain_name()

    sync.check_container_state(reserv_ips)
    sync.get_cert_dir(main_ip, domains)
    sync.sync_to_reserv(domains, reserv_ips)
    sync.change_owner(domains, reserv_ips)
    sync.reload_bind(reserv_ips)
    sync.check_nginx_conf(reserv_ips)
    sync.reload_nginx(reserv_ips)

