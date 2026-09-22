"""
Configuration for Lythos SPWA.

This file contains default parameters, constants, and loads external data
like the section database and language translations. The app name and version
live in the package's ``__init__`` so that there is one copy of each.
"""

import json
from pathlib import Path

from . import APP_NAME
from . import __version__ as APP_VERSION

# --- Constants ---
DATABASE_FILE = Path(__file__).parent / "section_database.json"
MM_PER_M = 1000.0
NUM_PLOT_POINTS = 500

# --- Interface theme (web/static/style.css) and plot palette          ---
# --- (plotting.py, study_plots.py) -- kept together so the figures      ---
# --- always match the page they're shown on.                            ---
ACCENT = "#2F80ED"

THEMES = {
    "dark": dict(bg="#1E1F24", panel="#2A2C33", input_bg="#33363F", fg="#E6E6E6",
                 fg_dim="#9AA0AA", border="#3D414B", hover="#3A3E48", btn="#353943",
                 muted="#555A66", accent=ACCENT, accent_hover="#4A90F0"),
    "light": dict(bg="#F3F4F6", panel="#FFFFFF", input_bg="#FFFFFF", fg="#1F2933",
                  fg_dim="#6B7280", border="#D9DDE3", hover="#EEF1F5", btn="#F7F8FA",
                  muted="#B8C0CC", accent=ACCENT, accent_hover="#1F6FDB"),
}

# Semantic colors for the analysis diagrams; consistent across LE, beam-
# spring and study figures so e.g. "moment" is always the same color.
PLOT_PALETTE = dict(
    net_pressure=ACCENT, active="#EB5757", passive="#27AE60",
    shear="#0EA5A4", moment="#9B5DE5", rotation="#22B8CF",
    deflection="#F2994A", water_active=ACCENT, water_passive="#56CCF2",
    hydrodynamic="#1F6FDB", anchor="#F2994A",
)

# Fill colors for the schematic's soil hatching (theme-dependent, since a
# light sandy tone reads poorly on a dark background).
SOIL_FILL = {"light": "#C9A876", "dark": "#8A7250"}


try:
    with open(DATABASE_FILE, 'r', encoding='utf-8') as f:
        SECTION_DATABASE = json.load(f)
        if not SECTION_DATABASE:
            raise ValueError("Veritabanı dosyası boş.")
except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
    print(f"Error loading section database: {e}")
    # Çökmeyi önlemek için asgari bir varsayılan (fallback) veri seti
    SECTION_DATABASE = {
        "Default Manufacturer": [
            { "model": "Default-Z", "moment_of_inertia_I": 50000e-8, "section_modulus_W": 2000e-6 }
        ]
    }


DEFAULT_CONFIG = {
    "project_info": {
        "title": "Project: Multi-Anchor Quay Wall",
        "analyst": "Python Analysis Script",
    },
    "analysis_options": {
        # depth [m], angle below horizontal [deg], EA of one anchor [kN],
        # free length [m], spacing [m], lock-off load of one anchor [kN]
        "anchors": [
            {"depth": 1.5, "angle": 15.0, "EA": 117000.0, "free_length": 12.0,
             "spacing": 2.5, "prestress": 0.0},
            {"depth": 4.0, "angle": 15.0, "EA": 117000.0, "free_length": 10.0,
             "spacing": 2.5, "prestress": 0.0},
        ],
        "beam_spring": {
            "enabled": True,        # run the Winkler beam-spring analysis after the LE analysis
            "staged": True,         # automatic staged construction (excavate -> anchor -> ...)
            "overdig": 0.5,         # excavation below each anchor level before installing it (m)
            "embedment": 0.0,       # 0 -> use D_design from the LE analysis
            "element_size": 0.1,    # beam element length (m)
            "water_mode": "final",  # "final" (underwater dredging) | "dewatered"
        },
        "is_seismic": True,
        "kh": 0.1,
        "kv": 0.0,
        "submerged_theta": True,    # Mononobe-Okabe theta with gamma_sat/gamma' below the water table
        "hydrodynamic": True,       # Westergaard pressure of the free water in front of the wall
        "deflection_check_code": "FHWA (H/120)",
    },
    "deflection_codes": {
        "No Check": None,
        "FHWA (H/120)": 120,
        "BS 8002 (H/100)": 100,
        "NAVFAC DM-7.2 (H/240)": 240,
    },
    "structural_properties": {
        "youngs_modulus_E": 210e6,
        "selected_manufacturer": "Nucor Skyline",
        "selected_section_model": "NZ 26",
        "selected_steel_grade": "S355",
        "steel_grades": {
            "S240GP": 240000, "S270GP": 270000, "S355": 355000,
            "S420": 420000, "S430GP": 430000, "S460AP": 460000
        },
    },
    "section_database": SECTION_DATABASE,
    "geometry": {
        "excavation_depth_H": 8.0,
        "backfill_slope_beta": 0.0,
        "dredge_line_slope_alpha": 0.0,
        "wall_friction_delta": 20.0,
    },
    "loads": {
        "surcharge_load": 15.0,
        "water_level_active": 4.0,
        "water_level_passive": 7.0,
    },
    "factors": {
        "FS_cohesion": 1.25,
        "FS_friction_angle": 1.25,
        "FS_bending": 1.5,
        "embedment_increase_factor": 1.2,
        "rounding_increment": 0.5,
    },
    "constants": {
        "gamma_water": 9.81
    },
    "soil_profile": [
        {
            "name": "Sloped Sandy Gravel",
            "thickness": 25.0,
            "gamma": 19.5,
            "gamma_sat": 21.0,
            "phi": 38,
            "cohesion": 0,
            "k_s": 30000.0,          # used when k_s_method == "manual"
            "k_s_method": "manual",  # "manual" | "menard" | "schmitt"
            "E_M": 20.0,             # Menard pressuremeter modulus (MPa)
            "alpha": 0.33            # rheological coefficient (sand 1/3, silt 1/2, clay 2/3)
        }
    ],
}

