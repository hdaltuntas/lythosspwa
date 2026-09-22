"""
Input schema and readers for Lythos SPWA.

Every input of the program is declared here once: key, bilingual label, unit,
range and default. The browser builds its forms from this schema, and the
server turns the values that come back into the nested configuration
dictionary the analysis core expects. Labels therefore exist in one place
only, and there is no second copy to keep in step.

The flat field keys (``excavation_depth_H``, ``kh``, ``bs_overdig`` …) are the
ones the interface and the saved ``.json`` input files use; the nested keys of
the configuration (``geometry.excavation_depth_H`` …) are the ones the engine
and the ``.spwa`` project files use. `to_config()` and `from_config()` convert
between the two, so both file formats stay readable.

This module depends on neither HTTP nor the interface, and is tested directly.
"""

from __future__ import annotations

import copy
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from .config import DEFAULT_CONFIG, SECTION_DATABASE, TRANSLATIONS

#: Subgrade-reaction methods, in the order the select offers them
KS_METHODS = ["manual", "menard", "schmitt"]

#: Water in the excavation during the staged beam-spring analysis
WATER_MODES = ["final", "dewatered"]

#: Steel grades, from the structural defaults (name -> f_y in kPa)
STEEL_GRADES = DEFAULT_CONFIG["structural_properties"]["steel_grades"]

#: Deflection criteria (name -> H/x denominator, None for "no check")
DEFLECTION_CODES = DEFAULT_CONFIG["deflection_codes"]


def _t(lang: str, key: str, fallback: str = "") -> str:
    """A translation from config.TRANSLATIONS, by language code."""
    return TRANSLATIONS.get(lang, TRANSLATIONS["en"]).get(key, fallback or key)


def _head(lang: str, key: str) -> str:
    """A translation as a table heading: the form label's trailing colon goes."""
    return _t(lang, key).rstrip(":").strip()


# --------------------------------------------------------------------------- #
#  Schema data structures
# --------------------------------------------------------------------------- #

@dataclass
class Field:
    """One input field."""
    key: str
    label: str
    kind: str = "number"                     # number | text | check | select
    default: Any = 0.0
    unit: str = ""
    min: Optional[float] = None
    max: Optional[float] = None
    step: Optional[float] = None
    decimals: int = 2
    options: List[Dict[str, str]] = field(default_factory=list)
    note: str = ""

    def to_dict(self) -> dict:
        """Only what the browser needs; empty values are left out."""
        keep = ("key", "label", "kind", "default", "decimals")
        return {k: v for k, v in asdict(self).items()
                if k in keep or v not in ("", None, [], 0.0)}


@dataclass
class Group:
    """A titled set of fields."""
    title: str
    fields: List[Field]
    note: str = ""

    def to_dict(self) -> dict:
        d = {"title": self.title, "fields": [f.to_dict() for f in self.fields]}
        if self.note:
            d["note"] = self.note
        return d


def _num(key, label, default, lo=None, hi=None, unit="", dec=2, step=None, note=""):
    return Field(key, label, "number", default, unit, lo, hi, step, dec, note=note)


def _check(key, label, default=False):
    return Field(key, label, "check", default)


def _select(key, label, default, options):
    return Field(key, label, "select", default,
                 options=[{"value": v, "label": t} for v, t in options])


def _text(key, label, default=""):
    return Field(key, label, "text", default)


# --------------------------------------------------------------------------- #
#  Input groups
# --------------------------------------------------------------------------- #

