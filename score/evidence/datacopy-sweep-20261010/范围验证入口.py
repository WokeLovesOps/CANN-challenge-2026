"""不初始化GM/UB的搬入诊断入口；不检查算子数学输出。"""
import argparse,ctypes as c,json,os
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('library');p.add_argument('--point',type=int,required=True);p.add_argument('--report',required=True);p.add_argument('--capture',action='store_true');a=p.parse_args()
if os.environ.get('IS_SIMULATOR_ENV','').lower()!='true':raise RuntimeError('必须使用msprof op simulator')
m=json.loads(Path('/mnt/newdisk/code/CANN-challenge/score/evidence/datacopy-sweep-20261010/实验配置.json').read_text());batch,rows,cols,k=m['shapes'][a.point-1]
if a.point==4:rows-=1
class TensorInfo(c.Structure):_fields_=[('shape',c.POINTER(c.c_int64)),('numDims',c.c_int64),('dtype',c.c_int32)]
class TensorGroupInfo(c.Structure):_fields_=[('tensors',c.POINTER(TensorInfo)),('numTensors',c.c_int64)]
rt=c.CDLL('libascendcl.so',mode=c.RTLD_GLOBAL);ptr=c.c_void_p

def bind(name,args):
 f=getattr(rt,name);f.argtypes=args;f.restype=c.c_int;return f

def ck(f,*v):
 code=f(*v)
 if code:raise RuntimeError(f'{f.__name__}: {code}')
ck(bind('aclInit',[c.c_char_p]),None);ck(bind('aclrtSetDevice',[c.c_int]),0)
stream=ptr();ck(bind('aclrtCreateStream',[c.POINTER(ptr)]),c.byref(stream))
addresses=[];malloc=bind('aclrtMalloc',[c.POINTER(ptr),c.c_size_t,c.c_int]);memcpy=bind('aclrtMemcpy',[ptr,c.c_size_t,ptr,c.c_size_t,c.c_int]);sync=bind('aclrtSynchronizeStream',[ptr]);model=ptr()
record={'point':a.point,'passed':False,'capture':a.capture,'execution':'simulator','initialization':'none'}
try:
 for _ in range(3):
  address=ptr();ck(malloc,c.byref(address),64,0);addresses.append(address)
 def read(address):
  buf=c.create_string_buffer(64);ck(memcpy,buf,64,address,64,2);return buf.raw
 before=[read(x) for x in addresses]
 shapes=[(c.c_int64*3)(batch,rows,k),(c.c_int64*3)(batch,k,cols),(c.c_int64*1)(batch)]
 infos=[TensorInfo(shape,len(shape),1 if i<2 else 0) for i,shape in enumerate(shapes)];groups=[TensorGroupInfo(c.pointer(x),1) for x in infos]
 lib=c.CDLL(str(Path(a.library).resolve()),mode=c.RTLD_GLOBAL);run=lib.run_kernel;gp=c.POINTER(TensorGroupInfo);run.argtypes=[ptr,gp,ptr,gp,ptr,gp,c.c_int64,ptr,c.c_bool,c.c_bool];run.restype=None
 for i in range(2):
  if a.capture and i==1:ck(bind('aclmdlRICaptureBegin',[ptr,c.c_int]),stream,0)
  run(addresses[0],c.byref(groups[0]),addresses[1],c.byref(groups[1]),addresses[2],c.byref(groups[2]),20,stream,False,False)
  if a.capture and i==1:
   ck(bind('aclmdlRICaptureEnd',[ptr,c.POINTER(ptr)]),stream,c.byref(model));ck(bind('aclmdlRIExecuteAsync',[ptr,ptr]),model,stream)
  ck(sync,stream)
  assert [read(x) for x in addresses]==before,'输入或输出被探针修改'
 record['passed']=True;print('PROBE_EXECUTION_PASS',flush=True)
finally:
 Path(a.report).write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
 if model.value:ck(bind('aclmdlRIDestroy',[ptr]),model)
 for x in addresses:ck(bind('aclrtFree',[ptr]),x)
 ck(bind('aclrtDestroyStream',[ptr]),stream);ck(bind('aclrtResetDevice',[c.c_int]),0);ck(bind('aclFinalize',[]))
