"""Build a private, evidence-linked rough cut. Never grants publication clearance.

Media timing comes from full-decode audits and recorder counter observations.
Speech is protected using word timestamps, not VAD segments that can span long
silent pauses. Every proposed cut and sync correction still needs review.
"""
import argparse
import bisect
import collections
import datetime
import json
import math
import statistics
from pathlib import Path


def merge(spans, gap=0.0):
    result = []
    for start, end in sorted((max(0., a), b) for a, b in spans if b > a):
        if result and start <= result[-1][1] + gap:
            result[-1][1] = max(result[-1][1], end)
        else:
            result.append([start, end])
    return result


def subtract(spans, removed):
    result = []
    removed = merge(removed)
    for start, end in spans:
        cursor = start
        for left, right in removed:
            if right <= cursor:
                continue
            if left >= end:
                break
            if left > cursor:
                result.append([cursor, min(left, end)])
            cursor = max(cursor, right)
            if cursor >= end:
                break
        if cursor < end:
            result.append([cursor, end])
    return result


def interpolate(points, value, reverse=False):
    pairs = sorted((b, a) if reverse else (a, b) for a, b in points)
    if not pairs:
        return value
    keys = [a for a, _ in pairs]
    i = bisect.bisect_right(keys, value)
    if i == 0:
        return value + pairs[0][1] - pairs[0][0]
    if i == len(pairs):
        return value + pairs[-1][1] - pairs[-1][0]
    x1, y1 = pairs[i - 1]
    x2, y2 = pairs[i]
    return y1 + (value - x1) * (y2 - y1) / (x2 - x1)


