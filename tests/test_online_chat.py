"""
Unit & Integration Tests for Online AI Chat, Multi-Backend Clients, and Secure Key Management
=============================================================================================
Verifies:
1. Environment variable loading & API key masking (zero key leakage).
2. AutoClient provider priority selection and auto-detection.
3. Provider clients (OpenAI, Azure, Gemini, Ollama) with mocked HTTP responses.
4. Automatic graceful fallback to Pure Python deterministic mode on network/API failure.
5. PHI de-identification before remote dispatch.
6. Advisory watermarks on all copilot outputs.
7. Interaction audit logging without sensitive credentials.
"""

import os
import json
import pytest
from unittest.mock import patch, MagicMock

from severity_agent.llm_copilot.config import (
    LLMCopilotConfig,
    OpenAIConfig,
    AzureOpenAIConfig,
    GeminiConfig,
    OllamaConfig,
    mask_key,
    get_copilot_config
)
from severity_agent.llm_copilot.client import (
    OpenAIClient,
    AzureOpenAIClient,
    GeminiClient,
    OllamaClient,
    AutoClient,
    LLMClient
)
from severity_agent.llm_copilot.chat import BedsideClinicalChat
from severity_agent.llm_copilot.safety import PHIScrubber, ADVISORY_WATERMARK
from severity_agent.llm_copilot.audit import CopilotAuditLogger


# 1. Configuration & Key Masking Tests
def test_key_masking_security():
    assert mask_key(None) == "<NOT_SET>"
    assert mask_key("") == "<NOT_SET>"
    assert mask_key("short") == "***"
    masked = mask_key("sk-proj-1234567890abcdefghijklmnopqrstuvwxyz")
    assert masked.startswith("sk-proj")
    assert masked.endswith("wxyz")
    assert "..." in masked
    assert "1234567890" not in masked


def test_config_loading_and_priority():
    cfg = LLMCopilotConfig()
    assert 0.0 <= cfg.temperature <= 0.2
    assert cfg.timeout_seconds > 0
    summary = cfg.get_active_provider_summary()
    assert "openai" in summary
    assert "azure" in summary
    assert "gemini" in summary
    assert "ollama" in summary


# 2. AutoClient Selection Logic
def test_autoclient_selects_openai_when_key_present():
    custom_cfg = LLMCopilotConfig()
    custom_cfg.openai.api_key = "sk-test-mock-key-123456789"
    client = AutoClient(config=custom_cfg)
    assert client.active_backend == "OpenAI"
    assert client.is_online


def test_autoclient_selects_azure_when_openai_missing():
    custom_cfg = LLMCopilotConfig()
    custom_cfg.openai.api_key = None
    custom_cfg.azure.api_key = "azure-test-key-12345"
    custom_cfg.azure.endpoint = "https://hospital-azure.openai.azure.com"
    client = AutoClient(config=custom_cfg)
    assert client.active_backend == "AzureOpenAI"
    assert client.is_online


def test_autoclient_selects_gemini_when_openai_and_azure_missing():
    custom_cfg = LLMCopilotConfig()
    custom_cfg.openai.api_key = None
    custom_cfg.azure.api_key = None
    custom_cfg.gemini.api_key = "gemini-test-key-12345"
    client = AutoClient(config=custom_cfg)
    assert client.active_backend == "Gemini"
    assert client.is_online


def test_autoclient_selects_pure_python_when_all_missing():
    custom_cfg = LLMCopilotConfig()
    custom_cfg.openai.api_key = None
    custom_cfg.azure.api_key = None
    custom_cfg.gemini.api_key = None
    custom_cfg.force_offline = True
    client = AutoClient(config=custom_cfg)
    assert client.active_backend == "PurePythonOffline"
    assert not client.is_online


# 3. Provider Client Execution with Mocked Responses
def test_openai_client_success():
    client = OpenAIClient(api_key="sk-mock-key-123456789")
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Norepinephrine titration indicated."}}],
        "usage": {"total_tokens": 42}
    }

    with patch("requests.post", return_value=mock_response):
        out = client.complete("Patient in septic shock, MAP 52")
        assert "Norepinephrine titration indicated." in out
        assert ADVISORY_WATERMARK.strip() in out


def test_azure_openai_client_success():
    client = AzureOpenAIClient(
        api_key="mock-azure-key",
        endpoint="https://hospital.openai.azure.com",
        deployment="gpt-4o"
    )
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Initiate lung-protective mechanical ventilation."}}],
        "usage": {"total_tokens": 55}
    }

    with patch("requests.post", return_value=mock_response):
        out = client.complete("Severe ARDS PaO2 55")
        assert "Initiate lung-protective mechanical ventilation." in out
        assert ADVISORY_WATERMARK.strip() in out


