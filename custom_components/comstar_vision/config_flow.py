"""Config flow for Comstar Vision (AO Reach)."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    AGENT_VISION_SCENE,
    CONF_API_TOKEN,
    CONF_APP_ID,
    CONF_DEFAULT_MODEL,
    CONF_DEFAULT_TARGET_WIDTH,
    CONF_ENABLED_AGENTS,
    CONF_ENGINE_URL,
    CONF_ENROLL_TOKEN,
    CONF_MULTIMODAL_READY,
    CONF_TTL_SECONDS,
    DEFAULT_APP_ID,
    DEFAULT_ENABLED_AGENTS,
    DEFAULT_ENGINE_URL,
    DEFAULT_MODEL,
    DEFAULT_MULTIMODAL_READY,
    DEFAULT_TARGET_WIDTH,
    DEFAULT_TTL,
    DOMAIN,
)


def _user_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    d = defaults or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_ENGINE_URL, default=d.get(CONF_ENGINE_URL, DEFAULT_ENGINE_URL)
            ): str,
            vol.Optional(CONF_API_TOKEN, default=d.get(CONF_API_TOKEN, "")): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
            ),
            vol.Optional(CONF_ENROLL_TOKEN, default=""): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
            ),
            vol.Optional(CONF_APP_ID, default=d.get(CONF_APP_ID, DEFAULT_APP_ID)): str,
            vol.Optional(CONF_TTL_SECONDS, default=d.get(CONF_TTL_SECONDS, DEFAULT_TTL)): vol.All(
                vol.Coerce(int), vol.Range(min=60, max=86400)
            ),
            vol.Optional(
                CONF_ENABLED_AGENTS,
                default=d.get(CONF_ENABLED_AGENTS, DEFAULT_ENABLED_AGENTS),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[AGENT_VISION_SCENE],
                    multiple=True,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(
                CONF_DEFAULT_MODEL, default=d.get(CONF_DEFAULT_MODEL, DEFAULT_MODEL)
            ): str,
            vol.Optional(
                CONF_DEFAULT_TARGET_WIDTH,
                default=d.get(CONF_DEFAULT_TARGET_WIDTH, DEFAULT_TARGET_WIDTH),
            ): vol.All(vol.Coerce(int), vol.Range(min=320, max=4096)),
            vol.Optional(
                CONF_MULTIMODAL_READY,
                default=d.get(CONF_MULTIMODAL_READY, DEFAULT_MULTIMODAL_READY),
            ): bool,
        }
    )


class ComstarVisionConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Comstar Vision."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is not None:
            enroll = (user_input.get(CONF_ENROLL_TOKEN) or "").strip()
            return self.async_create_entry(
                title="Comstar Vision",
                data={
                    **({CONF_ENROLL_TOKEN: enroll} if enroll else {}),
                    CONF_ENGINE_URL: user_input[CONF_ENGINE_URL].rstrip("/"),
                    CONF_API_TOKEN: user_input.get(CONF_API_TOKEN) or "",
                    CONF_APP_ID: user_input.get(CONF_APP_ID) or DEFAULT_APP_ID,
                    CONF_TTL_SECONDS: int(user_input.get(CONF_TTL_SECONDS) or DEFAULT_TTL),
                    CONF_ENABLED_AGENTS: list(
                        user_input.get(CONF_ENABLED_AGENTS) or DEFAULT_ENABLED_AGENTS
                    ),
                    CONF_DEFAULT_MODEL: user_input.get(CONF_DEFAULT_MODEL) or DEFAULT_MODEL,
                    CONF_DEFAULT_TARGET_WIDTH: int(
                        user_input.get(CONF_DEFAULT_TARGET_WIDTH) or DEFAULT_TARGET_WIDTH
                    ),
                    CONF_MULTIMODAL_READY: bool(
                        user_input.get(CONF_MULTIMODAL_READY, DEFAULT_MULTIMODAL_READY)
                    ),
                },
            )
        return self.async_show_form(step_id="user", data_schema=_user_schema())

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        return ComstarVisionOptionsFlow()


class ComstarVisionOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            enroll = (user_input.get(CONF_ENROLL_TOKEN) or "").strip()
            return self.async_create_entry(
                title="",
                data={
                    **({CONF_ENROLL_TOKEN: enroll} if enroll else {}),
                    CONF_ENGINE_URL: user_input[CONF_ENGINE_URL].rstrip("/"),
                    CONF_API_TOKEN: user_input.get(CONF_API_TOKEN) or "",
                    CONF_APP_ID: user_input.get(CONF_APP_ID) or DEFAULT_APP_ID,
                    CONF_TTL_SECONDS: int(user_input.get(CONF_TTL_SECONDS) or DEFAULT_TTL),
                    CONF_ENABLED_AGENTS: list(
                        user_input.get(CONF_ENABLED_AGENTS) or DEFAULT_ENABLED_AGENTS
                    ),
                    CONF_DEFAULT_MODEL: user_input.get(CONF_DEFAULT_MODEL) or DEFAULT_MODEL,
                    CONF_DEFAULT_TARGET_WIDTH: int(
                        user_input.get(CONF_DEFAULT_TARGET_WIDTH) or DEFAULT_TARGET_WIDTH
                    ),
                    CONF_MULTIMODAL_READY: bool(
                        user_input.get(CONF_MULTIMODAL_READY, DEFAULT_MULTIMODAL_READY)
                    ),
                },
            )
        defaults = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(step_id="init", data_schema=_user_schema(defaults))
