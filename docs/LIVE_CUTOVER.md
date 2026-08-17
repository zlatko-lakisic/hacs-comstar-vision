# Live cutover checklist

Status after initial implement (2026-08-17):

| Step | Status |
|------|--------|
| `custom_components/comstar_vision` installed on HA (`ha-live`) | Done |
| Zone/gate blueprints call `comstar_vision.image_analyzer` | Done |
| `02_ai_and_notifications.yaml` uses `vision_model` (no llmvision provider) | Done |
| HA config check | Valid |
| Automations reloaded / Core restarted | Done |
| Config entry (UI) + mint `comstar-vision` API + enroll tokens | **You** — Settings → Devices & services → Add **Comstar Vision** |
| `comstar_vision.pair` / `probe_reach` | After tokens |
| Enable **Multimodal ready** | After [AO_REACH_MULTIMODAL_HANDOFF.md](AO_REACH_MULTIMODAL_HANDOFF.md) on ADA |
| Smoke `image_analyzer` with two tmp JPEGs | After multimodal ready |

Until Multimodal ready is on, motion automations still capture GIFs and fall back (vision returns a clear error; blueprints `continue_on_error`).
