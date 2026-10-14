"""验证完整诊断核的邻域，失败立即停止并保存输出。"""
from pathlib import Path
import subprocess,json,os
root=Path(__file__).resolve().parent;out=root/'no-pipe-check';out.mkdir(exist_ok=False)
env=dict(os.environ,OPENBLAS_NUM_THREADS='2',OMP_NUM_THREADS='2');records=[]
for case in range(6,64,8):
 p=out/f'{case}.json'
 with (out/f'{case}.log').open('w') as log:status=subprocess.run(['python3',str(root/'domains.py'),str(root/'libno_pipe.so'),'--case',str(case),'--report',str(p),'--real-npu'],env=env,stdout=log,stderr=subprocess.STDOUT,timeout=120).returncode
 r=json.loads(p.read_text()) if p.exists() else {'case':case,'passed':False};r['exit_code']=status;records.append(r);(out/'summary.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n');print(case,r['passed'],flush=True)
 if status or not r['passed']:raise SystemExit(1)
