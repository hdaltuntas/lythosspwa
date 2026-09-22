"""
Tests for study.py / study_plots.py (sampling, statistics, reliability, export).
"""
import copy
import math

import numpy as np
import pytest
from matplotlib.figure import Figure
from scipy import stats

from lythosspwa import study_plots
from lythosspwa.config import DEFAULT_CONFIG, TRANSLATIONS
from lythosspwa.study import (
    Study,
    StudyVariable,
    available_variables,
    get_value,
    pretty_label,
    reliability,
    sample,
    set_value,
    to_csv,
    to_xlsx,
)


def cfg_static():
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    cfg['analysis_options']['is_seismic'] = False
    return cfg


# ---------------------------------------------------------------- variables
def test_paths_and_labels():
    cfg = cfg_static()
    paths = [p for p, _ in available_variables(cfg)]
    assert "soil_profile.0.phi" in paths and "analysis_options.anchors.1.prestress" in paths
    assert get_value(cfg, "soil_profile.0.phi") == 38
    set_value(cfg, "analysis_options.anchors.1.prestress", 123.0)
    assert cfg['analysis_options']['anchors'][1]['prestress'] == 123.0
    assert "φ" in pretty_label(cfg, "soil_profile.0.phi", TRANSLATIONS["en"])
    assert pretty_label(cfg, "analysis_options.anchors.1.prestress", TRANSLATIONS["tr"]).startswith("Ankraj 2")


def test_variable_validation():
    with pytest.raises(ValueError):
        StudyVariable("x", "range", 5, 5)
    with pytest.raises(ValueError):
        StudyVariable("x", "dist", dist="weird", mean=1, cov=0.1)
    with pytest.raises(ValueError):
        StudyVariable("x", "dist", dist="lognormal", mean=0, cov=0.1)


def test_ppf_moments():
    n = 200000
    u = (np.arange(n) + 0.5) / n
    for dist in ("normal", "lognormal", "uniform"):
        v = StudyVariable("x", "dist", dist=dist, mean=38.0, cov=0.1)
        x = v.ppf(u)
        assert np.mean(x) == pytest.approx(38.0, rel=2e-3)
        assert np.std(x) == pytest.approx(3.8, rel=2e-2)
    r = StudyVariable("x", "range", 2.0, 4.0)
    assert r.ppf(np.array([0.0, 0.5, 1.0])) == pytest.approx([2.0, 3.0, 4.0], abs=1e-6)


# ---------------------------------------------------------------- sampling
def test_sampling_shapes_and_oat_base():
    v = [StudyVariable("a", "range", 0, 1, n_points=4), StudyVariable("b", "range", 10, 20, n_points=3)]
    v[1].base = 12.0
    X, idx = sample(v, "oat")
    assert X.shape == (7, 2) and idx == [0] * 4 + [1] * 3
    assert np.all(X[:4, 1] == 12.0)            # other variable at its base
    X, _ = sample(v, "grid")
    assert X.shape == (12, 2)
    X, _ = sample(v, "lhs", n=50, seed=3)
    assert X.shape == (50, 2) and X[:, 1].min() >= 10 and X[:, 1].max() <= 20
    # LHS stratification: every decile of the first variable contains 5 points
    counts, _ = np.histogram(X[:, 0], bins=10, range=(0, 1))
    assert np.all(counts == 5)


def test_gaussian_copula_correlation():
    v = [StudyVariable("a", "dist", dist="normal", mean=10, cov=0.1),
         StudyVariable("b", "dist", dist="lognormal", mean=20, cov=0.2)]
    X, _ = sample(v, "mc", n=20000, seed=1, correlation={("a", "b"): 0.7})
    rho = stats.spearmanr(X[:, 0], X[:, 1]).statistic
    assert rho == pytest.approx(0.7, abs=0.04)


