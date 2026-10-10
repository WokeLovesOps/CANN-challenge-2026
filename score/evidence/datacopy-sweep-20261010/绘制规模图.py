from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
repo=Path('/mnt/newdisk/code/CANN-challenge')
d=repo/'score/evidence/datacopy-sweep-20261010'
x=json.loads((d/'差分分析.json').read_text())
font=FontProperties(fname='/usr/share/fonts/opentype/noto/NotoSansCJK-Light.ttc')
fig,ax=plt.subplots(figsize=(9,4.8))
for mode,label in [(0,'普通COPY'),(1,'DataCopyPad（不补零）')]:
    v=sorted([t for t in x['records'] if t['name'].startswith('连续') and t['mode']==mode and not t['pad']],key=lambda t:t['line'])
    ax.plot([t['line'] for t in v],[t['delta'] for t in v],marker='o',markersize=4,label=label)
ax.axhline(.39,color='gray',linestyle='--',label='零搬运分支增量中位数（0.39μs）')
ax.set_xscale('log',base=2)
ax.set_xticks([32,128,512,2048,8192,32768,131072,196608],['32B','128B','512B','2KiB','8KiB','32KiB','128KiB','192KiB'])
ax.set_xlabel('一次连续COPY的实际有效长度',fontproperties=font)
ax.set_ylabel('相对同点前后空核均值的增量（μs）',fontproperties=font)
ax.set_title('单核、无预初始化、一次COPY后排空结束：OJ观测',fontproperties=font)
ax.legend(prop=font,fontsize=9)
ax.grid(alpha=.25)
fig.tight_layout()
fig.savefig(d/'连续COPY规模差分.png',dpi=180)
