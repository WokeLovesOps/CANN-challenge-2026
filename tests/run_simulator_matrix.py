"""顺序运行本地模型验证并核验应用结果、采集文件；不访问真实 NPU。"""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("library", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--application", type=Path,
                        default=Path(__file__).with_name("simulator_matrix.py"),
                        help="复用相同命令行接口的定向正确性入口")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--cases", default="0", help="默认只运行最小用例 0")
    selection.add_argument("--all-cases", action="store_true", help="显式运行完整矩阵，耗时较长")
    parser.add_argument("--timeout-minutes", type=int, default=2)
    parser.add_argument("--core-ids", default="0", help="解析核编号，以 | 分隔，默认只解析核 0")
    args = parser.parse_args()
    if not re.fullmatch(r"\d+(\|\d+)*", args.core_ids):
        parser.error("解析核编号必须是以 | 分隔的整数")
    if any(int(core) > 49 for core in args.core_ids.split("|")):
        parser.error("解析核编号必须在 0 到 49 之间")
    folder = args.output.resolve()
    folder.mkdir(parents=True, exist_ok=False, mode=0o700)
    library = args.library.resolve()
    records = []
    metadata = dict(library=str(library),
                    library_sha256=hashlib.sha256(library.read_bytes()).hexdigest(),
                    git_commit=subprocess.check_output(
                        ["git", "rev-parse", "HEAD"], text=True).strip(),
                    soc="Ascend910B3", parsed_core_ids=args.core_ids, results=records)
    environment = os.environ.copy()
    environment.update(OPENBLAS_NUM_THREADS="2", OMP_NUM_THREADS="2",
                       PYTHONDONTWRITEBYTECODE="1")
    application = args.application.resolve()
    if args.all_cases:
        import runpy
        namespace = runpy.run_path(str(application))
        shapes = namespace.get("SHAPES")
        if shapes is None:
            shapes = namespace["simulator_matrix"].SHAPES
        indices = range(len(shapes) * 8)
    else:
        indices = map(int, args.cases.split(","))
    for index in indices:
        report = folder / f"case{index}.json"
        log = folder / f"case{index}.log"
        output = folder / f"case{index}"
        command = ["msprof", "op", "simulator", "--soc-version=Ascend910B3",
                   f"--core-id={args.core_ids}", "--launch-count=4",
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
        launches = re.findall(r"Start profiling on kernel: (\S+)", text)
        record["profiled_launches"] = launches
        # 两次调用只能各启动一次 Compute；采集上限为四，能暴露旧实现多启动的问题。
        record["passed"] = bool(record.get("passed") and process.returncode == 0
                                and "SIM_CORRECTNESS_PASS" in text
                                and "timeout has reached" not in text
                                and len(launches) == 2
                                and all("Compute" in name for name in launches)
                                and len(bins) == 2
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
