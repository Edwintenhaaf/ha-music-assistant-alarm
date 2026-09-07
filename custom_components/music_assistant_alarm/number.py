"""The adjustable numbers of a Music Assistant alarm."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import NumberEntity, NumberEntityDescription, NumberMode
from homeassistant.const import PERCENTAGE, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AlarmConfigEntry
from .const import (
    SET_FADE_MINUTES,
    SET_LIGHT_BRIGHTNESS,
    SET_LIGHT_MINUTES,
    SET_SNOOZE_MINUTES,
    SET_STOP_AFTER_MINUTES,
    SET_VOLUME,
)
from .coordinator import AlarmCoordinator
from .entity import AlarmEntity


@dataclass(frozen=True, kw_only=True)
class AlarmNumberDescription(NumberEntityDescription):
    """Describes one adjustable number of the alarm."""

    setting: str


NUMBERS: tuple[AlarmNumberDescription, ...] = (
    AlarmNumberDescription(
        key="volume",
        setting=SET_VOLUME,
        icon="mdi:volume-high",
        native_min_value=1,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        mode=NumberMode.SLIDER,
    ),
    AlarmNumberDescription(
        key="fade_minutes",
        setting=SET_FADE_MINUTES,
        icon="mdi:volume-plus",
        native_min_value=0,
        native_max_value=30,
        native_step=1,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        mode=NumberMode.BOX,
    ),
    AlarmNumberDescription(
        key="stop_after_minutes",
        setting=SET_STOP_AFTER_MINUTES,
        icon="mdi:timer-off-outline",
        native_min_value=1,
        native_max_value=240,
        native_step=1,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        mode=NumberMode.BOX,
    ),
    AlarmNumberDescription(
        key="snooze_minutes",
        setting=SET_SNOOZE_MINUTES,
        icon="mdi:alarm-snooze",
        native_min_value=1,
        native_max_value=60,
        native_step=1,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        mode=NumberMode.BOX,
    ),
    AlarmNumberDescription(
        key="light_minutes",
        setting=SET_LIGHT_MINUTES,
        icon="mdi:weather-sunset-up",
        native_min_value=0,
        native_max_value=60,
        native_step=1,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        mode=NumberMode.BOX,
    ),
    AlarmNumberDescription(
        key="light_brightness",
        setting=SET_LIGHT_BRIGHTNESS,
        icon="mdi:brightness-6",
        native_min_value=1,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        mode=NumberMode.SLIDER,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AlarmConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the numbers of one alarm."""
    async_add_entities(
        AlarmNumber(entry.runtime_data, description) for description in NUMBERS
    )


class AlarmNumber(AlarmEntity, NumberEntity):
    """One adjustable number of the alarm."""

    entity_description: AlarmNumberDescription

    def __init__(
        self, coordinator: AlarmCoordinator, description: AlarmNumberDescription
    ) -> None:
        """Initialise the number."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float:
        """Return the current value."""
        return float(self.coordinator.settings.get(self.entity_description.setting, 0))

    async def async_set_native_value(self, value: float) -> None:
        """Store a new value."""
        await self.coordinator.async_update_settings(
            **{self.entity_description.setting: int(value)}
        )
