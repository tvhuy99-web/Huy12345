#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compile the PE32 proxy; other exports are real PE forwarders, not guessed ABIs."""
import json
from pathlib import Path
import subprocess
from game_voice import EXPORTS, pe_exports

ROOT=Path(__file__).resolve().parents[1]
def build(output=None):
    output=Path(output) if output else ROOT/'app/app/src/main/assets/nvda/voice-trace-x86.dll'
    output.parent.mkdir(parents=True,exist_ok=True)
    definition=output.with_suffix('.def')
    traced=dict(xyttsInitA='traceInitA@8',xyttsInitW='traceInitW@8',
                xyttsSpeakA='traceSpeakA@4',xyttsSpeakW='traceSpeakW@4',
                xyttsSpeak2A='traceSpeak2A@4',xyttsSpeak2W='traceSpeak2W@4',
                xyttsStop='traceStop@0',xyttsPause='tracePause@0',
                xyttsSetNotify='traceNotify@12',xyttsUninit='traceUninit@4')
    lines=['LIBRARY xinyitts','EXPORTS']
    for ordinal,name in enumerate(EXPORTS,1):
        target=traced.get(name,'winlator-voice-original.'+name)
        lines.append(f'  {name}={target} @{ordinal}')
    definition.write_text('\n'.join(lines)+'\n')
    subprocess.run(['i686-w64-mingw32-gcc','-std=c11','-O2','-Wall','-Wextra','-Werror','-shared','-static-libgcc',
                    str(ROOT/'runtime-nvda/voice-trace.c'),str(definition),'-o',str(output),'-luser32'],check=True)
    definition.unlink()
    assert pe_exports(output.read_bytes())==dict(zip(EXPORTS,range(1,len(EXPORTS)+1)))
    print('Verified x86 voice diagnostic DLL and all 31 original export ordinals')

if __name__=='__main__':build()
