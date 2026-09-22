"""
Tests for beam_spring.py.   Run with:  pytest -q test_beam_spring.py
"""
import copy

import numpy as np
import pytest

from lythosspwa.analysis_engine import AnalysisEngine, RetainingWall, SoilLayer
from lythosspwa.beam_spring import BeamSpringAnalysis, subgrade_modulus
from lythosspwa.config import DEFAULT_CONFIG


def le(cfg):
    w = RetainingWall(cfg)
    e = AnalysisEngine(w)
    e.run()
    return w, e


def cantilever_cfg():
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    cfg['analysis_options'].update({'anchors': [], 'is_seismic': False})
    cfg['geometry']['excavation_depth_H'] = 4.0
    cfg['loads'].update({'water_level_active': 2.0, 'water_level_passive': 4.0})
    return cfg


def anchored_cfg(**anchor):
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    cfg['analysis_options'].update({'anchors': [{'depth': 1.5, **anchor}],
                                    'is_seismic': False})
    return cfg


# ----------------------------------------------------------------------
def test_cantilever_close_to_limit_equilibrium():
    w, e = le(cantilever_cfg())
    r = BeamSpringAnalysis(w, e).run()
    assert r['m_max_abs'] == pytest.approx(e.results['m_max_abs'], rel=0.10)
    assert r['toe_shear'] == pytest.approx(0.0, abs=1e-6 * abs(r['v_min']) + 1e-9)
    assert r['moment'][0] == pytest.approx(0.0, abs=1e-6 * r['m_max_abs'])
    assert r['toe_moment'] == pytest.approx(0.0, abs=1e-6 * r['m_max_abs'])


def test_single_anchor_close_to_limit_equilibrium():
    w, e = le(anchored_cfg())
    r = BeamSpringAnalysis(w, e).run()
    t_le = e.t_anchors[1.5]
    assert r['anchor_forces'][1.5] == pytest.approx(t_le, rel=0.10)
    assert r['m_max_abs'] == pytest.approx(e.results['m_max_abs'], rel=0.10)
    assert abs(r['toe_shear']) < 1e-6 * t_le


def test_spring_pressures_respect_limits():
    w, e = le(anchored_cfg())
    r = BeamSpringAnalysis(w, e).run()
    assert np.all(r['p_ret'] >= r['pa_ret'] - 1e-9)
    assert np.all(r['p_ret'] <= r['pp_ret'] + 1e-9)
    assert np.all(r['p_exc'] >= r['pa_exc'] - 1e-9)
    assert np.all(r['p_exc'] <= r['pp_exc'] + 1e-9)
    assert 0.0 <= r['passive_mobilization'] <= 1.0
    assert 0.0 <= r['active_mobilization'] <= 1.0 + 1e-9


def test_anchor_is_tension_only_and_prestress_increases_force():
    w, e = le(anchored_cfg(prestress=0.0))
    t0 = BeamSpringAnalysis(w, e).run()['anchor_forces'][1.5]
    w, e = le(anchored_cfg(prestress=150.0))
    r = BeamSpringAnalysis(w, e).run()
    assert r['anchor_forces'][1.5] >= 0.0
    assert r['anchor_forces'][1.5] > t0
    # prestress pulls the wall back -> smaller deflection
    w0, e0 = le(anchored_cfg(prestress=0.0))
    d0 = BeamSpringAnalysis(w0, e0).run()['actual_max_deflection']
    assert r['actual_max_deflection'] < d0


def test_stiffer_anchor_gives_smaller_deflection():
    w, e = le(anchored_cfg(stiffness=3000.0))
    d_soft = BeamSpringAnalysis(w, e).run()['actual_max_deflection']
    w, e = le(anchored_cfg(stiffness=30000.0))
    d_stiff = BeamSpringAnalysis(w, e).run()['actual_max_deflection']
    assert d_stiff < d_soft


def test_staged_and_unstaged_multi_anchor_both_converge():
    cfg = copy.deepcopy(DEFAULT_CONFIG)          # 2 anchors, seismic
    w, e = le(cfg)
    r1 = BeamSpringAnalysis(w, e, {'staged': True}).run()
    r2 = BeamSpringAnalysis(w, e, {'staged': False}).run()
    assert len(r1['stages']) == 5 and len(r2['stages']) == 3
    for r in (r1, r2):
        assert all(t >= 0 for t in r['anchor_forces'].values())
        assert sum(r['anchor_forces'].values()) == pytest.approx(
            sum(e.t_anchors.values()), rel=0.25)   # total anchor load ~ LE
        assert r['toe_moment'] == pytest.approx(0.0, abs=1e-6 * r['m_max_abs'])


