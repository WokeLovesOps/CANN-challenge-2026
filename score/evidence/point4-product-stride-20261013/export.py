"""归档步长实验的源码、基线和真机证据。"""
from pathlib import Path
import tarfile,hashlib
root=Path(__file__).resolve().parent
names=['src','baseline.asc','tests','build.py','build.json','build.log','smoke.json','smoke.log','domains.json','domains.log','measure.py','summarize.py','performance','comparison.json','performance_all.py','summarize_all.py','performance-all','all-comparison.json','pmu.py','pmu-baseline','pmu-candidate','export.py']
with tarfile.open(root/'evidence.tar.gz','w:gz') as archive:
    for name in names:
        archive.add(root/name,arcname=name,filter=lambda info: None if '__pycache__' in info.name else info)
print(hashlib.sha256((root/'evidence.tar.gz').read_bytes()).hexdigest(),flush=True)
