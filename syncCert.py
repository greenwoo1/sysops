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

    def update_nginx(self, reserv_ips):
        print("Checking NGINX configuration and reloading on reserv servers...")

        for ip in reserv_ips:
            try:
                # Check NGINX configuration
                check_command = ["ssh", f"root@{ip}", "nginx", "-t"]
                check_result = subprocess.run(check_command, capture_output=True, text=True)

                if check_result.returncode == 0:
                    print(f"NGINX configuration on {ip} is valid.")
                    # Reload NGINX
                    reload_command = ["ssh", f"root@{ip}", "nginx", "-s", "reload"]
                    reload_result = subprocess.run(reload_command, check=True)
                    print(f"Successfully reloaded NGINX on {ip}.")
                else:
                    print(f"NGINX configuration on {ip} is invalid. Skipping reload.")
                    print(f"Error: {check_result.stderr}")

            except subprocess.CalledProcessError as e:
                print(f"An error occurred on {ip}. Error: {e}")
            except Exception as e:
                print(f"An unexpected error occurred on {ip}. Error: {e}")


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
    sync.update_nginx(reserv_ips)
