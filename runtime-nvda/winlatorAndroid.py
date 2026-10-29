# SPDX-License-Identifier: MIT
"""NVDA synthesizer using the authenticated Android TTS host on this device."""
import json
import os
import queue
import select
import socket
import struct
import threading
import time
from collections import OrderedDict
import globalVars
import queueHandler
import synthDriverHandler
from speech.commands import IndexCommand


def endpoint():
    with open(os.path.join(globalVars.appArgs.configPath, 'winlator-android-voice.json'), encoding='utf-8') as stream:
        data = json.loads(stream.read(4096))
    if (data.get('version') != 1 or not data.get('enabled') or not 0 < data.get('port', 0) < 65536
            or len(data.get('token', '')) != 64 or any(c not in '0123456789abcdef' for c in data['token'])):
        raise ValueError('Android voice is not ready')
    return data


def receive(connection):
    def exact(size):
        data = bytearray()
        while len(data) < size:
            part = connection.recv(size-len(data))
            if not part:
                raise OSError('Android voice connection closed')
            data.extend(part)
        return bytes(data)
    size, = struct.unpack('!I', exact(4))
    if not 0 < size <= 65536:
        raise ValueError('Invalid speech frame')
    return json.loads(exact(size))


def send(connection, value):
    data = json.dumps(value, ensure_ascii=False).encode('utf-8')
    if len(data) > 65536:
        raise ValueError('Speech frame too large')
    connection.sendall(struct.pack('!I', len(data))+data)


class SynthDriver(synthDriverHandler.SynthDriver):
    name = 'winlatorAndroid'
    description = 'Giọng Android — tiếng Việt'
    supportedSettings = (synthDriverHandler.SynthDriver.RateSetting(),
                         synthDriverHandler.SynthDriver.PitchSetting(),
                         synthDriverHandler.SynthDriver.VolumeSetting())
    supportedCommands = {IndexCommand}
    supportedNotifications = {synthDriverHandler.synthIndexReached, synthDriverHandler.synthDoneSpeaking}

    @classmethod
    def check(cls):
        try:
            endpoint()
            return True
        except (OSError, ValueError, TypeError):
            return False

    def __init__(self):
        super().__init__()
        self._rate = self._pitch = 50
        self._volume = 100
        self._epoch = 0
        self._lock = threading.RLock()
        self._closed = threading.Event()
        self._out = queue.Queue(maxsize=32)
        self._connected = False
        self._connection = self._connect()
        self._connected = True
        self._thread = threading.Thread(target=self._run, name='WinlatorAndroidSpeech', daemon=True)
        self._thread.start()

    def _connect(self):
        data = endpoint()
        connection = socket.create_connection(('127.0.0.1', data['port']), timeout=2)
        try:
            send(connection, {'type': 'hello', 'version': 1, 'token': data['token']})
            reply = receive(connection)
            if reply.get('type') != 'ready' or reply.get('version') != 1:
                raise OSError('Android Vietnamese voice is unavailable')
            with self._lock:
                epoch = self._epoch
            send(connection, {'type': 'cancel', 'epoch': epoch})
            return connection
        except Exception:
            connection.close()
            raise

    def _notify(self, kind, index=None, epoch=None):
        def deliver():
            if self._closed.is_set() or epoch is not None and epoch != self._epoch:
                return
            if kind == 'index':
                synthDriverHandler.synthIndexReached.notify(synth=self, index=index)
            else:
                synthDriverHandler.synthDoneSpeaking.notify(synth=self)
        queueHandler.queueFunction(queueHandler.eventQueue, deliver)

    def _clear(self):
        while True:
            try:
                self._out.get_nowait()
            except queue.Empty:
                return

    def _run(self):
        ping = time.monotonic()
        while not self._closed.is_set():
            try:
                if self._connection is None:
                    self._connection = self._connect()
                    if self._closed.is_set():
                        self._connection.close()
                        break
                    with self._lock:
                        self._connected = True
                while True:
                    try:
                        message = self._out.get_nowait()
                    except queue.Empty:
                        break
                    if message['epoch'] == self._epoch:
                        send(self._connection, message)
                if time.monotonic()-ping > 5:
                    send(self._connection, {'type': 'ping'})
                    ping = time.monotonic()
                if select.select([self._connection], [], [], .02)[0]:
                    message = receive(self._connection)
                    if message.get('epoch') == self._epoch:
                        if message.get('type') == 'index':
                            self._notify('index', message['index'], message['epoch'])
                        elif message.get('type') == 'done':
                            self._notify('done', epoch=message['epoch'])
            except Exception:
                with self._lock:
                    self._connected = False
                    self._epoch += 1
                    self._clear()  # Never replay stale window text on reconnect.
                    epoch = self._epoch
                if self._connection:
                    self._connection.close()
                self._connection = None
                self._notify('done', epoch=epoch)
                self._closed.wait(1)
        if self._connection:
            self._connection.close()

    def _enqueue(self, message):
        with self._lock:
            if self._closed.is_set():
                return
            if message.get('epoch', self._epoch) != self._epoch:
                return
            if message['type'] == 'speak' and not self._connected:
                return
            message['epoch'] = self._epoch
            try:
                self._out.put_nowait(message)
            except queue.Full:
                self.cancel()
                self._notify('done', epoch=self._epoch)

    def speak(self, speechSequence):
        with self._lock:
            epoch = self._epoch
            if not self._connected:
                self._notify('done', epoch=epoch)
                return
        parts = []
        text = []
        for item in speechSequence:
            if isinstance(item, str):
                text.append(item)
            elif isinstance(item, IndexCommand):
                parts.append({'text': ' '.join(text), 'index': item.index})
                text = []
        if text:
            parts.append({'text': ' '.join(text)})
        # Bound each packet while retaining indexes on the final piece of its text.
        packet = []; size = 0
        for part in parts:
            value = part['text']
            pieces = [value[i:i+2000] for i in range(0, len(value), 2000)] or ['']
            for i, piece in enumerate(pieces):
                if size+len(piece) > 8000 or len(packet) >= 16:
                    self._speak(packet, epoch); packet = []; size = 0
                item = {'text': piece}
                if i == len(pieces)-1 and 'index' in part:
                    item['index'] = part['index']
                packet.append(item); size += len(piece)
        self._speak(packet, epoch)

    def _speak(self, parts, epoch):
        self._enqueue({'type': 'speak', 'parts': parts, 'rate': self._rate,
                       'pitch': self._pitch, 'volume': self._volume, 'epoch': epoch})

    def cancel(self):
        with self._lock:
            self._epoch += 1
            self._clear()
            self._enqueue({'type': 'cancel'})

    def pause(self, switch):
        self._enqueue({'type': 'pause', 'paused': bool(switch)})

    def _get_language(self): return 'vi'
    def _get_voice(self): return 'android-vi'
    def _get_availableVoices(self):
        return OrderedDict({'android-vi': synthDriverHandler.VoiceInfo('android-vi', 'Tiếng Việt Android', 'vi')})
    def _get_rate(self): return self._rate
    def _set_rate(self, value): self._rate = max(0, min(100, int(value)))
    def _get_pitch(self): return self._pitch
    def _set_pitch(self, value): self._pitch = max(0, min(100, int(value)))
    def _get_volume(self): return self._volume
    def _set_volume(self, value): self._volume = max(0, min(100, int(value)))

    def terminate(self):
        self._closed.set()
        self._connected = False
        connection = self._connection
        if connection:
            try:
                connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            connection.close()
        self._thread.join(timeout=.3)
        super().terminate()
