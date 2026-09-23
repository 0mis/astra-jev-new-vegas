"""Observed normal barter scrolling/selection; never accepts a trade implicitly."""
import json,math,pathlib,time
from observe_game import Observer
from game_input import act,point_cursor

PREFIX={'player':'/BarterMenu/NOGLOW_BRANCH/BM_ItemsRect/BM_Items_InventoryList/',
        'merchant':'/BarterMenu/NOGLOW_BRANCH/BM_ContainerRect/BM_Container_InventoryList/'}

def read(observer):
    state=observer.snapshot()
    menus={m['name'] for m in state['menus']}
    if 'barter' not in menus:return None
    labels=next(m['labels'] for m in state['menus'] if m['name']=='barter')
    rows={side:[dict(x,price=next((v['text'] for v in labels if v['path']==x['path']+'/BM_list_template_ItemValue'),None))
                for x in labels if x['path'].startswith(prefix) and '/' not in x['path'][len(prefix):]]
          for side,prefix in PREFIX.items()}
    return {'state':state,'menus':menus,'rows':rows,'labels':labels,
            'summary':{x['path'].rsplit('/',1)[-1]:x['text'] for x in labels
                       if 'CapsLabel' in x['path'] or 'TransactionAmount' in x['path']}}

def offer(pid,recording,side,name):
    """Stage one exact item or open its quantity menu. Caller verifies quantity."""
    if side not in PREFIX:raise ValueError('Unknown barter side')
    observer=Observer(pid)
    try:
        before=read(observer)
        if not before or before['menus']!={'hud','barter'}:raise RuntimeError('Barter is not ready')
        matches=[x for x in before['rows'][side] if x['path']==PREFIX[side]+name]
        if len(matches)!=1:raise RuntimeError('Item is missing or ambiguous; inspect before selection')
        original=matches[0]
        point_cursor(pid,recording,450 if side=='player' else 850,250)
        for _ in range(35):
            current=read(observer)
            if not current or current['menus']!={'hud','barter'}:raise RuntimeError('Menu changed during scroll')
            row=next((x for x in current['rows'][side] if x['tile']==original['tile']),None)
            if not row or row['text']!=original['text']:raise RuntimeError('Item changed before selection')
            center=row['y']+row['height']/2
            if 175<=center<=490:
                point_cursor(pid,recording,(row['x']+90)*.75,center*.75)
                fresh=read(observer)
                if not fresh or not any(x['tile']==row['tile'] and x['highlighted'] for x in fresh['rows'][side]):
                    raise RuntimeError('Barter hover did not match selected item')
                act(pid,recording,button='left',seconds=.12);time.sleep(.15)
                after=read(observer)
                result={'at':time.time(),'side':side,'item':row['text'],'price':row['price'],
                        'before':before['summary'],'after':after['summary'] if after else None,
                        'menus':sorted(after['menus']) if after else None}
                with pathlib.Path('barter-actions.jsonl').open('a',encoding='utf-8') as out:out.write(json.dumps(result)+'\n')
                return result
            direction=-1 if center>490 else 1
            steps=min(5,max(1,math.ceil(abs(center-330)/156)))
            act(pid,recording,wheel=direction*steps,seconds=.12);time.sleep(.12)
            after=read(observer)
            shifted=next((x for x in after['rows'][side] if x['tile']==row['tile']),None) if after else None
            if not shifted or shifted['y']==row['y']:raise RuntimeError('Barter scroll did not move; inspect')
        raise RuntimeError('Barter scroll limit reached')
    finally:observer.close()

def quantity(pid,recording,count):
    if not isinstance(count,int) or not 1<=count<=9999:raise ValueError('Invalid quantity')
    observer=Observer(pid)
    try:
        for _ in range(50):
            state=observer.snapshot()
            menu=next((m for m in state['menus'] if m['name']=='quantity'),None)
            if not menu:raise RuntimeError('Quantity menu not present')
            value=int(next(x['text'] for x in menu['labels'] if x['path'].endswith('/QM_AmountChosen')))
            if value==count:
                assert any(x['path'].endswith('/QM_OKButton/PCShortcutLabel') and x['text']=='A)' for x in menu['labels'])
                act(pid,recording,keys=['a'],seconds=.12,
                    stop_when=lambda s:not any(m['name']=='quantity' for m in s['menus']))
                time.sleep(.15)
                after=read(observer)
                if not after or after['menus']!={'hud','barter'}:raise RuntimeError('Quantity acknowledgement not verified; inspect before retry')
                return {'quantity_staged':count,'summary':after['summary']}
            # Vanilla's quantity slider did not respond to arrow keys here.
            # These arrow positions were inspected at the pinned 1280x720 size.
            from decide_game import recording_health
            if recording_health(recording)['source_size']!=[1280,720]:raise RuntimeError('Quantity layout not verified at this size')
            point_cursor(pid,recording,481 if value>count else 795,348)
            act(pid,recording,button='left',seconds=.12);time.sleep(.12)
            fresh=observer.snapshot()
            now=next((x['text'] for m in fresh['menus'] if m['name']=='quantity' for x in m['labels'] if x['path'].endswith('/QM_AmountChosen')),None)
            if now==str(value):raise RuntimeError('Quantity did not change; inspect')
        raise RuntimeError('Quantity adjustment limit reached')
    finally:observer.close()
