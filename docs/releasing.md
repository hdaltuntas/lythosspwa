# Releasing to PyPI

The distribution is named `lythosspwa`; so are the package you import and the
directory in the repository. The command you type is `lythos-spwa`.

## Without a terminal

`tools/upload_to_pypi.py` does everything below from an editor: open it in
Thonny (or IDLE, or VS Code), press Run, and answer the questions in the shell
pane. It builds its own environment for `build` and `twine`, so the system
Python is left alone — on Arch, where pip refuses to install into it, that is
the difference between working and not. Set `TEST_PYPI = True` at the top of
the file to rehearse.

Nothing is sent before it has printed what it is about to upload and you have
answered `yes`.

## Once, before the first upload

Get an API token from <https://pypi.org/manage/account/token/>. Until the
project exists on PyPI the token has to be account-wide; afterwards replace it
with one scoped to `lythosspwa`. Put it in `~/.pypirc`:

```ini
[pypi]
username = __token__
password = pypi-AgEIcHlwaS5vcmc...
```

`chmod 600 ~/.pypirc`. The token is a password — it never belongs in the
repository.

## Every release

1. Raise `version` in `pyproject.toml` and `__version__` in
   `lythosspwa/__init__.py`; the test suite checks that the two agree.
   **PyPI accepts a version number once and only once**, so anything wrong in
   the metadata — the author name, the licence, the README that becomes the
   project page — has to be fixed before the upload, not after.
2. Run the tests: `pytest -q`.
3. Build clean:

   ```bash
   rm -rf dist build
   python -m build
   twine check dist/*
   ```

4. Upload:

   ```bash
   twine upload dist/*
   ```

5. Check what was actually published, in an empty environment:

   ```bash
   python -m venv /tmp/check
   /tmp/check/bin/pip install lythosspwa
   /tmp/check/bin/lythos-spwa example -o /tmp/check.spwa
   /tmp/check/bin/lythos-spwa run /tmp/check.spwa -o /tmp/check.pdf
   /tmp/check/bin/lythos-spwa web --no-browser        # then open the address
   ```

6. Tag it: `git tag v0.1.0 && git push --tags`.

## Rehearsing on TestPyPI

TestPyPI is a separate site with its own account and its own token
(<https://test.pypi.org/manage/account/token/>; add it to `~/.pypirc` under a
`[testpypi]` section):

```bash
twine upload --repository testpypi dist/*
pip install --index-url https://test.pypi.org/simple/ \
            --extra-index-url https://pypi.org/simple/ lythosspwa
```

The second index is needed because NumPy, SciPy, Matplotlib and reportlab are
not mirrored there. A name used on TestPyPI does not reserve it on PyPI.

## What goes into the wheel

`lythosspwa/web/static/*` and `lythosspwa/section_database.json` are declared
as package data in `pyproject.toml`. Without the first the interface serves a
blank page; without the second there are no sheet pile sections to choose from,
and the program falls back to one dummy section. Neither failure shows up in
the tests, which run from the source tree. After building, look:

```bash
python -c "import zipfile; print(zipfile.ZipFile('dist/lythosspwa-0.1.0-py3-none-any.whl').namelist())"
```

Both `tests/test_packaging.py` and the check above exist because this is the
one class of mistake a green test suite will not catch.
