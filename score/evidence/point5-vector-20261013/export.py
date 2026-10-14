"""归档点5两种纯Vector候选、完整编译与真机比较。"""
from pathlib import Path
import tarfile,hashlib,json
root=Path(__file__).resolve().parent
for v in ('single','split'):
    q=root/v
    b=json.loads((q/'build.json').read_text());assert b['exit_code']==0 and b['seconds']<300
    for p in (q/'performance').glob('*/application.json'):assert json.loads(p.read_text())['passed']
with tarfile.open(root/'evidence.tar.gz','w:gz') as archive:
    for p in sorted(root.iterdir()):
        if p.name=='evidence.tar.gz':continue
        archive.add(p,arcname=p.name,filter=lambda i:None if '__pycache__' in i.name or i.name.endswith('libcandidate.so') else i)
print(hashlib.sha256((root/'evidence.tar.gz').read_bytes()).hexdigest(),flush=True)
