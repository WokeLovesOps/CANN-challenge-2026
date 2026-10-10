"""通过 msprof op simulator 执行双调用检查；结果不是板上性能。"""
import argparse
import sys
sys.path.insert(0, '/mnt/newdisk/code/CANN-challenge/tests')
import ctypes as c
import itertools
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


SHAPES = [("点1随机",1,1,1,32),("点1全负",1,1,1,32),("点1全零",1,1,1,32),("单点积正负抵消",1,1,1,32),("FP16极值抵消",1,1,1,32),("FP16次正规数",1,1,1,32)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("library", type=Path)
    parser.add_argument("--case", type=int, required=True, choices=range(len(SHAPES) * 8))
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--capture", action="store_true", help="先普通调用，再捕获并重放两次")
    parser.add_argument("--real-npu", action="store_true", help="明确选择真实 NPU 验证")
    parser.add_argument("--allocation", choices=["separate", "ab", "ba", "gap"], default="separate")
    args = parser.parse_args()
    simulated = os.environ.get("IS_SIMULATOR_ENV", "").lower() == "true"
    if not simulated and not args.real_npu:
        raise RuntimeError("本入口必须由 msprof op simulator 启动；上板需显式 --real-npu")
    if simulated and args.real_npu:
        raise RuntimeError("模型环境不能记为真实 NPU 运行")

    cases = list(itertools.product(SHAPES, (1, 2), (False, True), (False, True)))
    (label, batch, m, n, k), dtype_id, trans_a, trans_b = cases[args.case]
    dtype = np.float16 if dtype_id == 1 else bfloat16
    rng = np.random.default_rng(20260915 + args.case)
    a = rng.uniform(-1, 1, (batch, m, k)).astype(dtype)
    b = rng.uniform(-1, 1, (batch, k, n)).astype(dtype)
    if label.endswith("全负"):
        a = np.abs(a).astype(dtype)
        b = -np.abs(b).astype(dtype)
    elif label.endswith("全零"):
        a.fill(0)
    elif label == "FP16极值抵消":
        a.fill(65504)
        b[0, :, 0] = np.tile([1.0, -1.0], k // 2).astype(dtype)
    elif label == "FP16次正规数":
        a.fill(np.nextafter(np.float16(0), np.float16(1)))
        b.fill(1)
    elif label == "单点积正负抵消":
        # 大小不同的正负乘积抵消，FP64 golden 应为 0.5；检查归约精度与全 K 覆盖。
        a.fill(1)
        b[0, :, 0] = np.tile([32.0, -32.0, 0.125, -0.0625], k // 4).astype(dtype)
    elif label == "K分片先和后Max":
        # 不同K分片的最优列相反；必须先完成各列点积之和，再取Max。
        a.fill(1)
        b.fill(0)
        b[0, :k // 2, 0] = 1
        b[0, :k // 2, 1] = -1
        b[0, k // 2:, 0] = -1
        b[0, k // 2:, 1] = 2
    elif label == "K分片正负抵消":
        a.fill(1)
        pattern = np.repeat(np.array([32.0, -32.0, 0.125, -0.0625]), 512)
        b[0, :, :] = np.tile(pattern, k // len(pattern))[:, None].astype(dtype)
    elif label in ("N分片四块边界", "N自适应十三片", "N自适应二十片"):
        # 两行最优列位于不同分片；最后一列也必须参与，最终得分应为 23。
        a.fill(0)
        a[0, 0, 0] = 1
        a[0, 1, 1] = 1
        b.fill(0)
        b[0, :2, :] = -4
        b[0, 0, 0] = 10
        b[0, 1, 128] = 10
        b[0, 0, -1] = 13
    expected = golden(a, b)
    if label.endswith("全负"):
        assert np.all(a >= 0) and np.all(b <= 0) and np.all(expected < 0)
    elif label.endswith("全零"):
        assert np.all(a == 0) and np.all(expected == 0)
    stored_a = np.ascontiguousarray(a.swapaxes(-1, -2) if trans_a else a)
    stored_b = np.ascontiguousarray(b.swapaxes(-1, -2) if trans_b else b)
    record = dict(case=args.case, label=label, shape=[batch, m, n, k],
                  dtype=str(dtype), transpose=[trans_a, trans_b], capture=args.capture,
                  execution="simulator" if simulated else "npu", passed=False)
    record["input_sha256"] = [hashlib.sha256(x.tobytes()).hexdigest()
                              for x in (stored_a, stored_b)]
    record["input_pattern"] = ("全负" if label.endswith("全负") else
                               "全零" if label.endswith("全零") else "随机或独立构造")
    record["expected_range"] = [float(expected.min()), float(expected.max())]
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
    model = ptr()
    try:
        allocated = []
        if args.allocation == "separate":
            for raw in buffers:
                address = ptr()
                check(malloc, c.byref(address), len(raw), 0)
                allocated.append(address)
                addresses.append(address)
                check(memcpy, address, len(raw), c.c_char_p(raw), len(raw), 1)
        else:
            combined = ptr()
            input_bytes = len(originals[0])
            gap_bytes = 32 if args.allocation == "gap" else 0
            check(malloc, c.byref(combined), 2 * input_bytes + gap_bytes, 0)
            allocated.append(combined)
            offsets = [input_bytes, 0] if args.allocation == "ba" else [0, input_bytes + gap_bytes]
            for offset, raw in zip(offsets, originals):
                address = ptr(combined.value + offset)
                addresses.append(address)
                check(memcpy, address, len(raw), c.c_char_p(raw), len(raw), 1)
            output_address = ptr()
            check(malloc, c.byref(output_address), len(guard), 0)
            allocated.append(output_address)
            addresses.append(output_address)
            check(memcpy, output_address, len(guard), c.c_char_p(guard), len(guard), 1)
        record["allocation"] = args.allocation
        record["input_addresses"] = [addresses[0].value, addresses[1].value]
        record["address_delta_bytes"] = addresses[1].value - addresses[0].value
        shapes = [(c.c_int64 * len(shape))(*shape)
                  for shape in (stored_a.shape, stored_b.shape, (batch,))]
        infos = [TensorInfo(shape, len(shape), dtype_id if i < 2 else 0)
                 for i, shape in enumerate(shapes)]
        groups = [TensorGroupInfo(c.pointer(info), 1) for info in infos]
        previous = None
        for repeat in range(3 if args.capture else 2):
            if repeat == 1:
                a = (-a).astype(dtype)
                expected = golden(a, b)
                stored_a = np.ascontiguousarray(a.swapaxes(-1, -2) if trans_a else a)
                originals[0] = stored_a.tobytes()
                check(memcpy, addresses[0], len(originals[0]), c.c_char_p(originals[0]), len(originals[0]), 1)
                record["second_input_sha256"] = hashlib.sha256(originals[0]).hexdigest()
                previous = None
            check(memcpy, addresses[2], len(guard), c.c_char_p(guard), len(guard), 1)
            print(f"CASE_{args.case}_CALL_{repeat + 1}_BEGIN", flush=True)
            if args.capture and repeat == 1:
                check(bind("aclmdlRICaptureBegin", [ptr, c.c_int]), stream, 0)
            if repeat < 2:
                run(addresses[0], c.byref(groups[0]), addresses[1], c.byref(groups[1]),
                    ptr(addresses[2].value + 64), c.byref(groups[2]), cores.value,
                    stream, trans_a, trans_b)
            if args.capture and repeat == 1:
                check(bind("aclmdlRICaptureEnd", [ptr, c.POINTER(ptr)]), stream, c.byref(model))
                print("CAPTURE_END_PASS", flush=True)
            if args.capture and repeat >= 1:
                check(bind("aclmdlRIExecuteAsync", [ptr, ptr]), model, stream)
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
        for input_index, (address, original) in enumerate(zip(addresses, originals)):
            output = c.create_string_buffer(len(original))
            check(memcpy, output, len(original), address, len(original), 2)
            if output.raw != original:
                actual_bytes = np.frombuffer(output.raw, dtype=np.uint8)
                expected_bytes = np.frombuffer(original, dtype=np.uint8)
                changed = np.flatnonzero(actual_bytes != expected_bytes)
                record["input_corruption"] = dict(
                    input=input_index + 1, changed_bytes=int(changed.size),
                    first_offsets=changed[:32].tolist(),
                    expected=expected_bytes[changed[:32]].tolist(),
                    actual=actual_bytes[changed[:32]].tolist())
                args.report.with_suffix(f".x{input_index + 1}.before.bin").write_bytes(original)
                args.report.with_suffix(f".x{input_index + 1}.after.bin").write_bytes(output.raw)
                raise AssertionError(f"输入 {input_index + 1} 被修改，共 {changed.size} 字节")
        record["passed"] = True
        record["alternating_input"] = True
        print("SIM_CORRECTNESS_PASS", flush=True)
    except Exception as error:
        record["error"] = str(error)
        raise
    finally:
        args.report.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
        if model.value:
            check(bind("aclmdlRIDestroy", [ptr]), model)
        for address in allocated:
            check(free, address)
        check(bind("aclrtDestroyStream", [ptr]), stream)
        check(bind("aclrtResetDevice", [c.c_int]), 0)
        check(bind("aclFinalize", []))


if __name__ == "__main__":
    main()
