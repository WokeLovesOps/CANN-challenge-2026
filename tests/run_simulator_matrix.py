"""顺序运行本地模型验证并核验应用结果、采集文件；不访问真实 NPU。"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("library", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cases", default=",".join(map(str, range(72))))
    parser.add_argument("--timeout-minutes", type=int, default=10)
    args = parser.parse_args()
    folder = args.output.resolve()
    folder.mkdir(parents=True, exist_ok=False, mode=0o700)
    library = args.library.resolve()
    records = []
    metadata = dict(library=str(library),
                    library_sha256=hashlib.sha256(library.read_bytes()).hexdigest(),
                    git_commit=subprocess.check_output(
                        ["git", "rev-parse", "HEAD"], text=True).strip(),
                    soc="Ascend910B3", results=records)
    environment = os.environ.copy()
    environment.update(OPENBLAS_NUM_THREADS="2", OMP_NUM_THREADS="2",
                       PYTHONDONTWRITEBYTECODE="1")
    application = Path(__file__).with_name("simulator_matrix.py").resolve()
    for index in map(int, args.cases.split(",")):
        report = folder / f"case{index}.json"
        log = folder / f"case{index}.log"
        output = folder / f"case{index}"
        command = ["msprof", "op", "simulator", "--soc-version=Ascend910B3",
                   "--core-id=0", "--launch-count=4",
                   f"--timeout={args.timeout_minutes}", f"--output={output}",
                   sys.executable, str(application), str(library),
                   f"--case={index}", f"--report={report}"]
        print(f"开始 case {index}", flush=True)
        with log.open("w") as stream:
            process = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT,
                                     env=environment)
        record = json.loads(report.read_text()) if report.exists() else dict(case=index, passed=False)
        text = log.read_text(errors="replace")
        bins = list(output.glob("OPPROF_*/**/visualize_data.bin"))
        record["command"] = command
        record["profiler_exitcode"] = process.returncode
        record["bins"] = [dict(path=str(path.relative_to(folder)), size=path.stat().st_size,
                               sha256=hashlib.sha256(path.read_bytes()).hexdigest())
                          for path in bins]
        # 两次调用各有 Compute / Finish，共四份 BIN；工具零退出码本身不足以证明成功。
        record["passed"] = bool(record.get("passed") and process.returncode == 0
                                and "SIM_CORRECTNESS_PASS" in text
                                and "timeout has reached" not in text
                                and len(bins) == 4
                                and all(item["size"] > 0 for item in record["bins"]))
        records.append(record)
        (folder / "summary.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
        print(f"case {index}: {'通过' if record['passed'] else '失败'}，BIN={len(bins)}", flush=True)
        if not record["passed"]:
            raise SystemExit(1)
    print(f"本轮 {len(records)} 组全部通过", flush=True)


if __name__ == "__main__":
    main()
