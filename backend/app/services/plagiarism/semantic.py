"""Deteksi PARAFRASE terhadap teks penuh paper terbit (kesamaan makna, bukan kata).

Pencocokan kalimat biasa (`_chunk_match`) hanya menangkap teks yang sama. Dokumen yang
ditulis ulang dengan kata/struktur berbeda lolos (uji: 0,1-6,5%) walau paper sumbernya
sudah ditemukan dan teks penuhnya sudah diunduh. Modul ini membandingkan MAKNA: jendela
2-kalimat dokumen vs jendela 2-kalimat tiap kandidat teks-penuh memakai embedding bge-m3.

Ambang diukur, bukan ditebak (sumber IJHT 10.18280/ijht.440419, bge-m3, jendela 2 kalimat):
- parafrase agresif (tumpang-tindih kata ~0)        : cosine rata-rata 0,875; 96% jendela >= 0,80
- paper LAIN bertopik SAMA (kontrol negatif)         : rata-rata 0,68; p90 0,75; 0% >= 0,80
  (kontrol lain: sampai 4% jendela >= 0,80 — kalimat generik)
Maka satu jendela dianggap cocok bila cosine >= 0,80, dan dokumen ditandai bila >= 35%
jendelanya cocok dengan SATU paper (jauh di atas kontrol negatif, jauh di bawah positif).
Hasil adalah INDIKASI: tidak dimasukkan ke Similarity Index.
"""

from __future__ import annotations

import logging
import re

import numpy as np

from app.core.config import get_settings

from . import _sentences

log = logging.getLogger(__name__)
settings = get_settings()

WINDOW_SENTENCES = 2
MIN_WINDOW_CHARS = 60
MAX_DOC_WINDOWS = 300
MAX_SRC_WINDOWS = 800
MAX_CANDIDATES = 4
MIN_SRC_CHARS = 4000  # sumber terlalu pendek (abstrak/snippet) tak layak dibandingkan
SKIP_IF_INDEX_AT_LEAST = 60.0  # dokumen sudah dijelaskan pencocokan kata
SKIP_CANDIDATE_IF_LEXICAL_AT_LEAST = 60.0
MAX_EXAMPLES = 3
VERBATIM_COS = 0.985  # pasangan nyaris identik bukan contoh parafrase
EXAMPLE_MAX_WORD_OVERLAP = 0.6  # contoh harus benar-benar berbeda kata (bukan judul bab sama)


_SOFT_BREAK_RE = re.compile(r"(?<!\n)\n(?!\n)")


def _unwrap(text: str) -> str:
    """Sambung baris PDF yang terpotong (pindah baris tunggal) menjadi satu kalimat utuh.

    Teks hasil ekstraksi PDF dibungkus per baris. Tanpa ini kalimat terbelah dan jendela
    "dua kalimat" hanya serpihan yang batasnya tak sejajar antara dokumen dan sumber, sehingga
    kesamaan makna tak terdeteksi (uji: dokumen PDF diparafrase 0% vs 97% dari teks mentah).
    Baris kosong (paragraf) dipertahankan sebagai pemisah.
    """
    return re.sub(r"[ \t]+", " ", _SOFT_BREAK_RE.sub(" ", text or ""))


def _windows(text: str, cap: int) -> list[str]:
    sents = [s.strip() for s in _sentences(_unwrap(text)) if len(s.strip()) >= 25]
    wins = [
        " ".join(sents[i : i + WINDOW_SENTENCES])
        for i in range(0, max(1, len(sents) - WINDOW_SENTENCES + 1))
    ]
    wins = [w for w in wins if len(w) >= MIN_WINDOW_CHARS]
    if len(wins) > cap:  # sampel merata agar cakupan tetap mewakili seluruh dokumen
        idx = np.linspace(0, len(wins) - 1, cap).round().astype(int)
        wins = [wins[i] for i in sorted(set(idx.tolist()))]
    return wins


def _embed(llm, texts: list[str]) -> np.ndarray:
    out: list[list[float]] = []
    for i in range(0, len(texts), 32):
        out.extend(llm.embed_batch([t[:1500] for t in texts[i : i + 32]]))
    mat = np.asarray(out, dtype=np.float32)
    if mat.size == 0:
        return mat.reshape(0, 0)
    mat /= np.linalg.norm(mat, axis=1, keepdims=True) + 1e-9
    return mat


