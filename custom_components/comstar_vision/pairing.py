"""AO mTLS pairing for Comstar Vision (Agentic Watering / Comstar parity)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .ao_reach.mtls import (
    ReachMtlsConfig,
    clear_reach_mtls_material,
    load_reach_mtls_material,
    material_present,
)
from .ao_reach.mtls_enroller import ReachMtlsEnroller
from .ao_reach.session_bridge import probe_health
from .const import DEFAULT_APP_ID

_LOGGER = logging.getLogger(__name__)


class AoPairingService:
    """Manage the mTLS client material this integration presents to the AO engine."""

    def __init__(self, *, engine_url: str, material_dir: Path) -> None:
        self.engine_url = engine_url.rstrip("/")
        self.material_dir = material_dir
        self.material_dir.mkdir(parents=True, exist_ok=True)
        self.last_error: str | None = None
        self.last_probe: dict[str, Any] | None = None

    def inspect(self) -> dict[str, Any]:
        paired = material_present(str(self.material_dir))
        out: dict[str, Any] = {
            "ok": True,
            "base_url": self.engine_url,
            "material_dir": str(self.material_dir),
            "paired": paired,
            "last_error": self.last_error,
        }
        if paired:
            try:
                material = load_reach_mtls_material(
                    ReachMtlsConfig(material_dir=str(self.material_dir))
                )
                out["subject"] = material.subject
                out["expires_at"] = material.expires_at
            except Exception as exc:  # noqa: BLE001
                out["ok"] = False
                out["last_error"] = str(exc)
        return out

    async def enroll(
        self, enroll_token: str, *, client_name: str | None = None
    ) -> dict[str, Any]:
        try:
            await ReachMtlsEnroller().enroll(
                base_url=self.engine_url,
                enroll_token=enroll_token,
                material_dir=str(self.material_dir),
                common_name=client_name or DEFAULT_APP_ID,
                trust_enrollment_ca=True,
            )
            self.last_error = None
            return {"ok": True, "action": "enroll", **self.inspect()}
        except Exception as exc:  # noqa: BLE001
            self.last_error = str(exc)
            _LOGGER.exception("AO mTLS enroll failed")
            return {"ok": False, "action": "enroll", "error": str(exc), **self.inspect()}

    def clear(self) -> dict[str, Any]:
        clear_reach_mtls_material(str(self.material_dir))
        self.last_error = None
        self.last_probe = None
        return {"ok": True, "action": "clear", **self.inspect()}

    async def probe(self) -> dict[str, Any]:
        if not material_present(str(self.material_dir)):
            raise RuntimeError("not paired — enroll first")
        result = await probe_health(
            self.engine_url,
            ReachMtlsConfig(material_dir=str(self.material_dir)),
        )
        self.last_probe = result
        if not result.get("ok"):
            self.last_error = f"probe HTTP {result.get('status_code')}"
        else:
            self.last_error = None
        return {**result, **self.inspect()}

    def mtls_config(self) -> ReachMtlsConfig | None:
        if not material_present(str(self.material_dir)):
            return None
        return ReachMtlsConfig(material_dir=str(self.material_dir))