def project_groups(lang: str = "en") -> List[Group]:
    """Project identification, analysis options and factors."""
    opts = DEFAULT_CONFIG["analysis_options"]
    bs = opts["beam_spring"]
    factors = DEFAULT_CONFIG["factors"]
    return [
        Group(_t(lang, "project_group"), [
            _text("title", _t(lang, "project_title_label"),
                  DEFAULT_CONFIG["project_info"]["title"]),
            _text("analyst", _t(lang, "analyst"),
                  DEFAULT_CONFIG["project_info"]["analyst"]),
        ]),
        Group(_t(lang, "analysis_options_group"), [
            _check("is_seismic", _t(lang, "seismic_checkbox"), opts["is_seismic"]),
            _num("kh", _t(lang, "kh_label"), opts["kh"], 0, 1, "", 3, 0.01),
            _num("kv", _t(lang, "kv_label"), opts["kv"], -1, 1, "", 3, 0.01),
            _check("submerged_theta", _t(lang, "submerged_theta"),
                   opts["submerged_theta"]),
            _check("hydrodynamic", _t(lang, "hydrodynamic"), opts["hydrodynamic"]),
            _select("deflection_check_code", _t(lang, "deflection_check_label"),
                    opts["deflection_check_code"],
                    [(name, name) for name in DEFLECTION_CODES]),
        ]),
        Group(_t(lang, "bs_group"), [
            _check("bs_enabled", _t(lang, "bs_enable"), bs["enabled"]),
            _check("bs_staged", _t(lang, "bs_staged"), bs["staged"]),
            _num("bs_overdig", _t(lang, "bs_overdig_label"), bs["overdig"], 0, 5, "m", 2, 0.1),
            _num("bs_embedment", _t(lang, "bs_embedment_label"), bs["embedment"], 0, 60, "m", 2, 0.5),
            _select("bs_water_mode", _t(lang, "bs_water_mode"), bs["water_mode"],
                    [(mode, _t(lang, f"water_{mode}")) for mode in WATER_MODES]),
        ], note=_t(lang, "bs_embedment_hint")),
        Group(_t(lang, "factors_group"), [
            _num("FS_friction_angle", _t(lang, "fs_phi_label"), factors["FS_friction_angle"],
                 1, 3, "", 2, 0.05),
            _num("FS_cohesion", _t(lang, "fs_c_label"), factors["FS_cohesion"], 1, 3, "", 2, 0.05),
            _num("FS_bending", _t(lang, "fs_b_label"), factors["FS_bending"], 1, 3, "", 2, 0.05),
            _num("embedment_increase_factor", _t(lang, "emb_factor_label"),
                 factors["embedment_increase_factor"], 1, 2, "", 2, 0.05),
            _num("rounding_increment", _t(lang, "rounding_label"),
                 factors["rounding_increment"], 0.1, 5, "m", 2, 0.1),
        ]),
    ]


def structure_groups(lang: str = "en") -> List[Group]:
    """Wall section, geometry, loads and water."""
    struct = DEFAULT_CONFIG["structural_properties"]
    geom = DEFAULT_CONFIG["geometry"]
    loads = DEFAULT_CONFIG["loads"]
    manufacturers = list(SECTION_DATABASE)
    return [
        Group(_t(lang, "structural_props_group"), [
            _select("selected_manufacturer", _t(lang, "manufacturer_label"),
                    struct["selected_manufacturer"], [(m, m) for m in manufacturers]),
            _select("selected_section_model", _t(lang, "section_model_label"),
                    struct["selected_section_model"],
                    [(s["model"], s["model"])
                     for s in SECTION_DATABASE.get(struct["selected_manufacturer"], [])]),
            _select("selected_steel_grade", _t(lang, "steel_grade_label"),
                    struct["selected_steel_grade"], [(g, g) for g in STEEL_GRADES]),
        ]),
        Group(_t(lang, "geometry_group"), [
            _num("excavation_depth_H", _t(lang, "excavation_depth_label"),
                 geom["excavation_depth_H"], 0.5, 60, "m", 2, 0.5),
            _num("backfill_slope_beta", _t(lang, "backfill_slope_label"),
                 geom["backfill_slope_beta"], 0, 45, "°", 1),
            _num("dredge_line_slope_alpha", _t(lang, "dredge_line_slope_label"),
                 geom["dredge_line_slope_alpha"], 0, 45, "°", 1),
            _num("wall_friction_delta", _t(lang, "wall_friction_label"),
                 geom["wall_friction_delta"], 0, 45, "°", 1),
        ]),
        Group(_t(lang, "loads_group"), [
            _num("surcharge_load", _t(lang, "surcharge_label"), loads["surcharge_load"],
                 0, 1000, "kPa", 1),
            _num("water_level_active", _t(lang, "active_water_label"),
                 loads["water_level_active"], 0, 60, "m", 2, 0.5),
            _num("water_level_passive", _t(lang, "passive_water_label"),
                 loads["water_level_passive"], 0, 60, "m", 2, 0.5),
            _num("gamma_water", _t(lang, "gamma_water_label"), DEFAULT_CONFIG["constants"]["gamma_water"],
                 1, 15, "kN/m³", 2, 0.01),
        ]),
    ]