def _word_overlap(a: str, b: str) -> float:
    wa, wb = set(re.findall(r"\w+", a.lower())), set(re.findall(r"\w+", b.lower()))
    return len(wa & wb) / max(1, len(wa | wb))


def _coverage(
    doc_vecs: np.ndarray, src_vecs: np.ndarray, tau: float
) -> tuple[float, np.ndarray, np.ndarray]:
    """(% jendela dokumen yang cocok, cosine maksimum, indeks jendela sumber terdekat)."""
    n = len(doc_vecs)
    if doc_vecs.size == 0 or src_vecs.size == 0:
        return 0.0, np.zeros(n), np.zeros(n, dtype=int)
    sims = doc_vecs @ src_vecs.T
    mx = sims.max(axis=1)
    return float((mx >= tau).mean() * 100.0), mx, sims.argmax(axis=1)


def _lexical_percent(result: dict, cand: dict) -> float:
    key = (cand.get("doi") or cand.get("title") or "").lower().strip()
    for s in result.get("sources", []) or []:
        if (s.get("doi") or s.get("title") or "").lower().strip() == key:
            return float(s.get("match_percent", 0.0) or 0.0)
    return 0.0


def find_semantic_source(doc: str, candidates: list[dict], result: dict, llm=None) -> dict | None:
    """Kembalikan paper yang kemungkinan DIPARAFRASE oleh dokumen, atau None.

    `candidates`: kandidat daring (dengan `_fulltext` + `fulltext_oa`). `result`: keluaran
    `check_plagiarism` (dipakai untuk melewati dokumen yang sudah dijelaskan pencocokan kata).
    """
    if not settings.online_semantic_enabled:
        return None
    if result.get("publication_match"):
        return None  # sudah teridentifikasi sebagai paper terbit (kata-demi-kata)
    if float(result.get("similarity_index", 0.0) or 0.0) >= SKIP_IF_INDEX_AT_LEAST:
        return None
    cands = [
        c
        for c in candidates or []
        if c.get("fulltext_oa")
        and len(c.get("_fulltext") or "") >= MIN_SRC_CHARS
        and _lexical_percent(result, c) < SKIP_CANDIDATE_IF_LEXICAL_AT_LEAST
    ]
    if not cands:
        return None
    if llm is None:
        from app.services.llm.provider import get_llm

        llm = get_llm()

    doc_wins = _windows(doc, MAX_DOC_WINDOWS)
    if len(doc_wins) < 8:
        return None  # terlalu sedikit untuk persentase yang bermakna
    doc_vecs = _embed(llm, doc_wins)
    tau = settings.semantic_match_cos

    if len(cands) > MAX_CANDIDATES:  # saring awal: kemiripan topik dokumen vs sumber
        doc_mean = doc_vecs.mean(axis=0)
        doc_mean /= np.linalg.norm(doc_mean) + 1e-9

        def topical(c: dict) -> float:
            vecs = _embed(llm, _windows(c["_fulltext"], 40))
            return float((vecs @ doc_mean).max()) if vecs.size else 0.0

        cands = sorted(cands, key=topical, reverse=True)[:MAX_CANDIDATES]

    best: dict | None = None
    for c in cands:
        src_wins = _windows(c["_fulltext"], MAX_SRC_WINDOWS)
        src_vecs = _embed(llm, src_wins)
        cov, mx, arg = _coverage(doc_vecs, src_vecs, tau)
        if best is None or cov > best["coverage"]:
            order = [
                i
                for i in np.argsort(-mx)
                if tau <= mx[i] < VERBATIM_COS
                and _word_overlap(doc_wins[i], src_wins[int(arg[i])]) < EXAMPLE_MAX_WORD_OVERLAP
            ][:MAX_EXAMPLES]
            best = {
                "title": c.get("title"),
                "doi": c.get("doi"),
                "url": c.get("url"),
                "source": c.get("source"),
                "coverage": round(cov, 1),
                "matched_windows": int((mx >= tau).sum()),
                "total_windows": len(doc_wins),
                "threshold": tau,
                "examples": [
                    {
                        "doc": re.sub(r"\s+", " ", doc_wins[i])[:260],
                        "source": re.sub(r"\s+", " ", src_wins[int(arg[i])])[:260],
                        "cos": round(float(mx[i]), 3),
                    }
                    for i in order
                ],
            }
    if best is None or best["coverage"] < settings.semantic_min_coverage:
        return None
    return best
