"""
Modulo 10 - Geopolitica y Riesgos Globales
Se renderiza cuando la URL es /module/10.

Exporta:
  render_module_10()                -> layout completo
  register_callbacks_module_10(app) -> registra todos los callbacks
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, State, dcc, html, no_update

from components.chart_config import get_base_layout, get_time_range_buttons
from components.common import create_section_header
from config import COLORS
from modules.data_helpers import (
    get_latest_value,
    get_series,
    get_latest_news,
    get_geopolitical_events,
    load_json_data,
    get_conflict_asset_impact,
    calculate_gpr_percentile,
)

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

# ── IDs de indicadores GPR ────────────────────────────────────────────────────

ID_GPR_GLOBAL  = "fred_gpr_gprc"       # GPR global (desde 1985)
ID_GPR_HIST    = "fred_gpr_gprh"       # GPR histórico (desde 1900)
ID_GPR_USA     = "fred_gpr_gprc_usa"
ID_GPR_CHN     = "fred_gpr_gprc_chn"
ID_GPR_RUS     = "fred_gpr_gprc_rus"
ID_GPR_DEU     = "fred_gpr_gprc_deu"
ID_GPR_ISR     = "fred_gpr_gprc_isr"   # proxy Irán/Oriente Medio
ID_SP500       = "yf_sp500_close"
ID_BRENT       = "yf_bz_close"

# ── Estilos compartidos ───────────────────────────────────────────────────────

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
_SECTION = {"padding": "16px"}
_CARD = {
    "background": COLORS["card_bg"],
    "border": f"1px solid {COLORS['border']}",
    "borderRadius": "6px",
    "padding": "14px 16px",
    "marginBottom": "12px",
}
_NOTE = {
    "fontSize": "0.75rem",
    "color": COLORS["text_muted"],
    "fontStyle": "italic",
    "lineHeight": "1.5",
    "padding": "8px 12px",
    "background": "#0d1320",
    "borderLeft": f"3px solid {COLORS['accent']}",
    "borderRadius": "0 4px 4px 0",
    "marginTop": "8px",
}

# Banderas por código ISO-3
_FLAGS3 = {
    "USA": "🇺🇸", "RUS": "🇷🇺", "CHN": "🇨🇳", "DEU": "🇩🇪",
    "IRN": "🚩",  "ISR": "🇮🇱", "UKR": "🇺🇦", "GBR": "🇬🇧",
    "FRA": "🇫🇷", "JPN": "🇯🇵", "IND": "🇮🇳", "BRA": "🇧🇷",
    "SAU": "🇸🇦", "TWN": "🇹🇼", "PRK": "🇰🇵", "KOR": "🇰🇷",
    "AUS": "🇦🇺", "CAN": "🇨🇦", "EU":  "🇪🇺", "EU27": "🇪🇺",
    "G7":  "🌐",  "OPEC": "🛢️",
}

# Colores semáforo GPR
_GPR_SEMAPHORE_COLOR = {
    "green":  COLORS["green"],
    "yellow": COLORS["yellow"],
    "orange": COLORS["orange"],
    "red":    COLORS["red"],
    "gray":   COLORS["text_label"],
}

# Colores nivel de riesgo
_RISK_COLORS = {
    "critical": COLORS["red"],
    "high":     COLORS["orange"],
    "medium":   COLORS["yellow"],
    "low":      COLORS["green"],
}

# Colores escenario
_SCENARIO_COLORS = {
    "positive": COLORS["green"],
    "neutral":  COLORS["text_muted"],
    "negative": COLORS["orange"],
    "critical": COLORS["red"],
}


# ── Helpers internos ──────────────────────────────────────────────────────────

def _rgba(hex_color: str, alpha: float = 0.12) -> str:
    """Convierte un color hex a rgba() compatible con Plotly."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def _safe(val, fmt=".1f", suffix="", none_str="—") -> str:
    if val is None:
        return none_str
    try:
        return f"{val:{fmt}}{suffix}"
    except Exception:
        return none_str


def _empty_fig(msg: str = "Sin datos disponibles", height: int = 350) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        **get_base_layout(height=height),
        annotations=[{
            "text": msg, "xref": "paper", "yref": "paper",
            "x": 0.5, "y": 0.5, "showarrow": False,
            "font": {"color": COLORS["text_muted"], "size": 13},
        }],
    )
    return fig


def _gpr_level(value: Optional[float]) -> str:
    """Devuelve nivel semáforo para un valor GPR."""
    if value is None:
        return "gray"
    if value < 100:
        return "green"
    if value < 150:
        return "yellow"
    if value < 200:
        return "orange"
    return "red"


def _gpr_label(value: Optional[float]) -> str:
    """Texto del nivel GPR."""
    level = _gpr_level(value)
    labels = {
        "green": "Bajo", "yellow": "Moderado",
        "orange": "Alto", "red": "Crítico", "gray": "—",
    }
    return labels[level]


def _risk_color(level: str) -> str:
    return _RISK_COLORS.get(level, COLORS["text_label"])


def _compact_metric(
    title: str,
    value_str: str,
    sub_str: str,
    sub_color: str,
    badge: Optional[html.Span] = None,
) -> html.Div:
    children = [
        html.Div(title, style={
            "fontSize": "0.60rem", "color": COLORS["text_label"],
            "fontWeight": "600", "letterSpacing": "0.08em", "marginBottom": "2px",
        }),
        html.Div(
            [html.Span(value_str), badge] if badge else value_str,
            style={"fontSize": "1.05rem", "fontWeight": "700", "color": COLORS["text"],
                   "lineHeight": "1.1", "display": "flex", "alignItems": "center", "gap": "6px"},
        ),
        html.Div(sub_str, style={
            "fontSize": "0.72rem", "color": sub_color, "marginTop": "2px",
        }),
    ]
    return html.Div(children, style={
        "background": COLORS["card_bg"],
        "border": f"1px solid {COLORS['border']}",
        "borderRadius": "6px",
        "padding": "10px 14px",
        "flex": "1",
        "minWidth": "130px",
    })


def _gpr_metric_card(
    label: str,
    value: Optional[float],
    country_code: Optional[str] = None,
) -> html.Div:
    level = _gpr_level(value)
    color = _GPR_SEMAPHORE_COLOR[level]
    val_str = _safe(value, ".0f") if value else "—"
    flag = _FLAGS3.get(country_code or "", "") + " " if country_code else ""
    sub_label = _gpr_label(value)

    dot = html.Div(style={
        "width": "10px", "height": "10px",
        "borderRadius": "50%", "backgroundColor": color,
        "boxShadow": f"0 0 6px {color}80",
        "flexShrink": "0",
    })
    return _compact_metric(
        title=f"{flag}{label}",
        value_str=val_str,
        sub_str=sub_label,
        sub_color=color,
        badge=dot,
    )


def _flag_badges(countries: list) -> list:
    """Devuelve una lista de html.Span con banderas."""
    badges = []
    for c in countries:
        flag = _FLAGS3.get(c, "")
        badges.append(
            html.Span(
                f"{flag} {c}",
                style={
                    "fontSize": "0.7rem", "background": "#1f2937",
                    "borderRadius": "3px", "padding": "2px 6px",
                    "marginRight": "4px", "color": COLORS["text_muted"],
                },
            )
        )
    return badges


def _severity_badge(severity: int) -> html.Span:
    colors = {1: COLORS["green"], 2: COLORS["green_yellow"],
              3: COLORS["yellow"], 4: COLORS["orange"], 5: COLORS["red"]}
    labels = {1: "1 Muy bajo", 2: "2 Bajo", 3: "3 Medio", 4: "4 Alto", 5: "5 Crítico"}
    c = colors.get(severity, COLORS["text_muted"])
    return html.Span(
        labels.get(severity, str(severity)),
        style={
            "background": f"{c}22", "color": c,
            "border": f"1px solid {c}55", "borderRadius": "4px",
            "padding": "1px 8px", "fontSize": "0.72rem", "fontWeight": "600",
        },
    )


def _intensity_badge(intensity: str) -> html.Span:
    colors = {"high": COLORS["red"], "medium": COLORS["orange"], "low": COLORS["yellow"]}
    labels = {"high": "Alta", "medium": "Media", "low": "Baja"}
    c = colors.get(intensity, COLORS["text_muted"])
    return html.Span(
        labels.get(intensity, intensity),
        style={
            "background": f"{c}22", "color": c,
            "border": f"1px solid {c}55", "borderRadius": "4px",
            "padding": "1px 8px", "fontSize": "0.72rem",
        },
    )


def _days_since(date_str: str) -> Optional[int]:
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return (datetime.utcnow() - dt).days
    except Exception:
        return None


# ── Sección: Header del módulo ────────────────────────────────────────────────

