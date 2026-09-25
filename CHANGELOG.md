# Changelog

## Unreleased

- The licence changes from MIT to the GNU Affero General Public License, version 3
  (`AGPL-3.0-only`). Versions already published keep the MIT licence they were released under.

## 0.1.1

Three fixes, all found while working through the program as a user would.

- **`lythos-spwa` with no subcommand crashed.** The bare command — the way the
  README tells you to start the interface, and the way `python main.py` and
  `python -m lythosspwa` reach it — ended in
  `AttributeError: 'Namespace' object has no attribute 'host'`, because the
  host, port and language defaults lived only on the `web` subparser. They are
  now defaults of the parser itself, so `lythos-spwa` and `lythos-spwa web`
  behave identically. Introduced in 0.1.0.

- **The study's "unfactored strengths (FS = 1)" option failed every sample.**
  A reliability study sets every partial factor to 1.0, but the wall refused
  `FS_bending = 1.0` with `'FS_bending' must be > 1.0.`, so all samples came
  back as errors and the study reported nothing. A factor of 1.0 means "no
  factor on bending", which is exactly what an unfactored analysis wants; only
  a factor below 1.0 — which would permit more than the yield stress — is
  refused now. This one predates the web version: it was in SPWA from its
  first release.

- **The command line printed a traceback where it had something to say.** The
  analysis refuses impossible input with a sentence written for the engineer
  ("the anchor is too close to the dredge line for this excavation depth"),
  and that sentence was buried under fifteen lines of Python. Those refusals,
  and unreadable project files, now print as one line on stderr and exit 1.
  Unexpected failures still keep their traceback.

Each of the three has a test that fails without its fix.

## 0.1.0

First release: SPWA rebuilt as a web application and packaged for PyPI.

- The PyQt6 window is replaced by a local HTTP server driven from a browser,
  built with the standard library alone. Nothing needs a display any more.
- The analysis cores — limit equilibrium, beam-spring, studies, figures — moved
  into the `lythosspwa` package unchanged in their numerics.
- The PDF report is assembled with reportlab from the same HTML the
  self-contained HTML and DOCX exports use, with a Unicode font taken from
  Matplotlib's DejaVu so Turkish and the Greek symbols come out as letters.
- `lythos-spwa` command line: `web`, `run`, `study`, `example`.
- Bilingual in English and Turkish, switchable while it runs.
