"""
Módulo 16 — Análisis de Mercados y Submercados
Renta variable por sectores, renta fija, materias primas, divisas,
inmobiliario y criptomonedas. Visión granular de cada mercado.
"""

from __future__ import annotations

import json
from pathlib import Path

import dash_bootstrap_components as dbc
import plotly.graph_objs as go
from dash import Input, Output, dcc, html

from components.chart_config import COLORS as C, get_base_layout
from config import COLORS
from modules.data_helpers import (
    calculate_bond_duration_impact,
    calculate_sector_performance,
    get_latest_value,
    get_series,
)

# ── Constantes ─────────────────────────────────────────────────────────────────

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

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
_CARD = {
    "backgroundColor": COLORS["card_bg"],
    "border": f"1px solid {COLORS['border']}",
    "borderRadius": "8px",
    "padding": "16px",
    "marginBottom": "16px",
}
_INFO_BOX = {
    "backgroundColor": "#1a2332",
    "border": f"1px solid {COLORS['accent']}",
    "borderLeft": f"4px solid {COLORS['accent']}",
    "borderRadius": "6px",
    "padding": "14px 16px",
    "fontSize": "0.82rem",
    "color": COLORS["text_muted"],
    "lineHeight": "1.6",
    "marginBottom": "16px",
}
_WARNING_BOX = {
    **_INFO_BOX,
    "backgroundColor": "#2d1a1a",
    "border": f"1px solid {COLORS['red']}",
    "borderLeft": f"4px solid {COLORS['red']}",
    "color": "#fca5a5",
}

_SECTOR_COLORS = {
    "XLK":  "#3b82f6",
    "XLE":  "#f97316",
    "XLF":  "#10b981",
    "XLV":  "#ec4899",
    "XLP":  "#8b5cf6",
    "XLY":  "#f59e0b",
    "XLB":  "#84cc16",
    "XLI":  "#14b8a6",
    "XLU":  "#ef4444",
    "XLRE": "#06b6d4",
    "XLC":  "#a78bfa",
}

_COMMODITY_COLORS = {
    "crude_oil_brent":      "#f97316",
    "natural_gas_henry_hub": "#3b82f6",
    "gold":                 "#f59e0b",
    "copper":               "#84cc16",
}
_COMMODITY_LABELS = {
    "crude_oil_brent":      "Petróleo Brent",
    "natural_gas_henry_hub": "Gas Natural (Henry Hub)",
    "gold":                 "Oro",
    "copper":               "Cobre",
}

# ── Helpers ────────────────────────────────────────────────────────────────────


def _rgba(hex_color: str, alpha: float = 0.12) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def _safe(value, fmt=".2f", fallback="—"):
    if value is None:
        return fallback
    try:
        return f"{value:{fmt}}"
    except Exception:
        return fallback


def _load_json(filename: str) -> dict:
    try:
        path = _DATA_DIR / filename
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _metric_card(title: str, value: str, subtitle: str = "", color: str | None = None) -> html.Div:
    vc = color or COLORS["text"]
    return html.Div(
        [
            html.Div(title, style={
                "fontSize": "0.72rem", "color": COLORS["text_muted"],
                "textTransform": "uppercase", "letterSpacing": "0.05em",
                "marginBottom": "4px",
            }),
            html.Div(value, style={
                "fontSize": "1.4rem", "fontWeight": "700",
                "color": vc, "lineHeight": "1.2",
            }),
            html.Div(subtitle, style={
                "fontSize": "0.72rem", "color": COLORS["text_muted"],
                "marginTop": "2px",
            }) if subtitle else html.Div(),
        ],
        style={
            "backgroundColor": COLORS["card_bg"],
            "border": f"1px solid {COLORS['border']}",
            "borderRadius": "8px",
            "padding": "14px 16px",
        },
    )


def _badge(text: str, color: str = "#ef4444", bg: str | None = None) -> html.Span:
    bg = bg or _rgba(color, 0.15)
    return html.Span(text, style={
        "backgroundColor": bg,
        "color": color,
        "border": f"1px solid {color}",
        "borderRadius": "4px",
        "padding": "3px 10px",
        "fontSize": "0.75rem",
        "fontWeight": "600",
        "marginRight": "8px",
    })


def _section_title(text: str) -> html.Div:
    return html.Div(text, style={
        "fontSize": "1rem", "fontWeight": "600", "color": COLORS["text"],
        "marginBottom": "12px",
    })


def _pct_color(v: float | None) -> str:
    if v is None:
        return COLORS["text_muted"]
    return COLORS["green"] if v >= 0 else COLORS["red"]


# ── Header ─────────────────────────────────────────────────────────────────────

def _build_header() -> html.Div:
    # S&P 500 precio
    sp500_val, _ = get_latest_value("yahoo_^GSPC_close")
    sp500_str = f"{sp500_val:,.0f}" if sp500_val else "~5,600"

    # Sector líder (tech, XLK weight)
    sector_data = _load_json("sector_fundamentals.json")
    best_sector = "Tecnología"
    best_ticker = "XLK"
    if sector_data.get("sectors"):
        # Highest earnings growth = best sector
        best = max(
            sector_data["sectors"].items(),
            key=lambda x: x[1].get("earnings_growth_est_pct", 0),
        )
        best_ticker = best[0]
        best_sector = best[1].get("name", best_ticker)

    # Bitcoin precio
    btc_data = _load_json("bitcoin_onchain.json")
    btc_price = btc_data.get("current_price_usd", 84320)
    btc_str = f"${btc_price:,.0f}"

    # Brent
    futures = _load_json("futures_curves.json")
    brent_spot = futures.get("commodities", {}).get("crude_oil_brent", {}).get("spot", 103.5)
    brent_str = f"${brent_spot:.1f}"

    # Oro
    gold_spot = futures.get("commodities", {}).get("gold", {}).get("spot", 3021)
    gold_str = f"${gold_spot:,.0f}"

    badges = [
        _badge(f"💹 Sector líder (est.): {best_sector} ({best_ticker})", color=COLORS["green"]),
        _badge(
            f"⚠️ Magnificent 7 = 33.3% del S&P 500 — concentración histórica",
            color=COLORS["yellow"],
        ),
    ]

    return html.Div([
        html.Div([
            html.Div([
                html.Span("💹", style={"fontSize": "1.4rem", "marginRight": "10px"}),
                html.Div([
                    html.Div("Análisis de Mercados y Submercados",
                             style={"fontSize": "1.2rem", "fontWeight": "700", "color": COLORS["text"]}),
                    html.Div("Renta variable, renta fija, materias primas, divisas, inmobiliario y cripto",
                             style={"fontSize": "0.82rem", "color": COLORS["text_muted"]}),
                ]),
            ], style={"display": "flex", "alignItems": "center"}),
            html.Div(badges, style={"display": "flex", "flexWrap": "wrap", "gap": "6px", "marginTop": "8px"}),
        ], style={"marginBottom": "14px"}),

        dbc.Row([
            dbc.Col(_metric_card("S&P 500", sp500_str, "Fuente: Yahoo Finance"), width=2),
            dbc.Col(_metric_card("Petróleo Brent", brent_str, "USD/barril"), width=2),
            dbc.Col(_metric_card("Oro", gold_str, "USD/oz"), width=2),
            dbc.Col(_metric_card("Bitcoin", btc_str, "USD"), width=2),
            dbc.Col(_metric_card("Mejor Sector Est.", best_sector, "Mayor crec. beneficios",
                                 COLORS["green"]), width=2),
            dbc.Col(_metric_card("ETFs Bitcoin AUM", "$62.5B", "742K BTC en ETFs"), width=2),
        ], className="g-2"),
    ], id="m16-header", style={
        "backgroundColor": COLORS["card_bg"],
        "border": f"1px solid {COLORS['border']}",
        "borderRadius": "8px",
        "padding": "16px",
        "marginBottom": "16px",
    })


# ── TAB 1: Renta Variable por Sectores ─────────────────────────────────────────