def _build_header() -> html.Div:
    gpr_global, gpr_ts = get_latest_value(ID_GPR_GLOBAL, source="FRED_GPR")
    gpr_isr,    _      = get_latest_value(ID_GPR_ISR,    source="FRED_GPR")
    gpr_rus,    _      = get_latest_value(ID_GPR_RUS,    source="FRED_GPR")
    gpr_chn,    _      = get_latest_value(ID_GPR_CHN,    source="FRED_GPR")

    # Conflictos activos en BD
    try:
        since_90 = datetime.utcnow() - timedelta(days=90)
        from database.database import SessionLocal, GeopoliticalEvent
        with SessionLocal() as db:
            n_conflicts = (
                db.query(GeopoliticalEvent)
                .filter(
                    GeopoliticalEvent.date >= since_90,
                    GeopoliticalEvent.severity >= 3,
                )
                .count()
            )
    except Exception:
        n_conflicts = 0

    # Número de conflictos del JSON también
    conflicts_data = load_json_data("active_conflicts.json") or {}
    json_conflicts = conflicts_data.get("conflicts", [])
    active_json = sum(1 for c in json_conflicts if c.get("status") in ("active", "ongoing_tension"))
    total_conflicts = n_conflicts + active_json

    ts_str = gpr_ts.strftime("%b %Y") if gpr_ts else "—"

    # Badge de tensión histórica
    crisis_badge = None
    if gpr_global and gpr_global > 200:
        crisis_badge = html.Div(
            "⚠️ TENSIÓN HISTÓRICA — GPR en zona de crisis",
            style={
                "background": f"{COLORS['red']}22",
                "border": f"1px solid {COLORS['red']}66",
                "color": COLORS["red"],
                "borderRadius": "6px",
                "padding": "6px 14px",
                "fontSize": "0.78rem",
                "fontWeight": "700",
                "letterSpacing": "0.05em",
                "marginTop": "8px",
                "display": "inline-block",
            },
        )

    metrics_row = html.Div(
        [
            _gpr_metric_card("GPR Global",  gpr_global, None),
            _gpr_metric_card("GPR ISR/ME",  gpr_isr,   "ISR"),
            _gpr_metric_card("GPR Rusia",   gpr_rus,   "RUS"),
            _gpr_metric_card("GPR China",   gpr_chn,   "CHN"),
            _compact_metric(
                title="Conflictos activos (BD)",
                value_str=str(total_conflicts),
                sub_str="severidad ≥ 3 / últimos 90 días",
                sub_color=COLORS["orange"] if total_conflicts >= 3 else COLORS["text_muted"],
            ),
        ],
        style={
            "display": "flex", "gap": "10px", "flexWrap": "wrap",
            "marginBottom": "12px",
        },
    )

    header_children = [
        html.Div(
            [
                html.Div("🌍 Geopolítica y Riesgos Globales", className="module-title"),
                html.Div(
                    f"Módulo 10 · GPR actualizado: {ts_str} · Fuente: Caldara & Iacoviello",
                    className="module-subtitle",
                ),
            ]
        ),
        metrics_row,
    ]
    if crisis_badge:
        header_children.append(crisis_badge)

    return html.Div(header_children, style={"padding": "16px 16px 8px"})


# ── Tab 1: Mapa de Riesgo Global ──────────────────────────────────────────────

def _build_tab1() -> html.Div:
    return html.Div(
        [
            dcc.Loading(
                dcc.Graph(id="m10-risk-map", config={"displayModeBar": False}, style={"height": "480px"}),
                color=COLORS["accent"],
            ),
            # Panel lateral de detalle de país (oculto por defecto)
            html.Div(
                id="m10-country-detail-panel",
                style={
                    "marginTop": "10px",
                    "background": COLORS["card_bg"],
                    "border": f"1px solid {COLORS['border']}",
                    "borderRadius": "6px",
                    "padding": "14px",
                },
            ),
            html.Hr(style={"borderColor": COLORS["border"], "margin": "16px 0"}),
            create_section_header(
                "Regiones de Alta Tensión",
                "Ordenadas por severidad del conflicto activo más crítico",
            ),
            html.Div(id="m10-tension-regions", style={"marginTop": "10px"}),
        ],
        style=_SECTION,
    )


# ── Tab 2: Conflictos Activos ─────────────────────────────────────────────────

def _build_conflict_dropdown() -> dcc.Dropdown:
    conflicts_data = load_json_data("active_conflicts.json") or {}
    conflicts = conflicts_data.get("conflicts", [])
    options = [
        {"label": f"{'🔴' if c['severity']==5 else '🟠' if c['severity']==4 else '🟡'} {c['title']}", "value": c["id"]}
        for c in conflicts
    ]
    default = conflicts[0]["id"] if conflicts else None
    return dcc.Dropdown(
        id="m10-conflict-selector",
        options=options,
        value=default,
        clearable=False,
        style={
            "backgroundColor": COLORS["card_bg"],
            "color": COLORS["text"],
            "borderColor": COLORS["border"],
            "fontSize": "0.85rem",
        },
    )


def _build_tab2() -> html.Div:
    return html.Div(
        [
            create_section_header("Conflictos Activos", "Selecciona un conflicto para ver el análisis completo"),
            html.Div(
                _build_conflict_dropdown(),
                style={"maxWidth": "500px", "marginBottom": "16px"},
            ),
            # Métricas del conflicto seleccionado
            html.Div(id="m10-conflict-metrics", style={"marginBottom": "16px"}),
            # Panel de 3 columnas
            dbc.Row(
                [
                    dbc.Col(
                        html.Div(id="m10-conflict-context"),
                        md=4,
                    ),
                    dbc.Col(
                        html.Div(id="m10-conflict-scenarios"),
                        md=4,
                    ),
                    dbc.Col(
                        html.Div(id="m10-conflict-impact"),
                        md=4,
                    ),
                ],
                className="g-3",
            ),
            # Noticias del conflicto
            html.Div(id="m10-conflict-news", style={"marginTop": "16px"}),
            # Panel especial Irán
            html.Hr(style={"borderColor": COLORS["border"], "margin": "20px 0"}),
            html.Div(id="m10-iran-special-panel"),
        ],
        style=_SECTION,
    )


# ── Tab 3: GPR Histórico ──────────────────────────────────────────────────────

def _build_tab3() -> html.Div:
    # Botones de rango GPR histórico
    range_btns = html.Div(
        [
            html.Button(
                lbl, id=f"m10-gpr-range-{key}", n_clicks=0,
                style={
                    "background": COLORS["card_bg"],
                    "color": COLORS["text_muted"],
                    "border": f"1px solid {COLORS['border']}",
                    "borderRadius": "4px",
                    "padding": "4px 12px",
                    "fontSize": "0.75rem",
                    "cursor": "pointer",
                    "marginRight": "4px",
                },
            )
            for lbl, key in [("10A", "10"), ("20A", "20"), ("50A", "50"), ("100A", "100")]
        ],
        style={"marginBottom": "8px"},
    )

    return html.Div(
        [
            create_section_header(
                "GPR Global — El Termómetro Histórico",
                "Geopolitical Risk Index (Caldara & Iacoviello) · Más de 120 años de tensión geopolítica",
            ),
            range_btns,
            dcc.Store(id="m10-gpr-range-store", data=20),
            dcc.Loading(
                dcc.Graph(id="m10-gpr-hist-chart", config={"displayModeBar": True}, style={"height": "420px"}),
                color=COLORS["accent"],
            ),
            html.Div(id="m10-gpr-percentile-text", style={
                "marginTop": "8px", **_NOTE,
            }),
            html.Hr(style={"borderColor": COLORS["border"], "margin": "16px 0"}),
            create_section_header("GPR por País", "Comparativa de riesgo geopolítico específico por nación"),
            dcc.Loading(
                dcc.Graph(id="m10-gpr-country-chart", config={"displayModeBar": False}, style={"height": "350px"}),
                color=COLORS["accent"],
            ),
            html.Hr(style={"borderColor": COLORS["border"], "margin": "16px 0"}),
            create_section_header(
                "GPR como Indicador de Mercado",
                "Correlación histórica entre tensión geopolítica y rentabilidad bursátil a 1 mes",
            ),
            dcc.Loading(
                dcc.Graph(id="m10-gpr-market-scatter", config={"displayModeBar": False}, style={"height": "350px"}),
                color=COLORS["accent"],
            ),
            html.Div(style={**_NOTE, "marginTop": "8px"}, children=[
                "Históricamente, los picos del GPR suelen ser puntos de entrada en bolsa — el mercado ya ha descontado el miedo. "
                "Sin embargo, los GPR persistentemente altos (>150 durante +6 meses) sí correlacionan con menor crecimiento económico."
            ]),
        ],
        style=_SECTION,
    )


# ── Tab 4: Sanciones y Fragmentación ─────────────────────────────────────────

def _build_tab4() -> html.Div:
    return html.Div(
        [
            create_section_header("Sanciones Económicas Activas", "Estado de regímenes de sanciones en el mundo"),
            dcc.Loading(
                dcc.Graph(id="m10-sanctions-map", config={"displayModeBar": False}, style={"height": "420px"}),
                color=COLORS["accent"],
            ),
            # Tabla de sanciones
            html.Div(id="m10-sanctions-table", style={"marginTop": "12px"}),
            html.Hr(style={"borderColor": COLORS["border"], "margin": "16px 0"}),
            create_section_header(
                "Índice de Fragmentación Geoeconómica",
                "El mundo se divide en bloques — impacto estructural en inflación y comercio",
            ),
            dbc.Row(
                [
                    dbc.Col(
                        dcc.Loading(
                            dcc.Graph(id="m10-fragmentation-chart", config={"displayModeBar": False}, style={"height": "300px"}),
                            color=COLORS["accent"],
                        ),
                        md=6,
                    ),
                    dbc.Col(
                        dcc.Loading(
                            dcc.Graph(id="m10-trade-blocs-chart", config={"displayModeBar": False}, style={"height": "300px"}),
                            color=COLORS["accent"],
                        ),
                        md=6,
                    ),
                ],
                className="g-3",
            ),
            html.Div(style={**_NOTE, "marginTop": "8px"}, children=[
                "La fragmentación geoeconómica reduce la eficiencia del comercio global y es estructuralmente inflacionaria: "
                "duplicar cadenas de suministro, replicar infraestructuras y añadir aranceles incrementa el coste de todo lo que se produce."
            ]),
            html.Hr(style={"borderColor": COLORS["border"], "margin": "16px 0"}),
            create_section_header(
                "Dependencias Estratégicas Críticas",
                "¿Qué necesita EE.UU. de China? ¿Qué necesita China de EE.UU.? ¿Qué necesita Europa?",
            ),
            html.Div(id="m10-dependencies-table", style={"marginTop": "10px"}),
        ],
        style=_SECTION,
    )


