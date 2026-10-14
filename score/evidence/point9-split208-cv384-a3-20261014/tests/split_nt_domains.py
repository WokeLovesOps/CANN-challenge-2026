"""验证208行384列交接NT分片的跨片Max、尾块、分派边界及图重放。"""
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
    parser.add_argument('--cases', help='可选编号子集，默认执行全部定向边界')
    parser.add_argument('--capture', action='store_true', help='普通调用后捕获并重放两次')
    parser.add_argument('--report', required=True, type=Path)
    parser.add_argument('--real-npu', action='store_true', help='明确选择真实 NPU 验证')
    args = parser.parse_args()
    simulated = os.environ.get('IS_SIMULATOR_ENV', '').lower() == 'true'
    if not simulated and not args.real_npu:
        raise RuntimeError('本入口必须由 msprof op simulator 启动；上板需显式 --real-npu')
    if simulated and args.real_npu:
        raise RuntimeError('模型环境不能记为真实 NPU 运行')
    # 检查两路N分片的边界、跨片Max、行尾和域外回退，不参与算子分派。
    cases = [((f'K边界{k}', 1, 2048, 1536, k), 1, False, True)
             for k in (32, 40, 64, 120, 128, 256, 320, 512, 1032, 1280, 1536, 2048, 8192)]
    cases += [((f'M边界{m}', 1, m, 1537, 320), 1, False, True)
              for m in (1280, 1281, 1456, 1457, 1872, 1873, 2048, 2079, 2080, 2081, 2240)]
    cases += [((f'N边界{n}', 1, 2048, n, 320), 1, False, True)
              for n in (1024, 1025, 1151, 1152, 1153, 1279, 1280, 1281, 1535, 1536, 1537, 1663, 1664, 1665, 1791, 1792, 1793, 1921, 2047, 2048, 2049)]
    cases += [((label, batch, m, n, k), dtype, ta, tb) for label, batch, m, n, k, dtype, ta, tb in (
        ('全负', 1, 2048, 1536, 1280, 1, False, True),
        ('全零', 1, 2048, 1025, 1280, 1, False, True),
        ('尾列最大', 1, 2049, 1537, 1280, 1, False, True),
        ('尾列全负', 1, 2049, 1025, 320, 1, False, True),
        ('分片两侧最大', 1, 2048, 1536, 320, 1, False, True),
        ('批量回退', 2, 1281, 1537, 320, 1, False, True),
        ('BF16切换', 1, 2048, 1537, 320, 2, False, True),
        ('NN切换', 1, 2048, 1537, 320, 1, False, False),
        ('TN切换', 1, 2048, 1537, 320, 1, True, False),
        ('TT切换', 1, 2048, 1537, 320, 1, True, True),
        ('返回分片核', 1, 2048, 1536, 1280, 1, False, True))]
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
            if label == '分片两侧最大':
                a.fill(0)
                a[0, 0, 0] = 1
                a[0, 1, 1] = 1
                b.fill(-4)
                b[0, 0, 0] = 10
                b[0, 1, 768] = 10
                b[0, 0, -1] = 13
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
        print(f'SPLIT_NT_DOMAIN_PASS count={len(indices)} capture={args.capture}', flush=True)
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
