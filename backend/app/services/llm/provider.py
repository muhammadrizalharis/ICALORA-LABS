"""Abstraksi penyedia LLM. Default: Ollama (server bersama).

Lapisan ini sengaja dibuat agar provider (Ollama / API komersial / model lain)
dapat diganti tanpa mengubah kode fitur.
"""

from __future__ import annotations

import threading
import time
from typing import Protocol

import httpx

from app.core.config import get_settings

settings = get_settings()

# Ollama bersama kadang mengembalikan 5xx sesaat saat sibuk / memuat model.
_MAX_RETRIES = 3
_RETRY_BACKOFF = 1.5


# Server embedding dipakai bersama banyak job (plagiarisme, AI detector, semantik). Tanpa batas,
# permintaan menumpuk di server dan waktu ANTRE ikut dihitung sebagai timeout (terukur: 2 job
# serempak -> ReadTimeout 120 dtk x3). Semaphore membuat waktu tunggu antrean terjadi di sini,
# sebelum jam timeout permintaan berjalan.
_EMBED_SEM = threading.BoundedSemaphore(max(1, settings.embed_max_concurrency))
# Jalur CEPAT (batch kecil, berbatas waktu: embedding dokumen & semantik) punya slot sendiri agar
# tak kelaparan di belakang job massal (mis. AI detector) yang menguasai _EMBED_SEM berjam-jam.
_FAST_SEM = threading.BoundedSemaphore(max(1, settings.embed_max_concurrency))


def _post_with_retry(
    client: httpx.Client, url: str, payload: dict, attempts: int | None = None
) -> httpx.Response:
    """POST dengan retry eksponensial untuk galat transien (5xx / koneksi)."""
    last_exc: Exception | None = None
    tries = attempts or _MAX_RETRIES
    for attempt in range(tries):
        try:
            resp = client.post(url, json=payload)
            if resp.status_code >= 500 and attempt < tries - 1:
                time.sleep(_RETRY_BACKOFF * (attempt + 1))
                continue
            resp.raise_for_status()
            return resp
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError) as exc:
            last_exc = exc
            if attempt < tries - 1:
                time.sleep(_RETRY_BACKOFF * (attempt + 1))
                continue
            raise
    if last_exc:
        raise last_exc
    raise RuntimeError("Permintaan LLM gagal tanpa respons.")


class LLMProvider(Protocol):
    def chat(
        self,
        messages: list[dict],
        temperature: float = 0.2,
        max_tokens: int | None = None,
        think: bool | None = None,
        num_ctx: int | None = None,
        timeout: float | None = None,
    ) -> str: ...

    def embed(self, text: str) -> list[float]: ...

    def embed_batch(self, texts: list[str]) -> list[list[float]]: ...


class OllamaProvider:
    """Adapter untuk Ollama (API lokal /api/chat & /api/embeddings)."""

    def __init__(
        self,
        base_url: str,
        model: str,
        embed_model: str,
        timeout: int,
        keep_alive: str = "5m",
        embed_base_url: str | None = None,
        think: bool | None = None,
        embed_keep_alive: str | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.embed_base_url = (embed_base_url or base_url).rstrip("/")
        self.model = model
        self.embed_model = embed_model
        self.timeout = timeout
        self.keep_alive = keep_alive
        self.embed_keep_alive = embed_keep_alive or keep_alive
        self.think = think

    def _embed_payload(self, **fields) -> dict:
        payload = {"model": self.embed_model, **fields}
        if self.embed_keep_alive.strip().lower() != "server":
            payload["keep_alive"] = self.embed_keep_alive
        return payload

    def chat(
        self,
        messages: list[dict],
        temperature: float = 0.2,
        max_tokens: int | None = None,
        think: bool | None = None,
        num_ctx: int | None = None,
        timeout: float | None = None,
    ) -> str:
        options: dict = {"temperature": temperature}
        if max_tokens:
            options["num_predict"] = max_tokens
        # num_ctx: tanpa ini Ollama memakai jendela default (~4k token) sehingga
        # dokumen panjang DIPOTONG diam-diam. Set eksplisit agar seluruh teks
        # terbaca (sampai batas model, mis. 32k untuk qwen2.5).
        if num_ctx:
            options["num_ctx"] = num_ctx
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": options,
            "keep_alive": self.keep_alive,
        }
        # `think` per-panggilan menimpa default provider. Penting untuk model
        # reasoning (mis. qwen3.x): bila thinking aktif, seluruh num_predict bisa
        # habis untuk reasoning tersembunyi sehingga `message.content` kosong.
        effective_think = think if think is not None else self.think
        if effective_think is not None:
            payload["think"] = effective_think
        # timeout per-panggilan menimpa default provider (berguna untuk tugas yang
        # toleran lambat seperti grammar chunk saat model dingin di GPU bersama).
        with httpx.Client(timeout=timeout or self.timeout) as client:
            resp = _post_with_retry(client, f"{self.base_url}/api/chat", payload)
            return resp.json()["message"]["content"].strip()

    def embed(self, text: str) -> list[float]:
        payload = self._embed_payload(prompt=text)
        with httpx.Client(timeout=self.timeout) as client:
            resp = _post_with_retry(client, f"{self.embed_base_url}/api/embeddings", payload)
            return resp.json()["embedding"]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed banyak teks dalam satu panggilan (GPU) via /api/embed."""
        if not texts:
            return []
        payload = self._embed_payload(input=texts)
        with _EMBED_SEM, httpx.Client(timeout=self.timeout) as client:
            resp = _post_with_retry(client, f"{self.embed_base_url}/api/embed", payload)
            return resp.json()["embeddings"]

    def embed_batch_fast(
        self, texts: list[str], timeout: float, attempts: int = 1, wait: float | None = None
    ) -> list[list[float]]:
        """Seperti embed_batch tetapi GAGAL CEPAT: timeout & percobaan ulang ditentukan pemanggil,
        dan menunggu antrean maksimal `wait` detik (TimeoutError bila tak kebagian giliran)."""
        if not texts:
            return []
        if not _FAST_SEM.acquire(timeout=wait if wait is not None else -1):
            raise TimeoutError("Antrean embedding penuh.")
        try:
            payload = self._embed_payload(input=texts)
            with httpx.Client(timeout=timeout) as client:
                resp = _post_with_retry(
                    client, f"{self.embed_base_url}/api/embed", payload, attempts=attempts
                )
                return resp.json()["embeddings"]
        finally:
            _FAST_SEM.release()


def get_llm() -> LLMProvider:
    if settings.llm_provider == "ollama":
        return OllamaProvider(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            embed_model=settings.ollama_embed_model,
            timeout=settings.llm_timeout,
            keep_alive=settings.ollama_keep_alive,
            embed_base_url=settings.ollama_embed_base_url or settings.ollama_base_url,
            think=settings.ollama_think,
            embed_keep_alive=settings.ollama_embed_keep_alive,
        )
    raise ValueError(f"Provider LLM tidak dikenal: {settings.llm_provider}")
