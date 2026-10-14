"""归档点9的延迟水平归约候选及验证证据。"""
from pathlib import Path
import tarfile,hashlib
root=Path(__file__).resolve().parent
with tarfile.open(root/'evidence.tar.gz','w:gz') as archive:
    for p in sorted(root.iterdir()):
        if p.name in ('evidence.tar.gz','libcandidate.so'):continue
        archive.add(p,arcname=p.name,filter=lambda i:None if '__pycache__' in i.name or i.name.endswith('.so') else i)
print(hashlib.sha256((root/'evidence.tar.gz').read_bytes()).hexdigest(),flush=True)