# ── Tab 5: Calendario y Alertas ───────────────────────────────────────────────

def _build_tab5() -> html.Div:
    # Filtros del calendario
    filter_row = dbc.Row(
        [
            dbc.Col(
                dcc.Dropdown(
                    id="m10-cal-category-filter",
                    options=[
                        {"label": "Todas las categorías", "value": "all"},
                        {"label": "📊 Política Monetaria", "value": "monetary_policy"},
                        {"label": "🗳️ Elecciones", "value": "election"},
                        {"label": "🌐 Geopolítica", "value": "geopolitics"},
                        {"label": "🛢️ Energía/OPEP", "value": "energy"},
                    ],
                    value="all",
                    clearable=False,
                    style={
                        "backgroundColor": COLORS["card_bg"],
                        "color": COLORS["text"],
                        "borderColor": COLORS["border"],
                        "fontSize": "0.82rem",
                    },
                ),
                md=4,
            ),
            dbc.Col(
                dcc.Dropdown(
                    id="m10-cal-period-filter",
                    options=[
                        {"label": "Próximos 30 días", "value": 30},
                        {"label": "Próximos 90 días", "value": 90},
                        {"label": "Próximos 6 meses", "value": 180},
                        {"label": "Próximo año", "value": 365},
                    ],
                    value=90,
                    clearable=False,
                    style={
                        "backgroundColor": COLORS["card_bg"],
                        "color": COLORS["text"],
                        "borderColor": COLORS["border"],
                        "fontSize": "0.82rem",
                    },
                ),
                md=3,
            ),
        ],
        className="g-2 mb-3",
    )

    return html.Div(
        [
            create_section_header(
                "Calendario Político Global",
                "Próximos eventos políticos y financieros con impacto en mercados",
            ),
            filter_row,
            html.Div(id="m10-calendar-list", style={"marginTop": "4px"}),
            html.Hr(style={"borderColor": COLORS["border"], "margin": "20px 0"}),
            create_section_header(
                "Sistema de Alertas Geopolíticas",
                "Alertas activas basadas en umbrales del GPR y precio del petróleo",
            ),
            html.Div(id="m10-geo-alerts", style={"marginTop": "10px"}),
            html.Hr(style={"borderColor": COLORS["border"], "margin": "16px 0"}),
            create_section_header(
                "Reuniones Internacionales Próximas",
                "G7, G20, FOMC, BCE, OPEP+ · Próximos 6 meses",
            ),
            html.Div(id="m10-intl-meetings", style={"marginTop": "10px"}),
        ],
        style=_SECTION,
    )


# ── render_module_10 ──────────────────────────────────────────────────────────

def render_module_10() -> html.Div:
    return html.Div(
        [
            _build_header(),
            dcc.Interval(id="m10-refresh-interval", interval=300_000, n_intervals=0),
            dcc.Tabs(
                id="m10-tabs",
                value="tab-map",
                children=[
                    dcc.Tab(label="🗺️ Mapa de Riesgo",      value="tab-map",       style=TAB_STYLE, selected_style=TAB_SELECTED_STYLE),
                    dcc.Tab(label="⚔️ Conflictos Activos",  value="tab-conflicts", style=TAB_STYLE, selected_style=TAB_SELECTED_STYLE),
                    dcc.Tab(label="📊 GPR Histórico",        value="tab-gpr",       style=TAB_STYLE, selected_style=TAB_SELECTED_STYLE),
                    dcc.Tab(label="🚧 Sanciones",            value="tab-sanctions", style=TAB_STYLE, selected_style=TAB_SELECTED_STYLE),
                    dcc.Tab(label="📅 Calendario",           value="tab-calendar",  style=TAB_STYLE, selected_style=TAB_SELECTED_STYLE),
                ],
                style=TABS_STYLE,
            ),
            html.Div(id="m10-tab-content"),
        ],
        style={"backgroundColor": COLORS["background"]},
    )


# ── Callbacks ─────────────────────────────────────────────────────────────────

