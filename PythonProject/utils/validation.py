"""Validation shared by forms, storage, backups and blocking."""
import ipaddress
import json
import re
from urllib.parse import urlsplit


def hostname(value):
    value = value.strip()
    if not value or any(c.isspace() for c in value):
        raise ValueError('Enter a website domain or an http/https URL.')
    try:
        url = urlsplit(value if '://' in value else 'https://' + value)
        if url.scheme not in ('http', 'https') or url.username or url.password:
            raise ValueError
        name = (url.hostname or '').rstrip('.').encode('idna').decode('ascii').lower()
        if not name or len(name) > 253 or any(not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', p) for p in name.split('.')):
            raise ValueError
        try:
            ipaddress.ip_address(name)
        except ValueError:
            if '.' not in name:
                raise ValueError
        return name
    except (ValueError, UnicodeError):
        raise ValueError('Enter a valid website, such as youtube.com.') from None


def application(value):
    value = value.strip()
    if not re.fullmatch(r'[^<>:"/\\|?*\x00-\x1f]{1,180}\.exe', value, re.IGNORECASE):
        raise ValueError('Enter an application filename, such as Discord.exe, without a path or wildcard.')
    return value


def blocklist(values, kind):
    if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
        raise ValueError('Blocklists must contain text entries.')
    normalize = hostname if kind == 'website' else application
    result, seen = [], set()
    for value in values:
        if not value.strip():
            continue
        value = normalize(value)
        if value.casefold() not in seen:
            result.append(value)
            seen.add(value.casefold())
    return result


def validate_mode(mode):
    mode.name = mode.name.strip()
    if not mode.name or len(mode.name) > 80:
        raise ValueError('Use a mode name between 1 and 80 characters.')
    for value in (mode.focus_minutes, mode.short_break_minutes, mode.long_break_minutes, mode.sessions_before_long_break):
        if type(value) is not int or not 1 <= value <= 1440:
            raise ValueError('Time and session values must be whole numbers from 1 to 1440.')
    if type(mode.target_goal) is not int or not 0 <= mode.target_goal <= 1440:
        raise ValueError('Daily goal must be between 0 and 1440 sessions (0 means unlimited).')
    for field, kind in (('blocked_sites', 'website'), ('blocked_apps', 'app')):
        try:
            values = json.loads(getattr(mode, field))
        except (ValueError, TypeError):
            raise ValueError('The mode contains an invalid blocklist.') from None
        setattr(mode, field, json.dumps(blocklist(values, kind)))
    from utils.constants import SOUND_TYPES
    if not isinstance(mode.auto_sound,str) or (mode.auto_sound not in ['none',*SOUND_TYPES] and not re.fullmatch(r'custom_[1-9][0-9]*',mode.auto_sound)):
        raise ValueError('Choose an available background sound.')
    if type(mode.auto_sound_volume) not in (int,float) or not 0 <= mode.auto_sound_volume <= 1:
        raise ValueError('Sound volume must be between 0 and 100%.')
    return mode
