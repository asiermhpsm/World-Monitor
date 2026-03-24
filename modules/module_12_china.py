"""
Módulo 12 — China Panel Especial
Segunda economía del mundo: datos oficiales vs. indicadores alternativos,
deflación, crisis inmobiliaria, comercio, Taiwán y proyecciones globales.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import dash_bootstrap_components as dbc
import plotly.graph_objs as go
from dash import Input, Output, State, ctx, dcc, html, no_update

from components.chart_config import COLORS as C, get_base_layout, get_time_range_buttons
from config import COLORS
from modules.data_helpers import (
    get_latest_value,
    get_series,
    get_change,
    load_json_data,
)

# ── Constantes ─────────────────────────────────────────────────────────────────

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# ── Datos estáticos de fallback (cuando la BD no tiene la serie) ───────────────

_CHINA_CPI_STATIC = {
    2010: 3.3, 2011: 5.4, 2012: 2.6, 2013: 2.6, 2014: 2.0,
    2015: 1.4, 2016: 2.0, 2017: 1.6, 2018: 2.1, 2019: 2.9,
    2020: 2.5, 2021: 0.9, 2022: 2.0, 2023: 0.2, 2024: 0.3,
}

_CHINA_GDP_STATIC = {
    2005: 11.4, 2006: 12.7, 2007: 14.2, 2008: 9.7, 2009: 9.4,
    2010: 10.6, 2011: 9.5, 2012: 7.9, 2013: 7.8, 2014: 7.3,
    2015: 6.9, 2016: 6.7, 2017: 6.9, 2018: 6.7, 2019: 6.0,
    2020: 2.2, 2021: 8.5, 2022: 3.0, 2023: 5.2, 2024: 5.0,
}

_INDIA_GDP_STATIC = {
    2005: 9.3, 2006: 9.3, 2007: 9.8, 2008: 3.9, 2009: 8.4,
    2010: 8.5, 2011: 6.6, 2012: 5.5, 2013: 6.4, 2014: 7.4,
    2015: 8.0, 2016: 8.3, 2017: 6.8, 2018: 6.5, 2019: 3.7,
    2020: -5.8, 2021: 8.7, 2022: 7.2, 2023: 8.2, 2024: 6.8,
}

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


def _tension_color(level: str) -> str:
    return {
        "low": COLORS["green"],
        "medium": COLORS["yellow"],
        "high": COLORS["orange"],
        "critical": COLORS["red"],
    }.get(level, COLORS["text_muted"])


def _tension_label(level: str) -> str:
    return {
        "low": "BAJO",
        "medium": "MEDIO",
        "high": "ALTO",
        "critical": "CRÍTICO",
    }.get(level, "DESCONOCIDO")


# ── Header del módulo ──────────────────────────────────────────────────────────

def _build_header() -> html.Div:
    # PIB China
    gdp_val, gdp_ts = get_latest_value("wb_gdp_growth_chn")
    gdp_str = _safe(gdp_val, ".1f") + "%" if gdp_val is not None else "—"

    # CPI China
    cpi_val, cpi_ts = get_latest_value("wb_cpi_chn")
    cpi_str = _safe(cpi_val, ".1f") + "%" if cpi_val is not None else "—"
    cpi_color = COLORS["red"] if (cpi_val is not None and cpi_val < 0) else COLORS["green"]

    # Yuan/USD
    cny_val, cny_ts = get_latest_value("yf_cny_usd_close")
    cny_str = _safe(cny_val, ".4f") if cny_val is not None else "—"

    # Reservas divisas (en billones)
    res_val, res_ts = get_latest_value("wb_fx_reserves_chn")
    if res_val is not None:
        res_str = f"{res_val / 1e12:.2f}B USD"
    else:
        res_str = "~3.2B USD"  # fallback estático

    # Shanghai Composite
    sh_val, sh_ts = get_latest_value("yf_000001ss_close")
    sh_chg, sh_pct = None, None
    if sh_val is not None:
        _, sh_prev, _, sh_pct_raw = get_change("yf_000001ss_close")
        sh_pct = sh_pct_raw
    sh_str = f"{sh_val:,.0f}" if sh_val is not None else "—"
    sh_sub = (f"{sh_pct:+.2f}%" if sh_pct is not None else "")

    # GPR China
    gpr_val, gpr_ts = get_latest_value("gpr_china")
    gpr_str = _safe(gpr_val, ".0f") if gpr_val is not None else "—"
    gpr_color = COLORS["red"] if (gpr_val is not None and gpr_val > 200) else COLORS["text"]

    # Badges
    badges = []
    if cpi_val is not None and cpi_val < 0:
        badges.append(_badge("⚠️ DEFLACIÓN — China en territorio deflacionario", COLORS["red"]))
    if gpr_val is not None and gpr_val > 200:
        badges.append(_badge("🔴 RIESGO ELEVADO ASIA-PACÍFICO", COLORS["orange"]))

    return html.Div([
        # Título
        html.Div([
            html.Div([
                html.H2("🇨🇳 China — Panel Especial",
                        style={"margin": 0, "fontSize": "1.4rem", "color": COLORS["text"]}),
                html.Div("Segunda economía del mundo — Datos oficiales vs. indicadores alternativos",
                         style={"color": COLORS["text_muted"], "fontSize": "0.83rem", "marginTop": "4px"}),
            ]),
            html.Div(badges, style={"display": "flex", "alignItems": "center", "flexWrap": "wrap", "gap": "8px"}),
        ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "flex-start",
                  "marginBottom": "16px", "flexWrap": "wrap", "gap": "12px"}),

        # 6 métricas
        dbc.Row([
            dbc.Col(_metric_card("PIB China (crecim.)", gdp_str, "World Bank, último año"), width=2),
            dbc.Col(_metric_card("CPI China", cpi_str, "Vigilar deflación", cpi_color), width=2),
            dbc.Col(_metric_card("Yuan / USD", cny_str, "CNY=X"), width=2),
            dbc.Col(_metric_card("Reservas Divisas", res_str, "World Bank FI.RES.TOTL.CD"), width=2),
            dbc.Col(_metric_card("Shanghai Comp.", sh_str, sh_sub or "000001.SS"), width=2),
            dbc.Col(_metric_card("GPR China", gpr_str, "Riesgo geopolítico", gpr_color), width=2),
        ], className="g-2"),
    ], style={
        "backgroundColor": COLORS["card_bg"],
        "border": f"1px solid {COLORS['border']}",
        "borderRadius": "10px",
        "padding": "20px",
        "marginBottom": "20px",
    })


# ── TAB 1: Economía Real ───────────────────────────────────────────────────────

def _build_tab1() -> html.Div:
    return html.Div([
        # 1.1 — Problema datos chinos
        html.Div([
            html.Div("1.1 — El Problema de los Datos Chinos", style={
                "fontSize": "1rem", "fontWeight": "600", "color": COLORS["text"],
                "marginBottom": "10px",
            }),
            html.Div([
                "Los datos del PIB chino son publicados por la Oficina Nacional de Estadísticas (NBS) con un historial de revisiones muy limitadas y sospechosamente suaves. ",
                html.Strong("El índice de Li Keqiang"),
                " (propuesto por el propio ex-primer ministro Li Keqiang en un cable diplomático filtrado por WikiLeaks en 2007) combina consumo de electricidad, volumen de carga ferroviaria y préstamos bancarios como alternativa más fiable al PIB oficial. ",
                "Este módulo muestra ambas fuentes para que el usuario pueda juzgar la divergencia.",
            ], style=_INFO_BOX),
        ], style=_CARD),

        # 1.2 — PIB Oficial vs Li Keqiang
        html.Div([
            html.Div("1.2 — PIB Oficial vs. Índice Li Keqiang (Proxy)", style={
                "fontSize": "1rem", "fontWeight": "600", "color": COLORS["text"],
                "marginBottom": "12px",
            }),
            dcc.Loading(
                dcc.Graph(id="m12-gdp-li-keqiang-chart", config={"displayModeBar": False},
                          style={"height": "380px"}),
                color=COLORS["accent"],
            ),
            html.Div(
                "Una divergencia creciente entre el PIB oficial y los proxies alternativos puede indicar que el crecimiento real es menor que el reportado. "
                "En 2014-2016, varios analistas estimaron que el PIB real chino crecía 2-3pp menos que las cifras oficiales.",
                style={**_INFO_BOX, "marginTop": "10px"},
            ),
        ], style=_CARD),

        # 1.3 — Indicadores de actividad
        html.Div([
            html.Div("1.3 — Indicadores de Actividad en Tiempo Real", style={
                "fontSize": "1rem", "fontWeight": "600", "color": COLORS["text"],
                "marginBottom": "12px",
            }),
            dcc.Loading(html.Div(id="m12-activity-cards"), color=COLORS["accent"]),
        ], style=_CARD),

        # 1.4 — Composición PIB
        html.Div([
            html.Div("1.4 — Composición del PIB: Servicios vs Manufactura vs Agricultura", style={
                "fontSize": "1rem", "fontWeight": "600", "color": COLORS["text"],
                "marginBottom": "12px",
            }),
            dcc.Loading(
                dcc.Graph(id="m12-gdp-composition-chart", config={"displayModeBar": False},
                          style={"height": "380px"}),
                color=COLORS["accent"],
            ),
        ], style=_CARD),
    ], style={"padding": "4px 0"})


# ── TAB 2: Deflación e Inmobiliario ───────────────────────────────────────────

def _build_tab2() -> html.Div:
    return html.Div([
        # 2.1 — Trampa deflacionaria
        html.Div([
            html.Div("2.1 — La Trampa Deflacionaria", style={
                "fontSize": "1rem", "fontWeight": "600", "color": COLORS["text"],
                "marginBottom": "12px",
            }),
            dbc.Row([
                dbc.Col([
                    dcc.Loading(
                        dcc.Graph(id="m12-deflation-chart", config={"displayModeBar": False},
                                  style={"height": "340px"}),
                        color=COLORS["accent"],
                    ),
                ], width=8),
                dbc.Col([
                    html.Div([
                        html.Div("⚠️ Diagnóstico", style={
                            "fontWeight": "600", "color": COLORS["red"],
                            "marginBottom": "8px", "fontSize": "0.88rem",
                        }),
                        html.Div(
                            "China ha experimentado deflación en el PPI durante más de 20 meses consecutivos (2022-2024). "
                            "La deflación es peligrosa porque: (1) los consumidores posponen compras esperando precios más bajos, "
                            "(2) las empresas reducen inversión y empleo, (3) el valor real de la deuda aumenta, "
                            "(4) los márgenes empresariales se comprimen. "
                            "Es la trampa de liquidez japonesa aplicada a China.",
                            style={"fontSize": "0.8rem", "color": COLORS["text_muted"], "lineHeight": "1.7"},
                        ),
                    ], style={**_WARNING_BOX, "height": "100%"}),
                ], width=4),
            ]),
            html.Div("Comparativa con Japón: CPI chino actual vs. inicio de la 'Década Perdida' japonesa (años 90)",
                     style={"fontSize": "0.85rem", "color": COLORS["text_muted"], "marginTop": "12px", "marginBottom": "8px"}),
            dcc.Loading(
                dcc.Graph(id="m12-japan-comparison-chart", config={"displayModeBar": False},
                          style={"height": "280px"}),
                color=COLORS["accent"],
            ),
        ], style=_CARD),

        # 2.2 — Crisis inmobiliaria
        html.Div([
            html.Div("2.2 — La Crisis Inmobiliaria: El Mayor Riesgo Estructural de China", style={
                "fontSize": "1rem", "fontWeight": "600", "color": COLORS["text"],
                "marginBottom": "10px",
            }),
            html.Div(
                "El sector inmobiliario chino llegó a representar el 25-30% del PIB incluyendo toda la cadena de valor. "
                "La crisis de Evergrande en 2021 marcó el inicio del colapso. Desde entonces, más de 60 promotores han "
                "incumplido su deuda o entrado en reestructuración. El inventario de viviendas sin vender es el mayor de la historia china.",
                style=_WARNING_BOX,
            ),
            dbc.Row([
                dbc.Col([
                    dcc.Loading(
                        dcc.Graph(id="m12-realestate-sales-chart", config={"displayModeBar": False},
                                  style={"height": "300px"}),
                        color=COLORS["accent"],
                    ),
                ], width=6),
                dbc.Col([
                    dcc.Loading(
                        dcc.Graph(id="m12-realestate-inventory-chart", config={"displayModeBar": False},
                                  style={"height": "300px"}),
                        color=COLORS["accent"],
                    ),
                ], width=6),
            ]),
            html.Div("Principales impagos de promotores chinos", style={
                "fontWeight": "600", "fontSize": "0.88rem", "marginTop": "14px", "marginBottom": "8px",
                "color": COLORS["text"],
            }),
            dcc.Loading(html.Div(id="m12-developer-defaults-table"), color=COLORS["accent"]),
            html.Div(
                "El inventario de viviendas sin vender en China equivale a más de 18 meses de demanda al ritmo actual de ventas. "
                "Para absorberlo, China necesitaría que el mercado se detuviera totalmente durante más de año y medio.",
                style={**_INFO_BOX, "marginTop": "14px"},
            ),
        ], style=_CARD),

        # 2.3 — ¿Momento Lehman chino?
        html.Div([
            html.Div("2.3 — ¿Un Momento Lehman Chino?", style={
                "fontSize": "1rem", "fontWeight": "600", "color": COLORS["text"],
                "marginBottom": "12px",
            }),
            dbc.Row([
                dbc.Col([
                    html.Table([
                        html.Thead(html.Tr([
                            html.Th("Factor", style={"color": COLORS["text_muted"], "padding": "8px 12px",
                                                      "borderBottom": f"2px solid {COLORS['border']}",
                                                      "fontSize": "0.78rem", "textAlign": "left"}),
                            html.Th("EE.UU. 2006-2008", style={"color": "#60a5fa", "padding": "8px 12px",
                                                                 "borderBottom": f"2px solid {COLORS['border']}",
                                                                 "fontSize": "0.78rem"}),
                            html.Th("China 2021-presente", style={"color": COLORS["red"], "padding": "8px 12px",
                                                                    "borderBottom": f"2px solid {COLORS['border']}",
                                                                    "fontSize": "0.78rem"}),
                        ])),
                        html.Tbody([
                            _lehman_row("Inmobiliario como % PIB", "~18%", "25-30%"),
                            _lehman_row("Apalancamiento promotores", "Moderado", "Extremo"),
                            _lehman_row("Exposición bancaria", "Alta", "Muy alta"),
                            _lehman_row("Capacidad de intervención gubernamental", "Limitada (Fed)", "Muy alta (partido único)"),
                            _lehman_row("Velocidad contagio", "Rápida (mercados integrados)", "Contenida (control capitales)"),
                            _lehman_row("Riesgo sistémico global", "Muy alto (crisis 2008)", "Moderado-alto"),
                        ]),
                    ], style={
                        "width": "100%", "borderCollapse": "collapse",
                        "fontSize": "0.82rem", "color": COLORS["text"],
                    }),
                ], width=12),
            ]),
            html.Div(
                "China tiene las herramientas para evitar un colapso sistémico (control total del sistema bancario, "
                "capacidad de monetización, control de capitales) pero a costa de prolongar el ajuste durante años, "
                "al estilo japonés, en lugar de resolverlo con un crash rápido. La experiencia histórica sugiere que "
                "el camino japonés de ajuste lento es muy costoso en términos de crecimiento perdido.",
                style={**_INFO_BOX, "marginTop": "14px"},
            ),
        ], style=_CARD),
    ], style={"padding": "4px 0"})


def _lehman_row(factor: str, usa: str, china: str) -> html.Tr:
    return html.Tr([
        html.Td(factor, style={"padding": "8px 12px", "color": COLORS["text_muted"],
                                "borderBottom": f"1px solid {COLORS['border']}"}),
        html.Td(usa, style={"padding": "8px 12px", "color": "#93c5fd", "textAlign": "center",
                             "borderBottom": f"1px solid {COLORS['border']}"}),
        html.Td(china, style={"padding": "8px 12px", "color": "#fca5a5", "textAlign": "center",
                               "borderBottom": f"1px solid {COLORS['border']}"}),
    ])


# ── TAB 3: Comercio y Finanzas ─────────────────────────────────────────────────

def _build_tab3() -> html.Div:
    return html.Div([
        # 3.1 — Superávit comercial
        html.Div([
            html.Div("3.1 — El Superávit Comercial Récord", style={
                "fontSize": "1rem", "fontWeight": "600", "color": COLORS["text"],
                "marginBottom": "12px",
            }),
            dbc.Row([
                dbc.Col([
                    dcc.Loading(
                        dcc.Graph(id="m12-trade-balance-chart", config={"displayModeBar": False},
                                  style={"height": "280px"}),
                        color=COLORS["accent"],
                    ),
                ], width=7),
                dbc.Col([
                    dcc.Loading(
                        dcc.Graph(id="m12-exports-destination-chart", config={"displayModeBar": False},
                                  style={"height": "280px"}),
                        color=COLORS["accent"],
                    ),
                ], width=5),
            ]),
            dcc.Loading(
                dcc.Graph(id="m12-exports-products-chart", config={"displayModeBar": False},
                          style={"height": "260px", "marginTop": "8px"}),
                color=COLORS["accent"],
            ),
            html.Div(
                "El superávit comercial de China supera el 1 billón de dólares anuales — una cifra sin precedentes en la historia "
                "económica mundial. Esto refleja simultáneamente la competitividad exportadora china Y la debilidad del consumo "
                "interno. Este desequilibrio es una fuente persistente de tensiones comerciales globales.",
                style={**_INFO_BOX, "marginTop": "12px"},
            ),
        ], style=_CARD),

        # 3.2 — Reservas divisas
        html.Div([
            html.Div("3.2 — Reservas de Divisas: El Escudo Financiero", style={
                "fontSize": "1rem", "fontWeight": "600", "color": COLORS["text"],
                "marginBottom": "12px",
            }),
            dbc.Row([
                dbc.Col([
                    dcc.Loading(
                        dcc.Graph(id="m12-fx-reserves-chart", config={"displayModeBar": False},
                                  style={"height": "260px"}),
                        color=COLORS["accent"],
                    ),
                ], width=8),
                dbc.Col([
                    html.Div([
                        html.Div("🛡️ El Arma de Doble Filo", style={
                            "fontWeight": "600", "color": "#60a5fa",
                            "marginBottom": "8px", "fontSize": "0.88rem",
                        }),
                        html.Div(
                            "China mantiene aproximadamente 760.000 millones en bonos del Tesoro americano "
                            "(reducidos desde 1.3 billones en 2013). La amenaza implícita de vender masivamente "
                            "esos bonos es un arma geopolítica — pero su uso destruiría también el valor de las "
                            "reservas chinas restantes.",
                            style={"fontSize": "0.8rem", "color": COLORS["text_muted"], "lineHeight": "1.7"},
                        ),
                    ], style=_INFO_BOX),
                ], width=4),
            ]),
        ], style=_CARD),

        # 3.3 — Yuan
        html.Div([
            html.Div("3.3 — El Yuan: Entre el Control y la Internacionalización", style={
                "fontSize": "1rem", "fontWeight": "600", "color": COLORS["text"],
                "marginBottom": "12px",
            }),
            dcc.Loading(
                dcc.Graph(id="m12-yuan-chart", config={"displayModeBar": False},
                          style={"height": "260px"}),
                color=COLORS["accent"],
            ),
            html.Div(
                "El yuan tiene dos tipos de cambio: el CNY (onshore, controlado por el PBOC dentro de China) y el CNH "
                "(offshore, más libre, cotiza en Hong Kong). Cuando el CNH se debilita más que el CNY, indica que el "
                "mercado libre espera una depreciación que el gobierno chino está resistiendo.",
                style={**_INFO_BOX, "marginTop": "10px"},
            ),
            # Datos estáticos de internacionalización
            dbc.Row([
                dbc.Col(_metric_card("Yuan en reservas globales FMI", "~2.7%",
                                     "vs Dólar ~58%, Euro ~20%", COLORS["yellow"]), width=3),
                dbc.Col(_metric_card("Yuan en transacciones SWIFT", "~4.5%",
                                     "Creciente pero marginal", COLORS["yellow"]), width=3),
                dbc.Col(_metric_card("Posición FMI (SDR)", "10.9%",
                                     "Incluido en SDR desde 2016", COLORS["accent"]), width=3),
                dbc.Col(_metric_card("Bonos US Treasury en manos CN", "~760B USD",
                                     "Reducidos desde 1.3B en 2013", COLORS["text_muted"]), width=3),
            ], className="g-2", style={"marginTop": "10px"}),
        ], style=_CARD),

        # 3.4 — Flujos IED
        html.Div([
            html.Div("3.4 — Flujos de Inversión: El Capital que Sale", style={
                "fontSize": "1rem", "fontWeight": "600", "color": COLORS["text"],
                "marginBottom": "12px",
            }),
            dcc.Loading(
                dcc.Graph(id="m12-fdi-chart", config={"displayModeBar": False},
                          style={"height": "260px"}),
                color=COLORS["accent"],
            ),
            html.Div(
                "El concepto de 'China+1' — tener una segunda fábrica fuera de China para diversificar el riesgo — "
                "se ha convertido en política estándar de muchas multinacionales. Vietnam, India, México y Polonia son "
                "los principales beneficiarios.",
                style={**_INFO_BOX, "marginTop": "10px"},
            ),
        ], style=_CARD),
    ], style={"padding": "4px 0"})


# ── TAB 4: Taiwán y Geopolítica ────────────────────────────────────────────────

def _build_tab4() -> html.Div:
    taiwan = _load_json("taiwan_monitor.json")
    level = taiwan.get("tension_level", "medium")
    level_color = _tension_color(level)
    level_label = _tension_label(level)
    incidents = taiwan.get("recent_incidents", [])
    econ = taiwan.get("economic_interdependence", {})
    scenarios = taiwan.get("scenarios", [])

    # Semáforo de tensión
    semaphore = html.Div([
        html.Div([
            html.Div(style={
                "width": "64px", "height": "64px", "borderRadius": "50%",
                "backgroundColor": level_color,
                "boxShadow": f"0 0 30px {level_color}80",
                "margin": "0 auto 8px",
            }),
            html.Div(f"TENSIÓN: {level_label}", style={
                "color": level_color, "fontWeight": "700",
                "fontSize": "0.9rem", "textAlign": "center",
            }),
            html.Div(taiwan.get("tension_description", ""), style={
                "color": COLORS["text_muted"], "fontSize": "0.78rem",
                "textAlign": "center", "marginTop": "6px", "lineHeight": "1.5",
            }),
        ], style={"padding": "16px"}),
    ], style={
        "backgroundColor": _rgba(level_color, 0.08),
        "border": f"2px solid {level_color}",
        "borderRadius": "10px",
        "marginBottom": "16px",
    })

    # Incidentes recientes
    incident_items = []
    for inc in incidents:
        incident_items.append(html.Div([
            html.Span(inc.get("date", ""), style={
                "color": COLORS["accent"], "fontSize": "0.75rem",
                "minWidth": "90px", "display": "inline-block",
            }),
            html.Span(inc.get("description", ""), style={
                "color": COLORS["text_muted"], "fontSize": "0.8rem",
            }),
        ], style={"marginBottom": "6px", "display": "flex", "gap": "10px"}))

    # Tarjetas interdependencia
    econ_cards = dbc.Row([
        dbc.Col(_metric_card("Exportaciones Taiwán → China", f"{econ.get('taiwan_exports_to_china_pct', 25)}%",
                             "% total exportaciones", COLORS["yellow"]), width=4),
        dbc.Col(_metric_card("Cuota TSMC chips avanzados", f"{econ.get('tsmc_market_share_advanced_chips_pct', 90)}%",
                             "< 5 nanómetros", COLORS["red"]), width=4),
        dbc.Col(_metric_card("Ingresos semicond. mundiales", f"{econ.get('global_semiconductor_revenue_taiwan_pct', 22)}%",
                             "% global de Taiwán", COLORS["orange"]), width=4),
    ], className="g-2")

    # Escenarios
    scenario_color_map = {
        "green": (COLORS["green"], "#10b981"),
        "orange": (COLORS["orange"], "#f97316"),
        "red": (COLORS["red"], "#ef4444"),
    }
    scenario_cards = []
    for sc in scenarios:
        sc_col_key = sc.get("color", "green")
        sc_color, sc_border = scenario_color_map.get(sc_col_key, (COLORS["text_muted"], COLORS["text_muted"]))
        scenario_cards.append(dbc.Col(
            html.Div([
                html.Div([
                    html.Span(sc.get("name", ""), style={
                        "fontWeight": "700", "color": sc_color, "fontSize": "0.88rem",
                    }),
                    html.Span(f"{sc.get('probability_pct', 0)}%", style={
                        "backgroundColor": _rgba(sc_color, 0.2),
                        "color": sc_color,
                        "border": f"1px solid {sc_color}",
                        "borderRadius": "12px",
                        "padding": "1px 8px",
                        "fontSize": "0.75rem",
                        "marginLeft": "8px",
                    }),
                ], style={"marginBottom": "8px"}),
                html.Div(sc.get("description", ""), style={
                    "fontSize": "0.78rem", "color": COLORS["text_muted"], "marginBottom": "8px",
                }),
                html.Div("Impacto económico:", style={
                    "fontSize": "0.72rem", "color": COLORS["text_muted"],
                    "textTransform": "uppercase", "marginBottom": "3px",
                }),
                html.Div(sc.get("economic_impact", ""), style={
                    "fontSize": "0.78rem", "color": COLORS["text"], "marginBottom": "8px",
                }),
                html.Div("Activos:", style={
                    "fontSize": "0.72rem", "color": COLORS["text_muted"],
                    "textTransform": "uppercase", "marginBottom": "3px",
                }),
                html.Div(sc.get("assets", ""), style={
                    "fontSize": "0.78rem", "color": sc_color, "fontWeight": "600",
                }),
            ], style={
                "backgroundColor": _rgba(sc_color, 0.05),
                "border": f"1px solid {sc_color}",
                "borderRadius": "8px",
                "padding": "14px",
                "height": "100%",
            }),
            width=4,
        ))

    return html.Div([
        # 4.1 — Monitor del Estrecho
        html.Div([
            html.Div("4.1 — Monitor del Estrecho de Taiwán", style={
                "fontSize": "1rem", "fontWeight": "600", "color": COLORS["text"],
                "marginBottom": "12px",
            }),
            dbc.Row([
                dbc.Col([semaphore] + incident_items, width=5),
                dbc.Col([
                    html.Div("¿Por qué importa económicamente?", style={
                        "fontWeight": "600", "color": COLORS["text"],
                        "marginBottom": "8px", "fontSize": "0.88rem",
                    }),
                    html.Div(
                        "Taiwán produce el 90% de los semiconductores más avanzados del mundo (los de menos de 5 nanómetros). "
                        "Sin esos chips, no hay iPhones, servidores de IA, coches modernos ni equipos militares avanzados. "
                        "Una interrupción del suministro de semiconductores taiwaneses durante 6-12 meses causaría la mayor "
                        "recesión industrial desde la Segunda Guerra Mundial.",
                        style={"fontSize": "0.8rem", "color": COLORS["text_muted"], "lineHeight": "1.7",
                               "marginBottom": "14px"},
                    ),
                    econ_cards,
                ], width=7),
            ]),
        ], style=_CARD),

        # 4.2 — Escenarios
        html.Div([
            html.Div([
                html.Div("4.2 — Escenarios de Tensión China-Taiwán y su Impacto", style={
                    "fontSize": "1rem", "fontWeight": "600", "color": COLORS["text"],
                }),
                html.Div(
                    taiwan.get("diplomatic_status", ""),
                    style={"color": COLORS["text_muted"], "fontSize": "0.78rem", "marginTop": "4px"},
                ),
            ], style={"marginBottom": "14px"}),
            dbc.Row(scenario_cards, className="g-3"),
        ], style=_CARD),

        # 4.3 — Cadena de suministro semiconductores
        html.Div([
            html.Div("4.3 — La Cadena de Suministro de Semiconductores", style={
                "fontSize": "1rem", "fontWeight": "600", "color": COLORS["text"],
                "marginBottom": "12px",
            }),
            _semiconductor_chain(),
            html.Div(
                "EE.UU. diseña los chips más avanzados pero no los fabrica. Taiwán los fabrica pero no los diseña. "
                "China ensambla dispositivos pero no puede fabricar los chips más avanzados. Esta interdependencia es "
                "un arma de doble filo: todos tienen algo que perder en un conflicto.",
                style={**_INFO_BOX, "marginTop": "12px"},
            ),
            _chips_act_status(),
        ], style=_CARD),
    ], style={"padding": "4px 0"})


def _semiconductor_chain() -> html.Div:
    """Diagrama visual de la cadena de suministro de semiconductores."""
    nodes = [
        ("🇺🇸 EE.UU.", "Diseño", ["Intel", "Qualcomm", "NVIDIA", "AMD"], "#60a5fa"),
        ("🇹🇼 Taiwán", "Fabricación", ["TSMC (90% avanzados)", "UMC", "PSMC"], "#f97316"),
        ("🇨🇳 China / 🇻🇳 Vietnam", "Ensamblaje", ["Foxconn", "Pegatron", "Luxshare"], "#10b981"),
        ("🌍 Mercado Global", "Distribución", ["Consumo mundial"], "#9ca3af"),
    ]
    items = []
    for i, (country, role, companies, color) in enumerate(nodes):
        items.append(html.Div([
            html.Div(country, style={
                "fontWeight": "700", "color": color, "fontSize": "0.9rem", "marginBottom": "4px",
            }),
            html.Div(role, style={
                "fontSize": "0.7rem", "color": COLORS["text_muted"],
                "textTransform": "uppercase", "marginBottom": "6px",
            }),
            *[html.Div(f"• {c}", style={"fontSize": "0.75rem", "color": COLORS["text_muted"]})
              for c in companies],
        ], style={
            "backgroundColor": _rgba(color, 0.08),
            "border": f"1px solid {color}",
            "borderRadius": "8px",
            "padding": "12px",
            "flex": "1",
        }))
        if i < len(nodes) - 1:
            items.append(html.Div("→", style={
                "fontSize": "1.5rem", "color": COLORS["text_muted"],
                "display": "flex", "alignItems": "center", "padding": "0 8px",
            }))
    return html.Div(items, style={"display": "flex", "alignItems": "stretch", "gap": "4px"})


def _chips_act_status() -> html.Div:
    rows = [
        ("CHIPS Act (EE.UU.)", "2022", "52.7B USD", "Intel (Ohio), TSMC Arizona, Samsung Texas"),
        ("European Chips Act", "2023", "43B EUR", "TSMC Dresden, Intel Magdeburg"),
        ("Programa China (CXMT, SMIC)", "Continuo", ">150B USD (2025-2030)", "SMIC, CXMT, Yangtze Memory"),
        ("India Semiconductor Mission", "2021", "10B USD", "Tata Electronics, Micron Gujarat"),
    ]
    return html.Div([
        html.Div("Estado de los programas de soberanía semiconductora", style={
            "fontSize": "0.85rem", "fontWeight": "600", "color": COLORS["text"],
            "marginTop": "14px", "marginBottom": "8px",
        }),
        html.Table([
            html.Thead(html.Tr([
                html.Th(h, style={"padding": "6px 10px", "color": COLORS["text_muted"],
                                   "fontSize": "0.72rem", "borderBottom": f"1px solid {COLORS['border']}",
                                   "textAlign": "left"})
                for h in ["Programa", "Año", "Inversión", "Proyectos clave"]
            ])),
            html.Tbody([
                html.Tr([
                    html.Td(cell, style={"padding": "6px 10px", "color": COLORS["text"],
                                          "fontSize": "0.78rem",
                                          "borderBottom": f"1px solid {COLORS['border']}"})
                    for cell in row
                ]) for row in rows
            ]),
        ], style={"width": "100%", "borderCollapse": "collapse"}),
    ])


# ── TAB 5: China vs Mundo ──────────────────────────────────────────────────────

def _build_tab5() -> html.Div:
    return html.Div([
        # 5.1 — Competencia estratégica EE.UU. vs China
        html.Div([
            html.Div("5.1 — Competencia Estratégica EE.UU. vs China", style={
                "fontSize": "1rem", "fontWeight": "600", "color": COLORS["text"],
                "marginBottom": "12px",
            }),
            _usa_china_comparison_table(),
        ], style=_CARD),

        # 5.2 — China vs India
        html.Div([
            html.Div("5.2 — China vs India: El Relevo del Motor del Crecimiento", style={
                "fontSize": "1rem", "fontWeight": "600", "color": COLORS["text"],
                "marginBottom": "12px",
            }),
            dcc.Loading(
                dcc.Graph(id="m12-china-india-chart", config={"displayModeBar": False},
                          style={"height": "340px"}),
                color=COLORS["accent"],
            ),
            dbc.Row([
                dbc.Col([
                    html.Div("✅ Ventajas de India", style={
                        "fontWeight": "600", "color": COLORS["green"],
                        "marginBottom": "8px", "fontSize": "0.85rem",
                    }),
                    *[html.Div(f"• {v}", style={"fontSize": "0.78rem", "color": COLORS["text_muted"],
                                                  "marginBottom": "4px"})
                      for v in ["Demografía más joven", "Democracia (más atractiva para Occidente)",
                                "Mayor dominio del inglés", "Sector tecnológico maduro (software)",
                                "Reciente aceleración manufacturera"]],
                ], width=6, style={**_INFO_BOX, "margin": "10px 6px 0"}),
                dbc.Col([
                    html.Div("✅ Ventajas de China", style={
                        "fontWeight": "600", "color": "#60a5fa",
                        "marginBottom": "8px", "fontSize": "0.85rem",
                    }),
                    *[html.Div(f"• {v}", style={"fontSize": "0.78rem", "color": COLORS["text_muted"],
                                                  "marginBottom": "4px"})
                      for v in ["Infraestructura mucho más desarrollada", "Mayor manufactura acumulada",
                                "Más capital y reservas internacionales",
                                "Cohesión política para ejecutar planes",
                                "Mayor base industrial instalada"]],
                ], width=6, style={**_INFO_BOX, "margin": "10px 6px 0", "borderColor": "#60a5fa",
                                    "backgroundColor": "#1a2332"}),
            ]),
        ], style=_CARD),

        # 5.3 — Triángulo EE.UU.-China-Europa
        html.Div([
            html.Div("5.3 — El Triángulo EE.UU.-China-Europa", style={
                "fontSize": "1rem", "fontWeight": "600", "color": COLORS["text"],
                "marginBottom": "12px",
            }),
            dcc.Loading(html.Div(id="m12-triangle-table"), color=COLORS["accent"]),
        ], style=_CARD),

        # 5.4 — Proyecciones PIB 2050
        html.Div([
            html.Div("5.4 — Proyecciones de PIB Global a 2050", style={
                "fontSize": "1rem", "fontWeight": "600", "color": COLORS["text"],
                "marginBottom": "12px",
            }),
            dcc.Loading(
                dcc.Graph(id="m12-gdp2050-chart", config={"displayModeBar": False},
                          style={"height": "400px"}),
                color=COLORS["accent"],
            ),
            html.Div(
                "Las proyecciones de largo plazo muestran que India podría convertirse en la tercera mayor economía del mundo "
                "antes de 2040, superando a Japón y potencialmente a la Eurozona. China podría alcanzar a EE.UU. en PIB nominal "
                "alrededor de 2040-2045, aunque esto depende críticamente de resolver su crisis demográfica e inmobiliaria.",
                style={**_INFO_BOX, "marginTop": "12px"},
            ),
        ], style=_CARD),
    ], style={"padding": "4px 0"})


def _usa_china_comparison_table() -> html.Div:
    metrics = [
        ("PIB nominal (2025)", "~30.0B USD", "~19.0B USD", "usa"),
        ("PIB en PPP (2025)", "~30.0B USD", "~33.0B USD", "china"),
        ("Gasto en defensa", "~900B USD (3% PIB)", "~290B USD (1.5% PIB)", "usa"),
        ("Gasto en I+D (% PIB)", "~3.3%", "~2.6%", "usa"),
        ("Patentes anuales registradas", "~350,000", "~1,600,000", "china"),
        ("Universidades en top 100 mundial", "~50", "~8", "usa"),
        ("Emisiones CO₂ (Gt/año)", "~5.0", "~12.0", "china"),
        ("Reservas de divisas", "~0.1B USD", "~3.2B USD", "china"),
        ("Exportaciones (% mundial)", "~8.5%", "~14.5%", "china"),
        ("Empresas Fortune 500", "~136", "~135", "neutral"),
    ]

    rows = []
    for metric, usa_val, chn_val, leader in metrics:
        usa_style = {"padding": "7px 12px", "fontSize": "0.8rem", "textAlign": "center",
                      "borderBottom": f"1px solid {COLORS['border']}",
                      "color": "#93c5fd" if leader == "usa" else COLORS["text_muted"],
                      "fontWeight": "600" if leader == "usa" else "400"}
        chn_style = {"padding": "7px 12px", "fontSize": "0.8rem", "textAlign": "center",
                      "borderBottom": f"1px solid {COLORS['border']}",
                      "color": "#fca5a5" if leader == "china" else COLORS["text_muted"],
                      "fontWeight": "600" if leader == "china" else "400"}
        badge_col = html.Td(
            "🇺🇸 EE.UU." if leader == "usa" else ("🇨🇳 China" if leader == "china" else "—"),
            style={"padding": "7px 12px", "fontSize": "0.75rem", "textAlign": "center",
                   "borderBottom": f"1px solid {COLORS['border']}",
                   "color": "#93c5fd" if leader == "usa" else "#fca5a5"},
        )
        rows.append(html.Tr([
            html.Td(metric, style={"padding": "7px 12px", "color": COLORS["text_muted"],
                                    "fontSize": "0.8rem",
                                    "borderBottom": f"1px solid {COLORS['border']}"}),
            html.Td(usa_val, style=usa_style),
            html.Td(chn_val, style=chn_style),
            badge_col,
        ]))

    return html.Table([
        html.Thead(html.Tr([
            html.Th("Indicador", style={"padding": "8px 12px", "color": COLORS["text_muted"],
                                         "fontSize": "0.75rem", "borderBottom": f"2px solid {COLORS['border']}",
                                         "textAlign": "left"}),
            html.Th("🇺🇸 EE.UU.", style={"padding": "8px 12px", "color": "#60a5fa",
                                           "fontSize": "0.75rem", "borderBottom": f"2px solid {COLORS['border']}",
                                           "textAlign": "center"}),
            html.Th("🇨🇳 China", style={"padding": "8px 12px", "color": COLORS["red"],
                                          "fontSize": "0.75rem", "borderBottom": f"2px solid {COLORS['border']}",
                                          "textAlign": "center"}),
            html.Th("Líder", style={"padding": "8px 12px", "color": COLORS["text_muted"],
                                     "fontSize": "0.75rem", "borderBottom": f"2px solid {COLORS['border']}",
                                     "textAlign": "center"}),
        ])),
        html.Tbody(rows),
    ], style={"width": "100%", "borderCollapse": "collapse"})


# ── Render principal ───────────────────────────────────────────────────────────

def render_module_12() -> html.Div:
    return html.Div([
        # Header siempre visible
        html.Div(id="m12-header-container", children=_build_header()),

        # Intervalo de refresco
        dcc.Interval(id="m12-interval", interval=300_000, n_intervals=0),

        # Tabs
        dcc.Tabs(
            id="m12-tabs",
            value="tab-1",
            style=_TABS_CONTAINER,
            children=[
                dcc.Tab(label="📊 Economía Real", value="tab-1",
                        style=_TAB_STYLE, selected_style=_TAB_SELECTED),
                dcc.Tab(label="🏚️ Deflación e Inmobiliario", value="tab-2",
                        style=_TAB_STYLE, selected_style=_TAB_SELECTED),
                dcc.Tab(label="💹 Comercio y Finanzas", value="tab-3",
                        style=_TAB_STYLE, selected_style=_TAB_SELECTED),
                dcc.Tab(label="⚔️ Taiwán y Geopolítica", value="tab-4",
                        style=_TAB_STYLE, selected_style=_TAB_SELECTED),
                dcc.Tab(label="🌍 China vs Mundo", value="tab-5",
                        style=_TAB_STYLE, selected_style=_TAB_SELECTED),
            ],
        ),

        # Contenido de tabs
        html.Div(id="m12-tab-content", style={"padding": "20px 0"}),

    ], style={"padding": "16px 24px"})


# ── Callbacks ──────────────────────────────────────────────────────────────────

def register_callbacks_module_12(app) -> None:

    # ── Routing de tabs ────────────────────────────────────────────────────────
    @app.callback(
        Output("m12-tab-content", "children"),
        Input("m12-tabs", "value"),
    )
    def render_tab(tab):
        if tab == "tab-1":
            return _build_tab1()
        elif tab == "tab-2":
            return _build_tab2()
        elif tab == "tab-3":
            return _build_tab3()
        elif tab == "tab-4":
            return _build_tab4()
        elif tab == "tab-5":
            return _build_tab5()
        return html.Div()

    # ── Header refresh ────────────────────────────────────────────────────────
    @app.callback(
        Output("m12-header-container", "children"),
        Input("m12-interval", "n_intervals"),
    )
    def refresh_header(_n):
        return _build_header()

    # ── Tab 1: PIB oficial vs Li Keqiang ──────────────────────────────────────
    @app.callback(
        Output("m12-gdp-li-keqiang-chart", "figure"),
        Input("m12-tabs", "value"),
        Input("m12-interval", "n_intervals"),
    )
    def update_gdp_li_keqiang(tab, _n):
        if tab != "tab-1":
            return go.Figure()
        try:
            from modules.data_helpers import calculate_li_keqiang_proxy
        except ImportError:
            calculate_li_keqiang_proxy = None

        layout = get_base_layout()
        layout.update(
            title=dict(text="PIB Oficial vs. Índice Li Keqiang Proxy", font=dict(size=13)),
            xaxis_title="Año",
            yaxis_title="Variación YoY (%)",
            legend=dict(x=0.01, y=0.99),
            hovermode="x unified",
        )
        fig = go.Figure(layout=layout)

        import pandas as pd

        # PIB oficial — BD o fallback estático
        gdp_series = get_series("wb_gdp_growth_chn", days=6000)
        if gdp_series is not None and not gdp_series.empty:
            try:
                gdp_series["timestamp"] = pd.to_datetime(gdp_series["timestamp"])
            except Exception:
                pass
            fig.add_trace(go.Scatter(
                x=gdp_series["timestamp"], y=gdp_series["value"],
                name="PIB Oficial (World Bank)", mode="lines+markers",
                line=dict(color="#3b82f6", width=2),
                marker=dict(size=4),
                hovertemplate="%{y:.1f}%<extra>PIB Oficial</extra>",
            ))
        else:
            # Fallback estático
            gdp_years = sorted(_CHINA_GDP_STATIC.keys())
            gdp_vals = [_CHINA_GDP_STATIC[y] for y in gdp_years]
            fig.add_trace(go.Scatter(
                x=gdp_years, y=gdp_vals,
                name="PIB Oficial (estimación)", mode="lines+markers",
                line=dict(color="#3b82f6", width=2, dash="dot"),
                marker=dict(size=4),
                hovertemplate="%{y:.1f}%<extra>PIB Oficial (est.)</extra>",
            ))

        # Li Keqiang proxy
        lk_df = None
        if calculate_li_keqiang_proxy is not None:
            try:
                lk_df = calculate_li_keqiang_proxy("CHN")
            except Exception:
                lk_df = None

        if lk_df is not None and not lk_df.empty:
            fig.add_trace(go.Scatter(
                x=lk_df.index, y=lk_df.values,
                name="Índice Li Keqiang (Proxy)", mode="lines",
                line=dict(color="#f97316", width=2, dash="dot"),
                hovertemplate="%{y:.1f}%<extra>Li Keqiang Proxy</extra>",
            ))
            # Anotaciones en mayor divergencia
            if gdp_series is not None and not gdp_series.empty:
                _add_divergence_annotations(fig, gdp_series, lk_df)
        else:
            fig.add_annotation(
                text="Proxy Li Keqiang no disponible — mostrando solo PIB oficial<br>"
                     "(requiere datos de energía, comercio y mercado chino en BD)",
                xref="paper", yref="paper", x=0.5, y=0.2,
                showarrow=False, font=dict(size=10, color=COLORS["text_muted"]),
                align="center",
            )

        # Línea cero
        fig.add_hline(y=0, line_dash="dash", line_color="#6b7280", line_width=1)
        return fig

    def _add_divergence_annotations(fig, gdp_df, lk_series):
        """Añade anotaciones en los puntos de mayor divergencia."""
        try:
            gdp_reindexed = gdp_df.set_index("timestamp")["value"].resample("A").mean()
            lk_reindexed = lk_series.resample("A").mean()
            common = gdp_reindexed.index.intersection(lk_reindexed.index)
            if len(common) == 0:
                return
            divergence = (gdp_reindexed[common] - lk_reindexed[common]).abs()
            top = divergence.nlargest(2)
            for date, div in top.items():
                gdp_v = gdp_reindexed.get(date)
                if gdp_v is not None:
                    fig.add_annotation(
                        x=date, y=gdp_v,
                        text=f"Div. {div:.1f}pp",
                        showarrow=True, arrowhead=2,
                        font=dict(size=9, color="#fbbf24"),
                        arrowcolor="#fbbf24",
                        ax=0, ay=-30,
                    )
        except Exception:
            pass

    # ── Tab 1: Cards de actividad ────────────────────────────────────────────
    @app.callback(
        Output("m12-activity-cards", "children"),
        Input("m12-tabs", "value"),
        Input("m12-interval", "n_intervals"),
    )
    def update_activity_cards(tab, _n):
        if tab != "tab-1":
            return html.Div()

        # Card 1: Manufactura
        manuf_val, _ = get_latest_value("wb_manufacturing_pct_gdp_chn")
        manuf_str = _safe(manuf_val, ".1f") + "%" if manuf_val is not None else "~27%"
        usa_manuf = "~11%"

        # Card 2: ETF MCHI como proxy consumo
        mchi_val, _ = get_latest_value("yf_mchi_close")
        mchi_str = f"{mchi_val:.2f}" if mchi_val is not None else "—"

        # Card 3: Exportaciones % PIB
        exp_val, _ = get_latest_value("wb_exports_pct_gdp_chn")
        exp_str = _safe(exp_val, ".1f") + "%" if exp_val is not None else "—"

        # Card 4: Shanghai Composite YTD
        sh_val, _ = get_latest_value("yf_000001ss_close")
        sh_str = f"{sh_val:,.0f}" if sh_val is not None else "—"

        return dbc.Row([
            dbc.Col(html.Div([
                html.Div("Manufactura % PIB China", style={
                    "fontSize": "0.78rem", "color": COLORS["text_muted"],
                    "marginBottom": "6px", "fontWeight": "600",
                }),
                html.Div(manuf_str, style={"fontSize": "2rem", "fontWeight": "700", "color": "#f97316"}),
                html.Div(
                    f"La manufactura representa el {manuf_str} del PIB chino, vs {usa_manuf} en EE.UU. "
                    "Cuando la actividad manufacturera cae, China lo siente más que las economías de servicios.",
                    style={"fontSize": "0.75rem", "color": COLORS["text_muted"], "marginTop": "8px",
                           "lineHeight": "1.5"},
                ),
            ], style=_CARD), width=3),
            dbc.Col(html.Div([
                html.Div("ETF MCHI (Proxy Consumo Chino)", style={
                    "fontSize": "0.78rem", "color": COLORS["text_muted"],
                    "marginBottom": "6px", "fontWeight": "600",
                }),
                html.Div(mchi_str, style={"fontSize": "2rem", "fontWeight": "700", "color": COLORS["accent"]}),
                html.Div(
                    "El ETF iShares MSCI China sirve como proxy de la renta variable y consumo chino accesible desde mercados occidentales.",
                    style={"fontSize": "0.75rem", "color": COLORS["text_muted"], "marginTop": "8px",
                           "lineHeight": "1.5"},
                ),
            ], style=_CARD), width=3),
            dbc.Col(html.Div([
                html.Div("Exportaciones como % del PIB", style={
                    "fontSize": "0.78rem", "color": COLORS["text_muted"],
                    "marginBottom": "6px", "fontWeight": "600",
                }),
                html.Div(exp_str, style={"fontSize": "2rem", "fontWeight": "700", "color": COLORS["yellow"]}),
                html.Div(
                    "La creciente dependencia exportadora de China es una señal de debilidad del consumo interno. "
                    "Un superávit récord refleja demanda doméstica deprimida.",
                    style={"fontSize": "0.75rem", "color": COLORS["text_muted"], "marginTop": "8px",
                           "lineHeight": "1.5"},
                ),
            ], style=_CARD), width=3),
            dbc.Col(html.Div([
                html.Div("Shanghai Composite", style={
                    "fontSize": "0.78rem", "color": COLORS["text_muted"],
                    "marginBottom": "6px", "fontWeight": "600",
                }),
                html.Div(sh_str, style={"fontSize": "2rem", "fontWeight": "700", "color": COLORS["text"]}),
                html.Div(
                    "La bolsa china (000001.SS) es relativamente poco representativa de la economía real, "
                    "pero su tendencia indica la confianza del mercado doméstico.",
                    style={"fontSize": "0.75rem", "color": COLORS["text_muted"], "marginTop": "8px",
                           "lineHeight": "1.5"},
                ),
            ], style=_CARD), width=3),
        ], className="g-2")

    # ── Tab 1: Composición PIB ──────────────────────────────────────────────
    @app.callback(
        Output("m12-gdp-composition-chart", "figure"),
        Input("m12-tabs", "value"),
        Input("m12-interval", "n_intervals"),
    )
    def update_gdp_composition(tab, _n):
        if tab != "tab-1":
            return go.Figure()

        layout = get_base_layout()
        layout.update(
            title=dict(text="Composición del PIB: China vs EE.UU.", font=dict(size=13)),
            barmode="stack",
            xaxis_title="País / Año",
            yaxis_title="% del PIB",
            legend=dict(x=0.01, y=1.1, orientation="h"),
        )
        fig = go.Figure(layout=layout)

        countries = {"CHN": "China", "USA": "EE.UU."}
        indicators = {
            "wb_manufacturing_pct_gdp": ("Manufactura", "#f97316"),
            "wb_services_pct_gdp": ("Servicios", "#3b82f6"),
            "wb_agriculture_pct_gdp": ("Agricultura", "#10b981"),
        }

        for iso, country_name in countries.items():
            for ind_base, (ind_label, color) in indicators.items():
                series_id = f"{ind_base}_{iso.lower()}"
                val, _ = get_latest_value(series_id)
                if val is not None:
                    fig.add_trace(go.Bar(
                        x=[country_name], y=[val],
                        name=ind_label,
                        marker_color=color,
                        showlegend=(iso == "CHN"),
                        legendgroup=ind_label,
                        hovertemplate=f"{ind_label}: %{{y:.1f}}%<extra>{country_name}</extra>",
                    ))

        if not fig.data:
            fig.add_annotation(
                text="Datos de composición del PIB no disponibles en BD<br>"
                     "(Requiere World Bank NV.IND.MANF.ZS, NV.SRV.TOTL.ZS, NV.AGR.TOTL.ZS)",
                xref="paper", yref="paper", x=0.5, y=0.5,
                showarrow=False, font=dict(size=11, color=COLORS["text_muted"]),
            )

        return fig

    # ── Tab 2: Deflación ────────────────────────────────────────────────────
    @app.callback(
        Output("m12-deflation-chart", "figure"),
        Input("m12-tabs", "value"),
        Input("m12-interval", "n_intervals"),
    )
    def update_deflation(tab, _n):
        if tab != "tab-2":
            return go.Figure()

        layout = get_base_layout()
        layout.update(
            title=dict(text="CPI China — Inflación al Consumidor (YoY %)", font=dict(size=13)),
            xaxis_title="Año",
            yaxis_title="Variación YoY (%)",
            hovermode="x unified",
        )
        fig = go.Figure(layout=layout)

        # CPI China — intentar BD, fallback a datos estáticos
        cpi_series = get_series("wb_cpi_chn", days=4000)
        use_static = cpi_series is None or cpi_series.empty

        if not use_static:
            try:
                import pandas as pd
                cpi_series["timestamp"] = pd.to_datetime(cpi_series["timestamp"])
                vals = cpi_series["value"].tolist()
                dates = cpi_series["timestamp"].tolist()
            except Exception:
                use_static = True

        if use_static:
            dates = list(_CHINA_CPI_STATIC.keys())
            vals = list(_CHINA_CPI_STATIC.values())
            fig.add_annotation(
                text="Fuente: estimación histórica (BD sin datos en línea)",
                xref="paper", yref="paper", x=0.01, y=1.05,
                showarrow=False, font=dict(size=9, color=COLORS["text_muted"]),
            )

        fig.add_trace(go.Scatter(
            x=dates, y=vals,
            name="CPI China (YoY%)", mode="lines+markers",
            line=dict(color="#3b82f6", width=2),
            marker=dict(size=5),
            fill="tozeroy",
            fillcolor="rgba(59,130,246,0.08)",
            hovertemplate="%{y:.1f}%<extra>CPI China</extra>",
        ))

        # Zona roja cuando CPI < 0
        neg_x, neg_y = [], []
        for d, v in zip(dates, vals):
            if v is not None and v < 0:
                neg_x.append(d)
                neg_y.append(v)
            else:
                if neg_x:
                    neg_x.append(d)
                    neg_y.append(0)
                    fig.add_trace(go.Scatter(
                        x=neg_x[:], y=neg_y[:],
                        fill="tozeroy", fillcolor="rgba(239,68,68,0.25)",
                        line=dict(color="rgba(239,68,68,0.5)", width=0.5),
                        name="Zona deflación", showlegend=True,
                    ))
                neg_x, neg_y = [], []

        # Línea cero
        fig.add_hline(y=0, line_dash="dash", line_color="#ef4444", line_width=1.5,
                      annotation_text="Umbral deflación", annotation_position="bottom right",
                      annotation_font=dict(color="#ef4444", size=9))
        return fig

    # ── Tab 2: Comparativa Japón ────────────────────────────────────────────
    @app.callback(
        Output("m12-japan-comparison-chart", "figure"),
        Input("m12-tabs", "value"),
    )
    def update_japan_comparison(tab):
        if tab != "tab-2":
            return go.Figure()

        layout = get_base_layout()
        layout.update(
            title=dict(text="Comparativa Deflacionaria: Japón (años 90) vs China (actual)", font=dict(size=13)),
            xaxis=dict(title="Años desde inicio del período (Japón=1990, China=2010)", tickmode="linear", dtick=2),
            yaxis=dict(title="CPI — Variación YoY (%)"),
            hovermode="x unified",
            legend=dict(x=0.65, y=0.99),
        )
        fig = go.Figure(layout=layout)

        jpn_data = _load_json("japan_deflation_comparison.json")
        jp_cpi = jpn_data.get("japan_cpi_1990s", {})
        if jp_cpi:
            years = sorted(jp_cpi.keys())
            vals = [jp_cpi[y] for y in years]
            rel_years = list(range(len(years)))
            fig.add_trace(go.Scatter(
                x=rel_years, y=vals,
                name="Japón 1990-2005 (Década Perdida)", mode="lines+markers",
                line=dict(color="#f59e0b", width=2, dash="dot"),
                marker=dict(size=5),
                hovertemplate="Año +%{x}: %{y:.1f}%<extra>Japón</extra>",
            ))

        # China: BD o fallback estático
        cpi_series = get_series("wb_cpi_chn", days=3650)
        china_cpi_vals = None
        if cpi_series is not None and not cpi_series.empty:
            try:
                import pandas as pd
                cpi_series["timestamp"] = pd.to_datetime(cpi_series["timestamp"])
                annual = cpi_series.set_index("timestamp")["value"].resample("A").mean().dropna()
                china_cpi_vals = annual.values.tolist()
            except Exception:
                pass
        if china_cpi_vals is None:
            china_cpi_vals = list(_CHINA_CPI_STATIC.values())

        rel_years_cn = list(range(len(china_cpi_vals)))
        fig.add_trace(go.Scatter(
            x=rel_years_cn, y=china_cpi_vals,
            name="China 2010-actual", mode="lines+markers",
            line=dict(color="#ef4444", width=2),
            marker=dict(size=5),
            hovertemplate="Año +%{x}: %{y:.1f}%<extra>China</extra>",
        ))

        fig.add_hline(y=0, line_dash="dash", line_color="#6b7280", line_width=1)
        return fig

    # ── Tab 2: Real estate ventas e inversión ───────────────────────────────
    @app.callback(
        Output("m12-realestate-sales-chart", "figure"),
        Input("m12-tabs", "value"),
    )
    def update_realestate_sales(tab):
        if tab != "tab-2":
            return go.Figure()

        re_data = _load_json("china_real_estate.json")
        sales = re_data.get("new_home_sales_yoy_pct", {})
        inv = re_data.get("property_investment_yoy_pct", {})

        layout = get_base_layout()
        layout.update(
            title=dict(text="Ventas e Inversión Inmobiliaria China (YoY %)", font=dict(size=13)),
            barmode="group",
            xaxis_title="Año",
            yaxis_title="Variación YoY (%)",
        )
        fig = go.Figure(layout=layout)

        years = sorted(set(sales.keys()) | set(inv.keys()))
        fig.add_trace(go.Bar(
            x=years, y=[sales.get(y) for y in years],
            name="Ventas nuevas viviendas",
            marker_color=["#ef4444" if (sales.get(y) or 0) < 0 else "#10b981" for y in years],
        ))
        fig.add_trace(go.Bar(
            x=years, y=[inv.get(y) for y in years],
            name="Inversión inmobiliaria",
            marker_color=["#f97316" if (inv.get(y) or 0) < 0 else "#3b82f6" for y in years],
        ))
        fig.add_hline(y=0, line_dash="dash", line_color="#6b7280")
        return fig

    @app.callback(
        Output("m12-realestate-inventory-chart", "figure"),
        Input("m12-tabs", "value"),
    )
    def update_realestate_inventory(tab):
        if tab != "tab-2":
            return go.Figure()

        re_data = _load_json("china_real_estate.json")
        inv = re_data.get("unsold_inventory_months", {})

        layout = get_base_layout()
        layout.update(
            title=dict(text="Inventario Viviendas Sin Vender (meses de demanda)", font=dict(size=13)),
            xaxis_title="Año",
            yaxis_title="Meses",
        )
        fig = go.Figure(layout=layout)

        years = sorted(inv.keys())
        vals = [inv[y] for y in years]
        fig.add_trace(go.Scatter(
            x=years, y=vals,
            name="Inventario (meses)",
            mode="lines+markers",
            line=dict(color="#ef4444", width=2),
            fill="tozeroy",
            fillcolor="rgba(239,68,68,0.1)",
            hovertemplate="%{y:.1f} meses<extra></extra>",
        ))
        fig.add_hline(y=6, line_dash="dash", line_color="#10b981", line_width=1,
                      annotation_text="Nivel saludable (~6m)", annotation_position="top right",
                      annotation_font=dict(color="#10b981", size=9))
        return fig

    @app.callback(
        Output("m12-developer-defaults-table", "children"),
        Input("m12-tabs", "value"),
    )
    def update_developer_defaults(tab):
        if tab != "tab-2":
            return html.Div()

        re_data = _load_json("china_real_estate.json")
        defaults = re_data.get("major_developer_defaults", [])

        if not defaults:
            return html.Div("Sin datos", style={"color": COLORS["text_muted"]})

        rows = []
        for d in sorted(defaults, key=lambda x: x.get("date", ""), reverse=True):
            debt = d.get("debt_bn_usd", 0)
            color = COLORS["red"] if debt > 100 else COLORS["orange"]
            rows.append(html.Tr([
                html.Td(d.get("name", ""), style={"padding": "6px 12px", "color": COLORS["text"],
                                                    "fontWeight": "600",
                                                    "borderBottom": f"1px solid {COLORS['border']}"}),
                html.Td(d.get("date", ""), style={"padding": "6px 12px", "color": COLORS["text_muted"],
                                                   "fontSize": "0.8rem",
                                                   "borderBottom": f"1px solid {COLORS['border']}"}),
                html.Td(f"{debt}B USD", style={"padding": "6px 12px", "color": color,
                                                "fontWeight": "600", "textAlign": "right",
                                                "borderBottom": f"1px solid {COLORS['border']}"}),
            ]))

        return html.Table([
            html.Thead(html.Tr([
                html.Th(h, style={"padding": "6px 12px", "color": COLORS["text_muted"],
                                   "fontSize": "0.72rem",
                                   "borderBottom": f"2px solid {COLORS['border']}",
                                   "textAlign": "left" if i < 2 else "right"})
                for i, h in enumerate(["Promotor", "Fecha impago", "Deuda afectada"])
            ])),
            html.Tbody(rows),
        ], style={"width": "100%", "borderCollapse": "collapse"})

    # ── Tab 3: Superávit comercial ─────────────────────────────────────────
    @app.callback(
        Output("m12-trade-balance-chart", "figure"),
        Input("m12-tabs", "value"),
        Input("m12-interval", "n_intervals"),
    )
    def update_trade_balance(tab, _n):
        if tab != "tab-3":
            return go.Figure()

        trade = _load_json("china_trade.json")
        balance = trade.get("trade_balance_bn_usd", {})

        layout = get_base_layout(height=255)
        layout.update(
            title=dict(text="Superávit Comercial China (miles de millones USD)", font=dict(size=12)),
            xaxis_title="",
            yaxis_title="Miles de millones USD",
            margin=dict(l=55, r=15, t=40, b=55),
        )
        fig = go.Figure(layout=layout)

        # Convertir años a int para eje numérico continuo
        years = [int(y) for y in sorted(balance.keys())]
        vals = [balance[str(y)] for y in years]

        fig.update_layout(xaxis=dict(
            tickmode="array", tickvals=years,
            ticktext=[str(y) for y in years],
            tickangle=-45,
        ))

        fig.add_trace(go.Bar(
            x=years, y=vals,
            name="Superávit comercial",
            marker_color=[
                "#10b981" if v < 500 else "#f59e0b" if v < 800 else "#ef4444"
                for v in vals
            ],
            hovertemplate="<b>%{x}</b>: %{y}B USD<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=years, y=vals,
            mode="lines", name="Tendencia",
            line=dict(color="#9ca3af", width=1, dash="dot"),
            showlegend=False,
        ))

        # Anotación récord
        if vals:
            max_val = max(vals)
            max_year = years[vals.index(max_val)]
            fig.add_annotation(
                x=max_year, y=max_val,
                text=f"Récord: {max_val}B USD",
                showarrow=True, arrowhead=2,
                font=dict(size=10, color="#fbbf24"),
                arrowcolor="#fbbf24",
                ax=0, ay=-36,
            )
        return fig

    @app.callback(
        Output("m12-exports-destination-chart", "figure"),
        Input("m12-tabs", "value"),
    )
    def update_exports_destination(tab):
        if tab != "tab-3":
            return go.Figure()

        trade = _load_json("china_trade.json")
        dest = trade.get("exports_by_destination_pct_2025", {})

        layout = get_base_layout(height=255)
        layout.update(
            title=dict(text="Destino Exportaciones 2025", font=dict(size=12)),
            showlegend=False,
            margin=dict(l=5, r=5, t=35, b=5),
        )
        fig = go.Figure(layout=layout)

        colors = ["#3b82f6", "#10b981", "#f97316", "#8b5cf6", "#f59e0b", "#ef4444", "#6b7280"]
        labels = list(dest.keys())
        vals = list(dest.values())

        fig.add_trace(go.Pie(
            labels=labels, values=vals,
            hole=0.42,
            marker=dict(colors=colors[:len(labels)]),
            # Mostrar porcentaje en segmentos grandes, solo % en pequeños
            textinfo="label+percent",
            textfont=dict(size=9),
            insidetextorientation="radial",
            hovertemplate="<b>%{label}</b>: %{value:.1f}%<extra></extra>",
        ))
        return fig

    @app.callback(
        Output("m12-exports-products-chart", "figure"),
        Input("m12-tabs", "value"),
    )
    def update_exports_products(tab):
        if tab != "tab-3":
            return go.Figure()

        trade = _load_json("china_trade.json")
        products = trade.get("top_export_products_2025", [])

        layout = get_base_layout(height=235)
        layout.update(
            title=dict(text="Principales Productos de Exportación 2025 (%)", font=dict(size=12)),
            xaxis_title="% del total",
            yaxis=dict(autorange="reversed"),
            margin=dict(l=165, r=55, t=35, b=35),
            showlegend=False,
        )
        fig = go.Figure(layout=layout)

        if products:
            names = [p["product"] for p in products]
            pcts = [p["pct"] for p in products]
            colors = ["#3b82f6", "#10b981", "#f97316", "#8b5cf6", "#f59e0b", "#9ca3af"]
            fig.add_trace(go.Bar(
                x=pcts, y=names, orientation="h",
                marker_color=colors[:len(names)],
                text=[f"{v}%" for v in pcts],
                textposition="outside",
                textfont=dict(size=10, color=COLORS["text_muted"]),
                hovertemplate="<b>%{y}</b>: %{x}%<extra></extra>",
            ))
        return fig

    # ── Tab 3: Reservas divisas ────────────────────────────────────────────
    @app.callback(
        Output("m12-fx-reserves-chart", "figure"),
        Input("m12-tabs", "value"),
        Input("m12-interval", "n_intervals"),
    )
    def update_fx_reserves(tab, _n):
        if tab != "tab-3":
            return go.Figure()

        layout = get_base_layout(height=235)
        layout.update(
            title=dict(text="Reservas de Divisas China (billones USD)", font=dict(size=12)),
            xaxis_title="",
            yaxis_title="Billones USD",
            hovermode="x unified",
            margin=dict(l=55, r=15, t=40, b=40),
        )
        fig = go.Figure(layout=layout)

        res_series = get_series("wb_fx_reserves_chn", days=9000)
        if res_series is not None and not res_series.empty:
            vals_t = res_series["value"] / 1e12
            fig.add_trace(go.Scatter(
                x=res_series["timestamp"], y=vals_t,
                name="Reservas divisas",
                mode="lines", line=dict(color="#10b981", width=2),
                fill="tozeroy", fillcolor="rgba(16,185,129,0.08)",
                hovertemplate="%{y:.2f}B USD<extra></extra>",
            ))
            # Pico
            peak_idx = vals_t.idxmax()
            fig.add_annotation(
                x=res_series.loc[peak_idx, "timestamp"],
                y=vals_t[peak_idx],
                text=f"Pico: {vals_t[peak_idx]:.2f}B USD",
                showarrow=True, arrowhead=2,
                font=dict(size=9, color="#fbbf24"),
                arrowcolor="#fbbf24", ax=0, ay=-30,
            )
        else:
            # Datos estáticos de fallback
            static_years = ["2000", "2005", "2010", "2014", "2017", "2020", "2023", "2025"]
            static_vals = [0.17, 0.82, 2.85, 3.99, 3.01, 3.22, 3.11, 3.25]
            fig.add_trace(go.Scatter(
                x=static_years, y=static_vals,
                name="Reservas divisas (estimación)",
                mode="lines+markers", line=dict(color="#10b981", width=2),
                fill="tozeroy", fillcolor="rgba(16,185,129,0.08)",
            ))

        return fig

    # ── Tab 3: Yuan ────────────────────────────────────────────────────────
    @app.callback(
        Output("m12-yuan-chart", "figure"),
        Input("m12-tabs", "value"),
        Input("m12-interval", "n_intervals"),
    )
    def update_yuan(tab, _n):
        if tab != "tab-3":
            return go.Figure()

        layout = get_base_layout(height=235)
        layout.update(
            title=dict(text="Tipo de Cambio CNY/USD (Yuan por Dólar)", font=dict(size=12)),
            xaxis_title="",
            yaxis_title="CNY / USD",
            hovermode="x unified",
            margin=dict(l=55, r=15, t=40, b=40),
        )
        fig = go.Figure(layout=layout)

        import pandas as pd

        cny_series = get_series("yf_cny_usd_close", days=3650)
        use_static_cny = True

        if cny_series is not None and not cny_series.empty:
            try:
                cny_series["timestamp"] = pd.to_datetime(cny_series["timestamp"])
                fig.add_trace(go.Scatter(
                    x=cny_series["timestamp"], y=cny_series["value"],
                    name="CNY/USD (onshore)",
                    mode="lines", line=dict(color="#f59e0b", width=2),
                    hovertemplate="CNY %{y:.4f}<extra></extra>",
                ))
                use_static_cny = False
            except Exception:
                pass

        if use_static_cny:
            # Datos históricos estáticos CNY/USD
            static_years = [2005, 2006, 2007, 2008, 2009, 2010, 2011, 2012,
                            2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020,
                            2021, 2022, 2023, 2024, 2025]
            static_cny   = [8.19, 7.97, 7.61, 6.95, 6.83, 6.77, 6.46, 6.31,
                            6.09, 6.14, 6.49, 6.64, 6.51, 6.52, 6.91, 6.90,
                            6.45, 6.74, 7.08, 7.18, 7.25]
            fig.add_trace(go.Scatter(
                x=static_years, y=static_cny,
                name="CNY/USD (estimación histórica)",
                mode="lines+markers", line=dict(color="#f59e0b", width=2),
                marker=dict(size=5),
                hovertemplate="CNY/USD %{y:.2f}<extra></extra>",
            ))
            fig.add_annotation(
                text="Datos estimados anuales — BD sin datos en tiempo real",
                xref="paper", yref="paper", x=0.01, y=1.05,
                showarrow=False, font=dict(size=9, color=COLORS["text_muted"]),
            )

        fig.add_annotation(
            text="Mayor valor = Yuan más débil vs USD",
            xref="paper", yref="paper", x=0.01, y=0.95,
            showarrow=False, font=dict(size=9, color=COLORS["text_muted"]),
        )
        return fig

    # ── Tab 3: IED ────────────────────────────────────────────────────────
    @app.callback(
        Output("m12-fdi-chart", "figure"),
        Input("m12-tabs", "value"),
        Input("m12-interval", "n_intervals"),
    )
    def update_fdi(tab, _n):
        if tab != "tab-3":
            return go.Figure()

        layout = get_base_layout(height=235)
        layout.update(
            title=dict(text="Inversión Extranjera Directa en China (% PIB)", font=dict(size=12)),
            xaxis_title="",
            yaxis_title="% del PIB",
            margin=dict(l=50, r=15, t=40, b=40),
        )
        fig = go.Figure(layout=layout)

        fdi_series = get_series("wb_fdi_inflows_pct_gdp_chn", days=9000)
        if fdi_series is not None and not fdi_series.empty:
            fig.add_trace(go.Bar(
                x=fdi_series["timestamp"], y=fdi_series["value"],
                name="IED Entradas (% PIB)",
                marker_color=["#10b981" if v > 0 else "#ef4444" for v in fdi_series["value"]],
                hovertemplate="%{y:.2f}%<extra></extra>",
            ))
        else:
            # Fallback estático
            static_years = ["2010", "2012", "2014", "2016", "2018", "2020", "2022", "2024"]
            static_vals = [3.1, 2.7, 2.5, 1.6, 1.5, 2.5, 0.8, 0.6]
            fig.add_trace(go.Bar(
                x=static_years, y=static_vals,
                name="IED Entradas (% PIB) — estimación",
                marker_color=["#10b981" if v > 1.5 else "#f59e0b" if v > 0.8 else "#ef4444"
                               for v in static_vals],
            ))
            fig.add_annotation(
                text="Datos estimados — caída drástica post-2022 por tensiones geopolíticas",
                xref="paper", yref="paper", x=0.5, y=0.95,
                showarrow=False, font=dict(size=9, color="#fbbf24"),
            )
        return fig

    # ── Tab 5: China-India crecimiento ─────────────────────────────────────
    @app.callback(
        Output("m12-china-india-chart", "figure"),
        Input("m12-tabs", "value"),
        Input("m12-interval", "n_intervals"),
    )
    def update_china_india(tab, _n):
        if tab != "tab-5":
            return go.Figure()

        layout = get_base_layout()
        layout.update(
            title=dict(text="Crecimiento PIB: China vs India (% YoY)", font=dict(size=13)),
            xaxis_title="Año",
            yaxis_title="Crecimiento PIB (%)",
            hovermode="x unified",
            legend=dict(x=0.01, y=0.99),
        )
        fig = go.Figure(layout=layout)

        import pandas as pd

        static_map = {"chn": _CHINA_GDP_STATIC, "ind": _INDIA_GDP_STATIC}
        last_hist_year = {"chn": 2024, "ind": 2024}

        for iso, name, color in [("chn", "China", "#ef4444"), ("ind", "India", "#f97316")]:
            series = get_series(f"wb_gdp_growth_{iso}", days=9000)
            plotted_live = False
            if series is not None and not series.empty:
                try:
                    series["timestamp"] = pd.to_datetime(series["timestamp"])
                    fig.add_trace(go.Scatter(
                        x=series["timestamp"], y=series["value"],
                        name=name, mode="lines",
                        line=dict(color=color, width=2),
                        hovertemplate=f"{name}: %{{y:.1f}}%<extra></extra>",
                    ))
                    plotted_live = True
                    last_hist_year[iso] = series["timestamp"].dt.year.max()
                except Exception:
                    pass
            if not plotted_live:
                # Fallback estático
                static = static_map[iso]
                hist_years = sorted(static.keys())
                hist_vals = [static[y] for y in hist_years]
                fig.add_trace(go.Scatter(
                    x=hist_years, y=hist_vals,
                    name=name, mode="lines",
                    line=dict(color=color, width=2),
                    hovertemplate=f"{name}: %{{y:.1f}}%<extra></extra>",
                ))
                last_hist_year[iso] = hist_years[-1]

        # Proyecciones 2025-2030 — conectar con último año histórico
        proj_years_int = [2025, 2026, 2027, 2028, 2029, 2030]
        chn_proj = [5.0, 4.5, 4.2, 4.0, 3.8, 3.6]
        ind_proj = [6.8, 6.5, 6.5, 6.8, 6.7, 6.5]
        fig.add_trace(go.Scatter(
            x=proj_years_int, y=chn_proj,
            name="China (proyección)", mode="lines",
            line=dict(color="#ef4444", dash="dot", width=1.5),
            hovertemplate="China proj.: %{y:.1f}%<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=proj_years_int, y=ind_proj,
            name="India (proyección)", mode="lines",
            line=dict(color="#f97316", dash="dot", width=1.5),
            hovertemplate="India proj.: %{y:.1f}%<extra></extra>",
        ))
        # Zona de proyecciones
        fig.add_vrect(
            x0=2025, x1=2030,
            fillcolor="rgba(255,255,255,0.03)",
            line_width=0,
            annotation_text="Proyección", annotation_position="top left",
            annotation_font=dict(size=9, color=COLORS["text_muted"]),
        )
        fig.add_hline(y=0, line_dash="dash", line_color="#6b7280", line_width=1)
        return fig

    # ── Tab 5: Triángulo comercial ─────────────────────────────────────────
    @app.callback(
        Output("m12-triangle-table", "children"),
        Input("m12-tabs", "value"),
    )
    def update_triangle(tab):
        if tab != "tab-5":
            return html.Div()

        strategic = load_json_data("strategic_dependencies.json") or {}
        relationships = [
            ("🇺🇸 EE.UU. → 🇨🇳 China", "Competencia tecnológica, aranceles, sanciones",
             "Tensión alta", COLORS["orange"]),
            ("🇨🇳 China → 🇺🇸 EE.UU.", "Mayor déficit comercial US: ~350B USD/año",
             "Dependencia económica mutua", COLORS["yellow"]),
            ("🇺🇸 EE.UU. → 🇪🇺 Europa", "OTAN, alianza política, comercio intenso",
             "Aliados — tensiones comerciales menores", COLORS["green"]),
            ("🇪🇺 Europa → 🇨🇳 China", "Mayor socio comercial, dependencia en manufacturas",
             "Creciente desconfianza estratégica", COLORS["yellow"]),
            ("🇨🇳 China → 🇪🇺 Europa", "Exportaciones masivas, BRI, inversión",
             "Tensión regulatoria creciente (aranceles EVs)", COLORS["orange"]),
            ("🇪🇺 Europa → 🇺🇸 EE.UU.", "Dependencia en defensa, dólar, semiconductores",
             "Aliados estratégicos", COLORS["green"]),
        ]

        rows = [html.Tr([
            html.Td(rel, style={"padding": "8px 12px", "color": COLORS["text"],
                                 "fontWeight": "600", "fontSize": "0.82rem",
                                 "borderBottom": f"1px solid {COLORS['border']}"}),
            html.Td(desc, style={"padding": "8px 12px", "color": COLORS["text_muted"],
                                  "fontSize": "0.78rem",
                                  "borderBottom": f"1px solid {COLORS['border']}"}),
            html.Td(status, style={"padding": "8px 12px", "color": sc,
                                    "fontWeight": "600", "fontSize": "0.78rem",
                                    "borderBottom": f"1px solid {COLORS['border']}"}),
        ]) for rel, desc, status, sc in relationships]

        return html.Table([
            html.Thead(html.Tr([
                html.Th(h, style={"padding": "8px 12px", "color": COLORS["text_muted"],
                                   "fontSize": "0.72rem",
                                   "borderBottom": f"2px solid {COLORS['border']}",
                                   "textAlign": "left"})
                for h in ["Relación", "Descripción", "Estado"]
            ])),
            html.Tbody(rows),
        ], style={"width": "100%", "borderCollapse": "collapse"})

    # ── Tab 5: PIB 2050 ────────────────────────────────────────────────────
    @app.callback(
        Output("m12-gdp2050-chart", "figure"),
        Input("m12-tabs", "value"),
    )
    def update_gdp2050(tab):
        if tab != "tab-5":
            return go.Figure()

        layout = get_base_layout()
        layout.update(
            title=dict(text="Proyecciones PIB Global a 2050 (billones USD constantes 2025)", font=dict(size=13)),
            xaxis_title="Año",
            yaxis_title="Billones USD",
            hovermode="x unified",
            legend=dict(x=0.01, y=0.99),
        )
        fig = go.Figure(layout=layout)

        proj = _load_json("gdp_projections_2050.json")
        gdp_data = proj.get("gdp_usd_trillion_constant_2025", {})

        country_styles = {
            "USA":  ("🇺🇸 EE.UU.", "#3b82f6", "solid"),
            "CHN":  ("🇨🇳 China", "#ef4444", "solid"),
            "IND":  ("🇮🇳 India", "#f97316", "dot"),
            "EU27": ("🇪🇺 Eurozona", "#10b981", "dash"),
            "JPN":  ("🇯🇵 Japón", "#9ca3af", "dot"),
        }

        for iso, (name, color, dash) in country_styles.items():
            if iso in gdp_data:
                # Convertir años string → int para eje numérico continuo
                years = [int(y) for y in sorted(gdp_data[iso].keys())]
                vals = [gdp_data[iso][str(y)] for y in years]
                fig.add_trace(go.Scatter(
                    x=years, y=vals,
                    name=name, mode="lines+markers",
                    line=dict(color=color, width=2, dash=dash),
                    marker=dict(size=6),
                    hovertemplate=f"{name}: %{{y:.1f}}B USD<extra></extra>",
                ))

        # Zona proyección (a partir de 2025)
        fig.add_vrect(
            x0=2025, x1=2050,
            fillcolor="rgba(255,255,255,0.02)",
            line_width=0,
            annotation_text="Proyección", annotation_position="top left",
            annotation_font=dict(size=9, color=COLORS["text_muted"]),
        )

        # Anotación del cruce China-EE.UU.
        fig.add_annotation(
            text="~2040-2045: posible<br>cruce China-EE.UU.",
            x=2042, y=45.0,
            showarrow=True, arrowhead=2,
            font=dict(size=9, color="#fbbf24"),
            arrowcolor="#fbbf24", ax=50, ay=-30,
        )
        return fig
