"""Fitur ringan berbasis LLM: grammar, paraphrase, humanize, rewrite,
chat, grader, reader-reactions, resume-builder."""

from __future__ import annotations

import json
import re
from pathlib import Path

from app.services.llm.provider import get_llm

_JSON_RE = re.compile(r"\{.*\}|\[.*\]", re.DOTALL)

# --- Role "Profesor / evaluator ilmiah" untuk AI Chat topik akademik ---
# Dimuat dari berkas (dibundel bersama paket) agar mudah disunting tanpa ubah kode.
_ROLE_PROF_PATH = Path(__file__).with_name("role_prof.md")
try:
    _ROLE_PROF = _ROLE_PROF_PATH.read_text(encoding="utf-8").strip()
except Exception:
    _ROLE_PROF = ""

# Kata kunci penanda topik akademik/riset (ID + EN). Jika salah satu muncul pada
# pesan pengguna, AI Chat beralih ke role Profesor (advisor & reviewer ilmiah).
_ACADEMIC_KEYWORDS = {
    # Indonesia
    "penelitian", "riset", "jurnal", "naskah", "makalah", "paper", "abstrak",
    "metodologi", "metode penelitian", "hipotesis", "kebaruan", "sitasi",
    "kutipan", "variabel", "dataset", "data set", "revisi", "reviewer",
    "publikasi", "literatur", "pustaka", "tinjauan pustaka", "kerangka teori",
    "rumusan masalah", "tujuan penelitian", "kontribusi", "skripsi", "tesis",
    "disertasi", "eksperimen", "statistik", "signifikansi", "baseline",
    "ablation", "ablasi", "temuan", "simpulan", "kesimpulan", "diskusi",
    "metode", "analisis data", "pembahasan", "latar belakang", "state of the art",
    # Inggris
    "research", "journal", "manuscript", "abstract", "methodology", "method",
    "hypothesis", "novelty", "citation", "literature", "related work",
    "experiment", "benchmark", "statistical", "significance",
    "contribution", "thesis", "dissertation", "peer review", "publication",
    "scopus", "sota", "ablation study", "validity", "robustness",
    "methods", "results", "discussion", "introduction", "conclusion",
    "research gap", "research question", "findings", "framework", "doi",
    "p-value", "confusion matrix", "cross-validation", "overfitting",
}


def _is_academic(text: str) -> bool:
    """Deteksi apakah teks pengguna menyangkut topik akademik/riset."""
    low = (text or "").lower()
    # Frasa multi-kata dicek via substring; kata tunggal via batas kata.
    for kw in _ACADEMIC_KEYWORDS:
        if " " in kw or "-" in kw:
            if kw in low:
                return True
        elif re.search(rf"\b{re.escape(kw)}\b", low):
            return True
    return False


def _academic_chat_prompt() -> str:
    """System prompt role Profesor + aturan operasional AI Chat."""
    guard = (
        "Anda bertindak sebagai dosen/profesor & evaluator ilmiah pada AI Chat "
        "ICALORA-LABS. Terapkan peran-peran di bawah SESUAI kebutuhan topik "
        "(tidak semua sekaligus). Jawab dalam bahasa yang sama dengan pengguna, "
        "kritis, ringkas, terstruktur, dan berbasis bukti. Jangan mengarang DOI, "
        "data, hasil, atau sitasi, dan jangan membuat klaim kebaruan/SOTA tanpa "
        "dukungan bukti.\n\n"
    )
    return guard + _ROLE_PROF if _ROLE_PROF else guard


