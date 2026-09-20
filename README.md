# Astra + Jev: Fallout: New Vegas

An experiment in splitting game decisions between a fast typed model and a planning assistant. **This is a work in progress, not a completed autonomous playthrough.**

The intended division is simple: Typesafe Jev chooses frequent actions from fresh structured game observations. Astra sets objectives, checks mistakes, and handles recovery. A recorder preserves the run, and timestamped public commentary can be added to the eventual video.

## What works so far

- A live `jev-1.13.0` API call completed in 0.596 seconds and selected the correct recording prerequisite. A later main-menu decision took 0.619 seconds. These are individual measurements, not throughput benchmarks.
- The read-only observer returned player and menu data in approximately 22–25 ms on the test machine.
- A 20-second recording pilot produced 604 frames of decoded 1280×720 video at 30 fps, 960,000 stereo audio samples per channel, nonzero sound, and clean finalization.
- Existing saves were backed up before setup.

## What is still unfinished

- Reliable game input and the closed-loop gameplay controller. The initial desktop input test did not activate New Game. There is **no verified autonomous game-playing loop** yet.
- Correct screen-coordinate conversion, map/navigation observations, gameplay safeguards, and recovery tests.
- A complete campaign and verified ending, edited video, YouTube/X publication.
- Recording reliability over a whole campaign. A longer setup capture reported an audio discontinuity; the recorder now logs these warnings explicitly. Inspect them before accepting a recording as complete.

## Requirements

Windows, Python 3.12, a legally installed Steam copy of Fallout: New Vegas 1.4.0.525, and Typesafe API access. Jev is a hosted model; its weights/service and the game are not included. The observer uses version-specific xNVSE layout research and opens the process with read/query permissions only. It does not inject code or write game memory.

Install dependencies in a local virtual environment:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Keep credentials out of source control. `jev_bridge.py` reads `TYPESAFE_API_KEY` from its process environment. For the optional local Windows launcher, create `typesafe-key.dpapi` yourself using the current Windows account's secure-string encryption:

```powershell
$jevSecret = Read-Host 'Typesafe API key' -AsSecureString
$jevSecret | ConvertFrom-SecureString | Set-Content -LiteralPath .\typesafe-key.dpapi
$jevSecret = $null
```

The example client reserves a conservative maximum cost before each request and refuses to exceed a $1 local test cap. It makes no top-ups and no automatic network retries. Run only one decision process at a time; the ledger is not a distributed billing authority. Actual account charges and other API clients are outside its accounting.

## Run the individual components

Use a windowed game with the exact title `Fallout: New Vegas`. Keep other applications away from the game window during capture; occlusion behavior has not been validated.

```powershell
# Replace GAME_PID with the live FalloutNV.exe process ID.
.\.venv\Scripts\python.exe .\observe_game.py GAME_PID

# Session directory must not already exist. Default duration is one hour.
.\.venv\Scripts\python.exe .\record_game.py --title 'Fallout: New Vegas' --session .\recordings\run-001 --seconds 3600

# In another terminal, after verifying the recording:
.\invoke_jev.ps1 -GamePid GAME_PID -RequestFile .\request.example.json -RecordingFolder .\recordings\run-001
```

The decision command reads fresh game state and recording counters, calls Jev once, and records the answer. **It does not send game input.** An executor must independently validate freshness, expected state, and capture health before applying any choice.

To stop a recorder cleanly, create an empty `stop.request` file inside its session directory. Wait for `session.json` to report `stopped`, `audio_finalized: true`, and `video_exit_code: 0`. Do not assume those values prove there were no capture gaps; review frame progress, audio warnings, actual decoded content and durations too.

Video is segmented H.264/MKV; audio is separate 48 kHz stereo PCM/WAV. Audio uses the default playback device's system loopback, so other applications' sounds can be included. No microphone is used. A 5 GiB free-space reserve stops recording before the disk fills. Audio/video start timestamps are stored for later alignment; the files are not yet a finished YouTube upload.

## Files

- `observe_game.py`: bounded, read-only process-memory observations; coordinates are preliminary.
- `jev_bridge.py`: typed Choice API client, conservative budget ledger, public commentary events.
- `decide_game.py`: recording gate plus one observed decision and an execution handoff record.
- `invoke_jev.ps1`: optional local DPAPI credential loader.
- `record_game.py`: segmented capture and health/finalization metadata.
- `request.example.json`: an example objective and legal action choices.
- `ARCHITECTURE.md`: intended controller contract and current limitations.
- `THIRD_PARTY.md`: external services and layout references.

The original project code is MIT-licensed. Credentials, personal data, saves, game binaries/assets, and third-party source bundles are excluded. This is an independent experiment and is not affiliated with Bethesda, Obsidian, Typesafe or OpenAI.
