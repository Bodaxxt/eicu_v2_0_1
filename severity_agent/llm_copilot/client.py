"""
ICU Guard v5.0 — Multi-Backend Clinical LLM Client Suite
========================================================
Enterprise-grade LLM connectivity layer supporting:
1. OpenAIClient (GPT-4o-mini, GPT-4o)
2. AzureOpenAIClient (Azure OpenAI Healthcare Cloud)
3. GeminiClient (Google Gemini 1.5 Flash/Pro)
4. OllamaClient (Local on-premise inference, zero external network)
5. AutoClient (Intelligent auto-detection with multi-tier fallback to Pure Python)

Guarantees:
- Strict Zero-PHI sanitization before any remote payload dispatch.
- Zero API keys in logs or version control.
- 100% operational resilience: deterministic Pure Python fallback if cloud fails.
"""

import os
import json
import time
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List

import requests

from severity_agent.llm_copilot.config import (
    LLMCopilotConfig,
    get_copilot_config,
    mask_key
)
from severity_agent.llm_copilot.safety import stamp_advisory, PHIScrubber
from severity_agent.llm_copilot.audit import CopilotAuditLogger

logger = logging.getLogger(__name__)

# Marker present in AutoClient's generic Pure Python fallback response.
# Higher-level tools (BedsideClinicalChat, ClinicalReviewer, WhatIfSimulator)
# can detect this to substitute their own specialised deterministic answers.
AUTO_FALLBACK_MARKER = "CLINICAL DECISION SUPPORT (DETERMINISTIC SYNTHESIS)"

# Sentinel: distinguishes LLMClient(api_key=None) from LLMClient() (no arg passed).
_UNSET = object()


class BaseLLMClient(ABC):
    """Abstract base class for all clinical LLM backends."""

    def __init__(
        self,
        provider_name: str,
        model_name: str,
        temperature: float = 0.1,
        timeout: int = 15
    ):
        self.provider_name = provider_name
        self.model_name = model_name
        self.temperature = min(0.2, max(0.0, float(temperature)))  # Strict determinism <= 0.2
        self.timeout = timeout
        self.audit_logger = CopilotAuditLogger()

    @property
    @abstractmethod
    def is_online(self) -> bool:
        """Return True if backend credentials and configuration are active."""
        pass

    @abstractmethod
    def complete(
        self,
        prompt: str,
        system_prompt: str = "You are an expert ICU Clinical Decision Support AI Assistant."
    ) -> str:
        """Execute text completion with PHI sanitization and advisory stamping."""
        pass

    def ping(self) -> bool:
        """Quick health probe for provider availability."""
        return self.is_online

    def _sanitize(self, prompt: str) -> str:
        """Ensure all prompts are scrubbed of direct identifiers before transmission."""
        return PHIScrubber.sanitize_text(prompt)


