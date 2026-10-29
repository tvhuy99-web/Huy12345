#!/usr/bin/env python3
"""Build the actual startup file manager, with a pinned source and reviewable patch."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SOURCE = HERE / '.source'
COMMIT = '6b1860895885a6d65c37815308260293341acb5f'
SHA256 = '0b7d46ab45a34cd443cc0c96f8833755ae30383ca7e0f708a20f77396a8eb528'
ASSETS = ROOT / 'app/app/src/main/assets/nvda'


def build():
    archive = HERE / '.source.zip'
    if not archive.exists() or hashlib.sha256(archive.read_bytes()).hexdigest() != SHA256:
        url = f'https://codeload.github.com/brunodev85/wfm/zip/{COMMIT}'
        with urllib.request.urlopen(url, timeout=60) as source, archive.open('wb') as output:
            shutil.copyfileobj(source, output)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != SHA256:
        raise RuntimeError('WFM source archive checksum mismatch')
    shutil.rmtree(SOURCE, ignore_errors=True)
    SOURCE.mkdir()
    with zipfile.ZipFile(archive) as package:
        for entry in package.infolist():
            path = Path(entry.filename)
            relative = Path(*path.parts[1:])
            if path.is_absolute() or '..' in path.parts or entry.file_size > 1024 * 1024:
                raise RuntimeError('Unexpected WFM source path')
            if entry.is_dir() or not relative.parts:
                continue
            target = SOURCE / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(package.read(entry))
    subprocess.run(['patch', '-p1', '--batch', '--fuzz=0', '-i', str(HERE / 'keyboard.patch')], cwd=SOURCE, check=True)
    obj = SOURCE / 'obj'; obj.mkdir()
    objects = []
    for source in sorted((SOURCE / 'src').glob('*.c')):
        target = obj / (source.stem + '.o'); objects.append(str(target))
        subprocess.run(['x86_64-w64-mingw32-gcc', '-std=c99', '-O2', '-DUNICODE', '-D_UNICODE',
                        '-DCOBJMACROS', '-DWINVER=0x0600', '-I'+str(SOURCE/'include'),
                        '-I'+str(SOURCE/'include/libcdio'), '-c', str(source), '-o', str(target)], check=True)
    resource = obj / 'resource.o'
    subprocess.run(['x86_64-w64-mingw32-windres', '-I'+str(SOURCE/'include'), '-I'+str(SOURCE/'res'),
                    '-i', str(SOURCE/'res/resource.rc'), '-o', str(resource)], cwd=SOURCE, check=True)
    ASSETS.mkdir(parents=True, exist_ok=True)
    binary = ASSETS / 'wfm.exe'
    subprocess.run(['x86_64-w64-mingw32-gcc', '-mwindows', '-static-libgcc', '-s', *objects, str(resource),
                    str(SOURCE/'libcdio.dll'), '-lcomctl32', '-lgdi32', '-lole32', '-luuid', '-lshell32',
                    '-ladvapi32', '-lcomdlg32', '-o', str(binary)], check=True)
    # Compile a separate CI-only slow variant from the same production source.
    delayed = obj/'accessibility-delayed.o'
    subprocess.run(['x86_64-w64-mingw32-gcc','-std=c99','-O2','-DUNICODE','-D_UNICODE','-DCOBJMACROS',
        '-DWINVER=0x0600','-DWFM_A11Y_TEST','-I'+str(SOURCE/'include'),'-I'+str(SOURCE/'include/libcdio'),
        '-c',str(SOURCE/'src/accessibility.c'),'-o',str(delayed)],check=True)
    test_objects=[str(delayed) if Path(name).name=='accessibility.o' else name for name in objects]
    subprocess.run(['x86_64-w64-mingw32-gcc','-mwindows','-static-libgcc','-s',*test_objects,str(resource),
        str(SOURCE/'libcdio.dll'),'-lcomctl32','-lgdi32','-lole32','-luuid','-lshell32','-ladvapi32','-lcomdlg32',
        '-o',str(SOURCE/'wfm-delayed-test.exe')],check=True)
    # The DLL is only a link/test dependency here. Android reuses the libcdio already in Wine.
    metadata = {'sourceCommit': COMMIT, 'sourceArchiveSha256': SHA256, 'commandProtocol': 3,
                'patchSha256': hashlib.sha256((HERE/'keyboard.patch').read_bytes()).hexdigest(),
                'binarySha256': hashlib.sha256(binary.read_bytes()).hexdigest()}
    (ASSETS/'wfm-build.json').write_text(json.dumps(metadata, indent=2)+'\n')
    for name in ['LICENSE-MIT.txt', 'COPYING-GPL-3.txt', 'SOURCE.txt']:
        shutil.copyfile(HERE/name, ASSETS/('wfm-'+name))
    print('Built WFM with real keyboard focus and selection reporting: '+metadata['binarySha256'])


if __name__ == '__main__':
    build()
