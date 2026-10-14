"""限时编译并保存真实退出码、耗时、源码和产物哈希。"""
from pathlib import Path
import hashlib, json, subprocess, time, sys
root = Path(__file__).resolve().parent
source = root/'tests/simulator_bridge.asc'
command = ['bisheng','-shared','-fPIC','--npu-arch=dav-2201','-g',str(source),
           '-o',str(root/'libcandidate.so'),'-ltiling_api','-lregister','-lplatform',
           '-lunified_dlog','-ldl','-lm','-lgraph_base']
start=time.monotonic()
with (root/'build.log').open('w') as log:
    try:
        result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=300)
        status=result.returncode
    except subprocess.TimeoutExpired:
        status=124
record={'command':command,'seconds':time.monotonic()-start,'exit_code':status,
        'source_sha256':hashlib.sha256((root/'src/kernel.asc').read_bytes()).hexdigest()}
if status==0: record['library_sha256']=hashlib.sha256((root/'libcandidate.so').read_bytes()).hexdigest()
(root/'build.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(record,ensure_ascii=False),flush=True)
sys.exit(status)
