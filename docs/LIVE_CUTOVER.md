# Live cutover checklist

Status after orchestrator-driven config (2026-08-17, v1.2.1):

| Step | Status |
|------|--------|
| `custom_components/comstar_vision` installed on HA via HACS | Done (v1.2.0 + v1.2.1 hotfix) |
| Zone/gate blueprints call `comstar_vision.image_analyzer` **without** `model` / `vision_model` | Done |
| `02_ai_and_notifications.yaml` has no `vision_model` lines | Done |
| Config entry: agents / MCPs / skills / harness from AO catalog | Configure in options |
| Multimodal ready | Enable when ADA vision model is healthy |
| `probe_reach` | Verified: paired + overlay ACTIVE |
| Smoke `image_analyzer` | Images reach AO (`imgs=2`); model selection is ADA's job |

Model selection is the **AO orchestrator's** job. The plugin overlays capability only. If ADA's vision route still points at OpenAI with a bad key, you will see litellm auth errors until a local VLM (or valid cloud key) is configured on ADA — not a plugin model pin.
