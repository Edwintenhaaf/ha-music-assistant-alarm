"""The radio station or playlist a Music Assistant alarm wakes you with."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AlarmConfigEntry
from .const import SET_MEDIA_NAME, SET_MEDIA_TYPE
from .entity import AlarmEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AlarmConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the media select of one alarm."""
    async_add_entities([AlarmMediaSelect(entry.runtime_data, "media")])


class AlarmMediaSelect(AlarmEntity, SelectEntity):
    """Pick a radio station or playlist from the Music Assistant library."""

    _attr_icon = "mdi:playlist-music"

    @property
    def options(self) -> list[str]:
        """Return every radio station and playlist in the library."""
        return self.coordinator.media_options

    @property
    def current_option(self) -> str | None:
        """Return the selected radio station or playlist."""
        selected = self.coordinator.settings.get(SET_MEDIA_NAME)
        return selected or None

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Expose whether the selection is a radio station or a playlist."""
        return {"media_type": str(self.coordinator.settings.get(SET_MEDIA_TYPE, ""))}

    async def async_select_option(self, option: str) -> None:
        """Store the selected radio station or playlist."""
        await self.coordinator.async_update_settings(
            **{
                SET_MEDIA_NAME: option,
                SET_MEDIA_TYPE: self.coordinator.media_type_of(option),
            }
        )