def study_groups(lang: str = "en") -> List[Group]:
    """Options of the parametric / reliability study."""
    import os

    from .study import METHODS
    return [
        Group(_t(lang, "study_options_group"), [
            _select("study_method", _t(lang, "study_method"), "lhs",
                    [(m, _t(lang, f"method_{m}")) for m in METHODS]),
            _num("study_n", _t(lang, "study_n"), 200, 4, 100000, "", 0, 10),
            _check("study_run_bs", _t(lang, "study_run_bs"), True),
            _check("study_unfactored", _t(lang, "study_unfactored"), False),
            _num("study_workers", _t(lang, "study_workers"),
                 max(1, (os.cpu_count() or 2) - 1), 1, 64, "", 0, 1),
            _num("study_seed", _t(lang, "study_seed"), 0, 0, 10 ** 6, "", 0, 1),
        ]),
    ]


# --------------------------------------------------------------------------- #
#  Tables: soil layers, anchors, study variables
# --------------------------------------------------------------------------- #

def soil_columns(lang: str = "en") -> List[dict]:
    """Columns of the soil profile table."""
    return [
        {"key": "name", "label": _head(lang, "layer_name"), "kind": "text"},
        {"key": "thickness", "label": _head(lang, "thickness"), "kind": "number"},
        {"key": "gamma", "label": _head(lang, "unit_weight"), "kind": "number"},
        {"key": "gamma_sat", "label": _head(lang, "sat_unit_weight"), "kind": "number"},
        {"key": "phi", "label": _head(lang, "friction_angle"), "kind": "number"},
        {"key": "cohesion", "label": _head(lang, "cohesion"), "kind": "number"},
        {"key": "k_s_method", "label": _head(lang, "ks_method"), "kind": "select",
         "options": [{"value": m, "label": _head(lang, f"ks_{m}")} for m in KS_METHODS]},
        {"key": "k_s", "label": _head(lang, "subgrade_modulus"), "kind": "number"},
        {"key": "E_M", "label": _head(lang, "E_M"), "kind": "number"},
        {"key": "alpha", "label": _head(lang, "alpha"), "kind": "number"},
    ]


def anchor_columns(lang: str = "en") -> List[dict]:
    """Columns of the anchor table."""
    return [
        {"key": "depth", "label": _head(lang, "depth"), "kind": "number"},
        {"key": "angle", "label": _head(lang, "anchor_angle"), "kind": "number"},
        {"key": "EA", "label": _head(lang, "anchor_EA"), "kind": "number"},
        {"key": "free_length", "label": _head(lang, "anchor_free_length"), "kind": "number"},
        {"key": "spacing", "label": _head(lang, "anchor_spacing"), "kind": "number"},
        {"key": "prestress", "label": _head(lang, "anchor_prestress"), "kind": "number"},
    ]


