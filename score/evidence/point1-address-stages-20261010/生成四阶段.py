from pathlib import Path
import difflib
r=Path(__file__).resolve().parent
s=(r/'正式基线.asc').read_text()
a=s.index('template <typename T>\n__global__ __aicore__ void ComputeDot32(')
b=s.index('// 点6精确形状',a)
header='''template <typename T>
__global__ __aicore__ void ComputeDot32(GM_ADDR x1, GM_ADDR x2, GM_ADDR y)
{
    KERNEL_TASK_TYPE_DEFAULT(KERNEL_TYPE_AIV_ONLY);
    using namespace AscendC;
'''
addresses='''    // 保留A/B地址加载和非空校验；不读取输入内容、不写UB/GM。
    // 地址阶段含此校验的比较与分支，不称纯参数读取。
    if (x1 == nullptr || x2 == nullptr) {
        return;
    }
'''
setup='''    GlobalTensor<T> a;
    a.SetGlobalBuffer(reinterpret_cast<__gm__ T*>(x1));
    auto input = LocalTensor<T>(TPosition::VECCALC, 0, 64);
    DataCopyExtParams copy{1, 64, 0, 0, 0};
    DataCopyPadExtParams<T> padding{false, 0, 0, 0};
    DataCopyPad(input, a, copy, padding);
'''
second='''    GlobalTensor<T> b;
    b.SetGlobalBuffer(reinterpret_cast<__gm__ T*>(x2));
    DataCopyPad(input[32], b, copy, padding);
'''
for stage in range(4):
 body=header+(addresses if stage>=1 else '')+(setup if stage>=2 else '')+(second if stage>=3 else '')+'''    // 四个版本使用同一结束屏障，确保已发出的搬运完成。
    PipeBarrier<PIPE_ALL>();
}

'''
 out=s[:a]+body+s[b:]
 assert out[:a]==s[:a] and out[a+len(body):]==s[b:]
 (r/f'stage{stage}.asc').write_text(out)
 (r/f'stage{stage}-bridge.asc').write_text('#include <cstdint>\n#include "acl/acl.h"\nstruct TensorInfo { const int64_t* shape; int64_t numDims; int32_t dtype; };\nstruct TensorGroupInfo { const TensorInfo* tensors; int64_t numTensors; };\n#include "stage'+str(stage)+'.asc"\n')
 Path('/mnt/newdisk/code/CANN-challenge/score/evidence/point1-address-stages-20261010',f'stage{stage}.patch').write_text(''.join(difflib.unified_diff(s.splitlines(True),out.splitlines(True),fromfile='正式基线.asc',tofile=f'stage{stage}.asc')))
