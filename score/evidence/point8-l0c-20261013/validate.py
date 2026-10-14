from pathlib import Path
import subprocess,json,os
root=Path('/home/developer/cann-point8-l0c-20261013')
env=dict(os.environ,OPENBLAS_NUM_THREADS='2',OMP_NUM_THREADS='2')
for name,flags in [('domain',[]),('capture',['--capture'])]:
    command=['python3',str(root/'tests/resident_tt_domains.py'),str(root/'libcandidate.so'),'--real-npu','--report',str(root/(name+'.json'))]+flags
    with (root/(name+'.log')).open('w') as f:
        result=subprocess.run(command,stdout=f,stderr=subprocess.STDOUT,env=env,timeout=240)
    print(name,result.returncode,flush=True)
    if result.returncode: raise SystemExit(result.returncode)