def chat(messages: list[dict], system: str | None = None) -> dict:
    """AI Chat: asisten tulis akademik multi-giliran berbasis LLM lokal.

    Bila pengguna membahas topik akademik/riset, aktifkan role "Profesor /
    evaluator ilmiah" (docs/ROLE-PROFF.md) secara otomatis; selain itu gunakan
    asisten umum. `system` eksplisit (bila diberikan) selalu diprioritaskan.
    """
    llm = get_llm()
    user_text = " ".join(
        (m.get("content") or "") for m in messages if m.get("role") == "user"
    )
    if system:
        sys_prompt = system
    elif _is_academic(user_text):
        sys_prompt = _academic_chat_prompt()
    else:
        sys_prompt = (
            "Anda adalah asisten penulisan akademik ICALORA-LABS. Jawab dengan jelas, "
            "akurat, dan dalam bahasa yang sama dengan pengguna. Bantu menulis, merangkum, "
            "menjelaskan, dan menyusun argumen secara ilmiah."
        )
    convo = [{"role": "system", "content": sys_prompt}]
    for m in messages[-20:]:
        role = m.get("role")
        content = (m.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            convo.append({"role": role, "content": content})
    reply = llm.chat(convo, temperature=0.5, max_tokens=1024)
    return {"reply": reply}


def _extract_json(raw: str):
    """Ambil objek/array JSON pertama yang VALID dari balasan LLM.

    Toleran terhadap teks tambahan sebelum/sesudah JSON, blok ```json, maupun
    beberapa blok. Dulu memakai regex rakus `\\{.*\\}` yang menyambung dari `{`
    pertama ke `}` terakhir — bila LLM menulis prosa + JSON + teks lanjutan,
    hasilnya malah gagal di-parse walau ada objek valid. Kini memakai
    `json.JSONDecoder().raw_decode` yang berhenti di akhir objek valid pertama.
    """
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.IGNORECASE).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    decoder = json.JSONDecoder()
    # Coba dekode dari tiap posisi kurung pembuka; ambil JSON valid pertama.
    for i, ch in enumerate(raw):
        if ch in "{[":
            try:
                obj, _end = decoder.raw_decode(raw[i:])
                return obj
            except json.JSONDecodeError:
                continue
    # Fallback terakhir: regex rakus (biar perilaku lama tetap ada).
    m = _JSON_RE.search(raw)
    if m:
        return json.loads(m.group(0))
    raise json.JSONDecodeError("tidak ada JSON valid", raw, 0)


def _clamp_score(val, lo: float = 0.0, hi: float = 100.0):
    """Batasi skor numerik dari LLM ke rentang [lo, hi]; None bila bukan angka."""
    try:
        return max(lo, min(hi, float(val))) if val is not None else None
    except (TypeError, ValueError):
        return None


def _text_metrics(text: str) -> dict:
    """Metrik tulisan deterministik (dihitung di Python, bukan LLM)."""
    chars = len(text)
    words = len(re.findall(r"\w+", text, flags=re.UNICODE))
    sent_terminators = len(re.findall(r"[.!?]+(?=\s|$)", text))
    sentences = sent_terminators if sent_terminators else (1 if words else 0)
    return {
        "characters": chars,
        "words": words,
        "sentences": sentences,
        "reading_time_min": round(words / 200, 1),
        "speaking_time_min": round(words / 130, 1),
    }


_WRITING_CATEGORIES = {"Ketepatan", "Kejelasan", "Keterlibatan", "Penyampaian"}


def _norm_for_match(s: str) -> str:
    """Normalisasi untuk pencocokan toleran: lipat spasi, huruf kecil, buang
    tanda kutip tipografis yang sering diubah LLM."""
    s = s.replace("\u2019", "'").replace("\u2018", "'")
    s = s.replace("\u201c", '"').replace("\u201d", '"')
    s = s.replace("\u2013", "-").replace("\u2014", "-")
    return re.sub(r"\s+", " ", s).strip().lower()


def _original_in_text(original: str, text_norm: str) -> bool:
    """True jika potongan 'original' dari LLM benar-benar ada di teks pengguna.
    Mencegah issue halusinasi (menuduh kesalahan yang tak pernah ditulis user)."""
    o = _norm_for_match(original)
    if not o:
        return False
    if o in text_norm:
        return True
    # Toleran terhadap perbedaan tanda baca (LLM sering menghilangkan tanda kutip/
    # koma): bandingkan versi yang hanya menyisakan kata & spasi.
    def _alnum(s: str) -> str:
        return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", s)).strip()

    o_alnum = _alnum(o)
    text_alnum = _alnum(text_norm)
    if o_alnum and o_alnum in text_alnum:
        return True
    # Toleransi: jika LLM memberi potongan panjang, cek sub-frasa inti (>=6 kata)
    words = o_alnum.split()
    if len(words) >= 6:
        core = " ".join(words[:6])
        return core in text_alnum
    return False


