# SPDX-License-Identifier: MIT
"""Local, session-bound touch commands. Bounded diagnostic telemetry is collected locally; explicit exports are initiated on Android."""
import ctypes
from ctypes import wintypes
from collections import deque
import json
import os
import re
import secrets
import time
import threading
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
from NVDAObjects.IAccessible import IAccessible
from NVDAObjects import NVDAObject
import wx


KEYS = {
    'up': 'upArrow', 'down': 'downArrow', 'left': 'leftArrow', 'right': 'rightArrow',
    'tab': 'tab', 'shift_tab': 'shift+tab', 'enter': 'enter', 'space': 'space',
    'escape': 'escape', 'home': 'home', 'end': 'end', 'page_up': 'pageUp', 'page_down': 'pageDown',
    'backspace': 'backspace', 'delete': 'delete', 'select_all': 'control+a',
    'copy': 'control+c', 'paste': 'control+v', 'cut': 'control+x',
    'window': 'NVDA+b', 'read_all': 'NVDA+downArrow',
}
NAVIGATION = {'up', 'down', 'left', 'right', 'tab', 'shift_tab', 'enter', 'space', 'escape',
              'home', 'end', 'page_up', 'page_down',
              'backspace', 'delete', 'select_all'}
SHORTCUT_ACTIONS = {**{value.lower(): action for action,value in KEYS.items()},
    'up':'up','down':'down','left':'left','right':'right','pageup':'page_up','pagedown':'page_down',
    'control+a':'select_all','control+c':'copy','control+x':'cut','control+v':'paste',
    'alt+tab':'alt_tab','alt+shift+tab':'alt_shift_tab'}


def shortcut_action(value):
    if not isinstance(value,str) or not 1 <= len(value) <= 80:
        raise ValueError('Invalid shortcut')
    parts=value.lower().split('+');modifiers=parts[:-1];key=parts[-1]
    if len(set(modifiers))!=len(modifiers) or any(m not in ('control','alt','shift','windows') for m in modifiers):
        raise ValueError('Invalid shortcut modifiers')
    if not re.fullmatch(r'[a-z0-9]|f(?:[1-9]|1[0-2])|up|down|left|right|enter|escape|tab|space|home|end|pageup|pagedown|insert|delete|backspace|minus|equal|comma|period|slash|backslash|semicolon|apostrophe|bracketleft|bracketright|control|windows|alt|shift',key):
        raise ValueError('Invalid shortcut key')
    if modifiers and key in ('control','windows','alt','shift'):
        raise ValueError('Modifier requires a normal key')
    ordered=[m for m in ('control','alt','shift','windows') if m in modifiers]
    return SHORTCUT_ACTIONS.get('+'.join(ordered+[key]))


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
USER32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
USER32.FindWindowW.restype = wintypes.HWND
USER32.GetDlgCtrlID.argtypes = [wintypes.HWND]
USER32.SetFocus.argtypes = [wintypes.HWND]
USER32.SetFocus.restype = wintypes.HWND
USER32.GetAsyncKeyState.argtypes = [ctypes.c_int]
USER32.GetAsyncKeyState.restype = ctypes.c_short
USER32.IsChild.argtypes = [wintypes.HWND, wintypes.HWND]
USER32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, ctypes.c_size_t, ctypes.c_ssize_t]
USER32.IsWindow.argtypes = [wintypes.HWND]
USER32.IsWindowEnabled.argtypes = [wintypes.HWND]
USER32.IsWindowVisible.argtypes = [wintypes.HWND]
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
    if value.value not in ('WFM-NVDA-2', 'WFM-NVDA-3'):
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


def menu_context():
    info = GUIThreadInfo(); info.cbSize = ctypes.sizeof(info)
    thread = USER32.GetWindowThreadProcessId(USER32.GetForegroundWindow(), None)
    return info if USER32.GetGUIThreadInfo(thread, ctypes.byref(info)) and info.flags & 0x1c else None


def native_menu_text():
    if not menu_context():
        return None
    popup = None; inaccessible = False
    for unused in range(16):
        popup = USER32.FindWindowExW(None, popup, '#32768', None)
        if not popup:
            break
        if not USER32.IsWindowVisible(popup):
            continue
        menu = _message(popup, 0x1e1)  # MN_GETHMENU: handle, never a cross-process pointer.
        count = USER32.GetMenuItemCount(menu)
        if not 0 < count <= 256:
            inaccessible = True
            continue
        for index in range(count):
            state = USER32.GetMenuState(menu, index, 0x400)
            if state != 0xffffffff and state & 0x80:
                text = ctypes.create_unicode_buffer(1025)
                USER32.GetMenuStringW(menu, index, text, len(text), 0x400)
                if text.value:
                    return text.value.replace('&', '').split('\t')[0] + f'. Mục trình đơn {index+1} trên {count}.'
    if inaccessible:
        return 'Trình đơn đang mở nhưng Wine chưa cung cấp tên mục cho NVDA. Vuốt trái hai ngón để đóng.'
    return 'Trình đơn đang mở. Vuốt lên hoặc xuống để chọn mục; vuốt trái hai ngón để đóng.'


def native_menu_key(action):
    info = menu_context()
    keys = {'up':0x26, 'down':0x28, 'left':0x25, 'right':0x27, 'enter':0x0d,
            'escape':0x1b, 'home':0x24, 'end':0x23}
    if not info or action not in keys:
        return False
    owner = info.menuOwner or USER32.GetForegroundWindow()
    if not USER32.PostMessageW(owner, 0x100, keys[action], 0):
        raise RuntimeError('Menu did not accept the navigation message')
    USER32.PostMessageW(owner, 0x101, keys[action], 0xc0000000)
    return True


def control_family(kind):
    value = kind.lower()
    match = re.match(r'^windowsforms10\.([a-z0-9_]+)\.', value)
    return match.group(1) if match else value



def recover_legacy_text(text):
    """Conservative display repair for known GBK-as-Latin1 signatures, never a code-page change.
    Latin accents alone are not evidence. Keep originals in diagnostics and never rewrite input/files.
    """
    if not isinstance(text, str) or len(text) > 8000:
        return text
    if not re.search(r'[ÐÓÊÎÏÒÔÖ¿¼½µ¶±×£¢¬ÂÃÅÆÇËÌÍÑÕÙÚÛÝÞ]{2}', text):
        return text
    def piece(value):
        try:
            candidate = value.encode('latin1').decode('gbk')
            if candidate.encode('gbk').decode('latin1') != value:
                return value
        except (UnicodeError, LookupError):
            return value
        if not any(word in candidate for word in ('信息', '语音', '配置', '键盘', '退出', '保存')):
            return value
        return candidate
    candidate = piece(text)
    if candidate != text:
        return candidate
    return ''.join(piece(part) if not part.isspace() else part for part in re.split(r'(\s+)', text))



def native_role(hwnd):
    kind = ctypes.create_unicode_buffer(256)
    USER32.GetClassNameW(hwnd, kind, len(kind))
    family = control_family(kind.value)
    if family == 'button':
        style = USER32.GetWindowLongW(hwnd, -16) & 15
        return 'GROUPING' if style == 7 else 'RADIOBUTTON' if style in (4, 9) else 'CHECKBOX' if style in (2, 3, 5, 6) else 'BUTTON' if style in (0, 1, 11) else None
    return {'edit':'EDITABLETEXT', 'listbox':'LIST', 'combobox':'COMBOBOX', 'syslistview32':'LIST',
            'systreeview32':'TREEVIEW', 'msctls_trackbar32':'SLIDER', 'static':'STATICTEXT'}.get(family)


def focus_native_control(target, root):
    """Explicit review activation only. Verify the actual foreign thread focus and always detach."""
    if USER32.GetForegroundWindow() != root or USER32.GetAncestor(target, 2) != root:
        return False
    if not USER32.IsWindowEnabled(target) or not USER32.IsWindowVisible(target):
        return False
    # Attaching queues can reset key state. Never do it during a physical modifier chord.
    if any(USER32.GetAsyncKeyState(key) & 0x8000 for key in (0x10, 0x11, 0x12, 0x5b, 0x5c)):
        return False
    current = ctypes.windll.kernel32.GetCurrentThreadId()
    thread = USER32.GetWindowThreadProcessId(target, None)
    attached = current != thread and USER32.AttachThreadInput(current, thread, True)
    if current != thread and not attached:
        return False
    try:
        if USER32.GetForegroundWindow() != root:
            return False
        USER32.SetFocus(target)
        info = GUIThreadInfo(); info.cbSize = ctypes.sizeof(info)
        return bool(USER32.GetGUIThreadInfo(thread, ctypes.byref(info)) and
                    (info.focus == target or USER32.IsChild(target, info.focus)))
    finally:
        if attached:
            USER32.AttachThreadInput(current, thread, False)


