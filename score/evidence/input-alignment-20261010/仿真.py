from pathlib import Path
import subprocess,json,re,hashlib,os,sys
r=Path(__file__).resolve().parent;d=Path('score/evidence/input-alignment-20261010')
for name in sys.argv[1:]:
 for offset in [0,2,64,128]:
  label=f'{name}-offset{offset}';out=r/'sim'/label;out.mkdir(parents=True,mode=0o700,exist_ok=True)
  report=out/'检查.json';log=out/'run.log';batch=64 if offset==2 else 1
  cmd=['msprof','op','simulator','--soc-version=Ascend910B3','--launch-count=2','--timeout=2',f'--output={out}/profile','python3',str(r/'对齐验证入口.py'),str(r/f'lib{name}.so'),'--case=0',f'--report={report}',f'--tensor={name[0]}',f'--alignment={name[1:]}',f'--offset={offset}',f'--batch={batch}']
  with log.open('w') as f:process=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
  record=json.loads(report.read_text()) if report.exists() else {'passed':False}
  bins=list(out.glob('profile/**/visualize_data.bin'));files=list(out.glob('profile/**/*instr_exe*.csv'));aligned=offset%int(name[1:])==0
  expected='ComputeDot32' if aligned else 'WriteAlignmentDiagnosticNaN'
  valid=process.returncode==0 and record['passed'] and len(bins)==2 and len(files)==(8 if aligned else 2) and all(expected in str(f) for f in bins)
  record.update(passed=valid,variant=name,command=cmd,exit_code=process.returncode,source_sha256=hashlib.sha256((r/f'{name}.asc').read_bytes()).hexdigest(),library_sha256=hashlib.sha256((r/f'lib{name}.so').read_bytes()).hexdigest(),bins=[dict(path=str(f),sha256=hashlib.sha256(f.read_bytes()).hexdigest(),size=f.stat().st_size) for f in bins],csvs=[str(f) for f in files])
  (d/(label+'.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
  print(name,offset,batch,aligned,valid,flush=True)
  if not valid:raise SystemExit('探针正确性或采集验证失败')
