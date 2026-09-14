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
