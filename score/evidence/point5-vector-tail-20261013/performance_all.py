"""同输入ABBA顺序对照，使用真实NPU的msprof核时间。"""
from pathlib import Path
import subprocess, json, os, sys
root=Path(__file__).resolve().parent
out=root/'performance-all'
out.mkdir(exist_ok=False)
groups=[('fp16','NN','1,5,13'),('bf16','TN','2,12'),('fp16','NT','3,9'),('bf16','TT','4,8'),('bf16','NT','6,14'),('fp16','TN','7'),('fp16','TT','11,15'),('bf16','NN','10')]
env=dict(os.environ,OPENBLAS_NUM_THREADS='2',OMP_NUM_THREADS='2')
records=[]
for gi,(dtype,layout,cases) in enumerate(groups):
    order=['baseline','candidate','candidate','baseline'] if gi%2==0 else ['candidate','baseline','baseline','candidate']
    for seq,version in enumerate(order):
        dest=out/f'{gi}-{seq}-{version}'
        dest.mkdir()
        lib=Path('/home/developer/cann-point8-tail-load-20261013/libcandidate.so') if version=='baseline' else root/'libcandidate.so'
        app=dest/'application.json'
        command=['python3',str(root/'tests/benchmark.py'),str(lib),'--commit',version,'--report',str(app),'--cases',cases,'--dtype',dtype,'--layout',layout,'--warmup','20','--repeat','50','--real-npu']
        profile=dest/'profile'
        with (dest/'run.log').open('w') as log:
            status=subprocess.run(['msprof','--task-time=l0',f'--output={profile}','--application='+' '.join(command)],stdout=log,stderr=subprocess.STDOUT,env=env,timeout=240).returncode
        if status: sys.exit(status)
        status=subprocess.run(['python3',str(root/'tests/summarize_profile.py'),str(app),str(profile),'--output',str(dest/'summary.json')],env=env).returncode
        if status: sys.exit(status)
        records.append({'group':gi,'seq':seq,'version':version,'directory':str(dest)})
        (out/'runs.json').write_text(json.dumps(records,indent=2))
        print(dtype,layout,seq,version,'完成',flush=True)
