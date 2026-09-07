"""The wake-up time of a Music Assistant alarm."""

from __future__ import annotations

from datetime import time

from homeassistant.components.time import TimeEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AlarmConfigEntry
from .const import SET_TIME
from .entity import AlarmEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AlarmConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the wake-up time of one alarm."""
    async_add_entities([AlarmTime(entry.runtime_data, "alarm_time")])


class AlarmTime(AlarmEntity, TimeEntity):
    """The time the alarm goes off."""

    _attr_icon = "mdi:clock-outline"

    @property
    def native_value(self) -> time:
        """Return the wake-up time."""
        return self.coordinator.alarm_time

    async def async_set_value(self, value: time) -> None:
        """Store a new wake-up time."""
        await self.coordinator.async_update_settings(**{SET_TIME: value.isoformat()})
