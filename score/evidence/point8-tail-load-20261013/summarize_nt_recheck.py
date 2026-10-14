"""汇总15点交错性能并核对所有应用结果和输入哈希。"""
from pathlib import Path
import json,statistics
root=Path(__file__).resolve().parent
records={}; hashes={}
for dest in sorted((root/'performance-nt-recheck').iterdir()):
    if not dest.is_dir(): continue
    app=json.loads((dest/'application.json').read_text(encoding='utf-8'));assert app['passed']
    summary=json.loads((dest/'summary.json').read_text(encoding='utf-8'))
    for case in app['results']:
        idx=str(case['case']);h=case['input_sha256'];assert idx not in hashes or hashes[idx]==h;hashes[idx]=h
    for idx,values in summary['results'].items():
        records.setdefault(idx,{}).setdefault(app['commit'],[]).extend(values['samples_us'])
assert len(records)==2
out={}
for idx in sorted(records,key=int):
    values=records[idx];assert set(values)=={'baseline','candidate'}
    assert all(len(v)==200 for v in values.values())
    a=statistics.median(values['baseline']);b=statistics.median(values['candidate'])
    out[idx]={'baseline_us':a,'candidate_us':b,'change_percent':(b/a-1)*100,'samples_per_version':200,'input_sha256':hashes[idx]}
    print(idx,round(a,3),round(b,3),round((b/a-1)*100,2),flush=True)
(root/'nt-recheck-comparison.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
