"""Comstar Vision — AO Reach still-burst analysis for Home Assistant motion AI."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
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
    DEFAULT_SESSION_ENV,
    DEFAULT_TARGET_WIDTH,
    DEFAULT_TTL,
    DOMAIN,
    MULTIMODAL_REQUIRED_ERROR,
    SERVICE_CLEAR_PAIRING,
    SERVICE_IMAGE_ANALYZER,
    SERVICE_PAIR,
    SERVICE_PROBE_REACH,
    SERVICE_REFRESH_OVERLAY,
)
from .image_prep import load_images_for_reach, parse_image_file_field

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)

IMAGE_ANALYZER_SCHEMA = vol.Schema(
    {
        vol.Required("image_file"): vol.Any(cv.string, [cv.string]),
        vol.Required("message"): cv.string,
        vol.Optional("model"): cv.string,
        vol.Optional("temperature"): vol.Coerce(float),
        vol.Optional("max_tokens"): vol.Coerce(int),
        vol.Optional("target_width"): vol.Coerce(int),
        vol.Optional("selected_agents"): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional("timeout"): vol.Coerce(float),
        # llmvision drop-in no-ops
        vol.Optional("provider"): cv.string,
        vol.Optional("include_filename"): cv.boolean,
        vol.Optional("store_in_timeline"): cv.boolean,
        vol.Optional("use_memory"): cv.boolean,
        vol.Optional("generate_title"): cv.boolean,
        vol.Optional("expose_images"): cv.boolean,
        vol.Optional("mock_reply"): cv.string,
    }
)

PAIR_SCHEMA = vol.Schema(
    {
        vol.Required("enroll_token"): cv.string,
        vol.Optional("client_name"): cv.string,
    }
)


def _merged_entry_data(entry: ConfigEntry) -> dict[str, Any]:
    return {**entry.data, **entry.options}


def _parse_session_env(raw: Any) -> dict[str, str]:
    """Accept dict or KEY=VALUE newline text."""
    if isinstance(raw, dict):
        return {str(k).strip(): str(v) for k, v in raw.items() if str(k).strip()}
    text = str(raw or "").strip()
    if not text:
        return {}
    out: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        if key:
            out[key] = val.strip()
    return out


def _empty_response(*, error: str, question_id: str = "") -> dict[str, Any]:
    return {
        "response_text": "",
        "text": "",
        "question_id": question_id,
        "error": error,
        "image_count": 0,
    }


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up via configuration.yaml when present."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up via HACS / UI config entry."""
    from .pairing import AoPairingService
    from .reach_session import VisionReachSession

    hass.data.setdefault(DOMAIN, {})
    data = _merged_entry_data(entry)
    overlay_root = Path(__file__).parent / "overlays"
    enabled_agents = list(data.get(CONF_ENABLED_AGENTS) or DEFAULT_ENABLED_AGENTS)
    enabled_mcps = list(data.get(CONF_ENABLED_MCPS) or DEFAULT_ENABLED_MCPS)
    enabled_skills = list(data.get(CONF_ENABLED_SKILLS) or DEFAULT_ENABLED_SKILLS)
    harness_profile = str(
        data.get(CONF_HARNESS_PROFILE) or DEFAULT_HARNESS_PROFILE
    ).strip()
    session_env = _parse_session_env(data.get(CONF_SESSION_ENV) or DEFAULT_SESSION_ENV)
    engine_url = str(data.get(CONF_ENGINE_URL) or DEFAULT_ENGINE_URL)

    material_dir = Path(hass.config.path(f"comstar_vision_mtls_{entry.entry_id}"))
    pairing = await hass.async_add_executor_job(
        lambda: AoPairingService(engine_url=engine_url, material_dir=material_dir)
    )

    session = VisionReachSession(
        engine_url=engine_url,
        app_id=str(data.get(CONF_APP_ID) or DEFAULT_APP_ID),
        api_token=(str(data.get(CONF_API_TOKEN) or "").strip() or None),
        ttl_seconds=int(data.get(CONF_TTL_SECONDS) or DEFAULT_TTL),
        overlay_root=overlay_root,
        enabled_agents=enabled_agents,
        enabled_mcps=enabled_mcps,
        enabled_skills=enabled_skills,
        harness_profile=harness_profile or None,
        session_env=session_env or None,
        pairing=pairing,
    )

    runtime = {
        "entry": entry,
        "session": session,
        "pairing": pairing,
        "overlay_root": overlay_root,
        "enabled_agents": enabled_agents,
        "enabled_mcps": enabled_mcps,
        "enabled_skills": enabled_skills,
        "harness_profile": harness_profile,
        "session_env": session_env,
        "default_target_width": int(
            data.get(CONF_DEFAULT_TARGET_WIDTH) or DEFAULT_TARGET_WIDTH
        ),
        "multimodal_ready": bool(
            data.get(CONF_MULTIMODAL_READY, DEFAULT_MULTIMODAL_READY)
        ),
    }
    hass.data[DOMAIN][entry.entry_id] = runtime
    hass.data[DOMAIN]["primary"] = runtime

    enroll_token = str(data.get(CONF_ENROLL_TOKEN) or "").strip()
    if enroll_token:
        result = await pairing.enroll(enroll_token)
        if not result.get("ok"):
            _LOGGER.error("AO mTLS enrollment failed: %s", result.get("error"))
        hass.config_entries.async_update_entry(
            entry,
            data={k: v for k, v in entry.data.items() if k != CONF_ENROLL_TOKEN},
            options={k: v for k, v in entry.options.items() if k != CONF_ENROLL_TOKEN},
        )

    async def _image_analyzer(call: ServiceCall) -> dict[str, Any]:
        return await _async_image_analyzer(hass, call)

    async def _probe_reach(call: ServiceCall) -> dict[str, Any]:
        rt = hass.data[DOMAIN].get("primary") or {}
        sess: VisionReachSession | None = rt.get("session")
        pair_svc = rt.get("pairing")
        pairing_info = pair_svc.inspect() if pair_svc else {"paired": False}
        if sess is None:
            return {
                "ok": False,
                "error": "Reach not configured",
                "pairing": pairing_info,
            }
        try:
            await sess.ensure_started()
            st = sess.state
            return {
                "ok": True,
                "connected": sess.connected,
                "paired": sess.paired,
                "pairing": pairing_info,
                "session_overlay": bool(getattr(sess.bridge, "session_overlay", False)),
                "mcp_tunnel": bool(getattr(sess.bridge, "mcp_tunnel", False)),
                "state": getattr(st, "name", str(st)),
                "enabled_agents": list(sess.enabled_agents),
                "enabled_mcps": list(sess.enabled_mcps),
                "enabled_skills": list(sess.enabled_skills),
                "harness_profile": sess.harness_profile or "",
                "engine_url": sess.engine_url,
            }
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc), "pairing": pairing_info}

    async def _pair(call: ServiceCall) -> dict[str, Any]:
        rt = hass.data[DOMAIN].get("primary") or {}
        pair_svc = rt.get("pairing")
        if pair_svc is None:
            return {"ok": False, "error": "Pairing service unavailable"}
        result = await pair_svc.enroll(
            str(call.data["enroll_token"]).strip(),
            client_name=call.data.get("client_name"),
        )
        sess = rt.get("session")
        if result.get("ok") and sess is not None:
            await sess.stop()
        hass.bus.async_fire(f"{DOMAIN}_pair_result", result)
        return result

    async def _clear_pairing(call: ServiceCall) -> dict[str, Any]:
        rt = hass.data[DOMAIN].get("primary") or {}
        pair_svc = rt.get("pairing")
        if pair_svc is None:
            return {"ok": False, "error": "Pairing service unavailable"}
        sess = rt.get("session")
        if sess is not None:
            await sess.stop()
        return await hass.async_add_executor_job(pair_svc.clear)

    async def _refresh_overlay(call: ServiceCall) -> None:
        rt = hass.data[DOMAIN].get("primary") or {}
        sess = rt.get("session")
        if sess is not None:
            await sess.refresh_overlay()

    hass.services.async_register(
        DOMAIN,
        SERVICE_IMAGE_ANALYZER,
        _image_analyzer,
        schema=IMAGE_ANALYZER_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_PROBE_REACH,
        _probe_reach,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REFRESH_OVERLAY,
        _refresh_overlay,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_PAIR,
        _pair,
        schema=PAIR_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CLEAR_PAIRING,
        _clear_pairing,
        supports_response=SupportsResponse.OPTIONAL,
    )

    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload integration entry."""
    runtime = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if runtime and runtime.get("session"):
        await runtime["session"].stop()
    if hass.data.get(DOMAIN, {}).get("primary") is runtime:
        hass.data[DOMAIN].pop("primary", None)
    if DOMAIN in hass.data and not any(k != "primary" for k in hass.data[DOMAIN]):
        for svc in (
            SERVICE_IMAGE_ANALYZER,
            SERVICE_PROBE_REACH,
            SERVICE_REFRESH_OVERLAY,
            SERVICE_PAIR,
            SERVICE_CLEAR_PAIRING,
        ):
            hass.services.async_remove(DOMAIN, svc)
    return True


async def _async_image_analyzer(hass: HomeAssistant, call: ServiceCall) -> dict[str, Any]:
    rt = hass.data.get(DOMAIN, {}).get("primary") or {}
    sess = rt.get("session")
    mock_reply = call.data.get("mock_reply")
    if mock_reply is not None:
        text = str(mock_reply)
        return {
            "response_text": text,
            "text": text,
            "question_id": "mock",
            "error": "",
            "image_count": 0,
        }

    paths = parse_image_file_field(call.data.get("image_file"))
    if not paths:
        return _empty_response(error="image_file is empty")

    target_width = int(
        call.data.get("target_width")
        or rt.get("default_target_width")
        or DEFAULT_TARGET_WIDTH
    )
    images = await hass.async_add_executor_job(
        lambda: load_images_for_reach(paths, target_width=target_width)
    )
    if not images:
        return _empty_response(error="no readable image files")

    if not bool(rt.get("multimodal_ready", DEFAULT_MULTIMODAL_READY)):
        return {
            "response_text": "",
            "text": "",
            "question_id": "",
            "error": MULTIMODAL_REQUIRED_ERROR,
            "image_count": len(images),
        }

    if sess is None:
        return _empty_response(error="Reach session not configured")

    message = str(call.data.get("message") or "").strip()
    if not message:
        return _empty_response(error="message is empty", question_id="")

    # Optional escape hatch only — AO picks the vision model by default.
    model = str(call.data.get("model") or "").strip()
    agents = list(call.data.get("selected_agents") or rt.get("enabled_agents") or [])
    timeout = float(call.data.get("timeout") or 180.0)

    text = message
    if model:
        text = f"[model={model}]\n{message}"

    try:
        result = await sess.analyze_images(
            text=text,
            images=images,
            selected_agent_provider_ids=agents or None,
            timeout=timeout,
        )
    except Exception as exc:  # noqa: BLE001
        err = str(exc)
        _LOGGER.exception("image_analyzer Reach chat failed: %s", exc)
        if "images" in err.lower() or "multimodal" in err.lower():
            err = f"{err} | {MULTIMODAL_REQUIRED_ERROR}"
        return {
            "response_text": "",
            "text": "",
            "question_id": "",
            "error": err or MULTIMODAL_REQUIRED_ERROR,
            "image_count": len(images),
        }

    raw = str(result.get("text") or "").strip()
    question_id = str(result.get("questionId") or result.get("question_id") or "")
    return {
        "response_text": raw,
        "text": raw,
        "question_id": question_id,
        "error": "",
        "image_count": len(images),
        "agents_used": agents,
    }
