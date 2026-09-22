"""
The one working session the server keeps.

Kept apart from the HTTP layer: there is no network here, only "take a
dictionary of inputs, run the analysis, give the results back as a
dictionary". Everything the interface does can therefore be tested without
opening a socket.

The limit-equilibrium and beam-spring analyses take well under a second and
run inline. A parametric or reliability study does not: it runs in a thread
(over a process pool of its own), reports progress through `state()`, and can
be cancelled.
"""

from __future__ import annotations

import threading
import traceback
from typing import Any, Dict, List, Optional

import numpy as np

from .. import forms, render, report, study_plots, summary
from .. import study as study_mod
from ..analysis_engine import AnalysisEngine, RetainingWall
from ..beam_spring import BeamSpringAnalysis
from ..config import TRANSLATIONS
from ..study import Study
from .strings import shell_strings

#: Languages the interface offers
LANGS = ("en", "tr")


def _cell(value) -> str:
    """One table cell as text: numbers short, missing values empty."""
    if value is None or value == "":
        return ""
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float, np.integer, np.floating)):
        number = float(value)
        return "" if np.isnan(number) else f"{number:.4g}"
    return str(value)


def _clean(value):
    """Makes NaN and infinity safe to put in JSON."""
    if isinstance(value, (np.floating, float)):
        value = float(value)
        if np.isnan(value):
            return None
        if np.isinf(value):
            return "inf" if value > 0 else "-inf"
        return value
    if isinstance(value, (np.integer, int)):
        return int(value)
    return value


