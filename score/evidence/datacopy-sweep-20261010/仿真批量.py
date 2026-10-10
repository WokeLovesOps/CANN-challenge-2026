from pathlib import Path
import subprocess,json,hashlib,csv,re,os,sys
r=Path(__file__).resolve().parent;d=Path('/mnt/newdisk/code/CANN-challenge/score/evidence/datacopy-sweep-20261010');m=json.loads((d/'实验配置.json').read_text())
for i in map(int,sys.argv[1:]):
 previous=d/f'batch{i}-models.json'
 records=[x for x in json.loads(previous.read_text()) if x['passed']] if previous.exists() else []
 points=[1,2,15] if i in [0,8] else list(range(2,16))
 for point in points:
  if any(x['point']==point for x in records):continue
  cfg=m['batches'][i]['configs'][point-1]
  target=r/'sim'/f'batch{i}-point{point}-validated';target.mkdir(parents=True,mode=0o700,exist_ok=True)
  report=target/'执行检查.json';cmd=['msprof','op','simulator','--soc-version=Ascend910B3','--launch-count=2','--timeout=2',f'--output={target}/profile','python3',str(r/'仿真入口.py'),str(r/f'libbatch{i}.so'),f'--point={point}',f'--report={report}']
  with (target/'run.log').open('w') as f:p=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
  x=json.loads(report.read_text()) if report.exists() else {'passed':False}
  log=(target/'run.log').read_text();bins=list(target.glob('profile/*/*/*/simulator/visualize_data.bin'));csvs=list(target.glob('profile/*/*/*/simulator/core0.veccore0/*instr_exe*.csv'))
  counts=[]
  for f in csvs:
   rows=list(csv.DictReader(f.open()));copies=[v for v in rows if v['pipe']=='MTE2' and 'Src:OUT,Dst:UB' in v['detail']];counts.append(sum(int(v['call_count']) for v in copies))
   assert not any(v['pipe']=='MTE3' and v['instr'].startswith('MOV_') for v in rows),'探针不应搬出'
  expected=0 if cfg is None else 1
  x.update(batch=i,configuration=cfg,exit_code=p.returncode,copy_counts=counts,source_sha256=hashlib.sha256((r/f'batch{i}.asc').read_bytes()).hexdigest(),library_sha256=hashlib.sha256((r/f'libbatch{i}.so').read_bytes()).hexdigest(),bins=[dict(path=str(b),size=b.stat().st_size,sha256=hashlib.sha256(b.read_bytes()).hexdigest()) for b in bins],timings=[dict(core=c,duration_us=float(v),running_us=float(t)) for c,v,t in re.findall(r'(core\d+\.veccore\d+)\s+(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)',log)])
  x['passed']=x['passed'] and p.returncode==0 and len(bins)==2 and len(csvs)==2 and counts==[expected,expected] and len(x['timings'])==2
  records.append(x);(d/f'batch{i}-models.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n');print(i,point,x['passed'],x['timings'],counts,flush=True)
  if not x['passed']:raise SystemExit('采集/执行检查失败，停止批量')
