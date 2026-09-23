"""Add traceable public commentary and chapters to the private story timeline.

Positions are editorial proposals. They still require matching-scene and final
export review. This tool never publishes or clears privacy.
"""
import argparse
import copy
import datetime
import json
from pathlib import Path


SELECTED = [0, 3, 4, 6, 11, 18, 21, 27, 28, 30, 31, 34, 36, 37, 38,
            45, 50, 55, 64, 66, 67, 68, 69, 70, 71]
# Public action labels only; request identifiers stay in private provenance.
JEV_ACTIONS = [
    '0db5765f-5a18-4f41-af99-a804c88363a3',
    '6557444d-a0e3-4f30-b65c-f43185b1ac0e',
    'bb6c358a-0760-4e90-97e0-44261a0ff70d',
    '7987f0e7-efb9-4091-b82d-dec4ecf027fa',
    'aea2d698-d323-44a5-a7cb-a1257b55ae1f',
]
JEV_DISPLAY = {
    '0db5765f-5a18-4f41-af99-a804c88363a3': 'Open Mick and Ralphs shop door',
    '6557444d-a0e3-4f30-b65c-f43185b1ac0e': 'Talk to Ralph',
    'bb6c358a-0760-4e90-97e0-44261a0ff70d': "Search Benny's inventory",
    '7987f0e7-efb9-4091-b82d-dec4ecf027fa': 'Move toward the southern pass',
    'aea2d698-d323-44a5-a7cb-a1257b55ae1f': 'Aim and fire at the Centurion',
}
CHAPTERS = [
    ('campaign-004', 0, 'A fresh start in Goodsprings'),
    ('campaign-014', 0, 'Resuming the road to Primm'),
    ('campaign-019', 0, 'The Bison Steve and Beagle'),
    ('campaign-022', 0, 'The road through Nipton'),
    ('campaign-023', 0, 'Novac and the trail to Benny'),
    ('campaign-024', 0, 'Boulder City and Veronica'),
    ('campaign-025', 0, 'Freeside and a way into the Strip'),
    ('campaign-026', 0, 'Benny: setback, retry and the Platinum Chip'),
    ('campaign-027', 0, 'Yes Man and the independent route'),
    ('campaign-028', 0, 'The Lucky 38 and Mr. House'),
    ('campaign-030', 0, 'Faction contacts and the first Nellis attempt'),
    ('campaign-031', 0, 'Resupply and the Brotherhood'),
    ('campaign-032', 0, 'The road to the Great Khans'),
    ('campaign-033', 0, 'Another Nellis attempt'),
    ('campaign-034', 0, 'Side Bets and El Dorado'),
    ('campaign-035', 0, 'Hoover Dam and a crash recovery'),
    ('campaign-037', 0, 'Crossing the dam with scarce ammunition'),
    ('campaign-038', 0, 'Lanius, Oliver and Speech 100'),
    ('campaign-038', 1667, 'The independent New Vegas ending'),
    ('campaign-038', 1852, 'Closing credits and the paranoid part'),
    ('campaign-039', 35, 'Completion verified'),
]


def output_at(clips, session, source_time):
    candidates = [c for c in clips if c['session'] == session]
    if not candidates:
        return None
    clip = next((c for c in candidates if c['session_start'] <= source_time < c['session_end']), None)
    if clip is None:
        clip = next((c for c in candidates if c['session_start'] >= source_time), candidates[-1])
    fraction = max(0., min(1., (source_time-clip['session_start'])/(clip['session_end']-clip['session_start'])))
    return clip['output_start'] + fraction * clip['output_seconds']