def _build_tab1() -> html.Div:
    mag7_dropdown = dcc.Dropdown(
        id="m16-mag7-metric",
        options=[
            {"label": "PER Forward", "value": "forward_pe"},
            {"label": "Crecimiento Ingresos YoY %", "value": "revenue_growth_yoy_pct"},
            {"label": "Margen Neto %", "value": "net_margin_pct"},
        ],
        value="forward_pe",
        clearable=False,
        style={
            "backgroundColor": COLORS["card_bg"],
            "color": COLORS["text"],
            "border": f"1px solid {COLORS['border']}",
            "width": "240px",
        },
    )

    return html.Div([
        # 1.1 — Rendimiento sectorial
        html.Div([
            _section_title("1.1 — Rendimiento Sectorial S&P 500"),
            dcc.Loading(
                dcc.Graph(id="m16-sector-performance-chart", config={"displayModeBar": False},
                          style={"height": "300px"}),
                color=COLORS["accent"],
            ),
            html.Div(
                "Los rendimientos sectoriales reflejan las expectativas del mercado sobre la economía. "
                "Energía y materiales lideran en contextos inflacionarios; tecnología y consumo discrecional "
                "en expansiones; utilities y consumo básico en recesiones.",
                style=_INFO_BOX,
            ),
        ], style=_CARD),

        # 1.2 — Valoraciones sectoriales
        dbc.Row([
            dbc.Col([
                html.Div([
                    _section_title("1.2 — PER Forward por Sector"),
                    dcc.Loading(
                        dcc.Graph(id="m16-sector-pe-chart", config={"displayModeBar": False},
                                  style={"height": "280px"}),
                        color=COLORS["accent"],
                    ),
                ], style=_CARD),
            ], width=6),
            dbc.Col([
                html.Div([
                    _section_title("1.3 — Peso en S&P 500 vs Crecimiento Estimado"),
                    dcc.Loading(
                        dcc.Graph(id="m16-sector-bubble-chart", config={"displayModeBar": False},
                                  style={"height": "280px"}),
                        color=COLORS["accent"],
                    ),
                ], style=_CARD),
            ], width=6),
        ]),

        # 1.4 — Magnificent 7
        html.Div([
            html.Div([
                _section_title("1.4 — Magnificent 7 — Análisis Detallado"),
                mag7_dropdown,
            ], style={"display": "flex", "alignItems": "center", "justifyContent": "space-between",
                      "marginBottom": "12px"}),
            dbc.Row([
                dbc.Col([
                    dcc.Loading(
                        dcc.Graph(id="m16-mag7-chart", config={"displayModeBar": False},
                                  style={"height": "280px"}),
                        color=COLORS["accent"],
                    ),
                ], width=8),
                dbc.Col([
                    html.Div(id="m16-mag7-stats"),
                ], width=4),
            ]),
            html.Div(
                "Las 7 mega-capitalizaciones representan el 33.3% del S&P 500. "
                "Su concentración sin precedentes significa que el índice está cada vez más "
                "expuesto a los ciclos de gasto en IA y tecnología.",
                style={**_WARNING_BOX, "marginTop": "12px"},
            ),
        ], style=_CARD),

        # 1.5 — Sector Defensa
        html.Div([
            _section_title("1.5 — Sector Defensa — Impulso OTAN"),
            dbc.Row([
                dbc.Col([
                    dcc.Loading(
                        dcc.Graph(id="m16-defense-chart", config={"displayModeBar": False},
                                  style={"height": "260px"}),
                        color=COLORS["accent"],
                    ),
                ], width=7),
                dbc.Col([
                    html.Div(id="m16-defense-stats", style={"marginTop": "8px"}),
                ], width=5),
            ]),
        ], style=_CARD),
    ])


# ── TAB 2: Renta Fija y Crédito ────────────────────────────────────────────────

def _build_tab2() -> html.Div:
    duration_inputs = html.Div([
        html.Div("Calculadora de Impacto de Duración", style={
            "fontSize": "0.9rem", "fontWeight": "600", "color": COLORS["text"],
            "marginBottom": "10px",
        }),
        dbc.Row([
            dbc.Col([
                html.Div("Yield actual (%)", style={"fontSize": "0.75rem", "color": COLORS["text_muted"], "marginBottom": "4px"}),
                dcc.Input(id="m16-yield-current", type="number", value=4.5, step=0.1, min=0, max=20,
                          style={"backgroundColor": COLORS["bg"], "color": COLORS["text"],
                                 "border": f"1px solid {COLORS['border']}", "borderRadius": "4px",
                                 "padding": "6px 10px", "width": "100%"}),
            ], width=4),
            dbc.Col([
                html.Div("Cambio yield (pp)", style={"fontSize": "0.75rem", "color": COLORS["text_muted"], "marginBottom": "4px"}),
                dcc.Input(id="m16-yield-change", type="number", value=0.5, step=0.1, min=-5, max=5,
                          style={"backgroundColor": COLORS["bg"], "color": COLORS["text"],
                                 "border": f"1px solid {COLORS['border']}", "borderRadius": "4px",
                                 "padding": "6px 10px", "width": "100%"}),
            ], width=4),
            dbc.Col([
                html.Div("Duración (años)", style={"fontSize": "0.75rem", "color": COLORS["text_muted"], "marginBottom": "4px"}),
                dcc.Input(id="m16-duration", type="number", value=7, step=1, min=1, max=30,
                          style={"backgroundColor": COLORS["bg"], "color": COLORS["text"],
                                 "border": f"1px solid {COLORS['border']}", "borderRadius": "4px",
                                 "padding": "6px 10px", "width": "100%"}),
            ], width=4),
        ], className="g-2"),
        html.Div(id="m16-duration-result", style={"marginTop": "10px"}),
    ], style={
        "backgroundColor": COLORS["bg"],
        "border": f"1px solid {COLORS['border']}",
        "borderRadius": "6px",
        "padding": "14px",
        "marginBottom": "16px",
    })

    return html.Div([
        # 2.1 — Curva de tipos en tiempo real (proxy)
        html.Div([
            _section_title("2.1 — Curva de Tipos EE.UU."),
            dcc.Loading(
                dcc.Graph(id="m16-yield-curve-chart", config={"displayModeBar": False},
                          style={"height": "280px"}),
                color=COLORS["accent"],
            ),
            html.Div(
                "Una curva invertida (yields cortos > largos) históricamente precede recesiones "
                "con 12-18 meses de antelación. La desinversión actual señala que el mercado "
                "anticipa recortes de tipos por la Fed.",
                style=_INFO_BOX,
            ),
        ], style=_CARD),

        # 2.2 — Flujos bonos + calculadora
        dbc.Row([
            dbc.Col([
                html.Div([
                    _section_title("2.2 — Flujos Fondos de Renta Fija"),
                    dcc.Loading(
                        dcc.Graph(id="m16-bond-flows-chart", config={"displayModeBar": False},
                                  style={"height": "250px"}),
                        color=COLORS["accent"],
                    ),
                ], style=_CARD),
            ], width=6),
            dbc.Col([
                html.Div([
                    _section_title("2.3 — Calculadora Duración"),
                    duration_inputs,
                    html.Div(
                        "La duración mide la sensibilidad del precio al cambio en yields. "
                        "Un bono a 10 años con duración 7 pierde ~6.7% si los yields suben 100pb.",
                        style={**_INFO_BOX, "marginBottom": "0"},
                    ),
                ], style=_CARD),
            ], width=6),
        ]),

        # 2.4 — Carry trade monitor
        html.Div([
            _section_title("2.4 — Monitor de Carry Trade"),
            dcc.Loading(
                dcc.Graph(id="m16-carry-chart", config={"displayModeBar": False},
                          style={"height": "260px"}),
                color=COLORS["accent"],
            ),
            html.Div(id="m16-carry-table", style={"marginTop": "12px"}),
            html.Div(
                "El carry trade consiste en pedir prestado en monedas con tipos bajos (JPY, CHF) "
                "e invertir en monedas con tipos altos. Una reversión brusca puede provocar "
                "ventas masivas en activos de riesgo globales.",
                style={**_WARNING_BOX, "marginTop": "12px"},
            ),
        ], style=_CARD),
    ])


# ── TAB 3: Materias Primas ─────────────────────────────────────────────────────

