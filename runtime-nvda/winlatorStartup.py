# SPDX-License-Identifier: MIT
"""Local, session-bound touch commands. UI content is spoken, never put in replies."""
import ctypes
from ctypes import wintypes
from collections import deque
import json
import os
import secrets
import time
import api
import config
import controlTypes
import eventHandler
import globalVars
import globalPluginHandler
import inputCore
import keyboardHandler
import speech
from speech.extensions import pre_speech
import synthDriverHandler
import ui
import wx


KEYS = {
    'up': 'upArrow', 'down': 'downArrow', 'left': 'leftArrow', 'right': 'rightArrow',
    'tab': 'tab', 'shift_tab': 'shift+tab', 'enter': 'enter', 'space': 'space',
    'escape': 'escape', 'home': 'home', 'end': 'end', 'page_up': 'pageUp', 'page_down': 'pageDown',
    'alt_tab': 'alt+tab', 'desktop': 'windows+d', 'start_menu': 'windows',
    'backspace': 'backspace', 'delete': 'delete', 'select_all': 'control+a',
    'copy': 'control+c', 'paste': 'control+v', 'cut': 'control+x',
    'nvda_menu': 'NVDA+n', 'window': 'NVDA+b', 'read_all': 'NVDA+downArrow',
}
NAVIGATION = {'up', 'down', 'left', 'right', 'tab', 'shift_tab', 'enter', 'space', 'escape',
              'home', 'end', 'page_up', 'page_down', 'alt_tab', 'desktop', 'start_menu',
              'backspace', 'delete', 'select_all'}
WFM_ACTIONS = dict(zip(('up', 'down', 'left', 'right', 'tab', 'shift_tab', 'enter', 'space',
                       'escape', 'home', 'end', 'page_up', 'page_down', 'backspace', 'select_all',
                       'copy', 'paste', 'cut'), range(1, 19)))
USER32 = ctypes.windll.user32


class GUIThreadInfo(ctypes.Structure):
    _fields_ = [('cbSize', wintypes.DWORD), ('flags', wintypes.DWORD)] + [
        (name, wintypes.HWND) for name in ('active', 'focus', 'capture', 'menuOwner', 'moveSize', 'caret')
    ] + [('rect', wintypes.RECT)]


USER32.GetGUIThreadInfo.argtypes = [wintypes.DWORD, ctypes.POINTER(GUIThreadInfo)]
USER32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
USER32.GetForegroundWindow.restype = wintypes.HWND
USER32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
USER32.GetAncestor.restype = wintypes.HWND
USER32.GetDlgItem.argtypes = [wintypes.HWND, ctypes.c_int]
USER32.GetDlgItem.restype = wintypes.HWND
USER32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
USER32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
USER32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
USER32.SendMessageTimeoutW.argtypes = [wintypes.HWND, wintypes.UINT, ctypes.c_size_t,
                                    ctypes.c_ssize_t, wintypes.UINT, wintypes.UINT,
                                    ctypes.POINTER(ctypes.c_size_t)]
USER32.SendMessageTimeoutW.restype = ctypes.c_ssize_t


def _message(hwnd, message, wparam=0, lparam=0, timeout=150):
    result = ctypes.c_size_t()
    if not USER32.SendMessageTimeoutW(hwnd, message, wparam, lparam, 2, timeout, ctypes.byref(result)):
        raise OSError('Windows control did not respond')
    return ctypes.c_ssize_t(result.value).value


def wfm_root():
    root = USER32.GetForegroundWindow()
    kind = ctypes.create_unicode_buffer(256)
    USER32.GetClassNameW(root, kind, len(kind))
    if kind.value != 'WFM-MainWnd':
        return None
    marker = USER32.GetDlgItem(root, 0x7e02)
    value = ctypes.create_unicode_buffer(64)
    if marker:
        _message(marker, 0xD, len(value), ctypes.addressof(value))
    if value.value != 'WFM-NVDA-2':
        raise RuntimeError('Restart the environment to load the updated file manager')
    return root