def register_callbacks_module_10(app) -> None:

    # ── Tab routing ───────────────────────────────────────────────────────────
    @app.callback(
        Output("m10-tab-content", "children"),
        Input("m10-tabs", "value"),
    )
    def render_tab(tab):
        if tab == "tab-map":
            return _build_tab1()
        if tab == "tab-conflicts":
            return _build_tab2()
        if tab == "tab-gpr":
            return _build_tab3()
        if tab == "tab-sanctions":
            return _build_tab4()
        if tab == "tab-calendar":
            return _build_tab5()
        return html.Div()

    # ── Mapa de Riesgo Global ─────────────────────────────────────────────────
    @app.callback(
        Output("m10-risk-map", "figure"),
        Input("m10-refresh-interval", "n_intervals"),
        Input("m10-tabs", "value"),
    )
    def update_risk_map(_n, tab):
        if tab != "tab-map":
            return no_update

        risk_data = load_json_data("geopolitical_risk_levels.json") or {}
        country_risk = risk_data.get("country_risk_levels", {})

        # Añadir datos de GPR específico para países con serie en BD
        gpr_countries = {
            "USA": ID_GPR_USA, "CHN": ID_GPR_CHN,
            "RUS": ID_GPR_RUS, "DEU": ID_GPR_DEU,
        }
        gpr_values = {}
        for iso3, sid in gpr_countries.items():
            v, _ = get_latest_value(sid, source="FRED_GPR")
            if v is not None:
                gpr_values[iso3] = v
                # Sobreescribir nivel según GPR real
                if v < 100:
                    country_risk[iso3] = "low"
                elif v < 150:
                    country_risk[iso3] = "medium"
                elif v < 200:
                    country_risk[iso3] = "high"
                else:
                    country_risk[iso3] = "critical"

        score_map = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        color_map = {"critical": "#ef4444", "high": "#f97316", "medium": "#f59e0b", "low": "#10b981"}

        iso3_list = list(country_risk.keys())
        z_vals    = [score_map.get(country_risk[c], 0) for c in iso3_list]
        colors_list = [color_map.get(country_risk[c], "#4b5563") for c in iso3_list]

        custom_text = []
        for iso3 in iso3_list:
            lvl = country_risk.get(iso3, "—")
            gpr_note = f"GPR: {gpr_values[iso3]:.0f}" if iso3 in gpr_values else ""
            custom_text.append(
                f"<b>{iso3}</b><br>Riesgo: {lvl.upper()}<br>{gpr_note}"
            )

        fig = go.Figure(go.Choropleth(
            locations=iso3_list,
            z=z_vals,
            text=custom_text,
            hovertemplate="%{text}<extra></extra>",
            colorscale=[
                [0.0,  "#1f2937"],
                [0.25, "#10b981"],
                [0.50, "#f59e0b"],
                [0.75, "#f97316"],
                [1.0,  "#ef4444"],
            ],
            showscale=False,
            marker_line_color="#374151",
            marker_line_width=0.5,
        ))

        _layout = get_base_layout(height=480)
        _layout["margin"] = {"l": 0, "r": 0, "t": 30, "b": 0}
        _layout["title"] = {
            "text": "Mapa de Riesgo Geopolítico Global",
            "font": {"color": COLORS["text"], "size": 13},
            "x": 0.01,
        }
        fig.update_layout(
            **_layout,
            geo=dict(
                showframe=False,
                showcoastlines=True,
                coastlinecolor="#374151",
                showland=True,
                landcolor="#1f2937",
                showocean=True,
                oceancolor="#0a0e1a",
                showlakes=False,
                bgcolor="#0a0e1a",
                projection_type="natural earth",
            ),
        )
        return fig

    # ── Panel lateral click en país ───────────────────────────────────────────
    @app.callback(
        Output("m10-country-detail-panel", "children"),
        Input("m10-risk-map", "clickData"),
    )
    def country_detail(click_data):
        if not click_data:
            return html.Div(
                "Haz clic en un país del mapa para ver el detalle",
                style={"color": COLORS["text_muted"], "fontSize": "0.82rem", "padding": "6px"},
            )

        try:
            iso3 = click_data["points"][0]["location"]
        except (KeyError, IndexError, TypeError):
            return html.Div()

        risk_data = load_json_data("geopolitical_risk_levels.json") or {}
        country_risk = risk_data.get("country_risk_levels", {})
        level = country_risk.get(iso3, "sin datos")
        color = _risk_color(level)

        # Conflictos relacionados
        conflicts_data = load_json_data("active_conflicts.json") or {}
        conflicts = conflicts_data.get("conflicts", [])
        related = [c for c in conflicts if iso3 in c.get("countries_involved", [])]

        children = [
            html.Div(
                [
                    html.Span(f"🌍 {iso3}", style={"fontWeight": "700", "fontSize": "1rem"}),
                    html.Span(
                        f" · Nivel: {level.upper()}",
                        style={"color": color, "fontWeight": "600", "marginLeft": "8px"},
                    ),
                ],
                style={"marginBottom": "8px"},
            ),
        ]

        if related:
            children.append(html.Div("Conflictos activos relacionados:", style={
                "fontSize": "0.75rem", "color": COLORS["text_muted"], "marginBottom": "4px",
            }))
            for c in related:
                children.append(html.Div(
                    f"• {c['title']} — Severidad: {c['severity']}/5",
                    style={"fontSize": "0.78rem", "color": COLORS["text"], "marginLeft": "8px"},
                ))
        else:
            children.append(html.Div(
                "Sin conflictos activos registrados en este país",
                style={"fontSize": "0.78rem", "color": COLORS["text_muted"]},
            ))

        return html.Div(children)

    # ── Regiones de alta tensión ──────────────────────────────────────────────
    @app.callback(
        Output("m10-tension-regions", "children"),
        Input("m10-refresh-interval", "n_intervals"),
        Input("m10-tabs", "value"),
    )
    def update_tension_regions(_n, tab):
        if tab != "tab-map":
            return no_update

        conflicts_data = load_json_data("active_conflicts.json") or {}
        conflicts = sorted(
            conflicts_data.get("conflicts", []),
            key=lambda c: c.get("severity", 0),
            reverse=True,
        )

        if not conflicts:
            return html.Div("Sin datos de conflictos", style={"color": COLORS["text_muted"]})

        cards = []
        for c in conflicts:
            sev = c.get("severity", 0)
            color = _risk_color("critical" if sev == 5 else "high" if sev == 4 else "medium" if sev == 3 else "low")
            cards.append(
                html.Div(
                    [
                        html.Div(c.get("title", ""), style={
                            "fontWeight": "600", "fontSize": "0.82rem", "marginBottom": "4px",
                        }),
                        _severity_badge(sev),
                        html.Span(" ", ),
                        _intensity_badge(c.get("intensity", "medium")),
                        html.Div(
                            c.get("summary", "")[:100] + "…",
                            style={"fontSize": "0.72rem", "color": COLORS["text_muted"], "marginTop": "6px"},
                        ),
                    ],
                    style={
                        "background": COLORS["card_bg"],
                        "border": f"1px solid {color}55",
                        "borderLeft": f"3px solid {color}",
                        "borderRadius": "6px",
                        "padding": "10px 14px",
                        "flex": "1",
                        "minWidth": "220px",
                        "maxWidth": "340px",
                    },
                )
            )

        return html.Div(cards, style={"display": "flex", "gap": "10px", "flexWrap": "wrap"})

    # ── Detalle del conflicto seleccionado ────────────────────────────────────
    @app.callback(
        Output("m10-conflict-metrics",   "children"),
        Output("m10-conflict-context",   "children"),
        Output("m10-conflict-scenarios", "children"),
        Output("m10-conflict-impact",    "children"),
        Output("m10-conflict-news",      "children"),
        Output("m10-iran-special-panel", "children"),
        Input("m10-conflict-selector",   "value"),
        Input("m10-refresh-interval",    "n_intervals"),
        Input("m10-tabs",                "value"),
    )
    def update_conflict_detail(conflict_id, _n, tab):
        empty = html.Div()
        if tab != "tab-conflicts":
            return empty, empty, empty, empty, empty, empty

        conflicts_data = load_json_data("active_conflicts.json") or {}
        conflicts_list = conflicts_data.get("conflicts", [])
        conflict = next((c for c in conflicts_list if c.get("id") == conflict_id), None)

        iran_panel = _build_iran_panel()

        if conflict is None:
            return (
                html.Div("Selecciona un conflicto", style={"color": COLORS["text_muted"]}),
                empty, empty, empty, empty, iran_panel,
            )

        # ── Métricas superiores ───────────────────────────────────────────
        days = _days_since(conflict.get("start_date", ""))
        metrics = html.Div(
            [
                _compact_metric(
                    title="Duración",
                    value_str=f"{days:,}d" if days else "—",
                    sub_str=f"Desde {conflict.get('start_date', '—')}",
                    sub_color=COLORS["text_muted"],
                ),
                html.Div(
                    [
                        html.Div("SEVERIDAD", style={
                            "fontSize": "0.60rem", "color": COLORS["text_label"],
                            "fontWeight": "600", "letterSpacing": "0.08em", "marginBottom": "4px",
                        }),
                        _severity_badge(conflict.get("severity", 1)),
                    ],
                    style={
                        "background": COLORS["card_bg"],
                        "border": f"1px solid {COLORS['border']}",
                        "borderRadius": "6px",
                        "padding": "10px 14px",
                        "flex": "1",
                        "minWidth": "130px",
                    },
                ),
                html.Div(
                    [
                        html.Div("INTENSIDAD", style={
                            "fontSize": "0.60rem", "color": COLORS["text_label"],
                            "fontWeight": "600", "letterSpacing": "0.08em", "marginBottom": "4px",
                        }),
                        _intensity_badge(conflict.get("intensity", "medium")),
                    ],
                    style={
                        "background": COLORS["card_bg"],
                        "border": f"1px solid {COLORS['border']}",
                        "borderRadius": "6px",
                        "padding": "10px 14px",
                        "flex": "1",
                        "minWidth": "130px",
                    },
                ),
                html.Div(
                    [
                        html.Div("PAÍSES", style={
                            "fontSize": "0.60rem", "color": COLORS["text_label"],
                            "fontWeight": "600", "letterSpacing": "0.08em", "marginBottom": "6px",
                        }),
                        html.Div(_flag_badges(conflict.get("countries_involved", [])),
                                 style={"display": "flex", "flexWrap": "wrap", "gap": "2px"}),
                    ],
                    style={
                        "background": COLORS["card_bg"],
                        "border": f"1px solid {COLORS['border']}",
                        "borderRadius": "6px",
                        "padding": "10px 14px",
                        "flex": "2",
                        "minWidth": "200px",
                    },
                ),
            ],
            style={"display": "flex", "gap": "10px", "flexWrap": "wrap"},
        )

        # ── Columna izquierda: contexto y cronología ───────────────────────
        key_dates = conflict.get("key_dates", [])
        timeline_items = []
        for kd in key_dates:
            timeline_items.append(
                html.Div(
                    [
                        html.Div(
                            kd.get("date", ""),
                            style={"fontSize": "0.68rem", "color": COLORS["accent"],
                                   "fontWeight": "600", "marginBottom": "2px"},
                        ),
                        html.Div(kd.get("event", ""),
                                 style={"fontSize": "0.75rem", "color": COLORS["text"]}),
                    ],
                    style={
                        "borderLeft": f"2px solid {COLORS['accent']}44",
                        "paddingLeft": "10px",
                        "marginBottom": "10px",
                    },
                )
            )

        context_col = html.Div(
            [
                html.Div(
                    [html.Div("RESUMEN", style={
                        "fontSize": "0.68rem", "color": COLORS["text_label"],
                        "fontWeight": "600", "letterSpacing": "0.08em", "marginBottom": "6px",
                    }),
                    html.Div(
                        conflict.get("summary", "Sin resumen disponible"),
                        style={"fontSize": "0.78rem", "color": COLORS["text"], "lineHeight": "1.5"},
                    )],
                    style=_CARD,
                ),
                html.Div(
                    [
                        html.Div("CRONOLOGÍA", style={
                            "fontSize": "0.68rem", "color": COLORS["text_label"],
                            "fontWeight": "600", "letterSpacing": "0.08em", "marginBottom": "8px",
                        }),
                        *timeline_items,
                    ],
                    style=_CARD,
                ) if timeline_items else html.Div(),
            ]
        )

        # ── Columna central: escenarios ────────────────────────────────────
        scenarios = conflict.get("scenarios", [])
        scenario_items = []
        for s in scenarios:
            prob = s.get("probability", 0)
            sent = s.get("sentiment", "neutral")
            c_color = _SCENARIO_COLORS.get(sent, COLORS["text_muted"])
            scenario_items.append(
                html.Div(
                    [
                        html.Div(
                            [
                                html.Span(s.get("name", ""), style={
                                    "fontSize": "0.78rem", "fontWeight": "600", "color": COLORS["text"],
                                }),
                                html.Span(
                                    f"{prob*100:.0f}%",
                                    style={
                                        "fontSize": "0.75rem", "fontWeight": "700",
                                        "color": c_color, "marginLeft": "auto",
                                    },
                                ),
                            ],
                            style={"display": "flex", "justifyContent": "space-between",
                                   "marginBottom": "4px"},
                        ),
                        # Barra de probabilidad
                        html.Div(
                            html.Div(style={
                                "width": f"{prob*100:.0f}%",
                                "height": "4px",
                                "background": c_color,
                                "borderRadius": "2px",
                            }),
                            style={
                                "width": "100%", "height": "4px",
                                "background": "#1f2937", "borderRadius": "2px", "marginBottom": "4px",
                            },
                        ),
                        html.Div(
                            s.get("description", ""),
                            style={"fontSize": "0.70rem", "color": COLORS["text_muted"], "lineHeight": "1.4"},
                        ),
                    ],
                    style={"marginBottom": "12px"},
                )
            )

        scenarios_col = html.Div(
            [
                html.Div("ESCENARIOS POSIBLES", style={
                    "fontSize": "0.68rem", "color": COLORS["text_label"],
                    "fontWeight": "600", "letterSpacing": "0.08em", "marginBottom": "10px",
                }),
                *scenario_items,
            ],
            style=_CARD,
        )

        # ── Columna derecha: impacto económico ────────────────────────────
        econ = conflict.get("economic_impact", {})
        assets = conflict.get("affected_assets", [])
        asset_impacts = get_conflict_asset_impact(assets, conflict.get("start_date", ""))

        asset_rows = []
        for ai in asset_impacts:
            if ai is None:
                continue
            pct = ai["variacion_pct"]
            color_pct = COLORS["red"] if pct < 0 else COLORS["green"]
            arrow = "↑" if pct > 0 else "↓"
            asset_rows.append(
                html.Tr([
                    html.Td(ai["nombre"], style={"fontSize": "0.72rem", "padding": "3px 6px"}),
                    html.Td(
                        f"{ai['precio_actual']:.1f}",
                        style={"fontSize": "0.72rem", "textAlign": "right", "padding": "3px 6px"},
                    ),
                    html.Td(
                        f"{arrow}{abs(pct):.1f}%",
                        style={"fontSize": "0.72rem", "color": color_pct,
                               "textAlign": "right", "fontWeight": "600", "padding": "3px 6px"},
                    ),
                ])
            )

        impact_col = html.Div(
            [
                html.Div("IMPACTO ECONÓMICO", style={
                    "fontSize": "0.68rem", "color": COLORS["text_label"],
                    "fontWeight": "600", "letterSpacing": "0.08em", "marginBottom": "8px",
                }),
                html.Div(
                    [
                        html.Div([
                            html.Span("Disrupc. petróleo: ", style={"color": COLORS["text_muted"], "fontSize": "0.72rem"}),
                            html.Span(f"{econ.get('oil_disruption_pct', 0)}%",
                                      style={"fontWeight": "600", "color": COLORS["orange"]}),
                        ], style={"marginBottom": "4px"}),
                        html.Div([
                            html.Span("Impacto PIB global: ", style={"color": COLORS["text_muted"], "fontSize": "0.72rem"}),
                            html.Span(f"{econ.get('estimated_gdp_impact_global_pct', 0):+.1f}%",
                                      style={"fontWeight": "600", "color": COLORS["red"]}),
                        ], style={"marginBottom": "4px"}),
                        html.Div([
                            html.Span("Inflación adicional: ", style={"color": COLORS["text_muted"], "fontSize": "0.72rem"}),
                            html.Span(f"+{econ.get('inflation_impact_pp', 0):.1f}pp",
                                      style={"fontWeight": "600", "color": COLORS["yellow"]}),
                        ], style={"marginBottom": "4px"}),
                    ]
                ),
                html.Hr(style={"borderColor": COLORS["border"], "margin": "8px 0"}),
                html.Div("Activos financieros afectados desde inicio:", style={
                    "fontSize": "0.68rem", "color": COLORS["text_label"], "marginBottom": "4px",
                }),
                html.Table(
                    [
                        html.Thead(html.Tr([
                            html.Th("Activo", style={"fontSize": "0.65rem", "color": COLORS["text_label"], "padding": "3px 6px"}),
                            html.Th("Precio", style={"fontSize": "0.65rem", "color": COLORS["text_label"], "padding": "3px 6px", "textAlign": "right"}),
                            html.Th("Cambio", style={"fontSize": "0.65rem", "color": COLORS["text_label"], "padding": "3px 6px", "textAlign": "right"}),
                        ])),
                        html.Tbody(asset_rows if asset_rows else [
                            html.Tr(html.Td(
                                "Sin datos en BD para estos activos",
                                colSpan=3,
                                style={"fontSize": "0.72rem", "color": COLORS["text_muted"], "padding": "6px"},
                            ))
                        ]),
                    ],
                    style={"width": "100%", "borderCollapse": "collapse"},
                ),
            ],
            style=_CARD,
        )

        # ── Noticias relacionadas ─────────────────────────────────────────
        all_news = get_latest_news(n=20, hours=168)
        keywords = [
            w.lower() for w in (
                conflict.get("title", "").split() +
                conflict.get("countries_involved", [])
            )
            if len(w) > 2
        ]
        def _news_match(article: dict) -> bool:
            text = (
                (article.get("title") or "") + " " +
                (article.get("description") or "") + " " +
                (article.get("region") or "")
            ).lower()
            return any(kw in text for kw in keywords)

        related_news = [a for a in all_news if _news_match(a)][:5]
        if related_news:
            news_items = []
            for art in related_news:
                ts = art.get("published_at")
                ts_str = ts.strftime("%d %b") if ts else ""
                news_items.append(
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Span(art.get("source_name", ""), style={
                                        "fontSize": "0.65rem", "color": COLORS["accent"],
                                        "marginRight": "6px",
                                    }),
                                    html.Span(ts_str, style={
                                        "fontSize": "0.65rem", "color": COLORS["text_label"],
                                    }),
                                ]
                            ),
                            html.Div(art.get("title", ""), style={
                                "fontSize": "0.78rem", "color": COLORS["text"],
                                "lineHeight": "1.4",
                            }),
                        ],
                        style={
                            "borderBottom": f"1px solid {COLORS['border']}",
                            "paddingBottom": "8px", "marginBottom": "8px",
                        },
                    )
                )
            news_panel = html.Div(
                [
                    create_section_header("Noticias recientes relacionadas"),
                    html.Div(news_items),
                ]
            )
        else:
            news_panel = html.Div(
                "Sin noticias recientes relacionadas en la base de datos",
                style={"color": COLORS["text_muted"], "fontSize": "0.78rem"},
            )

        return metrics, context_col, scenarios_col, impact_col, news_panel, iran_panel

    # ── Panel especial Irán ───────────────────────────────────────────────────
    def _build_iran_panel() -> html.Div:
        brent_current, _  = get_latest_value(ID_BRENT)
        brent_pre = 67.0  # precio aproximado antes del conflicto

        days = _days_since("2026-02-28")
        days_str = str(days) if days else "—"

        if brent_current and brent_pre:
            brent_chg_abs = brent_current - brent_pre
            brent_chg_pct = (brent_chg_abs / brent_pre) * 100
            brent_str = f"{brent_current:.1f}$"
            brent_chg_str = f"↑{brent_chg_abs:+.1f}$ ({brent_chg_pct:+.1f}%)"
            brent_color = COLORS["red"]
        else:
            brent_str = "—"
            brent_chg_str = "Sin datos"
            brent_color = COLORS["text_muted"]

        # Gráfico Brent desde 1 febrero 2026
        brent_df = get_series(ID_BRENT, days=60)

        fig_brent = go.Figure()
        if not brent_df.empty:
            fig_brent.add_trace(go.Scatter(
                x=brent_df["timestamp"], y=brent_df["value"],
                mode="lines", name="Brent",
                line={"color": COLORS["orange"], "width": 2},
            ))
            # Anotación inicio conflicto
            fig_brent.add_shape(
                type="line",
                x0="2026-02-28", x1="2026-02-28",
                y0=0, y1=1, yref="paper",
                line={"color": COLORS["red"], "dash": "dash", "width": 1.5},
            )
            fig_brent.add_annotation(
                x="2026-02-28", y=0.95, yref="paper",
                text="28-Feb: Irán", showarrow=False,
                font={"color": COLORS["red"], "size": 9},
                xanchor="left",
            )
        fig_brent.update_layout(
            **get_base_layout("Brent Crude (USD)", height=250),
            showlegend=False,
        )

        # Escenarios Irán
        iran_data = None
        conflicts_data = load_json_data("active_conflicts.json") or {}
        for c in conflicts_data.get("conflicts", []):
            if c.get("id") == "iran_us_2026":
                iran_data = c
                break

        scenario_items = []
        if iran_data:
            for s in iran_data.get("scenarios", []):
                prob = s.get("probability", 0)
                sent = s.get("sentiment", "neutral")
                c_color = _SCENARIO_COLORS.get(sent, COLORS["text_muted"])
                scenario_items.append(
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Span(s.get("name", ""), style={"fontSize": "0.75rem", "fontWeight": "600"}),
                                    html.Span(f"{prob*100:.0f}%", style={
                                        "marginLeft": "auto", "color": c_color, "fontWeight": "700", "fontSize": "0.75rem",
                                    }),
                                ],
                                style={"display": "flex", "justifyContent": "space-between", "marginBottom": "3px"},
                            ),
                            html.Div(
                                html.Div(style={"width": f"{prob*100:.0f}%", "height": "3px", "background": c_color}),
                                style={"width": "100%", "height": "3px", "background": "#1f2937", "marginBottom": "3px"},
                            ),
                        ],
                        style={"marginBottom": "8px"},
                    )
                )

        return html.Div(
            [
                html.Div(
                    [
                        html.Span("🚨 ", style={"fontSize": "1rem"}),
                        html.Span(
                            "PANEL ESPECIAL: Guerra EE.UU.-Israel vs Irán",
                            style={"fontWeight": "700", "fontSize": "0.88rem", "color": COLORS["red"]},
                        ),
                    ],
                    style={"marginBottom": "10px"},
                ),
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                _compact_metric("Días en conflicto", days_str, "desde 28 Feb 2026", COLORS["red"]),
                                html.Div(style={"height": "10px"}),
                                _compact_metric("Brent actual", brent_str, brent_chg_str, brent_color),
                                html.Div(style={"height": "10px"}),
                                html.Div(
                                    [
                                        html.Div("ESTRECHO DE ORMUZ", style={
                                            "fontSize": "0.60rem", "color": COLORS["text_label"],
                                            "fontWeight": "600", "letterSpacing": "0.08em", "marginBottom": "4px",
                                        }),
                                        html.Div(
                                            "🔴 TRÁNSITO RESTRINGIDO",
                                            style={"color": COLORS["red"], "fontWeight": "700", "fontSize": "0.82rem"},
                                        ),
                                        html.Div("~20% del petróleo global en riesgo", style={
                                            "fontSize": "0.70rem", "color": COLORS["text_muted"],
                                        }),
                                    ],
                                    style=_CARD,
                                ),
                            ],
                            md=3,
                        ),
                        dbc.Col(
                            dcc.Graph(figure=fig_brent, config={"displayModeBar": False}),
                            md=5,
                        ),
                        dbc.Col(
                            [
                                html.Div("ESCENARIOS", style={
                                    "fontSize": "0.68rem", "color": COLORS["text_label"],
                                    "fontWeight": "600", "letterSpacing": "0.08em", "marginBottom": "8px",
                                }),
                                *scenario_items,
                            ],
                            md=4,
                        ),
                    ],
                    className="g-2",
                ),
            ],
            style={
                "background": f"{COLORS['red']}08",
                "border": f"1px solid {COLORS['red']}33",
                "borderRadius": "8px",
                "padding": "14px 16px",
                "marginTop": "8px",
            },
        )

    # ── GPR Histórico ─────────────────────────────────────────────────────────
    @app.callback(
        Output("m10-gpr-range-store", "data"),
        Input("m10-gpr-range-10",  "n_clicks"),
        Input("m10-gpr-range-20",  "n_clicks"),
        Input("m10-gpr-range-50",  "n_clicks"),
        Input("m10-gpr-range-100", "n_clicks"),
    )
    def update_gpr_range_store(n10, n20, n50, n100):
        from dash import ctx as dash_ctx
        tid = dash_ctx.triggered_id
        if tid == "m10-gpr-range-10":
            return 10
        if tid == "m10-gpr-range-50":
            return 50
        if tid == "m10-gpr-range-100":
            return 100
        return 20

    @app.callback(
        Output("m10-gpr-hist-chart",    "figure"),
        Output("m10-gpr-percentile-text", "children"),
        Input("m10-gpr-range-store",   "data"),
        Input("m10-refresh-interval",  "n_intervals"),
        Input("m10-tabs",              "value"),
    )
    def update_gpr_hist(years, _n, tab):
        if tab != "tab-gpr":
            return no_update, no_update

        days = years * 365
        df_hist = get_series(ID_GPR_HIST, days=days + 365, source="FRED_GPR")
        df_gprc = get_series(ID_GPR_GLOBAL, days=days + 365, source="FRED_GPR")

        # Usar histórico si disponible, sino usar GPRC
        df = df_hist if not df_hist.empty else df_gprc
        if df.empty:
            return _empty_fig("Sin datos GPR histórico disponibles"), "—"

        # Filtrar por años seleccionados
        cutoff = datetime.utcnow() - timedelta(days=days)
        df = df[df["timestamp"] >= cutoff].copy()
        if df.empty:
            return _empty_fig(f"Sin datos GPR para los últimos {years} años"), "—"

        current_val = df["value"].iloc[-1] if not df.empty else None
        level = _gpr_level(current_val)
        color = _GPR_SEMAPHORE_COLOR[level]

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df["timestamp"], y=df["value"],
            mode="lines", name="GPR",
            line={"color": COLORS["accent"], "width": 1.5},
            fill="tozeroy",
            fillcolor=_rgba(COLORS["accent"], 0.08),
        ))

        # Punto actual
        if current_val is not None:
            fig.add_trace(go.Scatter(
                x=[df["timestamp"].iloc[-1]],
                y=[current_val],
                mode="markers",
                marker={"size": 10, "color": color},
                name=f"Actual: {current_val:.0f}",
                showlegend=True,
            ))

        # Líneas de referencia
        fig.add_hline(y=100, line_dash="dot", line_color=COLORS["yellow"], line_width=1,
                      annotation_text="100: Normal", annotation_font_size=9,
                      annotation_font_color=COLORS["yellow"])
        fig.add_hline(y=200, line_dash="dot", line_color=COLORS["red"], line_width=1,
                      annotation_text="200: Crisis", annotation_font_size=9,
                      annotation_font_color=COLORS["red"])

        # Anotaciones de eventos históricos
        HIST_ANNOTATIONS = [
            ("1914-07-01", "WWI", 350),
            ("1939-09-01", "WWII", 500),
            ("1950-06-25", "Corea", 250),
            ("1962-10-15", "Cuba", 300),
            ("1973-10-06", "Yom Kipur", 280),
            ("1990-08-02", "Golfo", 260),
            ("2001-09-11", "11-S",  420),
            ("2003-03-20", "Iraq",  200),
            ("2022-02-24", "Ucrania", 220),
            ("2026-02-28", "Irán",  250),
        ]
        annotations = []
        for date_str, label, y_hint in HIST_ANNOTATIONS:
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                if dt >= cutoff:
                    annotations.append({
                        "x": date_str, "y": y_hint,
                        "text": label, "showarrow": True, "arrowhead": 2,
                        "arrowcolor": COLORS["border_mid"], "arrowwidth": 1,
                        "font": {"color": COLORS["text_muted"], "size": 9},
                        "bgcolor": "#0a0e1a", "borderpad": 2,
                    })
            except Exception:
                pass

        fig.update_layout(
            **get_base_layout(f"GPR Histórico — últimos {years} años", height=420),
            annotations=annotations,
        )

        # Texto percentil
        pct_data = calculate_gpr_percentile(current_val)
        pct = pct_data.get("percentile")
        if pct is not None:
            z_pct = 100 - pct
            pct_text = (
                f"El GPR actual de {current_val:.0f} está en el percentil {pct:.0f} histórico — "
                f"más alto que el {pct:.0f}% de todos los meses registrados desde 1900. "
                f"{pct_data.get('interpretation', '')}"
            )
        else:
            pct_text = "Datos históricos insuficientes para calcular el percentil."

        return fig, pct_text

    @app.callback(
        Output("m10-gpr-country-chart", "figure"),
        Input("m10-refresh-interval",  "n_intervals"),
        Input("m10-tabs",              "value"),
    )
    def update_gpr_country(_n, tab):
        if tab != "tab-gpr":
            return no_update

        country_series = {
            "EE.UU.":  (ID_GPR_USA, COLORS["accent"]),
            "China":   (ID_GPR_CHN, COLORS["orange"]),
            "Rusia":   (ID_GPR_RUS, "#ef4444"),
            "Alemania":(ID_GPR_DEU, COLORS["green"]),
            "ISR/ME":  (ID_GPR_ISR, COLORS["yellow"]),
        }

        fig = go.Figure()
        for name, (sid, c) in country_series.items():
            df = get_series(sid, days=5 * 365, source="FRED_GPR")
            if df.empty:
                continue
            fig.add_trace(go.Scatter(
                x=df["timestamp"], y=df["value"],
                mode="lines", name=name,
                line={"color": c, "width": 1.8},
            ))

        if not fig.data:
            return _empty_fig("Sin datos GPR por país disponibles")

        fig.add_hline(y=100, line_dash="dot", line_color=COLORS["text_label"],
                      line_width=1, annotation_text="Normal")
        fig.update_layout(**get_base_layout("GPR por País (5 años)", height=350))
        return fig

    @app.callback(
        Output("m10-gpr-market-scatter", "figure"),
        Input("m10-refresh-interval",   "n_intervals"),
        Input("m10-tabs",               "value"),
    )
    def update_gpr_market_scatter(_n, tab):
        if tab != "tab-gpr":
            return no_update

        df_gpr = get_series(ID_GPR_GLOBAL, days=25 * 365, source="FRED_GPR")
        df_sp  = get_series(ID_SP500,      days=25 * 365)

        if df_gpr.empty or df_sp.empty:
            return _empty_fig("Sin datos suficientes para el análisis GPR-Mercado")

        df_gpr = df_gpr.set_index("timestamp").resample("ME").mean().reset_index()
        df_sp  = df_sp.set_index("timestamp").resample("ME").last().reset_index()

        # Calcular retorno mensual del S&P
        df_sp["return_1m"] = df_sp["value"].pct_change(1) * 100

        # Merge por mes
        df_gpr["ym"] = df_gpr["timestamp"].dt.to_period("M")
        df_sp["ym"]  = df_sp["timestamp"].dt.to_period("M")
        merged = df_gpr.merge(df_sp[["ym", "return_1m"]], on="ym", how="inner").dropna()

        if merged.empty:
            return _empty_fig("Sin datos para correlación GPR-S&P500")

        corr = merged["value"].corr(merged["return_1m"])

        color_scatter = [
            COLORS["red"] if r < 0 else COLORS["green"]
            for r in merged["return_1m"]
        ]

        fig = go.Figure(go.Scatter(
            x=merged["value"],
            y=merged["return_1m"],
            mode="markers",
            marker={"color": color_scatter, "size": 5, "opacity": 0.65},
            text=merged["timestamp"].dt.strftime("%b %Y"),
            hovertemplate="GPR: %{x:.0f}<br>S&P 1m: %{y:.1f}%<br>%{text}<extra></extra>",
        ))

        # Línea de tendencia
        try:
            import numpy as np
            z = np.polyfit(merged["value"], merged["return_1m"], 1)
            p = np.poly1d(z)
            x_line = [merged["value"].min(), merged["value"].max()]
            fig.add_trace(go.Scatter(
                x=x_line, y=[p(x) for x in x_line],
                mode="lines", name="Tendencia",
                line={"color": COLORS["text_muted"], "dash": "dash", "width": 1},
            ))
        except Exception:
            pass

        fig.update_layout(
            **get_base_layout(
                f"GPR vs Retorno S&P 500 al mes siguiente · Correlación: {corr:.2f}",
                height=350,
            ),
            xaxis_title="GPR Index",
            yaxis_title="Retorno S&P 500 +1 mes (%)",
        )
        return fig

    # ── Sanciones ─────────────────────────────────────────────────────────────
    @app.callback(
        Output("m10-sanctions-map",   "figure"),
        Output("m10-sanctions-table", "children"),
        Input("m10-refresh-interval", "n_intervals"),
        Input("m10-tabs",             "value"),
    )
    def update_sanctions(_n, tab):
        if tab != "tab-sanctions":
            return no_update, no_update

        data = load_json_data("sanctions_map.json") or {}
        regimes = data.get("sanction_regimes", [])

        severity_score = {"comprehensive": 3, "sectoral": 2, "targeted": 1}
        severity_color = {
            "comprehensive": "#ef4444",
            "sectoral":       "#f97316",
            "targeted":       "#f59e0b",
        }

        # Mapa de países sancionados
        iso3_list, z_vals, texts = [], [], []
        for r in regimes:
            iso3 = r["target_country"]
            sev  = r.get("severity", "targeted")
            iso3_list.append(iso3)
            z_vals.append(severity_score.get(sev, 1))
            sanct = ", ".join(r.get("sanctioning_entities", []))
            texts.append(
                f"<b>{iso3}</b><br>Sanciones: {sev.upper()}<br>"
                f"Entidades: {sanct}<br>Impacto PIB: {r.get('estimated_gdp_impact_pct', 0):+.1f}%"
            )

        fig = go.Figure(go.Choropleth(
            locations=iso3_list,
            z=z_vals,
            text=texts,
            hovertemplate="%{text}<extra></extra>",
            colorscale=[
                [0.0, "#0a0e1a"],
                [0.33, "#f59e0b"],
                [0.66, "#f97316"],
                [1.0,  "#ef4444"],
            ],
            showscale=False,
            marker_line_color="#374151",
            marker_line_width=0.5,
        ))
        _slayout = get_base_layout("Países bajo régimen de sanciones", height=380)
        _slayout["margin"] = {"l": 0, "r": 0, "t": 30, "b": 0}
        fig.update_layout(
            **_slayout,
            geo=dict(
                showframe=False, showcoastlines=True,
                coastlinecolor="#374151",
                showland=True, landcolor="#1f2937",
                showocean=True, oceancolor="#0a0e1a",
                bgcolor="#0a0e1a",
                projection_type="natural earth",
            ),
        )

        # Tabla de sanciones
        rows = []
        for r in regimes:
            sev = r.get("severity", "")
            c = severity_color.get(sev, COLORS["text_muted"])
            rows.append(html.Tr([
                html.Td(r["target_country"], style={"padding": "6px 10px", "fontWeight": "600"}),
                html.Td(
                    html.Span(sev.upper(), style={
                        "background": f"{c}22", "color": c,
                        "border": f"1px solid {c}55", "borderRadius": "3px",
                        "padding": "1px 8px", "fontSize": "0.70rem",
                    }),
                    style={"padding": "6px 10px"},
                ),
                html.Td(", ".join(r.get("sanctioning_entities", [])),
                        style={"padding": "6px 10px", "fontSize": "0.72rem", "color": COLORS["text_muted"]}),
                html.Td(f"{r.get('estimated_gdp_impact_pct', 0):+.1f}%",
                        style={"padding": "6px 10px", "color": COLORS["red"], "textAlign": "right"}),
                html.Td(r.get("description", "")[:70] + "…",
                        style={"padding": "6px 10px", "fontSize": "0.70rem", "color": COLORS["text_muted"]}),
            ], style={"borderBottom": f"1px solid {COLORS['border']}"}))

        table = html.Table(
            [
                html.Thead(html.Tr([
                    html.Th(h, style={"padding": "6px 10px", "textAlign": "left",
                                      "fontSize": "0.68rem", "color": COLORS["text_label"],
                                      "borderBottom": f"1px solid {COLORS['border']}"})
                    for h in ["País", "Severidad", "Sancionadores", "Impacto PIB", "Descripción"]
                ])),
                html.Tbody(rows),
            ],
            style={"width": "100%", "borderCollapse": "collapse",
                   "background": COLORS["card_bg"], "borderRadius": "6px"},
        )

        return fig, table

    @app.callback(
        Output("m10-fragmentation-chart", "figure"),
        Output("m10-trade-blocs-chart",   "figure"),
        Input("m10-refresh-interval",     "n_intervals"),
        Input("m10-tabs",                 "value"),
    )
    def update_fragmentation(_n, tab):
        if tab != "tab-sanctions":
            return no_update, no_update

        data = load_json_data("geoeconomic_fragmentation.json") or {}
        frag = data.get("fragmentation_index", {})
        intra = data.get("intra_bloc_trade_pct_gdp", {})
        cross = data.get("cross_bloc_trade_pct_gdp", {})

        years_frag  = sorted(frag.keys())
        vals_frag   = [frag[y] for y in years_frag]
        years_trade = sorted(intra.keys())
        vals_intra  = [intra[y] for y in years_trade]
        vals_cross  = [cross[y] for y in years_trade]

        # Gráfico 1: índice de fragmentación
        fig1 = go.Figure()
        if years_frag:
            fig1.add_trace(go.Scatter(
                x=years_frag, y=vals_frag,
                mode="lines+markers", name="Índice Fragmentación",
                line={"color": COLORS["red"], "width": 2},
                marker={"size": 6},
                fill="tozeroy", fillcolor=_rgba(COLORS["red"], 0.06),
            ))
        fig1.update_layout(**get_base_layout("Índice de Fragmentación Geoeconómica", height=300))

        # Gráfico 2: comercio intra vs entre bloques
        fig2 = go.Figure()
        if years_trade:
            fig2.add_trace(go.Scatter(
                x=years_trade, y=vals_intra,
                mode="lines+markers", name="Intra-bloque (↑)",
                line={"color": COLORS["orange"], "width": 2},
            ))
            fig2.add_trace(go.Scatter(
                x=years_trade, y=vals_cross,
                mode="lines+markers", name="Entre bloques (↓)",
                line={"color": COLORS["accent"], "width": 2},
            ))
        fig2.update_layout(**get_base_layout("Comercio Intra vs Entre Bloques (% PIB)", height=300))

        return fig1, fig2

    @app.callback(
        Output("m10-dependencies-table", "children"),
        Input("m10-refresh-interval",    "n_intervals"),
        Input("m10-tabs",                "value"),
    )
    def update_dependencies(_n, tab):
        if tab != "tab-sanctions":
            return no_update

        data = load_json_data("strategic_dependencies.json") or {}
        deps = data.get("dependencies", [])

        if not deps:
            return html.Div("Sin datos", style={"color": COLORS["text_muted"]})

        crit_colors = {
            "critical": COLORS["red"],
            "high":     COLORS["orange"],
            "medium":   COLORS["yellow"],
            "low":      COLORS["green"],
        }
        rows = []
        for d in deps:
            crit = d.get("criticality", "medium")
            c = crit_colors.get(crit, COLORS["text_muted"])
            f_from = _FLAGS3.get(d.get("from", ""), "")
            f_to   = _FLAGS3.get(d.get("to", ""), "")
            pct_field = d.get("pct_imports") or d.get("pct_holdings")
            pct_str = f"{pct_field}%" if pct_field else "—"
            rows.append(html.Tr([
                html.Td(f"{f_from} {d.get('from','')}", style={"padding": "6px 10px"}),
                html.Td(f"{f_to} {d.get('to','')}", style={"padding": "6px 10px"}),
                html.Td(d.get("category", ""), style={"padding": "6px 10px",
                         "fontSize": "0.72rem", "color": COLORS["text_muted"]}),
                html.Td(d.get("item", ""), style={"padding": "6px 10px", "fontSize": "0.78rem"}),
                html.Td(pct_str, style={"padding": "6px 10px", "textAlign": "right",
                         "fontWeight": "600", "color": COLORS["orange"]}),
                html.Td(
                    html.Span(crit.upper(), style={
                        "background": f"{c}22", "color": c,
                        "border": f"1px solid {c}55", "borderRadius": "3px",
                        "padding": "1px 8px", "fontSize": "0.68rem",
                    }),
                    style={"padding": "6px 10px"},
                ),
            ], style={"borderBottom": f"1px solid {COLORS['border']}"}))

        return html.Div([
            html.Table(
                [
                    html.Thead(html.Tr([
                        html.Th(h, style={"padding": "6px 10px", "textAlign": "left",
                                          "fontSize": "0.68rem", "color": COLORS["text_label"],
                                          "borderBottom": f"1px solid {COLORS['border']}"})
                        for h in ["Desde", "Hacia", "Categoría", "Ítem", "% Dependencia", "Criticidad"]
                    ])),
                    html.Tbody(rows),
                ],
                style={"width": "100%", "borderCollapse": "collapse",
                       "background": COLORS["card_bg"], "borderRadius": "6px"},
            )
        ], style={"overflowX": "auto"})

    # ── Calendario ────────────────────────────────────────────────────────────
    @app.callback(
        Output("m10-calendar-list", "children"),
        Input("m10-cal-category-filter", "value"),
        Input("m10-cal-period-filter",   "value"),
        Input("m10-refresh-interval",    "n_intervals"),
    )
    def update_calendar(category, period_days, _n):
        data = load_json_data("political_calendar.json") or {}
        events = data.get("events", [])

        now = datetime.utcnow()
        cutoff = now + timedelta(days=period_days or 90)

        filtered = []
        for e in events:
            try:
                dt = datetime.strptime(e["date"], "%Y-%m-%d")
            except Exception:
                continue
            if dt < now or dt > cutoff:
                continue
            if category and category != "all" and e.get("category") != category:
                continue
            filtered.append((dt, e))

        filtered.sort(key=lambda x: x[0])

        if not filtered:
            return html.Div(
                "Sin eventos para el período y filtro seleccionados",
                style={"color": COLORS["text_muted"], "fontSize": "0.82rem"},
            )

        cat_colors = {
            "monetary_policy": COLORS["accent"],
            "election":        COLORS["green"],
            "geopolitics":     COLORS["red"],
            "energy":          COLORS["orange"],
        }
        cat_labels = {
            "monetary_policy": "Política Monetaria",
            "election":        "Elecciones",
            "geopolitics":     "Geopolítica",
            "energy":          "Energía/OPEP",
        }
        impact_colors = {
            "very_high": COLORS["red"],
            "high":      COLORS["orange"],
            "medium":    COLORS["yellow"],
            "low":       COLORS["text_muted"],
        }
        impact_labels = {
            "very_high": "Muy alto", "high": "Alto",
            "medium": "Medio", "low": "Bajo",
        }

        items = []
        for dt, e in filtered:
            days_left = (dt - now).days
            cat = e.get("category", "")
            imp = e.get("impact", "medium")
            cat_color = cat_colors.get(cat, COLORS["text_muted"])
            imp_color = impact_colors.get(imp, COLORS["text_muted"])

            countries = e.get("countries", [])
            flags = " ".join(_FLAGS3.get(c, c) for c in countries)

            items.append(
                html.Div(
                    [
                        dbc.Row(
                            [
                                dbc.Col(
                                    html.Div(
                                        [
                                            html.Div(
                                                f"{days_left}d",
                                                style={"fontSize": "1.1rem", "fontWeight": "700",
                                                       "color": COLORS["accent"], "lineHeight": "1"},
                                            ),
                                            html.Div(dt.strftime("%d %b %Y"),
                                                     style={"fontSize": "0.65rem", "color": COLORS["text_muted"]}),
                                        ],
                                        style={"textAlign": "center"},
                                    ),
                                    width=2,
                                ),
                                dbc.Col(
                                    [
                                        html.Div(
                                            [
                                                html.Span(
                                                    cat_labels.get(cat, cat),
                                                    style={
                                                        "background": f"{cat_color}22", "color": cat_color,
                                                        "border": f"1px solid {cat_color}55",
                                                        "borderRadius": "3px", "padding": "1px 6px",
                                                        "fontSize": "0.65rem", "marginRight": "6px",
                                                    },
                                                ),
                                                html.Span(
                                                    impact_labels.get(imp, imp),
                                                    style={
                                                        "background": f"{imp_color}22", "color": imp_color,
                                                        "border": f"1px solid {imp_color}55",
                                                        "borderRadius": "3px", "padding": "1px 6px",
                                                        "fontSize": "0.65rem",
                                                    },
                                                ),
                                            ],
                                            style={"marginBottom": "3px"},
                                        ),
                                        html.Div(
                                            e.get("title", ""),
                                            style={"fontWeight": "600", "fontSize": "0.82rem"},
                                        ),
                                        html.Div(
                                            e.get("description", ""),
                                            style={"fontSize": "0.72rem", "color": COLORS["text_muted"],
                                                   "marginTop": "2px"},
                                        ),
                                    ],
                                    width=9,
                                ),
                                dbc.Col(
                                    html.Div(flags, style={"fontSize": "1.1rem", "textAlign": "right"}),
                                    width=1,
                                ),
                            ],
                            align="center",
                            className="g-0",
                        ),
                    ],
                    style={
                        "background": COLORS["card_bg"],
                        "border": f"1px solid {COLORS['border']}",
                        "borderLeft": f"3px solid {cat_color}",
                        "borderRadius": "4px",
                        "padding": "10px 14px",
                        "marginBottom": "6px",
                    },
                )
            )

        return html.Div(items)

    # ── Alertas geopolíticas ──────────────────────────────────────────────────
    @app.callback(
        Output("m10-geo-alerts",       "children"),
        Output("m10-intl-meetings",    "children"),
        Input("m10-refresh-interval",  "n_intervals"),
        Input("m10-tabs",              "value"),
    )
    def update_alerts_and_meetings(_n, tab):
        if tab != "tab-calendar":
            return no_update, no_update

        # Obtener valores actuales
        gpr_global, _ = get_latest_value(ID_GPR_GLOBAL, source="FRED_GPR")
        gpr_isr, _    = get_latest_value(ID_GPR_ISR,    source="FRED_GPR")
        gpr_chn, _    = get_latest_value(ID_GPR_CHN,    source="FRED_GPR")
        brent, _      = get_latest_value(ID_BRENT)

        # Definición de alertas predefinidas
        ALERT_DEFS = [
            {
                "id": "gpr_global_200",
                "label": "GPR Global > 200",
                "desc": "Tensión geopolítica en zona histórica de crisis",
                "active": gpr_global is not None and gpr_global > 200,
                "current": f"{gpr_global:.0f}" if gpr_global else "—",
                "threshold": "200",
            },
            {
                "id": "gpr_isr_300",
                "label": "GPR ISR/ME > 300",
                "desc": "Riesgo de escalada en Oriente Medio en zona crítica",
                "active": gpr_isr is not None and gpr_isr > 300,
                "current": f"{gpr_isr:.0f}" if gpr_isr else "—",
                "threshold": "300",
            },
            {
                "id": "gpr_chn_200",
                "label": "GPR China > 200",
                "desc": "Riesgo geopolítico en Asia-Pacífico muy elevado",
                "active": gpr_chn is not None and gpr_chn > 200,
                "current": f"{gpr_chn:.0f}" if gpr_chn else "—",
                "threshold": "200",
            },
            {
                "id": "brent_120",
                "label": "Brent > 120$",
                "desc": "Shock energético severo — impacto inflacionario crítico",
                "active": brent is not None and brent > 120,
                "current": f"{brent:.1f}$" if brent else "—",
                "threshold": "120$",
            },
            {
                "id": "brent_150",
                "label": "Brent > 150$",
                "desc": "Crisis energética extrema — nivel 1973/1979",
                "active": brent is not None and brent > 150,
                "current": f"{brent:.1f}$" if brent else "—",
                "threshold": "150$",
            },
        ]

        alert_items = []
        for a in ALERT_DEFS:
            active = a["active"]
            if active:
                icon, color, bg = "🚨", COLORS["red"], f"{COLORS['red']}11"
            else:
                icon, color, bg = "✅", COLORS["green"], f"{COLORS['green']}08"

            alert_items.append(
                html.Div(
                    [
                        html.Span(icon, style={"marginRight": "8px", "fontSize": "0.9rem"}),
                        html.Div(
                            [
                                html.Span(a["label"], style={"fontWeight": "600", "fontSize": "0.82rem"}),
                                html.Span(f" · Actual: {a['current']} (umbral: {a['threshold']})",
                                          style={"fontSize": "0.72rem", "color": COLORS["text_muted"]}),
                                html.Div(a["desc"],
                                         style={"fontSize": "0.72rem", "color": color if active else COLORS["text_muted"]}),
                            ],
                        ),
                    ],
                    style={
                        "display": "flex", "alignItems": "flex-start",
                        "background": bg,
                        "border": f"1px solid {color}33",
                        "borderRadius": "5px",
                        "padding": "8px 12px",
                        "marginBottom": "6px",
                    },
                )
            )

        # Reuniones internacionales (de political_calendar.json)
        data = load_json_data("political_calendar.json") or {}
        events = data.get("events", [])
        now = datetime.utcnow()
        cutoff_6m = now + timedelta(days=180)
        intl_categories = {"monetary_policy", "geopolitics", "energy"}

        intl = []
        for e in events:
            try:
                dt = datetime.strptime(e["date"], "%Y-%m-%d")
            except Exception:
                continue
            if dt < now or dt > cutoff_6m:
                continue
            if e.get("category") in intl_categories:
                intl.append((dt, e))

        intl.sort(key=lambda x: x[0])
        meeting_rows = []
        for dt, e in intl:
            days_left = (dt - now).days
            countries = e.get("countries", [])
            flags = " ".join(_FLAGS3.get(c, c) for c in countries)
            meeting_rows.append(html.Tr([
                html.Td(dt.strftime("%d %b %Y"), style={"padding": "5px 10px", "fontSize": "0.75rem"}),
                html.Td(f"{days_left}d", style={"padding": "5px 10px", "color": COLORS["accent"],
                         "fontWeight": "600", "textAlign": "right"}),
                html.Td(e.get("title", ""), style={"padding": "5px 10px", "fontWeight": "600", "fontSize": "0.82rem"}),
                html.Td(e.get("description", ""), style={"padding": "5px 10px", "fontSize": "0.72rem",
                         "color": COLORS["text_muted"]}),
                html.Td(flags, style={"padding": "5px 10px", "textAlign": "right"}),
            ], style={"borderBottom": f"1px solid {COLORS['border']}"}))

        meetings_panel = html.Table(
            [
                html.Thead(html.Tr([
                    html.Th(h, style={"padding": "5px 10px", "textAlign": "left",
                                      "fontSize": "0.68rem", "color": COLORS["text_label"],
                                      "borderBottom": f"1px solid {COLORS['border']}"})
                    for h in ["Fecha", "En", "Evento", "Agenda prevista", ""]
                ])),
                html.Tbody(meeting_rows or [
                    html.Tr(html.Td("Sin reuniones en los próximos 6 meses",
                                    colSpan=5, style={"padding": "10px", "color": COLORS["text_muted"]}))
                ]),
            ],
            style={"width": "100%", "borderCollapse": "collapse",
                   "background": COLORS["card_bg"], "borderRadius": "6px"},
        )

        return html.Div(alert_items), meetings_panel
