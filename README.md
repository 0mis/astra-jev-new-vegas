# Astra + Jev: Fallout: New Vegas

A work in progress: Jev selects frequent typed actions, Astra develops and supervises the controller, and local recording preserves gameplay. The campaign is **not complete**, and this is not yet an unattended full-game player.

## Verified progress

- Jev completed the recorded opening prompts, default character creation and most attribute allocation; Astra supplied one Perception increment during calibration.
- Normal keyboard and measured relative mouse input walked to and activated the Vigor Tester. A read-only floor mesh route then took the character around an interior wall to the couch, which it activated successfully.
- The opening-room navigation pilot reads quest targets, loaded references, crosshair identity and actual camera position. This is game telemetry, not image recognition. No game-memory writes, console commands, teleportation or quest cheats are used.
- Jev completed Doc Mitchell's opening and discharge, crossed Goodsprings, entered the Prospector Saloon, spoke with Sunny Smiles and completed her bottle-shooting lesson. The active objective advanced to following her toward the water source. Suggested Guns, Sneak and Speech tags were accepted before the broader autonomy policy was introduced. Creature combat and many later menus remain unverified.
- A six-request benchmark measured a 193.5 ms warm Jev median over five warm calls, with a 505.5 ms cold request. These are decision latencies, not gameplay frame rates.
- The corrected 45-second capture pilot decoded 45.53 seconds of 720p30 video and 45.035 seconds of stereo audio, with zero reported audio discontinuities and clean encoder exits. Whole-campaign reliability is not established.
- Two later segments each reported one audio discontinuity during paused intermissions. Those segments and warnings are preserved. The latest recorder moves disk/window checks and status publication away from audio capture, uses a two-second buffer, and passed a 45-second decoded pilot (45.433 seconds video,45.035 seconds audio) with zero warnings. This does not establish gap-free long-duration capture.

## Requirements and credentials

Windows, Python 3.12, an owned Steam copy of Fallout: New Vegas 1.4.0.525 and Typesafe API access. Install `requirements.txt` into `.venv`. Layouts are version-specific; modified executables or mods can invalidate them.

The client reads `TYPESAFE_API_KEY` from its environment. The optional PowerShell launchers load Windows-user DPAPI ciphertext from `typesafe-key.dpapi`:

```powershell
$jevSecret = Read-Host 'Typesafe API key' -AsSecureString
$jevSecret | ConvertFrom-SecureString | Set-Content -LiteralPath .\typesafe-key.dpapi
$jevSecret = $null
```

One client owns a durable local $1 test ledger. It reserves a conservative cost before dispatch, settles successful requests using reported input-token usage and retains reservations for uncertain requests. Legacy ledger entries remain conservative. There are no purchases, top-ups or automatic network retries. Other API clients and account billing are outside this ledger.

## Recording and input

Back up existing saves first. The local pilot uses a separate `JevSaves` path. `repair_input_settings.ps1` backs up both game INIs and sets that path, `bUse Joystick=0` and `bDisable360Controller=1` while the game is closed. The launcher can regenerate settings, so verify them again afterward.

```powershell
$nvPid = (Get-Process FalloutNV).Id
# A new session directory is required. Capture binds to the PID and exact HWND.
.\.venv\Scripts\python.exe .\record_game.py --title 'Fallout: New Vegas' --game-pid $nvPid --session .\recordings\run-001 --seconds 3600
# In another terminal, after verifying real recorded video and sound:
.\start_jev_loop.ps1 -GamePid $nvPid -RecordingFolder .\recordings\run-001 -Seconds 300
```

The default recording is segmented H.264/MKV at 720p30, a 1500 kbps video ceiling, and separate AAC stereo audio at 128 kbps. WAV is optional. A bounded queue separates audio capture from encoding. Audio is system playback loopback, never microphone input; other applications' sounds can be included. The estimated 72-hour encoded payload is about 49.1 GiB before overhead. A 5 GiB free-space reserve stops capture. This size estimate is not a long-duration reliability test.

Keep the game foreground and unobscured during play; background capture has not been validated. Inputs require matching game/recording identity, fresh advancing video and audio encoding counters, no audio discontinuity, and exclusive controller ownership. Held inputs are released on errors. At handoff, the loop tries normal Escape only in a recognized gameplay state and verifies the pause menu. Unsupported menus or lost focus can prevent that pause; inspect the result rather than assuming success.

Create `controller.stop` beside the scripts to request a controller stop. To finalize recording, create `stop.request` inside its session directory and verify clean exits, audio finalization, warnings and decoded content. Preserve original segments, timestamps and logs for later editing.

## Jev world controls

Once ordinary unpaused gameplay is recorded, run the small camera calibration, then enable world controls:

```powershell
.\.venv\Scripts\python.exe .\calibrate_mouse.py --pid $nvPid --recording .\recordings\run-001
.\start_jev_loop.ps1 -GamePid $nvPid -RecordingFolder .\recordings\run-001 -Seconds 300 -World
```

Calibration moves the view slightly and writes a machine-specific `mouse-calibration.json`. Jev chooses nearby targets, floor routes or direct approaches, normal movement and looking, interactions, weapon controls, dialogue and recoveries. Recent outcomes and disabled-control flags are part of each decision. Repeated ineffective actions temporarily cool down, with Astra assistance for sustained stalls or missing interfaces. Ordinary choices do not require planner approval.

The current optimization uses bounded route skills, useful action filtering and nonblocking planning advice. Route execution can perform up to three seconds of observed normal steering per Jev choice. The planner mailbox scopes advice to the observed quest stage and ignores expired or mismatched plans. It uses the existing Codex task; it does not start a second planner API client. Reusable recovery lessons describe actual controller failures. See ARCHITECTURE.md and THIRD_PARTY.md for the design reference.

Floor routing joins matching triangle edges across loaded meshes and exterior cells. The observer distinguishes interior coordinate frames, follows paired door destinations, reads both ends of door locks and exposes the active journal. Persistent-cell metadata retains a distant quest target's coordinate frame. A partial route can approach an objective beyond the currently connected floor. Straight shortcuts require continuous floor-triangle and height coverage; geometry tests cover missing floor, different elevation and a blocked corner. One sampled route reduced21waypoints to3 in0.208seconds of calculation; this is not a whole-run speed benchmark.

The aiming skill uses an observed rendered-object center, bounded normal mouse correction and one normal shot. It completed the bottle lesson. Actor life state and current combat targets support a preliminary combat interface; health, ammunition, broader faction hostility, later menus and full-game reliability remain unfinished. Read `loop-status.json` before resuming. Logged action IDs do not yet provide durable duplicate-action rejection: never blindly replay an uncertain action.

`observe_game.py`, `navmesh.py`, `world_controller.py` and `vigor_controller.py` implement read-only observations and the tutorial pilot. `jev_bridge.py`, `jev_loop.py` and `game_input.py` implement decisions and bounded normal execution. `record_game.py` and `decide_game.py` implement recording and health gates. `benchmark_jev.py` performs read-only latency samples. The launchers are optional local credential loaders.

The eventual video will use timestamped public gameplay commentary and actual selected actions, not private reasoning transcripts or invented Jev quotations. Editing and YouTube/X publication follow a verified ending; neither has been completed for this campaign.

Original code is MIT-licensed. Secrets, personal data, game assets, saves and third-party source bundles are excluded. See THIRD_PARTY.md for layout and dependency sources. This independent experiment is not affiliated with Bethesda, Obsidian, Typesafe or OpenAI.
