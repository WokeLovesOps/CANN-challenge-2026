#!/bin/bash
set -e
source /home/developer/Ascend/cann-9.0.0/set_env.sh
export LD_LIBRARY_PATH=/usr/local/Ascend/driver/lib64/common:/usr/local/Ascend/driver/lib64/driver:$LD_LIBRARY_PATH
export OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1
cd /home/developer/cann-prune-20261001
for order in ABBA BAAB; do
 prefix="focused-$order"
 mkdir -p "$prefix"
 for i in 0 1 2 3; do
  c=${order:$i:1}
  variant=base; hash=3acbe89
  if [ "$c" = B ]; then variant=candidate; hash=1e4fcee; fi
  msprof --task-time=l0 --output="$prefix/profile-$i" --application="python3 candidate-source/tests/benchmark.py $variant-build/libsimulator_bridge.so --commit=$hash --cases=1,4,6,7,13,14 --warmup=20 --repeat=50 --real-npu --report=$prefix/app-$i.json" > "$prefix/profile-$i.log" 2>&1
  python3 -c 'import json,sys; assert json.load(open(sys.argv[1]))["passed"]' "$prefix/app-$i.json"
  echo "$order $i $variant 6点定向复测通过"
 done
done
