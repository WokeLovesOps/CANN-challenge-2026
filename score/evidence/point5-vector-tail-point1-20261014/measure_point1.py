"""点1受点5候选影响的正反交错对照。"""
from pathlib import Path
import subprocess,os,json
root=Path(__file__).resolve().parent
out=root/'point1-recheck-20261014';out.mkdir(exist_ok=False)
env=dict(os.environ,OPENBLAS_NUM_THREADS='2',OMP_NUM_THREADS='2')
for i,version in enumerate(['baseline','candidate','candidate','baseline','candidate','baseline','baseline','candidate']):
    dest=out/f'{i}-{version}';dest.mkdir()
    lib=root/'libcandidate.so' if version=='candidate' else Path('/home/developer/cann-point8-tail-load-20261013/libcandidate.so')
    app=dest/'application.json'
    command=['python3',str(root/'tests/benchmark.py'),str(lib),'--commit',version,'--report',str(app),'--cases','1','--dtype','fp16','--layout','NN','--warmup','20','--repeat','50','--real-npu']
    with (dest/'run.log').open('w') as f:
        p=subprocess.run(['msprof','--task-time=l0','--output='+str(dest/'profile'),'--application='+' '.join(command)],stdout=f,stderr=subprocess.STDOUT,env=env,timeout=240)
    if p.returncode: raise SystemExit(p.returncode)
    subprocess.run(['python3',str(root/'tests/summarize_profile.py'),str(app),str(dest/'profile'),'--output',str(dest/'summary.json')],env=env,check=True)
    print(version,'完成',flush=True)

import statistics,hashlib,tarfile
records=[]
for dest in sorted(out.iterdir()):
    a=json.loads((dest/'application.json').read_text(encoding='utf-8'));assert a['passed']
    samples=json.loads((dest/'summary.json').read_text(encoding='utf-8'))['results']['1']['samples_us']
    assert len(samples)==50
    records.append(dict(version=a['commit'],input_sha256=a['results'][0]['input_sha256'],samples_us=samples,median_us=statistics.median(samples)))
assert all(r['input_sha256']==records[0]['input_sha256'] for r in records)
summary={'runs':records,'rounds':[]}
for start in [0,4]:
    row={v:statistics.median([x for r in records[start:start+4] if r['version']==v for x in r['samples_us']]) for v in ['baseline','candidate']}
    row['change_percent']=(row['candidate']/row['baseline']-1)*100
    summary['rounds'].append(row)
summary['libraries']={v:hashlib.sha256(p.read_bytes()).hexdigest() for v,p in {'baseline':Path('/home/developer/cann-point8-tail-load-20261013/libcandidate.so'),'candidate':root/'libcandidate.so'}.items()}
(out/'comparison.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print(json.dumps(summary['rounds']),flush=True)
with tarfile.open(root/'point1-recheck-20261014.tar.gz','w:gz') as t:
    t.add(out,arcname=out.name)
    t.add(Path(__file__),arcname=Path(__file__).name)
print(hashlib.sha256((root/'point1-recheck-20261014.tar.gz').read_bytes()).hexdigest(),flush=True)
