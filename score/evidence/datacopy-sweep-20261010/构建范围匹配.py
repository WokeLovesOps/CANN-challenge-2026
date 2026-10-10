from pathlib import Path
import subprocess,time,json
r=Path(__file__).resolve().parent;records=[]
for i in range(3,9):
 start=time.monotonic();cmd=['bisheng','-shared','-fPIC','--npu-arch=dav-2201','-g',str(r/f'batch{i}-range-bridge.asc'),'-o',str(r/f'libbatch{i}-range.so'),'-ltiling_api','-lregister','-lplatform','-lunified_dlog','-ldl','-lm','-lgraph_base']
 with (r/f'batch{i}-range-build.log').open('w') as f:result=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT)
 record={'batch':i,'seconds':time.monotonic()-start,'exit_code':result.returncode};records.append(record);(r/'范围匹配构建.json').write_text(json.dumps(records,indent=2)+'\n');print(record,flush=True)
 if result.returncode:raise SystemExit(result.returncode)
