"""
Tests for the things a green test suite would otherwise miss: the data files
that have to travel inside the wheel, and the version numbers that have to
agree before a release.

The tests run from the source tree, where the interface's static files and the
section database are simply there. In an installed copy they are there only
because `pyproject.toml` declares them as package data — so that declaration is
what is checked here.
"""
import os
import re

import pytest

import lythosspwa
from lythosspwa import cli, forms
from lythosspwa.config import SECTION_DATABASE
from lythosspwa.web import server

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def pyproject() -> str:
    with open(os.path.join(ROOT, "pyproject.toml"), encoding="utf-8") as fh:
        return fh.read()


def test_the_version_is_the_same_in_the_package_and_the_distribution():
    declared = re.search(r'^version\s*=\s*"([^"]+)"', pyproject(), re.MULTILINE)
    assert declared, "pyproject.toml has no version"
    assert declared.group(1) == lythosspwa.__version__


def test_the_static_files_are_declared_as_package_data():
    text = pyproject()
    assert '"lythosspwa.web" = ["static/*"]' in text
    assert '"lythosspwa" = ["section_database.json"]' in text


def test_the_interface_files_the_server_serves_are_present():
    for name in ("index.html", "app.js", "style.css"):
        path = os.path.join(server.STATIC, name)
        assert os.path.isfile(path), f"{name} is missing from the package"
        assert os.path.getsize(path) > 500


def test_the_section_database_is_loaded_and_not_the_fallback():
    assert len(SECTION_DATABASE) > 1, "the section database fell back to its default"
    for manufacturer, sections in SECTION_DATABASE.items():
        assert sections, f"{manufacturer} has no sections"
        for section in sections:
            assert section["moment_of_inertia_I"] > 0
            assert section["section_modulus_W"] > 0


def test_the_console_script_points_at_something_that_exists():
    assert 'lythos-spwa = "lythosspwa.cli:main"' in pyproject()
    assert callable(cli.main)


def test_the_command_line_writes_and_reads_a_project_file(tmp_path, capsys):
    path = tmp_path / "p.spwa"
    assert cli.main(["example", "-o", str(path)]) == 0
    capsys.readouterr()
    assert cli.main(["run", str(path)]) == 0
    printed = capsys.readouterr().out
    assert "D_req" in printed or "D_design" in printed.replace("_", "_")


def test_the_dependencies_are_the_ones_the_program_imports():
    """Nothing in the runtime path may need a package the wheel does not ask for."""
    text = pyproject()
    for required in ("numpy", "scipy", "matplotlib", "reportlab"):
        assert re.search(rf'"{required}>=', text), f"{required} is not a dependency"
    # Qt was the desktop toolkit; the interface is a web page now.
    assert "PyQt" not in text
    for module in (forms, server):
        assert "PyQt" not in open(module.__file__, encoding="utf-8").read()


def test_the_optional_formats_are_optional():
    """python-docx and openpyxl are extras: importing the package must not need them."""
    text = pyproject()
    assert 'docx = ["python-docx' in text and 'xlsx = ["openpyxl' in text
    for name in ("python-docx", "openpyxl"):
        assert not re.search(rf'^\s*"{name}>=[^"]*",\s*$',
                             text.split("[project.optional-dependencies]")[0],
                             re.MULTILINE), f"{name} must not be a hard dependency"


# --------------------------------------------------------------------------- #
#  Regressions fixed in 0.1.1
# --------------------------------------------------------------------------- #

def test_the_bare_command_starts_the_interface(monkeypatch):
    """`lythos-spwa` with no subcommand is the documented way to start it."""
    started = {}

    def fake_serve(host, port, open_browser, lang):
        started.update(host=host, port=port, open_browser=open_browser, lang=lang)

    import lythosspwa.web.server as server_module
    monkeypatch.setattr(server_module, "serve", fake_serve)
    assert cli.main([]) == 0
    assert started == {"host": "127.0.0.1", "port": cli.PORT,
                       "open_browser": True, "lang": "en"}


def test_the_web_subcommand_still_takes_its_options(monkeypatch):
    started = {}

    def fake_serve(host, port, open_browser, lang):
        started.update(host=host, port=port, open_browser=open_browser, lang=lang)

    import lythosspwa.web.server as server_module
    monkeypatch.setattr(server_module, "serve", fake_serve)
    assert cli.main(["web", "--host", "0.0.0.0", "--port", "9000",
                     "--lang", "tr", "--no-browser"]) == 0
    assert started == {"host": "0.0.0.0", "port": 9000,
                       "open_browser": False, "lang": "tr"}


def test_a_refused_analysis_prints_a_message_not_a_traceback(tmp_path, capsys):
    """The engine's refusals are sentences meant to be read by the engineer."""
    import json

    values = forms.defaults()
    # An anchor just above the dredge line breaks the free-earth assumption.
    values["excavation_depth_H"] = 9.0
    values["anchors"] = [dict(values["anchors"][0], depth=8.0)]
    path = tmp_path / "impossible.spwa"
    path.write_text(json.dumps(forms.project_file(values)), encoding="utf-8")

    assert cli.main(["run", str(path)]) == 1
    captured = capsys.readouterr()
    assert "Lythos SPWA:" in captured.err
    assert "free-earth" in captured.err.lower() or "anchor" in captured.err.lower()
    assert "Traceback" not in captured.err


def test_a_missing_project_file_is_reported_plainly(tmp_path, capsys):
    assert cli.main(["run", str(tmp_path / "nothing.spwa")]) == 1
    assert "Traceback" not in capsys.readouterr().err


def test_unfactored_strengths_are_analysable():
    """A reliability study sets every factor to 1.0; that must be allowed."""
    from lythosspwa.analysis_engine import AnalysisEngine, RetainingWall

    cfg = forms.to_config(forms.defaults())
    cfg["factors"].update(FS_friction_angle=1.0, FS_cohesion=1.0, FS_bending=1.0)
    wall = RetainingWall(cfg)
    assert wall.f_allowable == wall.fy_yield       # no factor on bending
    engine = AnalysisEngine(wall)
    engine.run()
    assert engine.d_required > 0


def test_a_bending_factor_below_one_is_still_refused():
    from lythosspwa.analysis_engine import RetainingWall

    cfg = forms.to_config(forms.defaults())
    cfg["factors"]["FS_bending"] = 0.8
    with pytest.raises(ValueError, match="FS_bending"):
        RetainingWall(cfg)


def test_an_unfactored_study_produces_results():
    """The study's 'unfactored strengths' option used to fail every sample."""
    from lythosspwa.study import Study, StudyVariable

    study = Study(forms.to_config(forms.defaults()),
                  [StudyVariable("soil_profile.0.phi", "dist", dist="normal",
                                 mean=38.0, cov=0.05, label="phi")],
                  method="lhs", n=4, run_bs=False, unfactored=True, seed=1, workers=1)
    rows = study.run()
    assert rows and all(row["ok"] for row in rows), \
        [row["error"] for row in rows if not row["ok"]]