def _build_tab3() -> html.Div:
    commodity_selector = dcc.Dropdown(
        id="m16-commodity-select",
        options=[
            {"label": "🛢️ Petróleo Brent", "value": "crude_oil_brent"},
            {"label": "🔥 Gas Natural", "value": "natural_gas_henry_hub"},
            {"label": "🥇 Oro", "value": "gold"},
            {"label": "🟤 Cobre", "value": "copper"},
        ],
        value="crude_oil_brent",
        clearable=False,
        style={
            "backgroundColor": COLORS["card_bg"],
            "color": COLORS["text"],
            "border": f"1px solid {COLORS['border']}",
            "width": "240px",
        },
    )

    return html.Div([
        # 3.1 — Superciclo BCOM
        html.Div([
            _section_title("3.1 — Bloomberg Commodity Index — Superciclo"),
            dcc.Loading(
                dcc.Graph(id="m16-bcom-chart", config={"displayModeBar": False},
                          style={"height": "300px"}),
                color=COLORS["accent"],
            ),
            html.Div(
                "El análisis de superciclos sugiere que la transición energética y la "
                "desglobalización podrían impulsar un nuevo ciclo alcista en materias primas. "
                "Goldman Sachs proyecta un +8.5% en el BCOM a 12 meses.",
                style=_INFO_BOX,
            ),
        ], style=_CARD),

        # 3.2 — Curvas de futuros
        dbc.Row([
            dbc.Col([
                html.Div([
                    html.Div([
                        _section_title("3.2 — Curva de Futuros"),
                        commodity_selector,
                    ], style={"display": "flex", "alignItems": "center",
                              "justifyContent": "space-between", "marginBottom": "12px"}),
                    dcc.Loading(
                        dcc.Graph(id="m16-futures-curve-chart", config={"displayModeBar": False},
                                  style={"height": "280px"}),
                        color=COLORS["accent"],
                    ),
                    html.Div(id="m16-futures-note", style={"marginTop": "8px"}),
                ], style=_CARD),
            ], width=7),
            dbc.Col([
                html.Div([
                    _section_title("3.3 — Contango vs Backwardation"),
                    dcc.Loading(
                        dcc.Graph(id="m16-market-structure-chart", config={"displayModeBar": False},
                                  style={"height": "280px"}),
                        color=COLORS["accent"],
                    ),
                    html.Div(
                        "Backwardation → mercado en déficit (spot > futuros). "
                        "Contango → mercado en superávit (futuros > spot).",
                        style={**_INFO_BOX, "marginBottom": "0"},
                    ),
                ], style=_CARD),
            ], width=5),
        ]),
    ])


# ── TAB 4: Divisas ─────────────────────────────────────────────────────────────

def _build_tab4() -> html.Div:
    return html.Div([
        # 4.1 — Índice dólar (DXY)
        html.Div([
            _section_title("4.1 — Índice Dólar (DXY) — Evolución Histórica"),
            dcc.Loading(
                dcc.Graph(id="m16-dxy-chart", config={"displayModeBar": False},
                          style={"height": "280px"}),
                color=COLORS["accent"],
            ),
            html.Div(
                "El dólar fuerte presiona a economías emergentes con deuda en USD, "
                "reduce la competitividad exportadora de EE.UU. y supone un viento "
                "en contra para materias primas cotizadas en dólares.",
                style=_INFO_BOX,
            ),
        ], style=_CARD),

        # 4.2 — Carry trade diferencial
        dbc.Row([
            dbc.Col([
                html.Div([
                    _section_title("4.2 — Diferencial de Tipos por Par de Carry"),
                    dcc.Loading(
                        dcc.Graph(id="m16-carry-differential-chart", config={"displayModeBar": False},
                                  style={"height": "260px"}),
                        color=COLORS["accent"],
                    ),
                ], style=_CARD),
            ], width=6),
            dbc.Col([
                html.Div([
                    _section_title("4.3 — Riesgo de Reversión por Par"),
                    dcc.Loading(
                        dcc.Graph(id="m16-carry-risk-chart", config={"displayModeBar": False},
                                  style={"height": "260px"}),
                        color=COLORS["accent"],
                    ),
                ], style=_CARD),
            ], width=6),
        ]),

        # 4.4 — Tabla divisas principales
        html.Div([
            _section_title("4.4 — Divisas Principales — Monitor"),
            html.Div(id="m16-fx-table"),
        ], style=_CARD),
    ])


# ── TAB 5: Inmobiliario ────────────────────────────────────────────────────────

def _build_tab5() -> html.Div:
    housing_metric = dcc.Dropdown(
        id="m16-housing-metric",
        options=[
            {"label": "Precio / Ingresos", "value": "price_to_income"},
            {"label": "Precio / Alquiler", "value": "price_to_rent"},
            {"label": "Variación Precio YoY %", "value": "price_yoy_pct"},
            {"label": "Tipo Hipotecario %", "value": "mortgage_rate_pct"},
        ],
        value="price_to_income",
        clearable=False,
        style={
            "backgroundColor": COLORS["card_bg"],
            "color": COLORS["text"],
            "border": f"1px solid {COLORS['border']}",
            "width": "240px",
        },
    )

    return html.Div([
        # 5.1 — Comparativa vivienda global
        html.Div([
            html.Div([
                _section_title("5.1 — Mercado Residencial Global"),
                housing_metric,
            ], style={"display": "flex", "alignItems": "center",
                      "justifyContent": "space-between", "marginBottom": "12px"}),
            dcc.Loading(
                dcc.Graph(id="m16-housing-chart", config={"displayModeBar": False},
                          style={"height": "300px"}),
                color=COLORS["accent"],
            ),
            html.Div(
                "España lidera el crecimiento con +8.5% YoY. Alemania y China corrijen. "
                "Los ratios Precio/Ingresos en Australia (13.5×), China (18.3×) y Canadá (15.8×) "
                "siguen en zona de burbuja histórica.",
                style=_INFO_BOX,
            ),
        ], style=_CARD),

        # 5.2 — Real estate comercial
        dbc.Row([
            dbc.Col([
                html.Div([
                    _section_title("5.2 — Tasa de Desocupación Oficinas EE.UU."),
                    dcc.Loading(
                        dcc.Graph(id="m16-cre-vacancy-chart", config={"displayModeBar": False},
                                  style={"height": "280px"}),
                        color=COLORS["accent"],
                    ),
                ], style=_CARD),
            ], width=6),
            dbc.Col([
                html.Div([
                    _section_title("5.3 — Exposición Bancaria al Real Estate Comercial"),
                    dcc.Loading(
                        dcc.Graph(id="m16-cre-exposure-chart", config={"displayModeBar": False},
                                  style={"height": "280px"}),
                        color=COLORS["accent"],
                    ),
                ], style=_CARD),
            ], width=6),
        ]),

        html.Div(
            "⚠️ $950B en préstamos CRE vencen en 2026-2027. Los pequeños bancos tienen el 28.7% "
            "de sus préstamos en CRE. Con una vacancia del 35% en San Francisco, las refinanciaciones "
            "pueden desencadenar pérdidas que estresen el sistema bancario regional.",
            style=_WARNING_BOX,
        ),
    ])


# ── TAB 6: Criptomonedas ───────────────────────────────────────────────────────

def _build_tab6() -> html.Div:
    return html.Div([
        # 6.1 — On-chain metrics
        html.Div([
            _section_title("6.1 — Bitcoin On-Chain — Métricas Clave"),
            dbc.Row([
                dbc.Col([
                    dcc.Loading(
                        dcc.Graph(id="m16-btc-mvrv-chart", config={"displayModeBar": False},
                                  style={"height": "280px"}),
                        color=COLORS["accent"],
                    ),
                ], width=6),
                dbc.Col([
                    dcc.Loading(
                        dcc.Graph(id="m16-btc-supply-chart", config={"displayModeBar": False},
                                  style={"height": "280px"}),
                        color=COLORS["accent"],
                    ),
                ], width=6),
            ]),
            html.Div(id="m16-btc-metrics-cards", style={"marginTop": "12px"}),
        ], style=_CARD),

        # 6.2 — Institucional
        html.Div([
            _section_title("6.2 — Institucionalización — ETFs y Tesorerías Corporativas"),
            dbc.Row([
                dbc.Col([
                    dcc.Loading(
                        dcc.Graph(id="m16-btc-etf-chart", config={"displayModeBar": False},
                                  style={"height": "280px"}),
                        color=COLORS["accent"],
                    ),
                ], width=6),
                dbc.Col([
                    dcc.Loading(
                        dcc.Graph(id="m16-btc-treasury-chart", config={"displayModeBar": False},
                                  style={"height": "280px"}),
                        color=COLORS["accent"],
                    ),
                ], width=6),
            ]),
            html.Div(
                "Los ETFs de Bitcoin acumulan ya 742.000 BTC (~$62.5B). BlackRock lidera con "
                "285.000 BTC. MicroStrategy mantiene 214.000 BTC como activo de tesorería principal. "
                "La institucionalización reduce la volatilidad a largo plazo pero crea correlación "
                "con mercados financieros tradicionales.",
                style=_INFO_BOX,
            ),
        ], style=_CARD),
    ])


# ── render_module_16 ───────────────────────────────────────────────────────────

