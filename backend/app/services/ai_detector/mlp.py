"""MLP ringan (numpy murni) di atas fitur stilometrik + embedding bge-m3.

Satu hidden layer ReLU, dilatih di CPU dengan Adam + dropout + bobot kelas seimbang
dan early stopping pada split validasi. Bobot disimpan sebagai float32 base64 di
JSON (format sama dengan model_emb.json: kunci "type": "mlp") sehingga backend
cukup numpy untuk inferensi.

Pemakaian (dari backend/):
  python -m app.services.ai_detector.mlp train --data A.jsonl,B.jsonl --out model_mlp.json
"""

from __future__ import annotations

import argparse
import base64
import json
import time
from pathlib import Path

import numpy as np


def _enc(a: np.ndarray) -> str:
    return base64.b64encode(np.ascontiguousarray(a, dtype=np.float32).tobytes()).decode()


def _dec(s: str, shape: tuple[int, ...]) -> np.ndarray:
    return np.frombuffer(base64.b64decode(s), dtype=np.float32).reshape(shape).astype(np.float64)


class MLPModel:
    def __init__(self, w1, b1, w2, b2, mean, std, meta: dict | None = None):
        self.w1 = np.asarray(w1, dtype=float)
        self.b1 = np.asarray(b1, dtype=float)
        self.w2 = np.asarray(w2, dtype=float)
        self.b2 = float(b2)
        self.mean = np.asarray(mean, dtype=float)
        self.std = np.asarray(std, dtype=float)
        self.meta = meta or {}

    def _logits(self, X: np.ndarray) -> np.ndarray:
        z = (X - self.mean) / self.std
        h = np.maximum(z @ self.w1 + self.b1, 0.0)
        return h @ self.w2 + self.b2

    def predict_proba(self, x: list[float]) -> float:
        logit = float(self._logits(np.asarray(x, dtype=float)[None, :])[0])
        return 1.0 / (1.0 + np.exp(-logit))

    def predict_many(self, X: np.ndarray) -> np.ndarray:
        return 1.0 / (1.0 + np.exp(-self._logits(X)))

    def to_dict(self) -> dict:
        d, h = self.w1.shape
        return {
            "type": "mlp",
            "dim": d,
            "hidden": h,
            "w1": _enc(self.w1),
            "b1": _enc(self.b1),
            "w2": _enc(self.w2),
            "b2": self.b2,
            "mean": _enc(self.mean),
            "std": _enc(self.std),
            "meta": self.meta,
        }

    @classmethod
    def from_dict(cls, d: dict) -> MLPModel:
        dim, h = int(d["dim"]), int(d["hidden"])
        return cls(
            _dec(d["w1"], (dim, h)), _dec(d["b1"], (h,)), _dec(d["w2"], (h,)), d["b2"],
            _dec(d["mean"], (dim,)), _dec(d["std"], (dim,)), d.get("meta"),
        )


