"""穷举紧凑Cast/Gather容量域的合法形状，并验证同上下文切换与计算图重放。"""
import argparse
import ctypes as c
import hashlib
import json
import os
from pathlib import Path

os.environ.setdefault('OPENBLAS_NUM_THREADS', '2')
os.environ.setdefault('OMP_NUM_THREADS', '2')
import numpy as np
from ml_dtypes import bfloat16
from correctness import golden
from simulator import TensorInfo, TensorGroupInfo


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('library', type=Path)
    parser.add_argument('--cases', help='可选编号子集，默认执行全部容量域及边界')
    parser.add_argument('--capture', action='store_true', help='普通调用后捕获并重放两次')
    parser.add_argument('--report', required=True, type=Path)
    parser.add_argument('--real-npu', action='store_true', help='明确选择真实 NPU 验证')
    args = parser.parse_args()
    simulated = os.environ.get('IS_SIMULATOR_ENV', '').lower() == 'true'
    if not simulated and not args.real_npu:
        raise RuntimeError('本入口必须由 msprof op simulator 启动；上板需显式 --real-npu')
    if simulated and args.real_npu:
        raise RuntimeError('模型环境不能记为真实 NPU 运行')
    # m*n<=16、32<=k<=64且k为8的倍数：覆盖该分支的全部合法形状。
    cases = [((f'容量域{m}x{n}x{k}', 1, m, n, k), 2, True, False)
             for m in range(1, 17) for n in range(1, 16 // m + 1)
             for k in range(32, 65, 8)]
    cases += [((label, batch, m, n, k), dtype, ta, tb) for label, batch, m, n, k, dtype, ta, tb in (
        ('全负', 1, 3, 5, 40, 2, True, False),
        ('全零', 1, 1, 16, 64, 2, True, False),
        ('K超容量回退', 1, 3, 5, 72, 2, True, False),
        ('输出超容量回退', 1, 3, 6, 40, 2, True, False),
        ('批量回退', 2, 3, 5, 40, 2, True, False),
        ('切换FP16纯Vector', 1, 1, 1, 40, 1, False, False),
        ('切换FP16Cube', 1, 3, 5, 40, 1, True, False),
        ('切换BF16Cube', 1, 3, 5, 40, 2, False, False),
        ('返回紧凑核', 1, 3, 5, 40, 2, True, False),
        ('尾列最大', 1, 1, 16, 40, 2, True, False),
        ('尾列全负', 1, 1, 9, 64, 2, True, False))]
    indices = list(map(int, args.cases.split(','))) if args.cases else list(range(len(cases)))
    if any(index < 0 or index >= len(cases) for index in indices):
        parser.error('用例编号超出范围')
    report = dict(library=str(args.library.resolve()),
                  library_sha256=hashlib.sha256(args.library.read_bytes()).hexdigest(),
                  execution='simulator' if simulated else 'real_npu',
                  cases=indices, capture=args.capture, passed=False, results=[])
    if args.report.exists():
        parser.error('报告已存在，拒绝覆盖')
    args.report.parent.mkdir(parents=True, exist_ok=True)

    def save():
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')

    save()
    runtime = c.CDLL('libascendcl.so', mode=c.RTLD_GLOBAL)
    ptr = c.c_void_p

    def bind(name, types):
        fn = getattr(runtime, name)
        fn.argtypes = types
        fn.restype = c.c_int
        return fn

    def check(fn, *values):
        result = fn(*values)
        if result:
            raise RuntimeError(f'{fn.__name__}: {result}')

    check(bind('aclInit', [c.c_char_p]), None)
    check(bind('aclrtSetDevice', [c.c_int]), 0)
    library = c.CDLL(str(args.library.resolve()), mode=c.RTLD_GLOBAL)
    run = library.run_kernel
    group = c.POINTER(TensorGroupInfo)
    run.argtypes = [ptr, group, ptr, group, ptr, group, c.c_int64, ptr, c.c_bool, c.c_bool]
    run.restype = None
    stream = ptr()
    check(bind('aclrtCreateStream', [c.POINTER(ptr)]), c.byref(stream))
    cores = c.c_int64()
    check(bind('aclrtGetDeviceInfo', [c.c_uint32, c.c_int, c.POINTER(c.c_int64)]),
          0, 102, c.byref(cores))
    assert cores.value > 0
    report['available_cores'] = cores.value
    malloc = bind('aclrtMalloc', [c.POINTER(ptr), c.c_size_t, c.c_int])
    copy = bind('aclrtMemcpy', [ptr, c.c_size_t, ptr, c.c_size_t, c.c_int])
    free = bind('aclrtFree', [ptr])
    try:
        for position, index in enumerate(indices):
            (label, batch, m, n, k), dtype_id, ta, tb = cases[index]
            dtype = np.float16 if dtype_id == 1 else bfloat16
            rng = np.random.default_rng(20260915 + index)
            a = rng.uniform(-1, 1, (batch, m, k)).astype(dtype)
            b = rng.uniform(-1, 1, (batch, k, n)).astype(dtype)
            if label == '全负':
                a = np.abs(a).astype(dtype)
                b = -np.abs(b).astype(dtype)
            elif label == '全零':
                a.fill(0)
            elif label in ('尾列最大', '尾列全负'):
                a.fill(1)
                b.fill(-2)
                b[:, :, -1] = 2 if label == '尾列最大' else -1
            expected = golden(a, b)
            stored = [np.ascontiguousarray(a.swapaxes(-1, -2) if ta else a),
                      np.ascontiguousarray(b.swapaxes(-1, -2) if tb else b)]
            guard = b'\xa5' * (128 + batch * 4)
            buffers = [x.tobytes() for x in stored] + [guard]
            addresses = []
            record = dict(position=position, case=index, shape=[batch, m, n, k],
                          dtype=str(dtype), transpose=[ta, tb], label=label, passed=False,
                          input_sha256=[hashlib.sha256(x.tobytes()).hexdigest() for x in stored])
            report['results'].append(record)
            save()
            model = ptr()
            try:
                for raw in buffers:
                    address = ptr()
                    check(malloc, c.byref(address), len(raw), 0)
                    addresses.append(address)
                    check(copy, address, len(raw), c.c_char_p(raw), len(raw), 1)
                shapes = [(c.c_int64 * len(shape))(*shape)
                          for shape in (stored[0].shape, stored[1].shape, (batch,))]
                infos = [TensorInfo(shape, len(shape), dtype_id if i < 2 else 0)
                         for i, shape in enumerate(shapes)]
                groups = [TensorGroupInfo(c.pointer(info), 1) for info in infos]
                previous = None
                for repeat in range(3 if args.capture else 2):
                    check(copy, addresses[2], len(guard), c.c_char_p(guard), len(guard), 1)
                    print(f'SEQUENCE_{position}_CASE_{index}_CALL_{repeat + 1}_BEGIN', flush=True)
                    if args.capture and repeat == 1:
                        check(bind('aclmdlRICaptureBegin', [ptr, c.c_int]), stream, 0)
                    if repeat < 2:
                        run(addresses[0], c.byref(groups[0]), addresses[1], c.byref(groups[1]),
                            ptr(addresses[2].value + 64), c.byref(groups[2]), cores.value, stream, ta, tb)
                    if args.capture and repeat == 1:
                        check(bind('aclmdlRICaptureEnd', [ptr, c.POINTER(ptr)]), stream, c.byref(model))
                    if args.capture and repeat >= 1:
                        check(bind('aclmdlRIExecuteAsync', [ptr, ptr]), model, stream)
                    check(bind('aclrtSynchronizeStream', [ptr]), stream)
                    output = c.create_string_buffer(len(guard))
                    check(copy, output, len(guard), addresses[2], len(guard), 2)
                    raw = output.raw
                    assert raw[:64] == guard[:64] and raw[-64:] == guard[-64:], '输出保护区改写'
                    actual = np.frombuffer(raw[64:-64], dtype=np.float32)
                    record['actual'] = actual.tolist()
                    record['expected'] = expected.tolist()
                    assert np.isfinite(actual).all() and np.allclose(actual, expected, rtol=1e-4, atol=1e-4), f'精度失败: actual={actual}, expected={expected}'
                    assert previous is None or previous == raw, '两次输出不一致'
                    previous = raw
                    record['max_abs_error'] = float(np.max(np.abs(actual - expected)))
                for address, original in zip(addresses[:2], buffers[:2]):
                    output = c.create_string_buffer(len(original))
                    check(copy, output, len(original), address, len(original), 2)
                    assert output.raw == original, '输入被改写'
                record['passed'] = True
                print(f'SEQUENCE_{position}_CASE_{index}_PASS', flush=True)
            finally:
                save()
                if model.value:
                    check(bind('aclmdlRIDestroy', [ptr]), model)
                for address in addresses:
                    check(free, address)
        report['passed'] = True
        print(f'CAPACITY_DOMAIN_PASS count={len(indices)} capture={args.capture}', flush=True)
    except Exception as error:
        report['error'] = str(error)
        raise
    finally:
        save()
        check(bind('aclrtDestroyStream', [ptr]), stream)
        check(bind('aclrtResetDevice', [c.c_int]), 0)
        check(bind('aclFinalize', []))


if __name__ == '__main__':
    main()
