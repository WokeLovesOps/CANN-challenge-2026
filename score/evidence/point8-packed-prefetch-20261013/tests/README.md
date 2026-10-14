# NPU 正确性测试

测试入口独立于赛题模板，不修改 `src/main.asc`、`src/CMakeLists.txt` 或 `src/scripts/`。实际调用的是 `src/kernel.asc` 中的 `run_kernel`。

## 编译与运行

### 合法输入回退专项回归（2026-10-13）

`legal_input_fallback.py` 定义11个场景，每个场景覆盖两类型、四布局，共88个可选用例。
重点检查此前被裁剪分支拒绝的小矩阵、小批量非对齐K、中批量与紧凑批量的其他布局，
以及通用N分片、双GM槽、同核多任务、固化大矩阵和SplitK模板的邻近形状。
仍使用实际输入的FP64参考、双调用一致性、输入保护及输出保护区检查。

定向仿真命令如下；这里列出18组，不默认执行全部88组：

```bash
python3 tests/run_simulator_matrix.py /绝对路径/libsimulator_bridge.so \
    --application tests/legal_input_fallback.py \
    --cases=0,1,2,3,4,5,6,7,8,16,28,36,40,55,59,68,72,84 \
    --output=/新建私有目录/合法输入回退
```

相同入口支持 `--real-npu` 和 `--capture`；真机与图重放通过情况须单独记录。
本地编译和模型正确性不替代远端编译不超过300秒的验证。

### 常规正确性入口

先加载当前主机的 CANN 环境，再在仓库根目录执行：

```bash
cmake -S tests -B Build/Correctness -DNPU_ARCH=dav-2201
cmake --build Build/Correctness -j4
OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 python3 tests/correctness.py \
    Build/Correctness/correctness --report Build/correctness.json
```

当前本地 CANN 9.0.0 环境脚本为 `/home/ye/Ascend-9.0.0/cann-9.0.0/set_env.sh`；CANN 8.5.2 仍独立保存在 `/home/ye/Ascend/cann-8.5.2/set_env.sh`。两个版本必须在独立 shell 中加载，编译和测试记录必须标明实际版本。历史远端测试使用 `/home/developer/Ascend/cann-8.5.2/set_env.sh`，设备为 Ascend 910B3。

## 覆盖范围

以下每个场景覆盖 FP16、BF16 和四种转置存储组合，共 72 组。每组调用两次算子。

| 场景 | B | M | N | K |
| --- | ---: | ---: | ---: | ---: |
| 最小 | 1 | 1 | 1 | 32 |
| 双维尾块 | 2 | 33 | 129 | 40 |
| 多行多列块 | 3 | 65 | 257 | 128 |
| 最大 K | 1 | 33 | 129 | 8192 |
| 最大 M | 1 | 8192 | 3 | 32 |
| 最大 N | 1 | 3 | 8192 | 32 |
| 最大 Batch | 64 | 1 | 1 | 32 |
| 全负相似度 | 2 | 33 | 129 | 40 |
| 全零 | 2 | 33 | 129 | 40 |

Golden 使用量化后的实际输入存储值，FP64 点积、Max、Sum 后转为 FP32。通过条件为输出 shape 正确、全部有限，且每个元素满足 `abs(actual - golden) <= 1e-4 + 1e-4 * abs(golden)`。同时检查两次执行结果逐字节一致、输入未修改，以及输出前后各 64 字节保护区未被覆盖。

测试遇到首个失败立即停止，JSON 逐组保存已完成结果。每组子进程限时 120 秒；这里不记录性能分数，进程启动、保护区校验和重复调用不适合作为核函数性能测量。这 72 组是自主补充测试，并非官方未公开的 15 个测试点，也不穷尽所有合法 shape。

## 本地软件仿真

无 NPU 主机使用 CANN 的 Ascend910B3 软件模型。先初始化模型 ACL，再动态加载共享库；`simulator_bridge.asc` 直接包含正式 `src/kernel.asc`，不另写计算实现。

