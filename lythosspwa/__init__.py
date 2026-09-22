"""
Lythos SPWA — sheet pile wall analysis, driven from a browser.

The program analyses cantilever and anchored sheet pile walls two ways and
compares them:

    1. Limit equilibrium   — free-earth support, Coulomb / Mononobe-Okabe
                             pressures, embedment by root-finding, anchor
                             forces, internal-force diagrams, design checks
    2. Beam-spring         — Winkler beam on elastoplastic soil springs with
                             automatic staged construction and tension-only
                             inclined anchors

On top of either, a parametric or reliability study sweeps any input (range,
or a distribution) and reports sensitivities, failure probability and the
reliability index.

The interface is a local web server driven from the browser (standard library
only), so the program also runs over a remote session or inside a container,
where a desktop toolkit would need a display it does not have.

Package layout
--------------
    lythosspwa.config           app identity, defaults, themes, translations
    lythosspwa.analysis_engine  limit-equilibrium core (free-earth support)
    lythosspwa.beam_spring      Winkler beam-spring core (staged construction)
    lythosspwa.study            parametric / reliability studies
    lythosspwa.plotting         analysis figures (schematic + diagrams)
    lythosspwa.study_plots      study figures (sweeps, scatter, histogram, tornado)
    lythosspwa.report           calculation report: HTML, PDF, DOCX
    lythosspwa.forms            input schema and readers (interface-independent)
    lythosspwa.web              local web server and the browser interface

Run it:  lythos-spwa            (or  python -m lythosspwa)
"""

__version__ = "0.1.1"

APP_NAME = "Lythos SPWA"
ORG = "Lythos"

__all__ = ["__version__", "APP_NAME", "ORG"]