def _normalize_issue(raw: dict, text_norm: str | None = None) -> dict | None:
    original = str(raw.get("original") or "").strip()
    suggestion = str(raw.get("suggestion") or "").strip()
    if not original and not suggestion:
        return None
    # Verifikasi deterministik: buang issue yang 'original'-nya tidak ada di teks
    # (halusinasi LLM). Hanya diterapkan bila original non-kosong & teks diberikan.
    if text_norm is not None and original and not _original_in_text(original, text_norm):
        return None
    category = str(raw.get("category") or "").strip().title()
    if category not in _WRITING_CATEGORIES:
        category = "Ketepatan"
    severity = str(raw.get("severity") or "").strip().lower()
    if severity not in {"critical", "advanced"}:
        severity = "advanced"
    return {
        "category": category,
        "severity": severity,
        "original": original[:400],
        "suggestion": suggestion[:400],
        "explanation": str(raw.get("explanation") or "").strip()[:400],
    }


_GRAMMAR_SYSTEM = (
    "Anda editor bahasa akademik. Perbaiki ejaan, tata bahasa, dan tanda "
    "baca tanpa mengubah makna atau bahasa asli teks. Periksa SELURUH bagian "
    "yang diberikan secara teliti dan laporkan SEMUA kesalahan yang Anda temukan "
    "(jangan berhenti setelah beberapa). Balas HANYA JSON valid dengan bentuk: "
    "{\"corrected\": \"<teks hasil perbaikan lengkap>\", "
    "\"issues\": [{\"category\": \"Ketepatan|Kejelasan|Keterlibatan|Penyampaian\", "
    "\"severity\": \"critical|advanced\", \"original\": \"<potongan asli>\", "
    "\"suggestion\": \"<perbaikan>\", \"explanation\": \"<alasan singkat>\"}]}. "
    "Gunakan 'critical' untuk kesalahan yang mengubah makna/ejaan fatal, "
    "'advanced' untuk perbaikan gaya. Jangan tambahkan teks di luar JSON."
)

# Satu chunk ditahan cukup kecil agar model fokus dan recall-nya tinggi (model
# cenderung under-report bila diberi teks sangat panjang sekaligus).
_GRAMMAR_CHUNK_CHARS = 6000
# num_ctx TETAP untuk semua chunk: chunk <=6000 char (~2000 token) + output muat
# nyaman di 8192. Memakai nilai tetap mencegah Ollama memuat-ulang model tiap
# panggilan (reload terjadi bila num_ctx berubah antar-panggilan).
_GRAMMAR_NUM_CTX = 8192
# Timeout per panggilan chunk (detik). Longgar agar tahan cold-load model di GPU
# bersama; job async punya deadline keseluruhan sendiri (20 menit).
_GRAMMAR_CALL_TIMEOUT = 300.0
# Batas atas issue yang disimpan (praktis tak terbatas; hanya pengaman payload).
_GRAMMAR_ISSUE_CAP = 2000


def _grammar_chunks(text: str, limit: int = _GRAMMAR_CHUNK_CHARS) -> list[str]:
    """Pecah teks menjadi segmen <= limit karakter pada batas paragraf/kalimat,
    tanpa membuang apa pun (seluruh dokumen diperiksa)."""
    if len(text) <= limit:
        return [text] if text.strip() else []
    # Unit dasar: paragraf; paragraf yang terlalu besar dipecah per kalimat.
    units: list[str] = []
    for para in re.split(r"\n\s*\n", text):
        if len(para) <= limit:
            units.append(para)
            continue
        buf = ""
        for sent in re.split(r"(?<=[.!?])\s+", para):
            if len(sent) > limit:
                # Kalimat raksasa (mis. tabel/daftar) — pecah keras per limit.
                for i in range(0, len(sent), limit):
                    units.append(sent[i : i + limit])
                continue
            if len(buf) + len(sent) + 1 > limit:
                if buf:
                    units.append(buf)
                buf = sent
            else:
                buf = f"{buf} {sent}".strip()
        if buf:
            units.append(buf)
    # Gabungkan unit kecil hingga mendekati limit agar jumlah panggilan minimal.
    chunks: list[str] = []
    cur = ""
    for u in units:
        if len(cur) + len(u) + 2 > limit:
            if cur.strip():
                chunks.append(cur)
            cur = u
        else:
            cur = f"{cur}\n\n{u}" if cur else u
    if cur.strip():
        chunks.append(cur)
    return chunks


