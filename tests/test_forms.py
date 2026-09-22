"""
Tests for forms.py: the schema the interface builds its forms from, and the
conversion between flat interface values and the nested configuration.
"""
import pytest

from lythosspwa import forms
from lythosspwa.config import DEFAULT_CONFIG


def test_schema_covers_every_part_of_the_interface():
    schema = forms.schema("en")
    assert set(schema) == {"project", "structure", "study", "soil", "anchors",
                           "study_vars", "sections"}
    for part in ("project", "structure", "study"):
        assert schema[part]["groups"], f"{part} has no groups"
        for group in schema[part]["groups"]:
            assert group["title"]
            assert all(field["key"] and field["label"] for field in group["fields"])


@pytest.mark.parametrize("lang", ["en", "tr"])
def test_schema_is_translated(lang):
    titles = [group["title"] for group in forms.schema(lang)["project"]["groups"]]
    assert titles == [forms._t(lang, key) for key in
                      ("project_group", "analysis_options_group", "bs_group",
                       "factors_group")]


def test_english_and_turkish_schemas_have_the_same_shape():
    """A translation may change the words, never the fields."""
    def keys(schema):
        return [(part, group["title"] is not None, field["key"])
                for part in ("project", "structure", "study")
                for group in schema[part]["groups"]
                for field in group["fields"]]
    assert keys(forms.schema("en")) == keys(forms.schema("tr"))


def test_defaults_fill_every_field_in_the_schema():
    values = forms.defaults()
    schema = forms.schema()
    for part in ("project", "structure", "study"):
        for group in schema[part]["groups"]:
            for field in group["fields"]:
                assert field["key"] in values
    assert values["soil_profile"] and values["anchors"]


def test_defaults_give_back_the_shipped_configuration():
    cfg = forms.to_config(forms.defaults())
    assert cfg["geometry"] == DEFAULT_CONFIG["geometry"]
    assert cfg["loads"] == DEFAULT_CONFIG["loads"]
    assert cfg["factors"] == DEFAULT_CONFIG["factors"]
    assert cfg["soil_profile"] == DEFAULT_CONFIG["soil_profile"]
    assert (cfg["analysis_options"]["anchors"]
            == DEFAULT_CONFIG["analysis_options"]["anchors"])


def test_values_survive_a_round_trip_through_a_project_file():
    values = forms.defaults()
    values["excavation_depth_H"] = 11.5
    values["is_seismic"] = False
    values["anchors"] = [{"depth": 2.0, "angle": 20.0, "EA": 90000.0,
                          "free_length": 8.0, "spacing": 2.0, "prestress": 150.0}]
    back = forms.from_config(forms.project_file(values))
    assert back["excavation_depth_H"] == 11.5
    assert back["is_seismic"] is False
    assert back["anchors"] == values["anchors"]


def test_anchors_are_sorted_and_unusable_rows_dropped():
    values = forms.defaults()
    values["anchors"] = [{"depth": 6.0}, {"depth": ""}, {"depth": 2.0}, {}]
    anchors = forms.read_anchors(values)
    assert [a["depth"] for a in anchors] == [2.0, 6.0]
    assert all(a["spacing"] > 0 for a in anchors)     # the defaults filled in


def test_a_soil_row_without_a_thickness_is_dropped():
    values = forms.defaults()
    values["soil_profile"] = [{"name": "sand", "thickness": 10.0, "phi": 32},
                              {"name": "nothing", "thickness": ""},
                              {"name": "zero", "thickness": 0.0}]
    layers = forms.read_soil_profile(values)
    assert [layer["name"] for layer in layers] == ["sand"]
    assert layers[0]["k_s_method"] == "manual"        # the default filled in


def test_a_v01_project_file_loads_with_defaults():
    """Files that knew anchor depths only must still open."""
    old = {"version": "0.1", "project_info": {"title": "old"},
           "analysis_options": {"anchor_depths": [1.5, 4.0], "is_seismic": True,
                                "kh": 0.15},
           "geometry": {"excavation_depth_H": 7.0},
           "soil_profile": [{"name": "clay", "thickness": 20.0, "gamma": 18.0,
                             "gamma_sat": 19.0, "phi": 24.0, "cohesion": 15.0}]}
    values = forms.from_config(old)
    assert values["title"] == "old"
    assert [a["depth"] for a in values["anchors"]] == [1.5, 4.0]
    assert all("EA" in a and "spacing" in a for a in values["anchors"])
    assert values["soil_profile"][0]["k_s_method"] == "manual"
    assert forms.to_config(values)["geometry"]["excavation_depth_H"] == 7.0


def test_blank_and_missing_numbers_fall_back_instead_of_raising():
    values = forms.defaults()
    values["kh"] = ""
    values["excavation_depth_H"] = None
    del values["surcharge_load"]
    cfg = forms.to_config(values)
    assert cfg["analysis_options"]["kh"] == 0.0
    assert cfg["geometry"]["excavation_depth_H"] == \
        DEFAULT_CONFIG["geometry"]["excavation_depth_H"]
    assert cfg["loads"]["surcharge_load"] == DEFAULT_CONFIG["loads"]["surcharge_load"]


def test_water_mode_and_ks_method_reject_nonsense():
    values = forms.defaults()
    values["bs_water_mode"] = "underwater-ish"
    values["soil_profile"][0]["k_s_method"] = "guesswork"
    cfg = forms.to_config(values)
    assert cfg["analysis_options"]["beam_spring"]["water_mode"] == "final"
    assert cfg["soil_profile"][0]["k_s_method"] == "manual"


def test_study_variables_are_offered_for_every_layer_and_anchor():
    values = forms.defaults()
    paths = [choice["value"] for choice in forms.variable_choices(values)]
    assert "geometry.excavation_depth_H" in paths
    assert "soil_profile.0.phi" in paths
    assert "analysis_options.anchors.1.prestress" in paths   # two anchors by default
    assert all(choice["label"] for choice in forms.variable_choices(values, "tr"))


def test_study_spec_is_carried_by_the_project_file():
    values = forms.defaults()
    values["study_variables"] = [{"path": "soil_profile.0.phi", "label": "φ",
                                  "mode": "dist", "dist": "normal", "mean": 32.0,
                                  "cov": 0.1, "min": 0, "max": 1, "n_points": 5}]
    values["study_method"] = "mc"
    values["study_n"] = 64
    back = forms.from_config(forms.project_file(values))
    assert back["study_method"] == "mc" and back["study_n"] == 64
    assert back["study_variables"] == values["study_variables"]
    assert forms.study_variables(back)[0].path == "soil_profile.0.phi"