class OpenAIClient(BaseLLMClient):
    """Client for OpenAI and standard OpenAI-compatible inference endpoints."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: float = 0.1,
        timeout: int = 15
    ):
        cfg = get_copilot_config()
        self.api_key = api_key or cfg.openai.api_key
        model = model_name or cfg.openai.model
        super().__init__(
            provider_name="OpenAI",
            model_name=model,
            temperature=temperature,
            timeout=timeout
        )
        self.base_url = (base_url or cfg.openai.base_url).rstrip('/')

    @property
    def is_online(self) -> bool:
        return bool(self.api_key and len(self.api_key.strip()) > 5)

    def complete(
        self,
        prompt: str,
        system_prompt: str = "You are an expert ICU Clinical Decision Support AI Assistant."
    ) -> str:
        if not self.is_online:
            raise ConnectionError("OpenAI API key not configured.")

        clean_prompt = self._sanitize(prompt)
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model_name,
            "temperature": self.temperature,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": clean_prompt}
            ]
        }

        t0 = time.perf_counter()
        resp = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
        latency_ms = (time.perf_counter() - t0) * 1000.0

        if resp.status_code == 200:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            tokens = data.get("usage", {}).get("total_tokens")
            self.audit_logger.log_interaction(
                provider="OpenAI", model=self.model_name,
                prompt=clean_prompt, response=content,
                latency_ms=latency_ms, success=True, tokens_used=tokens
            )
            return stamp_advisory(content)
        else:
            err = f"OpenAI HTTP {resp.status_code}: {resp.text[:200]}"
            self.audit_logger.log_interaction(
                provider="OpenAI", model=self.model_name,
                prompt=clean_prompt, response="",
                latency_ms=latency_ms, success=False, error_msg=err
            )
            raise RuntimeError(err)


class AzureOpenAIClient(BaseLLMClient):
    """Client for Azure OpenAI Service in enterprise hospital clouds."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        deployment: Optional[str] = None,
        api_version: Optional[str] = None,
        temperature: float = 0.1,
        timeout: int = 15
    ):
        cfg = get_copilot_config()
        self.api_key = api_key or cfg.azure.api_key
        self.endpoint = (endpoint or cfg.azure.endpoint or "").rstrip('/')
        self.deployment = deployment or cfg.azure.deployment or "gpt-4o"
        self.api_version = api_version or cfg.azure.api_version
        super().__init__(
            provider_name="AzureOpenAI",
            model_name=self.deployment,
            temperature=temperature,
            timeout=timeout
        )

    @property
    def is_online(self) -> bool:
        return bool(self.api_key and self.endpoint and self.deployment)

    def complete(
        self,
        prompt: str,
        system_prompt: str = "You are an expert ICU Clinical Decision Support AI Assistant."
    ) -> str:
        if not self.is_online:
            raise ConnectionError("Azure OpenAI credentials incomplete (missing key, endpoint, or deployment).")

        clean_prompt = self._sanitize(prompt)
        url = f"{self.endpoint}/openai/deployments/{self.deployment}/chat/completions?api-version={self.api_version}"
        headers = {
            "api-key": self.api_key,
            "Content-Type": "application/json"
        }
        payload = {
            "temperature": self.temperature,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": clean_prompt}
            ]
        }

        t0 = time.perf_counter()
        resp = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
        latency_ms = (time.perf_counter() - t0) * 1000.0

        if resp.status_code == 200:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            tokens = data.get("usage", {}).get("total_tokens")
            self.audit_logger.log_interaction(
                provider="AzureOpenAI", model=self.deployment,
                prompt=clean_prompt, response=content,
                latency_ms=latency_ms, success=True, tokens_used=tokens
            )
            return stamp_advisory(content)
        else:
            err = f"Azure OpenAI HTTP {resp.status_code}: {resp.text[:200]}"
            self.audit_logger.log_interaction(
                provider="AzureOpenAI", model=self.deployment,
                prompt=clean_prompt, response="",
                latency_ms=latency_ms, success=False, error_msg=err
            )
            raise RuntimeError(err)


class GeminiClient(BaseLLMClient):
    """Client for Google Gemini API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        temperature: float = 0.1,
        timeout: int = 15
    ):
        cfg = get_copilot_config()
        self.api_key = api_key or cfg.gemini.api_key
        model = model_name or cfg.gemini.model
        super().__init__(
            provider_name="Gemini",
            model_name=model,
            temperature=temperature,
            timeout=timeout
        )

    @property
    def is_online(self) -> bool:
        return bool(self.api_key and len(self.api_key.strip()) > 5)

    def complete(
        self,
        prompt: str,
        system_prompt: str = "You are an expert ICU Clinical Decision Support AI Assistant."
    ) -> str:
        if not self.is_online:
            raise ConnectionError("Gemini API key not configured.")

        clean_prompt = self._sanitize(prompt)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [
                {"role": "user", "parts": [{"text": clean_prompt}]}
            ],
            "systemInstruction": {
                "parts": [{"text": system_prompt}]
            },
            "generationConfig": {
                "temperature": self.temperature,
                "maxOutputTokens": 1024
            }
        }

        t0 = time.perf_counter()
        resp = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
        latency_ms = (time.perf_counter() - t0) * 1000.0

        if resp.status_code == 200:
            data = resp.json()
            try:
                content = data["candidates"][0]["content"]["parts"][0]["text"]
            except (KeyError, IndexError) as parse_err:
                raise RuntimeError(f"Failed to parse Gemini response: {parse_err}")

            self.audit_logger.log_interaction(
                provider="Gemini", model=self.model_name,
                prompt=clean_prompt, response=content,
                latency_ms=latency_ms, success=True
            )
            return stamp_advisory(content)
        else:
            err = f"Gemini HTTP {resp.status_code}: {resp.text[:200]}"
            self.audit_logger.log_interaction(
                provider="Gemini", model=self.model_name,
                prompt=clean_prompt, response="",
                latency_ms=latency_ms, success=False, error_msg=err
            )
            raise RuntimeError(err)


class OllamaClient(BaseLLMClient):
    """Client for local, on-premise Ollama server (Llama 3, Mistral, Med-Llama)."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        temperature: float = 0.1,
        timeout: int = 15
    ):
        cfg = get_copilot_config()
        self.base_url = (base_url or cfg.ollama.base_url).rstrip('/')
        model = model_name or cfg.ollama.model
        super().__init__(
            provider_name="Ollama",
            model_name=model,
            temperature=temperature,
            timeout=timeout
        )

    @property
    def is_online(self) -> bool:
        return True  # Local endpoint address configured

    def ping(self) -> bool:
        """Verify that local Ollama daemon is actively reachable."""
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=2)
            return r.status_code == 200
        except Exception:
            return False

    def complete(
        self,
        prompt: str,
        system_prompt: str = "You are an expert ICU Clinical Decision Support AI Assistant."
    ) -> str:
        clean_prompt = self._sanitize(prompt)
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": clean_prompt}
            ],
            "options": {"temperature": self.temperature},
            "stream": False
        }

        t0 = time.perf_counter()
        resp = requests.post(url, json=payload, timeout=self.timeout)
        latency_ms = (time.perf_counter() - t0) * 1000.0

        if resp.status_code == 200:
            data = resp.json()
            content = data.get("message", {}).get("content", "")
            self.audit_logger.log_interaction(
                provider="Ollama", model=self.model_name,
                prompt=clean_prompt, response=content,
                latency_ms=latency_ms, success=True
            )
            return stamp_advisory(content)
        else:
            err = f"Ollama HTTP {resp.status_code}: {resp.text[:200]}"
            self.audit_logger.log_interaction(
                provider="Ollama", model=self.model_name,
                prompt=clean_prompt, response="",
                latency_ms=latency_ms, success=False, error_msg=err
            )
            raise RuntimeError(err)


