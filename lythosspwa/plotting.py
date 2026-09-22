"""
Matplotlib figures for Lythos SPWA: LE diagrams with
the problem schematic, and the beam-spring (Winkler) 4-panel figure.

Figures are theme-aware: pass theme="dark" to match the interface's dark mode
(config.THEMES). Colors come from config.PLOT_PALETTE so every diagram uses
the same color for "moment", "shear", etc.
"""

import matplotlib.patches as patches
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.figure import Figure

from .analysis_engine import AnalysisEngine, RetainingWall
from .config import PLOT_PALETTE, SOIL_FILL
from .plot_style import annotate_point, label_box, style_axis, style_figure


class Plotter:
    def __init__(self, wall: RetainingWall, analysis: AnalysisEngine,
                 lang_dict: dict, bs_results: dict = None, theme: str = "light"):
        self.wall = wall
        self.analysis = analysis
        self.results = analysis.results
        self.bs = bs_results
        self.lang_dict = lang_dict
        self.theme_name = theme
        self.palette = PLOT_PALETTE
        self.l_total = wall.h + analysis.d_design          # design length (schematic)
        self.l_theory = wall.h + analysis.d_required       # diagrams end here

    def _create_base_figure_and_axes(self, fig: Figure, title: str):
        """Creates axes on the provided figure object."""
        self.theme = style_figure(fig, self.theme_name)
        axes = fig.subplots(
            1, 2,
            gridspec_kw={'width_ratios': [1, 1]}
        )
        self._format_figure(fig, axes, title)
        return axes

    def _format_figure(self, fig: plt.Figure, axes: list[plt.Axes], title: str):
        th = self.theme
        title_info = self.wall.config['project_info']
        analysis_type = self.lang_dict["anchored_wall"] if \
            not self.analysis.is_cantilever else self.lang_dict["cantilever_wall"]
        seismic = (f"({self.lang_dict['seismic']}, kh={self.wall.kh})"
                   if self.wall.is_seismic else f"({self.lang_dict['static']})")
        main_title = f"{title_info.get('title')}\n{analysis_type} {seismic}"
        fig.suptitle(main_title, fontsize=14, y=0.99, color=th['fg'])

        axes[1].set_title(
            f"{title}\n{self.lang_dict['section']}: "
            f"{self.wall.selected_section_model} ({self.wall.selected_steel_grade})",
            fontsize=11, color=th['fg'])

        bottom_lim = self.l_total * 1.05
        top_lim = -self.l_total * 0.05
        for ax in axes:
            ax.set_ylim(bottom_lim, top_lim)

        axes[0].tick_params(axis='y', labelleft=True)
        axes[1].tick_params(axis='y', labelleft=False)
        fig.tight_layout(rect=[0.03, 0.03, 0.97, 0.90])

    def setup_plot(self, plot_key: str, figure: Figure):
        """Configures and draws a specific plot onto the provided figure."""
        if plot_key == 'beam_spring':
            self._setup_beam_spring_plot(figure)
            return
        plot_configs = {
            'net_pressure': {'title_key': 'tab_net_pressure', 'data_key': 'net_pressure',
                             'xlabel': 'kPa', 'color': 'net_pressure', 'annotations': [('p_max', 'max'), ('p_min', 'min')]},
            'earth_pressure': {'title_key': 'tab_earth_pressure', 'xlabel': 'kPa'},
            'water_pressure': {'title_key': 'tab_water_pressure', 'xlabel': 'kPa'},
            'shear': {'title_key': 'tab_shear', 'data_key': 'shear',
                      'xlabel': 'kN/m', 'color': 'shear', 'annotations': [('v_max', 'max'), ('v_min', 'min')]},
            'moment': {'title_key': 'tab_moment', 'data_key': 'moment',
                       'xlabel': 'kNm/m', 'color': 'moment', 'annotations': [('m_max', 'max'), ('m_min', 'min')]},
            'rotation': {'title_key': 'tab_rotation', 'data_key': 'rotation',
                         'xlabel': 'rad', 'color': 'rotation', 'annotations': [('rot_max_abs', 'max_abs', 1, "max_abs_rotation")]},
            'deflection': {'title_key': 'tab_deflection', 'data_key': 'deflection',
                           'xlabel': 'mm', 'color': 'deflection', 'annotations': [('delta_max', 'max_abs', 1000, "max_deflection")]}
        }
        config = plot_configs[plot_key]

        axes = self._create_base_figure_and_axes(
            figure, self.lang_dict[config['title_key']])
        self._plot_schematic(axes[0])

        if plot_key == 'earth_pressure':
            self._plot_dual_diagram(
                axes[1], self.results['earth_pressure_active'],
                self.results['earth_pressure_passive'], config['xlabel'],
                self.lang_dict['earth_active'], self.lang_dict['earth_passive'],
                self.palette['active'], self.palette['passive']
            )
        elif plot_key == 'water_pressure':
            self._plot_dual_diagram(
                axes[1], self.results['water_pressure_active'],
                self.results['water_pressure_passive'], config['xlabel'],
                self.lang_dict['water_active'],
                self.lang_dict['water_passive'],
                self.palette['water_active'], self.palette['water_passive']
            )
            hydro = self.results.get('hydrodynamic_pressure')
            if hydro is not None and np.max(hydro) > 1e-9:
                axes[1].plot(hydro, self.results['z_vals'], color=self.palette['hydrodynamic'],
                             ls=':', lw=1.4, label=self.lang_dict['hydro_legend'])
                axes[1].legend(fontsize=8, facecolor=self.theme['panel'],
                               edgecolor=self.theme['border'], labelcolor=self.theme['fg'])
        else:
            multiplier = 1000 if plot_key == 'deflection' else 1
            data_to_plot = self.results[config['data_key']] * multiplier
            color = self.palette[config['color']]
            self._plot_diagram(axes[1], data_to_plot, config['xlabel'], color)
            for ann_config in config['annotations']:
                res_key, pos, *rest = ann_config

                value_for_label = self.results[res_key]
                label_key = rest[1] if len(rest) > 1 else res_key
                label_text = f"{self.lang_dict.get(label_key, label_key)} = {value_for_label:.2f}"
                if "rotation" in label_key:
                    label_text = f"{self.lang_dict.get(label_key, label_key)} = {value_for_label:.4f}"
                elif "deflection" in label_key:
                     label_text = f"{self.lang_dict.get(label_key, label_key)} = {value_for_label*1000:.2f} mm"

                self._annotate_diagram(
                    axes[1], data_to_plot, label_text, pos, color)

    def _setup_beam_spring_plot(self, fig: Figure):
        """Four panels: mobilised earth pressures, shear, moment, deflection."""
        L = self.lang_dict
        bs = self.bs
        th = style_figure(fig, self.theme_name)
        self.theme = th
        title_info = self.wall.config['project_info']
        fig.suptitle(f"{title_info.get('title')}\n{L['bs_fig_title']}", fontsize=13, y=0.99, color=th['fg'])
        if bs is None:
            ax = fig.add_subplot(111)
            ax.set_facecolor(th['panel'])
            ax.text(0.5, 0.5, L["results_placeholder"], ha='center', va='center', color=th['fg_dim'])
            ax.set_axis_off()
            return
        axes = fig.subplots(1, 4, sharey=True)
        z = bs['z_vals']
        length = bs['length']
        for ax in axes:
            ax.set_ylim(length * 1.05, -length * 0.05)
            ax.axhline(self.wall.h, color=self.palette['active'], ls='--', lw=1)
            style_axis(ax, th)
        axes[0].set_ylabel(L["depth_m"])

        # panel 1: pressures (retained positive, excavation negative)
        ax = axes[0]
        ax.set_title(L["bs_panel_pressure"], fontsize=10, color=th['fg'])
        active, passive = self.palette['active'], self.palette['passive']
        ax.plot(bs['pa_ret'], z, color=active, ls=':', lw=1, label=f"{L['bs_side_ret']} {L['bs_limit_active']}")
        ax.plot(bs['p_ret'], z, color=active, lw=2, label=f"{L['bs_side_ret']} {L['bs_mobilized']}")
        ax.fill_betweenx(z, bs['p_ret'], 0, color=active, alpha=0.15, lw=0)
        ax.plot(-bs['pp_exc'], z, color=passive, ls=':', lw=1, label=f"{L['bs_side_exc']} {L['bs_limit_passive']}")
        ax.plot(-bs['p_exc'], z, color=passive, lw=2, label=f"{L['bs_side_exc']} {L['bs_mobilized']}")
        ax.fill_betweenx(z, -bs['p_exc'], 0, color=passive, alpha=0.15, lw=0)
        ax.axvline(0, color=th['border'], lw=1)
        ax.legend(fontsize=6, loc='lower left', facecolor=th['panel'],
                 edgecolor=th['border'], labelcolor=th['fg'])
        for depth, force in bs['anchor_forces'].items():
            ax.axhline(depth, color=th['fg'], lw=1.2)
            ax.text(ax.get_xlim()[0], depth, f" T={force:.0f}", fontsize=7, va='bottom',
                    color=th['fg'], bbox=label_box(th, alpha=0.8))

        for ax, key, xlabel, color, mult in [
                (axes[1], 'shear', 'kN/m', self.palette['shear'], 1.0),
                (axes[2], 'moment', 'kNm/m', self.palette['moment'], 1.0),
                (axes[3], 'deflection', 'mm', self.palette['deflection'], 1000.0)]:
            data = bs[key] * mult
            ax.set_title(f"{L['tab_' + key]}", fontsize=10, color=th['fg'])
            ax.set_xlabel(xlabel, fontsize=9)
            ax.plot(data, z, color=color, lw=2.2, solid_capstyle='round')
            ax.fill_betweenx(z, data, 0, color=color, alpha=0.15, lw=0)
            ax.axvline(0, color=th['border'], lw=1)
            idx = int(np.argmax(np.abs(data)))
            annotate_point(ax, data[idx], z[idx], f"{data[idx]:.1f}", th, color,
                           dx=10, ha='left', fontsize=8)
            m = max(abs(np.min(data)), abs(np.max(data))) * 0.35 or 0.1
            ax.set_xlim(np.min(data) - m, np.max(data) + m)
        fig.tight_layout(rect=[0.03, 0.03, 0.97, 0.90])

    def _annotate_diagram(self, ax, data, label, position, color):
        th = self.theme
        if abs(np.max(np.abs(data))) < 1e-6:
            return

        if position == 'max_abs':
            idx = np.argmax(np.abs(data))
        elif position == 'max':
            idx = np.argmax(data)
        else:
            idx = np.argmin(data)

        annot_val, annot_y = data[idx], self.results['z_vals'][idx]

        xlims = ax.get_xlim()
        x_range = xlims[1] - xlims[0]
        if abs(x_range) < 1e-9: x_range = 1
        x_pos_ratio = (annot_val - xlims[0]) / x_range

        if x_pos_ratio > 0.8:
            ha, x_offset = 'right', -25
        elif x_pos_ratio < 0.2:
            ha, x_offset = 'left', 25
        else:
            ha = 'left' if annot_val >= 0 else 'right'
            x_offset = 25 if annot_val >= 0 else -25

        va = 'bottom' if position != 'min' else 'top'
        y_offset = 25 if position != 'min' else -25

        annotate_point(ax, annot_val, annot_y, label, th, color,
                       dx=x_offset, dy=y_offset, ha=ha, va=va)

    def _mark_levels(self, ax):
        """Dredge line and theoretical toe (D_req) on a diagram axis."""
        th = self.theme
        ax.axhline(self.wall.h, color=self.palette['active'], ls='--', lw=1)
        ax.axhline(self.l_theory, color=th['fg_dim'], ls='-.', lw=0.8)
        ax.text(0.98, self.l_theory, f" {self.lang_dict['theoretical_toe']} ",
                transform=ax.get_yaxis_transform(), ha='right', va='bottom',
                fontsize=7, color=th['fg_dim'])

    def _plot_diagram(self, ax, data, xlabel, color):
        th = self.theme
        ax.set_xlabel(xlabel, fontsize=10)
        ax.plot(data, self.results['z_vals'], color=color, lw=2.2, solid_capstyle='round', zorder=3)
        self._mark_levels(ax)
        ax.axvline(0, color=th['border'], lw=1, zorder=1)
        ax.fill_betweenx(self.results['z_vals'], data, 0, color=color, alpha=0.15, lw=0, zorder=2)
        style_axis(ax, th)
        min_val, max_val = np.min(data), np.max(data)
        margin = max(abs(min_val), abs(max_val)) * 0.3
        if margin < 1e-9: margin = 0.1
        ax.set_xlim(min_val - margin, max_val + margin)

    def _plot_dual_diagram(self, ax, data1, data2, xlabel, label1, label2,
                           color1, color2):
        th = self.theme
        ax.set_xlabel(xlabel, fontsize=10)
        ax.plot(data1, self.results['z_vals'], color=color1, lw=2.0, label=label1, zorder=3)
        ax.fill_betweenx(self.results['z_vals'], data1, 0, color=color1, alpha=0.15, lw=0, zorder=2)
        ax.plot(-data2, self.results['z_vals'], color=color2, lw=2.0, label=label2, zorder=3)
        ax.fill_betweenx(self.results['z_vals'], -data2, 0, color=color2, alpha=0.15, lw=0, zorder=2)
        self._mark_levels(ax)
        ax.axvline(0, color=th['border'], lw=1, zorder=1)
        style_axis(ax, th)
        ax.legend(fontsize=8, facecolor=th['panel'], edgecolor=th['border'], labelcolor=th['fg'])
        min_val = -np.max(data2) if len(data2) > 0 else 0
        max_val = np.max(data1) if len(data1) > 0 else 0
        margin = max(abs(min_val), abs(max_val)) * 0.1
        if margin < 1e-9: margin = 0.1
        ax.set_xlim(min_val - margin, max_val + margin)

    def _plot_schematic(self, ax: plt.Axes):
        th = self.theme
        sw, wall_x, w = 1.3, -0.1, self.wall
        ax.set_title(self.lang_dict["schematic_title"], fontsize=12, color=th['fg'])
        ax.set_xlim(-sw, sw)
        ax.set_xticks([])
        ax.set_ylabel(self.lang_dict["depth_m"], fontsize=10)
        soil = SOIL_FILL[self.theme_name if self.theme_name in SOIL_FILL else "light"]

        by = -np.tan(w.beta) * (sw + wall_x)
        active_poly = [(wall_x, 0), (-sw, by), (-sw, self.l_total), (wall_x, self.l_total)]
        ax.add_patch(patches.Polygon(active_poly, fc=soil, alpha=0.45, lw=0))

        dy = w.h + np.tan(w.alpha) * (sw - (wall_x + 0.2))
        passive_poly = [(wall_x + 0.2, w.h), (sw, dy), (sw, self.l_total), (wall_x + 0.2, self.l_total)]
        ax.add_patch(patches.Polygon(passive_poly, fc=soil, alpha=0.45, lw=0))

        ax.add_patch(patches.Rectangle((wall_x, 0), 0.2, self.l_total,
                                       fc=th['fg_dim'], ec=th['fg'], lw=1, zorder=10))

        ax.axhline(w.hw_active, color=self.palette['water_active'], ls='--', lw=1.4,
                  xmin=0.05, xmax=0.45, label=self.lang_dict["water_active"])
        ax.axhline(w.hw_passive, color=self.palette['water_passive'], ls=':', lw=1.4,
                  xmin=0.55, xmax=0.95, label=self.lang_dict["water_passive"])
        ax.axhline(w.h, color=self.palette['active'], ls='-', lw=2,
                  xmin=0.55, xmax=1.0, label=self.lang_dict["dredge_line"])

        if not self.analysis.is_cantilever:
            for depth, force in self.analysis.t_anchors.items():
                ax.plot([-0.5, wall_x], [depth, depth], color=th['fg'], lw=2, zorder=11)
                ax.text(-0.5, depth, f" T={force:.1f}", ha='right', va='bottom', fontsize=8,
                        zorder=12, color=th['fg'], bbox=label_box(th, alpha=0.85))

        self._draw_dimension_line(ax, 0.9, 0, w.h, f"H = {w.h:.2f} m")
        self._draw_dimension_line(ax, 0.9, w.h, self.l_total,
                                  f"D_design = {self.analysis.d_design:.2f} m")
        self._draw_dimension_line(ax, 0.6, w.h, self.l_theory,
                                  f"D_req = {self.analysis.d_required:.2f} m")
        ax.axhline(self.l_theory, color=th['fg_dim'], ls='-.', lw=0.8, xmin=0.4, xmax=0.95)

        ax.set_facecolor(th['panel'])
        for s in ax.spines.values():
            s.set_color(th['border'])
        ax.tick_params(colors=th['fg_dim'], labelsize=8.5)
        ax.legend(loc='lower left', fontsize=8, facecolor=th['panel'],
                 edgecolor=th['border'], labelcolor=th['fg'])
        ax.grid(False)

    def _draw_dimension_line(self, ax, x, y1, y2, label):
        th = self.theme
        ax.arrow(x, y1, 0, y2 - y1, head_width=0.04, head_length=0.2, fc=th['fg'], ec=th['fg'])
        ax.arrow(x, y2, 0, y1 - y2, head_width=0.04, head_length=0.2, fc=th['fg'], ec=th['fg'])
        ax.text(x + 0.05, (y1 + y2) / 2, f" {label} ", ha='left', va='center', rotation=90,
                color=th['fg'], bbox=dict(fc=th['panel'], ec='none', alpha=0.85), fontsize=8)
