"""Actual viewport verification; missing rendering infrastructure is not a score."""
from pathlib import Path
import json,os,shutil,subprocess,sys

class RenderingUnavailable(RuntimeError):
    pass

def verify_render(project,report,godot,script):
    out=Path(report)/'render';out.mkdir(parents=True,exist_ok=True)
    command=[godot,'--rendering-method','gl_compatibility','--audio-driver','Dummy','--fixed-fps','60','--path',str(project),'--script',str(script),'--',str(out),'--verification']
    env=dict(os.environ);options={}
    if sys.platform=='win32':
        startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
        options['startupinfo']=startup
    elif sys.platform.startswith('linux') and not env.get('DISPLAY'):
        xvfb=shutil.which('xvfb-run')
        if not xvfb:raise RenderingUnavailable('Actual viewport checks require xvfb-run and Mesa, or a working DISPLAY')
        command=[xvfb,'-a','-s','-screen 0 640x360x24']+command
        env['LIBGL_ALWAYS_SOFTWARE']='1'
    try:
        r=subprocess.run(command,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=90,**options)
    except (OSError,subprocess.TimeoutExpired) as e:
        raise RenderingUnavailable(str(e)) from e
    (out/'execution.json').write_text(json.dumps({'command':command,'exit_code':r.returncode,'stdout':r.stdout,'stderr':r.stderr,'platform':sys.platform},indent=2)+'\n',encoding='utf-8')
    result=out/'render-checks.json'
    if r.returncode not in (0,1) or not result.exists():raise RenderingUnavailable('Actual rendering did not complete; inspect render/execution.json')
    data=json.loads(result.read_text(encoding='utf-8'))
    return bool(data['passed']),data
