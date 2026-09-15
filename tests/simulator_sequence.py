"""在同一 ACL 上下文和共享库内切换核函数；仅供本地软件模型诊断。"""
import argparse
import ctypes as c
import hashlib
import itertools
import json
import os
from pathlib import Path

os.environ.setdefault('OPENBLAS_NUM_THREADS', '2')
os.environ.setdefault('OMP_NUM_THREADS', '2')
import numpy as np
from ml_dtypes import bfloat16
from correctness import golden
from simulator import TensorInfo, TensorGroupInfo
from simulator_matrix import SHAPES


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('library', type=Path)
    parser.add_argument('--cases', required=True, help='按顺序执行，允许重复编号')
    parser.add_argument('--report', required=True, type=Path)
    args = parser.parse_args()
    if os.environ.get('IS_SIMULATOR_ENV', '').lower() != 'true':
        raise RuntimeError('必须由 msprof op simulator 启动')
    indices = list(map(int, args.cases.split(',')))
    # 仅接收本次排查使用的随机输入场景，避免遗漏原矩阵的特殊数值生成器。
    if any(index not in (0, 6, 8, 14, 262, 318) for index in indices):
        raise ValueError('本入口仅支持 0、6、8、14、262、318')
    report = dict(library=str(args.library.resolve()),
                  library_sha256=hashlib.sha256(args.library.read_bytes()).hexdigest(),
                  execution='simulator', cases=indices, passed=False, results=[])
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
    cases = list(itertools.product(SHAPES, (1, 2), (False, True), (False, True)))
    try:
        for position, index in enumerate(indices):
            (label, batch, m, n, k), dtype_id, ta, tb = cases[index]
            dtype = np.float16 if dtype_id == 1 else bfloat16
            rng = np.random.default_rng(20260915 + index)
            a = rng.uniform(-1, 1, (batch, m, k)).astype(dtype)
            b = rng.uniform(-1, 1, (batch, k, n)).astype(dtype)
            expected = golden(a, b)
            stored = [np.ascontiguousarray(a.swapaxes(-1, -2) if ta else a),
                      np.ascontiguousarray(b.swapaxes(-1, -2) if tb else b)]
            guard = b'\xa5' * (128 + batch * 4)
            buffers = [x.tobytes() for x in stored] + [guard]
            addresses = []
            record = dict(position=position, case=index, shape=[batch, m, n, k],
                          dtype=str(dtype), transpose=[ta, tb], passed=False)
            report['results'].append(record)
            save()
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
                for repeat in range(2):
                    check(copy, addresses[2], len(guard), c.c_char_p(guard), len(guard), 1)
                    print(f'SEQUENCE_{position}_CASE_{index}_CALL_{repeat + 1}_BEGIN', flush=True)
                    run(addresses[0], c.byref(groups[0]), addresses[1], c.byref(groups[1]),
                        ptr(addresses[2].value + 64), c.byref(groups[2]), cores.value, stream, ta, tb)
                    check(bind('aclrtSynchronizeStream', [ptr]), stream)
                    output = c.create_string_buffer(len(guard))
                    check(copy, output, len(guard), addresses[2], len(guard), 2)
                    raw = output.raw
                    assert raw[:64] == guard[:64] and raw[-64:] == guard[-64:], '输出保护区改写'
                    actual = np.frombuffer(raw[64:-64], dtype=np.float32)
                    assert np.isfinite(actual).all() and np.allclose(actual, expected, rtol=1e-4, atol=1e-4), '精度失败'
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
                for address in addresses:
                    check(free, address)
        report['passed'] = True
        print('SIM_SEQUENCE_PASS', flush=True)
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
