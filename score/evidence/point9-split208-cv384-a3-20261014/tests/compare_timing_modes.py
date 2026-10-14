"""独立对照普通调用与计算图重放；不修改提交算子或宣称复现未知OJ口径。"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shlex
import statistics
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('library', type=Path)
    parser.add_argument('--source', type=Path, required=True, help='对应库的源码快照，仅记录哈希，不代表重新编译核验')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cases', default='2')
    parser.add_argument('--dtype', choices=('fp16', 'bf16'), default='bf16')
    parser.add_argument('--layout', choices=('NN', 'NT', 'TN', 'TT'), default='TN')
    parser.add_argument('--warmups', default='0,20,200')
    parser.add_argument('--repeat', type=int, default=50)
    args = parser.parse_args()
    warmups = [int(v) for v in args.warmups.split(',')]
    if not warmups or len(set(warmups)) != len(warmups) or min(warmups) < 0 or args.repeat < 2:
        parser.error('预热次数必须唯一且非负，正式采样至少两次')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    suite = Path(__file__).resolve().parent
    library = args.library.resolve()
    lib_sha = hashlib.sha256(library.read_bytes()).hexdigest()
    manifest = dict(library=str(library), library_sha256=lib_sha,
                    source=str(args.source.resolve()), source_sha256=hashlib.sha256(args.source.read_bytes()).hexdigest(),
                    warmups=warmups, repeat=args.repeat, cases=args.cases, dtype=args.dtype, layout=args.layout,
                    timing_scope='msprof_kernel_task_duration', synchronization='each_call', address_mode='fixed',
                    validation_calls=1, oj_protocol_confirmed=False, passed=False, runs=[])
    for name in ('benchmark.py', 'summarize_profile.py', 'compare_timing_modes.py'):
        manifest.setdefault('script_sha256', {})[name] = hashlib.sha256((suite / name).read_bytes()).hexdigest()
    env = dict(os.environ, OPENBLAS_NUM_THREADS='2', OMP_NUM_THREADS='2')
    def save():
        (output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    save()
    grouped = {}
    identities = {}
    soc = None
    for wi, warmup in enumerate(warmups):
        order = ['direct', 'graph', 'graph', 'direct'] if wi % 2 == 0 else ['graph', 'direct', 'direct', 'graph']
        for seq, mode in enumerate(order):
            dest = output / f'w{warmup}-{seq}-{mode}'
            dest.mkdir()
            app_path = dest / 'application.json'
            app_cmd = [sys.executable, str(suite / 'benchmark.py'), str(library), '--commit', 'timing-modes',
                       '--report', str(app_path), '--cases', args.cases, '--dtype', args.dtype, '--layout', args.layout,
                       '--warmup', str(warmup), '--repeat', str(args.repeat), '--call-mode', mode, '--real-npu']
            cmd = ['msprof', '--task-time=l0', '--output=' + str(dest / 'profile'), '--application=' + shlex.join(app_cmd)]
            run_record = dict(directory=dest.name, warmup=warmup, call_mode=mode, command=cmd)
            manifest['runs'].append(run_record)
            save()
            with (dest / 'run.log').open('w', encoding='utf-8') as log:
                try:
                    result = subprocess.run(cmd, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=240)
                    run_record['exit_code'] = result.returncode
                except subprocess.TimeoutExpired:
                    run_record['exit_code'] = 124
                    save()
                    raise
            save()
            if run_record['exit_code']:
                raise RuntimeError(f'{dest.name}采集失败，详见run.log')
            subprocess.run([sys.executable, str(suite / 'summarize_profile.py'), str(app_path), str(dest / 'profile'),
                            '--output', str(dest / 'summary.json')], env=env, check=True, timeout=60)
            app = json.loads(app_path.read_text(encoding='utf-8'))
            assert app['passed'] and app['library_sha256'] == lib_sha and app['call_mode'] == mode
            assert app['warmup'] == warmup and app['repeat'] == args.repeat
            if soc is None:
                soc = app['soc']
            assert soc == app['soc']
            for case in app['results']:
                identity = [case['shape'], case['input_sha256']]
                idx = str(case['case'])
                assert idx not in identities or identities[idx] == identity
                identities[idx] = identity
            summary = json.loads((dest / 'summary.json').read_text(encoding='utf-8'))
            for idx, vals in summary['results'].items():
                assert len(vals['samples_us']) == args.repeat
                grouped.setdefault((warmup, mode, idx), []).extend(vals['samples_us'])
            print(dest.name + '完成', flush=True)
    comparison = []
    for (warmup, mode, idx), values in grouped.items():
        assert len(values) == 2 * args.repeat
        comparison.append(dict(case=idx, warmup=warmup, call_mode=mode, count=len(values),
                               mean_us=statistics.mean(values), median_us=statistics.median(values),
                               p90_us=sorted(values)[math.ceil(0.9 * len(values)) - 1],
                               min_us=min(values), max_us=max(values), above_2us=sum(v > 2 for v in values),
                               samples_us=values))
    (output / 'comparison.json').write_text(json.dumps(dict(soc=soc, results=comparison, identities=identities,
        percentile_method='nearest_rank', timing_scope='kernel_task_duration', oj_protocol_confirmed=False),
        ensure_ascii=False, indent=2), encoding='utf-8')
    manifest['passed'] = True
    save()
    for row in comparison:
        print(json.dumps({k: v for k, v in row.items() if k != 'samples_us'}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
