"""
Beam-on-elastoplastic-springs (Winkler / subgrade reaction) analysis of a
sheet pile wall — the "advanced" companion of the free-earth support
analysis in analysis_engine.py.

Model
-----
* The wall is an Euler-Bernoulli beam (Hermite cubic elements, 2 DOF per
  node: horizontal displacement w [m, positive towards the excavation]
  and rotation theta).
* Each side of the wall is represented by nodal soil springs whose
  pressure p(w) is linear elastic between the active and passive limit
  pressures (Coulomb / Mononobe-Okabe, same coefficients as the LE
  analysis) and constant once a limit is reached:

      retained side :  p = clip(p_ref - k_s (w - w_ref), p_a, p_p)
      excavation side: p = clip(p_ref + k_s (w - w_ref), p_a, p_p)

  Springs start from the at-rest pressure K0 * sigma'_v (K0 = 1 - sin phi,
  Jaky) and remember their state between construction stages.
* Water pressures are applied as fixed loads (no seepage correction).
* Anchors are tension-only springs installed at a given stage:
      T = max(0, P_prestress + k_a (w - w_install))
* Construction stages are generated automatically: excavate to
  (anchor depth + overdig), install the anchor, ... , final excavation
  to H. The non-staged variant installs all anchors wished-in-place and
  excavates in one step.
* Equilibrium is solved with Newton-Raphson on the full system; internal
  forces are recovered by integrating the converged nodal loads from the
  top (so V and M close at the toe within round-off).

The retained side is assumed to extend over the full wall length; the
excavation side is active only below the current dredge level.

Limitations (deliberately simple first version): single-value k_s per
layer (no depth or stress dependency), horizontal anchor forces only,
no seepage, no wall/soil creep, no reloading hysteresis.
"""

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy.integrate import cumulative_trapezoid

from .analysis_engine import MM_PER_M, AnalysisEngine, RetainingWall

DEFAULT_BS_OPTIONS = {
    "enabled": True,
    "staged": True,
    "overdig": 0.5,
    "embedment": 0.0,       # 0 -> D_design from the LE analysis
    "element_size": 0.1,
    "water_mode": "final",   # "final": passive water level as given at every stage
                             # "dewatered": excavation kept dry (water at the current
                             #              dredge level) until the final stage
    "max_iter": 300,
    "tol": 1e-7,
}


def subgrade_modulus(layer, ei: float, embedment: float) -> float:
    """
    Horizontal subgrade reaction modulus k_s (kN/m^3) for a soil layer.

    manual  : the value entered by the user.
    menard  : Menard-Bourdon (1964)
                  k_s = E_M / [ alpha*a/2 + 0.133*(9a)^alpha ],  a = max(2D/3, 0.6 m)
              with E_M the pressuremeter modulus, alpha the rheological
              coefficient and a the characteristic length (2/3 of the
              embedment for a wall).
    schmitt : Schmitt (1995)
                  k_s = 2.1 * (E_M/alpha)^(4/3) / (EI)^(1/3)
              (E_M in kPa, EI in kNm^2/m).
    """
    method = getattr(layer, 'k_s_method', 'manual')
    if method == 'manual':
        return float(layer.k_s)
    e_m = float(layer.E_M) * 1000.0          # MPa -> kPa
    alpha = float(layer.alpha)
    if e_m <= 0 or alpha <= 0:
        raise ValueError(f"Layer '{layer.name}': E_M and alpha must be > 0 "
                         f"for the '{method}' method.")
    if method == 'menard':
        a = max(2.0 * embedment / 3.0, 0.6)
        return e_m / (alpha * a / 2.0 + 0.133 * (9.0 * a) ** alpha)
    if method == 'schmitt':
        return 2.1 * (e_m / alpha) ** (4.0 / 3.0) / ei ** (1.0 / 3.0)
    raise ValueError(f"Unknown k_s method '{method}'.")


