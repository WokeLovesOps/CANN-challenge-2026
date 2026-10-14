from pathlib import Path
import csv,json,statistics
root=Path(__file__).resolve().parent
for version in ['baseline','candidate']:
    dest=root/('pmu-'+version)
    app=json.loads((dest/'application.json').read_text())
    print(version,'application',app)
    for name in ['ResourceConflictRatio.csv','PipeUtilization.csv']:
        for f in dest.rglob(name):
            print(name,f.read_text())
