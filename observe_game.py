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
MENUS={1001:"message",1002:"inventory",1003:"stats",1004:"hud",1007:"loading",1008:"container",1009:"dialogue",1012:"wait",1013:"start",1014:"lockpick",1016:"quantity",1023:"map",1026:"book",1027:"levelup",1035:"repair",1036:"appearance",1047:"credits",1048:"chargen",1051:"textedit",1053:"barter",1055:"hacking",1056:"vats",1057:"computer",1059:"tutorial",1074:"vigor",1075:"companion",1076:"traitselect",1084:"traits"}
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
  target=v.get(0xFAF,0);highlighted=bool(v.get(0xFC3,0))
  if name=='computers_file_template_text':
   # Terminal rows keep selection on the parent image, text on its child.
   # Preserve actual observed selection; do not infer it from row order.
   try:
    parent_name,parent_values=self.tile(self.u32(p+0x28))
    if parent_name=='computers_file_template_item':
     target=parent_values.get(0xFAF,0);highlighted=bool(parent_values.get(0xFC3,0))
   except (OSError,ValueError):pass
  found=[]
  for ident,val in v.items():
   if isinstance(val,str) and val.strip() and ident==0xFC4:
    found.append({"path":path,"text":val,"x":round(x,2),"y":round(y,2),
                  "width":v.get(0xFB1),"height":v.get(0xFB0),"tile":hex(p),
                  "target":target,"highlighted":highlighted})
  try:
   for child in self.linked(p+4,1024):
    found.extend(self.walk(self.u32(child+8),path,x,y,seen,depth+1))
  except (OSError,ValueError):pass
  return found
 def snapshot(self,include_labels=True):
  start=time.perf_counter();out={"pid":self.pid,"observed_at":time.time(),"read_only":True}
  player=self.u32(0x11DEA3C)
  if player:
   try:
    pos=self.floats(player+0x30,3);rot=self.floats(player+0x24,3);cell=self.u32(player+0x40)
    if all(math.isfinite(x) for x in pos+rot):
     out["player"]={"position":pos,"rotation_radians":rot,"ref_id":hex(self.u32(player+0xC)),
       "cell_id":hex(self.u32(cell+0xC)) if cell else None,
       "cell_name":self.string(self.u32(cell+0x1C)) if cell else None}
     # PlayerCharacter overrides the actor combat field with pcInCombat.
     out['player']['in_combat']=bool(self.read(player+0xDF0,1)[0])
     out['player']['life_state']=self.u32(player+0x108)
     out['player']['sit_sleep_state']=self.u32(player+0x1AC)
     process=self.u32(player+0x68)
     if process and self.u32(process+0x28)<=1:
      out['player']['weapon_drawn']=bool(self.read(process+0x135,1)[0])
      try:
       weapon_info=self.u32(process+0x114)
       weapon=self.u32(weapon_info+8) if weapon_info else 0
       if weapon and self.read(weapon+4,1)[0]==0x28:
        out['player']['equipped_weapon']=self.string(self.u32(weapon+0x34))
      except (OSError,ValueError):pass
      ammo=self.u32(process+0x118)
      count=self.u32(ammo+4) if ammo else None
      if count is not None and count<=100000:out['player']['loaded_ammunition']=count
      cache=self.u32(process+0x2C)
      if cache and self.u32(cache+0x44)&0x2000:
       speed=self.floats(cache+0x3C,1)[0]
       if math.isfinite(speed) and 0<speed<2000:out['player']['run_speed']=speed
   except (OSError,ValueError):out["player"]=None
  base=self.u32(0x11F350C);menus=[]
  out['interface_mode']=self.u32(self.u32(0x11D8A80)+0xC)
  out['vats_mode']=self.u32(0x11F2258)
  visibility=self.read(0x11F308F+1001,84)
  for ident in range(1001,1085):
   name=MENUS.get(ident,'unknown_'+str(ident))
   try:
    if visibility[ident-1001]==0:continue
    tile=self.u32(base+4*(ident-1001)) if base else 0
    menus.append({"id":ident,"name":name,"labels":self.walk(tile) if tile and include_labels else []})
   except (OSError,ValueError):continue
  out["menus"]=menus
  try:
   if out.get('player') and any(m['name']=='hud' for m in menus):
    hud=self.u32(0x11D96C0);name,values=self.tile(self.u32(hud+0x2C))
    width=values.get(0xFB1);texture=values.get(0xFCC,'')
    # Vanilla HUD template: 300-unit bar quantized to eight-unit tick marks.
    # This is a display estimate, not an exact actor health value.
    if name=='meter' and str(texture).lower().endswith('hud_tick_mark.dds') and isinstance(width,(float,int)) and 0<=width<=300:
     out['player']['health_bar_fraction_approx']=round(min(1,(width+4)/300),3)
  except (OSError,ValueError):pass
  out["read_ms"]=round((time.perf_counter()-start)*1000,2)
  return out

 def world(self,state,nearby_ref_ids=None):
  """Loaded references, door destinations and journal; read-only telemetry."""
  player=self.u32(0x11DEA3C);cell=self.u32(player+0x40)
  if not cell or not state.get('player') or hex(self.u32(cell+0xC))!=state['player'].get('cell_id'):
   raise RuntimeError('World changed during observation')
  space=self.u32(cell+0xC0);cells=self.loaded_cells(cell);cell_set=set(cells)
  combat_ids=set()
  combat_array=self.u32(player+0x12C)
  if combat_array:
   combat_data,combat_count=struct.unpack('<II',self.read(combat_array+4,8))
   if 0<combat_count<=64:
    for actor in struct.unpack('<'+'I'*combat_count,self.read(combat_data,combat_count*4)):
     if actor:combat_ids.add(hex(self.u32(actor+0xC)))
  origin=state['player']['position'];yaw=state['player']['rotation_radians'][2]
  def reference(ptr):
   base=self.u32(ptr+0x20);kind=self.read(base+4,1)[0]
   if kind not in (21,22,23,28,31,39,42,43):return None
   name=self.string(self.u32(base+(0xD4 if kind in (42,43) else 0x34)))
   pos=self.floats(ptr+0x30,3)
   if not name or not all(math.isfinite(v) for v in pos):return None
   if kind==31 and 'bottle' not in name.lower():return None
   if self.u32(ptr+8)&0x20:return None
   delta=[a-b for a,b in zip(pos,origin)]
   heading=math.atan2(delta[0],delta[1]);error=(heading-yaw+math.pi)%(2*math.pi)-math.pi
   parent=self.parent_cell(ptr)
   parent_space=self.u32(parent+0xC0) if parent else 0
   same_space=parent==cell or bool(space and parent_space==space)
   row={'ref_id':hex(self.u32(ptr+0xC)),'name':name,'kind':kind,'position':pos,
           'distance':round(math.hypot(*delta[:2]),1),'heading_error':round(error,5),
           'same_cell':parent==cell,'same_space':same_space,'loaded':parent in cell_set,
           'cell_id':hex(self.u32(parent+0xC)) if parent else None}
   row['worldspace_id']=hex(self.u32(parent_space+0xC)) if parent_space else None
   if kind in (42,43):
    life=self.u32(ptr+0x108);enemy=self.u32(ptr+0x128)
    row['life_state']=life;row['alive']=life not in (1,2)
    row['attacking_player']=enemy==player
    row['player_combat_target']=row['ref_id'] in combat_ids
    row['combat_target_id']=hex(self.u32(enemy+0xC)) if enemy else None
   if kind in (22,23,28,31,39,42,43):
    render=self.u32(ptr+0x64);node=self.u32(render+0x14) if render else 0
    # An actor's parent cell can be loaded while its disabled reference has
    # no live 3D. Such campaign variants are not actors we can approach/fire at.
    # Keep the reference for remote quest routing, but not as a loaded target.
    if kind in (42,43):row['loaded']=row['loaded'] and bool(node)
    bound=self.u32(node+0x20) if node else 0
    if bound:
     center=self.floats(bound,4)
     if all(math.isfinite(v) for v in center) and 0<center[3]<500 and math.dist(center[:3],pos)<500:
      row['aim_position']=center[:3];row['bounding_radius']=center[3]
    if kind==31 and 'aim_position' not in row:return None
   # Coordinates in separate interiors are unrelated, even when numerically close.
   if not same_space:row.update(distance=None,heading_error=None)
   if kind==28:
    lock=self.extra(ptr,0x2A);lock_data=self.u32(lock+0xC) if lock else 0
    row['locked']=bool(lock_data and self.read(lock_data+8,1)[0]&1)
    row['lock_level']=self.read(lock_data,1)[0] if row['locked'] else None
    extra=self.extra(ptr,0x2B)
    if extra:
     data=self.u32(extra+0xC);linked=self.u32(data) if data else 0
     destination=self.parent_cell(linked) if linked else 0
     # A paired loading door may store its lock on the opposite reference.
     linked_lock=self.extra(linked,0x2A) if linked else 0
     linked_lock_data=self.u32(linked_lock+0xC) if linked_lock else 0
     if linked_lock_data and self.read(linked_lock_data+8,1)[0]&1:
      row['locked']=True;row['lock_level']=self.read(linked_lock_data,1)[0]
     if destination:
      destination_space=self.u32(destination+0xC0)
      row['destination']={'cell_id':hex(self.u32(destination+0xC)),
                          'cell_name':self.string(self.u32(destination+0x1C)),
                          'worldspace_name':self.string(self.u32(destination_space+0x1C)) if destination_space else None,
                          'worldspace_id':hex(self.u32(destination_space+0xC)) if destination_space else None,
                          'door_ref_id':hex(self.u32(linked+0xC))}
   return row
  nearby=[]
  seen=set()
  if nearby_ref_ids is None:
   self._reference_cache={}
   for loaded_cell in cells:
    # Dense casino interiors have important actors/loading doors after the
    # first 1500 decorative refs. Keep the scan bounded without dropping them.
    for ptr in self.linked(loaded_cell+0xAC,8000 if loaded_cell==cell else 1500):
     if ptr==player or ptr in seen:continue
     seen.add(ptr)
     try:
      row=reference(ptr)
      if row and row['same_space']:
       nearby.append(row);self._reference_cache[row['ref_id']]=ptr
     except (OSError,ValueError):continue
  else:
   # During a bounded shooting action, refresh the already observed target
   # instead of scanning thousands of unrelated static references. Verify the
   # reference identity again before reading its current life/position/bounds.
   for ident in nearby_ref_ids:
    ptr=getattr(self,'_reference_cache',{}).get(ident)
    if not ptr:continue
    try:
     if hex(self.u32(ptr+0xC))!=ident:continue
     row=reference(ptr)
     if row and row['same_space'] and row['loaded']:nearby.append(row)
    except (OSError,ValueError):continue
  quest=self.u32(player+0x6B8);objectives=[];journal=[];destination_cells=[]
  for obj in self.linked(player+0x6BC,100):
   try:
    if self.u32(obj+0x20)!=1:continue
    objective_quest=self.u32(obj+0x10)
    journal.append({'quest':self.string(self.u32(objective_quest+0x34)),
                    'quest_id':hex(self.u32(objective_quest+0xC)),
                    'text':self.string(self.u32(obj+8)), 'active':objective_quest==quest})
    if objective_quest!=quest:continue
    targets=[]
    for item in self.linked(obj+0x14,30):
     ptr=self.u32(item+0xC)
     if ptr:
      target=reference(ptr)
      if target:
       targets.append(target)
       if not target['same_space'] and not target['worldspace_id']:
        destination_cells.append((self.parent_cell(ptr),self.string(self.u32(obj+8)),0))
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
    if not row['same_space']:continue
    delta=[a-b for a,b in zip(row['position'],camera_position)]
    row['heading_error']=round((math.atan2(delta[0],delta[1])-camera_view['yaw']+math.pi)%(2*math.pi)-math.pi,5)
  disabled=self.read(player+0x680,1)[0]
  controls={name:bool(disabled & bit) for bit,name in ((1,'movement'),(2,'look'),(4,'pipboy'),(8,'fight'),(16,'point_of_view'),(32,'rollover_text'),(64,'sneak'))}
  target_cells={t['cell_id'] for obj in objectives for t in obj['targets'] if not t['same_space'] and t['cell_id']}
  target_spaces={t['worldspace_id'] for obj in objectives for t in obj['targets'] if not t['same_space'] and t['worldspace_id']}
  entrances=[dict(row,quest_target=True) for row in nearby if 'destination' in row and
             (row['destination'].get('cell_id') in target_cells or row['destination'].get('worldspace_id') in target_spaces)]
  # Follow actual paired loading doors outward from an interior quest target.
  # This exposes the exterior entrance even before its grid is loaded, while
  # preserving the target's separate interior coordinate frame.
  visited=set();remote={row['ref_id']:row for row in entrances}
  while destination_cells and len(visited)<8:
   destination,objective_text,depth=destination_cells.pop(0)
   if not destination or destination in visited or depth>3:continue
   visited.add(destination)
   try:
    for door in self.linked(destination+0xAC,8000):
     base=self.u32(door+0x20)
     if self.read(base+4,1)[0]!=28:continue
     teleport=self.extra(door,0x2B);data=self.u32(teleport+0xC) if teleport else 0
     other=self.u32(data) if data else 0
     if not other:continue
     row=reference(other)
     if not row:continue
     if row['same_space']:
      if camera_view:
       delta=[a-b for a,b in zip(row['position'],camera_position)]
       row['heading_error']=round((math.atan2(delta[0],delta[1])-camera_view['yaw']+math.pi)%(2*math.pi)-math.pi,5)
      remote[row['ref_id']]=dict(row,quest_target=True,objective_text=objective_text,route_source='observed paired quest doors')
     elif not row['worldspace_id']:
      destination_cells.append((self.parent_cell(other),objective_text,depth+1))
   except (OSError,ValueError):continue
  entrances=list(remote.values())
  if self.u32(player+0x40)!=cell:raise RuntimeError('World changed during observation')
  return {'quest':self.string(self.u32(quest+0x34)) if quest else None,'objectives':objectives,
          'journal':journal,'travel_targets':sorted(entrances,key=lambda row:row['distance']),
          'worldspace_id':hex(self.u32(space+0xC)) if space else None,
          'worldspace_name':self.string(self.u32(space+0x1C)) if space else None,
          'cell_id':state['player']['cell_id'],'loaded_cell_count':len(cells),
          'nearby':sorted(nearby,key=lambda row:(not row.get('attacking_player',False),row['distance']))[:40],
          'actors':[row for row in nearby if row['kind'] in (42,43) and row['same_space'] and row['loaded']],
          'terminals':[row for row in nearby if row['kind']==23 and row['same_space'] and row['loaded']],
          'doors':[row for row in nearby if row['kind']==28 and row['same_space'] and row['loaded']],
          'furniture':[row for row in nearby if row['kind']==39 and row['same_space'] and row['loaded']],
          'crosshair':crosshair,'camera_position':camera_position,
          'camera_view':camera_view,'disabled_controls':controls,
          'observation_source':'read-only loaded-world telemetry; not visual recognition'}

 def extra(self,reference,kind):
  """Find a bounded BSExtraData entry without invoking any game functions."""
  node=self.u32(reference+0x48);seen=set()
  while node and node not in seen and len(seen)<64:
   seen.add(node)
   if self.read(node+4,1)[0]==kind:return node
   node=self.u32(node+8)
  return None

 def parent_cell(self,reference):
  cell=self.u32(reference+0x40)
  if not cell:
   persistent=self.extra(reference,0x0C)
   if persistent:cell=self.u32(persistent+0xC)
  return cell

 def loaded_cells(self,cell):
  space=self.u32(cell+0xC0)
  if not space:return [cell]
  tes=self.u32(0x11DEA10);grid=self.u32(tes+8)
  size=self.u32(grid+0xC);data=self.u32(grid+0x10)
  if not 1<=size<=11:raise RuntimeError('Loaded exterior grid outside bounds')
  result=[cell]
  for ptr in struct.unpack('<'+'I'*(size*size),self.read(data,4*size*size)):
   if ptr and ptr not in result and self.u32(ptr+0xC0)==space and self.read(ptr+0x26,1)[0]==6:
    result.append(ptr)
  return result

if __name__=="__main__":
 obj=Observer(int(sys.argv[1]))
 try:
  state=obj.snapshot()
  pathlib.Path(__file__).with_name("latest-observation.json").write_text(json.dumps(state,indent=2),encoding="utf-8")
  print(json.dumps(state))
 finally:obj.close()
