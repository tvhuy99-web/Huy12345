#!/usr/bin/env python3
"""Inspect a user-supplied game package without executing it or publishing its binaries."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import pefile
import rarfile


def decode(data):
    if data.startswith((b'\xff\xfe', b'\xfe\xff')):
        return 'utf-16', data.decode('utf-16', errors='replace')
    for encoding in ('utf-8-sig', 'gb18030'):
        try:
            return encoding, data.decode(encoding)
        except UnicodeError:
            pass
    return 'windows-1252', data.decode('cp1252', errors='replace')


def redact(text):
    text = re.sub(r'(?im)^([^\r\n]*(?:password|passwd|token|secret|licensekey|serialkey|密码|密钥)[^=:\r\n]*[=:]).*$', r'\1[redacted]', text)
    text = re.sub(r'(?i)(C:\\Users\\)[^\\\s]+', r'\1[user]', text)
    return text


def main():
    archive, destination, results = map(Path, sys.argv[1:4])
    destination.mkdir(parents=True, exist_ok=True); results.mkdir(parents=True, exist_ok=True)
    digest = hashlib.file_digest(archive.open('rb'), 'sha256').hexdigest()
    with rarfile.RarFile(archive) as package:
        entries = package.infolist()
        (results/'archive-info.json').write_text(json.dumps(dict(bytes=archive.stat().st_size, sha256=digest,
            entries=len(entries), needsPassword=package.needs_password(), firstPaths=[row.filename for row in entries[:40]]),ensure_ascii=False,indent=2))
        if len(entries) > 100000 or sum(row.file_size for row in entries) > 12*1024**3:
            raise ValueError('Archive exceeds the investigation size budget')
        for row in entries:
            path = PurePosixPath(row.filename.replace('\\', '/'))
            if path.is_absolute() or '..' in path.parts or ':' in path.parts[0]:
                raise ValueError('Unsafe archive path')
            if row.needs_password():
                raise ValueError('Game archive requires a password')
            if row.is_symlink():
                raise ValueError('Symbolic links are not part of this Windows-game probe')
    unpack=subprocess.run(['unrar', 'x', '-p-', '-o+', str(archive), str(destination)+'/'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    (results/'unrar.txt').write_bytes(unpack.stdout[-200000:])
    unpack.check_returncode()
    games = list(destination.rglob('zetianji.exe'))
    if len(games) != 1:
        raise ValueError('Expected one zetianji.exe, got '+str(len(games)))
    root = games[0].parent
    summary = dict(archiveBytes=archive.stat().st_size, archiveSha256=digest, gameRoot=str(root), files=[], pe=[], texts=[])
    for path in sorted(root.rglob('*')):
        if not path.is_file(): continue
        relative = path.relative_to(root).as_posix(); size = path.stat().st_size
        summary['files'].append(dict(path=relative, bytes=size))
        if path.suffix.lower() in ('.exe', '.dll', '.fne') and size < 100*1024**2:
            try:
                image = pefile.PE(str(path), fast_load=True)
                image.parse_data_directories(directories=[1, 0, 13])
                imports = [dict(dll=module.dll.decode(errors='replace'), symbols=[(symbol.name.decode(errors='replace') if symbol.name else '#'+str(symbol.ordinal)) for symbol in module.imports]) for module in getattr(image, 'DIRECTORY_ENTRY_IMPORT', [])]
                exports = [(symbol.name.decode(errors='replace') if symbol.name else '#'+str(symbol.ordinal)) for symbol in getattr(getattr(image, 'DIRECTORY_ENTRY_EXPORT', None), 'symbols', [])]
                summary['pe'].append(dict(path=relative, machine=hex(image.FILE_HEADER.Machine), subsystem=image.OPTIONAL_HEADER.Subsystem, entryPoint=hex(image.OPTIONAL_HEADER.AddressOfEntryPoint), imports=imports, exports=exports[:1000]))
                image.close()
            except pefile.PEFormatError:
                summary['pe'].append(dict(path=relative, format='not-standard-PE'))
        if path.suffix.lower() in ('.txt', '.ini', '.cfg', '.json', '.log') and size <= 128*1024 and len(summary['texts']) < 120:
            if any(part.lower() in ('licenses', 'vendor', 'music', 'sounds', 'update') for part in path.relative_to(root).parts[:-1]):
                continue
            encoding, text = decode(path.read_bytes())
            summary['texts'].append(dict(path=relative, encoding=encoding, text=redact(text)[:16000]))
    (results/'static-summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(json.dumps(dict(archiveBytes=summary['archiveBytes'], archiveSha256=digest, fileCount=len(summary['files']), peCount=len(summary['pe']), textCount=len(summary['texts'])), flush=True))


if __name__ == '__main__': main()