def native_inventory(root=None):
    """Bounded structure, not values: unknown/custom classes and Edit contents are never read."""
    root = root or USER32.GetForegroundWindow()
    result = dict(hwnd=int(root or 0), controls=[], limited=False, source='Win32')
    if not root:
        return result
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    started = time.monotonic()
    @callback_type
    def visit(hwnd, unused):
        if len(result['controls']) >= 96 or time.monotonic()-started > .15:
            result['limited'] = True; return False
        kind = ctypes.create_unicode_buffer(256)
        USER32.GetClassNameW(hwnd, kind, len(kind))
        family = control_family(kind.value)
        role = native_role(hwnd)
        text = ctypes.create_unicode_buffer(513)
        if family in ('static', 'button'):
            USER32.GetWindowTextW(hwnd, text, len(text))
        result['controls'].append(dict(hwnd=int(hwnd), kind=kind.value, role=role or 'UNKNOWN',
            text=text.value, visible=bool(USER32.IsWindowVisible(hwnd)), enabled=bool(USER32.IsWindowEnabled(hwnd)),
            tabstop=bool(USER32.GetWindowLongW(hwnd, -16) & 0x10000), controlId=int(USER32.GetDlgCtrlID(hwnd))))
        return True
    USER32.EnumChildWindows.argtypes = [wintypes.HWND, callback_type, wintypes.LPARAM]
    USER32.EnumChildWindows(root, visit, 0)
    result['elapsedMs'] = round((time.monotonic()-started)*1000)
    return result


def dialog_brief(text, previous_registration_failure=False):
    if previous_registration_failure and 'Install finished' in text:
        return 'Ứng dụng báo cài xong, nhưng trước đó đăng ký thư viện .NET đã lỗi. Chưa thể xác nhận cài đặt thành công.'
    if 'RegistrationServices.RegisterAssembly' in text and 'not implemented' in text:
        return 'Không hoàn tất được việc đăng ký thư viện .NET: môi trường chưa triển khai chức năng này. Có thể đọc đầy đủ thông báo trong phần Đọc màn hình.'
    if len(text) > 300 and re.search(r'(?:\r?\n| )\s*at [A-Za-z_][\w.]+\s*\(', text):
        first = text.splitlines()[0][:240]
        return first + '. Có chi tiết kỹ thuật trong nhật ký và mục Đọc đầy đủ thông báo.'
    return recover_legacy_text(text)

def native_window_snapshot():
    """Read labels/buttons only. Never read Edit/custom control values or password contents."""
    root = USER32.GetForegroundWindow()
    kind = ctypes.create_unicode_buffer(256); title = ctypes.create_unicode_buffer(512)
    USER32.GetClassNameW(root, kind, len(kind)); USER32.GetWindowTextW(root, title, len(title))
    result = dict(hwnd=int(root or 0), kind=kind.value, title=title.value, controls=[])
    if not root:
        result['dialog'] = False
        return result
    budget = 6000
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    @callback_type
    def visit(hwnd, unused):
        nonlocal budget
        if len(result['controls']) >= 48 or budget <= 0:
            result['limited'] = True
            return False
        if not USER32.IsWindowVisible(hwnd):
            return True
        child_kind = ctypes.create_unicode_buffer(256)
        USER32.GetClassNameW(hwnd, child_kind, len(child_kind))
        family = control_family(child_kind.value)
        if family not in ('static', 'button'):
            return True
        text = ctypes.create_unicode_buffer(min(1025, budget+1))
        USER32.GetWindowTextW(hwnd, text, len(text))
        if text.value:
            style = USER32.GetWindowLongW(hwnd, -16) & 0xf
            role = 'group' if family == 'button' and style == 7 else 'radio' if family == 'button' and style in (4, 9) else 'check' if family == 'button' and style in (2, 3, 5, 6) else family
            result['controls'].append(dict(hwnd=int(hwnd), kind=child_kind.value, family=family, role=role,
                text=text.value, enabled=bool(USER32.IsWindowEnabled(hwnd))))
            budget -= len(text.value)
        return True
    USER32.EnumChildWindows.argtypes = [wintypes.HWND, callback_type, wintypes.LPARAM]
    USER32.EnumChildWindows(root, visit, 0)
    result['dialog'] = kind.value == '#32770'
    return result


def native_window_text(snapshot=None, include_buttons=False):
    snapshot = snapshot or native_window_snapshot()
    labels = [snapshot.get('title', '')]
    labels.extend(control['text'] + ({'button':'. Nút', 'group':'. Nhóm', 'check':'. Ô chọn', 'radio':'. Nút chọn'}.get(control.get('role', control['family']), '')) for control in snapshot['controls'] if control['family'] in ('static', 'button') and (include_buttons or control['family'] == 'static'))
    seen = set(); parts = []
    for label in labels:
        if label and label not in seen:
            seen.add(label); parts.append(label)
    return recover_legacy_text('. '.join(parts))


def native_focus_text():
    """Real Win32 selection when Wine MSAA events/roles are incomplete. Bounded calls only."""
    menu = native_menu_text()
    if menu:
        return menu
    thread = USER32.GetWindowThreadProcessId(USER32.GetForegroundWindow(), None)
    info = GUIThreadInfo(); info.cbSize = ctypes.sizeof(info)
    if not USER32.GetGUIThreadInfo(thread, ctypes.byref(info)) or not info.focus:
        return None
    name = ctypes.create_unicode_buffer(256)
    USER32.GetClassNameW(info.focus, name, len(name))
    kind = control_family(name.value)
    root = USER32.GetAncestor(info.focus, 2)
    root_kind = ctypes.create_unicode_buffer(256)
    USER32.GetClassNameW(root, root_kind, len(root_kind))
    if root_kind.value == 'WFM-MainWnd' and kind in ('syslistview32', 'systreeview32', 'wfm-mainwnd'):
        marker = USER32.GetDlgItem(root, 0x7e02)
        value = ctypes.create_unicode_buffer(1025)
        if marker:
            _message(marker, 0xD, len(value), ctypes.addressof(value))
        if value.value not in ('WFM-NVDA-2', 'WFM-NVDA-3'):
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
        if style & 0xf in (2, 3, 4, 5, 6, 9):
            state = _message(info.focus, 0xF0)
            return name.value + ('. Chọn một phần.' if state == 2 else '. Đã chọn.' if state else '. Chưa chọn.')
        return name.value + ('. Nhóm.' if style & 0xf == 7 else '. Nút.')
    if kind == 'msctls_trackbar32':
        USER32.GetWindowTextW(info.focus, name, len(name))
        return f'{name.value or "Thanh trượt"}. Giá trị {_message(info.focus, 0x400)}.'
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


# All handles come from the current desktop. Calls are bounded or verified.
USER32.EnumWindows.argtypes = [ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM), wintypes.LPARAM]
USER32.IsWindowVisible.argtypes = [wintypes.HWND]
USER32.IsWindowEnabled.argtypes = [wintypes.HWND]
USER32.IsWindow.argtypes = [wintypes.HWND]
USER32.IsIconic.argtypes = [wintypes.HWND]
USER32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
USER32.SetForegroundWindow.argtypes = [wintypes.HWND]
USER32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
USER32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
USER32.GetWindow.restype = wintypes.HWND
USER32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
USER32.FindWindowW.restype = wintypes.HWND
USER32.FindWindowExW.argtypes = [wintypes.HWND, wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR]
USER32.FindWindowExW.restype = wintypes.HWND
USER32.GetMenuItemCount.argtypes = [wintypes.HMENU]
USER32.GetMenuState.argtypes = [wintypes.HMENU, wintypes.UINT, wintypes.UINT]
USER32.GetMenuState.restype = wintypes.UINT
USER32.GetMenuStringW.argtypes = [wintypes.HMENU, wintypes.UINT, wintypes.LPWSTR, ctypes.c_int, wintypes.UINT]
USER32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, ctypes.c_size_t, ctypes.c_ssize_t]


