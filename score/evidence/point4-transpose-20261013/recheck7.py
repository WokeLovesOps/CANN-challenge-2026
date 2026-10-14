"""点4两版本同输入交错比较。"""
from pathlib import Path
import subprocess,os,json
root=Path(__file__).resolve().parent
out=root/'performance-point7-recheck';out.mkdir(exist_ok=False)
env=dict(os.environ,OPENBLAS_NUM_THREADS='2',OMP_NUM_THREADS='2')
for i,version in enumerate(['candidate','baseline','baseline','candidate','baseline','candidate','candidate','baseline']):
    dest=out/f'{i}-{version}';dest.mkdir()
    lib=root/'libcandidate.so' if version=='candidate' else Path('/home/developer/cann-point4-direct-v2-20261013/libcandidate.so')
    app=dest/'application.json'
    command=['python3',str(root/'tests/benchmark.py'),str(lib),'--commit',version,'--report',str(app),'--cases','7','--dtype','fp16','--layout','TN','--warmup','20','--repeat','50','--real-npu']
    with (dest/'run.log').open('w') as f:
        p=subprocess.run(['msprof','--task-time=l0','--output='+str(dest/'profile'),'--application='+' '.join(command)],stdout=f,stderr=subprocess.STDOUT,env=env,timeout=240)
    if p.returncode: raise SystemExit(p.returncode)
    subprocess.run(['python3',str(root/'tests/summarize_profile.py'),str(app),str(dest/'profile'),'--output',str(dest/'summary.json')],env=env,check=True)
    print(version,'完成',flush=True)
