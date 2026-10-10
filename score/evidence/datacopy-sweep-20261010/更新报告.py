from pathlib import Path
import json
repo=Path('/mnt/newdisk/code/CANN-challenge');d=repo/'score/evidence/datacopy-sweep-20261010';m=json.loads((d/'实验配置.json').read_text());results=json.loads((d/'OJ结果.json').read_text()) if (d/'OJ结果.json').exists() else []
lines=['# 单次GM到UB COPY规模诊断（2026-10-10）','','## 提交汇总','','所有点固定启动1个AIV核；不初始化源GM或目标UB；非空探针一次DataCopy API调用后PIPE_ALL排空结束，不计算、不搬出。全部WA为预期诊断结果，不计作有效算子成绩。','','| Git | 批次 | OJ | 点1～15耗时μs | 完整结果上界秒 |','|---|---|---|---|---:|','| 平台TBest | 完整算子参考 | — | 不适用于搬入探针，不比较得分 | — |']
for r in reversed(results):
 vals=[x.split('\t')[3].replace('μs','') for x in r['table'].splitlines()[1:]]
 lines.append(f"| {r['git']} | {m['batches'][r['batch']]['name']} | [{r['id']}]({r['url']}) | {' / '.join(vals)} | {r['upperBoundSeconds']:.3f} |")
lines+=['','## 测量口径','','用户确认只测单次搬运：循环每次128B即收录128B，不累计循环2KB。清单中的分行项是一条DataCopy描述符调用，另列行数与单行长度；不累加kernel其他COPY。131072B、196608B明确为范围采样，不是当前实际单次量。当前15点GM→UB搬入规模与尾块，另补32B至192KiB代表规模。Cube的GM→L1/ND→NZ通路不等价于GM→UB，本轮不将其时长混入结论。','','普通COPY仅支持32B对齐，非对齐项向上对齐搬运并明确真实读取长度；Pad按精确字节读取。源空间足够容纳普通COPY多读的对齐尾部。Pad默认不启用填充值；非对齐配置另测Pad补零功能，它仅属于本次COPY，不是事先初始化。','','全局前后空核仅PIPE_ALL，不读参数；每个搬入批点1为同一测量kernel的零搬运分支，仍可能包含参数读取，只用作批间漂移锚点。按相同OJ测试点扣除全局空核，避免把首点启动异常带到其他点。最终同时记录前测/后测差分及两者平均差分，不将差分称为纯DMA硬件服务延迟。','','所有COPY配置使用相同MeasureCopy机器码入口和参数布局，确保每项仅改变描述符。新分配1MiB未初始化GM源，固定192KiB UB目标，没有Memset、Host H2D、Duplicate、Cast、Mul、归约、输入张量修改或答案缓存。内存由捕获模型销毁回调持有，普通调用同步后释放；每次算子仅启动一次。','','## 单次配置与覆盖','','| 批/点 | 名称 | 行数 | 单行字节 | 有效总字节 | 实际读字节 | 源行距 | 接口 | Pad填充 | 来源 |','|---|---|---:|---:|---:|---:|---:|---|---|---|']
for i,b in enumerate(m['batches']):
 for j,c in enumerate(b['configs'],1):
  if c is None:continue
  lines.append(f"| {i}/{j} | {c['name']} | {c['rows']} | {c['line']} | {c['payloadBytes']} | {c['readBytes']} | {max(c['pitch'],(c['line']+31)//32*32)} | {'DataCopy' if c['mode']==0 else 'DataCopyPad'} | {'启用尾部补零' if c['pad'] else '无'} | {c['coverage']} |")
lines+=['','## 仿真与构建证据','','本地CANN9.0.0、bisheng dav-2201、Ascend910B3模型。诊断副本不改CMake，9个源版本独立编译。普通调用双采集逐项确认一条真实Src:OUT,Dst:UB指令、无搬出指令、外部输入输出未修改，记录源码/库/BIN哈希。空核确认零搬入。模型时长不替代OJ。','','图捕获试采ACL调用成功，但重放的第二份指令信息为空，因此捕获采集不完整，不作为指令证明；另用完整普通调用采集验证。试采构建地址空间转换报错和输出目录权限错误均已修正，原日志保留。Pad填充值设置MOV_SPR_XN曾被脚本误计为第二次COPY，已改为根据Src:OUT,Dst:UB筛选，原失败记录保留在Build。','','原始源码、库、构建日志、BIN、CSV在Build/datacopy-sweep-20261010，被Git忽略；Git保存实验配置、生成/复现脚本、模型摘要、OJ原始表格和截图，不声称原始BIN入Git。','','## 当前完成状态','']
for i,b in enumerate(m['batches']):
 mods=d/f'batch{i}-models.json';x=json.loads(mods.read_text()) if mods.exists() else [];done=sum(v['passed'] for v in x);oj=next((r for r in results if r['batch']==i),None)
 lines.append(f"- 批{i} {b['name']}：本地完成{done}项；OJ{'已完成，ID'+str(oj['id']) if oj else '待提交/待结果'}。")
if len(results)==len(m['batches']):
 first=next(r for r in results if r['batch']==0);last=next(r for r in results if r['batch']==8)
 a=[float(l.split('\t')[3].replace('μs','')) for l in first['table'].splitlines()[1:]];b=[float(l.split('\t')[3].replace('μs','')) for l in last['table'].splitlines()[1:]]
 lines+=['','## 空核扣除后的逐项成本','','单位μs。前后平均为空核参考；负差分原样保留，不解释为负硬件耗时。','','| 批/点 | 配置 | 原耗时 | 空核前 | 空核后 | 减前测 | 减后测 | 减空核均值 |','|---|---|---:|---:|---:|---:|---:|---:|']
 for r in results:
  i=r['batch']
  for j,l in enumerate(r['table'].splitlines()[1:]):
   c=m['batches'][i]['configs'][j]
   if c is None:continue
   t=float(l.split('\t')[3].replace('μs',''));name=f"{c['name']} {'Copy' if c['mode']==0 else 'Pad'} {'补零' if c['pad'] else ''}"
   lines.append(f'| {i}/{j+1} | {name} | {t:.2f} | {a[j]:.2f} | {b[j]:.2f} | {t-a[j]:.2f} | {t-b[j]:.2f} | {t-(a[j]+b[j])/2:.2f} |')
(repo/'score/单次COPY规模诊断-20261010.md').write_text('\n'.join(lines)+'\n')
