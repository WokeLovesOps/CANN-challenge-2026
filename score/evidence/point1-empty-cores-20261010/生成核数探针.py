from pathlib import Path
import difflib
r=Path(__file__).resolve().parent
repo=Path('/mnt/newdisk/code/CANN-challenge')
formal=(r/'正式基线.asc').read_text()
# 完全复用前轮点1空核体与签名，只改变生效Host入口的启动核数。
empty=(repo/'Build/point1-address-stages-20261010/stage0.asc').read_text()
call='ComputeDot32<half><<<1, nullptr, stream>>>(x1, x2, y);'
a=empty.rindex(call)
for cores in [2,4,8]:
    source=empty[:a]+call.replace('<<<1,','<<<'+str(cores)+',')+empty[a+len(call):]
    assert source.replace('ComputeDot32<half><<<'+str(cores)+', nullptr, stream>>>(x1, x2, y);',call)==empty
    (r/f'core{cores}.asc').write_text(source)
    (r/f'core{cores}-bridge.asc').write_text('#include <cstdint>\n#include "acl/acl.h"\nstruct TensorInfo { const int64_t* shape; int64_t numDims; int32_t dtype; };\nstruct TensorGroupInfo { const TensorInfo* tensors; int64_t numTensors; };\n#include "core'+str(cores)+'.asc"\n')
    (repo/'score/evidence/point1-empty-cores-20261010'/f'core{cores}.patch').write_text(''.join(difflib.unified_diff(formal.splitlines(True),source.splitlines(True),fromfile='正式基线.asc',tofile=f'core{cores}.asc')))
