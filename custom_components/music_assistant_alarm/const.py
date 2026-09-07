"""Constants for the Music Assistant Alarm Clock integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "music_assistant_alarm"

# Config entry data (set once, in the config flow)
CONF_NAME: Final = "name"
CONF_PLAYER: Final = "player"

# Config entry options (changeable, in the options flow)
CONF_LIGHTS: Final = "lights"
CONF_NOTIFY_SERVICE: Final = "notify_service"
CONF_SQUEEZEBOX_HOST: Final = "squeezebox_host"
CONF_SQUEEZEBOX_PORT: Final = "squeezebox_port"

DEFAULT_SQUEEZEBOX_PORT: Final = 9997

# Stored settings (the runtime state behind the entities)
SET_ENABLED: Final = "enabled"
SET_TIME: Final = "time"
SET_DAYS: Final = "days"
SET_MEDIA_NAME: Final = "media_name"
SET_MEDIA_TYPE: Final = "media_type"
SET_VOLUME: Final = "volume"
SET_FADE_MINUTES: Final = "fade_minutes"
SET_STOP_AFTER_MINUTES: Final = "stop_after_minutes"
SET_SNOOZE_MINUTES: Final = "snooze_minutes"
SET_LIGHT_ENABLED: Final = "light_enabled"
SET_LIGHT_MINUTES: Final = "light_minutes"
SET_LIGHT_BRIGHTNESS: Final = "light_brightness"
SET_LIGHT_OFF_AT_END: Final = "light_off_at_end"

# Weekdays, indexed the same way as datetime.weekday()
WEEKDAYS: Final = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

DEFAULT_SETTINGS: Final[dict] = {
    SET_ENABLED: False,
    SET_TIME: "07:30:00",
    SET_DAYS: list(WEEKDAYS),
    SET_MEDIA_NAME: "",
    SET_MEDIA_TYPE: "radio",
    SET_VOLUME: 20,
    SET_FADE_MINUTES: 2,
    SET_STOP_AFTER_MINUTES: 30,
    SET_SNOOZE_MINUTES: 9,
    SET_LIGHT_ENABLED: True,
    SET_LIGHT_MINUTES: 15,
    SET_LIGHT_BRIGHTNESS: 80,
    SET_LIGHT_OFF_AT_END: True,
}

# Alarm status, exposed by the status sensor
STATUS_OFF: Final = "off"
STATUS_ARMED: Final = "armed"
STATUS_LIGHT: Final = "light"
STATUS_RINGING: Final = "ringing"
STATUS_SNOOZED: Final = "snoozed"

# Events fired on the HA event bus
EVENT_STARTED: Final = f"{DOMAIN}_started"
EVENT_STOPPED: Final = f"{DOMAIN}_stopped"
EVENT_SNOOZED: Final = f"{DOMAIN}_snoozed"
EVENT_FAILED: Final = f"{DOMAIN}_failed"

# Services
SERVICE_TRIGGER: Final = "trigger"
SERVICE_STOP: Final = "stop"
SERVICE_SNOOZE: Final = "snooze"
SERVICE_REFRESH_MEDIA: Final = "refresh_media"

# Media types offered in the media select
MEDIA_TYPES: Final = ("radio", "playlist")

# The volume ramp climbs in this many steps, whatever the fade length is.
VOLUME_STEPS: Final = 10
# The light ramp aims for a step every this many seconds.
LIGHT_STEP_SECONDS: Final = 20
# Brightness the wake-up light starts at, in percent.
LIGHT_START_BRIGHTNESS: Final = 1
# The next alarm is kept in place this long after it fired, so that a device
# reading it (the Squeezebox applet) does not clear its own timer a second early.
NEXT_ALARM_GRACE_MINUTES: Final = 2
# How often the media library and the Squeezebox push are refreshed.
REFRESH_INTERVAL_MINUTES: Final = 5