def runtime_windows():
    windows = []
    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def visit(hwnd, unused):
        if len(windows) >= 128:
            return False
        if not USER32.IsWindowVisible(hwnd) or USER32.GetWindowLongW(hwnd, -20) & (0x80 | 0x08000000):
            return True
        title = ctypes.create_unicode_buffer(256); kind = ctypes.create_unicode_buffer(256)
        USER32.GetWindowTextW(hwnd, title, len(title)); USER32.GetClassNameW(hwnd, kind, len(kind))
        owner = USER32.GetWindow(hwnd, 4)
        if title.value and kind.value not in ('Progman', 'Shell_TrayWnd', '#32769'):
            # Prefer a modal dialog over the disabled window which owns it.
            if USER32.IsWindowEnabled(hwnd) and not (owner and USER32.IsWindowVisible(owner) and USER32.IsWindowEnabled(owner)):
                windows.append((hwnd, title.value, kind.value))
        return True
    USER32.EnumWindows(visit, 0)
    return windows


def activate_window(hwnd):
    if not USER32.IsWindow(hwnd):
        raise RuntimeError('The selected window has closed')
    current = ctypes.windll.kernel32.GetCurrentThreadId()
    foreground = USER32.GetWindowThreadProcessId(USER32.GetForegroundWindow(), None)
    target = USER32.GetWindowThreadProcessId(hwnd, None)
    attached = []
    try:
        for thread in set((foreground, target)) - {current, 0}:
            if USER32.AttachThreadInput(current, thread, True):
                attached.append(thread)
        if USER32.IsIconic(hwnd):
            USER32.ShowWindow(hwnd, 9)
        USER32.SetForegroundWindow(hwnd)
    finally:
        for thread in reversed(attached):
            USER32.AttachThreadInput(current, thread, False)
    return USER32.GetForegroundWindow() == hwnd


def switch_window(files_only=False, reverse=False):
    current = USER32.GetForegroundWindow()
    choices = [row for row in runtime_windows() if (row[2]=='WFM-MainWnd' if files_only else row[0]!=current)]
    if not choices:
        ui.message('Không có cửa sổ khác đang mở.' if not files_only else 'Trình quản lý tệp chưa mở.'); return
    hwnd, title, kind = choices[-1 if reverse else 0]
    activate_window(hwnd)
    return hwnd, title


def shell_action(action):
    tray = USER32.FindWindowW('Shell_TrayWnd', None)
    desktop = USER32.FindWindowW('Progman', None)
    if action == 'start_menu':
        start = USER32.GetDlgItem(tray, 0) if tray else None
        kind = ctypes.create_unicode_buffer(64)
        if start:
            USER32.GetClassNameW(start, kind, len(kind))
        if not start or kind.value.lower() != 'button' or not USER32.IsWindowVisible(start):
            ui.message('Môi trường Wine này không có trình đơn Start. Dùng danh sách cửa sổ để đổi ứng dụng.'); return 'unavailable'
        if not USER32.PostMessageW(start, 0xf5, 0, 0):
            raise RuntimeError('The Wine shell rejected Start')
        return 'pending'
    elif desktop:
        if not activate_window(desktop):
            raise RuntimeError('Wine did not activate the desktop')
        ui.message('Màn hình nền Windows.'); return 'changed'
    else:
        ui.message('Môi trường Wine này chưa cung cấp màn hình nền có thể điều khiển. '
                   'Computer là đầu danh sách ổ đĩa. Dùng danh sách cửa sổ để đổi ứng dụng.')
        return 'unavailable'


def label(control):
    text = control.GetLabel().replace('&', '').strip()
    container = control.GetContainingSizer()
    labels = [item.GetWindow() for item in container.GetChildren() if item.IsWindow() and isinstance(item.GetWindow(), wx.StaticText)] if container else []
    caption = labels[0].GetLabel().replace('&', '').strip() if len(labels)==1 else ''
    prefix = caption + '. ' if caption else ''
    if isinstance(control, wx.TextCtrl):
        if control.HasFlag(wx.TE_PASSWORD):
            return 'Ô mật khẩu. Nội dung ẩn.'
        return prefix + (control.GetValue()[:1024] or 'Trống') + '. Ô nhập liệu.'
    if isinstance(control, wx.ListCtrl):
        index = control.GetFocusedItem()
        if index < 0:
            index = control.GetFirstSelected()
        if index >= 0:
            return f'{control.GetItemText(index)}. Mục {index+1} trên {control.GetItemCount()}.'
    if isinstance(control, (wx.ListBox, wx.Choice, wx.ComboBox)):
        selected = control.GetSelection()
        if selected != wx.NOT_FOUND:
            return prefix + f'{control.GetString(selected)}. Mục {selected+1} trên {control.GetCount()}.'
    if isinstance(control, wx.CheckBox):
        state = control.Get3StateValue() if control.Is3State() else int(control.GetValue())
        return text + ('. Chọn một phần.' if state==2 else '. Đã chọn.' if state else '. Chưa chọn.')
    if isinstance(control, wx.Slider):
        return f'{caption or text or "Thanh trượt"}. {control.GetValue()}.'
    return text or control.GetName() or 'Điều khiển NVDA'


def announce(control):
    speech.cancelSpeech(); ui.message(label(control))


def dispatch(control, eventType):
    event = wx.CommandEvent(eventType.typeId, control.GetId())
    event.SetEventObject(control)
    if isinstance(control, (wx.ListBox, wx.Choice, wx.ComboBox)):
        event.SetInt(control.GetSelection())
        event.SetString(control.GetStringSelection())
    elif isinstance(control, wx.CheckBox):
        event.SetInt(control.Get3StateValue() if control.Is3State() else int(control.GetValue()))
    control.GetEventHandler().ProcessEvent(event)


class TouchMenu:
    """The choices and handlers come from NVDA's live wx.Menu, not a copied command list."""
    def __init__(self):
        self.dialog = None
        self.levels = []
        self.items = []
        self.windowMode = False
        self.returnWindow = None
        self.pendingWindow = None

    @property
    def active(self):
        return bool(self.dialog and self.dialog.IsShown() and USER32.GetForegroundWindow() == self.dialog.GetHandle())

    def open(self):
        import gui
        if self.active:
            announce(self.list)
            return
        self.close()
        self.returnWindow = USER32.GetForegroundWindow()
        self.windowMode = False
        self.dialog = wx.Dialog(gui.mainFrame, title='Trình đơn NVDA', size=(520, 420))
        self.list = wx.ListBox(self.dialog)
        box = wx.BoxSizer(wx.VERTICAL); box.Add(self.list, 1, wx.EXPAND | wx.ALL, 12)
        self.dialog.SetSizer(box)
        self.dialog.Bind(wx.EVT_CLOSE, self._closed)
        self.list.Bind(wx.EVT_LISTBOX_DCLICK, lambda event: self.action('enter'))
        gui.mainFrame.sysTrayIcon.evaluateUpdatePendingUpdateMenuItemCommand()
        self.levels = [(gui.mainFrame.sysTrayIcon.menu, 'Trình đơn NVDA', 0)]
        self._populate()
        self.dialog.Show(); self.dialog.Raise(); self.list.SetFocus()
        ui.message('Trình đơn NVDA. ' + label(self.list))

    def open_windows(self):
        import gui
        self.close()
        self.returnWindow = USER32.GetForegroundWindow()
        self.windowMode = True
        self.items = runtime_windows()
        self.dialog = wx.Dialog(gui.mainFrame, title='Cửa sổ đang mở', size=(520, 420))
        self.list = wx.ListBox(self.dialog, choices=[row[1] for row in self.items])
        if self.items:
            self.list.SetSelection(0)
        box = wx.BoxSizer(wx.VERTICAL); box.Add(self.list, 1, wx.EXPAND | wx.ALL, 12)
        self.dialog.SetSizer(box); self.dialog.Bind(wx.EVT_CLOSE, self._closed)
        self.list.Bind(wx.EVT_LISTBOX_DCLICK, lambda event: self.action('enter'))
        self.dialog.Show(); self.dialog.Raise(); self.list.SetFocus()
        ui.message('Cửa sổ đang mở. ' + (label(self.list) if self.items else 'Không có cửa sổ.'))

    def _closed(self, event):
        dialog = self.dialog; self.dialog = None; self.levels = []
        if dialog:
            dialog.Destroy()
        previous = self.returnWindow; self.returnWindow = None
        if previous and USER32.IsWindow(previous):
            activate_window(previous)

    def close(self):
        if self.dialog:
            self._closed(None)

    def _populate(self):
        menu, title, selected = self.levels[-1]
        self.items = [item for item in menu.GetMenuItems() if not item.IsSeparator()]
        self.list.Set([item.GetItemLabelText() + ('. Trình đơn con' if item.GetSubMenu() else '')
                       + ('. Không khả dụng' if not item.IsEnabled() else '') for item in self.items])
        if self.items:
            self.list.SetSelection(min(selected, len(self.items)-1))
        self.dialog.SetTitle(title)

    def action(self, action, text=''):
        if not self.active:
            return False
        if action in ('up', 'down', 'tab', 'shift_tab', 'home', 'end', 'page_up', 'page_down'):
            count = len(self.items); old = self.list.GetSelection()
            if count:
                nextIndex = (0 if action == 'home' else count-1 if action == 'end' else
                             max(0, min(count-1, old + (-1 if action in ('up', 'shift_tab', 'page_up') else 1))))
                self.list.SetSelection(nextIndex)
                if self.levels:
                    self.levels[-1] = (*self.levels[-1][:2], nextIndex)
            announce(self.list); return True
        if action in ('escape', 'left', 'backspace'):
            if len(self.levels)>1:
                self.levels.pop(); self._populate(); announce(self.list)
            else:
                closing = 'Đã đóng danh sách cửa sổ.' if self.windowMode else 'Đã đóng trình đơn NVDA.'
                self.close(); ui.message(closing)
            return True
        if action in ('enter', 'right', 'space'):
            index = self.list.GetSelection()
            if index == wx.NOT_FOUND:
                return True
            if self.windowMode:
                hwnd, title, kind = self.items[index]
                self.close()
                activate_window(hwnd)
                self.pendingWindow = (hwnd,title)
                return True
            item = self.items[index]
            if not item.IsEnabled():
                ui.message('Mục này không khả dụng.'); return True
            submenu = item.GetSubMenu()
            if submenu:
                self.levels.append((submenu, item.GetItemLabelText(), 0)); self._populate(); announce(self.list)
            elif action != 'right':
                import gui
                identifier = item.GetId()
                self.close()
                event = wx.CommandEvent(wx.EVT_MENU.typeId, identifier)
                event.SetEventObject(gui.mainFrame.sysTrayIcon)
                wx.CallAfter(gui.mainFrame.sysTrayIcon.ProcessEvent, event)
            return True
        if action in ('focus', 'window', 'read_all'):
            announce(self.list); return True
        return False


