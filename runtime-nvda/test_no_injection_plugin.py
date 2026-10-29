# SPDX-License-Identifier: MIT
"""CI-only NVDA add-on. Never copied to APK assets or the portable package."""
import ctypes
import os
import globalVars
import globalPluginHandler
import keyboardHandler
import json
import wx
from ctypes import wintypes


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
    def __init__(self):
        super().__init__()
        self._config = globalVars.appArgs.configPath
        self._timer = wx.CallLater(100, self._inspect)
        self._original_key = keyboardHandler.KeyboardInputGesture.send
        self._original_input = ctypes.windll.user32.SendInput

        def check():
            if os.path.exists(os.path.join(self._config, 'winlator-test-block-injection')):
                with open(os.path.join(self._config, 'winlator-test-injection-attempts'), 'a', encoding='ascii') as stream:
                    stream.write('1\n')
                raise RuntimeError('CI deliberately blocked the old keyboard injection path')

        def key(gesture, *args, **kwargs):
            check()
            return self._original_key(gesture, *args, **kwargs)

        def send_input(*args):
            check()
            return self._original_input(*args)

        keyboardHandler.KeyboardInputGesture.send = key
        ctypes.windll.user32.SendInput = send_input

    def _inspect(self):
        path = os.path.join(self._config, 'winlator-test-inspect.json')
        try:
            with open(path) as stream:
                request = json.load(stream)
            os.remove(path)
            from globalPlugins.winlatorStartup import GUIThreadInfo, USER32, label, _message
            hwnd = USER32.GetForegroundWindow()
            info = GUIThreadInfo(); info.cbSize = ctypes.sizeof(info)
            USER32.GetGUIThreadInfo(USER32.GetWindowThreadProcessId(hwnd, None), ctypes.byref(info))
            title = ctypes.create_unicode_buffer(256); kind = ctypes.create_unicode_buffer(256)
            USER32.GetWindowTextW(hwnd, title, len(title)); USER32.GetClassNameW(hwnd, kind, len(kind))
            focusKind = ctypes.create_unicode_buffer(256)
            USER32.GetClassNameW(info.focus, focusKind, len(focusKind))
            observed = dict(id=request['id'], foreground=int(hwnd or 0), foregroundTitle=title.value,
                foregroundClass=kind.value, focus=int(info.focus or 0), focusClass=focusKind.value,
                menuMode=bool(info.flags & 0x1c), windows=[w.GetTitle() for w in wx.GetTopLevelWindows() if w.IsShown()])
            if kind.value=='NvdaTouchFixture':
                observed['controls'] = dict(combo=_message(USER32.GetDlgItem(hwnd,105),0x147),
                    radio=_message(USER32.GetDlgItem(hwnd,106),0xf0), slider=_message(USER32.GetDlgItem(hwnd,107),0x400))
            focused = wx.Window.FindFocus()
            observed['wxFocus'] = dict(handle=int(focused.GetHandle()), kind=type(focused).__name__, label=label(focused)) if focused else None
            for plugin in globalPluginHandler.runningPlugins:
                menu = getattr(plugin, '_touchMenu', None)
                if menu and menu.active:
                    observed['touchMenu'] = dict(title=menu.dialog.GetTitle(), selected=menu.list.GetSelection(),
                        items=[menu.list.GetString(i) for i in range(menu.list.GetCount())])
            with open(os.path.join(self._config, 'winlator-test-observed.json.tmp'), 'w') as stream:
                json.dump(observed, stream)
            os.replace(os.path.join(self._config, 'winlator-test-observed.json.tmp'),
                       os.path.join(self._config, 'winlator-test-observed.json'))
        except Exception:
            pass
        self._timer = wx.CallLater(50, self._inspect)

    def terminate(self):
        self._timer.Stop()
        keyboardHandler.KeyboardInputGesture.send = self._original_key
        ctypes.windll.user32.SendInput = self._original_input
        super().terminate()
