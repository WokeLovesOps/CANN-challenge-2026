# 分组FinishSplitN候选P

| 候选 | 基线 | 本地完整编译 | OJ | 当前结论 |
| --- | --- | --- | --- | --- |
| P：多个行块共同执行逐分片Max | 4cc7e815 | 59.623秒，退出码0 | 待提交 | 静态及编译通过，尚无运行正确性或性能结论 |

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

未运行NPU或仿真。后续直接交OJ验证，远端编译必须≤300秒，本地59.623秒不替代远端验证。
