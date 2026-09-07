"""The Music Assistant Alarm Clock integration.

An alarm clock that wakes you with a radio station or a playlist from Music
Assistant, optionally preceded by a wake-up light that fades in.
"""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import (
    DOMAIN,
    SERVICE_REFRESH_MEDIA,
    SERVICE_SNOOZE,
    SERVICE_STOP,
    SERVICE_TRIGGER,
)
from .coordinator import AlarmCoordinator

type AlarmConfigEntry = ConfigEntry[AlarmCoordinator]

PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TIME,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

SERVICE_SCHEMA = vol.Schema({vol.Required("config_entry_id"): cv.string})


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register the integration services."""
    _async_register_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: AlarmConfigEntry) -> bool:
    """Set up one alarm from a config entry."""
    coordinator = AlarmCoordinator(hass, entry)
    await coordinator.async_load()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AlarmConfigEntry) -> bool:
    """Unload an alarm."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_shutdown()
    return unloaded


async def _async_options_updated(hass: HomeAssistant, entry: AlarmConfigEntry) -> None:
    """Reload the alarm when its options changed."""
    await hass.config_entries.async_reload(entry.entry_id)


@callback
def _async_register_services(hass: HomeAssistant) -> None:
    """Register the services that act on one alarm."""

    def _coordinator(call: ServiceCall) -> AlarmCoordinator:
        entry_id = call.data["config_entry_id"]
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is None or entry.domain != DOMAIN or not hasattr(entry, "runtime_data"):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="unknown_entry",
                translation_placeholders={"entry_id": entry_id},
            )
        return entry.runtime_data

    async def handle_trigger(call: ServiceCall) -> None:
        await _coordinator(call).async_trigger()

    async def handle_stop(call: ServiceCall) -> None:
        await _coordinator(call).async_stop()

    async def handle_snooze(call: ServiceCall) -> None:
        await _coordinator(call).async_snooze()

    async def handle_refresh_media(call: ServiceCall) -> None:
        await _coordinator(call).async_request_refresh()

    for service, handler in (
        (SERVICE_TRIGGER, handle_trigger),
        (SERVICE_STOP, handle_stop),
        (SERVICE_SNOOZE, handle_snooze),
        (SERVICE_REFRESH_MEDIA, handle_refresh_media),
    ):
        if not hass.services.has_service(DOMAIN, service):
            hass.services.async_register(DOMAIN, service, handler, schema=SERVICE_SCHEMA)
