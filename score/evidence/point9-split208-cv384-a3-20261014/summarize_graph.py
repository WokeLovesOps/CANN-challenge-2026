"""汇总交错采样，校验应用成功与同输入；模型指令仅用于诊断。"""
from pathlib import Path
import csv,json,statistics,collections
root=Path(__file__).resolve().parent
result={}
for v in ['baseline','candidate']:
    samples=[];hashes=[]
    for d in sorted((root/'graph-performance').glob('*-'+v)):
        a=json.loads((d/'application.json').read_text(encoding='utf-8'));assert a['passed']
        hashes.append(a['results'][0]['input_sha256'])
        samples+=json.loads((d/'summary.json').read_text(encoding='utf-8'))['results']['9']['samples_us']
    assert len(samples)==100 and all(h==hashes[0] for h in hashes)
    result[v]={'median_us':statistics.median(samples),'mean_us':statistics.mean(samples),'samples':len(samples),'input_sha256':hashes[0]}
assert result['baseline']['input_sha256']==result['candidate']['input_sha256']
(root/'graph-comparison.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result))
