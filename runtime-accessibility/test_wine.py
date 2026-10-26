#!/usr/bin/env python3
"""Exercise the actual Windows executable in Wine, not a simulated Android tree."""
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import struct
import subprocess
import tempfile
import time


def run():
    root = Path(__file__).resolve().parents[1]
    executable = root / 'app/app/src/main/assets/accessibility/winlator-a11y.exe'
    wine = os.environ.get('WINE_BINARY') or shutil.which('wine64') or '/usr/lib/wine/wine64'
    token = secrets.token_hex(16)
    env = dict(os.environ, WINEDEBUG='-all', WINEARCH='win64', WINEDLLOVERRIDES='mscoree,mshtml=')
    with tempfile.TemporaryDirectory(prefix='winlator-a11y-wine-') as prefix:
        env['WINEPREFIX'] = prefix
        with socket.socket() as listener, open(root / 'runtime-accessibility/wine-test.log', 'w') as log:
            listener.bind(('127.0.0.1', 0)); listener.listen(4); listener.settimeout(90)
            process = subprocess.Popen([wine, str(executable), str(listener.getsockname()[1]), token],
                                       env=env, stdout=log, stderr=log)
            connection = None
            try:
                connection, _ = listener.accept(); connection.settimeout(45)

                def exact(n):
                    result = bytearray()
                    while len(result) < n:
                        part = connection.recv(n - len(result))
                        assert part, 'Guest closed connection'
                        result.extend(part)
                    return bytes(result)

                def receive():
                    n, = struct.unpack('!I', exact(4))
                    assert 0 < n <= 1024*1024
                    data = exact(n).decode('utf-8')
                    assert 'SECRET_MUST_NOT_LEAK' not in data, 'Password leaked through the bridge'
                    return data

                assert receive() == 'WINLATOR-A11Y-1 ' + token

                def command(text):
                    data = text.encode('utf-8'); connection.sendall(struct.pack('!I', len(data)) + data)
                    snapshot = json.loads(receive())
                    assert snapshot['version'] == 1
                    assert len(snapshot['nodes']) <= 256
                    return snapshot

                def until(predicate, timeout=15):
                    deadline = time.monotonic() + timeout
                    while True:
                        s = command('snapshot')
                        if predicate(s): return s
                        assert time.monotonic() < deadline, json.dumps(s, ensure_ascii=False)
                        time.sleep(.2)

                def node(snapshot, predicate):
                    matches = [n for n in snapshot['nodes'] if predicate(n)]
                    assert matches, json.dumps(snapshot, ensure_ascii=False)
                    return matches[0]

                def action(s, n, verb, text=''):
                    return command(f"act\t{s['revision']}\t{n['id']}\t{verb}\t{text.encode('utf-8').hex()}")

                command('snapshot'); command('test')
                s = until(lambda s: s['title'] == 'Winlator accessibility test' and any(n['edit'] for n in s['nodes']))
                assert any(n['name'] == 'Tiếp tục' for n in s['nodes']), 'Unicode label not read'
                assert any(n['password'] and not n['value'] and not n['edit'] for n in s['nodes'])
                print('Guest sources:', {source: sum(n['source'] == source for n in s['nodes']) for source in ('msaa', 'win32')}, flush=True)
                print('PASS: real Wine controls, Unicode labels, password suppression', flush=True)
                text_node = node(s, lambda n: n['edit'])
                result = action(s, text_node, 'edit', 'Tiếng Việt 123')
                assert result['result'] == 1, result
                s = until(lambda s: any(n['value'] == 'Tiếng Việt 123' for n in s['nodes']))
                print('PASS: Unicode text editing in a real Windows edit control', flush=True)
                checkbox = node(s, lambda n: n['role'] == 44)
                assert checkbox['state'] & 16 == 0
                result = action(s, checkbox, 'click'); assert result['result'] == 1, result
                s = until(lambda s: any(n['role'] == 44 and n['state'] & 16 for n in s['nodes']))
                print('PASS: checkbox activation and updated checked state', flush=True)
                next_button = node(s, lambda n: n['name'] == 'Tiếp tục')
                result = action(s, next_button, 'click'); assert result['result'] == 1, result
                s = until(lambda s: any(n['name'] == 'Đã kích hoạt' for n in s['nodes']))
                print('PASS: Windows button activation updates the real window', flush=True)
                disabled = node(s, lambda n: n['name'] == 'Disabled control')
                assert disabled['state'] & 1
                assert action(s, disabled, 'click')['result'] == 2
                assert command(f"act\t0\t{next_button['id']}\tclick\t")['result'] == 3
                assert command('window\tdeadbeef')['result'] == 2
                assert command(f"key\t{s['revision']}\tunknown")['result'] == 4
                print('PASS: disabled controls, stale actions and invalid targets rejected', flush=True)
                # A raw frame close must make the helper exit; no persistent guest service.
                data = b'quit'; connection.sendall(struct.pack('!I',len(data))+data)
                process.wait(timeout=15); assert process.returncode == 0
                print('Wine integration tests passed', flush=True)
            finally:
                if connection: connection.close()
                process.terminate()
                server = shutil.which('wineserver') or '/usr/lib/wine/wineserver'
                subprocess.run([server, '-k'], env=env, timeout=15, check=False)


if __name__ == '__main__':
    run()
