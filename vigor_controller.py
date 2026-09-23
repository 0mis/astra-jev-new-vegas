"""Normal keyboard control of the 3D character-attribute menu.

Offsets for the page and total were verified by observed Right/Up changes.
Attribute bytes use the referenced TESActorBase/TESAttributes layout.
"""
import json,pathlib,time,uuid
from game_input import act

ROOT=pathlib.Path(__file__).resolve().parent
NAMES=['Strength','Perception','Endurance','Charisma','Intelligence','Agility','Luck']

def read(observer):
    if observer.read(0x11F308F+1074,1)==b'\0':return None
    tile=observer.u32(observer.u32(0x11F350C)+4*(1074-1001))
    if observer.tile(tile)[0]!='LoveTesterMenu':raise RuntimeError('Unexpected attribute menu')
    menu=observer.u32(tile+0x3C);page=observer.u32(menu+0x48);total=observer.u32(menu+0x58)
    player=observer.u32(0x11DEA3C);base=observer.u32(player+0x20)
    values=list(observer.read(base+0xBC,7))
    if not 1<=page<=8 or total!=40 or any(not 1<=v<=10 for v in values):
        raise RuntimeError('Unvalidated attribute layout; stop before input')
    return {'page':page,'values':values,'remaining':total-sum(values),'ready':observer.u32(menu+0x54)==1}

def step(observer,client,pid,recording):
    state=read(observer)
    if not state:return {'discarded':'Attribute menu closed'}
    if not state['ready']:
        time.sleep(.2);return {'waiting':'3D menu animation'}
    index=min(6,state['page']-1)
    options={}
    if state['page']==8:
        if state['remaining']==0:options['finish']='Accept your character attributes and leave the tester'
        options['previous']='Return to the previous attribute to revise your build'
    else:
        options['next']='View the next attribute or final review page'
        if state['page']>1:options['previous']='View the previous attribute'
        if state['remaining']>0 and state['values'][index]<10:options['increase']='Add one point to '+NAMES[index]
        if state['values'][index]>1:options['decrease']='Remove one point from '+NAMES[index]+' to reallocate elsewhere'
    options['assist']='Ask Astra if allocation controls are missing or malfunctioning'
    compact={'objective':'Choose your own SPECIAL build for completing the main story, spend all available points, then finish the review.',
             'attribute':NAMES[index],'values':dict(zip(NAMES,state['values'])),
             'page':state['page'],'points_remaining':state['remaining']}
    answer=client.request(compact,{'action':{'type':'choice','instructions':'Choose your own allocation or navigation action. No fixed build is prescribed.','criteria':options}})
    choice=answer['answers']['action']['choice'];ident=str(uuid.uuid4())
    with (ROOT/'vigor-decisions.jsonl').open('a',encoding='utf-8') as output:
        output.write(json.dumps({'at':time.time(),'state':compact,'choice':choice,'answer':answer,'request_id':ident})+'\n')
    if choice=='assist':return {'handoff':'Jev requested attribute review','attributes':state}
    if read(observer)!=state:return {'discarded':'Attribute menu changed during decision'}
    act(pid,recording,keys=[{'increase':'up','decrease':'down','next':'right','previous':'left','finish':'right'}[choice]],
        seconds=.12,request_id=ident,actor='Jev')
    if choice=='finish':
        until=time.monotonic()+3
        while read(observer) and time.monotonic()<until:time.sleep(.1)
    after=read(observer)
    if after and after['values']==state['values'] and after['page']==state['page']:
        raise RuntimeError('Attribute action had no observed effect')
    return {'choice':choice,'attributes':after}