def render_module_16() -> html.Div:
    return html.Div([
        dcc.Interval(id="m16-interval", interval=300_000, n_intervals=0),
        _build_header(),
        html.Div([
            dcc.Tabs(
                id="m16-tabs",
                value="tab-1",
                children=[
                    dcc.Tab(label="📊 Renta Variable", value="tab-1",
                            style=_TAB_STYLE, selected_style=_TAB_SELECTED),
                    dcc.Tab(label="📈 Renta Fija", value="tab-2",
                            style=_TAB_STYLE, selected_style=_TAB_SELECTED),
                    dcc.Tab(label="⚡ Materias Primas", value="tab-3",
                            style=_TAB_STYLE, selected_style=_TAB_SELECTED),
                    dcc.Tab(label="💱 Divisas", value="tab-4",
                            style=_TAB_STYLE, selected_style=_TAB_SELECTED),
                    dcc.Tab(label="🏠 Inmobiliario", value="tab-5",
                            style=_TAB_STYLE, selected_style=_TAB_SELECTED),
                    dcc.Tab(label="₿ Criptomonedas", value="tab-6",
                            style=_TAB_STYLE, selected_style=_TAB_SELECTED),
                ],
                style=_TABS_CONTAINER,
            ),
            html.Div(id="m16-tab-content", style={"padding": "16px 0"}),
        ], style={
            "backgroundColor": COLORS["card_bg"],
            "border": f"1px solid {COLORS['border']}",
            "borderRadius": "8px",
            "padding": "0",
            "overflow": "hidden",
        }),
    ])


# ── Callbacks ──────────────────────────────────────────────────────────────────

