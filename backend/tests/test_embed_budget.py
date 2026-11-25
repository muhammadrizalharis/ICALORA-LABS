"""Embedding dokumen berbatas waktu: parsial/gagal tidak boleh melempar atau menghabiskan waktu."""

import threading
import time

import pytest

from app.services import embedding as emb
from app.services.llm import provider as prov

DOC = " ".join(
    f"kalimat nomor {i} tentang topik penelitian yang cukup panjang." for i in range(1900)
)


class FastLLM:
    """Meniru OllamaProvider.embed_batch_fast; tiap panggilan memajukan jam palsu."""

    def __init__(self, clock, cost=10.0, fail_after=None):
        self.clock, self.cost, self.fail_after, self.calls = clock, cost, fail_after, 0

    def embed_batch_fast(self, texts, timeout, attempts=1, wait=None):
        self.calls += 1
        if self.fail_after is not None and self.calls > self.fail_after:
            raise TimeoutError("server sibuk")
        self.clock["t"] += self.cost
        return [[float(len(t))] for t in texts]


@pytest.fixture
def clock(monkeypatch):
    c = {"t": 0.0}
    monkeypatch.setattr(emb.time, "monotonic", lambda: c["t"])
    return c


def _run(llm, budget=150.0, batch=8, max_chunks=64):
    return emb.embed_chunks_budgeted(
        llm, DOC, max_chunks=max_chunks, budget_seconds=budget, batch_size=batch, call_timeout=60
    )


def test_complete_when_server_is_fast(clock):
    vecs, total = _run(FastLLM(clock, cost=1.0))
    assert total == 64 and len(vecs) == total


def test_budget_exhaustion_returns_partial_not_error(clock):
    llm = FastLLM(clock, cost=40.0)  # 150 dtk cukup untuk 4 batch dari 8
    vecs, total = _run(llm)
    assert total == 64 and len(vecs) == 4 * 8 and llm.calls == 4


def test_server_failure_midway_keeps_what_finished(clock):
    llm = FastLLM(clock, cost=1.0, fail_after=2)
    vecs, total = _run(llm)
    assert len(vecs) == 16 and total == 64  # 2 batch berhasil, sisanya dilewati tanpa melempar


def test_total_failure_gives_empty_list_quickly(clock):
    llm = FastLLM(clock, fail_after=0)
    vecs, total = _run(llm)
    assert vecs == [] and total == 64 and llm.calls == 1  # berhenti di kegagalan pertama


def test_partial_result_is_spread_across_the_whole_document():
    order = emb._spread_order(64)
    assert sorted(order) == list(range(64))
    first_quarter = order[:16]
    assert min(first_quarter) == 0 and max(first_quarter) >= 56  # bukan hanya awal dokumen


def test_falls_back_to_plain_embed_batch_for_providers_without_fast_path():
    class Plain:
        def embed_batch(self, texts):
            return [[1.0] for _ in texts]

    vecs, total = emb.embed_chunks_budgeted(
        Plain(), DOC, max_chunks=10, budget_seconds=60, batch_size=4, call_timeout=30
    )
    assert total == 10 and len(vecs) == 10


def test_empty_text_returns_nothing():
    assert emb.embed_chunks_budgeted(object(), "  ", max_chunks=5, budget_seconds=10) == ([], 0)


def test_embed_semaphore_limits_concurrency_and_fast_path_times_out_in_queue(monkeypatch):
    sem = threading.BoundedSemaphore(1)
    monkeypatch.setattr(prov, "_EMBED_SEM", sem)
    llm = prov.OllamaProvider("http://x", "m", "e", timeout=5, embed_base_url="http://x")
    assert sem.acquire(blocking=False)  # slot sedang dipakai job lain
    t0 = time.monotonic()
    with pytest.raises(TimeoutError):
        llm.embed_batch_fast(["a"], timeout=5, attempts=1, wait=0.3)
    assert time.monotonic() - t0 < 2  # menyerah di antrean, bukan menunggu 120 dtk
    sem.release()
