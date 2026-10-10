from pathlib import Path
import json
root=Path(__file__).resolve().parent
out=Path('/mnt/newdisk/code/CANN-challenge/score/evidence/datacopy-sweep-20261010')
m=json.loads((out/'实验配置.json').read_text())
samples=list({x['name']: x for x in m['samples']}.values())
for x in samples:
 if x['name']=='点14-64行x128列':x.update(name='点14-64行x256列',line=1024,coverage='点14实际分行整块')
for size,label in [(1216,'点9最终部分结果合并'),(3072,'点11分N部分结果合并')]:
 if not any(x['name']==f'连续{size}B' for x in samples): samples.append(dict(name=f'连续{size}B',rows=1,line=size,pitch=size,dstGap=0,coverage=label))
configs=[]
for sample in samples:
 for mode in [0,1]:
  x=dict(sample,mode=mode,pad=False);x['actualLine']=(x['line']+31)//32*32 if mode==0 else x['line'];x['payloadBytes']=x['rows']*x['line'];x['readBytes']=x['rows']*x['actualLine'];configs.append(x)
 if sample['line']%32:configs.append(dict(sample,mode=1,pad=True,actualLine=sample['line'],payloadBytes=sample['rows']*sample['line'],readBytes=sample['rows']*sample['line']))
