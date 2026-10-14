"""归档112行对照与B预取实验的源码、构建和真机证据。"""
from pathlib import Path
import tarfile,hashlib
root=Path(__file__).resolve().parent
names=['src','baseline.asc','tests','build.py','build.json','build.log','measure.py','summarize.py','performance','comparison.json']
for name in ['smoke.json','smoke.log','domains.json','domains.log','performance_all.py','summarize_all.py','performance-all','all-comparison.json','build-failed.json','build-failed.log','resident_tt_bprefetch_domains.py']:
    if (root/name).exists():names.append(name)
with tarfile.open(root/'evidence.tar.gz','w:gz') as archive:
    for name in names+['export.py']:
        archive.add(root/name,arcname=name,filter=lambda info: None if '__pycache__' in info.name else info)
print(hashlib.sha256((root/'evidence.tar.gz').read_bytes()).hexdigest(),flush=True)
