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
