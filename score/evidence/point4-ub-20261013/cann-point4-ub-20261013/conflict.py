"""采集当前完整库的点4真机计时、PMU及软件模型，分别记录。"""
from pathlib import Path
import subprocess,os,json,time,hashlib
root=Path('/home/developer/cann-point4-ub-20261013');root.mkdir(exist_ok=True,mode=0o700)
root.chmod(0o700)
suite=Path('/home/developer/cann-point8-l0c-20261013')
assert hashlib.sha256((suite/'src/kernel.asc').read_bytes()).hexdigest()=='cdd0133ec408efbcfd9f91d6939e93a0e5ddad68ccf1f4d6a89edac3e82c25c4'
env=dict(os.environ,OPENBLAS_NUM_THREADS='2',OMP_NUM_THREADS='2')
for version in ['baseline','candidate']:
    mode='pmu'
    suite=Path('/home/developer/cann-point8-l0c-20261013') if version=='baseline' else root
    dest=root/(mode+'-'+version);dest.mkdir(exist_ok=True);dest.chmod(0o700)
    if (dest/'run.log').exists(): (dest/'run.log').rename(dest/'permissions-failed.log')
    app=dest/'application.json'
    application=['python3',str(suite/'tests/benchmark.py'),str(suite/'libcandidate.so'),'--commit','current-point4','--report',str(app),'--cases','4','--dtype','bf16','--layout','TT','--warmup','0' if mode=='model' else '20','--repeat','50' if mode.startswith('l0') else '2']
    if mode!='model': application+=['--real-npu']
    if mode.startswith('l0'):
        command=['msprof','--task-time=l0','--output='+str(dest/'profile'),'--application='+' '.join(application)]
    elif mode=='pmu':
        command=['msprof','op','--aic-metrics=PipeUtilization,ResourceConflictRatio,MemoryUB','--launch-count=1','--launch-skip-before-match=20','--output='+str(dest/'profile')]+application
    else:
        command=['msprof','op','simulator','--soc-version=Ascend910B3','--core-id=0','--launch-count=2','--timeout=2','--output='+str(dest/'profile')]+application
    start=time.monotonic()
    with (dest/'run.log').open('w') as log:
        try: status=subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=150).returncode
        except subprocess.TimeoutExpired: status=124
    (dest/'command.json').write_text(json.dumps({'command':command,'exit_code':status,'seconds':time.monotonic()-start},indent=2))
    print(mode,status,flush=True)
    if status==0 and mode.startswith('l0'):
        subprocess.run(['python3',str(suite/'tests/summarize_profile.py'),str(app),str(dest/'profile'),'--output',str(dest/'summary.json')],env=env,check=True)
