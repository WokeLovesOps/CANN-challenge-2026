from pathlib import Path
import json
repo=Path('/mnt/newdisk/code/CANN-challenge');d=repo/'score/evidence/point1-address-stages-20261010';records=json.loads((d/'OJ结果.json').read_text()) if (d/'OJ结果.json').exists() else []
labels=['空核','A/B地址加载与非空校验','A地址64B COPY一次','A/B地址各64B COPY']
lines=['# 点1地址加载与单次COPY阶段诊断（2026-10-10）','','## OJ汇总','','四阶段仅替换ComputeDot32函数体，签名、Host调度、单核启动及其他14点完整计算保持正式基线95f9cea。点1不写结果，预期WA；其他点应Pass。诊断结果不能当作有效算子成绩。','','| Git | 阶段 | OJ | 点1μs | 完整结果上界秒 |','|---|---|---|---:|---:|','| 平台TBest | 完整算子参考 | — | 1.20（前轮快照，待本轮核验） | — |']
for x in reversed(records):
    t=float(x['table'].splitlines()[1].split('\t')[3].replace('μs',''))
    lines.append('| %s | %s | [%s](%s) | %.2f | %.3f |'%(x['git'],labels[x['stage']],x['id'],x['url'],t,x['upperBoundSeconds']))
lines+=['','## 方法与边界','','四个ComputeDot32<T>均为(GM_ADDR x1, GM_ADDR x2, GM_ADDR y)签名、KERNEL_TYPE_AIV_ONLY、单核、最终PIPE_ALL。无GM/UB预初始化、无TPipe、无数据计算、无结果搬出；读取平台实际A/B输入，不另外申请源GM。','','阶段0不要求装载未使用参数；平台拒绝空汇编地址约束版（没有产生OJ记录），经用户确认改用A/B非空指针校验保留地址参数加载。阶段1不访问输入内容、不写UB/GM；有效输入通过校验后执行PIPE_ALL。阶段2保留相同校验，再以常量DataCopyExtParams读取A的64B；阶段3再读B的64B到独立UB槽。地址阶段包含比较与条件分支，不是纯寄存器加载。接口为当前正式实现的无填充DataCopyPad。','','“相同签名”不能保证相同机器码前缀：编译器可能合并、重排参数和描述符设置。阶段差分是新增操作、设置与完成等待的总成本，不是独立硬件指令延迟。本地核验实际LD/LDP参数加载、0/0/1/2条真实GM→UB指令、无搬出及外部输入输出未修改。','','本地软件模型为CANN9.0.0、dav-2201、Ascend910B3；模型不替代OJ。两次调用改变A，截断诊断不检查数学输出，但检查整个输出区保持不变及输入不变。原始库、源码、BIN、CSV、日志在Build/point1-address-stages-20261010，Git保存补丁、脚本、哈希和摘要。首次桥接文件漏ACL头文件导致编译失败，已补齐；地址汇编使用r约束亦被bisheng拒绝，SDK示例的64位l约束最小编译通过后重建。所有原失败日志保留。汇编一笔COPY试采超时、仅一份BIN且零COPY，判为采集失败。平台拒绝汇编地址版，无提交记录；经用户授权改用指针校验，原汇编模型和构建哈希单独保留，不用于新方案计时。','','每个阶段OJ前保存Git快照、编辑器复制逐字核对。平台独立编译时间未披露，提交到完整结果观测上界<300秒才保守确认编译上限；沿用至少305秒提交间隔避免前轮限流。','','## 本地指令与模型结果','','| 阶段 | 双次模型μs | 双次COPY条数 | 参数加载指令 | 采集完整 |','|---|---|---|---|---|']
for i in range(4):
    p=d/f'stage{i}-model.json'
    if not p.exists():continue
    x=json.loads(p.read_text());ins=x['instructions'][-1];loads=[v['instr']+':'+v['detail'] for v in ins if v['instr'].startswith('LD')]
    lines.append('| %s | %s | %s | %s | %s |'%(labels[i],'/'.join(str(v['duration_us']) for v in x['timings']),x['copy_counts'],'；'.join(loads),x['passed']))
if records:
    lines[lines.index('| 平台TBest | 完整算子参考 | — | 1.20（前轮快照，待本轮核验） | — |')]='| 平台TBest（本轮结果） | 完整算子参考 | — | '+records[-1]['table'].splitlines()[1].split('\t')[4]+' | — |'
    lines+=['','## 全部15点原始耗时','','| Git/OJ | '+' | '.join(map(str,range(1,16)))+' |','|---|'+'---:|'*15]
    lines.append('| 平台TBest（本轮结果） | '+' | '.join(v.split('\t')[4].replace('μs','') for v in records[-1]['table'].splitlines()[1:])+' |')
    for x in reversed(records):lines.append('| %s/%s | %s |'%(x['git'],x['id'],' | '.join(v.split('\t')[3].replace('μs','') for v in x['table'].splitlines()[1:])))
if len(records)==4:
    t=[float(next(x for x in records if x['stage']==i)['table'].splitlines()[1].split('\t')[3].replace('μs','')) for i in range(4)]
    lines+=['','## 同点阶段差分','','| 项目 | 差分μs |','|---|---:|','| 空核 | %.2f |'%t[0],'| A/B地址装载及非空校验增量 | %.2f |'%(t[1]-t[0]),'| 首笔64B COPY及设置/等待增量 | %.2f |'%(t[2]-t[1]),'| 第二笔64B COPY及设置/等待增量 | %.2f |'%(t[3]-t[2]),'','差分来自四次跨窗口提交，必须结合未改点波动判断；同签名与相同PIPE_ALL不能消除机器码变化。若参数地址读取耗时大，不能推断可安全删除：真实输入地址始终必须取得。']
(repo/'score/点1地址与COPY四阶段诊断-20261010.md').write_text('\n'.join(lines)+'\n')
