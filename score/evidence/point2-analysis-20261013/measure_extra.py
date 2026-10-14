"""完整数值计算的隔离对照，正序/逆序各一轮，固定20次预热和50次采样。"""
from pathlib import Path
import subprocess,json,os
root=Path(__file__).resolve().parent
suite=Path('/home/developer/cann-general-dispatch-20261013')
env=dict(os.environ,OPENBLAS_NUM_THREADS='2',OMP_NUM_THREADS='2')
records=[]
for seq,name in enumerate(['base','index_early','no_pipe','no_pipe','index_early','base']):
    out=root/'timing3'/f'{seq}-{name}';out.mkdir(parents=True,exist_ok=False)
    lib=suite/'libcandidate.so' if name=='production' else root/f'lib{name}.so'
    app=out/'application.json'
    command=['python3',str(suite/'tests/benchmark.py'),str(lib),'--commit',name,'--cases','2','--dtype','bf16','--layout','TN','--warmup','20','--repeat','50','--real-npu','--report',str(app)]
    with (out/'run.log').open('w') as log:
        status=subprocess.run(['msprof','--task-time=l0',f'--output={out}/profile','--application='+' '.join(command)],env=env,stdout=log,stderr=subprocess.STDOUT,timeout=240).returncode
    if status:raise SystemExit(status)
    subprocess.run(['python3',str(suite/'tests/summarize_profile.py'),str(app),str(out/'profile'),'--output',str(out/'summary.json')],env=env,check=True)
    records.append({'seq':seq,'variant':name,'directory':str(out)})
    (root/'runs3.json').write_text(json.dumps(records,indent=2)+'\n')
    print(name,'完成',flush=True)
