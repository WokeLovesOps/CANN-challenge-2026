"""按采样入口记录的启动顺序解析 msprof l0；拒绝启动数不匹配和失败应用。"""
import argparse
import csv
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import statistics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("application", type=Path)
    parser.add_argument("profile", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    app = json.loads(args.application.read_text())
    if not app["passed"]:
        raise RuntimeError("应用未完成正确性检查，不生成成功计时报告")
    files = list(args.profile.glob("**/op_summary*.csv"))
    if len(files) != 1:
        raise RuntimeError(f"需要唯一的 op_summary，实际 {len(files)} 个")
    rows = list(csv.DictReader(files[0].open()))
    rows = [row for row in rows if "batch_max_sum" in row["Op Name"]]
    rows.sort(key=lambda row: Decimal(row["Task Start Time(us)"].strip()))
    if len(rows) != len(app["launches"]):
        raise RuntimeError(f"启动数不匹配：设备 {len(rows)}，应用 {len(app['launches'])}")
    records = {}
    for row, launch in zip(rows, app["launches"]):
        duration = float(row["Task Duration(us)"])
        if duration <= 0:
            raise RuntimeError("存在非正核函数时间")
        key = str(launch["case"])
        record = records.setdefault(key, dict(samples_us=[], warmup_us=[], validation_us=[], kernels=[]))
        phase = {"sample": "samples_us", "warmup": "warmup_us", "validation": "validation_us"}[launch["phase"]]
        record[phase].append(duration)
        if row["Op Name"] not in record["kernels"]:
            record["kernels"].append(row["Op Name"])
    for key, record in records.items():
        samples = record["samples_us"]
        record.update(median_us=statistics.median(samples), mean_us=statistics.mean(samples),
                      min_us=min(samples), max_us=max(samples), count=len(samples))
        print(f"点{key}: median={record['median_us']:.3f} us，范围={min(samples):.3f}..{max(samples):.3f}")
    output = dict(commit=app["commit"], mode="真实NPU普通msprof task-time=l0",
                  soc=app["soc"], dtype=app["dtype"], layout=app["layout"],
                  library_sha256=app["library_sha256"],
                  application_report=str(args.application), csv=str(files[0]),
                  csv_sha256=hashlib.sha256(files[0].read_bytes()).hexdigest(), results=records)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
