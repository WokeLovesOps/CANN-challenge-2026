from pathlib import Path
import json,statistics
p=Path('score/evidence/point1-stages-20261010');r=[json.loads((p/f'stage{i}-oj.json').read_text()) for i in range(4)];t=[d['rows'][0]['duration_us'] for d in r];d=[round(t[i+1]-t[i],6) for i in range(3)];labels=['搬运前基线','输入阶段增量','计算阶段增量','输出阶段增量'];cost=[t[0]]+d
s='\n## 最终阶段差分分析\n\n| 项目 | 算式 | 本轮OJ μs | 占完整阶段比例 |\n|---|---|---:|---:|\n'
for i,(label,v) in enumerate(zip(labels,cost)):
 formula='T0' if i==0 else f'T{i}−T{i-1}';s+=f'| {label} | {formula} | {v:.2f} | {100*v/t[3]:.1f}% |\n'
s+=f'\n完整阶段T3={t[3]:.2f}μs，相对搬运前基线增加{t[3]-t[0]:.2f}μs。上表比例仅是本轮阶段差分占比，不是硬件单元利用率，也不是每条DMA的独立服务延迟。\n\n'
s+='本轮最大增量来自输入阶段；计算阶段增量较小，单纯削减Cast/Mul/归约指令未必触及主要成本。输入阶段同时引入输入参数加载、两次64字节GM→UB搬运、MTE2_V同步和终止等待；输出阶段同时引入输出参数加载、4字节DataCopyPad和输出完成等待，不能只归因于DataCopyPad。\n\n'
s+='未改测试点提供跨窗口波动参考：\n\n| 相邻阶段 | 点2～15耗时相对变化中位数 | 最小变化 | 最大变化 |\n|---|---:|---:|---:|\n'
for i in range(3):
 changes=[100*(b['duration_us']/a['duration_us']-1) for a,b in zip(r[i]['rows'][1:],r[i+1]['rows'][1:])];s+=f'| {i}→{i+1} | {statistics.median(changes):+.2f}% | {min(changes):+.2f}% | {max(changes):+.2f}% |\n'
s+='\n其他测试点未改但出现波动，四次仅各测一轮，没有ABBA统计验证；阶段差分用作定位方向，不能当精确稳定的延迟。T0也不是纯硬件启动时间。阶段0～2点1WA是预期诊断；完整阶段15/15 Pass才能视为完整算子证据。\n\n所有提交的远端完整流程观测上界均小于300秒，保守验证编译硬上限；平台没有披露独立编译时间。各次提交间隔大于180秒。源码、逐点耗时、截图和模型证据已保存当前分支，正式源码逐字恢复9adcc9d；未推送远端或改main。\n'
f=Path('score/点1四阶段OJ成本诊断-20261010.md');f.write_text(f.read_text()+s);(p/'差分.json').write_text(json.dumps(dict(stage_times_us=t,stage_increments_us=d),ensure_ascii=False,indent=2)+'\n');print(s)
