"""AO Reach session manager for Comstar Vision."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .ao_reach.connection_config import ReachConnectionConfig
from .ao_reach.mcp_bootstrap import EmptySessionMcpBootstrap
from .ao_reach.session_bridge import SessionBridge, SessionBridgeState
from .const import DEFAULT_APP_ID, DEFAULT_ENABLED_AGENTS
from .pairing import AoPairingService

_LOGGER = logging.getLogger(__name__)


class VisionReachSession:
    """Long-lived Reach bridge for gate/zone still-burst analysis."""

    def __init__(
        self,
        *,
        engine_url: str,
        app_id: str = DEFAULT_APP_ID,
        api_token: str | None = None,
        ttl_seconds: int = 3600,
        overlay_root: Path,
        enabled_agents: list[str] | None = None,
        pairing: AoPairingService | None = None,
    ) -> None:
        self.engine_url = engine_url
        self.app_id = app_id
        self.api_token = api_token
        self.ttl_seconds = ttl_seconds
        self.overlay_root = overlay_root
        self.enabled_agents = list(enabled_agents or DEFAULT_ENABLED_AGENTS)
        self.pairing = pairing
        self.bootstrap = EmptySessionMcpBootstrap()
        self.bridge = SessionBridge()
        self.connected = False
        self.last_error: str | None = None

    def _config(self, *, session_id: str = "comstar-vision") -> ReachConnectionConfig:
        headers: dict[str, str] = {
            "x-agentic-user-name": "home-assistant",
            "x-agentic-session-id": session_id,
        }
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        return ReachConnectionConfig(
            base_url=self.engine_url,
            app_id=self.app_id,
            headers=headers,
            ttl_seconds=self.ttl_seconds,
            question_id_prefix="comstar-vision",
            dynamic_planning=True,
            default_run_mode="dynamic",
            mtls=self.pairing.mtls_config() if self.pairing else None,
        )

    @property
    def paired(self) -> bool:
        return bool(self.pairing and self.pairing.mtls_config() is not None)

    async def ensure_started(self, *, session_id: str = "comstar-vision") -> None:
        if self.bridge.is_active:
            return
        if not self.paired and self.engine_url.lower().startswith("https://"):
            _LOGGER.warning(
                "Starting Reach without mTLS material; engines with mtls.required "
                "will reject this session. Run comstar_vision.pair first."
            )
        try:
            await self.bridge.start(
                config=self._config(session_id=session_id),
                overlay_root=str(self.overlay_root),
                mcp_bootstrap=self.bootstrap,
            )
            self.connected = self.bridge.is_active
            self.last_error = None
        except Exception as exc:  # noqa: BLE001
            self.connected = False
            self.last_error = str(exc)
            _LOGGER.exception("Reach session start failed: %s", exc)
            raise

    async def stop(self) -> None:
        await self.bridge.stop(clear_remote=True)
        self.connected = False

    async def refresh_overlay(self) -> None:
        if self.bridge.is_active:
            await self.bridge.refresh_overlay()

    async def analyze_images(
        self,
        *,
        text: str,
        images: list[dict[str, Any]],
        selected_agent_provider_ids: list[str] | None = None,
        timeout: float = 180.0,
    ) -> dict[str, Any]:
        """Send multimodal chat with stills to the vision overlay agent(s)."""
        await self.ensure_started()
        agents = [
            a
            for a in (selected_agent_provider_ids or self.enabled_agents)
            if a and str(a).strip()
        ]
        if not agents:
            raise RuntimeError("No vision agents selected — fail-closed")
        if not images:
            raise RuntimeError("No images provided for analysis")
        return await self.bridge.chat(
            text=text,
            run_mode="dynamic",
            selected_agent_provider_ids=agents,
            images=images,
            timeout=timeout,
        )

    @property
    def state(self) -> SessionBridgeState:
        return self.bridge.state
