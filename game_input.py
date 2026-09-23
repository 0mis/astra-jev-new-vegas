"""Bounded normal keyboard/mouse input for the verified foreground game only.

User authorized this dedicated controller after the standard desktop input pilot.
This module never writes game memory, changes quests or executes game commands.
"""
import argparse,ctypes as c,ctypes.wintypes as w,json,pathlib,time,msvcrt,uuid
from observe_game import Observer
from decide_game import recording_health, read_recording_state

ROOT=pathlib.Path(__file__).resolve().parent
u=c.WinDLL('user32',use_last_error=True)
ULONG_PTR=c.c_size_t
class MOUSEINPUT(c.Structure):
 _fields_=[('dx',w.LONG),('dy',w.LONG),('mouseData',w.DWORD),('dwFlags',w.DWORD),('time',w.DWORD),('dwExtraInfo',ULONG_PTR)]
class KEYBDINPUT(c.Structure):
 _fields_=[('wVk',w.WORD),('wScan',w.WORD),('dwFlags',w.DWORD),('time',w.DWORD),('dwExtraInfo',ULONG_PTR)]
class HARDWAREINPUT(c.Structure):
 _fields_=[('uMsg',w.DWORD),('wParamL',w.WORD),('wParamH',w.WORD)]
class UNION(c.Union):
 _fields_=[('mi',MOUSEINPUT),('ki',KEYBDINPUT),('hi',HARDWAREINPUT)]
class INPUT(c.Structure):
 _anonymous_=('data',)
 _fields_=[('type',w.DWORD),('data',UNION)]
u.SendInput.argtypes=[w.UINT,c.POINTER(INPUT),c.c_int];u.SendInput.restype=w.UINT
u.GetForegroundWindow.restype=w.HWND
u.GetWindowThreadProcessId.argtypes=[w.HWND,c.POINTER(w.DWORD)]
u.GetWindowThreadProcessId.restype=w.DWORD
KEYS={'escape':(1,False),'1':(2,False),'2':(3,False),'3':(4,False),'4':(5,False),
 '5':(6,False),'6':(7,False),'7':(8,False),'8':(9,False),'9':(10,False),'0':(11,False),
 'backspace':(14,False),'tab':(15,False),'q':(16,False),'w':(17,False),
 'e':(18,False),'r':(19,False),'t':(20,False),'y':(21,False),'u':(22,False),
 'i':(23,False),'o':(24,False),'p':(25,False),'enter':(28,False),'ctrl':(29,False),
 'a':(30,False),'s':(31,False),'d':(32,False),'f':(33,False),'g':(34,False),
 'h':(35,False),'j':(36,False),'k':(37,False),'l':(38,False),'shift':(42,False),
 'z':(44,False),'x':(45,False),'c':(46,False),'v':(47,False),'b':(48,False),
 'n':(49,False),'m':(50,False),'space':(57,False),'capslock':(58,False),
 'f1':(59,False),'f2':(60,False),'f3':(61,False),'f5':(63,False),'f9':(67,False),'up':(72,True),'left':(75,True),
 'right':(77,True),'down':(80,True),'home':(71,True),'end':(79,True),'delete':(83,True)}
BUTTONS={'left':(0x0002,0x0004),'right':(0x0008,0x0010)}

def foreground_pid():
 p=w.DWORD();u.GetWindowThreadProcessId(u.GetForegroundWindow(),c.byref(p));return p.value
def send(event):
 if u.SendInput(1,c.byref(event),c.sizeof(INPUT))!=1:raise c.WinError(c.get_last_error())
def key_event(name,up=False):
 scan,extended=KEYS[name]
 return INPUT(type=1,ki=KEYBDINPUT(0,scan,0x0008|(0x0001 if extended else 0)|(0x0002 if up else 0),0,0))
def mouse_event(flags,dx=0,dy=0,data=0):
 return INPUT(type=0,mi=MOUSEINPUT(dx,dy,data&0xFFFFFFFF,flags,0,0))

