from pathlib import Path
import json,statistics
repo=Path('/mnt/newdisk/code/CANN-challenge')
d=repo/'score/evidence/datacopy-sweep-20261010'
m=json.loads((d/'实验配置.json').read_text())
r=json.loads((d/'OJ结果.json').read_text())
def times(x):
    return [float(v.split('\t')[3].replace('μs','')) for v in x['table'].splitlines()[1:]]
a=times(next(x for x in r if x['batch']==0));b=times(next(x for x in r if x['batch']==8));base=[(x+y)/2 for x,y in zip(a,b)]
zero=next(x for x in r if x['batch']==7)
zero_deltas=[t-base[j] for j,t in enumerate(times(zero)) if j>=10]
records=[]
for x in r:
    for j,t in enumerate(times(x)):
        c=m['batches'][x['batch']]['configs'][j]
        if c is None or j+1 in x.get('invalidCopySlots',[]):continue
        records.append(dict(c,batch=x['batch'],point=j+1,time=t,delta=t-base[j]))
by={}
for x in records:by.setdefault(x['name'],{})[(x['mode'],x['pad'])]=x
pairs=[]
for name,v in by.items():
    if (0,False) in v and (1,False) in v:
        a1,b1=v[(0,False)],v[(1,False)]
        pairs.append(dict(name=name,copy_delta=a1['delta'],pad_delta=b1['delta'],pad_minus_copy=b1['delta']-a1['delta'],aligned=a1['line']%32==0))
(d/'差分分析.json').write_text(json.dumps(dict(empty_before=a,empty_after=b,empty_average=base,records=records,pairs=pairs),ensure_ascii=False,indent=2)+'\n')
lines=['','## 分析结论','','以下都是一次COPY加必要完成等待、相对纯空核的增量，包含参数装载、地址/描述符设置、DMA发射和完成等待；不是纯DMA服务延迟。源GM每次新分配而不初始化，与完整算子的输入缓存状态可能不同。每配置只测一次OJ，不能据此判断0.01～0.1μs差别是稳定收益。','','### 空核漂移','','前后空核各点绝对差最大 %.2fμs，点2～15差值中位数 %.2fμs。'%(max(abs(x-y) for x,y in zip(a,b)),statistics.median(abs(x-y) for x,y in zip(a[1:],b[1:]))),'','### 普通COPY与Pad配对','','| 描述符 | 普通COPY增量μs | Pad增量μs | Pad−COPY μs | 读取量关系 |','|---|---:|---:|---:|---|']
for v in pairs:
    lines.append('| %s | %.3f | %.3f | %.3f | %s |'%(v['name'],v['copy_delta'],v['pad_delta'],v['pad_minus_copy'],'相同' if v['aligned'] else '普通COPY向上32B对齐，Pad精确字节'))
lines+=['','### 参数与零分支对照','','第7批点11～15执行同一COPY kernel的零搬运分支，原时间为'+str(times(zero)[10:])+'μs；减相同点前后空核均值后，增量为'+str([round(x,3) for x in zero_deltas])+'μs，中位数%.3fμs。'%statistics.median(zero_deltas),'','该增量包含通用探针参数读取、零分支和结束等待的差异。小COPY相对纯空核的增量中有相当部分属于探针固定成本；不能把整个增量称为搬入服务时间，也不能用跨点零分支直接精确拆分某个COPY。正式算子的常量描述符可能无需同样参数装载，应按完整kernel对照确认。','','### 连续规模汇总','','| 单次长度 | 普通COPY原时间/差分μs | Pad原时间/差分μs |','|---:|---:|---:|']
for name,v in sorted(by.items(),key=lambda z:next(iter(z[1].values()))['line']):
    x=next(iter(v.values()))
    if x['rows']!=1 or not name.startswith('连续'):continue
    vals=[]
    for k in [(0,False),(1,False)]:
        t=v.get(k);vals.append('—' if t is None else '%.2f / %.3f'%(t['time'],t['delta']))
    lines.append('| %dB | %s | %s |'%(x['line'],*vals))
(repo/'score/单次COPY规模诊断-20261010.md').open('a').write('\n'.join(lines)+'\n')
print('有效COPY样本',len(records),'配对描述符',len(pairs),'空核最大漂移',max(abs(x-y) for x,y in zip(a,b)))
