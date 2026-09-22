"""
Tests for the browser interface: the session that does the work, and the HTTP
layer that serves it. The server is started on a port of its own and driven
with urllib, so what is tested is the same thing the browser talks to.
"""
import json
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from lythosspwa import forms
from lythosspwa.web import server as server_module
from lythosspwa.web.session import Session
from lythosspwa.web.strings import shell_strings

# --------------------------------------------------------------------------- #
#  The session
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def session():
    s = Session()
    s.analyse(forms.defaults())
    return s


def test_meta_carries_everything_the_page_needs():
    meta = Session().meta()
    assert meta["app"] == "Lythos SPWA"
    assert meta["languages"] == ["en", "tr"]
    assert meta["schema"]["project"]["groups"]
    assert meta["defaults"]["excavation_depth_H"] > 0
    assert "beam_spring" in meta["figures"]
    assert all(meta["figure_labels"][key] for key in meta["figures"])


def test_analyse_returns_cards_text_and_figures(session):
    result = session.analyse(forms.defaults())
    assert result["ok"] and result["beam_spring"]
    assert [card["key"] for card in result["cards"]] == \
        ["embed", "moment", "defl", "anchor", "stress", "deflcheck", "vertical"]
    assert result["d_required"] < result["d_design"]
    assert "beam_spring" in result["figures"]
    assert str(round(result["d_design"], 2)) in result["text"]


def test_analysis_without_the_beam_spring_offers_no_such_figure():
    values = forms.defaults()
    values["bs_enabled"] = False
    result = Session().analyse(values)
    assert result["beam_spring"] is False
    assert "beam_spring" not in result["figures"]


def test_a_cantilever_wall_analyses_without_anchors():
    values = forms.defaults()
    values["anchors"] = []
    values["excavation_depth_H"] = 4.0
    result = Session().analyse(values)
    assert result["ok"]
    assert any(card["key"] == "anchor" and card["state"] == "na"
               for card in result["cards"])


def test_a_shallow_soil_column_is_warned_about():
    values = forms.defaults()
    values["soil_profile"] = [dict(values["soil_profile"][0], thickness=5.0)]
    values["excavation_depth_H"] = 8.0
    result = Session().analyse(values)
    assert any("soil" in w.lower() or "zemin" in w.lower() for w in result["warnings"])


@pytest.mark.parametrize("kind", ["net_pressure", "moment", "deflection", "beam_spring"])
def test_every_figure_is_drawn_as_a_png(session, kind):
    png = session.plot("analysis", kind)
    assert png.startswith(b"\x89PNG") and len(png) > 5000


def test_a_figure_before_an_analysis_says_so_instead_of_breaking():
    with pytest.raises(ValueError):
        Session().plot("analysis", "moment")


@pytest.mark.parametrize("lang", ["en", "tr"])
def test_the_language_reaches_results_and_figures(lang):
    s = Session()
    s.set_language(lang)
    result = s.analyse(forms.defaults())
    from lythosspwa.config import TRANSLATIONS
    assert TRANSLATIONS[lang]["card_embed"] == result["cards"][0]["title"]
    assert TRANSLATIONS[lang]["design_results_title"] in result["text"]


def test_report_is_written_in_each_format(session, tmp_path):
    pdf = session.report("pdf", str(tmp_path / "r.pdf"))
    assert open(pdf, "rb").read(4) == b"%PDF"
    html = session.report("html", str(tmp_path / "r.html"))
    assert "<html" in open(html, encoding="utf-8").read(200)
    with pytest.raises(ValueError):
        session.report("txt", str(tmp_path / "r.txt"))


def test_a_project_file_round_trips_through_the_session(session):
    values = forms.defaults()
    values["excavation_depth_H"] = 9.5
    project = session.project_file(values)
    assert project["format"] == "lythos-spwa"
    loaded = session.load_project(project)
    assert loaded["ok"] and loaded["values"]["excavation_depth_H"] == 9.5


def test_a_study_runs_reports_progress_and_can_be_read_back():
    s = Session()
    values = forms.defaults()
    values.update(study_method="lhs", study_n=8, study_workers=1, study_run_bs=False,
                  study_variables=[
                      {"path": "soil_profile.0.phi", "label": "φ", "mode": "dist",
                       "dist": "normal", "mean": 38.0, "cov": 0.08,
                       "min": 30, "max": 42, "n_points": 5},
                      {"path": "loads.surcharge_load", "label": "q", "mode": "range",
                       "min": 5.0, "max": 25.0, "dist": "normal", "mean": 15,
                       "cov": 0.2, "n_points": 5}])
    s.analyse(values)
    assert s.start_study(values)["ok"]
    for _ in range(600):                      # 60 s is far more than it needs
        if s.state()["job"] != "running":
            break
        time.sleep(0.1)
    state = s.state()
    assert state["job"] == "done", state["error"]
    assert state["has_study"]

    payload = s.study_payload()
    assert payload["ok"] and payload["n"] == 8
    assert payload["views"] and payload["outputs"]
    assert payload["table"]["rows"] and len(payload["table"]["rows"][0]) == \
        len(payload["table"]["columns"])
    png = s.plot("study", payload["views"][0], payload["outputs"][0]["value"])
    assert png.startswith(b"\x89PNG")


