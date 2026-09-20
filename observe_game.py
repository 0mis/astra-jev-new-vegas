"""Read-only New Vegas 1.4.0.525 observer based on xNVSE public layouts.
No memory writes, injection, quest changes, or game modifications.
"""
import ctypes as c,ctypes.wintypes as w,struct,json,time,sys,pathlib,math
k=c.WinDLL("kernel32",use_last_error=True)
k.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];k.OpenProcess.restype=w.HANDLE
k.ReadProcessMemory.argtypes=[w.HANDLE,c.c_void_p,c.c_void_p,c.c_size_t,c.POINTER(c.c_size_t)]
k.ReadProcessMemory.restype=w.BOOL
k.CloseHandle.argtypes=[w.HANDLE]
k.QueryFullProcessImageNameW.argtypes=[w.HANDLE,w.DWORD,w.LPWSTR,c.POINTER(w.DWORD)]
EXPECTED=pathlib.Path(r"C:\Program Files (x86)\Steam\steamapps\common\Fallout New Vegas\FalloutNV.exe")
MENUS={1001:"message",1002:"inventory",1003:"stats",1004:"hud",1007:"loading",1008:"container",1009:"dialogue",1012:"wait",1013:"start",1014:"lockpick",1016:"quantity",1023:"map",1026:"book",1027:"levelup",1035:"repair",1036:"appearance",1047:"credits",1048:"chargen",1051:"textedit",1053:"barter",1055:"hacking",1056:"vats",1057:"computer",1059:"tutorial",1074:"vigor"}
class Observer:
 def __init__(self,pid):
  self.pid=int(pid);self.h=k.OpenProcess(0x1010,False,self.pid)
  if not self.h:raise c.WinError(c.get_last_error())
  buf=c.create_unicode_buffer(32768);n=w.DWORD(len(buf))
  if not k.QueryFullProcessImageNameW(self.h,0,buf,c.byref(n)):raise c.WinError(c.get_last_error())
  if pathlib.Path(buf.value)!=EXPECTED:raise RuntimeError("Refusing non-game process")
  if self.read(0x400000,2)!=b"MZ":raise RuntimeError("Unexpected executable base")
 def close(self):k.CloseHandle(self.h)
 def read(self,address,n):
  if address<0x10000 or address+n>0x80000000 or not 0<n<=1048576:raise ValueError("Invalid bounded read")
  buf=c.create_string_buffer(n);done=c.c_size_t()
  if not k.ReadProcessMemory(self.h,c.c_void_p(address),buf,n,c.byref(done)) or done.value!=n:raise OSError("Game state unavailable")
  return buf.raw
 def u32(self,a):return struct.unpack("<I",self.read(a,4))[0]
 def floats(self,a,n):return list(struct.unpack("<"+"f"*n,self.read(a,n*4)))
 def string(self,p,limit=512):
  if not p:return ""
  # Read only through the next page boundary, avoiding an unnecessary failed read.
  raw=self.read(p,min(limit,4096-(p%4096)))
  return raw.split(b"\0",1)[0].decode("cp1252",errors="replace")
 def linked(self,head,limit=1024):
  seen=set();node=head
  while node and node not in seen and len(seen)<limit:
   seen.add(node);data,nxt=struct.unpack("<II",self.read(node,8))
   if data:yield data
   node=nxt
 def tile(self,p):
  base=self.read(p,0x38);arr,size=struct.unpack_from("<II",base,0x14)
  vals={}
  if size>512:raise ValueError("Invalid tile value count")
  if size:
   ptrs=struct.unpack("<"+"I"*size,self.read(arr,4*size))
   for v in ptrs:
    if not v:continue
    raw=self.read(v,20);ident,_,num,st,_=struct.unpack("<IIfII",raw)
    vals[ident]=self.string(st,1024) if st else num
  return self.string(struct.unpack_from("<I",base,0x20)[0]),vals
 def walk(self,p,path="",x=0,y=0,seen=None,depth=0):
  if seen is None:seen=set()
  if not p or p in seen or len(seen)>=3000 or depth>40:return []
  seen.add(p)
  try:name,v=self.tile(p)
  except (OSError,ValueError):return []
  if v.get(0xFA3,1)==0:return []
  path=path+"/"+name
  x+=v.get(0xFA1,0);y+=v.get(0xFA2,0)
  found=[]
  for ident,val in v.items():
   if isinstance(val,str) and val.strip() and ident==0xFC4:
    found.append({"path":path,"text":val,"x":round(x,2),"y":round(y,2),
                  "width":v.get(0xFB1),"height":v.get(0xFB0),"tile":hex(p)})
  try:
   for child in self.linked(p+4,1024):
    found.extend(self.walk(self.u32(child+8),path,x,y,seen,depth+1))
  except (OSError,ValueError):pass
  return found
 def snapshot(self):
  start=time.perf_counter();out={"pid":self.pid,"observed_at":time.time(),"read_only":True}
  player=self.u32(0x11DEA3C)
  if player:
   try:
    pos=self.floats(player+0x30,3);rot=self.floats(player+0x24,3);cell=self.u32(player+0x40)
    if all(math.isfinite(x) for x in pos+rot):
     out["player"]={"position":pos,"rotation_radians":rot,"ref_id":hex(self.u32(player+0xC)),
       "cell_id":hex(self.u32(cell+0xC)) if cell else None,
       "cell_name":self.string(self.u32(cell+0x1C)) if cell else None}
   except (OSError,ValueError):out["player"]=None
  base=self.u32(0x11F350C);menus=[]
  for ident,name in MENUS.items():
   try:
    if self.read(0x11F308F+ident,1)==b"\0":continue
    tile=self.u32(base+4*(ident-1001)) if base else 0
    menus.append({"id":ident,"name":name,"labels":self.walk(tile) if tile else []})
   except (OSError,ValueError):continue
  out["menus"]=menus
  out["read_ms"]=round((time.perf_counter()-start)*1000,2)
  return out

if __name__=="__main__":
 obj=Observer(int(sys.argv[1]))
 try:
  state=obj.snapshot()
  pathlib.Path(__file__).with_name("latest-observation.json").write_text(json.dumps(state,indent=2),encoding="utf-8")
  print(json.dumps(state))
 finally:obj.close()
