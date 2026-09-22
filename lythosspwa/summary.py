"""
Results as text and as summary cards.

Both the browser interface and the command line show the same thing: the
headline numbers as a row of cards, and the full account of the analysis as
text. Assembling them here keeps that promise without either side copying the
other's wording, and it needs no interface toolkit at all — pass a finished
analysis and a language code.
"""

from __future__ import annotations

from typing import List, Optional

from .config import TRANSLATIONS

#: Card order, as the interface lays them out
CARD_KEYS = ["embed", "moment", "defl", "anchor", "stress", "deflcheck", "vertical"]


def _lang(lang: str) -> dict:
    return TRANSLATIONS.get(lang, TRANSLATIONS["en"])


def _status(L: dict, status: str) -> tuple:
    """A check status as (short text, state) — state drives the card color."""
    if status == "N/A":
        return L["na_short"], "na"
    return (L["ok_short"], "ok") if status == "OK" else (L["notok_short"], "bad")


def cards(wall, engine, bs: Optional[dict] = None, lang: str = "en") -> List[dict]:
    """The headline numbers: embedment, moment, deflection, anchor and checks."""
    L = _lang(lang)
    res = engine.results
    out = []

    def card(key, value, sub="", state=""):
        out.append({"key": key, "title": L[f"card_{key}"], "value": value,
                    "sub": sub, "state": state})

    card("embed", f"{engine.d_required:.2f} / {engine.d_design:.2f} m", L["card_embed_sub"])
    m_bs = f" / {bs['m_max_abs']:.0f}" if bs else ""
    card("moment", f"{res['m_max_abs']:.0f}{m_bs} kNm/m", L["card_moment_sub"])
    d_bs = f" / {bs['actual_max_deflection']:.1f}" if bs else ""
    card("defl", f"{res['actual_max_deflection']:.1f}{d_bs} mm", L["card_defl_sub"])

    if engine.t_anchors:
        t_le = max(engine.t_anchors.values())
        t_bs = f" / {max(bs['anchor_forces'].values()):.0f}" if bs and bs['anchor_forces'] else ""
        card("anchor", f"{t_le:.0f}{t_bs} kN/m", L["card_anchor_sub"])
    else:
        card("anchor", L["card_none"], L["no_anchors"].strip(), "na")

    # The beam-spring results govern the checks whenever that analysis ran.
    src = bs if bs else res
    text, state = _status(L, src['stress_check_status'])
    card("stress", text,
         f"{src['actual_stress'] / 1000:.0f} / {wall.f_allowable / 1000:.0f} MPa", state)

    text, state = _status(L, src['deflection_check_status'])
    sub = (f"{src['actual_max_deflection']:.1f} / {src['allowable_deflection']:.1f} mm"
           if src['deflection_check_status'] != "N/A" else "")
    card("deflcheck", text, sub, state)

    text, state = _status(L, src.get('vertical_status', "N/A"))
    sub = (f"{src.get('vertical_load', 0):.0f} / {src.get('vertical_resistance', 0):.0f} kN/m"
           if src.get('vertical_status', "N/A") != "N/A" else "")
    card("vertical", text, sub, state)
    return out


def _beam_spring_lines(wall, engine, bs: dict, L: dict) -> List[str]:
    """The beam-spring part of the text: stages, kₛ table, anchors, checks."""
    le_res = engine.results
    lines = [L["bs_title"],
             L["bs_embedment"].format(val=bs['embedment'], L=bs['length'],
                                      n=len(bs['stages']), it=bs['iterations']),
             L["ks_table_title"]]
    for name, ks, method in bs['k_s_table']:
        lines.append(L["ks_table_line"].format(name=name, val=ks, method=L["ks_" + method]))
    for i, stage in enumerate(bs['stages'], 1):
        label = L["bs_stage_" + stage['kind']].format(val=stage['value'])
        if stage['solved']:
            forces = "".join(f", T({d:.1f} m)={t:.0f}"
                             for d, t in sorted(stage['anchor_forces'].items()))
            lines.append(L["bs_stage_line"].format(i=i, label=label,
                                                   w=stage['w_max_mm'], forces=forces))
        else:
            lines.append(L["bs_stage_noline"].format(i=i, label=label))
    lines.append("")
    for anchor in wall.anchors:
        rep = bs['anchor_report'][anchor['depth']]
        lines.append(L["anchor_report_line"].format(
            depth=anchor['depth'], angle=anchor['angle'], th=rep['T_h'],
            ta=rep['T_axial'], v=rep['V']))
    lines += [
        L["bs_summary_moment"].format(val=bs['m_max_abs'], le=le_res['m_max_abs']),
        L["actual_stress"].format(val=bs['actual_stress'] / 1000),
        L["status"].format(status=bs['stress_check_status']),
        L["bs_summary_deflection"].format(val=bs['actual_max_deflection'],
                                         le=le_res['actual_max_deflection']),
    ]
    if bs['deflection_check_status'] != "N/A":
        lines.append(L["status"].format(status=bs['deflection_check_status']))
    if bs.get('vertical_status', "N/A") != "N/A":
        lines += [L["vertical_load"].format(val=bs['vertical_load']),
                  L["vertical_resistance"].format(val=bs['vertical_resistance']),
                  L["status"].format(status=bs['vertical_status'])]
    lines.append(L["bs_mobilization"].format(p=bs['passive_mobilization'],
                                             a=bs['active_mobilization']))
    return lines


