"""
Regression / verification tests for analysis_engine.py.
Run with:  pytest -q test_engine.py
"""
import copy

import numpy as np
import pytest
from scipy.optimize import brentq

from lythosspwa.analysis_engine import AnalysisEngine, RetainingWall
from lythosspwa.config import DEFAULT_CONFIG


def base_cfg(**over):
    """Dry sand, Rankine (delta=0), no surcharge, unfactored strength."""
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    cfg['analysis_options'].update({'anchors': [], 'is_seismic': False})
    cfg['geometry'].update({'excavation_depth_H': 5.0, 'wall_friction_delta': 0.0,
                            'backfill_slope_beta': 0.0, 'dredge_line_slope_alpha': 0.0})
    cfg['loads'].update({'surcharge_load': 0.0, 'water_level_active': 100.0,
                         'water_level_passive': 100.0})
    cfg['factors'].update({'FS_friction_angle': 1.0, 'FS_cohesion': 1.0})
    cfg['soil_profile'] = [{"name": "sand", "thickness": 40.0, "gamma": 18.0,
                            "gamma_sat": 20.0, "phi": 30.0, "cohesion": 0.0}]
    for k, v in over.items():
        cfg[k].update(v)
    return cfg


def run(cfg):
    w = RetainingWall(cfg)
    a = AnalysisEngine(w)
    a.run()
    return w, a


# ----------------------------------------------------------------------
# 1. Closed-form checks (Rankine, dry sand)
# ----------------------------------------------------------------------
def test_cantilever_matches_closed_form():
    """Simplified free-earth: Ka(H+D)^3 = Kp D^3  ->  D = H / ((Kp/Ka)^(1/3) - 1)."""
    w, a = run(base_cfg())
    ka, kp = 1 / 3, 3.0
    d_exact = w.h / ((kp / ka) ** (1 / 3) - 1)
    assert a.d_required == pytest.approx(d_exact, rel=1e-4)
    # moment closes at the theoretical toe, toe shear = reaction R
    assert abs(a.results['toe_moment']) < 1e-3 * a.results['m_max_abs']
    assert a.results['toe_shear'] < 0


def test_single_anchor_matches_closed_form():
    """Free-earth anchored: moment about anchor of Pa and Pp -> D, then T = Pa - Pp."""
    za = 1.0
    cfg = base_cfg(analysis_options={'anchors': [{'depth': za}]})
    w, a = run(cfg)
    g, h, ka, kp = 18.0, w.h, 1 / 3, 3.0

    def f(d):
        pa = 0.5 * ka * g * (h + d) ** 2
        pp = 0.5 * kp * g * d ** 2
        return pa * (2 / 3 * (h + d) - za) - pp * (h + 2 / 3 * d - za)

    d_exact = brentq(f, 0.01, 50)
    t_exact = 0.5 * ka * g * (h + d_exact) ** 2 - 0.5 * kp * g * d_exact ** 2
    assert a.d_required == pytest.approx(d_exact, rel=1e-4)
    assert a.t_anchors[za] == pytest.approx(t_exact, rel=1e-3)
    # equilibrium closes at the theoretical toe
    assert abs(a.results['toe_shear']) < 1e-3 * abs(a.t_anchors[za])
    assert abs(a.results['toe_moment']) < 1e-3 * a.results['m_max_abs']


# ----------------------------------------------------------------------
# 2. Bugs fixed in v0.2
# ----------------------------------------------------------------------
def test_layered_passive_uses_true_stratigraphy():
    cfg = base_cfg(geometry={'excavation_depth_H': 4.0})
    cfg['soil_profile'] = [
        {"name": "soft", "thickness": 4.0, "gamma": 10.0, "gamma_sat": 10.0, "phi": 30, "cohesion": 0},
        {"name": "dense", "thickness": 30.0, "gamma": 20.0, "gamma_sat": 20.0, "phi": 30, "cohesion": 0},
    ]
    w = RetainingWall(cfg)
    a = AnalysisEngine(w)
    p = a._calculate_pressure_at_depth(6.0)          # 2 m into the dense layer
    assert p['earth_passive'] == pytest.approx(3.0 * 2.0 * 20.0, rel=1e-6)


def test_free_water_above_dredge_line_on_passive_side():
    cfg = copy.deepcopy(DEFAULT_CONFIG)                # hw_passive = 7 < H = 8
    a = AnalysisEngine(RetainingWall(cfg))
    p = a._calculate_pressure_at_depth(7.5)
    assert p['water_passive'] == pytest.approx(0.5 * 9.81, rel=1e-6)
    assert p['earth_passive'] == 0.0


def mo_textbook(phi, delta, beta, kh, kv):
    phi, delta, beta = map(np.radians, (phi, delta, beta))
    th = np.arctan(kh / (1 - kv))
    kae = np.cos(phi - th) ** 2 / (np.cos(th) * np.cos(delta + th) * (
        1 + np.sqrt(np.sin(phi + delta) * np.sin(phi - th - beta) / (np.cos(delta + th) * np.cos(beta)))) ** 2)
    kpe = np.cos(phi - th) ** 2 / (np.cos(th) * np.cos(delta + th) * (
        1 - np.sqrt(np.sin(phi + delta) * np.sin(phi - th) / (np.cos(delta + th)))) ** 2)
    return kae, kpe


@pytest.mark.parametrize("kh", [0.1, 0.2, 0.3])
def test_mononobe_okabe_matches_textbook(kh):
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    cfg['analysis_options']['kh'] = kh
    w = RetainingWall(cfg)
    a = AnalysisEngine(w)
    phi_d = 32.0
    kae, kpe = a._get_pressure_coeffs(phi_d)
    kae_ref, kpe_ref = mo_textbook(phi_d, 20.0, 0.0, kh, 0.0)
    assert kae == pytest.approx(kae_ref, rel=1e-9)
    assert kpe == pytest.approx(kpe_ref, rel=1e-9)