def pause_world(pid):
 """Emergency normal Escape, allowed when capture fails; never toggles an open menu."""
 observer=Observer(pid); lock=(ROOT/'controller.lock').open('a+b'); acquired=False
 result={'at':time.time(),'pid':pid,'purpose':'pause after controller handoff','verified_paused':False}
 def visible_pause(state):
  return state.get('interface_mode')==2 and any(menu['name']=='start' and any(x['text']=='Continue' for x in menu['labels']) for menu in state['menus'])
 def stable_pause(state):
  if not visible_pause(state):return False,state
  for _ in range(2):
   time.sleep(.25);state=observer.snapshot()
   if not visible_pause(state):return False,state
  return True,state
 try:
  lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);acquired=True
  if foreground_pid()!=pid:raise RuntimeError('Cannot pause a game without foreground ownership')
  # Loading and autosaving can swallow the first Escape. Reobserve before
  # each bounded retry, and never send Escape once any Start menu appears.
  for attempt in range(3):
   state=observer.snapshot()
   confirmed,state=stable_pause(state)
   if confirmed:break
   names={menu['name'] for menu in state['menus']}
   if 'start' in names:
    time.sleep(.25);continue
   if names-{'hud','tutorial'} or not (state.get('player') or {}).get('cell_id'):
    raise RuntimeError('Unknown menu or cinematic state; no blind Escape')
   if foreground_pid()!=pid:raise RuntimeError('Game lost foreground before pause retry')
   result['escape_attempts']=attempt+1
   try:
    send(key_event('escape'));time.sleep(.1)
   finally:send(key_event('escape',True))
   until=time.monotonic()+1.5
   while time.monotonic()<until:
    time.sleep(.1);state=observer.snapshot()
    if visible_pause(state):break
   confirmed,state=stable_pause(state)
   if confirmed:break
  result['verified_paused']=confirmed
  if not result['verified_paused']:raise RuntimeError('Pause menu was not observed')
 except Exception as exc:result['error']=f'{type(exc).__name__}: {exc}'
 finally:
  observer.close()
  if acquired:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
  lock.close()
  with (ROOT/'safety-events.jsonl').open('a',encoding='utf-8') as output:output.write(json.dumps(result)+'\n')
 return result

def point_cursor(pid,recording,x,y,actor='Astra'):
 """Relative menu mouse movement with feedback from the observed game cursor."""
 if not 0<=x<1280 or not 0<=y<720:raise ValueError('Cursor target outside validated client size')
 observer=Observer(pid);gains=[4.,4.]
 def position():
  interface=observer.u32(0x11D8A80)
  return [observer.floats(interface+0x38,1)[0],observer.floats(interface+0x40,1)[0]]
 try:
  for _ in range(24):
   before=position();errors=[x-before[0],y-before[1]]
   if max(abs(v) for v in errors)<3:return {'cursor':before,'target':[x,y]}
   moves=[max(-25,min(25,round(error/gain))) for error,gain in zip(errors,gains)]
   for i in range(2):
    if abs(errors[i])>=3 and moves[i]==0:moves[i]=1 if errors[i]>0 else -1
   act(pid,recording,dx=moves[0],dy=moves[1],seconds=.1,actor=actor)
   after=position()
   for i in range(2):
    if moves[i] and (after[i]-before[i])/moves[i]>.1:
     gains[i]=max(.5,min(15,(after[i]-before[i])/moves[i]))
  raise RuntimeError('Menu cursor did not converge to its observed target')
 finally:observer.close()

