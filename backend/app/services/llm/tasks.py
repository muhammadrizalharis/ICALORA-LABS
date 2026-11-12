"""Fitur ringan berbasis LLM: grammar, paraphrase, humanize, rewrite,
chat, grader, reader-reactions, resume-builder."""

from __future__ import annotations

import json
import re

from app.services.llm.provider import get_llm

_JSON_RE = re.compile(r"\{.*\}|\[.*\]", re.DOTALL)


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


def _normalize_issue(raw: dict) -> dict | None:
    original = str(raw.get("original") or "").strip()
    suggestion = str(raw.get("suggestion") or "").strip()
    if not original and not suggestion:
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


def grammar_check(text: str) -> dict:
    llm = get_llm()
    messages = [
        {
            "role": "system",
            "content": (
                "Anda editor bahasa akademik. Perbaiki ejaan, tata bahasa, dan tanda "
                "baca tanpa mengubah makna atau bahasa asli teks. Balas HANYA JSON valid "
                "dengan bentuk: {\"corrected\": \"<teks hasil perbaikan lengkap>\", "
                "\"issues\": [{\"category\": \"Ketepatan|Kejelasan|Keterlibatan|Penyampaian\", "
                "\"severity\": \"critical|advanced\", \"original\": \"<potongan asli>\", "
                "\"suggestion\": \"<perbaikan>\", \"explanation\": \"<alasan singkat>\"}]}. "
                "Gunakan 'critical' untuk kesalahan yang mengubah makna/ejaan fatal, "
                "'advanced' untuk perbaikan gaya. Jangan tambahkan teks di luar JSON."
            ),
        },
        {"role": "user", "content": text},
    ]
    raw = llm.chat(messages, temperature=0.1)

    corrected = text
    issues: list[dict] = []
    try:
        data = _extract_json(raw)
        if isinstance(data, dict):
            corrected = str(data.get("corrected") or "").strip() or text
            for item in data.get("issues") or []:
                if isinstance(item, dict):
                    norm = _normalize_issue(item)
                    if norm:
                        issues.append(norm)
    except (json.JSONDecodeError, ValueError):
        # LLM tidak mengembalikan JSON valid — pakai balasannya sebagai teks perbaikan.
        corrected = raw.strip() or text

    issues = issues[:40]
    metrics = _text_metrics(text)
    critical = sum(1 for i in issues if i["severity"] == "critical")
    advanced = len(issues) - critical

    points = critical * 3 + advanced
    # Skor menurun seiring kepadatan masalah, tetapi tetap adil untuk teks pendek:
    # 0 masalah -> 100; makin banyak poin relatif jumlah kata, makin rendah.
    score = max(0, min(100, round(100 * metrics["words"] / max(1, metrics["words"] + 2 * points))))
    better_than_percent = max(1, round(score * 0.95))

    return {
        "corrected": corrected,
        "metrics": metrics,
        "score": score,
        "better_than_percent": better_than_percent,
        "issues": issues,
        "issue_summary": {
            "total": len(issues),
            "critical": critical,
            "advanced": advanced,
        },
    }


def paraphrase(text: str, style: str = "standar") -> dict:
    llm = get_llm()
    messages = [
        {
            "role": "system",
            "content": (
                f"Parafrasekan teks pengguna dengan gaya '{style}', pertahankan makna "
                "dan bahasa aslinya. Balas HANYA hasil parafrase."
            ),
        },
        {"role": "user", "content": text},
    ]
    result = llm.chat(messages, temperature=0.7)
    return {"result": result, "style": style}


def humanize(text: str) -> dict:
    llm = get_llm()
    messages = [
        {
            "role": "system",
            "content": (
                "Tulis ulang teks agar terdengar lebih alami dan manusiawi: variasikan "
                "panjang kalimat, kurangi pola kaku, pertahankan makna dan bahasa asli. "
                "Balas HANYA hasil tulisan ulang."
            ),
        },
        {"role": "user", "content": text},
    ]
    result = llm.chat(messages, temperature=0.8)
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
    desc = REWRITE_TONES.get(tone, REWRITE_TONES["formal"])
    llm = get_llm()
    messages = [
        {
            "role": "system",
            "content": (
                f"Tulis ulang teks pengguna dengan gaya {desc}. Pertahankan makna inti "
                "dan bahasa asli teks. Balas HANYA hasil tulisan ulang tanpa penjelasan."
            ),
        },
        {"role": "user", "content": text},
    ]
    result = llm.chat(messages, temperature=0.7)
    return {"result": result, "tone": tone}


def chat(messages: list[dict], system: str | None = None) -> dict:
    """AI Chat: asisten tulis akademik multi-giliran berbasis LLM lokal."""
    llm = get_llm()
    sys_prompt = system or (
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
    try:
        return _extract_json(raw)
    except json.JSONDecodeError:
        return {
            "reactions": [],
            "overall_sentiment": None,
            "clarity_score": None,
            "engagement_score": None,
            "summary": raw[:500],
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


def _toc_source(text: str, max_chars: int = 14000) -> str:
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
                "susun Daftar Isi berjenjang (bab & sub-bab). Balas HANYA JSON valid: "
                '{"entries": [{"level": <1-3>, "title": "<judul>", '
                '"number": "<1 / 1.1 / 1.1.1>"}], "markdown": "<daftar isi dalam Markdown>"}'
            ),
        },
        {"role": "user", "content": source},
    ]
    raw = llm.chat(messages, temperature=0.2, max_tokens=1200)
    try:
        return _extract_json(raw)
    except json.JSONDecodeError:
        return {"entries": [], "markdown": raw[:1500]}


def improve_document(text: str, goal: str | None = None) -> dict:
    """Perbaikan Dokumen: sunting dokumen agar lebih jelas, rapi, dan baku."""
    llm = get_llm()
    goal_line = f" Fokus perbaikan: {goal}." if goal else ""
    messages = [
        {
            "role": "system",
            "content": (
                "Anda editor akademik profesional. Perbaiki dokumen pengguna: tata bahasa, "
                "kejelasan, alur, dan gaya baku — tanpa mengubah makna, data, atau bahasa "
                "asli." + goal_line + " Balas HANYA teks dokumen hasil perbaikan."
            ),
        },
        {"role": "user", "content": text},
    ]
    improved = llm.chat(messages, temperature=0.3, max_tokens=2048)
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
