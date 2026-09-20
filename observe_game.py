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
MENUS={1001:"message",1002:"inventory",1003:"stats",1004:"hud",1007:"loading",1008:"container",1009:"dialogue",1012:"wait",1013:"start",1014:"lockpick",1016:"quantity",1023:"map",1026:"book",1027:"levelup",1035:"repair",1036:"appearance",1047:"credits",1048:"chargen",1051:"textedit",1053:"barter",1055:"hacking",1056:"vats",1057:"computer",1059:"tutorial",1074:"vigor",1076:"traitselect",1084:"traits"}
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
                  "width":v.get(0xFB1),"height":v.get(0xFB0),"tile":hex(p),
                  "target":v.get(0xFAF,0),"highlighted":bool(v.get(0xFC3,0))})
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
  out['interface_mode']=self.u32(self.u32(0x11D8A80)+0xC)
  visibility=self.read(0x11F308F+1001,84)
  for ident in range(1001,1085):
   name=MENUS.get(ident,'unknown_'+str(ident))
   try:
    if visibility[ident-1001]==0:continue
    tile=self.u32(base+4*(ident-1001)) if base else 0
    menus.append({"id":ident,"name":name,"labels":self.walk(tile) if tile else []})
   except (OSError,ValueError):continue
  out["menus"]=menus
  out["read_ms"]=round((time.perf_counter()-start)*1000,2)
  return out

 def world(self,state):
  """Loaded references and active quest only; read-only telemetry, not screen vision."""
  player=self.u32(0x11DEA3C);cell=self.u32(player+0x40)
  origin=state['player']['position'];yaw=state['player']['rotation_radians'][2]
  def reference(ptr):
   base=self.u32(ptr+0x20);kind=self.read(base+4,1)[0]
   if kind not in (21,28,39,42,43):return None
   name=self.string(self.u32(base+(0xD4 if kind in (42,43) else 0x34)))
   pos=self.floats(ptr+0x30,3)
   if not name or not all(math.isfinite(v) for v in pos):return None
   delta=[a-b for a,b in zip(pos,origin)]
   heading=math.atan2(delta[0],delta[1]);error=(heading-yaw+math.pi)%(2*math.pi)-math.pi
   return {'ref_id':hex(self.u32(ptr+0xC)),'name':name,'kind':kind,'position':pos,
           'distance':round(math.hypot(*delta[:2]),1),'heading_error':round(error,5),
           'same_cell':self.u32(ptr+0x40)==cell}
  nearby=[]
  for ptr in self.linked(cell+0xAC,1500):
   if ptr==player:continue
   try:
    row=reference(ptr)
    if row:nearby.append(row)
   except (OSError,ValueError):continue
  quest=self.u32(player+0x6B8);objectives=[]
  for obj in self.linked(player+0x6BC,100):
   try:
    if self.u32(obj+0x10)!=quest or self.u32(obj+0x20)!=1:continue
    targets=[]
    for item in self.linked(obj+0x14,30):
     ptr=self.u32(item+0xC)
     if ptr:
      target=reference(ptr)
      if target:targets.append(target)
    objectives.append({'text':self.string(self.u32(obj+8)),'targets':targets})
   except (OSError,ValueError):continue
  crosshair=None
  camera_position=None;camera_view=None
  try:
   interface=self.u32(0x11D8A80);ptr=self.u32(interface+0xFC)
   if ptr:crosshair=reference(ptr)
  except (OSError,ValueError):pass
  try:
   node=self.u32(cell+0xB4)
   for _ in range(12):
    if not node:break
    if self.string(self.u32(node+8))=='WorldRoot Node':
     camera=self.u32(node+0xAC);position=self.floats(camera+0x8C,3)
     if all(math.isfinite(v) for v in position) and math.dist(position,origin)<500:
      camera_position=position
      rotation=self.floats(camera+0x68,9)
      forward=[rotation[0],rotation[3],rotation[6]]
      if all(math.isfinite(v) for v in forward) and .95<math.sqrt(sum(v*v for v in forward))<1.05:
       camera_view={'yaw':math.atan2(forward[0],forward[1]),'pitch':-math.asin(max(-1,min(1,forward[2])))}
     break
    node=self.u32(node+0x18)
  except (OSError,ValueError):pass
  if camera_view:
   for row in nearby+[t for obj in objectives for t in obj['targets']]+([crosshair] if crosshair else []):
    delta=[a-b for a,b in zip(row['position'],camera_position)]
    row['heading_error']=round((math.atan2(delta[0],delta[1])-camera_view['yaw']+math.pi)%(2*math.pi)-math.pi,5)
  disabled=self.read(player+0x680,1)[0]
  controls={name:bool(disabled & bit) for bit,name in ((1,'movement'),(2,'look'),(4,'pipboy'),(8,'fight'),(16,'point_of_view'),(32,'rollover_text'),(64,'sneak'))}
  return {'quest':self.string(self.u32(quest+0x34)) if quest else None,'objectives':objectives,
          'nearby':sorted(nearby,key=lambda row:row['distance'])[:40], 'crosshair':crosshair,'camera_position':camera_position,
          'camera_view':camera_view,'disabled_controls':controls,
          'observation_source':'read-only loaded-world telemetry; not visual recognition'}

if __name__=="__main__":
 obj=Observer(int(sys.argv[1]))
 try:
  state=obj.snapshot()
  pathlib.Path(__file__).with_name("latest-observation.json").write_text(json.dumps(state,indent=2),encoding="utf-8")
  print(json.dumps(state))
 finally:obj.close()
