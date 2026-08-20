"""Config flow for Comstar Vision (AO Reach)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .ao_reach.catalog_client import ReachCatalog, ReachCatalogClient
from .ao_reach.connection_config import ReachConnectionConfig
from .const import (
    AGENT_VISION_SCENE,
    CONF_API_TOKEN,
    CONF_APP_ID,
    CONF_DEFAULT_TARGET_WIDTH,
    CONF_ENABLED_AGENTS,
    CONF_ENABLED_MCPS,
    CONF_ENABLED_SKILLS,
    CONF_ENGINE_URL,
    CONF_ENROLL_TOKEN,
    CONF_HARNESS_PROFILE,
    CONF_MULTIMODAL_READY,
    CONF_SESSION_ENV,
    CONF_TTL_SECONDS,
    DEFAULT_APP_ID,
    DEFAULT_ENABLED_AGENTS,
    DEFAULT_ENABLED_MCPS,
    DEFAULT_ENABLED_SKILLS,
    DEFAULT_ENGINE_URL,
    DEFAULT_HARNESS_PROFILE,
    DEFAULT_MULTIMODAL_READY,
    DEFAULT_TARGET_WIDTH,
    DEFAULT_TTL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _connection_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
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
                CONF_DEFAULT_TARGET_WIDTH,
                default=d.get(CONF_DEFAULT_TARGET_WIDTH, DEFAULT_TARGET_WIDTH),
            ): vol.All(vol.Coerce(int), vol.Range(min=320, max=4096)),
            vol.Optional(
                CONF_MULTIMODAL_READY,
                default=d.get(CONF_MULTIMODAL_READY, DEFAULT_MULTIMODAL_READY),
            ): bool,
        }
    )


def _session_env_to_text(raw: Any) -> str:
    if isinstance(raw, dict):
        return "\n".join(f"{k}={v}" for k, v in raw.items())
    return str(raw or "")


def _normalize_id_list(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    text = str(raw or "").strip()
    if not text:
        return []
    parts: list[str] = []
    for chunk in text.replace("\n", ",").split(","):
        item = chunk.strip()
        if item:
            parts.append(item)
    return parts


def _capabilities_schema(
    defaults: dict[str, Any] | None = None,
    *,
    catalog: ReachCatalog | None = None,
) -> vol.Schema:
    d = defaults or {}
    agents_default = list(d.get(CONF_ENABLED_AGENTS) or DEFAULT_ENABLED_AGENTS)
    mcps_default = list(d.get(CONF_ENABLED_MCPS) or DEFAULT_ENABLED_MCPS)
    skills_default = list(d.get(CONF_ENABLED_SKILLS) or DEFAULT_ENABLED_SKILLS)
    harness_default = str(d.get(CONF_HARNESS_PROFILE) or DEFAULT_HARNESS_PROFILE)
    env_default = _session_env_to_text(d.get(CONF_SESSION_ENV))

    if catalog is not None:
        agent_opts = [AGENT_VISION_SCENE] + [
            e.id for e in catalog.agents if e.id and e.id != AGENT_VISION_SCENE
        ]
        seen: set[str] = set()
        deduped_agents: list[str] = []
        for item in agent_opts:
            if item not in seen:
                seen.add(item)
                deduped_agents.append(item)
        agent_opts = deduped_agents
        mcp_opts = [e.id for e in catalog.mcps if e.id]
        skill_opts = [e.id for e in catalog.skills if e.id]
        harness_opts = [""] + [e.id for e in catalog.harnesses if e.id]
        return vol.Schema(
            {
                vol.Optional(CONF_ENABLED_AGENTS, default=agents_default): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=agent_opts or [AGENT_VISION_SCENE],
                        multiple=True,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(CONF_ENABLED_MCPS, default=mcps_default): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=mcp_opts or ["(none)"],
                        multiple=True,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(CONF_ENABLED_SKILLS, default=skills_default): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=skill_opts or ["(none)"],
                        multiple=True,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(CONF_HARNESS_PROFILE, default=harness_default): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=harness_opts or [""],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(CONF_SESSION_ENV, default=env_default): selector.TextSelector(
                    selector.TextSelectorConfig(multiline=True)
                ),
            }
        )

    # Manual fallback when catalog is unreachable
    return vol.Schema(
        {
            vol.Optional(
                CONF_ENABLED_AGENTS,
                default=",".join(agents_default) if agents_default else AGENT_VISION_SCENE,
            ): selector.TextSelector(selector.TextSelectorConfig(multiline=True)),
            vol.Optional(
                CONF_ENABLED_MCPS,
                default=",".join(mcps_default),
            ): selector.TextSelector(selector.TextSelectorConfig(multiline=True)),
            vol.Optional(
                CONF_ENABLED_SKILLS,
                default=",".join(skills_default),
            ): selector.TextSelector(selector.TextSelectorConfig(multiline=True)),
            vol.Optional(CONF_HARNESS_PROFILE, default=harness_default): str,
            vol.Optional(CONF_SESSION_ENV, default=env_default): selector.TextSelector(
                selector.TextSelectorConfig(multiline=True)
            ),
        }
    )


async def _fetch_catalog(
    *,
    engine_url: str,
    api_token: str,
    app_id: str,
    material_dir: Path | None = None,
) -> ReachCatalog | None:
    from .ao_reach.mtls import ReachMtlsConfig

    headers: dict[str, str] = {"Accept": "application/json"}
    if api_token:
        headers["Authorization"] = f"Bearer {api_token}"
    mtls = None
    if material_dir and (material_dir / "cert.pem").is_file():
        mtls = ReachMtlsConfig(material_dir=str(material_dir))
    try:
        config = ReachConnectionConfig(
            base_url=engine_url.rstrip("/"),
            app_id=app_id or DEFAULT_APP_ID,
            headers=headers,
            mtls=mtls,
        )
        return await ReachCatalogClient().fetch(config)
    except Exception as exc:  # noqa: BLE001
        _LOGGER.warning("AO catalog fetch failed: %s", exc)
        return None


async def _async_enroll_token(
    *,
    engine_url: str,
    enroll_token: str,
    material_dir: Path,
    app_id: str,
) -> dict[str, Any]:
    """Redeem enroll token against engine_url.

    On success, mTLS PEMs are overwritten for this material_dir. On failure the
    previous pairing files are left untouched.

    Returns ``{"ok": True, "engine_url", "subject", ...}`` or
    ``{"ok": False, "error": "..."}``.
    """
    from .pairing import AoPairingService

    token = (enroll_token or "").strip()
    if not token:
        return {"ok": True, "skipped": True}

    base = engine_url.rstrip("/")
    pairing = AoPairingService(engine_url=base, material_dir=material_dir)
    result = await pairing.enroll(token, client_name=app_id or DEFAULT_APP_ID)
    if result.get("ok"):
        return {
            "ok": True,
            "engine_url": base,
            "subject": result.get("subject") or app_id or DEFAULT_APP_ID,
            "paired": True,
        }
    return {
        "ok": False,
        "engine_url": base,
        "error": str(result.get("error") or "AO mTLS enrollment failed"),
    }


async def _async_notify_enroll_result(
    hass: HomeAssistant, result: dict[str, Any]
) -> None:
    """Surface enroll success/failure as a persistent notification."""
    engine = str(result.get("engine_url") or "").strip() or "(unknown)"
    if result.get("ok") and not result.get("skipped"):
        subject = str(result.get("subject") or DEFAULT_APP_ID)
        await hass.services.async_call(
            "persistent_notification",
            "create",
            {
                "notification_id": "comstar_vision_enroll",
                "title": "Comstar Vision enrolled",
                "message": (
                    f"mTLS enrollment succeeded.\n"
                    f"Server: {engine}\n"
                    f"Client: {subject}"
                ),
            },
            blocking=False,
        )
        return
    if result.get("ok"):
        return
    err = str(result.get("error") or "unknown error")
    await hass.services.async_call(
        "persistent_notification",
        "create",
        {
            "notification_id": "comstar_vision_enroll",
            "title": "Comstar Vision enrollment failed",
            "message": f"Server: {engine}\nError: {err}",
        },
        blocking=False,
    )


def _entry_payload(
    connection: dict[str, Any],
    capabilities: dict[str, Any],
) -> dict[str, Any]:
    # Enroll tokens are one-shot and must not be persisted once redeemed in the flow.
    agents = _normalize_id_list(capabilities.get(CONF_ENABLED_AGENTS))
    mcps = [
        x
        for x in _normalize_id_list(capabilities.get(CONF_ENABLED_MCPS))
        if x != "(none)"
    ]
    skills = [
        x
        for x in _normalize_id_list(capabilities.get(CONF_ENABLED_SKILLS))
        if x != "(none)"
    ]
    harness = str(capabilities.get(CONF_HARNESS_PROFILE) or "").strip()
    return {
        CONF_ENGINE_URL: str(connection[CONF_ENGINE_URL]).rstrip("/"),
        CONF_API_TOKEN: connection.get(CONF_API_TOKEN) or "",
        CONF_APP_ID: connection.get(CONF_APP_ID) or DEFAULT_APP_ID,
        CONF_TTL_SECONDS: int(connection.get(CONF_TTL_SECONDS) or DEFAULT_TTL),
        CONF_DEFAULT_TARGET_WIDTH: int(
            connection.get(CONF_DEFAULT_TARGET_WIDTH) or DEFAULT_TARGET_WIDTH
        ),
        CONF_MULTIMODAL_READY: bool(
            connection.get(CONF_MULTIMODAL_READY, DEFAULT_MULTIMODAL_READY)
        ),
        CONF_ENABLED_AGENTS: agents or list(DEFAULT_ENABLED_AGENTS),
        CONF_ENABLED_MCPS: mcps,
        CONF_ENABLED_SKILLS: skills,
        CONF_HARNESS_PROFILE: harness,
        CONF_SESSION_ENV: str(capabilities.get(CONF_SESSION_ENV) or ""),
    }


def _catalog_status_text(
    catalog: ReachCatalog | None, enroll_status: str | None = None
) -> str:
    parts: list[str] = []
    if enroll_status:
        parts.append(enroll_status)
    if catalog is not None:
        parts.append("Loaded from AO catalog.")
    else:
        parts.append(
            "Catalog unavailable — enter IDs manually (comma or newline separated)."
        )
    return " ".join(parts)


class ComstarVisionConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Comstar Vision."""

    VERSION = 1

    def __init__(self) -> None:
        self._connection: dict[str, Any] = {}
        self._catalog: ReachCatalog | None = None
        self._enroll_status: str | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is not None:
            self._connection = dict(user_input)
            # First install: keep enroll_token in entry data so async_setup_entry can
            # redeem it into the entry-scoped material dir, then notify + clear.
            if str(user_input.get(CONF_ENROLL_TOKEN) or "").strip():
                self._enroll_status = (
                    "Enrollment token accepted — pairing will complete when the "
                    f"integration loads against {str(user_input[CONF_ENGINE_URL]).rstrip('/')}."
                )
            self._catalog = await _fetch_catalog(
                engine_url=str(user_input[CONF_ENGINE_URL]),
                api_token=str(user_input.get(CONF_API_TOKEN) or ""),
                app_id=str(user_input.get(CONF_APP_ID) or DEFAULT_APP_ID),
            )
            return await self.async_step_capabilities()
        return self.async_show_form(
            step_id="user",
            data_schema=_connection_schema(),
            description_placeholders={"enroll_error": ""},
        )

    async def async_step_capabilities(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            payload = _entry_payload(self._connection, user_input)
            # Preserve one-shot token for setup_entry on first install only.
            enroll = str(self._connection.get(CONF_ENROLL_TOKEN) or "").strip()
            if enroll:
                payload[CONF_ENROLL_TOKEN] = enroll
            return self.async_create_entry(title="Comstar Vision", data=payload)
        description_placeholders = {
            "catalog_status": _catalog_status_text(self._catalog, self._enroll_status),
            "enroll_error": "",
        }
        return self.async_show_form(
            step_id="capabilities",
            data_schema=_capabilities_schema(
                {
                    CONF_ENABLED_AGENTS: DEFAULT_ENABLED_AGENTS,
                    CONF_ENABLED_MCPS: DEFAULT_ENABLED_MCPS,
                    CONF_ENABLED_SKILLS: DEFAULT_ENABLED_SKILLS,
                    CONF_HARNESS_PROFILE: DEFAULT_HARNESS_PROFILE,
                    CONF_SESSION_ENV: "",
                },
                catalog=self._catalog,
            ),
            description_placeholders=description_placeholders,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        return ComstarVisionOptionsFlow()


class ComstarVisionOptionsFlow(config_entries.OptionsFlow):
    def __init__(self) -> None:
        self._connection: dict[str, Any] = {}
        self._catalog: ReachCatalog | None = None
        self._enroll_status: str | None = None

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        defaults = {**self.config_entry.data, **self.config_entry.options}
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {"enroll_error": ""}
        if user_input is not None:
            self._connection = dict(user_input)
            engine_url = str(user_input[CONF_ENGINE_URL]).rstrip("/")
            app_id = str(user_input.get(CONF_APP_ID) or DEFAULT_APP_ID)
            enroll_token = str(user_input.get(CONF_ENROLL_TOKEN) or "").strip()
            material_dir = Path(
                self.hass.config.path(f"comstar_vision_mtls_{self.config_entry.entry_id}")
            )
            if enroll_token:
                result = await _async_enroll_token(
                    engine_url=engine_url,
                    enroll_token=enroll_token,
                    material_dir=material_dir,
                    app_id=app_id,
                )
                await _async_notify_enroll_result(self.hass, result)
                if not result.get("ok"):
                    errors["enroll_token"] = "enroll_failed"
                    placeholders["enroll_error"] = str(result.get("error") or "")
                else:
                    self._enroll_status = (
                        f"Enrolled successfully to {result.get('engine_url')} "
                        f"(client: {result.get('subject')})."
                    )
            # Never persist one-shot enroll tokens.
            self._connection.pop(CONF_ENROLL_TOKEN, None)
            if not errors:
                self._catalog = await _fetch_catalog(
                    engine_url=engine_url,
                    api_token=str(user_input.get(CONF_API_TOKEN) or ""),
                    app_id=app_id,
                    material_dir=material_dir,
                )
                return await self.async_step_capabilities()
        return self.async_show_form(
            step_id="init",
            data_schema=_connection_schema(defaults),
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_capabilities(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        defaults = {**self.config_entry.data, **self.config_entry.options}
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data=_entry_payload(self._connection, user_input),
            )
        description_placeholders = {
            "catalog_status": _catalog_status_text(self._catalog, self._enroll_status),
            "enroll_error": "",
        }
        return self.async_show_form(
            step_id="capabilities",
            data_schema=_capabilities_schema(defaults, catalog=self._catalog),
            description_placeholders=description_placeholders,
        )
