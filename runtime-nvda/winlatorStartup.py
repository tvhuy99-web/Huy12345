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
    'backspace': 'backspace', 'delete': 'delete', 'select_all': 'control+a',
    'copy': 'control+c', 'paste': 'control+v', 'cut': 'control+x',
    'window': 'NVDA+b', 'read_all': 'NVDA+downArrow',
}
NAVIGATION = {'up', 'down', 'left', 'right', 'tab', 'shift_tab', 'enter', 'space', 'escape',
              'home', 'end', 'page_up', 'page_down',
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
        if style & 0xf in (2, 3, 4, 5, 6, 9):
            state = _message(info.focus, 0xF0)
            return name.value + ('. Chọn một phần.' if state == 2 else '. Đã chọn.' if state else '. Chưa chọn.')
        return name.value + '. Nút.'
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


def switch_window(files_only=False):
    current = USER32.GetForegroundWindow()
    choices = [row for row in runtime_windows() if (row[2]=='WFM-MainWnd' if files_only else row[0]!=current)]
    if not choices:
        ui.message('Không có cửa sổ khác đang mở.' if not files_only else 'Trình quản lý tệp chưa mở.'); return
    hwnd, title, kind = choices[0]
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


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
    def __init__(self):
        super().__init__()
        self._closed = False
        self._touchMenu = TouchMenu()
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

    def _execute(self, request):
        action = request['action']
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
        if action in ('alt_tab', 'files'):
            pending = switch_window(action=='files')
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
        self._touchMenu.close()
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