def _grammar_check_chunk(llm, chunk: str) -> tuple[str, list[dict]]:
    """Periksa satu chunk; kembalikan (teks_terkoreksi, daftar_issue).

    Memakai num_ctx tetap agar model tidak dimuat-ulang antar-panggilan. Bila
    panggilan gagal (mis. timeout saat model dingin), coba ulang sekali; bila
    tetap gagal, kembalikan teks asli chunk tanpa issue agar seluruh job tidak
    ikut gagal hanya karena satu bagian.
    """
    messages = [
        {"role": "system", "content": _GRAMMAR_SYSTEM},
        {"role": "user", "content": chunk},
    ]
    max_out = max(1024, min(6144, int(len(chunk) // 3 * 1.8) + 512))
    raw = ""
    for attempt in range(2):
        try:
            raw = llm.chat(
                messages, temperature=0.1, max_tokens=max_out,
                num_ctx=_GRAMMAR_NUM_CTX, timeout=_GRAMMAR_CALL_TIMEOUT,
            )
            break
        except Exception:  # noqa: BLE001 — timeout/5xx sesaat; coba ulang lalu lewati
            if attempt == 0:
                continue
            return chunk, []

    corrected = chunk
    issues: list[dict] = []
    chunk_norm = _norm_for_match(chunk)
    try:
        data = _extract_json(raw)
        if isinstance(data, dict):
            corrected = str(data.get("corrected") or "").strip() or chunk
            for item in data.get("issues") or []:
                if isinstance(item, dict):
                    norm = _normalize_issue(item, chunk_norm)
                    if norm:
                        issues.append(norm)
    except (json.JSONDecodeError, ValueError):
        corrected = raw.strip() or chunk
    return corrected, issues


def grammar_check(text: str) -> dict:
    """Pemeriksaan tata bahasa menyeluruh. Dokumen panjang dipecah menjadi
    beberapa chunk agar tidak dipotong/under-report, lalu hasilnya digabung."""
    llm = get_llm()
    chunks = _grammar_chunks(text)

    corrected_parts: list[str] = []
    issues: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for chunk in chunks:
        c_corr, c_issues = _grammar_check_chunk(llm, chunk)
        corrected_parts.append(c_corr)
        for it in c_issues:
            key = (it["original"].lower(), it["suggestion"].lower())
            if key in seen:
                continue
            seen.add(key)
            issues.append(it)
            if len(issues) >= _GRAMMAR_ISSUE_CAP:
                break
        if len(issues) >= _GRAMMAR_ISSUE_CAP:
            break

    corrected = "\n\n".join(corrected_parts).strip() or text
    metrics = _text_metrics(text)
    critical = sum(1 for i in issues if i["severity"] == "critical")
    advanced = len(issues) - critical

    points = critical * 3 + advanced
    # Skor menurun seiring kepadatan masalah, tetapi tetap adil untuk teks pendek:
    # 0 masalah -> 100; makin banyak poin relatif jumlah kata, makin rendah.
    score = max(0, min(100, round(100 * metrics["words"] / max(1, metrics["words"] + 2 * points))))

    return {
        "corrected": corrected,
        "metrics": metrics,
        "score": score,
        "issues": issues,
        "issue_summary": {
            "total": len(issues),
            "critical": critical,
            "advanced": advanced,
        },
        "chunks": len(chunks),
    }


# --- Transformasi teks panjang (parafrase/humanize/rewrite/perbaikan) ---------
# Alat transformasi menghasilkan teks baru sepanjang input. Sama seperti grammar,
# tanpa chunking + num_ctx dokumen panjang DIPOTONG diam-diam (input ~4k token)
# dan output pun terpotong. Di sini dokumen dipecah, tiap bagian ditransformasi,
# lalu hasilnya dirangkai urut tanpa kehilangan teks.
_TRANSFORM_CHUNK_CHARS = 4000  # input+output per chunk harus muat di num_ctx
_TRANSFORM_NUM_CTX = 8192      # tetap antar-panggilan agar model tak dimuat-ulang
_TRANSFORM_CALL_TIMEOUT = 300.0


def _transform_chunk(llm, system: str, chunk: str, temperature: float) -> str:
    """Transformasi satu chunk; num_ctx tetap, timeout longgar, 1 retry lalu
    kembalikan teks asli chunk bila gagal agar seluruh job tak ikut gagal."""
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": chunk},
    ]
    # Output bisa sedikit lebih panjang dari input; beri ruang num_predict cukup.
    max_out = max(1024, min(6144, int(len(chunk) // 3 * 1.9) + 512))
    for attempt in range(2):
        try:
            out = llm.chat(
                messages, temperature=temperature, max_tokens=max_out,
                num_ctx=_TRANSFORM_NUM_CTX, timeout=_TRANSFORM_CALL_TIMEOUT,
            )
            return out.strip() or chunk
        except Exception:  # noqa: BLE001 — timeout/5xx sesaat; coba ulang lalu lewati
            if attempt == 0:
                continue
            return chunk
    return chunk


def _llm_transform_long(system: str, text: str, *, temperature: float) -> str:
    """Transformasi teks panjang menyeluruh (dipecah per-chunk, tanpa kehilangan
    teks). Dokumen pendek tetap satu panggilan."""
    llm = get_llm()
    chunks = _grammar_chunks(text, limit=_TRANSFORM_CHUNK_CHARS)
    if not chunks:
        return ""
    parts = [_transform_chunk(llm, system, c, temperature) for c in chunks]
    return "\n\n".join(parts).strip()


PARAPHRASE_STYLES = {
    "standar": "standar dan netral",
    "formal": "formal dan baku",
    "akademik": "akademik dan ilmiah",
    "sederhana": "sederhana dan mudah dipahami",
    "kreatif": "kreatif dan bervariasi",
}


def paraphrase(text: str, style: str = "standar") -> dict:
    key = (style or "").strip().lower()
    if key not in PARAPHRASE_STYLES:
        key = "standar"
    desc = PARAPHRASE_STYLES[key]
    system = (
        f"Parafrasekan teks pengguna dengan gaya {desc}, pertahankan makna "
        "dan bahasa aslinya. Balas HANYA hasil parafrase."
    )
    result = _llm_transform_long(system, text, temperature=0.7)
    return {"result": result, "style": key}


def humanize(text: str) -> dict:
    system = (
        "Tulis ulang teks agar terdengar lebih alami dan manusiawi: variasikan "
        "panjang kalimat, kurangi pola kaku, pertahankan makna dan bahasa asli. "
        "Balas HANYA hasil tulisan ulang."
    )
    result = _llm_transform_long(system, text, temperature=0.8)
    return {"result": result}


# Gaya penulisan ulang yang didukung AI Rewriter
REWRITE_TONES = {
    "formal": "formal dan profesional",
    "akademik": "akademik dan ilmiah",
    "kasual": "santai dan ramah",
    "ringkas": "ringkas dan padat",
    "persuasif": "persuasif dan meyakinkan",
    "sederhana": "sederhana dan mudah dipahami",
}


def rewrite(text: str, tone: str = "formal") -> dict:
    """AI Rewriter: rombak gaya tulisan sesuai nada yang dipilih."""
    key = (tone or "").strip().lower()
    if key not in REWRITE_TONES:
        key = "formal"
    desc = REWRITE_TONES[key]
    system = (
        f"Tulis ulang teks pengguna dengan gaya {desc}. Pertahankan makna inti "
        "dan bahasa asli teks. Balas HANYA hasil tulisan ulang tanpa penjelasan."
    )
    result = _llm_transform_long(system, text, temperature=0.7)
    return {"result": result, "tone": tone}


def grade_essay(text: str, rubric: str | None = None) -> dict:
    """AI Grader: nilai esai dengan rubrik otomatis (0-100 per kriteria)."""
    llm = get_llm()
    rubric_line = (
        f"Gunakan rubrik khusus berikut: {rubric}."
        if rubric
        else "Gunakan rubrik umum: Isi & Argumen, Struktur & Organisasi, "
        "Tata Bahasa & Gaya, Orisinalitas & Kedalaman."
    )
    messages = [
        {
            "role": "system",
            "content": (
                "Anda penilai esai akademik. " + rubric_line + " Nilai esai pengguna. "
                "Jawab dalam bahasa yang sama dengan esai pengguna. "
                "Balas HANYA JSON valid dengan bentuk: "
                '{"overall_score": <0-100>, "grade": "<A/B/C/D/E>", '
                '"criteria": [{"name": "<nama>", "score": <0-100>, '
                '"feedback": "<umpan balik singkat>"}], '
                '"summary": "<ringkasan evaluasi 1-2 kalimat>", '
                '"suggestions": ["<saran perbaikan>", ...]}'
            ),
        },
        {"role": "user", "content": text},
    ]
    raw = llm.chat(messages, temperature=0.2, max_tokens=1200)
    fallback = {
        "overall_score": None,
        "grade": None,
        "criteria": [],
        "summary": raw[:500],
        "suggestions": [],
    }
    try:
        data = _extract_json(raw)
    except json.JSONDecodeError:
        return fallback
    # Validasi bentuk: LLM kadang mengembalikan list atau kunci tak lengkap.
    # Normalkan ke skema yang dijanjikan agar frontend tak menerima bentuk asing.
    if not isinstance(data, dict):
        return fallback
    score = data.get("overall_score")
    try:
        score = max(0.0, min(100.0, float(score))) if score is not None else None
    except (TypeError, ValueError):
        score = None
    criteria = data.get("criteria")
    criteria = [c for c in criteria if isinstance(c, dict)] if isinstance(criteria, list) else []
    # Clamp skor tiap kriteria ke 0-100 agar frontend tidak menerima nilai liar.
    for c in criteria:
        cs = c.get("score")
        try:
            c["score"] = max(0.0, min(100.0, float(cs))) if cs is not None else None
        except (TypeError, ValueError):
            c["score"] = None
    suggestions = data.get("suggestions")
    suggestions = (
        [str(s) for s in suggestions if s] if isinstance(suggestions, list) else []
    )
    return {
        "overall_score": score,
        "grade": data.get("grade") if isinstance(data.get("grade"), str) else None,
        "criteria": criteria,
        "summary": str(data.get("summary") or raw[:500]),
        "suggestions": suggestions,
    }


def reader_reactions(text: str) -> dict:
    """Reader Reactions: prediksi reaksi beberapa persona pembaca."""
    llm = get_llm()
    messages = [
        {
            "role": "system",
            "content": (
                "Prediksi bagaimana beragam pembaca akan bereaksi terhadap teks pengguna. "
                "Jawab dalam bahasa yang sama dengan teks pengguna. "
                "Balas HANYA JSON valid: "
                '{"reactions": [{"persona": "<tipe pembaca>", '
                '"reaction": "<reaksi singkat>", "sentiment": "<positif/netral/negatif>"}], '
                '"overall_sentiment": "<positif/netral/negatif>", '
                '"clarity_score": <0-100>, "engagement_score": <0-100>, '
                '"summary": "<ringkasan 1 kalimat>"}'
            ),
        },
        {"role": "user", "content": text},
    ]
    raw = llm.chat(messages, temperature=0.4, max_tokens=900)
    fallback = {
        "reactions": [],
        "overall_sentiment": None,
        "clarity_score": None,
        "engagement_score": None,
        "summary": raw[:500],
    }
    try:
        data = _extract_json(raw)
    except json.JSONDecodeError:
        return fallback
    if not isinstance(data, dict):
        return fallback
    reactions = data.get("reactions")
    reactions = [r for r in reactions if isinstance(r, dict)] if isinstance(reactions, list) else []
    return {
        "reactions": reactions,
        "overall_sentiment": (
            data.get("overall_sentiment")
            if isinstance(data.get("overall_sentiment"), str)
            else None
        ),
        "clarity_score": _clamp_score(data.get("clarity_score")),
        "engagement_score": _clamp_score(data.get("engagement_score")),
        "summary": str(data.get("summary") or raw[:500]),
    }


def build_resume(info: str, target_role: str | None = None) -> dict:
    """Resume Builder: susun CV profesional (Markdown) dari informasi mentah."""
    llm = get_llm()
    role_line = f" Sesuaikan untuk posisi: {target_role}." if target_role else ""
    messages = [
        {
            "role": "system",
            "content": (
                "Anda penulis CV profesional. Dari informasi pengguna, susun CV yang rapi "
                "dalam format Markdown (judul nama, kontak, Ringkasan, Pengalaman, "
                "Pendidikan, Keahlian, dll. jika tersedia). Gunakan bahasa yang sama dengan "
                "pengguna. Jangan mengarang data yang tidak diberikan." + role_line + " "
                "Balas HANYA isi CV dalam Markdown."
            ),
        },
        {"role": "user", "content": info},
    ]
    result = llm.chat(messages, temperature=0.4, max_tokens=1200)
    return {"resume_markdown": result, "target_role": target_role}


def _toc_source(text: str, max_chars: int = 24000) -> str:
    """Padatkan dokumen panjang menjadi sumber TOC (baris-baris judul).

    Dokumen bisa puluhan ribu karakter; mengirim utuh ke LLM lambat/timeout.
    Untuk daftar isi kita hanya butuh struktur, jadi kita ambil baris yang
    berpotensi judul di seluruh dokumen, lalu batasi panjangnya.
    """
    if len(text) <= max_chars:
        return text

    num_re = re.compile(r"^\s*(?:bab|chapter|bagian|part)\b", re.IGNORECASE)
    dotted_re = re.compile(r"^\s*\d+(?:\.\d+)*[\.\)]?\s+\S")
    lines = text.splitlines()
    candidates: list[str] = []
    for ln in lines:
        s = ln.strip()
        if not s or len(s) > 120:
            continue
        words = s.split()
        is_heading = (
            num_re.match(s)
            or dotted_re.match(s)
            or (s.isupper() and len(words) >= 1)
            or (len(s) <= 70 and s == s.title())
            or len(words) <= 8
        )
        if is_heading:
            candidates.append(s)

    condensed = "\n".join(candidates) if len(candidates) >= 3 else text
    return condensed[:max_chars]


def generate_toc(text: str) -> dict:
    """Buat Daftar Isi Otomatis: susun struktur bab/sub-bab dari dokumen."""
    llm = get_llm()
    source = _toc_source(text)
    messages = [
        {
            "role": "system",
            "content": (
                "Anda penyusun struktur dokumen akademik. Dari isi dokumen pengguna, "
                "susun Daftar Isi berjenjang (bab & sub-bab). "
                "Jawab dalam bahasa yang sama dengan dokumen pengguna. "
                "Balas HANYA JSON valid: "
                '{"entries": [{"level": <1-3>, "title": "<judul>", '
                '"number": "<1 / 1.1 / 1.1.1>"}], "markdown": "<daftar isi dalam Markdown>"}'
            ),
        },
        {"role": "user", "content": source},
    ]
    raw = llm.chat(messages, temperature=0.2, max_tokens=1200, num_ctx=_TRANSFORM_NUM_CTX)
    try:
        data = _extract_json(raw)
    except json.JSONDecodeError:
        return {"entries": [], "markdown": raw[:1500]}
    if not isinstance(data, dict):
        return {"entries": [], "markdown": raw[:1500]}
    entries = data.get("entries")
    clean: list[dict] = []
    if isinstance(entries, list):
        for e in entries:
            if not isinstance(e, dict):
                continue
            try:
                lvl = int(e.get("level", 1))
            except (TypeError, ValueError):
                lvl = 1
            clean.append({
                "level": max(1, min(3, lvl)),
                "title": str(e.get("title") or "").strip(),
                "number": str(e.get("number") or "").strip(),
            })
    return {"entries": clean, "markdown": str(data.get("markdown") or raw[:1500])}


def improve_document(text: str, goal: str | None = None) -> dict:
    """Perbaikan Dokumen: sunting dokumen agar lebih jelas, rapi, dan baku."""
    goal_line = f" Fokus perbaikan: {goal}." if goal else ""
    system = (
        "Anda editor akademik profesional. Perbaiki dokumen pengguna: tata bahasa, "
        "kejelasan, alur, dan gaya baku — tanpa mengubah makna, data, atau bahasa "
        "asli." + goal_line + " Balas HANYA teks dokumen hasil perbaikan."
    )
    improved = _llm_transform_long(system, text, temperature=0.3)
    return {"improved": improved, "goal": goal}


def _select_context(context: str, question: str, budget: int = 12000) -> str:
    """Pilih bagian dokumen paling relevan dengan pertanyaan (retrieval ringan).

    Untuk dokumen panjang, mengirim hanya 12k char pertama membuat pertanyaan
    tentang halaman akhir gagal dijawab. Di sini dokumen dibagi menjadi potongan
    lalu diberi skor berdasarkan tumpang-tindih kata dengan pertanyaan terakhir;
    potongan ber-skor tertinggi dirangkai (urut dokumen) sampai mendekati budget.
    Tanpa embedding/GPU sehingga cepat & deterministik.
    """
    context = context or ""
    if len(context) <= budget:
        return context
    terms = {t for t in re.findall(r"\w+", (question or "").lower()) if len(t) > 2}
    # Potongan ~1200 char dengan sedikit tumpang-tindih antar-batas kalimat.
    chunk_len = 1200
    chunks = [context[i : i + chunk_len] for i in range(0, len(context), chunk_len)]
    if not terms:
        # Tanpa kata kunci: ambil awal + akhir dokumen agar konteks tetap luas.
        head = context[: budget // 2]
        tail = context[-(budget - len(head)) :]
        return head + "\n…\n" + tail
    scored = []
    for idx, ch in enumerate(chunks):
        low = ch.lower()
        score = sum(low.count(t) for t in terms)
        scored.append((score, idx, ch))
    # Ambil potongan ber-skor tertinggi, lalu susun ulang sesuai urutan dokumen.
    scored.sort(key=lambda x: x[0], reverse=True)
    picked: list[tuple[int, str]] = []
    total = 0
    for score, idx, ch in scored:
        if score == 0 and picked:
            break
        if total + len(ch) > budget and picked:
            break
        picked.append((idx, ch))
        total += len(ch)
        if total >= budget:
            break
    if not picked:
        return context[:budget]
    picked.sort(key=lambda x: x[0])
    return "\n…\n".join(ch for _, ch in picked)


def doc_chat(context: str, messages: list[dict]) -> dict:
    """Chat PDF/Dokumen: tanya-jawab berdasarkan isi dokumen yang diunggah."""
    llm = get_llm()
    last_q = ""
    for m in reversed(messages):
        if m.get("role") == "user" and (m.get("content") or "").strip():
            last_q = m["content"].strip()
            break
    selected = _select_context(context or "", last_q)
    truncated = len(selected) < len(context or "")
    note = (
        "\n\nCATATAN: dokumen panjang, hanya bagian paling relevan dengan "
        "pertanyaan yang ditampilkan di atas. Bila jawaban mungkin ada di bagian "
        "lain, minta pengguna mempersempit/menegaskan pertanyaannya."
        if truncated
        else ""
    )
    sys_prompt = (
        "Anda asisten yang menjawab pertanyaan HANYA berdasarkan dokumen berikut. "
        "Jika jawaban tidak ada dalam dokumen, katakan terus terang. Gunakan bahasa "
        "yang sama dengan pengguna.\n\n=== DOKUMEN ===\n" + selected + "\n=== AKHIR ===" + note
    )
    convo = [{"role": "system", "content": sys_prompt}]
    for m in messages[-12:]:
        role = m.get("role")
        content = (m.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            convo.append({"role": role, "content": content})
    reply = llm.chat(convo, temperature=0.3, max_tokens=1024)
    return {"reply": reply, "context_truncated": truncated}
