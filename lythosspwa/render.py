"""
Figure production for Lythos SPWA.

The interface runs in a browser, so figures are drawn on the server and sent
as PNG. The same functions draw the figures that go into the report, so what
is on screen and what is in the report are the same picture.

Matplotlib is used through the Agg backend: the server needs no display.
"""

from __future__ import annotations

import io
from typing import Optional

import matplotlib

matplotlib.use("Agg")

from matplotlib.figure import Figure

from . import study_plots
from .config import TRANSLATIONS
from .plotting import Plotter

#: Resolution of the PNGs (enough for the screen, and used by the report)
DPI = 130

#: The analysis diagrams, in the order the interface offers them
PLOT_KEYS = ["net_pressure", "earth_pressure", "water_pressure", "shear",
             "moment", "rotation", "deflection", "beam_spring"]

#: The study figures
STUDY_VIEWS = ["oat", "scatter", "hist", "tornado"]


def figure_to_png(fig: Figure, dpi: int = DPI) -> bytes:
    """The figure as PNG bytes."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    return buf.getvalue()


def analysis_figure(wall, engine, bs: Optional[dict], key: str, lang: str = "en",
                    theme: str = "light", size=(10.0, 7.0)) -> Figure:
    """One analysis diagram: schematic beside the requested diagram."""
    if key not in PLOT_KEYS:
        raise ValueError(f"unknown figure: {key}")
    if key == "beam_spring" and bs is None:
        raise ValueError("the beam-spring analysis did not run")
    fig = Figure(figsize=size, dpi=DPI)
    Plotter(wall, engine, TRANSLATIONS.get(lang, TRANSLATIONS["en"]), bs,
            theme=theme).setup_plot(key, fig)
    return fig


def study_figure(study, view: str, output: str, lang: str = "en",
                 theme: str = "light", size=(10.0, 7.0)) -> Figure:
    """One study figure: sweep, scatter, histogram or tornado."""
    if view not in STUDY_VIEWS:
        raise ValueError(f"unknown study view: {view}")
    L = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    fig = Figure(figsize=size, dpi=DPI)
    if view == "oat":
        study_plots.plot_oat(fig, study, L, theme=theme)
    elif view == "scatter":
        study_plots.plot_scatter(fig, study, L, output, theme=theme)
    elif view == "hist":
        study_plots.plot_hist(fig, study, L, theme=theme)
    else:
        study_plots.plot_tornado(fig, study, L, output, theme=theme)
    return fig


def available_figures(bs: Optional[dict]) -> list:
    """The diagrams that can be drawn for the analysis just run."""
    return [key for key in PLOT_KEYS if key != "beam_spring" or bs is not None]


def available_study_views(study) -> list:
    """The study figures that apply to the sampling method used."""
    if study is None or not study.rows:
        return []
    if study.method == "oat":
        return ["oat", "hist"]
    return ["hist", "scatter", "tornado"]
