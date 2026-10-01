"""按事先记录的清单逐项核验并归档真实NPU结果，拒绝把部分通过写成全部通过。"""
import json,hashlib
from pathlib import Path
root=Path('/mnt/newdisk/cann-explore-artifacts-20260930/compile-prune/npu/regression')
plan=json.loads(Path('score/evidence/compile-prune-20261001/regression-plan.json').read_text())
r={'源码提交':'1e4fcee','补充测试提交':'ce6bfa2','说明':'真实NPU，普通调用＋图捕获两次重放；校验输入不变、输出保护区、FP64参考转FP32及重复一致。每个性能形状两类型四布局另做20预热＋50采样。','边界':{},'新增通用':{},'布局':{}}
for key,prefix,ids in [('边界','case',plan['原测试cases']),('新增通用','generic',plan['新增cases'])]:
 for i in ids:
  p=root/f'{prefix}-{i}.json';d=json.loads(p.read_text());assert d['passed'] and d['execution']=='npu' and d['capture'];r[key][str(i)]=d
for dt in ['fp16','bf16']:
 for layout in ['NN','NT','TN','TT']:
  key=f'{dt}-{layout}';d=json.loads((root/f'layout-{key}.json').read_text());assert d['passed'] and d['warmup']==20 and d['repeat']==50 and len(d['results'])==15;r['布局'][key]=d
r['切换序列']=json.loads((root/'sequence.json').read_text());assert r['切换序列']['passed']
r['计数']={'原边界':len(r['边界']),'新增通用':len(r['新增通用']),'布局形状组合':sum(len(x['results']) for x in r['布局'].values()),'切换调用':len(plan['切换序列'])}
Path('score/evidence/explore-20260930/e54-regression.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(r['计数'])
