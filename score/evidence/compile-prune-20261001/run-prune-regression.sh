#!/bin/bash
set -e
source /home/developer/Ascend/cann-9.0.0/set_env.sh
export LD_LIBRARY_PATH=/usr/local/Ascend/driver/lib64/common:/usr/local/Ascend/driver/lib64/driver:$LD_LIBRARY_PATH
export OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1
cd /home/developer/cann-prune-20261001
mkdir -p regression
for i in 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 56 57 58 59 60 61 62 63 64 65 66 67 68 69 70 71 72 73 74 75 76 77 78 79 80 81 82 83 84 85 86 87 120 121 122 123 124 125 126 127 128 129 130 131 132 133 134 135 136 137 138 139 140 141 142 143 152 153 154 155 156 157 158 159 160 161 162 163 164 165 166 167 168 169 170 171 172 173 174 175 176 177 178 179 180 181 182 183 184 185 186 187 188 189 190 191 200 201 202 203 204 205 206 207 208 209 210 211 212 213 214 215 256 257 258 259 260 261 262 263 336 337 338 339 340 341 342 343 424 425 426 427 428 429 430 431 520 521 522 523 524 525 526 527 536 537 538 539 540 541 542 543 544 545 546 547 548 549 550 551 552 553 554 555 556 557 558 559 560 561 562 563 564 565 566 567 576 577 578 579 580 581 582 583 592 593 594 595 596 597 598 599 600 601 602 603 604 605 606 607 608 609 610 611 612 613 614 615 616 617 618 619 620 621 622 623 1080 1081 1082 1083 1084 1085 1086 1087 1104 1105 1106 1107 1108 1109 1110 1111 1112 1113 1114 1115 1116 1117 1118 1119; do
 python3 candidate-source/tests/simulator_matrix.py candidate-build/libsimulator_bridge.so --case=$i --capture --real-npu --report=regression/case-$i.json > regression/case-$i.log 2>&1
 echo "边界 $i 通过"
done
for i in {0..31}; do
 python3 candidate-source/tests/generic_fallback.py candidate-build/libsimulator_bridge.so --case=$i --capture --real-npu --report=regression/generic-$i.json > regression/generic-$i.log 2>&1
 echo "新增通用边界 $i 通过"
done
python3 candidate-source/tests/simulator_sequence.py candidate-build/libsimulator_bridge.so --cases=408,440,453,415,8,408,14,415,440,408 --real-npu --report=regression/sequence.json > regression/sequence.log 2>&1
for dtype in fp16 bf16; do
 for layout in NN NT TN TT; do
  python3 candidate-source/tests/benchmark.py candidate-build/libsimulator_bridge.so --commit=1e4fcee --dtype=$dtype --layout=$layout --warmup=20 --repeat=50 --real-npu --report=regression/layout-$dtype-$layout.json > regression/layout-$dtype-$layout.log 2>&1
  echo "全15点 $dtype $layout 通过"
 done
done