class Session:
    """The single analysis session the server knows about."""

    def __init__(self, lang: str = "en", theme: str = "light"):
        self.lock = threading.Lock()
        self.lang = lang if lang in LANGS else "en"
        self.theme = theme
        # last analysis
        self.wall: Optional[RetainingWall] = None
        self.engine: Optional[AnalysisEngine] = None
        self.bs: Optional[dict] = None
        self.values: Dict[str, Any] = {}
        # last study
        self.study: Optional[Study] = None
        self.study_view = "hist"
        self.study_output = ""
        # background job
        self.job = "idle"                    # idle | running | done | error
        self.job_kind = ""
        self.job_error = ""
        self.job_detail = ""
        self.job_note = ""
        self.done = 0
        self.total = 0
        self.cancelled = False

    # ------------------------------------------------------------------ language
    def set_language(self, lang: str) -> str:
        with self.lock:
            self.lang = lang if lang in LANGS else "en"
            return self.lang

    def set_theme(self, theme: str) -> str:
        with self.lock:
            self.theme = "dark" if theme == "dark" else "light"
            return self.theme

    @property
    def t(self) -> dict:
        return TRANSLATIONS.get(self.lang, TRANSLATIONS["en"])

    # ------------------------------------------------------------------ what the page loads with
    def meta(self) -> dict:
        """Everything the interface reads on startup: version, texts, schema."""
        from .. import APP_NAME, __version__
        return {
            "app": APP_NAME,
            "version": __version__,
            "language": self.lang,
            "languages": list(LANGS),
            "strings": shell_strings(self.lang),
            "schema": forms.schema(self.lang),
            "defaults": forms.defaults(self.lang),
            "figures": render.PLOT_KEYS,
            "figure_labels": {key: self.t.get(f"tab_{key}", key) for key in render.PLOT_KEYS},
            "study_views": render.STUDY_VIEWS,
            "study_view_labels": {view: self.t.get(f"study_fig_{view}", view)
                                  for view in render.STUDY_VIEWS},
        }

    # ------------------------------------------------------------------ job state
    def _begin(self, kind: str, total: int = 0) -> bool:
        with self.lock:
            if self.job == "running":
                return False
            self.job, self.job_kind = "running", kind
            self.job_error = self.job_detail = self.job_note = ""
            self.done, self.total, self.cancelled = 0, total, False
        return True

    def _finish(self, note: str = "") -> None:
        with self.lock:
            self.job, self.job_note = "done", note

    def _fail(self, exc: Exception) -> None:
        with self.lock:
            self.job = "error"
            self.job_error = f"{type(exc).__name__}: {exc}"
            self.job_detail = traceback.format_exc(limit=4)

    def cancel(self) -> dict:
        """Asks a running study to stop at the next sample."""
        with self.lock:
            self.cancelled = True
        return {"ok": True}

    def state(self) -> dict:
        with self.lock:
            return {
                "job": self.job,
                "kind": self.job_kind,
                "error": self.job_error,
                "detail": self.job_detail if self.job == "error" else "",
                "note": self.job_note,
                "done": self.done,
                "total": self.total,
                "has_analysis": self.engine is not None,
                "has_beam_spring": self.bs is not None,
                "has_study": self.study is not None and bool(self.study.rows),
            }

    # ================================================================== analysis
    def analyse(self, values: dict) -> dict:
        """Runs the limit-equilibrium analysis and, if asked for, the beam-spring one."""
        cfg = forms.to_config(values)
        warnings: List[str] = []

        # A soil column much shallower than the wall cannot be analysed as given;
        # the engine extends the lowest layer, and the user should know it did.
        depth = sum(layer["thickness"] for layer in cfg["soil_profile"])
        if depth < cfg["geometry"]["excavation_depth_H"] * 1.5:
            warnings.append(self.t["soil_depth_warning"])

        wall = RetainingWall(cfg)
        engine = AnalysisEngine(wall)
        engine.run()

        bs = None
        bs_error = ""
        if cfg["analysis_options"]["beam_spring"]["enabled"]:
            try:
                bs = BeamSpringAnalysis(wall, engine).run()
            except Exception as exc:                  # an unstable wall, typically
                bs_error = self.t["bs_failed"].format(e=exc)
                warnings.append(bs_error)

        with self.lock:
            self.wall, self.engine, self.bs = wall, engine, bs
            self.values = dict(values)
            self.study = None

        results = engine.results
        return {
            "ok": True,
            "cards": summary.cards(wall, engine, bs, self.lang),
            "text": summary.results_text(wall, engine, bs, self.lang),
            "headline": summary.headline(wall, engine, bs, self.lang),
            "figures": render.available_figures(bs),
            "warnings": warnings + list(results.get("warnings", [])),
            "beam_spring": bs is not None,
            "beam_spring_error": bs_error,
            "d_required": _clean(engine.d_required),
            "d_design": _clean(engine.d_design),
            "length": _clean(wall.h + engine.d_design),
        }

    # ------------------------------------------------------------------ figures
    def plot(self, target: str, kind: str, output: str = "") -> bytes:
        """The requested figure as PNG."""
        if target == "study":
            with self.lock:
                study, theme = self.study, self.theme
            if study is None or not study.rows:
                raise ValueError(self.t["study_no_data"])
            outputs = study_plots.default_outputs(study)
            return render.figure_to_png(render.study_figure(
                study, kind, output or (outputs[0] if outputs else "d_req"),
                self.lang, theme))

        with self.lock:
            wall, engine, bs, theme = self.wall, self.engine, self.bs, self.theme
        if engine is None:
            raise ValueError(shell_strings(self.lang)["no_results"])
        return render.figure_to_png(render.analysis_figure(wall, engine, bs, kind,
                                                           self.lang, theme))

    # ================================================================== study
    def study_variables(self, values: dict) -> dict:
        """Which inputs a study may sweep, for the variable table's select."""
        return {"ok": True, "choices": forms.variable_choices(values, self.lang)}

    def start_study(self, values: dict) -> dict:
        """Starts the parametric / reliability study in the background."""
        spec = forms.study_spec(values)
        if not spec["variables"]:
            return {"ok": False, "error": self.t["study_no_vars"]}
        try:
            variables = forms.study_variables(values)
            study = Study(forms.to_config(values), variables, spec["method"], spec["n"],
                          spec["run_bs"], spec["unfactored"], spec["seed"],
                          workers=spec["workers"])
        except Exception as exc:
            return {"ok": False, "error": self.t["study_failed"].format(e=exc)}

        if not self._begin("study"):
            return {"ok": False, "error": shell_strings(self.lang)["busy"]}
        with self.lock:
            self.values = dict(values)
            self.study = None
        threading.Thread(target=self._run_study, args=(study,), daemon=True).start()
        return {"ok": True}

    def _run_study(self, study: Study) -> None:
        def progress(done: int, total: int) -> None:
            with self.lock:
                self.done, self.total = done, total

        def cancel_asked() -> bool:
            with self.lock:
                return self.cancelled

        try:
            study.run(progress=progress, is_cancelled=cancel_asked)
            with self.lock:
                self.study = study
                self.study_view = "oat" if study.method == "oat" else "hist"
                self.study_output = ""
                cancelled = self.cancelled
            note = self.t["study_done"].format(n=len(study.rows))
            if cancelled:
                note = f"{note} {self.t['study_cancelled']}"
            self._finish(note)
        except Exception as exc:
            self._fail(exc)

    def study_payload(self) -> dict:
        """What the study view shows: summary text, figures and outputs."""
        with self.lock:
            study = self.study
        if study is None or not study.rows:
            return {"ok": False, "error": self.t["study_no_data"]}
        outputs = study_plots.default_outputs(study)
        labels = TRANSLATIONS.get(self.lang, TRANSLATIONS["en"])
        return {
            "ok": True,
            "method": study.method,
            "n": len(study.rows),
            "text": study_plots.summary_text(study, labels),
            "views": render.available_study_views(study),
            "outputs": [{"value": key, "label": labels.get(f"out_{key}", key)}
                        for key in outputs],
            "table": self._study_table(study),
        }

    #: How many sampled rows the page is given; the full table is the CSV / XLSX
    TABLE_LIMIT = 500

    def _study_table(self, study: Study) -> dict:
        """The sampled table, trimmed to what a page can usefully show."""
        labels = TRANSLATIONS.get(self.lang, TRANSLATIONS["en"])
        by_path = {variable.path: variable.label for variable in study.variables}
        columns = study_mod.table_columns(study)
        header = [labels.get(f"out_{column}", by_path.get(column, column))
                  for column in columns]
        rows = [[_cell(row.get(column)) for column in columns]
                for row in study.rows[:self.TABLE_LIMIT]]
        return {"columns": header, "rows": rows,
                "truncated": len(study.rows) > len(rows)}

    def export_study(self, kind: str, path: str) -> str:
        """Writes the sampled table as CSV or XLSX and returns the path."""
        with self.lock:
            study = self.study
        if study is None or not study.rows:
            raise ValueError(self.t["study_no_data"])
        (study_mod.to_csv if kind == "csv" else study_mod.to_xlsx)(study, path)
        return path

    # ================================================================== report
    def report(self, fmt: str, path: str) -> str:
        """Writes the calculation report in the chosen format; returns the path."""
        with self.lock:
            wall, engine, bs, study = self.wall, self.engine, self.bs, self.study
        if engine is None:
            raise ValueError(shell_strings(self.lang)["no_results"])
        writer = {"pdf": report.export_pdf, "html": report.export_html,
                  "docx": report.export_docx}.get(fmt)
        if writer is None:
            raise ValueError(f"unknown report format: {fmt}")
        writer(path, wall, engine, bs, self.lang,
               study if study is not None and study.rows else None)
        return path

    # ================================================================== project files
    def project_file(self, values: dict) -> dict:
        """What `Save` downloads."""
        return forms.project_file(values)

    def load_project(self, data: dict) -> dict:
        """Flat interface values from a project file, defaults filling the gaps."""
        if not isinstance(data, dict):
            raise ValueError(shell_strings(self.lang)["bad_file"])
        return {"ok": True, "values": forms.from_config(data, forms.defaults(self.lang))}
