from pathlib import Path
import json,collections,hashlib,tarfile
root=Path('/home/developer/cann-point4-analysis-20261013')
results=[]
for p in sorted((root/'model').glob('**/core0.veccore0/trace.json')):
    events=[x for x in json.loads(p.read_text())['traceEvents'] if x.get('ph')=='X']
    origin=min(x['ts'] for x in events)
    groups=collections.defaultdict(list)
    for x in events:
        if x['name'].startswith('V') or x['name']=='MOV_SRC_TO_DST_ALIGN': groups[x['name']].append(x)
    record={'trace':str(p.relative_to(root)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'span_us':max(x['ts']+x['dur'] for x in events)-origin,'instructions':{}}
    for name,es in groups.items():
        record['instructions'][name]={'count':len(es),'first_us':min(x['ts'] for x in es)-origin,'last_us':max(x['ts']+x['dur'] for x in es)-origin,'duration_sum_us':sum(x['dur'] for x in es)}
    results.append(record)
    print(json.dumps(record),flush=True)
(root/'model-summary.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
with tarfile.open(root/'evidence.tar.gz','w:gz') as t:
    for p in root.rglob('*'):
        if p.is_file() and p.name!='evidence.tar.gz': t.add(p,arcname=str(p.relative_to(root)))