def sync_points(actions):
    buckets = collections.defaultdict(list)
    for action in actions:
        rec = action.get('recording', {})
        if not rec.get('healthy') or not rec.get('video_frames') or not rec.get('audio_frames'):
            continue
        video = rec['video_frames'] / 30
        audio = rec['audio_frames'] / 48000
        buckets[int(video // 20)].append((video, audio - video))
    result = []
    for _, values in sorted(buckets.items()):
        video = statistics.median(v for v, _ in values)
        audio = video + statistics.median(offset for _, offset in values)
        if not result or (video > result[-1][0] and audio > result[-1][1]):
            result.append([video, audio])
    return result


def load_jsonl(path):
    if not path.exists():
        return []
    with path.open(encoding='utf-8') as source:
        return [json.loads(line) for line in source if line.strip()]


def audited_files(root, rows, session, kind):
    folder = root / session
    suffixes = ('.mkv', '.mp4') if kind == 'video' else ('.wav', '.aac')
    result = []
    offset = 0.
    for original in sorted(p for p in folder.glob(kind + '-*') if p.suffix in suffixes):
        recovered = folder / 'recovered' / original.name
        candidate = recovered if recovered.exists() else original
        name = candidate.relative_to(root).as_posix()
        audit = rows.get(name, {})
        if not audit.get('decode_complete'):
            raise ValueError('Missing complete decode audit: ' + name)
        duration = (audit['decoded_audio_samples'] / audit['sample_rate']
                    if kind == 'audio' else audit['decoded_seconds'])
        result.append({'path': name, 'sha256': audit['sha256'], 'start': offset,
                       'end': offset + duration, 'duration': duration,
                       'first_pts': audit.get('first_pts_seconds', 0),
                       'recovered': candidate == recovered})
        offset += duration
    if not result:
        raise ValueError('No audited ' + kind + ' media for ' + session)
    return result


def containing(files, second):
    return next((f for f in files if f['start'] - .00001 <= second < f['end'] + .00001), None)


def session_clips(root, rows, transcripts, actions, name, editorial=None):
    editorial = editorial or {}
    exclusions = editorial.get('exclusions', {}).get(name, [])
    speed_overrides = editorial.get('speed_overrides', {}).get(name, [])
    videos = audited_files(root, rows, name, 'video')
    audios = audited_files(root, rows, name, 'audio')
    points = sync_points(actions)
    if not points:
        raise ValueError('No recorded counter anchors for ' + name)
    duration = videos[-1]['end']
    paused = []
    for video in videos:
        pause_file = root / 'postproduction/pause-detection' / (video['path'].replace('/', '__') + '.json')
        pause = json.loads(pause_file.read_text(encoding='utf-8')) if pause_file.exists() else {}
        if not pause.get('scan_complete') or pause.get('sha256') != video['sha256']:
            raise ValueError('Missing matching full-frame pause scan: ' + video['path'])
        # Actual boundary review found menu fade-in before the text reaches
        # the detector threshold, and fade-out after it falls below it.
        paused.extend([video['start'] + a - .7, video['start'] + b + .6] for a, b in pause['pause_candidates'])
    active, real_time = [], []
    for action in actions:
        rec = action.get('recording', {})
        if action.get('phase') != 'input_sent' or not rec.get('video_frames') or action.get('error'):
            continue
        start = rec['video_frames'] / 30
        held = max(.1, min(60., action.get('finished_at', action['at'] + action.get('seconds', .1)) - action['at']))
        active.append([start - 1.5, start + held + 2.5])
        if action.get('button') or any(k in ('e', 'v', 'r') for k in action.get('keys', [])):
            real_time.append([start - 3., start + held + 7.])
    for audio in audios:
        transcript = transcripts.get(audio['path'])
        if not transcript or not transcript.get('transcription_complete') or transcript.get('sha256') != audio['sha256']:
            raise ValueError('Missing matching local transcript: ' + audio['path'])
        for segment in transcript['segments']:
            for word in segment.get('words', []):
                a = interpolate(points, audio['start'] + word['start'], reverse=True)
                b = interpolate(points, audio['start'] + word['end'], reverse=True)
                active.append([a - .8, b + 1.2])
                real_time.append([a - 1.8, b + 2.2])
    if name == 'campaign-004':
        # The later Doc Mitchell restart is retained. Opening cinema is optional
        # context; these reviewed bounds avoid setup menus and the duplicate birth.
        active = [[389., 578.]]
        real_time = active.copy()
    if name == 'campaign-038':
        # Keep the final conversation and whole ending. Credits will receive
        # separately reviewed acceleration; never infer that silence is idle here.
        active.append([1600., duration])
        real_time.append([1600., duration])
    if name == 'campaign-039':
        # Completion proof, after the overlapping handoff; exclude the later menu.
        active = [[35., 47.]]
        real_time = active.copy()
    for span in editorial.get('forced_spans', {}).get(name, []):
        active.append([span['start'], span['end']])
        real_time.append([span['start'], span['end']])
    active = subtract(merge(active, gap=2.), paused + [[e['start'], e['end']] for e in exclusions])
    active = [[max(0., a), min(duration, b)] for a, b in active if min(duration, b) - max(0., a) >= .4]
    real_time = merge(real_time, gap=2.)
    boundaries = {0., duration}
    for f in videos:
        boundaries.update((f['start'], f['end']))
    for f in audios:
        boundaries.update((interpolate(points, f['start'], reverse=True), interpolate(points, f['end'], reverse=True)))
    for a, b in real_time:
        boundaries.update((a, b))
    for override in speed_overrides:
        boundaries.update((override['start'], override['end']))
    clips = []
    for start, end in active:
        splits = sorted({start, end} | {x for x in boundaries if start < x < end})
        for left, right in zip(splits, splits[1:]):
            if right - left < .1:
                continue
            mid = (left + right) / 2
            speed = 1. if any(a <= mid <= b for a, b in real_time) else 2.
            if speed != 1. and right - left < 8:
                speed = 1.
            override = next((v for v in speed_overrides if v['start'] <= mid < v['end']), None)
            if override:
                speed = override['speed']
            video = containing(videos, mid)
            a1, a2 = interpolate(points, left), interpolate(points, right)
            audio = containing(audios, (a1 + a2) / 2)
            if video is None:
                raise ValueError('Uncovered video edge at ' + str((left, right)))
            if audio and (a1 < audio['start'] - .01 or a2 > audio['end'] + .01):
                raise ValueError('Audio boundary splitting failed at ' + str((left, right)))
            frames = max(1, round((right - left) / speed * 30))
            out_seconds = frames / 30
            clips.append({'session': name, 'session_start': left, 'session_end': right,
                          'video': video['path'], 'video_sha256': video['sha256'],
                          'video_in': left - video['start'], 'video_out': right - video['start'],
                          'audio': audio['path'] if audio else None,
                          'audio_sha256': audio['sha256'] if audio else None,
                          'audio_in': max(0., a1 - audio['start']) if audio else 0.,
                          'audio_out': a2 - audio['start'] if audio else out_seconds,
                          'audio_alignment_gap': audio is None,
                          'speed': speed, 'output_frames': frames, 'output_seconds': out_seconds,
                          'speed_label': override['label'] if override else None,
                          'audio_tempo': (a2 - a1) / out_seconds if audio else 1.,
                          'sync_basis': 'median recorded video/audio counters in 20-second bins; listen-check pending',
                          'visual_review': 'pending', 'audio_review': 'pending'})
    return clips, {'session': name, 'video_seconds': duration, 'audio_seconds': audios[-1]['end'],
                   'anchor_count': len(points), 'anchors': points,
                   'pause_seconds': sum(b - a for a, b in merge(paused)),
                   'editorial_exclusions': exclusions, 'speed_overrides': speed_overrides,
                   'audio_alignment_gap_seconds': sum(x['output_seconds'] for x in clips if x['audio_alignment_gap']),
                   'retained_source_seconds': sum(x['session_end'] - x['session_start'] for x in clips),
                   'draft_output_seconds': sum(x['output_seconds'] for x in clips)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path('.'))
    parser.add_argument('--session', action='append')
    parser.add_argument('--output', type=Path, default=Path('postproduction/story-draft.json'))
    args = parser.parse_args()
    root = args.root.resolve()
    editorial_path = root / 'postproduction/editorial-edits.json'
    editorial = json.loads(editorial_path.read_text(encoding='utf-8')) if editorial_path.exists() else {}
    rows = {x['path']: x for x in load_jsonl(root / 'postproduction/media-audit.jsonl')}
    transcripts = {}
    for p in (root / 'postproduction/transcripts').glob('*.json'):
        if not p.name.endswith('.partial.json'):
            d = json.loads(p.read_text(encoding='utf-8'))
            transcripts[d['path']] = d
    grouped = collections.defaultdict(list)
    for action in load_jsonl(root / 'actions.jsonl'):
        grouped[action.get('recording', {}).get('session')].append(action)
    names = args.session or [p.name for p in sorted(root.glob('campaign-*')) if p.is_dir()]
    draft = {'version': 1, 'status': 'PRIVATE ROUGH CUT - NOT APPROVED FOR UPLOAD',
             'credit': 'GPT-6 Astra + Jev', 'all_source_privacy_review': 'pending',
             'final_export_review': 'pending', 'clips': [], 'sessions': [], 'pending': [],
             'editorial_exclusions': [], 'created_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    timing_path = root / 'postproduction/campaign-timing.json'
    if timing_path.exists():
        timing = json.loads(timing_path.read_text(encoding='utf-8'))
        if timing.get('public_headline'):
            draft['presentation'] = {'elapsed_time': {
                'headline': timing['public_headline'],
                'definition': timing['public_definition'],
                'source': 'postproduction/campaign-timing.json'}}
    for name in names:
        if name in ('campaign-001', 'campaign-002', 'campaign-003', 'campaign-005', 'campaign-006', 'campaign-020'):
            draft['editorial_exclusions'].append({'session': name, 'reason': 'Startup, menu/input setup or superseded character attempt. Preserve private raw files and required privacy review.'})
            continue
        try:
            clips, report = session_clips(root, rows, transcripts, grouped[name], name, editorial)
            draft['clips'].extend(clips)
            draft['sessions'].append(report)
        except (ValueError, KeyError) as exc:
            draft['pending'].append({'session': name, 'reason': str(exc)})
    offset = 0.
    for i, clip in enumerate(draft['clips']):
        clip['index'] = i
        clip['output_start'] = offset
        offset += clip['output_seconds']
    draft['output_seconds'] = offset
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(draft, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'output': str(args.output), 'clips': len(draft['clips']), 'output_seconds': offset,
                      'ready_sessions': len(draft['sessions']), 'pending': draft['pending']}, indent=2))


if __name__ == '__main__':
    main()
