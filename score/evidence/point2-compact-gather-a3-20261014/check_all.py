"""验证15个代表输入的完整候选正确性，不用墙钟声称性能。"""
from pathlib import Path
import json,subprocess,os
root=Path(__file__).resolve().parent
out=root/'correctness-all';out.mkdir(exist_ok=False)
env=dict(os.environ,OPENBLAS_NUM_THREADS='2',OMP_NUM_THREADS='2')
groups=[('fp16','NN','1,5,13'),('bf16','TN','2,12'),('fp16','NT','3,9'),('bf16','TT','4,8'),('bf16','NT','6,14'),('fp16','TN','7'),('fp16','TT','11,15'),('bf16','NN','10')]
for dtype,layout,cases in groups:
 report=out/(dtype+'-'+layout+'.json')
 command=['python3',str(root/'tests/benchmark.py'),str(root/'libcandidate.so'),'--commit','candidate','--report',str(report),'--cases',cases,'--dtype',dtype,'--layout',layout,'--warmup','0','--repeat','2','--real-npu']
 subprocess.run(command,env=env,check=True,timeout=120)
 assert json.loads(report.read_text())['passed']
 print(dtype,layout,'通过',flush=True)