def focused_control():
    pid = wintypes.DWORD()
    USER32.GetWindowThreadProcessId(USER32.GetForegroundWindow(), ctypes.byref(pid))
    if pid.value != os.getpid():
        return None
    control = wx.Window.FindFocus()
    if control:
        top = wx.GetTopLevelParent(control)
        if top and top.IsShown() and isinstance(top, wx.Dialog):
            return control
    return None


def control_action(action, text=''):
    control = focused_control()
    if not control:
        return False
    if action in ('focus', 'window'):
        announce(control); return True
    if action in ('tab', 'shift_tab'):
        control.Navigate(wx.NavigationKeyEvent.IsForward if action == 'tab' else wx.NavigationKeyEvent.IsBackward)
        wx.CallLater(60, lambda: announce(wx.Window.FindFocus()) if wx.Window.FindFocus() else None)
        return True
    if action == 'escape':
        top = wx.GetTopLevelParent(control)
        cancel = top.FindWindow(wx.ID_CANCEL)
        if isinstance(cancel, wx.Button) and cancel.IsEnabled():
            dispatch(cancel, wx.EVT_BUTTON)
        else:
            top.Close()
        ui.message('Đã đóng hộp thoại NVDA.'); return True
    if action in ('enter', 'space') and isinstance(control, (wx.Button, wx.CheckBox)):
        if isinstance(control, wx.CheckBox):
            state = control.Get3StateValue() if control.Is3State() else int(control.GetValue())
            control.SetValue(state != 1); dispatch(control, wx.EVT_CHECKBOX); announce(control)
        else:
            dispatch(control, wx.EVT_BUTTON)
        return True
    if action in ('up', 'down', 'home', 'end') and isinstance(control, wx.ListCtrl):
        count = control.GetItemCount(); old = control.GetFocusedItem()
        if count:
            selected = 0 if action=='home' else count-1 if action=='end' else max(0,min(count-1,old+(-1 if action=='up' else 1)))
            control.SetItemState(-1, 0, wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED)
            control.Select(selected); control.Focus(selected); control.EnsureVisible(selected)
        wx.CallLater(60, announce, control); return True
    if action in ('up', 'down', 'home', 'end') and isinstance(control, (wx.ListBox, wx.Choice)):
        count = control.GetCount(); old = control.GetSelection()
        if count:
            selected = 0 if action=='home' else count-1 if action=='end' else max(0,min(count-1,old+(-1 if action=='up' else 1)))
            control.SetSelection(selected)
            dispatch(control, wx.EVT_LISTBOX if isinstance(control, wx.ListBox) else wx.EVT_CHOICE)
        announce(control); return True
    if action in ('up', 'down', 'left', 'right', 'home', 'end') and isinstance(control, wx.Slider):
        old=control.GetValue()
        value=control.GetMin() if action=='home' else control.GetMax() if action=='end' else old+(-1 if action in ('up','left') else 1)
        control.SetValue(max(control.GetMin(),min(control.GetMax(),value)))
        dispatch(control, wx.EVT_SLIDER); announce(control); return True
    if isinstance(control, wx.TextCtrl):
        if action == 'text':
            control.WriteText(text); return True
        if action == 'select_all':
            control.SelectAll(); return True
        if action in ('copy', 'cut', 'paste'):
            getattr(control, action.capitalize())(); return True
    return False


