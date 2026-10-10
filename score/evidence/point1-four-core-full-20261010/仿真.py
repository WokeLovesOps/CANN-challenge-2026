from pathlib import Path
import subprocess,json,re,hashlib,csv,os,sys
r=Path(__file__).resolve().parent;d=Path('score/evidence/point1-four-core-full-20261010')
for v in sys.argv[1:]:
 for case,capture in ([(0,False)] if v=='baseline' else [(0,False),(8,False),(16,False),(24,False)]):
  label=f'{v}-case{case}'+('-capture' if capture else '')
  out=r/'sim'/label;out.mkdir(parents=True,mode=0o700,exist_ok=True)
  report=out/'正确性.json';log=out/'run.log'
  cmd=['msprof','op','simulator','--soc-version=Ascend910B3',f'--launch-count={3 if capture else 2}','--timeout=2',f'--output={out}/profile','python3',str(r/'正确性入口.py'),str(r/f'lib{v}.so'),f'--case={case}',f'--report={report}']+(['--capture'] if capture else [])
  if report.exists():
   p=subprocess.CompletedProcess(cmd,0)
  else:
   with log.open('w') as f:p=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
  record=json.loads(report.read_text()) if report.exists() else {'passed':False}
  bins=list(out.glob('profile/**/visualize_data.bin'));files=list(out.glob('profile/**/*instr_exe*.csv'))
  count=3 if capture else 2
  valid=p.returncode==0 and record['passed'] and len(bins)==count and len(files)==count*(1 if v=='baseline' else 4)
  instructions=[]
  for f in files:
   rows=list(csv.DictReader(f.open())); active=f.parent.name=='core0.veccore0'
   copyin=sum(int(x['call_count']) for x in rows if x['pipe']=='MTE2' and x['instr'].startswith('MOV_'));copyout=sum(int(x['call_count']) for x in rows if x['pipe']=='MTE3' and x['instr'].startswith('MOV_'))
   valid=valid and (copyin==2 and copyout==1 if active else copyin==0 and copyout==0)
   instructions.append(dict(path=str(f),copyin=copyin,copyout=copyout,instructions=rows))
  record.update(variant=v,capture=capture,passed=valid,command=cmd,exit_code=p.returncode,source_sha256=hashlib.sha256((r/f'{v}.asc').read_bytes()).hexdigest(),library_sha256=hashlib.sha256((r/f'lib{v}.so').read_bytes()).hexdigest(),bins=[dict(path=str(f),sha256=hashlib.sha256(f.read_bytes()).hexdigest(),size=f.stat().st_size) for f in bins],instructions=instructions,timings=re.findall(r'(core\d+\.veccore\d+)\s+(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)',log.read_text()))
  (d/(label+'.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
  print(label,valid,record['timings'],flush=True)
  if not valid:raise SystemExit('正确性或指令采集核验失败')