TRANSLATIONS = {
    "en": {
        "window_title": f"{APP_NAME} v{APP_VERSION} — Sheet Pile Wall Analysis", "file_menu": "&File",
        "help_menu": "&Help", "about_action": "&About",
        "about_title": f"About {APP_NAME}",
        "about_text": f"<h3>{APP_NAME} v{APP_VERSION}</h3>"
                      "<p>Sheet Pile Wall Analysis — geotechnical analysis of sheet pile walls "
                      "using the free-earth support method for both cantilever and multi-anchored systems.</p>"
                      "<p>Developed using Python, Matplotlib and SciPy; the interface runs in a browser.</p>"
                      "<p><b>Developer:</b> Hasan Deniz Altuntaş<br>© 2025 Hasan Deniz Altuntaş</p>",
        "open_project": "&Open Project...", "save_project": "&Save Project As...",
        "exit_action": "E&xit", "lang_label": "Language:",
        "project_group": "Project Information",
        "project_title_label": "Project Title:",
        "analysis_options_group": "Analysis Options",
        "seismic_checkbox": "Activate Seismic Analysis",
        "kh_label": "Horizontal Seismic Coeff. (kh):",
        "kv_label": "Vertical Seismic Coeff. (kv):",
        "deflection_check_label": "Deflection Code:",
        "soil_profile_group": "Soil Profile",
        "add_soil_layer_button": "Add Soil Layer",
        "anchor_levels_group": "Anchor Levels",
        "add_anchor_button": "Add Anchor",
        "structural_props_group": "Structural Properties",
        "section_model_label": "Section Model:",
        "manufacturer_label": "Manufacturer:",
        "steel_grade_label": "Steel Grade:", "geometry_group": "Geometry",
        "excavation_depth_label": "Excavation Depth H (m):",
        "backfill_slope_label": "Backfill Slope β (°):",
        "dredge_line_slope_label": "Dredge Line Slope α (°):",
        "wall_friction_label": "Wall Friction Angle δ (°):",
        "loads_group": "Loads and Water", "surcharge_label": "Surcharge Load (kPa):",
        "active_water_label": "Active Water Level (m):",
        "passive_water_label": "Passive Water Level (m):",
        "run_analysis_button": "RUN ANALYSIS",
        "results_summary_tab": "Results Summary",
        "save_plot_button": "Save Plot",
        "results_placeholder": "Analysis results will be displayed here...",
        "running_analysis": "Running analysis, please wait...",
        "analysis_complete": "Analysis completed successfully.",
        "error_title": "Error", "error_message": "An error occurred:\n\n{type}: {e}",
        "warning_title": "Warning",
        "no_plot_warning": "There is no plot to save. Please run an analysis first.",
        "save_success_title": "Success",
        "save_success_message": "Plot successfully saved to:\n{path}",
        "save_error_message": "An error occurred while saving the plot:\n{e}",
        "layer_name": "Layer Name:", "thickness": "Thickness (m):",
        "unit_weight": "Unit Weight (kN/m³):",
        "sat_unit_weight": "Saturated Unit W. (kN/m³):",
        "friction_angle": "Friction Angle (°):", "cohesion": "Cohesion (kPa):",
        "remove_layer": "Remove This Layer", "depth": "  Depth (m):",
        "remove": "Remove", "design_results_title": "--- DESIGN RESULTS ---",
        "selected_section": "Selected Section: {model} ({grade})",
        "req_embedment": "Theoretical Required Embedment (D_req): {val:.2f} m",
        "design_embedment": "Design Embedment Depth (D_design):     {val:.2f} m",
        "total_length": "Total Wall Length (L_total):          {val:.2f} m",
        "anchor_forces_title": "\n--- ANCHOR FORCES ---",
        "anchor_force_line": "  Depth {depth:.2f} m: {force:.2f} kN/m",
        "no_anchors": "  No anchors (Cantilever Wall).",
        "summary_of_results_title": "\n--- SUMMARY OF RESULTS ---",
        "summary_pressure": "Net Pressure:      Min={p_min:.2f}, Max={p_max:.2f} kPa",
        "summary_shear": "Shear Force:       Min={v_min:.2f}, Max={v_max:.2f} kN/m",
        "summary_moment": "Bending Moment:    Min={m_min:.2f}, Max={m_max:.2f} kNm/m",
        "summary_rotation": "Rotation:          Min={rot_min:.4f}, Max={rot_max:.4f} rad",
        "summary_deflection": "Deflection (mm):   Min={d_min:.2f}, Max={d_max:.2f} mm",
        "stress_check_title": "\n--- STRESS CHECK ---",
        "max_abs_moment": "Max. Absolute Moment: {val:.2f} kNm/m",
        "actual_stress": "Actual Bending Stress (σ_actual):   {val:.1f} MPa",
        "allowable_stress": "Allowable Bending Stress (f_allowable): {val:.1f} MPa",
        "status": "STATUS: {status}",
        "deflection_check_title": "\n--- DEFLECTION CHECK ({code}) ---",
        "actual_deflection": "Actual Max. Deflection (Δ_actual):   {val:.1f} mm",
        "allowable_deflection": "Allowable Deflection (Δ_allowable): {val:.1f} mm",
        "save_plot_action": "Save {plot_name} Plot...",
        "tab_net_pressure": "Net Pressure", "tab_earth_pressure": "Earth Pressure",
        "tab_water_pressure": "Water Pressure", "tab_shear": "Shear Force",
        "tab_moment": "Bending Moment", "tab_rotation": "Rotation",
        "tab_deflection": "Deflection", "anchored_wall": "Anchored Wall",
        "cantilever_wall": "Cantilever Wall", "seismic": "Seismic",
        "static": "Static", "section": "Section",
        "schematic_title": "Problem Schematic", "depth_m": "Depth (m)",
        "water_active": "Water (Active)", "water_passive": "Water (Passive)",
        "dredge_line": "Dredge Line", "earth_active": "Earth (Active)",
        "earth_passive": "Earth (Passive)", "p_max": "P Max", "p_min": "P Min",
        "v_max": "V Max", "v_min": "V Min", "m_max": "M Max", "m_min": "M Min",
        "max_abs_rotation": "Max Abs Rotation", "max_deflection": "Max Deflection",
        "tab_project": "Project & Analysis", "tab_soil": "Soil Profile",
        "tab_anchors": "Anchor Levels", "tab_structure": "Structure & Geometry",
        "tab_loads": "Loads",
        "theoretical_toe": "theoretical toe (D_req)",
        "toe_reaction": "  Toe reaction R (simplified method): {val:.2f} kN/m",
        "diagram_note": "(Diagrams evaluated over H + D_req = H + {val:.2f} m; "
                        "D_design is the constructed length.)",
        "closure_check": "Equilibrium check: M(toe) = {val:.2f} kNm/m (should be ~0)",
        "multi_anchor_note": "  NOTE: multi-anchor distribution is approximate "
                             "(free-earth method is exact for one anchor only).",
        "soil_depth_warning": "Total thickness of the soil layers is small compared "
                              "to the excavation depth. The lowest layer will be "
                              "extended downwards automatically.",
        "anchor_stiffness": "k (kN/m/m):",
        "subgrade_modulus": "Subgrade Modulus kₛ (kN/m³):",
        # --- labels the web interface adds to the ones above
        "analyst": "Analyst:",
        "factors_group": "Partial Factors",
        "fs_phi_label": "Partial factor on tan φ:",
        "fs_c_label": "Partial factor on c:",
        "fs_b_label": "Bending factor (f_y / FS):",
        "emb_factor_label": "Embedment increase factor:",
        "rounding_label": "Rounding increment (m):",
        "gamma_water_label": "Unit weight of water (kN/m³):",
        "bs_embedment_hint": "Embedment 0 takes D_design from the limit-equilibrium analysis.",
        "bs_group": "Beam-Spring (Winkler) Analysis",
        "bs_enable": "Run beam-spring analysis after the LE analysis",
        "bs_staged": "Staged construction (excavate → anchor → …)",
        "bs_overdig_label": "Overdig below anchor level (m):",
        "bs_embedment_label": "Embedment D (m; 0 = use D_design):",
        "tab_beam_spring": "Beam-Spring",
        "bs_title": "\n--- BEAM-SPRING (WINKLER) ANALYSIS ---",
        "bs_embedment": "Embedment used: D = {val:.2f} m (L = {L:.2f} m); "
                        "{n} stages, {it} Newton iterations",
        "bs_stage_excavate": "excavate to {val:.2f} m",
        "bs_stage_anchor": "install anchor at {val:.2f} m",
        "bs_stage_line": "  {i}. {label}: w_max = {w:.1f} mm{forces}",
        "bs_stage_noline": "  {i}. {label}",
        "bs_anchor_line": "  Anchor {depth:.2f} m: T = {force:.2f} kN/m   (LE: {le:.2f})",
        "bs_summary_moment": "Max. Absolute Moment: {val:.2f} kNm/m   (LE: {le:.2f})",
        "bs_summary_deflection": "Max. Deflection: {val:.1f} mm   (LE: {le:.1f})",
        "bs_mobilization": "Passive resistance mobilized: {p:.0%}   |   "
                           "retained face at the active limit: {a:.0%} of the height",
        "bs_failed": "Beam-spring analysis could not be completed:\n{e}",
        "bs_panel_pressure": "Earth pressure (kPa)", "bs_limit_active": "active limit",
        "bs_limit_passive": "passive limit", "bs_mobilized": "mobilized",
        "bs_side_ret": "retained", "bs_side_exc": "excavation",
        "bs_fig_title": "Beam-Spring (Winkler) — final stage",
        "run_action": "Run analysis", "theme_action": "Theme", "save_plot_current": "Save current plot…",
        "card_embed": "Embedment", "card_embed_sub": "D_req / D_design",
        "card_moment": "Max. moment", "card_moment_sub": "LE / beam-spring",
        "card_defl": "Max. deflection", "card_defl_sub": "LE / beam-spring",
        "card_anchor": "Max. anchor load", "card_anchor_sub": "horizontal, per m",
        "card_stress": "Stress check", "card_stress_sub": "σ / f_allow",
        "card_deflcheck": "Deflection check", "card_vertical": "Vertical check",
        "card_vertical_sub": "V_anchor / R_skin", "card_none": "—",
        "ok_short": "OK", "notok_short": "NOT OK", "na_short": "n/a",
        "anchor_title": "Anchor {i}", "anchor_angle": "Angle (°):", "anchor_EA": "EA (kN):",
        "anchor_free_length": "Free length (m):", "anchor_spacing": "Spacing (m):",
        "anchor_prestress": "Lock-off P₀ (kN):",
        "anchor_k_computed": "k_h = {val:,.0f} kN/m per m",
        "layer_title": "Layer {i}", "ks_method": "kₛ method:", "ks_manual": "Manual",
        "ks_menard": "Ménard–Bourdon", "ks_schmitt": "Schmitt (1995)",
        "E_M": "E_M (MPa):", "alpha": "α (rheological):",
        "submerged_theta": "Submerged backfill θ correction (γsat/γ′)",
        "hydrodynamic": "Westergaard hydrodynamic pressure (free water)",
        "bs_water_mode": "Water in excavation:",
        "water_final": "As given (underwater dredging)",
        "water_dewatered": "Dewatered until final stage",
        "anchor_report_line": "  Anchor {depth:.2f} m ({angle:.0f}°): T_h = {th:.1f} kN/m | "
                              "axial = {ta:.1f} kN/anchor | V = {v:.1f} kN/m",
        "vertical_check_title": "\n--- VERTICAL EQUILIBRIUM (indicative) ---",
        "vertical_load": "Vertical anchor component ΣV: {val:.1f} kN/m",
        "vertical_resistance": "Skin friction on embedded length (both faces): {val:.1f} kN/m",
        "warnings_title": "\n--- WARNINGS ---",
        "ks_table_title": "  Subgrade moduli used:",
        "ks_table_line": "    {name}: kₛ = {val:,.0f} kN/m³ ({method})",
        "hydro_legend": "hydrodynamic (Westergaard)",
        "inputs_title": "Inputs", "outputs_title": "Results",
        "report_action": "Export report…",
        "report_filter": "PDF report (*.pdf);;HTML report (*.html);;Word report (*.docx)",
        "report_success": "Report saved to:\n{path}",
        "report_error": "The report could not be created:\n{e}",
        "report_running": "Creating report, please wait…",
        "tab_study": "Study", "study_vars_group": "Study variables",
        "study_options_group": "Sampling and analysis", "study_method": "Method:",
        "method_oat": "One-at-a-time sweep", "method_grid": "Full grid",
        "method_lhs": "Latin hypercube (LHS)", "method_mc": "Monte Carlo",
        "study_n": "Samples N (LHS / MC):", "study_run_bs": "Include beam-spring analysis",
        "study_unfactored": "Unfactored strengths (FS = 1) — for reliability",
        "study_workers": "Parallel workers:", "study_seed": "Random seed:",
        "study_add": "Add variable", "study_remove": "Remove selected",
        "study_run": "Run study", "study_cancel": "Cancel",
        "study_export_csv": "Export CSV…", "study_export_xlsx": "Export XLSX…",
        "col_param": "Parameter", "col_mode": "Mode", "col_min": "Min", "col_max": "Max",
        "col_dist": "Distribution", "col_mean": "Mean", "col_cov": "CoV", "col_points": "Points",
        "mode_range": "Range", "mode_dist": "Distribution",
        "dist_normal": "Normal", "dist_lognormal": "Lognormal", "dist_uniform": "Uniform",
        "study_progress": "Study: {done} / {total} samples", "study_done": "Study completed: {n} samples",
        "study_failed": "The study could not be run:\n{e}", "study_no_vars": "Add at least one study variable.",
        "study_view": "View:", "study_output": "Output:",
        "study_fig_oat": "One-at-a-time sweep", "study_fig_scatter": "Output vs inputs",
        "study_fig_hist": "Distribution of results", "study_fig_tornado": "Sensitivity (tornado)",
        "study_no_data": "No study results yet.", "study_no_sens": "Sensitivities need an LHS / MC / grid study.",
        "study_spearman": "Spearman ρ", "study_src": "SRC (linear)",
        "study_summary_title": "--- STUDY SUMMARY ---",
        "study_samples": "Samples: {n} ({ok} LE ok, {okbs} beam-spring ok), method {m}",
        "study_cancelled": "(cancelled before completion)",
        "study_reliability_title": "Limit states (failure when demand > allowable):",
        "study_no_failures": "no failures in {n} samples (P_f < {lim:.2g} at 95 %)",
        "study_sens_title": "Spearman rank correlation (ranked by |ρ|):",
        "study_oat_title": "One-at-a-time ranges (min → max of output):",
        "study_placeholder": "Define variables in the Study tab and run the study.",
        "out_d_req": "D_req", "out_d_design": "D_design", "out_M_le": "M_max (LE)", "out_sigma_le": "σ (LE)",
        "out_defl_le": "Δ (LE)", "out_T_le": "T_max (LE)", "out_M_bs": "M_max (W)", "out_sigma_bs": "σ (W)",
        "out_defl_bs": "Δ (W)", "out_T_bs": "T_max (W)", "out_mob_p": "passive mob.",
        "var_phi": "φ", "var_cohesion": "c", "var_gamma": "γ", "var_gamma_sat": "γsat",
        "var_thickness": "thickness", "var_k_s": "kₛ", "var_E_M": "E_M",
        "var_excavation_depth_H": "H", "var_wall_friction_delta": "δ", "var_backfill_slope_beta": "β",
        "var_surcharge_load": "q", "var_water_level_active": "hw (retained)",
        "var_water_level_passive": "hw (excavation)", "var_kh": "kh",
        "var_embedment_increase_factor": "D factor", "var_depth": "depth", "var_prestress": "P₀",
        "var_EA": "EA", "var_free_length": "L_free", "var_spacing": "s", "var_angle": "angle",
        "grp_geometry": "Geometry", "grp_loads": "Loads", "grp_seismic": "Seismic", "grp_factors": "Factors",
        "grp_anchor": "Anchor {i}"
    },
    "tr": {
        "window_title": f"{APP_NAME} v{APP_VERSION} — Palplanş Duvar Analizi", "file_menu": "&Dosya",
        "help_menu": "&Yardım", "about_action": "&Hakkında",
        "about_title": f"{APP_NAME} Hakkında",
        "about_text": f"<h3>{APP_NAME} v{APP_VERSION}</h3>"
                      "<p>Palplanş Duvar Analizi — konsol ve çok ankrajlı sistemler için serbest zemin desteği "
                      "yöntemini kullanarak palplanş duvarlarının geoteknik analizini gerçekleştirir.</p>"
                      "<p>Python, Matplotlib ve SciPy ile geliştirilmiştir; arayüz tarayıcıda çalışır.</p>"
                      "<p><b>Geliştirici:</b> Hasan Deniz Altuntaş<br>© 2025 Hasan Deniz Altuntaş</p>",
        "open_project": "&Proje Aç...", "save_project": "Projeyi &Farklı Kaydet...",
        "exit_action": "Çı&kış", "lang_label": "Dil:",
        "project_group": "Proje Bilgileri", "project_title_label": "Proje Başlığı:",
        "analysis_options_group": "Analiz Seçenekleri",
        "seismic_checkbox": "Sismik Analizi Aktive Et",
        "kh_label": "Yatay Sismik Katsayı (kh):",
        "kv_label": "Düşey Sismik Katsayı (kv):",
        "deflection_check_label": "Deplasman Kodu:",
        "soil_profile_group": "Zemin Profili",
        "add_soil_layer_button": "Zemin Tabakası Ekle",
        "anchor_levels_group": "Ankraj Seviyeleri",
        "add_anchor_button": "Ankraj Ekle",
        "structural_props_group": "Yapısal Özellikler",
        "section_model_label": "Kesit Modeli:",
        "manufacturer_label": "Üretici:", "steel_grade_label": "Çelik Sınıfı:",
        "geometry_group": "Geometri",
        "excavation_depth_label": "Kazı Derinliği H (m):",
        "backfill_slope_label": "Dolgu Şev Açısı β (°):",
        "dredge_line_slope_label": "Tarama Hattı Şev Açısı α (°):",
        "wall_friction_label": "Duvar Sürtünme Açısı δ (°):",
        "loads_group": "Yükler ve Su", "surcharge_label": "Sürşarj Yükü (kPa):",
        "active_water_label": "Aktif Su Seviyesi (m):",
        "passive_water_label": "Pasif Su Seviyesi (m):",
        "run_analysis_button": "ANALİZİ ÇALIŞTIR",
        "results_summary_tab": "Sonuç Özeti",
        "save_plot_button": "Grafiği Kaydet",
        "results_placeholder": "Analiz sonuçları burada gösterilecektir...",
        "running_analysis": "Analiz çalıştırılıyor, lütfen bekleyin...",
        "analysis_complete": "Analiz başarıyla tamamlandı.",
        "error_title": "Hata", "error_message": "Bir hata oluştu:\n\n{type}: {e}",
        "warning_title": "Uyarı",
        "no_plot_warning": "Kaydedilecek bir grafik bulunmuyor. Lütfen önce analiz çalıştırın.",
        "save_success_title": "Başarılı",
        "save_success_message": "Grafik başarıyla kaydedildi:\n{path}",
        "save_error_message": "Grafik kaydedilirken bir hata oluştu:\n{e}",
        "layer_name": "Tabaka Adı:", "thickness": "Kalınlık (m):",
        "unit_weight": "Birim Hacim Ağırlığı (kN/m³):",
        "sat_unit_weight": "Doygun Birim Hacim Ağ. (kN/m³):",
        "friction_angle": "İçsel Sürtünme Açısı (°):",
        "cohesion": "Kohezyon (kPa):", "remove_layer": "Bu Tabakayı Kaldır",
        "depth": "  Derinlik (m):", "remove": "Kaldır",
        "design_results_title": "--- TASARIM SONUÇLARI ---",
        "selected_section": "Seçilen Kesit: {model} ({grade})",
        "req_embedment": "Teorik Gerekli Gömülme Derinliği (D_req): {val:.2f} m",
        "design_embedment": "Tasarım Gömülme Derinliği (D_design):     {val:.2f} m",
        "total_length": "Toplam Duvar Uzunluğu (L_total):          {val:.2f} m",
        "anchor_forces_title": "\n--- ANKRAJ KUVVETLERİ ---",
        "anchor_force_line": "  Derinlik {depth:.2f} m: {force:.2f} kN/m",
        "no_anchors": "  Ankraj yok (Konsol Duvar).",
        "summary_of_results_title": "\n--- SONUÇLARIN ÖZETİ ---",
        "summary_pressure": "Net Basınç:        Min={p_min:.2f}, Maks={p_max:.2f} kPa",
        "summary_shear": "Kesme Kuvveti:     Min={v_min:.2f}, Maks={v_max:.2f} kN/m",
        "summary_moment": "Eğilme Momenti:    Min={m_min:.2f}, Maks={m_max:.2f} kNm/m",
        "summary_rotation": "Dönme:             Min={rot_min:.4f}, Maks={rot_max:.4f} rad",
        "summary_deflection": "Deplasman (mm):    Min={d_min:.2f}, Maks={d_max:.2f} mm",
        "stress_check_title": "\n--- GERİLME KONTROLÜ ---",
        "max_abs_moment": "Maksimum Mutlak Moment: {val:.2f} kNm/m",
        "actual_stress": "Oluşan Gerilme (σ_actual):   {val:.1f} MPa",
        "allowable_stress": "İzin Verilen Gerilme (f_allowable): {val:.1f} MPa",
        "status": "DURUM: {status}",
        "deflection_check_title": "\n--- DEPLASMAN KONTROLÜ ({code}) ---",
        "actual_deflection": "Oluşan Maks. Deplasman (Δ_actual):   {val:.1f} mm",
        "allowable_deflection": "İzin Verilen Deplasman (Δ_allowable): {val:.1f} mm",
        "save_plot_action": "{plot_name} Grafiğini Kaydet...",
        "tab_net_pressure": "Net Basınç", "tab_earth_pressure": "Zemin Basıncı",
        "tab_water_pressure": "Su Basıncı", "tab_shear": "Kesme Kuvveti",
        "tab_moment": "Eğilme Momenti", "tab_rotation": "Dönme",
        "tab_deflection": "Deplasman", "anchored_wall": "Ankrajlı Duvar",
        "cantilever_wall": "Konsol Duvar", "seismic": "Sismik",
        "static": "Statik", "section": "Kesit",
        "schematic_title": "Problem Şeması", "depth_m": "Derinlik (m)",
        "water_active": "Su (Aktif)", "water_passive": "Su (Pasif)",
        "dredge_line": "Tarama Hattı", "earth_active": "Zemin (Aktif)",
        "earth_passive": "Zemin (Pasif)", "p_max": "P Maks", "p_min": "P Min",
        "v_max": "V Maks", "v_min": "V Min", "m_max": "M Maks", "m_min": "M Min",
        "max_abs_rotation": "Maks Mutlak Dönme",
        "max_deflection": "Maks Deplasman",
        "tab_project": "Proje & Analiz", "tab_soil": "Zemin Profili",
        "tab_anchors": "Ankraj Seviyeleri",
        "tab_structure": "Yapısal & Geometri", "tab_loads": "Yükler",
        "theoretical_toe": "teorik uç (D_req)",
        "toe_reaction": "  Uç reaksiyonu R (basitleştirilmiş yöntem): {val:.2f} kN/m",
        "diagram_note": "(Diyagramlar H + D_req = H + {val:.2f} m boyunca hesaplanmıştır; "
                        "D_design imal edilecek boydur.)",
        "closure_check": "Denge kontrolü: M(uç) = {val:.2f} kNm/m (~0 olmalı)",
        "multi_anchor_note": "  NOT: Çok ankrajlı dağılım yaklaşıktır "
                             "(serbest zemin desteği yöntemi tek ankraj için kesindir).",
        "soil_depth_warning": "Zemin tabakalarının toplam kalınlığı kazı derinliğine "
                              "göre düşük. En alt tabaka otomatik olarak aşağı "
                              "doğru uzatılacaktır.",
        "anchor_stiffness": "k (kN/m/m):",
        "subgrade_modulus": "Yatak Katsayısı kₛ (kN/m³):",
        # --- web arayüzünün yukarıdakilere eklediği etiketler
        "analyst": "Hazırlayan:",
        "factors_group": "Kısmi Katsayılar",
        "fs_phi_label": "tan φ kısmi katsayısı:",
        "fs_c_label": "c kısmi katsayısı:",
        "fs_b_label": "Eğilme katsayısı (f_y / FS):",
        "emb_factor_label": "Gömülme artırma katsayısı:",
        "rounding_label": "Yuvarlama adımı (m):",
        "gamma_water_label": "Suyun birim hacim ağırlığı (kN/m³):",
        "bs_embedment_hint": "Gömülme 0 ise limit denge analizinin D_design değeri kullanılır.",
        "bs_group": "Kiriş-Yay (Winkler) Analizi",
        "bs_enable": "LE analizinden sonra kiriş-yay analizini çalıştır",
        "bs_staged": "Aşamalı imalat (kazı → ankraj → …)",
        "bs_overdig_label": "Ankraj seviyesi altı kazı payı (m):",
        "bs_embedment_label": "Gömülme D (m; 0 = D_design kullan):",
        "tab_beam_spring": "Kiriş-Yay",
        "bs_title": "\n--- KİRİŞ-YAY (WINKLER) ANALİZİ ---",
        "bs_embedment": "Kullanılan gömülme: D = {val:.2f} m (L = {L:.2f} m); "
                        "{n} aşama, {it} Newton iterasyonu",
        "bs_stage_excavate": "{val:.2f} m'ye kazı",
        "bs_stage_anchor": "{val:.2f} m'de ankraj montajı",
        "bs_stage_line": "  {i}. {label}: w_maks = {w:.1f} mm{forces}",
        "bs_stage_noline": "  {i}. {label}",
        "bs_anchor_line": "  Ankraj {depth:.2f} m: T = {force:.2f} kN/m   (LE: {le:.2f})",
        "bs_summary_moment": "Maksimum Mutlak Moment: {val:.2f} kNm/m   (LE: {le:.2f})",
        "bs_summary_deflection": "Maks. Deplasman: {val:.1f} mm   (LE: {le:.1f})",
        "bs_mobilization": "Mobilize pasif direnç: {p:.0%}   |   "
                           "arka yüzün aktif sınıra ulaşan kısmı: yüksekliğin {a:.0%}'i",
        "bs_failed": "Kiriş-yay analizi tamamlanamadı:\n{e}",
        "bs_panel_pressure": "Zemin basıncı (kPa)", "bs_limit_active": "aktif sınır",
        "bs_limit_passive": "pasif sınır", "bs_mobilized": "mobilize",
        "bs_side_ret": "arka", "bs_side_exc": "kazı",
        "bs_fig_title": "Kiriş-Yay (Winkler) — son aşama",
        "run_action": "Analizi çalıştır", "theme_action": "Tema", "save_plot_current": "Açık grafiği kaydet…",
        "card_embed": "Gömülme", "card_embed_sub": "D_req / D_design",
        "card_moment": "Maks. moment", "card_moment_sub": "LE / kiriş-yay",
        "card_defl": "Maks. deplasman", "card_defl_sub": "LE / kiriş-yay",
        "card_anchor": "Maks. ankraj yükü", "card_anchor_sub": "yatay, m başına",
        "card_stress": "Gerilme kontrolü", "card_stress_sub": "σ / f_izin",
        "card_deflcheck": "Deplasman kontrolü", "card_vertical": "Düşey kontrol",
        "card_vertical_sub": "V_ankraj / R_sürtünme", "card_none": "—",
        "ok_short": "UYGUN", "notok_short": "UYGUN DEĞİL", "na_short": "—",
        "anchor_title": "Ankraj {i}", "anchor_angle": "Açı (°):", "anchor_EA": "EA (kN):",
        "anchor_free_length": "Serbest boy (m):", "anchor_spacing": "Aralık (m):",
        "anchor_prestress": "Kilitleme yükü P₀ (kN):",
        "anchor_k_computed": "k_h = {val:,.0f} kN/m (m başına)",
        "layer_title": "Tabaka {i}", "ks_method": "kₛ yöntemi:", "ks_manual": "Elle",
        "ks_menard": "Ménard–Bourdon", "ks_schmitt": "Schmitt (1995)",
        "E_M": "E_M (MPa):", "alpha": "α (reolojik):",
        "submerged_theta": "Batık dolgu θ düzeltmesi (γdoy/γ′)",
        "hydrodynamic": "Westergaard hidrodinamik basıncı (serbest su)",
        "bs_water_mode": "Kazıdaki su:",
        "water_final": "Girildiği gibi (su altı tarama)",
        "water_dewatered": "Son aşamaya kadar susuzlaştırılmış",
        "anchor_report_line": "  Ankraj {depth:.2f} m ({angle:.0f}°): T_h = {th:.1f} kN/m | "
                              "eksenel = {ta:.1f} kN/ankraj | V = {v:.1f} kN/m",
        "vertical_check_title": "\n--- DÜŞEY DENGE (gösterge) ---",
        "vertical_load": "Ankrajların düşey bileşeni ΣV: {val:.1f} kN/m",
        "vertical_resistance": "Gömülü boyda çevre sürtünmesi (iki yüz): {val:.1f} kN/m",
        "warnings_title": "\n--- UYARILAR ---",
        "ks_table_title": "  Kullanılan yatak katsayıları:",
        "ks_table_line": "    {name}: kₛ = {val:,.0f} kN/m³ ({method})",
        "hydro_legend": "hidrodinamik (Westergaard)",
        "inputs_title": "Girdiler", "outputs_title": "Sonuçlar",
        "report_action": "Rapor oluştur…",
        "report_filter": "PDF raporu (*.pdf);;HTML raporu (*.html);;Word raporu (*.docx)",
        "report_success": "Rapor kaydedildi:\n{path}",
        "report_error": "Rapor oluşturulamadı:\n{e}",
        "report_running": "Rapor oluşturuluyor, lütfen bekleyin…",
        "tab_study": "Çalışma", "study_vars_group": "Çalışma değişkenleri",
        "study_options_group": "Örnekleme ve analiz", "study_method": "Yöntem:",
        "method_oat": "Tek değişken taraması", "method_grid": "Tam ızgara",
        "method_lhs": "Latin hiperküp (LHS)", "method_mc": "Monte Carlo",
        "study_n": "Örnek sayısı N (LHS / MC):", "study_run_bs": "Kiriş-yay analizini de çalıştır",
        "study_unfactored": "Faktörsüz dayanımlar (FS = 1) — güvenilirlik için",
        "study_workers": "Paralel işçi:", "study_seed": "Rastgele tohum:",
        "study_add": "Değişken ekle", "study_remove": "Seçileni kaldır",
        "study_run": "Çalışmayı başlat", "study_cancel": "İptal",
        "study_export_csv": "CSV'ye aktar…", "study_export_xlsx": "XLSX'e aktar…",
        "col_param": "Parametre", "col_mode": "Mod", "col_min": "Min", "col_max": "Maks",
        "col_dist": "Dağılım", "col_mean": "Ortalama", "col_cov": "CoV", "col_points": "Nokta",
        "mode_range": "Aralık", "mode_dist": "Dağılım",
        "dist_normal": "Normal", "dist_lognormal": "Lognormal", "dist_uniform": "Üniform",
        "study_progress": "Çalışma: {done} / {total} örnek", "study_done": "Çalışma tamamlandı: {n} örnek",
        "study_failed": "Çalışma çalıştırılamadı:\n{e}", "study_no_vars": "En az bir çalışma değişkeni ekleyin.",
        "study_view": "Görünüm:", "study_output": "Çıktı:",
        "study_fig_oat": "Tek değişken taraması", "study_fig_scatter": "Çıktı – girdi ilişkisi",
        "study_fig_hist": "Sonuçların dağılımı", "study_fig_tornado": "Duyarlılık (tornado)",
        "study_no_data": "Henüz çalışma sonucu yok.", "study_no_sens": "Duyarlılık için LHS / MC / ızgara çalışması gerekir.",
        "study_spearman": "Spearman ρ", "study_src": "SRC (doğrusal)",
        "study_summary_title": "--- ÇALIŞMA ÖZETİ ---",
        "study_samples": "Örnek: {n} ({ok} LE başarılı, {okbs} kiriş-yay başarılı), yöntem {m}",
        "study_cancelled": "(tamamlanmadan iptal edildi)",
        "study_reliability_title": "Sınır durumları (talep > izin verilen ise göçme):",
        "study_no_failures": "{n} örnekte göçme yok (P_f < {lim:.2g}, %95 güven)",
        "study_sens_title": "Spearman sıra korelasyonu (|ρ| sırasıyla):",
        "study_oat_title": "Tek değişken aralıkları (çıktı min → maks):",
        "study_placeholder": "Çalışma sekmesinde değişkenleri tanımlayıp çalışmayı başlatın.",
        "out_d_req": "D_req", "out_d_design": "D_design", "out_M_le": "M_maks (LE)", "out_sigma_le": "σ (LE)",
        "out_defl_le": "Δ (LE)", "out_T_le": "T_maks (LE)", "out_M_bs": "M_maks (W)", "out_sigma_bs": "σ (W)",
        "out_defl_bs": "Δ (W)", "out_T_bs": "T_maks (W)", "out_mob_p": "pasif mob.",
        "var_phi": "φ", "var_cohesion": "c", "var_gamma": "γ", "var_gamma_sat": "γdoy",
        "var_thickness": "kalınlık", "var_k_s": "kₛ", "var_E_M": "E_M",
        "var_excavation_depth_H": "H", "var_wall_friction_delta": "δ", "var_backfill_slope_beta": "β",
        "var_surcharge_load": "q", "var_water_level_active": "hw (arka)",
        "var_water_level_passive": "hw (kazı)", "var_kh": "kh",
        "var_embedment_increase_factor": "D katsayısı", "var_depth": "derinlik", "var_prestress": "P₀",
        "var_EA": "EA", "var_free_length": "L_serbest", "var_spacing": "s", "var_angle": "açı",
        "grp_geometry": "Geometri", "grp_loads": "Yükler", "grp_seismic": "Sismik", "grp_factors": "Katsayılar",
        "grp_anchor": "Ankraj {i}"
    }
}
