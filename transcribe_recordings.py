"""Local ASR for private review. Transcripts can be wrong and never clear privacy."""
import argparse
import hashlib
import json
import os
import time
from pathlib import Path

os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
os.environ['HF_HUB_DISABLE_IMPLICIT_TOKEN'] = '1'


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, default=Path('.'))
    p.add_argument('--model', default='large-v3-turbo')
    p.add_argument('--threads', type=int, default=6)
    p.add_argument('--prepare-only', action='store_true')
    p.add_argument('--limit', type=int)
    p.add_argument('--only', action='append', help='Exact root-relative media path; repeat to select files')
    p.add_argument('--include-recovered', action='store_true')
    p.add_argument('--status-file', type=Path, help='Separate progress file for an independent selected-file batch')
    a = p.parse_args()
    from faster_whisper import WhisperModel
    from media_inventory import digest, media_paths
    root = a.root.resolve()
    out = root / 'postproduction' / 'transcripts'
    out.mkdir(parents=True, exist_ok=True)
    model = WhisperModel(a.model, device='cpu', compute_type='int8', cpu_threads=a.threads,
                         download_root=str(root / 'postproduction' / 'models'))
    print(json.dumps({'model_ready': a.model, 'local_inference': True}), flush=True)
    if a.prepare_only:
        return
    completed = 0
    for path, session in media_paths(root):
        if path.suffix.lower() not in ('.aac', '.wav'):
            continue
        name = path.relative_to(root).as_posix()
        if a.only and name not in a.only:
            continue
        # Explicitly include a surviving recovery when the original is damaged.
        # Never erase the original failure or imply recovery restored lost sound.
        if 'recovered' in path.parts and not a.include_recovered:
            continue
        key = hashlib.sha256(name.encode()).hexdigest()[:16]
        target = out / (key + '.json')
        sha = digest(path)
        if target.exists():
            previous = json.loads(target.read_text(encoding='utf-8'))
            if previous.get('sha256') == sha and previous.get('transcription_complete') and previous.get('model') == a.model:
                continue
        started = time.time()
        row = {'path': name, 'sha256': sha, 'model': a.model, 'inference': 'local CPU int8',
               'transcription_complete': False, 'privacy_review': 'PENDING',
               'limitation': 'Machine transcript only; may omit, misrecognize or hallucinate words. Listening and visual review still required.',
               'segments': []}
        status = a.status_file or root / 'postproduction' / 'transcription-status.json'
        status.parent.mkdir(parents=True, exist_ok=True)
        def checkpoint():
            status.write_text(json.dumps({'at': time.time(), 'path': name, 'segments': len(row['segments']),
                                         'audio_processed_through': row['segments'][-1]['end'] if row['segments'] else 0,
                                         'state': 'transcribing', 'model': a.model}), encoding='utf-8')
        checkpoint()
        try:
            segments, info = model.transcribe(str(path), language='en', beam_size=5,
                vad_filter=True, condition_on_previous_text=False, word_timestamps=True)
            row.update(audio_duration=info.duration, language=info.language,
                       vad_kept_duration=info.duration_after_vad)
            for seg in segments:
                row['segments'].append({'start': seg.start, 'end': seg.end, 'text': seg.text,
                    'avg_logprob': seg.avg_logprob, 'no_speech_prob': seg.no_speech_prob,
                    'words': [{'start': w.start, 'end': w.end, 'word': w.word, 'probability': w.probability} for w in (seg.words or [])]})
                partial = target.with_suffix('.partial.json')
                partial.write_text(json.dumps(row, ensure_ascii=False), encoding='utf-8')
                checkpoint()
            row['transcription_complete'] = True
        except Exception as exc:
            row['error'] = type(exc).__name__ + ': ' + str(exc)
        row.update(completed_at=time.time(), processing_seconds=time.time() - started)
        target.write_text(json.dumps(row, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({k: row.get(k) for k in ('path', 'transcription_complete', 'audio_duration', 'error', 'processing_seconds')}), flush=True)
        completed += 1
        if a.limit and completed >= a.limit:
            break
    status = a.status_file or root / 'postproduction' / 'transcription-status.json'
    status.parent.mkdir(parents=True, exist_ok=True)
    status.write_text(json.dumps({'at': time.time(), 'state': 'batch_finished', 'files_processed': completed, 'privacy_review': 'PENDING'}), encoding='utf-8')


if __name__ == '__main__':
    main()
