"""只核验地址与资源公式，不执行算子、不模拟浮点运算。"""
from pathlib import Path
import hashlib
import json
import math
import re
import subprocess

root = Path(__file__).resolve().parents[3]
source = (root / 'src/kernel.asc').read_text()
base = subprocess.check_output(['git', 'show', '4cc7e815:src/kernel.asc'], cwd=root, text=True)
begin = 'template <uint32_t TILE_ROWS, bool BULK_PARTIAL = false>'
end = '// 异步模式显式请求完成通知'
assert source.split(begin)[0] == base.split(begin)[0]
assert source.split(end)[1] == base.split(end)[1]
assert not re.search(r'\b(?:printf|PRINTF)\s*\(', source)
# 以下枚举比实际核心数约束更宽，不把组合数称为实际运行用例。
combinations = 0
mask_shapes = {}
for rows in (32, 64, 112, 128, 256):
    masks = [min(64, rows - offset) for offset in range(0, rows, 64)]
    mask_shapes[str(rows)] = masks
    for parts in range(2, 65):
        input_elements = parts * rows
        if input_elements // 8 > 255:
            continue
        for tiles in range(2, math.ceil(8192 / rows) + 1):
            group_limit = min(tiles, 255, 4096 // input_elements)
            # 任一更严格UB预算只会降低组上限，逐个覆盖所有可能组大小。
            for group in range(2, group_limit + 1):
                assert group * input_elements * 4 <= 16384
                assert group * rows * 4 % 32 == 0
                for start in range(0, tiles, group):
                    active = min(group, tiles - start)
                    assert 1 <= active <= 255
                    assert (start + active) * input_elements <= tiles * input_elements
                    for offset, mask in zip(range(0, rows, 64), masks):
                        # 最后repeat、最后part为最大地址；其他索引均单调不大于此。
                        last_source_end = (active - 1) * input_elements + (parts - 1) * rows + offset + mask
                        last_dest_end = (active - 1) * rows + offset + mask
                        assert last_source_end <= group * input_elements
                        assert last_dest_end <= group * rows
                        assert offset * 4 % 32 == 0
                combinations += 1
result = {
    '说明': '静态地址算术枚举，不是NPU、仿真或数值正确性运行',
    '源码SHA256': hashlib.sha256(source.encode()).hexdigest(),
    '仅FinishSplitN范围修改': True,
    '无诊断printf': True,
    '静态组合数量': combinations,
    '各行块mask': mask_shapes,
    '预算证明': [
        '非bulk：G<=floor((budget-fixed)/(rowInputBytes+rowMaximumBytes))，所以fixed+G*(input+maxima)<=budget。',
        'bulk：先验证remaining>batchInputBytes，再G<=floor((remaining-batchInputBytes)/rowMaximumBytes)，所以fixed+整batch输入+G*maxima<=budget。',
        'fixed包含133120字节调用方显式上界、256字节output、sums、temp和32字节reduce；各申请都是32字节整数倍。',
        'budget使用编译时实际TOTAL_VEC_LOCAL_SIZE-sizeof(KfcMsg)，不硬写KFC大小。',
        'G<2、stride超界或预算不足时，原bulk标志、原输入大小与旧逐tile归约保持。'
    ]
}
(root / 'score/evidence/grouped-finish-splitn-20261017/静态核验.json').write_text(
    json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(result, ensure_ascii=False))
