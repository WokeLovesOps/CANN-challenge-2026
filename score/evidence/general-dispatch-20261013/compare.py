"""汇总交错对照，验证各轮输入一致后合并正式样本。"""
from pathlib import Path
import json,statistics,hashlib
root=Path(__file__).resolve().parent
runs=json.loads((root/'performance/runs.json').read_text())
points={}
for run in runs:
    dest=Path(run['directory'])
    summary=json.loads((dest/'summary.json').read_text())
    app=json.loads((dest/'application.json').read_text())
    for item in app['results']:
        key=str(item['case']); p=points.setdefault(key,{'case':item['case'],'shape':item['shape'],'dtype':app['dtype'],'layout':app['layout'],'inputs':item['input_sha256'],'baseline':[],'candidate':[],'runs':[]})
        assert p['inputs']==item['input_sha256']
        p[run['version']].extend(summary['results'][key]['samples_us'])
        p['runs'].append({'version':run['version'],'median_us':summary['results'][key]['median_us']})
result=[]
for key,p in sorted(points.items(),key=lambda x:int(x[0])):
    a=statistics.median(p['baseline']);b=statistics.median(p['candidate'])
    result.append({k:v for k,v in p.items() if k not in ('baseline','candidate')}|{'baseline_us':a,'candidate_us':b,'change_percent':(b/a-1)*100,'sample_counts':[len(p['baseline']),len(p['candidate'])]})
assert len(result)==15 and all(x['sample_counts']==[100,100] for x in result)
(root/'performance/comparison.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
for p in result: print(p['case'],p['baseline_us'],p['candidate_us'],round(p['change_percent'],2),flush=True)
