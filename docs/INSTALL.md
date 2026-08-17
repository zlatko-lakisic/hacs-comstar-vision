# Install — Comstar Vision

## Prerequisites

- Home Assistant 2024.6+
- HACS
- ADA Agentic Orchestration engine reachable at `https://10.0.10.16:8765` (or your LAN URL)
- AO Admin access to mint tokens for **`appId: comstar-vision`**
- At least one **vision-capable** model configured on ADA (local VLM or valid cloud key)

## Install

1. HACS → Integrations → Custom repositories → `https://github.com/zlatko-lakisic/hacs-comstar-vision` (Integration)
2. Download **Comstar Vision**, restart Home Assistant
3. Settings → Devices & services → Add **Comstar Vision**
4. **Connection step:** Engine URL `https://10.0.10.16:8765`, API token (mint External client → **`comstar-vision`**), optional mTLS enrollment token
5. **Capabilities step:** pick agents / MCP servers / skills / harness from the live AO catalog (or enter IDs manually if the catalog is unreachable). Default agent: `client.vision_scene_analyzer`
6. Enable **Multimodal ready** once ADA multimodal + a vision model are verified

Do **not** configure an OpenAI (or other) model in the plugin — AO picks the vision model for image turns.

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

## Smoke

```yaml
service: comstar_vision.image_analyzer
data:
  image_file: |
    /config/www/tmp/near_driveway_1.jpg
    /config/www/tmp/near_driveway_2.jpg
  message: |
    Reply with three lines. Line 1 exactly PERSON or CAR or DOG or OTHER or CLEAR.
  target_width: 1280
```

Expect `response_text` non-empty. Optional `model:` is an escape hatch only.

## Blueprint cutover

Zone / gate blueprints call `comstar_vision.image_analyzer` instead of `llmvision.image_analyzer`. Keep `response_variable: ai_response` — reply key remains `response_text`. No `vision_model` blueprint input.

## Do not reuse tokens

| appId | Consumer |
|-------|----------|
| `comstar-ha` | Comstar Assist |
| `agentic-watering` | Agentic Watering (Jetson) |
| `home-assistant` | Legacy LLM Vision HTTP |
| **`comstar-vision`** | **This integration (ADA)** |
