"""导出索引倍增实验的源码与验证证据。"""
from pathlib import Path
import tarfile,hashlib
root=Path(__file__).resolve().parent
with tarfile.open(root/'evidence.tar.gz','w:gz') as tar:
    for p in root.rglob('*'):
        if p.is_file() and (p.suffix in ('.json','.csv','.log','.py') or p.name=='kernel.asc'):
            tar.add(p,arcname=str(p.relative_to(root)))
print(hashlib.sha256((root/'evidence.tar.gz').read_bytes()).hexdigest())
