# Install — Comstar Vision

## Prerequisites

- Home Assistant 2024.6+
- HACS
- ADA Agentic Orchestration engine reachable at `https://10.0.10.16:8765` (or your LAN URL)
- AO Admin access to mint tokens for **`appId: comstar-vision`**

## Install

1. HACS → Integrations → Custom repositories → `https://github.com/zlatko-lakisic/hacs-comstar-vision` (Integration)
2. Download **Comstar Vision**, restart Home Assistant
3. Settings → Devices & services → Add **Comstar Vision**
4. Engine URL: `https://10.0.10.16:8765`
5. API token: mint in ADA AO Admin → Access → API tokens → External client → **`comstar-vision`**
6. Optional at setup: paste one-time **mTLS enrollment** token (same appId / CN `comstar-vision`)
7. Leave **Multimodal ready** **off** until ADA implements [AO_REACH_MULTIMODAL_HANDOFF.md](AO_REACH_MULTIMODAL_HANDOFF.md)

## Pair / probe

```yaml
service: comstar_vision.pair
data:
  enroll_token: "<enrollment token>"
  client_name: comstar-vision
```

```yaml
service: comstar_vision.probe_reach
```

Expect `ok: true`, `paired: true`, `session_overlay: true`.

Material is stored under `config/comstar_vision_mtls_<entry_id>/`.

## Enable after AO multimodal lands

1. Confirm ADA acceptance tests in the handoff doc
2. Comstar Vision → Configure → enable **Multimodal ready**
3. Reload the integration
4. Smoke `comstar_vision.image_analyzer` with two tmp JPEGs

## Blueprint cutover

Zone / gate blueprints call `comstar_vision.image_analyzer` instead of `llmvision.image_analyzer`. Keep `response_variable: ai_response` — reply key remains `response_text`.

## Do not reuse tokens

| appId | Consumer |
|-------|----------|
| `comstar-ha` | Comstar Assist |
| `agentic-watering` | Agentic Watering (Jetson) |
| `home-assistant` | Legacy LLM Vision HTTP |
| **`comstar-vision`** | **This integration (ADA)** |
