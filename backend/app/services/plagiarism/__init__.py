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

# Kategori temuan — skema ORISINAL berbasis sifat & tingkat keparahan
# kecocokan (bukan model status-sitasi milik alat komersial). Urutan = dari
# paling berisiko ke paling aman.
#   salinan_langsung : teks nyaris identik, tanpa atribusi  (paling berat)
#   kemiripan_kuat   : tumpang-tindih leksikal tinggi tapi parsial/ditata ulang
#   indikasi_parafrase: mirip makna, kata diubah (leksikal rendah)
#   sumber_terkredit : dikutip & disitasi dengan benar      (tidak dihitung risiko)
_MATCH_GROUP_ORDER = [
    "salinan_langsung",
    "kemiripan_kuat",
    "indikasi_parafrase",
    "sumber_terkredit",
]

# Ambang pencocokan tingkat-kalimat (lebih sensitif agar tumpang-tindih
# parsial ikut tertangkap — penting untuk ketelitian akademik).
_MATCH_MIN = 0.30      # minimum containment shingle agar dihitung sebagai temuan
_VERBATIM_AT = 0.80    # >= ini: dianggap salinan nyaris persis
_STRUCTURAL_AT = 0.45  # >= ini: kemiripan kuat terstruktur
# Deteksi frasa (sub-kalimat): lari kata verbatim beruntun sepanjang ini atau
# lebih DI DALAM kalimat yang secara keseluruhan tak melewati ambang containment
# tetap ditandai sebagai salinan langsung (fragmen). Ini menangkap potongan
# teks yang disalin persis meski sisanya diubah — selaras dengan alat komersial
# yang menyorot fragmen pendek, tanpa menggelembungkan skor (bobot proporsional
# pada porsi kalimat yang benar-benar identik). 8 kata = ambang standar plagiat.
_PHRASE_MIN_WORDS = 8

# Deteksi identitas publikasi (reverse-containment): bila teks SUMBER
# (mis. abstrak dari OpenAlex) nyaris seluruhnya termuat di dokumen, dokumen
# kemungkinan adalah publikasi terbit itu sendiri (atau turunannya).
_PUBMATCH_MIN = 0.75        # >= 75% teks sumber termuat di dokumen → cocok publikasi
_PUBMATCH_MIN_WORDS = 40    # abaikan sumber terlalu pendek (judul/snippet)
_CONTAIN_SHOW = 40.0        # tampilkan sumber ber-containment tinggi walau 0% tersorot

# Bobot kontribusi tiap kategori pada Indeks Integritas (salinan penuh = 1.0,
# makin "longgar" makin kecil; sumber terkredit tidak menambah risiko).
_GROUP_WEIGHT = {
    "salinan_langsung": 1.0,
    "kemiripan_kuat": 0.85,
    "indikasi_parafrase": 0.6,
    "sumber_terkredit": 0.0,
}

# Batas teks dokumen yang disimpan untuk tampilan "Dokumen dengan Sorotan".
# Cukup untuk naskah panjang, tanpa membengkakkan riwayat (jsonb).
_MAX_DOC_DISPLAY = 60_000


def _classify_match(
    sent: str,
    idx: int,
    best_ratio: float,
    quoted_spans: list[tuple[int, int]],
    cite_spans: list[tuple[int, int]],
    bib_start: int | None,
    run_words: int = 0,
) -> dict:
    """Tentukan kategori temuan berdasar atribusi + kekuatan kecocokan.

    `run_words` = panjang lari kata verbatim terpanjang di kalimat ini. Bila
    >= `_PHRASE_MIN_WORDS`, kalimat memuat fragmen yang disalin persis sehingga
    digolongkan `salinan_langsung` meski containment keseluruhannya rendah.
    """
    if idx < 0:
        quoted = cited = in_bib = False
    else:
        end = idx + len(sent)
        mid = idx + len(sent) // 2
        quoted = any(s <= mid <= e for s, e in quoted_spans)
        cited = any(s < end + 80 and e > idx for s, e in cite_spans)
        in_bib = bib_start is not None and idx >= bib_start
    # Dikutip DAN disitasi dengan benar → atribusi sah (bukan risiko).
    if cited and quoted:
        group = "sumber_terkredit"
    elif best_ratio >= _VERBATIM_AT:
        group = "salinan_langsung"
    elif run_words >= _PHRASE_MIN_WORDS:
        # Fragmen verbatim panjang di dalam kalimat = salinan langsung (parsial).
        group = "salinan_langsung"
    elif best_ratio >= _STRUCTURAL_AT:
        group = "kemiripan_kuat"
    else:
        group = "indikasi_parafrase"
    return {"quoted": quoted, "cited": cited, "in_bibliography": in_bib, "group": group}



