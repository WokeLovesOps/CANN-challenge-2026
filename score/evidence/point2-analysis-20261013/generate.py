"""从当前源码提取完整小矩阵核，生成仅用于瓶颈诊断的等价变体。"""
from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parent
src=Path('src/kernel.asc').read_text(encoding='utf-8')
a=src.index('template <typename T, bool TRANS_A, bool TRANS_B>\n__global__ __aicore__ void ComputePackedCastGather')
b=src.index('template <typename T, bool TRANS_A, bool TRANS_B>\n__global__ __aicore__ void ComputePackedDots',a)
body=src[a:b]
constants=src[src.index('constexpr uint32_t DEFAULT_ROWS'):src.index('enum class ShapeKey')]
header='''#include <cstdint>
#include "acl/acl.h"
#include "kernel_operator.h"
struct TensorInfo { const int64_t* shape; int64_t numDims; int32_t dtype; };
struct TensorGroupInfo { const TensorInfo* tensors; int64_t numTensors; };
namespace batch_max_sum {
'''+constants
footer='''
}
extern "C" void run_kernel(GM_ADDR x1, const TensorGroupInfo* info1, GM_ADDR x2,
    const TensorGroupInfo* info2, GM_ADDR y, const TensorGroupInfo*, int64_t,
    aclrtStream stream, bool, bool) {
    auto a=info1->tensors[0]; auto b=info2->tensors[0];
    batch_max_sum::ComputePackedCastGather<bfloat16_t,true,false><<<1,nullptr,stream>>>(
        x1,x2,y,a.shape[2],b.shape[2],a.shape[1]);
    aclrtSynchronizeStream(stream);
}
'''
variants={'base':body}
t=body
start=t.index('    TPipe pipe;');end=t.index('    constexpr uint32_t outputEnd',start)
t=t[:start]+'''    TPipe pipe;
'''+t[end:]
t=t.replace('auto input = inputQueue.AllocTensor<T>();','auto input = LocalTensor<T>(TPosition::VECCALC, 0, 2 * SMALL_VECTOR_MATRIX_ELEMENTS);')
t=t.replace('inputQueue.EnQue(input);','SetFlag<HardEvent::MTE2_V>(EVENT_ID0);')
t=t.replace('input = inputQueue.DeQue<T>();','WaitFlag<HardEvent::MTE2_V>(EVENT_ID0);')
t=t.replace('    inputQueue.FreeTensor(input);\n','')
t=t.replace('auto result = outputQueue.AllocTensor<float>();','auto result = LocalTensor<float>(TPosition::VECCALC, 2 * SMALL_VECTOR_MATRIX_ELEMENTS * sizeof(T), 8);')
t=t.replace('    outputQueue.EnQue(result);\n    result = outputQueue.DeQue<float>();','    SetFlag<HardEvent::V_MTE3>(EVENT_ID0);\n    WaitFlag<HardEvent::V_MTE3>(EVENT_ID0);')
t=t.replace('    outputQueue.FreeTensor(result);\n','')
variants['no_queue']=t
old='''    uint64_t maximumMask[2] = {0, 0};
    for (uint32_t col = 0; col < n; ++col) {
        maximumMask[col / 8] |= uint64_t{1} << ((col % 8) * 8);
    }'''
new='''    constexpr uint64_t sparse = 0x0101010101010101ULL;
    uint64_t maximumMask[2] = {
        n >= 8 ? sparse : sparse & ((uint64_t{1} << (n * 8)) - 1),
        n <= 8 ? 0 : n == 16 ? sparse : sparse & ((uint64_t{1} << ((n - 8) * 8)) - 1)};'''
assert old in body
variants['mask']=body.replace(old,new)
variants['no_queue_mask']=t.replace(old,new)
for name,code in variants.items(): (root/f'{name}.asc').write_text(header+code+footer,encoding='utf-8')
(root/'manifest.json').write_text(json.dumps({'original_source_sha256':hashlib.sha256(Path('src/kernel.asc').read_bytes()).hexdigest(),'variants':{n:hashlib.sha256((root/f'{n}.asc').read_bytes()).hexdigest() for n in variants}},indent=2)+'\n')
