"""归档完整与定向对照，保留所有正反向原始结果。"""
import json
import statistics
from pathlib import Path

e = Path('score/evidence/explore-20260930')
tags = ['abba', 'baab', 'focused-abba', 'focused-baab']
data = {tag: json.loads((e / ('e54-' + tag + '-20-50.json')).read_text()) for tag in tags}
rounds = data['abba']['轮次'] + data['baab']['轮次']
combined = {}
for k in map(str, range(1, 16)):
    by = {}
    for v in ['3acbe89', '1e4fcee']:
        samples = [x for r in rounds if r['commit'] == v for x in r['results'][k]['samples_us']]
        assert len(samples) == 200
        by[v] = statistics.median(samples)
    assert all(r['results'][k]['kernels'] == rounds[0]['results'][k]['kernels'] for r in rounds)
    combined[k] = dict(baseline_us=by['3acbe89'], candidate_us=by['1e4fcee'], change_percent=100*(by['1e4fcee']/by['3acbe89']-1))
for tag in tags[2:]:
    for r in data[tag]['轮次']:
        for k in r['results']:
            assert r['results'][k]['kernels'] == rounds[0]['results'][k]['kernels']
conclusion = '编译目标达成，15点性能整体接近，未复现稳定的明显退化；不能保证逐点耗时严格相等。'
result = {'说明': '完整ABBA＋BAAB每版每点合计200个采样，各组20预热＋50采样且输入hash一致。定向复测保持独立，不替换首轮数据。', '源码': '1e4fcee', '基线': '3acbe89', '完整合并': combined, '定向复测': {tag: data[tag]['合并'] for tag in tags[2:]}, '结论': conclusion}
(e / 'e54-performance-conclusion.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')

def row(label, values):
    return '| ' + label + ' | ' + ' | '.join('未测' if v is None else format(v, '.3f') for v in values) + ' |\n'

platform = [1.22,1.58,2.13,2.92,1.89,7.07,3.68,14.88,50.68,68.65,71.25,85.25,5.14,5.40,4.05]
table = '| 版本／微秒 | ' + ' | '.join('点'+str(i) for i in range(1,16)) + ' |\n'
table += '| --- | ' + ' | '.join(['---:']*15) + ' |\n'
table += row('平台最优（用户提供）', platform)
table += row('`1e4fcee` 候选，完整两轮合并', [combined[str(i)]['candidate_us'] for i in range(1,16)])
table += row('`3acbe89` 原版，本轮同机对照', [combined[str(i)]['baseline_us'] for i in range(1,16)])
comparison = '| 点 | 完整ABBA | 完整BAAB | 定向ABBA | 定向BAAB |\n| --- | ---: | ---: | ---: | ---: |\n'
for k in ['1','4','6','7','13','14']:
    values = [format(data[t]['合并'][k]['change_percent'], '+.2f')+'%' for t in tags]
    comparison += '| ' + k + ' | ' + ' | '.join(values) + ' |\n'
text = '## NPU耗时汇总\n\n' + table
text += '\n完整ABBA＋BAAB合并后，候选相对原版的逐点变化为 **-0.045%～+1.194%**；最大增幅在点7。所有15点核名逐点一致。下表保留各轮变化，正值表示变慢；不能只挑选某一轮作为结论。\n\n' + comparison
text += '\n结论：**' + conclusion + '** 点7原完整BAAB的+3.23%没有在定向正反向复测中复现；定向点6的+3.77%也未在反向复测中复现。原因未进一步定性，不将它们宣称为确定的纯噪声，也不把某次下降归因于代码加速。\n\n'
p = Path('score/编译收敛实验汇报-20261001.md')
s = p.read_text().replace('## 编译结果', text + '## 编译结果', 1)
s = s.replace('完整ABBA＋BAAB性能已采集；针对点7波动的附加复测待汇总。', '完整ABBA＋BAAB和6点定向ABBA＋BAAB均通过：每组20预热＋50采样，原版／候选输入hash一致；核名逐点一致。真实NPU正确性、普通计时串行运行。')
s = s.replace('- 首轮完整性能：', '- 定向性能：`e54-focused-abba-20-50.json`、`e54-focused-baab-20-50.json`；汇总：`e54-performance-conclusion.json`。\n- 回归应用记录：`e54-regression.json`；288项计划和脚本同时归档。\n- 首轮完整性能：')
s = s.replace('候选算子提交为 `1e4fcee`，', '源码在独立工作树 `/home/user/.codex/worktrees/bmm-npu-explore/CANN-challenge/src/kernel.asc`，候选算子提交为 `1e4fcee`，')
p.write_text(s)
p = Path('score/explore.md')
lines = p.read_text().splitlines(keepends=True)
pos = next(i for i,l in enumerate(lines) if l.startswith('| 平台最优')) + 1
new = ''
for tag,label in [('focused-baab','定向BAAB'),('focused-abba','定向ABBA'),('baab','完整BAAB'),('abba','完整ABBA')]:
    d = data[tag]['合并']
    values = [d[str(i)]['candidate_us'] if str(i) in d else None for i in range(1,16)]
    new += row('`1e4fcee` E54编译收敛105组合，'+label+' 20＋50；正确性通过，波动详见报告', values)
lines.insert(pos, new)
s = ''.join(lines)
s += '''
### E54最终结论与交付

- 代码提交 `1e4fcee`，补充测试提交 `ce6bfa2`；本轮未进一步修改候选源码。225→105入口组合由共享库和原始可执行产物分别核实；各自原版／候选共有153个AIC/AIV代码段全部相同。
- 本地原始src入口、默认参数、干净 `-j4`：188.62→79.47秒，减少57.87%，达到150秒以内要求。本地同参数带 `-g` 共享入口：325.22→135.28秒；远端同参数带 `-g` 共享入口：516.60→215.55秒。远端带调试入口仍超过150秒，不能把本地结果泛化到它或OJ。
- 模型5组均通过且实际命中ComputeGeneric；保留BIN、指令和源码映射。首次采集仅因目录权限被拒绝，重试通过。远端重建后原目录丢失，双方从固定提交重编；缺少GNU time已补齐。
- NPU的7项初测、288项边界（普通调用＋捕获重放）、120组两类型四布局标准形状、10次分支切换均通过。计时严格20预热＋50采样、完整ABBA＋BAAB；另做6点定向ABBA＋BAAB，所有核名与对应基线一致。
- 完整两轮合并后15点变化为-0.045%～+1.194%。完整BAAB点7曾增加3.23%，定向ABBA／BAAB为-0.63%／-1.50%；定向ABBA点6增加3.77%，反向为-0.76%。全部原始轮次保留，不以单次加速抵消单次退化。结论为性能整体接近、未复现稳定明显退化，不能承诺每点严格相等。
- 保留候选；本次编译收敛任务结束，不恢复此前无限探索。详见 `编译收敛实验汇报-20261001.md`、`score/evidence/compile-prune-20261001/` 和 `e54-*.json`。
'''
p.write_text(s)
print('报告与台账已生成，16组核名均核验通过')
