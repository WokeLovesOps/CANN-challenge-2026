"""采集当前完整库的点1真机计时、PMU及软件模型，分别记录。"""
from pathlib import Path
import subprocess,os,json,time,hashlib
root=Path(__file__).resolve().parent
root.chmod(0o700)
suite=Path('/home/developer/cann-point5-bfirst-20261014')
binary=suite/'baseline-build'
assert hashlib.sha256((binary/'src/kernel.asc').read_bytes()).hexdigest()=='17f4ea4969d62c6c59e6ec86aa396b7516c40ee124978c627e86ae53fee884ce'
assert hashlib.sha256((binary/'libcandidate.so').read_bytes()).hexdigest()=='08ef313a701ab76282ded88688bc92f5face4f04c267b63fe6c8abf3ff2adc2d'
(root/'build-provenance.json').write_bytes((binary/'build.json').read_bytes())
env=dict(os.environ,OPENBLAS_NUM_THREADS='2',OMP_NUM_THREADS='2')
for mode in ['l0-0','l0-1','l0-2','pmu-0','pmu-1','model']:
    dest=root/mode;dest.mkdir(exist_ok=False,mode=0o700)
    app=dest/'application.json'
    application=['python3',str(suite/'tests/benchmark.py'),str(binary/'libcandidate.so'),'--commit','current-point1','--report',str(app),'--cases','1','--dtype','fp16','--layout','NN','--warmup','0' if mode=='model' else '20','--repeat','50' if mode.startswith('l0') else '2']
    if mode!='model': application+=['--real-npu']
    if mode.startswith('l0'):
        command=['msprof','--task-time=l0','--output='+str(dest/'profile'),'--application='+' '.join(application)]
    elif mode.startswith('pmu'):
        command=['msprof','op','--aic-metrics=PipeUtilization,Memory,MemoryUB,ArithmeticUtilization','--launch-count=1','--launch-skip-before-match=20','--output='+str(dest/'profile')]+application
    else:
        command=['msprof','op','simulator','--soc-version=Ascend910B3','--core-id=0','--launch-count=2','--timeout=2','--output='+str(dest/'profile')]+application
    start=time.monotonic()
    with (dest/'run.log').open('w') as log:
        try: status=subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=150).returncode
        except subprocess.TimeoutExpired: status=124
    (dest/'command.json').write_text(json.dumps({'command':command,'exit_code':status,'seconds':time.monotonic()-start},indent=2))
    assert status == 0 and app.exists(), f'{mode}: 未产生有效应用报告'
    assert json.loads(app.read_text())['passed'], f'{mode}: 应用校验失败'
    print(mode,status,flush=True)
    if status==0 and mode.startswith('l0'):
        subprocess.run(['python3',str(suite/'tests/summarize_profile.py'),str(app),str(dest/'profile'),'--output',str(dest/'summary.json')],env=env,check=True)
