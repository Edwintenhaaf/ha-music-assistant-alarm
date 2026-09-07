"""Buttons to try, stop and snooze a Music Assistant alarm."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AlarmConfigEntry
from .coordinator import AlarmCoordinator
from .entity import AlarmEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AlarmConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the buttons of one alarm."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            AlarmButton(coordinator, "test", "mdi:play-circle-outline", coordinator.async_trigger),
            AlarmButton(coordinator, "stop", "mdi:alarm-off", coordinator.async_stop),
            AlarmButton(coordinator, "snooze", "mdi:alarm-snooze", coordinator.async_snooze),
        ]
    )


class AlarmButton(AlarmEntity, ButtonEntity):
    """A button that acts on the alarm."""

    def __init__(
        self,
        coordinator: AlarmCoordinator,
        key: str,
        icon: str,
        action: Callable[[], Awaitable[None]],
    ) -> None:
        """Initialise the button."""
        super().__init__(coordinator, key)
        self._attr_icon = icon
        self._action = action

    async def async_press(self) -> None:
        """Run the action of this button."""
        await self._action()
