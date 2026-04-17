"""
core/response_generator.py — NVIDIA LLM API wrapper (google/gemma-3-27b-it).

Responsibilities:
  • POST to NVIDIA /v1/chat/completions (non-streaming)
  • Handle timeouts, retries, and error cases
  • Return structured (response_text, latency_ms)
"""
from __future__ import annotations

import time

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from backend.config import get_settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)

NVIDIA_API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"


class NvidiaError(Exception):
    """Raised when the NVIDIA LLM API returns an error or is unreachable."""


class ResponseGenerator:
    """
    Wraps the NVIDIA LLM REST API for chat completions.

    Usage:
        generator = ResponseGenerator()
        text, latency = generator.generate(prompt)
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._model = self._settings.nvidia_model
        self._api_key = self._settings.nvidia_api_key
        self._max_tokens = self._settings.nvidia_max_tokens
        self._temperature = self._settings.nvidia_temperature
        self._timeout = self._settings.nvidia_timeout

    # ─────────────────────────────────────────
    #  Public API
    # ─────────────────────────────────────────

    def generate(self, prompt: str) -> tuple[str, float]:
        """
        Send a prompt to NVIDIA LLM and return (response_text, latency_ms).

        Raises:
            NvidiaError: On connection failure or API error.
        """
        start = time.perf_counter()
        payload = self._build_payload(prompt)

        logger.debug(
            "Sending request to NVIDIA model='{}' prompt_chars={}",
            self._model,
            len(prompt),
        )

        response_text = self._call_nvidia(payload)
        latency_ms = (time.perf_counter() - start) * 1000

        logger.info(
            "NVIDIA response received: {} chars in {:.0f}ms",
            len(response_text),
            latency_ms,
        )
        return response_text, latency_ms

    def is_reachable(self) -> bool:
        """Health check — True if API key is configured."""
        return bool(self._api_key and self._api_key != "your-nvidia-api-key-here")

    # ─────────────────────────────────────────
    #  Private helpers
    # ─────────────────────────────────────────

    def _build_payload(self, prompt: str) -> dict:
        return {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": self._max_tokens,
            "temperature": self._temperature,
            "top_p": 0.70,
            "stream": False,
        }

    @retry(
        retry=retry_if_exception_type(httpx.TransportError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def _call_nvidia(self, payload: dict) -> str:
        """POST to NVIDIA /v1/chat/completions and return response text."""
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.post(NVIDIA_API_URL, headers=headers, json=payload)

            if response.status_code != 200:
                raise NvidiaError(
                    f"NVIDIA API returned HTTP {response.status_code}: {response.text[:300]}"
                )

            data = response.json()
            return data["choices"][0]["message"]["content"].strip()

        except httpx.TimeoutException as exc:
            raise NvidiaError(f"NVIDIA API timed out after {self._timeout}s.") from exc
        except httpx.ConnectError as exc:
            raise NvidiaError(f"Cannot connect to NVIDIA API: {exc}") from exc
        except (KeyError, IndexError) as exc:
            raise NvidiaError(f"Unexpected NVIDIA response format: {exc}") from exc
        except NvidiaError:
            raise
        except Exception as exc:
            raise NvidiaError(f"Unexpected error calling NVIDIA API: {exc}") from exc
