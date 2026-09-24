# Astra + Jev: Fallout: New Vegas

The Jev/Astra team completed an independent New Vegas main-story run on September 23, 2026. The ending slideshow and credits were observed and recorded. Jev made frequent bounded gameplay choices; Astra developed the controller, planned routes, diagnosed loops and crashes, and handled recoveries. When the local Jev ledger reached its $1 cap, Astra completed the remaining combat and final conversations using ordinary game input.

This is the source of that supervised run. It is not a one-command unattended game player. The campaign required substantial development and intervention. The finished full-main-story edit runs 5h29m52s, with known pause/loading menus removed, accelerated footage labeled, public gameplay commentary, the independent ending, and a retrospective save-check montage.

[Watch the full main story on YouTube](https://youtu.be/tBVq09mDq6g) · [Read the presentation on X](https://x.com/imjustnewatai/status/2102934229180875054).

## What was verified

- Fresh character creation and the Goodsprings tutorial, the lead to Benny, the Platinum Chip, Mr. House, Yes Man, all five Side Bets contacts, El Dorado, Hoover Dam and the independent ending.
- Lanius and General Oliver were persuaded to withdraw through Speech dialogue. The final pre-ending checkpoint was level 9 with Speech 100 and Guns 78.
- Normal keyboard/mouse controls performed movement, interaction, aiming, VATS, dialogue, inventory, fast travel, sleeping and saving. The observer reads version-specific game telemetry and navigation geometry. It does not write game memory, invoke game functions, teleport, issue console commands or force quest stages.
- Crashes, failed routes, deaths and restored attempts occurred. Original recordings and recovery saves were retained privately. Recording interruptions and audio warnings exist; do not describe the capture as gap-free.
- All 147 included regression tests passed in the Windows development environment on September 23. They cover observed failure modes, not proof of universal or unattended completion.

About 24 hours across recorded sessions (approximately 23h55m50s) span the fresh-new-game confirmation through the verified ending. This includes recorded pauses, retries and control setup, with overlap removed and long unrecorded breaks excluded. It is not pure active gameplay or edited runtime. Jev's conservative local ledger finished near $0.99891, including unresolved reservations; that is not a provider invoice or the total cost of Jev plus Astra.

## Setup

Use Windows, Python 3.12, an owned Steam installation of Fallout: New Vegas 1.4.0.525, and your own Typesafe access. The observer verifies the expected executable; its default installation path is in `observe_game.py`. Other executables, patches, mods and installation paths require explicit adaptation and validation.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -p 'test_*.py' -q
```

Back up your saves and settings before playing. The optional `repair_input_settings.ps1` makes backups and configures the dedicated `JevSaves` path and keyboard/mouse input while the game is closed. Verify settings after launching: the launcher can regenerate them. The recorded campaign starts on Normal and changes to Very Easy during the Primm attempts; Hardcore mode is off. Crashes and restored settings occurred, so do not label the entire run as one difficulty.

The client reads `TYPESAFE_API_KEY` from its process environment. Optional PowerShell launchers can read local Windows-user DPAPI ciphertext from `typesafe-key.dpapi`. Never commit credentials, encrypted credentials, logs, saves or recordings. The $1 client ledger reserves budget before a request, settles confirmed usage and preserves uncertain reservations. No automatic purchases, top-ups or network retries are implemented. Do not erase an existing ledger to resume a capped run.

## Running the supervised controller

The game must be foreground with one input owner. Each new recorder requires a unique directory. Verify real video and audible game playback before allowing inputs.

```powershell
$nvPid = (Get-Process FalloutNV).Id
.\.venv\Scripts\python.exe record_game.py --title 'Fallout: New Vegas' --game-pid $nvPid --session recordings/run-001 --seconds 3600 --max-video-kbps 2500 --audio-format aac --audio-backend wasapi_callback
```

Run the independent `loop_watchdog.py` observer before `start_jev_loop.ps1`. Read each command's `--help` and the launcher parameters. The planner supplies scoped, expiring advice and observed destinations; none of the private campaign plans or saved route history is included. Never guess stale process IDs, window handles, worldspace coordinates or current quest state.

Inputs are guarded by fresh recording progress, process identity, focus, stop files and an exclusive input lock. Keys release on failures. The watchdog observes sustained stalls, room cycles and menu loops, requests a handoff, and never sends competing inputs. A recovery requires fresh observation and a changed plan; restarting the same loop is not recovery.

`astra_route_run.py` and `astra_dialogue.py` provide bounded supervised normal-input helpers. The dialogue helper verifies speaker, exact topic and hover before selection; an offscreen topic must be scrolled into view first. These tools still require active human or planner judgment.

## Components

- `observe_game.py`, `navmesh.py`, `portal_atlas.py`: read-only telemetry, loaded-reference checks, floor routing and observed door links.
- `world_controller.py`, `planner_destination.py`, `course_traversal.py`, `travel_memory.py`: scoped travel, multi-stage routes and progression checks.
- `jev_bridge.py`, `jev_loop.py`, `decision_context.py`: typed Jev choices, local budget accounting and compact decision context.
- `game_input.py`, `combat_guard.py`, `vats_controller.py`, menu controllers: bounded input, near-range explosive protection, VATS and observed UI selection.
- `loop_watchdog.py`, `damage_watch.py`, `campaign_checkpoint.py`: independent supervision, injury detection and protected ordinary saves.
- `record_game.py`, `loopback_audio.py`, `capture_progress.py`: window video, system playback audio, finalization and advancing-counter checks.
- `media_inventory.py`, `transcribe_recordings.py`: private full-decode inventory and local machine transcripts for review. Install `requirements-postproduction.txt` for these tools. Neither decoding nor transcription constitutes a privacy review or permission to publish.
- `detect_pause_frames.py`, `scan_timeline_menus.py`: template-based pause candidates and a supplemental check of every retained frame for observed submenus. Unrecognized menus and false matches remain possible; review the proposed cuts.
- `build_story_timeline.py`, `apply_story_editorial.py`, `render_story_draft.py`: campaign-specific rough-cut construction, traceable public commentary, chapter metadata and private rendering. The renderer offers CPU H.264 and optional NVIDIA NVENC, normalizes intermediate audio to FLAC s16 and verifies decoded audio/video durations after assembly.
- `review_frames.py`, `scan_review_text.py`: timestamped review samples and explicitly sampled local OCR. These are review aids, not complete visual/audio review. See `POSTPRODUCTION.md` for data requirements and limitations.

The edit uses actual public gameplay commentary and clearly labeled retrospective narration. It does not present private reasoning transcripts or invented quotes.

## Limitations and provenance

The controller relies on game telemetry, not only screenshots. Navigation meshes omit some props and can connect the wrong floor unless carefully scoped. Dialogues may scroll, scripted scenes temporarily disable controls, and observer state can change during reads. Actor targeting requires an actual rendered actor. The code is version-specific and still needs supervision.

The recording is game-window video plus system playback loopback, not microphone input. Other applications' audio can enter loopback. Decoding, sampled frame checks and machine transcripts do not certify an end-to-end privacy review or establish that every sound is game-only. Review your recordings and final captions, thumbnails and metadata before publishing.

See `ARCHITECTURE.md` and `THIRD_PARTY.md` for design and layout research, including the user-supplied Minecraft agent reference. The implementation is original. No game assets, saves, recordings, dependency binaries or credentials are distributed. The MIT license covers this repository's original source and documentation only.