def wfm_text(text):
    if not wfm_root():
        return False
    info = GUIThreadInfo(); info.cbSize = ctypes.sizeof(info)
    thread = USER32.GetWindowThreadProcessId(USER32.GetForegroundWindow(), None)
    if not USER32.GetGUIThreadInfo(thread, ctypes.byref(info)) or not info.focus:
        raise RuntimeError('No file manager input field has focus')
    kind = ctypes.create_unicode_buffer(256)
    USER32.GetClassNameW(info.focus, kind, len(kind))
    if kind.value.lower() != 'edit':
        raise RuntimeError('Select the address or search field before typing')
    value = ctypes.create_unicode_buffer(text)
    _message(info.focus, 0xC2, 1, ctypes.addressof(value))  # EM_REPLACESEL, Win32 marshals the text.
    return True


def native_focus_text():
    """Real Win32 selection when Wine MSAA events/roles are incomplete. Bounded calls only."""
    thread = USER32.GetWindowThreadProcessId(USER32.GetForegroundWindow(), None)
    info = GUIThreadInfo(); info.cbSize = ctypes.sizeof(info)
    if not USER32.GetGUIThreadInfo(thread, ctypes.byref(info)) or not info.focus:
        return None
    name = ctypes.create_unicode_buffer(256)
    USER32.GetClassNameW(info.focus, name, len(name))
    kind = name.value.lower()
    root = USER32.GetAncestor(info.focus, 2)
    root_kind = ctypes.create_unicode_buffer(256)
    USER32.GetClassNameW(root, root_kind, len(root_kind))
    if root_kind.value == 'WFM-MainWnd' and kind in ('syslistview32', 'systreeview32', 'wfm-mainwnd'):
        marker = USER32.GetDlgItem(root, 0x7e02)
        value = ctypes.create_unicode_buffer(1025)
        if marker:
            _message(marker, 0xD, len(value), ctypes.addressof(value))
        if value.value != 'WFM-NVDA-2':
            return 'Trình quản lý tệp chưa có bản sửa bàn phím. Hãy đóng rồi mở lại môi trường sau khi cập nhật APK.'
        label = USER32.GetDlgItem(root, 0x7e03 if kind == 'systreeview32' else 0x7e01)
        _message(label, 0xD, len(value), ctypes.addressof(value))
        return value.value or 'Danh sách tệp đang cập nhật.'
    style = USER32.GetWindowLongW(info.focus, -16)
    if kind == 'edit' and style & 0x20:
        return 'Ô mật khẩu. Nội dung ẩn.'
    if kind == 'edit':
        value = ctypes.create_unicode_buffer(1025)
        _message(info.focus, 0xD, len(value), ctypes.addressof(value))
        return (value.value or 'Trống') + '. Ô nhập liệu.'
    if kind in ('listbox', 'combobox'):
        index = _message(info.focus, 0x188 if kind == 'listbox' else 0x147)
        if index < 0:
            return 'Danh sách. Chưa chọn mục nào.'
        length = _message(info.focus, 0x18A if kind == 'listbox' else 0x149, index)
        # LB_GETTEXT has no capacity parameter. Never call it with an undersized buffer.
        if length < 0 or length > 1024:
            return 'Mục được chọn có nội dung quá dài để đọc qua cầu nối.'
        value = ctypes.create_unicode_buffer(length + 1)
        _message(info.focus, 0x189 if kind == 'listbox' else 0x148, index, ctypes.addressof(value))
        return f'{value.value}. Mục {index + 1}.'
    if kind == 'button':
        USER32.GetWindowTextW(info.focus, name, len(name))
        if style & 0xf in (2, 3, 5, 6):
            return name.value + ('. Đã chọn.' if _message(info.focus, 0xF0) else '. Chưa chọn.')
        return name.value + '. Nút.'
    # NVDA handles editors, documents, custom controls and protected values itself.
    return None


