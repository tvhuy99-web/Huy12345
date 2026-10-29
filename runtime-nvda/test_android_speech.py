#!/usr/bin/env python3
"""Real NVDA synth driver, with a test host in place of Android's device-only TTS engine."""
import json
from pathlib import Path
import secrets
import socket
import struct
import threading
import time


def exercise_android_speech(config, command):
    token = secrets.token_hex(32)
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0)); listener.listen(2); listener.settimeout(15)
    records = []; failures = []; closed = threading.Event(); authenticated = threading.Event()

    def send(connection, message):
        data = json.dumps(message, ensure_ascii=False).encode('utf-8')
        connection.sendall(struct.pack('!I', len(data))+data)

    def receive(connection):
        def exact(size):
            data = bytearray()
            while len(data) < size:
                part = connection.recv(size-len(data))
                if not part: raise EOFError()
                data.extend(part)
            return data
        length, = struct.unpack('!I', exact(4))
        assert 0 < length <= 65536
        return json.loads(exact(length))

    def server():
        try:
            connection, _ = listener.accept()
            with connection:
                connection.settimeout(12)
                hello = receive(connection)
                assert hello == {'type': 'hello', 'version': 1, 'token': token}
                authenticated.set(); send(connection, {'type': 'ready', 'version': 1})
                epoch = -1
                while not closed.is_set():
                    message = receive(connection)
                    records.append(message)
                    if message['type'] == 'ping':
                        send(connection, {'type': 'pong'}); continue
                    if message['epoch'] < epoch: continue
                    epoch = message['epoch']
                    if message['type'] == 'speak':
                        for part in message['parts']:
                            assert isinstance(part['text'], str)
                            if 'index' in part:
                                send(connection, {'type': 'index', 'epoch': epoch, 'index': part['index']})
                        send(connection, {'type': 'done', 'epoch': epoch})
        except (EOFError, OSError):
            pass
        except Exception as error:
            failures.append(str(error))

    (config/'winlator-android-voice.json').write_text(json.dumps({
        'version': 1, 'enabled': True, 'port': listener.getsockname()[1], 'token': token}))
    thread = threading.Thread(target=server, daemon=True); thread.start()
    try:
        command('android_voice')
        assert authenticated.wait(5), 'NVDA did not authenticate its speech connection'
        phrase = 'Kiểm tra giọng Android. Ổ đĩa thứ hai, tiếng Việt rõ ràng.'
        command('message', phrase)
        deadline = time.monotonic()+8
        while time.monotonic() < deadline:
            texts = [p['text'] for m in records if m['type']=='speak' for p in m['parts']]
            if phrase in ' '.join(texts): break
            time.sleep(.05)
        assert phrase in ' '.join(texts), 'Vietnamese text did not reach the host'
        command('silence')
        deadline = time.monotonic()+3
        while time.monotonic()<deadline:
            if len([m for m in records if m['type']=='cancel'])>=2: break
            time.sleep(.05)
        assert len([m for m in records if m['type']=='cancel'])>=2, 'Speech cancellation missing'
        assert any('index' in p for m in records if m['type']=='speak' for p in m['parts']), 'NVDA indexes missing'
        command('android_voice_test')
        assert not failures, failures
        print('PASS: real NVDA Android synth authenticates, streams Vietnamese, receives completion indexes and cancels speech', flush=True)
    finally:
        command('espeak_voice')
        closed.set(); listener.close();thread.join(timeout=2)
        (config/'winlator-android-voice.json').unlink(missing_ok=True)