batches=[dict(name='空核前测',configs=[None]*15)]
for i in range(0,len(configs),14):batches.append(dict(name=f'搬入批{1+i//14}',configs=[None]+configs[i:i+14]+[None]*max(0,14-len(configs[i:i+14]))))
batches.append(dict(name='空核后测',configs=[None]*15));m.update(batches=batches,sourceBytes=1048576)
for sample in samples:
 assert (sample['rows']-1)*sample['pitch']+(sample['line']+31)//32*32<=m['sourceBytes']
 assert sample['rows']*((sample['line']+31)//32*32+sample['dstGap']*32)<=m['ubBytes']
(out/'实验配置.json').write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n')
header='''#include <cstdint>
#include <memory>
#include <stdexcept>
#include "acl/acl.h"
#include "kernel_operator.h"

// 仅测单核GM->UB搬入：不初始化GM/UB，不计算，不写输出。
struct CopyProbe {
    uint32_t rows;
    uint32_t lineBytes;
    uint32_t pitchBytes;
    uint32_t destinationGap;
    uint32_t mode;
    uint32_t padding;
};

__global__ __aicore__ void MeasureCopy(GM_ADDR source, CopyProbe probe)
{
    KERNEL_TASK_TYPE_DEFAULT(KERNEL_TYPE_AIV_ONLY);
    using namespace AscendC;
    GlobalTensor<uint16_t> input;
    input.SetGlobalBuffer(reinterpret_cast<__gm__ uint16_t*>(source));
    auto local = LocalTensor<uint16_t>(TPosition::VECCALC, 0, 196608 / 2);
    if (probe.rows != 0) {
        if (probe.mode == 0) {
            const uint32_t alignedLine = (probe.lineBytes + 31) / 32 * 32;
            DataCopyParams copy{
                static_cast<uint16_t>(probe.rows),
                static_cast<uint16_t>(alignedLine / 32),
                static_cast<uint16_t>((probe.pitchBytes - alignedLine) / 32),
                static_cast<uint16_t>(probe.destinationGap)};
            DataCopy(local, input, copy);
        } else {
            DataCopyExtParams copy{
                static_cast<uint16_t>(probe.rows), probe.lineBytes,
                probe.pitchBytes - probe.lineBytes, probe.destinationGap, 0};
            const uint8_t right = probe.padding
                ? static_cast<uint8_t>(((32 - probe.lineBytes % 32) % 32) / 2) : 0;
            DataCopyPadExtParams<uint16_t> padding{probe.padding != 0, 0, right, 0};
            DataCopyPad(local, input, copy, padding);
        }
    }
    // 测完成时间，不能只发出搬运就结束。
    PipeBarrier<PIPE_ALL>();
}

inline void CheckProbeAcl(aclError code)
{
    if (code != ACL_SUCCESS) {
        throw std::runtime_error("COPY probe ACL error: " + std::to_string(code));
    }
}
struct ProbeMemory {
    void* address = nullptr;
    ~ProbeMemory() { if (address != nullptr) { aclrtFree(address); } }
};
void DestroyProbeMemory(void* pointer)
{
    delete static_cast<ProbeMemory*>(pointer);
}

extern "C" void run_kernel(GM_ADDR x1, const TensorGroupInfo& info_x1,
    GM_ADDR x2, const TensorGroupInfo& info_x2, GM_ADDR y, const TensorGroupInfo& info_y,
    int64_t availableCoreNum, aclrtStream stream, bool transposeX1, bool transposeX2)
{
    const auto& a = info_x1.tensors[0];
    const auto& b = info_x2.tensors[0];
    const int64_t batch = a.shape[0];
    const int64_t rows = a.shape[transposeX1 ? 2 : 1];
    const int64_t depth = a.shape[transposeX1 ? 1 : 2];
    const int64_t columns = b.shape[transposeX2 ? 1 : 2];
    int index = -1;
'''
tail='''    if (index < 0) { throw std::invalid_argument("unknown COPY probe shape"); }
    CopyProbe probe = configurations[index];
    aclmdlRICaptureStatus status = ACL_MODEL_RI_CAPTURE_STATUS_NONE;
    aclmdlRI model = nullptr;
    CheckProbeAcl(aclmdlRICaptureGetInfo(stream, &status, &model));
    std::unique_ptr<ProbeMemory> memory(new ProbeMemory);
    CheckProbeAcl(aclrtMalloc(&memory->address, 1048576, ACL_MEM_MALLOC_HUGE_FIRST));
    // 不调用Memset/Memcpy：搬入源内容不参与运算，也不搬出。
    auto source = (GM_ADDR)memory->address;
    if (status == ACL_MODEL_RI_CAPTURE_STATUS_ACTIVE) {
        CheckProbeAcl(aclmdlRIDestroyRegisterCallback(model, DestroyProbeMemory, memory.get()));
        memory.release();
    }
    MeasureCopy<<<1, nullptr, stream>>>(source, probe);
    if (status != ACL_MODEL_RI_CAPTURE_STATUS_ACTIVE) {
        CheckProbeAcl(aclrtSynchronizeStream(stream));
    }
}
'''
shape_conditions=''
for i,(batch,rows,columns,depth) in enumerate(m['shapes']):shape_conditions+=f'    {"if" if i==0 else "else if"} (batch == {batch} && rows == {rows} && columns == {columns} && depth == {depth}) {{ index = {i}; }}\n'
for i,batch in enumerate(batches):
 entries=[]
 for x in batch['configs']:
  if x is None:entries.append('        {0, 0, 0, 0, 0, 0}')
  else:entries.append(f"        {{{x['rows']}, {x['line']}, {max(x['pitch'],(x['line']+31)//32*32)}, {x['dstGap']}, {x['mode']}, {int(x['pad'])}}}")
 source=header+shape_conditions+'    const CopyProbe configurations[15] = {\n'+',\n'.join(entries)+'\n    };\n'+tail
 if i in [0,8]:
  start=source.index('    using namespace AscendC;');end=source.index('\n}\n\ninline void CheckProbeAcl',start)
  source=source[:start]+'    // 真正空核对照：不加载参数、不初始化、不搬入、不搬出。\n    AscendC::PipeBarrier<PIPE_ALL>();'+source[end:]
 (root/f'batch{i}.asc').write_text(source)
 (root/f'batch{i}-bridge.asc').write_text('#include <cstdint>\nstruct TensorInfo { const int64_t* shape; int64_t numDims; int32_t dtype; };\nstruct TensorGroupInfo { const TensorInfo* tensors; int64_t numTensors; };\n#include "batch'+str(i)+'.asc"\n')
print(len(samples),len(configs),len(batches))
