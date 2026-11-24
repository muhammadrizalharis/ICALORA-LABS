"""Anggaran waktu job plagiarisme: jumlah fase tak boleh melewati batas polling klien (20 mnt)."""

from app.api import tools


def test_budgets_fit_inside_client_poll_even_in_worst_case():
    total = tools.settings.online_total_budget_seconds
    assert total + 30 <= 20 * 60  # batas polling frontend

    # Identitas memakai habis jatahnya (180 dtk): fase luas hanya diberi sisa.
    broad = tools._broad_timeout(180)
    assert broad <= tools.settings.online_budget_seconds
    assert 180 + broad + 120 <= total

    # Setelah luas + lokal, semantik tak boleh melampaui total.
    elapsed = 180 + broad + 100
    assert elapsed + tools._semantic_budget(elapsed) <= total + 20  # lantai 20 dtk


def test_fast_jobs_keep_full_phase_budgets():
    assert tools._broad_timeout(10) == float(tools.settings.online_budget_seconds)
    assert tools._semantic_budget(300) == float(tools.settings.online_semantic_seconds - 25)


def test_budgets_never_collapse_below_floor():
    assert tools._broad_timeout(10_000) == 30.0
    assert tools._semantic_budget(10_000) == 20.0