def test_gemini_client_success():
    client = GeminiClient(api_key="mock-gemini-key")
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "candidates": [{
            "content": {"parts": [{"text": "Administer 30 mL/kg balanced crystalloids within 3 hours."}]}
        }]
    }

    with patch("requests.post", return_value=mock_response):
        out = client.complete("Severe sepsis dysoxia lactate 4.5")
        assert "crystalloids" in out
        assert ADVISORY_WATERMARK.strip() in out


def test_ollama_client_success():
    client = OllamaClient(base_url="http://localhost:11434", model_name="llama3:8b")
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "message": {"content": "KDIGO Stage 2 AKI requires fluid optimization and nephrotoxic drug hold."}
    }

    with patch("requests.post", return_value=mock_response):
        out = client.complete("Patient creatinine 2.4 BUN 45")
        assert "KDIGO Stage 2" in out
        assert ADVISORY_WATERMARK.strip() in out


# 4. Graceful Fallback on Network / Server Error
def test_autoclient_graceful_fallback_on_network_error():
    custom_cfg = LLMCopilotConfig()
    custom_cfg.openai.api_key = "sk-mock-key-123456789"
    client = AutoClient(config=custom_cfg)

    # Simulate network failure (e.g. DNS failure or connection reset)
    with patch("requests.post", side_effect=ConnectionError("Cloud host unreachable")):
        response = client.complete("Evaluate patient with acute deterioration")
        assert "CLINICAL DECISION SUPPORT (DETERMINISTIC SYNTHESIS)" in response
        assert "Surviving Sepsis Campaign" in response
        assert ADVISORY_WATERMARK.strip() in response


def test_autoclient_graceful_fallback_on_http_500():
    custom_cfg = LLMCopilotConfig()
    custom_cfg.openai.api_key = "sk-mock-key-123456789"
    client = AutoClient(config=custom_cfg)

    mock_err_response = MagicMock()
    mock_err_response.status_code = 500
    mock_err_response.text = "Internal Server Error"

    with patch("requests.post", return_value=mock_err_response):
        response = client.complete("Evaluate patient with refractory shock")
        assert "CLINICAL DECISION SUPPORT (DETERMINISTIC SYNTHESIS)" in response
        assert ADVISORY_WATERMARK.strip() in response


# 5. PHI Scrubbing Integration
def test_phi_scrubbing_before_remote_call():
    vitals_with_phi = {
        "patientunitstayid": 123456,
        "patient_id": "MRN-998877",
        "uniquepid": "002-PT-88",
        "heartrate_mean": 115.0,
        "meanbp_min": 55.0,
        "lactate_max": 4.2
    }
    clean = PHIScrubber.sanitize_features(vitals_with_phi)
    assert "patientunitstayid" not in clean
    assert "patient_id" not in clean
    assert "uniquepid" not in clean
    assert clean["heartrate_mean"] == 115.0
    assert clean["meanbp_min"] == 55.0


# 6. Bedside Clinical Chat with AutoClient and Multi-Turn Memory
def test_bedside_chat_interactive():
    chat = BedsideClinicalChat(client=AutoClient())
    summary = {
        "severity_tier": "CRITICAL",
        "primary_etiology": "Septic Shock",
        "trajectory": "RAPID_DETERIORATION",
        "active_red_flags": ["Lactate > 4.0 mmol/L"]
    }
    vitals = {"heartrate_mean": 120.0, "meanbp_min": 52.0, "lactate_max": 5.4}

    # Query 1: Fluid resuscitation question
    ans1 = chat.ask("What is the fluid resuscitation protocol for this patient?", summary, vitals)
    assert "Surviving Sepsis" in ans1 or "crystalloids" in ans1
    assert len(chat.history) == 2

    # Query 2: Vasopressor question
    ans2 = chat.ask("Which vasopressor should we titrate first?", summary, vitals)
    assert "Norepinephrine" in ans2
    assert len(chat.history) == 4

    # Reset session
    chat.reset_session()
    assert len(chat.history) == 0


# 7. Audit Logging Without Secrets
def test_audit_logger_records_safely(tmp_path):
    log_file = tmp_path / "test_copilot_audit.jsonl"
    audit = CopilotAuditLogger(log_path=str(log_file))
    
    rec = audit.log_interaction(
        provider="OpenAI",
        model="gpt-4o-mini",
        prompt="Assessment for patient in shock",
        response="Titrate norepinephrine to MAP >= 65",
        latency_ms=125.4,
        success=True
    )
    assert rec["provider"] == "OpenAI"
    assert rec["latency_ms"] == 125.4
    assert os.path.exists(log_file)

    with open(log_file, "r", encoding="utf-8") as f:
        line = f.readline()
        data = json.loads(line)
        assert data["provider"] == "OpenAI"
        assert "sk-" not in line  # Guarantee zero API keys in audit file
