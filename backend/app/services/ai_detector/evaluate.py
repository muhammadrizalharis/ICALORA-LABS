"""Evaluasi AI Detector: test set terpisah, lintas-generator, ablation, kalibrasi.

Mengikuti prinsip desain evaluasi (docs/logika_ai_detector_lengkap.md §10.7, §12.7-12.8):
- test set dibangun dari dokumen korpus yang TIDAK dipakai saat training
  (id cache latih + train_used_ids.json dikecualikan);
- prompt generasi berbeda dari prompt training (hindari kebocoran template);
- generator "unseen" (tidak dipakai saat training) diuji terpisah;
- data dibagi val/test: kalibrasi & threshold dipilih di val, dilaporkan di test.

Pemakaian (dari backend/):
  python -m app.services.ai_detector.evaluate build  --out eval_set.jsonl
  python -m app.services.ai_detector.evaluate run    --set eval_set.jsonl --out eval_res.jsonl
  python -m app.services.ai_detector.evaluate report --results eval_res.jsonl [--write-calibration]
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import time
from pathlib import Path

import httpx

from app.services.ai_detector import _blend, _raw_blend, detect_ai
from app.services.ai_detector import train as T
from app.services.ai_detector.model import EMB_MODEL_PATH

_SHARED = os.environ.get("ICALORA_SHARED_ENDPOINT", "http://127.0.0.1:11438")

# Prompt evaluasi — sengaja berbeda dari _AI_STYLES/_AI_STYLES_ID di train.py.
_EVAL_PROMPTS = {
    "en": [
        "Write the introduction section of an undergraduate thesis on the topic below. "
        "About 200-300 words, formal academic English, no headings.",
        "Write a short argumentative essay paragraph sequence (about 250 words) about the "
        "topic below, as a university student would submit it.",
        "Write the literature review discussion (about 250 words) for a journal article on "
        "the topic below. Do not use bullet points.",
    ],
    "id": [
        "Tuliskan bagian Pendahuluan skripsi S1 tentang topik di bawah. Sekitar 200-300 "
        "kata, bahasa Indonesia baku akademik, tanpa judul subbab.",
        "Tuliskan pembahasan hasil penelitian (sekitar 250 kata) untuk artikel jurnal "
        "tentang topik di bawah, seperti ditulis mahasiswa. Tanpa poin-poin.",
        "Tuliskan esai ilmiah singkat (sekitar 250 kata) tentang topik di bawah untuk "
        "tugas kuliah. Bahasa Indonesia formal, tanpa daftar.",
    ],
}


def _gen(client: httpx.Client, model: str, topic: str, lang: str, rng: random.Random) -> str | None:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": rng.choice(_EVAL_PROMPTS[lang])
             + (" Output only the text." if lang == "en" else " Keluarkan HANYA teksnya.")},
            {"role": "user", "content": f"Topik: {topic}" if lang == "id" else f"Topic: {topic}"},
        ],
        "stream": False,
        "keep_alive": "10m",
        "think": "low" if "gpt-oss" in model else False,
        "options": {"temperature": rng.choice((0.6, 0.8, 1.0)), "num_predict": 1500,
                    "num_ctx": 4096},
    }
    try:
        r = client.post(f"{_SHARED}/api/chat", json=payload, timeout=300)
        r.raise_for_status()
        out = (r.json()["message"]["content"] or "").strip()
    except Exception:  # noqa: BLE001
        return None
    out = "\n\n".join(p.strip() for p in out.split("\n\n") if p.strip() and not p.startswith("#"))
    if len(out.split()) < 80:
        return None
    if lang == "id" and not T._looks_indonesian(out, min_hits=5):
        return None
    return out


def _excluded_ids() -> set[int]:
    ids: set[int] = set()
    if T._EMB_CACHE_PATH.exists():
        with T._EMB_CACHE_PATH.open(encoding="utf-8") as fh:
            for line in fh:
                i = line.find('"src_id":')
                if i >= 0:
                    tail = line[i + 9:].lstrip()
                    num = "".join(ch for ch in tail[:15] if ch.isdigit())
                    if num:
                        ids.add(int(num))
    used = T._EMB_CACHE_PATH.parent / "train_used_ids.json"
    if used.exists():
        ids |= set(json.loads(used.read_text(encoding="utf-8")))
    return ids


def _load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def _jsonable(o):
    # nilai numpy (mis. numpy.bool_) dari model → tipe Python bawaan
    return o.item() if hasattr(o, "item") else str(o)


def _append(path: Path, rec: dict) -> None:
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False, default=_jsonable) + "\n")


def _split(i: int) -> str:
    return "val" if i % 2 == 0 else "test"


def cmd_build(args) -> None:
    out = Path(args.out)
    recs = _load(out)
    have = {(r["group"]) for r in recs}
    rng = random.Random(args.seed)
    random.seed(args.seed)
    excl = _excluded_ids()
    print(f"[build] dikecualikan {len(excl)} id dokumen latih", flush=True)

    if "human-en" not in have:
        docs = T._human_samples(args.humans_en, excl)
        for i, (did, _t, body) in enumerate(docs):
            excl.add(did)
            _append(out, {"group": "human-en", "label": 0, "lang": "en", "generator": None,
                          "humanized": False, "src_id": did, "split": _split(i), "text": body})
        print(f"[build] manusia EN={len(docs)}", flush=True)
    if "human-id" not in have:
        n = 0
        for did, _t, body in T._indonesian_human_samples(args.humans_id, excl):
            excl.add(did)
            _append(out, {"group": "human-id", "label": 0, "lang": "id", "generator": None,
                          "humanized": False, "src_id": did, "split": _split(n), "text": body})
            n += 1
        print(f"[build] manusia ID={n}", flush=True)

    recs = _load(out)
    topics = {
        "en": [r["text"].split(".")[0][:160] for r in recs if r["group"] == "human-en"],
        "id": [r["text"].split(".")[0][:160] for r in recs if r["group"] == "human-id"],
    }
    seen = [m for m in args.seen.split(",") if m]
    unseen = [m for m in args.unseen.split(",") if m]
    with httpx.Client() as client:
        for model in seen + unseen:
            tag = "unseen" if model in unseen else "seen"
            for lang in ("en", "id"):
                group = f"ai-{lang}:{model}"
                if group in have:
                    continue
                t0 = time.time()
                got = 0
                tries = 0
                while got < args.per_gen and tries < args.per_gen * 3:
                    tries += 1
                    topic = rng.choice(topics[lang]) if topics[lang] else "pendidikan"
                    txt = _gen(client, model, topic, lang, rng)
                    if not txt:
                        continue
                    base = {"label": 1, "lang": lang, "generator": model, "seen": tag,
                            "split": _split(got)}
                    _append(out, {**base, "group": group, "humanized": False, "text": txt})
                    if rng.random() < args.humanize_frac:
                        hum = T._humanize(client, _SHARED, model, txt, lang, rng)
                        if hum:
                            _append(out, {**base, "group": f"{group}+hum", "humanized": True,
                                          "text": hum})
                    got += 1
                print(f"[build] {group} ({tag}) = {got} dalam {time.time() - t0:.0f}s", flush=True)
            T._unload_models([(_SHARED, model)])

    recs = _load(out)
    if not any(r["group"] == "mixed" for r in recs):
        _build_mixed(out, recs, rng, args.mixed)
    print(f"[build] total {len(_load(out))} rekaman → {out}", flush=True)


def _build_mixed(out: Path, recs: list[dict], rng: random.Random, n: int) -> None:
    """Dokumen campuran: paragraf manusia + 1-2 teks AI di posisi acak."""
    made = 0
    for lang in ("en", "id"):
        hum = [r["text"] for r in recs if r["label"] == 0 and r["lang"] == lang]
        ai = [r["text"] for r in recs if r["label"] == 1 and r["lang"] == lang
              and not r["humanized"]]
        if len(hum) < 4 or len(ai) < 2:
            continue
        for _ in range(n // 2):
            parts = [(t, 0) for t in rng.sample(hum, rng.randint(3, 5))]
            for t in rng.sample(ai, rng.randint(1, 2)):
                parts.insert(rng.randint(0, len(parts)), (t, 1))
            doc = "\n\n".join(t for t, _l in parts)
            spans, off = [], 0
            for t, lab in parts:
                s = doc.index(t, off)
                spans.append([s, s + len(t), lab])
                off = s + len(t)
            ai_words = sum(len(t.split()) for t, lab in parts if lab)
            _append(out, {"group": f"mixed-{lang}", "label": -1, "lang": lang, "generator": None,
                          "humanized": False, "split": _split(made), "text": doc,
                          "spans": spans,
                          "true_share": round(100 * ai_words / len(doc.split()), 1)})
            made += 1
    print(f"[build] dokumen campuran={made}", flush=True)


def cmd_run(args) -> None:
    recs = _load(Path(args.set))
    out = Path(args.out)
    done = len(_load(out))
    import app.services.ai_detector as det

    if args.no_llm:
        det._LLM_ENABLED = False
    if args.binoculars:
        det._BINOC_ALWAYS = True
    if args.model:
        det._model.EMB_MODEL_PATH = Path(args.model)
        det._EMB_TRAINED = None
        det._CALIB = None
        det._STACK = None
        det._MODEL_INFO = None
    t0 = time.time()
    for i, r in enumerate(recs[done:], start=done):
        res = detect_ai(r["text"])
        row = {k: v for k, v in r.items() if k != "text"}
        row.update({k: res.get(k) for k in (
            "ai_probability", "verdict", "needs_review", "ai_share", "language",
            "stat_probability", "llm_probability", "model_probability",
            "emb_model_probability", "binoculars_score", "reliability")})
        row["words"] = len(r["text"].split())
        if r["label"] == -1:
            row["segments"] = [{"start": s["start"], "end": s["end"], "words": s["words"],
                                "p": s["ai_probability"]} for s in res.get("segments") or []]
        _append(out, row)
        if (i + 1) % 20 == 0:
            print(f"[run] {i + 1}/{len(recs)} ({time.time() - t0:.0f}s)", flush=True)
    print(f"[run] selesai {len(recs)} → {out}", flush=True)


# ---------------------------------------------------------------- metrik ---

def _auc(scores: list[float], labels: list[int]) -> float | None:
    pos = [s for s, y in zip(scores, labels, strict=True) if y == 1]
    neg = [s for s, y in zip(scores, labels, strict=True) if y == 0]
    if not pos or not neg:
        return None
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return round(wins / (len(pos) * len(neg)), 3)


def _logit(p: float) -> float:
    p = min(max(p / 100.0, 1e-4), 1 - 1e-4)
    return math.log(p / (1 - p))


def fit_platt(scores: list[float], labels: list[int], iters: int = 500,
              l2: float = 1e-3) -> tuple[float, float]:
    """Platt scaling: p = sigmoid(a·logit(s) + b), dilatih dengan Newton teredam.

    Penalti L2 kecil (relatif terhadap ukuran data) ke arah identitas (a=1, b=0)
    plus line search mencegah divergensi bila data validasi hampir terpisah.
    """
    xs = [_logit(s) for s in scores]
    # Bobot kelas seimbang: skor hasil = peluang AI dengan prior 50:50, tidak
    # terpengaruh rasio AI:manusia di set validasi.
    n1 = max(1, sum(labels))
    n0 = max(1, len(labels) - n1)
    cw = {1: len(labels) / (2 * n1), 0: len(labels) / (2 * n0)}
    lam = l2 * len(labels)

    def loss(a: float, b: float) -> float:
        tot = 0.0
        for x, y in zip(xs, labels, strict=True):
            z = a * x + b
            # log(1+e^z) - y*z, stabil numerik
            tot += cw[y] * ((max(z, 0.0) + math.log1p(math.exp(-abs(z)))) - y * z)
        return tot + 0.5 * lam * ((a - 1.0) ** 2 + b * b)

    a, b = 1.0, 0.0
    cur = loss(a, b)
    for _ in range(iters):
        ga = gb = haa = hab = hbb = 0.0
        for x, y in zip(xs, labels, strict=True):
            p = 1 / (1 + math.exp(-max(-50.0, min(50.0, a * x + b))))
            d = (p - y) * cw[y]
            w = (p * (1 - p) + 1e-9) * cw[y]
            ga += d * x
            gb += d
            haa += w * x * x
            hab += w * x
            hbb += w
        ga += lam * (a - 1.0)
        gb += lam * b
        haa += lam
        hbb += lam
        det = haa * hbb - hab * hab
        if abs(det) < 1e-12:
            break
        da = (hbb * ga - hab * gb) / det
        db = (haa * gb - hab * ga) / det
        step = 1.0
        while step > 1e-6:
            na, nb = a - step * da, b - step * db
            new = loss(na, nb)
            if new <= cur:
                break
            step /= 2
        else:
            break
        a, b, prev, cur = na, nb, cur, new
        if abs(step * da) + abs(step * db) < 1e-7 or prev - cur < 1e-10:
            break
    return round(a, 4), round(b, 4)


def apply_platt(score: float, a: float, b: float) -> float:
    return 100.0 / (1 + math.exp(-(a * _logit(score) + b)))


def _brier_ece(probs: list[float], labels: list[int]) -> tuple[float, float]:
    ps = [p / 100 for p in probs]
    brier = sum((p - y) ** 2 for p, y in zip(ps, labels, strict=True)) / len(ps)
    ece = 0.0
    for lo in range(10):
        idx = [i for i, p in enumerate(ps) if lo / 10 <= p < (lo + 1) / 10 or (lo == 9 and p == 1)]
        if idx:
            conf = sum(ps[i] for i in idx) / len(idx)
            acc = sum(labels[i] for i in idx) / len(idx)
            ece += len(idx) / len(ps) * abs(conf - acc)
    return round(brier, 4), round(ece, 4)


def _tpr_at_fpr(scores: list[float], labels: list[int], fprs=(0.01, 0.05)) -> dict:
    """TPR pada titik FPR tetap (ambang = kuantil skor manusia), standar benchmark detektor."""
    hs = sorted((s for s, y in zip(scores, labels, strict=True) if y == 0), reverse=True)
    ais = [s for s, y in zip(scores, labels, strict=True) if y == 1]
    out = {}
    for f in fprs:
        if not hs or not ais:
            out[f"tpr@fpr{f:g}"] = None
            continue
        k = int(math.floor(f * len(hs)))  # maksimal k manusia boleh ≥ ambang
        thr = hs[k] if k < len(hs) else -math.inf
        out[f"tpr@fpr{f:g}"] = round(sum(s > thr for s in ais) / len(ais), 3)
    return out


def _wilson(k: int, n: int, z: float = 1.96) -> list[float] | None:
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0.0, c - h), 3), round(min(1.0, c + h), 3)]


def _nll(probs: list[float], labels: list[int]) -> float:
    ps = [min(max(p / 100, 1e-6), 1 - 1e-6) for p in probs]
    return round(-sum(math.log(p if y else 1 - p) for p, y in zip(ps, labels, strict=True))
                 / len(ps), 4)


def _rate_ci(scores_h: list[float], scores_ai: list[float], thr: float) -> dict:
    kh = sum(v >= thr for v in scores_h)
    ka = sum(v >= thr for v in scores_ai)
    return {"threshold": thr,
            "test_fpr": round(kh / len(scores_h), 3), "test_fpr_ci95": _wilson(kh, len(scores_h)),
            "test_recall": round(ka / len(scores_ai), 3),
            "test_recall_ci95": _wilson(ka, len(scores_ai))}


def _rate(rows: list[dict], key: str, thr: float) -> str:
    vals = [r[key] for r in rows if r.get(key) is not None]
    if not vals:
        return "-"
    k = sum(v >= thr for v in vals)
    return f"{k}/{len(vals)} ({100 * k / len(vals):.0f}%)"


def cmd_report(args) -> None:
    rows = _load(Path(args.results))
    binary = [r for r in rows if r["label"] in (0, 1)]
    out: dict = {"n": len(rows)}

    print("\n=== Per kelompok (ambang verdict AI ≥70 / ditandai ≥45) ===")
    groups = sorted({r["group"] for r in binary})
    per_group = {}
    for g in groups:
        rs = [r for r in binary if r["group"] == g]
        rev = sum(bool(r.get("needs_review")) for r in rs)
        per_group[g] = {"n": len(rs), "ai70": _rate(rs, "ai_probability", 70),
                        "ai45": _rate(rs, "ai_probability", 45), "review": rev}
        print(f"  {g:55} n={len(rs):3}  ≥70: {per_group[g]['ai70']:13} "
              f"≥45: {per_group[g]['ai45']:13} tinjau: {rev}")
    out["per_group"] = per_group

    print("\n=== Ablation: AUC per komponen (semua / EN / ID / unseen-generator) ===")
    comps = {
        "statistik": "stat_probability",
        "model_6_fitur": "model_probability",
        "embedding": "emb_model_probability",
        "llm (EN)": "llm_probability",
        "gabungan": "ai_probability",
    }
    for r in binary:
        if r.get("model_probability") is not None and r.get("emb_model_probability") is not None:
            r["emb+model"] = _blend(r["stat_probability"], None, r["model_probability"],
                                    r["emb_model_probability"])[0]
    comps["emb+model+stat (tanpa LLM)"] = "emb+model"
    abl = {}
    for name, key in comps.items():
        line = {}
        for sub, filt in (
            ("semua", lambda r: True),
            ("EN", lambda r: r["lang"] == "en"),
            ("ID", lambda r: r["lang"] == "id"),
            ("unseen", lambda r: r["label"] == 0 or r.get("seen") == "unseen"),
            ("parafrase", lambda r: r["label"] == 0 or r.get("humanized")),
        ):
            rs = [r for r in binary if filt(r) and r.get(key) is not None]
            line[sub] = _auc([r[key] for r in rs], [r["label"] for r in rs])
        abl[name] = line
        print(f"  {name:28} " + "  ".join(f"{k}={v}" for k, v in line.items()))
    out["ablation_auc"] = abl

    print("\n=== Metrik keputusan (skor gabungan, ambang 70) per split ===")
    for split in ("val", "test"):
        rs = [r for r in binary if r["split"] == split and r.get("ai_probability") is not None]
        tp = sum(r["label"] == 1 and r["ai_probability"] >= 70 for r in rs)
        fp = sum(r["label"] == 0 and r["ai_probability"] >= 70 for r in rs)
        fn = sum(r["label"] == 1 and r["ai_probability"] < 70 for r in rs)
        tn = sum(r["label"] == 0 and r["ai_probability"] < 70 for r in rs)
        prec = tp / (tp + fp) if tp + fp else 0
        rec = tp / (tp + fn) if tp + fn else 0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0
        m = {"acc": round((tp + tn) / len(rs), 3), "precision": round(prec, 3),
             "recall": round(rec, 3), "f1": round(f1, 3),
             "fpr": round(fp / (fp + tn), 3) if fp + tn else None,
             "fnr": round(fn / (fn + tp), 3) if fn + tp else None, "n": len(rs)}
        out[f"metrics_{split}"] = m
        print(f"  {split}: {m}")

    val = [r for r in binary if r["split"] == "val" and r.get("ai_probability") is not None]
    test = [r for r in binary if r["split"] == "test" and r.get("ai_probability") is not None]
    a, b = fit_platt([r["ai_probability"] for r in val], [r["label"] for r in val])
    raw = _brier_ece([r["ai_probability"] for r in test], [r["label"] for r in test])
    cal = _brier_ece([apply_platt(r["ai_probability"], a, b) for r in test],
                     [r["label"] for r in test])
    out["calibration"] = {"a": a, "b": b, "test_brier_ece_raw": raw, "test_brier_ece_cal": cal}
    t_lab = [r["label"] for r in test]
    t_cal = [apply_platt(r["ai_probability"], a, b) for r in test]
    out["calibration"]["test_nll_cal"] = _nll(t_cal, t_lab)
    out["test_tpr_at_fpr"] = _tpr_at_fpr(t_cal, t_lab)
    print(f"\n=== Kalibrasi (Platt seimbang, fit di val) a={a} b={b} ===")
    print(f"  test Brier/ECE mentah    : {raw}")
    print(f"  test Brier/ECE kalibrasi : {cal}  NLL {out['calibration']['test_nll_cal']}")
    print(f"  test TPR @ FPR tetap     : {out['test_tpr_at_fpr']}")
    sweep = {}
    for thr in (45, 50, 60, 70, 80, 90):
        row = {}
        for name, f in (("mentah", lambda v: v), ("kalibrasi", lambda v: apply_platt(v, a, b))):
            hs = [f(r["ai_probability"]) for r in test if r["label"] == 0]
            ais = [f(r["ai_probability"]) for r in test if r["label"] == 1]
            row[name] = {"fpr": round(sum(v >= thr for v in hs) / len(hs), 3),
                         "recall": round(sum(v >= thr for v in ais) / len(ais), 3)}
        sweep[thr] = row
        print(f"  ambang {thr}: mentah {row['mentah']}  kalibrasi {row['kalibrasi']}")
    out["threshold_sweep_test"] = sweep

    def pick(rows_: list[dict], max_fpr: float) -> float:
        hs = sorted(apply_platt(r["ai_probability"], a, b) for r in rows_ if r["label"] == 0)
        for thr in range(30, 100):
            if sum(v >= thr for v in hs) / len(hs) <= max_fpr:
                return float(thr)
        return 99.0

    thr_ai, thr_mix = pick(val, args.max_fpr_ai), pick(val, args.max_fpr_mixed)
    thr_mix = min(thr_mix, thr_ai)
    res = {}
    for name, thr in (("ai", thr_ai), ("mixed", thr_mix)):
        hs = [apply_platt(r["ai_probability"], a, b) for r in test if r["label"] == 0]
        ais = [apply_platt(r["ai_probability"], a, b) for r in test if r["label"] == 1]
        res[name] = _rate_ci(hs, ais, thr)
    out["thresholds"] = res
    print(f"  ambang dipilih di val (FPR≤{args.max_fpr_ai}/{args.max_fpr_mixed}) → test: {res}")

    mixed = [r for r in rows if r["label"] == -1]
    if mixed:
        errs = [abs((r.get("ai_share") or 0) - r["true_share"]) for r in mixed]
        seg_ok = seg_n = 0
        for r in mixed:
            for s in r.get("segments") or []:
                ai_chars = sum(max(0, min(s["end"], e) - max(s["start"], st))
                               for st, e, lab in r["spans"] if lab == 1)
                truth = ai_chars / max(1, s["end"] - s["start"]) >= 0.5
                seg_ok += (s["p"] >= 70) == truth
                seg_n += 1
        out["mixed"] = {"n": len(mixed), "mae_share": round(sum(errs) / len(errs), 1),
                        "segment_accuracy": round(seg_ok / seg_n, 3) if seg_n else None}
        print(f"\n=== Dokumen campuran === {out['mixed']}")

    stack = _fit_stack(binary, args) if args.fit_stack else None
    if stack:
        out["stack"] = stack

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(out, indent=2, ensure_ascii=False), "utf-8")
    if args.write_calibration:
        target = Path(args.model) if args.model else EMB_MODEL_PATH
        d = json.loads(target.read_text(encoding="utf-8"))
        d.setdefault("meta", {})["calibration"] = {
            "method": "platt-balanced", "a": a, "b": b, "fitted_on": len(val),
            "threshold_ai": thr_ai, "threshold_mixed": thr_mix,
            "test": res, "date": time.strftime("%Y-%m-%d", time.gmtime()),
        }
        if stack:
            d["meta"]["stack"] = stack
        elif "stack" in d["meta"]:
            del d["meta"]["stack"]
        target.write_text(json.dumps(d), encoding="utf-8")
        print(f"[report] kalibrasi{' + stack' if stack else ''} ditulis ke {target}")


def _fit_stack(binary: list[dict], args) -> dict | None:
    """Penggabung logistic seimbang: z = w_s·logit(skor mentah) + w_b·(−(B−mu)/sd) + b.

    Dilatih pada split val; ambang dipilih di val dengan batas FPR; dilaporkan di test.
    """
    rows = []
    for r in binary:
        if r.get("binoculars_score") is None or r.get("stat_probability") is None:
            continue
        raw = _raw_blend(r["stat_probability"], r.get("llm_probability"),
                         r.get("model_probability"), r.get("emb_model_probability"))
        rows.append((r, _logit(raw), r["binoculars_score"]))
    val = [x for x in rows if x[0]["split"] == "val"]
    test = [x for x in rows if x[0]["split"] == "test"]
    if len(val) < 40 or not test:
        print("[stack] skor Binoculars kurang; jalankan `run --binoculars` dulu")
        return None
    bs = [x[2] for x in val]
    mu = sum(bs) / len(bs)
    sd = (sum((v - mu) ** 2 for v in bs) / len(bs)) ** 0.5 or 1.0

    def feats(x):
        return (x[1], -(x[2] - mu) / sd)

    ys = [x[0]["label"] for x in val]
    n1 = max(1, sum(ys))
    n0 = max(1, len(ys) - n1)
    cw = {1: len(ys) / (2 * n1), 0: len(ys) / (2 * n0)}
    w = [0.0, 0.0, 0.0]
    for _ in range(200):  # Newton, sedikit L2 agar stabil
        g = [0.0, 0.0, 0.0]
        h = [[1e-3 if i == j else 0.0 for j in range(3)] for i in range(3)]
        for x, yv in zip(val, ys, strict=True):
            f = (*feats(x), 1.0)
            z = max(-30.0, min(30.0, sum(wi * fi for wi, fi in zip(w, f, strict=True))))
            p = 1 / (1 + math.exp(-z))
            for i in range(3):
                g[i] += cw[yv] * (p - yv) * f[i]
                for j in range(3):
                    h[i][j] += cw[yv] * p * (1 - p) * f[i] * f[j]
        for i in range(3):
            g[i] += 1e-3 * w[i]
        step = _solve3(h, g)
        w = [wi - si for wi, si in zip(w, step, strict=True)]
        if sum(abs(si) for si in step) < 1e-8:
            break

    def prob(x):
        f = (*feats(x), 1.0)
        z = max(-30.0, min(30.0, sum(wi * fi for wi, fi in zip(w, f, strict=True))))
        return 100 / (1 + math.exp(-z))

    def pick(rs, max_fpr):
        hs = [prob(x) for x in rs if x[0]["label"] == 0]
        for thr in range(30, 100):
            if sum(v >= thr for v in hs) / len(hs) <= max_fpr:
                return float(thr)
        return 99.0

    thr_ai, thr_mix = pick(val, args.max_fpr_ai), pick(val, args.max_fpr_mixed)
    thr_mix = min(thr_mix, thr_ai)
    res = {}
    for name, thr in (("ai", thr_ai), ("mixed", thr_mix)):
        hs = [prob(x) for x in test if x[0]["label"] == 0]
        ais = [prob(x) for x in test if x[0]["label"] == 1]
        res[name] = _rate_ci(hs, ais, thr)
    t_lab = [x[0]["label"] for x in test]
    t_p = [prob(x) for x in test]
    extra = {"test_nll": _nll(t_p, t_lab), "test_brier_ece": _brier_ece(t_p, t_lab),
             **_tpr_at_fpr(t_p, t_lab)}
    auc = {}
    for sub, filt in (
        ("semua", lambda r: True), ("EN", lambda r: r["lang"] == "en"),
        ("ID", lambda r: r["lang"] == "id"),
        ("unseen", lambda r: r["label"] == 0 or r.get("seen") == "unseen"),
        ("parafrase", lambda r: r["label"] == 0 or r.get("humanized")),
    ):
        rs = [x for x in test if filt(x[0])]
        labels = [x[0]["label"] for x in rs]
        auc[sub] = {"model": _auc([x[1] for x in rs], labels),
                    "binoculars": _auc([-x[2] for x in rs], labels),
                    "gabungan": _auc([prob(x) for x in rs], labels)}
    print(f"\n=== Stack model+Binoculars (fit val n={len(val)}, test n={len(test)}) ===")
    print(f"  bobot: skor={w[0]:.3f} binoc={w[1]:.3f} b={w[2]:.3f} (mu={mu:.4f} sd={sd:.4f})")
    for k, v in auc.items():
        print(f"  AUC test {k:9}: {v}")
    print(f"  ambang (val) → test: {res}")
    print(f"  test kalibrasi/TPR@FPR: {extra}")
    return {"method": "logistic-balanced", "w_score": round(w[0], 5), "w_binoc": round(w[1], 5),
            "b": round(w[2], 5), "mu": round(mu, 5), "sd": round(sd, 5),
            "threshold_ai": thr_ai, "threshold_mixed": thr_mix, "fitted_on": len(val),
            "test": res, "test_auc": auc, "test_extra": extra,
            "date": time.strftime("%Y-%m-%d", time.gmtime())}


def _solve3(a: list[list[float]], b: list[float]) -> list[float]:
    m = [row[:] + [bv] for row, bv in zip(a, b, strict=True)]
    for c in range(3):
        piv = max(range(c, 3), key=lambda r: abs(m[r][c]))
        m[c], m[piv] = m[piv], m[c]
        if abs(m[c][c]) < 1e-12:
            return [0.0, 0.0, 0.0]
        for r in range(3):
            if r != c:
                f = m[r][c] / m[c][c]
                m[r] = [x - f * y for x, y in zip(m[r], m[c], strict=True)]
    return [m[i][3] / m[i][i] for i in range(3)]


def main() -> None:
    ap = argparse.ArgumentParser(prog="evaluate")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--out", required=True)
    b.add_argument("--humans-en", type=int, default=80)
    b.add_argument("--humans-id", type=int, default=80)
    b.add_argument("--per-gen", type=int, default=20)
    b.add_argument("--seen", default="qwen3.6:latest,gemma3:27b,gemma4:latest")
    b.add_argument("--unseen", default="gpt-oss:latest")
    b.add_argument("--humanize-frac", type=float, default=0.3)
    b.add_argument("--mixed", type=int, default=20)
    b.add_argument("--seed", type=int, default=4242)
    r = sub.add_parser("run")
    r.add_argument("--set", required=True)
    r.add_argument("--out", required=True)
    r.add_argument("--no-llm", action="store_true")
    r.add_argument("--model", help="jalur model_emb alternatif (mis. cadangan lama)")
    r.add_argument("--binoculars", action="store_true",
                   help="kumpulkan skor Binoculars (butuh layanan services/binoculars)")
    p = sub.add_parser("report")
    p.add_argument("--results", required=True)
    p.add_argument("--json-out")
    p.add_argument("--write-calibration", action="store_true")
    p.add_argument("--model", help="model tujuan --write-calibration (default model aktif)")
    p.add_argument("--fit-stack", action="store_true",
                   help="latih penggabung skor model + Binoculars (butuh run --binoculars)")
    p.add_argument("--max-fpr-ai", type=float, default=0.05)
    p.add_argument("--max-fpr-mixed", type=float, default=0.15)
    args = ap.parse_args()
    {"build": cmd_build, "run": cmd_run, "report": cmd_report}[args.cmd](args)


if __name__ == "__main__":
    main()
