# Music Assistant Alarm Clock

A Home Assistant integration that turns any Music Assistant player into an alarm
clock: it wakes you with a radio station or a playlist from your own Music
Assistant library, fades the volume in, and can bring a wake-up light up before
the music starts.

Music Assistant itself has no alarm clock, and its provider system only loads
providers that ship inside the server package — so this lives in Home Assistant,
where the lights are anyway.

<img width="2296" height="2353" alt="image" src="https://github.com/user-attachments/assets/16511b20-f675-45ed-be3c-ab87549d9919" />

<img width="1206" height="1575" alt="image" src="https://github.com/user-attachments/assets/68d8c07c-8e1b-4519-a762-5bdaaf30b77f" />


## What you get

Add one alarm per person or per room. Each one is a config entry with its own
device and its own entities:

| Entity | What it does |
|---|---|
| `switch` **Alarm** | The master switch |
| `switch` **Monday … Sunday** | Which days it is armed on |
| `time` **Wake-up time** | When it goes off |
| `select` **Wake-up sound** | Every radio station and playlist in your Music Assistant library |
| `number` **Volume** | The volume it ends up at |
| `number` **Fade-in** | Minutes the volume takes to climb there; `0` starts at full volume |
| `number` **Stop after** | Minutes after which the player switches itself off |
| `number` **Snooze time** | Minutes a snooze lasts |
| `switch` **Wake-up light** | Whether the lights come on at all |
| `number` **Light head start** | Minutes the light starts before the music |
| `number` **Light brightness** | The brightness it ends up at |
| `switch` **Light off afterwards** | Switch the lights off again when the alarm ends |
| `sensor` **Next alarm** | The next wake-up as a timestamp |
| `sensor` **Status** | `off`, `armed`, `light`, `ringing` or `snoozed` |
| `button` **Try now / Stop / Snooze** | Test it without touching the time |

## How a wake-up runs

1. **Light head start minutes before the alarm** the lights come on at 1% and
   climb to the set brightness in steps of about 20 seconds. Lights that can
   fade by themselves are given a `transition`; the rest are stepped.
2. **At the wake-up time** the volume is set to a fifth of the target, the
   selected station or playlist starts, and the volume climbs to the target in
   ten steps across the fade-in.
3. **Pausing on the player itself counts as "I'm up"**: the ramp stops and the
   player is left alone.
4. **After "stop after" minutes** the player switches off, and the lights go out
   if you asked for that.

If the player is unavailable, or Music Assistant cannot start the selected item,
the wake-up is abandoned, a `music_assistant_alarm_failed` event is fired and —
if you filled in a notification service — you get a message.

### The wake-up sound survives a library rebuild

The select stores the **name** of the station or playlist, not its uri. Music
Assistant hands out `library://radio/30`, but those ids are renumbered when the
library is rebuilt, and an alarm that silently points at nothing is the worst
kind of alarm. The name is resolved to a uri at wake-up time, and falls back to
letting Music Assistant look up the name itself.

## Install

### HACS

Add this repository as a custom repository (category: Integration), install it,
and restart Home Assistant. Then **Settings → Devices & services → Add
integration → Music Assistant Alarm Clock**.

### Manual

Copy `custom_components/music_assistant_alarm` into your `config/custom_components`
folder and restart Home Assistant.

## Options

Per alarm, under **Configure**:

- **Music Assistant player** — the player the sound comes out of.
- **Wake-up light** — zero or more lights.
- **Notification service** — for example `notify.mobile_app_phone`, used when a
  wake-up fails.
- **Squeezebox address / port** — optional; see
  [`extras/squeezebox_hawekker`](extras/squeezebox_hawekker) for a classic
  Squeezebox that should show its own bell and wake-up window, and keep its
  clock on time.

## Services

| Service | What it does |
|---|---|
| `music_assistant_alarm.trigger` | Runs the wake-up now |
| `music_assistant_alarm.stop` | Stops a running wake-up |
| `music_assistant_alarm.snooze` | Silences it for the snooze time |
| `music_assistant_alarm.refresh_media` | Reads the library again |

Each takes a `config_entry_id`. Events on the bus:
`music_assistant_alarm_started`, `_stopped`, `_snoozed` and `_failed`.

## Requirements

- Home Assistant 2025.2 or newer
- The Music Assistant integration, set up and with at least one player

## Licence

MIT
