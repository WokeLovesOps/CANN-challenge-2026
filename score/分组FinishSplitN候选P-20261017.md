# 分组FinishSplitN候选P

本报告保留P的历史验证记录；本轮收尾已在P基础上采用AG，当前状态见[仅OJ优化收尾结论](仅OJ优化收尾结论-20261017.md)。

| 候选 | 基线 | 本地完整编译 | OJ | 当前结论 |
| --- | --- | --- | --- | --- |
| P：多个行块共同执行逐分片Max | 4cc7e815 | 59.623秒，退出码0 | P1/P2/P3均15/15 Pass | 按综合分判据已生效为当前基线，未push；P3已完成，继续A7/U3相邻比较 |

## OJ结果及当前状态

源码提交`645a8bc5543ee1f924d009f4ef9dd201cd440f85`已快进至正式分支，源码SHA256为`3e6f28b59d9e75743e6fe2aea4e7f8c6686921c863a114dd7151be5c0d88c164`，尚未push。P1/P2/P3均15/15 Pass、错误占比均0.00%，OJ提交源码与本地源码逐字节一致。远端编译300秒上限由提交至首次观察Pass的全链路上界证明，不能称编译净耗时：P1为76.950秒，P2为122.781秒，P3为75.402秒。

单位微秒；平台TBest固定采用OJ869465页面快照。P同源码复测最新在前，A4/A5是前一轮相邻交错基线。