def test_mesh_convergence():
    w, e = le(anchored_cfg())
    m_coarse = BeamSpringAnalysis(w, e, {'element_size': 0.2}).run()['m_max_abs']
    m_fine = BeamSpringAnalysis(w, e, {'element_size': 0.05}).run()['m_max_abs']
    assert m_coarse == pytest.approx(m_fine, rel=0.01)


def test_too_short_embedment_is_reported_as_unstable():
    w, e = le(cantilever_cfg())
    with pytest.raises(RuntimeError):
        BeamSpringAnalysis(w, e, {'embedment': 1.5}).run()


def test_old_project_format_with_anchor_depths_still_works():
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    cfg['analysis_options'].pop('anchors')
    cfg['analysis_options']['anchor_depths'] = [2.0]
    cfg['soil_profile'][0].pop('k_s')
    w, e = le(cfg)
    assert w.anchors[0]['depth'] == 2.0 and w.anchors[0]['stiffness'] > 0
    r = BeamSpringAnalysis(w, e).run()
    assert r['anchor_forces'][2.0] > 0


# ----------------------------------------------------------------------
# v0.4: k_s methods, water mode, hydrodynamics, inclined anchors
# ----------------------------------------------------------------------


def test_subgrade_modulus_methods():
    ei = 120000.0
    lay = SoilLayer("s", 10, 18, 20, 30, 0, k_s=12345.0, k_s_method="manual", E_M=20, alpha=1 / 3)
    assert subgrade_modulus(lay, ei, 5.0) == 12345.0
    lay.k_s_method = "menard"
    a = 2 * 5.0 / 3
    expected = 20000.0 / ((1 / 3) * a / 2 + 0.133 * (9 * a) ** (1 / 3))
    assert subgrade_modulus(lay, ei, 5.0) == pytest.approx(expected)
    assert subgrade_modulus(lay, ei, 0.3) == pytest.approx(   # a floored at 0.6 m
        20000.0 / ((1 / 3) * 0.6 / 2 + 0.133 * (9 * 0.6) ** (1 / 3)))
    lay.k_s_method = "schmitt"
    assert subgrade_modulus(lay, ei, 5.0) == pytest.approx(
        2.1 * (20000.0 / (1 / 3)) ** (4 / 3) / ei ** (1 / 3))
    lay.E_M = 0.0
    with pytest.raises(ValueError):
        subgrade_modulus(lay, ei, 5.0)


def test_menard_ks_runs_end_to_end():
    cfg = anchored_cfg()
    cfg['soil_profile'][0].update({'k_s_method': 'menard', 'E_M': 15.0, 'alpha': 0.33})
    w, e = le(cfg)
    r = BeamSpringAnalysis(w, e).run()
    name, ks, method = r['k_s_table'][0]
    assert method == 'menard' and ks > 0
    assert r['anchor_forces'][1.5] > 0


def test_dewatered_stage_water_differs_from_final_mode():
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    cfg['analysis_options']['is_seismic'] = False
    cfg['loads']['water_level_passive'] = 3.0          # water high in front of the wall
    w, e = le(cfg)
    r_final = BeamSpringAnalysis(w, e, {'water_mode': 'final'}).run()
    r_dry = BeamSpringAnalysis(w, e, {'water_mode': 'dewatered'}).run()
    # intermediate stage (excavation to 4.5 m) sees a different water regime:
    # less water in front (more driving load) but a stronger, non-buoyant
    # passive wedge -> the two modes must differ, sign is case-dependent
    assert r_dry['stages'][2]['w_max_mm'] != pytest.approx(
        r_final['stages'][2]['w_max_mm'], rel=0.01)
    # final stage is identical in load, results close
    assert r_dry['m_max_abs'] == pytest.approx(r_final['m_max_abs'], rel=0.15)


def test_hydrodynamic_load_included_in_beam_spring():
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    w, e = le(cfg)
    r_on = BeamSpringAnalysis(w, e).run()
    cfg2 = copy.deepcopy(cfg); cfg2['analysis_options']['hydrodynamic'] = False
    w2, e2 = le(cfg2)
    r_off = BeamSpringAnalysis(w2, e2).run()
    assert sum(r_on['anchor_forces'].values()) > sum(r_off['anchor_forces'].values())


def test_inclined_anchor_report_in_beam_spring():
    cfg = anchored_cfg(angle=20.0, EA=100000.0, free_length=10.0, spacing=2.0)
    w, e = le(cfg)
    r = BeamSpringAnalysis(w, e).run()
    rep = r['anchor_report'][1.5]
    assert rep['T_axial'] == pytest.approx(r['anchor_forces'][1.5] / np.cos(np.radians(20)) * 2)
    assert r['vertical_load'] == pytest.approx(rep['V'])
    assert r['vertical_status'] in ("OK", "NOT OK - VERTICAL CAPACITY EXCEEDED!")
