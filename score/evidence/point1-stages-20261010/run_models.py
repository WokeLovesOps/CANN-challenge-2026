from pathlib import Path
import os,subprocess,json,re,hashlib,sys,csv,collections
p=Path(__file__).resolve().parent
records=[]
for n in sys.argv[1:]:
 out=p/'sim'/n;out.mkdir(parents=True,mode=0o700,exist_ok=True)
 app=p/'diagnose.py' if n!='stage3' else Path('/mnt/newdisk/code/CANN-challenge/Build/point1-20261010/screen_point1.py')
 cmd=['msprof','op','simulator','--soc-version=Ascend910B3','--launch-count=2','--timeout=2',f'--output={out}/profile','python3',str(app),str(p/f'lib{n}.so'),'--case=0',f'--report={out}/execution.json']
 print('开始',n,flush=True)
 with (out/'run.log').open('w') as log:r=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,env=dict(os.environ,OPENBLAS_NUM_THREADS='2',OMP_NUM_THREADS='2'))
 d=json.loads((out/'execution.json').read_text()) if (out/'execution.json').exists() else {'passed':False}
 d.update(variant=n,command=cmd,exit_code=r.returncode,source_sha256=hashlib.sha256((p/f'{n}.asc').read_bytes()).hexdigest(),library_sha256=hashlib.sha256((p/f'lib{n}.so').read_bytes()).hexdigest(),bins=[dict(path=str(b),size=b.stat().st_size,sha256=hashlib.sha256(b.read_bytes()).hexdigest()) for b in out.glob('profile/**/visualize_data.bin')])
 d['timings']=[dict(core=c,duration_us=float(t),running_us=float(v)) for c,t,v in re.findall(r'(core\d+\.veccore\d+)\s+(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)',(out/'run.log').read_text())]
 f=next(out.glob('profile/**/1/simulator/core0.veccore0/*instr_exe*.csv'),None);cnt=collections.Counter()
 if f:
  for row in csv.DictReader(f.open()):cnt[row['instr']]+=int(row['call_count'])
 d['instructions']=dict(cnt);d['execution_passed']=r.returncode==0 and d['passed'] and len(d['bins'])==2
 (p/f'{n}-model.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
 print(n,d['execution_passed'],d['timings'],dict(cnt),flush=True)
 if not d['execution_passed']:sys.exit(1)
