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

输出目录必须尚不存在，以免覆盖已有证据。运行器顺序执行全部 72 组，默认每组模型运行上限为 10 分钟，可用 `--timeout-minutes` 调整；`--cases=0,8` 可指定需要复现的场景。仿真应用复用上述量化输入、随机种子、FP64 golden 和误差判定，并使用模型报告的 Cube 核数。`--core-id=0` 仅限制解析核，不限制核函数只执行一个核。

每组必须同时满足应用打印 `SIM_CORRECTNESS_PASS`、没有超时、工具正常退出，以及两次 Compute 和两次 Finish 对应的四份非空 `visualize_data.bin`。`summary.json` 保存库哈希、Git 版本、命令、逐组结果和 BIN 哈希。源码行映射由 `-g` 提供，正常编译优化保持启用。

软件模型时间只用于定位指令与同步行为，不等于真实 NPU 的 Task Duration，也不用于计算比赛得分。`simulator_matrix.py` 会拒绝脱离模型环境直接运行；普通 NPU 测试命令仍属于上板验证流程。
