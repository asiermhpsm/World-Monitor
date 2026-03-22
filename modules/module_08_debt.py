"""
Módulo 8 — Deuda y Sostenibilidad Fiscal
Se renderiza cuando la URL es /module/8.

Exporta:
  render_module_8()               -> layout completo
  register_callbacks_module_8(app) -> registra todos los callbacks
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, dcc, html, no_update

from components.chart_config import get_base_layout, get_time_range_buttons
from components.common import create_section_header
from config import COLORS
from modules.data_helpers import (
    calculate_debt_sustainability,
    calculate_financial_repression_transfer,
    get_change,
    get_latest_value,
    get_series,
    get_world_bank_indicator,
    load_json_data,
)

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

# ── IDs de indicadores ────────────────────────────────────────────────────────

ID_DEBT_GDP_US     = "fred_debt_gdp_us"
ID_DEFICIT_GDP_US  = "fred_deficit_gdp_us"
ID_INTEREST_PAY_US = "fred_interest_pay_us"
ID_TAX_REV_US      = "fred_tax_revenues_us"
ID_FEDERAL_DEBT_US = "fred_federal_debt_us"
ID_REAL_RATE_US    = "fred_real_rate_us"
ID_CPI_YOY_US      = "fred_cpi_yoy_us"
ID_FED_FUNDS       = "fred_fed_funds_us"
ID_YIELD_10Y_US    = "fred_yield_10y_us"

ID_SPREAD_ES = "ecb_spread_es_de"
ID_SPREAD_IT = "ecb_spread_it_de"
ID_SPREAD_FR = "ecb_spread_fr_de"
ID_BUND_10Y  = "ecb_bund_10y_de"
ID_YIELD_ES  = "ecb_yield_10y_es"
ID_YIELD_IT  = "ecb_yield_10y_it"
ID_YIELD_FR  = "ecb_yield_10y_fr"

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
_FORMULA_BOX = {
    "background": "#0d1320",
    "border": f"1px solid {COLORS['accent']}40",
    "borderRadius": "6px",
    "padding": "16px 20px",
    "fontFamily": "monospace",
    "fontSize": "1.1rem",
    "color": COLORS["text"],
    "textAlign": "center",
    "marginBottom": "12px",
}

# Colores por país
_CC = {
    "USA": "#3b82f6",
    "JPN": "#ec4899",
    "DEU": "#10b981",
    "FRA": "#8b5cf6",
    "ESP": "#f59e0b",
    "ITA": "#ef4444",
    "GBR": "#06b6d4",
    "CHN": "#f97316",
    "BRA": "#14b8a6",
    "EMU": "#9ca3af",
}

# ── Helpers internos ──────────────────────────────────────────────────────────

def _safe(val, fmt=".1f", suffix="") -> str:
    if val is None:
        return "—"
    try:
        return f"{val:{fmt}}{suffix}"
    except Exception:
        return "—"


def _arrow(chg: Optional[float], higher_bad: bool = True) -> str:
    if chg is None:
        return ""
    up = "↑" if chg > 0 else ("↓" if chg < 0 else "→")
    return up


def _chg_color(chg: Optional[float], higher_bad: bool = True) -> str:
    if chg is None:
        return COLORS["text_muted"]
    if chg == 0:
        return COLORS["text_muted"]
    if higher_bad:
        return COLORS["red"] if chg > 0 else COLORS["green"]
    return COLORS["green"] if chg > 0 else COLORS["red"]


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
            style={"fontSize": "1.10rem", "fontWeight": "700", "color": COLORS["text"],
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


def _empty_fig(msg: str = "Sin datos disponibles", height: int = 350) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        **get_base_layout(height=height),
        annotations=[{"text": msg, "xref": "paper", "yref": "paper",
                       "x": 0.5, "y": 0.5, "showarrow": False,
                       "font": {"color": COLORS["text_muted"], "size": 13}}],
    )
    return fig


def _rgba(hex_color: str, alpha: float = 0.15) -> str:
    """Convierte #RRGGBB + alpha a rgba() válido para Plotly."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def _layout(height: int = 400, title_text: str | None = None) -> dict:
    """
    Devuelve el layout base sin el sub-dict 'title' en xaxis/yaxis,
    para evitar el conflicto de keyword doble al añadir title propio.
    """
    base = get_base_layout(height=height, title=title_text)
    for ax in ("xaxis", "yaxis"):
        if ax in base and "title" in base[ax]:
            base[ax] = {k: v for k, v in base[ax].items() if k != "title"}
    return base


def _rating_color(rating: str) -> str:
    """Color según rating crediticio."""
    if rating in ("AAA", "AA+", "AA", "AA-", "Aaa", "Aa1", "Aa2", "Aa3"):
        return COLORS["green"]
    if rating in ("A+", "A", "A-", "A1", "A2", "A3"):
        return COLORS["green_yellow"]
    if rating in ("BBB+", "BBB", "BBB-", "Baa1", "Baa2", "Baa3"):
        return COLORS["yellow"]
    if rating in ("BB+", "BB", "BB-", "Ba1", "Ba2", "Ba3"):
        return COLORS["orange"]
    return COLORS["red"]


def _load_json(filename: str) -> dict:
    try:
        path = DATA_DIR / filename
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.debug("_load_json(%s): %s", filename, e)
        return {}


def _sustainability_badge(classification: str) -> html.Span:
    cfg = {
        "sostenible":       ("SOSTENIBLE",       COLORS["green"],       "#0a2218"),
        "estabilizando":    ("ESTABILIZANDO",    COLORS["green_yellow"], "#1a2200"),
        "insostenible_leve":("INSOST. LEVE",     COLORS["yellow"],      "#201900"),
        "insostenible_grave":("INSOST. GRAVE",   COLORS["red"],         "#200808"),
    }
    label, color, bg = cfg.get(classification, ("DESCONOCIDO", COLORS["text_muted"], "#111"))
    return html.Span(label, style={
        "fontSize": "0.65rem", "fontWeight": "700", "color": color,
        "background": bg, "padding": "2px 7px", "borderRadius": "4px",
        "border": f"1px solid {color}40",
    })


# ── EU countries for stability pact ──────────────────────────────────────────

_EU_COUNTRIES = [
    ("AT", "AUT", "🇦🇹 Austria"),    ("BE", "BEL", "🇧🇪 Bélgica"),
    ("BG", "BGR", "🇧🇬 Bulgaria"),   ("HR", "HRV", "🇭🇷 Croacia"),
    ("CY", "CYP", "🇨🇾 Chipre"),     ("CZ", "CZE", "🇨🇿 Chequia"),
    ("DK", "DNK", "🇩🇰 Dinamarca"),  ("EE", "EST", "🇪🇪 Estonia"),
    ("FI", "FIN", "🇫🇮 Finlandia"),  ("FR", "FRA", "🇫🇷 Francia"),
    ("DE", "DEU", "🇩🇪 Alemania"),   ("GR", "GRC", "🇬🇷 Grecia"),
    ("HU", "HUN", "🇭🇺 Hungría"),    ("IE", "IRL", "🇮🇪 Irlanda"),
    ("IT", "ITA", "🇮🇹 Italia"),     ("LV", "LVA", "🇱🇻 Letonia"),
    ("LT", "LTU", "🇱🇹 Lituania"),  ("LU", "LUX", "🇱🇺 Luxemburgo"),
    ("MT", "MLT", "🇲🇹 Malta"),      ("NL", "NLD", "🇳🇱 Países Bajos"),
    ("PL", "POL", "🇵🇱 Polonia"),    ("PT", "PRT", "🇵🇹 Portugal"),
    ("RO", "ROU", "🇷🇴 Rumanía"),    ("SK", "SVK", "🇸🇰 Eslovaquia"),
    ("SI", "SVN", "🇸🇮 Eslovenia"),  ("ES", "ESP", "🇪🇸 España"),
    ("SE", "SWE", "🇸🇪 Suecia"),
]

# Países actualmente en Procedimiento de Déficit Excesivo (PDE) — aprox. 2024-2025
_IN_EDP = {"BEL", "FRA", "HUN", "ITA", "MLT", "POL", "ROU", "SVK", "EST", "CZE"}


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — DEUDA GLOBAL
# ══════════════════════════════════════════════════════════════════════════════

def _build_tab1() -> html.Div:
    return html.Div([
        # 1.1 Mapa mundial
        create_section_header(
            "1.1 — Mapa Mundial de Deuda Pública (% PIB)",
            subtitle="Banco Mundial · GC.DOD.TOTL.GD.ZS",
        ),
        html.Div([
            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.Label("Año:", style={"fontSize": "0.78rem", "color": COLORS["text_muted"], "marginRight": "8px"}),
                        dcc.Dropdown(
                            id="m8-year-dropdown",
                            options=[{"label": str(y), "value": y} for y in range(2023, 1999, -1)],
                            value=2022,
                            clearable=False,
                            style={"width": "110px", "display": "inline-block",
                                   "fontSize": "0.80rem", "background": COLORS["card_bg"]},
                        ),
                    ], style={"marginBottom": "8px", "display": "flex", "alignItems": "center"}),
                    dcc.Graph(id="m8-world-map", config={"displayModeBar": False}),
                ], width=12),
            ]),
            html.Div(id="m8-top-bottom-panel", style={"marginTop": "12px"}),
        ], style=_CARD),

        # 1.2 Evolución histórica
        create_section_header(
            "1.2 — Evolución Histórica de la Deuda Pública (% PIB)",
            subtitle="EE.UU., Japón, Eurozona, Alemania, Francia, España, Italia, China, UK · desde 2000",
        ),
        html.Div([
            dcc.Graph(id="m8-debt-evolution-chart", config={"displayModeBar": False}),
            html.Div(
                "La deuda pública mundial ha prácticamente triplicado desde 2000 como % del PIB global, "
                "impulsada por las respuestas a la Crisis Financiera de 2008 y a la pandemia de COVID-19.",
                style=_NOTE,
            ),
        ], style=_CARD),

        # 1.3 Tabla comparativa
        create_section_header(
            "1.3 — Tabla Comparativa Global de Deuda",
            subtitle="Principales economías · datos Banco Mundial y ratings estáticos",
        ),
        html.Div([
            html.Div(id="m8-debt-comparison-table"),
        ], style=_CARD),

    ], style=_SECTION)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — EE.UU. EN DETALLE
# ══════════════════════════════════════════════════════════════════════════════

