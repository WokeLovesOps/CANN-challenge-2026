from pathlib import Path
import json
p=Path('score/输入基址对齐OJ探测-20261010.md');s=p.read_text();a=s.index('| Git |');b=s.index('\n## 探测方法',a)
r=Path('score/evidence/input-alignment-20261010');records=[json.loads(f.read_text()) for f in r.glob('*-oj.json')];old=r/'B64-首次迟观测.json'
if old.exists():records.append(json.loads(old.read_text()))
records.sort(key=lambda x:x['submittedAt'],reverse=True)
t='| Git | 条件 | OJ | 点1μs | 15点判定 | 完整结果观测上界秒 |\n|---|---|---|---:|---|---:|\n| 平台TBest（本轮参考） | 完整算子性能参考 | — | 1.20 | 不用于地址判定 | — |\n'
for v in records:
 time=v['table'].splitlines()[1].split('\t')[3].replace('μs','');text='全部对齐' if all(v['aligned']) else '不对齐点：'+','.join(str(i+1) for i,x in enumerate(v['aligned']) if not x)
 bound=f"{v['upperBoundSeconds']:.3f}" if v['upperBoundSeconds'] is not None else '迟观测，未验证'
 t+=f"| {v['git']} | {v['probe']} | [{v['id']}]({v['url']}) | {time} | {text} | {bound} |\n"
s=s[:a]+t+s[b:];s=s.split('\n## 逐点对齐判定')[0]
s+='\n## 逐点对齐判定\n\n是=Pass，否=Wrong Answer，—=尚未测量。\n\n| 点 | A64 | A128 | A256 | B64 | B128 | B256 |\n|---:|---|---|---|---|---|---|\n'
for i in range(15):
 cells=[]
 for probe in ['A64','A128','A256','B64','B128','B256']:
  v=next((v for v in records if v['probe']==probe),None);cells.append('—' if v is None else ('是' if v['aligned'][i] else '否'))
 s+=f'| {i+1} | '+' | '.join(cells)+' |\n'
s+='\n## 15点时间与状态\n\n时间单位μs，平台TBest固定首行，探针按源码Git提交时间倒序。本实验用状态判地址，时间仅归档。\n\n| Git/参考 | '+' | '.join(map(str,range(1,16)))+' |\n|---|'+ '|'.join(['---']*15)+'|\n'
s+='| 平台TBest（本轮） | '+' | '.join(x.split('\t')[4].replace('μs','') for x in records[0]['table'].splitlines()[1:])+' |\n'
for v in records:
 s+='| '+v['git']+' | '+' | '.join(x.split('\t')[3].replace('μs','')+' '+x.split('\t')[1] for x in v['table'].splitlines()[1:])+' |\n'
p.write_text(s)
