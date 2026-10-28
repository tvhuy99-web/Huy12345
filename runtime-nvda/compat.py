#!/usr/bin/env python3
"""Defer missing kernel32/user32 export errors until the API is requested.

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
SOURCES={
    'kernel32':'294baca8838c47fbabc8896c0c87f5219e1b964a2ddd74204789dcecd7ef9757',
    'user32':'157fdb926c17a512c77f2172a65dc48630fe6bf85ec28583110a6cac2dd314f4',
}


def patch():
    if sys.version_info[:2] != (3,13): raise RuntimeError('NVDA bytecode must be compiled with Python 3.13')
    manifest=json.loads((ASSETS/'manifest.json').read_text())
    if manifest.get('winlatorCompatibilityVersion')==3:
        print('NVDA compatibility patch already applied'); return
    pattern=re.compile(r'(?m)^(\w+) = (WINFUNCTYPE\([^\n]+?\))\(\("([^\"]+)", dll\)\)$')
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
    texts={}
    for module,expected in SOURCES.items():
        url=f'https://raw.githubusercontent.com/nvaccess/nvda/{COMMIT}/source/winBindings/{module}.py'
        source=urllib.request.urlopen(url,timeout=60).read()
        if hashlib.sha256(source).hexdigest()!=expected: raise RuntimeError('NVDA source checksum mismatch: '+module)
        text=source.decode('utf-8');matches=list(pattern.finditer(text))
        if len(matches)<20: raise RuntimeError('Unexpected NVDA binding source: '+module)
        position=matches[0].start();text=text[:position]+helper+text[position:]
        texts[module]=pattern.sub(lambda m:f'{m[1]} = _winlatorBind({m[2]}, "{m[3]}")',text)
    archive=ASSETS/'nvda-portable.zip'
    with zipfile.ZipFile(archive) as outer:
        library=outer.read('library.zip')
    buffer=io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(library)) as before, zipfile.ZipFile(buffer,'w') as after:
        replacements={}
        for module,text in texts.items():
            name=f'winBindings/{module}.pyc'
            if before.read(name)[:4]!=importlib.util.MAGIC_NUMBER: raise RuntimeError('Python bytecode version mismatch')
            code=compile(text,f'winBindings/{module}.py','exec')
            replacements[name]=importlib.util.MAGIC_NUMBER+b'\0'*12+marshal.dumps(code)
        for entry in before.infolist():
            data=replacements[entry.filename] if entry.filename in replacements else before.read(entry)
            after.writestr(entry,data)
    temporary=archive.with_suffix('.patched.zip')
    with zipfile.ZipFile(archive) as before, zipfile.ZipFile(temporary,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as after:
        for entry in before.infolist():
            if entry.filename in [f'source/winBindings/{module}.py' for module in texts] or entry.filename=='source/WINLATOR-COMPATIBILITY.txt': continue
            after.writestr(entry,buffer.getvalue() if entry.filename=='library.zip' else before.read(entry))
        def add_source(name, data):
            entry=zipfile.ZipInfo(name,date_time=(2026,1,1,0,0,0))
            entry.compress_type=zipfile.ZIP_DEFLATED;entry.external_attr=0o100644 << 16
            after.writestr(entry,data)
        for module,text in texts.items():add_source(f'source/winBindings/{module}.py',text)
        add_source('source/WINLATOR-COMPATIBILITY.txt',
            'NVDA 2026.3 compatibility change: defer missing kernel32/user32 export errors until use. '
            'Present APIs retain their original binding. Missing APIs raise WinError 120 when called.\n'
            f'Original source: https://github.com/nvaccess/nvda/tree/{COMMIT}\n'
            'Build and patch scripts: https://github.com/tvhuy99-web/Huy12345/tree/main/runtime-nvda\n'
            'The modified module retains the NVDA GPL v2-or-later license. See documentation/copying.txt.\n')
    temporary.replace(archive)
    manifest['archiveSha256']=hashlib.sha256(archive.read_bytes()).hexdigest()
    manifest['winlatorCompatibilityVersion']=3
    manifest['sourceCommit']=COMMIT
    with zipfile.ZipFile(archive) as packaged:
        manifest['unpackedBytes']=sum(entry.file_size for entry in packaged.infolist())
        manifest['files']=len(packaged.infolist())
    (ASSETS/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('Applied NVDA Wine compatibility guards:',manifest['archiveSha256'])


if __name__=='__main__': patch()
