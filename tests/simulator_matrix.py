"""通过 msprof op simulator 执行 72 组双调用检查；结果不是板上性能。"""
import argparse
import ctypes as c
import itertools
import json
import os
from pathlib import Path

os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
os.environ.setdefault("OMP_NUM_THREADS", "2")
import numpy as np
from ml_dtypes import bfloat16

from correctness import golden
from simulator import TensorInfo, TensorGroupInfo


SHAPES = [
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("library", type=Path)
    parser.add_argument("--case", type=int, required=True, choices=range(72))
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if os.environ.get("IS_SIMULATOR_ENV", "").lower() != "true":
        raise RuntimeError("本入口必须由 msprof op simulator 启动")

    cases = list(itertools.product(SHAPES, (1, 2), (False, True), (False, True)))
    (label, batch, m, n, k), dtype_id, trans_a, trans_b = cases[args.case]
    dtype = np.float16 if dtype_id == 1 else bfloat16
    rng = np.random.default_rng(20260915 + args.case)
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
    record = dict(case=args.case, label=label, shape=[batch, m, n, k],
                  dtype=str(dtype), transpose=[trans_a, trans_b], passed=False)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")

    runtime = c.CDLL("libascendcl.so", mode=c.RTLD_GLOBAL)
    ptr = c.c_void_p

    def bind(name, types):
        function = getattr(runtime, name)
        function.argtypes = types
        function.restype = c.c_int
        return function

    def check(function, *values):
        result = function(*values)
        if result:
            raise RuntimeError(f"{function.__name__}: {result}")

    check(bind("aclInit", [c.c_char_p]), None)
    check(bind("aclrtSetDevice", [c.c_int]), 0)
    library = c.CDLL(str(args.library.resolve()), mode=c.RTLD_GLOBAL)
    run = library.run_kernel
    group_ptr = c.POINTER(TensorGroupInfo)
    run.argtypes = [ptr, group_ptr, ptr, group_ptr, ptr, group_ptr,
                   c.c_int64, ptr, c.c_bool, c.c_bool]
    run.restype = None
    stream = ptr()
    check(bind("aclrtCreateStream", [c.POINTER(ptr)]), c.byref(stream))
    # 与硬件测试入口一致，使用模型报告的 Cube 核数，不把多核场景缩成单核。
    cores = c.c_int64()
    # CANN 9.0 acl_rt.h 中 ACL_DEV_ATTR_CUBE_CORE_NUM 的公开枚举值为 102。
    check(bind("aclrtGetDeviceInfo", [c.c_uint32, c.c_int, c.POINTER(c.c_int64)]),
          0, 102, c.byref(cores))
    if cores.value <= 0:
        raise RuntimeError("模型未报告有效 Cube 核数")
    record["available_cores"] = cores.value
    malloc = bind("aclrtMalloc", [c.POINTER(ptr), c.c_size_t, c.c_int])
    memcpy = bind("aclrtMemcpy", [ptr, c.c_size_t, ptr, c.c_size_t, c.c_int])
    free = bind("aclrtFree", [ptr])
    originals = [stored_a.tobytes(), stored_b.tobytes()]
    guard = b"\xa5" * (batch * 4 + 128)
    buffers = originals + [guard]
    addresses = []
    try:
        for raw in buffers:
            address = ptr()
            check(malloc, c.byref(address), len(raw), 0)
            addresses.append(address)
            check(memcpy, address, len(raw), c.c_char_p(raw), len(raw), 1)
        shapes = [(c.c_int64 * len(shape))(*shape)
                  for shape in (stored_a.shape, stored_b.shape, (batch,))]
        infos = [TensorInfo(shape, len(shape), dtype_id if i < 2 else 0)
                 for i, shape in enumerate(shapes)]
        groups = [TensorGroupInfo(c.pointer(info), 1) for info in infos]
        previous = None
        for repeat in range(2):
            check(memcpy, addresses[2], len(guard), c.c_char_p(guard), len(guard), 1)
            print(f"CASE_{args.case}_CALL_{repeat + 1}_BEGIN", flush=True)
            run(addresses[0], c.byref(groups[0]), addresses[1], c.byref(groups[1]),
                ptr(addresses[2].value + 64), c.byref(groups[2]), cores.value,
                stream, trans_a, trans_b)
            check(bind("aclrtSynchronizeStream", [ptr]), stream)
            output = c.create_string_buffer(len(guard))
            check(memcpy, output, len(guard), addresses[2], len(guard), 2)
            raw = output.raw
            if raw[:64] != guard[:64] or raw[-64:] != guard[-64:]:
                raise AssertionError("输出保护区被覆盖")
            actual = np.frombuffer(raw[64:-64], dtype=np.float32)
            if not np.isfinite(actual).all() or not np.allclose(actual, expected, rtol=1e-4, atol=1e-4):
                raise AssertionError(f"精度失败: actual={actual}, expected={expected}")
            if previous is not None and raw != previous:
                raise AssertionError("重复调用结果不一致")
            previous = raw
            record["max_abs_error"] = float(np.max(np.abs(actual - expected)))
            print(f"CASE_{args.case}_CALL_{repeat + 1}_PASS", flush=True)
        for address, original in zip(addresses, originals):
            output = c.create_string_buffer(len(original))
            check(memcpy, output, len(original), address, len(original), 2)
            if output.raw != original:
                raise AssertionError("输入被修改")
        record["passed"] = True
        print("SIM_CORRECTNESS_PASS", flush=True)
    except Exception as error:
        record["error"] = str(error)
        raise
    finally:
        args.report.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
        for address in addresses:
            check(free, address)
        check(bind("aclrtDestroyStream", [ptr]), stream)
        check(bind("aclrtResetDevice", [c.c_int]), 0)
        check(bind("aclFinalize", []))


if __name__ == "__main__":
    main()