```bash
source /home/ye/Ascend-9.0.0/cann-9.0.0/set_env.sh
umask 077
cmake -S tests -B Build/SimulatorValidation \
    -DNPU_ARCH=dav-2201 -DBUILD_SIMULATOR_BRIDGE=ON -DCMAKE_ASC_FLAGS=-g
cmake --build Build/SimulatorValidation --target simulator_bridge -j2
PYTHONDONTWRITEBYTECODE=1 python3 tests/run_simulator_matrix.py \
    Build/SimulatorValidation/libsimulator_bridge.so \
    --output=Build/SimulatorValidationResults
```

输出目录必须尚不存在，以免覆盖已有证据。**默认只执行最小用例 0，每组模型运行上限为 2 分钟**；`--cases=0,8` 可指定定向场景，`--timeout-minutes` 可调整上限。完整 72 组需显式传入 `--all-cases`，大规模仿真须事先征得用户同意，不能默认启动。仿真应用复用上述量化输入、随机种子、FP64 golden 和误差判定，并使用模型报告的 Cube 核数。`--core-id=0` 仅限制解析核，不限制核函数只执行一个核。

每组必须同时满足应用打印 `SIM_CORRECTNESS_PASS`、没有超时、工具正常退出，以及两次调用恰好对应两次 `Compute` 启动和两份非空 `visualize_data.bin`。最终求和在 `Compute` 内完成，不另启动 `Finish`，符合 OJ 每次迭代只能启动一个 kernel 的规则。采集上限保留为四，便于检测意外多启动。`summary.json` 保存库哈希、Git 版本、命令、逐组启动名称和 BIN 哈希。源码行映射由 `-g` 提供，正常编译优化保持启用。

软件模型时间只用于定位指令与同步行为，不等于真实 NPU 的 Task Duration，也不用于计算比赛得分。`simulator_matrix.py` 默认拒绝脱离模型环境运行；显式 `--real-npu` 才进入上板验证流程。

### 行归约并行化的定向场景

仿真矩阵在原有场景后追加边界检查，保留已有用例编号。每个场景的八个编号依次覆盖 FP16/BF16 及四种存储布局；原先的 72–79 为单任务小矩阵，80–87 为列块流水槽复用。

| 用例编号 | 场景 | B,M,N,K | 检查目的 |
| --- | --- | --- | --- |
| 88–95 | 归约半行前尾 | 1,32,63,40 | mask 小于 64，排除无效列 |
| 96–103 | 归约半行边界 | 1,32,64,40 | 恰好一个 float repeat 的列宽 |
| 104–111 | 归约半行后尾 | 1,32,65,40 | 后半行只有一个有效值 |
| 112–119 | 归约整行前尾 | 1,32,127,40 | 后半行 mask 为 63 |
| 120–127 | 多核任务槽复用 | 1,641,65,32 | 21 个行任务超过模型报告的 20 核，覆盖同核下一任务复用 |

该轮只执行 16 个定向小用例：`0,8,9,10,12,15,56,63,64,79,87,88,96,104,112,120`，没有运行完整矩阵。每个用例仍执行两次正式核函数，并核验输出、输入、保护区、重复一致性、启动数和采集文件。当时仿真矩阵为 128 组；正文中的 72 组指原始正确性矩阵。

### 四路 N 分片的定向场景

在原编号后追加下列场景，每个场景仍对应两种类型和四种布局，共八个编号；仿真矩阵扩展为 200 组，默认继续只运行用例 0。

| 用例编号 | 场景 | B,M,N,K | 检查目的 |
| --- | --- | --- | --- |
| 128–135 | N 分片四块边界 | 1,2,385,32 | 四个分片中最后一片只有一列；两行最优列跨分片，正确分数为 23 |
| 136–143 | N 分片五块尾行 | 2,33,513,40 | 分片列块数不均、双 batch、尾行及非零起始槽 |
| 144–151 | N 分片长列流水 | 1,32,1537,128 | 每片有多个列块，覆盖双 GM 槽的多轮复用 |
| 152–159 | N 分片全负 | 1,31,1025,40 | 分片最大值不能从零初始化 |
| 160–167 | N 分片全零 | 1,31,1025,40 | 全零及尾行 |
| 168–175 | N 分片核数边界 | 5,1,385,32 | 模型报告 20 核时恰好启用 20 个分片任务 |
| 176–183 | N 分片核数回退 | 6,1,385,32 | 模型报告 20 核时，24 个分片任务超过核数，回退原路径 |
| 184–191 | N 分片列数回退 | 1,2,384,32 | 只有三个列块，回退原路径 |
| 192–199 | N 分片单行 | 1,1,512,40 | 单行及每片一个完整列块 |

