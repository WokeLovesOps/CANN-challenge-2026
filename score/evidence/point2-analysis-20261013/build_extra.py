"""诊断核远端限时编译；每个产物均记录真实耗时和哈希。"""
from pathlib import Path
import subprocess,hashlib,json,time
root=Path(__file__).resolve().parent
records=[]
for name in ('index_early','no_pipe'):
    cmd=['bisheng','-shared','-fPIC','--npu-arch=dav-2201','-g',str(root/f'{name}.asc'),'-o',str(root/f'lib{name}.so'),'-lascendcl']
    start=time.monotonic()
    with (root/f'build-{name}.log').open('w') as log:
        try: status=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,timeout=300).returncode
        except subprocess.TimeoutExpired: status=124
    r={'variant':name,'command':cmd,'seconds':time.monotonic()-start,'exit_code':status,'source_sha256':hashlib.sha256((root/f'{name}.asc').read_bytes()).hexdigest()}
    if status==0:r['library_sha256']=hashlib.sha256((root/f'lib{name}.so').read_bytes()).hexdigest()
    records.append(r);(root/'builds-extra.json').write_text(json.dumps(records,indent=2)+'\n');print(r,flush=True)
    if status:raise SystemExit(status)
