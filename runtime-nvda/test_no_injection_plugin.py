# SPDX-License-Identifier: MIT
"""CI-only NVDA add-on. Never copied to APK assets or the portable package."""
import ctypes
import os
import globalVars
import globalPluginHandler
import keyboardHandler
import json
import traceback
import time
import sys
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
            # Block our bridge's legacy injection, not NVDA's own caret scripts.
            # EditableText deliberately replays an intercepted physical arrow before reading it.
            frame = sys._getframe(1); bridge = False
            for unused in range(16):
                if frame is None: break
                if frame.f_globals.get('__name__') == 'globalPlugins.winlatorStartup':
                    bridge = True; break
                frame = frame.f_back
            if bridge and os.path.exists(os.path.join(self._config, 'winlator-test-block-injection')):
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
        request = None; observed = {}
        try:
            with open(path) as stream:
                request = json.load(stream)
            os.remove(path)
            from globalPlugins.winlatorStartup import GUIThreadInfo, USER32, label, _message, native_menu_text, native_focus_text
            hwnd = USER32.GetForegroundWindow()
            info = GUIThreadInfo(); info.cbSize = ctypes.sizeof(info)
            USER32.GetGUIThreadInfo(USER32.GetWindowThreadProcessId(hwnd, None), ctypes.byref(info))
            title = ctypes.create_unicode_buffer(256); kind = ctypes.create_unicode_buffer(256)
            USER32.GetWindowTextW(hwnd, title, len(title)); USER32.GetClassNameW(hwnd, kind, len(kind))
            focusKind = ctypes.create_unicode_buffer(256)
            USER32.GetClassNameW(info.focus, focusKind, len(focusKind))
            observed = dict(id=request['id'], foreground=int(hwnd or 0), foregroundTitle=title.value,
                foregroundClass=kind.value, focus=int(info.focus or 0), focusClass=focusKind.value,
                menuMode=bool(info.flags & 0x1c), windows=[w.GetTitle() for w in wx.GetTopLevelWindows() if isinstance(w, wx.TopLevelWindow) and w.IsShown()])
            if kind.value=='NvdaTouchFixture':
                observed['controls'] = dict(combo=_message(USER32.GetDlgItem(hwnd,105),0x147),
                    radio=_message(USER32.GetDlgItem(hwnd,106),0xf0), slider=_message(USER32.GetDlgItem(hwnd,107),0x400))
            if request.get('operation')=='read-focus':
                observed['nativeFocusText']=native_focus_text(request.get('action'))
            if observed['menuMode']:
                observed['menuRead']=native_menu_text()
                menus=[]; popup=None
                for unused in range(16):
                    popup=USER32.FindWindowExW(None,popup,'#32768',None)
                    if not popup: break
                    handle=_message(popup,0x1e1)
                    count=USER32.GetMenuItemCount(handle)
                    entries=[]
                    for index in range(max(0,min(count,32))):
                        value=ctypes.create_unicode_buffer(256)
                        USER32.GetMenuStringW(handle,index,value,len(value),0x400)
                        entries.append(dict(text=value.value,state=USER32.GetMenuState(handle,index,0x400)))
                    menus.append(dict(popup=int(popup),visible=bool(USER32.IsWindowVisible(popup)),handle=handle,count=count,items=entries))
                observed['nativeMenus']=menus
            if request.get('operation')=='stall':
                def stall():
                    marker=os.path.join(self._config,'winlator-test-stall-active')
                    with open(marker,'w') as stream:
                        stream.write('CI only')
                    time.sleep(3.4)
                    os.remove(marker)
                wx.CallLater(30,stall)
            if request.get('operation')=='clipboard':
                import api
                observed['clipboardText']=api.getClipData()
            import api
            nvda_focus=api.getFocusObject()
            observed['nvdaRole']=getattr(nvda_focus.role,'name',str(nvda_focus.role)) if nvda_focus else None
            focused = wx.Window.FindFocus()
            observed['wxFocus'] = None
            if focused:
                observed['wxFocus'] = dict(handle=int(focused.GetHandle()),kind=type(focused).__name__)
                try:
                    observed['wxFocus']['label']=label(focused)
                except Exception:
                    observed['wxFocus']['label']=''
                    observed['wxFocus']['labelError']=traceback.format_exc()
            if focused:
                top=wx.GetTopLevelParent(focused)
                categories=getattr(top,'catListCtrl',None)
                if categories:
                    observed['settings']=dict(handle=int(categories.GetHandle()), count=categories.GetItemCount(),
                        selected=categories.GetFocusedItem())
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
            if request:
                observed.update(id=request['id'],inspectionError=traceback.format_exc())
                with open(os.path.join(self._config,'winlator-test-observed.json'),'w') as stream:
                    json.dump(observed,stream)
        self._timer = wx.CallLater(50, self._inspect)

    def terminate(self):
        self._timer.Stop()
        keyboardHandler.KeyboardInputGesture.send = self._original_key
        ctypes.windll.user32.SendInput = self._original_input
        super().terminate()
