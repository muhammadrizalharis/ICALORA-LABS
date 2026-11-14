"""Layanan skor Binoculars (Hans et al., 2024) untuk AI Detector ICALORA.

B(s) = log-PPL_performer(s) / X-PPL(observer || performer)(s); makin rendah makin
mirip teks AI. Pelengkap model embedding: kuat pada generator yang tidak ikut
dilatih (zero-shot).

Hemat sumber daya:
- Proses HTTP utama TIDAK menyentuh CUDA. Model dimuat di subprocess worker saat
  ada permintaan pertama, lalu worker dimatikan setelah BINOC_IDLE_SECONDS tanpa
  permintaan → VRAM kembali 0 (perilaku sama dengan keep_alive Ollama).
- GPU dipilih saat memuat: yang memori bebasnya terbesar dan ≥ BINOC_MIN_FREE_MB.
- Alokasi PyTorch dibatasi BINOC_MAX_VRAM_GB.

API (127.0.0.1 saja):
  GET  /health                 -> {"ok": true, "loaded": bool, ...}
  POST /score {"texts": [...]} -> {"scores": [float|null, ...], "device": ..}
"""

from __future__ import annotations

import json
import logging
import multiprocessing as mp
import os
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

OBSERVER = os.getenv("BINOC_OBSERVER", "Qwen/Qwen2.5-1.5B")
PERFORMER = os.getenv("BINOC_PERFORMER", "Qwen/Qwen2.5-1.5B-Instruct")
HOST = os.getenv("BINOC_HOST", "127.0.0.1")
PORT = int(os.getenv("BINOC_PORT", "58050"))
IDLE_SECONDS = float(os.getenv("BINOC_IDLE_SECONDS", "300"))
MAX_TOKENS = int(os.getenv("BINOC_MAX_TOKENS", "512"))
MAX_TEXTS = int(os.getenv("BINOC_MAX_TEXTS", "400"))
MAX_CHARS = int(os.getenv("BINOC_MAX_CHARS", "6000"))
MAX_VRAM_GB = float(os.getenv("BINOC_MAX_VRAM_GB", "9"))
MIN_FREE_MB = int(os.getenv("BINOC_MIN_FREE_MB", "10240"))

log = logging.getLogger("binoculars")


class Unavailable(RuntimeError):
    pass


def _pick_gpu() -> int:
    out = subprocess.run(
        ["nvidia-smi", "--query-gpu=index,memory.free", "--format=csv,noheader,nounits"],
        capture_output=True, text=True, timeout=10, check=True,
    ).stdout
    gpus = [tuple(int(x) for x in line.split(",")) for line in out.strip().splitlines()]
    idx, free = max(gpus, key=lambda g: g[1])
    if free < MIN_FREE_MB:
        raise Unavailable(f"VRAM bebas tidak cukup (maks {free} MiB < {MIN_FREE_MB} MiB)")
    return idx


def _worker(conn, gpu: int) -> None:
    os.environ["CUDA_VISIBLE_DEVICES"] = str(gpu)
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    total = torch.cuda.get_device_properties(0).total_memory
    torch.cuda.set_per_process_memory_fraction(min(1.0, MAX_VRAM_GB * 1e9 / total), 0)
    tok = AutoTokenizer.from_pretrained(OBSERVER)
    kw = {"torch_dtype": torch.bfloat16, "device_map": "cuda:0"}
    obs = AutoModelForCausalLM.from_pretrained(OBSERVER, **kw).eval()
    perf = AutoModelForCausalLM.from_pretrained(PERFORMER, **kw).eval()
    conn.send({"ready": True, "vram_gb": round(torch.cuda.memory_allocated() / 1e9, 2)})

    @torch.inference_mode()
    def score(text: str) -> float | None:
        enc = tok(text[:MAX_CHARS], return_tensors="pt", truncation=True,
                  max_length=MAX_TOKENS).to("cuda:0")
        if enc["input_ids"].shape[1] < 8:
            return None
        lo = obs(**enc).logits[0, :-1].float()
        lp = perf(**enc).logits[0, :-1].float()
        tgt = enc["input_ids"][0, 1:]
        ppl = torch.nn.functional.cross_entropy(lp, tgt)
        x_ppl = (torch.softmax(lo, -1) * -torch.log_softmax(lp, -1)).sum(-1).mean()
        return round((ppl / x_ppl).item(), 5)

    while True:
        texts = conn.recv()
        if texts is None:
            break
        try:
            conn.send({"scores": [score(t) for t in texts],
                       "peak_gb": round(torch.cuda.max_memory_allocated() / 1e9, 2)})
        except Exception as exc:  # noqa: BLE001
            conn.send({"error": str(exc)[:300]})
        finally:
            torch.cuda.empty_cache()