def _shingles(words: list[str], n: int = _SHINGLE) -> set[str]:
    if len(words) < n:
        return {" ".join(words)} if words else set()
    return {" ".join(words[i : i + n]) for i in range(len(words) - n + 1)}


def _shingle_seq(words: list[str], n: int = _SHINGLE) -> list[str]:
    """Shingle BERURUTAN (list) — untuk mendeteksi lari verbatim beruntun.
    `set(_shingle_seq(w)) == _shingles(w)`.
    """
    if len(words) < n:
        return [" ".join(words)] if words else []
    return [" ".join(words[i : i + n]) for i in range(len(words) - n + 1)]


def _longest_shingle_run(seq: list[str], cset: set[str]) -> int:
    """Jumlah shingle beruntun terpanjang di `seq` yang ada di `cset`."""
    best = cur = 0
    for sh in seq:
        if sh in cset:
            cur += 1
            if cur > best:
                best = cur
        else:
            cur = 0
    return best


def _sentences(s: str) -> list[str]:
    return [m.group(0).strip() for m in _SENT_RE.finditer(s) if len(m.group(0).strip()) >= 20]


def _chunk_match(
    doc: str,
    candidates: list[dict],
    threshold: float = _MATCH_MIN,
    exclude: dict | None = None,
) -> dict:
    """Pencocokan tingkat-kalimat (tingkat kalimat) terhadap dokumen kandidat.

    Untuk tiap kalimat masukan, hitung containment shingle terhadap gabungan
    shingle tiap dokumen kandidat; kalimat dengan containment di atas ambang
    ditandai sebagai temuan dan diberi kategori sesuai kekuatan kecocokan.
    Indeks Integritas = proporsi karakter yang cocok, DIBOBOT per kategori
    (salinan penuh bobot 1.0, parsial/parafrase lebih kecil).

    `exclude` adalah pengaturan yang DIKUNCI saat cek dijalankan (dipilih user
    sebelum pengecekan): kecocokan yang dikecualikan tidak ikut menghitung
    Indeks Integritas maupun tampil sebagai temuan. Kunci yang didukung:
      - ``bibliography`` (bool): abaikan kecocokan di bagian daftar pustaka.
      - ``quotes`` (bool): abaikan kecocokan yang berada dalam tanda kutip.
      - ``min_source_percent`` (float): abaikan sumber yang kontribusinya
        kurang dari N% dokumen (0 = nonaktif).
    """
    exclude = exclude or {}
    ex_bib = bool(exclude.get("bibliography"))
    ex_quotes = bool(exclude.get("quotes"))
    min_pct = max(0.0, float(exclude.get("min_source_percent") or 0.0))

    cand_shingles: list[tuple[dict, set[str]]] = []
    for c in candidates:
        body = c.get("_fulltext") or ""
        if not body:
            continue
        words = [w.lower() for w in _WORD_RE.findall(body)]
        cand_shingles.append((c, _shingles(words)))

    sentences = _sentences(doc)
    total_chars = max(len(doc), 1)

    quoted_spans = [(m.start(), m.end()) for m in _QUOTE_RE.finditer(doc)]
    cite_spans = [(m.start(), m.end()) for m in _CITATION_RE.finditer(doc)]
    bib_m = _BIB_RE.search(doc)
    bib_start = bib_m.start() if bib_m else None
    low_doc = doc.lower()

    # Kumpulkan dulu seluruh kecocokan mentah; exclude diterapkan setelahnya
    # (ambang per-sumber butuh total kontribusi tiap sumber lebih dulu).
    raw: list[dict] = []
    for sent in sentences:
        words = [w.lower() for w in _WORD_RE.findall(sent)]
        sh_seq = _shingle_seq(words)
        sh = set(sh_seq)
        if not sh:
            continue
        sent_wc = max(len(words), 1)
        best_score = 0.0
        best_ratio = 0.0
        best_run_words = 0
        best_src: dict | None = None
        for c, cset in cand_shingles:
            if not cset:
                continue
            overlap = len(sh & cset)
            ratio = overlap / len(sh)
            run = _longest_shingle_run(sh_seq, cset)
            # Lari `run` shingle beruntun ≈ (run + n-1) kata verbatim, dibatasi
            # jumlah kata kalimat (kalimat pendek tak boleh dihitung berlebih).
            run_words = min(run + _SHINGLE - 1, len(words)) if run > 0 else 0
            run_cov = run_words / sent_wc
            score = max(ratio, run_cov)
            if score > best_score:
                best_score = score
                best_ratio = ratio
                best_run_words = run_words
                best_src = c
        qualifies = best_src is not None and (
            best_ratio >= threshold or best_run_words >= _PHRASE_MIN_WORDS
        )
        if qualifies:
            idx = doc.find(sent)
            if idx < 0:
                idx = low_doc.find(sent.lower())
            status = _classify_match(
                sent, idx, best_ratio, quoted_spans, cite_spans, bib_start,
                run_words=best_run_words,
            )
            # Porsi kalimat yang benar-benar tumpang-tindih: ambil yang lebih
            # besar antara containment keseluruhan dan cakupan fragmen verbatim,
            # agar pembobotan indeks proporsional terhadap teks yang identik.
            effective = max(best_ratio, best_run_words / sent_wc)
            skey = (best_src.get("doi") or best_src.get("title") or "").lower().strip()
            raw.append(
                {
                    "sent": sent,
                    "best_ratio": effective,
                    "verbatim_words": best_run_words,
                    "best_src": best_src,
                    "skey": skey,
                    "status": status,
                    "group": status["group"],
                }
            )

    # Terapkan exclude bibliografi/kutipan lebih dulu, lalu ambang per-sumber
    # dihitung dari sisa kecocokan (sumber yang hanya muncul di daftar pustaka
    # tak ikut terhitung).
    def _attrib_ok(m: dict) -> bool:
        if ex_bib and m["status"]["in_bibliography"]:
            return False
        if ex_quotes and m["status"]["quoted"]:
            return False
        return True

    kept = [m for m in raw if _attrib_ok(m)]

    excluded_sources: set[str] = set()
    if min_pct > 0:
        pre_chars: dict[str, float] = {}
        for m in kept:
            if m["skey"]:
                pre_chars[m["skey"]] = pre_chars.get(m["skey"], 0.0) + len(m["sent"])
        for key, chars in pre_chars.items():
            if chars / total_chars * 100 < min_pct:
                excluded_sources.add(key)
        if excluded_sources:
            kept = [m for m in kept if m["skey"] not in excluded_sources]

    matched: list[dict] = []
    weighted_chars = 0.0
    group_chars = {k: 0 for k in _MATCH_GROUP_ORDER}
    group_count = {k: 0 for k in _MATCH_GROUP_ORDER}
    source_contrib: dict[str, float] = {}
    for m in kept:
        sent = m["sent"]
        best_ratio = m["best_ratio"]
        best_src = m["best_src"]
        status = m["status"]
        grp = m["group"]
        group_chars[grp] += len(sent)
        group_count[grp] += 1
        # Kontribusi ke indeks: proporsi kalimat yang benar-benar cocok,
        # dibobot kategori — bukan seluruh panjang kalimat.
        weighted_chars += len(sent) * best_ratio * _GROUP_WEIGHT[grp]
        # Kontribusi per-sumber (porsi dokumen yang tersorot ke sumber ini) —
        # dipakai agar "Sumber Teratas" selaras dengan "Ringkasan Kecocokan".
        if m["skey"]:
            source_contrib[m["skey"]] = source_contrib.get(m["skey"], 0.0) + len(sent)
        matched.append(
            {
                "sentence": sent[:300],
                "match_ratio": round(best_ratio * 100, 1),
                "source_title": best_src.get("title"),
                "source_doi": best_src.get("doi"),
                "doc_id": best_src.get("doc_id"),
                "char_len": len(sent),
                "verbatim_words": m.get("verbatim_words", 0),
                "quoted": status["quoted"],
                "cited": status["cited"],
                "in_bibliography": status["in_bibliography"],
                "group": grp,
            }
        )

    # Indeks Integritas (leksikal berbobot): seberapa besar porsi dokumen yang
    # tumpang-tindih dengan korpus, menimbang kekuatan tiap kecocokan.
    integrity_index = round(weighted_chars / total_chars * 100, 1)
    matched.sort(key=lambda m: m["match_ratio"], reverse=True)
    match_groups = [
        {
            "type": k,
            "count": group_count[k],
            "percent": round(group_chars[k] / total_chars * 100, 1),
        }
        for k in _MATCH_GROUP_ORDER
    ]
    # Kontribusi per-sumber dalam persen dokumen (porsi tersorot).
    source_percent = {
        key: round(chars / total_chars * 100, 1) for key, chars in source_contrib.items()
    }
    return {
        "similarity_index": integrity_index,
        "matched_sentences": len(matched),
        "total_sentences": len(sentences),
        "matched_passages": matched[:50],
        "match_groups": match_groups,
        "source_percent": source_percent,
        "excluded_sources": excluded_sources,
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

# Pencarian teks-penuh langsung berdasarkan DOI (memakai index lower(doi)).
# Menjangkau SELURUH korpus — termasuk dokumen yang belum di-embed — sehingga
# paper terbit yang DOI-nya tertera di dokumen dapat dicocokkan teks-penuh
# (bukan sekadar abstrak), menghasilkan skor yang jujur (mendekati 100% untuk
# karya sendiri yang sudah terbit & terindeks).
_BY_DOI = text(
    """
    SELECT d.id, d.source, d.external_id, d.doi, d.title, d.pub_year,
           d.text_zstd, f.minhash
    FROM corpus_documents d
    LEFT JOIN corpus_fingerprints f ON f.doc_id = d.id
    WHERE lower(d.doi) = ANY(:dois)
    LIMIT :k
    """
)

_DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", re.UNICODE)


def _extract_dois(doc: str, limit: int = 8) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for m in _DOI_RE.finditer(doc):
        d = m.group(0).rstrip(".,);]").lower()
        if d not in seen:
            seen.add(d)
            out.append(d)
        if len(out) >= limit:
            break
    return out


# Heading daftar pustaka (EN/ID). DOI setelah heading ini adalah DOI REFERENSI
# yang dikutip — bukan identitas dokumen.
_REF_HEADING_RE = re.compile(
    r"(?im)^\s*(references|reference|bibliography|works\s+cited|literature\s+cited"
    r"|daftar\s+pustaka|daftar\s+rujukan|referensi|kepustakaan)\s*:?\s*$"
)
# Perkiraan panjang "halaman depan" (judul+penulis+abstrak). DOI milik makalah
# sendiri hampir selalu tercetak di sini.
_FRONT_MATTER_CHARS = 5000


def _extract_own_dois(doc: str) -> list[str]:
    """DOI milik dokumen SENDIRI (identitas publikasi), bukan DOI referensi.

    Hanya mengambil DOI dari front-matter: sebelum heading daftar pustaka DAN
    dalam ~halaman pertama. Ini mencegah salah-tandai ketika dokumen mengutip
    paper lain (yang DOI-nya ada di korpus) sebagai "publikasi terindeks".
    """
    m = _REF_HEADING_RE.search(doc)
    cut = m.start() if m else len(doc)
    front = doc[: min(cut, _FRONT_MATTER_CHARS)]
    return _extract_dois(front, limit=3)


def _front_matter(doc: str) -> str:
    """Potongan 'halaman depan' (judul+penulis+abstrak), sebelum daftar pustaka."""
    m = _REF_HEADING_RE.search(doc)
    cut = m.start() if m else len(doc)
    return doc[: min(cut, _FRONT_MATTER_CHARS)]


def _title_in_front_matter(source_title: str, front_shingles: set[str]) -> float:
    """Porsi (0..1) shingle-3 JUDUL sumber yang muncul di front-matter dokumen.

    Judul dokumen SENDIRI tercetak di halaman depan; judul paper yang hanya
    DIRUJUK muncul di daftar pustaka (di luar front-matter). Jadi kecocokan
    judul di front-matter = bukti kuat dokumen ADALAH publikasi itu, bukan
    sekadar mengutipnya. Tahan terhadap pemenggalan baris/hyphenation karena
    dibandingkan pada level shingle kata, bukan substring mentah.
    """
    tw = [w.lower() for w in _WORD_RE.findall(source_title or "")]
    if len(tw) < 6:
        return 0.0
    tsh = _shingles(tw, 3)
    if not tsh or not front_shingles:
        return 0.0
    return len(tsh & front_shingles) / len(tsh)


# Ambang kecocokan judul di front-matter untuk menyatakan identitas publikasi.
_TITLE_IDENTITY_MIN = 0.70


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


def _normalize_exclude(exclude: dict | None) -> dict:
    """Bakukan pengaturan Exclude yang dipilih user sebelum cek (dikunci)."""
    exclude = exclude or {}
    try:
        min_pct = max(0.0, min(100.0, float(exclude.get("min_source_percent") or 0.0)))
    except (TypeError, ValueError):
        min_pct = 0.0
    return {
        "bibliography": bool(exclude.get("bibliography")),
        "quotes": bool(exclude.get("quotes")),
        "min_source_percent": round(min_pct, 2),
    }


def check_plagiarism(
    doc: str,
    top_k: int = 30,
    extra_candidates: list[dict] | None = None,
    exclude: dict | None = None,
) -> dict:
    """Bandingkan `doc` dengan korpus; kembalikan laporan kemiripan.

    `extra_candidates` adalah kandidat sumber tambahan (mis. hasil Cek Sumber
    Daring tanpa-unduh) yang digabungkan ke pencocokan teks tingkat-kalimat
    sehingga Indeks Integritas mencakup korpus lokal + sumber daring sekaligus.
    Tiap kandidat minimal memuat `_fulltext` dan `title` (opsional `doi`,
    `url`, `source`, `pub_year`).

    `exclude` adalah pengaturan Exclude yang dipilih user SEBELUM pengecekan
    dan DIKUNCI pada hasil (tanpa daftar pustaka / tanpa kutipan / kecualikan
    sumber di bawah N%). Diterapkan di sisi server agar Indeks Integritas,
    daftar sumber, dan laporan konsisten di mana pun dibuka.
    """
    exclude_settings = _normalize_exclude(exclude)
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
    # DOI yang tertera di dokumen (mis. header paper terbit) + DOI dari kandidat
    # daring → pencocokan teks-penuh langsung ke korpus lokal (seluruh korpus,
    # termasuk yang belum di-embed).
    doi_wanted = set(_extract_dois(doc))
    for c in extra_candidates or []:
        d = (c.get("doi") or "").strip().lower()
        if d:
            doi_wanted.add(d)
    with engine.connect() as conn:
        _set_ef_search(conn, ef)
        for qv in qvecs:
            rows = conn.execute(_NEAREST, {"qvec": _vec_literal(qv), "k": per_k}).all()
            for r in rows:
                cs = float(r.cos_sim) if r.cos_sim is not None else 0.0
                cur = best.get(r.id)
                if cur is None or cs > cur["cos"]:
                    best[r.id] = {"row": r, "cos": cs}
        doi_rows = []
        if doi_wanted:
            doi_rows = conn.execute(
                _BY_DOI, {"dois": list(doi_wanted), "k": 50}
            ).all()
    ranked = sorted(best.values(), key=lambda x: x["cos"], reverse=True)[:top_k]
    # Dokumen hasil pencocokan DOI dimasukkan sebagai kandidat teks-penuh.
    # Skor semantiknya tidak dipalsukan (cos=0); copy_index tingkat-kalimat,
    # MinHash, dan reverse-containment yang menilai kemiripan sebenarnya.
    for r in doi_rows:
        if r.id not in best:
            ranked.append({"row": r, "cos": 0.0})

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

    # Kandidat sumber daring (tanpa-unduh) digabungkan ke pencocokan teks.
    online_sources: list[dict] = []
    for c in extra_candidates or []:
        body = c.get("_fulltext") or ""
        if not body or not c.get("title"):
            continue
        online_sources.append(
            {
                "doc_id": None,
                "source": c.get("source") or "daring",
                "external_id": None,
                "doi": c.get("doi"),
                "url": c.get("url"),
                "title": c.get("title"),
                "pub_year": c.get("pub_year"),
                "semantic_similarity": 0.0,
                "lexical_similarity": 0.0,
                "similarity": 0.0,
                "snippet": body[:320].strip(),
                "_fulltext": body,
                "online": True,
            }
        )

    # Pencocokan tingkat-kalimat (korpus lokal + sumber daring) untuk indeks.
    chunk = _chunk_match(doc, sources + online_sources, exclude=exclude_settings)

    # ── Deteksi Identitas Publikasi (reverse-containment + DOI) ──────────────
    # Indeks kemiripan mengukur "berapa % DOKUMEN termuat di sumber". Untuk
    # sumber daring yang hanya memaparkan ABSTRAK, angka itu kecil walau
    # dokumen adalah paper terbit itu sendiri. Dua sinyal identitas terpisah:
    #   1) reverse-containment: % teks SUMBER yang termuat di dokumen (abstrak
    #      paper sendiri ≈100% termuat), dan
    #   2) DOI-identity: dokumen MENYATAKAN DOI yang sama dengan sumber terbit —
    #      bukti kuat bahwa dokumen ADALAH karya terbit itu (atau duplikatnya).
    doc_words = [w.lower() for w in _WORD_RE.findall(doc)]
    doc_sh = _shingles(doc_words)
    doc_dois = set(_extract_own_dois(doc))
    front_words = [w.lower() for w in _WORD_RE.findall(_front_matter(doc))]
    front_sh = _shingles(front_words, 3)
    doi_pub: dict | None = None
    title_pub: dict | None = None
    contain_pub: dict | None = None
    for s in sources + online_sources:
        sdoi = (s.get("doi") or "").strip().lower()
        body = s.get("_fulltext") or ""
        swords = [w.lower() for w in _WORD_RE.findall(body)]
        containment = 0.0
        if len(swords) >= _PUBMATCH_MIN_WORDS:
            ssh = _shingles(swords)
            containment = len(ssh & doc_sh) / len(ssh) if ssh else 0.0
        s["source_containment"] = round(containment * 100, 1)
        s["doi_identity"] = bool(sdoi and sdoi in doc_dois)
        # Kecocokan judul sumber di front-matter dokumen = identitas publikasi.
        title_overlap = _title_in_front_matter(s.get("title") or "", front_sh)
        s["title_identity"] = bool(title_overlap >= _TITLE_IDENTITY_MIN)
        if s["doi_identity"] and doi_pub is None:
            doi_pub = {
                "title": s.get("title"),
                "doi": s.get("doi"),
                "url": s.get("url"),
                "source": s.get("source"),
                "containment": s["source_containment"],
                "online": bool(s.get("online")),
                "by_doi": True,
                "by_title": False,
            }
        if s["title_identity"] and (
            title_pub is None or title_overlap > title_pub["_overlap"]
        ):
            title_pub = {
                "title": s.get("title"),
                "doi": s.get("doi"),
                "url": s.get("url"),
                "source": s.get("source"),
                "containment": s["source_containment"],
                "online": bool(s.get("online")),
                "by_doi": False,
                "by_title": True,
                "_overlap": title_overlap,
            }
        # Reverse-containment tinggi HANYA dihitung sebagai identitas bila judul
        # sumber juga ada di front-matter — mencegah paper yang sekadar dirujuk
        # (abstraknya banyak dikutip) salah ditandai sebagai publikasi.
        # sumber juga ada di front-matter — ATAU sumber itu teks-PENUH OA.
        # Teks penuh yang ~separuhnya termuat di dokumen tak mungkin berasal
        # dari paper yang sekadar dirujuk (hanya abstraknya yang akan cocok),
        # jadi containment-tinggi atas teks penuh = identitas publikasi yang
        # andal meski judul tak terekstrak dari PDF (mis. header hilang).
        if (
            containment >= _PUBMATCH_MIN
            and (s["title_identity"] or s.get("fulltext_oa"))
            and (contain_pub is None or containment > contain_pub["containment"] / 100)
        ):
            contain_pub = {
                "title": s.get("title"),
                "doi": s.get("doi"),
                "url": s.get("url"),
                "source": s.get("source"),
                "containment": round(containment * 100, 1),
                "online": bool(s.get("online")),
                "by_doi": False,
                "by_title": bool(s["title_identity"]),
            }
    if title_pub is not None:
        title_pub.pop("_overlap", None)
    # Prioritas bukti identitas: DOI sendiri > judul di front-matter > containment.
    publication_match = doi_pub or title_pub or contain_pub

    # Skor tampilan tiap sumber = KONTRIBUSI NYATA ke dokumen (porsi tersorot),
    # BUKAN kemiripan topik (cosine). Ini membuat "Sumber Teratas" selaras
    # dengan "Ringkasan Kecocokan" dan menghapus angka 76% yang menyesatkan.
    contrib = chunk.get("source_percent", {})

    def _skey(s: dict) -> str:
        return (s.get("doi") or s.get("title") or "").lower().strip()

    for s in sources + online_sources:
        s["match_percent"] = contrib.get(_skey(s), 0.0)
        s["similarity"] = s["match_percent"]

    # Komponen parafrase/leksikal dihitung dari SELURUH kandidat (termasuk yang
    # nanti disembunyikan) agar deteksi parafrase tak hilang saat memfilter.
    all_local = [s for s in sources if not s.get("online")]
    lexical_doc = max((s["lexical_similarity"] for s in all_local), default=0.0)
    paraphrase = max((s["semantic_similarity"] for s in all_local), default=0.0)

    # Gabungkan & bersihkan, lalu HANYA tampilkan sumber yang benar-benar punya
    # kecocokan teks ( >0% ) atau teridentifikasi sebagai publikasi (DOI/abstrak
    # termuat). Sumber yang sekadar setopik (0% kecocokan) tidak ditampilkan.
    sources.extend(online_sources)
    for s in sources:
        s.pop("_fulltext", None)
    sources = [
        s
        for s in sources
        if s.get("match_percent", 0.0) > 0
        or s.get("doi_identity")
        or s.get("title_identity")
        or s.get("source_containment", 0.0) >= _CONTAIN_SHOW
    ]
    sources.sort(
        key=lambda s: (
            s.get("match_percent", 0.0),
            1.0 if (s.get("doi_identity") or s.get("title_identity")) else 0.0,
            s.get("source_containment", 0.0),
            s.get("semantic_similarity", 0.0),
        ),
        reverse=True,
    )
    # Komponen integritas:
    #  - copy_index     : tumpang-tindih teks berbobot tingkat-kalimat (sensitif,
    #                     mencakup salinan penuh + parsial + indikasi parafrase;
    #                     kini juga mencakup sumber daring).
    #  - lexical_doc    : kemiripan leksikal tingkat-dokumen (MinHash Jaccard,
    #                     korpus lokal saja — sumber daring lewat copy_index).
    #  - paraphrase     : kemiripan semantik tertinggi (parafrase kata diubah).
    copy_index = chunk["similarity_index"]
    # lexical_doc & paraphrase sudah dihitung di atas dari SELURUH kandidat
    # (sebelum sumber 0% disembunyikan) agar deteksi parafrase tetap utuh.
    # Kontribusi parafrase dikalibrasi konservatif: hanya kemiripan semantik
    # sangat tinggi yang menambah indeks, agar dokumen yang sekadar SETOPIK
    # tidak ikut terangkat (menghindari tuduhan palsu). cos 80%→0, 100%→~18%.
    paraphrase_component = round(max(0.0, paraphrase - 80.0) / 20.0 * 18.0, 1)
    # Indeks Integritas (gabungan) = tumpang-tindih teks + kontribusi parafrase.
    integrity_index = round(
        min(100.0, max(copy_index, lexical_doc) + paraphrase_component), 1
    )
    generated_at = datetime.now(timezone.utc)
    total_docs = _corpus_size()
    embedded_docs = embedded_corpus_size()
    semantic_coverage = round(embedded_docs / total_docs * 100, 1) if total_docs else 0.0
    return {
        "overall_similarity": integrity_index,
        "integrity_index": integrity_index,
        "exclude_settings": exclude_settings,
        "copy_similarity": copy_index,
        "document_lexical_similarity": lexical_doc,
        "paraphrase_similarity": paraphrase,
        "paraphrase_component": paraphrase_component,
        "publication_match": publication_match,
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
            "Deteksi salinan (leksikal) mencakup seluruh korpus akses-terbuka "
            "(penuh). Deteksi parafrase (semantik) mencakup bagian korpus yang "
            "telah di-embed; skor parafrase adalah batas bawah."
        ),
        "generated_at": generated_at.isoformat(timespec="seconds"),
    }
