"""
Figures for parametric / reliability studies (study.py).

    plot_oat      one-at-a-time sweep curves: rows = variables, cols = outputs
    plot_scatter  output vs every input (LHS / MC / grid) with Spearman rho
    plot_hist     histograms + empirical CDFs of the key outputs with the
                  allowable values and the failure probabilities
    plot_tornado  ranked Spearman rho / SRC bars for one output
"""

from typing import Dict, List, Optional, Sequence

import numpy as np
from matplotlib.figure import Figure
from scipy import stats

from .config import PLOT_PALETTE
from .plot_style import label_box, style_axis, style_figure
from .study import OUTPUTS, Study

UNITS = {k: u for k, _, u in OUTPUTS}
COLORS = {"M": PLOT_PALETTE["moment"], "T": PLOT_PALETTE["net_pressure"],
          "defl": PLOT_PALETTE["deflection"], "d": PLOT_PALETTE["passive"],
          "sigma": PLOT_PALETTE["active"], "mob": PLOT_PALETTE["shear"]}


def _color(key: str) -> str:
    for k, c in COLORS.items():
        if key.startswith(k):
            return c
    return "#555"


def _label(lang: Dict[str, str], key: str) -> str:
    return lang.get(f"out_{key}", key)


def _var_label(lang: Dict[str, str], study: Study, path: str) -> str:
    for v in study.variables:
        if v.path == path:
            return v.label if v.label != path else lang.get(f"var_{path.split('.')[-1]}", path)
    return path


def default_outputs(study: Study) -> List[str]:
    keys = ["M_le", "T_le", "defl_le", "d_req"]
    if study.summary.get("n_ok_bs", 0) > 0:
        keys = ["M_bs", "T_bs", "defl_bs", "d_req"]
    if not any(v for v in study.base_cfg.get("analysis_options", {}).get("anchors", [])):
        keys = [k for k in keys if not k.startswith("T")] + ["M_le"]
    return keys[:4]


def _ok_rows(study: Study):
    return [r for r in study.rows if r["ok"]]


def plot_oat(fig: Figure, study: Study, lang: Dict[str, str],
             outputs: Optional[Sequence[str]] = None, theme: str = "light") -> None:
    th = style_figure(fig, theme)
    outputs = list(outputs or default_outputs(study))
    oat = study.summary.get("oat", {})
    paths = [p for p in study.paths if p in oat]
    if not paths:
        _empty(fig, lang.get("study_no_data", "no data"), th)
        return
    axes = fig.subplots(len(paths), len(outputs), squeeze=False)
    for i, p in enumerate(paths):
        data = oat[p]
        x = np.array(data["x"])
        for j, key in enumerate(outputs):
            ax = axes[i, j]
            y = np.array(data[key])
            m = np.isfinite(y)
            ax.plot(x[m], y[m], "o-", color=_color(key), ms=4, lw=1.8)
            base = next((v.base for v in study.variables if v.path == p), None)
            if base is not None:
                ax.axvline(base, color=th['fg_dim'], ls=":", lw=1)
            style_axis(ax, th)
            if i == len(paths) - 1:
                ax.set_xlabel(_var_label(lang, study, p), fontsize=9)
            if i == 0:
                ax.set_title(f"{_label(lang, key)} ({UNITS.get(key, '')})", fontsize=10, color=th['fg'])
    fig.suptitle(lang.get("study_fig_oat", "One-at-a-time sweep"), fontsize=12, color=th['fg'])
    fig.tight_layout(rect=[0, 0, 1, 0.95])