def act(pid,recording,keys=(),seconds=.15,dx=0,dy=0,button=None,request_id=None,actor='Astra',stop_when=None,wheel=0,drag=False,poll_menu_labels=True):
 keys=list(keys)
 if not .05<=seconds<=3:raise ValueError('Key hold must be 0.05 to 3 seconds')
 if len(keys)>3 or len(set(keys))!=len(keys) or any(key not in KEYS for key in keys):raise ValueError('Unknown or excessive keys')
 if any(not isinstance(v,int) or abs(v)>1500 for v in (dx,dy)):raise ValueError('Mouse movement exceeds bounds')
 if button not in (None,*BUTTONS):raise ValueError('Unknown mouse button')
 if drag and (button!='left' or not (dx or dy)):raise ValueError('Map dragging requires left button and movement')
 if not isinstance(wheel,int) or abs(wheel)>5:raise ValueError('Wheel movement must be at most five notches')
 if not keys and not dx and not dy and not button and not wheel:raise ValueError('No input requested')
 if actor not in ('Astra','Jev'):raise ValueError('Unknown decision actor')
 # An exclusive one-byte lock prevents competing controller processes.
 lock=(ROOT/'controller.lock').open('a+b');lock.seek(0)
 if not lock.read(1):lock.write(b'0');lock.flush()
 lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
 observer=None;held=[];mouse_held=False;capture_checked_at=0;capture_health=None
 request_id=request_id or str(uuid.uuid4())
 row={'at':time.time(),'request_id':request_id,'actor':actor,'keys':keys,
      'seconds':seconds,'dx':dx,'dy':dy,'button':button,'wheel':wheel,'drag':drag,'phase':'dispatching','executor':'game_input'}
 def log():
  with (ROOT/'actions.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(row)+'\n')
 def guard():
  nonlocal capture_checked_at,capture_health
  if foreground_pid()!=pid:raise RuntimeError('Game lost foreground; input stopped')
  if (ROOT/'controller.stop').exists():raise RuntimeError('Controller stop requested')
  # Check focus/stop on every tick, but avoid rereading identical encoder files
  # several times in one input frame. Capture still gets four checks per second.
  if capture_health is None or time.monotonic()-capture_checked_at>=.25:
   capture_health=recording_health(recording);capture_checked_at=time.monotonic()
   if capture_health.get('game_pid')!=pid:raise RuntimeError('Recorder is not pinned to this game process')
  return capture_health
 try:
  # Opens only the known FalloutNV.exe with read/query permissions.
  observer=Observer(pid);before=observer.snapshot(include_labels=poll_menu_labels);health=guard()
  row.update(observed_at=before['observed_at'],recording=health);log()
  if drag and not any(m['name']=='map' for m in before['menus']):raise RuntimeError('Dragging is restricted to the observed game map')
  if (dx or dy) and not drag:send(mouse_event(0x0001,dx,dy))
  if wheel:send(mouse_event(0x0800,data=wheel*120))
  for key in keys:
   guard();send(key_event(key));held.append(key)
  if button:
   guard();send(mouse_event(BUTTONS[button][0]));mouse_held=True
  if drag:
   time.sleep(.1);guard();send(mouse_event(0x0001,dx,dy))
  end=time.perf_counter()+seconds
  while time.perf_counter()<end:
   time.sleep(min(.05,max(0,end-time.perf_counter())));guard()
   if stop_when is not None and stop_when(observer.snapshot(include_labels=poll_menu_labels)):
    row['released_on_observed_state_change']=True
    break
  row['phase']='input_sent'
 except BaseException as exc:
  row.update(phase='failed_or_uncertain',error=f'{type(exc).__name__}: {exc}')
  raise
 finally:
  # Releases must happen even if focus was lost while a key was held.
  release_errors=[]
  for key in reversed(held):
   try:send(key_event(key,True))
   except OSError as exc:release_errors.append(str(exc))
  if mouse_held:
   try:send(mouse_event(BUTTONS[button][1]))
   except OSError as exc:release_errors.append(str(exc))
  row.update(finished_at=time.time(),release_errors=release_errors)
  try:log()
  finally:
   if observer:observer.close()
   lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()
  if release_errors:raise RuntimeError('Input release failed: '+'; '.join(release_errors))
 time.sleep(.08)
 observer=Observer(pid)
 try:after=observer.snapshot(include_labels=poll_menu_labels)
 finally:observer.close()
 (ROOT/'latest-observation.json').write_text(json.dumps(after,indent=2),encoding='utf-8')
 return {'action':row,'after':after}

def main():
 p=argparse.ArgumentParser();p.add_argument('--pid',type=int,required=True)
 p.add_argument('--recording',required=True);p.add_argument('--key',action='append',default=[])
 p.add_argument('--seconds',type=float,default=.15);p.add_argument('--dx',type=int,default=0)
 p.add_argument('--dy',type=int,default=0);p.add_argument('--button',choices=list(BUTTONS))
 p.add_argument('--request-id');p.add_argument('--actor',choices=['Astra','Jev'],default='Astra')
 args=p.parse_args();result=act(args.pid,args.recording,args.key,args.seconds,args.dx,args.dy,args.button,args.request_id,args.actor)
 print(json.dumps(result));return 0
if __name__=='__main__':raise SystemExit(main())
