"""归档短K装载、点2复测及当前PMU的完整证据。"""
from pathlib import Path
import tarfile,hashlib
root=Path(__file__).resolve().parent
names=['performance_nt_recheck.py','summarize_nt_recheck.py','performance-nt-recheck','nt-recheck-comparison.json','src','baseline.asc','tests','build.py','build.json','build.log','domains.json','domains.log','domains-invalid-input.json','domains-invalid-input.log','invalid-domain-script.py','resident_tt_tail_load_domains.py','measure.py','summarize.py','performance','comparison.json','measure_recheck.py','summarize_recheck.py','performance-recheck','comparison-recheck.json','performance_all.py','summarize_all.py','performance-all','all-comparison.json','pmu.py','pmu-baseline','pmu-candidate','summarize_pmu.py','pmu-summary.json','recheck2.py','summarize2.py','point2-before-after','recheck2.json','export.py']
with tarfile.open(root/'evidence.tar.gz','w:gz') as archive:
    for name in names:
        archive.add(root/name,arcname=name,filter=lambda info: None if '__pycache__' in info.name else info)
print(hashlib.sha256((root/'evidence.tar.gz').read_bytes()).hexdigest(),flush=True)
