# BatchMatmulMaxSum 测试记录

| 代码版本 | CANN / 芯片 | 模板单次最小用例 | 连续两次最小用例 | 补充 72 组 | 官方 15 点用时 / 总分 |
| --- | --- | --- | --- | --- | --- |
| 平台最优 | 未取得数据 | — | — | — | 未取得数据 |
| `57ee039` | 8.5.2 / 910B3 | 通过，最大绝对误差 2.384185791015625e-7 | 失败：第二次调用阻塞，20 秒超时 | 连续调用检查失败后未启动 | 未测 |
| `fa8b7f4` | 8.5.2 / 910B3 | 通过，最大绝对误差 2.384185791015625e-7 | 失败：第二次调用阻塞 | 第 1 组超时，0 组完整通过，后 71 组未运行 | 未测 |
| `a76cd2d` | 8.5.2 / 910B3 | 失败：同步返回 507015，Cube 非法内存访问 | 未运行 | 未运行 | 未测 |
| `bdedc5e` | 8.5.2 / 910B3 | 失败：运行 120 秒超时 | 未运行 | 未运行 | 未测 |
| `6111cfa`，完整工程提交 `786ddbf` | 8.5.2 / 910B3 | 失败：Matmul tiling failed | 未运行 | 未运行 | 未测 |

## 当前结论

2026-09-15，项目已通过 GitHub 推送，再在 NPU 主机全新 clone 到 `/home/developer/CANN-challenge`。当前算子代码版本为 `57ee039`，**尚未通过完整正确性测试，不能作为已通过精度的基线**。

本地 CANN 9.0、目标架构 `dav-2201` 的编译和链接通过。经用户明确允许，实际硬件测试使用远端 CANN 8.5.2、Ascend 910B3；本记录不代表 CANN 9.0 硬件运行验证。`src/` 内只修改了 `kernel.asc`，其他 7 个模板文件的 SHA-256 校验与用户提供时一致。

## 最小用例与重复执行

模板用例的逻辑 shape 为 `B=1, M=1, N=1, K=32`，FP16，两个转置属性均为 false。原模板 `verify_result.py 0` 校验通过，最大绝对误差为 `2.384185791015625e-7`。

独立测试入口对相同输入连续调用两次，输出前后各放置 64 字节保护区。`57ee039` 的复现日志显示：

```text
输入传输完成
第 1 次算子调用开始
第 1 次算子调用完成
第 2 次算子调用开始
```

20 秒超时后进程退出码为 124，未出现第二次调用完成。第二次调用的输出、重复执行逐字节一致性及最终输入不变检查均未完成，不能记为通过。原始记录见 [重复调用日志](evidence/57ee039-repeat.txt)。

`fa8b7f4` 的 GDB 复现记录确认两次进入 `run_kernel`，第二次阻塞于 `aclrtSynchronizeStream`。独立 72 组测试在第 1 组的 120 秒限制处失败并停止，原始记录见 [测试 JSON](evidence/fa8b7f4-correctness.json)。

## 修正与尚未解决的问题

- `bdedc5e`：使用固定计算块配合 `SetTail`，修正最小 shape 被 Tiling API 拒绝的问题。
- `a76cd2d`：尝试直接读取系统工作区，实际触发 `507015`，不是可用版本。
- `fa8b7f4`：显式分配工作区，并用 `__kfc_workspace__` 标注核函数参数，单次最小用例通过。
- `57ee039`：每次调用前清零 KFC 工作区，但第二次调用仍然阻塞。此前“残留通信状态”的假设未被这一修正证实，根因仍需进一步定位。

没有换用其他计算算法来绕开失败，也没有测量或填写性能分数。72 组自主测试的覆盖说明和运行命令见 [测试说明](../tests/README.md)，它们不是官方未公开的 15 个测试点。

## 复现命令

在远端仓库根目录执行：

```bash
source /home/developer/Ascend/cann-8.5.2/set_env.sh
cmake -S tests -B Build/Correctness -DNPU_ARCH=dav-2201
cmake --build Build/Correctness -j4
OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 python3 tests/correctness.py \
    Build/Correctness/correctness --report Build/correctness.json
```

测试在首个失败处停止。要复现单独的连续调用，将模板生成的 `x1.bin`、`x2.bin` 放到工作目录，再运行 `timeout -k 5 20 /home/developer/CANN-challenge/Build/Correctness/correctness 1 1 1 32 1 0 0`。
