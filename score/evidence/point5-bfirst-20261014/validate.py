"""定向检查容量边界、路径切换和图重放，保留真实退出码。"""
from pathlib import Path
import subprocess,json
r=Path(__file__).resolve().parent
indices=sorted(set(range(0,1180,30))|set(range(1180,1208)))
command=['python3',str(r/'tests/small_cube_bfirst_domains.py'),str(r/'libcandidate.so'),'--capture','--real-npu','--cases',','.join(map(str,indices)),'--report',str(r/'domains-selected.json')]
(r/'validation-command.json').write_text(json.dumps(command,ensure_ascii=False,indent=2),encoding='utf-8')
with (r/'domains-selected.log').open('w') as log:
    subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=240)
d=json.loads((r/'domains-selected.json').read_text(encoding='utf-8'))
assert d['passed'] and len(d['results'])==len(indices) and all(x['passed'] for x in d['results'])
print('边界及图重放通过',len(indices),flush=True)
