"""同进程、同输入地址对照点5正式入口、固定工作区异步入口及图重放；仅供开发诊断。"""
import argparse
import ctypes as c
import hashlib
import json
import os
from pathlib import Path
import time

os.environ.setdefault('OPENBLAS_NUM_THREADS', '2')
os.environ.setdefault('OMP_NUM_THREADS', '2')
import numpy as np
from correctness import golden
from simulator import TensorInfo, TensorGroupInfo

MODES = ['prod-direct', 'prod-graph', 'raw-direct', 'raw-graph',
         'raw-direct-burst', 'raw-graph-burst']


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('library', type=Path)
    p.add_argument('--report', type=Path, required=True)
    p.add_argument('--modes', default=','.join(MODES))
    p.add_argument('--rounds', type=int, default=2)
    p.add_argument('--warmup', type=int, default=20)
    p.add_argument('--repeat', type=int, default=50)
    p.add_argument('--real-npu', action='store_true')
    args = p.parse_args()
    modes = args.modes.split(',')
    if not args.real_npu or os.environ.get('IS_SIMULATOR_ENV', '').lower() == 'true':
        p.error('本工具仅支持明确指定的真机诊断')
    if any(x not in MODES for x in modes) or args.rounds < 1 or args.repeat < 1 or args.warmup < 0:
        p.error('模式或次数无效')
    if args.report.exists():
        p.error('拒绝覆盖已有报告')
    args.report.parent.mkdir(parents=True, exist_ok=True)
    report = dict(passed=False, library_sha256=hashlib.sha256(args.library.read_bytes()).hexdigest(),
                  modes=modes, warmup=args.warmup, repeat=args.repeat, launches=[], blocks=[],
                  note='raw入口仅用于固定工作区和异步诊断，不是提交算子；墙钟与设备任务时间分开解释')

    def save():
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')

    rt = c.CDLL('libascendcl.so', mode=c.RTLD_GLOBAL)
    ptr = c.c_void_p

    def bind(name, types):
        f = getattr(rt, name)
        f.argtypes, f.restype = types, c.c_int
        return f

    def check(f, *a):
        status = f(*a)
        if status:
            raise RuntimeError(f'{f.__name__}: {status}')

    check(bind('aclInit', [c.c_char_p]), None)
    check(bind('aclrtSetDevice', [c.c_int]), 0)
    rt.aclrtGetSocName.restype = c.c_char_p
    report['soc'] = rt.aclrtGetSocName().decode()
    stream = ptr()
    check(bind('aclrtCreateStream', [c.POINTER(ptr)]), c.byref(stream))
    sync = bind('aclrtSynchronizeStream', [ptr])
    malloc = bind('aclrtMalloc', [c.POINTER(ptr), c.c_size_t, c.c_int])
    copy = bind('aclrtMemcpy', [ptr, c.c_size_t, ptr, c.c_size_t, c.c_int])
    free = bind('aclrtFree', [ptr])
    begin = bind('aclmdlRICaptureBegin', [ptr, c.c_int])
    end = bind('aclmdlRICaptureEnd', [ptr, c.POINTER(ptr)])
    execute = bind('aclmdlRIExecuteAsync', [ptr, ptr])
    destroy = bind('aclmdlRIDestroy', [ptr])
    cores = c.c_int64()
    check(bind('aclrtGetDeviceInfo', [c.c_uint32, c.c_int, c.POINTER(c.c_int64)]), 0, 102, c.byref(cores))
    lib = c.CDLL(str(args.library.resolve()), mode=c.RTLD_LOCAL)
    run = lib.run_kernel
    gp = c.POINTER(TensorGroupInfo)
    run.argtypes = [ptr, gp, ptr, gp, ptr, gp, c.c_int64, ptr, c.c_bool, c.c_bool]
    run.restype = None
    raw = lib.diagnostic_point5_enqueue
    raw.argtypes = [ptr, ptr, ptr, ptr, c.c_uint32, c.c_uint32, c.c_uint32, c.c_uint32, ptr]
    raw.restype = None
    batch, m, n, k = 8, 16, 32, 128
    rng = np.random.default_rng(20260935)
    a = rng.uniform(-1, 1, (batch, m, k)).astype(np.float16)
    b = rng.uniform(-1, 1, (batch, k, n)).astype(np.float16)
    expected = golden(a, b)
    originals = [a.tobytes(), b.tobytes()]
    guard = b'\xa5' * (128 + batch * 4)
    addresses, models = [], {}
    shapes = [(c.c_int64 * 3)(*a.shape), (c.c_int64 * 3)(*b.shape), (c.c_int64 * 1)(batch)]
    infos = [TensorInfo(shape, len(shape), 1 if i < 2 else 0) for i, shape in enumerate(shapes)]
    groups = [TensorGroupInfo(c.pointer(info), 1) for info in infos]
    previous = None
    try:
        for data in originals + [guard, bytes(batch * 16 * 32 * 4)]:
            address = ptr()
            check(malloc, c.byref(address), len(data), 0)
            addresses.append(address)
            check(copy, address, len(data), c.c_char_p(data), len(data), 1)
        y = ptr(addresses[2].value + 64)
        report['input_sha256'] = [hashlib.sha256(x).hexdigest() for x in originals]
        report['addresses'] = dict(a=addresses[0].value, b=addresses[1].value,
                                   y=y.value, raw_scratch=addresses[3].value)

        def direct():
            run(addresses[0], c.byref(groups[0]), addresses[1], c.byref(groups[1]),
                y, c.byref(groups[2]), cores.value, stream, False, False)

        def enqueue():
            raw(addresses[0], addresses[1], addresses[3], y, batch, m, n, k, stream)

        def validate():
            nonlocal previous
            out = c.create_string_buffer(len(guard))
            check(copy, out, len(guard), addresses[2], len(guard), 2)
            value = out.raw
            assert value[:64] == guard[:64] and value[-64:] == guard[-64:], '输出越界'
            actual = np.frombuffer(value[64:-64], dtype=np.float32)
            assert np.isfinite(actual).all() and np.allclose(actual, expected, rtol=1e-4, atol=1e-4), '输出错误'
            assert previous is None or value == previous, '跨模式输出不同'
            previous = value
            report['max_abs_error'] = float(np.max(np.abs(actual - expected)))

        for key, fn in [('prod-graph', direct), ('raw-graph', enqueue)]:
            if any(mode.startswith(key) for mode in modes):
                model = ptr()
                check(begin, stream, 0)
                fn()
                check(end, stream, c.byref(model))
                models[key] = model
        for round_id in range(args.rounds):
            # 相邻模式在同一进程共享同一输入/输出地址，每轮正序后反序。
            order = modes + list(reversed(modes)) if round_id % 2 == 0 else list(reversed(modes)) + modes
            for mode in order:
                block = dict(id=len(report['blocks']), mode=mode, round=round_id,
                             sync='phase_end' if mode.endswith('-burst') else 'each_call')
                report['blocks'].append(block)
                for phase, count in [('validation', 1), ('warmup', args.warmup), ('sample', args.repeat)]:
                    check(sync, stream)
                    check(copy, addresses[2], len(guard), c.c_char_p(guard), len(guard), 1)
                    start = time.perf_counter_ns()
                    for i in range(count):
                        if mode == 'prod-direct':
                            direct()
                        elif mode.startswith('prod-graph'):
                            check(execute, models['prod-graph'], stream)
                        elif mode.startswith('raw-graph'):
                            check(execute, models['raw-graph'], stream)
                        else:
                            enqueue()
                        if not mode.endswith('-burst'):
                            check(sync, stream)
                    check(sync, stream)
                    elapsed = (time.perf_counter_ns() - start) / 1000
                    report['launches'].extend(dict(mode=mode, block=block['id'], phase=phase) for _ in range(count))
                    if phase == 'sample':
                        block['host_wall_us_per_call'] = elapsed / count
                    validate()
                block['passed'] = True
        for address, data in zip(addresses[:2], originals):
            out = c.create_string_buffer(len(data))
            check(copy, out, len(data), address, len(data), 2)
            assert out.raw == data, '输入被改写'
        report['passed'] = True
        print('同地址跨模式检查通过', flush=True)
    except Exception as e:
        report['error'] = str(e)
        raise
    finally:
        save()
        for model in models.values():
            check(destroy, model)
        for address in addresses:
            check(free, address)
        check(bind('aclrtDestroyStream', [ptr]), stream)
        check(bind('aclrtResetDevice', [c.c_int]), 0)
        check(bind('aclFinalize', []))


if __name__ == '__main__':
    main()
