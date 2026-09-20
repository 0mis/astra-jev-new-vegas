# Architecture and progress contract

The target pipeline is:

```text
Game -> read-only observations -> Jev typed action choice -> guarded normal input -> Game
             |                          |
             +--- Astra objectives -----+
             +--- evidence and public commentary
Recorder health ----------------> gate every gameplay action
```

The repository implements observation, decision, recording and bounded normal input. The continuous loop has executed Jev's opening notification and character-name choices in the live game. It supports only those opening menus and the main-menu confirmation, and deliberately yields unfamiliar states to the planner. Full gameplay control remains under development.

## Observation limits

The observer is specific to FalloutNV.exe 1.4.0.525 and the unmodified layouts referenced in THIRD_PARTY.md. Its executable-path/MZ checks are not a complete version verifier. Do not use it on another build or assume it is portable across mods.

Menu labels were checked against the visible main menu. Tile x/y values are virtual UI coordinates, not validated click targets. Menu visibility and labels may change while memory is read. Main-menu player coordinates are placeholders and do not prove an in-world location. Missing or stale state must stop the executor.

## Decision contract

The planner supplies an objective, observed context, allowed choices and instructions. Jev returns one Choice value with confidence and usage. Confidence is not proof that the action is correct. The executor should accept only known choices, reject stale observations, check expected menus and recording health, and log the request identity before sending input.

An uncertain action triggers fresh observation, not a blind retry. The input executor uses an exclusive lock, bounded holds, key release on failure, foreground checks and recording gates. The menu loop rejects stale replies and changed control sets and stops if activation fails to change the menu. Separate API-client ownership prevents simultaneous budget-ledger writers. Individual action IDs are logged, but the executor does not yet implement durable duplicate-ID rejection; a caller must not replay uncertain requests.

Jev chooses a menu item from fresh observed alternatives. Code performs the mechanical key navigation to that exact item and releases the activation key when the visible menu changes. No Astra approval is required between supported menu choices. No game simulation pause or time stepping is used. Code currently hands appearance and world navigation back to Astra because those controls are unfinished, rather than pretending Jev can act on unsupported observations.

## Recording contract

Before campaign input, decode a real sample, check actual video/audio progress and verify clean finalization of a pilot. During play, inspect timestamps and advancing counters. The current gate checks fresh recording state, increasing video frames and positive audio frames; it is only a starting point, not a guarantee of continuous capture or process identity.

Record a capture failure explicitly and pause gameplay for recovery. Preserve raw footage, segment order, start timestamps, warnings and logs. Never describe unrecorded play as continuously recorded. Long-duration audio sync, background-window capture, recorder crash recovery and segmentation still require validation.

## Commentary and evidence

Commentary is a short public gameplay update: an objective, observation, result, or recovery note. It is not a transcript of private model reasoning. Label actual Jev choices as choices, not invented quotations or free-form thoughts. Keep live notes distinguishable from later editorial narration.

Completion requires a verified main-story ending in the new campaign, preserved footage, published YouTube/X results and this public source repository. Old saves and unrelated prior game completions do not satisfy that requirement.
