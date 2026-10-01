"""保存E54模型正确性、核名、代码映射与指令摘要。"""
import csv,hashlib,json,re
from pathlib import Path
r={'源码提交':'1e4fcee','补充测试提交':'ce6bfa2','说明':'模型仅用于通用分支正确性与指令验证，core0采集不代表完整最慢核；模型时间不作为NPU性能。','首次失败':'第一次case128因输出父目录组可写被msprof拒绝，见Build/prune-model-split128.log；未执行kernel。','结果':{}}
root=Path('/mnt/newdisk/cann-explore-artifacts-20260930/prune-model-private')
for tag,logstem,appstem in [('split128','split128-retry','split128-retry'),('case-72','72','72'),('case-15','15','15'),('generic-7','generic-7','generic-7'),('generic-24','generic-24','generic-24')]:
 app=json.loads(Path(f'Build/prune-model-{appstem}.json').read_text());assert app['passed']
 log=Path(f'Build/prune-model-{logstem}.log').read_text();assert 'Profiling data parse finished.' in log
 sim=next((root/tag).glob('OPPROF_*/simulator'));bn=sim/'visualize_data.bin';assert bn.stat().st_size
 kernels=[l for l in log.splitlines() if 'Start profiling on kernel:' in l];assert any('ComputeGeneric' in l for l in kernels)
 v={'应用':app,'核名':kernels,'BIN':str(bn),'BIN字节数':bn.stat().st_size,'BIN_SHA256':hashlib.sha256(bn.read_bytes()).hexdigest(),'核':{}}
 for core in sorted(sim.glob('core*')):
  code=list(csv.DictReader(next(core.glob('*code_exe.csv')).open()));assert any('kernel.asc:' in x['code'] for x in code)
  counts={}
  for x in csv.DictReader(next(core.glob('*instr_exe.csv')).open()):counts[x['instr']]=counts.get(x['instr'],0)+int(x['call_count'])
  v['核'][core.name]={'源码映射行数':len(code),'指令次数':counts,'模型duration_running_us':re.findall(re.escape(core.name)+r'\s+([\d.]+)\s+([\d.]+)',log)}
 r['结果'][tag]=v
Path('score/evidence/explore-20260930/e54-models.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
print('5组模型核名、正确性、BIN及源码映射全部核验')
