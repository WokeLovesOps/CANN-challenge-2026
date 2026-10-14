"""归档点4三个方向的源码、编译、验证及性能证据。"""
from pathlib import Path
import tarfile,hashlib
root=Path(__file__).resolve().parent
names=['cann-point4-mask-20261013','cann-point4-unroll-20261013','cann-point4-direct-20261013','cann-point4-direct-v2-20261013']
with tarfile.open(root/'evidence.tar.gz','w:gz') as tar:
    for name in names:
        src=root.parent/name
        for p in src.rglob('*'):
            if p.is_file() and (p.suffix in ('.json','.csv','.log','.py') or p.name=='kernel.asc'):
                tar.add(p,arcname=str(Path(name)/p.relative_to(src)))
print(hashlib.sha256((root/'evidence.tar.gz').read_bytes()).hexdigest())
