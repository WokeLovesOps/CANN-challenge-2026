"""汇总点7复测，保留每轮中位数和输入一致性证据。"""
from pathlib import Path
import json,statistics
root=Path(__file__).resolve().parent
out={};all_hashes=[]
for v in ('baseline','candidate'):
    samples=[];rounds=[]
    for d in sorted((root/'performance-point7-recheck').glob('*-'+v)):
        a=json.loads((d/'application.json').read_text());assert a['passed']
        all_hashes.append(a['results'][0]['input_sha256'])
        values=json.loads((d/'summary.json').read_text())['results']['7']['samples_us']
        assert len(values)==50
        samples+=values;rounds.append(statistics.median(values))
    assert len(samples)==200
    out[v]={'median_us':statistics.median(samples),'round_medians_us':rounds,'samples':len(samples)}
assert all(h==all_hashes[0] for h in all_hashes)
out['input_sha256']=all_hashes[0]
(root/'recheck7.json').write_text(json.dumps(out,indent=2))
print(json.dumps(out))
