"""
ICU Guard v5.0 — LLM Copilot Advisory Package
=============================================
Provides adjunctive clinical decision support, peer review, shift handoff, and simulation:
- config: Secure environment variable management via python-dotenv and key masking.
- safety: PHI scrubbing, prompt injection defense, and non-autonomous watermarking.
- client: Multi-backend LLM client suite (OpenAI, Azure, Gemini, Ollama, AutoClient) with Pure Python fallback.
- audit: Secure logging without exposing API keys or PHI.
- reviewer: Second-opinion clinical review and blind-spot detection.
- chat: Bedside conversational interface with multi-turn support.
- sbar: Standardized clinical shift handoff generator.
- what_if: Counterfactual intervention simulator.
"""

from severity_agent.llm_copilot.config import (
    LLMCopilotConfig,
    OpenAIConfig,
    AzureOpenAIConfig,
    GeminiConfig,
    OllamaConfig,
    get_copilot_config,
    mask_key
)
from severity_agent.llm_copilot.safety import (
    PHIScrubber,
    stamp_advisory,
    ADVISORY_WATERMARK
)
from severity_agent.llm_copilot.audit import CopilotAuditLogger
from severity_agent.llm_copilot.client import (
    BaseLLMClient,
    OpenAIClient,
    AzureOpenAIClient,
    GeminiClient,
    OllamaClient,
    AutoClient,
    LLMClient,
    AUTO_FALLBACK_MARKER
)
from severity_agent.llm_copilot.reviewer import ClinicalReviewer
from severity_agent.llm_copilot.chat import BedsideClinicalChat
from severity_agent.llm_copilot.sbar import SBARGenerator
from severity_agent.llm_copilot.what_if import WhatIfSimulator

__all__ = [
    # Config
    "LLMCopilotConfig",
    "OpenAIConfig",
    "AzureOpenAIConfig",
    "GeminiConfig",
    "OllamaConfig",
    "get_copilot_config",
    "mask_key",
    # Safety & Audit
    "PHIScrubber",
    "stamp_advisory",
    "ADVISORY_WATERMARK",
    "CopilotAuditLogger",
    # Clients
    "BaseLLMClient",
    "OpenAIClient",
    "AzureOpenAIClient",
    "GeminiClient",
    "OllamaClient",
    "AutoClient",
    "LLMClient",
    "AUTO_FALLBACK_MARKER",
    # Clinical Tools
    "ClinicalReviewer",
    "BedsideClinicalChat",
    "SBARGenerator",
    "WhatIfSimulator",
]