def results_text(wall, engine, bs: Optional[dict] = None, lang: str = "en") -> str:
    """The whole analysis as text, in the chosen language."""
    L = _lang(lang)
    res = engine.results
    lines = [
        L["design_results_title"],
        L["selected_section"].format(model=wall.selected_section_model,
                                     grade=wall.selected_steel_grade),
        "-" * 60,
        L["req_embedment"].format(val=engine.d_required),
        L["design_embedment"].format(val=engine.d_design),
        L["total_length"].format(val=wall.h + engine.d_design),
        L["anchor_forces_title"],
    ]
    if not engine.is_cantilever:
        for anchor in wall.anchors:
            rep = res['anchor_report'][anchor['depth']]
            lines.append(L["anchor_report_line"].format(
                depth=anchor['depth'], angle=anchor['angle'], th=rep['T_h'],
                ta=rep['T_axial'], v=rep['V']))
        if len(engine.t_anchors) > 1:
            lines.append(L["multi_anchor_note"])
    else:
        lines.append(L["no_anchors"])
        lines.append(L["toe_reaction"].format(val=abs(res['toe_shear'])))

    lines += [
        L["summary_of_results_title"],
        L["diagram_note"].format(val=engine.d_required),
        L["closure_check"].format(val=res['toe_moment']),
        L["summary_pressure"].format(p_min=res['p_min'], p_max=res['p_max']),
        L["summary_shear"].format(v_min=res['v_min'], v_max=res['v_max']),
        L["summary_moment"].format(m_min=res['m_min'], m_max=res['m_max']),
        L["summary_rotation"].format(rot_min=res['rot_min'], rot_max=res['rot_max']),
        L["summary_deflection"].format(d_min=float(res['deflection'].min()) * 1000,
                                       d_max=float(res['deflection'].max()) * 1000),
        L["stress_check_title"],
        L["max_abs_moment"].format(val=res['m_max_abs']),
        L["actual_stress"].format(val=res['actual_stress'] / 1000),
        L["allowable_stress"].format(val=wall.f_allowable / 1000),
        L["status"].format(status=res['stress_check_status']),
    ]
    code = wall.config['analysis_options']['deflection_check_code']
    if res['deflection_check_status'] != "N/A":
        lines += [L["deflection_check_title"].format(code=code),
                  L["actual_deflection"].format(val=res['actual_max_deflection']),
                  L["allowable_deflection"].format(val=res['allowable_deflection']),
                  L["status"].format(status=res['deflection_check_status'])]
    if res.get('vertical_status', "N/A") != "N/A":
        lines += [L["vertical_check_title"],
                  L["vertical_load"].format(val=res['vertical_load']),
                  L["vertical_resistance"].format(val=res['vertical_resistance']),
                  L["status"].format(status=res['vertical_status'])]
    if bs:
        lines += _beam_spring_lines(wall, engine, bs, L)
    if res.get('warnings'):
        lines.append(L["warnings_title"])
        lines += ["  • " + w for w in res['warnings']]
    return "\n".join(lines)


def headline(wall, engine, bs: Optional[dict] = None, lang: str = "en") -> str:
    """One line for the status bar: embedment, moment and the governing check."""
    L = _lang(lang)
    src = bs if bs else engine.results
    status, _ = _status(L, src['stress_check_status'])
    return (f"D_design = {engine.d_design:.2f} m · "
            f"M_max = {src['m_max_abs']:.0f} kNm/m · "
            f"{L['card_stress']}: {status}")
