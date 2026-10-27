"""Publish verified artifacts using the local Git Credential Manager login.

Credentials remain in memory and are never printed or written to the project.
Run only after reviewing/committing the source and pushing it to GitHub.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = 'Nguyen-Cong-Trung/Focus'
TAG = 'v1.0.1'
ARCHIVE = ROOT / 'releases/Focus-1.0.1-Windows-x64.zip'
INSTALLER = ROOT / 'releases/Focus-Setup-1.0.1-Windows-x64.exe'


def main():
    report = json.loads((ROOT / '.release-work/final-package-check.json').read_text(encoding='utf-8'))
    if not report.get('ok') or not report.get('frozen'):
        raise RuntimeError('The extracted release executable must pass its check before publishing.')
    installer_check = json.loads((ROOT / '.release-work/installer-check.json').read_text(encoding='utf-8'))
    if not installer_check.get('ok') or installer_check['installer_sha256'] != hashlib.sha256(INSTALLER.read_bytes()).hexdigest():
        raise RuntimeError('This exact installer must pass the install/upgrade/uninstall check.')
    checksums = dict((name, digest) for digest, name in
                     (line.split(maxsplit=1) for line in (ROOT / 'releases/SHA256SUMS.txt').read_text().splitlines()))
    for path in (INSTALLER, ARCHIVE):
        if hashlib.sha256(path.read_bytes()).hexdigest() != checksums.get(path.name):
            raise RuntimeError('Package checksum does not match: ' + path.name)
    subprocess.run(['git', 'diff', '--quiet', 'HEAD', '--'], cwd=ROOT, check=True)
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    environment = os.environ.copy()
    environment.update(GIT_TERMINAL_PROMPT='0', GCM_INTERACTIVE='never')
    result = subprocess.run(['git', 'credential', 'fill'], cwd=ROOT,
        input='protocol=https\nhost=github.com\nusername=Nguyen-Cong-Trung\n\n',
        text=True, capture_output=True, check=True, env=environment)
    credential = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
    token = credential.get('password')
    if not token:
        raise RuntimeError('No GitHub login available. Sign in with Git Credential Manager.')
    headers = {'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2026-03-10', 'User-Agent': 'Focus-release-builder'}
    api = 'https://api.github.com/repos/' + REPOSITORY

    def request(method, url, payload=None, binary=False):
        body = payload if binary else (json.dumps(payload).encode('utf-8') if payload is not None else None)
        current = dict(headers)
        if body is not None:
            current['Content-Type'] = 'application/octet-stream' if binary else 'application/json'
        req = urllib.request.Request(url, data=body, headers=current, method=method)
        with urllib.request.urlopen(req, timeout=180) as response:
            content = response.read()
            return json.loads(content) if content else None

    remote = request('GET', api + '/commits/main')
    if remote['sha'] != commit:
        raise RuntimeError('Push the reviewed commit to main before creating the release.')
    try:
        release = request('GET', api + '/releases/tags/' + TAG)
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise
        release = None
    if release and not release['draft']:
        raise RuntimeError('This release is already published; it will not be overwritten.')
    if release is None:
        release = request('POST', api + '/releases', {'tag_name': TAG, 'target_commitish': commit,
            'name': 'Focus 1.0.1 — Windows Installer', 'draft': True, 'prerelease': False,
            'body': (ROOT / 'build_tools/release_notes.md').read_text(encoding='utf-8')})
    upload_url = release['upload_url'].split('{', 1)[0]
    if urllib.parse.urlsplit(upload_url).hostname != 'uploads.github.com':
        raise RuntimeError('Unexpected upload host')
    for path in (INSTALLER, ARCHIVE, ROOT / 'releases/SHA256SUMS.txt'):
        digest = 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()
        existing = next((a for a in release['assets'] if a['name'] == path.name), None)
        if existing:
            if existing.get('digest') == digest:
                continue
            request('DELETE', existing['url'])
        print('Uploading ' + path.name, flush=True)
        uploaded = request('POST', upload_url + '?' + urllib.parse.urlencode({'name': path.name}),
            path.read_bytes(), binary=True)
        if uploaded.get('digest') and uploaded['digest'] != digest:
            raise RuntimeError('GitHub asset digest differs from the local file')
        if uploaded['size'] != path.stat().st_size:
            raise RuntimeError('GitHub asset size differs from the local file')
    published = request('PATCH', release['url'], {'draft': False, 'make_latest': 'true'})
    result = {'url': published['html_url'], 'tag': TAG, 'commit': commit,
        'assets': [{'name': a['name'], 'size': a['size'], 'digest': a.get('digest'),
                    'url': a['browser_download_url']} for a in published['assets']]}
    (ROOT / '.release-work/published-release.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()