def test_static_coulomb_reduces_to_rankine_when_delta_zero():
    a = AnalysisEngine(RetainingWall(base_cfg()))
    ka, kp = a._get_pressure_coeffs(30.0)
    assert ka == pytest.approx(1 / 3, rel=1e-9)
    assert kp == pytest.approx(3.0, rel=1e-9)


# ----------------------------------------------------------------------
# 3. Deflection boundary conditions
# ----------------------------------------------------------------------
def test_cantilever_deflection_boundary_conditions():
    w, a = run(base_cfg())
    r, d = a.results['rotation'], a.results['deflection']
    assert r[-1] == pytest.approx(0.0, abs=1e-12)
    assert d[-1] == pytest.approx(0.0, abs=1e-12)
    assert abs(d[0]) == pytest.approx(a.results['actual_max_deflection'] / 1000, rel=1e-9)
    assert d[0] > 0            # top moves towards the excavation


def test_anchored_deflection_boundary_conditions():
    za = 1.5
    w, a = run(base_cfg(analysis_options={'anchors': [{'depth': za}]}))
    z, d = a.results['z_vals'], a.results['deflection']
    assert np.interp(za, z, d) == pytest.approx(0.0, abs=1e-9)
    assert d[-1] == pytest.approx(0.0, abs=1e-9)


# ----------------------------------------------------------------------
# 4. Default project runs and closes; validation
# ----------------------------------------------------------------------
def test_default_config_single_anchor_closes():
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    cfg['analysis_options']['anchors'] = [{'depth': 1.5}]
    w, a = run(cfg)
    assert a.t_anchors[1.5] > 0
    assert abs(a.results['toe_moment']) < 1e-3 * a.results['m_max_abs']
    assert a.d_design >= a.d_required * 1.2


def test_anchor_deeper_than_excavation_is_rejected():
    cfg = base_cfg(analysis_options={'anchors': [{'depth': 5.0}]})
    with pytest.raises(ValueError):
        RetainingWall(cfg)


# ----------------------------------------------------------------------
# 5. v0.4 features: seismic water, inclined anchors
# ----------------------------------------------------------------------
def test_submerged_theta_increases_active_coefficient():
    cfg = copy.deepcopy(DEFAULT_CONFIG)          # kh = 0.1, hw_active = 4 m
    a = AnalysisEngine(RetainingWall(cfg))
    soil = a.wall.soil_profile.get_properties_at_depth(6.0, True, (1.25, 1.25))
    f_dry = a._theta_factor(2.0, 4.0, soil)
    f_wet = a._theta_factor(6.0, 4.0, soil)
    assert f_dry == 1.0
    assert f_wet == pytest.approx(21.0 / (21.0 - 9.81))
    kae_dry, _ = a._get_pressure_coeffs(soil.phi, f_dry)
    kae_wet, _ = a._get_pressure_coeffs(soil.phi, f_wet)
    assert kae_wet > kae_dry
    cfg['analysis_options']['submerged_theta'] = False
    b = AnalysisEngine(RetainingWall(cfg))
    assert b._theta_factor(6.0, 4.0, soil) == 1.0


def test_westergaard_pressure_resultant():
    cfg = copy.deepcopy(DEFAULT_CONFIG)          # free water from 7 m to 8 m, kh = 0.1
    a = AnalysisEngine(RetainingWall(cfg))
    hw = 1.0
    total, _ = a._robust_quad(a.hydrodynamic_pressure, 7.0, 8.0)
    assert total == pytest.approx(7 / 12 * 0.1 * 9.81 * hw ** 2, rel=1e-6)
    assert a.hydrodynamic_pressure(6.9) == 0.0 and a.hydrodynamic_pressure(8.1) == 0.0
    assert a._calculate_pressure_at_depth(7.5)['hydrodynamic'] > 0
    cfg['analysis_options']['hydrodynamic'] = False
    assert AnalysisEngine(RetainingWall(cfg)).hydrodynamic_pressure(7.5) == 0.0


def test_inclined_anchor_stiffness_and_report():
    cfg = base_cfg(analysis_options={'anchors': [
        {'depth': 1.0, 'angle': 20.0, 'EA': 100000.0, 'free_length': 10.0,
         'spacing': 2.0, 'prestress': 200.0}]})
    w = RetainingWall(cfg)
    a = w.anchors[0]
    cos20 = np.cos(np.radians(20))
    assert a['stiffness'] == pytest.approx(100000 / (10 * 2) * cos20 ** 2)
    assert a['prestress_h'] == pytest.approx(200 * cos20 / 2)
    rep = RetainingWall.anchor_report(a, 100.0)
    assert rep['T_axial'] == pytest.approx(100 / cos20 * 2)
    assert rep['V'] == pytest.approx(100 * np.tan(np.radians(20)))
    e = AnalysisEngine(w); e.run()
    assert e.results['vertical_load'] > 0
    assert e.results['vertical_resistance'] == 0.0      # delta = 0 in base_cfg
    assert e.results['vertical_status'].startswith("NOT OK")


def test_vertical_resistance_positive_with_wall_friction():
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    cfg['analysis_options']['anchors'] = [{'depth': 1.5, 'angle': 15.0}]
    w = RetainingWall(cfg); e = AnalysisEngine(w); e.run()
    assert e.results['vertical_resistance'] > 0
    assert e.results['anchor_report'][1.5]['V'] == pytest.approx(
        e.t_anchors[1.5] * np.tan(np.radians(15)))
