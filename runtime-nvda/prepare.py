#!/usr/bin/env python3
"""Package an unchanged, checksum-pinned NVDA portable tree from NV Access."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile

VERSION = '2026.3'
SHA256 = 'a8a87cb823da0c62cfbae4a444ae5ae238d54dc82ad6d46d3fdb3fef082799b2'
URL = f'https://download.nvaccess.org/releases/{VERSION}/nvda_{VERSION}.exe'
ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'app/app/src/main/assets/nvda'


def templates():
    for source, target in [('default.ini', 'config-template.ini'), ('manifest.ini', 'addon-manifest.ini'),
                           ('winlatorStartup.py', 'winlatorStartup.py'), ('winlatorAndroid.py', 'winlatorAndroid.py'),
                           ('game_voice.py', 'game_voice.py'), ('game_startup.py', 'game_startup.py'), ('voice-trace-original.json', 'voice-trace-original.json')]:
        shutil.copyfile(ROOT / 'runtime-nvda' / source, ASSETS / target)


def prepare(installer=None):
    ASSETS.mkdir(parents=True, exist_ok=True)
    existing = ASSETS / 'manifest.json'
    archive = ASSETS / 'nvda-portable.zip'
    if existing.is_file() and archive.is_file():
        metadata = json.loads(existing.read_text())
        if metadata.get('upstreamSha256') == SHA256 and metadata.get('archiveSha256') == hashlib.sha256(archive.read_bytes()).hexdigest():
            templates()
            print('Reusing verified NVDA portable package')
            return
    with tempfile.TemporaryDirectory(prefix='winlator-nvda-package-') as scratch:
        scratch = Path(scratch)
        source = Path(installer) if installer else scratch / 'nvda.exe'
        if not installer:
            with urllib.request.urlopen(URL, timeout=90) as response, source.open('wb') as output:
                shutil.copyfileobj(response, output)
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        if digest != SHA256:
            raise RuntimeError(f'Official NVDA checksum mismatch: {digest}')
        extracted = scratch / 'extract'
        subprocess.run(['7z', 'x', '-y', f'-o{extracted}', str(source)], check=True, stdout=subprocess.DEVNULL)
        candidates = list(extracted.rglob('nvda_noUIAccess.exe'))
        if len(candidates) != 1:
            raise RuntimeError('Unexpected official package layout')
        tree = candidates[0].parent
        # This is the same executable selection used by NVDA createPortableCopy.
        shutil.copyfile(tree / 'nvda_noUIAccess.exe', tree / 'nvda.exe')
        required = ['nvda.exe', 'python313.dll', 'documentation/copying.txt',
                    'synthDrivers/espeak-ng-data/vi_dict', 'locale/vi/LC_MESSAGES/nvda.mo']
        for name in required:
            if not (tree / name).is_file():
                raise RuntimeError(f'Missing NVDA component: {name}')
        files = sorted(p for p in tree.rglob('*') if p.is_file())
        total = sum(p.stat().st_size for p in files)
        archive = ASSETS / 'nvda-portable.zip'
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as output:
            for path in files:
                info = zipfile.ZipInfo(path.relative_to(tree).as_posix(), date_time=(2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                output.writestr(info, path.read_bytes())
        manifest = {'version': VERSION, 'upstreamUrl': URL, 'upstreamSha256': SHA256,
                    'archiveSha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
                    'unpackedBytes': total, 'files': len(files),
                    'sourceUrl': f'https://github.com/nvaccess/nvda/tree/release-{VERSION}'}
        (ASSETS / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        shutil.copyfile(tree / 'documentation/copying.txt', ASSETS / 'NVDA-COPYING.txt')
        templates()
        print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--installer')
    prepare(parser.parse_args().installer)
