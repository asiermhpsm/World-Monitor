"""
Módulo 11 — Indicadores Adelantados y Señales de Alerta
Síntesis prospectiva: ¿Qué anticipan los datos para los próximos 6-18 meses?
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import dash_bootstrap_components as dbc
import plotly.graph_objs as go
from dash import Input, Output, State, ctx, dcc, html, no_update

from components.chart_config import COLORS as C, get_base_layout, get_time_range_buttons
from config import COLORS
from modules.data_helpers import (
    calculate_inflation_pressure,
    calculate_recession_probability,
    calculate_sahm_indicator,
    calculate_systemic_risk_index,
    generate_indicator_summary,
    get_indicator_history_for_dashboard,
    get_latest_value,
    get_series,
    get_change,
    load_json_data,
)

# ── Estilos de tabs ───────────────────────────────────────────────────────────

_TAB_STYLE = {
    "backgroundColor": "transparent",
    "color": COLORS["text_muted"],
    "border": "none",
    "borderBottom": "2px solid transparent",
    "padding": "10px 18px",
    "fontSize": "0.82rem",
    "fontWeight": "500",
}
_TAB_SELECTED = {
    **_TAB_STYLE,
    "color": COLORS["text"],
    "borderBottom": f"2px solid {COLORS['accent']}",
    "fontWeight": "600",
}
_TABS_CONTAINER = {
    "borderBottom": f"1px solid {COLORS['border']}",
    "backgroundColor": COLORS["card_bg"],
}

# ── Constantes ─────────────────────────────────────────────────────────────────

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Colores nivel semáforo
_LEVEL_COLOR = {
    "green":       "#10b981",
    "yellow_green": "#84cc16",
    "yellow":      "#f59e0b",
    "orange":      "#f97316",
    "red":         "#ef4444",
    "gray":        "#6b7280",
}

_LEVEL_LABEL = {
    "green":        "NORMAL",
    "yellow_green": "ATENCIÓN",
    "yellow":       "ALERTA",
    "orange":       "ALERTA",
    "red":          "CRÍTICO",
    "gray":         "SIN DATOS",
}


def _rgba(hex_color: str, alpha: float = 0.12) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def _safe(val, fmt=".2f", suffix="", none_str="—"):
    if val is None:
        return none_str
    try:
        return f"{float(val):{fmt}}{suffix}"
    except Exception:
        return none_str


def _semaphore_card(title: str, value_str: str, level: str, subtitle: str = "") -> html.Div:
    color = _LEVEL_COLOR.get(level, "#6b7280")
    label = _LEVEL_LABEL.get(level, "—")
    return html.Div(
        [
            html.Div(title, style={"fontSize": "0.7rem", "color": "#9ca3af", "textTransform": "uppercase", "letterSpacing": "0.05em"}),
            html.Div(
                [
                    html.Div(
                        style={"width": "10px", "height": "10px", "borderRadius": "50%",
                               "backgroundColor": color, "boxShadow": f"0 0 6px {color}", "flexShrink": "0"},
                    ),
                    html.Span(value_str, style={"fontSize": "1.5rem", "fontWeight": "700", "color": color, "marginLeft": "8px"}),
                ],
                style={"display": "flex", "alignItems": "center", "margin": "4px 0"},
            ),
            html.Div(
                label,
                style={"fontSize": "0.68rem", "color": color, "fontWeight": "600",
                       "background": _rgba(color, 0.15), "borderRadius": "4px",
                       "padding": "1px 6px", "display": "inline-block"},
            ),
            html.Div(subtitle, style={"fontSize": "0.68rem", "color": "#6b7280", "marginTop": "2px"}) if subtitle else None,
        ],
        style={
            "background": "#111827", "border": f"1px solid {_rgba(color, 0.3)}",
            "borderRadius": "8px", "padding": "12px 14px", "flex": "1",
        },
    )


def _status_badge(level: str) -> html.Span:
    color = _LEVEL_COLOR.get(level, "#6b7280")
    label = _LEVEL_LABEL.get(level, "—")
    return html.Span(
        label,
        style={
            "background": _rgba(color, 0.18),
            "color": color,
            "border": f"1px solid {_rgba(color, 0.4)}",
            "borderRadius": "4px",
            "padding": "1px 7px",
            "fontSize": "0.7rem",
            "fontWeight": "600",
        },
    )


# ── Header ─────────────────────────────────────────────────────────────────────

def _build_header() -> html.Div:
    rec = calculate_recession_probability()
    fin = calculate_systemic_risk_index()
    inf = calculate_inflation_pressure()
    gpr_val, gpr_ts = get_latest_value("fred_gpr_gprc")
    gpr_level = "gray"
    if gpr_val is not None:
        if gpr_val < 100:   gpr_level = "green"
        elif gpr_val < 150: gpr_level = "yellow"
        elif gpr_val < 200: gpr_level = "orange"
        else:               gpr_level = "red"

    fin_level = fin.get("level", "gray")
    fin_idx   = fin.get("composite_index", fin.get("index", 0))

    ts_str = gpr_ts.strftime("%b %Y") if gpr_ts else "—"

    return html.Div(
        [
            html.Div(
                [
                    html.Div("Indicadores Adelantados y Señales de Alerta", className="module-title"),
                    html.Div(
                        "Síntesis prospectiva — ¿Qué anticipan los datos para los próximos 6-18 meses?",
                        className="module-subtitle",
                    ),
                ],
                style={"marginBottom": "16px"},
            ),
            # Fila de 4 semáforos
            html.Div(
                [
                    _semaphore_card(
                        "Riesgo Recesión (12m)",
                        f"{rec['probability']:.0f}%",
                        rec["level"],
                        subtitle=", ".join(
                            c["name"] for c in rec["components"] if c.get("alert")
                        )[:60] or "Sin alertas activas",
                    ),
                    _semaphore_card(
                        "Riesgo Crisis Financiera",
                        f"{fin_idx:.0f}/100",
                        fin_level,
                    ),
                    _semaphore_card(
                        "Presión Inflacionaria",
                        f"{inf['index']:.0f}/100",
                        inf["level"],
                    ),
                    _semaphore_card(
                        "Riesgo Geopolítico (GPR)",
                        _safe(gpr_val, ".0f"),
                        gpr_level,
                        subtitle=f"Actualizado: {ts_str}",
                    ),
                ],
                id="m11-header-semaphores",
                style={"display": "flex", "gap": "12px", "flexWrap": "wrap"},
            ),
            # Botón recalcular
            html.Div(
                [
                    html.Button(
                        "↺ Recalcular ahora",
                        id="m11-recalculate-btn",
                        style={
                            "background": "transparent", "border": f"1px solid {C['primary']}",
                            "color": C["primary"], "borderRadius": "6px", "padding": "5px 14px",
                            "fontSize": "0.75rem", "cursor": "pointer", "marginTop": "10px",
                        },
                    ),
                    html.Span(id="m11-recalc-ts", style={"fontSize": "0.7rem", "color": "#6b7280", "marginLeft": "10px"}),
                ],
            ),
        ],
        style={"padding": "20px 24px 10px"},
    )


# ── Tab 1: Cuadro de Mando ──────────────────────────────────────────────────────

def _build_dashboard_table() -> html.Div:
    """Tabla de indicadores con estado actual."""
    rows_html = []

    def _row(group: str, name: str, series_id: str, value_fn=None, level_fn=None,
              threshold: str = "", last_alert: str = "—", bold_group: bool = False) -> list:
        if bold_group:
            rows_html.append(
                html.Tr(
                    html.Td(
                        group,
                        colSpan=6,
                        style={
                            "background": "#1f2937", "color": "#9ca3af", "fontSize": "0.68rem",
                            "textTransform": "uppercase", "letterSpacing": "0.08em",
                            "padding": "6px 12px", "fontWeight": "600",
                        },
                    )
                )
            )
            return

        val_str = "—"
        level = "gray"
        try:
            if value_fn:
                val_str, level = value_fn()
            else:
                v, _ = get_latest_value(series_id)
                val_str = _safe(v, ".2f") if v is not None else "—"
                if level_fn and v is not None:
                    level = level_fn(v)
        except Exception:
            pass

        bg = _rgba(_LEVEL_COLOR.get(level, "#6b7280"), 0.06) if level in ("orange", "red") else "transparent"
        rows_html.append(
            html.Tr(
                [
                    html.Td(name, style={"padding": "6px 12px", "fontSize": "0.78rem", "color": "#e5e7eb"}),
                    html.Td(val_str, style={"padding": "6px 12px", "fontSize": "0.78rem",
                                            "color": _LEVEL_COLOR.get(level, "#9ca3af"), "fontWeight": "600"}),
                    html.Td(_status_badge(level), style={"padding": "4px 12px"}),
                    html.Td(threshold, style={"padding": "6px 12px", "fontSize": "0.72rem", "color": "#6b7280"}),
                    html.Td(last_alert, style={"padding": "6px 12px", "fontSize": "0.72rem", "color": "#6b7280"}),
                ],
                style={"background": bg, "borderBottom": "1px solid #1f2937"},
            )
        )

    # ── Curva de Tipos ──
    _row("CURVA DE TIPOS (6-18 meses adelanto)", None, None, bold_group=True)

    def _t10y2y():
        v, _ = get_latest_value("fred_t10y2y_us")
        if v is None: return "—", "gray"
        lvl = "red" if v < -0.5 else ("orange" if v < 0 else ("yellow" if v < 0.5 else "green"))
        return f"{v:.2f}%", lvl
    _row("", "Spread 10Y-2Y EE.UU.", "fred_t10y2y_us", value_fn=_t10y2y, threshold="< 0% = invertida")

    def _t10y3m():
        v, _ = get_latest_value("fred_t10y3m_us")
        if v is None: return "—", "gray"
        lvl = "red" if v < -0.5 else ("orange" if v < 0 else ("yellow" if v < 0.5 else "green"))
        return f"{v:.2f}%", lvl
    _row("", "Spread 10Y-3M EE.UU.", "fred_t10y3m_us", value_fn=_t10y3m, threshold="< 0% = invertida")

    # ── Mercado Laboral ──
    _row("MERCADO LABORAL", None, None, bold_group=True)

    def _sahm():
        v, lvl, _ = calculate_sahm_indicator()
        if v is None: return "—", "gray"
        return f"{v:.2f}", lvl or "green"
    _row("", "Regla de Sahm", "", value_fn=_sahm, threshold=">= 0.5 = recesión")

    def _icsa():
        df = get_series("fred_jobless_claims_us", days=40)
        if df.empty or len(df) < 4: return "—", "gray"
        avg4 = float(df.tail(4)["value"].mean())
        lvl = "red" if avg4 > 300000 else ("orange" if avg4 > 250000 else ("yellow" if avg4 > 220000 else "green"))
        return f"{avg4:,.0f}", lvl
    _row("", "Solicitudes desempleo (media 4s)", "fred_jobless_claims_us", value_fn=_icsa, threshold="> 250k alerta")

    # ── Actividad ──
    _row("ACTIVIDAD ECONÓMICA", None, None, bold_group=True)

    def _lei():
        df = get_series("fred_lei_us", days=210)
        if df.empty or len(df) < 6: return "—", "gray"
        df = df.sort_values("timestamp")
        cur = float(df.iloc[-1]["value"])
        prev6 = float(df.iloc[-6]["value"])
        if prev6 == 0: return "—", "gray"
        chg = (cur - prev6) / abs(prev6) * 100
        lvl = "red" if chg < -4 else ("orange" if chg < -2 else ("yellow" if chg < 0 else "green"))
        return f"{chg:+.1f}% (6m)", lvl
    _row("", "LEI Conference Board (6m)", "fred_lei_us", value_fn=_lei, threshold="< -4% = alerta")

    def _permit():
        v_cur, v_prev, _, pct = get_change("fred_building_permits_us", period_days=365)
        if pct is None: return "—", "gray"
        lvl = "red" if pct < -20 else ("orange" if pct < -10 else ("yellow" if pct < 0 else "green"))
        return f"{pct:+.1f}% YoY", lvl
    _row("", "Permisos de construcción (YoY)", "fred_building_permits_us", value_fn=_permit, threshold="< -15% alerta")

    def _busloans():
        v_cur, v_prev, _, pct = get_change("fred_business_loans_us", period_days=365)
        if pct is None: return "—", "gray"
        lvl = "red" if pct < -5 else ("orange" if pct < 0 else "green")
        return f"{pct:+.1f}% YoY", lvl
    _row("", "Crédito empresarial (YoY)", "fred_business_loans_us", value_fn=_busloans, threshold="< 0% = contracción")

    # ── Sistema Financiero ──
    _row("SISTEMA FINANCIERO", None, None, bold_group=True)

    def _stlfsi():
        v, _ = get_latest_value("fred_financial_stress_us")
        if v is None: return "—", "gray"
        lvl = "red" if v > 2 else ("orange" if v > 1 else ("yellow" if v > 0 else "green"))
        return f"{v:.2f}", lvl
    _row("", "STLFSI4 (estrés financiero Fed)", "fred_financial_stress_us", value_fn=_stlfsi, threshold="> 1 alerta, > 2 crítico")

    def _vix():
        v, _ = get_latest_value("yf_vix_close")
        if v is None: return "—", "gray"
        lvl = "red" if v > 35 else ("orange" if v > 25 else ("yellow" if v > 18 else "green"))
        return f"{v:.1f}", lvl
    _row("", "VIX", "yf_vix_close", value_fn=_vix, threshold="> 25 alerta, > 35 crítico")

    # ── Inflación ──
    _row("INFLACIÓN", None, None, bold_group=True)

    def _t5yie():
        v, _ = get_latest_value("fred_inflation_exp_5y_us")
        if v is None: return "—", "gray"
        lvl = "red" if v > 3 else ("orange" if v > 2.5 else ("yellow" if v > 2.3 else "green"))
        return f"{v:.2f}%", lvl
    _row("", "Expectativas inflación 5Y (T5YIE)", "fred_inflation_exp_5y_us", value_fn=_t5yie, threshold="> 3% desancladas")

    def _wages():
        v_cur, v_prev, _, pct = get_change("fred_wages_us", period_days=365)
        if pct is None: return "—", "gray"
        lvl = "red" if pct > 5 else ("orange" if pct > 4.5 else ("yellow" if pct > 4 else "green"))
        return f"{pct:+.1f}% YoY", lvl
    _row("", "Crecimiento salarial (YoY)", "fred_wages_us", value_fn=_wages, threshold="> 5% presión inflacionaria")

    # ── Geopolítico ──
    _row("GEOPOLÍTICO", None, None, bold_group=True)

    def _gpr():
        v, _ = get_latest_value("fred_gpr_gprc")
        if v is None: return "—", "gray"
        lvl = "green" if v < 100 else ("yellow" if v < 150 else ("orange" if v < 200 else "red"))
        return f"{v:.0f}", lvl
    _row("", "GPR Global", "fred_gpr_gprc", value_fn=_gpr, threshold="> 150 alerta, > 200 crítico")

    def _brent():
        v, _ = get_latest_value("yf_bz_close")
        if v is None: return "—", "gray"
        lvl = "red" if v > 130 else ("orange" if v > 100 else ("yellow" if v > 85 else "green"))
        return f"${v:.1f}", lvl
    _row("", "Brent Crude", "yf_bz_close", value_fn=_brent, threshold="> $100 alerta, > $130 crítico")

    return html.Div(
        [
            html.Table(
                [
                    html.Thead(
                        html.Tr([
                            html.Th("Indicador", style={"padding": "8px 12px", "color": "#9ca3af", "fontSize": "0.72rem", "fontWeight": "600"}),
                            html.Th("Valor Actual", style={"padding": "8px 12px", "color": "#9ca3af", "fontSize": "0.72rem", "fontWeight": "600"}),
                            html.Th("Estado", style={"padding": "8px 12px", "color": "#9ca3af", "fontSize": "0.72rem", "fontWeight": "600"}),
                            html.Th("Umbral de Alerta", style={"padding": "8px 12px", "color": "#9ca3af", "fontSize": "0.72rem", "fontWeight": "600"}),
                            html.Th("Última alerta", style={"padding": "8px 12px", "color": "#9ca3af", "fontSize": "0.72rem", "fontWeight": "600"}),
                        ]),
                        style={"borderBottom": "1px solid #374151"},
                    ),
                    html.Tbody(rows_html),
                ],
                style={"width": "100%", "borderCollapse": "collapse"},
            ),
        ],
        style={"overflowX": "auto", "background": "#0d1117", "borderRadius": "8px",
               "border": "1px solid #1f2937"},
    )


def _build_tab1() -> html.Div:
    summary = generate_indicator_summary()
    history_df = get_indicator_history_for_dashboard(weeks=24)

    fig_hist = go.Figure()
    if not history_df.empty:
        fig_hist.add_trace(go.Scatter(
            x=history_df["semana"], y=history_df["n_normal"],
            name="Normal", stackgroup="one", fill="tonexty",
            line={"color": "#10b981", "width": 0}, fillcolor=_rgba("#10b981", 0.5),
        ))
        fig_hist.add_trace(go.Scatter(
            x=history_df["semana"], y=history_df["n_attention"],
            name="Atención", stackgroup="one", fill="tonexty",
            line={"color": "#f59e0b", "width": 0}, fillcolor=_rgba("#f59e0b", 0.6),
        ))
        fig_hist.add_trace(go.Scatter(
            x=history_df["semana"], y=history_df["n_alert"],
            name="Alerta", stackgroup="one", fill="tonexty",
            line={"color": "#f97316", "width": 0}, fillcolor=_rgba("#f97316", 0.7),
        ))
        fig_hist.add_trace(go.Scatter(
            x=history_df["semana"], y=history_df["n_critical"],
            name="Crítico", stackgroup="one", fill="tonexty",
            line={"color": "#ef4444", "width": 0}, fillcolor=_rgba("#ef4444", 0.8),
        ))
    layout_hist = get_base_layout("Evolución del cuadro de mando (últimas 24 semanas)", height=220)
    layout_hist["yaxis"]["title"] = {"text": "Nº indicadores", "font": {"color": "#9ca3af", "size": 11}}
    fig_hist.update_layout(**layout_hist)

    return html.Div(
        [
            html.H6("1.1 — Cuadro de Mando de Indicadores", style={"color": "#9ca3af", "fontSize": "0.8rem", "marginBottom": "10px"}),
            _build_dashboard_table(),
            html.H6("1.2 — Resumen Narrativo", style={"color": "#9ca3af", "fontSize": "0.8rem", "margin": "18px 0 8px"}),
            html.Div(
                summary["text"],
                style={
                    "background": "#111827", "border": "1px solid #1f2937",
                    "borderRadius": "8px", "padding": "14px 16px",
                    "fontSize": "0.82rem", "color": "#d1d5db", "lineHeight": "1.6",
                },
            ),
            html.H6("1.3 — Evolución del Cuadro de Mando", style={"color": "#9ca3af", "fontSize": "0.8rem", "margin": "18px 0 8px"}),
            dcc.Graph(figure=fig_hist, config={"displayModeBar": False}),
        ],
        style={"padding": "16px"},
    )


# ── Tab 2: Indicadores de Recesión ──────────────────────────────────────────────

def _build_tab2() -> html.Div:
    # 2.1 Curva 10Y-2Y histórica
    df_spread = get_series("fred_t10y2y_us", days=365 * 50)
    fig_spread = go.Figure()
    if not df_spread.empty:
        pos = df_spread[df_spread["value"] >= 0]
        neg = df_spread[df_spread["value"] < 0]
        fig_spread.add_trace(go.Scatter(
            x=df_spread["timestamp"], y=df_spread["value"],
            name="10Y-2Y", line={"color": C["primary"], "width": 1.5},
        ))
        if not neg.empty:
            fig_spread.add_trace(go.Scatter(
                x=neg["timestamp"], y=neg["value"],
                name="Invertida", fill="tozeroy",
                fillcolor=_rgba("#ef4444", 0.25), line={"color": "#ef4444", "width": 0},
            ))
        fig_spread.add_hline(y=0, line_dash="dash", line_color="#6b7280", line_width=1)

    layout_s = get_base_layout("Spread 10Y-2Y EE.UU. (histórico)", height=300)
    layout_s["yaxis"]["ticksuffix"] = "%"
    layout_s["xaxis"]["rangeselector"] = get_time_range_buttons()
    fig_spread.update_layout(**layout_s)

    # Tabla historial inversiones
    inversion_history = [
        {"periodo": "1978–1980", "inicio": "Ago 1978", "fin": "Mar 1980", "dias": 593, "recesion": "1980", "adelanto_m": 6},
        {"periodo": "1980–1981", "inicio": "Oct 1980", "fin": "Ene 1981", "dias": 112, "recesion": "1981", "adelanto_m": 12},
        {"periodo": "1988–1990", "inicio": "Feb 1988", "fin": "Nov 1988", "dias": 287, "recesion": "1990", "adelanto_m": 18},
        {"periodo": "2000–2001", "inicio": "Mar 2000", "fin": "May 2000", "dias": 95, "recesion": "2001", "adelanto_m": 14},
        {"periodo": "2006–2007", "inicio": "Ene 2006", "fin": "Jun 2007", "dias": 459, "recesion": "2008", "adelanto_m": 24},
        {"periodo": "2022–2024", "inicio": "Abr 2022", "fin": "¿?", "dias": "700+", "recesion": "¿?", "adelanto_m": "—"},
    ]

    inversion_rows = [
        html.Tr([
            html.Td(r["periodo"], style={"padding": "6px 12px", "fontSize": "0.78rem"}),
            html.Td(r["inicio"],  style={"padding": "6px 12px", "fontSize": "0.78rem", "color": "#9ca3af"}),
            html.Td(r["fin"],     style={"padding": "6px 12px", "fontSize": "0.78rem", "color": "#9ca3af"}),
            html.Td(str(r["dias"]), style={"padding": "6px 12px", "fontSize": "0.78rem"}),
            html.Td(str(r["recesion"]), style={"padding": "6px 12px", "fontSize": "0.78rem", "color": "#ef4444"}),
            html.Td(
                f"{r['adelanto_m']} meses" if isinstance(r["adelanto_m"], int) else str(r["adelanto_m"]),
                style={"padding": "6px 12px", "fontSize": "0.78rem", "color": "#f59e0b"},
            ),
        ], style={"borderBottom": "1px solid #1f2937"})
        for r in inversion_history
    ]

    # 2.2 Sahm
    sahm_val, sahm_lvl, df_sahm = calculate_sahm_indicator()
    fig_sahm = go.Figure()
    if not df_sahm.empty:
        fig_sahm.add_trace(go.Scatter(
            x=df_sahm["timestamp"], y=df_sahm["sahm"],
            name="Sahm", line={"color": C["primary"], "width": 1.5},
        ))
        recession = df_sahm[df_sahm["sahm"] >= 0.5]
        if not recession.empty:
            fig_sahm.add_trace(go.Scatter(
                x=recession["timestamp"], y=recession["sahm"],
                name="Recesión activa", fill="tozeroy",
                fillcolor=_rgba("#ef4444", 0.25), line={"color": "#ef4444", "width": 0},
            ))
        fig_sahm.add_hline(y=0.5, line_dash="dash", line_color="#ef4444", line_width=1,
                           annotation_text="0.5 = Recesión", annotation_font_color="#ef4444",
                           annotation_font_size=10)
        fig_sahm.add_hline(y=0.3, line_dash="dot", line_color="#f97316", line_width=1)

    layout_sahm = get_base_layout(f"Regla de Sahm (actual: {_safe(sahm_val, '.2f')})", height=260)
    layout_sahm["xaxis"]["rangeselector"] = get_time_range_buttons()
    fig_sahm.update_layout(**layout_sahm)

    # 2.3 LEI
    df_lei = get_series("fred_lei_us", days=365 * 10)
    fig_lei = go.Figure()
    if not df_lei.empty:
        fig_lei.add_trace(go.Scatter(
            x=df_lei["timestamp"], y=df_lei["value"],
            name="LEI", line={"color": "#84cc16", "width": 1.5},
        ))
    layout_lei = get_base_layout("LEI Conference Board (nivel)", height=240)
    layout_lei["xaxis"]["rangeselector"] = get_time_range_buttons()
    fig_lei.update_layout(**layout_lei)

    # 2.4 Gauge recesión
    rec = calculate_recession_probability()
    rec_prob = rec["probability"]
    rec_color = _LEVEL_COLOR.get(rec["level"], "#6b7280")

    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number",
        value=rec_prob,
        number={"suffix": "%", "font": {"size": 28, "color": rec_color}},
        gauge={
            "axis": {"range": [0, 100], "tickcolor": "#6b7280", "tickfont": {"color": "#9ca3af", "size": 10}},
            "bar": {"color": rec_color},
            "bgcolor": "#111827",
            "steps": [
                {"range": [0, 15],  "color": _rgba("#10b981", 0.2)},
                {"range": [15, 30], "color": _rgba("#84cc16", 0.2)},
                {"range": [30, 50], "color": _rgba("#f59e0b", 0.2)},
                {"range": [50, 70], "color": _rgba("#f97316", 0.2)},
                {"range": [70, 100],"color": _rgba("#ef4444", 0.2)},
            ],
            "threshold": {"line": {"color": rec_color, "width": 2}, "thickness": 0.75, "value": rec_prob},
        },
        title={"text": "Probabilidad de Recesión (12m)", "font": {"color": "#9ca3af", "size": 12}},
    ))
    fig_gauge.update_layout(
        paper_bgcolor="#0a0e1a", plot_bgcolor="#0a0e1a", height=260,
        font={"color": "#e5e7eb"}, margin={"l": 20, "r": 20, "t": 40, "b": 10},
    )

    component_rows = [
        html.Tr([
            html.Td(c["name"], style={"padding": "5px 10px", "fontSize": "0.78rem"}),
            html.Td(c["value"], style={"padding": "5px 10px", "fontSize": "0.78rem", "color": "#9ca3af"}),
            html.Td(
                f"+{c['contribution']} pts",
                style={"padding": "5px 10px", "fontSize": "0.78rem",
                       "color": "#ef4444" if c.get("alert") else "#6b7280"},
            ),
        ], style={"borderBottom": "1px solid #1f2937"})
        for c in rec["components"]
    ]

    # 2.5 Cuatro gráficos
    def _mini_chart(series_id, title, threshold_y=None, color="#3b82f6"):
        df = get_series(series_id, days=365 * 5)
        fig = go.Figure()
        if not df.empty:
            fig.add_trace(go.Scatter(x=df["timestamp"], y=df["value"],
                                     line={"color": color, "width": 1.5}, name=title))
            if threshold_y is not None:
                fig.add_hline(y=threshold_y, line_dash="dash", line_color="#6b7280", line_width=1)
        lyt = get_base_layout(title, height=220)
        lyt["xaxis"]["rangeselector"] = get_time_range_buttons()
        fig.update_layout(**lyt)
        return dcc.Graph(figure=fig, config={"displayModeBar": False})

    return html.Div(
        [
            # 2.1
            html.H6("2.1 — Curva de Tipos: El Indicador Más Fiable de la Historia",
                    style={"color": "#9ca3af", "fontSize": "0.8rem", "marginBottom": "8px"}),
            dcc.Graph(figure=fig_spread, config={"displayModeBar": False}),
            html.Div(
                [
                    "La curva 10Y-2Y ha predicho ",
                    html.Strong("todas las recesiones americanas"),
                    " de los últimos 50 años, con adelanto de 6-24 meses. Sin embargo, el período varía ampliamente — lo que puede generar impaciencia o falsas alarmas.",
                ],
                style={"fontSize": "0.78rem", "color": "#9ca3af", "margin": "8px 0 14px",
                       "background": "#111827", "borderRadius": "6px", "padding": "10px 14px",
                       "border": "1px solid #1f2937"},
            ),
            html.Div(
                html.Table(
                    [
                        html.Thead(html.Tr([
                            html.Th("Período", style={"padding": "6px 12px", "color": "#9ca3af", "fontSize": "0.72rem"}),
                            html.Th("Inicio", style={"padding": "6px 12px", "color": "#9ca3af", "fontSize": "0.72rem"}),
                            html.Th("Fin", style={"padding": "6px 12px", "color": "#9ca3af", "fontSize": "0.72rem"}),
                            html.Th("Días", style={"padding": "6px 12px", "color": "#9ca3af", "fontSize": "0.72rem"}),
                            html.Th("Recesión", style={"padding": "6px 12px", "color": "#9ca3af", "fontSize": "0.72rem"}),
                            html.Th("Adelanto", style={"padding": "6px 12px", "color": "#9ca3af", "fontSize": "0.72rem"}),
                        ]), style={"borderBottom": "1px solid #374151"}),
                        html.Tbody(inversion_rows),
                    ],
                    style={"width": "100%", "borderCollapse": "collapse"},
                ),
                style={"background": "#0d1117", "borderRadius": "8px", "border": "1px solid #1f2937",
                       "overflowX": "auto", "marginBottom": "18px"},
            ),

            # 2.2
            html.H6("2.2 — Regla de Sahm",
                    style={"color": "#9ca3af", "fontSize": "0.8rem", "marginBottom": "8px"}),
            dcc.Graph(figure=fig_sahm, config={"displayModeBar": False}),

            # 2.3
            html.H6("2.3 — LEI Conference Board",
                    style={"color": "#9ca3af", "fontSize": "0.8rem", "margin": "16px 0 8px"}),
            dcc.Graph(figure=fig_lei, config={"displayModeBar": False}),

            # 2.4
            html.H6("2.4 — Probabilidad de Recesión (Modelo Propio)",
                    style={"color": "#9ca3af", "fontSize": "0.8rem", "margin": "16px 0 8px"}),
            dbc.Row(
                [
                    dbc.Col(dcc.Graph(figure=fig_gauge, config={"displayModeBar": False}), width=5),
                    dbc.Col(
                        html.Div(
                            [
                                html.Div("Desglose de componentes",
                                         style={"fontSize": "0.75rem", "color": "#9ca3af", "marginBottom": "8px"}),
                                html.Table(
                                    [
                                        html.Thead(html.Tr([
                                            html.Th("Indicador", style={"padding": "5px 10px", "color": "#9ca3af", "fontSize": "0.7rem"}),
                                            html.Th("Valor", style={"padding": "5px 10px", "color": "#9ca3af", "fontSize": "0.7rem"}),
                                            html.Th("Pts", style={"padding": "5px 10px", "color": "#9ca3af", "fontSize": "0.7rem"}),
                                        ]), style={"borderBottom": "1px solid #374151"}),
                                        html.Tbody(component_rows),
                                    ],
                                    style={"width": "100%", "borderCollapse": "collapse"},
                                ),
                                html.Div(
                                    rec["interpretation"],
                                    style={"fontSize": "0.78rem", "color": "#d1d5db",
                                           "marginTop": "10px", "lineHeight": "1.5"},
                                ),
                            ],
                            style={"background": "#111827", "borderRadius": "8px",
                                   "border": "1px solid #1f2937", "padding": "12px"},
                        ),
                        width=7,
                    ),
                ],
                className="g-3",
            ),

            # 2.5
            html.H6("2.5 — Otros Indicadores Adelantados",
                    style={"color": "#9ca3af", "fontSize": "0.8rem", "margin": "18px 0 8px"}),
            dbc.Row(
                [
                    dbc.Col(_mini_chart("fred_building_permits_us", "Permisos Construcción", color="#84cc16"), width=6),
                    dbc.Col(_mini_chart("fred_jobless_claims_us", "Solicitudes Desempleo", threshold_y=300000, color="#f97316"), width=6),
                ],
                className="g-3 mb-3",
            ),
            dbc.Row(
                [
                    dbc.Col(_mini_chart("fred_business_loans_us", "Crédito Empresarial (nivel)", color="#3b82f6"), width=6),
                    dbc.Col(_mini_chart("fred_lei_us", "LEI Conference Board", color="#84cc16"), width=6),
                ],
                className="g-3",
            ),
        ],
        style={"padding": "16px"},
    )


# ── Tab 3: Crisis Financiera ────────────────────────────────────────────────────

def _build_tab3() -> html.Div:
    fin = calculate_systemic_risk_index()
    fin_level = fin.get("level", "gray")
    fin_idx   = fin.get("composite_index", fin.get("index", 0) or 0)
    fin_color = _LEVEL_COLOR.get(fin_level, "#6b7280")

    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number",
        value=float(fin_idx),
        number={"suffix": "/100", "font": {"size": 28, "color": fin_color}},
        gauge={
            "axis": {"range": [0, 100], "tickfont": {"color": "#9ca3af", "size": 10}},
            "bar": {"color": fin_color},
            "bgcolor": "#111827",
            "steps": [
                {"range": [0, 25],  "color": _rgba("#10b981", 0.2)},
                {"range": [25, 50], "color": _rgba("#84cc16", 0.2)},
                {"range": [50, 65], "color": _rgba("#f59e0b", 0.2)},
                {"range": [65, 80], "color": _rgba("#f97316", 0.2)},
                {"range": [80, 100],"color": _rgba("#ef4444", 0.2)},
            ],
        },
        title={"text": "Índice Riesgo Sistémico", "font": {"color": "#9ca3af", "size": 12}},
    ))
    fig_gauge.update_layout(
        paper_bgcolor="#0a0e1a", plot_bgcolor="#0a0e1a", height=260,
        font={"color": "#e5e7eb"}, margin={"l": 20, "r": 20, "t": 40, "b": 10},
    )

    # Componentes
    comp_rows = []
    for k, v in fin.get("components", {}).items():
        comp_rows.append(html.Tr([
            html.Td(k, style={"padding": "5px 10px", "fontSize": "0.78rem"}),
            html.Td(f"{v:.1f}/100" if isinstance(v, float) else str(v),
                    style={"padding": "5px 10px", "fontSize": "0.78rem", "color": "#9ca3af"}),
        ], style={"borderBottom": "1px solid #1f2937"}))

    # VIX histórico
    df_vix = get_series("yf_vix_close", days=365 * 5)
    fig_vix = go.Figure()
    if not df_vix.empty:
        fig_vix.add_trace(go.Scatter(
            x=df_vix["timestamp"], y=df_vix["value"],
            line={"color": "#f97316", "width": 1.5}, name="VIX",
        ))
        above35 = df_vix[df_vix["value"] > 35]
        if not above35.empty:
            fig_vix.add_trace(go.Scatter(
                x=above35["timestamp"], y=above35["value"],
                fill="tozeroy", fillcolor=_rgba("#ef4444", 0.2),
                line={"color": "#ef4444", "width": 0}, name="Crisis",
            ))
        fig_vix.add_hline(y=25, line_dash="dash", line_color="#f59e0b", line_width=1,
                          annotation_text="25", annotation_font_color="#f59e0b", annotation_font_size=10)
        fig_vix.add_hline(y=35, line_dash="dash", line_color="#ef4444", line_width=1,
                          annotation_text="35", annotation_font_color="#ef4444", annotation_font_size=10)
    lyt_vix = get_base_layout("VIX — Volatilidad S&P 500", height=240)
    lyt_vix["xaxis"]["rangeselector"] = get_time_range_buttons()
    fig_vix.update_layout(**lyt_vix)

    # MOVE Index
    df_move = get_series("yf_move_close", days=365 * 5)
    fig_move = go.Figure()
    if not df_move.empty:
        fig_move.add_trace(go.Scatter(
            x=df_move["timestamp"], y=df_move["value"],
            line={"color": "#8b5cf6", "width": 1.5}, name="MOVE",
        ))
    lyt_move = get_base_layout("MOVE Index — Volatilidad de Bonos", height=240)
    lyt_move["xaxis"]["rangeselector"] = get_time_range_buttons()
    fig_move.update_layout(**lyt_move)

    # Condiciones Financieras (índice simplificado)
    t10y2y_v, _ = get_latest_value("fred_t10y2y_us")
    vix_v, _    = get_latest_value("yf_vix_close")
    dxy_v, _    = get_latest_value("yf_dxy_close")
    _, _, _, sp_pct = get_change("yf_sp500_close", period_days=90)

    fc_components = []
    fc_score = 50.0  # neutral
    if vix_v is not None:
        vix_comp = max(0, min(100, 100 - (vix_v - 10) / 0.7))
        fc_score += (vix_comp - 50) * 0.25
        fc_components.append(f"VIX: {vix_v:.1f}")
    if t10y2y_v is not None:
        t_comp = 70 if t10y2y_v > 0 else 30
        fc_score += (t_comp - 50) * 0.2
    if sp_pct is not None:
        sp_comp = 70 if sp_pct > 0 else 30
        fc_score += (sp_comp - 50) * 0.2
    fc_score = max(0, min(100, fc_score))

    fc_label = (
        "muy restrictivas" if fc_score < 25 else
        "restrictivas" if fc_score < 40 else
        "neutras" if fc_score < 60 else
        "acomodaticias" if fc_score < 80 else
        "muy acomodaticias"
    )

    return html.Div(
        [
            html.H6("3.1 — Semáforo de Crisis Financiera",
                    style={"color": "#9ca3af", "fontSize": "0.8rem", "marginBottom": "8px"}),
            dbc.Row(
                [
                    dbc.Col(dcc.Graph(figure=fig_gauge, config={"displayModeBar": False}), width=5),
                    dbc.Col(
                        html.Div(
                            [
                                html.Div("Componentes del índice",
                                         style={"fontSize": "0.75rem", "color": "#9ca3af", "marginBottom": "8px"}),
                                html.Table(
                                    [html.Tbody(comp_rows)] if comp_rows else [html.Tbody([html.Tr([html.Td("Sin datos", style={"padding": "8px", "color": "#6b7280"})])])],
                                    style={"width": "100%", "borderCollapse": "collapse"},
                                ),
                            ],
                            style={"background": "#111827", "borderRadius": "8px",
                                   "border": "1px solid #1f2937", "padding": "12px"},
                        ),
                        width=7,
                    ),
                ],
                className="g-3 mb-4",
            ),

            html.H6("3.2 — VIX y MOVE: Termómetros de Volatilidad",
                    style={"color": "#9ca3af", "fontSize": "0.8rem", "marginBottom": "8px"}),
            dbc.Row(
                [
                    dbc.Col(dcc.Graph(figure=fig_vix, config={"displayModeBar": False}), width=6),
                    dbc.Col(dcc.Graph(figure=fig_move, config={"displayModeBar": False}), width=6),
                ],
                className="g-3 mb-4",
            ),

            html.H6("3.3 — Índice de Condiciones Financieras (simplificado)",
                    style={"color": "#9ca3af", "fontSize": "0.8rem", "marginBottom": "8px"}),
            html.Div(
                [
                    html.Div(
                        [
                            html.Span("Condiciones financieras actuales: ",
                                      style={"color": "#9ca3af", "fontSize": "0.82rem"}),
                            html.Span(fc_label.upper(),
                                      style={"color": _LEVEL_COLOR.get("orange" if fc_score < 40 else "green", "#10b981"),
                                             "fontWeight": "700", "fontSize": "0.9rem"}),
                            html.Span(f" ({fc_score:.0f}/100)",
                                      style={"color": "#9ca3af", "fontSize": "0.78rem"}),
                        ],
                        style={"marginBottom": "6px"},
                    ),
                    html.Div(
                        f"Las condiciones financieras son {fc_label}, lo que {'restringe' if fc_score < 40 else 'no restringe significativamente' if fc_score < 60 else 'estimula'} el acceso al crédito y el crecimiento económico.",
                        style={"fontSize": "0.78rem", "color": "#d1d5db"},
                    ),
                ],
                style={"background": "#111827", "borderRadius": "8px", "border": "1px solid #1f2937",
                       "padding": "14px 16px"},
            ),
        ],
        style={"padding": "16px"},
    )


# ── Tab 4: Inflación ────────────────────────────────────────────────────────────

def _build_tab4() -> html.Div:
    # 4.1 IPP vs IPC
    df_ppi = get_series("fred_ppi_us", days=365 * 10)
    df_cpi = get_series("fred_cpi_yoy_us", days=365 * 10)

    fig_ppi_cpi = go.Figure()
    if not df_ppi.empty:
        fig_ppi_cpi.add_trace(go.Scatter(
            x=df_ppi["timestamp"], y=df_ppi["value"],
            name="IPP (nivel)", line={"color": "#f97316", "width": 1.5},
        ))
    if not df_cpi.empty:
        fig_ppi_cpi.add_trace(go.Scatter(
            x=df_cpi["timestamp"], y=df_cpi["value"],
            name="IPC YoY", line={"color": "#3b82f6", "width": 1.5},
        ))
    lyt_pc = get_base_layout("IPP vs IPC — Presión Inflacionaria", height=260)
    lyt_pc["xaxis"]["rangeselector"] = get_time_range_buttons()
    fig_ppi_cpi.update_layout(**lyt_pc)

    # 4.2 Expectativas
    df_t5y  = get_series("fred_inflation_exp_5y_us",  days=365 * 10)
    df_t10y = get_series("fred_inflation_exp_10y_us", days=365 * 10)

    fig_exp = go.Figure()
    if not df_t5y.empty:
        fig_exp.add_trace(go.Scatter(
            x=df_t5y["timestamp"], y=df_t5y["value"],
            name="T5YIE (5 años)", line={"color": "#84cc16", "width": 1.5},
        ))
    if not df_t10y.empty:
        fig_exp.add_trace(go.Scatter(
            x=df_t10y["timestamp"], y=df_t10y["value"],
            name="T10YIE (10 años)", line={"color": "#3b82f6", "width": 1.5},
        ))
    fig_exp.add_hline(y=2, line_dash="dash", line_color="#10b981", line_width=1,
                      annotation_text="2% objetivo", annotation_font_color="#10b981", annotation_font_size=10)
    fig_exp.add_hline(y=3, line_dash="dash", line_color="#ef4444", line_width=1,
                      annotation_text="3% desanclaje", annotation_font_color="#ef4444", annotation_font_size=10)
    lyt_exp = get_base_layout("Expectativas de Inflación de Mercado", height=260)
    lyt_exp["xaxis"]["rangeselector"] = get_time_range_buttons()
    lyt_exp["yaxis"]["ticksuffix"] = "%"
    fig_exp.update_layout(**lyt_exp)

    # 4.3 Salarios vs IPC
    df_wages = get_series("fred_wages_us", days=365 * 10)
    fig_wage = go.Figure()
    if not df_wages.empty and not df_cpi.empty:
        fig_wage.add_trace(go.Scatter(
            x=df_wages["timestamp"], y=df_wages["value"],
            name="Salarios (nivel)", line={"color": "#f59e0b", "width": 1.5},
        ))
        fig_wage.add_trace(go.Scatter(
            x=df_cpi["timestamp"], y=df_cpi["value"],
            name="IPC YoY", line={"color": "#3b82f6", "width": 1.5},
        ))
    elif not df_wages.empty:
        fig_wage.add_trace(go.Scatter(
            x=df_wages["timestamp"], y=df_wages["value"],
            name="Salarios (nivel)", line={"color": "#f59e0b", "width": 1.5},
        ))
    lyt_w = get_base_layout("Crecimiento Salarial vs Inflación", height=260)
    lyt_w["xaxis"]["rangeselector"] = get_time_range_buttons()
    fig_wage.update_layout(**lyt_w)

    # 4.4 Commodities normalizados
    def _norm_series(series_id, days=400):
        df = get_series(series_id, days=days)
        if df.empty or len(df) < 2:
            return df
        base = float(df.iloc[0]["value"])
        if base == 0:
            return df
        df = df.copy()
        df["norm"] = df["value"] / base * 100
        return df

    fig_comm = go.Figure()
    commodity_map = [
        ("yf_bz_close",  "Brent",  "#f97316"),
        ("yf_hg_close",  "Cobre",  "#ef4444"),
        ("yf_zw_close",  "Trigo",  "#f59e0b"),
        ("yf_gc_close",  "Oro",    "#fbbf24"),
    ]
    for sid, name, color in commodity_map:
        df_c = _norm_series(sid, days=400)
        if not df_c.empty and "norm" in df_c.columns:
            fig_comm.add_trace(go.Scatter(
                x=df_c["timestamp"], y=df_c["norm"],
                name=name, line={"color": color, "width": 1.5},
            ))
    fig_comm.add_hline(y=100, line_dash="dash", line_color="#374151", line_width=1)
    lyt_comm = get_base_layout("Commodities — Base 100 (hace 12 meses)", height=260)
    lyt_comm["yaxis"]["ticksuffix"] = ""
    fig_comm.update_layout(**lyt_comm)

    # Gauge presión inflacionaria
    inf = calculate_inflation_pressure()
    inf_color = _LEVEL_COLOR.get(inf["level"], "#6b7280")
    fig_inf_gauge = go.Figure(go.Indicator(
        mode="gauge+number",
        value=inf["index"],
        number={"suffix": "/100", "font": {"size": 26, "color": inf_color}},
        gauge={
            "axis": {"range": [0, 100], "tickfont": {"color": "#9ca3af", "size": 10}},
            "bar": {"color": inf_color},
            "bgcolor": "#111827",
            "steps": [
                {"range": [0, 25],  "color": _rgba("#10b981", 0.2)},
                {"range": [25, 50], "color": _rgba("#f59e0b", 0.2)},
                {"range": [50, 75], "color": _rgba("#f97316", 0.2)},
                {"range": [75, 100],"color": _rgba("#ef4444", 0.2)},
            ],
        },
        title={"text": "Índice Presión Inflacionaria", "font": {"color": "#9ca3af", "size": 12}},
    ))
    fig_inf_gauge.update_layout(
        paper_bgcolor="#0a0e1a", plot_bgcolor="#0a0e1a", height=240,
        font={"color": "#e5e7eb"}, margin={"l": 20, "r": 20, "t": 40, "b": 10},
    )

    inf_comp_rows = [
        html.Tr([
            html.Td(c["name"], style={"padding": "5px 10px", "fontSize": "0.78rem"}),
            html.Td(c["value"], style={"padding": "5px 10px", "color": "#9ca3af", "fontSize": "0.78rem"}),
            html.Td(
                f"+{c['contribution']} pts",
                style={"padding": "5px 10px", "fontSize": "0.78rem",
                       "color": "#ef4444" if c.get("alert") else "#6b7280"},
            ),
        ], style={"borderBottom": "1px solid #1f2937"})
        for c in inf["components"]
    ]

    return html.Div(
        [
            html.H6("4.1 — IPP como Cristal Bola de la Inflación",
                    style={"color": "#9ca3af", "fontSize": "0.8rem", "marginBottom": "8px"}),
            dcc.Graph(figure=fig_ppi_cpi, config={"displayModeBar": False}),

            html.H6("4.2 — Expectativas de Inflación: El Indicador de la Fed",
                    style={"color": "#9ca3af", "fontSize": "0.8rem", "margin": "16px 0 8px"}),
            dcc.Graph(figure=fig_exp, config={"displayModeBar": False}),

            html.H6("4.3 — Crecimiento Salarial y Riesgo de Espiral",
                    style={"color": "#9ca3af", "fontSize": "0.8rem", "margin": "16px 0 8px"}),
            dcc.Graph(figure=fig_wage, config={"displayModeBar": False}),

            html.H6("4.4 — Commodities e Índice de Presión Inflacionaria",
                    style={"color": "#9ca3af", "fontSize": "0.8rem", "margin": "16px 0 8px"}),
            dbc.Row(
                [
                    dbc.Col(dcc.Graph(figure=fig_comm, config={"displayModeBar": False}), width=7),
                    dbc.Col(
                        [
                            dcc.Graph(figure=fig_inf_gauge, config={"displayModeBar": False}),
                            html.Table(
                                [html.Tbody(inf_comp_rows)] if inf_comp_rows else [],
                                style={"width": "100%", "borderCollapse": "collapse",
                                       "background": "#111827", "borderRadius": "6px"},
                            ),
                            html.Div(inf["interpretation"],
                                     style={"fontSize": "0.76rem", "color": "#9ca3af",
                                            "marginTop": "8px", "lineHeight": "1.5"}),
                        ],
                        width=5,
                    ),
                ],
                className="g-3",
            ),
        ],
        style={"padding": "16px"},
    )


# ── Tab 5: Historial de Señales ─────────────────────────────────────────────────

def _build_tab5() -> html.Div:
    track_record = load_json_data("indicator_track_record.json") or {"indicators": []}

    # Gráfico de barras — precisión
    indicators = track_record.get("indicators", [])
    if indicators:
        names = [i["name"] for i in indicators]
        accuracy = [
            round(i["true_positives"] / i["total_signals"] * 100, 0) if i["total_signals"] > 0 else 0
            for i in indicators
        ]
        # Ordenar de mayor a menor
        sorted_pairs = sorted(zip(accuracy, names), reverse=False)
        accuracy_s, names_s = zip(*sorted_pairs) if sorted_pairs else ([], [])

        fig_accuracy = go.Figure(go.Bar(
            y=list(names_s), x=list(accuracy_s),
            orientation="h",
            marker={"color": [
                "#10b981" if a >= 90 else "#f59e0b" if a >= 70 else "#ef4444"
                for a in accuracy_s
            ]},
            text=[f"{a:.0f}%" for a in accuracy_s],
            textposition="outside",
        ))
        lyt_acc = get_base_layout("Precisión Histórica por Indicador", height=320)
        lyt_acc["xaxis"] = {**lyt_acc.get("xaxis", {}), "range": [0, 110], "ticksuffix": "%"}
        lyt_acc["margin"] = {"l": 220, "r": 40, "t": 40, "b": 30}
        fig_accuracy.update_layout(**lyt_acc)
    else:
        fig_accuracy = go.Figure()
        fig_accuracy.update_layout(**get_base_layout("Precisión por Indicador", height=300))

    # Tabla de track record
    track_rows = [
        html.Tr([
            html.Td(i["name"], style={"padding": "7px 12px", "fontSize": "0.78rem"}),
            html.Td(
                f"{i['true_positives']}/{i['total_signals']} ({round(i['true_positives']/i['total_signals']*100) if i['total_signals']>0 else 0:.0f}%)",
                style={"padding": "7px 12px", "fontSize": "0.78rem",
                       "color": "#10b981" if i["total_signals"] > 0 and i["true_positives"]/i["total_signals"] >= 0.9 else "#f59e0b"},
            ),
            html.Td(
                f"{i['avg_lead_time_months']}m" if i["avg_lead_time_months"] > 0 else "Coincidente",
                style={"padding": "7px 12px", "fontSize": "0.78rem", "color": "#9ca3af"},
            ),
            html.Td(i["notes"], style={"padding": "7px 12px", "fontSize": "0.72rem", "color": "#9ca3af", "lineHeight": "1.4"}),
        ], style={"borderBottom": "1px solid #1f2937"})
        for i in indicators
    ]

    # Matriz de convergencia
    def _convergence_cell(n_alert, n_total):
        if n_total == 0:
            return html.Td("—", style={"padding": "8px 12px", "textAlign": "center", "color": "#6b7280", "fontSize": "0.78rem"})
        ratio = n_alert / n_total
        color = "#ef4444" if ratio >= 0.7 else "#f97316" if ratio >= 0.5 else "#f59e0b" if ratio >= 0.3 else "#10b981"
        return html.Td(
            f"{n_alert}/{n_total}",
            style={"padding": "8px 12px", "textAlign": "center", "fontSize": "0.82rem",
                   "fontWeight": "600", "color": color,
                   "background": _rgba(color, 0.1)},
        )

    # Leer valores para matrix
    t10y2y_v, _ = get_latest_value("fred_t10y2y_us")
    t10y3m_v, _ = get_latest_value("fred_t10y3m_us")
    sahm_v, _, _ = calculate_sahm_indicator()
    icsa_df = get_series("fred_jobless_claims_us", days=40)
    icsa_v = float(icsa_df.tail(4)["value"].mean()) if not icsa_df.empty and len(icsa_df) >= 4 else None

    hy_from_systemic = calculate_systemic_risk_index().get("components", {})
    stlfsi_v, _ = get_latest_value("fred_financial_stress_us")
    vix_v, _    = get_latest_value("yf_vix_close")

    t5yie_v, _  = get_latest_value("fred_inflation_exp_5y_us")
    _, _, _, wage_pct = get_change("fred_wages_us", period_days=365)
    _, _, _, brent_pct = get_change("yf_bz_close", period_days=365)

    # Contar alertas por cuadrante [recesion, financiero, inflacion]
    curve_r = sum([
        1 if (t10y2y_v is not None and t10y2y_v < 0) else 0,
        1 if (t10y3m_v is not None and t10y3m_v < 0) else 0,
    ])
    emp_r = sum([
        1 if (sahm_v is not None and sahm_v >= 0.5) else 0,
        1 if (icsa_v is not None and icsa_v > 250000) else 0,
    ])
    credit_r = sum([
        1 if (stlfsi_v is not None and stlfsi_v > 1) else 0,
        1 if (vix_v is not None and vix_v > 25) else 0,
    ])
    price_r = sum([
        1 if (t5yie_v is not None and t5yie_v > 2.5) else 0,
        1 if (wage_pct is not None and wage_pct > 4.5) else 0,
        1 if (brent_pct is not None and brent_pct > 15) else 0,
    ])

    matrix_data = [
        ("Curva / Ciclo",   curve_r, 2,  0, 2,  0, 2),
        ("Empleo",          emp_r,   2,  0, 2,  0, 2),
        ("Crédito / Mercado", credit_r, 2, credit_r, 2, 0, 2),
        ("Precios",         0,       2,  0, 2,  price_r, 3),
    ]

    matrix_rows = [
        html.Tr([
            html.Td(label, style={"padding": "8px 12px", "fontSize": "0.78rem", "fontWeight": "500"}),
            _convergence_cell(r_alert, r_total),
            _convergence_cell(f_alert, f_total),
            _convergence_cell(i_alert, i_total),
        ], style={"borderBottom": "1px solid #1f2937"})
        for label, r_alert, r_total, f_alert, f_total, i_alert, i_total in matrix_data
    ]

    return html.Div(
        [
            html.H6("5.1 — Eficacia Histórica de las Señales",
                    style={"color": "#9ca3af", "fontSize": "0.8rem", "marginBottom": "8px"}),
            dcc.Graph(figure=fig_accuracy, config={"displayModeBar": False}),
            html.Div(
                [
                    "Los indicadores con mayor precisión histórica son ",
                    html.Strong("la inversión de la curva de tipos"),
                    " y la ",
                    html.Strong("Regla de Sahm"),
                    ". Sin embargo, la curva anticipa (6-24 meses) y la Sahm confirma (0 meses) — juntos dan la visión más completa.",
                ],
                style={"fontSize": "0.78rem", "color": "#9ca3af", "margin": "8px 0 16px",
                       "background": "#111827", "borderRadius": "6px", "padding": "10px 14px",
                       "border": "1px solid #1f2937"},
            ),

            html.H6("5.2 — Detalle por Indicador",
                    style={"color": "#9ca3af", "fontSize": "0.8rem", "marginBottom": "8px"}),
            html.Div(
                html.Table(
                    [
                        html.Thead(html.Tr([
                            html.Th("Indicador", style={"padding": "7px 12px", "color": "#9ca3af", "fontSize": "0.72rem"}),
                            html.Th("Precisión", style={"padding": "7px 12px", "color": "#9ca3af", "fontSize": "0.72rem"}),
                            html.Th("Adelanto medio", style={"padding": "7px 12px", "color": "#9ca3af", "fontSize": "0.72rem"}),
                            html.Th("Notas", style={"padding": "7px 12px", "color": "#9ca3af", "fontSize": "0.72rem"}),
                        ]), style={"borderBottom": "1px solid #374151"}),
                        html.Tbody(track_rows),
                    ],
                    style={"width": "100%", "borderCollapse": "collapse"},
                ),
                style={"background": "#0d1117", "borderRadius": "8px", "border": "1px solid #1f2937",
                       "overflowX": "auto", "marginBottom": "18px"},
            ),

            html.H6("5.3 — Matriz de Convergencia de Señales",
                    style={"color": "#9ca3af", "fontSize": "0.8rem", "marginBottom": "8px"}),
            html.Div(
                [
                    html.P(
                        "Cuando múltiples indicadores independientes apuntan en la misma dirección, la probabilidad de materialización es mucho mayor.",
                        style={"fontSize": "0.78rem", "color": "#9ca3af", "marginBottom": "10px"},
                    ),
                    html.Div(
                        html.Table(
                            [
                                html.Thead(html.Tr([
                                    html.Th("Categoría", style={"padding": "8px 12px", "color": "#9ca3af", "fontSize": "0.72rem"}),
                                    html.Th("Señal Recesión", style={"padding": "8px 12px", "color": "#9ca3af", "fontSize": "0.72rem", "textAlign": "center"}),
                                    html.Th("Señal Crisis Financiera", style={"padding": "8px 12px", "color": "#9ca3af", "fontSize": "0.72rem", "textAlign": "center"}),
                                    html.Th("Señal Inflación", style={"padding": "8px 12px", "color": "#9ca3af", "fontSize": "0.72rem", "textAlign": "center"}),
                                ]), style={"borderBottom": "1px solid #374151"}),
                                html.Tbody(matrix_rows),
                            ],
                            style={"width": "100%", "borderCollapse": "collapse"},
                        ),
                        style={"background": "#0d1117", "borderRadius": "8px", "border": "1px solid #1f2937", "overflowX": "auto"},
                    ),
                ]
            ),
        ],
        style={"padding": "16px"},
    )


# ── Layout principal ────────────────────────────────────────────────────────────

def render_module_11() -> html.Div:
    return html.Div(
        [
            dcc.Interval(id="m11-interval", interval=120_000, n_intervals=0),

            _build_header(),

            dcc.Tabs(
                id="m11-tabs",
                value="tab1",
                children=[
                    dcc.Tab(label="📊 Cuadro de Mando",        value="tab1", style=_TAB_STYLE, selected_style=_TAB_SELECTED),
                    dcc.Tab(label="📉 Indicadores Recesión",    value="tab2", style=_TAB_STYLE, selected_style=_TAB_SELECTED),
                    dcc.Tab(label="🏦 Crisis Financiera",       value="tab3", style=_TAB_STYLE, selected_style=_TAB_SELECTED),
                    dcc.Tab(label="🔥 Inflación",               value="tab4", style=_TAB_STYLE, selected_style=_TAB_SELECTED),
                    dcc.Tab(label="📋 Historial Señales",       value="tab5", style=_TAB_STYLE, selected_style=_TAB_SELECTED),
                ],
                style=_TABS_CONTAINER,
            ),

            html.Div(id="m11-tab-content", style={"minHeight": "600px"}),
        ],
        style={"backgroundColor": "#0a0e1a", "minHeight": "100vh"},
    )


# ── Callbacks ──────────────────────────────────────────────────────────────────

def register_callbacks_module_11(app):

    @app.callback(
        Output("m11-tab-content", "children"),
        Input("m11-tabs", "value"),
        Input("m11-interval", "n_intervals"),
    )
    def render_tab(tab, _):
        try:
            if tab == "tab1":
                return _build_tab1()
            if tab == "tab2":
                return _build_tab2()
            if tab == "tab3":
                return _build_tab3()
            if tab == "tab4":
                return _build_tab4()
            if tab == "tab5":
                return _build_tab5()
        except Exception as exc:
            return html.Div(f"Error cargando pestaña: {exc}",
                            style={"color": "#ef4444", "padding": "24px"})
        return html.Div()

    @app.callback(
        Output("m11-header-semaphores", "children"),
        Output("m11-recalc-ts", "children"),
        Input("m11-recalculate-btn", "n_clicks"),
        prevent_initial_call=True,
    )
    def recalculate(_):
        try:
            rec = calculate_recession_probability()
            fin = calculate_systemic_risk_index()
            inf = calculate_inflation_pressure()
            gpr_val, gpr_ts = get_latest_value("fred_gpr_gprc")
            gpr_level = "gray"
            if gpr_val is not None:
                if gpr_val < 100:   gpr_level = "green"
                elif gpr_val < 150: gpr_level = "yellow"
                elif gpr_val < 200: gpr_level = "orange"
                else:               gpr_level = "red"
            fin_level = fin.get("level", "gray")
            fin_idx   = fin.get("composite_index", fin.get("index", 0))
            ts_str = gpr_ts.strftime("%b %Y") if gpr_ts else "—"

            semaphores = [
                _semaphore_card("Riesgo Recesión (12m)", f"{rec['probability']:.0f}%", rec["level"],
                                subtitle=", ".join(c["name"] for c in rec["components"] if c.get("alert"))[:60] or "Sin alertas"),
                _semaphore_card("Riesgo Crisis Financiera", f"{fin_idx:.0f}/100", fin_level),
                _semaphore_card("Presión Inflacionaria", f"{inf['index']:.0f}/100", inf["level"]),
                _semaphore_card("Riesgo Geopolítico (GPR)", _safe(gpr_val, ".0f"), gpr_level, subtitle=f"Actualizado: {ts_str}"),
            ]
            ts_now = datetime.utcnow().strftime("Recalculado: %H:%M:%S UTC")
            return semaphores, ts_now
        except Exception as exc:
            return no_update, f"Error: {exc}"