def register_callbacks_module_16(app):  # noqa: C901

    # Tab routing
    @app.callback(
        Output("m16-tab-content", "children"),
        Input("m16-tabs", "value"),
    )
    def render_tab(tab):
        if tab == "tab-1":
            return _build_tab1()
        if tab == "tab-2":
            return _build_tab2()
        if tab == "tab-3":
            return _build_tab3()
        if tab == "tab-4":
            return _build_tab4()
        if tab == "tab-5":
            return _build_tab5()
        if tab == "tab-6":
            return _build_tab6()
        return html.Div()

    # ── TAB 1 callbacks ────────────────────────────────────────────────────────

    @app.callback(
        Output("m16-sector-performance-chart", "figure"),
        Input("m16-tabs", "value"),
    )
    def update_sector_performance(tab):
        if tab != "tab-1":
            return go.Figure()
        df = calculate_sector_performance(period_days=365)
        sector_data = _load_json("sector_fundamentals.json")
        sectors_info = sector_data.get("sectors", {})

        if df is not None and not df.empty:
            tickers = df["ticker"].tolist()
            changes_1d = df["change_1d_pct"].tolist()
            changes_period = df["change_period_pct"].tolist()
            names = [sectors_info.get(t, {}).get("name", t) for t in tickers]
        else:
            # Fallback estático
            tickers = list(sectors_info.keys())
            names = [v.get("name", k) for k, v in sectors_info.items()]
            changes_1d = [0.5, -0.3, 0.8, 0.2, -0.1, 1.2, 0.6, 0.4, -0.2, 0.9, 1.5]
            changes_period = [18.2, 8.5, 9.1, 11.3, 5.8, 14.7, 7.2, 10.4, 6.1, 4.3, 15.1]

        colors_1d = [COLORS["green"] if v >= 0 else COLORS["red"] for v in changes_1d]
        colors_period = [COLORS["green"] if v >= 0 else COLORS["red"] for v in changes_period]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            name="1 Día %",
            x=names,
            y=changes_1d,
            marker_color=colors_1d,
            opacity=0.85,
        ))
        fig.add_trace(go.Bar(
            name="12 Meses %",
            x=names,
            y=changes_period,
            marker_color=colors_period,
            opacity=0.55,
            visible="legendonly",
        ))

        layout = get_base_layout(height=290)
        layout.update(
            barmode="group",
            margin=dict(l=55, r=15, t=40, b=60),
            yaxis_title="Cambio %",
            legend=dict(orientation="h", y=1.12, x=0),
            xaxis_tickangle=-30,
        )
        fig.update_layout(layout)
        return fig

    @app.callback(
        Output("m16-sector-pe-chart", "figure"),
        Input("m16-tabs", "value"),
    )
    def update_sector_pe(tab):
        if tab != "tab-1":
            return go.Figure()
        sector_data = _load_json("sector_fundamentals.json")
        sectors = sector_data.get("sectors", {})
        tickers = list(sectors.keys())
        names = [v.get("name", k) for k, v in sectors.items()]
        pes = [v.get("forward_pe", 0) for v in sectors.values()]
        sp500_avg_pe = 22.0

        colors = [
            COLORS["red"] if pe > sp500_avg_pe * 1.2
            else COLORS["yellow"] if pe > sp500_avg_pe
            else COLORS["green"]
            for pe in pes
        ]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=names, y=pes,
            marker_color=colors,
            text=[f"{p:.1f}×" for p in pes],
            textposition="outside",
            textfont=dict(size=10),
        ))
        fig.add_hline(y=sp500_avg_pe, line_dash="dot", line_color=COLORS["text_muted"],
                      annotation_text=f"S&P500 avg {sp500_avg_pe}×",
                      annotation_font_color=COLORS["text_muted"])

        layout = get_base_layout(height=270)
        layout.update(margin=dict(l=55, r=15, t=40, b=60), xaxis_tickangle=-30,
                      yaxis_title="PER Forward")
        fig.update_layout(layout)
        return fig

    @app.callback(
        Output("m16-sector-bubble-chart", "figure"),
        Input("m16-tabs", "value"),
    )
    def update_sector_bubble(tab):
        if tab != "tab-1":
            return go.Figure()
        sector_data = _load_json("sector_fundamentals.json")
        sectors = sector_data.get("sectors", {})

        fig = go.Figure()
        for ticker, info in sectors.items():
            color = _SECTOR_COLORS.get(ticker, COLORS["text_muted"])
            fig.add_trace(go.Scatter(
                x=[info.get("weight_sp500_pct", 0)],
                y=[info.get("earnings_growth_est_pct", 0)],
                mode="markers+text",
                name=info.get("name", ticker),
                text=[ticker],
                textposition="top center",
                textfont=dict(size=10),
                marker=dict(
                    size=info.get("weight_sp500_pct", 1) * 3 + 8,
                    color=color,
                    opacity=0.8,
                ),
            ))

        layout = get_base_layout(height=270)
        layout.update(
            margin=dict(l=55, r=15, t=40, b=40),
            xaxis_title="Peso en S&P500 (%)",
            yaxis_title="Crec. Beneficios Est. (%)",
            showlegend=False,
        )
        fig.update_layout(layout)
        return fig

    @app.callback(
        Output("m16-mag7-chart", "figure"),
        Output("m16-mag7-stats", "children"),
        Input("m16-tabs", "value"),
        Input("m16-mag7-metric", "value"),
    )
    def update_mag7(tab, metric):
        if tab != "tab-1":
            return go.Figure(), html.Div()
        data = _load_json("magnificent_seven.json")
        companies = data.get("companies", [])
        if not companies:
            return go.Figure(), html.Div()

        names = [c["ticker"] for c in companies]
        values = [c.get(metric, 0) for c in companies]
        metric_labels = {
            "forward_pe": "PER Forward",
            "revenue_growth_yoy_pct": "Crec. Ingresos YoY %",
            "net_margin_pct": "Margen Neto %",
        }
        label = metric_labels.get(metric, metric)

        m7_colors = ["#3b82f6", "#10b981", "#f97316", "#f59e0b", "#8b5cf6", "#ec4899", "#ef4444"]
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=names, y=values,
            marker_color=m7_colors[:len(names)],
            text=[f"{v:.1f}" for v in values],
            textposition="outside",
        ))
        layout = get_base_layout(height=270)
        layout.update(margin=dict(l=55, r=15, t=40, b=40), yaxis_title=label)
        fig.update_layout(layout)

        # Stats panel
        stats = []
        for c in companies:
            stats.append(html.Div([
                html.Span(c["ticker"], style={"fontWeight": "700", "color": COLORS["accent"],
                                              "fontSize": "0.85rem", "marginRight": "6px"}),
                html.Span(f"{c.get('weight_sp500_pct', 0):.1f}% S&P",
                          style={"fontSize": "0.75rem", "color": COLORS["text_muted"]}),
            ], style={"marginBottom": "4px"}))

        stats_div = html.Div([
            html.Div(f"Peso combinado: {data.get('combined_weight_sp500_pct', 0):.1f}%",
                     style={"fontSize": "0.85rem", "fontWeight": "600",
                            "color": COLORS["yellow"], "marginBottom": "10px"}),
            html.Div(f"Market Cap: ${data.get('combined_market_cap_trillion', 0):.1f}T",
                     style={"fontSize": "0.82rem", "color": COLORS["text_muted"],
                            "marginBottom": "10px"}),
        ] + stats)
        return fig, stats_div

    @app.callback(
        Output("m16-defense-chart", "figure"),
        Output("m16-defense-stats", "children"),
        Input("m16-tabs", "value"),
    )
    def update_defense(tab):
        if tab != "tab-1":
            return go.Figure(), html.Div()
        data = _load_json("defense_sector.json")
        contractors = data.get("top_contractors", [])

        names = [c["name"] for c in contractors]
        revenues = [c.get("revenue_bn", 0) for c in contractors]
        backlogs = [c.get("backlog_bn", 0) for c in contractors]

        fig = go.Figure()
        fig.add_trace(go.Bar(name="Revenue $B", x=names, y=revenues,
                             marker_color=COLORS["accent"], opacity=0.85))
        fig.add_trace(go.Bar(name="Backlog $B", x=names, y=backlogs,
                             marker_color=COLORS["yellow"], opacity=0.55))

        layout = get_base_layout(height=250)
        layout.update(barmode="group", margin=dict(l=55, r=15, t=40, b=60),
                      xaxis_tickangle=-20, yaxis_title="USD Billions",
                      legend=dict(orientation="h", y=1.12, x=0))
        fig.update_layout(layout)

        stats = html.Div([
            html.Div("OTAN — Gasto en Defensa", style={"fontSize": "0.82rem", "fontWeight": "600",
                                                        "color": COLORS["text"], "marginBottom": "8px"}),
            html.Div(f"Países al objetivo 2%: {data.get('countries_meeting_target_2025', 0)} / "
                     f"{data.get('total_nato_members', 0)}",
                     style={"fontSize": "0.78rem", "color": COLORS["text_muted"], "marginBottom": "4px"}),
            html.Div(f"Presupuesto EE.UU. 2025: ${data.get('us_defense_budget_2025_bn', 0):.0f}B",
                     style={"fontSize": "0.78rem", "color": COLORS["text_muted"], "marginBottom": "4px"}),
            html.Div(f"Petición Trump 2026: ${data.get('us_defense_budget_trump_request_2026_bn', 0):.0f}B",
                     style={"fontSize": "0.78rem", "color": COLORS["yellow"], "marginBottom": "4px"}),
        ])
        return fig, stats

    # ── TAB 2 callbacks ────────────────────────────────────────────────────────

    @app.callback(
        Output("m16-yield-curve-chart", "figure"),
        Input("m16-tabs", "value"),
    )
    def update_yield_curve(tab):
        if tab != "tab-2":
            return go.Figure()

        # Intentar leer de DB, fallback estático
        maturities_label = ["3M", "6M", "1Y", "2Y", "5Y", "7Y", "10Y", "20Y", "30Y"]
        maturities_x = [0.25, 0.5, 1, 2, 5, 7, 10, 20, 30]

        series_ids = [
            "fred_DGS3MO", "fred_DGS6MO", "fred_DGS1", "fred_DGS2",
            "fred_DGS5", "fred_DGS7", "fred_DGS10", "fred_DGS20", "fred_DGS30",
        ]
        yields_current = []
        for sid in series_ids:
            v, _ = get_latest_value(sid)
            yields_current.append(v)

        # Si no hay datos en DB, usar fallback estático representativo
        static_current = [5.22, 5.15, 5.01, 4.72, 4.35, 4.38, 4.42, 4.75, 4.58]
        static_1y_ago = [5.38, 5.35, 5.12, 4.89, 4.21, 4.18, 4.22, 4.55, 4.40]

        curve = [v if v is not None else s for v, s in zip(yields_current, static_current)]

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=maturities_x, y=curve,
            mode="lines+markers",
            name="Actual",
            line=dict(color=COLORS["accent"], width=2.5),
            marker=dict(size=6),
        ))
        fig.add_trace(go.Scatter(
            x=maturities_x, y=static_1y_ago,
            mode="lines+markers",
            name="Hace 1 año",
            line=dict(color=COLORS["text_muted"], width=1.5, dash="dot"),
            marker=dict(size=5),
        ))
        fig.add_hline(y=0, line_color=COLORS["border"], line_width=1)

        layout = get_base_layout(height=270)
        layout.update(
            margin=dict(l=55, r=15, t=40, b=40),
            xaxis=dict(
                title="Vencimiento (años)",
                tickvals=maturities_x,
                ticktext=maturities_label,
            ),
            yaxis_title="Yield %",
            legend=dict(orientation="h", y=1.12, x=0),
        )
        fig.update_layout(layout)
        return fig

    @app.callback(
        Output("m16-bond-flows-chart", "figure"),
        Input("m16-tabs", "value"),
    )
    def update_bond_flows(tab):
        if tab != "tab-2":
            return go.Figure()
        data = _load_json("bond_flows.json")
        flows = data.get("monthly_flows_bn_usd", {})
        if not flows:
            return go.Figure()

        months = sorted(flows.keys())
        values = [flows[m] for m in months]
        colors = [COLORS["green"] if v >= 0 else COLORS["red"] for v in values]

        fig = go.Figure()
        fig.add_trace(go.Bar(x=months, y=values, marker_color=colors, name="Flujos $B"))
        layout = get_base_layout(height=240)
        layout.update(margin=dict(l=55, r=15, t=40, b=40),
                      yaxis_title="USD Billions", xaxis_tickangle=-30)
        fig.update_layout(layout)
        return fig

    @app.callback(
        Output("m16-duration-result", "children"),
        Input("m16-yield-current", "value"),
        Input("m16-yield-change", "value"),
        Input("m16-duration", "value"),
        Input("m16-tabs", "value"),
    )
    def update_duration_calc(current_yield, yield_change, duration, tab):
        if tab != "tab-2":
            return html.Div()
        try:
            current_yield = float(current_yield or 4.5)
            yield_change = float(yield_change or 0.5)
            duration = float(duration or 7)
            impact = calculate_bond_duration_impact(current_yield, yield_change, duration)
            color = COLORS["green"] if impact >= 0 else COLORS["red"]
            direction = "sube" if yield_change > 0 else "baja"
            return html.Div([
                html.Span("Impacto en precio: ", style={
                    "fontSize": "0.85rem", "color": COLORS["text_muted"],
                }),
                html.Span(f"{impact:+.2f}%", style={
                    "fontSize": "1.2rem", "fontWeight": "700", "color": color,
                    "marginLeft": "6px",
                }),
                html.Div(
                    f"Si el yield {direction} {abs(yield_change):.1f}pp, "
                    f"un bono con duración {duration:.0f} años pierde/gana {impact:+.2f}% de valor.",
                    style={"fontSize": "0.75rem", "color": COLORS["text_muted"], "marginTop": "4px"},
                ),
            ])
        except Exception:
            return html.Div()

    @app.callback(
        Output("m16-carry-chart", "figure"),
        Output("m16-carry-table", "children"),
        Input("m16-tabs", "value"),
    )
    def update_carry(tab):
        if tab != "tab-2":
            return go.Figure(), html.Div()
        data = _load_json("carry_trade_monitor.json")
        pairs = data.get("pairs", [])
        if not pairs:
            return go.Figure(), html.Div()

        labels = [f"{p['fund_currency']}/{p['invest_currency']}" for p in pairs]
        differentials = [p.get("rate_differential_pct", 0) for p in pairs]
        risk_colors = {
            "low": COLORS["green"],
            "medium": COLORS["yellow"],
            "high": COLORS["red"],
            "very_high": "#ef4444",
        }
        colors = [risk_colors.get(p.get("reversal_risk", "medium"), COLORS["yellow"]) for p in pairs]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=labels, y=differentials,
            marker_color=colors,
            text=[f"{d:.1f}%" for d in differentials],
            textposition="outside",
        ))
        layout = get_base_layout(height=250)
        layout.update(margin=dict(l=55, r=15, t=40, b=40), yaxis_title="Diferencial de Tipos %")
        fig.update_layout(layout)

        # Table
        rows = []
        for p in pairs:
            risk = p.get("reversal_risk", "medium")
            rc = risk_colors.get(risk, COLORS["yellow"])
            rows.append(html.Tr([
                html.Td(f"{p['fund_currency']}/{p['invest_currency']}",
                        style={"fontWeight": "600", "color": COLORS["accent"], "padding": "6px 8px"}),
                html.Td(f"{p.get('rate_differential_pct', 0):.1f}%",
                        style={"color": COLORS["green"], "padding": "6px 8px"}),
                html.Td(html.Span(risk.upper(), style={
                    "backgroundColor": _rgba(rc, 0.15), "color": rc,
                    "border": f"1px solid {rc}", "borderRadius": "4px",
                    "padding": "2px 8px", "fontSize": "0.72rem",
                }), style={"padding": "6px 8px"}),
                html.Td(p.get("note", ""), style={"fontSize": "0.75rem",
                                                   "color": COLORS["text_muted"], "padding": "6px 8px"}),
            ]))

        table = html.Table(
            [html.Thead(html.Tr([
                html.Th("Par", style={"padding": "6px 8px", "color": COLORS["text_muted"],
                                      "fontWeight": "600", "fontSize": "0.75rem",
                                      "borderBottom": f"1px solid {COLORS['border']}"}),
                html.Th("Diferencial", style={"padding": "6px 8px", "color": COLORS["text_muted"],
                                              "fontWeight": "600", "fontSize": "0.75rem",
                                              "borderBottom": f"1px solid {COLORS['border']}"}),
                html.Th("Riesgo Reversión", style={"padding": "6px 8px", "color": COLORS["text_muted"],
                                                    "fontWeight": "600", "fontSize": "0.75rem",
                                                    "borderBottom": f"1px solid {COLORS['border']}"}),
                html.Th("Nota", style={"padding": "6px 8px", "color": COLORS["text_muted"],
                                       "fontWeight": "600", "fontSize": "0.75rem",
                                       "borderBottom": f"1px solid {COLORS['border']}"}),
            ])),
             html.Tbody(rows)],
            style={"width": "100%", "borderCollapse": "collapse",
                   "backgroundColor": COLORS["bg"], "borderRadius": "6px"},
        )
        return fig, table

    # ── TAB 3 callbacks ────────────────────────────────────────────────────────

    @app.callback(
        Output("m16-bcom-chart", "figure"),
        Input("m16-tabs", "value"),
    )
    def update_bcom(tab):
        if tab != "tab-3":
            return go.Figure()
        data = _load_json("commodity_supercycle.json")
        annual = data.get("bcom_index_annual", {})
        if not annual:
            return go.Figure()

        years = sorted([int(y) for y in annual.keys()])
        values = [annual[str(y)] for y in years]

        # Divide en histórico y proyección (2024 en adelante)
        hist_years = [y for y in years if y <= 2023]
        hist_vals = [annual[str(y)] for y in hist_years]
        proj_years = [y for y in years if y >= 2023]
        proj_vals = [annual[str(y)] for y in proj_years]

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=hist_years, y=hist_vals,
            mode="lines+markers",
            name="BCOM Histórico",
            line=dict(color=COLORS["accent"], width=2.5),
            marker=dict(size=5),
            fill="tozeroy",
            fillcolor=_rgba(COLORS["accent"], 0.08),
        ))
        fig.add_trace(go.Scatter(
            x=proj_years, y=proj_vals,
            mode="lines+markers",
            name="Proyección",
            line=dict(color=COLORS["yellow"], width=2, dash="dot"),
            marker=dict(size=6, symbol="circle-open"),
        ))

        layout = get_base_layout(height=290)
        layout.update(
            margin=dict(l=55, r=15, t=40, b=40),
            yaxis_title="Índice (2000=100)",
            legend=dict(orientation="h", y=1.12, x=0),
            shapes=[
                dict(type="line", x0=2022, x1=2022, y0=0, y1=1,
                     xref="x", yref="paper",
                     line=dict(color=COLORS["red"], width=1, dash="dot")),
            ],
            annotations=[
                dict(x=2022, y=0.95, xref="x", yref="paper",
                     text="Guerra Ucrania", showarrow=False,
                     font=dict(size=9, color=COLORS["red"])),
            ],
        )
        fig.update_layout(layout)
        return fig

    @app.callback(
        Output("m16-futures-curve-chart", "figure"),
        Output("m16-futures-note", "children"),
        Input("m16-tabs", "value"),
        Input("m16-commodity-select", "value"),
    )
    def update_futures_curve(tab, commodity):
        if tab != "tab-3":
            return go.Figure(), html.Div()
        data = _load_json("futures_curves.json")
        comm_data = data.get("commodities", {}).get(commodity, {})
        if not comm_data:
            return go.Figure(), html.Div()

        tenors = ["Spot", "1 Mes", "3 Meses", "6 Meses", "12 Meses"]
        tenor_keys = ["spot", "1m_future", "3m_future", "6m_future", "12m_future"]
        prices = [comm_data.get(k, 0) for k in tenor_keys]
        structure = comm_data.get("structure", "contango")
        color = COLORS["red"] if structure == "backwardation" else COLORS["green"]
        label = _COMMODITY_LABELS.get(commodity, commodity)

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=tenors, y=prices,
            mode="lines+markers",
            name=label,
            line=dict(color=color, width=2.5),
            marker=dict(size=8),
            fill="tozeroy",
            fillcolor=_rgba(color, 0.08),
        ))
        layout = get_base_layout(height=270)
        layout.update(margin=dict(l=55, r=15, t=40, b=40), yaxis_title="Precio USD")
        fig.update_layout(layout)

        note = html.Div([
            html.Span(f"Estructura: ", style={"fontSize": "0.8rem", "color": COLORS["text_muted"]}),
            html.Span(structure.upper(), style={
                "fontSize": "0.8rem", "fontWeight": "700", "color": color,
                "marginRight": "8px",
            }),
            html.Span(comm_data.get("note", ""), style={
                "fontSize": "0.78rem", "color": COLORS["text_muted"],
            }),
        ])
        return fig, note

    @app.callback(
        Output("m16-market-structure-chart", "figure"),
        Input("m16-tabs", "value"),
    )
    def update_market_structure(tab):
        if tab != "tab-3":
            return go.Figure()
        data = _load_json("futures_curves.json")
        commodities = data.get("commodities", {})

        labels = [_COMMODITY_LABELS.get(k, k) for k in commodities.keys()]
        # Calcular "slope" 12m vs spot
        slopes = []
        colors = []
        for comm_data in commodities.values():
            spot = comm_data.get("spot", 1)
            fut12 = comm_data.get("12m_future", spot)
            pct_diff = ((fut12 - spot) / spot) * 100
            slopes.append(pct_diff)
            colors.append(COLORS["green"] if pct_diff > 0 else COLORS["red"])

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=labels, y=slopes,
            marker_color=colors,
            text=[f"{s:+.1f}%" for s in slopes],
            textposition="outside",
        ))
        fig.add_hline(y=0, line_color=COLORS["border"], line_width=1)
        layout = get_base_layout(height=270)
        layout.update(
            margin=dict(l=55, r=15, t=40, b=60),
            yaxis_title="Diferencia Futuro 12M vs Spot (%)",
            xaxis_tickangle=-15,
        )
        fig.update_layout(layout)
        return fig

    # ── TAB 4 callbacks ────────────────────────────────────────────────────────

    @app.callback(
        Output("m16-dxy-chart", "figure"),
        Input("m16-tabs", "value"),
    )
    def update_dxy(tab):
        if tab != "tab-4":
            return go.Figure()

        series = get_series("yahoo_DX-Y.NYB_close", limit=500)
        if series is not None and len(series) > 5:
            dates = [r[0] for r in series]
            values = [r[1] for r in series]
        else:
            # Fallback estático
            dates = [f"202{y}-{m:02d}" for y in range(4, 7) for m in range(1, 13)][:30]
            values = [
                101.5, 102.3, 103.8, 104.2, 103.1, 102.5,
                101.8, 100.9, 102.1, 103.5, 104.8, 105.2,
                104.5, 103.8, 102.9, 101.5, 100.2, 99.8,
                101.1, 102.3, 103.2, 104.5, 105.8, 106.2,
                107.1, 108.2, 106.8, 105.5, 104.2, 103.1,
            ]

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=dates, y=values,
            mode="lines",
            name="DXY",
            line=dict(color=COLORS["accent"], width=2),
            fill="tozeroy",
            fillcolor=_rgba(COLORS["accent"], 0.06),
        ))
        layout = get_base_layout(height=270)
        layout.update(margin=dict(l=55, r=15, t=40, b=40), yaxis_title="Índice DXY")
        fig.update_layout(layout)
        return fig

    @app.callback(
        Output("m16-carry-differential-chart", "figure"),
        Input("m16-tabs", "value"),
    )
    def update_carry_differential(tab):
        if tab != "tab-4":
            return go.Figure()
        data = _load_json("carry_trade_monitor.json")
        pairs = data.get("pairs", [])
        labels = [f"{p['fund_currency']}/{p['invest_currency']}" for p in pairs]
        differentials = [p.get("rate_differential_pct", 0) for p in pairs]
        risk_colors_map = {
            "low": COLORS["green"], "medium": COLORS["yellow"],
            "high": COLORS["red"], "very_high": "#ef4444",
        }
        colors = [risk_colors_map.get(p.get("reversal_risk", "medium"), COLORS["yellow"]) for p in pairs]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=labels, y=differentials,
            marker_color=colors,
            text=[f"{d:.1f}%" for d in differentials],
            textposition="outside",
        ))
        layout = get_base_layout(height=250)
        layout.update(margin=dict(l=55, r=15, t=40, b=40), yaxis_title="Diferencial Tipos %")
        fig.update_layout(layout)
        return fig

    @app.callback(
        Output("m16-carry-risk-chart", "figure"),
        Input("m16-tabs", "value"),
    )
    def update_carry_risk(tab):
        if tab != "tab-4":
            return go.Figure()
        data = _load_json("carry_trade_monitor.json")
        pairs = data.get("pairs", [])
        labels = [f"{p['fund_currency']}/{p['invest_currency']}" for p in pairs]
        risk_map = {"low": 1, "medium": 2, "high": 3, "very_high": 4}
        risk_colors_map = {
            "low": COLORS["green"], "medium": COLORS["yellow"],
            "high": COLORS["red"], "very_high": "#ef4444",
        }
        risks = [risk_map.get(p.get("reversal_risk", "medium"), 2) for p in pairs]
        colors = [risk_colors_map.get(p.get("reversal_risk", "medium"), COLORS["yellow"]) for p in pairs]
        risk_labels_map = {1: "Bajo", 2: "Medio", 3: "Alto", 4: "Muy Alto"}
        tick_text = ["Bajo", "Medio", "Alto", "Muy Alto"]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=labels, y=risks,
            marker_color=colors,
            text=[risk_labels_map.get(r, "") for r in risks],
            textposition="outside",
        ))
        layout = get_base_layout(height=250)
        layout.update(
            margin=dict(l=55, r=15, t=40, b=40),
            yaxis=dict(tickvals=[1, 2, 3, 4], ticktext=tick_text, title="Riesgo Reversión"),
        )
        fig.update_layout(layout)
        return fig

    @app.callback(
        Output("m16-fx-table", "children"),
        Input("m16-tabs", "value"),
    )
    def update_fx_table(tab):
        if tab != "tab-4":
            return html.Div()
        # Datos FX estáticos
        fx_data = [
            {"pair": "EUR/USD", "rate": 1.082, "change_1d": 0.12, "note": "BCE más dovish que Fed"},
            {"pair": "USD/JPY", "rate": 149.8, "change_1d": -0.22, "note": "BoJ en proceso normalización"},
            {"pair": "GBP/USD", "rate": 1.261, "change_1d": 0.05, "note": "Economía UK estabilizándose"},
            {"pair": "USD/CNY", "rate": 7.23,  "change_1d": 0.01,  "note": "PBOC fijación diaria"},
            {"pair": "USD/CHF", "rate": 0.892, "change_1d": -0.08, "note": "Franco refugio en tensión"},
            {"pair": "USD/BRL", "rate": 5.12,  "change_1d": 0.35,  "note": "Riesgo fiscal Brasil"},
            {"pair": "USD/MXN", "rate": 17.42, "change_1d": 0.18,  "note": "Nearshoring positivo para MXN"},
        ]
        rows = []
        for fx in fx_data:
            chg = fx["change_1d"]
            chg_color = COLORS["green"] if chg >= 0 else COLORS["red"]
            rows.append(html.Tr([
                html.Td(fx["pair"], style={"fontWeight": "600", "color": COLORS["accent"],
                                           "padding": "7px 8px"}),
                html.Td(f"{fx['rate']:.3f}", style={"color": COLORS["text"], "padding": "7px 8px"}),
                html.Td(f"{chg:+.2f}%", style={"color": chg_color, "fontWeight": "600",
                                                 "padding": "7px 8px"}),
                html.Td(fx["note"], style={"fontSize": "0.75rem", "color": COLORS["text_muted"],
                                           "padding": "7px 8px"}),
            ]))

        header = html.Thead(html.Tr([
            html.Th(h, style={"padding": "7px 8px", "color": COLORS["text_muted"],
                              "fontWeight": "600", "fontSize": "0.75rem",
                              "borderBottom": f"1px solid {COLORS['border']}"})
            for h in ["Par", "Tipo", "Var. 1D", "Contexto"]
        ]))
        return html.Table([header, html.Tbody(rows)],
                          style={"width": "100%", "borderCollapse": "collapse",
                                 "backgroundColor": COLORS["bg"], "borderRadius": "6px"})

    # ── TAB 5 callbacks ────────────────────────────────────────────────────────

    @app.callback(
        Output("m16-housing-chart", "figure"),
        Input("m16-tabs", "value"),
        Input("m16-housing-metric", "value"),
    )
    def update_housing(tab, metric):
        if tab != "tab-5":
            return go.Figure()
        data = _load_json("global_housing.json")
        markets = data.get("markets", {})
        if not markets:
            return go.Figure()

        country_names = {
            "USA": "EE.UU.", "ESP": "España", "DEU": "Alemania",
            "GBR": "Reino Unido", "AUS": "Australia",
            "CHN": "China", "CAN": "Canadá", "NLD": "Países Bajos",
        }
        metric_labels = {
            "price_to_income": "Precio / Ingresos (×)",
            "price_to_rent": "Precio / Alquiler (×)",
            "price_yoy_pct": "Variación Precio YoY (%)",
            "mortgage_rate_pct": "Tipo Hipotecario (%)",
        }
        trend_colors = {"rising": COLORS["red"], "stable": COLORS["yellow"], "falling": COLORS["green"]}

        countries = list(markets.keys())
        names = [country_names.get(c, c) for c in countries]
        values = [markets[c].get(metric, 0) for c in countries]
        trends = [markets[c].get("trend", "stable") for c in countries]
        colors = [trend_colors.get(t, COLORS["text_muted"]) for t in trends]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=names, y=values,
            marker_color=colors,
            text=[f"{v:.1f}" for v in values],
            textposition="outside",
        ))

        if metric == "price_yoy_pct":
            fig.add_hline(y=0, line_color=COLORS["border"], line_width=1)

        label = metric_labels.get(metric, metric)
        layout = get_base_layout(height=290)
        layout.update(margin=dict(l=55, r=15, t=40, b=40), yaxis_title=label)
        fig.update_layout(layout)
        return fig

    @app.callback(
        Output("m16-cre-vacancy-chart", "figure"),
        Input("m16-tabs", "value"),
    )
    def update_cre_vacancy(tab):
        if tab != "tab-5":
            return go.Figure()
        data = _load_json("commercial_real_estate.json")
        cities = data.get("cities_worst_vacancy", [])
        if not cities:
            return go.Figure()

        names = [c["city"] for c in cities]
        vacancies = [c["vacancy_pct"] for c in cities]
        colors = [
            COLORS["red"] if v > 30 else COLORS["yellow"] if v > 20 else COLORS["green"]
            for v in vacancies
        ]

        # Add logistics comparison
        logistics_vac = data.get("logistics_vacancy_pct", 6.2)
        names.append("Logística (ref.)")
        vacancies.append(logistics_vac)
        colors.append(COLORS["green"])

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=names, y=vacancies,
            marker_color=colors,
            text=[f"{v:.1f}%" for v in vacancies],
            textposition="outside",
        ))
        fig.add_hline(y=data.get("us_office_vacancy_rate_pct", 19.8),
                      line_dash="dot", line_color=COLORS["text_muted"],
                      annotation_text="Media EE.UU. Oficinas",
                      annotation_font_color=COLORS["text_muted"])

        layout = get_base_layout(height=270)
        layout.update(margin=dict(l=55, r=15, t=40, b=40), yaxis_title="Tasa Vacancia (%)")
        fig.update_layout(layout)
        return fig

    @app.callback(
        Output("m16-cre-exposure-chart", "figure"),
        Input("m16-tabs", "value"),
    )
    def update_cre_exposure(tab):
        if tab != "tab-5":
            return go.Figure()
        data = _load_json("commercial_real_estate.json")

        categories = [
            "Exposición Bancos EE.UU.\n(total CRE)",
            "Vencimientos 2026-27",
            "Pequeños Bancos\n(% préstamos CRE)",
        ]
        values_bn = [
            data.get("us_bank_cre_exposure_bn", 2800),
            data.get("cre_loan_maturities_2026_2027_bn", 950),
            data.get("us_small_banks_cre_pct_of_total_loans", 28.7),
        ]
        # Only chart the first two as $B, add annotation for the third
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=["Exposición Bancos EE.UU. ($B)", "Vencimientos 2026-27 ($B)"],
            y=[values_bn[0], values_bn[1]],
            marker_color=[COLORS["red"], COLORS["yellow"]],
            text=[f"${v:,.0f}B" for v in values_bn[:2]],
            textposition="outside",
        ))
        fig.add_annotation(
            x=0.5, y=0.9, xref="paper", yref="paper",
            text=f"Pequeños bancos: {values_bn[2]:.1f}% de su cartera en CRE",
            showarrow=False,
            font=dict(size=11, color=COLORS["yellow"]),
            bgcolor=_rgba(COLORS["yellow"], 0.1),
            bordercolor=COLORS["yellow"],
            borderwidth=1,
        )
        layout = get_base_layout(height=270)
        layout.update(margin=dict(l=55, r=15, t=40, b=40), yaxis_title="USD Billions")
        fig.update_layout(layout)
        return fig

    # ── TAB 6 callbacks ────────────────────────────────────────────────────────

    @app.callback(
        Output("m16-btc-mvrv-chart", "figure"),
        Input("m16-tabs", "value"),
    )
    def update_btc_mvrv(tab):
        if tab != "tab-6":
            return go.Figure()
        data = _load_json("bitcoin_onchain.json")
        mvrv = data.get("mvrv_ratio", 1.6)
        price = data.get("current_price_usd", 84320)
        realized = data.get("realized_price_usd", 52800)
        stf_price = data.get("stock_to_flow_model_price", 98000)

        # Gauge-style bar chart for MVRV
        mvrv_zones = [
            {"label": "Infravalorado (<1)", "min": 0, "max": 1.0, "color": COLORS["green"]},
            {"label": "Neutral (1–2)", "min": 1.0, "max": 2.0, "color": COLORS["yellow"]},
            {"label": "Euforia (2–3.5)", "min": 2.0, "max": 3.5, "color": "#f97316"},
            {"label": "Sobrecomprado (>3.5)", "min": 3.5, "max": 5.0, "color": COLORS["red"]},
        ]

        # Price comparison bar chart
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=["Precio Actual", "Precio Realizado", "Modelo S2F"],
            y=[price, realized, stf_price],
            marker_color=[COLORS["accent"], COLORS["text_muted"], COLORS["yellow"]],
            text=[f"${v:,.0f}" for v in [price, realized, stf_price]],
            textposition="outside",
        ))

        mvrv_color = COLORS["yellow"]
        if mvrv < 1:
            mvrv_color = COLORS["green"]
        elif mvrv > 2:
            mvrv_color = COLORS["red"]

        fig.add_annotation(
            x=0.5, y=0.95, xref="paper", yref="paper",
            text=f"MVRV = {mvrv:.2f} → Zona Neutral",
            showarrow=False,
            font=dict(size=12, color=mvrv_color),
            bgcolor=_rgba(mvrv_color, 0.1),
            bordercolor=mvrv_color,
            borderwidth=1,
        )

        layout = get_base_layout(height=270)
        layout.update(margin=dict(l=55, r=15, t=40, b=40), yaxis_title="USD")
        fig.update_layout(layout)
        return fig

    @app.callback(
        Output("m16-btc-supply-chart", "figure"),
        Output("m16-btc-metrics-cards", "children"),
        Input("m16-tabs", "value"),
    )
    def update_btc_supply(tab):
        if tab != "tab-6":
            return go.Figure(), html.Div()
        data = _load_json("bitcoin_onchain.json")
        lth_pct = data.get("long_term_holder_supply_pct", 74.3)
        sth_pct = data.get("short_term_holder_supply_pct", 25.7)

        fig = go.Figure()
        fig.add_trace(go.Pie(
            labels=["Holders Largo Plazo", "Holders Corto Plazo"],
            values=[lth_pct, sth_pct],
            hole=0.55,
            marker_colors=[COLORS["green"], COLORS["yellow"]],
            textinfo="label+percent",
            textfont=dict(size=11),
        ))
        fig.update_layout(
            get_base_layout(height=270),
            margin=dict(l=20, r=20, t=40, b=20),
            showlegend=False,
            annotations=[dict(
                text=f"LTH<br>{lth_pct:.1f}%",
                x=0.5, y=0.5, font_size=14,
                font_color=COLORS["green"],
                showarrow=False,
            )],
        )

        # Metrics row
        hash_rate = data.get("hash_rate_eh_s", 782)
        active_addr = data.get("active_addresses_7d_avg", 925000)
        exchange_res = data.get("exchange_reserves_btc", 2180000)
        days_halving = data.get("days_since_last_halving", 335)

        metrics_cards = dbc.Row([
            dbc.Col(_metric_card("Hash Rate", f"{hash_rate:,.0f} EH/s",
                                 "Seguridad de la red", COLORS["accent"]), width=3),
            dbc.Col(_metric_card("Dirs. Activas 7D", f"{active_addr:,.0f}",
                                 "Demanda on-chain"), width=3),
            dbc.Col(_metric_card("Reservas en Exchanges", f"{exchange_res:,.0f} BTC",
                                 "↓ = alcista (cold wallets)", COLORS["green"]), width=3),
            dbc.Col(_metric_card("Días desde Halving", f"{days_halving}",
                                 "Próximo: abr 2028"), width=3),
        ], className="g-2")

        return fig, metrics_cards

    @app.callback(
        Output("m16-btc-etf-chart", "figure"),
        Input("m16-tabs", "value"),
    )
    def update_btc_etf(tab):
        if tab != "tab-6":
            return go.Figure()
        data = _load_json("bitcoin_institutional.json")
        etfs = data.get("top_etf_holders", [])
        if not etfs:
            return go.Figure()

        names = [e["name"] for e in etfs]
        btc_held = [e["btc_held"] for e in etfs]
        aum = [e["aum_bn"] for e in etfs]

        etf_colors = [COLORS["accent"], "#10b981", "#f59e0b", "#ec4899", "#8b5cf6"]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=names, y=btc_held,
            marker_color=etf_colors[:len(names)],
            text=[f"{b:,.0f} BTC" for b in btc_held],
            textposition="outside",
            name="BTC Mantenidos",
        ))

        layout = get_base_layout(height=270)
        layout.update(
            margin=dict(l=55, r=15, t=40, b=70),
            yaxis_title="BTC Mantenidos",
            xaxis_tickangle=-20,
        )
        fig.update_layout(layout)
        return fig

    @app.callback(
        Output("m16-btc-treasury-chart", "figure"),
        Input("m16-tabs", "value"),
    )
    def update_btc_treasury(tab):
        if tab != "tab-6":
            return go.Figure()
        data = _load_json("bitcoin_institutional.json")
        treasuries = data.get("corporate_treasuries_btc", [])
        if not treasuries:
            return go.Figure()

        companies = [t["company"] for t in treasuries]
        btc_held = [t["btc_held"] for t in treasuries]
        avg_costs = [t["avg_cost_usd"] for t in treasuries]

        # Current BTC price
        onchain = _load_json("bitcoin_onchain.json")
        current_price = onchain.get("current_price_usd", 84320)

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=companies, y=btc_held,
            marker_color=[COLORS["accent"], COLORS["yellow"], COLORS["green"]],
            text=[f"{b:,.0f}" for b in btc_held],
            textposition="outside",
            name="BTC en Tesorería",
        ))
        # Add cost basis markers
        for i, (comp, btc, cost) in enumerate(zip(companies, btc_held, avg_costs)):
            pnl_pct = ((current_price - cost) / cost) * 100
            pnl_color = COLORS["green"] if pnl_pct >= 0 else COLORS["red"]
            fig.add_annotation(
                x=comp, y=btc * 0.5,
                text=f"Cost: ${cost:,.0f}<br>P&L: {pnl_pct:+.0f}%",
                showarrow=False,
                font=dict(size=9, color=pnl_color),
                bgcolor=_rgba(pnl_color, 0.15),
            )

        layout = get_base_layout(height=270)
        layout.update(margin=dict(l=55, r=15, t=40, b=40), yaxis_title="BTC en Tesorería")
        fig.update_layout(layout)
        return fig
