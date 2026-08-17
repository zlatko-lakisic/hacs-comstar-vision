"""Constants for the Comstar Vision integration."""

DOMAIN = "comstar_vision"

CONF_ENGINE_URL = "engine_url"
CONF_API_TOKEN = "api_token"
CONF_APP_ID = "app_id"
CONF_TTL_SECONDS = "ttl_seconds"
CONF_ENABLED_AGENTS = "enabled_agents"
CONF_ENROLL_TOKEN = "enroll_token"
CONF_DEFAULT_MODEL = "default_model"
CONF_DEFAULT_TARGET_WIDTH = "default_target_width"
CONF_MULTIMODAL_READY = "multimodal_ready"

DEFAULT_APP_ID = "comstar-vision"
DEFAULT_ENGINE_URL = "https://10.0.10.16:8765"
DEFAULT_TTL = 3600
DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_TARGET_WIDTH = 1280
# Flip to True in options after ADA implements docs/AO_REACH_MULTIMODAL_HANDOFF.md
DEFAULT_MULTIMODAL_READY = False

AGENT_VISION_SCENE = "client.vision_scene_analyzer"
DEFAULT_ENABLED_AGENTS = [AGENT_VISION_SCENE]

SERVICE_IMAGE_ANALYZER = "image_analyzer"
SERVICE_PROBE_REACH = "probe_reach"
SERVICE_REFRESH_OVERLAY = "refresh_overlay"
SERVICE_PAIR = "pair"
SERVICE_CLEAR_PAIRING = "clear_pairing"

# Until AO implements Reach multimodal (see docs/AO_REACH_MULTIMODAL_HANDOFF.md),
# image_analyzer refuses to pretend text-only chat can see JPEGs.
MULTIMODAL_REQUIRED_ERROR = (
    "AO Reach multimodal images are required for comstar_vision.image_analyzer. "
    "See docs/AO_REACH_MULTIMODAL_HANDOFF.md — engine must accept chat/direct_agent "
    "payload field images:[{mimeType,dataBase64,name?}]."
)
