"""Abstraksi penyedia LLM. Default: Ollama (server bersama).

Lapisan ini sengaja dibuat agar provider (Ollama / API komersial / model lain)
dapat diganti tanpa mengubah kode fitur.
"""

from __future__ import annotations

from typing import Protocol

import httpx

from app.core.config import get_settings

settings = get_settings()


class LLMProvider(Protocol):
    def chat(
        self, messages: list[dict], temperature: float = 0.2, max_tokens: int | None = None
    ) -> str: ...

    def embed(self, text: str) -> list[float]: ...

    def embed_batch(self, texts: list[str]) -> list[list[float]]: ...


class OllamaProvider:
    """Adapter untuk Ollama (API lokal /api/chat & /api/embeddings)."""

    def __init__(self, base_url: str, model: str, embed_model: str, timeout: int):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.embed_model = embed_model
        self.timeout = timeout

    def chat(
        self, messages: list[dict], temperature: float = 0.2, max_tokens: int | None = None
    ) -> str:
        options: dict = {"temperature": temperature}
        if max_tokens:
            options["num_predict"] = max_tokens
        payload = {"model": self.model, "messages": messages, "stream": False, "options": options}
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(f"{self.base_url}/api/chat", json=payload)
            resp.raise_for_status()
            return resp.json()["message"]["content"].strip()

    def embed(self, text: str) -> list[float]:
        payload = {"model": self.embed_model, "prompt": text}
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(f"{self.base_url}/api/embeddings", json=payload)
            resp.raise_for_status()
            return resp.json()["embedding"]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed banyak teks dalam satu panggilan (GPU) via /api/embed."""
        if not texts:
            return []
        payload = {"model": self.embed_model, "input": texts}
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(f"{self.base_url}/api/embed", json=payload)
            resp.raise_for_status()
            return resp.json()["embeddings"]


def get_llm() -> LLMProvider:
    if settings.llm_provider == "ollama":
        return OllamaProvider(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            embed_model=settings.ollama_embed_model,
            timeout=settings.llm_timeout,
        )
    raise ValueError(f"Provider LLM tidak dikenal: {settings.llm_provider}")