class WinlatorNativeControl(NVDAObject):
    """Use a real native class/style when Wine's API object has no role."""
    def _get_role(self):
        role = native_role(self.windowHandle)
        return getattr(controlTypes.Role, role, controlTypes.Role.UNKNOWN) if role else controlTypes.Role.UNKNOWN


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
    def __init__(self):
        super().__init__()
        self._closed = False
        self._touchMenu = TouchMenu()
        self._config = globalVars.appArgs.configPath
        self._path = os.path.join(self._config, 'winlator-status.json')
        self._session = secrets.token_hex(16)
        self._seen = deque(maxlen=256)
        self._requestLock = threading.RLock()
        self._diagnosticLock = threading.RLock()
        self._writeLock = threading.RLock()
        self._keyStop = threading.Event()
        self._pendingGuiKey = None
        self._latestKeyId = None
        self._lastDialog = None
        self._dialogDetails = ''
        self._registrationFailures = {}
        self._wfmPending = None
        self._launchSeen = deque(maxlen=128)
        self._objects = []
        self._objectRoot = None
        self._objectIndex = -1
        self._lastInventory = None
        self._unchangedFocus = None
        self._unchangedCount = 0
        self._feedbackSerial = 0
        self._lastSpeech = 0
        self._speechText = ''
        self._lastContent = ''
        self._controlSpeech = 0
        self._diagnosticEvents = deque()
        self._diagnosticCharacters = 0
        self._diagnosticSequence = 0
        self._diagnosticDirty = False
        self._diagnosticFlush = 0
        self._diagnosticContext = None
        self._diagnosticProtected = None
        self._commandTimer = None
        self._feedbackTimer = None
        pre_speech.register(self._spoke)
        self._timer = wx.CallLater(2500, self._started)

    def chooseNVDAObjectOverlayClasses(self, obj, clsList):
        try:
            # ContentGenericClient declares a literal UNKNOWN role, even when the initial
            # IAccessible object's Window fallback already reports a native button role.
            unknown = obj.role == controlTypes.Role.UNKNOWN or any(cls.__dict__.get('role') == controlTypes.Role.UNKNOWN for cls in clsList)
            if unknown and getattr(obj, 'IAccessibleChildID', 0) == 0:
                role = native_role(obj.windowHandle)
                if role:
                    clsList.insert(0, WinlatorNativeControl)
                    self._trace('role.repair', 'api=' + type(obj).__name__ + '; hwnd=' + str(int(obj.windowHandle or 0)) + '; role=' + role + '; replacing=' + ','.join(cls.__name__ for cls in clsList[1:]))
        except Exception as error:
            self._trace('role.error', type(error).__name__)

    def _trace(self, kind, details):
        value = str(details)
        with self._diagnosticLock:
            for start in range(0, max(1, len(value)), 4000):
                part = value[start:start+4000]
                self._diagnosticSequence += 1
                event = dict(seq=self._diagnosticSequence, kind=kind, details=part,
                             part=start//4000+1, parts=max(1, (len(value)+3999)//4000), time=round(time.time(), 3))
                self._diagnosticEvents.append(event)
                self._diagnosticCharacters += len(part) + 180
                while self._diagnosticCharacters > 32000:
                    old = self._diagnosticEvents.popleft()
                    self._diagnosticCharacters -= len(old['details']) + 180
            self._diagnosticDirty = True

    def _protected_focus(self):
        try:
            thread = USER32.GetWindowThreadProcessId(USER32.GetForegroundWindow(), None)
            info = GUIThreadInfo(); info.cbSize = ctypes.sizeof(info)
            if thread and USER32.GetGUIThreadInfo(thread, ctypes.byref(info)) and info.focus:
                kind = ctypes.create_unicode_buffer(256)
                USER32.GetClassNameW(info.focus, kind, len(kind))
                if 'edit' in kind.value.lower():
                    return bool(USER32.GetWindowLongW(info.focus, -16) & 0x20)
            # Never add MSAA/COM queries before sending keys or speech. Wine may stall them.
            return self._diagnosticProtected is not False
        except Exception:
            return True  # Unknown password state must not expose spoken characters.

    def _trace_context(self, reason, obj=None, windows=False):
        try:
            hwnd = USER32.GetForegroundWindow()
            pid = wintypes.DWORD()
            thread = USER32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            info = GUIThreadInfo(); info.cbSize = ctypes.sizeof(info)
            USER32.GetGUIThreadInfo(thread, ctypes.byref(info))
            def describe(handle, content=True):
                kind = ctypes.create_unicode_buffer(256); name = ctypes.create_unicode_buffer(256)
                USER32.GetClassNameW(handle, kind, len(kind))
                if content and 'edit' not in kind.value.lower():
                    USER32.GetWindowTextW(handle, name, len(name))
                return dict(hwnd=int(handle or 0), kind=kind.value, name=name.value,
                            enabled=bool(USER32.IsWindowEnabled(handle)))
            context = dict(window=describe(hwnd), pid=pid.value, thread=thread,
                           focus=describe(info.focus, not self._protected_focus()),
                           active=int(info.active or 0), menu=int(info.menuOwner or 0))
            if obj is not None:
                try:
                    states = obj.states
                    protected = controlTypes.State.PROTECTED in states
                    editable = obj.role == controlTypes.Role.EDITABLETEXT
                    context['nvda'] = dict(api=type(obj).__name__, windowHandle=int(getattr(obj, 'windowHandle', 0) or 0), childId=getattr(obj, 'IAccessibleChildID', None), role=getattr(obj.role, 'name', str(obj.role)), states=sorted(getattr(state, 'name', str(state)) for state in states),
                                           name='[hidden]' if protected or editable else (obj.name or '')[:512])
                except Exception as error:
                    context['nvdaError'] = type(error).__name__
            if windows:
                if context['window']['kind'] == '#32770':
                    context['dialog'] = native_window_snapshot()
                if context['window']['kind'] != 'WFM-MainWnd' and self._lastInventory != (int(hwnd or 0), pid.value):
                    self._lastInventory = (int(hwnd or 0), pid.value)
                    context['inventory'] = native_inventory(hwnd)
                    context['codePages'] = dict(ansi=int(ctypes.windll.kernel32.GetACP()), oem=int(ctypes.windll.kernel32.GetOEMCP()), userLCID=int(ctypes.windll.kernel32.GetUserDefaultLCID()), systemLCID=int(ctypes.windll.kernel32.GetSystemDefaultLCID()))
                context['windows'] = [dict(hwnd=int(handle), title=title, kind=kind)
                                      for handle, title, kind in runtime_windows()[:16]]
            encoded = json.dumps(context, ensure_ascii=False, sort_keys=True)
            if windows or encoded != self._diagnosticContext:
                self._trace('context', reason + '; ' + encoded)
                self._diagnosticContext = encoded
        except Exception as error:
            self._trace('context.error', reason + '; ' + type(error).__name__)

    def event_gainFocus(self, obj, nextHandler):
        nextHandler()
        try:
            self._diagnosticProtected = controlTypes.State.PROTECTED in obj.states
        except Exception:
            self._diagnosticProtected = None
        self._trace_context('NVDA gainFocus', obj)

    def _flush_diagnostics(self, force=False):
        with self._diagnosticLock:
            now = time.monotonic()
            if self._diagnosticDirty and (force or now-self._diagnosticFlush >= .2):
                self._write('winlator-diagnostics.json', dict(version=1, session=self._session,
                            events=list(self._diagnosticEvents)))
                self._diagnosticDirty = False
                self._diagnosticFlush = now

    def _spoke(self, speechSequence, **kwargs):
        if not self._protected_focus() and isinstance(speechSequence, list):
            for index, part in enumerate(speechSequence):
                if isinstance(part, str):
                    recovered = recover_legacy_text(part)
                    if recovered != part:
                        self._trace('encoding.repair', json.dumps(dict(raw=part, spoken=recovered, source='latin1-to-gbk roundtrip'), ensure_ascii=False))
                        speechSequence[index] = recovered
        if any(isinstance(part, str) and part.strip() for part in speechSequence):
            self._trace('speech', '[protected or unknown focus: speech hidden]' if self._protected_focus() else ' '.join(part for part in speechSequence if isinstance(part, str)))
            self._lastSpeech = time.monotonic()
            self._speechText = ' '.join(part for part in speechSequence if isinstance(part, str))[:2048]
            if not self._controlSpeech:
                self._lastContent = self._speechText

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
                   'chạm hai lần để Enter. Nhấn Quay lại để mở menu điều khiển.')
        self._heartbeat()
        self._commands()
        self._keyThread = threading.Thread(target=self._key_loop, name='WinlatorKeys', daemon=True)
        self._keyThread.start()

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

    def _control_message(self, text):
        self._controlSpeech += 1
        try:
            speech.cancelSpeech(); ui.message(text)
        finally:
            self._controlSpeech -= 1

    def _reply(self, request, ok, effect='handled', text=None):
        elapsed = round((time.monotonic()-request.get('_acceptedAt', time.monotonic()))*1000)
        reply = dict(version=1, session=self._session, id=request.get('id',''), ok=bool(ok), effect=effect,
                     processingMs=elapsed)
        if text is not None:
            reply['text'] = text[:2048]
        if request.get('_keyChannel') and self._latestKeyId not in (None, request.get('id')):
            self._trace('reply.stale', 'id=' + request.get('id','') + '; not overwriting the newer key acknowledgement')
        else:
            self._write('winlator-key-reply.json' if request.get('_keyChannel') else 'winlator-reply.json', reply)
        self._trace('reply', 'id=' + request.get('id','') + '; ok=' + str(bool(ok)) + '; effect=' + effect + '; processingMs=' + str(elapsed))
        phase = 'route acknowledgement; X outcome logged separately' if effect == 'external' else 'after ' + request.get('action','')
        self._trace_context(phase, windows=True)
        self._flush_diagnostics(True)
        if text is not None:
            wx.CallLater(3000, self._erase_reply, reply['id'])

    def _erase_reply(self, identifier):
        path=os.path.join(self._config,'winlator-reply.json')
        try:
            with open(path,encoding='utf-8') as stream:
                reply=json.load(stream)
            if reply.get('id')==identifier:
                os.remove(path)
        except (OSError,ValueError):
            pass

    def _write(self, name, value):
        path = os.path.join(self._config, name)
        with self._writeLock:
            try:
                with open(path + '.tmp', 'w', encoding='utf-8') as stream:
                    json.dump(value, stream, ensure_ascii=False)
                os.replace(path + '.tmp', path)
            except OSError as error:
                # Do not include exception text: file paths can contain private user content.
                pass

    def _external_feedback(self, trigger, serial):
        if self._closed or serial != self._feedbackSerial:
            return
        started = time.monotonic()
        try:
            snapshot = native_window_snapshot()
            signature = (snapshot['hwnd'], native_window_text(snapshot)) if snapshot['dialog'] else None
            announced = False
            if signature and signature != self._lastDialog:
                body_available = any(control['family'] == 'static' for control in snapshot['controls'])
                snapshot['bodyAvailable'] = body_available
                self._trace('dialog', json.dumps(snapshot, ensure_ascii=False))
                content = native_window_text(snapshot)
                self._dialogDetails = content
                pid = wintypes.DWORD(); USER32.GetWindowThreadProcessId(snapshot['hwnd'], ctypes.byref(pid))
                now = time.monotonic()
                self._registrationFailures = {key: value for key, value in self._registrationFailures.items() if now-value < 300}
                if 'RegistrationServices.RegisterAssembly' in content and 'not implemented' in content:
                    if len(self._registrationFailures) >= 16:
                        self._registrationFailures.clear()
                    self._registrationFailures[pid.value] = now
                    self._trace('compatibility.failure', 'pid=' + str(pid.value) + '; facility=dotnet-register-assembly; not treated as installation success')
                content = dialog_brief(content, pid.value in self._registrationFailures)
                if not body_available:
                    content += '. Chưa lấy được nội dung thông báo.'
                focused = native_focus_text()
                speech.cancelSpeech(); ui.message(content + ('. ' + focused if focused else ''))
                announced = True
            self._lastDialog = signature
            if not announced and not control_action('focus'):
                text = native_focus_text()
                focus = api.getFocusObject()
                if not text and focus and focus.role in (controlTypes.Role.PANE, controlTypes.Role.WINDOW, controlTypes.Role.UNKNOWN):
                    signature = (snapshot['hwnd'], getattr(focus, 'windowHandle', None), recover_legacy_text(focus.name or ''))
                    self._unchangedCount = self._unchangedCount+1 if signature == self._unchangedFocus else 1
                    self._unchangedFocus = signature
                    if self._unchangedCount == 3:
                        ui.message('Chưa đọc được các thành phần bên trong cửa sổ. Dùng Duyệt thành phần trong phần Đọc màn hình.')
                        self._trace('accessibility.unresolved', 'Repeated root-only feedback; actual UI change unknown')
                    elif self._unchangedCount < 3:
                        self._focus()
                else:
                    self._unchangedFocus = None; self._unchangedCount = 0
                    self._focus()
            self._trace('feedback.observed', 'trigger=' + trigger + '; elapsedMs=' + str(round((time.monotonic()-started)*1000)))
            self._trace_context('observed after X; trigger=' + trigger, windows=True)
        except Exception as error:
            self._trace('feedback.error', 'trigger=' + trigger + '; ' + type(error).__name__)

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

    def _window_feedback(self, request, hwnd, title, attempt=0):
        if self._closed:
            return
        if USER32.GetForegroundWindow() == hwnd:
            speech.cancelSpeech(); ui.message(title)
            self._reply(request, True, 'changed')
        elif attempt < 12 and USER32.IsWindow(hwnd):
            self._feedbackTimer=wx.CallLater(60, self._window_feedback, request, hwnd, title, attempt+1)
        else:
            ui.message('Wine chưa chuyển được sang cửa sổ đã chọn. Hãy thử lại từ danh sách cửa sổ.')
            self._reply(request, False, 'unchanged')

    def _shell_feedback(self, request):
        if self._closed:
            return
        text = native_menu_text()
        if text:
            ui.message('Trình đơn Start. ' + text)
            self._reply(request, True, 'changed')
        else:
            ui.message('Wine chưa mở được trình đơn Start. Dùng danh sách cửa sổ để đổi ứng dụng.')
            self._reply(request, True, 'unavailable')

    def _wfm_start(self, request, root, action):
        marker = USER32.GetDlgItem(root, 0x7e02)
        version = ctypes.create_unicode_buffer(64)
        USER32.GetWindowTextW(marker, version, len(version))
        if version.value != 'WFM-NVDA-3':
            return False  # Legacy protocol remains supported for a running old environment.
        if self._wfmPending:
            self._reply(request, False, 'busy'); return True
        if action not in ('enter', 'backspace'):
            return False
        token = secrets.randbelow(0xffffff-1)+1
        pending = dict(root=root, token=token, request=request, started=time.monotonic(), progress=False)
        self._wfmPending = pending
        deadline = (ctypes.windll.kernel32.GetTickCount()+3000) & 0xffffffff
        if not USER32.PostMessageW(root, 0x8000+0x4f, (token<<8)|WFM_ACTIONS[action], deadline):
            self._wfmPending = None; self._reply(request, False, 'rejected'); return True
        self._trace('operation.submitted', 'id=' + request['id'] + '; token=' + str(token) + '; action=' + action)
        # A submitted operation is not a completed operation. Android can now reject new WFM keys as busy.
        self._reply(request, True, 'pending')
        wx.CallLater(100, self._wfm_poll, pending)
        return True

    def _wfm_poll(self, pending):
        if self._closed or self._wfmPending is not pending:
            return
        age = time.monotonic()-pending['started']
        text = ctypes.create_unicode_buffer(96)
        hwnd = USER32.GetDlgItem(pending['root'], 0x7e04)
        if hwnd:
            USER32.GetWindowTextW(hwnd, text, len(text))  # Stored static caption, no synchronous WM_GETTEXT.
        parts = text.value.split('|')
        if len(parts) == 3 and parts[0] == str(pending['token']) and parts[1] in ('done', 'expired'):
            self._wfmPending = None
            self._trace('operation.completed', 'id=' + pending['request']['id'] + '; token=' + str(pending['token']) + '; state=' + parts[1] + '; effect=' + parts[2] + '; elapsedMs=' + str(round(age*1000)))
            self._collect_launches(pending['root'])
            if parts[1] == 'expired':
                ui.message('Thao tác đã hết hạn trước khi thực hiện.'); return
            if parts[2] == '0':
                ui.message('Trình quản lý tệp chưa thực hiện được thao tác.'); return
            # Read the real selection only while this is still the foreground window.
            if USER32.GetForegroundWindow() == pending['root']:
                try:
                    text = native_focus_text()
                    if text:
                        speech.cancelSpeech(); ui.message(text)
                except Exception as error:
                    self._trace('operation.feedback.error', type(error).__name__)
            return
        if age > 12:
            self._wfmPending = None
            self._trace('operation.unconfirmed', 'id=' + pending['request']['id'] + '; no completion after 12 seconds; never replayed')
            ui.message('Chưa xác nhận được kết quả thao tác. Không tự thực hiện lại.'); return
        if age > 1 and not pending['progress']:
            pending['progress'] = True
            self._trace('operation.progress', 'id=' + pending['request']['id'] + '; state=' + (parts[1] if len(parts)==3 and parts[0]==str(pending['token']) else 'submitted'))
            if USER32.GetForegroundWindow() == pending['root']:
                self._control_message('Đang xử lý thao tác. Hãy chờ.')
        wx.CallLater(100, self._wfm_poll, pending)

    def _collect_launches(self, root=None):
        root = root or wfm_root()
        if not root:
            return
        control = USER32.GetDlgItem(root, 0x7e05)
        if not control:
            return
        value = ctypes.create_unicode_buffer(2048)
        USER32.GetWindowTextW(control, value, len(value))
        for line in value.value.splitlines():
            parts = line.split('|', 4)
            if len(parts) != 5 or not parts[0].isdigit():
                continue
            key = (int(root), parts[0])
            if key in self._launchSeen:
                continue
            self._launchSeen.append(key)
            self._trace('process.launch', json.dumps(dict(sequence=parts[0], state=parts[1], pid=parts[2], code=parts[3], name=parts[4]), ensure_ascii=False))

    def _close_window(self, request):
        hwnd = USER32.GetForegroundWindow()
        pid = wintypes.DWORD(); USER32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not hwnd or pid.value == os.getpid() or not USER32.IsWindowEnabled(hwnd):
            self._reply(request, False, 'unavailable'); return
        if not USER32.PostMessageW(hwnd, 0x112, 0xf060, 0):
            self._reply(request, False, 'rejected'); return
        self._trace('window.close.requested', 'id=' + request['id'] + '; hwnd=' + str(int(hwnd)) + '; pid=' + str(pid.value))
        self._reply(request, True, 'pending')
        wx.CallLater(100, self._close_poll, request['id'], hwnd, pid.value, 0)

    def _close_poll(self, identifier, hwnd, pid, attempt):
        if self._closed:
            return
        current_pid = wintypes.DWORD(); USER32.GetWindowThreadProcessId(hwnd, ctypes.byref(current_pid))
        if not USER32.IsWindow(hwnd) or current_pid.value != pid:
            self._trace('window.close.result', 'id=' + identifier + '; state=closed')
            self._control_message('Đã đóng cửa sổ.'); return
        foreground = USER32.GetForegroundWindow()
        if foreground != hwnd and not USER32.IsWindowEnabled(hwnd):
            self._trace('window.close.result', 'id=' + identifier + '; state=confirmation; hwnd=' + str(int(foreground or 0)))
            self._feedbackSerial += 1
            self._external_feedback(identifier, self._feedbackSerial); return
        if attempt < 19:
            wx.CallLater(100, self._close_poll, identifier, hwnd, pid, attempt+1); return
        self._trace('window.close.result', 'id=' + identifier + '; state=unconfirmed; foreground=' + str(int(foreground or 0)))
        self._control_message('Ứng dụng chưa đóng cửa sổ.')

    def _browse_objects(self, action):
        root = USER32.GetForegroundWindow()
        pid = wintypes.DWORD(); USER32.GetWindowThreadProcessId(root, ctypes.byref(pid))
        identity = (int(root or 0), pid.value)
        if not root:
            self._control_message('Chưa có cửa sổ hiện tại.'); return
        if self._objectRoot != identity or action == 'inspect_controls':
            inventory = native_inventory(root)
            self._trace('accessibility.inventory', json.dumps(inventory, ensure_ascii=False))
            self._objects = [dict(native=row, label=recover_legacy_text(row['text']) or getattr(controlTypes.Role, row['role'], controlTypes.Role.UNKNOWN).displayString)
                             for row in inventory['controls'] if row['visible'] and row['role'] != 'UNKNOWN']
            # Read NVDA's active API object (IAccessible/UIA when available). Do not assume HWNDs are all elements.
            if len(self._objects) < 96:
                started = time.monotonic()
                try:
                    foreground = api.getForegroundObject()
                    provider_hwnd = int(getattr(foreground, 'windowHandle', 0) or 0)
                    if provider_hwnd and USER32.GetAncestor(provider_hwnd, 2) != root:
                        self._trace('accessibility.provider.stale', 'Provider belongs to another window; ignoring its children')
                        foreground = None
                    children = foreground.children if foreground else []
                    native_handles = {entry['native']['hwnd'] for entry in self._objects}
                    for obj in children[:64]:
                        if len(self._objects) >= 96 or time.monotonic()-started > .2:
                            self._trace('accessibility.limit', 'NVDA child traversal time budget'); break
                        handle = int(getattr(obj, 'windowHandle', 0) or 0)
                        if handle in native_handles and getattr(obj, 'IAccessibleChildID', 0) == 0:
                            continue
                        states = obj.states
                        if controlTypes.State.INVISIBLE in states or controlTypes.State.PROTECTED in states:
                            continue
                        name = '' if obj.role == controlTypes.Role.EDITABLETEXT else (obj.name or '')
                        self._objects.append(dict(obj=obj, label=recover_legacy_text(name) or obj.role.displayString))
                    self._trace('accessibility.provider', 'api=' + type(foreground).__name__ + '; children=' + str(len(children)) + '; usable=' + str(len(self._objects)))
                except Exception as error:
                    self._trace('accessibility.provider.error', type(error).__name__)
            self._objectRoot = identity; self._objectIndex = -1
        if not self._objects:
            self._control_message('Chưa lấy được thành phần trợ năng trong cửa sổ này.'); return
        if action == 'object_activate':
            if self._objectIndex < 0:
                self._control_message('Hãy chọn một thành phần trước.'); return
            entry = self._objects[self._objectIndex]
            row = entry.get('native')
            if row:
                target = row['hwnd']
                if USER32.GetAncestor(target, 2) != root or not USER32.IsWindowEnabled(target) or not USER32.IsWindowVisible(target) or native_role(target) != row['role'] or USER32.GetDlgCtrlID(target) != row['controlId']:
                    self._control_message('Thành phần không còn khả dụng.'); return
                if row['role'] in ('EDITABLETEXT', 'LIST', 'COMBOBOX', 'TREEVIEW', 'SLIDER'):
                    focused = focus_native_control(target, root)
                    self._trace('accessibility.focus', 'hwnd=' + str(target) + '; verified=' + str(focused))
                    if focused:
                        self._focus()
                    else:
                        self._control_message('Chưa chuyển được tiêu điểm vào thành phần này.'); return
                    return
                if row['role'] not in ('BUTTON', 'CHECKBOX', 'RADIOBUTTON'):
                    self._control_message('Chưa có thao tác kích hoạt cho thành phần này.'); return
                focus_native_control(target, root)
                USER32.PostMessageW(target, 0xf5, 0, 0)  # BM_CLICK: actual native button, no guessed key.
            else:
                obj = entry['obj']
                if controlTypes.State.UNAVAILABLE in obj.states:
                    self._control_message('Thành phần không khả dụng.'); return
                try:
                    obj.doAction()
                except (NotImplementedError, AttributeError):
                    obj.setFocus()
            self._trace('accessibility.activate', 'index=' + str(self._objectIndex) + '; result=requested')
            self._feedbackSerial += 1
            wx.CallLater(180, self._external_feedback, '', self._feedbackSerial)
            return
        count = len(self._objects)
        self._objectIndex = (self._objectIndex + (-1 if action == 'object_previous' else 1)) % count
        entry = self._objects[self._objectIndex]
        self._trace('accessibility.browse', 'index=' + str(self._objectIndex) + '; count=' + str(count) + '; source=' + ('Win32' if 'native' in entry else 'NVDA'))
        # This is a review cursor, never pretend it moved the application's keyboard focus.
        self._control_message('Thành phần ' + str(self._objectIndex+1) + ' trên ' + str(count) + '. ' + entry['label'] + ('. Không khả dụng.' if entry.get('native', {}).get('enabled') is False else ''))

    def _execute(self, request):
        action = request['action']
        if action == 'close_window':
            self._close_window(request); return
        if action in ('inspect_controls', 'object_next', 'object_previous', 'object_activate'):
            self._browse_objects(action); self._reply(request, True); return
        if action == 'dialog_details':
            speech.cancelSpeech(); ui.message(self._dialogDetails or 'Chưa có thông báo để đọc.'); self._reply(request, True); return
        external = action == 'shortcut'
        if external:
            action=shortcut_action(request.get('text',''))
            if action is None:
                self._reply(request,True,'external'); return
            request=dict(request,action=action)
        if action == 'copy_last':
            self._reply(request,bool(self._lastContent),'clipboard',self._lastContent); return
        if action == 'repeat_last':
            self._control_message(self._lastContent or 'Chưa có câu để đọc lại.')
            self._reply(request,True); return
        if action == 'external_feedback':
            trigger = request.get('text', '')
            if not re.fullmatch(r'[a-f0-9-]{0,64}', trigger):
                trigger = '[redacted]'
            self._feedbackSerial += 1
            serial = self._feedbackSerial
            self._reply(request, True, 'scheduled')
            wx.CallLater(40, self._external_feedback, trigger, serial)
            return
        if action == 'window':
            snapshot = native_window_snapshot()
            if snapshot['dialog'] or snapshot['kind'].lower().startswith('windowsforms10.window.'):
                self._trace('window.read', json.dumps(snapshot, ensure_ascii=False))
                speech.cancelSpeech(); ui.message(native_window_text(snapshot, True))
                self._reply(request, True); return
        if self._touchMenu.action(action, request.get('text', '')) or control_action(action, request.get('text', '')):
            pending = self._touchMenu.pendingWindow
            self._touchMenu.pendingWindow = None
            if pending:
                self._window_feedback(request, *pending)
            else:
                self._reply(request, True)
            return
        if native_menu_key(action):
            self._feedbackTimer = wx.CallLater(180, self._feedback, request, time.monotonic())
            return
        if action in ('alt_tab', 'alt_shift_tab', 'files'):
            pending = switch_window(action=='files',action=='alt_shift_tab')
            if pending:
                self._window_feedback(request, *pending)
            else:
                self._reply(request, True, 'unavailable')
            return
        if action == 'windows':
            self._touchMenu.open_windows(); self._reply(request, True); return
        if action in ('desktop', 'start_menu'):
            effect = shell_action(action)
            if effect == 'pending':
                self._feedbackTimer = wx.CallLater(250, self._shell_feedback, request)
            else:
                self._reply(request, True, effect)
            return
        if action == 'nvda_menu':
            self._touchMenu.open()
            self._reply(request, True)
            return
        if action == 'message':
            self._control_message(request.get('text', ''))
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
                if self._wfm_start(request, root, action):
                    return
                # Only predefined integer actions cross processes. WFM changes its own real
                # control state on its GUI thread and reports the observed result.
                result = _message(root, 0x8000 + 0x4e, WFM_ACTIONS[action], 2, timeout=1600)
                if result not in (1, 2, 3):
                    if external:
                        self._reply(request,True,'external'); return
                    raise RuntimeError('File manager did not handle the action')
                effect = {1: 'handled', 2: 'changed', 3: 'boundary'}[result]
                self._feedbackTimer = wx.CallLater(100, self._feedback, request, started, effect, True)
                return
            if external and action not in ('window','read_all'):
                self._reply(request,True,'external'); return
            gesture = keyboardHandler.KeyboardInputGesture.fromName(KEYS[action])
            if action in ('window', 'read_all'):
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

    def _read_request(self, name):
        with self._requestLock:
            path = os.path.join(self._config, name)
            with open(path, 'rb') as stream:
                data = stream.read(4097)
            os.remove(path)
            if len(data) > 4096:
                raise ValueError('Oversized touch command')
            request = json.loads(data)
            if not isinstance(request, dict):
                raise ValueError('Command must be an object')
            request['_keyChannel'] = name == 'winlator-key-command.json'
            if request['_keyChannel'] and request.get('session') == self._session and isinstance(request.get('id'), str):
                self._latestKeyId = request['id']
            age = time.time()-request.get('created', 0)
            lifetime = 7 if request.get('action') == 'external_feedback' else 3
            if (request.get('version') != 1 or request.get('session') != self._session
                    or not isinstance(request.get('id'), str) or len(request['id']) > 64
                    or request['id'] in self._seen or not -5 < age < lifetime
                    or not isinstance(request.get('text', ''), str) or len(request.get('text', '')) > 512):
                if request.get('session') == self._session and isinstance(request.get('id'), str) and len(request['id']) <= 64:
                    self._reply(request, False, 'expired_or_invalid')
                raise ValueError('Invalid or expired touch command')
            self._seen.append(request['id'])
            request['_acceptedAt'] = time.monotonic()
            self._log_request(request, age)
            return request

    def _log_request(self, request, age):
        action = request.get('action', ''); payload = request.get('text', '')
        detail = 'id=' + request['id'] + '; action=' + action + '; transportAgeMs=' + str(round(age*1000))
        if action == 'shortcut':
            try:
                shortcut_action(payload)
                printable = re.fullmatch(r'(?:shift\+)?(?:[a-z0-9]|space|minus|equal|comma|period|slash|backslash|semicolon|apostrophe|bracketleft|bracketright)', payload)
                detail += '; shortcut=' + ('[typed key hidden]' if printable else payload)
            except ValueError:
                detail += '; shortcut=[invalid rule hidden]'
        elif action == 'external_feedback' and re.fullmatch(r'[a-f0-9-]{0,64}', payload):
            detail += '; trigger=' + payload
        elif payload:
            detail += '; input hidden; characters=' + str(len(payload))
        self._trace('command', detail)

    def _key_cancelled(self, request):
        identifier = request.get('id', '')
        return bool(re.fullmatch(r'[a-f0-9-]{1,64}', identifier) and
                    os.path.isfile(os.path.join(self._config, 'winlator-key-cancel-' + identifier)))

    def _clean_key_cancellations(self):
        for name in os.listdir(self._config):
            if re.fullmatch(r'winlator-key-cancel-[a-f0-9-]{1,64}', name):
                path = os.path.join(self._config, name)
                try:
                    if time.time()-os.path.getmtime(path) > 15:
                        os.remove(path)
                except OSError:
                    pass

    def _foreign_foreground(self):
        hwnd = USER32.GetForegroundWindow()
        kind = ctypes.create_unicode_buffer(256)
        USER32.GetClassNameW(hwnd, kind, len(kind))
        pid = wintypes.DWORD(); USER32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return bool(hwnd and pid.value != os.getpid() and kind.value != 'WFM-MainWnd')

    def _check_pending_key(self):
        with self._requestLock:
            request = self._pendingGuiKey
            if not request or request.get('_guiState') != 'queued':
                return
            cancelled = self._key_cancelled(request)
            expired = not -5 < time.time()-request['created'] < 3
            external = not cancelled and not expired and self._foreign_foreground()
            if not cancelled and not expired and not external:
                return
            request['_guiState'] = 'cancelled' if cancelled else 'expired' if expired else 'routed'
            self._pendingGuiKey = None
        self._trace('key.transition', 'id=' + request['id'] + '; ' + request['_guiState'])
        self._reply(request, not (expired or cancelled), 'cancelled' if cancelled else 'expired' if expired else 'external')

    def _key_loop(self):
        last = 0
        while not self._keyStop.is_set():
            request = None
            try:
                self._check_pending_key()
                if time.monotonic()-last >= 1:
                    self._clean_key_cancellations()
                    self._write('winlator-key-status.json', dict(version=1, state='ready', session=self._session,
                        heartbeat=int(time.time()), commandProtocol=1, keyProtocol=1))
                    last = time.monotonic()
                request = self._read_request('winlator-key-command.json')
                request['_keyChannel'] = True
                if request.get('action') != 'shortcut':
                    raise ValueError('Key mailbox only accepts shortcuts')
                shortcut_action(request.get('text', ''))
                if self._foreign_foreground():
                    # No NVDA/MSAA/wx calls here: a slow gainFocus callback must not block physical keys.
                    self._reply(request, True, 'external')
                elif self._wfmPending:
                    self._reply(request, False, 'busy')
                else:
                    with self._requestLock:
                        if self._pendingGuiKey:
                            self._pendingGuiKey['_guiState'] = 'superseded'
                        request['_guiState'] = 'queued'
                        self._pendingGuiKey = request
                    wx.CallAfter(self._execute_key_on_gui, request)
            except FileNotFoundError:
                pass
            except Exception as error:
                self._trace('key.error', type(error).__name__)
                if request is not None:
                    request['_keyChannel'] = True
                    self._reply(request, False, 'rejected')
            self._flush_diagnostics()
            self._keyStop.wait(.025)

    def _execute_key_on_gui(self, request):
        if self._closed:
            return
        with self._requestLock:
            if request.get('_guiState', 'queued') != 'queued':
                return
            request['_guiState'] = 'executing'
            if self._pendingGuiKey is request:
                self._pendingGuiKey = None
        if self._key_cancelled(request):
            self._reply(request, False, 'cancelled'); return
        if not -5 < time.time()-request['created'] < 3:
            self._reply(request, False, 'expired'); return
        try:
            self._trace_context('before native shortcut', windows=True)
            self._execute(request)
        except Exception as error:
            self._trace('key.error', type(error).__name__)
            self._reply(request, False)

    def _commands(self):
        if self._closed:
            return
        request = None
        try:
            request = self._read_request('winlator-command.json')
            self._trace_context('before ' + request.get('action',''), windows=True)
            self._execute(request)
        except FileNotFoundError:
            pass
        except Exception as error:
            self._trace('command.error', type(error).__name__)
            if request is not None:
                self._reply(request, False)
        self._flush_diagnostics()
        self._commandTimer = wx.CallLater(40, self._commands)

    def _heartbeat(self):
        try:
            root = USER32.FindWindowW('WFM-MainWnd', None)
            self._collect_launches(root)
        except Exception as error:
            self._trace('process.monitor.error', type(error).__name__)
        if self._closed:
            return
        self._trace_context('heartbeat')
        self._flush_diagnostics()
        synth = synthDriverHandler.getSynth()
        state = {'version': 1, 'pid': os.getpid(), 'heartbeat': int(time.time()), 'state': 'ready',
                 'synth': synth.name if synth else 'silence', 'commandProtocol': 1, 'keyProtocol': 1, 'session': self._session}
        self._write('winlator-status.json', state)
        self._timer = wx.CallLater(3000, self._heartbeat)

    def terminate(self):
        self._closed = True
        self._keyStop.set()
        if hasattr(self, "_keyThread"):
            self._keyThread.join(timeout=1)
        self._touchMenu.close()
        try:
            os.remove(os.path.join(self._config,'winlator-reply.json'))
        except OSError:
            pass
        for name in ('winlator-key-status.json', 'winlator-key-command.json', 'winlator-key-reply.json'):
            try:
                os.remove(os.path.join(self._config, name))
            except OSError:
                pass
        if self._timer:
            self._timer.Stop()
        if self._commandTimer:
            self._commandTimer.Stop()
        if self._feedbackTimer:
            self._feedbackTimer.Stop()
        pre_speech.unregister(self._spoke)
        try:
            os.remove(os.path.join(self._config, 'winlator-diagnostics.json'))
            os.remove(self._path)
        except OSError:
            pass
        super().terminate()
