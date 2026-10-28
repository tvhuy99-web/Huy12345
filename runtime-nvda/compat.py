#!/usr/bin/env python3
"""Defer missing kernel32 export errors until that API is actually requested.

The fallback raises an explicit unsupported-operation error if called. It does
not synthesize accessibility data or change MSAA/UIA implementation.
The patched NVDA source is redistributed inside the portable bundle.
"""
import hashlib
import importlib.util
import io
import json
import marshal
import re
from pathlib import Path
import sys
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'app/app/src/main/assets/nvda'
COMMIT='7eb1738dd1556775145453fdd8b6b7ca6b397693'
SOURCE_SHA='294baca8838c47fbabc8896c0c87f5219e1b964a2ddd74204789dcecd7ef9757'


def patch():
    if sys.version_info[:2] != (3,13): raise RuntimeError('NVDA bytecode must be compiled with Python 3.13')
    manifest=json.loads((ASSETS/'manifest.json').read_text())
    if manifest.get('winlatorCompatibilityVersion')==2:
        print('NVDA compatibility patch already applied'); return
    url=f'https://raw.githubusercontent.com/nvaccess/nvda/{COMMIT}/source/winBindings/kernel32.py'
    source=urllib.request.urlopen(url,timeout=60).read()
    if hashlib.sha256(source).hexdigest()!=SOURCE_SHA: raise RuntimeError('NVDA source checksum mismatch')
    text=source.decode('utf-8')
    pattern=re.compile(r'(?m)^(\w+) = (WINFUNCTYPE\([^\n]+?\))\(\("([^\"]+)", dll\)\)$')
    matches=list(pattern.finditer(text))
    if len(matches)<20: raise RuntimeError('Unexpected NVDA binding source')
    helper='''# Winlator: fail only when a missing API is actually requested.
def _winlatorBind(factory, name):
    try:
        return factory((name, dll))
    except AttributeError:
        def unsupported(*args):
            import ctypes
            raise ctypes.WinError(120)
        return unsupported


'''
    position=matches[0].start()
    text=text[:position]+helper+text[position:]
    text=pattern.sub(lambda m:f'{m[1]} = _winlatorBind({m[2]}, "{m[3]}")',text)
    archive=ASSETS/'nvda-portable.zip'
    with zipfile.ZipFile(archive) as outer:
        library=outer.read('library.zip')
    buffer=io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(library)) as before, zipfile.ZipFile(buffer,'w') as after:
        old=before.read('winBindings/kernel32.pyc')
        if old[:4]!=importlib.util.MAGIC_NUMBER: raise RuntimeError('Python bytecode version mismatch')
        code=compile(text,'winBindings/kernel32.py','exec')
        compiled=importlib.util.MAGIC_NUMBER+b'\0'*12+marshal.dumps(code)
        for entry in before.infolist():
            data=compiled if entry.filename=='winBindings/kernel32.pyc' else before.read(entry)
            after.writestr(entry,data)
    temporary=archive.with_suffix('.patched.zip')
    with zipfile.ZipFile(archive) as before, zipfile.ZipFile(temporary,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as after:
        for entry in before.infolist():
            if entry.filename in ['source/winBindings/kernel32.py','source/WINLATOR-COMPATIBILITY.txt']: continue
            after.writestr(entry,buffer.getvalue() if entry.filename=='library.zip' else before.read(entry))
        after.writestr('source/winBindings/kernel32.py',text)
        after.writestr('source/WINLATOR-COMPATIBILITY.txt',
            'NVDA 2026.3 compatibility change: defer missing kernel32 export errors until use. '
            'Present APIs retain their original binding. Missing APIs raise WinError 120 when called.\n'
            f'Original source: https://github.com/nvaccess/nvda/tree/{COMMIT}\n'
            'Build and patch scripts: https://github.com/tvhuy99-web/Huy12345/tree/main/runtime-nvda\n'
            'The modified module retains the NVDA GPL v2-or-later license. See documentation/copying.txt.\n')
    temporary.replace(archive)
    manifest['archiveSha256']=hashlib.sha256(archive.read_bytes()).hexdigest()
    manifest['winlatorCompatibilityVersion']=2
    manifest['sourceCommit']=COMMIT
    with zipfile.ZipFile(archive) as packaged:
        manifest['unpackedBytes']=sum(entry.file_size for entry in packaged.infolist())
        manifest['files']=len(packaged.infolist())
    (ASSETS/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('Applied NVDA Wine compatibility guards:',manifest['archiveSha256'])


if __name__=='__main__': patch()
