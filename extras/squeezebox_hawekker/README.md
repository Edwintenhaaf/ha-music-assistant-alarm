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