def _build_tab2() -> html.Div:
    return html.Div([
        # 2.1 Contador de deuda
        create_section_header(
            "2.1 — La Deuda Federal Americana",
            subtitle="FRED · GFDEBTN (trimestral) — datos más recientes disponibles",
        ),
        html.Div([
            html.Div(id="m8-us-counter-panel"),
        ], style=_CARD),

        # 2.2 Histórico + proyecciones CBO
        create_section_header(
            "2.2 — Histórico y Proyecciones CBO de la Deuda Americana (% PIB)",
            subtitle="FRED · GFDEGDQ188S + Congressional Budget Office",
        ),
        html.Div([
            dcc.Graph(id="m8-us-historical-chart", config={"displayModeBar": False}),
        ], style=_CARD),

        # 2.3 Muro de vencimientos
        create_section_header(
            "2.3 — El Muro de Vencimientos de la Deuda Americana",
            subtitle="US Treasury · deuda que vence y debe refinanciarse por año",
        ),
        html.Div([
            dcc.Graph(id="m8-maturity-wall-chart", config={"displayModeBar": False}),
            html.Div(id="m8-maturity-note"),
        ], style=_CARD),

        # 2.4 Servicio de la deuda
        create_section_header(
            "2.4 — Coste del Servicio de la Deuda Federal Americana",
            subtitle="FRED · A091RC1Q027SBEA / W006RC1Q027SBEA × 100",
        ),
        html.Div([
            dbc.Row([
                dbc.Col(
                    dcc.Graph(id="m8-debt-service-chart", config={"displayModeBar": False}),
                    width=8,
                ),
                dbc.Col(
                    html.Div(id="m8-budget-panel"),
                    width=4,
                ),
            ], className="g-2"),
        ], style=_CARD),

        # 2.5 Principales tenedores
        create_section_header(
            "2.5 — Principales Tenedores de Deuda Americana",
            subtitle="US Treasury TIC Data",
        ),
        html.Div([
            dcc.Graph(id="m8-holders-chart", config={"displayModeBar": False}),
            html.Div(
                "China ha reducido sus tenencias de deuda americana a la mitad desde 2013. "
                "Si esta tendencia se acelerara, el Tesoro americano tendría que ofrecer tipos más altos "
                "para atraer compradores, incrementando el coste de financiación.",
                style=_NOTE,
            ),
        ], style=_CARD),

    ], style=_SECTION)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — EUROPA EN DETALLE
# ══════════════════════════════════════════════════════════════════════════════

def _build_tab3() -> html.Div:
    return html.Div([
        # 3.1 Pacto de estabilidad
        create_section_header(
            "3.1 — El Pacto de Estabilidad: Quién Cumple y Quién No",
            subtitle="Eurostat EDP · criterios: deuda <60% PIB y déficit <3% PIB",
        ),
        html.Div([
            html.Div(id="m8-stability-table"),
            html.Div(id="m8-stability-summary"),
            html.Div(
                "El Pacto de Estabilidad fue suspendido durante COVID (2020-2022) y renegociado en 2024. "
                "Francia e Italia llevan décadas incumpliendo sistemáticamente el criterio de deuda.",
                style=_NOTE,
            ),
        ], style=_CARD),

        # 3.2 Italia
        create_section_header(
            "3.2 — Italia: El Riesgo Sistémico de la Eurozona",
            subtitle="ECB · prima de riesgo BTP–Bund 10Y",
        ),
        html.Div([
            dbc.Row([
                dbc.Col(
                    dcc.Graph(id="m8-italy-spread-chart", config={"displayModeBar": False}),
                    width=8,
                ),
                dbc.Col(
                    html.Div(id="m8-italy-panel"),
                    width=4,
                ),
            ], className="g-2"),
            html.Div(
                "Italia tiene una deuda de ~2.8 billones de euros (~140% del PIB). "
                "Un aumento de 100 puntos básicos en los tipos supone ~28.000M€ adicionales en intereses "
                "anuales cuando vence y se refinancia la deuda.",
                style=_NOTE,
            ),
        ], style=_CARD),

        # 3.3 Francia
        create_section_header(
            "3.3 — Francia: El Nuevo Eslabón Débil",
            subtitle="ECB · prima de riesgo OAT–Bund 10Y vs España",
        ),
        html.Div([
            dcc.Graph(id="m8-france-spread-chart", config={"displayModeBar": False}),
            html.Div(
                "La degradación fiscal de Francia es uno de los desarrollos más significativos de la "
                "eurozona reciente. Un país que históricamente era pilar del euro ahora tiene métricas "
                "fiscales similares a las de países periféricos, reduciendo el cortafuegos de la eurozona.",
                style=_NOTE,
            ),
        ], style=_CARD),

        # 3.4 España
        create_section_header(
            "3.4 — España: Análisis Específico",
            subtitle="Banco Mundial · Eurostat · ECB",
        ),
        html.Div([
            html.Div(id="m8-spain-metrics"),
            dbc.Row([
                dbc.Col(
                    dcc.Graph(id="m8-spain-debt-chart", config={"displayModeBar": False}),
                    width=8,
                ),
                dbc.Col(
                    html.Div(id="m8-spain-context"),
                    width=4,
                ),
            ], className="g-2"),
            html.Div(
                "España pasó de ser uno de los países más saneados fiscalmente de Europa "
                "(deuda del 36% del PIB en 2007) a necesitar un rescate parcial de su sistema bancario "
                "en 2012. La recuperación ha sido notable pero la deuda sigue siendo estructuralmente elevada.",
                style=_NOTE,
            ),
        ], style=_CARD),

    ], style=_SECTION)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — SOSTENIBILIDAD FISCAL
# ══════════════════════════════════════════════════════════════════════════════

def _build_tab4() -> html.Div:
    return html.Div([
        # 4.1 La ecuación
        create_section_header(
            "4.1 — La Ecuación de la Dinámica de la Deuda",
            subtitle="Marco analítico estándar de sostenibilidad fiscal",
        ),
        html.Div([
            html.Div("Δ(D/Y) = (r − g) × (D/Y) − pb", style=_FORMULA_BOX),
            html.Div([
                html.Div([
                    html.Span("Δ(D/Y)", style={"fontWeight": "700", "color": COLORS["accent"]}),
                    html.Span(" = cambio en la ratio deuda/PIB", style={"color": COLORS["text_muted"]}),
                ], style={"marginBottom": "4px"}),
                html.Div([
                    html.Span("r", style={"fontWeight": "700", "color": COLORS["yellow"]}),
                    html.Span(" = tipo de interés real de la deuda (en %)", style={"color": COLORS["text_muted"]}),
                ], style={"marginBottom": "4px"}),
                html.Div([
                    html.Span("g", style={"fontWeight": "700", "color": COLORS["green"]}),
                    html.Span(" = tasa de crecimiento real del PIB (en %)", style={"color": COLORS["text_muted"]}),
                ], style={"marginBottom": "4px"}),
                html.Div([
                    html.Span("D/Y", style={"fontWeight": "700", "color": COLORS["text_muted"]}),
                    html.Span(" = ratio deuda/PIB actual", style={"color": COLORS["text_muted"]}),
                ], style={"marginBottom": "4px"}),
                html.Div([
                    html.Span("pb", style={"fontWeight": "700", "color": COLORS["green_yellow"]}),
                    html.Span(" = superávit primario (ingresos − gastos excl. intereses) como % del PIB",
                              style={"color": COLORS["text_muted"]}),
                ], style={"marginBottom": "4px"}),
            ], style={"background": "#0d1320", "padding": "12px 16px", "borderRadius": "6px",
                      "fontSize": "0.82rem", "lineHeight": "1.8", "marginBottom": "12px"}),
            html.Div(
                "La deuda como % del PIB BAJA cuando: (1) el crecimiento económico supera al tipo "
                "de interés real, O (2) el gobierno tiene superávit primario. La deuda SUBE cuando "
                "el tipo de interés supera al crecimiento Y el gobierno tiene déficit primario.",
                style={**_NOTE, "fontStyle": "normal"},
            ),
        ], style=_CARD),

        # 4.2 Calculadora por país
        create_section_header(
            "4.2 — Calculadora de Sostenibilidad por País",
            subtitle="Estimación basada en Banco Mundial + BCE + FRED",
        ),
        html.Div([
            html.Div(id="m8-sustainability-table"),
            html.Div(id="m8-sustainability-interpretation"),
        ], style=_CARD),

        # 4.3 Escenarios de resolución
        create_section_header(
            "4.3 — Mecanismos Históricos de Resolución de Deuda Elevada",
            subtitle="Los cuatro caminos que han tomado los países para reducir su deuda",
        ),
        html.Div([
            dbc.Row([
                dbc.Col(_resolution_card(
                    "📈", "Crecimiento", "green",
                    "El país crece más rápido que su deuda. Ejemplo: EE.UU. post-WWII redujo su deuda "
                    "del 120% al 30% del PIB entre 1946 y 1980 gracias al crecimiento sostenido.",
                    "Requiere g > r de forma sostenida",
                    "BAJA — envejecimiento demográfico + deuda alta = crecimiento limitado",
                ), width=12, md=6, lg=3),
                dbc.Col(_resolution_card(
                    "✂️", "Austeridad", "yellow",
                    "El gobierno recorta gastos y/o sube impuestos para generar superávit primario. "
                    "Ejemplo: Grecia 2010-2018, recortes del 25% del gasto público.",
                    "Requiere voluntad política y tolerancia social",
                    "MEDIA — políticamente difícil pero única opción ortodoxa",
                ), width=12, md=6, lg=3),
                dbc.Col(_resolution_card(
                    "🏦", "Represión Financiera", "orange",
                    "El gobierno mantiene tipos bajos y tolera inflación, erosionando el valor real "
                    "de la deuda. Ejemplo: EE.UU. y UK años 50-70, tipos reales negativos décadas.",
                    "Requiere control del banco central",
                    "ALTA — el camino con menos resistencia política",
                ), width=12, md=6, lg=3),
                dbc.Col(_resolution_card(
                    "💥", "Reestructuración", "red",
                    "El gobierno negocia con sus acreedores para reducir el valor nominal o extender plazos. "
                    "Ejemplo: Grecia 2012 (mayor default soberano de la historia en aquel momento).",
                    "Solo cuando las otras tres opciones han fallado",
                    "MUY BAJA para países desarrollados — impensable para EE.UU. o Japón a corto plazo",
                ), width=12, md=6, lg=3),
            ], className="g-2"),
        ], style=_CARD),

    ], style=_SECTION)


def _resolution_card(emoji, title, color_key, desc, condition, probability) -> html.Div:
    color = COLORS.get(color_key, COLORS["text_muted"])
    return html.Div([
        html.Div(f"{emoji} {title}", style={
            "fontSize": "1rem", "fontWeight": "700", "color": color,
            "marginBottom": "8px",
        }),
        html.Div(desc, style={"fontSize": "0.78rem", "color": COLORS["text"], "marginBottom": "8px", "lineHeight": "1.5"}),
        html.Div([
            html.Div("Condición:", style={"fontSize": "0.70rem", "color": COLORS["text_label"], "fontWeight": "600"}),
            html.Div(condition, style={"fontSize": "0.75rem", "color": COLORS["text_muted"]}),
        ], style={"marginBottom": "6px"}),
        html.Div([
            html.Div("Probabilidad actual:", style={"fontSize": "0.70rem", "color": COLORS["text_label"], "fontWeight": "600"}),
            html.Div(probability, style={"fontSize": "0.75rem", "color": color}),
        ]),
    ], style={
        "background": "#0d1320",
        "border": f"1px solid {color}30",
        "borderTop": f"3px solid {color}",
        "borderRadius": "6px",
        "padding": "14px",
        "height": "100%",
    })


# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — REPRESIÓN FINANCIERA
# ══════════════════════════════════════════════════════════════════════════════

def _build_tab5() -> html.Div:
    return html.Div([
        # 5.1 Simulación
        create_section_header(
            "5.1 — Cómo la Inflación Reduce el Valor Real de la Deuda",
            subtitle="Simulación interactiva de erosión del valor real",
        ),
        html.Div([
            dbc.Row([
                dbc.Col([
                    html.Label("Deuda inicial (índice 100):", style={"fontSize": "0.78rem", "color": COLORS["text_muted"]}),
                    dcc.Slider(id="m8-sim-debt", min=50, max=200, step=10, value=100,
                               marks={50: "50", 100: "100", 150: "150", 200: "200"},
                               tooltip={"placement": "bottom", "always_visible": False}),
                ], width=12, md=4),
                dbc.Col([
                    html.Label("Inflación anual (%):", style={"fontSize": "0.78rem", "color": COLORS["text_muted"]}),
                    dcc.Slider(id="m8-sim-inflation", min=0.5, max=10.0, step=0.5, value=3.0,
                               marks={1: "1%", 3: "3%", 5: "5%", 8: "8%", 10: "10%"},
                               tooltip={"placement": "bottom", "always_visible": False}),
                ], width=12, md=4),
                dbc.Col([
                    html.Label("Horizonte temporal (años):", style={"fontSize": "0.78rem", "color": COLORS["text_muted"]}),
                    dcc.Slider(id="m8-sim-years", min=5, max=30, step=5, value=10,
                               marks={5: "5", 10: "10", 20: "20", 30: "30"},
                               tooltip={"placement": "bottom", "always_visible": False}),
                ], width=12, md=4),
            ], className="g-3", style={"marginBottom": "16px"}),
            dcc.Graph(id="m8-repression-sim-chart", config={"displayModeBar": False}),
            html.Div(id="m8-repression-sim-text", style={**_NOTE, "fontStyle": "normal"}),
        ], style=_CARD),

        # 5.2 Histórico tipos reales EE.UU.
        create_section_header(
            "5.2 — Episodios Históricos de Represión Financiera en EE.UU.",
            subtitle="FRED · tipo real = Fed Funds – CPI YoY · desde 1954",
        ),
        html.Div([
            dcc.Graph(id="m8-real-rate-chart", config={"displayModeBar": False}),
            html.Div(
                "En el período 1946-1980, EE.UU. redujo su deuda del 120% al 30% del PIB en parte "
                "gracias a décadas de represión financiera. Los tenedores de bonos del gobierno americano "
                "perdieron poder adquisitivo real durante generaciones.",
                style=_NOTE,
            ),
        ], style=_CARD),

        # 5.3 Quién paga
        create_section_header(
            "5.3 — Quién Paga la Represión Financiera",
            subtitle="Transferencia de riqueza de ahorradores a deudores",
        ),
        html.Div([
            html.Div(id="m8-repression-transfer-panel"),
            html.Div(
                "La represión financiera es un impuesto invisible que recae desproporcionadamente sobre "
                "los ahorradores más conservadores (que guardan dinero en depósitos o bonos del Estado) "
                "y beneficia a quienes tienen deuda, incluyendo principalmente al propio Estado.",
                style=_NOTE,
            ),
        ], style=_CARD),

    ], style=_SECTION)


# ══════════════════════════════════════════════════════════════════════════════
# HEADER — 6 métricas
# ══════════════════════════════════════════════════════════════════════════════

def _build_header_metrics() -> html.Div:
    metrics = []

    # 1. Deuda EE.UU. % PIB
    try:
        cur, prev, chg_abs, chg_pct = get_change(ID_DEBT_GDP_US, period_days=400)
        val_str = f"{_safe(cur, '.1f')}% PIB" if cur else "—"
        arrow = _arrow(chg_abs, higher_bad=True)
        sub = f"{arrow} {'↑ subiendo' if chg_abs and chg_abs > 0 else '↓ bajando'} vs año ant." if chg_abs else "Sin variación"
        metrics.append(_compact_metric("DEUDA EE.UU. % PIB", val_str, sub, _chg_color(chg_abs, higher_bad=True)))
    except Exception:
        metrics.append(_compact_metric("DEUDA EE.UU. % PIB", "—", "Sin datos", COLORS["text_muted"]))

    # 2. Déficit fiscal EE.UU. % PIB
    try:
        cur, _, _, _ = get_change(ID_DEFICIT_GDP_US, period_days=400)
        val_str = f"{_safe(cur, '.1f')}% PIB" if cur else "—"
        color = COLORS["red"] if cur and cur < -3 else COLORS["yellow"] if cur and cur < 0 else COLORS["green"]
        sub = "Déficit" if cur and cur < 0 else ("Superávit" if cur and cur > 0 else "Sin datos")
        metrics.append(_compact_metric("DÉFICIT FISCAL EE.UU.", val_str, sub, color))
    except Exception:
        metrics.append(_compact_metric("DÉFICIT FISCAL EE.UU.", "—", "Sin datos", COLORS["text_muted"]))

    # 3. Intereses como % ingresos fiscales
    try:
        int_val, _ = get_latest_value(ID_INTEREST_PAY_US)
        tax_val, _ = get_latest_value(ID_TAX_REV_US)
        if int_val and tax_val and tax_val > 0:
            ratio = int_val / tax_val * 100
            val_str = f"{ratio:.1f}%"
            badge = None
            if ratio > 20:
                badge = html.Span("⚠ ALERTA", style={
                    "fontSize": "0.55rem", "fontWeight": "800", "color": "#fff",
                    "background": "#f97316", "padding": "1px 5px", "borderRadius": "3px",
                })
            color = COLORS["red"] if ratio > 20 else (COLORS["yellow"] if ratio > 15 else COLORS["text_muted"])
            sub = f"Intereses vs ingresos fiscales"
            metrics.append(_compact_metric("INTERESES / INGRESOS EE.UU.", val_str, sub, color, badge=badge))
        else:
            metrics.append(_compact_metric("INTERESES / INGRESOS EE.UU.", "—", "Sin datos", COLORS["text_muted"]))
    except Exception:
        metrics.append(_compact_metric("INTERESES / INGRESOS EE.UU.", "—", "Sin datos", COLORS["text_muted"]))

    # 4. Deuda Japón % PIB
    try:
        df_jpn = get_series("wb_gov_debt_pct_jpn", days=365 * 5)
        if not df_jpn.empty:
            jpn_val = float(df_jpn.sort_values("timestamp").iloc[-1]["value"])
            val_str = f"{jpn_val:.1f}% PIB"
            metrics.append(_compact_metric("DEUDA JAPÓN % PIB", val_str, "Banco Mundial", COLORS["red"] if jpn_val > 200 else COLORS["orange"]))
        else:
            metrics.append(_compact_metric("DEUDA JAPÓN % PIB", "—", "Sin datos", COLORS["text_muted"]))
    except Exception:
        metrics.append(_compact_metric("DEUDA JAPÓN % PIB", "—", "Sin datos", COLORS["text_muted"]))

    # 5. Deuda Italia % PIB
    try:
        df_ita = get_series("wb_gov_debt_pct_ita", days=365 * 5)
        if not df_ita.empty:
            ita_val = float(df_ita.sort_values("timestamp").iloc[-1]["value"])
            val_str = f"{ita_val:.1f}% PIB"
            metrics.append(_compact_metric("DEUDA ITALIA % PIB", val_str, "Banco Mundial", COLORS["red"] if ita_val > 120 else COLORS["yellow"]))
        else:
            metrics.append(_compact_metric("DEUDA ITALIA % PIB", "—", "Sin datos", COLORS["text_muted"]))
    except Exception:
        metrics.append(_compact_metric("DEUDA ITALIA % PIB", "—", "Sin datos", COLORS["text_muted"]))

    # 6. Deuda Francia % PIB
    try:
        df_fra = get_series("wb_gov_debt_pct_fra", days=365 * 5)
        if not df_fra.empty:
            fra_val = float(df_fra.sort_values("timestamp").iloc[-1]["value"])
            val_str = f"{fra_val:.1f}% PIB"
            metrics.append(_compact_metric("DEUDA FRANCIA % PIB", val_str, "Banco Mundial", COLORS["yellow"] if fra_val > 100 else COLORS["text_muted"]))
        else:
            metrics.append(_compact_metric("DEUDA FRANCIA % PIB", "—", "Sin datos", COLORS["text_muted"]))
    except Exception:
        metrics.append(_compact_metric("DEUDA FRANCIA % PIB", "—", "Sin datos", COLORS["text_muted"]))

    ts = datetime.utcnow().strftime("%d/%m/%Y %H:%M UTC")
    return html.Div([
        html.Div(metrics, style={"display": "flex", "gap": "10px", "flexWrap": "wrap", "marginBottom": "6px"}),
        html.Div(f"Actualizado: {ts}", style={
            "fontSize": "0.62rem", "color": COLORS["text_label"],
            "textAlign": "right", "paddingRight": "4px",
        }),
    ])


# ══════════════════════════════════════════════════════════════════════════════
# LAYOUT PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

def render_module_8() -> html.Div:
    return html.Div([
        dcc.Interval(id="m8-interval", interval=300_000, n_intervals=0),

        # Título del módulo
        html.Div([
            html.H2("Deuda y Sostenibilidad Fiscal", style={
                "fontSize": "1.3rem", "fontWeight": "700",
                "color": COLORS["text"], "margin": "0 0 4px 0",
            }),
            html.Div(
                "Deuda pública global · servicio de la deuda · muro de vencimientos · "
                "análisis de sostenibilidad · represión financiera",
                style={"fontSize": "0.78rem", "color": COLORS["text_muted"]},
            ),
        ], style={"marginBottom": "12px"}),

        # Header métricas
        html.Div(id="m8-header-metrics"),

        # Tabs
        dcc.Tabs(
            id="m8-main-tabs",
            value="tab1",
            style=TABS_STYLE,
            children=[
                dcc.Tab(label="1 — Deuda Global",          value="tab1",
                        style=TAB_STYLE, selected_style=TAB_SELECTED_STYLE,
                        children=_build_tab1()),
                dcc.Tab(label="2 — EE.UU. en Detalle",     value="tab2",
                        style=TAB_STYLE, selected_style=TAB_SELECTED_STYLE,
                        children=_build_tab2()),
                dcc.Tab(label="3 — Europa en Detalle",     value="tab3",
                        style=TAB_STYLE, selected_style=TAB_SELECTED_STYLE,
                        children=_build_tab3()),
                dcc.Tab(label="4 — Sostenibilidad Fiscal", value="tab4",
                        style=TAB_STYLE, selected_style=TAB_SELECTED_STYLE,
                        children=_build_tab4()),
                dcc.Tab(label="5 — Represión Financiera",  value="tab5",
                        style=TAB_STYLE, selected_style=TAB_SELECTED_STYLE,
                        children=_build_tab5()),
            ],
        ),
    ], style={"padding": "12px 16px", "fontFamily": "'Inter','Segoe UI',system-ui,sans-serif"})


