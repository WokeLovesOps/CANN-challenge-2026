# NPU 正确性测试

测试入口独立于赛题模板，不修改 `src/main.asc`、`src/CMakeLists.txt` 或 `src/scripts/`。实际调用的是 `src/kernel.asc` 中的 `run_kernel`。

## 编译与运行

先加载当前主机的 CANN 环境，再在仓库根目录执行：

```bash
cmake -S tests -B Build/Correctness -DNPU_ARCH=dav-2201
cmake --build Build/Correctness -j4
OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 python3 tests/correctness.py \
    Build/Correctness/correctness --report Build/correctness.json
```

本地 CANN 9.0 环境脚本为 `/mnt/newdisk/Ascend/cann-9.0.0/set_env.sh`；本次远端测试使用 `/home/developer/Ascend/cann-8.5.2/set_env.sh`，设备为 Ascend 910B3。两者的验证结果必须区分。

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
source /mnt/newdisk/Ascend/cann-9.0.0/set_env.sh
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

本轮只执行 16 个定向小用例：`0,8,9,10,12,15,56,63,64,79,87,88,96,104,112,120`，没有运行完整矩阵。每个用例仍执行两次正式核函数，并核验输出、输入、保护区、重复一致性、启动数和采集文件。完整仿真矩阵现为 128 组；正文中的 72 组指原始正确性矩阵。

## 计算图捕获检查

`simulator_matrix.py --capture` 执行一次普通调用，再捕获一次并重放两次，逐次检查输出、保护区和逐字节重复一致性。工作区必须存活到图销毁；仅能结束捕获不算功能通过。

本地 CANN 9.0 模型流程尚未通过图重放对照检查：独立常数写入核也未在重放后更新输出。真实 NPU 验证需在得到授权后，在目标机器本地构建共享库，再执行以下命令，不能把 x86_64 库复制给 aarch64 Host 使用：

```bash
OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1 \
python3 tests/simulator_matrix.py Build/SimulatorValidation/libsimulator_bridge.so \
    --case=0 --capture --real-npu --report=Build/capture-npu-case0.json
```

第 26 号场景可用 `--case=26` 复现大 K 转置输入保护检查；不加 `--capture` 时执行普通连续两次调用。若输入被修改，JSON 记录首批差异字节，报告旁保存对应输入的 `.before.bin` 和 `.after.bin`。
