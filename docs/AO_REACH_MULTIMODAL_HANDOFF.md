# AO Reach multimodal handoff — Comstar Vision

**Consumer:** Home Assistant HACS integration [`hacs-comstar-vision`](https://github.com/zlatko-lakisic/hacs-comstar-vision) (`comstar_vision`)  
**Engine:** ADA AO at `10.0.10.16` — Reach WSS `https://10.0.10.16:8765/ws`  
**appId:** `comstar-vision` (do **not** reuse `comstar-ha`, `agentic-watering`, or `home-assistant`)  
**Status:** Client already sends `images` on `chat` / `direct_agent`. Engine must accept and route them to a vision model before HA enables **Multimodal ready**.

This document is the only AO / AO Reach work scope for the motion-AI cutover. No AO repo edits land in the Comstar Vision workstream.

---

## 1. Problem

Gate and zone motion blueprints capture 4–15 ordered JPEG stills under `/config/www/tmp/…` and need a short classification reply.

Today’s Reach chat payload is **text-only**:

```json
{
  "type": "chat",
  "text": "…",
  "questionId": "comstar-vision-…",
  "runMode": "dynamic",
  "appId": "comstar-vision",
  "selectedAgentProviderIds": ["client.vision_scene_analyzer"]
}
```

(`SessionBridge.chat` in Agentic Watering / Comstar Vision vendored `ao_reach`.)

Without image parts, the model cannot see the stills. Pasting base64 into `text` is **out of scope** — Comstar Vision refuses that path.

---

## 2. Target consumer behaviour

| Item | Value |
|------|--------|
| HA service | `comstar_vision.image_analyzer` |
| Overlay agent | `client.vision_scene_analyzer` |
| Skill | `vision_plain_reply` (no tools / no MCP JSON) |
| Reply contract | Plain text; blueprints parse `response_text` as 3 lines (label / home log / phone) |
| Auth | Bearer `ao_…` + mTLS enrollment (same as watering) |

HA loads/resizes JPEGs (default long edge 1280) and builds Reach `images` parts.

---

## 3. Proposed protocol (backward compatible)

Extend **`type: chat`** and **`type: direct_agent`** with an optional field:

```json
{
  "type": "chat",
  "text": "[model=gpt-4o-mini]\nSecurity camera stills…",
  "questionId": "comstar-vision-1713…",
  "runMode": "dynamic",
  "appId": "comstar-vision",
  "selectedAgentProviderIds": ["client.vision_scene_analyzer"],
  "images": [
    {
      "mimeType": "image/jpeg",
      "dataBase64": "<standard base64>",
      "name": "near_driveway_1.jpg"
    },
    {
      "mimeType": "image/jpeg",
      "dataBase64": "<…>",
      "name": "near_driveway_2.jpg"
    }
  ]
}
```

### Rules

1. **Omit `images` or empty array** → existing text-only behaviour (watering / Comstar Assist unchanged).
2. **Non-empty `images`** → multimodal turn: engine must feed ordered image parts + `text` to a **vision-capable** model.
3. Preserve existing reply streaming (`chunk` / `run_end` / `text`) so the client keeps using `result["text"]`.
4. Optional OpenAI-style content parts internally is fine; the **wire** shape above is what HA sends.
5. Reject / error clearly if a multimodal turn would otherwise fall back to a **text-only** Ollama model (do not silently ignore images).

### Limits (suggested)

| Limit | Suggestion |
|-------|------------|
| Max images | 16 |
| Max decoded bytes / image | 4 MiB |
| Max total payload | ~20 MiB |
| Timeout | ≥ 120s for vision runs |

---

## 4. Engine routing on ADA

- Multimodal runs must hit a vision model (cloud OpenAI-compatible VLM **or** a local VLM such as `qwen2.5-vl`). Do **not** route image turns to text-only `qwen2.5:14b-instruct`.
- Prefer plain-text final answers. Overlay skill forbids tool/MCP JSON — blueprints treat tool echoes as unusable.
- `AGENTIC_CHAT_COMPLETIONS_BACKEND=auto` text fallback must **not** apply when `images` is present.
- Optional: honor `[model=…]` prefix on `text` as a soft model hint from HA.

---

## 5. Ops on ADA (`10.0.10.16`)

1. Ensure engine flags: `AGENTIC_SERVE_SESSION_OVERLAY=1` (MCP tunnel not required for this consumer).
2. Mint **API token** — External client, `appId: comstar-vision`.
3. Mint **mTLS enrollment token** — CN/appId `comstar-vision`.
4. Confirm `GET https://10.0.10.16:8765/health` and that `/ws` requires mTLS like Jetson watering.
5. Deploy protocol support; smoke with the acceptance tests below.
6. Tell HA operators to enable **Multimodal ready** in Comstar Vision options.

---

## 6. Acceptance tests

### A. Engine WS (preferred)

1. Pair a test client with `comstar-vision` mTLS + Bearer.
2. Register session overlay (agent `client.vision_scene_analyzer` may be supplied by the HA overlay pack).
3. Send `chat` with **two** small JPEGs (person then empty, or car then driveway) and a prompt that demands:

```text
Line 1: one word only — PERSON or CAR or DOG or OTHER or CLEAR
Line 2: ≤160 char home log
Line 3: ≤100 char phone line
```

4. Expect first line ∈ `{PERSON,CAR,DOG,OTHER,CLEAR}` and no tool JSON.

### B. Negative

- `chat` **without** `images` still works for text-only agents.
- `chat` **with** `images` but only text-only models configured → explicit error (not a hallucinated PERSON).

### C. Home Assistant

After Multimodal ready is on:

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

Expect `response_text` non-empty and `error` empty.

---

## 7. Non-goals

- Do **not** reuse Assist MCP `vision_comstar` (CodeProject.AI live feed) for this path.
- Do **not** require OpenAI cloud if ADA exposes a local VLM that meets quality for gate/plate-adjacent describes.
- Do **not** change Agentic Watering or Comstar Assist appIds.
- Do **not** implement LLM Vision timeline/memory.

---

## 8. Client already shipped

Comstar Vision vendored `ao_reach.session_bridge.chat(..., images=…)` and `direct_agent(..., images=…)` attach the `images` field when non-empty. HA `image_analyzer` stays fail-closed (`multimodal_ready: false` by default) until this handoff is done on ADA.
