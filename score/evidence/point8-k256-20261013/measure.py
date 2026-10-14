from pathlib import Path
import json,subprocess,os
root=Path('/home/developer/cann-point8-k256-20261013')
base=Path('/home/developer/cann-point2-implement-20261013/libcandidate.so')
out=root/'performance';out.mkdir(exist_ok=True)
env=dict(os.environ,OPENBLAS_NUM_THREADS='2',OMP_NUM_THREADS='2')
for i,version in enumerate(['baseline','candidate','candidate','baseline']):
    dest=out/f'{i}-{version}';dest.mkdir()
    lib=base if version=='baseline' else root/'libcandidate.so'
    app=dest/'application.json'
    command=['python3',str(root/'tests/benchmark.py'),str(lib),'--commit',version,'--report',str(app),'--cases','8','--dtype','bf16','--layout','TT','--warmup','20','--repeat','50','--real-npu']
    with (dest/'run.log').open('w') as f:
        p=subprocess.run(['msprof','--task-time=l0','--output='+str(dest/'profile'),'--application='+' '.join(command)],stdout=f,stderr=subprocess.STDOUT,env=env,timeout=240)
    if p.returncode: raise RuntimeError(p.returncode)
    subprocess.run(['python3',str(root/'tests/summarize_profile.py'),str(app),str(dest/'profile'),'--output',str(dest/'summary.json')],env=env,check=True)
