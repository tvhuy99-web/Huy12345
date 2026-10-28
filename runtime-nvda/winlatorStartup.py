# SPDX-License-Identifier: MIT
"""NVDA add-on: startup speech and local health, with no captured UI content."""
import json
import os
import time
import globalVars
import globalPluginHandler
import ui
import wx


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
    def __init__(self):
        super().__init__()
        self._closed = False
        self._path = os.path.join(globalVars.appArgs.configPath, 'winlator-status.json')
        self._timer = wx.CallLater(2500, self._started)

    def _started(self):
        if self._closed:
            return
        ui.message('NVDA đã khởi động. Bạn có thể dùng các phím điều hướng Windows.')
        self._heartbeat()

    def _heartbeat(self):
        if self._closed:
            return
        state = {'version': 1, 'pid': os.getpid(), 'heartbeat': int(time.time()), 'state': 'ready'}
        temporary = self._path + '.tmp'
        try:
            with open(temporary, 'w', encoding='utf-8') as stream:
                json.dump(state, stream)
            os.replace(temporary, self._path)
        except OSError:
            pass
        self._timer = wx.CallLater(3000, self._heartbeat)

    def terminate(self):
        self._closed = True
        if self._timer:
            self._timer.Stop()
        try:
            os.remove(self._path)
        except OSError:
            pass
        super().terminate()
