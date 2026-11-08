"""Deteksi kemiripan / plagiarisme terhadap korpus.

Strategi dua lapis (seperti alat komersial):
  1. Semantik (parafrase): embed teks (bge-m3, GPU) lalu cari tetangga
     terdekat di corpus_embeddings via pgvector cosine (index HNSW).
  2. Leksikal (salinan): MinHash Jaccard antara teks masukan dan dokumen
     kandidat (dari corpus_fingerprints).

Keterbatasan MVP: fingerprint tingkat-dokumen, jadi angka leksikal adalah
kemiripan keseluruhan, bukan per-paragraf. Pencocokan tingkat-paragraf
menyusul (chunk-level).
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone

from sqlalchemy import text

from app.core.clients import corpus_size, embedded_corpus_size, engine
from app.ingest.common import (
    decompress_text,
    make_minhash,
    minhash_from_bytes,
    text_metrics,
)
from app.services.embedding import embed_chunks
from app.services.llm.provider import get_llm

_SHINGLE = 5
_SENT_RE = re.compile(r"[^.!?\n]+[.!?]?", re.UNICODE)
_WORD_RE = re.compile(r"\w+", re.UNICODE)

# Rentang teks di antara tanda kutip (minimal 10 karakter agar bukan apostrof).
_QUOTE_RE = re.compile(r'["“”„«»][^"“”„«»]{10,}?["“”„«»]', re.UNICODE)

# Penanda sitasi: (… 2020), [12]/[1-3]/[1,2], dkk./et al.
_CITATION_RE = re.compile(
    r"\([^()]*\b(?:19|20)\d{2}[a-z]?\b[^()]*\)"
    r"|\[\s*\d+(?:\s*[-,]\s*\d+)*\s*\]"
    r"|\b(?:dkk|et al)\.",
    re.UNICODE,
)

# Awal bagian daftar pustaka / referensi (judul baris).
_BIB_RE = re.compile(
    r"(?i)(?:^|\n)\s*(?:daftar pustaka|daftar rujukan|referensi|references|"
    r"bibliography|works cited)\s*(?:\n|:|$)",
    re.UNICODE,
)

# Kelompok kecocokan berdasarkan status sitasi & kutipan (lihat docs/11 A.1).
_MATCH_GROUP_ORDER = ["uncited", "missing_quote", "missing_citation", "cited_quoted"]

# Batas teks dokumen yang disimpan untuk tampilan "Dokumen dengan Sorotan".
# Cukup untuk naskah panjang, tanpa membengkakkan riwayat (jsonb).
_MAX_DOC_DISPLAY = 60_000


def _classify_match(
    sent: str,
    idx: int,
    quoted_spans: list[tuple[int, int]],
    cite_spans: list[tuple[int, int]],
    bib_start: int | None,
) -> dict:
    """Tentukan status kutipan/sitasi sebuah kalimat yang cocok."""
    if idx < 0:
        quoted = cited = in_bib = False
    else:
        end = idx + len(sent)
        mid = idx + len(sent) // 2
        quoted = any(s <= mid <= e for s, e in quoted_spans)
        cited = any(s < end + 80 and e > idx for s, e in cite_spans)
        in_bib = bib_start is not None and idx >= bib_start
    if cited and quoted:
        group = "cited_quoted"
    elif cited and not quoted:
        group = "missing_quote"
    elif quoted and not cited:
        group = "missing_citation"
    else:
        group = "uncited"
    return {"quoted": quoted, "cited": cited, "in_bibliography": in_bib, "group": group}



def _shingles(words: list[str], n: int = _SHINGLE) -> set[str]:
    if len(words) < n:
        return {" ".join(words)} if words else set()
    return {" ".join(words[i : i + n]) for i in range(len(words) - n + 1)}


def _sentences(s: str) -> list[str]:
    return [m.group(0).strip() for m in _SENT_RE.finditer(s) if len(m.group(0).strip()) >= 20]


def _chunk_match(doc: str, candidates: list[dict], threshold: float = 0.55) -> dict:
    """Pencocokan tingkat-kalimat (tingkat kalimat) terhadap dokumen kandidat.

    Untuk tiap kalimat masukan, hitung containment shingle terhadap gabungan
    shingle tiap dokumen kandidat; kalimat dengan containment tinggi ditandai
    sebagai kutipan yang cocok. Indeks kemiripan = proporsi karakter yang cocok.
    """
    cand_shingles: list[tuple[dict, set[str]]] = []
    for c in candidates:
        body = c.get("_fulltext") or ""
        if not body:
            continue
        words = [w.lower() for w in _WORD_RE.findall(body)]
        cand_shingles.append((c, _shingles(words)))

    sentences = _sentences(doc)
    matched: list[dict] = []
    matched_chars = 0
    total_chars = max(len(doc), 1)

    quoted_spans = [(m.start(), m.end()) for m in _QUOTE_RE.finditer(doc)]
    cite_spans = [(m.start(), m.end()) for m in _CITATION_RE.finditer(doc)]
    bib_m = _BIB_RE.search(doc)
    bib_start = bib_m.start() if bib_m else None
    low_doc = doc.lower()
    group_chars = {k: 0 for k in _MATCH_GROUP_ORDER}
    group_count = {k: 0 for k in _MATCH_GROUP_ORDER}

    for sent in sentences:
        words = [w.lower() for w in _WORD_RE.findall(sent)]
        sh = _shingles(words)
        if not sh:
            continue
        best_ratio = 0.0
        best_src: dict | None = None
        for c, cset in cand_shingles:
            if not cset:
                continue
            overlap = len(sh & cset)
            ratio = overlap / len(sh)
            if ratio > best_ratio:
                best_ratio = ratio
                best_src = c
        if best_ratio >= threshold and best_src is not None:
            matched_chars += len(sent)
            idx = doc.find(sent)
            if idx < 0:
                idx = low_doc.find(sent.lower())
            status = _classify_match(sent, idx, quoted_spans, cite_spans, bib_start)
            group_chars[status["group"]] += len(sent)
            group_count[status["group"]] += 1
            matched.append(
                {
                    "sentence": sent[:300],
                    "match_ratio": round(best_ratio * 100, 1),
                    "source_title": best_src.get("title"),
                    "source_doi": best_src.get("doi"),
                    "doc_id": best_src.get("doc_id"),
                    "char_len": len(sent),
                    "quoted": status["quoted"],
                    "cited": status["cited"],
                    "in_bibliography": status["in_bibliography"],
                    "group": status["group"],
                }
            )

    similarity_index = round(matched_chars / total_chars * 100, 1)
    matched.sort(key=lambda m: m["match_ratio"], reverse=True)
    match_groups = [
        {
            "type": k,
            "count": group_count[k],
            "percent": round(group_chars[k] / total_chars * 100, 1),
        }
        for k in _MATCH_GROUP_ORDER
    ]
    return {
        "similarity_index": similarity_index,
        "matched_sentences": len(matched),
        "total_sentences": len(sentences),
        "matched_passages": matched[:50],
        "match_groups": match_groups,
    }


_NEAREST = text(
    """
    SELECT d.id, d.source, d.external_id, d.doi, d.title, d.pub_year,
           d.text_zstd, f.minhash,
           1 - (e.embedding <=> CAST(:qvec AS halfvec(1024))) AS cos_sim
    FROM corpus_embeddings e
    JOIN corpus_documents d ON d.id = e.doc_id
    LEFT JOIN corpus_fingerprints f ON f.doc_id = d.id
    ORDER BY e.embedding <=> CAST(:qvec AS halfvec(1024))
    LIMIT :k
    """
)


def _vec_literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"


# Perluas cakupan pencarian HNSW: semakin tinggi ef_search, semakin banyak
# kandidat dari seluruh korpus (1,2 juta+) yang ditelusuri sebelum memilih
# yang paling mirip — recall mendekati pemindaian penuh, bukan sekadar 10.
_EF_SEARCH = 500

# Saat dokumen panjang dicari per-jendela, kita menjalankan banyak pencarian
# (satu per jendela) lalu menggabungkan hasilnya. Gabungan antar-jendela sudah
# memperluas recall, jadi tiap pencarian cukup memakai ef_search lebih kecil
# agar total tetap cepat.
_EF_SEARCH_MULTI = 200


def _set_ef_search(conn, value: int = _EF_SEARCH) -> None:
    """Atur ef_search untuk transaksi ini agar menelusuri korpus lebih luas."""
    conn.execute(text(f"SET LOCAL hnsw.ef_search = {value}"))


_corpus_cache: dict[str, object] = {"size": 0, "ts": 0.0}


def _corpus_size() -> int:
    """Jumlah dokumen korpus (cache 5 menit) untuk cakupan laporan yang jujur."""
    return corpus_size()


def _report_id(doc: str, generated_at: datetime) -> str:
    """ID laporan reproducible: teks sama + tanggal sama → ID sama (dapat diverifikasi)."""
    h = hashlib.sha256(doc.encode("utf-8")).hexdigest()
    return f"ICL-{generated_at:%Y%m%d}-{h[:10].upper()}"


def check_plagiarism(doc: str, top_k: int = 30) -> dict:
    """Bandingkan `doc` dengan korpus; kembalikan laporan kemiripan."""
    doc = doc.strip()
    wc, cc = text_metrics(doc)
    if cc == 0:
        return {"overall_similarity": 0.0, "sources": [], "word_count": 0, "char_count": 0}

    llm = get_llm()
    q_mh_bytes = make_minhash(doc)
    q_mh = minhash_from_bytes(q_mh_bytes) if q_mh_bytes else None

    # Embed SELURUH dokumen per-jendela, lalu cari tetangga terdekat untuk tiap
    # jendela dan gabungkan — agar penyalinan di bagian mana pun (bukan hanya
    # pembuka) ikut tertangkap. Jumlah sumber akhir tetap `top_k` teratas.
    qvecs = embed_chunks(llm, doc, max_chunks=12) or [llm.embed(doc[:2000])]
    # Satu jendela: pakai ef_search penuh. Banyak jendela: ef_search lebih kecil
    # per pencarian karena gabungan antar-jendela sudah memperluas recall.
    ef = _EF_SEARCH if len(qvecs) <= 1 else _EF_SEARCH_MULTI
    per_k = max(top_k, 15)
    best: dict[int, dict] = {}
    with engine.connect() as conn:
        _set_ef_search(conn, ef)
        for qv in qvecs:
            rows = conn.execute(_NEAREST, {"qvec": _vec_literal(qv), "k": per_k}).all()
            for r in rows:
                cs = float(r.cos_sim) if r.cos_sim is not None else 0.0
                cur = best.get(r.id)
                if cur is None or cs > cur["cos"]:
                    best[r.id] = {"row": r, "cos": cs}
    ranked = sorted(best.values(), key=lambda x: x["cos"], reverse=True)[:top_k]

    sources: list[dict] = []
    for item in ranked:
        r = item["row"]
        cos_sim = item["cos"]
        lexical = 0.0
        if q_mh is not None and r.minhash is not None:
            lexical = float(q_mh.jaccard(minhash_from_bytes(bytes(r.minhash))))
        fulltext = decompress_text(r.text_zstd) if r.text_zstd else ""
        sources.append(
            {
                "doc_id": r.id,
                "source": r.source,
                "external_id": r.external_id,
                "doi": r.doi,
                "title": r.title,
                "pub_year": r.pub_year,
                "semantic_similarity": round(cos_sim * 100, 1),
                "lexical_similarity": round(lexical * 100, 1),
                "similarity": round(max(cos_sim, lexical) * 100, 1),
                "snippet": fulltext[:320].strip(),
                "_fulltext": fulltext,
            }
        )

    # Pencocokan tingkat-kalimat untuk indeks kemiripan tingkat kalimat.
    chunk = _chunk_match(doc, sources)
    for s in sources:
        s.pop("_fulltext", None)

    sources.sort(key=lambda s: (s["lexical_similarity"], s["semantic_similarity"]), reverse=True)
    # Indeks kemiripan utama = kecocokan leksikal/salinan (tingkat kalimat).
    # Semantik dilaporkan terpisah sebagai risiko parafrase (butuh ambang tinggi).
    overall = max((s["lexical_similarity"] for s in sources), default=0.0)
    paraphrase = max((s["semantic_similarity"] for s in sources), default=0.0)
    # Gabungkan: indeks utama = maksimum antara coverage kalimat dan leksikal dokumen.
    similarity_index = max(overall, chunk["similarity_index"])
    generated_at = datetime.now(timezone.utc)
    total_docs = _corpus_size()
    embedded_docs = embedded_corpus_size()
    semantic_coverage = round(embedded_docs / total_docs * 100, 1) if total_docs else 0.0
    return {
        "overall_similarity": similarity_index,
        "document_lexical_similarity": overall,
        "paraphrase_similarity": paraphrase,
        "similarity_index": chunk["similarity_index"],
        "matched_sentences": chunk["matched_sentences"],
        "total_sentences": chunk["total_sentences"],
        "matched_passages": chunk["matched_passages"],
        "match_groups": chunk["match_groups"],
        "document_text": doc[:_MAX_DOC_DISPLAY],
        "document_truncated": len(doc) > _MAX_DOC_DISPLAY,
        "word_count": wc,
        "char_count": cc,
        "sources": sources,
        "report_id": _report_id(doc, generated_at),
        "content_sha256": hashlib.sha256(doc.encode("utf-8")).hexdigest(),
        "corpus_size": total_docs,
        "lexical_coverage": total_docs,
        "semantic_coverage_docs": embedded_docs,
        "semantic_coverage_pct": semantic_coverage,
        "coverage_note": (
            f"Deteksi salinan (leksikal) mencakup {total_docs:,} dokumen (penuh). "
            f"Deteksi parafrase (semantik) mencakup {embedded_docs:,} dokumen "
            f"(~{semantic_coverage}% korpus); skor parafrase adalah batas bawah."
        ),
        "generated_at": generated_at.isoformat(timespec="seconds"),
    }
