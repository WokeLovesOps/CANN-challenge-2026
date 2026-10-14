"""先初始化仿真 ACL，再动态加载直接调用算子；复用正式 kernel.asc。"""
import argparse
import ctypes as c
from pathlib import Path
import struct


class TensorInfo(c.Structure):
    _fields_ = [("shape", c.POINTER(c.c_int64)), ("numDims", c.c_int64), ("dtype", c.c_int32)]


class TensorGroupInfo(c.Structure):
    _fields_ = [("tensors", c.POINTER(TensorInfo)), ("numTensors", c.c_int64)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("library", type=Path)
    parser.add_argument("--repeat", type=int, default=2)
    args = parser.parse_args()
    runtime = c.CDLL("libascendcl.so", mode=c.RTLD_GLOBAL)

    def bind(name, types):
        fn = getattr(runtime, name)
        fn.argtypes = types
        fn.restype = c.c_int
        return fn

    def check(fn, *values):
        code = fn(*values)
        if code:
            raise RuntimeError(f"{fn.__name__}: {code}")

    ptr = c.c_void_p
    init = bind("aclInit", [c.c_char_p])
    device = bind("aclrtSetDevice", [c.c_int])
    create = bind("aclrtCreateStream", [c.POINTER(ptr)])
    malloc = bind("aclrtMalloc", [c.POINTER(ptr), c.c_size_t, c.c_int])
    memcpy = bind("aclrtMemcpy", [ptr, c.c_size_t, ptr, c.c_size_t, c.c_int])
    sync = bind("aclrtSynchronizeStream", [ptr])
    free = bind("aclrtFree", [ptr])
    check(init, None)
    check(device, 0)
    print("SIM_DEVICE_READY", flush=True)
    library = c.CDLL(str(args.library.resolve()), mode=c.RTLD_GLOBAL)
    run = library.run_kernel
    run.argtypes = [ptr, c.POINTER(TensorGroupInfo), ptr, c.POINTER(TensorGroupInfo),
                    ptr, c.POINTER(TensorGroupInfo), c.c_int64, ptr, c.c_bool, c.c_bool]
    run.restype = None
    shape_a = (c.c_int64 * 3)(1, 1, 32)
    shape_b = (c.c_int64 * 3)(1, 32, 1)
    shape_y = (c.c_int64 * 1)(1)
    infos = [TensorInfo(shape_a, 3, 1), TensorInfo(shape_b, 3, 1), TensorInfo(shape_y, 1, 0)]
    groups = [TensorGroupInfo(c.pointer(info), 1) for info in infos]
    a = Path("x1.bin").read_bytes()
    b = Path("x2.bin").read_bytes()
    assert len(a) == len(b) == 64
    expected = sum(x * y for x, y in zip(struct.unpack("32e", a), struct.unpack("32e", b)))
    stream = ptr()
    check(create, c.byref(stream))
    addresses = [ptr(), ptr(), ptr()]
    for address, size in zip(addresses, (64, 64, 132)):
        check(malloc, c.byref(address), size, 0)
    try:
        check(memcpy, addresses[0], 64, c.c_char_p(a), 64, 1)
        check(memcpy, addresses[1], 64, c.c_char_p(b), 64, 1)
        previous = None
        for repeat in range(args.repeat):
            guard = b'\xa5' * 132
            check(memcpy, addresses[2], 132, c.c_char_p(guard), 132, 1)
            print(f"CALL_{repeat + 1}_BEGIN", flush=True)
            run(addresses[0], c.byref(groups[0]), addresses[1], c.byref(groups[1]),
                ptr(addresses[2].value + 64), c.byref(groups[2]), 1, stream, False, False)
            check(sync, stream)
            actual = c.create_string_buffer(132)
            check(memcpy, actual, 132, addresses[2], 132, 2)
            raw = actual.raw
            assert raw[:64] == guard[:64] and raw[68:] == guard[68:]
            value = struct.unpack('f', raw[64:68])[0]
            assert abs(value - expected) <= 1e-4 + 1e-4 * abs(expected), (value, expected)
            assert previous is None or previous == raw
            previous = raw
            print(f"CALL_{repeat + 1}_PASS value={value} expected={expected}", flush=True)
        for address, original in zip(addresses[:2], (a, b)):
            actual = c.create_string_buffer(64)
            check(memcpy, actual, 64, address, 64, 2)
            assert actual.raw == original
        print("SIM_CORRECTNESS_PASS", flush=True)
    finally:
        for address in addresses:
            check(free, address)
        check(bind("aclrtDestroyStream", [ptr]), stream)
        check(bind("aclrtResetDevice", [c.c_int]), 0)
        check(bind("aclFinalize", []))


if __name__ == "__main__":
    main()
