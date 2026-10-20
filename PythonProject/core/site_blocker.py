import ctypes
import os
import subprocess
import logging


class SiteBlocker:
    HOSTS_PATH = r"C:\Windows\System32\drivers\etc\hosts"
    REDIRECT_IP = "127.0.0.1"
    BLOCK_START_MARKER = "# === DeepFocus Block Start ==="
    BLOCK_END_MARKER = "# === DeepFocus Block End ==="

    def __init__(self):
        self._is_blocking = False
        self._blocked_sites: list[str] = []

    @staticmethod
    def is_admin() -> bool:
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False

    def block(self, sites: list[str]) -> bool:
        from utils.validation import blocklist
        sites = blocklist(sites, "website")
        if not self.is_admin():
            print("Warning: Admin privileges required to block sites.")
            return False

        try:
            if not self.unblock():
                return False
            
            # Auto-expand: for each site, also block the www. variant
            expanded_sites = []
            for site in sites:
                site = site.strip().lower()
                if not site:
                    continue
                expanded_sites.append(site)
                if not site.startswith("www."):
                    expanded_sites.append(f"www.{site}")
            
            with open(self.HOSTS_PATH, 'r') as f:
                content = f.read()
            
            if not content.endswith('\n'):
                content += '\n'
            
            content += f"{self.BLOCK_START_MARKER}\n"
            for site in expanded_sites:
                content += f"{self.REDIRECT_IP} {site}\n"
            content += f"{self.BLOCK_END_MARKER}\n"
            
            with open(self.HOSTS_PATH, 'w') as f:
                f.write(content)
                
            self._flush_dns()
            self._is_blocking = True
            self._blocked_sites = expanded_sites
            return True
        except Exception as e:
            logging.getLogger(__name__).exception("Could not block websites")
            return False

    def unblock(self) -> bool:
        try:
            if not os.path.exists(self.HOSTS_PATH):
                return True

            with open(self.HOSTS_PATH, 'r') as f:
                lines = f.readlines()

            if not any(line.strip() == self.BLOCK_START_MARKER for line in lines):
                self._is_blocking = False
                self._blocked_sites = []
                return True

            if sum(line.strip() == self.BLOCK_START_MARKER for line in lines) != sum(line.strip() == self.BLOCK_END_MARKER for line in lines):
                return False
            new_lines = []
            in_block = False
            for line in lines:
                if line.strip() == self.BLOCK_START_MARKER:
                    in_block = True
                    continue
                elif line.strip() == self.BLOCK_END_MARKER:
                    in_block = False
                    continue
                
                if not in_block:
                    new_lines.append(line)

            with open(self.HOSTS_PATH, 'w') as f:
                f.writelines(new_lines)
                
            self._flush_dns()
            self._is_blocking = False
            self._blocked_sites = []
            return True
        except PermissionError:
            print("PermissionError: Administrator privileges required to unblock sites (modify hosts file).")
            return False
        except Exception as e:
            logging.getLogger(__name__).exception("Could not unblock websites")
            return False

    @staticmethod
    def force_unblock() -> None:
        """Standalone emergency tool to remove DeepFocus blocks from hosts file."""
        try:
            if not os.path.exists(SiteBlocker.HOSTS_PATH):
                return

            with open(SiteBlocker.HOSTS_PATH, 'r') as f:
                lines = f.readlines()

            new_lines = []
            in_block = False
            for line in lines:
                if line.strip() == SiteBlocker.BLOCK_START_MARKER:
                    in_block = True
                    continue
                elif line.strip() == SiteBlocker.BLOCK_END_MARKER:
                    in_block = False
                    continue
                
                if not in_block:
                    new_lines.append(line)

            with open(SiteBlocker.HOSTS_PATH, 'w') as f:
                f.writelines(new_lines)
            
            try:
                subprocess.run(
                    ["ipconfig", "/flushdns"], 
                    capture_output=True, timeout=5, 
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
            except Exception:
                pass
            print("Successfully force-unblocked sites.")
        except PermissionError:
            print("PermissionError: Please run as Administrator to force unblock.")
        except Exception as e:
            print(f"Error in force_unblock: {e}")

    def _flush_dns(self) -> None:
        try:
            subprocess.run(
                ["ipconfig", "/flushdns"], 
                capture_output=True, timeout=5, 
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        except Exception:
            pass

    @property
    def is_blocking(self) -> bool:
        return self._is_blocking

    @property
    def blocked_sites(self) -> list[str]:
        return self._blocked_sites

    def cleanup(self) -> None:
        try:
            self.unblock()
        except Exception as e:
            print(f"Cleanup error (ignored): {e}")
        finally:
            self._is_blocking = False
