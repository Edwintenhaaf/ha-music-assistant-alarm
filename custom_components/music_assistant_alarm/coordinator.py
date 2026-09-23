"""Runtime for a single Music Assistant alarm."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import socket
from datetime import datetime, timedelta
from datetime import time as dt_time
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS_PCT,
    ATTR_TRANSITION,
    LightEntityFeature,
)
from homeassistant.components.light import (
    DOMAIN as LIGHT_DOMAIN,
)
from homeassistant.components.media_player import (
    ATTR_MEDIA_VOLUME_LEVEL,
)
from homeassistant.components.media_player import (
    DOMAIN as MEDIA_PLAYER_DOMAIN,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_SET,
    STATE_PLAYING,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    CONF_LIGHTS,
    CONF_NOTIFY_SERVICE,
    CONF_PLAYER,
    CONF_SQUEEZEBOX_HOST,
    CONF_SQUEEZEBOX_PORT,
    DEFAULT_SETTINGS,
    DEFAULT_SQUEEZEBOX_PORT,
    DOMAIN,
    EVENT_FAILED,
    EVENT_SNOOZED,
    EVENT_STARTED,
    EVENT_STOPPED,
    LIGHT_START_BRIGHTNESS,
    LIGHT_STEP_SECONDS,
    MEDIA_TYPES,
    NEXT_ALARM_GRACE_MINUTES,
    REFRESH_INTERVAL_MINUTES,
    SET_DAYS,
    SET_ENABLED,
    SET_FADE_MINUTES,
    SET_LIGHT_BRIGHTNESS,
    SET_LIGHT_ENABLED,
    SET_LIGHT_MINUTES,
    SET_LIGHT_OFF_AT_END,
    SET_MEDIA_NAME,
    SET_MEDIA_TYPE,
    SET_SNOOZE_MINUTES,
    SET_STOP_AFTER_MINUTES,
    SET_TIME,
    SET_VOLUME,
    STATUS_ARMED,
    STATUS_LIGHT,
    STATUS_OFF,
    STATUS_RINGING,
    STATUS_SNOOZED,
    VOLUME_STEPS,
    WEEKDAYS,
)

_LOGGER = logging.getLogger(__name__)

MA_DOMAIN = "music_assistant"
STORAGE_VERSION = 1

# How long we give Music Assistant to actually start playing before we decide
# that the wake-up failed. Radio streams need a moment to connect.
PLAY_TIMEOUT_SECONDS = 20


class AlarmCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Holds the settings of one alarm, schedules it and runs the wake-up."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialise the alarm."""
        super().__init__(
            hass,
            _LOGGER,
            name=entry.title,
            update_interval=timedelta(minutes=REFRESH_INTERVAL_MINUTES),
            config_entry=entry,
        )
        self.entry = entry
        self.settings: dict[str, Any] = dict(DEFAULT_SETTINGS)
        self.status: str = STATUS_OFF
        self.media_options: list[str] = []
        self._media_uris: dict[str, str] = {}
        self._store = Store[dict[str, Any]](
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}"
        )
        self._unsub_alarm: Any = None
        self._unsub_light: Any = None
        self._alarm_task: asyncio.Task | None = None
        self._light_task: asyncio.Task | None = None
        self._snooze_until: datetime | None = None
        self._lights_are_ours = False
        self._last_pushed_epoch: int | None = None

    # ------------------------------------------------------------------
    # configuration shortcuts
    # ------------------------------------------------------------------

    @property
    def player(self) -> str:
        """Return the Music Assistant media player entity id."""
        return self.entry.data[CONF_PLAYER]

    @property
    def lights(self) -> list[str]:
        """Return the light entity ids of the wake-up light."""
        return list(self.entry.options.get(CONF_LIGHTS, []))

    @property
    def notify_service(self) -> str | None:
        """Return the notify service used to report a failed wake-up."""
        return self.entry.options.get(CONF_NOTIFY_SERVICE) or None

    # ------------------------------------------------------------------
    # setup / teardown
    # ------------------------------------------------------------------

    async def async_load(self) -> None:
        """Load the stored settings and arm the alarm."""
        if (stored := await self._store.async_load()) is not None:
            self.settings = {**DEFAULT_SETTINGS, **stored}
        self.data = self.settings
        await self._async_refresh_media_options()
        self._reschedule()

    async def async_shutdown(self) -> None:
        """Cancel everything this alarm has running."""
        self._cancel_timers()
        await self._async_cancel_tasks()
        await super().async_shutdown()

    async def _async_update_data(self) -> dict[str, Any]:
        """Refresh the media library and keep an attached device in sync."""
        await self._async_refresh_media_options()
        await self._async_push_next_alarm()
        return self.settings

    # ------------------------------------------------------------------
    # settings
    # ------------------------------------------------------------------

    async def async_update_settings(self, **changes: Any) -> None:
        """Store changed settings, re-arm the alarm and update the entities."""
        self.settings.update(changes)
        await self._store.async_save(self.settings)
        self._reschedule()
        self.async_set_updated_data(self.settings)
        await self._async_push_next_alarm()

    def _refresh_entities(self) -> None:
        """Push the current state to the entities without touching the timers."""
        self.async_set_updated_data(self.settings)

    # ------------------------------------------------------------------
    # scheduling
    # ------------------------------------------------------------------

    @property
    def alarm_time(self) -> dt_time:
        """Return the configured wake-up time."""
        raw = str(self.settings.get(SET_TIME) or DEFAULT_SETTINGS[SET_TIME])
        parts = [int(part) for part in raw.split(":")]
        while len(parts) < 3:
            parts.append(0)
        return dt_time(parts[0], parts[1], parts[2])

    @property
    def days(self) -> list[str]:
        """Return the weekdays the alarm is armed on."""
        return [day for day in self.settings.get(SET_DAYS, []) if day in WEEKDAYS]

    def next_alarm(self, grace_minutes: int = 0) -> datetime | None:
        """Return when the alarm goes off next, or None when it never does.

        With ``grace_minutes`` an alarm that just fired is kept in place for a
        while instead of jumping to tomorrow straight away.
        """
        if self._snooze_until is not None:
            return self._snooze_until
        if not self.settings.get(SET_ENABLED) or not self.days:
            return None
        wanted = self.alarm_time
        now = dt_util.now()
        floor = now - timedelta(minutes=grace_minutes)
        for offset in range(8):
            candidate = (now + timedelta(days=offset)).replace(
                hour=wanted.hour,
                minute=wanted.minute,
                second=wanted.second,
                microsecond=0,
            )
            if candidate > floor and WEEKDAYS[candidate.weekday()] in self.days:
                return candidate
        return None

    def _cancel_timers(self) -> None:
        """Drop the pending alarm and wake-up light timers."""
        for attr in ("_unsub_alarm", "_unsub_light"):
            if (unsub := getattr(self, attr)) is not None:
                unsub()
                setattr(self, attr, None)

    def _reschedule(self) -> None:
        """Arm the timers for the next wake-up."""
        self._cancel_timers()
        if self.status in (STATUS_RINGING, STATUS_LIGHT):
            # A running wake-up keeps its own schedule; re-arming happens when
            # it finishes.
            return
        target = self.next_alarm()
        if target is None:
            self.status = STATUS_OFF
            return
        self.status = STATUS_SNOOZED if self._snooze_until else STATUS_ARMED
        self._unsub_alarm = async_track_point_in_time(
            self.hass, self._handle_alarm_time, target
        )
        light_minutes = int(self.settings.get(SET_LIGHT_MINUTES, 0))
        if (
            self.settings.get(SET_LIGHT_ENABLED)
            and self.lights
            and light_minutes > 0
            and self._snooze_until is None
        ):
            light_start = target - timedelta(minutes=light_minutes)
            if light_start > dt_util.now():
                self._unsub_light = async_track_point_in_time(
                    self.hass, self._handle_light_time, light_start
                )

    async def _handle_alarm_time(self, _now: datetime) -> None:
        """Run the wake-up because the alarm time has arrived."""
        self._unsub_alarm = None
        self._snooze_until = None
        await self.async_trigger()

    async def _handle_light_time(self, _now: datetime) -> None:
        """Start the wake-up light ahead of the alarm."""
        self._unsub_light = None
        self._start_light_task()
        self.status = STATUS_LIGHT
        self._refresh_entities()

    # ------------------------------------------------------------------
    # actions
    # ------------------------------------------------------------------

    async def async_trigger(self) -> None:
        """Start the wake-up right now."""
        # A wake-up light that is already climbing keeps climbing: cancelling it
        # here would drop the lamp back to its starting glow.
        await self._async_cancel_tasks(include_light=False)
        self._snooze_until = None
        self._cancel_timers()
        self.status = STATUS_RINGING
        self._refresh_entities()
        self._alarm_task = self.entry.async_create_background_task(
            self.hass, self._async_run_alarm(), f"{DOMAIN} alarm {self.entry.entry_id}"
        )

    async def async_stop(self) -> None:
        """Stop a running wake-up and arm the alarm again."""
        await self._async_cancel_tasks()
        self._snooze_until = None
        await self._async_turn_off_player()
        await self._async_finish_lights()
        self.hass.bus.async_fire(EVENT_STOPPED, self._event_data())
        self.status = STATUS_ARMED
        self._reschedule()
        self._refresh_entities()
        await self._async_push_next_alarm()

    async def async_snooze(self) -> None:
        """Silence the alarm and let it come back after the snooze time."""
        minutes = int(self.settings.get(SET_SNOOZE_MINUTES, 9))
        await self._async_cancel_tasks()
        await self._async_turn_off_player()
        self._snooze_until = dt_util.now() + timedelta(minutes=minutes)
        self.hass.bus.async_fire(
            EVENT_SNOOZED, {**self._event_data(), "minutes": minutes}
        )
        self.status = STATUS_ARMED
        self._reschedule()
        self._refresh_entities()
        await self._async_push_next_alarm()

    def _event_data(self) -> dict[str, Any]:
        """Return the payload shared by all events of this alarm."""
        return {
            "entry_id": self.entry.entry_id,
            "name": self.entry.title,
            "player": self.player,
        }

    async def _async_cancel_tasks(self, *, include_light: bool = True) -> None:
        """Cancel the wake-up and the light ramp, and wait for them to end."""
        attrs = ("_alarm_task", "_light_task") if include_light else ("_alarm_task",)
        for attr in attrs:
            task: asyncio.Task | None = getattr(self, attr)
            setattr(self, attr, None)
            if task is None or task.done():
                continue
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    # ------------------------------------------------------------------
    # the wake-up itself
    # ------------------------------------------------------------------

    def _start_light_task(self) -> None:
        """Start the wake-up light ramp in the background."""
        if self._light_task is not None and not self._light_task.done():
            return
        self._light_task = self.entry.async_create_background_task(
            self.hass, self._async_run_light(), f"{DOMAIN} light {self.entry.entry_id}"
        )

    async def _async_run_light(self) -> None:
        """Bring the wake-up light up from a glow to the target brightness."""
        lights = self.lights
        if not lights or not self.settings.get(SET_LIGHT_ENABLED):
            return
        target = int(self.settings.get(SET_LIGHT_BRIGHTNESS, 80))
        minutes = int(self.settings.get(SET_LIGHT_MINUTES, 0))
        if minutes <= 0:
            await self._async_set_lights(target, None)
            return
        steps = max(1, int(minutes * 60 // LIGHT_STEP_SECONDS))
        interval = minutes * 60 / steps
        supports_transition = self._lights_support_transition(lights)
        for step in range(steps + 1):
            pct = LIGHT_START_BRIGHTNESS + (target - LIGHT_START_BRIGHTNESS) * step / steps
            await self._async_set_lights(
                max(1, round(pct)), interval if supports_transition else None
            )
            if step < steps:
                await asyncio.sleep(interval)

    def _lights_support_transition(self, lights: list[str]) -> bool:
        """Return True when every light can fade by itself."""
        for entity_id in lights:
            state = self.hass.states.get(entity_id)
            features = (state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)) if state else 0
            if not features & LightEntityFeature.TRANSITION:
                return False
        return bool(lights)

    async def _async_set_lights(self, brightness_pct: int, transition: float | None) -> None:
        """Set the wake-up light to a brightness."""
        data: dict[str, Any] = {
            ATTR_ENTITY_ID: self.lights,
            ATTR_BRIGHTNESS_PCT: brightness_pct,
        }
        if transition is not None:
            data[ATTR_TRANSITION] = round(transition)
        try:
            await self.hass.services.async_call(
                LIGHT_DOMAIN, SERVICE_TURN_ON, data, blocking=True
            )
            self._lights_are_ours = True
        except HomeAssistantError as err:
            _LOGGER.warning("%s: could not set the wake-up light: %s", self.name, err)

    async def _async_finish_lights(self) -> None:
        """Switch the wake-up light off again when that was asked for."""
        if not self._lights_are_ours:
            return
        self._lights_are_ours = False
        if not self.settings.get(SET_LIGHT_OFF_AT_END) or not self.lights:
            return
        try:
            await self.hass.services.async_call(
                LIGHT_DOMAIN,
                SERVICE_TURN_OFF,
                {ATTR_ENTITY_ID: self.lights},
                blocking=True,
            )
        except HomeAssistantError as err:
            _LOGGER.warning("%s: could not switch off the wake-up light: %s", self.name, err)

    async def _async_run_alarm(self) -> None:
        """Play the wake-up music, ramp the volume and stop again."""
        try:
            self.hass.bus.async_fire(EVENT_STARTED, self._event_data())
            state = self.hass.states.get(self.player)
            if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                await self._async_report_failure(
                    f"{self.player} is unavailable, the alarm did not go off"
                )
                return

            if (
                self.settings.get(SET_LIGHT_ENABLED)
                and self.lights
                and not self._lights_are_ours
            ):
                # No head start, or the alarm was started by hand: the light
                # still has to come on. A ramp that already ran is left alone.
                self._start_light_task()

            target = int(self.settings.get(SET_VOLUME, 20))
            fade = float(self.settings.get(SET_FADE_MINUTES, 0))
            start = max(1, round(target / 5)) if fade > 0 else target

            await self._async_set_volume(start)
            if not await self._async_play_media():
                return
            if not await self._async_wait_for_playback():
                await self._async_report_failure(
                    f"{self.player} did not start playing within "
                    f"{PLAY_TIMEOUT_SECONDS} seconds"
                )
                return

            if fade > 0:
                step_seconds = fade * 60 / VOLUME_STEPS
                for step in range(1, VOLUME_STEPS + 1):
                    await asyncio.sleep(step_seconds)
                    if not self._is_playing():
                        # Paused on the device itself: that is a dismissal.
                        await self._async_end_run(turn_off=False)
                        return
                    await self._async_set_volume(
                        round(start + (target - start) * step / VOLUME_STEPS)
                    )

            stop_after = float(self.settings.get(SET_STOP_AFTER_MINUTES, 30))
            remaining = max(0.0, stop_after - fade)
            if remaining:
                await asyncio.sleep(remaining * 60)
            await self._async_end_run(turn_off=self._is_playing())
        except asyncio.CancelledError:
            raise
        except Exception:
            _LOGGER.exception("%s: the wake-up failed", self.name)
            await self._async_end_run(turn_off=False)

    async def _async_end_run(self, *, turn_off: bool) -> None:
        """Wind the wake-up down and arm the alarm for the next day."""
        if turn_off:
            await self._async_turn_off_player()
        await self._async_finish_lights()
        self.hass.bus.async_fire(EVENT_STOPPED, self._event_data())
        self._alarm_task = None
        self.status = STATUS_ARMED
        self._reschedule()
        self._refresh_entities()
        await self._async_push_next_alarm()

    def _is_playing(self) -> bool:
        """Return True while the player is actually playing."""
        state = self.hass.states.get(self.player)
        return state is not None and state.state == STATE_PLAYING

    async def _async_wait_for_playback(self) -> bool:
        """Wait until the player reports playback, or give up."""
        for _ in range(PLAY_TIMEOUT_SECONDS * 2):
            if self._is_playing():
                return True
            await asyncio.sleep(0.5)
        return self._is_playing()

    async def _async_set_volume(self, percent: int) -> None:
        """Set the player volume, in percent."""
        try:
            await self.hass.services.async_call(
                MEDIA_PLAYER_DOMAIN,
                SERVICE_VOLUME_SET,
                {
                    ATTR_ENTITY_ID: self.player,
                    ATTR_MEDIA_VOLUME_LEVEL: round(percent / 100, 3),
                },
                blocking=True,
            )
        except HomeAssistantError as err:
            _LOGGER.warning("%s: could not set the volume: %s", self.name, err)

    async def _async_turn_off_player(self) -> None:
        """Switch the player off."""
        try:
            await self.hass.services.async_call(
                MEDIA_PLAYER_DOMAIN,
                SERVICE_TURN_OFF,
                {ATTR_ENTITY_ID: self.player},
                blocking=True,
            )
        except HomeAssistantError as err:
            _LOGGER.warning("%s: could not switch the player off: %s", self.name, err)

    async def _async_play_media(self) -> bool:
        """Start the selected radio station or playlist."""
        name = str(self.settings.get(SET_MEDIA_NAME) or "")
        media_type = str(self.settings.get(SET_MEDIA_TYPE) or "radio")
        if not name:
            await self._async_report_failure("no radio station or playlist selected")
            return False
        # Resolve the name to a uri every time: library://<type>/<id> is handed
        # out by Music Assistant but is not stable across a library rebuild,
        # while the name survives it. The name is the fallback: Music Assistant
        # looks it up itself.
        media_id = self._media_uris.get(name) or await self._async_resolve_media(
            name, media_type
        )
        try:
            await self.hass.services.async_call(
                MA_DOMAIN,
                "play_media",
                {
                    ATTR_ENTITY_ID: self.player,
                    "media_id": media_id or name,
                    "media_type": media_type,
                    "enqueue": "replace",
                },
                blocking=True,
            )
        except HomeAssistantError as err:
            await self._async_report_failure(f"could not start {name}: {err}")
            return False
        return True

    async def _async_report_failure(self, message: str) -> None:
        """Log, announce and optionally notify that the wake-up failed."""
        _LOGGER.error("%s: %s", self.name, message)
        self.hass.bus.async_fire(
            EVENT_FAILED, {**self._event_data(), "message": message}
        )
        if service := self.notify_service:
            domain, _, service_name = service.partition(".")
            try:
                await self.hass.services.async_call(
                    domain or "notify",
                    service_name or service,
                    {"title": self.entry.title, "message": message},
                    blocking=False,
                )
            except HomeAssistantError as err:
                _LOGGER.warning("%s: could not send the notification: %s", self.name, err)
        await self._async_end_run(turn_off=False)

    # ------------------------------------------------------------------
    # the Music Assistant library
    # ------------------------------------------------------------------

    def _ma_config_entry_id(self) -> str | None:
        """Return the Music Assistant config entry that owns our player."""
        registry = er.async_get(self.hass)
        if (entry := registry.async_get(self.player)) is not None:
            return entry.config_entry_id
        entries = self.hass.config_entries.async_entries(MA_DOMAIN)
        return entries[0].entry_id if entries else None

    async def _async_library(
        self, media_type: str, search: str | None = None
    ) -> list[dict[str, Any]]:
        """Return library items of one type from Music Assistant."""
        if (config_entry_id := self._ma_config_entry_id()) is None:
            return []
        data: dict[str, Any] = {
            "config_entry_id": config_entry_id,
            "media_type": media_type,
            "limit": 500,
            "order_by": "name",
        }
        if search:
            data["search"] = search
        try:
            response = await self.hass.services.async_call(
                MA_DOMAIN,
                "get_library",
                data,
                blocking=True,
                return_response=True,
            )
        except HomeAssistantError as err:
            _LOGGER.debug("%s: could not read the %s library: %s", self.name, media_type, err)
            return []
        if not response:
            return []
        return list(response.get("items", []))

    async def _async_refresh_media_options(self) -> None:
        """Rebuild the list of radio stations and playlists to choose from."""
        options: list[str] = []
        uris: dict[str, str] = {}
        for media_type in MEDIA_TYPES:
            for item in await self._async_library(media_type):
                name = item.get("name")
                if not name or name in uris:
                    continue
                uris[name] = item.get("uri", "")
                options.append(name)
        if not options:
            # Keep the current option list rather than emptying the select when
            # Music Assistant is briefly unreachable.
            return
        selected = self.settings.get(SET_MEDIA_NAME)
        if selected and selected not in options:
            options.append(selected)
        self.media_options = sorted(options, key=str.casefold)
        self._media_uris = uris

    async def _async_resolve_media(self, name: str, media_type: str) -> str | None:
        """Look up the uri that belongs to a name, right now."""
        for item in await self._async_library(media_type, search=name):
            if str(item.get("name", "")).casefold() == name.casefold():
                return item.get("uri")
        return None

    def media_type_of(self, name: str) -> str:
        """Return whether a library name is a radio station or a playlist."""
        uri = self._media_uris.get(name, "")
        return "playlist" if "playlist" in uri else "radio"

    # ------------------------------------------------------------------
    # Squeezebox (optional)
    # ------------------------------------------------------------------

    async def _async_push_next_alarm(self) -> None:
        """Tell an attached Squeezebox when the next alarm is due, and what time it is.

        Music Assistant never fills the ``alarm_next`` field of the slimproto
        player status, so a Squeezebox running the HAWekker applet gets the
        epoch over udp instead. 0 means: no alarm set.

        The same packet carries the current time. A Squeezebox has no ntp
        client: it sets its clock from the ``/slim/datestatus`` subscription,
        which Music Assistant does not answer, so without this its clock just
        drifts away. The applet only touches the clock when it is actually off.
        """
        host = self.entry.options.get(CONF_SQUEEZEBOX_HOST)
        if not host:
            return
        port = int(self.entry.options.get(CONF_SQUEEZEBOX_PORT, DEFAULT_SQUEEZEBOX_PORT))
        target = self.next_alarm(grace_minutes=NEXT_ALARM_GRACE_MINUTES)
        epoch = int(target.timestamp()) if target else 0
        self._last_pushed_epoch = epoch
        now = int(dt_util.utcnow().timestamp())
        await self.hass.async_add_executor_job(self._send_udp, host, port, epoch, now)

    @staticmethod
    def _send_udp(host: str, port: int, epoch: int, now: int) -> None:
        """Send the next alarm time and the current time to the Squeezebox applet."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.settimeout(2)
                sock.sendto(f"next={epoch} now={now}".encode(), (host, port))
        except OSError as err:
            _LOGGER.debug("Could not reach the Squeezebox applet on %s: %s", host, err)
