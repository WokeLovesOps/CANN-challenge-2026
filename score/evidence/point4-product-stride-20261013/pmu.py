"""顺序采集两版硬件冲突，仅用于解释，不能替代普通设备计时。"""
from pathlib import Path
import subprocess,os,json,time
root=Path(__file__).resolve().parent
env=dict(os.environ,OPENBLAS_NUM_THREADS='2',OMP_NUM_THREADS='2')
for version in ['baseline','candidate']:
    dest=root/('pmu-'+version);dest.mkdir(mode=0o700,exist_ok=False)
    lib=root/'libcandidate.so' if version=='candidate' else Path('/home/developer/cann-point4-transpose-20261013/libcandidate.so')
    app=dest/'application.json'
    application=['python3',str(root/'tests/benchmark.py'),str(lib),'--commit',version,'--report',str(app),'--cases','4','--dtype','bf16','--layout','TT','--warmup','20','--repeat','2','--real-npu']
    command=['msprof','op','--aic-metrics=PipeUtilization,ResourceConflictRatio,MemoryUB','--launch-count=1','--launch-skip-before-match=20','--output='+str(dest/'profile')]+application
    start=time.monotonic()
    with (dest/'run.log').open('w') as log:
        status=subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=180).returncode
    (dest/'command.json').write_text(json.dumps({'command':command,'exit_code':status,'seconds':time.monotonic()-start},indent=2))
    print(version,status,flush=True)
    if status: raise SystemExit(status)
