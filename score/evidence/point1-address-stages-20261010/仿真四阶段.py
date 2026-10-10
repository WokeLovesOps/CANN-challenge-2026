from pathlib import Path
import subprocess,json,csv,hashlib,re,sys,os
r=Path(__file__).resolve().parent
d=Path('/mnt/newdisk/code/CANN-challenge/score/evidence/point1-address-stages-20261010')
for i in map(int,sys.argv[1:]):
    out=r/'sim'/f'stage{i}-指针校验'
    out.mkdir(parents=True,mode=0o700,exist_ok=True)
    report=out/'执行检查.json'
    cmd=['msprof','op','simulator','--soc-version=Ascend910B3','--launch-count=2','--timeout=2',f'--output={out}/profile','python3',str(r/'仿真入口.py'),str(r/f'libstage{i}.so'),'--case=0',f'--report={report}']
    with (out/'run.log').open('w') as f:
        p=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
    record=json.loads(report.read_text()) if report.exists() else {'passed':False}
    bins=list(out.glob('profile/**/visualize_data.bin'))
    csvs=list(out.glob('profile/**/core0.veccore0/*instr_exe*.csv'))
    counts=[];instructions=[]
    for f in csvs:
        rows=list(csv.DictReader(f.open()))
        counts.append(sum(int(v['call_count']) for v in rows if v['pipe']=='MTE2' and 'Src:OUT,Dst:UB' in v['detail']))
        assert not any(v['pipe']=='MTE3' and v['instr'].startswith('MOV_') for v in rows)
        instructions.append([v for v in rows if v['instr'].startswith(('LD','MOV_','BAR'))])
    record.update(stage=i,exit_code=p.returncode,copy_counts=counts,command=cmd,source_sha256=hashlib.sha256((r/f'stage{i}.asc').read_bytes()).hexdigest(),library_sha256=hashlib.sha256((r/f'libstage{i}.so').read_bytes()).hexdigest(),bins=[dict(path=str(b),size=b.stat().st_size,sha256=hashlib.sha256(b.read_bytes()).hexdigest()) for b in bins],instructions=instructions)
    record['timings']=[dict(core=c,duration_us=float(v),running_us=float(t)) for c,v,t in re.findall(r'(core\d+\.veccore\d+)\s+(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)',(out/'run.log').read_text())]
    expected=max(0,i-1)
    record['passed']=record['passed'] and p.returncode==0 and len(bins)==2 and len(csvs)==2 and counts==[expected,expected] and len(record['timings'])==2
    (d/f'stage{i}-model.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
    print(i,record['passed'],record['timings'],counts,flush=True)
    if not record['passed']:raise SystemExit('阶段指令核验失败')
