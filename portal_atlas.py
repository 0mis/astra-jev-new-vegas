"""Bounded read-only paired-door atlas for Astra's current route planning.

This is game telemetry, not visual recognition or proof a place was visited.
No memory writes or game commands. Coordinates always retain their scope.
"""
import argparse, json, pathlib, time
from observe_game import Observer


def collect(observer, target_id, max_scopes=32):
    player = observer.u32(0x11DEA3C)
    active = observer.u32(player + 0x6B8)
    target = None
    for obj in observer.linked(player + 0x6BC, 100):
        if observer.u32(obj + 0x20) != 1 or observer.u32(obj + 0x10) != active:
            continue
        for item in observer.linked(obj + 0x14, 30):
            ref = observer.u32(item + 0xC)
            if ref and hex(observer.u32(ref + 0xC)) == target_id:
                target = ref
    if not target:
        raise RuntimeError('Requested target is not in the active observed quest')
    queue = [(observer.parent_cell(target), 0)]
    seen, nodes = set(), []
    while queue and len(seen) < max_scopes:
        cell, depth = queue.pop(0)
        space = observer.u32(cell + 0xC0)
        node = space or cell
        if node in seen or depth > 6:
            continue
        seen.add(node)
        scope = hex(observer.u32(node + 0xC))
        sources = [cell]
        if space:
            persistent = observer.u32(space + 0x34)
            if persistent and persistent != cell:
                sources.append(persistent)
        doors, refs, next_nodes = [], set(), []
        for source in sources:
            for ref in observer.linked(source + 0xAC, 8000):
                if ref in refs:
                    continue
                refs.add(ref)
                try:
                    base = observer.u32(ref + 0x20)
                    if observer.read(base + 4, 1)[0] != 28:
                        continue
                    extra = observer.extra(ref, 0x2B)
                    data = observer.u32(extra + 0xC) if extra else 0
                    other = observer.u32(data) if data else 0
                    other_cell = observer.parent_cell(other) if other else 0
                    if not other_cell:
                        continue
                    other_space = observer.u32(other_cell + 0xC0)
                    other_scope = hex(observer.u32((other_space or other_cell) + 0xC))
                    doors.append({'ref_id': hex(observer.u32(ref + 0xC)),
                        'name': observer.string(observer.u32(base + 0x34)),
                        'position': observer.floats(ref + 0x30, 3),
                        'destination_scope': other_scope,
                        'destination_name': observer.string(observer.u32((other_space or other_cell) + 0x1C)),
                        'opposite_ref_id': hex(observer.u32(other + 0xC)),
                        'opposite_position': observer.floats(other + 0x30, 3)})
                    if other_scope != '0xda726':
                        next_nodes.append((other_cell, depth + 1, bool(other_space)))
                except (OSError, ValueError):
                    continue
        nodes.append({'scope': scope, 'name': observer.string(observer.u32(node + 0x1C)),
                      'exterior': bool(space), 'depth': depth, 'doors': doors,
                      'refs_scanned': len(refs)})
        # Prioritize the city gateway chain over optional casino back rooms.
        queue = [(c, d) for c, d, exterior in next_nodes if exterior] + queue
        queue += [(c, d) for c, d, exterior in next_nodes if not exterior]
    return {'at': time.time(), 'source': 'Read-only actual paired quest doors; incomplete bounded graph.',
            'target_id': target_id, 'nodes': nodes}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--pid', type=int, required=True)
    parser.add_argument('--target', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    observer = Observer(args.pid)
    try:
        atlas = collect(observer, args.target)
        pathlib.Path(args.output).write_text(json.dumps(atlas, indent=2), encoding='utf-8')
        print(json.dumps({'scopes': len(atlas['nodes']), 'output': args.output}))
    finally:
        observer.close()
