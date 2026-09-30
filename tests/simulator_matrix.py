"""通过 msprof op simulator 执行双调用检查；结果不是板上性能。"""
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
    ("单任务小矩阵", 1, 31, 17, 40),
    ("流水槽复用", 1, 3, 257, 40),
    ("归约半行前尾", 1, 32, 63, 40),
    ("归约半行边界", 1, 32, 64, 40),
    ("归约半行后尾", 1, 32, 65, 40),
    ("归约整行前尾", 1, 32, 127, 40),
    ("多核任务槽复用", 1, 641, 65, 32),
    ("N分片四块边界", 1, 2, 385, 32),
    ("N分片五块尾行", 2, 33, 513, 40),
    ("N分片长列流水", 1, 32, 1537, 128),
    ("N分片全负", 1, 31, 1025, 40),
    ("N分片全零", 1, 31, 1025, 40),
    ("N分片核数边界", 5, 1, 385, 32),
    ("N分片核数回退", 6, 1, 385, 32),
    ("N分片列数回退", 1, 2, 384, 32),
    ("N分片单行", 1, 1, 512, 40),
    ("N自适应十三片", 1, 2, 1537, 32),
    ("N自适应二十片", 1, 2, 8192, 32),
    ("单点积搬运尾块", 1, 1, 1, 40),
    ("单点积六十四", 1, 1, 1, 64),
    ("单点积一百二十八", 1, 1, 1, 128),
    ("单点积上限前尾", 1, 1, 1, 248),
    ("单点积上限", 1, 1, 1, 256),
    ("单点积K回退", 1, 1, 1, 264),
    ("单点积全负", 1, 1, 1, 256),
    ("单点积全零", 1, 1, 1, 40),
    ("单点积正负抵消", 1, 1, 1, 256),
    ("单点积Batch回退", 2, 1, 1, 32),
    ("单点积M回退", 1, 2, 1, 32),
    ("单点积N回退", 1, 1, 2, 32),
    ("基础小矩阵假设", 1, 2, 3, 32),
    ("对齐小矩阵假设", 1, 16, 16, 32),
    ("ShapeKey大矩阵边界", 1, 1024, 512, 32),
    ("ShapeKey高窄单任务", 1, 64, 64, 32),
    ("打包点积矩阵", 1, 3, 5, 40),
    ("打包点积输出边界", 1, 4, 4, 64),
    ("打包点积超限回退", 1, 3, 6, 40),
    ("小批量向量矩阵", 2, 7, 13, 48),
    ("小批量向量M超限", 2, 9, 13, 48),
    ("小批量向量上界", 4, 8, 16, 64),
    ("小批量向量全负", 2, 7, 13, 48),
    ("小批量向量非紧凑K", 2, 7, 13, 40),
    ("中等批量向量点4", 4, 16, 16, 128),
    ("中等批量向量中间批量", 5, 16, 16, 128),
    ("中等批量向量K下界", 4, 16, 16, 80),
    ("中等批量向量全负", 4, 16, 16, 128),
    ("中等批量向量点5", 8, 16, 32, 128),
    ("中等批量向量点6", 13, 23, 73, 192),
    ("中等批量向量点7", 16, 32, 128, 256),
    ("中等批量向量行尾块", 3, 15, 16, 128),
    ("点13高窄矩阵", 1, 8192, 64, 128),
    ("点14矮宽矩阵", 1, 64, 8192, 128),
    ("点15大K矩阵", 1, 64, 64, 8192),
    ("大矩阵列块后尾", 1, 1025, 513, 40),
    ("大矩阵列块全负", 1, 1025, 513, 40),
    ("大矩阵列块全零", 1, 1025, 513, 40),
    ("矮宽列块后尾", 1, 63, 513, 40),
    ("矮宽列块段前尾", 1, 63, 767, 40),
    ("高窄128行边界", 1, 128, 64, 40),
    ("高窄128行尾块", 1, 129, 63, 40),
    ("高窄行块全负", 1, 129, 63, 40),
    ("高窄行块全零", 1, 129, 63, 40),
    ("高窄128行前界", 1, 127, 64, 40),
    ("高窄多批行尾", 3, 257, 33, 128),
    ("高窄256行边界", 1, 256, 64, 40),
    ("高窄256行尾块", 1, 257, 63, 40),
    ("高窄256行全负", 1, 257, 63, 40),
    ("高窄256行全零", 1, 257, 63, 40),
    ("高窄256行前界", 1, 255, 64, 40),
    ("高窄256行多批尾", 3, 513, 33, 128),
    ("高窄512行边界", 1, 512, 64, 40),
    ("高窄512行尾块", 1, 513, 63, 40),
    ("高窄512行全负", 1, 513, 63, 40),
    ("高窄512行全零", 1, 513, 63, 40),
    ("高窄512行前界", 1, 511, 64, 40),
    ("高窄512行多批尾", 3, 1025, 33, 128),
    ("高窄大K行尾", 1, 513, 33, 8192),
    ("高窄最大批量", 64, 512, 64, 40),
    ("高窄单列行尾", 1, 513, 1, 40),
    ("大K分片下界", 1, 63, 64, 4096),
    ("大K分片列尾", 1, 64, 127, 4104),
    ("大K分片全负", 1, 64, 127, 4104),
    ("大K分片全零", 1, 64, 127, 4104),
    ("大K分片批量边界", 5, 33, 128, 4096),
    ("大K分片批量回退", 6, 33, 128, 4096),
    ("大K分片K回退", 1, 64, 128, 4088),
    ("大K分片M回退", 1, 65, 64, 4096),
    ("大K分片N前界", 1, 64, 63, 4096),
    ("大K分片N后界", 1, 64, 129, 4096),
    ("K分片八元素尾", 1, 63, 63, 4184),
    ("K分片全负", 1, 33, 17, 4104),
    ("K分片全零", 1, 33, 17, 4104),
    ("K分片先和后Max", 1, 2, 2, 4096),
    ("K分片正负抵消", 1, 3, 5, 8192),
    ("K分片批量回退", 2, 64, 64, 8192),
    ("自适应大矩阵256行尾块", 1, 1281, 2049, 40),
    ("自适应大矩阵256行全负", 1, 1535, 2049, 40),
    ("自适应大矩阵256行全零", 1, 1535, 2049, 40),
    ("自适应大矩阵核增益回退", 1, 1537, 2049, 40),
    ("自适应大矩阵转置对齐", 1, 1536, 2049, 40),
    ("自适应大矩阵转置长K尾块", 1, 1281, 2049, 128),
    ("自适应大矩阵转置长K全负", 1, 1535, 2049, 128),
    ("大矩阵L1步长四块后尾", 1, 1281, 2049, 264),
    ("大矩阵L1步长全负", 1, 1535, 2049, 520),
    ("大矩阵L1步长全零", 1, 1537, 2049, 520),
    ("大矩阵L1步长最小模型", 1, 1024, 512, 264),
    ("大矩阵L1完整四块模型", 1, 1024, 512, 256),
    ("大矩阵L1搬运批次尾部模型", 1, 1024, 512, 384),
    ("紧凑批量合并单行块尾部", 5, 7, 15, 64),
    ("紧凑批量合并单行块边界", 5, 8, 16, 128),
    ("紧凑批量合并双轴尾部", 5, 9, 17, 64),
    ("紧凑批量合并单元素", 8, 1, 1, 128),
    ("紧凑批量合并全负", 7, 15, 31, 128),
    ("紧凑批量合并全零", 6, 9, 32, 128),
    ("紧凑批量合并短K列尾", 8, 16, 17, 64),
    ("紧凑批量合并整行双列块", 5, 8, 32, 128),
    ("大矩阵五块L1双批模型", 1, 1024, 512, 640),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("library", type=Path)
    parser.add_argument("--case", type=int, required=True, choices=range(len(SHAPES) * 8))
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--capture", action="store_true", help="先普通调用，再捕获并重放两次")
    parser.add_argument("--real-npu", action="store_true", help="明确选择真实 NPU 验证")
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
    if label in ("全负", "N分片全负", "单点积全负", "小批量向量全负",
                 "中等批量向量全负", "大矩阵列块全负", "高窄行块全负", "高窄256行全负", "高窄512行全负", "大K分片全负", "K分片全负", "自适应大矩阵256行全负", "自适应大矩阵转置长K全负", "大矩阵L1步长全负", "紧凑批量合并全负"):
        a = np.abs(a).astype(dtype)
        b = -np.abs(b).astype(dtype)
    elif label in ("全零", "N分片全零", "单点积全零", "大矩阵列块全零", "高窄行块全零", "高窄256行全零", "高窄512行全零", "大K分片全零", "K分片全零", "自适应大矩阵256行全零", "大矩阵L1步长全零", "紧凑批量合并全零"):
        a.fill(0)
    elif label == "单点积正负抵消":
        # 大小不同的正负乘积抵消，FP64 golden 应为 4；检查归约精度与全 K 覆盖。
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
    stored_a = np.ascontiguousarray(a.swapaxes(-1, -2) if trans_a else a)
    stored_b = np.ascontiguousarray(b.swapaxes(-1, -2) if trans_b else b)
    record = dict(case=args.case, label=label, shape=[batch, m, n, k],
                  dtype=str(dtype), transpose=[trans_a, trans_b], capture=args.capture,
                  execution="simulator" if simulated else "npu", passed=False)
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
        for repeat in range(3 if args.capture else 2):
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
        print("SIM_CORRECTNESS_PASS", flush=True)
    except Exception as error:
        record["error"] = str(error)
        raise
    finally:
        args.report.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
        if model.value:
            check(bind("aclmdlRIDestroy", [ptr]), model)
        for address in addresses:
            check(free, address)
        check(bind("aclrtDestroyStream", [ptr]), stream)
        check(bind("aclrtResetDevice", [c.c_int]), 0)
        check(bind("aclFinalize", []))


if __name__ == "__main__":
    main()
