"""Base entity for the Music Assistant Alarm Clock integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AlarmCoordinator


class AlarmEntity(CoordinatorEntity[AlarmCoordinator]):
    """An entity that belongs to one alarm."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: AlarmCoordinator, key: str) -> None:
        """Initialise the entity."""
        super().__init__(coordinator)
        self._key = key
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)},
            name=coordinator.entry.title,
            manufacturer="Music Assistant Alarm Clock",
            model="Alarm",
        )
