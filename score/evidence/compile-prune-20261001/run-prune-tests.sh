#!/bin/bash
set -e
source /home/developer/Ascend/cann-9.0.0/set_env.sh
export LD_LIBRARY_PATH=/usr/local/Ascend/driver/lib64/common:/usr/local/Ascend/driver/lib64/driver:$LD_LIBRARY_PATH
export OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1
cd /home/developer/cann-prune-20261001
mkdir -p smoke
for i in 128 72 8 15 1287 423 1415; do
 python3 candidate-source/tests/simulator_matrix.py candidate-build/libsimulator_bridge.so --case=$i --capture --real-npu --report=smoke/case-$i.json > smoke/case-$i.log 2>&1
 echo "通用初测 $i 通过"
done
for order in ABBA BAAB; do
 mkdir -p "$order"
 for i in 0 1 2 3; do
  c=${order:$i:1}
  variant=base; hash=3acbe89
  if [ "$c" = B ]; then variant=candidate; hash=1e4fcee; fi
  msprof --task-time=l0 --output="$order/profile-$i" --application="python3 candidate-source/tests/benchmark.py $variant-build/libsimulator_bridge.so --commit=$hash --warmup=20 --repeat=50 --real-npu --report=$order/app-$i.json" > "$order/profile-$i.log" 2>&1
  python3 -c 'import json,sys; assert json.load(open(sys.argv[1]))["passed"]' "$order/app-$i.json"
  echo "$order $i $variant 15点通过"
 done
done
