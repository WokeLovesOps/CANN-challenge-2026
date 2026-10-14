"""串行真实NPU回归；每组独立进程，失败即停，保存原始记录。"""
from pathlib import Path
import argparse, json, subprocess, sys, os
p=argparse.ArgumentParser()
p.add_argument('--suite',default='tiling_domains')
p.add_argument('--cases',required=True)
p.add_argument('--capture',action='store_true')
p.add_argument('--output',required=True)
a=p.parse_args()
root=Path(__file__).resolve().parent
out=root/a.output
out.mkdir(exist_ok=False)
records=[]
env=dict(os.environ,OPENBLAS_NUM_THREADS='2',OMP_NUM_THREADS='2',PYTHONDONTWRITEBYTECODE='1')
for case in map(int,a.cases.split(',')):
    report=out/f'{case}.json'
    cmd=[sys.executable,str(root/f'tests/{a.suite}.py'),str(root/'libcandidate.so'),
         '--case',str(case),'--report',str(report),'--real-npu']
    if a.capture: cmd.append('--capture')
    with (out/f'{case}.log').open('w') as log:
        try: status=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,env=env,timeout=120).returncode
        except subprocess.TimeoutExpired: status=124
    record=json.loads(report.read_text()) if report.exists() else {'case':case,'passed':False}
    record.update(exit_code=status,command=cmd)
    record['passed']=record['passed'] and status==0
    records.append(record)
    (out/'summary.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
    print(case,record['passed'],record.get('error',''),flush=True)
    if not record['passed']: sys.exit(1)
