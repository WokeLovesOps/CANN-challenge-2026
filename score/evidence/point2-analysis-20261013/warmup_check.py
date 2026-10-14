"""补充预热敏感性检查，不替代正式20+50对照。"""
from pathlib import Path
import subprocess,json,os
root=Path(__file__).resolve().parent
suite=Path('/home/developer/cann-general-dispatch-20261013')
env=dict(os.environ,OPENBLAS_NUM_THREADS='2',OMP_NUM_THREADS='2')
records=[]
for seq,name in enumerate(['production','no_pipe']):
    out=root/'warmup200'/f'{seq}-{name}';out.mkdir(parents=True,exist_ok=False)
    lib=suite/'libcandidate.so' if name=='production' else root/f'lib{name}.so'
    app=out/'application.json'
    command=['python3',str(suite/'tests/benchmark.py'),str(lib),'--commit',name,'--cases','2','--dtype','bf16','--layout','TN','--warmup','200','--repeat','50','--real-npu','--report',str(app)]
    with (out/'run.log').open('w') as log:
        status=subprocess.run(['msprof','--task-time=l0',f'--output={out}/profile','--application='+' '.join(command)],env=env,stdout=log,stderr=subprocess.STDOUT,timeout=240).returncode
    if status:raise SystemExit(status)
    subprocess.run(['python3',str(suite/'tests/summarize_profile.py'),str(app),str(out/'profile'),'--output',str(out/'summary.json')],env=env,check=True)
    records.append({'seq':seq,'variant':name,'directory':str(out)})
    (root/'warmup200-runs.json').write_text(json.dumps(records,indent=2)+'\n')
    print(name,'完成',flush=True)
