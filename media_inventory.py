"""Private, resumable full-decode inventory. Decoding is not privacy clearance."""
import argparse
import hashlib
import json
import time
from pathlib import Path

import av


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def media_paths(root):
    for folder in sorted(root.iterdir()):
        if not folder.is_dir() or not folder.name.startswith(('campaign-', 'recording-pilot-')):
            continue
        session_path = folder / 'session.json'
        session = json.loads(session_path.read_text(encoding='utf-8-sig')) if session_path.exists() else {}
        if session.get('state') in ('starting', 'recording'):
            continue
        for path in sorted(folder.rglob('*')):
            if path.is_file() and path.suffix.lower() in ('.mkv', '.aac', '.wav', '.mp4'):
                yield path, session


def inspect(path):
    result = {'decoded_frames': 0, 'decoded_audio_samples': 0, 'decode_complete': False}
    try:
        with av.open(str(path)) as container:
            stream = next(s for s in container.streams if s.type in ('video', 'audio'))
            stream.thread_type = 'AUTO'
            stream.codec_context.thread_count = 2
            result.update(type=stream.type, codec=stream.codec_context.name, metadata=dict(container.metadata))
            if stream.type == 'video':
                result.update(width=stream.codec_context.width, height=stream.codec_context.height, average_rate=str(stream.average_rate))
            first = last = None
            frame_duration = 0.0
            for frame in container.decode(stream):
                result['decoded_frames'] += 1
                if frame.pts is not None:
                    stamp = float(frame.pts * frame.time_base)
                    if first is None:
                        first = stamp
                    last = stamp
                if stream.type == 'audio':
                    result['decoded_audio_samples'] += frame.samples
                    result['sample_rate'] = frame.sample_rate
                    frame_duration = frame.samples / frame.sample_rate
                else:
                    frame_duration = 1 / float(stream.average_rate or 30)
            result.update(first_pts_seconds=first, last_pts_seconds=last)
            result['decoded_seconds'] = (last - first + frame_duration) if first is not None else 0
            result['decode_complete'] = result['decoded_frames'] > 0
    except Exception as exc:
        result['error'] = type(exc).__name__ + ': ' + str(exc)
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, default=Path('.'))
    p.add_argument('--limit', type=int)
    a = p.parse_args()
    root = a.root.resolve()
    out = root / 'postproduction'
    out.mkdir(exist_ok=True)
    report = out / 'media-audit.jsonl'
    known = {}
    if report.exists():
        for line in report.read_text(encoding='utf-8').splitlines():
            row = json.loads(line)
            known[row['path']] = row
    count = 0
    for path, session in media_paths(root):
        name = path.relative_to(root).as_posix()
        stat = path.stat()
        previous = known.get(name, {})
        if previous.get('bytes') == stat.st_size and previous.get('mtime_ns') == stat.st_mtime_ns:
            continue
        started = time.time()
        row = {'path': name, 'bytes': stat.st_size, 'mtime_ns': stat.st_mtime_ns, 'sha256': digest(path),
               'session_state': session.get('state'), 'session_started_at': session.get('started_at'),
               'video_launch_at': session.get('video_launch_at'), 'audio_started_at': session.get('audio_started_at'),
               'capture_warnings': session.get('audio_warnings', []), 'capture_error': session.get('error'),
               'derived_recovery': 'recovered' in path.parts,
               'privacy_review': 'PENDING - full decode does not establish visual or audio privacy review'}
        row.update(inspect(path))
        row.update(audited_at=time.time(), processing_seconds=time.time() - started)
        with report.open('a', encoding='utf-8') as f:
            f.write(json.dumps(row) + '\n')
        print(json.dumps({k: row.get(k) for k in ('path', 'decode_complete', 'decoded_seconds', 'error', 'processing_seconds')}), flush=True)
        count += 1
        if a.limit and count >= a.limit:
            break


if __name__ == '__main__':
    main()
