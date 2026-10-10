from pathlib import Path
import json,csv,hashlib,re
r=Path(__file__).resolve().parent
d=Path('score/evidence/point1-empty-cores-20261010')
import sys
for n in map(int,sys.argv[1:]):
 p=r/'sim'/f'core{n}'
 record=json.loads((p/'执行检查.json').read_text())
 files=list(p.glob('profile/**/*instr_exe*.csv'))
 assert len(files)==n*2,(n,len(files))
 records=[]
 for f in files:
  rows=list(csv.DictReader(f.open()))
  assert not any(v['instr'].startswith(('LD','ST')) or v['pipe'] in ('MTE2','MTE3') for v in rows)
  assert [v['instr'] for v in rows if v['pipe']=='VECTOR']==['MOVEMASK','MOVEMASK']
  assert sum(int(v['call_count']) for v in rows if v['instr']=='BAR')==1
  records.append(dict(path=str(f),instructions=rows))
 bins=list(p.glob('profile/**/visualize_data.bin'))
 assert len(bins)==2 and record['passed']
 record.update(cores=n,source_sha256=hashlib.sha256((r/f'core{n}.asc').read_bytes()).hexdigest(),instructions=records,bins=[dict(path=str(f),sha256=hashlib.sha256(f.read_bytes()).hexdigest(),size=f.stat().st_size) for f in bins])
 record['timings']=re.findall(r'(core\d+\.veccore\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)',(r/f'core{n}-sim.log').read_text())
 (d/f'core{n}-model.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
 print(n,record['passed'],len(files),record['timings'])
