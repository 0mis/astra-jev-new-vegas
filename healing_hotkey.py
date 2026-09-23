"""Read the actual Stimpak binding; use only an ordinary verified hotkey."""
import time
from game_input import act

STIMPAK=0x15169

def binding(observer):
    # Public xNVSE ExtraContainerChanges/ExtraHotkey layouts, read-only.
    try:
        player=observer.u32(0x11DEA3C)
        changes=observer.extra(player,0x15)
        if not changes:return None
        data=observer.u32(changes+12)
        if not data:return None
        for entry in observer.linked(observer.u32(data),512):
            form=observer.u32(entry+8)
            if not form or observer.u32(form+12)!=STIMPAK:continue
            count=observer.u32(entry+4)
            if not 1<=count<=9999:return None
            extension=observer.u32(entry)
            if not extension:return None
            for extra_list in observer.linked(extension,32):
                node=observer.u32(extra_list+4);seen=set()
                while node and node not in seen and len(seen)<64:
                    seen.add(node)
                    if observer.read(node+4,1)[0]==0x4a:
                        index=observer.read(node+12,1)[0]
                        if index in (0,2,3,4,5,6,7):
                            return {'item':'Stimpak','form_id':hex(STIMPAK),'key':str(index+1),'count':count}
                        return None
                    node=observer.u32(node+8)
    except (OSError,ValueError):return None
    return None

def available(state,item):
    player=state.get('player') or {}
    health=player.get('health_bar_fraction_approx')
    return bool(item and item.get('form_id')==hex(STIMPAK)
        and item.get('key') in ('1','3','4','5','6','7','8')
        and 0<item.get('count',0)<=9999 and health is not None and 0<health<.85
        and player.get('life_state')==0 and state.get('interface_mode')==1
        and state.get('vats_mode',0)==0
        and not any(m['name'] not in ('hud','tutorial') for m in state.get('menus',[])))

def inventory_count(observer):
    """A complete successful inventory read distinguishes depletion from failure."""
    try:
        player=observer.u32(0x11DEA3C)
        changes=observer.extra(player,0x15)
        if not changes:return None
        data=observer.u32(changes+12)
        if not data:return None
        head=observer.u32(data)
        if not head:return None
        node=head;seen=set()
        while node:
            if node in seen or len(seen)>=512:return None
            seen.add(node);entry=observer.u32(node);node=observer.u32(node+4)
            if not entry:continue
            form=observer.u32(entry+8)
            if form and observer.u32(form+12)==STIMPAK:
                count=observer.u32(entry+4)
                return count if count<=9999 else None
        return 0
    except (OSError,ValueError):return None

def use(observer,pid,recording,request_id,*,move_forward=False):
    state=observer.snapshot();before=binding(observer)
    if not available(state,before):return {'discarded':'Stimpak binding, inventory or health changed before input'}
    act(pid,recording,keys=(['w'] if move_forward else [])+[before['key']],seconds=.12,actor='Jev',request_id=request_id,
        stop_when=lambda observed:observed.get('interface_mode')!=1 or (observed.get('player') or {}).get('life_state') in (1,2))
    until=time.monotonic()+1
    while True:
        after=binding(observer)
        # A missing binding may also mean a read failure. Only a positive
        # observed count decrease confirms consumption here.
        if after and after['key']==before['key'] and after['count']<before['count']:
            return {'input_sent':True,'input_count':1,'result':{'action':'Use one verified Stimpak hotkey',
                'changed':True,'count_before':before['count'],'count_after':after['count']}}
        if before['count']==1 and after is None and inventory_count(observer)==0:
            return {'input_sent':True,'input_count':1,'result':{'action':'Use the last verified Stimpak hotkey',
                'changed':True,'count_before':1,'count_after':0}}
        if time.monotonic()>=until:
            return {'handoff':'Stimpak hotkey sent once; consumption needs inventory verification before another use.',
                    'input_sent':True,'input_count':1}
        time.sleep(.05)
