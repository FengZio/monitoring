from routes.config_route import ConfigPayload
from database import Alert


def test_config_payload_exposes_vllm_defaults():
    payload = ConfigPayload()

    assert payload.vllm_enabled is False
    assert payload.vllm_model == "GLM-4V-Flash"
    assert payload.vllm_timeout_seconds == 30


def test_alert_model_has_structured_vllm_result_fields():
    assert hasattr(Alert, "vllm_risk_level")
    assert hasattr(Alert, "vllm_is_destructive")
