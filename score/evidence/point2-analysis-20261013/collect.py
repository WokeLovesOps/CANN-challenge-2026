"""汇总完整计算对照并导出原始证据，保留失败实验。"""
from pathlib import Path
import json,statistics,hashlib,tarfile,csv
root=Path(__file__).resolve().parent
comparison={}
for folder in ('timing2','timing3'):
 groups={}; hashes=set()
 for dest in sorted((root/folder).iterdir()):
  s=json.loads((dest/'summary.json').read_text());app=json.loads((dest/'application.json').read_text());assert app['passed'];name=s['commit'];r=s['results']['2'];hashes.add(tuple(app['results'][0]['input_sha256']))
  g=groups.setdefault(name,{'samples_us':[],'round_medians_us':[],'library_sha256':s['library_sha256']});g['samples_us']+=r['samples_us'];g['round_medians_us'].append(r['median_us'])
 assert len(hashes)==1
 for name,g in groups.items():
  g['median_us']=statistics.median(g['samples_us']);g['count']=len(g['samples_us']);g['mean_us']=statistics.mean(g['samples_us']);g['min_us']=min(g['samples_us']);g['max_us']=max(g['samples_us']);g['samples_gt_2us']=sum(x>2 for x in g['samples_us'])
 comparison[folder]={'input_sha256':list(next(iter(hashes))),'variants':groups}
print(json.dumps({f:{n:{k:v for k,v in g.items() if k!='samples_us'} for n,g in x['variants'].items()} for f,x in comparison.items()},ensure_ascii=False))
(root/'comparison.json').write_text(json.dumps(comparison,ensure_ascii=False,indent=2)+'\n')
metrics=[]
for folder in ('pmu','pmu-no-pipe'):
 for p in (root/folder).rglob('PipeUtilization*.csv'):
  row=list(csv.DictReader(p.open()))[0];metrics.append({'variant':folder,'csv':str(p),'csv_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'values':{k:v for k,v in row.items() if k and not k.startswith('aic_')}})
(root/'metrics.json').write_text(json.dumps(metrics,indent=2)+'\n')
with tarfile.open(root/'evidence.tar.gz','w:gz') as tar:
 for p in root.rglob('*'):
  if p.is_file() and (p.parent==root and p.suffix in ('.py','.asc','.json','.log') or p.name in ('application.json','summary.json','run.log') or p.parent.name=='no-pipe-check' or p.suffix=='.csv' and any(tag in p.name for tag in ('op_summary','PipeUtilization','ResourceConflictRatio','Memory','OpBasicInfo'))):tar.add(p,arcname=str(p.relative_to(root)))
