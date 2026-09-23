"""Build original vector layouts around explicitly supplied game screenshots.

Facts and screenshots must be reviewed before publication. This script neither
uploads files nor grants privacy clearance. Game imagery is not source licensed.
"""
import argparse
import base64
import html
import json
from pathlib import Path


def text(x, y, value, size=24, color='#fff4d8', weight=400):
    return (f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" '
            f'font-weight="{weight}">{html.escape(str(value))}</text>')


def rect(x, y, w, h, fill='#253029', radius=12, stroke='#536046'):
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')


def picture(path, x, y, w, h):
    data = base64.b64encode(path.read_bytes()).decode('ascii')
    return (f'<image x="{x}" y="{y}" width="{w}" height="{h}" '
            f'preserveAspectRatio="xMidYMid meet" href="data:image/png;base64,{data}"/>')


def document(elements):
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="900" '
            'viewBox="0 0 1200 900"><style>text{font-family:Segoe UI,Arial,sans-serif}</style>'
            '<rect width="1200" height="900" fill="#131d19"/>'
            '<path d="M36 30H1164" stroke="#e9b85c" stroke-width="4"/>'
            + ''.join(elements) + '</svg>')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--facts', type=Path, required=True)
    p.add_argument('--completion-image', type=Path, required=True)
    p.add_argument('--speech-image', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    facts = json.loads(a.facts.read_text(encoding='utf-8'))
    if not facts['main_story_complete']:
        raise ValueError('Completion graphics require verified completion')
    a.output.mkdir(parents=True, exist_ok=True)
    e = [text(36, 89, 'GPT-6 ASTRA + JEV', 24, '#e9b85c', 700),
         text(36, 140, 'The road to an independent New Vegas', 42, weight=700),
         rect(36, 168, 450, 338),
         text(64, 236, 'ABOUT', 20, '#c2c9b4', 600),
         text(60, 327, f"{facts['rounded_recorded_hours']} hours", 74, '#ffc661', 700),
         text(64, 370, 'across recorded sessions', 27),
         text(64, 414, 'Includes recorded pauses and retries.', 20),
         text(64, 446, 'Excludes long unrecorded breaks.', 20),
         text(64, 478, 'Recorded time, not pure active play.', 20, '#c2c9b4'),
         picture(a.completion_image, 524, 162, 640, 360),
         text(526, 547, 'Actual game completion screen', 18, '#c2c9b4')]
    for i, milestone in enumerate(facts['milestones']):
        x, y = 36+(i % 4)*286, 576+(i//4)*125
        e.extend([rect(x, y, 270, 110),
                  text(x+16, y+29, f'{i+1:02}', 18, '#ffc661', 700),
                  text(x+16, y+59, milestone['title'], 23, weight=700),
                  text(x+16, y+86, milestone['detail'], 16, '#c2c9b4')])
    e.extend([text(36, 849, 'Verified scope: main story. Independent / Yes Man ending.', 21),
              text(36, 878, 'Supervised play, with loops, retries and recoveries.', 18, '#c2c9b4')])
    (a.output/'milestones.svg').write_text(document(e), encoding='utf-8')
    e = [text(36, 89, 'GPT-6 ASTRA + JEV  /  FALLOUT: NEW VEGAS', 23, '#e9b85c', 700),
         text(36, 140, 'Speech 100 settled the final showdown', 43, weight=700),
         picture(a.speech_image, 36, 177, 744, 418.5),
         text(36, 626, 'Actual Lanius dialogue from the recorded run', 19, '#c2c9b4')]
    for i, (label, number) in enumerate([('LEVEL', facts['level']), ('SPEECH', facts['speech']), ('GUNS', facts['guns'])]):
        y = 177+i*140
        e.extend([rect(824, y, 340, 125), text(846, y+35, label, 20, '#c2c9b4', 700),
                  text(846, y+101, number, 63, '#ffc661', 700)])
    e.extend([text(825, 626, 'Final protected checkpoint', 19, '#c2c9b4'),
              rect(36, 665, 1128, 132),
              text(60, 716, f"{facts['loaded_rounds']} round loaded", 32, '#ffc661', 700),
              text(60, 756, facts['weapon']+' after Lanius', 23),
              text(620, 710, 'Lanius + General Oliver withdrew', 26, weight=700),
              text(620, 750, 'through Speech dialogue.', 25),
              text(36, 850, 'Jev: rapid decisions. Astra: planning, controls, recoveries and the finish.', 23),
              text(36, 880, 'Independent ending verified in the slideshow, credits and completion screen.', 18, '#c2c9b4')])
    (a.output/'final-build.svg').write_text(document(e), encoding='utf-8')
    print(json.dumps({'svg_files':['milestones.svg','final-build.svg'], 'publication_review':'pending'}))


if __name__ == '__main__':
    main()
