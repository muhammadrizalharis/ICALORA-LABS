"""Embedding tingkat-dokumen untuk teks panjang.

Alih-alih hanya meng-embed potongan awal dokumen, modul ini memecah teks
menjadi beberapa jendela (chunk) dan meng-embed semuanya dalam satu panggilan
batch GPU. Dengan begitu analisis semantik mencakup *seluruh* isi dokumen,
bukan hanya bagian pembuka — penting untuk dokumen panjang (skripsi/tesis).
"""

from __future__ import annotations

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
