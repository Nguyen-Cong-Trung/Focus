"""Build the branded Inno Setup installer from the validated app bundle."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def artwork():
    # Native installer artwork, composed from the supplied, unchanged logo.
    from PIL import Image, ImageDraw, ImageFont
    panel = Image.new('RGB', (656, 1256), '#111318')
    draw = ImageDraw.Draw(panel)
    draw.rounded_rectangle((64, 96, 592, 624), radius=56, fill='#1B2029', outline='#2B313D', width=2)
    logo = Image.open(ROOT / 'branding/focus-logo.png').convert('RGBA')
    logo.thumbnail((360, 360), Image.Resampling.LANCZOS)
    panel.paste(logo, ((656 - logo.width) // 2, 360 - logo.height // 2), logo)
    fonts = ROOT / 'PythonProject/assets/fonts'
    bold = ImageFont.truetype(str(fonts / 'Inter-Bold.ttf'), 72)
    regular = ImageFont.truetype(str(fonts / 'Inter-Regular.ttf'), 30)
    small = ImageFont.truetype(str(fonts / 'Inter-Regular.ttf'), 22)
    draw.text((64, 692), 'Focus', font=bold, fill='#F5F5F7')
    draw.text((64, 802), 'Make room for', font=regular, fill='#BCC4D0')
    draw.text((64, 846), 'your best work.', font=regular, fill='#BCC4D0')
    draw.rounded_rectangle((64, 958, 146, 964), radius=3, fill='#E73A2E')
    draw.text((64, 1110), 'SPERTULO UTILITY', font=small, fill='#929DAD')
    draw.text((64, 1150), 'WINDOWS / 1.0.0', font=small, fill='#929DAD')
    panel.save(ROOT / 'build_tools/installer/wizard.png', optimize=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--compiler', type=Path, default=ROOT / '.release-tools/inno/ISCC.exe')
    args = parser.parse_args()
    bundle = ROOT / 'dist/Focus'
    if not (bundle / 'Focus.exe').is_file():
        raise SystemExit('Build and verify the app bundle first.')
    artwork()
    subprocess.run([str(args.compiler.resolve()), '/Qp',
        '/DBundleDir=' + str(bundle), '/DReleaseDir=' + str(ROOT / 'releases'),
        str(ROOT / 'build_tools/installer/Focus.iss')], check=True, cwd=ROOT)
    files = [ROOT / 'releases/Focus-Setup-1.0.0-Windows-x64.exe',
             ROOT / 'releases/Focus-1.0.0-Windows-x64.zip']
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    (ROOT / 'releases/SHA256SUMS.txt').write_text(
        ''.join(f'{digest}  {name}\n' for name, digest in hashes.items()), encoding='ascii')
    manifest = {p.name: {'bytes': p.stat().st_size, 'sha256': hashes[p.name]} for p in files}
    (ROOT / '.release-work/installer-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
