# Live cutover checklist

Status after orchestrator-driven config (2026-08-17, v1.2.0):

| Step | Status |
|------|--------|
| `custom_components/comstar_vision` installed on HA via HACS | Done (v1.1.0 → v1.2.0) |
| Zone/gate blueprints call `comstar_vision.image_analyzer` **without** `model` / `vision_model` | Done |
| `02_ai_and_notifications.yaml` has no `vision_model` lines | Done |
| Config entry: agents / MCPs / skills / harness from AO catalog | Configure in options |
| Multimodal ready | Enable after ADA vision model is configured |
| `probe_reach` / smoke `image_analyzer` | After upgrade |

Model selection is the **AO orchestrator's** job. The plugin overlays capability only. ADA needs a vision-capable model (local VLM or valid cloud key); otherwise expect `vision_unavailable`, not OpenAI auth errors.
