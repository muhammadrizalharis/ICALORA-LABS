"""Embedding teks untuk AI Detector (fitur semantik 1024-dim via bge-m3).

Model stylometrik 6-fitur jenuh di beberapa ribu sampel. Menambahkan embedding
semantik (bge-m3, 1024-dim) sebagai fitur memberi sinyal jauh lebih kaya sehingga
akurasi bisa naik signifikan. Embedding diambil dari Ollama (endpoint dapat
dikonfigurasi), cepat (~45 ms/teks) dan hemat VRAM (566M param).

Fungsi ini sengaja mengembalikan None bila gagal (endpoint mati/timeout) agar
pemanggil bisa degradasi anggun ke model statistik.
"""

from __future__ import annotations

import os

import httpx

EMB_ENDPOINT = os.environ.get("ICALORA_EMB_ENDPOINT", "http://127.0.0.1:11434")
EMB_MODEL = os.environ.get("ICALORA_EMB_MODEL", "bge-m3:latest")
EMB_DIM = 1024
_MAX_CHARS = 8000


def embed_text(
    text: str,
    client: httpx.Client | None = None,
    endpoint: str | None = None,
) -> list[float] | None:
    """Kembalikan vektor embedding (EMB_DIM float) untuk `text`, atau None bila gagal."""
    endpoint = endpoint or EMB_ENDPOINT
    own = client is None
    if own:
        client = httpx.Client()
    try:
        resp = client.post(
            f"{endpoint}/api/embed",
            json={"model": EMB_MODEL, "input": text[:_MAX_CHARS]},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        embs = data.get("embeddings")
        if embs and embs[0]:
            vec = embs[0]
        else:
            vec = data.get("embedding")
        if not vec or len(vec) != EMB_DIM:
            return None
        return [float(v) for v in vec]
    except Exception:  # noqa: BLE001
        return None
    finally:
        if own:
            client.close()


def embed_texts(
    texts: list[str],
    endpoint: str | None = None,
    batch_size: int = 16,
) -> list[list[float] | None]:
    """Embed banyak teks via /api/embed berbatch. Elemen None bila gagal."""
    endpoint = endpoint or EMB_ENDPOINT
    out: list[list[float] | None] = []
    with httpx.Client() as client:
        for i in range(0, len(texts), batch_size):
            chunk = [t[:_MAX_CHARS] for t in texts[i : i + batch_size]]
            try:
                resp = client.post(
                    f"{endpoint}/api/embed",
                    json={"model": EMB_MODEL, "input": chunk},
                    timeout=120,
                )
                resp.raise_for_status()
                embs = resp.json().get("embeddings") or []
            except Exception:  # noqa: BLE001
                embs = []
            for j in range(len(chunk)):
                vec = embs[j] if j < len(embs) else None
                ok = vec is not None and len(vec) == EMB_DIM
                out.append([float(v) for v in vec] if ok else None)
    return out
