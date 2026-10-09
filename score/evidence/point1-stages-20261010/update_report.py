from pathlib import Path
import json,hashlib
p=Path(__file__).resolve().parent;e=Path('score/evidence/point1-stages-20261010');records=[]
for f in sorted(e.glob('stage*-oj.json')):
 d=json.loads(f.read_text());i=d['stage'];d['source_sha256']=hashlib.sha256((p/f'stage{i}.asc').read_bytes()).hexdigest();d['local_build_seconds']=float((p/f'stage{i}-build-seconds.txt').read_text());d['rows']=[dict(point=int(r[0]),status=r[1],error=r[2],duration_us=float(r[3].replace('μs','')),tbest_us=float(r[4].replace('μs',''))) for r in [x.split('\t') for x in d['rawTable'].splitlines()[1:]]];assert len(d['rows'])==15;f.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');records.append(d)
f=Path('score/点1四阶段OJ成本诊断-20261010.md');s=f.read_text();start=s.index('| 源码Git');end=s.index('## 测试方法',start)
rows=['| 源码Git | 阶段 | OJ | 点1μs | 点1状态 | 完整结果观测上界秒 |','|---|---|---|---:|---|---:|','| 平台TBest（当前结果页） | 完整算子 | — | 1.18 | 排行榜参考 | — |']
labels=['搬运前结束','搬入后结束','计算后结束','完整写回后结束']
for d in reversed(records):
 r=d['rows'][0];rows.append(f"| {d['git']} | {d['stage']}：{labels[d['stage']]} | [{d['submissionId']}]({d['url']}) | {r['duration_us']:.2f} | {r['status']} | {d['completeObservedUpperSeconds']:.3f} |")
rows.extend(['','### 全部测试点原始耗时','','| 源码Git / OJ | '+' | '.join(map(str,range(1,16)))+' |','|---|'+'---:|'*15,'| 平台TBest | '+' | '.join(f"{r['tbest_us']:.2f}" for r in records[-1]['rows'])+' |'])
for d in reversed(records):rows.append(f"| {d['git']} / {d['submissionId']} | "+' | '.join(f"{r['duration_us']:.2f}" for r in d['rows'])+' |')
s=s[:start]+'\n'.join(rows)+'\n\n'+s[end:];f.write_text(s)
