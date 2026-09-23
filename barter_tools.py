"""Observed normal trading controls. No game-memory writes or automatic accepts."""
import json, pathlib, time
from observe_game import Observer
from game_input import act, point_cursor

PLAYER_LIST = '/BarterMenu/NOGLOW_BRANCH/BM_ItemsRect/BM_Items_InventoryList/'
MERCHANT_LIST = '/BarterMenu/NOGLOW_BRANCH/BM_ContainerRect/BM_Container_InventoryList/'


def read(observer):
    state = observer.snapshot()
    menu = next((m for m in state['menus'] if m['name'] == 'barter'), None)
    if not menu:
        return None
    ptr = observer.u32(0x11D8FA4)
    merchant = observer.u32(ptr + 0x80)
    base = observer.u32(merchant + 0x20)
    rows = {'player': [], 'merchant': []}
    for side, prefix in (('player', PLAYER_LIST), ('merchant', MERCHANT_LIST)):
        for label in menu['labels']:
            path = label['path']
            if not path.startswith(prefix) or '/' in path[len(prefix):]:
                continue
            row = dict(label)
            row['price_text'] = None
            # Child tiles distinguish duplicate item names and their values.
            for child in observer.linked(int(row['tile'], 16) + 4, 50):
                name, values = observer.tile(observer.u32(child + 8))
                if name == 'BM_list_template_ItemValue':
                    row['price_text'] = values.get(0xFC4)
            rows[side].append(row)
    return {'state': state, 'merchant': observer.string(observer.u32(base + 0xD4)),
            'merchant_id': hex(observer.u32(merchant + 0xC)),
            'player_caps': observer.u32(ptr + 0x8C), 'merchant_caps': observer.u32(ptr + 0x90),
            'pending_total': observer.floats(ptr + 0x84, 1)[0],
            'rows': rows, 'labels': menu['labels']}


def offer_one(observer, pid, recording, item_name, merchant_name):
    """Stage one explicitly requested owned weapon; caller must review/accept."""
    before = read(observer)
    if not before or before['merchant'] != merchant_name or abs(before['pending_total']) > .01:
        raise RuntimeError('Expected an empty trade with the specified merchant')
    if before['state']['player'].get('equipped_weapon') == item_name:
        raise RuntimeError('Do not sell the equipped weapon')
    matches = [r for r in before['rows']['player'] if r['text'] == item_name]
    if len(matches) != 1:
        raise RuntimeError('Requested owned item is missing or ambiguous')
    price = float(matches[0]['price_text'])
    if not 0 < price <= before['merchant_caps']:
        raise RuntimeError('Merchant cannot pay the displayed item price')
    for _ in range(12):
        view = read(observer)
        if not view or view['merchant_id'] != before['merchant_id'] or abs(view['pending_total']) > .01:
            raise RuntimeError('Trade changed while locating the item')
        row = next(r for r in view['rows']['player'] if r['text'] == item_name)
        y = (row['y'] + row['height'] / 2) * .75
        if 125 <= y <= 390:
            break
        # Validated 1280x720 barter list viewport, not the whole screen bounds.
        point_cursor(pid, recording, 430, 260)
        act(pid, recording, wheel=-5 if y > 390 else 5, seconds=.12)
    else:
        raise RuntimeError('Owned item did not enter the observed list viewport')
    point_cursor(pid, recording, (row['x'] + 90) * .75, y)
    fresh = read(observer)
    selected = next((r for r in fresh['rows']['player'] if r['tile'] == row['tile'] and r['highlighted']), None)
    if not selected:
        raise RuntimeError('Requested owned item is not the actual hover selection')
    # Vanilla selection must also refer to the same actual item before input.
    entry = observer.u32(0x11D8FA8)
    form = observer.u32(entry + 8) if entry else 0
    if not form or observer.read(form + 4, 1)[0] != 0x28 or observer.string(observer.u32(form + 0x34)) != item_name:
        raise RuntimeError('Barter selection is not the exact requested weapon')
    act(pid, recording, button='left', seconds=.12)
    time.sleep(.3)
    after = read(observer)
    if not after:
        raise RuntimeError('Trade left the expected menu; inspect before further input')
    result = {'at': time.time(), 'merchant': merchant_name, 'item': item_name,
              'displayed_price': price, 'pending_total': after['pending_total'],
              'player_caps_before': before['player_caps'], 'merchant_caps_before': before['merchant_caps'],
              'item_still_owned_list': any(r['text'] == item_name for r in after['rows']['player']),
              'status': 'offered_only_not_accepted'}
    with pathlib.Path('trade-events.jsonl').open('a', encoding='utf-8') as output:
        output.write(json.dumps(result) + '\n')
    return result