def study_columns(lang: str = "en") -> List[dict]:
    """Columns of the study variable table."""
    from .study import DISTRIBUTIONS
    return [
        {"key": "path", "label": _head(lang, "col_param"), "kind": "select", "options": []},
        {"key": "mode", "label": _head(lang, "col_mode"), "kind": "select",
         "options": [{"value": "range", "label": _head(lang, "mode_range")},
                     {"value": "dist", "label": _head(lang, "mode_dist")}]},
        {"key": "min", "label": _head(lang, "col_min"), "kind": "number"},
        {"key": "max", "label": _head(lang, "col_max"), "kind": "number"},
        {"key": "dist", "label": _head(lang, "col_dist"), "kind": "select",
         "options": [{"value": d, "label": _head(lang, f"dist_{d}")} for d in DISTRIBUTIONS]},
        {"key": "mean", "label": _head(lang, "col_mean"), "kind": "number"},
        {"key": "cov", "label": _head(lang, "col_cov"), "kind": "number"},
        {"key": "n_points", "label": _head(lang, "col_points"), "kind": "number"},
    ]


def default_soil_rows() -> List[dict]:
    """The soil profile the interface opens with."""
    return [dict(layer) for layer in DEFAULT_CONFIG["soil_profile"]]


def default_anchor_rows() -> List[dict]:
    """The anchors the interface opens with."""
    return [dict(a) for a in DEFAULT_CONFIG["analysis_options"]["anchors"]]


# --------------------------------------------------------------------------- #
#  Schema collector
# --------------------------------------------------------------------------- #

def schema(lang: str = "en") -> dict:
    """The whole schema the browser builds its forms from, in one language."""
    return {
        "project": {"groups": [g.to_dict() for g in project_groups(lang)]},
        "structure": {"groups": [g.to_dict() for g in structure_groups(lang)]},
        "study": {"groups": [g.to_dict() for g in study_groups(lang)]},
        "soil": {"columns": soil_columns(lang), "rows": default_soil_rows()},
        "anchors": {"columns": anchor_columns(lang), "rows": default_anchor_rows()},
        "study_vars": {"columns": study_columns(lang)},
        "sections": {name: [s["model"] for s in sections]
                     for name, sections in SECTION_DATABASE.items()},
    }


def defaults(lang: str = "en") -> Dict[str, Any]:
    """Default values of every field, as one flat dictionary."""
    values: Dict[str, Any] = {}
    for group in project_groups(lang) + structure_groups(lang) + study_groups(lang):
        for f in group.fields:
            values[f.key] = f.default
    values["soil_profile"] = default_soil_rows()
    values["anchors"] = default_anchor_rows()
    values["study_variables"] = []
    return values


# --------------------------------------------------------------------------- #
#  Readers: flat values <-> configuration dictionary
# --------------------------------------------------------------------------- #

def _f(values: dict, key: str, default: float = 0.0) -> float:
    """A numeric field; missing or empty falls back to the default."""
    v = values.get(key, default)
    if v is None or v == "":
        return float(default)
    return float(v)


def _b(values: dict, key: str, default: bool = False) -> bool:
    v = values.get(key, default)
    return bool(default if v is None or v == "" else v)


def _s(values: dict, key: str, default: str = "") -> str:
    v = values.get(key, default)
    return str(default if v is None or v == "" else v)


def _row_number(row: dict, key: str, default: float) -> float:
    v = row.get(key, default)
    if v is None or v == "":
        return float(default)
    return float(v)


def read_soil_profile(values: dict) -> List[dict]:
    """Soil layers from the table; rows without a usable thickness are dropped."""
    layers = []
    for row in values.get("soil_profile") or []:
        try:
            thickness = float(row.get("thickness"))
        except (TypeError, ValueError):
            continue
        if thickness <= 0:
            continue
        method = str(row.get("k_s_method") or "manual")
        layers.append({
            "name": str(row.get("name") or "").strip() or "Layer",
            "thickness": thickness,
            "gamma": _row_number(row, "gamma", 19.0),
            "gamma_sat": _row_number(row, "gamma_sat", 20.0),
            "phi": _row_number(row, "phi", 30.0),
            "cohesion": _row_number(row, "cohesion", 0.0),
            "k_s": _row_number(row, "k_s", 30000.0),
            "k_s_method": method if method in KS_METHODS else "manual",
            "E_M": _row_number(row, "E_M", 20.0),
            "alpha": _row_number(row, "alpha", 0.33),
        })
    return layers


