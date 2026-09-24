"""Private campaign repair: preserve video, restore chapters, add audio headroom."""
import hashlib
import json
import re
import subprocess
import time
from pathlib import Path

import av
import imageio_ffmpeg

root = Path('postproduction')
folder = (root / 'drafts/full-story').resolve()
source = folder / 'private-full-story-candidate.mp4'
output = folder / 'private-full-story-chapters.mp4'
plan = json.loads((folder / 'input-final-menu-review-20260923.json').read_text(encoding='utf-8'))
total = 9 + sum(c['output_seconds'] for c in plan['clips'])
chapters = [{'title': 'GPT-6 Astra + Jev - ' + plan['presentation']['elapsed_time']['headline']}]
chapters += plan['chapters']
chapter_args = []
for i, chapter in enumerate(chapters):
    chapter_args += [f'-metadata:c:{i}', 'title=' + chapter['title']]
ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
command = [ffmpeg, '-hide_banner', '-nostdin', '-y', '-xerror', '-threads', '2',
           '-i', str(source), '-i', str(folder / 'chapters.ffmeta'),
           '-map', '0:v:0', '-map', '0:a:0', '-map_chapters', '1',
           '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k',
           '-af', f'volume=-6dB,atrim=duration={total:.9f}', '-ar', '48000',
           '-map_metadata', '-1', *chapter_args, '-metadata',
           'title=GPT-6 Astra + Jev - Fallout: New Vegas - Full Main Story',
           '-movflags', '+faststart', str(output)]
print(json.dumps({'audio_repair': 'started', 'gain_db': -6}), flush=True)
with (folder / 'audio-headroom-repair.log').open('wb') as log:
    result = subprocess.run(command, stdout=log, stderr=log)
assert result.returncode == 0, 'Headroom repair failed; inspect private log'
with av.open(str(output)) as container:
    actual = container.chapters()
    assert [c['metadata']['title'] for c in actual] == [c['title'] for c in chapters]
    metadata = {'container_metadata': container.metadata, 'chapters': actual,
                'streams': [{'type': s.type, 'metadata': s.metadata} for s in container.streams]}
(root / 'final-export-named-metadata.json').write_text(json.dumps(metadata, indent=2, default=str), encoding='utf-8')
print(json.dumps({'audio_repair': 'encoded', 'named_chapters': len(actual)}), flush=True)
log_path = root / 'final-export-audio-headroom-metrics.log'
with log_path.open('wb') as log:
    result = subprocess.run([ffmpeg, '-hide_banner', '-nostdin', '-xerror', '-threads', '2',
                             '-i', str(output), '-map', '0:a:0', '-vn', '-sn', '-dn',
                             '-af', 'ebur128=peak=true:framelog=verbose', '-f', 'null', 'NUL'],
                            stdout=log, stderr=log)
assert result.returncode == 0, 'Encoded audio did not decode cleanly'
summary = log_path.read_text(encoding='utf-8', errors='replace').rsplit('Summary:', 1)[-1]
peak = float(re.search(r'Peak:\s*([-\d.]+) dBFS', summary).group(1))
loudness = float(re.search(r'I:\s*([-\d.]+) LUFS', summary).group(1))
assert peak < 0, f'Encoded true peak still exceeds full scale: {peak}'
report = {'created_at': time.time(), 'path': str(output), 'gain_db': -6,
          'encoded_integrated_lufs': loudness, 'encoded_true_peak_dbfs': peak,
          'audio_decode_complete': True, 'chapter_titles_verified': len(actual),
          'scope': 'Full encoded audio decode and measurement, not a listening/privacy review.',
          'video_packet_identity_verification': 'pending', 'full_visual_listening_review': 'pending'}
(root / 'audio-headroom-repair-review.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report), flush=True)
