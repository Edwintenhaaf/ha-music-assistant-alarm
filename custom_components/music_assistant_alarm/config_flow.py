"""Config flow for the Music Assistant Alarm Clock integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_LIGHTS,
    CONF_NOTIFY_SERVICE,
    CONF_PLAYER,
    CONF_SQUEEZEBOX_HOST,
    CONF_SQUEEZEBOX_PORT,
    DEFAULT_SQUEEZEBOX_PORT,
    DOMAIN,
)

PLAYER_SELECTOR = selector.EntitySelector(
    selector.EntitySelectorConfig(domain="media_player", integration="music_assistant")
)
LIGHT_SELECTOR = selector.EntitySelector(
    selector.EntitySelectorConfig(domain="light", multiple=True)
)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): selector.TextSelector(),
        vol.Required(CONF_PLAYER): PLAYER_SELECTOR,
        vol.Optional(CONF_LIGHTS, default=[]): LIGHT_SELECTOR,
    }
)


class AlarmConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add an alarm."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the name, the player and the wake-up light."""
        if user_input is not None:
            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data={
                    CONF_NAME: user_input[CONF_NAME],
                    CONF_PLAYER: user_input[CONF_PLAYER],
                },
                options={CONF_LIGHTS: user_input.get(CONF_LIGHTS, [])},
            )
        return self.async_show_form(step_id="user", data_schema=USER_SCHEMA)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return AlarmOptionsFlow()


class AlarmOptionsFlow(OptionsFlow):
    """Change the player, the lights and the extras of an alarm."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show and store the options."""
        if user_input is not None:
            player = user_input.pop(CONF_PLAYER, None)
            if player and player != self.config_entry.data.get(CONF_PLAYER):
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data={**self.config_entry.data, CONF_PLAYER: player},
                )
            return self.async_create_entry(data=user_input)

        options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_PLAYER, default=self.config_entry.data.get(CONF_PLAYER)
                ): PLAYER_SELECTOR,
                vol.Optional(
                    CONF_LIGHTS, default=list(options.get(CONF_LIGHTS, []))
                ): LIGHT_SELECTOR,
                vol.Optional(
                    CONF_NOTIFY_SERVICE,
                    description={"suggested_value": options.get(CONF_NOTIFY_SERVICE)},
                ): selector.TextSelector(),
                vol.Optional(
                    CONF_SQUEEZEBOX_HOST,
                    description={"suggested_value": options.get(CONF_SQUEEZEBOX_HOST)},
                ): selector.TextSelector(),
                vol.Optional(
                    CONF_SQUEEZEBOX_PORT,
                    default=options.get(CONF_SQUEEZEBOX_PORT, DEFAULT_SQUEEZEBOX_PORT),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1, max=65535, step=1, mode=selector.NumberSelectorMode.BOX
                    )
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
