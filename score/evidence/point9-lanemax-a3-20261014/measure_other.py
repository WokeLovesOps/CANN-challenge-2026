"""交错检查其他代表点性能，保留应用哈希和原始Profiler证据。"""
from pathlib import Path
import subprocess,os,json,statistics
root=Path(__file__).resolve().parent
out=root/'other-performance';out.mkdir(exist_ok=False)
env=dict(os.environ,OPENBLAS_NUM_THREADS='2',OMP_NUM_THREADS='2')
groups=[('fp16','NN','1,5,13'),('bf16','TN','2,12'),('fp16','NT','3'),('bf16','TT','4,8'),('bf16','NT','6,14'),('fp16','TN','7'),('fp16','TT','11,15'),('bf16','NN','10')]
result={}
for dtype,layout,cases in groups:
 for i,version in enumerate(['baseline','candidate','candidate','baseline']):
  dest=out/f'{dtype}-{layout}-{i}-{version}';dest.mkdir()
  lib=root/'libcandidate.so' if version=='candidate' else Path('/home/developer/cann-point7-analysis-20261014/libcandidate.so')
  app=dest/'application.json'
  command=['python3',str(root/'tests/benchmark.py'),str(lib),'--commit',version,'--report',str(app),'--cases',cases,'--dtype',dtype,'--layout',layout,'--warmup','20','--repeat','50','--real-npu']
  with (dest/'run.log').open('w') as f:
   p=subprocess.run(['msprof','--task-time=l0','--output='+str(dest/'profile'),'--application='+' '.join(command)],stdout=f,stderr=subprocess.STDOUT,env=env,timeout=240)
  if p.returncode:raise SystemExit(p.returncode)
  subprocess.run(['python3',str(root/'tests/summarize_profile.py'),str(app),str(dest/'profile'),'--output',str(dest/'summary.json')],env=env,check=True,stdout=subprocess.DEVNULL)
  a=json.loads(app.read_text());assert a['passed']
  summary=json.loads((dest/'summary.json').read_text())
  for item in a['results']:
   key=str(item['case']);rec=result.setdefault(key,{'hash':item['input_sha256'],'baseline':[],'candidate':[]})
   assert rec['hash']==item['input_sha256']
   rec[version]+=summary['results'][key]['samples_us']
 for key in cases.split(','):
  rec=result[key];b=statistics.median(rec['baseline']);c=statistics.median(rec['candidate'])
  rec['baseline_median_us']=b;rec['candidate_median_us']=c;rec['change_percent']=(c/b-1)*100
  print(key,b,c,rec['change_percent'],flush=True)
 (root/'other-comparison.json').write_text(json.dumps(result,indent=2))
