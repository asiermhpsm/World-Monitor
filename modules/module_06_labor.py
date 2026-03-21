"""
Modulo 6 — Mercado Laboral
Se renderiza cuando la URL es /module/6.

Exporta:
  render_module_6()               -> layout completo
  register_callbacks_module_6(app) -> registra todos los callbacks
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

import plotly.graph_objects as go
import pandas as pd
from dash import Input, Output, dcc, html, callback_context

from components.chart_config import (
    COLORS as C,
    COUNTRY_COLORS,
    get_base_layout,
    get_time_range_buttons,
)
from components.common import (
    create_empty_state,
    create_section_header,
)
from config import COLORS
from modules.data_helpers import (
    calculate_sahm_indicator,
    format_value,
    get_change,
    get_latest_value,
    get_nfp_history,
    get_series,
    get_world_bank_indicator,
    time_ago,
)

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTES
# ══════════════════════════════════════════════════════════════════════════════

ID_UNEMP_US         = "fred_unemployment_us"
ID_NFP_US           = "fred_nfp_us"
ID_PARTIC_US        = "fred_labor_partic_us"
ID_WAGES_US         = "fred_avg_wages_us"
ID_INIT_CLAIMS      = "fred_initial_claims_us"
ID_CONT_CLAIMS      = "fred_cont_claims_us"
ID_YOUTH_UNEMP_US   = "fred_youth_unemp_us"
ID_LONG_UNEMP_US    = "fred_long_unemp_us"
ID_SHORT_UNEMP_US   = "fred_short_unemp_us"

ID_WB_UNEMP_ESP     = "wb_unemployment_esp"
ID_WB_UNEMP_EMU     = "wb_unemployment_emu"

# Países para comparativas
HIST_COUNTRIES = ["USA", "DEU", "ESP", "GBR", "JPN", "FRA", "ITA"]
EURO_COUNTRIES  = ["ESP", "DEU", "FRA", "ITA", "NLD", "PRT", "GRC", "POL", "SWE", "NOR"]

ISO3_NAMES = {
    "USA": "🇺🇸 EE.UU.", "CHN": "🇨🇳 China", "DEU": "🇩🇪 Alemania",
    "JPN": "🇯🇵 Japón",  "IND": "🇮🇳 India", "GBR": "🇬🇧 Reino Unido",
    "FRA": "🇫🇷 Francia","ITA": "🇮🇹 Italia","BRA": "🇧🇷 Brasil",
    "CAN": "🇨🇦 Canadá", "KOR": "🇰🇷 Corea del Sur","AUS": "🇦🇺 Australia",
    "ESP": "🇪🇸 España", "MEX": "🇲🇽 México","RUS": "🇷🇺 Rusia",
    "NLD": "🇳🇱 Países Bajos","CHE": "🇨🇭 Suiza","POL": "🇵🇱 Polonia",
    "TUR": "🇹🇷 Turquía","ARG": "🇦🇷 Argentina","ZAF": "🇿🇦 Sudáfrica",
    "SAU": "🇸🇦 Arabia Saudí","EGY": "🇪🇬 Egipto","IDN": "🇮🇩 Indonesia",
    "NGA": "🇳🇬 Nigeria","GRC": "🇬🇷 Grecia","PRT": "🇵🇹 Portugal",
    "SWE": "🇸🇪 Suecia","NOR": "🇳🇴 Noruega",
}

TAB_STYLE = {
    "backgroundColor": "transparent",
    "color": COLORS["text_muted"],
    "border": "none",
    "borderBottom": "2px solid transparent",
    "padding": "10px 18px",
    "fontSize": "0.82rem",
    "fontWeight": "500",
}
TAB_SELECTED_STYLE = {
    **TAB_STYLE,
    "color": COLORS["text"],
    "borderBottom": f"2px solid {COLORS['accent']}",
    "fontWeight": "600",
}
TABS_STYLE = {
    "borderBottom": f"1px solid {COLORS['border']}",
    "backgroundColor": COLORS["card_bg"],
}

_SECTION_STYLE = {"padding": "16px"}


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _safe(val, fmt=".1f", suffix="") -> str:
    if val is None:
        return "—"
    try:
        return f"{val:{fmt}}{suffix}"
    except Exception:
        return "—"


def _compact_metric(title: str, value_str: str, change_str: str,
                    change_color: str, freq: str = "") -> html.Div:
    """Card compacta para el header del módulo."""
    return html.Div(
        [
            html.Div(title, style={
                "fontSize": "0.60rem", "color": COLORS["text_label"],
                "fontWeight": "600", "letterSpacing": "0.08em", "marginBottom": "2px",
            }),
            html.Div(value_str, style={
                "fontSize": "1.15rem", "fontWeight": "700", "color": COLORS["text"],
                "lineHeight": "1.1",
            }),
            html.Div(change_str, style={
                "fontSize": "0.72rem", "color": change_color, "marginTop": "2px",
            }),
            html.Div(freq, style={
                "fontSize": "0.60rem", "color": COLORS["text_label"], "marginTop": "1px",
            }),
        ],
        style={
            "background": COLORS["card_bg"],
            "border": f"1px solid {COLORS['border']}",
            "borderRadius": "6px",
            "padding": "10px 14px",
            "flex": "1",
            "minWidth": "120px",
        },
    )


def _unemp_color(val: Optional[float]) -> str:
    if val is None:
        return COLORS["text_muted"]
    if val < 5:
        return COLORS["green"]
    if val < 8:
        return COLORS["yellow"]
    if val < 12:
        return COLORS["orange"]
    return COLORS["red"]


def _change_color(change: Optional[float], higher_bad: bool = True) -> str:
    """Devuelve color en función de la variación."""
    if change is None:
        return COLORS["text_muted"]
    if change == 0:
        return COLORS["text_muted"]
    if higher_bad:
        return COLORS["red"] if change > 0 else COLORS["green"]
    return COLORS["green"] if change > 0 else COLORS["red"]


def _arrow(change: Optional[float]) -> str:
    if change is None:
        return ""
    if change > 0:
        return "↑"
    if change < 0:
        return "↓"
    return "→"


# ══════════════════════════════════════════════════════════════════════════════
# HEADER METRICS
# ══════════════════════════════════════════════════════════════════════════════

def _build_header_metrics() -> html.Div:
    metrics = []

    # 1. Desempleo EE.UU.
    try:
        cur, prev, chg, _ = get_change(ID_UNEMP_US, period_days=40)
        val_str = _safe(cur, ".1f", "%")
        chg_str = f"{_arrow(chg)} {_safe(abs(chg) if chg else None, '.2f')} pp vs mes ant." if chg is not None else "Sin cambio"
        metrics.append(_compact_metric("DESEMPLEO EE.UU.", val_str, chg_str, _change_color(chg, True), "Mensual · FRED"))
    except Exception:
        metrics.append(_compact_metric("DESEMPLEO EE.UU.", "—", "Sin datos", COLORS["text_muted"], "Mensual · FRED"))

    # 2. NFP EE.UU. (nivel actual)
    try:
        nfp_val, nfp_ts = get_latest_value(ID_NFP_US)
        if nfp_val is not None:
            val_str = f"{nfp_val:,.0f}K"
            upd = time_ago(nfp_ts)
            metrics.append(_compact_metric("NFP EE.UU.", val_str, f"Nivel total empleos", COLORS["text_muted"], f"Actualiz. {upd}"))
        else:
            metrics.append(_compact_metric("NFP EE.UU.", "—", "Sin datos", COLORS["text_muted"], "Mensual · FRED"))
    except Exception:
        metrics.append(_compact_metric("NFP EE.UU.", "—", "Sin datos", COLORS["text_muted"], "Mensual · FRED"))

    # 3. Desempleo Eurozona
    try:
        emu_val, emu_ts = get_latest_value(ID_WB_UNEMP_EMU)
        if emu_val is not None:
            metrics.append(_compact_metric("DESEMPLEO EUROZONA", _safe(emu_val, ".1f", "%"), f"Datos anuales BM", COLORS["text_muted"], "Anual · Banco Mundial"))
        else:
            metrics.append(_compact_metric("DESEMPLEO EUROZONA", "—", "Sin datos", COLORS["text_muted"], "Anual · BM"))
    except Exception:
        metrics.append(_compact_metric("DESEMPLEO EUROZONA", "—", "Sin datos", COLORS["text_muted"], "Anual · BM"))

    # 4. Desempleo España
    try:
        esp_val, esp_ts = get_latest_value(ID_WB_UNEMP_ESP)
        if esp_val is not None:
            metrics.append(_compact_metric("DESEMPLEO ESPAÑA", _safe(esp_val, ".1f", "%"), f"Datos anuales BM", _unemp_color(esp_val), "Anual · Banco Mundial"))
        else:
            metrics.append(_compact_metric("DESEMPLEO ESPAÑA", "—", "Sin datos", COLORS["text_muted"], "Anual · BM"))
    except Exception:
        metrics.append(_compact_metric("DESEMPLEO ESPAÑA", "—", "Sin datos", COLORS["text_muted"], "Anual · BM"))

    # 5. Crecimiento salarial EE.UU.
    try:
        wages_val, wages_ts = get_latest_value(ID_WAGES_US)
        if wages_val is not None:
            metrics.append(_compact_metric("SALARIO HORA EE.UU.", f"${_safe(wages_val, '.2f')}", "Salario medio por hora", C["positive"], "Mensual · FRED"))
        else:
            metrics.append(_compact_metric("SALARIO HORA EE.UU.", "—", "Sin datos", COLORS["text_muted"], "Mensual · FRED"))
    except Exception:
        metrics.append(_compact_metric("SALARIO HORA EE.UU.", "—", "Sin datos", COLORS["text_muted"], "Mensual · FRED"))

    # 6. Participación laboral EE.UU.
    try:
        part_val, part_ts = get_latest_value(ID_PARTIC_US)
        if part_val is not None:
            metrics.append(_compact_metric("PARTICIP. LABORAL EE.UU.", _safe(part_val, ".1f", "%"), "Tasa de actividad", COLORS["text_muted"], "Mensual · FRED"))
        else:
            metrics.append(_compact_metric("PARTICIP. LABORAL EE.UU.", "—", "Sin datos", COLORS["text_muted"], "Mensual · FRED"))
    except Exception:
        metrics.append(_compact_metric("PARTICIP. LABORAL EE.UU.", "—", "Sin datos", COLORS["text_muted"], "Mensual · FRED"))

    return html.Div(
        metrics,
        style={
            "display": "flex", "gap": "10px", "flexWrap": "wrap",
            "padding": "12px 16px", "borderBottom": f"1px solid {COLORS['border']}",
        },
    )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — VISIÓN GLOBAL
# ══════════════════════════════════════════════════════════════════════════════

def _build_tab_global() -> html.Div:
    return html.Div([
        # 1.1 Mapa coroplético
        html.Div([
            create_section_header(
                "Mapa Mundial de Desempleo",
                "Últimos datos disponibles por país · Banco Mundial",
            ),
            html.Div(
                dcc.RadioItems(
                    id="m6-map-indicator",
                    options=[
                        {"label": "Desempleo total", "value": "unemployment"},
                        {"label": "Desempleo juvenil", "value": "youth_unemp"},
                        {"label": "Participación laboral", "value": "labor_force_pct"},
                    ],
                    value="unemployment",
                    inline=True,
                    inputStyle={"marginRight": "6px", "cursor": "pointer"},
                    labelStyle={
                        "marginRight": "18px", "fontSize": "0.82rem",
                        "color": COLORS["text_muted"], "cursor": "pointer",
                    },
                ),
                style={"marginBottom": "10px"},
            ),
            dcc.Loading(
                dcc.Graph(id="m6-choropleth-map", config={"displayModeBar": False}),
                color=COLORS["accent"],
            ),
        ], style=_SECTION_STYLE),

        # 1.2 Rankings
        html.Div([
            create_section_header(
                "Rankings de Desempleo",
                "Top 15 países con mayor y menor tasa de desempleo",
            ),
            html.Div([
                html.Div([
                    html.Div("Mayores tasas de desempleo", style={
                        "fontSize": "0.78rem", "color": COLORS["text_muted"],
                        "marginBottom": "10px", "fontWeight": "600",
                    }),
                    dcc.Loading(
                        html.Div(id="m6-ranking-high"),
                        color=COLORS["accent"],
                    ),
                ], style={"flex": "1", "minWidth": "280px"}),
                html.Div([
                    html.Div("Menores tasas de desempleo", style={
                        "fontSize": "0.78rem", "color": COLORS["text_muted"],
                        "marginBottom": "10px", "fontWeight": "600",
                    }),
                    dcc.Loading(
                        html.Div(id="m6-ranking-low"),
                        color=COLORS["accent"],
                    ),
                ], style={"flex": "1", "minWidth": "280px"}),
            ], style={"display": "flex", "gap": "24px", "flexWrap": "wrap"}),
        ], style=_SECTION_STYLE),

        # 1.3 Comparativa histórica
        html.Div([
            create_section_header(
                "Comparativa Histórica de Desempleo",
                "Evolución anual por países seleccionados · Banco Mundial",
            ),
            dcc.Loading(
                dcc.Graph(id="m6-hist-comparison", config={"displayModeBar": False}),
                color=COLORS["accent"],
            ),
        ], style=_SECTION_STYLE),
    ])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — EE.UU. EN DETALLE
# ══════════════════════════════════════════════════════════════════════════════

def _build_tab_usa() -> html.Div:
    return html.Div([
        # 2.1 Cards de métricas
        html.Div([
            create_section_header(
                "Indicadores Clave del Mercado Laboral EE.UU.",
                "Datos más recientes disponibles en base de datos",
            ),
            html.Div(id="m6-usa-cards", style={
                "display": "grid",
                "gridTemplateColumns": "repeat(auto-fill, minmax(200px, 1fr))",
                "gap": "12px",
                "marginTop": "10px",
            }),
        ], style=_SECTION_STYLE),

        # 2.2 Histórico de desempleo FRED
        html.Div([
            create_section_header(
                "Tasa de Desempleo EE.UU. — Histórico FRED",
                "313 registros mensuales 2000–2026 · FRED/BLS",
            ),
            dcc.Loading(
                dcc.Graph(id="m6-unemp-history", config={"displayModeBar": False}),
                color=COLORS["accent"],
            ),
        ], style=_SECTION_STYLE),

        # 2.3 NFP
        html.Div([
            create_section_header(
                "Nóminas No Agrícolas (NFP)",
                "El scheduler descarga el nivel total; se necesita histórico PAYEMS para variaciones",
            ),
            html.Div(id="m6-nfp-section"),
        ], style=_SECTION_STYLE),

        # 2.4 Solicitudes de desempleo
        html.Div([
            create_section_header(
                "Solicitudes de Subsidio por Desempleo",
                "Inicial (semanal) y Continuas — datos limitados en DB",
            ),
            dcc.Loading(
                dcc.Graph(id="m6-claims-chart", config={"displayModeBar": False}),
                color=COLORS["accent"],
            ),
        ], style=_SECTION_STYLE),

        # 2.5 Regla de Sahm
        html.Div([
            create_section_header(
                "Indicador de Sahm — Regla de Recesión",
                "Calculado sobre 313 registros FRED; ≥0.5 pp históricamente señala recesión",
            ),
            html.Div(id="m6-sahm-panel"),
        ], style=_SECTION_STYLE),

        # 2.6 Composición del desempleo
        html.Div([
            create_section_header(
                "Composición del Desempleo",
                "Corto plazo, largo plazo y juvenil",
            ),
            html.Div(id="m6-composition-panel"),
        ], style=_SECTION_STYLE),
    ])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — EUROPA EN DETALLE
# ══════════════════════════════════════════════════════════════════════════════

def _build_tab_europe() -> html.Div:
    return html.Div([
        # 3.1 Comparativa europea
        html.Div([
            create_section_header(
                "Comparativa Europea de Desempleo",
                "Datos anuales Banco Mundial — solo disponible hasta 2025",
            ),
            dcc.Loading(
                dcc.Graph(id="m6-europe-comparison", config={"displayModeBar": False}),
                color=COLORS["accent"],
            ),
        ], style=_SECTION_STYLE),

        # 3.2 España en detalle
        html.Div([
            create_section_header(
                "España — Panel Especial",
                "Desempleo total y juvenil, comparativa con Eurozona",
            ),
            html.Div(id="m6-spain-panel"),
            dcc.Loading(
                dcc.Graph(id="m6-spain-vs-emu", config={"displayModeBar": False}),
                color=COLORS["accent"],
            ),
        ], style=_SECTION_STYLE),

        # 3.3 Desempleo juvenil europeo
        html.Div([
            create_section_header(
                "Desempleo Juvenil Europeo",
                "Últimos datos disponibles por país · Banco Mundial",
            ),
            dcc.Loading(
                dcc.Graph(id="m6-youth-europe", config={"displayModeBar": False}),
                color=COLORS["accent"],
            ),
        ], style=_SECTION_STYLE),

        # 3.4 Salarios vs inflación (vacío)
        html.Div([
            create_section_header(
                "Salarios vs Inflación — Europa",
                "No disponible: sin series de salarios europeos en DB",
            ),
            create_empty_state(
                "Datos no disponibles",
                "El scheduler no descarga series de salarios para Europa. "
                "Para activar: añadir ESTAT wage series al scheduler.",
            ),
        ], style=_SECTION_STYLE),
    ])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — TENDENCIAS ESTRUCTURALES
# ══════════════════════════════════════════════════════════════════════════════

def _build_tab_structural() -> html.Div:
    return html.Div([
        # 4.1 Participación laboral
        html.Div([
            create_section_header(
                "Participación en la Fuerza Laboral",
                "Datos anuales Banco Mundial — % población activa sobre total en edad laboral",
            ),
            dcc.Loading(
                dcc.Graph(id="m6-labor-participation", config={"displayModeBar": False}),
                color=COLORS["accent"],
            ),
        ], style=_SECTION_STYLE),

        # 4.2 Productividad
        html.Div([
            create_section_header(
                "Productividad Laboral",
                "PIB por trabajador en USD (PPP) · Banco Mundial",
            ),
            dcc.Loading(
                dcc.Graph(id="m6-productivity", config={"displayModeBar": False}),
                color=COLORS["accent"],
            ),
        ], style=_SECTION_STYLE),

        # 4.3 Impacto IA (estático educativo)
        html.Div([
            create_section_header(
                "Impacto de la IA en el Empleo",
                "Estimaciones de automatización por sector · McKinsey/Oxford (2023)",
            ),
            dcc.Graph(
                id="m6-ai-impact",
                figure=_build_ai_impact_chart(),
                config={"displayModeBar": False},
            ),
        ], style=_SECTION_STYLE),

        # 4.4 Población en edad laboral
        html.Div([
            create_section_header(
                "Dinámica de la Fuerza Laboral por País",
                "Participación laboral histórica como proxy de tendencias estructurales",
            ),
            dcc.Loading(
                dcc.Graph(id="m6-workforce-dynamics", config={"displayModeBar": False}),
                color=COLORS["accent"],
            ),
        ], style=_SECTION_STYLE),
    ])


# ══════════════════════════════════════════════════════════════════════════════
# CHART BUILDERS (iniciales / estáticos)
# ══════════════════════════════════════════════════════════════════════════════

def _build_ai_impact_chart() -> go.Figure:
    """Gráfico estático educativo sobre automatización por sector."""
    sectors = [
        "Manufactura", "Transporte", "Retail", "Hostelería",
        "Servicios financieros", "Salud", "Educación", "Tecnología",
        "Construcción", "Agricultura",
    ]
    automation_risk = [73, 69, 54, 44, 43, 29, 22, 18, 47, 55]
    colors_bar = [
        COLORS["red"] if r >= 60 else COLORS["orange"] if r >= 45
        else COLORS["yellow"] if r >= 30 else COLORS["green"]
        for r in automation_risk
    ]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=sectors,
        x=automation_risk,
        orientation="h",
        marker_color=colors_bar,
        text=[f"{r}%" for r in automation_risk],
        textposition="outside",
        textfont={"color": COLORS["text_muted"], "size": 11},
        hovertemplate="%{y}: %{x}% riesgo de automatización<extra></extra>",
    ))
    fig.add_vline(x=50, line_dash="dash", line_color=COLORS["border_mid"],
                  annotation_text="Umbral 50%", annotation_font_color=COLORS["text_muted"],
                  annotation_font_size=10)
    layout = get_base_layout("Riesgo de Automatización por Sector (%)", height=380)
    layout.update({
        "xaxis": {**layout.get("xaxis", {}), "title": "% puestos en riesgo", "range": [0, 90]},
        "yaxis": {**layout.get("yaxis", {}), "title": ""},
        "margin": {"l": 120, "r": 60, "t": 40, "b": 40},
        "hovermode": "y unified",
        "annotations": layout.get("annotations", []) + [{
            "text": "Fuente: McKinsey Global Institute / Oxford Martin School (2023)",
            "xref": "paper", "yref": "paper", "x": 0.5, "y": -0.08,
            "showarrow": False, "font": {"color": COLORS["text_label"], "size": 10},
            "xanchor": "center",
        }],
    })
    fig.update_layout(**layout)
    return fig


def _build_choropleth_map(indicator: str) -> go.Figure:
    """Construye mapa coroplético de desempleo mundial."""
    try:
        df = get_world_bank_indicator(indicator)
        if df.empty:
            fig = go.Figure()
            fig.update_layout(**get_base_layout(f"Sin datos para {indicator}", height=480))
            return fig

        ind_labels = {
            "unemployment":  ("Desempleo (%)", "RdYlGn_r", 0, 25),
            "youth_unemp":   ("Desempleo Juvenil (%)", "RdYlGn_r", 0, 40),
            "labor_force_pct": ("Part. Laboral (%)", "RdYlGn", 40, 90),
        }
        label, scale, zmin, zmax = ind_labels.get(indicator, ("Valor", "RdYlGn_r", 0, 25))

        hover_texts = []
        for _, row in df.iterrows():
            iso = row["country_iso3"]
            name = ISO3_NAMES.get(iso, iso)
            hover_texts.append(f"{name}<br>{label}: {row['value']:.1f}%<br>Año: {int(row['year'])}")

        fig = go.Figure()
        fig.add_trace(go.Choropleth(
            locations=df["country_iso3"],
            z=df["value"],
            colorscale=scale,
            locationmode="ISO-3",
            text=hover_texts,
            hovertemplate="%{text}<extra></extra>",
            colorbar=dict(
                title=dict(text="%", side="right"),
                thickness=12, len=0.7,
                tickfont=dict(color="#9ca3af", size=10),
                bgcolor="rgba(0,0,0,0)",
                bordercolor="#1f2937",
            ),
            zmin=zmin, zmax=zmax,
        ))
        fig.update_layout(
            geo=dict(
                bgcolor="#0a0e1a", lakecolor="#0a0e1a", landcolor="#1f2937",
                showframe=False, showcoastlines=True,
                coastlinecolor="#374151", projection_type="natural earth",
            ),
            **get_base_layout(label, height=480),
        )
        return fig
    except Exception as exc:
        logger.warning("_build_choropleth_map error: %s", exc)
        fig = go.Figure()
        fig.update_layout(**get_base_layout("Error cargando mapa", height=480))
        return fig


def _build_ranking_table(df: pd.DataFrame, top_high: bool = True) -> html.Div:
    """Genera tabla de ranking de desempleo."""
    try:
        if df.empty:
            return create_empty_state("Sin datos disponibles")

        df_sorted = df.sort_values("value", ascending=not top_high).head(15)

        rows = []
        for i, (_, row) in enumerate(df_sorted.iterrows(), 1):
            iso = row["country_iso3"]
            name = ISO3_NAMES.get(iso, iso)
            val = row["value"]

            if val >= 15:
                col = COLORS["red"]
            elif val >= 10:
                col = COLORS["orange"]
            elif val >= 5:
                col = COLORS["yellow"]
            else:
                col = COLORS["green"]

            rows.append(html.Div([
                html.Span(f"{i}.", style={"color": COLORS["text_label"], "fontSize": "0.75rem", "width": "24px", "display": "inline-block"}),
                html.Span(name, style={"color": COLORS["text"], "fontSize": "0.78rem", "flex": "1"}),
                html.Span(f"{val:.1f}%", style={"color": col, "fontSize": "0.80rem", "fontWeight": "600"}),
            ], style={
                "display": "flex", "alignItems": "center", "gap": "8px",
                "padding": "5px 8px", "borderBottom": f"1px solid {COLORS['border']}",
            }))

        return html.Div(rows, style={
            "border": f"1px solid {COLORS['border']}",
            "borderRadius": "6px",
            "overflow": "hidden",
        })
    except Exception as exc:
        logger.warning("_build_ranking_table: %s", exc)
        return create_empty_state("Error al generar tabla")


def _build_hist_comparison_chart() -> go.Figure:
    """Gráfico histórico multi-país desde WB annual data."""
    fig = go.Figure()
    country_styles = {
        "USA": {"color": COUNTRY_COLORS["USA"], "width": 2},
        "DEU": {"color": COUNTRY_COLORS["DEU"], "width": 2},
        "ESP": {"color": COUNTRY_COLORS["ESP"], "width": 3},
        "GBR": {"color": COUNTRY_COLORS["GBR"], "width": 2},
        "JPN": {"color": COUNTRY_COLORS["JPN"], "width": 2},
        "FRA": {"color": COUNTRY_COLORS.get("FRA", "#8b5cf6"), "width": 2},
        "ITA": {"color": COUNTRY_COLORS["ITA"], "width": 2},
    }

    has_data = False
    for iso3, style in country_styles.items():
        try:
            series_id = f"wb_unemployment_{iso3.lower()}"
            df = get_series(series_id, days=365 * 30)
            if df.empty:
                continue
            df = df.sort_values("timestamp")
            fig.add_trace(go.Scatter(
                x=df["timestamp"],
                y=df["value"],
                name=ISO3_NAMES.get(iso3, iso3),
                line={"color": style["color"], "width": style["width"]},
                mode="lines+markers",
                marker={"size": 4},
                hovertemplate=f"{ISO3_NAMES.get(iso3, iso3)}: %{{y:.1f}}%<br>%{{x|%Y}}<extra></extra>",
            ))
            has_data = True
        except Exception:
            continue

    if not has_data:
        fig.add_annotation(
            text="Sin datos históricos disponibles",
            xref="paper", yref="paper", x=0.5, y=0.5,
            showarrow=False, font={"color": COLORS["text_muted"], "size": 14},
        )

    # Anotación pico España 2013
    try:
        fig.add_annotation(
            x="2013-01-01", y=26,
            text="España: pico 26%<br>(2013)", showarrow=True, arrowhead=2,
            font={"color": COLORS["yellow"], "size": 10},
            arrowcolor=COLORS["yellow"],
            bgcolor=COLORS["card_bg"], bordercolor=COLORS["yellow"],
            ax=40, ay=-30,
        )
    except Exception:
        pass

    layout = get_base_layout("Tasa de Desempleo por País (%)", height=400)
    layout.update({
        "yaxis": {**layout.get("yaxis", {}), "title": "% desempleo"},
        "hovermode": "x unified",
    })
    fig.update_layout(**layout)
    return fig


def _build_unemp_history_chart() -> go.Figure:
    """Histórico FRED de desempleo EE.UU. con anotaciones de crisis."""
    try:
        df = get_series(ID_UNEMP_US, days=365 * 30)
        if df.empty:
            fig = go.Figure()
            fig.update_layout(**get_base_layout("Sin datos FRED disponibles", height=380))
            return fig

        df = df.sort_values("timestamp")

        fig = go.Figure()

        # Relleno de recesiones aproximadas
        recessions = [
            ("2001-03-01", "2001-11-01", "Recesión 2001"),
            ("2007-12-01", "2009-06-01", "Crisis Financiera"),
            ("2020-02-01", "2020-04-01", "COVID-19"),
        ]
        for start_r, end_r, label_r in recessions:
            fig.add_vrect(
                x0=start_r, x1=end_r,
                fillcolor=COLORS["red"], opacity=0.08,
                line_width=0,
                annotation_text=label_r,
                annotation_position="top left",
                annotation_font={"color": COLORS["text_muted"], "size": 9},
            )

        fig.add_trace(go.Scatter(
            x=df["timestamp"],
            y=df["value"],
            name="Desempleo EE.UU.",
            line={"color": C["primary"], "width": 2},
            fill="tozeroy",
            fillcolor="rgba(59,130,246,0.08)",
            hovertemplate="Desempleo: %{y:.1f}%<br>%{x|%b %Y}<extra></extra>",
        ))

        # Referencia línea 4%
        fig.add_hline(y=4, line_dash="dot", line_color=COLORS["green"],
                      annotation_text="Pleno empleo ~4%",
                      annotation_font_color=COLORS["green"],
                      annotation_font_size=10)

        layout = get_base_layout("Tasa de Desempleo EE.UU. 2000–2026 (%)", height=380)
        layout.update({
            "yaxis": {**layout.get("yaxis", {}), "title": "% desempleo"},
            "xaxis": {
                **layout.get("xaxis", {}),
                "rangeselector": get_time_range_buttons(),
                "rangeslider": {"visible": False},
            },
        })
        fig.update_layout(**layout)
        return fig
    except Exception as exc:
        logger.warning("_build_unemp_history_chart: %s", exc)
        fig = go.Figure()
        fig.update_layout(**get_base_layout("Error cargando datos", height=380))
        return fig


def _build_nfp_section() -> html.Div:
    """Sección NFP: nivel actual prominente + empty state para histórico."""
    try:
        nfp_val, nfp_ts = get_latest_value(ID_NFP_US)

        level_card = html.Div([
            html.Div("NÓMINAS NO AGRÍCOLAS — NIVEL ACTUAL", style={
                "fontSize": "0.70rem", "color": COLORS["text_label"],
                "fontWeight": "600", "letterSpacing": "0.08em", "marginBottom": "8px",
            }),
            html.Div(
                f"{nfp_val:,.0f}K empleos" if nfp_val else "—",
                style={"fontSize": "2rem", "fontWeight": "700", "color": COLORS["text"]},
            ),
            html.Div("Total empleados no agrícolas · Miles de personas", style={
                "fontSize": "0.78rem", "color": COLORS["text_muted"], "marginTop": "4px",
            }),
            html.Div(
                f"Actualizado: {time_ago(nfp_ts)}" if nfp_ts else "",
                style={"fontSize": "0.72rem", "color": COLORS["text_label"], "marginTop": "2px"},
            ),
        ], style={
            "background": COLORS["card_bg"],
            "border": f"1px solid {COLORS['accent']}",
            "borderRadius": "8px", "padding": "20px 24px",
            "marginBottom": "16px", "display": "inline-block",
        })

        empty_note = create_empty_state(
            "Histórico de variaciones NFP no disponible",
            "El scheduler descarga únicamente el nivel acumulado más reciente (PAYEMS). "
            "Para construir el histórico de variaciones mensuales (MoM), activa la "
            "descarga histórica de PAYEMS en el scheduler.",
        )

        # Variaciones mensuales de desempleo como complemento
        try:
            df_unemp = get_series(ID_UNEMP_US, days=365 * 3)
            if not df_unemp.empty and len(df_unemp) >= 3:
                df_unemp = df_unemp.sort_values("timestamp").tail(36)
                df_unemp["mom"] = df_unemp["value"].diff()
                df_unemp = df_unemp.dropna(subset=["mom"])

                fig_mom = go.Figure()
                colors_mom = [COLORS["red"] if v > 0 else COLORS["green"] for v in df_unemp["mom"]]
                fig_mom.add_trace(go.Bar(
                    x=df_unemp["timestamp"],
                    y=df_unemp["mom"],
                    marker_color=colors_mom,
                    name="Variación mensual desempleo",
                    hovertemplate="%{x|%b %Y}: %{y:+.2f} pp<extra></extra>",
                ))
                layout_mom = get_base_layout("Variaciones Mensuales de la Tasa de Desempleo (pp)", height=280)
                layout_mom.update({
                    "yaxis": {**layout_mom.get("yaxis", {}), "title": "pp (puntos porcentuales)"},
                    "bargap": 0.2,
                })
                fig_mom.update_layout(**layout_mom)
                complement = dcc.Graph(figure=fig_mom, config={"displayModeBar": False})
            else:
                complement = html.Div()
        except Exception:
            complement = html.Div()

        return html.Div([level_card, empty_note, html.Div(style={"marginTop": "12px"}), complement])
    except Exception as exc:
        logger.warning("_build_nfp_section: %s", exc)
        return create_empty_state("Error cargando datos NFP")


def _build_claims_chart() -> go.Figure:
    """Gráfico de solicitudes iniciales y continuas de desempleo."""
    try:
        df_init = get_series(ID_INIT_CLAIMS, days=365 * 2)
        df_cont = get_series(ID_CONT_CLAIMS, days=365 * 2)

        if df_init.empty and df_cont.empty:
            fig = go.Figure()
            fig.add_annotation(
                text="Datos muy limitados en DB (4 registros semanales)",
                xref="paper", yref="paper", x=0.5, y=0.5,
                showarrow=False, font={"color": COLORS["text_muted"], "size": 13},
            )
            fig.update_layout(**get_base_layout("Solicitudes de Desempleo", height=300))
            return fig

        fig = go.Figure()

        if not df_init.empty:
            df_init = df_init.sort_values("timestamp")
            fig.add_trace(go.Scatter(
                x=df_init["timestamp"],
                y=df_init["value"],
                name="Solicitudes iniciales (miles)",
                line={"color": C["primary"], "width": 2},
                mode="lines+markers",
                marker={"size": 6},
                hovertemplate="Iniciales: %{y:,.0f}K<br>%{x|%d %b %Y}<extra></extra>",
            ))
            # Referencia histórica ~225K (pleno empleo)
            fig.add_hline(y=225, line_dash="dot", line_color=COLORS["green"],
                          annotation_text="~225K: zona sana",
                          annotation_font_color=COLORS["green"],
                          annotation_font_size=10)

        if not df_cont.empty:
            df_cont = df_cont.sort_values("timestamp")
            fig.add_trace(go.Scatter(
                x=df_cont["timestamp"],
                y=df_cont["value"],
                name="Solicitudes continuas (miles)",
                line={"color": C["warning"], "width": 2},
                mode="lines+markers",
                marker={"size": 6},
                yaxis="y2",
                hovertemplate="Continuas: %{y:,.0f}K<br>%{x|%d %b %Y}<extra></extra>",
            ))

        layout = get_base_layout("Solicitudes de Subsidio por Desempleo (miles)", height=300)
        layout.update({
            "yaxis": {**layout.get("yaxis", {}), "title": "Iniciales (miles)"},
            "yaxis2": {
                "title": "Continuas (miles)",
                "overlaying": "y", "side": "right",
                "gridcolor": "#1f2937", "tickfont": {"color": "#9ca3af", "size": 10},
                "title_font": {"color": "#9ca3af", "size": 11},
            },
            "margin": {"l": 60, "r": 60, "t": 50, "b": 40},
        })
        fig.update_layout(**layout)
        return fig
    except Exception as exc:
        logger.warning("_build_claims_chart: %s", exc)
        fig = go.Figure()
        fig.update_layout(**get_base_layout("Error cargando datos", height=300))
        return fig


def _build_sahm_panel() -> html.Div:
    """Panel del indicador de Sahm con semáforo y gráfico histórico."""
    try:
        sahm_val, level, df_sahm = calculate_sahm_indicator()

        level_colors = {
            "green":  COLORS["green"],
            "yellow": COLORS["yellow"],
            "red":    COLORS["red"],
            None:     COLORS["text_muted"],
        }
        level_labels = {
            "green":  "Sin señal de recesión",
            "yellow": "Alerta temprana",
            "red":    "Señal de recesión activa",
            None:     "Sin datos",
        }

        dot_color = level_colors[level]
        dot_label = level_labels[level]

        semaphore = html.Div([
            html.Div([
                html.Div(style={
                    "width": "20px", "height": "20px", "borderRadius": "50%",
                    "backgroundColor": dot_color,
                    "boxShadow": f"0 0 8px {dot_color}",
                    "display": "inline-block", "marginRight": "10px",
                }),
                html.Span(dot_label, style={"fontSize": "0.90rem", "color": dot_color, "fontWeight": "600"}),
            ], style={"display": "flex", "alignItems": "center", "marginBottom": "8px"}),
            html.Div([
                html.Span("Valor actual: ", style={"color": COLORS["text_muted"], "fontSize": "0.82rem"}),
                html.Span(
                    _safe(sahm_val, ".2f", " pp") if sahm_val is not None else "—",
                    style={"color": dot_color, "fontWeight": "700", "fontSize": "1.10rem"},
                ),
            ]),
            html.Div([
                html.Span("Umbral recesión: ", style={"color": COLORS["text_muted"], "fontSize": "0.78rem"}),
                html.Span("≥ 0.50 pp", style={"color": COLORS["red"], "fontWeight": "600", "fontSize": "0.82rem"}),
                html.Span("  |  Alerta temprana: ", style={"color": COLORS["text_muted"], "fontSize": "0.78rem"}),
                html.Span("0.30 – 0.50 pp", style={"color": COLORS["yellow"], "fontWeight": "600", "fontSize": "0.82rem"}),
            ], style={"marginTop": "6px"}),
            html.Div(
                "Definición: media móvil 3 meses del desempleo − mínimo de los últimos 12 meses",
                style={"fontSize": "0.72rem", "color": COLORS["text_label"], "marginTop": "8px"},
            ),
        ], style={
            "background": COLORS["card_bg"], "border": f"1px solid {COLORS['border']}",
            "borderRadius": "8px", "padding": "16px 20px", "marginBottom": "16px",
        })

        # Gráfico histórico de Sahm
        if not df_sahm.empty and len(df_sahm) >= 5:
            fig = go.Figure()

            # Zonas de alerta
            fig.add_hrect(y0=0.5, y1=df_sahm["sahm"].max() + 0.3,
                          fillcolor=COLORS["red"], opacity=0.08, line_width=0,
                          annotation_text="Zona recesión", annotation_position="top right",
                          annotation_font={"color": COLORS["red"], "size": 10})
            fig.add_hrect(y0=0.3, y1=0.5,
                          fillcolor=COLORS["yellow"], opacity=0.08, line_width=0,
                          annotation_text="Alerta", annotation_position="top right",
                          annotation_font={"color": COLORS["yellow"], "size": 10})

            fig.add_hline(y=0.5, line_dash="dash", line_color=COLORS["red"],
                          annotation_text="0.50 (recesión)", annotation_font_color=COLORS["red"],
                          annotation_font_size=10, annotation_position="right")
            fig.add_hline(y=0.3, line_dash="dot", line_color=COLORS["yellow"],
                          annotation_text="0.30 (alerta)", annotation_font_color=COLORS["yellow"],
                          annotation_font_size=10, annotation_position="right")

            line_color = dot_color
            fig.add_trace(go.Scatter(
                x=df_sahm["timestamp"],
                y=df_sahm["sahm"],
                name="Indicador de Sahm",
                line={"color": line_color, "width": 2},
                fill="tozeroy",
                fillcolor=f"rgba(59,130,246,0.06)",
                hovertemplate="Sahm: %{y:.2f} pp<br>%{x|%b %Y}<extra></extra>",
            ))

            layout = get_base_layout("Indicador de Sahm — Señal de Recesión (pp)", height=340)
            layout.update({
                "yaxis": {**layout.get("yaxis", {}), "title": "pp sobre mínimo 12m"},
                "xaxis": {
                    **layout.get("xaxis", {}),
                    "rangeselector": get_time_range_buttons(),
                    "rangeslider": {"visible": False},
                },
            })
            fig.update_layout(**layout)
            sahm_chart = dcc.Graph(figure=fig, config={"displayModeBar": False})
        else:
            sahm_chart = create_empty_state(
                "Serie histórica de Sahm no disponible",
                "Se necesitan al menos 15 meses de datos de desempleo.",
            )

        return html.Div([semaphore, sahm_chart])
    except Exception as exc:
        logger.warning("_build_sahm_panel: %s", exc)
        return create_empty_state("Error calculando el indicador de Sahm")


def _build_composition_panel() -> html.Div:
    """Panel de composición del desempleo: corto, largo plazo, juvenil."""
    cards = []

    metrics = [
        (ID_SHORT_UNEMP_US, "DESEMPLEO CORTO PLAZO", "< 27 semanas · miles de personas"),
        (ID_LONG_UNEMP_US, "DESEMPLEO LARGO PLAZO", "≥ 27 semanas · miles de personas"),
        (ID_YOUTH_UNEMP_US, "DESEMPLEO JUVENIL EE.UU.", "% 15-24 años"),
    ]

    for series_id, title, subtitle in metrics:
        try:
            val, ts = get_latest_value(series_id)
            if val is not None:
                # Determinar formato
                if "unemp_us" in series_id and series_id.endswith("_us") and "youth" not in series_id:
                    val_str = f"{val:,.0f}K"
                elif "youth" in series_id:
                    val_str = f"{val:.1f}%"
                else:
                    val_str = f"{val:,.0f}K"
                time_str = time_ago(ts) if ts else "—"
                cards.append(html.Div([
                    html.Div(title, style={
                        "fontSize": "0.65rem", "color": COLORS["text_label"],
                        "fontWeight": "600", "letterSpacing": "0.07em", "marginBottom": "6px",
                    }),
                    html.Div(val_str, style={
                        "fontSize": "1.40rem", "fontWeight": "700", "color": COLORS["text"],
                    }),
                    html.Div(subtitle, style={
                        "fontSize": "0.70rem", "color": COLORS["text_muted"], "marginTop": "4px",
                    }),
                    html.Div(f"Actualiz. {time_str}", style={
                        "fontSize": "0.65rem", "color": COLORS["text_label"], "marginTop": "2px",
                    }),
                ], style={
                    "background": COLORS["card_bg"],
                    "border": f"1px solid {COLORS['border']}",
                    "borderRadius": "8px", "padding": "16px 18px",
                    "flex": "1", "minWidth": "160px",
                }))
            else:
                cards.append(html.Div([
                    html.Div(title, style={"fontSize": "0.65rem", "color": COLORS["text_label"], "fontWeight": "600"}),
                    html.Div("Sin datos", style={"fontSize": "1rem", "color": COLORS["text_muted"], "marginTop": "8px"}),
                    html.Div(subtitle, style={"fontSize": "0.70rem", "color": COLORS["text_muted"], "marginTop": "4px"}),
                ], style={
                    "background": COLORS["card_bg"],
                    "border": f"1px solid {COLORS['border']}",
                    "borderRadius": "8px", "padding": "16px 18px",
                    "flex": "1", "minWidth": "160px",
                }))
        except Exception:
            cards.append(html.Div(
                create_empty_state(title, "Error"),
                style={"flex": "1", "minWidth": "160px"},
            ))

    return html.Div(cards, style={
        "display": "flex", "gap": "12px", "flexWrap": "wrap",
        "marginTop": "8px",
    })


def _build_usa_cards() -> html.Div:
    """Grid de 6 tarjetas de métricas para el mercado laboral EE.UU."""
    card_defs = [
        {
            "id": ID_UNEMP_US, "title": "UNRATE",
            "subtitle": "Tasa de desempleo mensual", "fmt": ".1f", "suffix": "%",
            "period_days": 40, "higher_bad": True,
        },
        {
            "id": ID_NFP_US, "title": "NFP (nivel)",
            "subtitle": "Total empleados no agrícolas (miles)", "fmt": ",.0f", "suffix": "K",
            "period_days": None,
        },
        {
            "id": ID_PARTIC_US, "title": "PARTICIPACIÓN LABORAL",
            "subtitle": "% población activa sobre total", "fmt": ".1f", "suffix": "%",
            "period_days": None,
        },
        {
            "id": None, "title": "JOLTS",
            "subtitle": "Vacantes laborales — sin datos en DB",
        },
        {
            "id": ID_WAGES_US, "title": "SALARIO HORA",
            "subtitle": "USD/hora · promedio trabajadores no sup.", "fmt": ".2f", "suffix": "$/h",
            "period_days": None, "higher_bad": False,
        },
        {
            "id": ID_YOUTH_UNEMP_US, "title": "DESEMPLEO JUVENIL",
            "subtitle": "% desempleo 15-24 años", "fmt": ".1f", "suffix": "%",
            "period_days": None, "higher_bad": True,
        },
    ]

    cards = []
    for defn in card_defs:
        try:
            if defn.get("id") is None:
                # JOLTS: empty state
                cards.append(html.Div([
                    html.Div(defn["title"], style={
                        "fontSize": "0.65rem", "color": COLORS["text_label"],
                        "fontWeight": "600", "letterSpacing": "0.07em", "marginBottom": "6px",
                    }),
                    html.Div("N/D", style={
                        "fontSize": "1.40rem", "fontWeight": "700", "color": COLORS["text_muted"],
                    }),
                    html.Div(defn["subtitle"], style={
                        "fontSize": "0.70rem", "color": COLORS["text_muted"], "marginTop": "4px",
                    }),
                ], style={
                    "background": COLORS["card_bg"],
                    "border": f"1px solid {COLORS['border']}",
                    "borderRadius": "8px", "padding": "16px 18px",
                }))
                continue

            val, ts = get_latest_value(defn["id"])
            if val is None:
                cards.append(html.Div([
                    html.Div(defn["title"], style={"fontSize": "0.65rem", "color": COLORS["text_label"], "fontWeight": "600"}),
                    html.Div("—", style={"fontSize": "1.40rem", "color": COLORS["text_muted"], "marginTop": "6px"}),
                    html.Div(defn["subtitle"], style={"fontSize": "0.70rem", "color": COLORS["text_muted"], "marginTop": "4px"}),
                ], style={
                    "background": COLORS["card_bg"], "border": f"1px solid {COLORS['border']}",
                    "borderRadius": "8px", "padding": "16px 18px",
                }))
                continue

            fmt = defn.get("fmt", ".2f")
            suffix = defn.get("suffix", "")
            try:
                val_str = f"{val:{fmt}}{suffix}"
            except Exception:
                val_str = f"{val}{suffix}"

            # Cambio si aplica
            chg_el = html.Div()
            if defn.get("period_days") is not None:
                _, _, chg, _ = get_change(defn["id"], period_days=defn["period_days"])
                if chg is not None:
                    higher_bad = defn.get("higher_bad", True)
                    color = _change_color(chg, higher_bad)
                    chg_el = html.Div(
                        f"{_arrow(chg)} {abs(chg):.2f} vs periodo ant.",
                        style={"fontSize": "0.72rem", "color": color, "marginTop": "4px"},
                    )

            time_str = time_ago(ts) if ts else ""
            cards.append(html.Div([
                html.Div(defn["title"], style={
                    "fontSize": "0.65rem", "color": COLORS["text_label"],
                    "fontWeight": "600", "letterSpacing": "0.07em", "marginBottom": "6px",
                }),
                html.Div(val_str, style={
                    "fontSize": "1.40rem", "fontWeight": "700", "color": COLORS["text"],
                }),
                html.Div(defn["subtitle"], style={
                    "fontSize": "0.70rem", "color": COLORS["text_muted"], "marginTop": "4px",
                }),
                chg_el,
                html.Div(f"Actualiz. {time_str}", style={
                    "fontSize": "0.65rem", "color": COLORS["text_label"], "marginTop": "2px",
                }),
            ], style={
                "background": COLORS["card_bg"],
                "border": f"1px solid {COLORS['border']}",
                "borderRadius": "8px", "padding": "16px 18px",
            }))
        except Exception:
            cards.append(html.Div(
                create_empty_state(defn.get("title", "?"), "Error"),
            ))

    return html.Div(cards, style={
        "display": "grid",
        "gridTemplateColumns": "repeat(auto-fill, minmax(200px, 1fr))",
        "gap": "12px",
    })


def _build_europe_comparison() -> go.Figure:
    """Comparativa europea multi-país con datos WB anuales."""
    fig = go.Figure()
    euro_styles = {
        "ESP": {"color": COUNTRY_COLORS["ESP"], "width": 3},
        "DEU": {"color": COUNTRY_COLORS["DEU"], "width": 2},
        "FRA": {"color": COUNTRY_COLORS.get("FRA", "#8b5cf6"), "width": 2},
        "ITA": {"color": COUNTRY_COLORS["ITA"], "width": 2},
        "GBR": {"color": COUNTRY_COLORS["GBR"], "width": 2},
        "GRC": {"color": "#ec4899", "width": 2},
        "PRT": {"color": "#f97316", "width": 2},
        "POL": {"color": "#06b6d4", "width": 1.5},
        "SWE": {"color": "#84cc16", "width": 1.5},
    }

    has_data = False
    for iso3, style in euro_styles.items():
        try:
            series_id = f"wb_unemployment_{iso3.lower()}"
            df = get_series(series_id, days=365 * 30)
            if df.empty:
                continue
            df = df.sort_values("timestamp")
            fig.add_trace(go.Scatter(
                x=df["timestamp"],
                y=df["value"],
                name=ISO3_NAMES.get(iso3, iso3),
                line={"color": style["color"], "width": style["width"]},
                mode="lines+markers",
                marker={"size": 4},
                hovertemplate=f"{ISO3_NAMES.get(iso3, iso3)}: %{{y:.1f}}%<br>%{{x|%Y}}<extra></extra>",
            ))
            has_data = True
        except Exception:
            continue

    if not has_data:
        fig.add_annotation(
            text="Sin datos disponibles para los países europeos",
            xref="paper", yref="paper", x=0.5, y=0.5,
            showarrow=False, font={"color": COLORS["text_muted"], "size": 14},
        )

    layout = get_base_layout("Tasa de Desempleo — Europa y EE.UU. (%)", height=400)
    layout.update({
        "yaxis": {**layout.get("yaxis", {}), "title": "% desempleo"},
        "hovermode": "x unified",
    })
    fig.update_layout(**layout)
    return fig


def _build_spain_panel() -> html.Div:
    """Métricas rápidas de España."""
    items = []
    metrics_esp = [
        (ID_WB_UNEMP_ESP, "DESEMPLEO TOTAL", ".1f", "%"),
        ("wb_youth_unemp_esp", "DESEMPLEO JUVENIL", ".1f", "%"),
    ]
    for sid, label, fmt, suffix in metrics_esp:
        try:
            val, ts = get_latest_value(sid)
            val_str = f"{val:{fmt}}{suffix}" if val is not None else "—"
            color = _unemp_color(val) if val is not None else COLORS["text_muted"]
            items.append(html.Div([
                html.Div(label, style={"fontSize": "0.65rem", "color": COLORS["text_label"], "fontWeight": "600"}),
                html.Div(val_str, style={"fontSize": "1.40rem", "fontWeight": "700", "color": color}),
                html.Div(f"Actualiz. {time_ago(ts)}" if ts else "", style={"fontSize": "0.65rem", "color": COLORS["text_label"]}),
            ], style={
                "background": COLORS["card_bg"], "border": f"1px solid {COLORS['border']}",
                "borderRadius": "8px", "padding": "14px 18px", "flex": "1", "minWidth": "140px",
            }))
        except Exception:
            pass

    # Pico histórico (anotado)
    items.append(html.Div([
        html.Div("PICO HISTÓRICO", style={"fontSize": "0.65rem", "color": COLORS["text_label"], "fontWeight": "600"}),
        html.Div("~26%", style={"fontSize": "1.40rem", "fontWeight": "700", "color": COLORS["red"]}),
        html.Div("2013 — crisis deuda eurozona", style={"fontSize": "0.65rem", "color": COLORS["text_label"]}),
    ], style={
        "background": COLORS["card_bg"], "border": f"1px solid {COLORS['border']}",
        "borderRadius": "8px", "padding": "14px 18px", "flex": "1", "minWidth": "140px",
    }))

    return html.Div(items, style={
        "display": "flex", "gap": "12px", "flexWrap": "wrap",
        "marginBottom": "16px",
    })


def _build_spain_vs_emu() -> go.Figure:
    """Gráfico España vs Eurozona (datos WB anuales)."""
    try:
        df_esp = get_series(ID_WB_UNEMP_ESP, days=365 * 30)
        df_emu = get_series(ID_WB_UNEMP_EMU, days=365 * 30)

        fig = go.Figure()

        if not df_esp.empty:
            df_esp = df_esp.sort_values("timestamp")
            fig.add_trace(go.Scatter(
                x=df_esp["timestamp"],
                y=df_esp["value"],
                name="España",
                line={"color": COUNTRY_COLORS["ESP"], "width": 3},
                fill="tozeroy",
                fillcolor="rgba(245,158,11,0.05)",
                hovertemplate="España: %{y:.1f}%<br>%{x|%Y}<extra></extra>",
            ))

        if not df_emu.empty:
            df_emu = df_emu.sort_values("timestamp")
            fig.add_trace(go.Scatter(
                x=df_emu["timestamp"],
                y=df_emu["value"],
                name="Eurozona",
                line={"color": COUNTRY_COLORS["DEU"], "width": 2, "dash": "dash"},
                hovertemplate="Eurozona: %{y:.1f}%<br>%{x|%Y}<extra></extra>",
            ))

        # Si tenemos ambas series, calcular prima/diferencial
        if not df_esp.empty and not df_emu.empty:
            df_merge = df_esp.rename(columns={"value": "esp"}).merge(
                df_emu.rename(columns={"value": "emu"}),
                on="timestamp", how="inner"
            )
            if not df_merge.empty:
                df_merge["premium"] = df_merge["esp"] - df_merge["emu"]
                fig.add_trace(go.Scatter(
                    x=df_merge["timestamp"],
                    y=df_merge["premium"],
                    name="Prima España vs EMU",
                    line={"color": COLORS["orange"], "width": 1.5, "dash": "dot"},
                    fill="tozeroy",
                    fillcolor="rgba(249,115,22,0.06)",
                    yaxis="y2",
                    hovertemplate="Prima: %{y:.1f} pp<br>%{x|%Y}<extra></extra>",
                ))

        if df_esp.empty and df_emu.empty:
            fig.add_annotation(
                text="Sin datos disponibles",
                xref="paper", yref="paper", x=0.5, y=0.5,
                showarrow=False, font={"color": COLORS["text_muted"], "size": 14},
            )

        layout = get_base_layout("España vs Eurozona — Tasa de Desempleo (%)", height=360)
        layout.update({
            "yaxis": {**layout.get("yaxis", {}), "title": "% desempleo"},
            "yaxis2": {
                "title": "Prima (pp)", "overlaying": "y", "side": "right",
                "gridcolor": "#1f2937", "tickfont": {"color": "#9ca3af", "size": 10},
                "title_font": {"color": "#9ca3af", "size": 11},
            },
            "hovermode": "x unified",
        })
        fig.update_layout(**layout)
        return fig
    except Exception as exc:
        logger.warning("_build_spain_vs_emu: %s", exc)
        fig = go.Figure()
        fig.update_layout(**get_base_layout("Error cargando datos", height=360))
        return fig


def _build_youth_europe() -> go.Figure:
    """Gráfico de barras de desempleo juvenil europeo."""
    try:
        df = get_world_bank_indicator("youth_unemp")
        euro_iso3 = ["ESP", "GRC", "ITA", "PRT", "FRA", "POL", "SWE", "DEU", "NLD", "NOR", "GBR"]

        if not df.empty:
            df_euro = df[df["country_iso3"].isin(euro_iso3)].copy()
        else:
            df_euro = pd.DataFrame(columns=["country_iso3", "value", "year"])

        if df_euro.empty:
            fig = go.Figure()
            fig.add_annotation(
                text="Sin datos de desempleo juvenil disponibles",
                xref="paper", yref="paper", x=0.5, y=0.5,
                showarrow=False, font={"color": COLORS["text_muted"], "size": 13},
            )
            fig.update_layout(**get_base_layout("Desempleo Juvenil Europa", height=320))
            return fig

        df_euro = df_euro.sort_values("value", ascending=False)
        df_euro["name"] = df_euro["country_iso3"].apply(lambda x: ISO3_NAMES.get(x, x))
        bar_colors = [
            COLORS["red"] if v >= 25 else
            COLORS["orange"] if v >= 15 else
            COLORS["yellow"] if v >= 10 else
            COLORS["green"]
            for v in df_euro["value"]
        ]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=df_euro["name"],
            y=df_euro["value"],
            marker_color=bar_colors,
            text=[f"{v:.1f}%" for v in df_euro["value"]],
            textposition="outside",
            textfont={"color": COLORS["text_muted"], "size": 11},
            hovertemplate="%{x}: %{y:.1f}%<extra></extra>",
        ))

        fig.add_hline(y=15, line_dash="dot", line_color=COLORS["orange"],
                      annotation_text="15% umbral crítico",
                      annotation_font_color=COLORS["orange"], annotation_font_size=10)

        layout = get_base_layout("Desempleo Juvenil por País (%)", height=320)
        layout.update({
            "yaxis": {**layout.get("yaxis", {}), "title": "% jóvenes 15-24 sin empleo"},
            "bargap": 0.3,
        })
        fig.update_layout(**layout)
        return fig
    except Exception as exc:
        logger.warning("_build_youth_europe: %s", exc)
        fig = go.Figure()
        fig.update_layout(**get_base_layout("Error cargando datos", height=320))
        return fig


def _build_labor_participation() -> go.Figure:
    """Participación laboral multi-país WB."""
    fig = go.Figure()
    part_countries = {
        "USA": COUNTRY_COLORS["USA"],
        "DEU": COUNTRY_COLORS["DEU"],
        "ESP": COUNTRY_COLORS["ESP"],
        "JPN": COUNTRY_COLORS["JPN"],
        "SWE": "#84cc16",
        "NOR": "#06b6d4",
        "GBR": COUNTRY_COLORS["GBR"],
    }

    has_data = False
    for iso3, color in part_countries.items():
        try:
            series_id = f"wb_labor_force_pct_{iso3.lower()}"
            df = get_series(series_id, days=365 * 30)
            if df.empty:
                continue
            df = df.sort_values("timestamp")
            fig.add_trace(go.Scatter(
                x=df["timestamp"],
                y=df["value"],
                name=ISO3_NAMES.get(iso3, iso3),
                line={"color": color, "width": 2},
                mode="lines+markers",
                marker={"size": 4},
                hovertemplate=f"{ISO3_NAMES.get(iso3, iso3)}: %{{y:.1f}}%<br>%{{x|%Y}}<extra></extra>",
            ))
            has_data = True
        except Exception:
            continue

    if not has_data:
        fig.add_annotation(
            text="Sin datos de participación laboral disponibles",
            xref="paper", yref="paper", x=0.5, y=0.5,
            showarrow=False, font={"color": COLORS["text_muted"], "size": 14},
        )

    layout = get_base_layout("Participación en la Fuerza Laboral (%)", height=380)
    layout.update({
        "yaxis": {**layout.get("yaxis", {}), "title": "% población activa"},
        "hovermode": "x unified",
    })
    fig.update_layout(**layout)
    return fig


def _build_productivity_chart() -> go.Figure:
    """Productividad laboral multi-país WB."""
    fig = go.Figure()
    prod_countries = {
        "USA": COUNTRY_COLORS["USA"],
        "DEU": COUNTRY_COLORS["DEU"],
        "FRA": COUNTRY_COLORS.get("FRA", "#8b5cf6"),
        "ESP": COUNTRY_COLORS["ESP"],
        "GBR": COUNTRY_COLORS["GBR"],
        "JPN": COUNTRY_COLORS["JPN"],
        "KOR": "#ec4899",
        "CHN": COUNTRY_COLORS.get("CHN", "#f97316"),
    }

    has_data = False
    for iso3, color in prod_countries.items():
        try:
            series_id = f"wb_labor_product_{iso3.lower()}"
            df = get_series(series_id, days=365 * 30)
            if df.empty:
                continue
            df = df.sort_values("timestamp")
            fig.add_trace(go.Scatter(
                x=df["timestamp"],
                y=df["value"],
                name=ISO3_NAMES.get(iso3, iso3),
                line={"color": color, "width": 2},
                mode="lines+markers",
                marker={"size": 4},
                hovertemplate=f"{ISO3_NAMES.get(iso3, iso3)}: $%{{y:,.0f}}<br>%{{x|%Y}}<extra></extra>",
            ))
            has_data = True
        except Exception:
            continue

    if not has_data:
        fig.add_annotation(
            text="Sin datos de productividad disponibles",
            xref="paper", yref="paper", x=0.5, y=0.5,
            showarrow=False, font={"color": COLORS["text_muted"], "size": 14},
        )

    layout = get_base_layout("Productividad Laboral — PIB por trabajador (USD PPP)", height=380)
    layout.update({
        "yaxis": {**layout.get("yaxis", {}), "title": "USD PPP por trabajador"},
        "hovermode": "x unified",
    })
    fig.update_layout(**layout)
    return fig


def _build_workforce_dynamics() -> go.Figure:
    """Dinámica de la fuerza laboral (participación) por países clave."""
    fig = go.Figure()
    dynamic_countries = {
        "USA": COUNTRY_COLORS["USA"],
        "CHN": COUNTRY_COLORS.get("CHN", "#f97316"),
        "IND": "#84cc16",
        "JPN": COUNTRY_COLORS["JPN"],
        "DEU": COUNTRY_COLORS["DEU"],
    }

    has_data = False
    for iso3, color in dynamic_countries.items():
        try:
            series_id = f"wb_labor_force_pct_{iso3.lower()}"
            df = get_series(series_id, days=365 * 30)
            if df.empty:
                continue
            df = df.sort_values("timestamp")
            fig.add_trace(go.Scatter(
                x=df["timestamp"],
                y=df["value"],
                name=ISO3_NAMES.get(iso3, iso3),
                line={"color": color, "width": 2},
                mode="lines+markers",
                marker={"size": 4},
                hovertemplate=f"{ISO3_NAMES.get(iso3, iso3)}: %{{y:.1f}}%<br>%{{x|%Y}}<extra></extra>",
            ))
            has_data = True
        except Exception:
            continue

    if not has_data:
        fig.add_annotation(
            text="Sin datos disponibles",
            xref="paper", yref="paper", x=0.5, y=0.5,
            showarrow=False, font={"color": COLORS["text_muted"], "size": 14},
        )

    layout = get_base_layout("Participación Laboral — Economías Clave (%)", height=360)
    layout.update({
        "yaxis": {**layout.get("yaxis", {}), "title": "% población activa"},
        "hovermode": "x unified",
    })
    fig.update_layout(**layout)
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# LAYOUT PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

def render_module_6() -> html.Div:
    return html.Div(
        [
            dcc.Interval(id="m6-refresh-interval", interval=300_000, n_intervals=0),

            # Cabecera del módulo
            html.Div([
                html.Div("Mercado Laboral", className="module-title"),
                html.Div(
                    "Desempleo global · NFP · Sahm · Participación laboral · Productividad",
                    className="module-subtitle",
                ),
            ]),

            # Métricas de cabecera
            _build_header_metrics(),

            # Tabs
            dcc.Tabs(
                [
                    dcc.Tab(
                        label="Visión Global",
                        value="tab-global",
                        children=_build_tab_global(),
                        style=TAB_STYLE,
                        selected_style=TAB_SELECTED_STYLE,
                    ),
                    dcc.Tab(
                        label="EE.UU. en Detalle",
                        value="tab-usa",
                        children=_build_tab_usa(),
                        style=TAB_STYLE,
                        selected_style=TAB_SELECTED_STYLE,
                    ),
                    dcc.Tab(
                        label="Europa en Detalle",
                        value="tab-europe",
                        children=_build_tab_europe(),
                        style=TAB_STYLE,
                        selected_style=TAB_SELECTED_STYLE,
                    ),
                    dcc.Tab(
                        label="Tendencias Estructurales",
                        value="tab-structural",
                        children=_build_tab_structural(),
                        style=TAB_STYLE,
                        selected_style=TAB_SELECTED_STYLE,
                    ),
                ],
                id="m6-tabs",
                value="tab-global",
                style=TABS_STYLE,
                colors={
                    "border": COLORS["border"],
                    "primary": COLORS["accent"],
                    "background": COLORS["card_bg"],
                },
            ),
        ],
        className="module-content",
    )


# ══════════════════════════════════════════════════════════════════════════════
# CALLBACKS
# ══════════════════════════════════════════════════════════════════════════════

def register_callbacks_module_6(app) -> None:

    # ── Tab Global: Mapa coroplético ────────────────────────────────────────────
    @app.callback(
        Output("m6-choropleth-map", "figure"),
        Input("m6-map-indicator", "value"),
        prevent_initial_call=False,
    )
    def update_choropleth(indicator):
        try:
            return _build_choropleth_map(indicator or "unemployment")
        except Exception as exc:
            logger.error("update_choropleth: %s", exc)
            fig = go.Figure()
            fig.update_layout(**get_base_layout("Error cargando mapa", height=480))
            return fig

    # ── Tab Global: Rankings ───────────────────────────────────────────────────
    @app.callback(
        Output("m6-ranking-high", "children"),
        Output("m6-ranking-low", "children"),
        Input("m6-refresh-interval", "n_intervals"),
        prevent_initial_call=False,
    )
    def update_rankings(n):
        try:
            df = get_world_bank_indicator("unemployment")
            return (
                _build_ranking_table(df, top_high=True),
                _build_ranking_table(df, top_high=False),
            )
        except Exception as exc:
            logger.error("update_rankings: %s", exc)
            empty = create_empty_state("Error al cargar rankings")
            return empty, empty

    # ── Tab Global: Comparativa histórica ─────────────────────────────────────
    @app.callback(
        Output("m6-hist-comparison", "figure"),
        Input("m6-refresh-interval", "n_intervals"),
        prevent_initial_call=False,
    )
    def update_hist_comparison(n):
        try:
            return _build_hist_comparison_chart()
        except Exception as exc:
            logger.error("update_hist_comparison: %s", exc)
            fig = go.Figure()
            fig.update_layout(**get_base_layout("Error", height=400))
            return fig

    # ── Tab EE.UU.: Cards métricas ─────────────────────────────────────────────
    @app.callback(
        Output("m6-usa-cards", "children"),
        Input("m6-refresh-interval", "n_intervals"),
        prevent_initial_call=False,
    )
    def update_usa_cards(n):
        try:
            return _build_usa_cards()
        except Exception as exc:
            logger.error("update_usa_cards: %s", exc)
            return create_empty_state("Error al cargar métricas")

    # ── Tab EE.UU.: Histórico desempleo ────────────────────────────────────────
    @app.callback(
        Output("m6-unemp-history", "figure"),
        Input("m6-refresh-interval", "n_intervals"),
        prevent_initial_call=False,
    )
    def update_unemp_history(n):
        try:
            return _build_unemp_history_chart()
        except Exception as exc:
            logger.error("update_unemp_history: %s", exc)
            fig = go.Figure()
            fig.update_layout(**get_base_layout("Error", height=380))
            return fig

    # ── Tab EE.UU.: NFP section ────────────────────────────────────────────────
    @app.callback(
        Output("m6-nfp-section", "children"),
        Input("m6-refresh-interval", "n_intervals"),
        prevent_initial_call=False,
    )
    def update_nfp_section(n):
        try:
            return _build_nfp_section()
        except Exception as exc:
            logger.error("update_nfp_section: %s", exc)
            return create_empty_state("Error al cargar datos NFP")

    # ── Tab EE.UU.: Initial claims ─────────────────────────────────────────────
    @app.callback(
        Output("m6-claims-chart", "figure"),
        Input("m6-refresh-interval", "n_intervals"),
        prevent_initial_call=False,
    )
    def update_claims(n):
        try:
            return _build_claims_chart()
        except Exception as exc:
            logger.error("update_claims: %s", exc)
            fig = go.Figure()
            fig.update_layout(**get_base_layout("Error", height=300))
            return fig

    # ── Tab EE.UU.: Sahm panel ─────────────────────────────────────────────────
    @app.callback(
        Output("m6-sahm-panel", "children"),
        Input("m6-refresh-interval", "n_intervals"),
        prevent_initial_call=False,
    )
    def update_sahm_panel(n):
        try:
            return _build_sahm_panel()
        except Exception as exc:
            logger.error("update_sahm_panel: %s", exc)
            return create_empty_state("Error al calcular el indicador de Sahm")

    # ── Tab EE.UU.: Composición desempleo ──────────────────────────────────────
    @app.callback(
        Output("m6-composition-panel", "children"),
        Input("m6-refresh-interval", "n_intervals"),
        prevent_initial_call=False,
    )
    def update_composition(n):
        try:
            return _build_composition_panel()
        except Exception as exc:
            logger.error("update_composition: %s", exc)
            return create_empty_state("Error al cargar composición del desempleo")

    # ── Tab Europa: Comparativa ────────────────────────────────────────────────
    @app.callback(
        Output("m6-europe-comparison", "figure"),
        Input("m6-refresh-interval", "n_intervals"),
        prevent_initial_call=False,
    )
    def update_europe_comparison(n):
        try:
            return _build_europe_comparison()
        except Exception as exc:
            logger.error("update_europe_comparison: %s", exc)
            fig = go.Figure()
            fig.update_layout(**get_base_layout("Error", height=400))
            return fig

    # ── Tab Europa: Panel España ───────────────────────────────────────────────
    @app.callback(
        Output("m6-spain-panel", "children"),
        Input("m6-refresh-interval", "n_intervals"),
        prevent_initial_call=False,
    )
    def update_spain_panel(n):
        try:
            return _build_spain_panel()
        except Exception as exc:
            logger.error("update_spain_panel: %s", exc)
            return create_empty_state("Error al cargar datos de España")

    # ── Tab Europa: España vs EMU ─────────────────────────────────────────────
    @app.callback(
        Output("m6-spain-vs-emu", "figure"),
        Input("m6-refresh-interval", "n_intervals"),
        prevent_initial_call=False,
    )
    def update_spain_emu(n):
        try:
            return _build_spain_vs_emu()
        except Exception as exc:
            logger.error("update_spain_emu: %s", exc)
            fig = go.Figure()
            fig.update_layout(**get_base_layout("Error", height=360))
            return fig

    # ── Tab Europa: Desempleo juvenil europeo ──────────────────────────────────
    @app.callback(
        Output("m6-youth-europe", "figure"),
        Input("m6-refresh-interval", "n_intervals"),
        prevent_initial_call=False,
    )
    def update_youth_europe(n):
        try:
            return _build_youth_europe()
        except Exception as exc:
            logger.error("update_youth_europe: %s", exc)
            fig = go.Figure()
            fig.update_layout(**get_base_layout("Error", height=320))
            return fig

    # ── Tab Estructural: Participación laboral ─────────────────────────────────
    @app.callback(
        Output("m6-labor-participation", "figure"),
        Input("m6-refresh-interval", "n_intervals"),
        prevent_initial_call=False,
    )
    def update_labor_participation(n):
        try:
            return _build_labor_participation()
        except Exception as exc:
            logger.error("update_labor_participation: %s", exc)
            fig = go.Figure()
            fig.update_layout(**get_base_layout("Error", height=380))
            return fig

    # ── Tab Estructural: Productividad ────────────────────────────────────────
    @app.callback(
        Output("m6-productivity", "figure"),
        Input("m6-refresh-interval", "n_intervals"),
        prevent_initial_call=False,
    )
    def update_productivity(n):
        try:
            return _build_productivity_chart()
        except Exception as exc:
            logger.error("update_productivity: %s", exc)
            fig = go.Figure()
            fig.update_layout(**get_base_layout("Error", height=380))
            return fig

    # ── Tab Estructural: Dinámica fuerza laboral ──────────────────────────────
    @app.callback(
        Output("m6-workforce-dynamics", "figure"),
        Input("m6-refresh-interval", "n_intervals"),
        prevent_initial_call=False,
    )
    def update_workforce_dynamics(n):
        try:
            return _build_workforce_dynamics()
        except Exception as exc:
            logger.error("update_workforce_dynamics: %s", exc)
            fig = go.Figure()
            fig.update_layout(**get_base_layout("Error", height=360))
            return fig
