"""Render a local editing draft from explicit, audited source spans.

All outputs remain private. This renderer cannot mark a privacy review complete
or publish anything. Raw media are opened read-only and never overwritten.
"""
import argparse
import hashlib
import json
import math
import subprocess
import time
from pathlib import Path

import av
import imageio_ffmpeg

RENDER_REVISION = 4

def ass_time(value):
    centiseconds = round(value * 100)
    return f'{centiseconds // 360000}:{centiseconds // 6000 % 60:02}:{centiseconds // 100 % 60:02}.{centiseconds % 100:02}'


def ass_text(value):
    return value.replace('\\', '\\u005c').replace('{', '(').replace('}', ')').replace('\n', r'\N')


def subtitles(path, duration, speed=1, title=False, opening=False, audio_gap=False, captions=None, title_timing=None, speed_label=None):
    header = '''[Script Info]
ScriptType: v4.00+
PlayResX: 1280
PlayResY: 720
WrapStyle: 0
ScaledBorderAndShadow: yes
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Credit,Segoe UI,18,&H00D2F2FF,&H000000FF,&H90101510,&H90101510,-1,0,0,0,100,100,0,0,3,4,0,7,24,24,20,1
Style: Speed,Segoe UI,18,&H00FFFFFF,&H000000FF,&H90101510,&H90101510,-1,0,0,0,100,100,0,0,3,4,0,9,24,24,20,1
Style: Main,Segoe UI,54,&H00D2F2FF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,0,0,5,70,70,0,1
Style: Body,Segoe UI,27,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,5,90,90,0,1
Style: Note,Segoe UI,24,&H00FFFFFF,&H000000FF,&H20101510,&H80101510,0,0,0,0,100,100,0,0,3,10,0,8,100,100,74,1
Style: Action,Segoe UI,18,&H00D2F2FF,&H000000FF,&H90101510,&H90101510,0,0,0,0,100,100,0,0,3,4,0,7,24,24,48,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    events = []
    def event(style, text, start=0, end=None):
        events.append(f'Dialogue: 0,{ass_time(start)},{ass_time(duration if end is None else end)},{style},,0,0,0,,{text}')
    if title:
        event('Main', r'{\pos(640,235)}GPT-6 Astra + Jev')
        event('Body', r'{\pos(640,318)\fs36}Fallout: New Vegas')
        event('Body', r'{\pos(640,378)}Full Main Story')
        if title_timing:
            event('Body', r'{\pos(640,429)\fs27}' + ass_text(title_timing['headline']))
            event('Body', r'{\pos(640,468)\fs18}' + ass_text(title_timing['definition']))
        event('Body', r'{\pos(640,541)\fs22}Jev: rapid gameplay decisions\NGPT-6 Astra: planning, controls and recoveries')
        event('Body', r'{\pos(640,627)\fs17\c&HAAAAAA&}PRIVATE EDITING DRAFT - privacy and edit review pending')
    else:
        event('Credit', 'GPT-6 Astra + Jev')
        event('Speed', ass_text(speed_label) if speed_label else f'{speed:g}x speed' if speed != 1 else 'Private editing draft')
        if opening:
            event('Note', r'{\fs16\c&H00D2F2FF&}RETROSPECTIVE INTRODUCTION\N{\fs24\c&H00FFFFFF&}A supervised main-story run.\NPauses and waiting are cut; accelerated sections are labeled.', end=min(duration, 8))
        if audio_gap:
            event('Note', 'Audio alignment gap - review required')
        for caption in captions or []:
            label = ass_text(caption['label'])
            body = ass_text(caption['text'])
            if caption.get('style') == 'Action':
                event('Action', label + ': ' + body,
                      start=max(0., caption['start']), end=min(duration, caption['end']))
                continue
            event('Note', r'{\fs16\c&H00D2F2FF&}' + label + r'\N{\fs24\c&H00FFFFFF&}' + body,
                  start=max(0., caption['start']), end=min(duration, caption['end']))
    path.write_text(header + '\n'.join(events) + '\n', encoding='utf-8-sig')


def tempo_filters(value):
    result = []
    while value > 2.:
        result.append('atempo=2')
        value /= 2
    while value < .5:
        result.append('atempo=0.5')
        value *= 2
    result.append(f'atempo={value:.10f}')
    return ','.join(result)


def inspect_output(path):
    result = {'video_frames': 0, 'audio_samples': 0, 'video_first': None, 'video_last': None}
    with av.open(str(path)) as c:
        for packet in c.demux():
            for frame in packet.decode():
                if isinstance(frame, av.VideoFrame):
                    result['video_frames'] += 1
                    if result['video_first'] is None:
                        result['video_first'] = frame.time
                    result['video_last'] = frame.time
                else:
                    result['audio_samples'] += frame.samples
                    result['audio_rate'] = frame.sample_rate
    result['decode_complete'] = result['video_frames'] > 0 and result['audio_samples'] > 0
    return result


def run(ffmpeg, args, folder, name):
    with (folder / (name + '.log')).open('wb') as log:
        result = subprocess.run([ffmpeg, '-hide_banner', '-nostdin', '-y', '-xerror', '-threads', '2'] + args,
                                cwd=folder, stdout=subprocess.DEVNULL, stderr=log,
                                creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        raise RuntimeError(f'{name} failed with exit {result.returncode}; inspect its private log')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('timeline', type=Path)
    p.add_argument('--root', type=Path, default=Path('.'))
    p.add_argument('--output', type=Path, default=Path('postproduction/drafts/opening'))
    p.add_argument('--limit', type=int)
    p.add_argument('--no-title', action='store_true')
    p.add_argument('--encoder', choices=('libx264', 'h264_nvenc'), default='libx264')
    p.add_argument('--filename', default='private-opening-draft.mp4')
    a = p.parse_args()
    root, folder = a.root.resolve(), a.output.resolve()
    if root / 'postproduction' not in folder.parents:
        raise ValueError('Draft output must stay inside the private postproduction folder')
    if Path(a.filename).name != a.filename or not a.filename.endswith('.mp4'):
        raise ValueError('Output filename must be a plain MP4 basename')
    folder.mkdir(parents=True, exist_ok=True)
    data = json.loads(a.timeline.read_text(encoding='utf-8'))
    clips = data['clips'][:a.limit] if a.limit else data['clips']
    if not clips:
        raise ValueError('No ready clips')
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    encoder_args = (['-c:v', 'h264_nvenc', '-preset', 'p4', '-rc', 'vbr', '-cq', '22', '-b:v', '0']
                    if a.encoder == 'h264_nvenc' else ['-c:v', 'libx264', '-preset', 'fast', '-crf', '22'])
    output_args = [*encoder_args, '-bf', '0', '-g', '60',
                   '-pix_fmt', 'yuv420p', '-c:a', 'flac', '-sample_fmt', 's16',
                   '-ar', '48000', '-ac', '2', '-map_metadata', '-1']
    rendered = []
    hash_cache = {}
    status_path = folder / 'status.json'
    if not a.no_title:
        title = folder / 'title.mkv'
        subtitles(folder / 'title.ass', 9, title=True, title_timing=data.get('presentation', {}).get('elapsed_time'))
        run(ffmpeg, ['-f', 'lavfi', '-i', 'color=c=0x101510:s=1280x720:r=30:d=9',
                     '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo',
                     '-vf', 'subtitles=title.ass', '-t', '9', *output_args, str(title)], folder, 'title')
        rendered.append(title)
    receipts = []
    for i, clip in enumerate(clips):
        # Reuse unchanged source cuts even when an earlier edit changes their
        # position or index. Review bookkeeping does not change rendered pixels.
        identity_clip = {k: v for k, v in clip.items()
                         if k not in ('index', 'output_start', 'visual_review', 'audio_review')}
        identity = hashlib.sha256(json.dumps({'clip': identity_clip, 'render_revision': RENDER_REVISION,
                                              'encoder': a.encoder, 'opening': i == 0}, sort_keys=True).encode()).hexdigest()
        clip_name = 'clip-' + identity[:24]
        file = folder / (clip_name + '.mkv')
        receipt_path = folder / (clip_name + '.json')
        if receipt_path.exists() and file.exists():
            previous = json.loads(receipt_path.read_text(encoding='utf-8'))
            if previous.get('clip_identity') == identity and previous.get('decode_complete'):
                rendered.append(file)
                receipts.append(previous)
                continue
        for key in ('video', 'audio'):
            if clip[key] is None:
                continue
            source = (root / clip[key]).resolve()
            if root not in source.parents or not source.parent.name.startswith('campaign-') and source.parent.name != 'recovered':
                raise ValueError('Source is outside the campaign recording folders')
            if source not in hash_cache:
                h = hashlib.sha256()
                with source.open('rb') as f:
                    for part in iter(lambda: f.read(1024 * 1024), b''):
                        h.update(part)
                hash_cache[source] = h.hexdigest()
            if hash_cache[source] != clip[key + '_sha256']:
                raise ValueError('Raw source hash changed')
        ass = folder / (clip_name + '.ass')
        duration = clip['output_seconds']
        subtitles(ass, duration, speed=clip['speed'], opening=i == 0,
                   audio_gap=clip.get('audio_alignment_gap', False), captions=clip.get('captions'),
                   speed_label=clip.get('speed_label'))
        vduration = clip['video_out'] - clip['video_in']
        aduration = clip['audio_out'] - clip['audio_in']
        filters = (f'[0:v]trim=duration={vduration:.9f},setpts=(PTS-STARTPTS)/{vduration/duration:.10f},'
                   f'scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,'
                   # Pad after converting to a fixed frame rate: source chunks
                   # can start with a nonzero PTS and end between output frames.
                   # A bounded four-frame tail handles that rounding without
                   # hiding a substantially truncated source.
                   f'setsar=1,fps=30:start_time=0,tpad=stop_mode=clone:stop=4,'
                   f'trim=end_frame={clip["output_frames"]},setpts=N/(30*TB),subtitles={ass.name}[v];'
                   f'[1:a]atrim=duration={aduration:.9f},asetpts=PTS-STARTPTS,'
                   f'{tempo_filters(clip["audio_tempo"])},aresample=48000,'
                   f'afade=t=in:d=0.012,afade=t=out:st={max(0,duration-.012):.9f}:d=0.012,'
                   f'apad,atrim=duration={duration:.9f}[a]')
        status_path.write_text(json.dumps({'at': time.time(), 'state': 'rendering', 'clip': i,
                                           'of': len(clips), 'source': clip['video'], 'privacy_review': 'pending'}), encoding='utf-8')
        audio_input = (['-ss', str(clip['audio_in']), '-i', str(root / clip['audio'])]
                       if clip['audio'] else ['-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo'])
        run(ffmpeg, ['-ss', str(clip['video_in']), '-i', str(root / clip['video']), *audio_input,
                     '-filter_complex_threads', '2', '-filter_complex', filters,
                     '-map', '[v]', '-map', '[a]', '-fps_mode:v', 'passthrough', *output_args, str(file)], folder, clip_name)
        receipt = inspect_output(file)
        if receipt['video_frames'] != clip['output_frames']:
            status_path.write_text(json.dumps({'at': time.time(), 'state': 'clip_validation_failed',
                                               'clip': i, 'source': clip['video'], 'file': str(file),
                                               'expected_frames': clip['output_frames'], 'decode': receipt,
                                               'privacy_review': 'pending'}), encoding='utf-8')
            raise ValueError('Rendered video duration does not match the cut')
        if abs(receipt['audio_samples'] - round(duration * 48000)) > 1024:
            status_path.write_text(json.dumps({'at': time.time(), 'state': 'clip_validation_failed',
                                               'clip': i, 'source': clip['audio'], 'file': str(file),
                                               'expected_audio_samples': round(duration*48000), 'decode': receipt,
                                               'privacy_review': 'pending'}), encoding='utf-8')
            raise ValueError('Rendered audio duration does not match the cut')
        receipt.update(clip_identity=identity, clip=i, source=clip,
                       privacy_review='pending', audio_sync_listening_review='pending')
        receipt_path.write_text(json.dumps(receipt, indent=2), encoding='utf-8')
        rendered.append(file)
        receipts.append(receipt)
        print(json.dumps({'clip': i + 1, 'of': len(clips), 'seconds': duration, 'decoded': receipt['decode_complete']}), flush=True)
    # Files have generated safe names, so the concat file needs no shell quoting.
    (folder / 'concat.txt').write_text(''.join("file '" + p.name + "'\n" for p in rendered), encoding='utf-8')
    draft = folder / a.filename
    chapter_metadata = [';FFMETADATA1']
    title_offset = 0 if a.no_title else 9
    total = title_offset + sum(c['output_seconds'] for c in clips)
    elapsed_label = data.get('presentation', {}).get('elapsed_time', {}).get('headline')
    opening_chapter = 'GPT-6 Astra + Jev' + (' - ' + elapsed_label if elapsed_label else '')
    chapters = ([{'title': opening_chapter, 'output_start': 0}]
                if title_offset else [])
    chapters.extend({'title': c['title'], 'output_start': c['output_start'] + title_offset}
                    for c in data.get('chapters', []) if c['output_start'] + title_offset < total)
    for i, chapter in enumerate(chapters):
        stop = chapters[i + 1]['output_start'] if i + 1 < len(chapters) else total
        title = chapter['title'].replace('\\', '\\\\').replace('=', '\\=').replace(';', '\\;').replace('#', '\\#').replace('\n', ' ')
        chapter_metadata.extend(['[CHAPTER]', 'TIMEBASE=1/1000',
                                 f'START={round(chapter["output_start"]*1000)}',
                                 f'END={round(stop*1000)}', 'title=' + title])
    (folder / 'chapters.ffmeta').write_text('\n'.join(chapter_metadata) + '\n', encoding='utf-8')
    run(ffmpeg, ['-f', 'concat', '-safe', '1', '-i', 'concat.txt', '-i', 'chapters.ffmeta',
                 '-map', '0:v', '-map', '0:a', '-map_chapters', '1', '-c:v', 'copy', '-c:a', 'aac',
                 '-b:a', '160k', '-map_metadata', '-1', '-metadata', 'title=GPT-6 Astra + Jev - private editing draft',
                 '-movflags', '+faststart', str(draft)], folder, 'assemble')
    check = inspect_output(draft)
    expected_seconds = sum(c['output_seconds'] for c in clips) + (0 if a.no_title else 9)
    actual_audio_seconds = check['audio_samples'] / check['audio_rate']
    actual_video_seconds = check['video_last'] - check['video_first'] + 1/30
    check.update(expected_seconds=expected_seconds, audio_seconds=actual_audio_seconds,
                 video_seconds=actual_video_seconds)
    if abs(actual_audio_seconds - expected_seconds) > .08 or abs(actual_video_seconds - expected_seconds) > .08:
        status_path.write_text(json.dumps({'at': time.time(), 'state': 'assembly_validation_failed',
                                           'decode': check, 'privacy_review': 'pending'}), encoding='utf-8')
        raise ValueError('Joined draft lost audio or video duration; do not use this output')
    status_path.write_text(json.dumps({'at': time.time(), 'state': 'rendered_private_draft', 'file': str(draft),
                                      'clips': len(clips), 'decode': check, 'privacy_review': 'pending',
                                      'encoder': a.encoder, 'pending_source_sessions': data.get('pending', []),
                                      'chapters': chapters,
                                      'full_export_watch_and_listen_review': 'pending'}, indent=2), encoding='utf-8')
    print(json.dumps({'rendered_private_draft': str(draft), 'decode': check, 'privacy_review': 'pending'}), flush=True)


if __name__ == '__main__':
    main()
