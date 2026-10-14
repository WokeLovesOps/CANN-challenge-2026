"""独立 NPU 正确性测试：实际存储值 FP64 golden，不替代官方 15 点测评。"""
import argparse
import itertools
import json
import os
from pathlib import Path
import subprocess
import tempfile

# 限制 CPU golden 的线程数，避免在共享主机上占满所有 CPU。
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
os.environ.setdefault("OMP_NUM_THREADS", "2")
import numpy as np
from ml_dtypes import bfloat16


def golden(a, b):
    output = np.zeros(a.shape[0], dtype=np.float64)
    for batch in range(a.shape[0]):
        right = b[batch].astype(np.float64)
        for row in range(0, a.shape[1], 32):
            scores = a[batch, row:row + 32].astype(np.float64) @ right
            output[batch] += scores.max(axis=-1).sum(dtype=np.float64)
    return output.astype(np.float32)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    executable = args.executable.resolve()
    shapes = [
        ("最小", 1, 1, 1, 32),
        ("双维尾块", 2, 33, 129, 40),
        ("多行多列块", 3, 65, 257, 128),
        ("最大K", 1, 33, 129, 8192),
        ("最大M", 1, 8192, 3, 32),
        ("最大N", 1, 3, 8192, 32),
        ("最大Batch", 64, 1, 1, 32),
        ("全负", 2, 33, 129, 40),
        ("全零", 2, 33, 129, 40),
    ]
    records = []
    for index, ((label, batch, m, n, k), dtype_id, trans_a, trans_b) in enumerate(
        itertools.product(shapes, (1, 2), (False, True), (False, True))
    ):
        dtype = np.float16 if dtype_id == 1 else bfloat16
        rng = np.random.default_rng(20260915 + index)
        a = rng.uniform(-1, 1, (batch, m, k)).astype(dtype)
        b = rng.uniform(-1, 1, (batch, k, n)).astype(dtype)
        if label == "全负":
            a = np.abs(a).astype(dtype)
            b = -np.abs(b).astype(dtype)
        elif label == "全零":
            a.fill(0)
        expected = golden(a, b)
        stored_a = np.ascontiguousarray(a.swapaxes(-1, -2) if trans_a else a)
        stored_b = np.ascontiguousarray(b.swapaxes(-1, -2) if trans_b else b)
        record = dict(case=index, label=label, shape=[batch, m, n, k],
                      dtype="float16" if dtype_id == 1 else "bfloat16",
                      transpose=[trans_a, trans_b])
        with tempfile.TemporaryDirectory(prefix="bmm-correctness-") as directory:
            folder = Path(directory)
            stored_a.tofile(folder / "x1.bin")
            stored_b.tofile(folder / "x2.bin")
            command = [str(executable), *map(str, [batch, m, n, k, dtype_id, int(trans_a), int(trans_b)])]
            try:
                result = subprocess.run(command, cwd=folder, capture_output=True, text=True, timeout=120)
                record["returncode"] = result.returncode
                record["log"] = result.stdout + result.stderr
                if result.returncode != 0:
                    record["passed"] = False
                else:
                    actual = np.fromfile(folder / "y.bin", dtype=np.float32)
                    valid = actual.shape == expected.shape and np.isfinite(actual).all()
                    record["passed"] = bool(valid and np.allclose(actual, expected, rtol=1e-4, atol=1e-4))
                    if valid:
                        record["max_abs_error"] = float(np.max(np.abs(actual - expected)))
                        record["max_rel_error"] = float(np.max(np.abs(actual - expected) / np.maximum(np.abs(expected), 1e-30)))
                    if not record["passed"]:
                        record["actual"] = actual.tolist()
                        record["expected"] = expected.tolist()
            except subprocess.TimeoutExpired:
                record.update(passed=False, log="超过 120 秒")
        records.append(record)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps(record, ensure_ascii=False), flush=True)
        if not record["passed"]:
            raise SystemExit(1)
    print(f"全部 {len(records)} 组通过；每组重复两次，检查输入不变及输出保护区。", flush=True)


if __name__ == "__main__":
    main()
