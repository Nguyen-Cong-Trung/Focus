import ctypes
import os
import subprocess
import logging
from contextlib import contextmanager


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

    @contextmanager
    def _writable_hosts(self):
        """Deny concurrent writers/replacement while changing the hosts file.

        On Windows this cooperates with the OS file-sharing rules, including
        editors/VPN clients that do not use Python or advisory file locks.
        """
        if os.name != 'nt':
            with open(self.HOSTS_PATH, 'r+b') as hosts:
                yield hosts
            return
        import msvcrt
        from ctypes import wintypes as W
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateFileW.argtypes = [W.LPCWSTR, W.DWORD, W.DWORD, ctypes.c_void_p,
                                      W.DWORD, W.DWORD, W.HANDLE]
        kernel.CreateFileW.restype = W.HANDLE
        kernel.CloseHandle.argtypes = [W.HANDLE]
        kernel.CloseHandle.restype = W.BOOL
        handle = kernel.CreateFileW(str(self.HOSTS_PATH), 0x80000000 | 0x40000000,
                                    1, None, 3, 0x80, None)  # FILE_SHARE_READ, OPEN_EXISTING
        if handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            fd = msvcrt.open_osfhandle(handle, os.O_RDWR | os.O_BINARY)
        except BaseException:
            kernel.CloseHandle(handle)
            raise
        with os.fdopen(fd, 'r+b') as hosts:
            yield hosts

    @classmethod
    def _without_blocks(cls, content):
        """Remove only well-formed owned sections, preserving all other bytes."""
        result = []
        inside = False
        added_separator = 0
        lines = content.splitlines(keepends=True)
        for index, line in enumerate(lines):
            marker = line.strip()
            if marker == cls.BLOCK_START_MARKER.encode('ascii'):
                if inside:
                    raise ValueError('Nested Focus hosts markers; leave hosts unchanged.')
                inside = True
                added_separator = 0
            elif marker == cls.BLOCK_END_MARKER.encode('ascii'):
                if not inside:
                    raise ValueError('Reversed Focus hosts markers; leave hosts unchanged.')
                if added_separator and result and index == len(lines) - 1:
                    # This newline was inserted solely to start our section.
                    result[-1] = result[-1][:-added_separator]
                inside = False
            elif inside:
                if marker == b'# DeepFocus added separator: LF':
                    added_separator = 1
                elif marker == b'# DeepFocus added separator: CRLF':
                    added_separator = 2
            else:
                result.append(line)
        if inside:
            raise ValueError('Unmatched Focus hosts markers; leave hosts unchanged.')
        return b''.join(result)

    def block(self, sites: list[str]) -> bool:
        from utils.validation import blocklist
        sites = blocklist(sites, 'website')
        if not self.is_admin():
            print('Warning: Admin privileges required to block sites.')
            return False
        try:
            # Binary mode preserves other applications' comments/encoding/CRLF.
            # Do not unblock first: failure must not discard the existing block.
            with self._writable_hosts() as hosts:
                original = hosts.read()
                base = self._without_blocks(original)
                newline = b'\r\n' if b'\r\n' in base else b'\n'
                added_separator = bool(base and not base.endswith(b'\n'))
                content = base + (newline if added_separator else b'')
                content += self.BLOCK_START_MARKER.encode('ascii') + newline
                if added_separator:
                    content += b'# DeepFocus added separator: ' + (b'CRLF' if newline == b'\r\n' else b'LF') + newline
                expanded_sites = []
                for site in sites:
                    expanded_sites.append(site)
                    if not site.startswith('www.'):
                        expanded_sites.append('www.' + site)
                for site in dict.fromkeys(expanded_sites):
                    content += f'{self.REDIRECT_IP} {site}'.encode('ascii') + newline
                content += self.BLOCK_END_MARKER.encode('ascii') + newline
                hosts.seek(0)
                hosts.write(content)
                hosts.truncate()
            self._flush_dns()
            self._is_blocking = True
            self._blocked_sites = list(dict.fromkeys(expanded_sites))
            return True
        except Exception:
            logging.getLogger(__name__).exception('Could not block websites')
            return False

    def unblock(self) -> bool:
        try:
            if not os.path.exists(self.HOSTS_PATH):
                self._is_blocking = False
                self._blocked_sites = []
                return True
            # Read first: ordinary non-admin startup succeeds without writing
            # when there is no Focus section in a read-only Windows hosts file.
            with open(self.HOSTS_PATH, 'rb') as hosts:
                original = hosts.read()
            cleaned = self._without_blocks(original)
            if cleaned != original:
                with self._writable_hosts() as hosts:
                    # A VPN/other blocker may have edited between read and open.
                    # Re-read through the writable handle so we preserve it.
                    latest = hosts.read()
                    cleaned = self._without_blocks(latest)
                    hosts.seek(0)
                    hosts.write(cleaned)
                    hosts.truncate()
                self._flush_dns()
            self._is_blocking = False
            self._blocked_sites = []
            return True
        except ValueError:
            logging.getLogger(__name__).warning('Malformed Focus hosts markers; file left unchanged')
            return False
        except PermissionError:
            print('PermissionError: Administrator privileges required to unblock sites (modify hosts file).')
            return False
        except Exception:
            logging.getLogger(__name__).exception('Could not unblock websites')
            return False

    @staticmethod
    def force_unblock() -> None:
        """Emergency cleanup uses the same non-destructive marker validation."""
        blocker = SiteBlocker()
        if not blocker.unblock():
            print('Could not safely unblock sites. Check permissions and hosts markers.')

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
