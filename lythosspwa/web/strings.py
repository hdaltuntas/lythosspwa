"""
Text of the interface shell.

Nothing is written into the page: the browser fetches this dictionary from
`/api/meta`, so changing the language is handled in one place and the wording
sits beside the rest of the program's translations. Whatever `config.TRANSLATIONS`
already says is reused; only what the web shell adds of its own is spelled out
here.
"""

from __future__ import annotations

from ..config import TRANSLATIONS

#: Text the web shell needs and the desktop translations do not carry.
#: key -> (English, Turkish)
SHELL = {
    "tagline": ("sheet pile wall analysis", "palplanş duvar analizi"),
    "language": ("Language", "Dil"),
    "open": ("Open…", "Aç…"),
    "save": ("Save", "Kaydet"),
    "theme": ("Theme", "Tema"),
    "ready": ("Ready.", "Hazır."),
    "running": ("Analysing…", "Analiz ediliyor…"),
    "tab_inputs": ("1 · Wall and soil", "1 · Duvar ve zemin"),
    "tab_study_inputs": ("2 · Study", "2 · Çalışma"),
    "add_row": ("+ Add row", "+ Satır ekle"),
    "del_row": ("− Remove row", "− Satır sil"),
    "soil_group": ("Soil profile", "Zemin profili"),
    "anchor_group": ("Anchors", "Ankrajlar"),
    "view_summary": ("Summary", "Özet"),
    "view_text": ("Results", "Sonuçlar"),
    "view_figures": ("Figures", "Şekiller"),
    "view_study": ("Study", "Çalışma"),
    "figure": ("Figure", "Şekil"),
    "output": ("Output", "Çıktı"),
    "report_format": ("Report", "Rapor"),
    "report_pdf": ("PDF report", "PDF rapor"),
    "report_html": ("HTML report", "HTML rapor"),
    "report_docx": ("Word report", "Word rapor"),
    "no_results": ("Run the analysis.", "Analizi çalıştırın."),
    "no_study": ("Define study variables and run the study.",
                 "Çalışma değişkenlerini tanımlayıp çalışmayı başlatın."),
    "error": ("Error", "Hata"),
    "saved": ("Saved.", "Kaydedildi."),
    "loaded": ("Project loaded.", "Proje yüklendi."),
    "bad_file": ("That file is not a Lythos SPWA project.",
                 "Bu dosya bir Lythos SPWA projesi değil."),
    "busy": ("An analysis is already running.", "Bir hesap zaten sürüyor."),
    "cancel": ("Cancel", "İptal"),
    "cancelled": ("Cancelled.", "İptal edildi."),
    "stop_hint": ("Press Ctrl+C to stop.", "Durdurmak için Ctrl+C."),
    "stopped": ("stopped", "durduruldu"),
    "select_variable": ("— choose an input —", "— bir girdi seçin —"),
}

#: Keys taken straight from the desktop translations, under the same name.
REUSED = [
    "run_analysis_button", "study_run", "study_cancel", "study_export_csv",
    "study_export_xlsx", "study_add", "study_remove", "study_vars_group",
    "study_view", "study_output", "study_no_vars", "study_progress", "study_done",
    "study_failed", "study_placeholder", "study_no_data", "study_no_sens",
    "analysis_complete", "running_analysis", "warnings_title", "inputs_title",
    "outputs_title", "report_action", "report_running", "soil_depth_warning",
    "tab_net_pressure", "tab_earth_pressure", "tab_water_pressure", "tab_shear",
    "tab_moment", "tab_rotation", "tab_deflection", "tab_beam_spring",
    "study_fig_oat", "study_fig_scatter", "study_fig_hist", "study_fig_tornado",
    "about_title", "about_text", "no_anchors",
]


def shell_strings(lang: str = "en") -> dict:
    """Every string the page needs, in one language."""
    translations = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    strings = {key: (tr if lang == "tr" else en) for key, (en, tr) in SHELL.items()}
    strings.update({key: translations[key] for key in REUSED if key in translations})
    strings["outputs"] = {key: translations.get(f"out_{key}", key)
                          for key in _output_keys()}
    return strings


def _output_keys() -> list:
    from ..study import OUTPUTS
    return [key for key, _, _ in OUTPUTS]