用例 128–135 使用确定性数据：两行查询分别只取 K 轴前两个分量；普通列对应值为 -4，第 0 列的第一行为 10，第 128 列的第二行为 10，最后一列的第一行为 13。正确结果为 `13+10=23`，可以检出遗漏尾列、分片错误以及先求和再合并的错误。

本轮定向选择为 `0,8,15,128,129,130,131,132,133,134,135,136,143,144,152,159,160,168,176,184,192,40`，共 22 组；15 检查 BF16 双转置回退模板，40 沿用原始最大 N 场景。通过标准与此前相同，完整矩阵不默认执行。核数边界以运行环境实际报告的 Cube 核数为准，20 核仅指此次本地模型。

## 计算图捕获检查

`simulator_matrix.py --capture` 执行一次普通调用，再捕获一次并重放两次，逐次检查输出、保护区和逐字节重复一致性。工作区必须存活到图销毁；仅能结束捕获不算功能通过。

本地 CANN 9.0 模型流程尚未通过图重放对照检查：独立常数写入核也未在重放后更新输出。真实 NPU 验证需在得到授权后，在目标机器本地构建共享库，再执行以下命令，不能把 x86_64 库复制给 aarch64 Host 使用：

```bash
OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1 \
python3 tests/simulator_matrix.py Build/SimulatorValidation/libsimulator_bridge.so \
    --case=0 --capture --real-npu --report=Build/capture-npu-case0.json
```

第 26 号场景可用 `--case=26` 复现大 K 转置输入保护检查；不加 `--capture` 时执行普通连续两次调用。若输入被修改，JSON 记录首批差异字节，报告旁保存对应输入的 `.before.bin` 和 `.after.bin`。

### 自适应 N 分片的定向场景

`9f31802` 在原四路分片触发范围内，令分片数为 `min(可用 Cube 核数 / 行任务数, 列块数)`。以下编号追加到既有矩阵后，原编号和随机种子保持不变；当前共有 216 个可选用例，不代表全部已经执行。

| 用例编号 | 场景 | B,M,N,K | 检查目的 |
| --- | --- | --- | --- |
| 200–207 | N 自适应十三片 | 1,2,1537,32 | 20 核模型上使用 13 片，最后一列参与 Max；覆盖两种类型与四种布局 |
| 208–215 | N 自适应二十片 | 1,2,8192,32 | 20 片划分 64 列块，各片 3 或 4 块，检查跨片与流水槽复用 |

上述两种场景与原用例 128–135 使用相同构造：行 0 的最大值 13 在最后一列，行 1 的最大值 10 在第 128 列，正确结果为 23。用例 136、144、152 在 20 核模型上分别产生 5、13、9 路分片，168 保持四路，176、184 仍回退。

`run_simulator_matrix.py` 新增 `--core-ids`，默认 `0`；例如 `--core-ids='0|19'` 解析核 0 与核 19。该格式按本地 CANN 9.0.0 工具校验信息核对，编号范围为 0–49。此选项只改变解析范围，不改变传入算子的可用核数；采到两个核也不能宣称取得全核时间线。命令和解析核选择随 `summary.json` 保存。实际完成的用例与性能证据见 [测试记录](../score/BatchMatmulMaxSum.md)。

### 测试点 1 假设与单点积 Vector 路径

`4d1aa53` 新增 `ComputeDot`，仅在实际输入 `B=M=N=1、32<=K<=256` 时启用，一个 Vector 核完成 FP32 Cast、Mul 和 ReduceSum。普通路径仍使用 `Compute`，每次调用总共只能启动其中一个。现有启动数检查的 `Compute` 名称匹配同时覆盖这两个入口，最终证据还须按输入形状核对是否选中 `ComputeDot`。

