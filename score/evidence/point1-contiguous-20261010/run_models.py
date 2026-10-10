from pathlib import Path
import os,subprocess,json,re,hashlib,sys
folder=Path(__file__).resolve().parent
records=[]
for allocation in sys.argv[1:]:
 name="contiguous"
 records=[]
 for case in [0,8,16,24,32,40]:
  label=f'{allocation}-case{case}'; out=folder/'sim'/label;out.mkdir(parents=True,mode=0o700,exist_ok=True)
  report=out/'correctness.json'; log=out/'run.log'
  cmd=['msprof','op','simulator','--soc-version=Ascend910B3','--launch-count=2','--timeout=2',f'--output={out}/profile','python3',str(folder/'screen.py'),str(folder/f'lib{name}.so'),f'--case={case}',f'--report={report}',f'--allocation={allocation}']
  print('开始',label,flush=True)
  with log.open('w') as f:p=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,env=dict(os.environ,OPENBLAS_NUM_THREADS='2',OMP_NUM_THREADS='2',PYTHONDONTWRITEBYTECODE='1'))
  content=log.read_text(); r=json.loads(report.read_text()) if report.exists() else {'passed':False}
  r.update(variant=name,command=cmd,exit_code=p.returncode,source_sha256=hashlib.sha256((folder/f'{name}.asc').read_bytes()).hexdigest(),library_sha256=hashlib.sha256((folder/f'lib{name}.so').read_bytes()).hexdigest(),timings=[dict(core=c,duration_us=float(d),running_us=float(t)) for c,d,t in re.findall(r'(core\d+\.(?:veccore|cubecore)\d+)\s+(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)',content)],bins=[dict(path=str(b),size=b.stat().st_size,sha256=hashlib.sha256(b.read_bytes()).hexdigest()) for b in out.glob('profile/OPPROF_*/**/visualize_data.bin')])
  r['passed']=r['passed'] and p.returncode==0 and bool(r['bins']) and 'SIM_CORRECTNESS_PASS' in content
  records.append(r); (folder/f'{allocation}-models.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
  print(label,r['passed'],r['timings'],flush=True)
  if not r['passed']:sys.exit(1)