def add_caption(clips, at, duration, label, text, evidence):
    stop = at + duration
    assigned = 0.
    for clip in clips:
        left = max(at, clip['output_start'])
        right = min(stop, clip['output_start'] + clip['output_seconds'])
        if right - left > .01:
            clip.setdefault('captions', []).append({
                'start': round(left - clip['output_start'], 6),
                'end': round(right - clip['output_start'], 6), 'label': label,
                'text': text, **evidence})
            assigned += right-left
    if abs(assigned-duration) > .05:
        raise ValueError('Caption was not fully placed')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path('.'))
    parser.add_argument('--timeline', type=Path, default=Path('postproduction/story-draft.json'))
    parser.add_argument('--output', type=Path, default=Path('postproduction/story-editorial-draft.json'))
    args = parser.parse_args()
    root = args.root.resolve()
    data = copy.deepcopy(json.loads(args.timeline.read_text(encoding='utf-8')))
    candidates = json.loads((root/'postproduction/public-commentary-candidates.json').read_text(encoding='utf-8'))
    raw = [json.loads(s) for s in (root/'commentary.jsonl').read_text(encoding='utf-8').splitlines() if s.strip()]
    authentic = {(s.get('at_utc'), s.get('text')) for s in raw}
    actions = [json.loads(s) for s in (root/'actions.jsonl').read_text(encoding='utf-8').splitlines() if s.strip()]
    actions = [s for s in actions if s.get('phase') == 'input_sent' and s.get('recording', {}).get('video_frames')]
    sessions = {}
    for p in sorted(root.glob('campaign-*/session.json')):
        s = json.loads(p.read_text(encoding='utf-8-sig'))
        sessions[p.parent.name] = s
    clips = data['clips']
    for clip in clips:
        clip.pop('captions', None)
    placements, pending = [], []
    last_stop = 0.
    for index in SELECTED:
        q = candidates[index]
        if (q['at_utc'], q['text']) not in authentic:
            raise ValueError('Public quote does not exactly match its source log')
        epoch = datetime.datetime.fromisoformat(q['at_utc']).timestamp()
        action = min(actions, key=lambda s: abs(s['at']-epoch))
        session = action['recording']['session']
        source_time = action['recording']['video_frames']/30 + epoch-action['at']
        start = output_at(clips, session, source_time)
        if index == 0:
            session, source_time, start = 'campaign-004', 417., 28.
        if start is None:
            pending.append({'candidate_index': index, 'reason': 'Source session is not ready', 'session': session})
            continue
        duration = max(9., min(25., len(q['text'].split())/2.5 + 2))
        end_of_session = max(c['output_start']+c['output_seconds'] for c in clips if c['session'] == session)
        start = max(last_stop+3 if placements else 0., min(start, end_of_session-duration))
        if start < 0 or start + duration > end_of_session + .01:
            pending.append({'candidate_index': index, 'reason': 'Insufficient space without overlapping another quote', 'session': session})
            continue
        evidence = {'source_at_utc': q['at_utc'], 'source_log': 'commentary.jsonl',
                    'candidate_index': index,
                    'placement_note': 'Public update from this story section; not claimed synchronous speech or private reasoning.'}
        add_caption(clips, start, duration, 'GPT-6 ASTRA - PUBLIC UPDATE FROM THE RUN', q['text'], evidence)
        placements.append({'candidate_index': index, 'text': q['text'], 'source_at_utc': q['at_utc'],
                           'session': session, 'proposed_source_seconds': source_time,
                           'output_start': start, 'output_end': start+duration,
                           'matching_scene_review': 'pending', 'kind': 'authentic public commentary'})
        last_stop = start+duration
    credits = output_at(clips, 'campaign-038', 1852)
    if credits is not None:
        p = json.loads((root/'postproduction/editorial-commentary.json').read_text(encoding='utf-8'))['paranoid_part']
        at = credits+5
        add_caption(clips, at, 18, 'THE PARANOID PART - RETROSPECTIVE', p['narration'], {'not_a_live_quote': True})
        placements.append({'kind': 'clearly labeled retrospective', 'output_start': at,
                           'output_end': at+18, 'text': p['narration'], 'matching_scene_review': 'pending'})
        add_caption(clips, at+25, 15, 'GPT-6 ASTRA + JEV - RETROSPECTIVE',
                    'Jev supplied rapid decisions. Astra planned, improved controls and recovered failures, then finished the normal game inputs after Jev reached its cap.',
                    {'not_a_live_quote': True})
    result_path = root/'world-results.jsonl'
    result_rows = [json.loads(s) for s in result_path.read_text(encoding='utf-8').splitlines() if s.strip()]
    wanted_ids = set(JEV_ACTIONS)
    decisions = {}
    with (root/'world-decisions.jsonl').open(encoding='utf-8') as source:
        for line in source:
            row = json.loads(line)
            if row.get('request_id') in wanted_ids:
                decisions[row['request_id']] = row
    jev_placements = []
    for request_id in JEV_ACTIONS:
        result = next((r for r in result_rows if r.get('request_id') == request_id and r.get('input_sent')), None)
        if result is None:
            raise ValueError('Selected Jev action lacks a dispatched-input result')
        decision = decisions.get(request_id, {})
        if (decision.get('choice') != result.get('choice')
                or not decision.get('answer', {}).get('model', '').startswith('jev-')):
            raise ValueError('Selected action lacks the matching Jev decision')
        related = [a for a in actions if request_id in a.get('request_id', '')]
        action = min(related or actions, key=lambda s: abs(s['at']-result['at']))
        session = action['recording']['session']
        source_time = action['recording']['video_frames']/30 + result['at']-action['at']
        at = output_at(clips, session, source_time)
        if at is None:
            continue
        # Short summaries verified against the result and corresponding footage.
        # They are action descriptions, not quotations or reasoning transcripts.
        text = JEV_DISPLAY[request_id]
        if len(text) > 145:
            raise ValueError('Action label needs explicit editorial shortening')
        stop = min(at+5, data['output_seconds'])
        evidence = {'style': 'Action', 'source_log': 'world-results.jsonl',
                    'source_request_id': request_id, 'kind': 'summary of a recorded action',
                    'original_action_label': result['action']}
        add_caption(clips, at, stop-at, 'JEV - RECORDED ACTION', text, evidence)
        jev_placements.append({'text': text, 'source_request_id': request_id,
                               'session': session, 'source_seconds': source_time,
                               'output_start': at, 'output_end': stop, 'matching_scene_review': 'pending'})
    chapters = []
    for session, at, title in CHAPTERS:
        start = output_at(clips, session, at)
        if start is not None:
            if chapters and start-chapters[-1]['output_start'] < 1:
                continue
            chapters.append({'title': title, 'output_start': start, 'source_session': session,
                             'source_seconds': at, 'review': 'proposed; verify actual export'})
    data['chapters'] = chapters
    data['editorial_commentary'] = {'placements': placements, 'pending': pending,
                                     'jev_actions': jev_placements,
                                     'status': 'Private proposed scene placement; final review pending'}
    data['difficulty_disclosure'] = 'Started on Normal; changed to Very Easy during the Primm attempts. Hardcore mode off, as verified in the recorded settings.'
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    timing_label = data.get('presentation', {}).get('elapsed_time', {}).get('headline')
    first_chapter = '00:00 GPT-6 Astra + Jev' + (' - ' + timing_label if timing_label else '')
    lines = ['PRIVATE CHAPTER DRAFT - regenerate after the final edit', first_chapter]
    for chapter in chapters:
        sec = int(chapter['output_start'] + 9)
        lines.append(f'{sec//3600:02}:{sec//60%60:02}:{sec%60:02} {chapter["title"]}')
    (args.output.parent/'chapter-draft.txt').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print(json.dumps({'output': str(args.output), 'clips': len(clips), 'chapters': len(chapters),
                      'commentary_placements': len(placements), 'pending_commentary': pending,
                      'pending_sessions': data.get('pending'), 'privacy_review': 'pending'}, indent=2))


if __name__ == '__main__':
    main()