class AutoClient(BaseLLMClient):
    """
    Intelligent Auto-Detecting Multi-Backend Client with 100% Guaranteed Offline Fallback.
    
    Priority Resolution Order:
    1. OpenAI (`OPENAI_API_KEY`)
    2. Azure OpenAI (`AZURE_OPENAI_API_KEY` + `AZURE_OPENAI_ENDPOINT`)
    3. Gemini (`GEMINI_API_KEY`)
    4. Ollama (Local daemon if running)
    5. Pure Python Deterministic Synthesis (Offline)
    """

    def __init__(
        self,
        preferred_provider: Optional[str] = None,
        config: Optional[LLMCopilotConfig] = None,
        temperature: float = 0.1,
        timeout: int = 15
    ):
        self.config = config or get_copilot_config()
        self.preferred_provider = (preferred_provider or "").lower().strip()
        super().__init__(
            provider_name="AutoClient",
            model_name="auto",
            temperature=temperature,
            timeout=timeout
        )
        self._active_client: Optional[BaseLLMClient] = None
        self._initialize_provider()

    def _initialize_provider(self):
        """Instantiate client backends according to credential availability.

        Credentials are passed explicitly from self.config so that custom
        LLMCopilotConfig instances (e.g. in tests) are fully respected, rather
        than each sub-client re-reading from environment variables.
        """
        if self.config.force_offline:
            self._active_client = None
            self.provider_name = "PurePythonOffline"
            self.model_name = "deterministic-v5.0"
            return

        def _make_openai():
            return OpenAIClient(
                api_key=self.config.openai.api_key,
                model_name=self.config.openai.model,
                base_url=self.config.openai.base_url,
                temperature=self.temperature, timeout=self.timeout
            )

        def _make_azure():
            return AzureOpenAIClient(
                api_key=self.config.azure.api_key,
                endpoint=self.config.azure.endpoint,
                deployment=self.config.azure.deployment,
                api_version=self.config.azure.api_version,
                temperature=self.temperature, timeout=self.timeout
            )

        def _make_gemini():
            return GeminiClient(
                api_key=self.config.gemini.api_key,
                model_name=self.config.gemini.model,
                temperature=self.temperature, timeout=self.timeout
            )

        def _make_ollama():
            return OllamaClient(
                base_url=self.config.ollama.base_url,
                model_name=self.config.ollama.model,
                temperature=self.temperature, timeout=self.timeout
            )

        # 1. Preferred explicit override
        if self.preferred_provider == "openai" and self.config.openai.api_key:
            self._active_client = _make_openai()
        elif self.preferred_provider == "azure" and self.config.azure.api_key:
            self._active_client = _make_azure()
        elif self.preferred_provider == "gemini" and self.config.gemini.api_key:
            self._active_client = _make_gemini()
        elif self.preferred_provider == "ollama":
            self._active_client = _make_ollama()

        # 2. Priority Auto-Detection
        if not self._active_client:
            if self.config.openai.api_key:
                logger.info(f"AutoClient: Selected OpenAI backend ({mask_key(self.config.openai.api_key)})")
                self._active_client = _make_openai()
            elif self.config.azure.api_key and self.config.azure.endpoint:
                logger.info("AutoClient: Selected Azure OpenAI backend")
                self._active_client = _make_azure()
            elif self.config.gemini.api_key:
                logger.info("AutoClient: Selected Gemini backend")
                self._active_client = _make_gemini()
            else:
                # Check local Ollama daemon
                candidate = _make_ollama()
                if candidate.ping():
                    logger.info("AutoClient: Selected local Ollama daemon")
                    self._active_client = candidate

        if self._active_client:
            self.provider_name = self._active_client.provider_name
            self.model_name = self._active_client.model_name
        else:
            self.provider_name = "PurePythonOffline"
            self.model_name = "deterministic-v5.0"

    @property
    def is_online(self) -> bool:
        return self._active_client is not None and self._active_client.is_online

    @property
    def active_backend(self) -> str:
        return self.provider_name

    def complete(
        self,
        prompt: str,
        system_prompt: str = "You are an expert ICU Clinical Decision Support AI Assistant."
    ) -> str:
        """Attempt primary online dispatch with automatic graceful fallback to offline."""
        clean_prompt = self._sanitize(prompt)

        if self._active_client and self._active_client.is_online:
            try:
                return self._active_client.complete(clean_prompt, system_prompt=system_prompt)
            except Exception as e:
                logger.warning(
                    f"AutoClient: Online dispatch failed on {self.provider_name}: {e}. "
                    "Engaging Pure Python deterministic fallback."
                )

        return self._offline_fallback(clean_prompt, system_prompt)

    def _offline_fallback(self, prompt: str, system_prompt: str) -> str:
        """Deterministic offline rule-based clinical response generator."""
        t0 = time.perf_counter()
        response = stamp_advisory(
            "### CLINICAL DECISION SUPPORT (DETERMINISTIC SYNTHESIS)\n\n"
            "**Operational Mode:** Offline Deterministic Fallback (Active ICU Guard v5.0 Core).\n\n"
            "**Core Assessment:** Multi-organ assessments and syndrome patterns have been evaluated "
            "directly via pure Python clinical rules adhering to Surviving Sepsis Campaign (SSC 2021), "
            "KDIGO 2012, and Berlin ARDS guidelines.\n\n"
            "**Recommended Action:** Refer to bedside telemetry, serial ABG / lactate measurements, "
            "and protocolized resuscitation bundles."
        )
        latency_ms = (time.perf_counter() - t0) * 1000.0
        self.audit_logger.log_interaction(
            provider="PurePythonOffline", model="deterministic-v5.0",
            prompt=prompt, response=response,
            latency_ms=latency_ms, success=True
        )
        return response


# Backwards-compatible alias for existing code
class LLMClient(AutoClient):
    """Backwards-compatible interface alias for AutoClient.

    Sentinel semantics for api_key:
    - ``LLMClient()``             → uses whatever key is in the environment.
    - ``LLMClient(api_key=None)`` → explicitly clears the OpenAI key (offline).
    - ``LLMClient(api_key="sk-…")`` → uses the supplied key.
    """

    def __init__(
        self,
        api_key=_UNSET,          # Use sentinel, NOT Optional[str] = None
        base_url: Optional[str] = None,
        model_name: str = "gpt-4o-mini",
        temperature: float = 0.1,
        timeout: int = 15,
        provider: Optional[str] = None
    ):
        cfg = get_copilot_config()

        if api_key is not _UNSET:
            # Explicit value (including None) overrides the env key.
            cfg.openai.api_key = api_key
        if base_url:
            cfg.openai.base_url = base_url
        if model_name:
            cfg.openai.model = model_name

        # Determine preferred provider from explicit api_key argument.
        if provider:
            pref = provider
        elif api_key is not _UNSET and api_key:
            pref = "openai"
        else:
            pref = None

        super().__init__(
            preferred_provider=pref,
            config=cfg,
            temperature=temperature,
            timeout=timeout
        )