`76db652` 将专用分支收窄为 FP16；BF16 小点积也恢复基线 Compute。平台核名已确认点 1 为 FP16 单点积，但具体 K 未知，因此保留合法 K=32–256 的范围。后续核入口核验需要同时检查 dtype 和形状，不能只按 B/M/N/K 判断。

追加场景保留既有编号与随机种子，当前矩阵为 328 个可选用例。本轮是定向验证，不代表运行完整矩阵。

| 用例编号 | B,M,N,K | 检查目的 |
| --- | --- | --- |
| 216–223 | 1,1,1,40 | 输入搬运不是 32B 整倍数的尾块 |
| 224–231 | 1,1,1,64 | FP32 一个 Vector repeat 的边界 |
| 232–239 | 1,1,1,128 | 多 repeat 归约 |
| 240–247 | 1,1,1,248 | K 上限前的非整 repeat 尾块 |
| 248–255 | 1,1,1,256 | 快路径上限 |
| 256–263 | 1,1,1,264 | K 刚超过上限时回退 |
| 264–271 | 1,1,1,256 | 全负点积 |
| 272–279 | 1,1,1,40 | 全零点积 |
| 280–287 | 1,1,1,256 | 正负大小乘积抵消，正确结果为 4 |
| 288–295 | 2,1,1,32 | B 不为 1 时回退 |
| 296–303 | 1,2,1,32 | M 不为 1 时回退 |
| 304–311 | 1,1,2,32 | N 不为 1 时回退 |
| 312–319 | 1,2,3,32 | 基础小矩阵的替代假设 |
| 320–327 | 1,16,16,32 | 对齐小矩阵的替代假设 |
| 328–335 | 1,1024,512,32 | `LARGE_BALANCED` 的64×128分块边界 |
| 336–343 | 1,64,64,32 | `TALL_NARROW` 的64×64单任务直接写回 |
| 344–351 | 1,3,5,40 | `SMALL_VECTOR` 打包点积矩阵及转置/BF16覆盖 |
| 352–359 | 1,4,4,64 | `SMALL_VECTOR` 的 `M×N=16` 与 `K=64` 双阈值边界 |
| 360–367 | 1,3,6,40 | `M×N` 超过16后回退Cube路径 |
| 368–375 | 2,7,13,48 | `SMALL_BATCH_VECTOR` 实际小批量矩阵及转置/BF16覆盖 |
| 376–383 | 2,9,13,48 | M超过8后回退Cube路径 |
| 384–391 | 4,8,16,64 | `SMALL_BATCH_VECTOR` 的B/M/N/K联合上界 |
| 392–399 | 2,7,13,48 | 全负点积不读取16列对齐槽中的填充值 |
| 400–407 | 2,7,13,40 | K不是16倍数时保留64元素对齐槽路径 |
| 408–415 | 4,16,16,128 | `MEDIUM_BATCH_VECTOR` 点4形状及转置/BF16覆盖 |
| 416–423 | 5,16,16,128 | `MEDIUM_BATCH_VECTOR` 的中间批量场景 |
| 424–431 | 4,16,16,80 | `MEDIUM_BATCH_VECTOR` 的K下界内部场景 |
| 432–439 | 4,16,16,128 | 全负点积覆盖分块最大值与最终求和 |
| 440–447 | 8,16,32,128 | `MEDIUM_BATCH_VECTOR` 点5形状及两轮16列分块覆盖 |
| 448–455 | 13,23,73,192 | `MEDIUM_BATCH_VECTOR` 点6形状及M/N/K尾块覆盖 |
| 456–463 | 16,32,128,256 | `MEDIUM_BATCH_VECTOR` 点7形状及B/M/N/K联合上界 |

每行的八个编号依次覆盖 FP16/BF16 和四种转置属性。单点积的四种实际存储布局均为连续 K 个元素，但仍检查属性不会影响正确性。隐藏点 1 的形状没有被确认；模板最小输入、历史用时和参考 TBest 只用于排列候选假设，不能把本地 case 0 等同于 OJ 点 1。

