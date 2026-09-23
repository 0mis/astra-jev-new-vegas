"""Extract timestamped private review samples without modifying source media.

A contact sheet is a navigation aid, never proof of a complete privacy review.
"""
import argparse
import json
from pathlib import Path

import av
from PIL import Image, ImageDraw, ImageFont


def extract(path, seconds):
    result = []
    with av.open(str(path)) as container:
        stream = container.streams.video[0]
        stream.codec_context.thread_count = 2
        first_frame = next(container.decode(stream))
        first = first_frame.time or 0
        for second in seconds:
            target = first + second
            container.seek(int(target / float(stream.time_base)), stream=stream, backward=True)
            for frame in container.decode(stream):
                if frame.time is not None and frame.time >= target - .017:
                    result.append((frame.time - first, frame.to_image()))
                    break
            else:
                raise ValueError(f'No frame available at {second} seconds')
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path)
    parser.add_argument('--seconds', type=float, nargs='+', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--columns', type=int, default=2)
    parser.add_argument('--width', type=int, default=640)
    args = parser.parse_args()
    frames = extract(args.source, args.seconds)
    args.output.mkdir(parents=True, exist_ok=True)
    height = int(args.width * 9 / 16) + 28
    rows = (len(frames) + args.columns - 1) // args.columns
    sheet = Image.new('RGB', (args.width * args.columns, height * rows), '#121519')
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype('C:/Windows/Fonts/consola.ttf', 17)
    except OSError:
        font = ImageFont.load_default()
    records = []
    for i, (second, frame) in enumerate(frames):
        file = f'frame-{i:03}-{second:.3f}.png'
        frame.save(args.output / file)
        records.append({'source_seconds': second, 'image': file})
        frame.thumbnail((args.width, height - 28))
        x, y = i % args.columns * args.width, i // args.columns * height
        sheet.paste(frame, (x, y + 28))
        draw.text((x + 9, y + 4), f'{args.source.parent.name}/{args.source.name}  {second:.3f}s', fill='white', font=font)
    sheet.save(args.output / 'contact.png')
    (args.output / 'samples.json').write_text(json.dumps({
        'source': str(args.source), 'samples': records,
        'scope': 'Selected frames only; full visual and audio review remains pending'
    }, indent=2), encoding='utf-8')
    print(json.dumps({'contact': str(args.output / 'contact.png'), 'samples': len(frames)}))


if __name__ == '__main__':
    main()