def test_a_study_without_variables_is_refused_with_a_message():
    s = Session()
    result = s.start_study(forms.defaults())
    assert not result["ok"] and result["error"]


def test_study_results_before_a_study_say_so():
    payload = Session().study_payload()
    assert not payload["ok"] and payload["error"]


def test_shell_strings_exist_in_both_languages():
    english, turkish = shell_strings("en"), shell_strings("tr")
    assert set(english) == set(turkish)
    assert all(english[key] for key in english)
    assert english["tagline"] != turkish["tagline"]


# --------------------------------------------------------------------------- #
#  The HTTP layer
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def http():
    """The real handler on a port the operating system picks."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), server_module.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def get(url, raw=False):
    with urllib.request.urlopen(url, timeout=120) as response:
        body = response.read()
        return body if raw else json.loads(body)


def post(url, payload, raw=False):
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode(), method="POST",
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=300) as response:
        body = response.read()
        return (body, dict(response.headers)) if raw else json.loads(body)


def test_the_page_and_its_assets_are_served(http):
    page = get(f"{http}/", raw=True).decode()
    assert "<title>Lythos SPWA</title>" in page
    assert b"function" in get(f"{http}/static/app.js", raw=True)
    assert b"--accent" in get(f"{http}/static/style.css", raw=True)
    assert get(f"{http}/favicon.ico", raw=True).startswith(b"<svg")


def test_every_element_the_script_addresses_is_in_the_page(http):
    """The page and the script are written together; keep them that way."""
    import re
    page = get(f"{http}/", raw=True).decode()
    script = get(f"{http}/static/app.js", raw=True).decode()
    ids = set(re.findall(r'id="([A-Za-z0-9_]+)"', page))
    for used in set(re.findall(r'\$\("([A-Za-z0-9_]+)"\)', script)):
        assert used in ids, f"app.js addresses #{used}, which the page has not got"


def test_meta_and_state_are_served_as_json(http):
    meta = get(f"{http}/api/meta")
    assert meta["app"] == "Lythos SPWA" and meta["version"]
    state = get(f"{http}/api/state")
    assert state["job"] in ("idle", "running", "done")


def test_an_analysis_over_http_gives_results_and_a_figure(http):
    meta = get(f"{http}/api/meta")
    result = post(f"{http}/api/analyse", {"values": meta["defaults"]})
    assert result["ok"] and result["cards"]
    png = get(f"{http}/api/plot?target=analysis&kind=moment", raw=True)
    assert png.startswith(b"\x89PNG")


def test_the_report_comes_back_as_a_download(http):
    body, headers = post(f"{http}/api/report", {"format": "html"}, raw=True)
    assert body.startswith(b"<html") or b"<html" in body[:200]
    assert "attachment" in headers["Content-Disposition"]


def test_the_project_file_comes_back_as_a_download(http):
    meta = get(f"{http}/api/meta")
    body, headers = post(f"{http}/api/project", {"values": meta["defaults"]}, raw=True)
    assert json.loads(body)["format"] == "lythos-spwa"
    assert "project.spwa" in headers["Content-Disposition"]


def test_switching_the_language_returns_the_translated_schema(http):
    turkish = post(f"{http}/api/language", {"lang": "tr"})
    assert turkish["language"] == "tr"
    assert turkish["schema"]["project"]["groups"][0]["title"] == "Proje Bilgileri"
    english = post(f"{http}/api/language", {"lang": "en"})
    assert english["schema"]["project"]["groups"][0]["title"] == "Project Information"


def test_a_bad_request_answers_with_an_error_not_a_traceback(http):
    with pytest.raises(urllib.error.HTTPError) as caught:
        post(f"{http}/api/report", {"format": "wingdings"})
    assert caught.value.code == 400
    assert "error" in json.loads(caught.value.read())


def test_an_unknown_route_is_a_404(http):
    with pytest.raises(urllib.error.HTTPError) as caught:
        get(f"{http}/api/nonsense")
    assert caught.value.code == 404
