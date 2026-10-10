from pathlib import Path
import json
p=Path('score/点1多核空kernel启动诊断-20261010.md')
s=p.read_text();a=s.index('| Git |');b=s.index('\n## 测试方法',a)
records=[json.loads(f.read_text()) for f in Path('score/evidence/point1-empty-cores-20261010').glob('core*-oj.json')];records.sort(key=lambda x:x['submittedAt'],reverse=True)
t='| Git | 点1启动核数 | OJ | 点1μs | 完整结果观测上界秒 |\n|---|---|---|---:|---:|\n| 平台TBest（本轮结果） | 完整计算 | — | 1.20 | — |\n'
for r in records:
 row=r['table'].splitlines()[1].split('\t');t+=f"| {r['git']} | {r['cores']} | [{r['id']}]({r['url']}) | {row[3].replace('μs','')} | {r['upperBoundSeconds']:.3f} |\n"
t+='| 24791c9（前轮参考） | 1 | 702951 | 1.13 | 62.777 |\n'
s=s[:a]+t+s[b:];s=s.split('\n## 每次提交15点原始时间')[0]
s+='\n## 每次提交15点原始时间\n\n均为点1预期WA、其余14点Pass；时间单位μs。\n\n| Git | 核数 | '+ ' | '.join(map(str,range(1,16)))+' |\n|---|---|'+ '|'.join(['---:']*15)+'|\n'
for r in records:
 times=[x.split('\t')[3].replace('μs','') for x in r['table'].splitlines()[1:]];s+=f"| {r['git']} | {r['cores']} | "+' | '.join(times)+' |\n'
p.write_text(s)
