"""汇总点1真机采样、逐核PMU及热调用模型指令；不混用计时。"""
from pathlib import Path
import csv,json,statistics,collections,hashlib,tarfile
root=Path(__file__).resolve().parent
out={'l0':{},'pmu':{},'model':{}};samples=[];hashes=[]
for folder in ['l0-0','l0-1','l0-2','pmu-0','pmu-1','model']:
    d=root/folder
    a=json.loads((d/'application.json').read_text());assert a['passed']
    hashes.append(a['results'][0]['input_sha256'])
    if folder.startswith('l0'):
        s=json.loads((d/'summary.json').read_text())['results']['1']['samples_us'];assert len(s)==50
        out['l0'][folder]={'median_us':statistics.median(s),'min_us':min(s),'max_us':max(s)};samples+=s
    elif folder.startswith('pmu'):
        result={}
        for metric in ['PipeUtilization','Memory','MemoryUB','ArithmeticUtilization','OpBasicInfo']:
            files=list(d.rglob(metric+'.csv'));assert len(files)==1
            rows=list(csv.DictReader(files[0].open()))
            if metric=='OpBasicInfo':result[metric]=rows;continue
            result[metric]={}
            for sub in sorted(set(r['sub_block_id'] for r in rows)):
                group=[r for r in rows if r['sub_block_id']==sub]
                v={}
                for key in group[0]:
                    if not key or key in ('block_id','sub_block_id'):continue
                    values=[float(r[key]) for r in group if r.get(key) not in ('NA','',None)]
                    if values:v[key]={'median':statistics.median(values),'min':min(values),'max':max(values)}
                result[metric][sub]={'blocks':len(group),'metrics':v}
        out['pmu'][folder]=result
assert all(h==hashes[0] for h in hashes)
out['l0']['combined']={'median_us':statistics.median(samples),'samples':len(samples),'input_sha256':hashes[0]}
for p in (root/'model').rglob('*instr_exe*.csv'):
    if '/1/' not in p.as_posix():continue
    counts=collections.Counter()
    for r in csv.DictReader(p.open()):counts[r['instr']]+=int(r['call_count'])
    t=p.parent/'trace.json';events=[e for e in json.loads(t.read_text())['traceEvents'] if e.get('ph')=='X'];origin=min(e['ts'] for e in events)
    grouped={}
    for name in sorted(set(e['name'] for e in events)):
        es=[e for e in events if e['name']==name]
        grouped[name]={'count':len(es),'start_us':min(e['ts'] for e in es)-origin,'end_us':max(e['ts']+e['dur'] for e in es)-origin,'sum_duration_us':sum(e['dur'] for e in es)}
    out['model'][p.parent.name]={'counts':dict(counts),'span_us':max(e['ts']+e['dur'] for e in events)-origin,'stages':grouped}
(root/'summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
print('l0',json.dumps(out['l0']))
for name,result in out['pmu'].items():
    print(name,json.dumps(result['OpBasicInfo']))
    for sub,group in result['PipeUtilization'].items():
        print(sub,group['blocks'],json.dumps({k:v for k,v in group['metrics'].items() if k.endswith('time(us)')}))
for name,result in out['model'].items():print(name,json.dumps(result))
with tarfile.open(root/'evidence.tar.gz','w:gz') as archive:
    for p in sorted(root.iterdir()):
        if p.name=='evidence.tar.gz':continue
        archive.add(p,arcname=p.name)
print('archive_sha256',hashlib.sha256((root/'evidence.tar.gz').read_bytes()).hexdigest())
