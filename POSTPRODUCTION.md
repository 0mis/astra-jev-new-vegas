# Private recording and editing workflow

The editing scripts were developed for this recorded campaign. They need local recording folders, action logs and reviewed editorial decisions. Private inputs, raw recordings, transcripts and generated outputs are deliberately not distributed. These tools do not publish, grant privacy clearance or reconstruct damaged or missing footage.

Install the main requirements plus `requirements-postproduction.txt`. Use Python 3.12 on Windows. The tested FFmpeg executable comes from `imageio-ffmpeg`; `render_story_draft.py` uses normal software H.264 unless `--encoder h264_nvenc` is supplied on compatible NVIDIA hardware. Successful hardware enumeration is insufficient: run and inspect a real sample export before relying on it.

## Input layout

Use closed recorder directories named `campaign-001`, `campaign-002`, and so on. Each has `session.json`, `video-*.mkv`, audio chunks and capture progress. `actions.jsonl` contains dispatched input receipts and their contemporaneous video/audio counters. `commentary.jsonl` contains deliberately public updates with `at_utc` and `text`; never supply private reasoning transcripts.

Recovered media live under the original session's `recovered` directory. Originals remain untouched. Keep the failure record: a recovered file is not evidence that the original was complete.

## Workflow

1. Run `media_inventory.py` to hash and fully decode closed media. Check errors, sample counts, duration, capture warnings and recovered files.
2. Run `transcribe_recordings.py` for private local machine transcripts. It downloads an open model on first use. Transcripts are imperfect and cannot replace listening. Word timestamps protect dialogue; segment boundaries can span long silent intervals.
3. Run `detect_pause_frames.py` with actual observed menu reference images. It checks every decoded frame at the validated 1280x720 resolution. Templates are campaign-specific; inspect candidate cuts, including settings and load submenus.
4. Run `build_story_timeline.py` to create `postproduction/story-draft.json`. Missing decode audits, transcripts or pause scans are explicitly pending. The builder uses recorded capture counters for proposed sound alignment, cuts pause candidates and preserves speech. It does not prove sound synchronization.
5. Run `scan_timeline_menus.py` on that timeline with additional observed submenu templates. It checks every frame within the proposed retained spans and resumes by source hash and reviewed spans. Visually verify matches before adding editorial exclusions.
6. Curate `postproduction/editorial-edits.json` and `postproduction/editorial-commentary.json`; run `apply_story_editorial.py` for draft chapters and overlays. Its selected commentary indexes, chapter boundaries and the builder's opening/ending treatment belong to this campaign. Adapt them explicitly for another run. Public quotations are matched exactly to their source log. Retrospective narration has a separate label. The paranoid segment takes explicit `paranoid_part.replay_sources` entries from the private commentary JSON, each with `video`, `video_in`, `video_out` and a `review` evidence string. Each replay must fit within an already retained source span; its audio mapping is copied from that span. Replays are labeled and receive a separate chapter before credits.
7. Render a private draft with `render_story_draft.py`. Use `--filename` for a plain MP4 basename. Output must stay beneath the local `postproduction` directory. Raw source hashes are checked before rendering; output is inspected by full decode. FLAC intermediates use one sample format to prevent silent audio loss when concatenating unlike streams.
8. Review the actual edit's scene coverage, dialogue, transitions, sound alignment and acceleration labels. Check the full output, not only successful encoding or selected frames. Then perform the complete required footage/audio privacy review and final export review before publication.

Example rendering command after preparing and reviewing the local timeline:

```powershell
.\.venv\Scripts\python.exe render_story_draft.py postproduction/story-editorial-draft.json --output postproduction/drafts/full-story --filename private-full-story-draft.mp4 --encoder h264_nvenc
```

Add `--clean-presentation` only when preparing the final appearance: it removes draft watermarks while retaining credits, speed labels and replay labels. It does not upload the file or clear review. All outputs and review statuses stay private and pending. Unchanged accelerated clips keep their validated cache; changed pixels receive a separate cache identity. During save replays, credits move away from the game's Quicksaving indicator.

Jev action labels sit at the top right, below the speed label, to avoid the game's save and quest notifications. The timeline builder pads observed pause candidates by 0.7 seconds before and 0.6 seconds after, based on reviewed menu fades. Inspect actual boundaries and restart screens; template matches can also be ordinary scenery and must not be cut blindly.

Use `--clips-only` to prepare and fully decode reusable clips while editorial review continues, without assembling a candidate. Run again without that option once the timeline is settled. `--normalize-audio` measures the exact concatenated audio, then performs a second loudness pass targeting -16 LUFS, -1.5 dBTP and an 11 LU loudness range. It keeps the video stream intact and records the measurement locally. Check the encoded result and listen: these processing targets do not prove perceptual quality or privacy. A seven-clip normalized sample fully decoded to 5,360 video frames and 178.67 seconds with matching audio duration. Full-export decoding reports its progress and uses four decoder threads.

An eight-clip production check covered the corrected title, public commentary, a Jev action label, four save replays and accelerated credits. Its assembled output decoded to 9,629 video frames over about 320.97 seconds with matching audio duration. This checks encoding and duration, not complete privacy or perceptual synchronization.

`review_frames.py` creates timestamped image samples. `scan_review_text.py` performs local RapidOCR at an explicitly chosen sampling interval. Neither covers unobserved frames, unintelligible text, faces, personal audio or every possible overlay. Their reports remain pending privacy review even when there are no automatic flags.

## Honest accounting

The run has about 24 hours across recorded sessions (approximately 23h55m50s) between fresh-new-game confirmation and the verified ending. This sums decoded recording intervals, removes overlaps, includes recorded pauses and retries, and excludes long unrecorded breaks. It is not pure active gameplay or edited runtime. The earlier calendar-time headline was withdrawn because it counted long breaks. Keep precise local timestamps private and publish only the duration and its definition.

The output title and captions visibly credit GPT-6 Astra and Jev. The run was supervised, used read-only game telemetry, changed difficulty and included crashes, reloads and loops. Jev reached its capped local budget before Astra finished. No flawless-autonomy or gap-free-recording claim is supported.

## Static presentation graphics

`make_campaign_graphics.py` builds two original SVG layouts around supplied PNG game screenshots: a milestone card with defined recorded-session timing, and a final-checkpoint build card. `presentation-facts.example.json` contains this campaign's verified public facts. Adapt and verify every fact for a different run. Provide inspected screenshots using `--completion-image` and `--speech-image`, the facts file with `--facts`, and a private output folder with `--output`.

The graphics preserve the screenshot's aspect ratio and label what the image shows. Game screenshots, generated images and private proof records are not included in this source package. Rasterize the SVG with a suitable renderer and inspect the entire actual output for text fitting, fact accuracy, private content and metadata before publication. The tested 1200x900 PNG exports were rendered with Sharp. Generating or decoding an artifact never grants publication clearance.
