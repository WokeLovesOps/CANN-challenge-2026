"""对照物理行跨度与K尾块；复用正式20＋50采样流程，不修改算子分发。"""
import benchmark


# 固定M以及N方向列块数，只改变N/K的对齐状态。
# K=1040保留baseK=64的尾块，但FP16/BF16物理行宽已满足32字节对齐。
benchmark.SHAPES = [
    (1, 1025, n, k)
    for n in (1031, 1040)
    for k in (1024, 1032, 1040)
]


if __name__ == "__main__":
    benchmark.main()
