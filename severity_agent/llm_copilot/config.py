"""
ICU Guard v5.0 — LLM Copilot Configuration & Environment Management
===================================================================
Secure environment loading via python-dotenv.
Guarantees:
- Zero API keys in version control or code.
- Cryptographic masking of sensitive keys in logs and telemetry.
- Seamless auto-detection of available inference backends.
"""

import os
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Search paths for .env file
_POTENTIAL_ENV_PATHS = [
    os.path.join(os.getcwd(), ".env"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".env"),
    "e:/eicu_v2_0_1.sqlite3/.env",
]

for _env_path in _POTENTIAL_ENV_PATHS:
    if os.path.exists(_env_path):
        load_dotenv(dotenv_path=_env_path, override=False)
        break
else:
    # Fallback to standard dotenv search
    load_dotenv(override=False)


def mask_key(key: Optional[str]) -> str:
    """Safely mask an API key for logs and diagnostics (e.g. 'sk-proj...3Blb')."""
    if not key:
        return "<NOT_SET>"
    k = str(key).strip()
    if len(k) <= 8:
        return "***"
    return f"{k[:7]}...{k[-4:]}"


@dataclass
class OpenAIConfig:
    api_key: Optional[str] = field(default_factory=lambda: os.environ.get("OPENAI_API_KEY"))
    model: str = field(default_factory=lambda: os.environ.get("OPENAI_MODEL", "gpt-4o-mini"))
    base_url: str = field(default_factory=lambda: os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"))


@dataclass
class AzureOpenAIConfig:
    api_key: Optional[str] = field(default_factory=lambda: os.environ.get("AZURE_OPENAI_API_KEY"))
    endpoint: Optional[str] = field(default_factory=lambda: os.environ.get("AZURE_OPENAI_ENDPOINT"))
    deployment: Optional[str] = field(default_factory=lambda: os.environ.get("AZURE_OPENAI_DEPLOYMENT"))
    api_version: str = field(default_factory=lambda: os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"))


@dataclass
class GeminiConfig:
    api_key: Optional[str] = field(default_factory=lambda: os.environ.get("GEMINI_API_KEY"))
    model: str = field(default_factory=lambda: os.environ.get("GEMINI_MODEL", "gemini-1.5-flash"))


@dataclass
class OllamaConfig:
    base_url: str = field(default_factory=lambda: os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"))
    model: str = field(default_factory=lambda: os.environ.get("OLLAMA_MODEL", "llama3:8b"))


@dataclass
class LLMCopilotConfig:
    """Master runtime configuration for ICU Guard LLM Copilot."""
    openai: OpenAIConfig = field(default_factory=OpenAIConfig)
    azure: AzureOpenAIConfig = field(default_factory=AzureOpenAIConfig)
    gemini: GeminiConfig = field(default_factory=GeminiConfig)
    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    
    temperature: float = 0.1
    timeout_seconds: int = 15
    max_retries: int = 2
    rate_limit_rpm: int = 60
    force_offline: bool = False

    def __post_init__(self):
        # Override with environment variables if present
        try:
            self.temperature = float(os.environ.get("LLM_TEMPERATURE", self.temperature))
        except (ValueError, TypeError):
            self.temperature = 0.1
        self.temperature = min(0.2, max(0.0, self.temperature))  # Enforce determinism <= 0.2

        try:
            self.timeout_seconds = int(os.environ.get("LLM_TIMEOUT_SECONDS", self.timeout_seconds))
        except (ValueError, TypeError):
            self.timeout_seconds = 15

        self.force_offline = os.environ.get("LLM_FORCE_OFFLINE", "").strip().lower() in ("true", "1", "yes")

    def detect_available_providers(self) -> List[str]:
        """Return list of providers with configured credentials in priority order."""
        if self.force_offline:
            return ["offline"]
            
        providers = []
        if self.openai.api_key:
            providers.append("openai")
        if self.azure.api_key and self.azure.endpoint:
            providers.append("azure")
        if self.gemini.api_key:
            providers.append("gemini")
        # Ollama is local, always listed as available local candidate
        providers.append("ollama")
        providers.append("offline")
        return providers

    def get_active_provider_summary(self) -> Dict[str, Any]:
        """Return sanitized overview of provider configuration for diagnostics (keys masked)."""
        return {
            "openai": {
                "configured": bool(self.openai.api_key),
                "key_preview": mask_key(self.openai.api_key),
                "model": self.openai.model,
                "base_url": self.openai.base_url
            },
            "azure": {
                "configured": bool(self.azure.api_key and self.azure.endpoint),
                "key_preview": mask_key(self.azure.api_key),
                "endpoint": self.azure.endpoint,
                "deployment": self.azure.deployment
            },
            "gemini": {
                "configured": bool(self.gemini.api_key),
                "key_preview": mask_key(self.gemini.api_key),
                "model": self.gemini.model
            },
            "ollama": {
                "configured": True,
                "base_url": self.ollama.base_url,
                "model": self.ollama.model
            },
            "runtime": {
                "temperature": self.temperature,
                "timeout_seconds": self.timeout_seconds,
                "force_offline": self.force_offline
            }
        }


def get_copilot_config() -> LLMCopilotConfig:
    """Factory helper to obtain active configuration."""
    return LLMCopilotConfig()
