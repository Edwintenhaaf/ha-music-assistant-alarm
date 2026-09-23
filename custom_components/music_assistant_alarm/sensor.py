"""Sensors of a Music Assistant alarm."""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AlarmConfigEntry
from .const import (
    NEXT_ALARM_GRACE_MINUTES,
    STATUS_ARMED,
    STATUS_LIGHT,
    STATUS_OFF,
    STATUS_RINGING,
    STATUS_SNOOZED,
)
from .entity import AlarmEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AlarmConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors of one alarm."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            AlarmNextSensor(coordinator, "next_alarm"),
            AlarmStatusSensor(coordinator, "status"),
        ]
    )


class AlarmNextSensor(AlarmEntity, SensorEntity):
    """When the alarm goes off next."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:alarm-check"

    @property
    def native_value(self) -> datetime | None:
        """Return the next wake-up time.

        The alarm that just fired is kept in place for a couple of minutes: a
        Squeezebox reading this would otherwise cancel its own timer a second
        before the alarm is due, and never open its wake-up window.
        """
        return self.coordinator.next_alarm(grace_minutes=NEXT_ALARM_GRACE_MINUTES)


class AlarmStatusSensor(AlarmEntity, SensorEntity):
    """What the alarm is doing."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options: ClassVar[list[str]] = [
        STATUS_OFF,
        STATUS_ARMED,
        STATUS_LIGHT,
        STATUS_RINGING,
        STATUS_SNOOZED,
    ]
    _attr_icon = "mdi:alarm-note"

    @property
    def native_value(self) -> str:
        """Return the status of the alarm."""
        return self.coordinator.status
