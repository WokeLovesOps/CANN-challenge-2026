from pathlib import Path
import tarfile
root=Path('/home/developer/cann-point8-k256-20261013')
with tarfile.open(root/'evidence.tar.gz','w:gz') as tar:
    for p in root.rglob('*'):
        if p.is_file() and (p.suffix in ('.json','.csv','.log','.py') or 'pmu' in p.relative_to(root).parts or p.name=='kernel.asc'):
            tar.add(p,arcname=str(p.relative_to(root)))