追加点6、点7的中等批量Vector边界后共有464个可选用例。默认仍只执行用例0，完整矩阵必须显式开启。


### 同进程核函数切换诊断

`simulator_sequence.py` 针对 `4d1aa53` 平台点 1 通过、点 2 首次 DeviceProf 预热失败补充普通调用诊断。同一进程、同一 ACL 上下文、同一共享库和 stream 内切换纯 Vector 点积与通用混合核，每段两次调用，保留逐段精度、输入保护、输出保护和重复一致性检查。只允许列出的随机输入用例，输入生成与矩阵入口相同；不覆盖其他特殊数值场景。默认仅接受软件模型环境，真实设备必须显式传入 `--real-npu`，两种模式均不覆盖图捕获。

```bash
source /home/ye/Ascend-9.0.0/cann-9.0.0/set_env.sh
msprof op simulator --soc-version=Ascend910B3 --core-id=0 \
  --launch-count=12 --timeout=2 --output=Build/新建序列输出目录 \
  python3 tests/simulator_sequence.py Build/SmallDot20260916/libsimulator_bridge.so \
  --cases=0,318,0,262,6,14 --report=Build/新建序列报告.json
```

完整序列需检查应用的 `SIM_SEQUENCE_PASS`、JSON passed=true，以及预期启动数和同等数量的非空 BIN。入口另允许用例408至415、440、453，用于按点4混合任务Vector、点5紧凑纯AIV、点6默认Cube的顺序检查连续切换。真实设备可运行 `python3 tests/simulator_sequence.py <库> --cases=408,440,453,440,408 --report=<报告> --real-npu`。应用成功不替代DeviceProf预热重放成功；失败即保存已执行段和未通过状态。详见 [测试记录](../score/BatchMatmulMaxSum.md)。


## 2026-10-01 列块加宽回归

`benchmark.py` 默认且正式性能测试统一采用20次预热＋50次采样；预热前另有一次正确性校验，`summarize_profile.py` 按启动序列排除它与预热。只以 msprof 的 Task Duration 计时，不使用 Python 墙钟。普通计时、PMU和软件模型分开采集。

`simulator_matrix.py` 补齐472–495的点13至15规模，并追加以下边界，每项覆盖两种类型与四种布局，原有编号不变。

| 编号 | B,M,N,K | 输入 |
| --- | --- | --- |
| 496–503 | 1,1025,513,40 | 随机，M/N双尾块 |
| 504–511 | 1,1025,513,40 | 全负相似度 |
| 512–519 | 1,1025,513,40 | 全零 |
| 520–527 | 1,63,513,40 | 矮宽尾块 |
| 528–535 | 1,63,767,40 | 256列块中最后一段只有63个有效float |

这些是自主补充用例，不能称为OJ输入。计算图检查可用既有 `--capture --real-npu`；少量软件模型调用用于指令诊断，不作为20＋50的真实NPU性能测量。

## 部分仿真与真机中间结果诊断

完整大矩阵模型耗时过长时，可以用较小K且命中相同分发路径的自主场景定位流水。例如编号328为`(1,1024,512,32)`，832和834为`(1,1281,2049,40)`的FP16/NN和TN。必须记录实际规模、代码hash、库hash和BIN，不能将部分场景通过写成完整测试点通过。真实正确性和正式性能仍上板验证，正式计时始终20轮预热＋50轮采样。

`diagnostic_alloc_dump.cpp`仅用于错误定位。它用`LD_PRELOAD`拦截算子工作区的分配/释放，在释放前回读不超过8MiB的缓冲，不修改设备内容。回读会改变执行时序，因此不能加载此库测性能。原始转储是内部数据，需与相同版本、相同输入、分块规则一起解释；未转储的较早GM槽不能被视为正确。

在远端NPU环境加载CANN后执行：