|记录|OJ|1|2|3|4|5|6|7|8|9|10|11|12|13|14|15|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|平台TBest|869465页面快照|0.99|1.47|1.92|2.48|3.42|6.08|6.39|24.59|46.46|61.58|65.53|80.07|7.64|8.10|6.19|
|P3|[872473](https://cannjudge.cn/public/op_challenge_shanghe_prelim/batchmatmulmaxsum/submission/6ad26b08193e507d8eb86848)|1.82|2.23|2.32|2.61|4.60|9.78|7.08|40.17|69.05|80.83|82.33|104.80|8.91|10.22|10.94|
|P2|[871380](https://cannjudge.cn/public/op_challenge_shanghe_prelim/batchmatmulmaxsum/submission/6ad25e50193e507d8eaaf411)|1.69|2.22|2.27|2.60|4.82|9.94|7.07|38.93|70.08|80.78|82.13|104.75|9.26|10.18|11.20|
|P1|[871223](https://cannjudge.cn/public/op_challenge_shanghe_prelim/batchmatmulmaxsum/submission/6ad25cb4193e507d8ea913be)|1.69|2.25|2.18|2.59|4.86|9.46|6.94|38.85|69.03|81.43|81.77|103.54|9.17|10.43|10.58|
|A5：4cc第五轮|见中心报告|1.78|2.19|2.16|2.65|4.73|9.79|7.14|42.82|69.01|81.55|82.57|104.83|9.39|10.51|10.79|
|A4：4cc第四轮|见中心报告|1.74|2.20|2.28|2.62|4.84|9.85|7.10|41.00|69.91|80.66|82.68|104.57|9.21|10.26|10.91|

公式分为各点`100/(1+ln(耗时/TBest)/ln(1.5))`的平均，不称平台榜单分。

|相邻交错对照|基线公式分|P公式分|差值|
|---|---:|---:|---:|
|A4→P1|58.69550929|59.94457307|+1.24906379|
|A5→P2|58.65508772|59.04363046|+0.38854273|

P两轮公式分均值59.49410176，相邻A4/A5均值58.67529851，相差+0.81880326。按用户最新判据，以稳定综合分提升作为有效标准，允许单点退化计入总分；两轮相邻交错对照整体均为正收益，P因此成为当前已验证有效工作基线，P3已完成，公式分59.15292734，三轮P公式分均值59.38037696；P3点8为40.17微秒，弱于前两轮38.85/38.93，需继续A7/U3相邻复测，确认当前窗口P与U谁的综合表现更好。两轮结果不足以确诊具体缓存或指令硬件原因。

正式归档：[P1身份](evidence/grouped-finish-splitn-20261017/P-identity.json)、[P2身份](evidence/grouped-finish-splitn-20261017/P-repeat-identity.json)、[P3身份](evidence/grouped-finish-splitn-20261017/P3-identity.json)、[交错统计](evidence/grouped-finish-splitn-20261017/P-interleaved-statistics.json)、[三轮统计](evidence/grouped-finish-splitn-20261017/P3-statistics.json)。同目录保留三轮结果文本及实际提交源码。以下保留原静态设计与本地构建记录。

## 改动范围

仅修改共享FinishSplitN，按资源上限把多个rowTile分为一组，同时进行各分片的逐元素Max。输入仍为[tile][part][行]，分组最大值为[tile][行]。当前调用方覆盖Generic的32行、矮宽Compute的64行、驻留TT的112/128行、Compute及ResidentA的128行、SwappedTT的256行。非split的Finish及其他独立收尾路径不变。

既有BULK_PARTIAL条件成立时仍一次搬入整个batch，仅使用组视图完成Max；未启用bulk时按组搬入至多16KiB。每个tile的validRows求和、sums槽位置、最终Sum及Scalar写回均保持，不叠加K的直接输出或L双槽预取。组不足两块、repeat stride超界或容量不足时保留原逐tile路径和原bulk输入分配。

只按已有输入布局、行块数量、指令字段和资源容量选择，不读取数据内容，不匹配精确shape、K或测试点。候选独立基于4cc，没有叠加其他实验。

## 指令语义及数据依赖

记R为TILE_ROWS、P为parts、G为本组实际tile数。SDK BinaryRepeatParams的repeat stride为uint8，单位32字节；Max的repeat为uint8。调用前守卫R及P*R按8个float对齐、R/8与P*R/8≤255，G≤255。

首part合并使用`{1,1,1,R/8,P*R/8,P*R/8}`，读取每tile的part0和part1；后续使用`{1,1,1,R/8,R/8,P*R/8}`，左侧为已有maxima、右侧为当前part。外层part按1、2、3递增，故各元素比较顺序与原始路径相同。行内按至多64个float分段；R112为64和48两个mask，R256为四个64，不能把112或256直接当作一次float repeat的mask。

同一part的行内片段写入不重叠的地址，全部发射后PIPE_V确保下个part读取当前结果；最后一轮屏障也确保Sum读取全部Max结果。每tile的Sum仍用原函数、validRows和原temp，逐tile保留PIPE_V，避免复用temp或下一组覆盖maxima时发生依赖错误。

所有五类当前partial生产者均先Duplicate完整R行输出槽，再写入validRows结果，故尾tile额外行是已初始化零；分组Max可以处理整个R行槽，但只有validRows参与Sum。最后一组repeat使用activeTiles，GM偏移为`(batch*rowTiles+firstTile)*P*R`，不会跨batch。非bulk单输入槽完成搬入、出队、所有Max/Sum后才Free；bulk整batch缓冲在全部组结束后Free。

## 完整域UB容量

当前所有FinishSplitN调用方既有显式UB上界为133120字节（SwappedTT256及Compute/ResidentA128达到此保守上界；Generic32为17280、矮宽Compute64为66560、驻留TT112/128为30464/34816）。SwappedTT的额外sumTemp仅parts==1分支分配，该分支不调用FinishSplitN，不能重复加入这里。

预算为SDK实际`TOTAL_VEC_LOCAL_SIZE-sizeof(KfcMsg)`。dav2201的TOTAL_VEC_LOCAL_SIZE为184KiB，低于完整192KiB UB，保留SDK临时区并额外保守扣除KFC消息；没有硬写KfcMsg大小。此预算针对当前4cc的全部调用族，未来新增调用方或叠加其他UB候选必须重新核算。

fixed为调用方133120、output256、sums的count*4、temp的tempCount*4、reduce32。count和tempCount使用原公式，覆盖Host m≤8192的完整域，不把rowTiles截成核心数。

- 非bulk：G不超过`floor(16384/(4*P*R))`及`floor((budget-fixed)/(4*R*(P+1)))`，所以输入及maxima总量在余量内。
- bulk：先扣除整个batch输入`4*rowTiles*P*R`，再按每tile maxima的4*R求容量上限；不能仅扣当前组输入。
- 先比较再减法，避免无符号下溢；所有分配均为32字节整数倍。G不足2不启用新路径，原路径分配和归约保持。

未把显式容量推导或SDK预留策略描述为NPU实际执行证明。

## 静态证据、构建及独立审查

静态地址核验对R32/64/112/128/256、parts2至64及完整m行块范围，枚举所有满足16KiB和stride限制的组大小，共121757个地址算术组合；检查每组最后repeat/最后part、行内mask、最后一组、GM batch范围及目的容量。只进行整数地址运算，没有执行算子、模拟浮点值或启动NPU。证据和可复查脚本位于`score/evidence/grouped-finish-splitn-20261017/`。源码在FinishSplitN以外与4cc逐字一致，无诊断printf。

先加载`/mnt/newdisk/Ascend/cann-9.0.0/set_env.sh`，通过bisheng完整编译正式源桥接，59.622708644秒成功。源码SHA256为`3e6f28b59d9e75743e6fe2aea4e7f8c6686921c863a114dd7151be5c0d88c164`，共享库SHA256为`b92408cb053d6ee14a45de7ff51706f128c37bf816515b099d3db4c1419e3d7f`。

address_control独立审查全部调用方尾槽初始化、R112的64/48 mask、repeat和stride字段、part/Sum顺序、bulk整batch搬运、容量守卫及实际源码/SO哈希绑定，未发现阻塞，无修改建议。组Max减少的是跨tile串行发射与屏障，可能增加maxima占用及行内分段指令，不预设加速。

本地阶段未运行NPU或仿真。随后P1/P2/P3的OJ正确性及远端编译上界已验证，详见上方；本地59.623秒不替代远端验证。
