"""汇总Cube固定缓冲候选的模型指令，仅作诊断。"""
from pathlib import Path
import json,csv,collections
root=Path(__file__).resolve().parent
out={}
for p in (root/'model').rglob('*instr_exe*.csv'):
    if '/1/' not in p.as_posix():continue
    counts=collections.Counter()
    for r in csv.DictReader(p.open()):counts[r['instr']]+=int(r['call_count'])
    events=[e for e in json.loads((p.parent/'trace.json').read_text())['traceEvents'] if e.get('ph')=='X'];origin=min(e['ts'] for e in events)
    out[p.parent.name]={'counts':dict(counts),'span_us':max(e['ts']+e['dur'] for e in events)-origin,'stages':{}}
    for name in ('MOV_OUT_TO_L1_MULTI_ND2NZ','LOAD_2D','MMAD','FIX_L0C_TO_DST','WAIT_FLAG_DEVI','VCMAX','VCADD'):
        es=[e for e in events if e['name']==name]
        if es:out[p.parent.name]['stages'][name]={'count':len(es),'start_us':min(e['ts'] for e in es)-origin,'end_us':max(e['ts']+e['dur'] for e in es)-origin}
(root/'model-summary.json').write_text(json.dumps(out,indent=2))
print(json.dumps(out))
