"""Embedding tingkat-dokumen untuk teks panjang.

Alih-alih hanya meng-embed potongan awal dokumen, modul ini memecah teks
menjadi beberapa jendela (chunk) dan meng-embed semuanya dalam satu panggilan
batch GPU. Dengan begitu analisis semantik mencakup *seluruh* isi dokumen,
bukan hanya bagian pembuka — penting untuk dokumen panjang (skripsi/tesis).
"""

from __future__ import annotations

import time

from app.services.llm.provider import LLMProvider


def chunk_text(
    text: str, size: int = 2000, overlap: int = 200, max_chunks: int = 20
) -> list[str]:
    """Pecah `text` menjadi jendela ~`size` karakter dengan sedikit tumpang-tindih.

    Jika jumlah jendela melebihi `max_chunks`, ambil sampel merata di seluruh
    dokumen sehingga keseluruhan isi tetap terwakili tanpa biaya yang meledak.
    """
    text = text.strip()
    if not text:
        return []
    step = max(size - overlap, 1)
    chunks = [text[i : i + size] for i in range(0, len(text), step)]
    chunks = [c for c in chunks if c.strip()]
    if len(chunks) <= max_chunks:
        return chunks
    # Sampel merata di sepanjang dokumen (termasuk awal & akhir).
    span = len(chunks) - 1
    picked: list[str] = []
    seen: set[int] = set()
    for i in range(max_chunks):
        j = round(i * span / (max_chunks - 1))
        if j not in seen:
            seen.add(j)
            picked.append(chunks[j])
    return picked


def embed_chunks(
    llm: LLMProvider,
    text: str,
    *,
    size: int = 2000,
    overlap: int = 200,
    max_chunks: int = 20,
) -> list[list[float]]:
    """Embed seluruh jendela dokumen dalam satu panggilan batch."""
    chunks = chunk_text(text, size=size, overlap=overlap, max_chunks=max_chunks)
    if not chunks:
        return []
    return llm.embed_batch(chunks)


def _spread_order(n: int, stride: int = 4) -> list[int]:
    """Urutan indeks yang menyebar (0,4,8,... lalu 1,5,9,...) agar hasil PARSIAL tetap mewakili
    seluruh dokumen, bukan hanya bagian pembukanya."""
    return [i for r in range(min(stride, n)) for i in range(r, n, stride)]


def embed_chunks_budgeted(
    llm: LLMProvider,
    text: str,
    *,
    max_chunks: int,
    budget_seconds: float,
    batch_size: int = 8,
    call_timeout: float = 60.0,
    size: int = 2000,
    overlap: int = 200,
) -> tuple[list[list[float]], int]:
    """Embed jendela dokumen dalam batch kecil dengan anggaran waktu.

    Mengembalikan (vektor_yang_berhasil, total_jendela). Tidak pernah melempar: batch yang
    gagal/timeout/lewat anggaran dilewati, sehingga pemanggil mendapat hasil parsial (urut menyebar)
    atau daftar kosong, dan memutuskan sendiri cara menurunkan mutu.
    """
    chunks = chunk_text(text, size=size, overlap=overlap, max_chunks=max_chunks)
    total = len(chunks)
    if not total:
        return [], 0
    fast = getattr(llm, "embed_batch_fast", None)
    deadline = time.monotonic() + budget_seconds
    order = _spread_order(total)
    out: list[list[float]] = []
    failures = 0
    for i in range(0, total, max(1, batch_size)):
        remaining = deadline - time.monotonic()
        if remaining <= 1:
            break
        batch = [chunks[j] for j in order[i : i + batch_size]]
        try:
            if fast is not None:
                vecs = fast(batch, timeout=min(call_timeout, remaining), attempts=1, wait=remaining)
            else:
                vecs = llm.embed_batch(batch)
        except Exception:  # noqa: BLE001
            failures += 1
            if failures >= 2:
                break  # server kewalahan: berhenti, pakai yang sudah ada
            continue  # satu kegagalan bisa sesaat (antrean); coba batch berikutnya
        failures = 0
        out.extend(vecs)
    return out, total


def embed_document(
    llm: LLMProvider,
    text: str,
    *,
    size: int = 2000,
    overlap: int = 200,
    max_chunks: int = 20,
) -> list[float]:
    """Satu vektor yang mewakili keseluruhan dokumen (rata-rata embedding jendela).

    Cocok untuk pencarian tetangga terdekat tunggal (sitasi/publikasi) agar
    representasi mencakup seluruh isi, bukan hanya pembuka. Aman untuk cosine
    (invarian skala), sehingga tidak perlu normalisasi eksplisit.
    """
    vecs = embed_chunks(llm, text, size=size, overlap=overlap, max_chunks=max_chunks)
    if not vecs:
        return llm.embed(text[:size])
    dim = len(vecs[0])
    n = len(vecs)
    return [sum(v[i] for v in vecs) / n for i in range(dim)]