```bash
g++ -shared -fPIC tests/diagnostic_alloc_dump.cpp -ldl -pthread \
  -o Build/diagnostic_alloc_dump.so
mkdir -p Build/诊断输出
BMM_DUMP_DIR=Build/诊断输出 \
LD_PRELOAD="$PWD/Build/diagnostic_alloc_dump.so" \
python3 tests/simulator_matrix.py Build/npu/libsimulator_bridge.so \
  --case=834 --real-npu --report=Build/诊断输出/app.json
```

`allocation-序号-字节数.bin`包含该工作区释放前的字节。系统通信区超过8MiB，默认不保存。普通调用在算子内同步后回读；计算图场景仅在图销毁释放工作区时回读，不能据此区分每次重放的中间值。

## 2026-10-13 通用分派与容量域回归

`tiling_domains.py` 以容量、对齐、任务覆盖和尾块为维度构造48个场景，每场景按FP16/BF16 × NN/NT/TN/TT展开，共384组可选用例。它复用独立FP64参考、双调用一致性、输入不变和输出保护区检查；`--capture`补充计算图捕获及两次重放。全部384组是可选测试空间，实际执行子集以证据中的summary.json为准。

```bash
python3 tests/tiling_domains.py /绝对路径/libcandidate.so \
  --case=215 --report=/新目录/尾块.json --real-npu
python3 tests/tiling_domains.py /绝对路径/libcandidate.so \
  --case=360 --report=/新目录/单点积重放.json --capture --real-npu
```

分派设计、已执行的正确性测试、远端编译时间和同输入性能比较见[整改记录](../score/通用分派整改-20261013.md)。历史失败也保留在证据目录，不以邻域测试代替官方隐藏数据或官方OJ编译验证。

## 2026-10-13 紧凑Cast/Gather索引优化回归

`packed_cast_domain.py` 在同一ACL上下文中覆盖BF16/TN、B=1、M×N≤16、32≤K≤64且K为8倍数的全部250种合法形状，并追加11组全负、全零、域外回退、其他核切换和尾列最大值检查。每个形状使用独立FP64参考，检查重复调用、输入不变和输出保护区。形状穷举不等于输入数值穷举。

```bash
python3 tests/packed_cast_domain.py /绝对路径/libcandidate.so \
  --real-npu --report=/新目录/domain.json
python3 tests/packed_cast_domain.py /绝对路径/libcandidate.so \
  --capture --real-npu --report=/新目录/capture.json
```

`--capture` 对每组先普通调用，再捕获并执行两次重放。`--cases=46` 可单独复现M=1、N=10、K=40的尾段Max检查。N>8时每次FP32 repeat只覆盖前8个稀疏点积，后半段必须另做Max后合并。

## 2026-10-13 TT驻留核L0C双缓冲回归

`resident_tt_l0c_domains.py` 覆盖64组定向场景，包括64列分块成对通知、单个尾块、最多8个通知事件、M/K尾块、容量回退、全负/全零及布局切换。使用独立FP64参考，检查输入不变、输出保护区与重复结果一致性。`--capture`先普通调用，再捕获并重放两次。

```bash
python3 tests/resident_tt_l0c_domains.py /绝对路径/libcandidate.so --real-npu --report=/新目录/domain.json
python3 tests/resident_tt_l0c_domains.py /绝对路径/libcandidate.so --capture --real-npu --report=/新目录/capture.json
```

## 2026-10-13 小批量静态UB与显式同步回归

`static_ub_domains.py` 穷举BF16/TT、B=2…4、M/N=1…16、K=64或128的1536种形状，追加4组特殊输入及12组其他路径与目标核交替调用，共1552组。检查独立FP64参考、输入不变、输出保护区和重复结果一致性。`--capture`对每组先普通调用，再捕获并重放两次；形状穷举不代表输入数值穷举。

```bash
python3 tests/static_ub_domains.py /绝对路径/libcandidate.so --capture --real-npu --report=/新目录/static-ub.json
```

本轮分两批验证：编号0—1539覆盖容量域及特殊输入，1540—1551覆盖同上下文路径切换。实验候选、远端编译及真机性能证据见`score/evidence/point4-control-20261013/`。
