#!/usr/bin/env bash
# 本次远端采集命令存档；重新运行需使用独立输出目录，避免覆盖既有证据。
set -e
source /home/developer/Ascend/cann-9.0.0/set_env.sh
export LD_LIBRARY_PATH=/usr/local/Ascend/driver/lib64/common:/usr/local/Ascend/driver/lib64/driver:$LD_LIBRARY_PATH
export OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1
cd /home/developer/cann-explore-20260930/final-release
mkdir -p Build/final-check
for i in 1440 1441 1442 1443 1444 1445 1446 1447 1448 1449 1450 1451 1452 1453 1454 1455 1456 1457 1458 1459 1460 1461 1462 1463 1464 1465 1466 1467 1468 1469 1470 1471 1472 1473 1474 1475 1476 1477 1478 1479 1480 1481 1482 1483 1484 1485 1486 1487 1488 1489 1490 1491 1492 1493 1494 1495 0 7 216 223 1304 1311 1352 1359 1360 1367 1400 1407 1424 1431 1432 1439 834 842 846 858 1248 1255; do
 python3 tests/simulator_matrix.py Build/npu/libsimulator_bridge.so --case=$i --capture --real-npu --report=Build/final-check/capture-$i.json > Build/final-check/capture-$i.log 2>&1
 echo "FINAL CAPTURE $i PASS"
done
python3 tests/simulator_sequence.py Build/npu/libsimulator_bridge.so --cases=408,440,453,415,8,408,14,415,440,408 --real-npu --report=Build/final-check/sequence.json > Build/final-check/sequence.log 2>&1
echo "最终跨核序列通过"
for dtype in fp16 bf16; do
 for layout in NN NT TN TT; do
  python3 tests/benchmark.py Build/npu/libsimulator_bridge.so --commit=3acbe89 --dtype=$dtype --layout=$layout --warmup=20 --repeat=50 --real-npu --report=Build/final-check/layout-$dtype-$layout.json > Build/final-check/layout-$dtype-$layout.log 2>&1
  echo "最终全15点布局 $dtype $layout PASS"
 done
done