class Engine:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.proc = None
        self.conn = None
        self.gpu: int | None = None
        self.vram_gb: float | None = None
        self.peak_gb: float | None = None
        self.last_used = 0.0
        threading.Thread(target=self._reaper, daemon=True).start()

    def _start(self) -> None:
        gpu = _pick_gpu()
        ctx = mp.get_context("spawn")
        parent, child = ctx.Pipe()
        proc = ctx.Process(target=_worker, args=(child, gpu), daemon=True)
        t0 = time.time()
        proc.start()
        if not parent.poll(300):
            proc.kill()
            raise Unavailable("worker gagal memuat model (timeout)")
        try:
            msg = parent.recv()
        except EOFError as exc:
            proc.join(5)
            raise Unavailable("worker gagal memuat model") from exc
        self.proc, self.conn, self.gpu, self.vram_gb = proc, parent, gpu, msg.get("vram_gb")
        log.info("model dimuat di GPU %s (%.1f GB) dalam %.1fs", gpu, self.vram_gb or 0,
                 time.time() - t0)

    def _stop(self) -> None:
        if self.proc is None:
            return
        try:
            self.conn.send(None)
            self.proc.join(15)
        except Exception:  # noqa: BLE001
            pass
        if self.proc.is_alive():
            self.proc.kill()
            self.proc.join(5)
        log.info("worker dihentikan, VRAM dilepas")
        self.proc = self.conn = self.gpu = self.vram_gb = None

    def score(self, texts: list[str]) -> dict:
        with self.lock:
            if self.proc is None or not self.proc.is_alive():
                self.proc = None
                self._start()
            self.last_used = time.time()
            try:
                self.conn.send(texts)
                if not self.conn.poll(600):
                    raise Unavailable("skor timeout")
                msg = self.conn.recv()
            except (EOFError, OSError, Unavailable) as exc:
                self._stop()
                raise Unavailable(f"worker gagal: {exc}") from exc
            self.last_used = time.time()
            gpu = self.gpu
        if "error" in msg:
            raise Unavailable(msg["error"])
        self.peak_gb = msg.get("peak_gb")
        return {"scores": msg["scores"], "device": f"cuda:{gpu}"}

    def _reaper(self) -> None:
        while True:
            time.sleep(15)
            with self.lock:
                if self.proc is not None and time.time() - self.last_used > IDLE_SECONDS:
                    self._stop()

    def status(self) -> dict:
        loaded = self.proc is not None and self.proc.is_alive()
        return {"ok": True, "loaded": loaded, "device": f"cuda:{self.gpu}" if loaded else None,
                "vram_gb": self.vram_gb if loaded else 0, "peak_gb": self.peak_gb,
                "idle_seconds": round(time.time() - self.last_used) if loaded else None,
                "idle_unload_after": IDLE_SECONDS, "observer": OBSERVER,
                "performer": PERFORMER, "max_tokens": MAX_TOKENS}


ENGINE: Engine | None = None


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: dict) -> None:
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._send(200, ENGINE.status())
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/score":
            self._send(404, {"error": "not found"})
            return
        try:
            n = int(self.headers.get("Content-Length", "0"))
            if n > 8_000_000:
                raise ValueError("payload terlalu besar")
            texts = json.loads(self.rfile.read(n))["texts"]
            if not isinstance(texts, list) or not all(isinstance(t, str) for t in texts):
                raise ValueError("texts harus list string")
            if len(texts) > MAX_TEXTS:
                raise ValueError(f"maksimal {MAX_TEXTS} teks per permintaan")
        except Exception as exc:  # noqa: BLE001
            self._send(400, {"error": str(exc)[:200]})
            return
        try:
            self._send(200, ENGINE.score(texts))
        except Unavailable as exc:
            self._send(503, {"error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            log.exception("score gagal")
            self._send(500, {"error": str(exc)[:200]})

    def log_message(self, fmt: str, *args) -> None:
        log.debug(fmt, *args)


def main() -> None:
    global ENGINE
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ENGINE = Engine()
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    log.info("Binoculars siap di %s:%s (idle unload %ss)", HOST, PORT, IDLE_SECONDS)
    srv.serve_forever()


if __name__ == "__main__":
    main()