# ══════════════════════════════════════════════════════════════════════════════
# CALLBACKS
# ══════════════════════════════════════════════════════════════════════════════

def register_callbacks_module_8(app) -> None:  # noqa: C901

    # ── Header metrics ────────────────────────────────────────────────────────
    @app.callback(
        Output("m8-header-metrics", "children"),
        Input("m8-interval", "n_intervals"),
    )
    def update_m8_header(_):
        return _build_header_metrics()

    # ── Tab 1: World map ──────────────────────────────────────────────────────
    @app.callback(
        Output("m8-world-map", "figure"),
        Output("m8-top-bottom-panel", "children"),
        Input("m8-year-dropdown", "value"),
    )
    def update_m8_world_map(year):
        df = get_world_bank_indicator("gov_debt_pct", year=year)
        if df.empty:
            return _empty_fig("Sin datos de deuda para este año", height=420), html.Div()

        # Compute world avg
        world_avg = df["value"].mean()

        colorscale = [
            [0.0,  "#10b981"],   # <40% verde
            [0.2,  "#84cc16"],   # 40%
            [0.4,  "#f59e0b"],   # 80%
            [0.6,  "#f97316"],   # 120%
            [0.8,  "#ef4444"],   # 160%
            [1.0,  "#7f1d1d"],   # >200% rojo intenso
        ]

        fig = go.Figure(go.Choropleth(
            locations=df["country_iso3"],
            z=df["value"],
            zmin=0,
            zmax=220,
            colorscale=colorscale,
            colorbar=dict(
                title=dict(text="% PIB", font=dict(color="#9ca3af", size=11)),
                tickfont=dict(color="#9ca3af", size=10),
                bgcolor="#111827",
                bordercolor="#1f2937",
                len=0.7,
            ),
            hovertemplate=(
                "<b>%{location}</b><br>"
                "Deuda: %{z:.1f}% PIB<br>"
                "<extra></extra>"
            ),
            marker_line_color="#1f2937",
            marker_line_width=0.5,
        ))
        fig.update_geos(
            showframe=False,
            showcoastlines=True,
            coastlinecolor="#1f2937",
            showland=True,
            landcolor="#1f2937",
            showocean=True,
            oceancolor="#0a0e1a",
            showlakes=False,
            projection_type="natural earth",
        )
        base = _layout(height=420)
        base.pop("margin", None)
        fig.update_layout(
            **base,
            geo=dict(bgcolor="#0a0e1a"),
            margin=dict(l=0, r=0, t=30, b=0),
            title=dict(text=f"Deuda Pública como % del PIB — {year} | Media mundial: {world_avg:.1f}%",
                       font=dict(color="#e5e7eb", size=12), x=0),
        )

        # Top / bottom 10
        df_sorted = df.sort_values("value", ascending=False).reset_index(drop=True)
        top10 = df_sorted.head(10)
        bot10 = df_sorted.tail(10).sort_values("value")

        def _mini_table(rows, title, color):
            return html.Div([
                html.Div(title, style={"fontWeight": "700", "fontSize": "0.78rem",
                                       "color": color, "marginBottom": "6px"}),
                html.Table([
                    html.Tbody([
                        html.Tr([
                            html.Td(r["country_iso3"], style={"fontSize": "0.72rem",
                                                               "color": COLORS["text_muted"], "paddingRight": "10px"}),
                            html.Td(f"{r['value']:.1f}%", style={"fontSize": "0.78rem",
                                                                   "fontWeight": "600", "color": color}),
                        ]) for _, r in rows.iterrows()
                    ])
                ])
            ])

        panel = dbc.Row([
            dbc.Col(_mini_table(top10, "🔴 Mayor Deuda", COLORS["red"]), width=6),
            dbc.Col(_mini_table(bot10, "🟢 Menor Deuda", COLORS["green"]), width=6),
        ])
        return fig, panel

    # ── Tab 1: Debt evolution ─────────────────────────────────────────────────
    @app.callback(
        Output("m8-debt-evolution-chart", "figure"),
        Input("m8-interval", "n_intervals"),
    )
    def update_m8_evolution(_):
        days = 365 * 27  # desde 1998

        countries = [
            ("USA", "EE.UU.", _CC["USA"]),
            ("JPN", "Japón",  _CC["JPN"]),
            ("DEU", "Alemania", _CC["DEU"]),
            ("FRA", "Francia", _CC["FRA"]),
            ("ESP", "España",  _CC["ESP"]),
            ("ITA", "Italia",  _CC["ITA"]),
            ("GBR", "UK",      _CC["GBR"]),
            ("CHN", "China",   _CC["CHN"]),
        ]

        fig = go.Figure()

        for iso3, name, color in countries:
            df = get_series(f"wb_gov_debt_pct_{iso3.lower()}", days=days)
            # Also try US FRED quarterly as supplement
            if iso3 == "USA":
                df_fred = get_series(ID_DEBT_GDP_US, days=days)
                if not df_fred.empty and not df.empty:
                    df = pd.concat([df, df_fred]).sort_values("timestamp").drop_duplicates("timestamp")
                elif not df_fred.empty:
                    df = df_fred
            if df.empty:
                continue
            df = df.sort_values("timestamp")
            fig.add_trace(go.Scatter(
                x=df["timestamp"], y=df["value"],
                name=name, line=dict(color=color, width=2),
                mode="lines",
                hovertemplate=f"<b>{name}</b><br>%{{x|%Y}}: %{{y:.1f}}%<extra></extra>",
            ))

        # Reference lines
        for ref_y, label, color in [(60, "60% — Límite Maastricht", "#10b981"),
                                     (90, "90% — Umbral Reinhart-Rogoff", "#f59e0b"),
                                     (120, "120% — Zona de alerta", "#ef4444")]:
            fig.add_hline(y=ref_y, line_dash="dot", line_color=color, opacity=0.5,
                          annotation_text=label,
                          annotation_position="right",
                          annotation_font=dict(color=color, size=10))

        # Crisis annotations
        for x_ann, text_ann in [("2008-09-15", "Crisis 2008"), ("2020-03-15", "COVID-19")]:
            fig.add_vline(x=x_ann, line_dash="dash", line_color="#374151", opacity=0.6)
            fig.add_annotation(x=x_ann, y=180, text=text_ann, showarrow=False,
                               font=dict(color="#6b7280", size=10),
                               xshift=5, yshift=0, textangle=-90)

        fig.update_layout(**_layout(height=420))
        fig.update_yaxes(title_text="% del PIB", range=[0, 270])
        fig.update_xaxes(title_text="")
        fig.update_layout(legend=dict(orientation="h", y=-0.15), hovermode="x unified")
        return fig

    # ── Tab 1: Comparison table ───────────────────────────────────────────────
    @app.callback(
        Output("m8-debt-comparison-table", "children"),
        Input("m8-interval", "n_intervals"),
    )
    def update_m8_comparison_table(_):
        ratings_data = _load_json("credit_ratings.json").get("ratings", {})

        rows_data = [
            ("USA", "🇺🇸 EE.UU."),
            ("JPN", "🇯🇵 Japón"),
            ("CHN", "🇨🇳 China"),
            ("GBR", "🇬🇧 UK"),
            ("FRA", "🇫🇷 Francia"),
            ("DEU", "🇩🇪 Alemania"),
            ("ITA", "🇮🇹 Italia"),
            ("ESP", "🇪🇸 España"),
            ("BRA", "🇧🇷 Brasil"),
            ("GRC", "🇬🇷 Grecia"),
            ("PRT", "🇵🇹 Portugal"),
            ("IND", "🇮🇳 India"),
        ]

        header_style = {"fontSize": "0.70rem", "color": COLORS["text_label"],
                        "fontWeight": "700", "padding": "6px 10px",
                        "borderBottom": f"1px solid {COLORS['border']}",
                        "textAlign": "right", "whiteSpace": "nowrap"}
        header_style_l = {**header_style, "textAlign": "left"}
        cell_style = {"fontSize": "0.78rem", "color": COLORS["text"],
                      "padding": "5px 10px", "textAlign": "right",
                      "borderBottom": f"1px solid {COLORS['border']}20"}
        cell_style_l = {**cell_style, "textAlign": "left"}

        rows = [
            html.Tr([
                html.Th("País", style=header_style_l),
                html.Th("Deuda % PIB", style=header_style),
                html.Th("Déficit % PIB", style=header_style),
                html.Th("Hace 5 años", style=header_style),
                html.Th("Variación (pp)", style=header_style),
                html.Th("Moody's", style=header_style),
                html.Th("S&P", style=header_style),
                html.Th("Tendencia", style=header_style),
            ])
        ]

        for iso3, name in rows_data:
            iso3_l = iso3.lower()
            df_now = get_series(f"wb_gov_debt_pct_{iso3_l}", days=365 * 3)
            df_5y  = get_series(f"wb_gov_debt_pct_{iso3_l}", days=365 * 8)
            df_def = get_series(f"wb_fiscal_balance_{iso3_l}", days=365 * 3)

            debt_now = float(df_now.sort_values("timestamp").iloc[-1]["value"]) if not df_now.empty else None
            deficit   = float(df_def.sort_values("timestamp").iloc[-1]["value"]) if not df_def.empty else None

            # 5 years ago (approx 5th year back)
            debt_5y = None
            if not df_5y.empty:
                df_5y_sorted = df_5y.sort_values("timestamp")
                if len(df_5y_sorted) >= 5:
                    debt_5y = float(df_5y_sorted.iloc[-5]["value"])

            chg_5y = round(debt_now - debt_5y, 1) if debt_now is not None and debt_5y is not None else None
            trend = ("↑" if chg_5y and chg_5y > 0.5 else ("↓" if chg_5y and chg_5y < -0.5 else "→")) if chg_5y is not None else "—"
            trend_color = COLORS["red"] if trend == "↑" else (COLORS["green"] if trend == "↓" else COLORS["text_muted"])

            rat = ratings_data.get(iso3, {})
            moodys = rat.get("moodys", "—")
            sp_r   = rat.get("sp", "—")

            rows.append(html.Tr([
                html.Td(name, style=cell_style_l),
                html.Td(_safe(debt_now, ".1f", "%"), style={**cell_style,
                        "color": COLORS["red"] if debt_now and debt_now > 100 else
                                 (COLORS["yellow"] if debt_now and debt_now > 60 else COLORS["green"])}),
                html.Td(_safe(deficit, ".1f", "%"), style={**cell_style,
                        "color": COLORS["red"] if deficit and deficit < -5 else
                                 (COLORS["yellow"] if deficit and deficit < -3 else COLORS["text_muted"])}),
                html.Td(_safe(debt_5y, ".1f", "%"), style=cell_style),
                html.Td(_safe(chg_5y, "+.1f", "pp") if chg_5y is not None else "—",
                        style={**cell_style, "color": COLORS["red"] if chg_5y and chg_5y > 0 else COLORS["green"]}),
                html.Td(moodys, style={**cell_style, "color": _rating_color(moodys), "fontWeight": "600"}),
                html.Td(sp_r,   style={**cell_style, "color": _rating_color(sp_r),   "fontWeight": "600"}),
                html.Td(trend, style={**cell_style, "color": trend_color, "fontWeight": "700"}),
            ]))

        return html.Table(rows, style={"width": "100%", "borderCollapse": "collapse"})

    # ── Tab 2: US debt counter ────────────────────────────────────────────────
    @app.callback(
        Output("m8-us-counter-panel", "children"),
        Input("m8-interval", "n_intervals"),
    )
    def update_m8_us_counter(_):
        df = get_series(ID_FEDERAL_DEBT_US, days=365 * 2)
        total_bn = None
        if not df.empty:
            # GFDEBTN is in USD millions
            total_mn = float(df.sort_values("timestamp").iloc[-1]["value"])
            total_bn = total_mn / 1_000  # billions

        # Also try from JSON static
        mat_data = _load_json("us_debt_maturities.json")
        if total_bn is None and mat_data:
            total_bn = mat_data.get("total_debt_trillion", 36.8) * 1_000  # billions

        total_usd = total_bn * 1e9 if total_bn else None
        total_trillion = total_bn / 1_000 if total_bn else None

        # Per capita (335M US pop) and per taxpayer (160M)
        pop = 335e6
        taxpayers = 160e6
        per_capita  = int(total_usd / pop)       if total_usd else None
        per_taxpayer = int(total_usd / taxpayers) if total_usd else None

        # Annual interest from FRED
        int_val, _ = get_latest_value(ID_INTEREST_PAY_US)
        interest_weekly_bn = (int_val / 52) if int_val else None

        # Deficit-based growth rate
        df_def = get_series(ID_DEFICIT_GDP_US, days=365 * 2)
        def_pct = None
        if not df_def.empty:
            def_pct = float(df_def.sort_values("timestamp").iloc[-1]["value"])

        # Estimate GDP ~27 trillion USD for calculation
        gdp_est_trillion = 27.0
        if def_pct and gdp_est_trillion:
            deficit_annual_bn = abs(def_pct) / 100 * gdp_est_trillion * 1_000
            per_second = deficit_annual_bn * 1e9 / (365.25 * 24 * 3600)
        else:
            per_second = None

        big_num = f"${total_trillion:,.3f} billones" if total_trillion else "—"

        return html.Div([
            # Big number
            html.Div([
                html.Div("DEUDA FEDERAL TOTAL DE EE.UU.", style={
                    "fontSize": "0.70rem", "color": COLORS["text_label"],
                    "fontWeight": "700", "letterSpacing": "0.1em", "marginBottom": "8px",
                }),
                html.Div(big_num, style={
                    "fontSize": "2.8rem", "fontWeight": "900",
                    "color": COLORS["red"], "lineHeight": "1",
                    "marginBottom": "16px", "fontFamily": "monospace",
                }),
            ], style={"textAlign": "center", "padding": "20px 0"}),

            # Sub-metrics
            dbc.Row([
                dbc.Col(_compact_metric(
                    "DEUDA PER CÁPITA",
                    f"~${per_capita:,}" if per_capita else "—",
                    "Por ciudadano americano",
                    COLORS["text_muted"],
                ), width=12, md=3),
                dbc.Col(_compact_metric(
                    "DEUDA POR CONTRIBUYENTE",
                    f"~${per_taxpayer:,}" if per_taxpayer else "—",
                    "Por trabajador activo (~160M)",
                    COLORS["text_muted"],
                ), width=12, md=3),
                dbc.Col(_compact_metric(
                    "CRECIMIENTO POR SEGUNDO",
                    f"~${per_second:,.0f}" if per_second else "—",
                    "USD por segundo (basado en déficit anual)",
                    COLORS["yellow"],
                ), width=12, md=3),
                dbc.Col(_compact_metric(
                    "INTERESES SEMANALES",
                    f"${interest_weekly_bn:,.1f}bn" if interest_weekly_bn else "—",
                    "USD pagados en intereses cada semana",
                    COLORS["red"],
                ), width=12, md=3),
            ], className="g-2"),
        ])

    # ── Tab 2: US historical + CBO ────────────────────────────────────────────
    @app.callback(
        Output("m8-us-historical-chart", "figure"),
        Input("m8-interval", "n_intervals"),
    )
    def update_m8_us_historical(_):
        # Historical data
        df = get_series(ID_DEBT_GDP_US, days=365 * 30)
        # WB supplement
        df_wb = get_series("wb_gov_debt_pct_usa", days=365 * 90)

        fig = go.Figure()

        if not df_wb.empty:
            df_wb = df_wb.sort_values("timestamp")
            fig.add_trace(go.Scatter(
                x=df_wb["timestamp"], y=df_wb["value"],
                name="EE.UU. (Banco Mundial)",
                line=dict(color=_CC["USA"], width=2),
                fill="tozeroy", fillcolor=_rgba(_CC["USA"], 0.1),
                mode="lines",
            ))
        if not df.empty:
            df = df.sort_values("timestamp")
            fig.add_trace(go.Scatter(
                x=df["timestamp"], y=df["value"],
                name="EE.UU. (FRED Trimestral)",
                line=dict(color=_CC["USA"], width=2.5),
                mode="lines",
            ))

        # CBO projections
        cbo = _load_json("cbo_projections.json")
        if cbo and "projections" in cbo:
            proj = cbo["projections"]
            years = sorted(proj.keys(), key=lambda x: int(x))
            x_proj = [f"{y}-01-01" for y in years]
            y_proj = [proj[y] for y in years]
            fig.add_trace(go.Scatter(
                x=x_proj, y=y_proj,
                name="Proyección CBO (base)",
                line=dict(color="#60a5fa", width=2, dash="dot"),
                mode="lines+markers",
                marker=dict(size=5),
            ))

        # Reference line at 100%
        fig.add_hline(y=100, line_dash="dash", line_color="#ef4444", opacity=0.6,
                      annotation_text="100% del PIB", annotation_position="right",
                      annotation_font=dict(color="#ef4444", size=10))

        # Annotations
        for x_ann, y_ann, text_ann in [
            ("1945-01-01", 115, "Pico WWII ~119%"),
            ("2008-09-15", 70,  "Crisis 2008"),
            ("2020-03-15", 100, "COVID-19"),
        ]:
            fig.add_annotation(x=x_ann, y=y_ann, text=text_ann,
                               showarrow=True, arrowhead=2,
                               font=dict(color="#9ca3af", size=10),
                               arrowcolor="#374151", ax=30, ay=-20)

        fig.update_layout(**_layout(height=420))
        fig.update_yaxes(title_text="% del PIB")
        fig.update_xaxes(title_text="", rangeselector=get_time_range_buttons(),
                         rangeslider=dict(visible=False))
        fig.update_layout(legend=dict(orientation="h", y=-0.15))
        return fig

    # ── Tab 2: Maturity wall ──────────────────────────────────────────────────
    @app.callback(
        Output("m8-maturity-wall-chart", "figure"),
        Output("m8-maturity-note", "children"),
        Input("m8-interval", "n_intervals"),
    )
    def update_m8_maturity_wall(_):
        data = _load_json("us_debt_maturities.json")
        if not data or "maturities_by_year" not in data:
            return _empty_fig("Sin datos de vencimientos"), html.Div()

        mat = data["maturities_by_year"]
        avg_coupon = data.get("average_coupon_pct", 2.7)
        mkt_rate   = data.get("current_market_rate_10y", 4.3)
        rate_diff  = mkt_rate - avg_coupon

        years = list(mat.keys())
        amounts = [mat[y] for y in years]
        extra_cost = [round(mat[y] * rate_diff / 100, 2) for y in years]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=years, y=amounts,
            name="Deuda que vence (billones USD)",
            marker_color=[_CC["USA"] if y != "2026" else COLORS["red"] for y in years],
            text=[f"${a:.1f}T" for a in amounts],
            textposition="outside",
            textfont=dict(size=11, color=COLORS["text"]),
            hovertemplate="<b>%{x}</b><br>Vence: $%{y:.1f}T<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=years, y=extra_cost,
            name=f"Coste adicional vs cupón {avg_coupon}% (bn/año)",
            mode="lines+markers",
            line=dict(color=COLORS["yellow"], width=2, dash="dot"),
            yaxis="y2",
            hovertemplate="<b>%{x}</b><br>Coste extra: $%{y:.1f}bn/año<extra></extra>",
        ))

        fig.update_layout(**_layout(height=380))
        fig.update_yaxes(title_text="Billones USD (T)")
        fig.update_layout(
            yaxis2=dict(title="Coste adicional (bn USD/año)", overlaying="y", side="right",
                        gridcolor="rgba(0,0,0,0)", tickfont=dict(color="#f59e0b", size=10),
                        titlefont=dict(color="#f59e0b", size=10)),
            legend=dict(orientation="h", y=-0.15),
            barmode="group",
        )

        extra_2026_bn = round(mat.get("2026", 9.2) * rate_diff / 100, 1)
        note = html.Div([
            html.Div(
                f"Refinanciar la deuda que vence en 2026 (${mat.get('2026', 9.2):.1f}T) al tipo de mercado "
                f"actual ({mkt_rate}%) supone un coste adicional de ~${extra_2026_bn}bn de dólares anuales "
                f"respecto al cupón promedio ({avg_coupon}%). Un tercio de toda la deuda federal americana "
                f"vence en 2026, forzando al Tesoro a refinanciarla a tipos significativamente más altos.",
                style=_NOTE,
            ),
        ])
        return fig, note

    # ── Tab 2: Debt service chart ─────────────────────────────────────────────
    @app.callback(
        Output("m8-debt-service-chart", "figure"),
        Output("m8-budget-panel", "children"),
        Input("m8-interval", "n_intervals"),
    )
    def update_m8_debt_service(_):
        days = 365 * 35
        df_int = get_series(ID_INTEREST_PAY_US, days=days)
        df_tax = get_series(ID_TAX_REV_US,      days=days)

        fig = go.Figure()

        if not df_int.empty and not df_tax.empty:
            df_int = df_int.sort_values("timestamp").set_index("timestamp")
            df_tax = df_tax.sort_values("timestamp").set_index("timestamp")
            merged = pd.concat([df_int["value"].rename("interest"),
                                df_tax["value"].rename("tax")], axis=1).dropna()
            merged["ratio"] = merged["interest"] / merged["tax"] * 100

            fig.add_trace(go.Scatter(
                x=merged.index, y=merged["ratio"],
                name="Intereses / Ingresos fiscales (%)",
                line=dict(color=COLORS["red"], width=2.5),
                fill="tozeroy", fillcolor=_rgba(COLORS["red"], 0.15),
                mode="lines",
            ))

            cur_ratio = float(merged["ratio"].iloc[-1]) if len(merged) > 0 else None
            if cur_ratio:
                fig.add_annotation(
                    x=merged.index[-1], y=cur_ratio,
                    text=f"Actual: {cur_ratio:.1f}%",
                    showarrow=True, arrowhead=2,
                    font=dict(color=COLORS["red"], size=11, weight=700),
                    arrowcolor=COLORS["red"], ax=-50, ay=-20,
                )
        else:
            fig.add_annotation(text="Sin datos de intereses/ingresos", xref="paper", yref="paper",
                               x=0.5, y=0.5, showarrow=False,
                               font=dict(color=COLORS["text_muted"], size=13))

        for ref_y, label, color in [
            (10, "10% — Nivel histórico normal", "#10b981"),
            (15, "15% — Zona de atención",       "#f59e0b"),
            (20, "20% — Zona de alerta",          "#f97316"),
            (30, "30% — Zona de crisis",          "#ef4444"),
        ]:
            fig.add_hline(y=ref_y, line_dash="dot", line_color=color, opacity=0.5,
                          annotation_text=label, annotation_position="right",
                          annotation_font=dict(color=color, size=9))

        fig.update_layout(**_layout(height=380))
        fig.update_yaxes(title_text="% de ingresos fiscales")
        fig.update_xaxes(title_text="")

        # Budget pie
        budget = _load_json("us_budget.json")
        if budget and "categories" in budget:
            cats = budget["categories"]
            labels = list(cats.keys())
            values = list(cats.values())
            colors_pie = [
                COLORS["red"] if l == "Interest on Debt" else
                _CC["USA"] if l == "Defense" else
                "#10b981" if l == "Social Security" else
                "#8b5cf6" if l == "Medicare/Medicaid" else
                "#9ca3af" for l in labels
            ]
            pie_fig = go.Figure(go.Pie(
                labels=labels, values=values,
                textinfo="label+percent",
                textfont=dict(size=10, color="#e5e7eb"),
                marker=dict(colors=colors_pie, line=dict(color="#0a0e1a", width=1.5)),
                hole=0.35,
                hovertemplate="<b>%{label}</b><br>$%{value}bn<br>%{percent}<extra></extra>",
            ))
            _pie_base = _layout(height=280)
            _pie_base.pop("margin", None)
            pie_fig.update_layout(
                **_pie_base,
                showlegend=False,
                margin=dict(l=0, r=0, t=30, b=0),
                title=dict(text=f"Presupuesto Federal FY{budget.get('fiscal_year', 2025)}",
                           font=dict(color="#e5e7eb", size=11), x=0),
            )
            total_rev = budget.get("total_revenue_bn", 4920)
            deficit   = budget.get("deficit_bn", 1830)
            int_amt   = cats.get("Interest on Debt", 1160)
            def_amt   = cats.get("Defense", 895)
            panel = html.Div([
                dcc.Graph(figure=pie_fig, config={"displayModeBar": False}),
                html.Div([
                    html.Div(f"💰 Ingresos: ${total_rev:,}bn",
                             style={"fontSize": "0.75rem", "color": COLORS["green"], "marginBottom": "3px"}),
                    html.Div(f"📉 Déficit: ${deficit:,}bn",
                             style={"fontSize": "0.75rem", "color": COLORS["red"], "marginBottom": "3px"}),
                    html.Div(f"🏦 Intereses: ${int_amt:,}bn > Defensa: ${def_amt:,}bn",
                             style={"fontSize": "0.72rem", "color": COLORS["yellow"]}),
                ], style={"padding": "4px 8px"}),
            ])
        else:
            panel = html.Div("Sin datos de presupuesto", style={"color": COLORS["text_muted"], "fontSize": "0.78rem"})

        return fig, panel

    # ── Tab 2: Debt holders ───────────────────────────────────────────────────
    @app.callback(
        Output("m8-holders-chart", "figure"),
        Input("m8-interval", "n_intervals"),
    )
    def update_m8_holders(_):
        data = _load_json("us_debt_holders.json")
        if not data or "holders" not in data:
            return _empty_fig("Sin datos de tenedores")

        holders = data["holders"]
        # Sort by value descending
        items = sorted(holders.items(), key=lambda x: x[1], reverse=True)
        labels = [x[0] for x in items]
        values = [x[1] for x in items]

        domestic = {"Federal Reserve", "Social Security Trust Fund", "Other US Government", "US Public (otros)"}
        colors_bar = [
            _CC["USA"] if l in domestic else
            ("#ec4899" if l == "Japan" else
             "#f97316" if l == "China" else
             "#06b6d4" if l == "UK" else
             "#9ca3af")
            for l in labels
        ]

        fig = go.Figure(go.Bar(
            y=labels, x=values,
            orientation="h",
            marker_color=colors_bar,
            text=[f"${v:.2f}T" for v in values],
            textposition="outside",
            textfont=dict(size=10, color=COLORS["text"]),
            hovertemplate="<b>%{y}</b><br>$%{x:.2f}T<extra></extra>",
        ))

        # China annotation
        china_2013 = data.get("china_2013_trillion", 1.3)
        china_now  = holders.get("China", 0.76)
        fig.add_annotation(
            x=china_now + 0.05, y="China",
            text=f"↓ desde ${china_2013}T en 2013",
            showarrow=False,
            font=dict(color="#f97316", size=10),
            xanchor="left",
        )

        fig.update_layout(**_layout(height=480))
        fig.update_xaxes(title_text="Billones USD (T)")
        fig.update_yaxes(autorange="reversed")
        fig.update_layout(margin=dict(l=170, r=120, t=30, b=40))
        return fig

    # ── Tab 3: EU Stability Pact ──────────────────────────────────────────────
    @app.callback(
        Output("m8-stability-table", "children"),
        Output("m8-stability-summary", "children"),
        Input("m8-interval", "n_intervals"),
    )
    def update_m8_stability(_):
        cell_s  = {"fontSize": "0.75rem", "padding": "5px 8px",
                   "borderBottom": f"1px solid {COLORS['border']}20",
                   "color": COLORS["text"]}
        head_s  = {"fontSize": "0.68rem", "padding": "6px 8px", "fontWeight": "700",
                   "color": COLORS["text_label"],
                   "borderBottom": f"1px solid {COLORS['border']}",
                   "whiteSpace": "nowrap"}

        rows = [html.Tr([
            html.Th("País", style=head_s),
            html.Th("Deuda % PIB", style={**head_s, "textAlign": "right"}),
            html.Th("Límite (60%)", style={**head_s, "textAlign": "center"}),
            html.Th("Déficit % PIB", style={**head_s, "textAlign": "right"}),
            html.Th("Límite (3%)", style={**head_s, "textAlign": "center"}),
            html.Th("En PDE", style={**head_s, "textAlign": "center"}),
        ])]

        comply_debt_count = 0
        comply_def_count  = 0
        comply_both_count = 0
        total = len(_EU_COUNTRIES)

        for eu2, iso3, name in _EU_COUNTRIES:
            iso3_l = iso3.lower()
            df_d = get_series(f"wb_gov_debt_pct_{iso3_l}", days=365 * 3)
            df_f = get_series(f"wb_fiscal_balance_{iso3_l}", days=365 * 3)

            # Fallback: Eurostat EDP
            if df_d.empty:
                df_d = get_series(f"estat_edp_gd_{eu2.lower()}", days=365 * 3)
            if df_f.empty:
                df_f = get_series(f"estat_edp_b9_{eu2.lower()}", days=365 * 3)

            debt  = float(df_d.sort_values("timestamp").iloc[-1]["value"]) if not df_d.empty else None
            deficit = float(df_f.sort_values("timestamp").iloc[-1]["value"]) if not df_f.empty else None

            ok_debt  = debt is not None and debt < 60
            ok_def   = deficit is not None and deficit > -3  # surplus or small deficit
            in_edp   = iso3 in _IN_EDP

            if ok_debt:
                comply_debt_count += 1
            if ok_def:
                comply_def_count += 1
            if ok_debt and ok_def:
                comply_both_count += 1

            # Row color
            if not ok_debt and not ok_def and debt is not None and deficit is not None:
                row_bg = f"{COLORS['red']}10"
            elif (not ok_debt or not ok_def) and (debt is not None or deficit is not None):
                row_bg = f"{COLORS['warning']}08"
            else:
                row_bg = "transparent"

            rows.append(html.Tr([
                html.Td(name, style={**cell_s, "fontWeight": "500"}),
                html.Td(_safe(debt, ".1f", "%"), style={**cell_s, "textAlign": "right",
                        "color": COLORS["red"] if not ok_debt and debt else
                                 (COLORS["green"] if ok_debt else COLORS["text_muted"])}),
                html.Td("✅" if ok_debt else ("❌" if debt is not None else "—"),
                        style={**cell_s, "textAlign": "center"}),
                html.Td(_safe(deficit, ".1f", "%"), style={**cell_s, "textAlign": "right",
                        "color": COLORS["red"] if not ok_def and deficit else
                                 (COLORS["green"] if ok_def else COLORS["text_muted"])}),
                html.Td("✅" if ok_def else ("❌" if deficit is not None else "—"),
                        style={**cell_s, "textAlign": "center"}),
                html.Td("⚠️ Sí" if in_edp else "No",
                        style={**cell_s, "textAlign": "center",
                               "color": COLORS["yellow"] if in_edp else COLORS["text_muted"]}),
            ], style={"backgroundColor": row_bg}))

        table = html.Table(rows, style={"width": "100%", "borderCollapse": "collapse"})
        summary = html.Div(
            f"{comply_debt_count} de {total} países de la UE cumplen el criterio de deuda (<60%). "
            f"{comply_def_count} de {total} cumplen el criterio de déficit (<3%). "
            f"Solo {comply_both_count} países cumplen ambos criterios.",
            style={"fontSize": "0.80rem", "color": COLORS["text"], "marginTop": "10px",
                   "padding": "8px 12px", "background": "#0d1320", "borderRadius": "4px"},
        )
        return table, summary

    # ── Tab 3: Italy spread ───────────────────────────────────────────────────
    @app.callback(
        Output("m8-italy-spread-chart", "figure"),
        Output("m8-italy-panel", "children"),
        Input("m8-interval", "n_intervals"),
    )
    def update_m8_italy(_):
        df_spread = get_series(ID_SPREAD_IT, days=365 * 15)
        fig = go.Figure()
        cur_spread = None

        if not df_spread.empty:
            df_spread = df_spread.sort_values("timestamp")
            cur_spread = float(df_spread.iloc[-1]["value"])
            fig.add_trace(go.Scatter(
                x=df_spread["timestamp"], y=df_spread["value"],
                name="Prima riesgo Italia (pb)",
                line=dict(color=_CC["ITA"], width=2.5),
                fill="tozeroy", fillcolor=_rgba(_CC["ITA"], 0.15),
                mode="lines",
            ))

            # Key crisis annotations
            for x_ann, y_ann, text_ann in [
                ("2011-11-01", 520, "Crisis soberana 2011 ~550pb"),
                ("2018-05-15", 320, "Gobierno populista 2018 ~350pb"),
                ("2020-03-15", 230, "COVID-19 ~250pb"),
            ]:
                fig.add_annotation(x=x_ann, y=y_ann, text=text_ann,
                                   showarrow=True, arrowhead=2, ax=40, ay=-25,
                                   font=dict(color="#9ca3af", size=9), arrowcolor="#374151")
        else:
            fig.add_annotation(text="Sin datos de spread Italia-Alemania",
                               xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False,
                               font=dict(color=COLORS["text_muted"], size=13))

        fig.add_hline(y=200, line_dash="dot", line_color=COLORS["yellow"], opacity=0.5,
                      annotation_text="200pb — zona de vigilancia",
                      annotation_font=dict(color=COLORS["yellow"], size=9))
        fig.add_hline(y=350, line_dash="dot", line_color=COLORS["red"], opacity=0.5,
                      annotation_text="350pb — zona de estrés",
                      annotation_font=dict(color=COLORS["red"], size=9))

        fig.update_layout(**_layout(height=350))
        fig.update_yaxes(title_text="Puntos básicos (pb)")
        fig.update_xaxes(title_text="")

        # Side panel
        df_debt_it = get_series("wb_gov_debt_pct_ita", days=365 * 3)
        debt_it = float(df_debt_it.sort_values("timestamp").iloc[-1]["value"]) if not df_debt_it.empty else None

        panel = html.Div([
            _compact_metric("SPREAD ACTUAL", f"{cur_spread:.0f}pb" if cur_spread else "—",
                            "vs Bund alemán 10Y", _chg_color(cur_spread - 150 if cur_spread else None)),
            html.Div(style={"height": "10px"}),
            _compact_metric("DEUDA ITALIA", f"{debt_it:.1f}% PIB" if debt_it else "~140%",
                            "~2.8 billones EUR", COLORS["red"]),
            html.Div(style={"height": "10px"}),
            html.Div(
                "+100pb en tipos → ~28.000M€ más en intereses anuales al refinanciar",
                style={"fontSize": "0.72rem", "color": COLORS["yellow"], "lineHeight": "1.4",
                       "padding": "8px", "background": "#0d1320", "borderRadius": "4px"},
            ),
        ])
        return fig, panel

    # ── Tab 3: France spread ──────────────────────────────────────────────────
    @app.callback(
        Output("m8-france-spread-chart", "figure"),
        Input("m8-interval", "n_intervals"),
    )
    def update_m8_france(_):
        df_fr = get_series(ID_SPREAD_FR, days=365 * 15)
        df_es = get_series(ID_SPREAD_ES, days=365 * 15)
        fig = go.Figure()

        if not df_fr.empty:
            df_fr = df_fr.sort_values("timestamp")
            fig.add_trace(go.Scatter(
                x=df_fr["timestamp"], y=df_fr["value"],
                name="Francia–Alemania",
                line=dict(color=_CC["FRA"], width=2.5),
                mode="lines",
            ))
        if not df_es.empty:
            df_es = df_es.sort_values("timestamp")
            fig.add_trace(go.Scatter(
                x=df_es["timestamp"], y=df_es["value"],
                name="España–Alemania",
                line=dict(color=_CC["ESP"], width=2),
                mode="lines", line_dash="dot",
            ))

        if df_fr.empty and df_es.empty:
            fig.add_annotation(text="Sin datos de spreads europeos",
                               xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False,
                               font=dict(color=COLORS["text_muted"], size=13))

        fig.update_layout(**_layout(height=350))
        fig.update_yaxes(title_text="Puntos básicos (pb)")
        fig.update_xaxes(title_text="")
        fig.update_layout(legend=dict(orientation="h", y=-0.2))
        return fig

    # ── Tab 3: Spain analysis ─────────────────────────────────────────────────
    @app.callback(
        Output("m8-spain-metrics", "children"),
        Output("m8-spain-debt-chart", "figure"),
        Output("m8-spain-context", "children"),
        Input("m8-interval", "n_intervals"),
    )
    def update_m8_spain(_):
        ratings = _load_json("credit_ratings.json").get("ratings", {}).get("ESP", {})

        df_debt = get_series("wb_gov_debt_pct_esp", days=365 * 30)
        df_def  = get_series("wb_fiscal_balance_esp", days=365 * 3)
        df_spr  = get_series(ID_SPREAD_ES, days=365)

        debt_now = float(df_debt.sort_values("timestamp").iloc[-1]["value"]) if not df_debt.empty else None
        deficit  = float(df_def.sort_values("timestamp").iloc[-1]["value"])  if not df_def.empty else None
        spread   = float(df_spr.sort_values("timestamp").iloc[-1]["value"])  if not df_spr.empty else None

        metrics_row = dbc.Row([
            dbc.Col(_compact_metric("DEUDA % PIB", f"{debt_now:.1f}%" if debt_now else "—",
                                    "Eurostat/Banco Mundial", COLORS["yellow"] if debt_now and debt_now > 100 else COLORS["text_muted"]), width=6, md=3),
            dbc.Col(_compact_metric("DÉFICIT % PIB", f"{deficit:.1f}%" if deficit else "—",
                                    "Banco Mundial", COLORS["red"] if deficit and deficit < -3 else COLORS["text_muted"]), width=6, md=3),
            dbc.Col(_compact_metric("PRIMA RIESGO", f"{spread:.0f}pb" if spread else "—",
                                    "vs Bund alemán", COLORS["yellow"] if spread and spread > 150 else COLORS["green"]), width=6, md=3),
            dbc.Col(_compact_metric("RATING MOODY'S", ratings.get("moodys", "—"),
                                    f"S&P: {ratings.get('sp','—')} · Fitch: {ratings.get('fitch','—')}",
                                    _rating_color(ratings.get("moodys", "—"))), width=6, md=3),
        ], className="g-2", style={"marginBottom": "12px"})

        # Debt chart
        fig = go.Figure()
        if not df_debt.empty:
            df_debt = df_debt.sort_values("timestamp")
            fig.add_trace(go.Scatter(
                x=df_debt["timestamp"], y=df_debt["value"],
                name="España", line=dict(color=_CC["ESP"], width=2.5),
                fill="tozeroy", fillcolor=_rgba(_CC["ESP"], 0.15), mode="lines",
            ))
            for x_ann, y_ann, text_ann in [
                ("2007-01-01", 36,  "2007: 36% PIB"),
                ("2013-01-01", 100, "2013: ~100%"),
                ("2020-06-01", 115, "COVID 2020"),
            ]:
                fig.add_annotation(x=x_ann, y=y_ann, text=text_ann,
                                   showarrow=True, arrowhead=2, ax=30, ay=-20,
                                   font=dict(color="#9ca3af", size=9), arrowcolor="#374151")
        else:
            fig.add_annotation(text="Sin datos de deuda España",
                               xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False,
                               font=dict(color=COLORS["text_muted"], size=13))

        fig.add_hline(y=60, line_dash="dot", line_color=COLORS["green"], opacity=0.5,
                      annotation_text="60% Maastricht",
                      annotation_font=dict(color=COLORS["green"], size=9))
        fig.add_hline(y=100, line_dash="dot", line_color=COLORS["red"], opacity=0.5,
                      annotation_text="100% umbral",
                      annotation_font=dict(color=COLORS["red"], size=9))

        fig.update_layout(**_layout(height=340))
        fig.update_yaxes(title_text="% del PIB")
        fig.update_xaxes(title_text="")

        # Context panel — historical spreads
        context = html.Div([
            html.Div("Momentos clave de la prima de riesgo:", style={
                "fontSize": "0.72rem", "fontWeight": "700", "color": COLORS["text_label"],
                "marginBottom": "8px",
            }),
            html.Div([
                html.Div("Crisis 2012 → máximo ~650pb", style={"fontSize": "0.75rem", "color": COLORS["red"]}),
                html.Div("COVID 2020 → ~130pb",         style={"fontSize": "0.75rem", "color": COLORS["yellow"]}),
                html.Div(f"Actual → ~{spread:.0f}pb" if spread else "Actual → —",
                         style={"fontSize": "0.75rem", "color": COLORS["green"] if spread and spread < 100 else COLORS["yellow"]}),
            ], style={"lineHeight": "2.0", "padding": "8px",
                      "background": "#0d1320", "borderRadius": "4px", "marginBottom": "10px"}),
            html.Div(
                f"Con una prima de riesgo de {spread:.0f}pb" if spread else "La prima de riesgo española",
                style={"fontSize": "0.72rem", "color": COLORS["text_muted"]},
            ) if spread else html.Div(),
        ])
        return metrics_row, fig, context

    # ── Tab 4: Sustainability table ───────────────────────────────────────────
    @app.callback(
        Output("m8-sustainability-table", "children"),
        Output("m8-sustainability-interpretation", "children"),
        Input("m8-interval", "n_intervals"),
    )
    def update_m8_sustainability(_):
        countries_list = ["USA", "JPN", "DEU", "FRA", "ESP", "ITA", "GBR", "CHN", "BRA"]
        country_names = {
            "USA": "🇺🇸 EE.UU.", "JPN": "🇯🇵 Japón", "DEU": "🇩🇪 Alemania",
            "FRA": "🇫🇷 Francia", "ESP": "🇪🇸 España", "ITA": "🇮🇹 Italia",
            "GBR": "🇬🇧 UK", "CHN": "🇨🇳 China", "BRA": "🇧🇷 Brasil",
        }

        head_s = {"fontSize": "0.68rem", "padding": "6px 8px", "fontWeight": "700",
                  "color": COLORS["text_label"],
                  "borderBottom": f"1px solid {COLORS['border']}",
                  "whiteSpace": "nowrap", "textAlign": "right"}
        head_sl = {**head_s, "textAlign": "left"}
        cell_s  = {"fontSize": "0.75rem", "padding": "5px 8px",
                   "borderBottom": f"1px solid {COLORS['border']}20",
                   "color": COLORS["text"], "textAlign": "right"}
        cell_sl = {**cell_s, "textAlign": "left"}

        rows = [html.Tr([
            html.Th("País",          style=head_sl),
            html.Th("Deuda % PIB",   style=head_s),
            html.Th("r (tipo real)", style=head_s),
            html.Th("g (crec. PIB)", style=head_s),
            html.Th("r − g",         style=head_s),
            html.Th("Superávit prim.", style=head_s),
            html.Th("Δ Deuda/PIB",   style=head_s),
            html.Th("Clasificación", style={**head_s, "textAlign": "center"}),
        ])]

        insostenible_count = 0
        risky_countries = []
        results = []

        for iso3 in countries_list:
            res = calculate_debt_sustainability(iso3)
            results.append((iso3, res))
            if res and res["classification"] in ("insostenible_leve", "insostenible_grave"):
                insostenible_count += 1
                risky_countries.append(country_names.get(iso3, iso3))

        for iso3, res in results:
            name = country_names.get(iso3, iso3)
            if res is None:
                rows.append(html.Tr([
                    html.Td(name, style=cell_sl),
                    html.Td("—", style=cell_s),
                    html.Td("—", style=cell_s),
                    html.Td("—", style=cell_s),
                    html.Td("—", style=cell_s),
                    html.Td("—", style=cell_s),
                    html.Td("—", style=cell_s),
                    html.Td("Sin datos", style={**cell_s, "textAlign": "center"}),
                ]))
                continue

            r = res["r"]
            g = res["g"]
            rmg = res["r_minus_g"]
            pb  = res["primary_balance"]
            delta = res["delta_debt_gdp"]
            debt_gdp = res["debt_gdp"]
            cl  = res["classification"]

            delta_color = (COLORS["red"] if delta > 1 else
                           COLORS["yellow"] if delta > 0 else
                           COLORS["green"])
            rmg_color = COLORS["red"] if rmg > 0 else COLORS["green"]

            rows.append(html.Tr([
                html.Td(name, style=cell_sl),
                html.Td(f"{debt_gdp:.1f}%", style=cell_s),
                html.Td(f"{r:.1f}%", style={**cell_s, "color": COLORS["yellow"]}),
                html.Td(f"{g:.1f}%", style={**cell_s, "color": COLORS["green"]}),
                html.Td(f"{rmg:+.1f}pp", style={**cell_s, "color": rmg_color, "fontWeight": "600"}),
                html.Td(f"{pb:+.1f}%", style={**cell_s,
                        "color": COLORS["green"] if pb > 0 else COLORS["red"]}),
                html.Td(f"{delta:+.1f}pp/año", style={**cell_s, "color": delta_color, "fontWeight": "600"}),
                html.Td(_sustainability_badge(cl), style={**cell_s, "textAlign": "center"}),
            ]))

        table = html.Table(rows, style={"width": "100%", "borderCollapse": "collapse"})

        interpretation = html.Div(
            f"Actualmente, {insostenible_count} de los {len(countries_list)} países analizados tienen "
            f"dinámicas de deuda insostenibles. Los países con mayor riesgo son: "
            f"{', '.join(risky_countries) if risky_countries else 'ninguno identificado'}. "
            f"El factor común es que el diferencial (r−g) es positivo y el superávit primario es "
            f"insuficiente para compensarlo.",
            style={**_NOTE, "fontStyle": "normal", "marginTop": "12px"},
        )
        return table, interpretation

    # ── Tab 5: Repression simulation ─────────────────────────────────────────
    @app.callback(
        Output("m8-repression-sim-chart", "figure"),
        Output("m8-repression-sim-text", "children"),
        Input("m8-sim-debt",      "value"),
        Input("m8-sim-inflation", "value"),
        Input("m8-sim-years",     "value"),
    )
    def update_m8_repression_sim(debt_idx, inflation_pct, years):
        debt_idx   = debt_idx or 100
        inflation_pct = inflation_pct or 3.0
        years      = years or 10

        t = list(range(0, int(years) + 1))
        real_values = [debt_idx / ((1 + inflation_pct / 100) ** yr) for yr in t]
        nominal_values = [debt_idx] * len(t)

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=t, y=nominal_values, name="Valor nominal (fijo)",
            line=dict(color=COLORS["red"], width=2, dash="dot"),
            mode="lines",
        ))
        fig.add_trace(go.Scatter(
            x=t, y=real_values, name="Valor real (descontando inflación)",
            line=dict(color=COLORS["green"], width=2.5),
            fill="tonexty", fillcolor=_rgba(COLORS["green"], 0.1),
            mode="lines",
        ))

        final_real = real_values[-1]
        fig.update_layout(**_layout(height=300))
        fig.update_yaxes(title_text="Valor")
        fig.update_xaxes(title_text="Años")
        fig.update_layout(legend=dict(orientation="h", y=-0.25))

        text = (
            f"Una deuda de {debt_idx} con inflación del {inflation_pct}% anual vale en términos reales "
            f"solo {final_real:.1f} después de {years} años (pérdida del "
            f"{((debt_idx - final_real) / debt_idx * 100):.1f}%). "
            f"Si el gobierno paga un tipo de interés inferior a la inflación, el tipo real es negativo: "
            f"el acreedor está efectivamente subvencionando al deudor."
        )
        return fig, text

    # ── Tab 5: Real rate history ──────────────────────────────────────────────
    @app.callback(
        Output("m8-real-rate-chart", "figure"),
        Input("m8-interval", "n_intervals"),
    )
    def update_m8_real_rate(_):
        df = get_series(ID_REAL_RATE_US, days=365 * 75)
        fig = go.Figure()

        if not df.empty:
            df = df.sort_values("timestamp")
            positive_mask = df["value"] >= 0
            negative_mask = df["value"] < 0

            fig.add_trace(go.Scatter(
                x=df["timestamp"], y=df["value"].where(positive_mask),
                name="Tipo real positivo", fill="tozeroy",
                fillcolor=_rgba(COLORS["green"], 0.25),
                line=dict(color=COLORS["green"], width=1.5),
                mode="lines",
                connectgaps=False,
            ))
            fig.add_trace(go.Scatter(
                x=df["timestamp"], y=df["value"].where(negative_mask),
                name="Represión financiera (tipo real negativo)", fill="tozeroy",
                fillcolor=_rgba(COLORS["red"], 0.3),
                line=dict(color=COLORS["red"], width=1.5),
                mode="lines",
                connectgaps=False,
            ))

            # Annotations for repression periods
            fig.add_annotation(x="1970-01-01", y=-3.5,
                               text="Post-WWII → 1980: represión sostenida",
                               showarrow=False,
                               font=dict(color="#ef4444", size=9))
            fig.add_annotation(x="2021-01-01", y=-6,
                               text="COVID 2020-2022",
                               showarrow=True, arrowhead=2, ax=-40, ay=-10,
                               font=dict(color="#ef4444", size=9), arrowcolor="#374151")
        else:
            fig.add_annotation(text="Sin datos de tipo real",
                               xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False,
                               font=dict(color=COLORS["text_muted"], size=13))

        fig.add_hline(y=0, line_color="#374151", line_width=1.5,
                      annotation_text="0% — umbral represión",
                      annotation_font=dict(color="#9ca3af", size=9))

        fig.update_layout(**_layout(height=380))
        fig.update_yaxes(title_text="Tipo real (%)")
        fig.update_xaxes(title_text="", rangeselector=get_time_range_buttons(),
                         rangeslider=dict(visible=False))
        return fig

    # ── Tab 5: Repression transfer ────────────────────────────────────────────
    @app.callback(
        Output("m8-repression-transfer-panel", "children"),
        Input("m8-interval", "n_intervals"),
    )
    def update_m8_repression_transfer(_):
        # Get current real rate
        df_real = get_series(ID_REAL_RATE_US, days=365)
        real_rate = float(df_real.sort_values("timestamp").iloc[-1]["value"]) if not df_real.empty else None

        # Total US debt
        df_debt = get_series(ID_FEDERAL_DEBT_US, days=365 * 2)
        total_bn = None
        if not df_debt.empty:
            total_mn = float(df_debt.sort_values("timestamp").iloc[-1]["value"])
            total_bn = total_mn / 1_000

        if total_bn is None:
            mat_data = _load_json("us_debt_maturities.json")
            total_bn = mat_data.get("total_debt_trillion", 36.8) * 1_000 if mat_data else 36_800

        pop_millions = 335.0
        result = calculate_financial_repression_transfer(total_bn, real_rate or -1.0, pop_millions)

        if result is None:
            return html.Div([
                html.Div(f"Tipo real actual: {real_rate:.2f}%" if real_rate else "Tipo real: —",
                         style={"fontSize": "0.90rem", "color": COLORS["green"], "marginBottom": "8px"}),
                html.Div("Con tipos reales positivos no hay represión financiera activa.",
                         style={"fontSize": "0.80rem", "color": COLORS["text_muted"]}),
            ])

        return html.Div([
            dbc.Row([
                dbc.Col(_compact_metric(
                    "TIPO REAL ACTUAL",
                    f"{real_rate:.2f}%" if real_rate else "—",
                    "Fed Funds – CPI YoY",
                    COLORS["red"] if real_rate and real_rate < 0 else COLORS["green"],
                ), width=12, md=4),
                dbc.Col(_compact_metric(
                    "TRANSFERENCIA TOTAL ANUAL",
                    f"${result['transferencia_total_bn']:,.0f}bn",
                    "De ahorradores a deudores (EE.UU.)",
                    COLORS["yellow"],
                ), width=12, md=4),
                dbc.Col(_compact_metric(
                    "TRANSFERENCIA PER CÁPITA",
                    f"~${result['transferencia_per_capita']:,.0f}",
                    "Por americano y año",
                    COLORS["orange"],
                ), width=12, md=4),
            ], className="g-2"),
            html.Div(
                f"Con un tipo real de {result['real_rate_pct']:.2f}% sobre una deuda de "
                f"${total_bn/1000:.1f}T, la transferencia anual de ahorradores a deudores es de "
                f"~${result['transferencia_total_bn']:,.0f}bn (~${result['transferencia_per_capita']:,.0f} "
                f"por americano). Este es el 'impuesto invisible' de la represión financiera.",
                style={**_NOTE, "fontStyle": "normal", "marginTop": "12px"},
            ),
        ])
