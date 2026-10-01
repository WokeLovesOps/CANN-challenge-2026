#!/usr/bin/env bash
# 本次远端采集命令存档；重新运行需使用独立输出目录，避免覆盖既有证据。
set -e
source /home/developer/Ascend/cann-9.0.0/set_env.sh
export LD_LIBRARY_PATH=/usr/local/Ascend/driver/lib64/common:/usr/local/Ascend/driver/lib64/driver:$LD_LIBRARY_PATH
export OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1
cd /home/developer/cann-explore-20260930
mkdir -p baab-final-vs-e01-20-50
order=(final-release e01-aligned e01-aligned final-release)
for i in 0 1 2 3; do
    candidate=${order[$i]}
    commit=b87e612
    if [ "$candidate" = final-release ]; then commit=3acbe89; fi
    msprof --task-time=l0 --output="baab-final-vs-e01-20-50/profile-$i" --application="python3 final-tests/tests/benchmark.py $candidate/Build/npu/libsimulator_bridge.so --commit=$commit --warmup=20 --repeat=50 --real-npu --report=baab-final-vs-e01-20-50/app-$i.json" > "baab-final-vs-e01-20-50/profile-$i.log" 2>&1
    python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); assert d["passed"]' "baab-final-vs-e01-20-50/app-$i.json"
    echo "BAAB $i $candidate 全15规模通过"
done