def send_text(text):
    """KEYEVENTF_UNICODE handles Vietnamese independently of the Wine keyboard layout."""
    class KeyInput(ctypes.Structure):
        _fields_ = [('vk', wintypes.WORD), ('scan', wintypes.WORD), ('flags', wintypes.DWORD),
                    ('time', wintypes.DWORD), ('extra', ctypes.c_size_t)]
    class InputUnion(ctypes.Union):
        _fields_ = [('key', KeyInput), ('padding', ctypes.c_byte * (32 if ctypes.sizeof(ctypes.c_void_p) == 8 else 24))]
    class Input(ctypes.Structure):
        _fields_ = [('type', wintypes.DWORD), ('data', InputUnion)]
    send = USER32.SendInput
    send.argtypes = [wintypes.UINT, ctypes.POINTER(Input), ctypes.c_int]
    raw = text.encode('utf-16-le')
    for i in range(0, len(raw), 2):
        unit = int.from_bytes(raw[i:i+2], 'little')
        events = (Input * 2)()
        for j, flags in enumerate((4, 6)):
            events[j].type = 1; events[j].data.key.scan = unit; events[j].data.key.flags = flags
        if send(2, events, ctypes.sizeof(Input)) != 2:
            raise OSError('Windows rejected text input')


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
    def __init__(self):
        super().__init__()
        self._closed = False
        self._config = globalVars.appArgs.configPath
        self._path = os.path.join(self._config, 'winlator-status.json')
        self._session = secrets.token_hex(16)
        self._seen = deque(maxlen=128)
        self._lastSpeech = 0
        self._speechText = ''
        self._commandTimer = None
        self._feedbackTimer = None
        pre_speech.register(self._spoke)
        self._timer = wx.CallLater(2500, self._started)

    def _spoke(self, speechSequence, **kwargs):
        if any(isinstance(part, str) and part.strip() for part in speechSequence):
            self._lastSpeech = time.monotonic()
            self._speechText = ' '.join(part for part in speechSequence if isinstance(part, str))[:2048]

    def _started(self):
        if self._closed:
            return
        self._android_voice(False)
        synth = synthDriverHandler.getSynth()
        marker = os.path.join(globalVars.appArgs.configPath, 'winlator-voice-configured')
        if synth and synth.name == 'espeak' and not os.path.exists(marker):
            voices = [(identifier, info) for identifier, info in synth.availableVoices.items()
                      if (getattr(info, 'language', '') or '').replace('_', '-').lower().split('-')[0] == 'vi']
            if voices:
                voices.sort(key=lambda item: (getattr(item[1], 'language', '').lower() != 'vi', item[0]))
                synth.voice = voices[0][0]
                synth.saveSettings()
                with open(marker, 'w', encoding='utf-8') as stream:
                    stream.write(voices[0][0])
        ui.message('NVDA đã khởi động. Khi tự tắt TalkBack, bạn có thể vuốt một ngón để điều hướng, '
                   'chạm hai lần để Enter. Chạm ba ngón để mở menu điều khiển bằng giọng nói.')
        self._heartbeat()
        self._commands()

    def _android_voice(self, required):
        path = os.path.join(self._config, 'winlator-android-voice.json')
        try:
            with open(path, encoding='utf-8') as stream:
                endpoint = json.loads(stream.read(4096))
            if not endpoint.get('enabled'):
                raise RuntimeError('Android Vietnamese voice is unavailable')
            synth = synthDriverHandler.getSynth()
            if not synth or synth.name != 'winlatorAndroid':
                speech.cancelSpeech()
                if not synthDriverHandler.setSynth('winlatorAndroid'):
                    raise RuntimeError('Android speech connection failed')
                config.conf.save()
            return True
        except Exception:
            if required:
                raise
            return False

    def _sync_focus(self):
        try:
            current = api.getDesktopObject().objectWithFocus()
            if current and current != api.getFocusObject():
                eventHandler.executeEvent('gainFocus', current)
        except Exception:
            pass

    def _focus(self):
        try:
            text = native_focus_text()
        except Exception:
            text = None
        if text:
            ui.message(text)
            return
        self._sync_focus()
        focus = api.getFocusObject()
        if focus:
            speech.speakObject(focus, reason=controlTypes.OutputReason.QUERY)
        else:
            ui.message('Wine chưa cung cấp mục có tiêu điểm. Hãy thử Tab hoặc mở màn hình nền.')

    def _reply(self, request, ok, effect='handled'):
        self._write('winlator-reply.json', {'version': 1, 'session': self._session,
                    'id': request.get('id', ''), 'ok': bool(ok), 'effect': effect})

    def _write(self, name, value):
        path = os.path.join(self._config, name)
        try:
            with open(path + '.tmp', 'w', encoding='utf-8') as stream:
                json.dump(value, stream)
            os.replace(path + '.tmp', path)
        except OSError:
            pass

    def _feedback(self, request, started, effect='handled', direct=False):
        if self._closed:
            return
        try:
            # Let normal NVDA speech finish. Fill in missing Wine focus/selection events only.
            text = native_focus_text()
            if direct and text:
                if effect == 'boundary':
                    prefix = 'Đã ở đầu danh sách. ' if request['action'] in ('up', 'home', 'page_up') else 'Không có mục tiếp theo theo hướng này. '
                    text = prefix + text
                speech.cancelSpeech(); ui.message(text)
            elif text and (self._lastSpeech <= started or text.split('.')[0] not in self._speechText):
                speech.cancelSpeech(); ui.message(text)
            elif self._lastSpeech <= started:
                self._focus()
            self._reply(request, True, effect)
        except Exception:
            self._reply(request, False)

    def _execute(self, request):
        action = request['action']
        if action == 'message':
            speech.cancelSpeech(); ui.message(request.get('text', ''))
        elif action == 'silence':
            speech.cancelSpeech()
        elif action in ('android_voice', 'android_voice_test'):
            speech.cancelSpeech(); self._android_voice(True)
            if action == 'android_voice_test':
                ui.message('Đây là giọng tiếng Việt của Android. NVDA vẫn đang điều khiển môi trường Windows. '
                           'Bạn có thể tắt TalkBack và dùng các cử chỉ như trước.')
        elif action == 'espeak_voice':
            speech.cancelSpeech()
            if not synthDriverHandler.setSynth('espeak'):
                raise RuntimeError('Fallback voice is unavailable')
        elif action == 'focus':
            speech.cancelSpeech(); self._focus()
        elif action == 'text':
            if not wfm_text(request.get('text', '')):
                send_text(request.get('text', ''))
        elif action in KEYS:
            started = time.monotonic()
            root = wfm_root() if action in WFM_ACTIONS else None
            if root:
                # Only predefined integer actions cross processes. WFM changes its own real
                # control state on its GUI thread and reports the observed result.
                result = _message(root, 0x8000 + 0x4e, WFM_ACTIONS[action], 2, timeout=1600)
                if result not in (1, 2, 3):
                    raise RuntimeError('File manager did not handle the action')
                effect = {1: 'handled', 2: 'changed', 3: 'boundary'}[result]
                self._feedbackTimer = wx.CallLater(100, self._feedback, request, started, effect, True)
                return
            gesture = keyboardHandler.KeyboardInputGesture.fromName(KEYS[action])
            if action in ('window', 'nvda_menu', 'read_all'):
                # These are NVDA commands, not key presses for the Windows application.
                inputCore.manager.executeGesture(gesture)
            else:
                # Do not query MSAA / run an asynchronous NVDA script before delivering a key.
                # Wine's COM focus queries can stall; ordinary Windows keys must still arrive.
                speech.cancelSpeech()
                gesture.send()
            if action in NAVIGATION:
                self._feedbackTimer = wx.CallLater(220, self._feedback, request, started)
                return
        else:
            raise ValueError('Unsupported touch command')
        self._reply(request, True)

    def _commands(self):
        if self._closed:
            return
        path = os.path.join(self._config, 'winlator-command.json')
        request = None
        try:
            with open(path, 'rb') as stream:
                data = stream.read(4097)
            os.remove(path)
            if len(data) > 4096:
                raise ValueError('Oversized touch command')
            request = json.loads(data)
            if (request.get('version') != 1 or request.get('session') != self._session
                    or not isinstance(request.get('id'), str) or len(request['id']) > 64
                    or request['id'] in self._seen
                    or not -5 < time.time() - request['created'] < 3
                    or not isinstance(request.get('text', ''), str) or len(request.get('text', '')) > 512):
                raise ValueError('Invalid or expired touch command')
            self._seen.append(request['id'])
            self._execute(request)
        except FileNotFoundError:
            pass
        except Exception:
            # Never log command payloads: they may contain user input.
            if isinstance(request, dict) and request.get('session') == self._session:
                self._reply(request, False)
        self._commandTimer = wx.CallLater(40, self._commands)

    def _heartbeat(self):
        if self._closed:
            return
        synth = synthDriverHandler.getSynth()
        state = {'version': 1, 'pid': os.getpid(), 'heartbeat': int(time.time()), 'state': 'ready',
                 'synth': synth.name if synth else 'silence', 'commandProtocol': 1, 'session': self._session}
        self._write('winlator-status.json', state)
        self._timer = wx.CallLater(3000, self._heartbeat)

    def terminate(self):
        self._closed = True
        if self._timer:
            self._timer.Stop()
        if self._commandTimer:
            self._commandTimer.Stop()
        if self._feedbackTimer:
            self._feedbackTimer.Stop()
        pre_speech.unregister(self._spoke)
        try:
            os.remove(self._path)
        except OSError:
            pass
        super().terminate()
