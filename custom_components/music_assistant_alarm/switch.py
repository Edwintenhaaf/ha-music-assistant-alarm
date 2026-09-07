"""Switches of the Music Assistant Alarm Clock integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AlarmConfigEntry
from .const import (
    SET_ENABLED,
    SET_LIGHT_ENABLED,
    SET_LIGHT_OFF_AT_END,
    WEEKDAYS,
)
from .coordinator import AlarmCoordinator
from .entity import AlarmEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AlarmConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the switches of one alarm."""
    coordinator = entry.runtime_data
    entities: list[SwitchEntity] = [
        AlarmSettingSwitch(coordinator, "enabled", SET_ENABLED, "mdi:alarm"),
        AlarmSettingSwitch(
            coordinator, "light_enabled", SET_LIGHT_ENABLED, "mdi:lightbulb-on-outline"
        ),
        AlarmSettingSwitch(
            coordinator, "light_off_at_end", SET_LIGHT_OFF_AT_END, "mdi:lightbulb-off-outline"
        ),
    ]
    entities.extend(AlarmDaySwitch(coordinator, day) for day in WEEKDAYS)
    async_add_entities(entities)


class AlarmSettingSwitch(AlarmEntity, SwitchEntity):
    """A switch that flips one boolean setting of the alarm."""

    def __init__(
        self, coordinator: AlarmCoordinator, key: str, setting: str, icon: str
    ) -> None:
        """Initialise the switch."""
        super().__init__(coordinator, key)
        self._setting = setting
        self._attr_icon = icon

    @property
    def is_on(self) -> bool:
        """Return whether the setting is on."""
        return bool(self.coordinator.settings.get(self._setting))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Switch the setting on."""
        await self.coordinator.async_update_settings(**{self._setting: True})

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Switch the setting off."""
        await self.coordinator.async_update_settings(**{self._setting: False})


class AlarmDaySwitch(AlarmEntity, SwitchEntity):
    """A switch that arms or disarms the alarm on one weekday."""

    _attr_icon = "mdi:calendar-check"

    def __init__(self, coordinator: AlarmCoordinator, day: str) -> None:
        """Initialise the weekday switch."""
        super().__init__(coordinator, f"day_{day}")
        self._day = day

    @property
    def is_on(self) -> bool:
        """Return whether the alarm is armed on this day."""
        return self._day in self.coordinator.days

    async def _async_set(self, armed: bool) -> None:
        """Add or remove this day and store the result."""
        days = set(self.coordinator.days)
        if armed:
            days.add(self._day)
        else:
            days.discard(self._day)
        ordered = [day for day in WEEKDAYS if day in days]
        await self.coordinator.async_update_settings(days=ordered)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Arm the alarm on this day."""
        await self._async_set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disarm the alarm on this day."""
        await self._async_set(False)
