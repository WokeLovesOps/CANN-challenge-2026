from pathlib import Path
import tarfile,hashlib
root=Path(__file__).resolve().parent
with tarfile.open(root/'evidence.tar.gz','w:gz') as tar:
    for name in ['cann-point4-ub-20261013','cann-point4-ub64-20261013']:
        src=root.parent/name
        for p in src.rglob('*'):
            if p.is_file() and (p.suffix in ('.json','.csv','.log','.py') or p.name=='kernel.asc'):
                tar.add(p,arcname=str(Path(name)/p.relative_to(src)))
print(hashlib.sha256((root/'evidence.tar.gz').read_bytes()).hexdigest())