# ---------------------------------------------------------------- reliability
def test_reliability_statistics():
    rng = np.random.default_rng(0)
    g = rng.normal(2.0, 1.0, 20000)            # true pf = Phi(-2) = 0.0228
    r = reliability(g)
    assert r['pf'] == pytest.approx(0.0228, abs=0.004)
    assert r['pf_lo'] < 0.0228 < r['pf_hi']
    assert r['beta'] == pytest.approx(2.0, abs=0.1)
    assert r['beta_fosm'] == pytest.approx(2.0, abs=0.05)
    r0 = reliability(np.ones(50))
    assert r0['n_fail'] == 0 and math.isinf(r0['beta']) and r0['pf_hi'] > 0


# ---------------------------------------------------------------- end-to-end
@pytest.fixture(scope="module")
def lhs_study():
    st = Study(cfg_static(), [
        StudyVariable("soil_profile.0.phi", "dist", dist="lognormal", mean=38, cov=0.08),
        StudyVariable("loads.surcharge_load", "dist", dist="normal", mean=15, cov=0.3)],
        "lhs", n=24, run_bs=True, workers=2, seed=0)
    st.run()
    return st


def test_lhs_study_results(lhs_study):
    st = lhs_study
    assert len(st.rows) == 24 and st.summary['n_ok'] == 24
    stt = st.summary['stats']
    assert stt['M_le']['min'] > 0 and stt['M_bs']['n'] == st.summary['n_ok_bs']
    sp = st.summary['spearman']['M_le']
    assert sp['soil_profile.0.phi'] < -0.7            # more friction -> less moment
    assert set(st.summary['reliability']) == {"stress_le", "defl_le", "stress_bs", "defl_bs"}
    assert all(0 <= r['pf'] <= 1 for r in st.summary['reliability'].values())
    assert st.spec_dict()['method'] == 'lhs' and len(st.spec_dict()['variables']) == 2


def test_progress_and_cancel():
    st = Study(cfg_static(), [StudyVariable("soil_profile.0.phi", "range", 30, 40, n_points=5)],
               "oat", run_bs=False, workers=1)
    seen = []
    st.run(progress=lambda d, n: seen.append((d, n)), is_cancelled=lambda: len(seen) >= 2)
    assert st.cancelled and len(st.rows) == 2 and seen[-1] == (2, 5)


def test_oat_study_and_failed_samples():
    st = Study(cfg_static(), [StudyVariable("geometry.excavation_depth_H", "range", 5, 10, n_points=6)],
               "oat", run_bs=False, workers=1)
    st.run()
    failed = [r for r in st.rows if not r['ok']]
    assert failed and all("Free-earth" in r['error'] for r in failed)   # anchor at 4 m, H = 5, 6
    oat = st.summary['oat']['geometry.excavation_depth_H']
    assert len(oat['x']) == 4 and np.all(np.diff(oat['M_le']) > 0)
    assert 'reliability' in st.summary and not st.summary['reliability']   # not for OAT


def test_exports_and_figures(lhs_study, tmp_path):
    to_csv(lhs_study, str(tmp_path / "s.csv"))
    text = (tmp_path / "s.csv").read_text(encoding="utf-8")
    assert text.count("\n") == 25 and "M_bs" in text.splitlines()[0]
    pytest.importorskip("openpyxl")
    to_xlsx(lhs_study, str(tmp_path / "s.xlsx"))
    import openpyxl
    wb = openpyxl.load_workbook(str(tmp_path / "s.xlsx"))
    assert set(wb.sheetnames) == {"samples", "summary", "variables"}
    L = TRANSLATIONS["en"]
    for fn in (lambda f: study_plots.plot_hist(f, lhs_study, L),
               lambda f: study_plots.plot_scatter(f, lhs_study, L, "M_bs"),
               lambda f: study_plots.plot_tornado(f, lhs_study, L, "defl_bs")):
        fig = Figure(figsize=(8, 6)); fn(fig)
        assert fig.get_axes()
    txt = study_plots.summary_text(lhs_study, L)
    assert "STUDY SUMMARY" in txt and "Spearman" in txt
