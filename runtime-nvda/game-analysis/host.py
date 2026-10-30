#!/usr/bin/env python3
"""Run only the supplied game and a pinned NVDA bundle in disposable containers."""
import json
from pathlib import Path
import shutil
import subprocess
import sys


def main():
    data, results = map(lambda s:Path(s).resolve(),sys.argv[1:3])
    game = Path(json.loads((results/'static/static-summary.json').read_text())['gameRoot'])
    tools = Path(__file__).resolve().parent
    scenarios=[('english-baseline','en_US.UTF-8',False,'none'), ('english-nvda','en_US.UTF-8',True,'none'),
               ('english-nvda-network','en_US.UTF-8',True,'bridge'), ('chinese-nvda-network','zh_CN.GB18030',True,'bridge')]
    for name, locale, nvda, network in scenarios:
        case = data/('case-'+name);case.mkdir();case.chmod(0o777)
        container='zetianji-probe-'+name
        arguments=['docker','run','--rm','--name',container,'--network='+network,'--cap-drop=ALL','--security-opt=no-new-privileges',
                   '--read-only','--tmpfs','/tmp:rw,size=1073741824,uid=1000,gid=1000',
                   '--pids-limit=512','--memory=4g','--cpus=2',
                   '--mount',f'type=bind,src={game},dst=/input/game,readonly',
                   '--mount',f'type=bind,src={data/"nvda"},dst=/input/nvda,readonly',
                   '--mount',f'type=bind,src={tools},dst=/tools,readonly',
                   '--mount',f'type=bind,src={case},dst=/work',
                   '-e','LANG='+locale,'-e','LC_ALL='+locale,'-e','PROBE_NETWORK='+network,'zetianji-wine-probe',name,'nvda' if nvda else 'plain']
        print('Starting isolated scenario: '+name,flush=True)
        try:
            run=subprocess.run(arguments,timeout=240)
            print('Scenario container return code: '+str(run.returncode),flush=True)
            if run.returncode:
                raise RuntimeError('Probe environment failed before completing scenario '+name)
        finally:
            subprocess.run(['docker','rm','-f',container],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            if (case/'results').exists():shutil.copytree(case/'results',results/name,dirs_exist_ok=True)
            subprocess.run(['sudo','rm','-rf','--',str(case)],check=True)


if __name__=='__main__':main()
