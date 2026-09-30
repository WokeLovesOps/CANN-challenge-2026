"""从指定提交生成只含大矩阵TN特化的诊断副本，禁止用于完整性能结论。"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("commit")
parser.add_argument("output", type=Path)
args = parser.parse_args()
if args.output.exists():
    parser.error("输出目录已存在，拒绝覆盖")
commit = subprocess.check_output(["git", "rev-parse", args.commit], text=True).strip()

def source(path):
    return subprocess.check_output(["git", "show", f"{commit}:{path}"], text=True)

original = source("src/kernel.asc")
text = original
# 保留全部核定义，移除Host对无关小矩阵分支的引用，避免实例化。
start = text.index("    const bool smallVector =", text.index('extern "C" void run_kernel'))
end = text.index("    ShapeKey shapeKey =", start)
text = text[:start] + text[end:]
start = text.index("void LaunchByShapeKey(")
body_start = text.index("{", start)
depth = 1
end = body_start + 1
while depth:
    depth += (text[end] == "{") - (text[end] == "}")
    end += 1
body = '''{
    // 诊断副本只编译TN大矩阵，其他布局/分发立即拒绝。
    if (!transA || transB) {
        throw std::invalid_argument("诊断副本只支持TN布局");
    }
'''
for key, rows, cols in [("LARGE_BALANCED", 128, 256), ("LARGE_TALL", 256, 128)]:
    body += f'''    if (key == ShapeKey::{key}) {{
        if (splitN) {{
            Compute<T, true, false, true, {rows}, {cols}, false>
                <<<params.cores, nullptr, stream>>>(x1, x2, scratch, partial, y, workspace, params);
        }} else {{
            Compute<T, true, false, false, {rows}, {cols}, false>
                <<<params.cores, nullptr, stream>>>(x1, x2, scratch, partial, y, workspace, params);
        }}
        return;
    }}
'''
body += '    throw std::invalid_argument("诊断副本只支持大矩阵路径");\n}'
text = text[:body_start] + body + text[end:]
(args.output / "src").mkdir(parents=True)
(args.output / "tests").mkdir()
(args.output / "src/kernel.asc").write_text(text)
for path in ["tests/CMakeLists.txt", "tests/main.asc", "tests/simulator_bridge.asc", "tests/simulator_matrix.py",
             "tests/correctness.py", "tests/simulator.py", "tests/benchmark.py"]:
    (args.output / path).write_text(source(path))
manifest = dict(源码提交=commit, 原始核SHA256=hashlib.sha256(original.encode()).hexdigest(),
                诊断核SHA256=hashlib.sha256(text.encode()).hexdigest(),
                差异="仅裁剪Host分发，保留128x256与256x128的双类型TN及分片/非分片，核函数内容不改；不支持完整性能测试")
(args.output / "diagnostic-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(manifest, ensure_ascii=False))