def plot_scatter(fig: Figure, study: Study, lang: Dict[str, str], output: str,
                 theme: str = "light") -> None:
    th = style_figure(fig, theme)
    rows = _ok_rows(study)
    if not rows:
        _empty(fig, lang.get("study_no_data", "no data"), th)
        return
    y = np.array([r.get(output, np.nan) for r in rows], dtype=float)
    k = len(study.paths)
    ncols = min(3, k)
    nrows = int(np.ceil(k / ncols))
    axes = fig.subplots(nrows, ncols, squeeze=False)
    sp = study.summary.get("spearman", {}).get(output, {})
    for idx, p in enumerate(study.paths):
        ax = axes[idx // ncols, idx % ncols]
        x = np.array([r[p] for r in rows], dtype=float)
        m = np.isfinite(y) & np.isfinite(x)
        ax.scatter(x[m], y[m], s=10, alpha=0.6, color=_color(output))
        if m.sum() > 3 and np.std(x[m]) > 0:
            coef = np.polyfit(x[m], y[m], 1)
            xs = np.linspace(x[m].min(), x[m].max(), 20)
            ax.plot(xs, np.polyval(coef, xs), color=th['fg'], lw=1, alpha=0.6)
        rho = sp.get(p)
        ax.set_title(f"{_var_label(lang, study, p)}" + (f"   ρ = {rho:+.2f}" if rho is not None else ""),
                     fontsize=9, color=th['fg'])
        ax.set_ylabel(f"{_label(lang, output)} ({UNITS.get(output, '')})", fontsize=8)
        style_axis(ax, th)
    for idx in range(k, nrows * ncols):
        axes[idx // ncols, idx % ncols].set_axis_off()
    fig.suptitle(lang.get("study_fig_scatter", "Output vs inputs"), fontsize=12, color=th['fg'])
    fig.tight_layout(rect=[0, 0, 1, 0.95])


def plot_hist(fig: Figure, study: Study, lang: Dict[str, str],
              outputs: Optional[Sequence[str]] = None, theme: str = "light") -> None:
    th = style_figure(fig, theme)
    rows = _ok_rows(study)
    outputs = list(outputs or default_outputs(study))
    if not rows:
        _empty(fig, lang.get("study_no_data", "no data"), th)
        return
    rel = study.summary.get("reliability", {})
    axes = fig.subplots(2, len(outputs), squeeze=False)
    for j, key in enumerate(outputs):
        y = np.array([r.get(key, np.nan) for r in rows], dtype=float)
        y = y[np.isfinite(y)]
        if len(y) == 0:
            axes[0, j].set_axis_off(); axes[1, j].set_axis_off()
            continue
        ax = axes[0, j]
        ax.hist(y, bins=max(8, min(30, len(y) // 5)), color=_color(key), alpha=0.75)
        ax.set_title(f"{_label(lang, key)} ({UNITS.get(key, '')})", fontsize=10, color=th['fg'])
        style_axis(ax, th)
        # allowable + Pf
        allow_key = {"sigma_le": "f_allow", "sigma_bs": "f_allow",
                     "defl_le": "defl_allow", "defl_bs": "defl_allow"}.get(key)
        ls_key = {"sigma_le": "stress_le", "sigma_bs": "stress_bs",
                  "defl_le": "defl_le", "defl_bs": "defl_bs"}.get(key)
        cdf_ax = axes[1, j]
        ys = np.sort(y)
        cdf_ax.step(ys, np.arange(1, len(ys) + 1) / len(ys), where="post", color=_color(key), lw=1.8)
        cdf_ax.set_ylim(0, 1)
        cdf_ax.set_ylabel("CDF", fontsize=8)
        style_axis(cdf_ax, th)
        if allow_key:
            allow = np.array([r.get(allow_key, np.nan) for r in rows], dtype=float)
            a = np.nanmedian(allow)
            if np.isfinite(a):
                for a_ in (ax, cdf_ax):
                    a_.axvline(a, color=PLOT_PALETTE['active'], ls="--", lw=1.2)
            if ls_key in rel:
                r_ = rel[ls_key]
                txt = f"P_f = {r_['pf']:.3g} [{r_['pf_lo']:.2g}, {r_['pf_hi']:.2g}]\nβ = {r_['beta']:.2f}"
                cdf_ax.text(0.03, 0.95, txt, transform=cdf_ax.transAxes, va="top", fontsize=8,
                            color=th['fg'], bbox=label_box(th))
        else:
            st = study.summary.get("stats", {}).get(key)
            if st:
                cdf_ax.text(0.03, 0.95, f"μ = {st['mean']:.3g}\nCoV = {st['std'] / st['mean']:.2f}"
                            if st['mean'] else f"μ = {st['mean']:.3g}",
                            transform=cdf_ax.transAxes, va="top", fontsize=8,
                            color=th['fg'], bbox=label_box(th))
    fig.suptitle(lang.get("study_fig_hist", "Distribution of results"), fontsize=12, color=th['fg'])
    fig.tight_layout(rect=[0, 0, 1, 0.95])


def plot_tornado(fig: Figure, study: Study, lang: Dict[str, str], output: str,
                 theme: str = "light") -> None:
    th = style_figure(fig, theme)
    sp = study.summary.get("spearman", {}).get(output, {})
    src = study.summary.get("src", {}).get(output, {})
    if not sp:
        _empty(fig, lang.get("study_no_sens", "Sensitivities need an LHS / MC / grid study"), th)
        return
    paths = sorted(sp, key=lambda p: abs(sp[p]))
    labels = [_var_label(lang, study, p) for p in paths]
    ax = fig.add_subplot(111)
    ypos = np.arange(len(paths))
    ax.barh(ypos + 0.2, [sp[p] for p in paths], height=0.4, color=PLOT_PALETTE['net_pressure'],
            label=lang.get("study_spearman", "Spearman ρ"))
    if src:
        ax.barh(ypos - 0.2, [src.get(p, 0.0) for p in paths], height=0.4, color=PLOT_PALETTE['deflection'],
                label=lang.get("study_src", "SRC (linear)"))
    ax.set_yticks(ypos)
    ax.set_yticklabels(labels, fontsize=9, color=th['fg'])
    ax.axvline(0, color=th['border'], lw=0.8)
    ax.set_xlim(-1, 1)
    style_axis(ax, th)
    ax.legend(fontsize=8, loc="lower right", facecolor=th['panel'],
             edgecolor=th['border'], labelcolor=th['fg'])
    ax.set_title(f"{lang.get('study_fig_tornado', 'Sensitivity')} — {_label(lang, output)}",
                fontsize=12, color=th['fg'])
    fig.tight_layout()


def _empty(fig: Figure, text: str, theme="light") -> None:
    th = theme if isinstance(theme, dict) else style_figure(fig, theme)
    ax = fig.add_subplot(111)
    ax.set_facecolor(th['panel'])
    ax.text(0.5, 0.5, text, ha="center", va="center", color=th['fg_dim'])
    ax.set_axis_off()


def summary_text(study: Study, lang: Dict[str, str]) -> str:
    s = study.summary
    L = lambda k, d: lang.get(k, d)
    lines = [L("study_summary_title", "--- STUDY SUMMARY ---"),
             L("study_samples", "Samples: {n} ({ok} LE ok, {okbs} beam-spring ok), method {m}").format(
                 n=s.get("n_total", 0), ok=s.get("n_ok", 0), okbs=s.get("n_ok_bs", 0),
                 m=study.method.upper())]
    if study.cancelled:
        lines.append(L("study_cancelled", "(cancelled before completion)"))
    lines.append("")
    lines.append(f"{'':10s} {'mean':>9s} {'std':>9s} {'p5':>9s} {'p50':>9s} {'p95':>9s}")
    for key, st in s.get("stats", {}).items():
        lines.append(f"{_label(lang, key):10s} {st['mean']:9.2f} {st['std']:9.2f} "
                     f"{st['p5']:9.2f} {st['p50']:9.2f} {st['p95']:9.2f}  {UNITS.get(key, '')}")
    if s.get("reliability"):
        lines += ["", L("study_reliability_title", "Limit states (failure if demand > allowable):")]
        for name, r in s["reliability"].items():
            pf_txt = (f"P_f = {r['pf']:.3g}  95% CI [{r['pf_lo']:.2g}, {r['pf_hi']:.2g}]"
                      if r['n_fail'] > 0 else
                      L("study_no_failures", "no failures in {n} samples (P_f < {lim:.2g} at 95%)").format(
                          n=r['n'], lim=3.0 / max(r['n'], 1)))
            beta = f"β = {r['beta']:.2f}" if np.isfinite(r['beta']) else "β > " + f"{-stats.norm.ppf(3.0 / max(r['n'], 1)):.2f}"
            lines.append(f"  {name:10s} {r['n_fail']:4d}/{r['n']:<5d} {pf_txt};  {beta};  β_FOSM = {r['beta_fosm']:.2f}")
    if s.get("spearman"):
        lines += ["", L("study_sens_title", "Spearman rank correlation (|ρ| ranked):")]
        for key in default_outputs(study):
            sp = s["spearman"].get(key)
            if sp:
                ranked = sorted(sp.items(), key=lambda kv: -abs(kv[1]))
                lines.append(f"  {_label(lang, key):8s}: " + ", ".join(
                    f"{_var_label(lang, study, p)} {rho:+.2f}" for p, rho in ranked))
    if study.method == "oat" and s.get("oat"):
        lines += ["", L("study_oat_title", "One-at-a-time ranges (min → max of output):")]
        for p, data in s["oat"].items():
            for key in default_outputs(study):
                y = np.array(data[key], dtype=float)
                y = y[np.isfinite(y)]
                if len(y):
                    lines.append(f"  {_var_label(lang, study, p):28s} {_label(lang, key):8s} "
                                 f"{y.min():9.2f} → {y.max():9.2f} {UNITS.get(key, '')}")
    return "\n".join(lines)
