# HAWekker — the bell and the wake-up window on a Squeezebox

Optional. Only needed if your Music Assistant player is a classic Squeezebox
(Radio, Boom, Touch) and you want the device itself to show the alarm bell and
open its wake-up window, the way it did when it hung off a Logitech Media
Server.

## Why it is needed

The Squeezebox runs the alarm itself. All it needs from the server is the
*time*: the `alarm_next` field in the player status. On that it sets its own
`RTCAlarmTimer` plus `iconbar:setAlarm('ON')`, and at the right moment it opens
`openAlarmWindow()` — the window that stays on top, with a clock that ticks
along and the choices *Snooze* and *Turn alarm off*.

Music Assistant cannot deliver that field: `aioslimproto/cli.py` hardcodes
`alarm_state` to `"none"` and has no concept of alarms. Patching the Music
Assistant container does not survive a restart of the add-on, so the fix lives
on the device.

## What it does

`HAWekker` listens on udp port 9997 for a plain text payload `next=<epoch>`
(`0` means: no alarm set) and feeds it into the stock alarm path of SqueezeOS
with `jnt:notify('playerAlarmState', ...)` — exactly the message the Logitech
Media Server used to send.

This integration sends that payload whenever the next alarm time changes and
every five minutes after that, so the device catches up on its own after a
reboot. Fill in the address of the Squeezebox in the options of the alarm to
switch it on.

## Who may send

The packet sets the alarm and the clock, so the applet only listens to one
address: that of Home Assistant. You do not have to fill it in. The first valid
packet that arrives decides, and its sender is stored in the applet settings on
the device (`/etc/squeezeplay/userpath/settings/HAWekker.lua`, key `ha_ip`).
Packets from any other address are ignored from then on.

Did Home Assistant move to another address, or do you want to pin it up front?
Put it in that file and restart the user interface:

```sh
echo 'settings = { ha_ip = "192.0.2.10" }' > /etc/squeezeplay/userpath/settings/HAWekker.lua
killall jive
```

Removing the file makes the applet learn the address again.

## It also sets the clock

The same packet carries `now=<epoch>`, the current time. A Squeezebox has no
ntp client: it gets its time from the server, by subscribing to
`/slim/datestatus/<playerid>` and feeding the `date_epoch` it receives into
`swclockSetEpoch()`. Music Assistant never answers that subscription -
`aioslimproto` only knows `playerstatus`, `serverstatus` and `menustatus` - so
the clock of a Squeezebox on Music Assistant drifts away unnoticed, and after a
power cut it is simply wrong.

The applet sets the clock along the same path SqueezeOS uses itself, but only
when it is more than five seconds off, and never in the last two minutes before
the alarm is due: the wake-up timer of the MCU is set in the old time, and
moving the clock underneath it would cost the wake-up window.

## Install

Copy the applet onto the device and restart the user interface:

```sh
scp -r . root@<squeezebox>:/usr/share/jive/applets/HAWekker/
ssh root@<squeezebox> "killall jive"
```

## Two deliberate quirks

- The **next alarm** sensor holds a wake-up time in place for two minutes after
  it has passed. Without that margin it rolls over to tomorrow on the wake-up
  second itself, and the device cancels its own timer a second early — the
  wake-up window then never appears.
- The applet **refuses a later time** while the alarm it already holds is due
  within 90 seconds, but an alarm that is switched *off* goes through
  immediately.

Because the clock screensaver only subscribes to alarm messages if the player
already existed when it opened, the applet rebuilds that screensaver once after
a restart. Without that, the bell stays away.

## Optional: a shorter silence before the built-in alarm tone

When the wake-up window opens and no audio arrives, SqueezeOS falls back to its
own alarm tone — but only after 13 failed checks of 5 seconds, over a minute of
silence. Anyone who pokes the radio in that minute dismisses the window, and the
tone never sounds. On the device the threshold can be lowered in
`/usr/share/jive/applets/AlarmSnooze/AlarmSnoozeApplet.lua`:

```sh
cd /usr/share/jive/applets/AlarmSnooze
[ -e AlarmSnoozeApplet.lua.orig ] || cp AlarmSnoozeApplet.lua AlarmSnoozeApplet.lua.orig
sed -i 's/failedAudioTicker > 12 then/failedAudioTicker > 3 then/' AlarmSnoozeApplet.lua
killall jive
```

With `> 3` the tone starts after about 20 seconds of silence. The root filesystem
is a unionfs over flash, so the change survives a reboot; a firmware update puts
the original back. BusyBox has no `cp -n`, hence the test.
