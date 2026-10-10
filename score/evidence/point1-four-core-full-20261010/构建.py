from pathlib import Path
import subprocess,time,json,hashlib
r=Path(__file__).resolve().parent
records=[]
for i in ['baseline','four']:
    start=time.monotonic()
    cmd=['bisheng','-shared','-fPIC','--npu-arch=dav-2201','-g',str(r/f'{i}-bridge.asc'),'-o',str(r/f'lib{i}.so'),'-ltiling_api','-lregister','-lplatform','-lunified_dlog','-ldl','-lm','-lgraph_base']
    with (r/f'{i}-build.log').open('w') as f:
        result=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT)
    record=dict(cores=i,seconds=time.monotonic()-start,exit_code=result.returncode,source_sha256=hashlib.sha256((r/f'{i}.asc').read_bytes()).hexdigest(),command=cmd)
    if result.returncode==0:record['library_sha256']=hashlib.sha256((r/f'lib{i}.so').read_bytes()).hexdigest()
    records.append(record)
    (r/'构建.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
    print(record,flush=True)
    if result.returncode:raise SystemExit(result.returncode)
