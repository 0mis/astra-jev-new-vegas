"""Check every frame of proposed retained spans for observed menu templates.

Supplemental edit review only. It does not inspect all raw footage, recognize
every possible menu, or grant privacy clearance. Raw files are read-only.
"""
import argparse
import hashlib
import json
import time
from pathlib import Path

import av
from PIL import Image

from build_story_timeline import merge, subtract
from detect_pause_frames import BOX, mask_frame, mask_rgb, score
from media_inventory import digest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('timeline', type=Path)
    parser.add_argument('--root', type=Path, default=Path('.'))
    parser.add_argument('--template', type=Path, action='append', required=True)
    parser.add_argument('--threshold', type=float, default=.65)
    parser.add_argument('--box', type=int, nargs=4, default=BOX,
                        help='Even pixel coordinates x1 y1 x2 y2 of the observed template region')
    parser.add_argument('--output-folder', type=Path, default=Path('postproduction/menu-review'))
    args = parser.parse_args()
    root = args.root.resolve()
    box = tuple(args.box)
    if (not (0 <= box[0] < box[2] <= 1280 and 0 <= box[1] < box[3] <= 720)
            or any(v % 2 for v in box)):
        raise ValueError('Template box must be aligned to even pixels within1280x720')
    timeline = json.loads(args.timeline.read_text(encoding='utf-8'))
    templates = [mask_rgb(Image.open(p).convert('RGB').crop(box)) for p in args.template]
    if any(t.sum() < 200 for t in templates):
        raise ValueError('Reference contains too little observed menu text')
    identity = hashlib.sha256(json.dumps({
        'revision': 1, 'box': box, 'threshold': args.threshold,
        'templates': [digest(p) for p in args.template]
    }, sort_keys=True).encode()).hexdigest()
    output = (root / args.output_folder).resolve()
    if root / 'postproduction' not in output.parents:
        raise ValueError('Review output must stay beneath private postproduction')
    output.mkdir(parents=True, exist_ok=True)
    grouped = {}
    for clip in timeline['clips']:
        item = grouped.setdefault(clip['video'], {'sha256': clip['video_sha256'], 'spans': []})
        if item['sha256'] != clip['video_sha256']:
            raise ValueError('Conflicting hashes for one source')
        item['spans'].append([clip['video_in'], clip['video_out']])
    for name, item in grouped.items():
        source = (root / name).resolve()
        if root not in source.parents or digest(source) != item['sha256']:
            raise ValueError('Source path or hash changed')
        target = output / (name.replace('/', '__') + '.json')
        old = json.loads(target.read_text(encoding='utf-8')) if target.exists() else {}
        if old.get('sha256') != item['sha256'] or old.get('detector_identity') != identity:
            old = {}
        spans = subtract(merge(item['spans'], gap=.04), old.get('scanned_spans', []))
        if not spans:
            continue
        row = {'path': name, 'sha256': item['sha256'], 'detector_identity': identity,
               'scanned_spans': old.get('scanned_spans', []),
               'menu_candidates': old.get('menu_candidates', []),
               'frames_checked': old.get('frames_checked', 0),
               'scope': 'Every decoded frame in proposed retained source spans only',
               'privacy_review': 'pending; menu matching is not a privacy review',
               'candidates_visual_review': 'pending'}
        with av.open(str(source)) as container:
            stream = container.streams.video[0]
            stream.codec_context.thread_count = 2
            first = next(container.decode(stream)).time or 0
            step = 1 / float(stream.average_rate or 30)
            for left, right in spans:
                container.seek(int((first + left) / float(stream.time_base)), stream=stream, backward=True)
                opened = None
                last = None
                for frame in container.decode(stream):
                    if frame.time is None:
                        raise ValueError('Missing frame timestamp')
                    t = frame.time - first
                    if t < left - .017:
                        continue
                    if t >= right:
                        break
                    last = t
                    row['frames_checked'] += 1
                    mask = mask_frame(frame, box=box)
                    found = max(score(mask, template) for template in templates) >= args.threshold
                    if found and opened is None:
                        opened = max(left, t)
                    if not found and opened is not None:
                        row['menu_candidates'].append([opened, t])
                        opened = None
                if last is None or last + step + .035 < right:
                    raise ValueError('Retained span extends past the decoded video')
                if opened is not None:
                    row['menu_candidates'].append([opened, min(right, last + step)])
                row['scanned_spans'] = merge(row['scanned_spans'] + [[left, right]], gap=.001)
                row['menu_candidates'] = merge(row['menu_candidates'], gap=.04)
                row['updated_at'] = time.time()
                target.write_text(json.dumps(row, indent=2), encoding='utf-8')
                (output / 'status.json').write_text(json.dumps({
                    'at': time.time(), 'path': name, 'through': right,
                    'frames_checked': row['frames_checked'], 'privacy_review': 'pending'}), encoding='utf-8')
        print(json.dumps({'source': name, 'new_spans': len(spans),
                          'menu_candidates': row['menu_candidates']}), flush=True)


if __name__ == '__main__':
    main()
