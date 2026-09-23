"""Find menu cuts in every decoded frame; produces review candidates, never edits raw media."""
import argparse
import json
import time
from pathlib import Path

import av
import numpy as np
from PIL import Image

from media_inventory import digest, media_paths


BOX = (1148, 240, 1260, 482)


def mask_rgb(image):
    rgb = np.asarray(image, dtype=np.float32)
    r, g, b = (rgb[:, :, i] for i in range(3))
    y = 16 + .257 * r + .504 * g + .098 * b
    u = 128 - .148 * r - .291 * g + .439 * b
    v = 128 + .439 * r - .368 * g - .071 * b
    return (y > 110) & (u < 110) & (v > 145)


def mask_frame(frame, box=BOX):
    if (frame.width, frame.height) != (1280, 720):
        raise ValueError('Unvalidated video resolution; no automatic cuts')
    x1, y1, x2, y2 = box
    if frame.format.name != 'yuv420p':
        return mask_rgb(frame.to_image().convert('RGB').crop(box))
    plane = frame.planes[0]
    y = np.frombuffer(plane, np.uint8).reshape(plane.height, plane.line_size)[y1:y2, x1:x2]
    chroma = []
    for plane in frame.planes[1:3]:
        crop = np.frombuffer(plane, np.uint8).reshape(plane.height, plane.line_size)[y1//2:y2//2, x1//2:x2//2]
        chroma.append(crop.repeat(2, 0).repeat(2, 1))
    return (y > 110) & (chroma[0] < 110) & (chroma[1] > 145)


def score(mask, template):
    denominator = int(mask.sum()) + int(template.sum())
    return 2 * int(np.count_nonzero(mask & template)) / max(denominator, 1)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, default=Path('.'))
    p.add_argument('--template', type=Path, action='append', required=True)
    p.add_argument('--threshold', type=float, default=.65)
    p.add_argument('--limit', type=int)
    p.add_argument('--check-image', type=Path, action='append')
    p.add_argument('--only', action='append', help='Exact root-relative media path')
    p.add_argument('--include-recovered', action='store_true')
    p.add_argument('--status-file', type=Path)
    a = p.parse_args()
    templates = [mask_rgb(Image.open(path).convert('RGB').crop(BOX)) for path in a.template]
    if any(t.sum() < 500 for t in templates):
        raise ValueError('Reference lacks enough observed menu text')
    if a.check_image:
        for path in a.check_image:
            mask = mask_rgb(Image.open(path).convert('RGB').crop(BOX))
            print(json.dumps({'image': str(path), 'scores': [round(score(mask, t), 4) for t in templates]}))
        return
    root = a.root.resolve()
    out = root / 'postproduction' / 'pause-detection'
    out.mkdir(parents=True, exist_ok=True)
    completed = 0
    for path, session in media_paths(root):
        if path.suffix.lower() not in ('.mkv', '.mp4'):
            continue
        relative = path.relative_to(root).as_posix()
        if a.only and relative not in a.only:
            continue
        if 'recovered' in path.parts and not a.include_recovered:
            continue
        target = out / (relative.replace('/', '__') + '.json')
        sha = digest(path)
        if target.exists():
            old = json.loads(target.read_text(encoding='utf-8'))
            if (old.get('sha256') == sha and old.get('scan_complete')
                    and old.get('threshold') == a.threshold
                    and old.get('templates') == [str(x) for x in a.template]):
                continue
        row = {'path': relative, 'sha256': sha, 'threshold': a.threshold,
               'scan_complete': False, 'frames_checked': 0, 'pause_candidates': [],
               'review_status': 'PENDING - inspect cuts and retained material; this is not a privacy review',
               'templates': [str(x) for x in a.template]}
        opened = None
        first = last = 0.0
        started = time.time()
        try:
            with av.open(str(path)) as container:
                stream = container.streams.video[0]
                stream.thread_type = 'AUTO'
                stream.codec_context.thread_count = 2
                frame_seconds = 1 / float(stream.average_rate or 30)
                for frame in container.decode(stream):
                    if frame.time is None:
                        raise ValueError('Frame timestamp missing')
                    if row['frames_checked'] == 0:
                        first = frame.time
                    last = frame.time - first
                    frame_mask = mask_frame(frame)
                    similarity = max(score(frame_mask, template) for template in templates)
                    paused = similarity >= a.threshold
                    if paused and opened is None:
                        opened = last
                    elif not paused and opened is not None:
                        row['pause_candidates'].append([opened, last])
                        opened = None
                    row['frames_checked'] += 1
                    if row['frames_checked'] % 1800 == 0:
                        status = a.status_file or root / 'postproduction' / 'pause-scan-status.json'
                        status.parent.mkdir(parents=True, exist_ok=True)
                        status.write_text(json.dumps({
                            'at': time.time(), 'path': relative, 'through_seconds': last,
                            'frames_checked': row['frames_checked']}), encoding='utf-8')
                if opened is not None:
                    row['pause_candidates'].append([opened, last + frame_seconds])
                row.update(scan_complete=row['frames_checked'] > 0, first_pts_seconds=first,
                           decoded_seconds=last + frame_seconds)
        except Exception as exc:
            row['error'] = type(exc).__name__ + ': ' + str(exc)
        row.update(processing_seconds=time.time() - started, completed_at=time.time())
        target.write_text(json.dumps(row, indent=2), encoding='utf-8')
        print(json.dumps({'path': relative, 'scan_complete': row['scan_complete'],
                          'candidate_pause_seconds': sum(b-a for a,b in row['pause_candidates']),
                          'error': row.get('error')}), flush=True)
        completed += 1
        if a.limit and completed >= a.limit:
            break


if __name__ == '__main__':
    main()