def _auc(p: np.ndarray, y: np.ndarray) -> float:
    order = np.argsort(p)
    ranks = np.empty(len(p))
    ranks[order] = np.arange(1, len(p) + 1)
    n1 = y.sum()
    n0 = len(y) - n1
    return float((ranks[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def fit(X: np.ndarray, y: np.ndarray, Xv: np.ndarray, yv: np.ndarray, hidden: int = 128,
        lr: float = 1e-3, l2: float = 1e-4, dropout: float = 0.3, epochs: int = 80,
        batch: int = 256, patience: int = 8, seed: int = 7) -> tuple[MLPModel, dict]:
    rng = np.random.default_rng(seed)
    mean = X.mean(0)
    std = X.std(0) + 1e-6
    Z = (X - mean) / std
    Zv = (Xv - mean) / std
    d = X.shape[1]
    w1 = rng.normal(0, np.sqrt(2 / d), (d, hidden))
    b1 = np.zeros(hidden)
    w2 = rng.normal(0, np.sqrt(1 / hidden), hidden)
    b2 = 0.0
    params = [w1, b1, w2]
    m = [np.zeros_like(p) for p in params] + [0.0]
    v = [np.zeros_like(p) for p in params] + [0.0]
    cw = np.where(y == 1, len(y) / (2 * y.sum()), len(y) / (2 * (len(y) - y.sum())))
    best = (-1.0, None, 0)
    t = 0
    hist = []
    for ep in range(epochs):
        idx = rng.permutation(len(Z))
        for s in range(0, len(idx), batch):
            bi = idx[s:s + batch]
            zb, yb, wb = Z[bi], y[bi], cw[bi]
            a1 = zb @ w1 + b1
            h = np.maximum(a1, 0.0)
            mask = (rng.random(h.shape) >= dropout) / (1 - dropout)
            hd = h * mask
            p = 1 / (1 + np.exp(-(hd @ w2 + b2)))
            g = (p - yb) * wb / len(bi)
            gw2 = hd.T @ g + l2 * w2
            gb2 = g.sum()
            gh = np.outer(g, w2) * mask * (a1 > 0)
            gw1 = zb.T @ gh + l2 * w1
            gb1 = gh.sum(0)
            t += 1
            for i, (p_, g_) in enumerate(((w1, gw1), (b1, gb1), (w2, gw2))):
                m[i] = 0.9 * m[i] + 0.1 * g_
                v[i] = 0.999 * v[i] + 0.001 * g_ * g_
                p_ -= lr * (m[i] / (1 - 0.9 ** t)) / (np.sqrt(v[i] / (1 - 0.999 ** t)) + 1e-8)
            m[3] = 0.9 * m[3] + 0.1 * gb2
            v[3] = 0.999 * v[3] + 0.001 * gb2 * gb2
            b2 -= lr * (m[3] / (1 - 0.9 ** t)) / (np.sqrt(v[3] / (1 - 0.999 ** t)) + 1e-8)
        pv = 1 / (1 + np.exp(-(np.maximum(Zv @ w1 + b1, 0) @ w2 + b2)))
        auc = _auc(pv, yv)
        hist.append(round(auc, 4))
        if auc > best[0]:
            best = (auc, (w1.copy(), b1.copy(), w2.copy(), b2), ep)
        elif ep - best[2] >= patience:
            break
    w1, b1, w2, b2 = best[1]
    model = MLPModel(w1, b1, w2, b2, mean, std)
    return model, {"val_auc": round(best[0], 4), "best_epoch": best[2], "history": hist}


def _load_rows(paths: list[str], exclude_ids: set[int]) -> tuple[np.ndarray, np.ndarray, list]:
    X, y, info = [], [], []
    for p in paths:
        with open(p, encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                r = json.loads(line)
                sid = r.get("src_id")
                if sid is not None and int(sid) in exclude_ids:
                    continue
                X.append([float(v) for v in r["feat"]] + [float(v) for v in r["emb"]])
                y.append(int(r["label"]))
                info.append(Path(p).name)
    return np.asarray(X), np.asarray(y, dtype=float), info


def _metrics(p: np.ndarray, y: np.ndarray) -> dict:
    pred = p >= 0.5
    tp = int((pred & (y == 1)).sum())
    tn = int((~pred & (y == 0)).sum())
    fp = int((pred & (y == 0)).sum())
    fn = int((~pred & (y == 1)).sum())
    return {"accuracy": round((tp + tn) / len(y), 3), "auc": round(_auc(p, y), 4),
            "false_positive_rate": round(fp / max(1, fp + tn), 3),
            "false_negative_rate": round(fn / max(1, fn + tp), 3),
            "confusion": {"tp": tp, "tn": tn, "fp": fp, "fn": fn}}


def cmd_train(args) -> None:
    excl: set[int] = set()
    for p in filter(None, args.exclude_ids_from.split(",")):
        for line in Path(p).read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                if r.get("src_id") is not None:
                    excl.add(int(r["src_id"]))
    X, y, _ = _load_rows(args.data.split(","), excl)
    print(f"[mlp] {len(y)} sampel (AI={int(y.sum())}), dim={X.shape[1]}, "
          f"id dikecualikan={len(excl)}", flush=True)
    rng = np.random.default_rng(args.seed)
    idx = rng.permutation(len(y))
    n_te = int(len(y) * 0.15)
    te, va, tr = idx[:n_te], idx[n_te:2 * n_te], idx[2 * n_te:]
    t0 = time.time()
    if args.arch == "logistic":
        from app.services.ai_detector.embed import EMB_DIM
        from app.services.ai_detector.model import FEATURES
        from app.services.ai_detector.model import train as train_lr

        names = list(FEATURES) + [f"emb_{i}" for i in range(EMB_DIM)]
        trv = np.concatenate([tr, va])
        model = train_lr(X[trv].tolist(), y[trv].astype(int).tolist(), epochs=args.lr_epochs,
                         lr=0.2, l2=1e-2, feature_names=names)
        held = _metrics(np.asarray([model.predict_proba(x) for x in X[te].tolist()]), y[te])
        info = {"arch": "logistic"}
        print(f"[lr] selesai {time.time() - t0:.0f}s; held-out={held}", flush=True)
        model.meta.update({
            "kind": "stat+emb", "emb_dim": EMB_DIM, "n_ai": int(y.sum()),
            "n_human": int(len(y) - y.sum()), "validation": held,
        })
    else:
        model, info = fit(X[tr], y[tr], X[va], y[va], hidden=args.hidden, lr=args.lr,
                          l2=args.l2, dropout=args.dropout, epochs=args.epochs, seed=args.seed)
        held = _metrics(model.predict_many(X[te]), y[te])
        print(f"[mlp] selesai {time.time() - t0:.0f}s, val AUC={info['val_auc']} "
              f"epoch={info['best_epoch']}; held-out={held}", flush=True)
        model.meta = {
            "kind": "stat+emb-mlp", "hidden": args.hidden, "n": len(y), "n_ai": int(y.sum()),
            "n_human": int(len(y) - y.sum()), "validation": held, "train_info": info,
        }
    model.meta["data"] = [Path(p).name for p in args.data.split(",")]
    model.meta["trained_at"] = time.strftime("%Y-%m-%d", time.gmtime())
    if args.meta_from:
        src = json.loads(Path(args.meta_from).read_text(encoding="utf-8")).get("meta", {})
        for k in ("generators", "prompts", "humanize_frac"):
            if k in src:
                model.meta[k] = src[k]
    Path(args.out).write_text(json.dumps(model.to_dict()), encoding="utf-8")
    print(f"[train] tersimpan → {args.out} ({Path(args.out).stat().st_size // 1024} KB)")


def main() -> None:
    ap = argparse.ArgumentParser(prog="mlp")
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("train")
    t.add_argument("--data", required=True, help="daftar jsonl (feat, emb, label) dipisah koma")
    t.add_argument("--out", required=True)
    t.add_argument("--exclude-ids-from", default="",
                   help="jsonl (mis. eval_set) yang src_id-nya dibuang dari data latih")
    t.add_argument("--meta-from", default="", help="salin generators/prompts dari model ini")
    t.add_argument("--hidden", type=int, default=128)
    t.add_argument("--lr", type=float, default=1e-3)
    t.add_argument("--l2", type=float, default=1e-4)
    t.add_argument("--dropout", type=float, default=0.3)
    t.add_argument("--epochs", type=int, default=80)
    t.add_argument("--seed", type=int, default=7)
    t.add_argument("--arch", choices=["mlp", "logistic"], default="mlp")
    t.add_argument("--lr-epochs", type=int, default=1200, help="epoch untuk --arch logistic")
    args = ap.parse_args()
    {"train": cmd_train}[args.cmd](args)


if __name__ == "__main__":
    main()