class BeamSpringAnalysis:
    """Winkler beam-spring analysis driven by a RetainingWall/AnalysisEngine pair."""

    def __init__(self, wall: RetainingWall, engine: AnalysisEngine,
                 options: Optional[Dict[str, Any]] = None):
        self.wall = wall
        self.engine = engine
        # precedence: explicit options > project config > defaults
        self.opt = {**DEFAULT_BS_OPTIONS, **wall.beam_spring_options,
                    **(options or {})}
        self.results: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # geometry & mesh
    # ------------------------------------------------------------------
    def _embedment(self) -> float:
        d = float(self.opt.get("embedment") or 0.0)
        if d > 0:
            return d
        if self.engine.d_design is None:
            raise RuntimeError("Run the LE analysis first or give an embedment.")
        return float(self.engine.d_design)

    def _build_mesh(self, length: float, stage_depths: List[float]) -> np.ndarray:
        w = self.wall
        le = float(self.opt["element_size"])
        pts = set(np.round(np.arange(0.0, length, le), 6).tolist())
        pts |= {0.0, length, w.h, w.hw_active, w.hw_passive}
        pts |= set(w.anchor_depths) | set(stage_depths)
        pts |= set(w.soil_profile.layer_boundaries())
        z = np.array(sorted(p for p in pts if 0.0 <= p <= length))
        keep = [0]
        for i in range(1, len(z)):
            if z[i] - z[keep[-1]] > 1e-3:
                keep.append(i)
        z = z[keep]
        if length - z[-1] > 1e-9:
            z = np.append(z, length)
        return z

    @staticmethod
    def _tributary(z: np.ndarray) -> np.ndarray:
        lt = np.zeros_like(z)
        lt[0] = (z[1] - z[0]) / 2
        lt[-1] = (z[-1] - z[-2]) / 2
        lt[1:-1] = (z[2:] - z[:-2]) / 2
        return lt

    def _beam_stiffness(self, z: np.ndarray) -> np.ndarray:
        ei = self.wall.ei
        n = len(z)
        k = np.zeros((2 * n, 2 * n))
        for e in range(n - 1):
            L = z[e + 1] - z[e]
            c = ei / L ** 3
            ke = c * np.array([
                [12, 6 * L, -12, 6 * L],
                [6 * L, 4 * L * L, -6 * L, 2 * L * L],
                [-12, -6 * L, 12, -6 * L],
                [6 * L, 2 * L * L, -6 * L, 4 * L * L]])
            idx = [2 * e, 2 * e + 1, 2 * e + 2, 2 * e + 3]
            k[np.ix_(idx, idx)] += ke
        return k

    # ------------------------------------------------------------------
    # soil states
    # ------------------------------------------------------------------
    def _soil_arrays(self, z: np.ndarray, side: str, h_s: float,
                     hw: float, embedment: float = 0.0) -> Dict[str, np.ndarray]:
        """
        Limit pressures, at-rest pressure, spring stiffness and pore
        pressure at every node for one side of the wall.
        side = 'ret' (retained, springs everywhere) or 'exc' (excavation
        side, springs only below the dredge level h_s).
        """
        w, eng = self.wall, self.engine
        factors = (w.fs_phi, w.fs_c)
        kv_factor = (1.0 - w.kv) if w.is_seismic else 1.0
        n = len(z)
        pa = np.zeros(n); pp = np.zeros(n); p0 = np.zeros(n)
        ks = np.zeros(n); u = np.zeros(n); sv = np.zeros(n)
        active = np.zeros(n, dtype=bool)
        for i, zi in enumerate(z):
            u[i] = max(0.0, zi - hw) * w.soil_profile.gamma_water
            if side == 'exc' and zi <= h_s + 1e-9:
                continue
            z_top = 0.0 if side == 'ret' else h_s
            soil_d = w.soil_profile.get_properties_at_depth(zi, True, factors)
            soil_c = w.soil_profile.get_properties_at_depth(zi)
            s_eff, _ = w.soil_profile.calculate_effective_stress(zi, hw, z_top=z_top)
            if side == 'ret':
                s_eff += w.surcharge
            ka, kp = eng._get_pressure_coeffs(
                soil_d.phi, eng._theta_factor(zi, hw, soil_d))
            k0 = 1.0 - np.sin(np.radians(soil_c.phi))
            pa[i] = max(0.0, ka * kv_factor * s_eff - 2 * soil_d.cohesion * np.sqrt(ka))
            pp[i] = max(pa[i], kp * kv_factor * s_eff + 2 * soil_d.cohesion * np.sqrt(kp))
            p0[i] = min(max(k0 * s_eff, pa[i]), pp[i])
            ks[i] = subgrade_modulus(soil_c, w.ei, embedment)
            sv[i] = s_eff
            active[i] = True
        return {'pa': pa, 'pp': pp, 'p0': p0, 'k': ks, 'u': u,
                'sv': sv, 'active': active}

    # ------------------------------------------------------------------
    # non-linear solve for one stage
    # ------------------------------------------------------------------
    def _solve(self, u: np.ndarray, kb: np.ndarray, z: np.ndarray,
               lt: np.ndarray, ret: Dict[str, np.ndarray],
               exc: Dict[str, np.ndarray], water_net: np.ndarray,
               anchors: List[Dict[str, Any]]) -> Tuple[np.ndarray, int]:
        n = len(z)
        max_iter, tol = int(self.opt["max_iter"]), float(self.opt["tol"])
        w_idx = np.arange(0, 2 * n, 2)

        def assemble(uv):
            wv = uv[w_idx]
            p_ret = np.clip(ret['ref'] - ret['k'] * (wv - ret['wref']), ret['pa'], ret['pp'])
            p_exc = np.where(exc['active'],
                             np.clip(exc['ref'] + exc['k'] * (wv - exc['wref']),
                                     exc['pa'], exc['pp']), 0.0)
            q = p_ret + water_net - p_exc
            f = np.zeros(2 * n)
            f[w_idx] = q * lt
            dk = np.zeros(n)
            el_ret = (p_ret > ret['pa'] + 1e-12) & (p_ret < ret['pp'] - 1e-12)
            el_exc = exc['active'] & (p_exc > exc['pa'] + 1e-12) & (p_exc < exc['pp'] - 1e-12)
            dk[el_ret] += ret['k'][el_ret] * lt[el_ret]
            dk[el_exc] += exc['k'][el_exc] * lt[el_exc]
            forces = []
            for a in anchors:
                node = a['node']
                t = max(0.0, a['prestress_h'] + a['stiffness'] * (wv[node] - a['w_inst']))
                f[2 * node] -= t
                if t > 0.0:
                    dk[node] += a['stiffness']
                forces.append(t)
            return f, dk, p_ret, p_exc, forces

        u = u.copy()
        f, dk, *_ = assemble(u)
        r = f - kb @ u
        scale = np.linalg.norm(f) + 1.0
        prev = np.linalg.norm(r)
        for it in range(1, max_iter + 1):
            if prev / scale < tol:
                break
            kt = kb.copy()
            kt[w_idx, w_idx] += dk
            try:
                du = np.linalg.solve(kt, r)
            except np.linalg.LinAlgError as exc_:
                raise RuntimeError(
                    "Beam-spring system is singular: the wall is kinematically "
                    "unstable (all soil springs at their limits). Increase the "
                    "embedment or the soil stiffness.") from exc_
            # damped Newton with simple back-tracking
            alpha = 1.0
            for _ in range(8):
                u_try = u + alpha * du
                f, dk, *_ = assemble(u_try)
                r_try = f - kb @ u_try
                if np.linalg.norm(r_try) <= prev * (1 - 1e-4 * alpha) or alpha < 0.02:
                    break
                alpha *= 0.5
            u, r, prev = u_try, r_try, np.linalg.norm(r_try)
            if np.max(np.abs(u[w_idx])) > 2.0:
                raise RuntimeError(
                    "Beam-spring analysis diverged (displacement > 2 m): the wall "
                    "is unstable for this embedment / soil stiffness.")
        else:
            raise RuntimeError(
                f"Beam-spring analysis did not converge in {max_iter} iterations "
                f"(residual {prev / scale:.2e}).")
        self._last = assemble(u)
        return u, it

    # ------------------------------------------------------------------
    # staged construction driver
    # ------------------------------------------------------------------
    def _stage_plan(self) -> List[Tuple[str, Any]]:
        w = self.wall
        plan: List[Tuple[str, Any]] = []
        if self.opt["staged"] and w.anchors:
            overdig = float(self.opt["overdig"])
            h_cur = 0.0
            for a in w.anchors:
                h_i = min(a['depth'] + overdig, w.h)
                if h_i > h_cur + 1e-9:
                    plan.append(('excavate', h_i)); h_cur = h_i
                plan.append(('anchor', a))
            if h_cur < w.h - 1e-9:
                plan.append(('excavate', w.h))
        else:
            for a in w.anchors:
                plan.append(('anchor', a))
            plan.append(('excavate', w.h))
        return plan

    def run(self) -> Dict[str, Any]:
        w = self.wall
        d = self._embedment()
        length = w.h + d
        plan = self._stage_plan()
        stage_depths = [h for kind, h in plan if kind == 'excavate']
        z = self._build_mesh(length, stage_depths)
        n = len(z)
        lt = self._tributary(z)
        kb = self._beam_stiffness(z)

        # initial (at-rest) state, no excavation, equal water on both sides
        ret0 = self._soil_arrays(z, 'ret', 0.0, w.hw_active, d)
        exc0 = self._soil_arrays(z, 'exc', 0.0, w.hw_active, d)
        hydro = np.array([self.engine.hydrodynamic_pressure(zi) for zi in z])
        n_exc = sum(1 for kind, _ in plan if kind == 'excavate')
        i_exc = 0
        ret = {**ret0, 'ref': ret0['p0'].copy(), 'wref': np.zeros(n)}
        exc = {**exc0, 'ref': exc0['p0'].copy(), 'wref': np.zeros(n)}
        water_net = ret0['u'] - exc0['u']

        u = np.zeros(2 * n)
        anchors: List[Dict[str, Any]] = []
        stages: List[Dict[str, Any]] = []
        h_cur, total_it = 0.0, 0

        for kind, payload in plan:
            solve_now = True
            if kind == 'excavate':
                h_new = float(payload)
                i_exc += 1
                if self.opt["water_mode"] == "dewatered" and i_exc < n_exc:
                    hw_exc = max(h_new, w.hw_passive)
                else:
                    hw_exc = w.hw_passive
                new = self._soil_arrays(z, 'exc', h_new, hw_exc, d)
                ratio = np.ones(n)
                both = exc['active'] & new['active'] & (exc['sv'] > 1e-9)
                ratio[both] = new['sv'][both] / exc['sv'][both]
                ref = np.where(new['active'], exc['ref'] * ratio, 0.0)
                # freshly activated springs (never happens with monotonic
                # excavation, kept for safety) start at rest
                fresh = new['active'] & ~exc['active']
                ref[fresh] = new['p0'][fresh]
                ref = np.where(new['active'], np.clip(ref, new['pa'], new['pp']), 0.0)
                exc = {**new, 'ref': ref, 'wref': u[0::2].copy()}
                water_net = ret['u'] - new['u']
                if i_exc == n_exc:          # final stage: design earthquake
                    water_net = water_net + hydro
                h_cur = h_new
                label = ('excavate', h_new)
            else:
                a = payload
                node = int(np.argmin(np.abs(z - a['depth'])))
                anchors.append({**a, 'node': node, 'w_inst': float(u[2 * node])})
                label = ('anchor', a['depth'])
                solve_now = a['prestress_h'] > 0.0 and h_cur > 0.0

            if solve_now:
                u, it = self._solve(u, kb, z, lt, ret, exc, water_net, anchors)
                total_it += it
            else:
                self._last = None
            self._record_stage(stages, label, h_cur, z, u, anchors)

            # springs remember their state for the next stage
            if self._last is not None:
                _, _, p_ret, p_exc, _ = self._last
                ret = {**ret, 'ref': p_ret.copy(), 'wref': u[0::2].copy()}
                exc = {**exc, 'ref': p_exc.copy(), 'wref': u[0::2].copy()}

        self._finalize(z, lt, u, ret, exc, water_net, anchors, stages,
                       d, length, total_it)
        return self.results

    # ------------------------------------------------------------------
    def _internal_forces(self, z, u, ret, exc, water_net, anchors):
        wv = u[0::2]
        p_ret = np.clip(ret['ref'] - ret['k'] * (wv - ret['wref']), ret['pa'], ret['pp'])
        p_exc = np.where(exc['active'],
                         np.clip(exc['ref'] + exc['k'] * (wv - exc['wref']),
                                 exc['pa'], exc['pp']), 0.0)
        q = p_ret + water_net - p_exc
        v = cumulative_trapezoid(q, x=z, initial=0.0)
        forces = {}
        for a in anchors:
            t = max(0.0, a['prestress_h'] + a['stiffness'] * (wv[a['node']] - a['w_inst']))
            v[z >= z[a['node']] - 1e-12] -= t
            forces[a['depth']] = t
        m = self._fe_moment(z, u)
        return p_ret, p_exc, q, v, m, forces

    def _fe_moment(self, z: np.ndarray, u: np.ndarray) -> np.ndarray:
        """
        Bending moment M = EI w'' from the Hermite element curvatures,
        averaged at shared nodes (FE-consistent; the free ends come out
        ~0 with a fine mesh). Sign convention as in the LE analysis:
        dM/dz = V, dV/dz = q (q positive towards the excavation).
        """
        ei, n = self.wall.ei, len(z)
        m = np.zeros(n)
        count = np.zeros(n)
        for e in range(n - 1):
            L = z[e + 1] - z[e]
            w1, t1, w2, t2 = u[2 * e:2 * e + 4]
            k1 = (-6 * w1 / L ** 2 - 4 * t1 / L + 6 * w2 / L ** 2 - 2 * t2 / L)
            k2 = (6 * w1 / L ** 2 + 2 * t1 / L - 6 * w2 / L ** 2 + 4 * t2 / L)
            m[e] += ei * k1; m[e + 1] += ei * k2
            count[e] += 1; count[e + 1] += 1
        return m / count

    def _record_stage(self, stages, label, h_cur, z, u, anchors):
        kind, value = label
        if self._last is None:
            stages.append({'kind': kind, 'value': value, 'h': h_cur, 'solved': False})
            return
        _, _, _, _, forces = self._last
        wv = u[0::2]
        stages.append({
            'kind': kind, 'value': value, 'h': h_cur, 'solved': True,
            'w_max_mm': float(wv[np.argmax(np.abs(wv))] * MM_PER_M),
            'anchor_forces': {a['depth']: float(t) for a, t in zip(anchors, forces)},
        })

    def _finalize(self, z, lt, u, ret, exc, water_net, anchors, stages,
                  d, length, total_it):
        w = self.wall
        p_ret, p_exc, q, v, m, forces = self._internal_forces(
            z, u, ret, exc, water_net, anchors)
        wv, th = u[0::2], u[1::2]
        imax = int(np.argmax(np.abs(wv)))
        m_max_abs = float(np.max(np.abs(m)))
        actual_stress = m_max_abs / w.w_modulus if w.w_modulus > 1e-9 else float('inf')

        exc_mask = exc['active']
        pp_sum = float(np.sum(exc['pp'][exc_mask] * lt[exc_mask]))
        # share of the passive resistance that is mobilised (1 = fully passive)
        passive_mob = float(np.sum(p_exc[exc_mask] * lt[exc_mask]) / pp_sum) if pp_sum > 0 else 0.0
        # share of the retained face that has reached the active limit
        at_active = p_ret <= ret['pa'] + 1e-6
        active_mob = float(np.sum(lt[at_active]) / np.sum(lt))

        delta_max_mm = abs(float(wv[imax]) * MM_PER_M)
        divisor = w.config['deflection_codes'].get(
            w.config['analysis_options']['deflection_check_code'])
        if divisor is None:
            defl_status, allowable_mm = "N/A", float('inf')
        else:
            allowable_mm = w.h / divisor * MM_PER_M
            defl_status = "OK" if delta_max_mm <= allowable_mm else "NOT OK - DEFLECTION EXCEEDED!"

        # moment per stage (recomputed quickly for the table)
        for s in stages:
            s.setdefault('m_max_abs', None)
        stages[-1]['m_max_abs'] = m_max_abs

        anchor_report = {a['depth']: RetainingWall.anchor_report(a, forces[a['depth']])
                         for a in anchors}
        ks_table = [(layer.name, subgrade_modulus(layer, w.ei, d),
                     getattr(layer, 'k_s_method', 'manual'))
                    for layer in w.soil_profile.layers]
        self.results = {
            'anchor_report': anchor_report, 'k_s_table': ks_table,
            'z_vals': z, 'deflection': wv, 'rotation': th, 'shear': v, 'moment': m,
            'net_pressure': q, 'p_ret': p_ret, 'p_exc': p_exc,
            'pa_ret': ret['pa'], 'pp_ret': ret['pp'], 'p0_ret': ret['p0'],
            'pa_exc': np.where(exc_mask, exc['pa'], 0.0),
            'pp_exc': np.where(exc_mask, exc['pp'], 0.0),
            'water_net': water_net,
            'anchor_forces': forces, 'stages': stages,
            'embedment': d, 'length': length, 'iterations': total_it,
            'm_max': float(np.max(m)), 'm_min': float(np.min(m)), 'm_max_abs': m_max_abs,
            'v_max': float(np.max(v)), 'v_min': float(np.min(v)),
            'delta_max': float(wv[imax]), 'actual_max_deflection': delta_max_mm,
            'allowable_deflection': allowable_mm, 'deflection_check_status': defl_status,
            'toe_shear': float(v[-1]), 'toe_moment': float(m[-1]),
            'actual_stress': actual_stress,
            'stress_check_status': "OK" if actual_stress <= w.f_allowable
            else "NOT OK - STRESS EXCEEDED!",
            'passive_mobilization': passive_mob,
            'active_mobilization': active_mob,
        }
        self.engine._perform_vertical_check(forces, self.results, length)
