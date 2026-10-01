"""比较共享库内可重定位设备ELF的核代码段；不将其等同于板上性能。"""
import hashlib,json,mmap,struct,re
from pathlib import Path
root=Path('/mnt/newdisk/cann-explore-artifacts-20260930/compile-prune')
def read(path):
 with path.open('rb') as f:
  b=mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ)
  pos=b.find(b'\x7fELF',1); assert pos>0
  h=struct.unpack_from('<16sHHIQQQIHHHHHH',b,pos); assert h[1]==1
  hs=[struct.unpack_from('<IIQQQQIIQQ',b,pos+h[6]+i*h[11]) for i in range(h[12])]
  st=hs[h[13]];strings=b[pos+st[4]:pos+st[4]+st[5]];out={}
  for sh in hs:
   name=strings[sh[0]:].split(b'\0',1)[0].decode()
   if name.startswith('.text._ZN13batch_max_sum') and 'Compute' in name:
    out[name]={'bytes':sh[5],'sha256':hashlib.sha256(b[pos+sh[4]:pos+sh[4]+sh[5]]).hexdigest()}
  return out
base=read(root/'base-build/libsimulator_bridge.so');cand=read(root/'candidate-build/libsimulator_bridge.so')
common=set(base)&set(cand);same=[k for k in common if base[k]==cand[k]];diff=[k for k in common if base[k]!=cand[k]]
def count(d):return len(set(re.sub(r'_mix_ai[cv]$','',x) for x in d))
r={'说明':'本地-g构建中可重定位设备ELF的Compute入口.text段逐字节摘要；不包含重定位解析，不代替NPU性能验证。','base_commit':'3acbe89','candidate_commit':'1e4fcee','base_kernel_count':count(base),'candidate_kernel_count':count(cand),'common_text_sections':len(common),'identical_text_sections':len(same),'different_text_sections':diff,'baseline':base,'candidate':cand}
Path('score/evidence/explore-20260930/e54-device-text.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
print({k:v for k,v in r.items() if k not in ('baseline','candidate','different_text_sections')});print('不同段数',len(diff));print('\n'.join(diff[:5]))
