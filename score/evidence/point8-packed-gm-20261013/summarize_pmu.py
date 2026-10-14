"""汇总前16个完整行任务的PMU，计时指标不能相加。"""
from pathlib import Path
import csv,json,statistics
root=Path(__file__).resolve().parent
out={}
keys=['aic_time(us)','aic_cube_time(us)','aic_mte2_time(us)','aic_mte1_time(us)','aic_fixpipe_time(us)','aiv_time(us)','aiv_vec_time(us)','aiv_mte2_time(us)']
for version in ['baseline','candidate']:
    files=list((root/('pmu-'+version)).rglob('PipeUtilization.csv'));assert len(files)==1
    rows=list(csv.DictReader(files[0].open()))
    group=[r for r in rows if int(r['block_id'])<16]
    result={}
    for key in keys:
        values=[float(r[key]) for r in group if r.get(key) not in (None,'NA','')]
        result[key]={'median':statistics.median(values),'count':len(values)}
    out[version]=result
(root/'pmu-summary.json').write_text(json.dumps(out,indent=2))
print(json.dumps(out))
