"""归档未采用的按列repeat实验及真机证据。"""
from pathlib import Path
import tarfile,hashlib
root=Path(__file__).resolve().parent
names=['src','baseline.asc','tests','build.py','build.json','build.log','smoke.json','smoke.log','measure.py','summarize.py','performance','comparison.json','export.py']
with tarfile.open(root/'evidence.tar.gz','w:gz') as archive:
    for name in names:
        archive.add(root/name,arcname=name,filter=lambda info: None if '__pycache__' in info.name else info)
print(hashlib.sha256((root/'evidence.tar.gz').read_bytes()).hexdigest(),flush=True)