def read_anchors(values: dict) -> List[dict]:
    """Anchors from the table, shallowest first; rows without a depth are dropped."""
    anchors = []
    for row in values.get("anchors") or []:
        try:
            depth = float(row.get("depth"))
        except (TypeError, ValueError):
            continue
        anchors.append({
            "depth": depth,
            "angle": _row_number(row, "angle", 15.0),
            "EA": _row_number(row, "EA", 117000.0),
            "free_length": _row_number(row, "free_length", 10.0),
            "spacing": _row_number(row, "spacing", 2.5),
            "prestress": _row_number(row, "prestress", 0.0),
        })
    return sorted(anchors, key=lambda a: a["depth"])


def to_config(values: dict) -> Dict[str, Any]:
    """The nested configuration the analysis core takes, from flat values."""
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    anchors = read_anchors(values)

    cfg["project_info"] = {
        "title": _s(values, "title", DEFAULT_CONFIG["project_info"]["title"]),
        "analyst": _s(values, "analyst", DEFAULT_CONFIG["project_info"]["analyst"]),
    }
    cfg["soil_profile"] = read_soil_profile(values) or copy.deepcopy(
        DEFAULT_CONFIG["soil_profile"])
    cfg["analysis_options"].update({
        "anchors": anchors,
        # kept for the v0.1 project format, which knew depths only
        "anchor_depths": [a["depth"] for a in anchors],
        "beam_spring": {
            "enabled": _b(values, "bs_enabled", True),
            "staged": _b(values, "bs_staged", True),
            "overdig": _f(values, "bs_overdig", 0.5),
            "embedment": _f(values, "bs_embedment", 0.0),
            "water_mode": (_s(values, "bs_water_mode", "final")
                           if _s(values, "bs_water_mode", "final") in WATER_MODES else "final"),
            "element_size": DEFAULT_CONFIG["analysis_options"]["beam_spring"]["element_size"],
        },
        "is_seismic": _b(values, "is_seismic", False),
        "kh": _f(values, "kh"),
        "kv": _f(values, "kv"),
        "submerged_theta": _b(values, "submerged_theta", True),
        "hydrodynamic": _b(values, "hydrodynamic", True),
        "deflection_check_code": _s(values, "deflection_check_code", "No Check"),
    })
    cfg["structural_properties"].update({
        "selected_manufacturer": _s(
            values, "selected_manufacturer",
            DEFAULT_CONFIG["structural_properties"]["selected_manufacturer"]),
        "selected_section_model": _s(
            values, "selected_section_model",
            DEFAULT_CONFIG["structural_properties"]["selected_section_model"]),
        "selected_steel_grade": _s(
            values, "selected_steel_grade",
            DEFAULT_CONFIG["structural_properties"]["selected_steel_grade"]),
    })
    cfg["geometry"].update({key: _f(values, key, DEFAULT_CONFIG["geometry"][key])
                            for key in DEFAULT_CONFIG["geometry"]})
    cfg["loads"].update({key: _f(values, key, DEFAULT_CONFIG["loads"][key])
                         for key in DEFAULT_CONFIG["loads"]})
    cfg["factors"].update({key: _f(values, key, DEFAULT_CONFIG["factors"][key])
                           for key in DEFAULT_CONFIG["factors"]})
    cfg["constants"]["gamma_water"] = _f(
        values, "gamma_water", DEFAULT_CONFIG["constants"]["gamma_water"])
    return cfg


