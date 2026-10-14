"""保存模型指令区间，仅用于定位，不替代真机计时。"""
from pathlib import Path
import json,hashlib,collections,csv
root=Path('/home/rose/cann-point2-analysis-20261013')
for folder in ('model','model-no-pipe'):
 paths=list((root/folder).glob('OPPROF*/*/1/simulator/core0.veccore0/trace.json'))
 if not paths: continue
 p=paths[0];events=[x for x in json.loads(p.read_text())['traceEvents'] if x.get('ph')=='X'];origin=min(x['ts'] for x in events)
 groups={'输入搬运':lambda x:x['pid']==60 and x['name']=='MOV_SRC_TO_DST_ALIGN','索引Vector计算':lambda x:x['name'] in ('VADDS','VMULS'),'Cast':lambda x:x['name']=='VCONV','Gather':lambda x:x['name']=='VGATHER','乘法':lambda x:x['name']=='VMUL','点积求和':lambda x:x['name']=='VCADD' and '0xf000008' in x.get('args',{}).get('detail',''),'行Max':lambda x:x['name']=='VCMAX','最终Sum':lambda x:x['name']=='VCADD' and '0x100000100' in x.get('args',{}).get('detail',''),'输出搬运':lambda x:x['pid']==70 and x['name']=='MOV_SRC_TO_DST_ALIGN'}
 result={'source_trace':str(p),'trace_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'模型完整指令跨度_us':max(x['ts']+x['dur'] for x in events)-origin,'各阶段':{}}
 for name,predicate in groups.items():
  selected=[x for x in events if predicate(x)]
  if selected:result['各阶段'][name]={'指令数':len(selected),'起始_us':min(x['ts'] for x in selected)-origin,'结束_us':max(x['ts']+x['dur'] for x in selected)-origin,'跨度_us':max(x['ts']+x['dur'] for x in selected)-min(x['ts'] for x in selected),'指令时长和_us':sum(x['dur'] for x in selected)}
 (root/f'{folder}-summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(result,ensure_ascii=False))
