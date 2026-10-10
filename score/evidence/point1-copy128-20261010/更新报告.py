from pathlib import Path
import json
p=Path('score/点1读取128B仅用64B实验-20261010.md');s=p.read_text();a=s.index('| Git |');b=s.index('\n## 实验实现',a)
r=Path('score/evidence/point1-copy128-20261010');records=[json.loads(f.read_text()) for f in r.glob('*-oj.json')];records.sort(key=lambda x:x['submittedAt'],reverse=True)
t='| Git | 版本 | OJ | 点1μs | 状态 |\n|---|---|---|---:|---|\n| 平台TBest（本轮参考） | 完整算子 | — | 1.20 | 参考 |\n'
for v in records:
 time=v['table'].splitlines()[1].split('\t')[3].replace('μs','');t+=f"| {v['git']} | {v['variant']} | [{v['id']}]({v['url']}) | {time} | 15/15 Pass |\n"
t+='| d9893db | 正式四核、紧凑UB及合法输入范围 | 704810 | 1.69 | 15/15 Pass，历史参考 |\n';s=s[:a]+t+s[b:]
s=s.split('\n## 15点原始时间')[0];s+='\n## 15点原始时间\n\n单位μs，所有点Pass，平台TBest固定首行，其余按源码提交时间倒序。\n\n| Git/参考 | '+ ' | '.join(map(str,range(1,16)))+' |\n|---|'+ '|'.join(['---:']*15)+'|\n'
s+='| 平台TBest（本轮） | '+' | '.join(x.split('\t')[4].replace('μs','') for x in records[0]['table'].splitlines()[1:])+' |\n'
for v in records+[json.loads(Path('score/evidence/point1-four-core-full-20261010/oj.json').read_text())]:
 s+='| '+v['git']+' | '+' | '.join(x.split('\t')[3].replace('μs','') for x in v['table'].splitlines()[1:])+' |\n'
p.write_text(s)
