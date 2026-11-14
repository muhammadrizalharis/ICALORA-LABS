"""Model terlatih (logistic regression) untuk AI Detector.

Dilatih atas fitur stylometrik terukur (burstiness, keragaman kosakata, panjang
kalimat, repetisi bigram, densitas klise, rasio suara personal). Ringan, tanpa
dependensi berat (hanya numpy); bobot disimpan sebagai JSON sehingga dapat
dimuat cepat saat inferensi dan diversikan di git.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

# Urutan fitur WAJIB konsisten antara pelatihan & inferensi.
FEATURES = [
    "burstiness",
    "type_token_ratio",
    "avg_sentence_length",
    "bigram_repetition",
    "cliche_density",
    "personal_ratio",
]

MODEL_PATH = Path(__file__).resolve().parent / "model.json"
EMB_MODEL_PATH = Path(__file__).resolve().parent / "model_emb.json"


def feature_vector(signals: dict) -> list[float]:
    """Ambil vektor fitur numerik (urutan tetap) dari hasil _statistical_signals."""
    return [float(signals.get(k, 0.0)) for k in FEATURES]


class LogisticModel:
    def __init__(
        self,
        weights: list[float],
        bias: float,
        mean: list[float],
        std: list[float],
        meta: dict | None = None,
        feature_names: list[str] | None = None,
    ):
        self.w = np.asarray(weights, dtype=float)
        self.b = float(bias)
        self.mean = np.asarray(mean, dtype=float)
        self.std = np.asarray(std, dtype=float)
        self.meta = meta or {}
        self.feature_names = feature_names or list(FEATURES)

    def predict_proba(self, x: list[float]) -> float:
        z = (np.asarray(x, dtype=float) - self.mean) / self.std
        logit = float(z @ self.w + self.b)
        return 1.0 / (1.0 + np.exp(-logit))

    def to_dict(self) -> dict:
        return {
            "features": self.feature_names,
            "weights": self.w.tolist(),
            "bias": self.b,
            "mean": self.mean.tolist(),
            "std": self.std.tolist(),
            "meta": self.meta,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "LogisticModel":
        return cls(
            d["weights"], d["bias"], d["mean"], d["std"],
            d.get("meta"), d.get("features"),
        )


def train(
    X: list[list[float]], y: list[int], epochs: int = 600, lr: float = 0.3, l2: float = 1e-3,
    feature_names: list[str] | None = None,
) -> LogisticModel:
    """Latih logistic regression dgn gradient descent atas fitur terstandarisasi."""
    Xa = np.asarray(X, dtype=float)
    ya = np.asarray(y, dtype=float)
    mean = Xa.mean(axis=0)
    std = Xa.std(axis=0)
    std[std == 0] = 1.0
    Z = (Xa - mean) / std

    n, d = Z.shape
    w = np.zeros(d)
    b = 0.0
    for _ in range(epochs):
        logits = Z @ w + b
        p = 1.0 / (1.0 + np.exp(-logits))
        err = p - ya
        grad_w = Z.T @ err / n + l2 * w
        grad_b = float(err.mean())
        w -= lr * grad_w
        b -= lr * grad_b

    preds = (1.0 / (1.0 + np.exp(-(Z @ w + b)))) >= 0.5
    acc = float((preds == (ya >= 0.5)).mean())
    return LogisticModel(
        w.tolist(), b, mean.tolist(), std.tolist(),
        meta={"train_accuracy": round(acc, 3), "n": n},
        feature_names=feature_names,
    )


def save(model: LogisticModel, path: Path = MODEL_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(model.to_dict(), indent=2), encoding="utf-8")


def load(path: Path = MODEL_PATH):
    """Muat model (logistic atau MLP, dibedakan kunci "type")."""
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        if d.get("type") == "mlp":
            from app.services.ai_detector.mlp import MLPModel

            return MLPModel.from_dict(d)
        return LogisticModel.from_dict(d)
    except (FileNotFoundError, json.JSONDecodeError, KeyError, ValueError):
        return None
