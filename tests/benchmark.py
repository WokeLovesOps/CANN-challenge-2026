"""运行真实算子的正确性与采样序列；核时间由外部 msprof 采集，不使用 Python 墙钟。"""
import argparse
import ctypes as c
import hashlib
import json
import os
from pathlib import Path

os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
os.environ.setdefault("OMP_NUM_THREADS", "2")
import numpy as np
from ml_dtypes import bfloat16

from correctness import golden
from simulator import TensorInfo, TensorGroupInfo


# 复用仓库已有形状记录作为自主构造的对照输入，不宣称复现官方隐藏数据。
SHAPES = [
    (1, 1, 1, 32), (1, 3, 5, 40), (2, 7, 13, 48),
    (4, 16, 16, 128), (8, 16, 32, 128), (13, 23, 73, 192),
    (16, 32, 128, 256), (1, 1025, 1031, 1032), (1, 2048, 1536, 1280),
    (1, 4096, 1280, 1152), (1, 1536, 2048, 2048), (1, 1280, 4096, 1536),
    (1, 8192, 64, 128), (1, 64, 8192, 128), (1, 64, 64, 8192),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("library", type=Path)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--cases", default="1,2,3,4,5,6,7,8,9,10,11,12,13,14,15")
    parser.add_argument("--dtype", choices=("fp16", "bf16"), default="fp16")
    parser.add_argument("--layout", choices=("NN", "NT", "TN", "TT"), default="NN")
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--repeat", type=int, default=50)
    parser.add_argument("--real-npu", action="store_true")
    args = parser.parse_args()
    simulated = os.environ.get("IS_SIMULATOR_ENV", "").lower() == "true"
    if simulated == args.real_npu:
        parser.error("必须选择 msprof 软件模型或显式 --real-npu，不能混用")
    if args.warmup < 0 or args.repeat < 2:
        parser.error("预热次数非负，正式采样至少两次")
    indices = [int(value) for value in args.cases.split(",")]
    if not indices or any(index < 1 or index > len(SHAPES) for index in indices):
        parser.error("用例编号必须为 1 至 15")
    if args.report.exists():
        parser.error("报告已存在，拒绝覆盖")
    args.report.parent.mkdir(parents=True, exist_ok=True)
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

    report = dict(commit=args.commit, execution="simulator" if simulated else "real_npu",
                  library=str(args.library.resolve()),
                  library_sha256=hashlib.sha256(args.library.read_bytes()).hexdigest(),
                  dtype=args.dtype, layout=args.layout, warmup=args.warmup,
                  repeat=args.repeat, passed=False, results=[], launches=[])

    def save():
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")

    save()
    check(bind("aclInit", [c.c_char_p]), None)
    check(bind("aclrtSetDevice", [c.c_int]), 0)
    soc_name = runtime.aclrtGetSocName
    soc_name.restype = c.c_char_p
    report["soc"] = soc_name().decode()
    cores = c.c_int64()
    check(bind("aclrtGetDeviceInfo", [c.c_uint32, c.c_int, c.POINTER(c.c_int64)]),
          0, 102, c.byref(cores))
    report["cube_cores"] = cores.value
    library = c.CDLL(str(args.library.resolve()), mode=c.RTLD_LOCAL)
    run = library.run_kernel
    group_ptr = c.POINTER(TensorGroupInfo)
    run.argtypes = [ptr, group_ptr, ptr, group_ptr, ptr, group_ptr,
                   c.c_int64, ptr, c.c_bool, c.c_bool]
    run.restype = None
    stream = ptr()
    check(bind("aclrtCreateStream", [c.POINTER(ptr)]), c.byref(stream))
    malloc = bind("aclrtMalloc", [c.POINTER(ptr), c.c_size_t, c.c_int])
    copy = bind("aclrtMemcpy", [ptr, c.c_size_t, ptr, c.c_size_t, c.c_int])
    free = bind("aclrtFree", [ptr])
    sync = bind("aclrtSynchronizeStream", [ptr])
    trans_a, trans_b = [value == "T" for value in args.layout]
    dtype_id = 1 if args.dtype == "fp16" else 2
    dtype = np.float16 if dtype_id == 1 else bfloat16
    try:
        for index in indices:
            batch, m, n, k = SHAPES[index - 1]
            rng = np.random.default_rng(20260930 + index)
            a = rng.uniform(-1, 1, (batch, m, k)).astype(dtype)
            b = rng.uniform(-1, 1, (batch, k, n)).astype(dtype)
            expected = golden(a, b)
            stored = [np.ascontiguousarray(a.swapaxes(-1, -2) if trans_a else a),
                      np.ascontiguousarray(b.swapaxes(-1, -2) if trans_b else b)]
            originals = [value.tobytes() for value in stored]
            guard = b"\xa5" * (128 + batch * 4)
            record = dict(case=index, shape=[batch, m, n, k], passed=False,
                          input_sha256=[hashlib.sha256(raw).hexdigest() for raw in originals],
                          launch_begin=len(report["launches"]), seed=20260930 + index)
            report["results"].append(record)
            addresses = []
            try:
                for raw in originals + [guard]:
                    address = ptr()
                    check(malloc, c.byref(address), len(raw), 0)
                    addresses.append(address)
                    check(copy, address, len(raw), c.c_char_p(raw), len(raw), 1)
                shapes = [(c.c_int64 * len(shape))(*shape)
                          for shape in (stored[0].shape, stored[1].shape, (batch,))]
                infos = [TensorInfo(shape, len(shape), dtype_id if pos < 2 else 0)
                         for pos, shape in enumerate(shapes)]
                groups = [TensorGroupInfo(c.pointer(info), 1) for info in infos]
                previous = None

                def validate():
                    nonlocal previous
                    output = c.create_string_buffer(len(guard))
                    check(copy, output, len(guard), addresses[2], len(guard), 2)
                    raw = output.raw
                    if raw[:64] != guard[:64] or raw[-64:] != guard[-64:]:
                        raise AssertionError("输出保护区被覆盖")
                    actual = np.frombuffer(raw[64:-64], dtype=np.float32)
                    if not np.isfinite(actual).all() or not np.allclose(
                            actual, expected, rtol=1e-4, atol=1e-4):
                        raise AssertionError(f"输出精度失败: {actual}, 参考 {expected}")
                    if previous is not None and raw != previous:
                        raise AssertionError("重复执行结果不一致")
                    previous = raw
                    record["max_abs_error"] = float(np.max(np.abs(actual - expected)))

                # 首次调用单独校验；随后预热，再连续采样，避免逐次回读干扰缓存。
                phases = ["validation"] + ["warmup"] * args.warmup + ["sample"] * args.repeat
                for position, phase in enumerate(phases):
                    report["launches"].append(dict(case=index, phase=phase, position=position))
                    run(addresses[0], c.byref(groups[0]), addresses[1], c.byref(groups[1]),
                        ptr(addresses[2].value + 64), c.byref(groups[2]), cores.value,
                        stream, trans_a, trans_b)
                    check(sync, stream)
                    if phase == "validation":
                        validate()
                        # 再次填哨兵，防止后续调用未写输出仍通过校验。
                        check(copy, addresses[2], len(guard), c.c_char_p(guard), len(guard), 1)
                validate()
                for address, original in zip(addresses[:2], originals):
                    output = c.create_string_buffer(len(original))
                    check(copy, output, len(original), address, len(original), 2)
                    if output.raw != original:
                        raise AssertionError("输入被修改")
                record["passed"] = True
                record["launch_end"] = len(report["launches"])
                print(f"CASE_{index}_PASS {args.dtype} {args.layout}", flush=True)
            finally:
                save()
                for address in addresses:
                    check(free, address)
        report["passed"] = True
        print("BENCHMARK_CORRECTNESS_PASS", flush=True)
    except Exception as error:
        report["error"] = str(error)
        raise
    finally:
        save()
        check(bind("aclrtDestroyStream", [ptr]), stream)
        check(bind("aclrtResetDevice", [c.c_int]), 0)
        check(bind("aclFinalize", []))


if __name__ == "__main__":
    main()