def from_config(cfg: dict, base: Optional[dict] = None) -> Dict[str, Any]:
    """Flat values from a nested configuration — reads a `.spwa` project file.

    Files written by SPWA v0.1 (anchor depths only, no kₛ fields) load with the
    defaults filled in for whatever they do not carry.
    """
    values = dict(base) if base is not None else defaults()
    opts = cfg.get("analysis_options", {})
    bs = opts.get("beam_spring", {})

    info = cfg.get("project_info", {})
    values["title"] = info.get("title", values["title"])
    values["analyst"] = info.get("analyst", values["analyst"])

    for key in ("is_seismic", "kh", "kv", "submerged_theta", "hydrodynamic",
                "deflection_check_code"):
        if key in opts:
            values[key] = opts[key]
    for src, dst in (("enabled", "bs_enabled"), ("staged", "bs_staged"),
                     ("overdig", "bs_overdig"), ("embedment", "bs_embedment"),
                     ("water_mode", "bs_water_mode")):
        if src in bs:
            values[dst] = bs[src]

    for key in ("selected_manufacturer", "selected_section_model", "selected_steel_grade"):
        if key in cfg.get("structural_properties", {}):
            values[key] = cfg["structural_properties"][key]
    for section in ("geometry", "loads", "factors"):
        for key, value in cfg.get(section, {}).items():
            if key in values:
                values[key] = value
    if "gamma_water" in cfg.get("constants", {}):
        values["gamma_water"] = cfg["constants"]["gamma_water"]

    if cfg.get("soil_profile"):
        layer_defaults = DEFAULT_CONFIG["soil_profile"][0]
        values["soil_profile"] = [{**{k: layer_defaults[k] for k in layer_defaults}, **layer}
                                  for layer in cfg["soil_profile"]]

    anchors = opts.get("anchors")
    if anchors is None:                                   # v0.1 files
        anchors = [{"depth": float(d)} for d in opts.get("anchor_depths", [])]
    anchor_defaults = DEFAULT_CONFIG["analysis_options"]["anchors"][0]
    values["anchors"] = [{**anchor_defaults, **(a if isinstance(a, dict)
                                                else {"depth": float(a)})}
                         for a in anchors]

    study = cfg.get("study") or {}
    for src, dst in (("method", "study_method"), ("n", "study_n"),
                     ("run_bs", "study_run_bs"), ("unfactored", "study_unfactored"),
                     ("workers", "study_workers"), ("seed", "study_seed")):
        if src in study:
            values[dst] = study[src]
    if "variables" in study:
        values["study_variables"] = [dict(spec) for spec in study["variables"]]
    return values


def study_spec(values: dict) -> Dict[str, Any]:
    """The study block of a project file: options plus the variable table."""
    return {
        "method": _s(values, "study_method", "lhs"),
        "n": int(_f(values, "study_n", 200)),
        "run_bs": _b(values, "study_run_bs", True),
        "unfactored": _b(values, "study_unfactored", False),
        "workers": int(_f(values, "study_workers", 1)),
        "seed": int(_f(values, "study_seed", 0)),
        "variables": [dict(spec) for spec in values.get("study_variables") or []],
    }


def project_file(values: dict) -> Dict[str, Any]:
    """What `Save` writes: the configuration plus the study definition."""
    cfg = to_config(values)
    return {
        "format": "lythos-spwa",
        "version": "0.4",
        "project_info": cfg["project_info"],
        "soil_profile": cfg["soil_profile"],
        "analysis_options": cfg["analysis_options"],
        "structural_properties": {
            key: cfg["structural_properties"][key]
            for key in ("selected_manufacturer", "selected_section_model",
                        "selected_steel_grade")
        },
        "geometry": cfg["geometry"],
        "loads": cfg["loads"],
        "factors": cfg["factors"],
        "constants": cfg["constants"],
        "study": study_spec(values),
    }


def study_variables(values: dict):
    """The study variables as `study.StudyVariable` objects."""
    from .study import StudyVariable
    return [StudyVariable.from_dict(spec) for spec in values.get("study_variables") or []]


def variable_choices(values: dict, lang: str = "en") -> List[dict]:
    """Every input a study may sweep, with a readable label."""
    from .study import available_variables, pretty_label
    cfg = to_config(values)
    translations = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    return [{"value": path, "label": pretty_label(cfg, path, translations)}
            for path, _ in available_variables(cfg)]
