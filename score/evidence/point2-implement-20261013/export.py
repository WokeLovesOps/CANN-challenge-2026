"""仅导出验证报告和原始核时间表，不复制设备分析二进制。"""
from pathlib import Path
import tarfile
root=Path(__file__).resolve().parent
with tarfile.open(root/'performance-evidence.tar.gz','w:gz') as tar:
    for p in (root/'performance').rglob('*'):
        if p.is_file() and (p.name in ('runs.json','comparison.json','application.json','summary.json','run.log') or p.name.startswith('op_summary') and p.suffix=='.csv'):
            tar.add(p,arcname=str(p.relative_to(root)))
