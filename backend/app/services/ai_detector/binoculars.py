"""Klien layanan skor Binoculars (services/binoculars).

Binoculars (Hans et al., 2024) adalah detektor zero-shot berbasis rasio perplexity
dua LLM; makin rendah skornya makin mirip teks AI. Sinyal ini pelengkap model
embedding — paling kuat pada generator yang tidak ikut dilatih.

Gagal-aman: bila layanan mati, VRAM penuh, atau timeout, kembalikan None dan
detektor tetap berjalan tanpa Binoculars.
"""

from __future__ import annotations

import os

import httpx

BINOC_ENDPOINT = os.getenv("ICALORA_BINOC_ENDPOINT", "http://127.0.0.1:58050")
BINOC_ENABLED = os.getenv("ICALORA_BINOC", "on").strip().lower() not in {"off", "0", "false", "no"}
try:
    # Termasuk waktu muat model saat layanan baru bangun dari idle (~35 dtk).
    BINOC_TIMEOUT = float(os.getenv("ICALORA_BINOC_TIMEOUT", "120"))
except ValueError:
    BINOC_TIMEOUT = 120.0
_MAX_BATCH = 400


def binoculars_scores(texts: list[str]) -> list[float | None] | None:
    """Skor Binoculars per teks, atau None bila layanan tidak tersedia."""
    if not BINOC_ENABLED or not texts:
        return None
    out: list[float | None] = []
    try:
        with httpx.Client(timeout=BINOC_TIMEOUT) as client:
            for i in range(0, len(texts), _MAX_BATCH):
                resp = client.post(f"{BINOC_ENDPOINT}/score",
                                   json={"texts": texts[i:i + _MAX_BATCH]})
                resp.raise_for_status()
                scores = resp.json()["scores"]
                if len(scores) != len(texts[i:i + _MAX_BATCH]):
                    return None
                out.extend(None if s is None else float(s) for s in scores)
    except (httpx.HTTPError, KeyError, ValueError, TypeError):
        return None
    return out
