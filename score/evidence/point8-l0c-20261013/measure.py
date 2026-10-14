"""三版本同输入交错比较：基线、64列单缓冲对照、64列双缓冲候选。"""
from pathlib import Path
import subprocess,os,json
root=Path(__file__).resolve().parent
out=root/'performance';out.mkdir(exist_ok=False)
env=dict(os.environ,OPENBLAS_NUM_THREADS='2',OMP_NUM_THREADS='2')
for i,version in enumerate(['baseline','control','candidate','candidate','control','baseline']):
    dest=out/f'{i}-{version}';dest.mkdir()
    lib=root/'libcandidate.so' if version=='candidate' else root/version/'libcandidate.so'
    app=dest/'application.json'
    command=['python3',str(root/'tests/benchmark.py'),str(lib),'--commit',version,'--report',str(app),'--cases','8','--dtype','bf16','--layout','TT','--warmup','20','--repeat','50','--real-npu']
    with (dest/'run.log').open('w') as f:
        p=subprocess.run(['msprof','--task-time=l0','--output='+str(dest/'profile'),'--application='+' '.join(command)],stdout=f,stderr=subprocess.STDOUT,env=env,timeout=240)
    if p.returncode: raise SystemExit(p.returncode)
    subprocess.run(['python3',str(root/'tests/summarize_profile.py'),str(app),str(dest/'profile'),'--output',str(dest/'summary.json')],env=env,check=True)
    print(version,'完成',flush=True)
