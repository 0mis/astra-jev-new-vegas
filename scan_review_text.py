"""Local OCR navigation aid for private footage review.

This samples video at an explicitly recorded interval. It cannot certify that
unsampled frames, faces, images, sound or unreadable text contain no private data.
"""
import argparse
import getpass
import hashlib
import json
import re
import time
from pathlib import Path

import av

from media_inventory import digest


RULES = {
    'email_like': re.compile(r'\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b', re.I),
    'local_path': re.compile(r'[A-Z]:[\\/]|\\Users\\|/Users/|OneDrive', re.I),
    'account_or_desktop': re.compile(r'Gmail|Outlook|Microsoft account|Sign in|notifications|Task Manager|Windows Security|Steam Community|Shift\+Tab', re.I),
    'address_or_phone_like': re.compile(r'\b\d{3}[- .]\d{3}[- .]\d{4}\b'),
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('video', type=Path)
    parser.add_argument('--root', type=Path, default=Path('.'))
    parser.add_argument('--interval', type=float, default=1.)
    parser.add_argument('--threads', type=int, default=2)
    args = parser.parse_args()
    if args.interval <= 0:
        raise ValueError('Sample interval must be positive')
    root, source = args.root.resolve(), args.video.resolve()
    if root not in source.parents:
        raise ValueError('Source must be in this private workspace')
    relative = source.relative_to(root).as_posix()
    sha = digest(source)
    key = hashlib.sha256((relative + sha + str(args.interval)).encode()).hexdigest()[:20]
    output = root / 'postproduction/text-review' / key
    output.mkdir(parents=True, exist_ok=True)
    metadata = output / 'coverage.json'
    if metadata.exists() and json.loads(metadata.read_text()).get('scan_finished'):
        print(json.dumps({'already_scanned': relative, 'coverage': str(metadata)}))
        return
    from rapidocr import RapidOCR
    engine = RapidOCR(params={
        'Global.model_root_dir': str(root / 'postproduction/models/rapidocr'),
        'Global.log_level': 'warning', 'Global.use_cls': False,
        'EngineConfig.onnxruntime.intra_op_num_threads': args.threads,
        'EngineConfig.onnxruntime.inter_op_num_threads': 1,
    })
    names = {getpass.getuser().casefold()}
    if 'Users' in root.parts:
        names.add(root.parts[root.parts.index('Users') + 1].casefold())
    completed = {}
    records = output / 'ocr-samples.jsonl'
    if records.exists():
        for line in records.read_text(encoding='utf-8').splitlines():
            row = json.loads(line)
            completed[row['sample_index']] = row
    report = {'path': relative, 'sha256': sha, 'method': 'local RapidOCR 3.9.2 PP-OCRv6 small',
              'sampling_interval_seconds': args.interval, 'scan_finished': False,
              'privacy_review': 'PENDING - sampled OCR is not full visual or audio review',
              'frames_decoded': 0, 'ocr_samples': len(completed), 'flagged_samples': 0,
              'limitation': 'Can miss brief overlays, faces, non-text content and OCR failures. No audio examined.'}
    status = root / 'postproduction/text-review-status.json'
    first = last = None
    next_index = 0
    seen_flags = set()
    started = time.time()
    with av.open(str(source)) as container:
        stream = container.streams.video[0]
        stream.thread_type = 'AUTO'
        stream.codec_context.thread_count = 2
        for frame in container.decode(stream):
            report['frames_decoded'] += 1
            if frame.time is None:
                raise ValueError('Frame has no timestamp')
            if first is None:
                first = frame.time
            last = frame.time - first
            if last + .0001 < next_index * args.interval:
                continue
            index = next_index
            next_index += 1
            if index in completed:
                continue
            # Local array input only: the OCR service never receives a URL or file
            # upload. The model runs on this computer.
            result = engine(frame.to_ndarray(format='bgr24'))
            texts = list(result.txts or [])
            joined = '\n'.join(texts)
            flags = [name for name, pattern in RULES.items() if pattern.search(joined)]
            if any(name and re.search(r'\b' + re.escape(name) + r'\b', joined, re.I) for name in names):
                flags.append('local_account_name_like')
            row = {'sample_index': index, 'source_seconds': last, 'texts': texts,
                   'scores': [float(x) for x in (result.scores or [])], 'flags': flags}
            if flags:
                text_key = hashlib.sha256(joined.encode()).hexdigest()
                if text_key not in seen_flags:
                    image = f'flag-{index:07}.png'
                    frame.to_image().save(output / image)
                    row['review_image'] = image
                    seen_flags.add(text_key)
                report['flagged_samples'] += 1
            with records.open('a', encoding='utf-8') as f:
                f.write(json.dumps(row, ensure_ascii=False) + '\n')
            completed[index] = row
            report['ocr_samples'] = len(completed)
            status.write_text(json.dumps({'at': time.time(), 'path': relative, 'through_seconds': last,
                                         'ocr_samples': len(completed), 'privacy_review': 'pending'}), encoding='utf-8')
            if len(completed) % 30 == 0:
                metadata.write_text(json.dumps(report, indent=2), encoding='utf-8')
    report.update(scan_finished=True, first_pts=first, last_source_seconds=last,
                  flagged_samples=sum(bool(r['flags']) for r in completed.values()),
                  processing_seconds=time.time() - started, completed_at=time.time())
    metadata.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({'path': relative, 'ocr_samples': len(completed),
                      'flagged_samples': report['flagged_samples'], 'coverage': str(metadata),
                      'privacy_review': 'pending'}), flush=True)


if __name__ == '__main__':
    main()
