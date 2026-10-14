"""验证统计口径和启动序列错配拒绝逻辑，不需要NPU。"""
import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class ProfileSummaryTest(unittest.TestCase):
    def run_summary(self, durations, phases):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        root = Path(folder.name)
        app = dict(passed=True, commit='测试', soc='Ascend910_9362', dtype='bf16', layout='TN',
                   library_sha256='测试哈希', warmup=1, repeat=3, call_mode='graph',
                   launches=[dict(case=2, phase=p) for p in phases])
        (root / 'app.json').write_text(json.dumps(app), encoding='utf-8')
        with (root / 'op_summary.csv').open('w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=['Op Name', 'Task Start Time(us)', 'Task Duration(us)'])
            w.writeheader()
            # 逆序CSV验证按开始时间匹配阶段，而非依赖文件行顺序。
            for i in reversed(range(len(durations))):
                w.writerow({'Op Name': 'batch_max_sum_Test', 'Task Start Time(us)': str(i),
                            'Task Duration(us)': str(durations[i])})
        dest = root / 'summary.json'
        proc = subprocess.run([sys.executable, str(Path(__file__).with_name('summarize_profile.py')),
                               str(root / 'app.json'), str(root), '--output', str(dest)], capture_output=True)
        return proc, dest

    def test_phase_statistics(self):
        proc, dest = self.run_summary([99, 88, 1, 2, 9], ['validation', 'warmup', 'sample', 'sample', 'sample'])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(dest.read_text(encoding='utf-8'))
        self.assertEqual(data['call_mode'], 'graph')
        result = data['results']['2']
        self.assertEqual(result['samples_us'], [1, 2, 9])
        self.assertEqual(result['mean_us'], 4)
        self.assertEqual(result['median_us'], 2)
        self.assertEqual(result['p90_us'], 9)

    def test_launch_mismatch_rejected(self):
        proc, dest = self.run_summary([1], ['sample', 'sample'])
        self.assertNotEqual(proc.returncode, 0)
        self.assertFalse(dest.exists())

    def test_nonfinite_duration_rejected(self):
        proc, dest = self.run_summary([float('nan'), 1], ['sample', 'sample'])
        self.assertNotEqual(proc.returncode, 0)
        self.assertFalse(dest.exists())


if __name__ == '__main__':
    unittest.main()
