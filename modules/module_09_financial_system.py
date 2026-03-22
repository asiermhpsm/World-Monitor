"""
Modulo 9 - Sistema Financiero y Riesgo Sistemico
Se renderiza cuando la URL es /module/9.

Exporta:
  render_module_9()                -> layout completo
  register_callbacks_module_9(app) -> registra todos los callbacks
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
    calculate_hy_spread_proxy,
    calculate_ig_spread_proxy,
    calculate_systemic_risk_index,
    get_change,
    get_latest_value,
    get_series,
    load_json_data,
)

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

# ── IDs de indicadores ────────────────────────────────────────────────────────

ID_STLFSI4   = "fred_stlfsi4_us"
ID_VIX       = "yf_vix_close"
ID_SOFR      = "fred_sofr_us"
ID_HYG       = "yf_hyg_close"
ID_IEF       = "yf_ief_close"
ID_LQD       = "yf_lqd_close"
ID_EMB       = "yf_emb_close"
ID_EEM       = "yf_eem_close"
ID_DXY       = "yf_dxy_close"
ID_USDJPY    = "yf_usdjpy_close"
ID_IT_SPREAD = "ecb_spread_it_de"
ID_JPM       = "yf_jpm_close"
ID_SAN       = "yf_san.mc_close"
ID_GOLD      = "yf_gc_close"

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

# Mapa de banderas para bancos
_BANK_FLAGS = {
    "US": "🇺🇸", "DE": "🇩🇪", "FR": "🇫🇷", "ES": "🇪🇸",
    "IT": "🇮🇹", "GB": "🇬🇧", "CH": "🇨🇭", "JP": "🇯🇵",
    "HK": "🇭🇰",
}

# ── Helpers internos ──────────────────────────────────────────────────────────

def _safe(val, fmt=".1f", suffix="", none_str="—") -> str:
    if val is None:
        return none_str
    try:
        return f"{val:{fmt}}{suffix}"
    except Exception:
        return none_str


def _chg_color(chg: Optional[float], higher_bad: bool = True) -> str:
    if chg is None:
        return COLORS["text_muted"]
    if chg == 0:
        return COLORS["text_muted"]
    if higher_bad:
        return COLORS["red"] if chg > 0 else COLORS["green"]
    return COLORS["green"] if chg > 0 else COLORS["red"]


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


def _rgba(hex_color: str, alpha: float = 0.15) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


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


def _nivel_label(nivel: str) -> tuple[str, str]:
    """Devuelve (texto, color) para un nivel de riesgo."""
    MAP = {
        "green":       ("SISTEMA SANO",        COLORS["green"]),
        "yellow_green":("TENSION LEVE",        COLORS["green_yellow"]),
        "yellow":      ("TENSION MODERADA",    COLORS["yellow"]),
        "orange":      ("ESTRES ELEVADO",      COLORS["orange"]),
        "red":         ("ESTRES SISTEMICO",    COLORS["red"]),
        "gray":        ("SIN DATOS",           COLORS["text_muted"]),
    }
    return MAP.get(nivel, ("DESCONOCIDO", COLORS["text_muted"]))


def _stlfsi_color(val: Optional[float]) -> str:
    if val is None:
        return COLORS["text_muted"]
    if val < 0:
        return COLORS["green"]
    if val < 1:
        return COLORS["accent"]
    if val < 2:
        return COLORS["orange"]
    return COLORS["red"]


def _usdjpy_risk(val: Optional[float]) -> tuple[str, str]:
    """Semaforo de riesgo del carry trade del yen."""
    if val is None:
        return "SIN DATOS", COLORS["text_muted"]
    if val < 140:
        return "RIESGO BAJO", COLORS["green"]
    if val < 150:
        return "RIESGO ELEVADO", COLORS["yellow"]
    if val < 160:
        return "MUY ELEVADO", COLORS["orange"]
    return "EXTREMO", COLORS["red"]


# ── HEADER: fila de 6 metricas ────────────────────────────────────────────────

def _build_header_metrics() -> html.Div:
    """Construye la fila de 6 metricas siempre visibles."""
    # STLFSI4
    stlfsi_val, _ = get_latest_value(ID_STLFSI4)
    stlfsi_badge = None
    if stlfsi_val is not None:
        if stlfsi_val > 2.0:
            stlfsi_badge = html.Span("ESTRES SISTEMICO", style={
                "fontSize": "0.55rem", "fontWeight": "700", "color": COLORS["red"],
                "background": _rgba(COLORS["red"], 0.18),
                "padding": "2px 6px", "borderRadius": "3px",
                "border": f"1px solid {COLORS['red']}50",
            })
        elif stlfsi_val > 1.0:
            stlfsi_badge = html.Span("ESTRES ELEVADO", style={
                "fontSize": "0.55rem", "fontWeight": "700", "color": COLORS["orange"],
                "background": _rgba(COLORS["orange"], 0.18),
                "padding": "2px 6px", "borderRadius": "3px",
                "border": f"1px solid {COLORS['orange']}50",
            })

    stlfsi_color = _stlfsi_color(stlfsi_val)

    # Spread HY
    hy_spread = calculate_hy_spread_proxy()
    hy_color = COLORS["green"] if (hy_spread and hy_spread < 400) else (
               COLORS["yellow"] if (hy_spread and hy_spread < 600) else
               COLORS["orange"] if (hy_spread and hy_spread < 900) else COLORS["red"])

    # Spread IG
    ig_spread = calculate_ig_spread_proxy()
    ig_color = COLORS["green"] if (ig_spread and ig_spread < 120) else (
               COLORS["yellow"] if (ig_spread and ig_spread < 200) else COLORS["orange"])

    # SOFR
    sofr_val, _ = get_latest_value(ID_SOFR)

    # JPMorgan
    jpm_curr, jpm_prev, jpm_abs, jpm_pct = get_change("yf_jpm_close", period_days=1)
    jpm_color = _chg_color(jpm_pct, higher_bad=False)

    # Santander
    san_curr, san_prev, san_abs, san_pct = get_change("yf_san.mc_close", period_days=1)
    san_color = _chg_color(san_pct, higher_bad=False)

    metrics = [
        _compact_metric(
            "STLFSI4 (Fed St. Louis)",
            _safe(stlfsi_val, ".2f"),
            "estres financiero" + (" | < 0: facil" if stlfsi_val is not None and stlfsi_val < 0 else ""),
            stlfsi_color,
            badge=stlfsi_badge,
        ),
        _compact_metric(
            "SPREAD HIGH YIELD",
            f"{_safe(hy_spread, '.0f')} pb" if hy_spread else "— pb",
            "proxy HYG vs IEF",
            hy_color,
        ),
        _compact_metric(
            "SPREAD INVEST. GRADE",
            f"{_safe(ig_spread, '.0f')} pb" if ig_spread else "— pb",
            "proxy LQD vs IEF",
            ig_color,
        ),
        _compact_metric(
            "SOFR",
            f"{_safe(sofr_val, '.2f')}%",
            "tipo interbancario USD",
            COLORS["accent"],
        ),
        _compact_metric(
            "JPMORGAN (JPM)",
            f"${_safe(jpm_curr, '.2f')}",
            f"{'+' if jpm_pct and jpm_pct > 0 else ''}{_safe(jpm_pct, '.2f')}% 24h",
            jpm_color,
        ),
        _compact_metric(
            "SANTANDER (SAN)",
            f"€{_safe(san_curr, '.3f')}",
            f"{'+' if san_pct and san_pct > 0 else ''}{_safe(san_pct, '.2f')}% 24h",
            san_color,
        ),
    ]

    return html.Div(
        metrics,
        style={
            "display": "flex",
            "gap": "10px",
            "flexWrap": "wrap",
            "padding": "12px 16px",
            "borderBottom": f"1px solid {COLORS['border']}",
            "background": COLORS["card_bg"],
        },
    )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — PANEL DE ESTRES SISTEMICO
# ══════════════════════════════════════════════════════════════════════════════

def _build_tab1() -> html.Div:
    return html.Div([
        # 1.1 Indicador Compuesto
        create_section_header(
            "1.1 — Indicador Compuesto de Riesgo Sistemico",
            subtitle="Calculo en tiempo real · 5 componentes ponderados · escala 0-100",
        ),
        html.Div([
            dbc.Row([
                dbc.Col([
                    dcc.Graph(id="m9-risk-gauge", config={"displayModeBar": False}),
                ], width=12, lg=5),
                dbc.Col([
                    html.Div(id="m9-risk-components-table"),
                ], width=12, lg=7),
            ]),
        ], style=_CARD),

        # 1.2 STLFSI4
        create_section_header(
            "1.2 — STLFSI4: El Termometro Oficial de la Fed",
            subtitle="Federal Reserve Bank of St. Louis · desde 2000 · media=0, sd=1",
        ),
        html.Div([
            dcc.Graph(id="m9-stlfsi-chart", config={"displayModeBar": False}),
            html.Div(
                "El STLFSI4 esta disenado para tener media 0 y desviacion estandar 1. "
                "Negativo = condiciones financieras mas faciles de lo normal. "
                "Picos historicos: Crisis 2008 (~9), COVID marzo 2020 (~6), Crisis SVB 2023 (~1.5).",
                style=_NOTE,
            ),
        ], style=_CARD),

        # 1.3 Spreads Interbancarios (SOFR)
        create_section_header(
            "1.3 — Mercado Interbancario: SOFR",
            subtitle="FRED · SOFR desde 2022 · sucesor del LIBOR",
        ),
        html.Div([
            dcc.Graph(id="m9-sofr-chart", config={"displayModeBar": False}),
            html.Div(id="m9-sofr-interpretation"),
            html.Div(
                "El SOFR (Secured Overnight Financing Rate) es el tipo de referencia "
                "para prestamos en dolares desde 2022, cuando reemplaza al LIBOR. "
                "En septiembre 2008 el LIBOR-OIS spread llego a 365 puntos basicos, "
                "senalizando la desconfianza total entre bancos.",
                style=_NOTE,
            ),
        ], style=_CARD),

        # 1.4 Mapa de Calor de Correlaciones
        create_section_header(
            "1.4 — Mapa de Calor de Correlaciones entre Activos (90 dias)",
            subtitle="S&P500 · HYG · LQD · EMB · VIX · Oro · DXY",
        ),
        html.Div([
            dcc.Graph(id="m9-correlation-heatmap", config={"displayModeBar": False}),
            html.Div(id="m9-correlation-interpretation"),
            html.Div(
                "Cuando todas las correlaciones convergen a 1 durante una crisis, "
                "los activos se mueven a la baja al mismo tiempo: es la senal de risk-off extremo. "
                "Los inversores venden todo (incluidos activos supuestamente 'seguros') "
                "para obtener liquidez.",
                style=_NOTE,
            ),
        ], style=_CARD),

    ], style=_SECTION)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — SALUD DE LOS GRANDES BANCOS
# ══════════════════════════════════════════════════════════════════════════════

def _build_tab2() -> html.Div:
    return html.Div([
        # 2.1 Dashboard de bancos
        create_section_header(
            "2.1 — Dashboard de Bancos Globales",
            subtitle="Precios en tiempo real · Ratios fundamentales actualizables · Semaforo de salud",
        ),
        html.Div([
            html.Div(id="m9-banks-table"),
        ], style=_CARD),

        # 2.2 Grafico comparativo normalizado
        create_section_header(
            "2.2 — Rendimiento Comparativo (Base 100)",
            subtitle="Rendimiento normalizado · Seleccionar bancos y periodo",
        ),
        html.Div([
            html.Div([
                html.Label("Bancos:", style={"fontSize": "0.78rem", "color": COLORS["text_muted"], "marginRight": "8px"}),
                dcc.Checklist(
                    id="m9-bank-selector",
                    options=[
                        {"label": " JPM (EE.UU.)", "value": "yf_jpm_close"},
                        {"label": " DB (Alemania)", "value": "yf_db_close"},
                        {"label": " SAN (Espana)", "value": "yf_san.mc_close"},
                        {"label": " UBS (Suiza)",  "value": "yf_ubsg.sw_close"},
                        {"label": " BAC (EE.UU.)", "value": "yf_bac_close"},
                        {"label": " HSBC (UK)",    "value": "yf_hsba.l_close"},
                        {"label": " BNP (Francia)","value": "yf_bnp.pa_close"},
                        {"label": " UCG (Italia)", "value": "yf_ucg.mi_close"},
                    ],
                    value=["yf_jpm_close", "yf_db_close", "yf_san.mc_close", "yf_ubsg.sw_close"],
                    inline=True,
                    inputStyle={"marginRight": "4px"},
                    labelStyle={"fontSize": "0.78rem", "marginRight": "12px", "color": COLORS["text_muted"]},
                ),
            ], style={"marginBottom": "10px"}),
            html.Div([
                html.Label("Periodo:", style={"fontSize": "0.78rem", "color": COLORS["text_muted"], "marginRight": "8px"}),
                dcc.RadioItems(
                    id="m9-bank-period",
                    options=[
                        {"label": "1M", "value": 30},
                        {"label": "3M", "value": 90},
                        {"label": "6M", "value": 180},
                        {"label": "1A", "value": 365},
                        {"label": "2A", "value": 730},
                    ],
                    value=365,
                    inline=True,
                    inputStyle={"marginRight": "4px"},
                    labelStyle={"fontSize": "0.78rem", "marginRight": "10px", "color": COLORS["text_muted"]},
                ),
            ], style={"marginBottom": "10px"}),
            dcc.Graph(id="m9-bank-performance-chart", config={"displayModeBar": False}),
            html.Div(
                "Las acciones bancarias son un indicador de mercado de la salud del sistema financiero. "
                "Cuando caen bruscamente (Deutsche Bank en 2016, Credit Suisse en 2022), "
                "el mercado esta descontando problemas que los datos oficiales aun no reflejan. "
                "Las lineas resaltadas en rojo indican caida anual superior al 30%.",
                style=_NOTE,
            ),
        ], style=_CARD),

        # 2.3 Stress Tests
        create_section_header(
            "2.3 — Resultados de Stress Tests Regulatorios",
            subtitle="Fed DFAST 2025 · BCE Stress Test 2024",
        ),
        html.Div([
            html.Div(id="m9-stress-tests-panel"),
            html.Div(
                "Los stress tests oficiales son importantes pero tienen limitaciones: "
                "el escenario adverso es definido por los propios reguladores y puede no "
                "capturar todos los riesgos relevantes. Los tests de 2006-2007 no previeron "
                "el colapso del mercado hipotecario.",
                style=_NOTE,
            ),
        ], style=_CARD),

    ], style=_SECTION)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — MERCADOS DE CREDITO
# ══════════════════════════════════════════════════════════════════════════════

def _build_tab3() -> html.Div:
    return html.Div([
        # 3.1 Spreads de credito corporativo
        create_section_header(
            "3.1 — Spreads de Credito Corporativo",
            subtitle="Proxy High Yield (HYG/IEF) · Proxy Investment Grade (LQD/IEF)",
        ),
        html.Div([
            html.Div([
                html.Label("Periodo:", style={"fontSize": "0.78rem", "color": COLORS["text_muted"], "marginRight": "8px"}),
                dcc.RadioItems(
                    id="m9-credit-period",
                    options=[
                        {"label": "1A", "value": 365},
                        {"label": "2A", "value": 730},
                        {"label": "5A", "value": 1825},
                    ],
                    value=730,
                    inline=True,
                    inputStyle={"marginRight": "4px"},
                    labelStyle={"fontSize": "0.78rem", "marginRight": "10px", "color": COLORS["text_muted"]},
                ),
            ], style={"marginBottom": "10px"}),
            dcc.Graph(id="m9-credit-spreads-chart", config={"displayModeBar": False}),
            html.Div(id="m9-credit-interpretation"),
            html.Div(
                "El mercado de credito corporativo frecuentemente anticipa problemas. "
                "Cuando las empresas mas endeudadas no pueden refinanciarse, el riesgo "
                "se extiende al sistema. Picos historicos: HY COVID 2020 (~1100pb), Crisis 2008 (~2000pb).",
                style=_NOTE,
            ),
        ], style=_CARD),

        # 3.2 Muro de vencimientos corporativo
        create_section_header(
            "3.2 — Muro de Vencimientos Corporativo EE.UU.",
            subtitle="Bloomberg / S&P LCD estimaciones · HY en rojo, IG en azul",
        ),
        html.Div([
            dcc.Graph(id="m9-corporate-maturity-chart", config={"displayModeBar": False}),
            html.Div(id="m9-maturity-note"),
        ], style=_CARD),

        # 3.3 Tasa de impagos
        create_section_header(
            "3.3 — Tasa de Impagos High Yield EE.UU. (Historico)",
            subtitle="Moody's / S&P · desde 2000",
        ),
        html.Div([
            dcc.Graph(id="m9-default-rate-chart", config={"displayModeBar": False}),
        ], style=_CARD),

        # 3.4 Deuda emergente
        create_section_header(
            "3.4 — Deuda Emergente: ETF EMB",
            subtitle="JP Morgan USD Emerging Markets Bond · 3 anos",
        ),
        html.Div([
            dcc.Graph(id="m9-emb-chart", config={"displayModeBar": False}),
            html.Div(id="m9-em-vulnerability-panel"),
            html.Div(
                "Cuando el dolar se aprecia y los tipos americanos suben, los paises emergentes "
                "con deuda en USD sufren el doble impacto: su deuda se encarece en moneda local "
                "Y los inversores extranjeros salen hacia activos americanos mas seguros.",
                style=_NOTE,
            ),
        ], style=_CARD),

    ], style=_SECTION)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — FLUJOS DE CAPITAL
# ══════════════════════════════════════════════════════════════════════════════

def _build_tab4() -> html.Div:
    return html.Div([
        # 4.1 El dolar como indicador de estres
        create_section_header(
            "4.1 — El Dolar como Indicador de Estres Global",
            subtitle="DXY vs STLFSI4 · correlacion entre fortaleza del dolar y estres financiero",
        ),
        html.Div([
            dcc.Graph(id="m9-dxy-chart", config={"displayModeBar": False}),
            html.Div(
                "Un dolar muy fuerte (DXY > 105) indica que los inversores globales estan en "
                "modo risk-off buscando refugio. Paradojicamente, esto empeora la situacion "
                "de los paises emergentes que deben pagar su deuda en dolares mas caros.",
                style=_NOTE,
            ),
        ], style=_CARD),

        # 4.2 Flujos hacia emergentes
        create_section_header(
            "4.2 — Flujos hacia Mercados Emergentes",
            subtitle="EEM (MSCI EM) vs DXY invertido · correlacion inversa historica",
        ),
        html.Div([
            dcc.Graph(id="m9-eem-chart", config={"displayModeBar": False}),
            html.Div(id="m9-em-vulnerable-panel"),
        ], style=_CARD),

        # 4.3 Carry trade del yen
        create_section_header(
            "4.3 — Monitor del Carry Trade del Yen (USD/JPY)",
            subtitle="Riesgo sistemico oculto · agosto 2024: deshacimiento masivo",
        ),
        html.Div([
            dcc.Graph(id="m9-usdjpy-chart", config={"displayModeBar": False}),
            html.Div(id="m9-carry-trade-panel"),
            html.Div(
                "El carry trade del yen consiste en pedir prestado en yenes (tipo ~0%) para "
                "invertir en activos con mayor rentabilidad. Cuando el yen se aprecia bruscamente, "
                "estos trades se deshacen todos a la vez causando ventas forzadas masivas en "
                "multiples mercados simultaneamente. Agosto 2024 fue el ultimo episodio significativo.",
                style=_NOTE,
            ),
        ], style=_CARD),

        # 4.4 Reservas de divisas globales
        create_section_header(
            "4.4 — Composicion de Reservas de Divisas Globales",
            subtitle="FMI COFER · tendencia de desdolarizacion desde 2000",
        ),
        html.Div([
            dcc.Graph(id="m9-reserves-chart", config={"displayModeBar": False}),
            html.Div(
                "La desdolarizacion gradual de las reservas globales reduce la demanda "
                "estructural de deuda americana. Sin embargo, no hay alternativa creible "
                "al dolar como moneda de reserva dominante en el corto o medio plazo.",
                style=_NOTE,
            ),
        ], style=_CARD),

    ], style=_SECTION)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — LECCIONES DEL 2008
# ══════════════════════════════════════════════════════════════════════════════

def _build_tab5() -> html.Div:
    return html.Div([
        # 5.1 El Radar del 2008
        create_section_header(
            "5.1 — El Radar del 2008: Perfil de Riesgo Comparado",
            subtitle="2007 (pre-crisis) · 2008-2009 (pico crisis) · 2026 (actual)",
        ),
        html.Div([
            dcc.Graph(id="m9-radar-chart", config={"displayModeBar": False}),
            html.Div(id="m9-radar-interpretation"),
        ], style=_CARD),

        # 5.2 Cronologia del 2008
        create_section_header(
            "5.2 — Cronologia del 2008: Las Senales que Nadie Vio",
            subtitle="Indicadores clave en cada momento de la crisis",
        ),
        html.Div([
            _build_crisis_timeline(),
        ], style=_CARD),

        # 5.3 Diferencias con 2007
        create_section_header(
            "5.3 — Que es Diferente Ahora vs 2007",
            subtitle="Factores de mas y menos seguridad respecto a la crisis financiera",
        ),
        html.Div([
            _build_comparison_2007(),
        ], style=_CARD),

    ], style=_SECTION)


def _build_crisis_timeline() -> html.Div:
    """Timeline narrativa de la crisis de 2008."""
    events = [
        {
            "date": "Feb 2007",
            "event": "HSBC anuncia perdidas hipotecarias masivas",
            "hy": 280, "vix": 12,
            "color": COLORS["green_yellow"],
        },
        {
            "date": "Jun 2007",
            "event": "Bear Stearns: colapso de fondos hedge hipotecarios",
            "hy": 350, "vix": 16,
            "color": COLORS["yellow"],
        },
        {
            "date": "Ago 2007",
            "event": "Crisis de liquidez interbancaria: LIBOR-OIS dispara a 90pb",
            "hy": 450, "vix": 25,
            "color": COLORS["orange"],
        },
        {
            "date": "Mar 2008",
            "event": "Rescate de Bear Stearns por JPMorgan (Fed backstop)",
            "hy": 750, "vix": 30,
            "color": COLORS["orange"],
        },
        {
            "date": "Sep 2008",
            "event": "Quiebra de Lehman Brothers",
            "hy": 1500, "vix": 80,
            "color": COLORS["red"],
        },
        {
            "date": "Oct 2008",
            "event": "Pico de la crisis: colapso sistemico global",
            "hy": 2000, "vix": 89,
            "color": COLORS["red"],
        },
    ]

    items = []
    for ev in events:
        items.append(
            html.Div([
                html.Div([
                    html.Div(ev["date"], style={
                        "fontSize": "0.72rem", "fontWeight": "700",
                        "color": ev["color"], "marginBottom": "2px",
                    }),
                    html.Div(ev["event"], style={
                        "fontSize": "0.80rem", "color": COLORS["text"], "marginBottom": "4px",
                    }),
                    html.Div([
                        html.Span(f"HY Spread: {ev['hy']}pb", style={
                            "fontSize": "0.68rem", "color": COLORS["text_muted"],
                            "marginRight": "12px",
                        }),
                        html.Span(f"VIX: {ev['vix']}", style={
                            "fontSize": "0.68rem", "color": COLORS["text_muted"],
                        }),
                    ]),
                ], style={
                    "borderLeft": f"3px solid {ev['color']}",
                    "paddingLeft": "12px",
                    "marginBottom": "14px",
                }),
            ])
        )

    # Comparativa con niveles actuales
    hy_curr = calculate_hy_spread_proxy()
    vix_curr, _ = get_latest_value(ID_VIX)

    items.append(html.Hr(style={"borderColor": COLORS["border"], "margin": "8px 0"}))
    items.append(html.Div([
        html.Div("NIVELES ACTUALES (2026)", style={
            "fontSize": "0.72rem", "fontWeight": "700",
            "color": COLORS["accent"], "marginBottom": "6px",
        }),
        html.Div([
            html.Span(
                f"HY Spread: {_safe(hy_curr, '.0f')} pb",
                style={"fontSize": "0.78rem", "color": COLORS["text"], "marginRight": "16px"},
            ),
            html.Span(
                f"VIX: {_safe(vix_curr, '.1f')}",
                style={"fontSize": "0.78rem", "color": COLORS["text"]},
            ),
        ]),
        html.Div(
            "En 2007, muchos de estos indicadores ya mostraban senales de alerta meses "
            "antes del colapso de Lehman. Quienes los monitorizaban pudieron protegerse. "
            "El objetivo de este modulo es que nunca te pille desprevenido.",
            style={**_NOTE, "marginTop": "12px"},
        ),
    ]))

    return html.Div(items)


def _build_comparison_2007() -> html.Div:
    """Panel de dos columnas: mas seguro / mas peligroso vs 2007."""
    safer = [
        "Bancos con mucho mas capital (CET1 ~13-16% vs ~8% en 2007)",
        "Regulacion mas estricta: Dodd Frank y Basilea III",
        "Menos apalancamiento en el sistema bancario regulado",
        "Los bancos centrales conocen las herramientas de emergencia (QE, backstops)",
        "No hay burbuja obvia en el mercado hipotecario americano de magnitud 2006",
    ]
    riskier = [
        "Deuda soberana global mucho mas alta (menos espacio fiscal para rescates)",
        "Los bancos centrales ya tienen balances enormes (menos municion de QE)",
        "Tipos de interes mas altos hacen mas fragiles a los deudores",
        "El shadow banking (sector financiero no regulado) ha crecido enormemente",
        "La interconexion financiera global es mayor aun",
        "La geopolitica anade un vector de riesgo que no existia en 2007",
    ]

    def _col(items: list, title: str, color: str, bg: str) -> dbc.Col:
        return dbc.Col([
            html.Div([
                html.Div(title, style={
                    "fontSize": "0.78rem", "fontWeight": "700",
                    "color": color, "marginBottom": "10px",
                    "borderBottom": f"1px solid {color}40",
                    "paddingBottom": "6px",
                }),
                *[
                    html.Div([
                        html.Span("✓ " if color == COLORS["green"] else "⚠ ", style={"color": color}),
                        html.Span(item, style={"fontSize": "0.78rem", "color": COLORS["text"]}),
                    ], style={"marginBottom": "8px", "display": "flex", "gap": "4px"})
                    for item in items
                ],
            ], style={
                "background": bg,
                "border": f"1px solid {color}30",
                "borderRadius": "6px",
                "padding": "14px 16px",
            }),
        ], width=12, lg=6)

    return dbc.Row([
        _col(safer, "MAS SEGURO QUE EN 2007", COLORS["green"], "#0a1a0f"),
        _col(riskier, "MAS PELIGROSO QUE EN 2007", COLORS["orange"], "#1a0e05"),
    ], className="g-3")


# ══════════════════════════════════════════════════════════════════════════════
# RENDER PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

def render_module_9() -> html.Div:
    return html.Div([
        # Cabecera del modulo
        html.Div([
            html.Div("🏦 Sistema Financiero y Riesgo Sistemico", className="module-title"),
            html.Div(
                "Estres financiero · Salud bancaria · Credito corporativo · Flujos de capital · Lecciones del 2008",
                className="module-subtitle",
            ),
        ]),

        # Fila de metricas
        html.Div(id="m9-header-metrics", children=_build_header_metrics()),

        # Tabs
        dcc.Tabs(
            id="m9-tabs",
            value="tab1",
            children=[
                dcc.Tab(label="Panel de Estres", value="tab1",
                        style=TAB_STYLE, selected_style=TAB_SELECTED_STYLE),
                dcc.Tab(label="Salud Bancaria", value="tab2",
                        style=TAB_STYLE, selected_style=TAB_SELECTED_STYLE),
                dcc.Tab(label="Mercados de Credito", value="tab3",
                        style=TAB_STYLE, selected_style=TAB_SELECTED_STYLE),
                dcc.Tab(label="Flujos de Capital", value="tab4",
                        style=TAB_STYLE, selected_style=TAB_SELECTED_STYLE),
                dcc.Tab(label="Lecciones del 2008", value="tab5",
                        style=TAB_STYLE, selected_style=TAB_SELECTED_STYLE),
            ],
            style=TABS_STYLE,
        ),

        html.Div(id="m9-tab-content"),

        # Interval de refresco global cada 300 segundos
        dcc.Interval(id="m9-interval", interval=300_000, n_intervals=0),
    ])


# ══════════════════════════════════════════════════════════════════════════════
# CALLBACKS
# ══════════════════════════════════════════════════════════════════════════════

def register_callbacks_module_9(app) -> None:

    # ── Routing de tabs ───────────────────────────────────────────────────────

    @app.callback(
        Output("m9-tab-content", "children"),
        Input("m9-tabs", "value"),
    )
    def render_tab(tab):
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
        return html.Div()

    # ── Tab 1: Gauge de riesgo sistemico ─────────────────────────────────────

    @app.callback(
        Output("m9-risk-gauge", "figure"),
        Output("m9-risk-components-table", "children"),
        Input("m9-interval", "n_intervals"),
        Input("m9-tabs", "value"),
    )
    def update_risk_gauge(_, tab):
        if tab != "tab1":
            return no_update, no_update

        risk = calculate_systemic_risk_index()
        indice = risk.get("indice_compuesto")
        nivel = risk.get("nivel", "gray")
        componentes = risk.get("componentes", [])

        nivel_txt, nivel_color = _nivel_label(nivel)

        # Gauge figure
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=indice if indice is not None else 0,
            number={"suffix": "", "font": {"size": 36, "color": nivel_color}},
            gauge={
                "axis": {
                    "range": [0, 100],
                    "tickwidth": 1,
                    "tickcolor": COLORS["text_muted"],
                    "tickfont": {"size": 10, "color": COLORS["text_muted"]},
                },
                "bar": {"color": nivel_color, "thickness": 0.25},
                "bgcolor": COLORS["card_bg"],
                "borderwidth": 0,
                "steps": [
                    {"range": [0, 25],   "color": _rgba(COLORS["green"], 0.25)},
                    {"range": [25, 50],  "color": _rgba(COLORS["green_yellow"], 0.25)},
                    {"range": [50, 65],  "color": _rgba(COLORS["yellow"], 0.25)},
                    {"range": [65, 80],  "color": _rgba(COLORS["orange"], 0.25)},
                    {"range": [80, 100], "color": _rgba(COLORS["red"], 0.25)},
                ],
                "threshold": {
                    "line": {"color": nivel_color, "width": 3},
                    "thickness": 0.8,
                    "value": indice if indice is not None else 0,
                },
            },
            title={
                "text": (
                    f"<b>INDICE DE RIESGO SISTEMICO</b><br>"
                    f"<span style='font-size:14px;color:{nivel_color}'>{nivel_txt}</span>"
                ),
                "font": {"size": 14, "color": COLORS["text"]},
            },
        ))
        gauge_layout = get_base_layout(height=320)
        gauge_layout["margin"] = {"l": 20, "r": 20, "t": 60, "b": 20}
        fig.update_layout(**gauge_layout)

        # Tabla de componentes
        if not componentes:
            comp_table = html.Div("Sin datos suficientes para calcular el indice.", style={"color": COLORS["text_muted"], "fontSize": "0.82rem", "padding": "20px"})
        else:
            rows = []
            for c in componentes:
                norm_val = c.get("valor_normalizado")
                contrib = c.get("contribucion")
                raw = c.get("valor_raw")
                peso = c.get("peso_final_pct", 0)
                unit = c.get("unit", "")

                raw_str = "—"
                if raw is not None:
                    if unit == "pb":
                        raw_str = f"{raw:.0f} pb"
                    else:
                        raw_str = f"{raw:.2f}"

                norm_color = COLORS["green"]
                if norm_val is not None:
                    if norm_val > 65:
                        norm_color = COLORS["red"]
                    elif norm_val > 50:
                        norm_color = COLORS["orange"]
                    elif norm_val > 25:
                        norm_color = COLORS["yellow"]

                rows.append(html.Tr([
                    html.Td(c["nombre"], style={"fontSize": "0.76rem", "color": COLORS["text"], "padding": "5px 8px"}),
                    html.Td(raw_str, style={"fontSize": "0.76rem", "color": COLORS["text_muted"], "padding": "5px 8px", "textAlign": "right"}),
                    html.Td(
                        f"{norm_val:.0f}" if norm_val is not None else "—",
                        style={"fontSize": "0.80rem", "fontWeight": "600", "color": norm_color, "padding": "5px 8px", "textAlign": "right"},
                    ),
                    html.Td(f"{peso:.0f}%", style={"fontSize": "0.72rem", "color": COLORS["text_muted"], "padding": "5px 8px", "textAlign": "right"}),
                    html.Td(
                        f"{contrib:.1f}" if contrib is not None else "—",
                        style={"fontSize": "0.78rem", "color": nivel_color, "padding": "5px 8px", "textAlign": "right"},
                    ),
                ]))

            comp_table = html.Div([
                html.Div(
                    f"Indice Compuesto: {_safe(indice, '.1f')} / 100",
                    style={"fontSize": "0.85rem", "fontWeight": "700", "color": nivel_color, "marginBottom": "8px"},
                ),
                html.Table([
                    html.Thead(html.Tr([
                        html.Th("Componente", style={"fontSize": "0.68rem", "color": COLORS["text_label"], "padding": "4px 8px", "fontWeight": "600"}),
                        html.Th("Valor", style={"fontSize": "0.68rem", "color": COLORS["text_label"], "padding": "4px 8px", "textAlign": "right"}),
                        html.Th("Norm (0-100)", style={"fontSize": "0.68rem", "color": COLORS["text_label"], "padding": "4px 8px", "textAlign": "right"}),
                        html.Th("Peso", style={"fontSize": "0.68rem", "color": COLORS["text_label"], "padding": "4px 8px", "textAlign": "right"}),
                        html.Th("Contribucion", style={"fontSize": "0.68rem", "color": COLORS["text_label"], "padding": "4px 8px", "textAlign": "right"}),
                    ])),
                    html.Tbody(rows),
                ], style={"width": "100%", "borderCollapse": "collapse"}),
                html.Div(
                    "Zonas: 0-25 VERDE (sano) · 25-50 AMARILLO-VERDE (tension leve) · "
                    "50-65 AMARILLO (moderado) · 65-80 NARANJA (elevado) · 80-100 ROJO (sistemico)",
                    style={**_NOTE, "marginTop": "12px"},
                ),
            ])

        return fig, comp_table

    # ── Tab 1: STLFSI4 historico ──────────────────────────────────────────────

    @app.callback(
        Output("m9-stlfsi-chart", "figure"),
        Input("m9-interval", "n_intervals"),
        Input("m9-tabs", "value"),
    )
    def update_stlfsi(_, tab):
        if tab != "tab1":
            return no_update

        df = get_series(ID_STLFSI4, days=365 * 26)
        if df.empty:
            return _empty_fig("Sin datos STLFSI4 — ejecutar colector FRED")

        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values("timestamp")

        # Separar en zonas por color
        fig = go.Figure()

        # Zona negativa (verde)
        df_neg = df.copy()
        df_neg["value_neg"] = df_neg["value"].clip(upper=0)
        fig.add_trace(go.Scatter(
            x=df_neg["timestamp"], y=df_neg["value_neg"],
            fill="tozeroy", fillcolor=_rgba(COLORS["green"], 0.20),
            line={"color": COLORS["green"], "width": 1},
            name="< 0 (condiciones faciles)", showlegend=True,
        ))

        # Zona 0-1 (azul/normal)
        df_01 = df.copy()
        df_01["v"] = df_01["value"].clip(lower=0, upper=1)
        fig.add_trace(go.Scatter(
            x=df_01["timestamp"], y=df_01["v"],
            fill="tozeroy", fillcolor=_rgba(COLORS["accent"], 0.20),
            line={"color": COLORS["accent"], "width": 0.5},
            name="0-1 (normal)", showlegend=True,
        ))

        # Zona 1-2 (naranja)
        df_12 = df.copy()
        df_12["v"] = df_12["value"].clip(lower=1, upper=2) - 1
        mask = df_12["value"] > 1
        if mask.any():
            fig.add_trace(go.Scatter(
                x=df_12.loc[mask, "timestamp"], y=df_12.loc[mask, "v"],
                fill="tozeroy", fillcolor=_rgba(COLORS["orange"], 0.25),
                line={"color": COLORS["orange"], "width": 1},
                name="1-2 (estres moderado)", showlegend=True,
            ))

        # Zona > 2 (rojo)
        df_2p = df.copy()
        df_2p["v"] = df_2p["value"].clip(lower=2) - 2
        mask2 = df_2p["value"] > 2
        if mask2.any():
            fig.add_trace(go.Scatter(
                x=df_2p.loc[mask2, "timestamp"], y=df_2p.loc[mask2, "v"],
                fill="tozeroy", fillcolor=_rgba(COLORS["red"], 0.30),
                line={"color": COLORS["red"], "width": 1},
                name="> 2 (estres severo)", showlegend=True,
            ))

        # Linea principal
        fig.add_trace(go.Scatter(
            x=df["timestamp"], y=df["value"],
            line={"color": COLORS["text"], "width": 1.5},
            name="STLFSI4",
            hovertemplate="%{x|%b %Y}: <b>%{y:.2f}</b><extra></extra>",
        ))

        # Lineas de referencia
        for val, label, color in [(0, "0 (neutral)", COLORS["text_muted"]), (1, "1 (atencion)", COLORS["orange"]), (2, "2 (crisis)", COLORS["red"])]:
            fig.add_hline(y=val, line_dash="dot", line_color=color, line_width=1,
                          annotation_text=label, annotation_position="right",
                          annotation_font_color=color, annotation_font_size=10)

        # Anotaciones en picos historicos
        annotations = [
            {"x": "2008-10-15", "y": 8.5,  "text": "Crisis 2008<br>~9.0", "color": COLORS["red"]},
            {"x": "2020-03-20", "y": 5.5,  "text": "COVID Mar 2020<br>~6.0", "color": COLORS["orange"]},
            {"x": "2023-03-15", "y": 1.8,  "text": "Crisis SVB 2023<br>~1.5", "color": COLORS["yellow"]},
        ]
        for ann in annotations:
            try:
                fig.add_annotation(
                    x=ann["x"], y=ann["y"],
                    text=ann["text"],
                    showarrow=True, arrowhead=2, arrowcolor=ann["color"],
                    font={"color": ann["color"], "size": 9},
                    ax=0, ay=-40,
                )
            except Exception:
                pass

        layout = get_base_layout(height=380, title="STLFSI4 — Indice de Estres Financiero (Fed St. Louis)")
        layout["xaxis"] = {**layout.get("xaxis", {}), "rangeselector": get_time_range_buttons()}
        layout["yaxis"] = {**layout.get("yaxis", {}), "title": {"text": "STLFSI4"}}
        layout["legend"] = {"orientation": "h", "y": -0.12, "font": {"size": 10}}
        fig.update_layout(**layout)

        return fig

    # ── Tab 1: SOFR historico ─────────────────────────────────────────────────

    @app.callback(
        Output("m9-sofr-chart", "figure"),
        Output("m9-sofr-interpretation", "children"),
        Input("m9-interval", "n_intervals"),
        Input("m9-tabs", "value"),
    )
    def update_sofr(_, tab):
        if tab != "tab1":
            return no_update, no_update

        df = get_series(ID_SOFR, days=365 * 4)
        sofr_val, _ = get_latest_value(ID_SOFR)

        if df.empty:
            fig = _empty_fig("Sin datos SOFR — ejecutar colector FRED")
            interp = html.Div()
        else:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.sort_values("timestamp")

            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=df["timestamp"], y=df["value"],
                fill="tozeroy",
                fillcolor=_rgba(COLORS["accent"], 0.15),
                line={"color": COLORS["accent"], "width": 2},
                name="SOFR",
                hovertemplate="%{x|%d %b %Y}: <b>%{y:.4f}%</b><extra></extra>",
            ))

            layout = get_base_layout(height=300, title="SOFR — Secured Overnight Financing Rate")
            layout["yaxis"] = {**layout.get("yaxis", {}), "title": {"text": "% anual"}}
            layout["xaxis"] = {**layout.get("xaxis", {}), "rangeselector": get_time_range_buttons()}
            fig.update_layout(**layout)

            level_text = "nivel normal"
            level_color = COLORS["accent"]
            if sofr_val is not None:
                if sofr_val > 5:
                    level_text = "nivel alto — presion sobre deudores"
                    level_color = COLORS["orange"]
                elif sofr_val > 4:
                    level_text = "nivel elevado"
                    level_color = COLORS["yellow"]

            interp = html.Div(
                f"SOFR actual: {_safe(sofr_val, '.4f')}% — {level_text}",
                style={"fontSize": "0.78rem", "color": level_color, "marginTop": "8px"},
            )

        return fig, interp

    # ── Tab 1: Heatmap de correlaciones ──────────────────────────────────────

    @app.callback(
        Output("m9-correlation-heatmap", "figure"),
        Output("m9-correlation-interpretation", "children"),
        Input("m9-interval", "n_intervals"),
        Input("m9-tabs", "value"),
    )
    def update_correlation(_, tab):
        if tab != "tab1":
            return no_update, no_update

        assets = {
            "S&P500": "yf_spy_close",
            "HYG":    "yf_hyg_close",
            "LQD":    "yf_lqd_close",
            "EMB":    "yf_emb_close",
            "Oro":    "yf_gc_close",
            "DXY":    "yf_dxy_close",
        }

        dfs = {}
        for label, sid in assets.items():
            df = get_series(sid, days=90)
            if not df.empty:
                df["timestamp"] = pd.to_datetime(df["timestamp"])
                df = df.set_index("timestamp")["value"].rename(label)
                dfs[label] = df

        if len(dfs) < 3:
            return _empty_fig("Sin datos suficientes para calcular correlaciones (90 dias)"), html.Div()

        combined = pd.DataFrame(dfs)
        combined = combined.dropna(how="all")
        combined = combined.ffill().dropna()

        if combined.empty or len(combined) < 10:
            return _empty_fig("Datos insuficientes para correlaciones"), html.Div()

        # DXY invertido para interpretacion (DXY sube → risk off → invertir para ver risk appetite)
        corr = combined.corr()

        labels = list(corr.columns)
        z = corr.values.tolist()

        fig = go.Figure(go.Heatmap(
            z=z,
            x=labels,
            y=labels,
            colorscale=[
                [0.0, _rgba(COLORS["red"], 1)],
                [0.5, _rgba(COLORS["text_muted"], 1)],
                [1.0, _rgba(COLORS["green"], 1)],
            ],
            zmin=-1, zmax=1,
            text=[[f"{v:.2f}" for v in row] for row in z],
            texttemplate="%{text}",
            textfont={"size": 11},
            hovertemplate="%{x} vs %{y}: <b>%{z:.3f}</b><extra></extra>",
            colorbar={"title": "Corr", "titlefont": {"size": 10}, "tickfont": {"size": 10}},
        ))

        layout = get_base_layout(height=380, title="Correlacion de Activos (ultimos 90 dias)")
        layout["margin"] = {"l": 60, "r": 20, "t": 50, "b": 60}
        fig.update_layout(**layout)

        # Interpretacion automatica
        off_diag = []
        for i in range(len(labels)):
            for j in range(i + 1, len(labels)):
                off_diag.append(corr.values[i][j])
        avg_corr = sum(off_diag) / len(off_diag) if off_diag else 0

        if avg_corr > 0.6:
            interp_text = "Las correlaciones actuales entre activos son ALTAS, indicando un entorno de mercado risk-off."
            interp_color = COLORS["red"]
        elif avg_corr > 0.3:
            interp_text = "Las correlaciones actuales entre activos son MODERADAS, indicando un entorno algo estresado."
            interp_color = COLORS["orange"]
        else:
            interp_text = "Las correlaciones actuales entre activos son BAJAS, indicando un entorno de mercado normal."
            interp_color = COLORS["green"]

        interp = html.Div(interp_text, style={"fontSize": "0.78rem", "color": interp_color, "marginTop": "8px"})

        return fig, interp

    # ── Tab 2: Tabla de bancos ────────────────────────────────────────────────

    @app.callback(
        Output("m9-banks-table", "children"),
        Input("m9-interval", "n_intervals"),
        Input("m9-tabs", "value"),
    )
    def update_banks_table(_, tab):
        if tab != "tab2":
            return no_update

        fundamentals = load_json_data("bank_fundamentals.json") or {}
        banks_data = fundamentals.get("banks", {})

        bank_tickers = {
            "JPM":     "yf_jpm_close",
            "BAC":     "yf_bac_close",
            "C":       "yf_c_close",
            "GS":      "yf_gs_close",
            "WFC":     "yf_wfc_close",
            "MS":      "yf_ms_close",
            "DB":      "yf_db_close",
            "BNP.PA":  "yf_bnp.pa_close",
            "SAN.MC":  "yf_san.mc_close",
            "BBVA.MC": "yf_bbva.mc_close",
            "HSBA.L":  "yf_hsba.l_close",
            "UBSG.SW": "yf_ubsg.sw_close",
            "BARC.L":  "yf_barc.l_close",
            "UCG.MI":  "yf_ucg.mi_close",
        }

        rows = []
        for ticker, series_id in bank_tickers.items():
            fund = banks_data.get(ticker, {})
            flag = _BANK_FLAGS.get(fund.get("flag", ""), "🏳")
            name = fund.get("name", ticker)

            curr, prev, abs_ch, pct_ch = get_change(series_id, period_days=1)
            curr_yr, prev_yr, _, pct_yr = get_change(series_id, period_days=365)

            cet1 = fund.get("cet1_pct")
            npl = fund.get("npl_pct")
            roe = fund.get("roe_pct")
            shares = fund.get("shares_bn")

            # Capitalización bursatil aproximada
            mktcap_str = "—"
            if curr is not None and shares is not None:
                mktcap_bn = (curr * shares * 1e9) / 1e9  # en billones
                if mktcap_bn > 1000:
                    mktcap_str = f"{mktcap_bn / 1000:.1f}T"
                else:
                    mktcap_str = f"{mktcap_bn:.0f}B"

            # Semaforo de salud
            health_color = COLORS["text_muted"]
            health_label = "?"
            if pct_yr is not None and cet1 is not None:
                if pct_yr > 0 and cet1 > 12:
                    health_color = COLORS["green"]
                    health_label = "SANO"
                elif pct_yr < -40 or (cet1 is not None and cet1 < 10):
                    health_color = COLORS["red"]
                    health_label = "CRITICO"
                elif pct_yr < -20 or (cet1 is not None and cet1 < 11):
                    health_color = COLORS["orange"]
                    health_label = "TENSION"
                else:
                    health_color = COLORS["yellow"]
                    health_label = "CAUTELA"

            pct_color = _chg_color(pct_ch, higher_bad=False)
            pct_yr_color = _chg_color(pct_yr, higher_bad=False)

            rows.append(html.Tr([
                html.Td([html.Span(flag + " ", style={"fontSize": "1rem"}),
                         html.Span(f"{name}", style={"fontSize": "0.78rem", "color": COLORS["text"]})],
                        style={"padding": "6px 8px", "whiteSpace": "nowrap"}),
                html.Td(f"{_safe(curr, '.2f')}", style={"fontSize": "0.78rem", "padding": "6px 8px", "textAlign": "right"}),
                html.Td(
                    html.Span(f"{'+' if pct_ch and pct_ch > 0 else ''}{_safe(pct_ch, '.2f')}%"),
                    style={"fontSize": "0.78rem", "color": pct_color, "padding": "6px 8px", "textAlign": "right"},
                ),
                html.Td(
                    html.Span(f"{'+' if pct_yr and pct_yr > 0 else ''}{_safe(pct_yr, '.1f')}%"),
                    style={"fontSize": "0.78rem", "color": pct_yr_color, "padding": "6px 8px", "textAlign": "right"},
                ),
                html.Td(mktcap_str, style={"fontSize": "0.76rem", "color": COLORS["text_muted"], "padding": "6px 8px", "textAlign": "right"}),
                html.Td(f"{_safe(cet1, '.1f')}%" if cet1 else "—",
                        style={"fontSize": "0.76rem", "padding": "6px 8px", "textAlign": "right"}),
                html.Td(f"{_safe(npl, '.1f')}%" if npl else "—",
                        style={"fontSize": "0.76rem", "color": COLORS["orange"] if (npl and npl > 3) else COLORS["text_muted"],
                               "padding": "6px 8px", "textAlign": "right"}),
                html.Td(f"{_safe(roe, '.1f')}%" if roe else "—",
                        style={"fontSize": "0.76rem", "padding": "6px 8px", "textAlign": "right"}),
                html.Td(
                    html.Span(health_label, style={
                        "fontSize": "0.65rem", "fontWeight": "700",
                        "color": health_color,
                        "background": _rgba(health_color, 0.15),
                        "padding": "2px 7px", "borderRadius": "4px",
                        "border": f"1px solid {health_color}40",
                    }),
                    style={"padding": "6px 8px", "textAlign": "center"},
                ),
            ]))

        if not rows:
            return html.Div("Sin datos bancarios — ejecutar colector Yahoo Finance", style={"color": COLORS["text_muted"], "padding": "16px"})

        headers = ["Banco", "Precio", "Var 24h", "Var 1A", "Mkt Cap", "CET1 %", "NPL %", "ROE %", "Salud"]
        th_row = html.Tr([
            html.Th(h, style={"fontSize": "0.68rem", "color": COLORS["text_label"],
                               "padding": "6px 8px", "fontWeight": "600",
                               "textAlign": "right" if h not in ("Banco", "Salud") else "left"})
            for h in headers
        ])

        return html.Div(
            html.Table(
                [html.Thead(th_row, style={"borderBottom": f"1px solid {COLORS['border']}"}),
                 html.Tbody(rows)],
                style={"width": "100%", "borderCollapse": "collapse"},
            ),
            style={"overflowX": "auto"},
        )

    # ── Tab 2: Grafico comparativo bancos ─────────────────────────────────────

    @app.callback(
        Output("m9-bank-performance-chart", "figure"),
        Input("m9-bank-selector", "value"),
        Input("m9-bank-period", "value"),
        Input("m9-interval", "n_intervals"),
    )
    def update_bank_chart(selected_series, period_days, _):
        if not selected_series:
            return _empty_fig("Selecciona al menos un banco")

        labels = {
            "yf_jpm_close":     "JPMorgan",
            "yf_bac_close":     "Bank of America",
            "yf_c_close":       "Citigroup",
            "yf_gs_close":      "Goldman Sachs",
            "yf_wfc_close":     "Wells Fargo",
            "yf_ms_close":      "Morgan Stanley",
            "yf_db_close":      "Deutsche Bank",
            "yf_bnp.pa_close":  "BNP Paribas",
            "yf_san.mc_close":  "Santander",
            "yf_bbva.mc_close": "BBVA",
            "yf_hsba.l_close":  "HSBC",
            "yf_ubsg.sw_close": "UBS",
            "yf_barc.l_close":  "Barclays",
            "yf_ucg.mi_close":  "UniCredit",
        }
        palette = [
            COLORS["accent"], COLORS["green"], COLORS["orange"], COLORS["yellow"],
            "#8b5cf6", "#ec4899", "#06b6d4", "#f97316",
        ]

        fig = go.Figure()
        for i, sid in enumerate(selected_series):
            df = get_series(sid, days=period_days + 10)
            if df.empty:
                continue
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.sort_values("timestamp").tail(period_days + 5)
            if len(df) < 2:
                continue

            base_val = float(df.iloc[0]["value"])
            if base_val == 0:
                continue
            df["norm"] = (df["value"] / base_val) * 100

            # Calcular caida anual para resaltar en rojo
            curr_val = float(df.iloc[-1]["value"])
            pct_1y = ((curr_val / base_val) - 1) * 100
            line_color = COLORS["red"] if pct_1y < -30 else palette[i % len(palette)]
            line_width = 2.5 if pct_1y < -30 else 1.5

            fig.add_trace(go.Scatter(
                x=df["timestamp"], y=df["norm"],
                name=labels.get(sid, sid),
                line={"color": line_color, "width": line_width},
                hovertemplate=f"{labels.get(sid, sid)}: <b>%{{y:.1f}}</b><extra></extra>",
            ))

        fig.add_hline(y=100, line_dash="dot", line_color=COLORS["text_muted"], line_width=1)

        layout = get_base_layout(height=380, title=f"Rendimiento Bancario Normalizado (Base 100, ultimos {period_days} dias)")
        layout["yaxis"] = {**layout.get("yaxis", {}), "title": {"text": "Rendimiento (Base 100)"}}
        layout["legend"] = {"orientation": "h", "y": -0.15, "font": {"size": 10}}
        fig.update_layout(**layout)
        return fig

    # ── Tab 2: Stress tests ───────────────────────────────────────────────────

    @app.callback(
        Output("m9-stress-tests-panel", "children"),
        Input("m9-tabs", "value"),
    )
    def update_stress_tests(tab):
        if tab != "tab2":
            return no_update

        data = load_json_data("stress_tests.json") or {}
        panels = []
        for key, test in data.items():
            if not isinstance(test, dict):
                continue
            passed = test.get("all_passed", False)
            color = COLORS["green"] if passed else COLORS["red"]
            label = "TODOS APROBARON" if passed else "HUBO SUSPENSOS"
            panels.append(html.Div([
                html.Div([
                    html.Span(test.get("source", key), style={"fontSize": "0.82rem", "fontWeight": "700", "color": COLORS["text"]}),
                    html.Span(" · " + test.get("published", ""), style={"fontSize": "0.72rem", "color": COLORS["text_muted"]}),
                    html.Span(label, style={
                        "fontSize": "0.65rem", "fontWeight": "700", "color": color,
                        "background": _rgba(color, 0.15), "padding": "2px 8px",
                        "borderRadius": "4px", "marginLeft": "8px",
                        "border": f"1px solid {color}40",
                    }),
                ], style={"marginBottom": "6px"}),
                html.Div(f"Escenario: {test.get('scenario', '—')}", style={"fontSize": "0.75rem", "color": COLORS["text_muted"], "marginBottom": "4px"}),
                html.Div([
                    html.Span(f"Bancos testados: {test.get('banks_tested', '—')}", style={"fontSize": "0.75rem", "color": COLORS["text_muted"], "marginRight": "16px"}),
                    html.Span(f"CET1 minimo post-estres: {test.get('minimum_cet1_post_stress', '—')}%", style={"fontSize": "0.75rem", "color": COLORS["accent"]}),
                ]),
            ], style={**_CARD, "marginBottom": "8px"}))

        return html.Div(panels) if panels else html.Div("Sin datos de stress tests", style={"color": COLORS["text_muted"]})

    # ── Tab 3: Spreads de credito historico ───────────────────────────────────

    @app.callback(
        Output("m9-credit-spreads-chart", "figure"),
        Output("m9-credit-interpretation", "children"),
        Input("m9-credit-period", "value"),
        Input("m9-interval", "n_intervals"),
    )
    def update_credit_spreads(period_days, _):
        days = period_days or 730

        hyg_df = get_series(ID_HYG, days=days + 30)
        ief_df = get_series(ID_IEF, days=days + 30)
        lqd_df = get_series(ID_LQD, days=days + 30)

        CUPON_HYG = 4.5
        CUPON_IEF = 2.5
        CUPON_LQD = 3.0

        fig = go.Figure()
        hy_curr_spread = None
        ig_curr_spread = None

        if not hyg_df.empty and not ief_df.empty:
            hyg_df["timestamp"] = pd.to_datetime(hyg_df["timestamp"])
            ief_df["timestamp"] = pd.to_datetime(ief_df["timestamp"])
            merged = pd.merge_asof(
                hyg_df.sort_values("timestamp").rename(columns={"value": "hyg"}),
                ief_df.sort_values("timestamp").rename(columns={"value": "ief"}),
                on="timestamp", direction="nearest",
            )
            merged = merged.dropna()
            if not merged.empty:
                merged["hy_spread"] = ((CUPON_HYG / merged["hyg"]) - (CUPON_IEF / merged["ief"])) * 10000  # en pb
                merged["hy_spread"] = merged["hy_spread"].clip(lower=0, upper=3000)
                hy_curr_spread = float(merged["hy_spread"].iloc[-1]) if len(merged) > 0 else None

                fig.add_trace(go.Scatter(
                    x=merged["timestamp"], y=merged["hy_spread"],
                    name="Spread HY (pb)",
                    line={"color": COLORS["red"], "width": 1.8},
                    fill="tozeroy", fillcolor=_rgba(COLORS["red"], 0.08),
                    hovertemplate="HY Spread: <b>%{y:.0f} pb</b><extra></extra>",
                ))

        if not lqd_df.empty and not ief_df.empty:
            lqd_df["timestamp"] = pd.to_datetime(lqd_df["timestamp"])
            ief_df["timestamp"] = pd.to_datetime(ief_df["timestamp"])
            merged2 = pd.merge_asof(
                lqd_df.sort_values("timestamp").rename(columns={"value": "lqd"}),
                ief_df.sort_values("timestamp").rename(columns={"value": "ief"}),
                on="timestamp", direction="nearest",
            )
            merged2 = merged2.dropna()
            if not merged2.empty:
                merged2["ig_spread"] = ((CUPON_LQD / merged2["lqd"]) - (CUPON_IEF / merged2["ief"])) * 10000
                merged2["ig_spread"] = merged2["ig_spread"].clip(lower=0, upper=800)
                ig_curr_spread = float(merged2["ig_spread"].iloc[-1]) if len(merged2) > 0 else None

                fig.add_trace(go.Scatter(
                    x=merged2["timestamp"], y=merged2["ig_spread"],
                    name="Spread IG (pb)",
                    line={"color": COLORS["accent"], "width": 1.5},
                    hovertemplate="IG Spread: <b>%{y:.0f} pb</b><extra></extra>",
                ))

        if not fig.data:
            return _empty_fig("Sin datos HYG/LQD/IEF — ejecutar colector Yahoo Finance"), html.Div()

        # Lineas de referencia HY
        for val, label, color in [
            (300, "HY 300pb (normal)", COLORS["green"]),
            (500, "HY 500pb (tension)", COLORS["yellow"]),
            (700, "HY 700pb (estres)", COLORS["orange"]),
        ]:
            fig.add_hline(y=val, line_dash="dot", line_color=color, line_width=0.8,
                          annotation_text=label, annotation_position="right",
                          annotation_font_color=color, annotation_font_size=9)

        layout = get_base_layout(height=380, title="Spreads de Credito Corporativo (Proxy)")
        layout["yaxis"] = {**layout.get("yaxis", {}), "title": {"text": "Puntos Basicos (pb)"}}
        layout["legend"] = {"orientation": "h", "y": -0.15, "font": {"size": 10}}
        fig.update_layout(**layout)

        # Interpretacion
        if hy_curr_spread is not None:
            if hy_curr_spread < 300:
                txt = f"El spread HY actual de ~{hy_curr_spread:.0f}pb indica condiciones de credito laxas — mercado optimista."
                col = COLORS["green"]
            elif hy_curr_spread < 500:
                txt = f"El spread HY actual de ~{hy_curr_spread:.0f}pb indica condiciones de credito normales."
                col = COLORS["accent"]
            elif hy_curr_spread < 700:
                txt = f"El spread HY actual de ~{hy_curr_spread:.0f}pb indica tension en credito corporativo."
                col = COLORS["yellow"]
            elif hy_curr_spread < 1000:
                txt = f"El spread HY actual de ~{hy_curr_spread:.0f}pb indica condiciones de estres."
                col = COLORS["orange"]
            else:
                txt = f"El spread HY actual de ~{hy_curr_spread:.0f}pb indica condiciones de CRISIS."
                col = COLORS["red"]
            interp = html.Div(txt, style={"fontSize": "0.78rem", "color": col, "marginTop": "8px"})
        else:
            interp = html.Div()

        return fig, interp

    # ── Tab 3: Muro de vencimientos corporativo ───────────────────────────────

    @app.callback(
        Output("m9-corporate-maturity-chart", "figure"),
        Output("m9-maturity-note", "children"),
        Input("m9-tabs", "value"),
    )
    def update_corporate_maturity(tab):
        if tab != "tab3":
            return no_update, no_update

        data = load_json_data("corporate_debt_maturities.json") or {}
        hy = data.get("high_yield_maturities_bn", {})
        ig = data.get("investment_grade_maturities_bn", {})

        if not hy and not ig:
            return _empty_fig("Sin datos de vencimientos corporativos"), html.Div()

        years = sorted(set(list(hy.keys()) + list(ig.keys())))

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=years, y=[ig.get(y, 0) for y in years],
            name="Investment Grade (IG)",
            marker_color=_rgba(COLORS["accent"], 0.7),
            hovertemplate="%{x}: <b>%{y:.0f}Bn USD</b> IG<extra></extra>",
        ))
        fig.add_trace(go.Bar(
            x=years, y=[hy.get(y, 0) for y in years],
            name="High Yield (HY)",
            marker_color=_rgba(COLORS["red"], 0.80),
            hovertemplate="%{x}: <b>%{y:.0f}Bn USD</b> HY<extra></extra>",
        ))

        layout = get_base_layout(height=380, title="Muro de Vencimientos Deuda Corporativa EE.UU.")
        layout["barmode"] = "group"
        layout["yaxis"] = {**layout.get("yaxis", {}), "title": {"text": "Billones USD"}}
        layout["legend"] = {"orientation": "h", "y": -0.15, "font": {"size": 10}}
        fig.update_layout(**layout)

        # Nota automatica
        hy_peak_year = max(hy, key=lambda y: hy[y]) if hy else "2028"
        hy_peak_val = hy.get(hy_peak_year, 0)
        note = html.Div(
            f"Pico de vencimientos HY en {hy_peak_year}: {hy_peak_val:.0f}Bn USD. "
            "Las empresas que se endeudaron a tipos bajos en 2020-2021 deberan refinanciar "
            "a tipos significativamente mas altos, aumentando sus costes de deuda.",
            style=_NOTE,
        )

        return fig, note

    # ── Tab 3: Tasa de impagos ────────────────────────────────────────────────

    @app.callback(
        Output("m9-default-rate-chart", "figure"),
        Input("m9-tabs", "value"),
    )
    def update_default_rate(tab):
        if tab != "tab3":
            return no_update

        data = load_json_data("default_rates.json") or {}
        rates = data.get("us_hy_default_rate_annual", {})
        forecast = data.get("moody_12m_forecast")
        current = data.get("current_rate")

        if not rates:
            return _empty_fig("Sin datos de tasa de impagos")

        years = sorted(rates.keys())
        vals = [rates[y] for y in years]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=years, y=vals,
            name="Tasa impago HY (anual %)",
            marker_color=[
                COLORS["red"] if v >= 10 else
                COLORS["orange"] if v >= 5 else
                COLORS["yellow"] if v >= 2 else
                COLORS["green"]
                for v in vals
            ],
            hovertemplate="%{x}: <b>%{y:.1f}%</b><extra></extra>",
        ))

        # Proyeccion Moody's
        if forecast is not None:
            last_year = int(years[-1]) + 1
            fig.add_trace(go.Scatter(
                x=[years[-1], str(last_year)], y=[current or vals[-1], forecast],
                mode="lines+markers",
                line={"dash": "dot", "color": COLORS["orange"], "width": 2},
                marker={"symbol": "diamond", "size": 8, "color": COLORS["orange"]},
                name=f"Proyeccion Moody's 12m: {forecast}%",
            ))

        for val, label, color in [
            (2, "2% (nivel bajo)", COLORS["green"]),
            (5, "5% (atencion)", COLORS["yellow"]),
            (10, "10% (crisis)", COLORS["red"]),
        ]:
            fig.add_hline(y=val, line_dash="dot", line_color=color, line_width=1,
                          annotation_text=label, annotation_position="right",
                          annotation_font_color=color, annotation_font_size=9)

        layout = get_base_layout(height=380, title="Tasa de Impagos High Yield EE.UU. (Anual %)")
        layout["yaxis"] = {**layout.get("yaxis", {}), "title": {"text": "% de impagos"}}
        layout["legend"] = {"orientation": "h", "y": -0.15, "font": {"size": 10}}
        fig.update_layout(**layout)
        return fig

    # ── Tab 3: EMB ───────────────────────────────────────────────────────────

    @app.callback(
        Output("m9-emb-chart", "figure"),
        Output("m9-em-vulnerability-panel", "children"),
        Input("m9-interval", "n_intervals"),
        Input("m9-tabs", "value"),
    )
    def update_emb(_, tab):
        if tab != "tab3":
            return no_update, no_update

        df = get_series(ID_EMB, days=365 * 3)
        if df.empty:
            fig = _empty_fig("Sin datos EMB — ejecutar colector Yahoo Finance")
        else:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.sort_values("timestamp")
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=df["timestamp"], y=df["value"],
                fill="tozeroy", fillcolor=_rgba(COLORS["orange"], 0.15),
                line={"color": COLORS["orange"], "width": 1.8},
                name="EMB (deuda emergente USD)",
                hovertemplate="%{x|%b %Y}: <b>$%{y:.2f}</b><extra></extra>",
            ))
            layout = get_base_layout(height=300, title="EMB — JP Morgan USD Emerging Markets Bond ETF")
            layout["yaxis"] = {**layout.get("yaxis", {}), "title": {"text": "Precio USD"}}
            layout["xaxis"] = {**layout.get("xaxis", {}), "rangeselector": get_time_range_buttons()}
            fig.update_layout(**layout)

        # Panel de vulnerabilidad emergente
        em_data = load_json_data("em_vulnerability.json") or {}
        vuln = em_data.get("most_vulnerable", [])
        risk_colors = {"critical": COLORS["red"], "high": COLORS["orange"], "medium": COLORS["yellow"]}

        vuln_rows = []
        for country in vuln:
            rc = risk_colors.get(country.get("risk", "medium"), COLORS["text_muted"])
            vuln_rows.append(html.Tr([
                html.Td(country.get("country", "—"), style={"fontSize": "0.76rem", "padding": "4px 8px"}),
                html.Td(f"{country.get('external_debt_gdp', '—')}%", style={"fontSize": "0.76rem", "padding": "4px 8px", "textAlign": "right"}),
                html.Td(f"{country.get('reserves_months', '—')}m", style={"fontSize": "0.76rem", "padding": "4px 8px", "textAlign": "right"}),
                html.Td(f"{country.get('current_account_gdp', '—')}%", style={"fontSize": "0.76rem", "padding": "4px 8px", "textAlign": "right"}),
                html.Td(
                    html.Span(country.get("risk", "—").upper(), style={
                        "fontSize": "0.62rem", "fontWeight": "700", "color": rc,
                        "background": _rgba(rc, 0.15), "padding": "2px 6px", "borderRadius": "3px",
                    }),
                    style={"padding": "4px 8px"},
                ),
            ]))

        vuln_panel = html.Div([
            html.Div("Economias Emergentes Mas Vulnerables (deuda externa en USD)", style={
                "fontSize": "0.72rem", "fontWeight": "600", "color": COLORS["text_label"],
                "marginTop": "12px", "marginBottom": "6px",
            }),
            html.Table([
                html.Thead(html.Tr([
                    html.Th(h, style={"fontSize": "0.65rem", "color": COLORS["text_label"], "padding": "4px 8px"})
                    for h in ["Pais", "Deuda Ext/PIB", "Reservas (meses)", "C/C % PIB", "Riesgo"]
                ])),
                html.Tbody(vuln_rows),
            ], style={"width": "100%", "borderCollapse": "collapse"}),
        ]) if vuln_rows else html.Div()

        return fig, vuln_panel

    # ── Tab 4: DXY + STLFSI4 ─────────────────────────────────────────────────

    @app.callback(
        Output("m9-dxy-chart", "figure"),
        Input("m9-interval", "n_intervals"),
        Input("m9-tabs", "value"),
    )
    def update_dxy(_, tab):
        if tab != "tab4":
            return no_update

        df_dxy = get_series(ID_DXY, days=365 * 5)
        df_stlfsi = get_series(ID_STLFSI4, days=365 * 5)

        if df_dxy.empty:
            return _empty_fig("Sin datos DXY — ejecutar colector Yahoo Finance")

        df_dxy["timestamp"] = pd.to_datetime(df_dxy["timestamp"])
        df_dxy = df_dxy.sort_values("timestamp")

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df_dxy["timestamp"], y=df_dxy["value"],
            name="DXY (Indice Dolar)",
            line={"color": COLORS["accent"], "width": 1.8},
            hovertemplate="DXY: <b>%{y:.2f}</b><extra></extra>",
        ))

        # Linea de referencia DXY > 105 = risk off
        fig.add_hline(y=105, line_dash="dot", line_color=COLORS["orange"], line_width=1,
                      annotation_text="105 (risk-off)", annotation_position="right",
                      annotation_font_color=COLORS["orange"], annotation_font_size=9)

        # Superponer STLFSI4 si disponible
        if not df_stlfsi.empty:
            df_stlfsi["timestamp"] = pd.to_datetime(df_stlfsi["timestamp"])
            df_stlfsi = df_stlfsi.sort_values("timestamp")
            fig.add_trace(go.Scatter(
                x=df_stlfsi["timestamp"], y=df_stlfsi["value"],
                name="STLFSI4 (eje dcho)",
                line={"color": COLORS["red"], "width": 1.2, "dash": "dot"},
                yaxis="y2",
                hovertemplate="STLFSI4: <b>%{y:.2f}</b><extra></extra>",
            ))
            fig.update_layout(yaxis2={
                "title": {"text": "STLFSI4", "font": {"size": 10, "color": COLORS["red"]}},
                "overlaying": "y", "side": "right",
                "gridcolor": "transparent",
                "tickfont": {"size": 9, "color": COLORS["red"]},
            })

        # Anotaciones eventos
        for x, label in [("2020-03-20", "COVID"), ("2022-09-28", "Max DXY 2022")]:
            try:
                fig.add_vline(x=x, line_dash="dot", line_color=COLORS["text_muted"], line_width=0.8,
                              annotation_text=label, annotation_position="top left",
                              annotation_font_color=COLORS["text_muted"], annotation_font_size=9)
            except Exception:
                pass

        layout = get_base_layout(height=380, title="DXY (Indice del Dolar) vs STLFSI4")
        layout["xaxis"] = {**layout.get("xaxis", {}), "rangeselector": get_time_range_buttons()}
        layout["yaxis"] = {**layout.get("yaxis", {}), "title": {"text": "DXY"}}
        layout["legend"] = {"orientation": "h", "y": -0.15, "font": {"size": 10}}
        fig.update_layout(**layout)
        return fig

    # ── Tab 4: EEM + emergentes vulnerables ───────────────────────────────────

    @app.callback(
        Output("m9-eem-chart", "figure"),
        Output("m9-em-vulnerable-panel", "children"),
        Input("m9-interval", "n_intervals"),
        Input("m9-tabs", "value"),
    )
    def update_eem(_, tab):
        if tab != "tab4":
            return no_update, no_update

        df_eem = get_series(ID_EEM, days=365 * 3)
        df_dxy = get_series(ID_DXY, days=365 * 3)

        if df_eem.empty:
            fig = _empty_fig("Sin datos EEM — ejecutar colector Yahoo Finance")
        else:
            df_eem["timestamp"] = pd.to_datetime(df_eem["timestamp"])
            df_eem = df_eem.sort_values("timestamp")

            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=df_eem["timestamp"], y=df_eem["value"],
                name="EEM (MSCI Emergentes)",
                line={"color": COLORS["orange"], "width": 1.8},
                hovertemplate="EEM: <b>$%{y:.2f}</b><extra></extra>",
            ))

            # DXY invertido en eje secundario
            if not df_dxy.empty:
                df_dxy["timestamp"] = pd.to_datetime(df_dxy["timestamp"])
                df_dxy = df_dxy.sort_values("timestamp")
                dxy_max = df_dxy["value"].max()
                df_dxy["dxy_inv"] = dxy_max - df_dxy["value"] + df_dxy["value"].min()
                fig.add_trace(go.Scatter(
                    x=df_dxy["timestamp"], y=df_dxy["dxy_inv"],
                    name="DXY invertido (eje dcho)",
                    line={"color": COLORS["accent"], "width": 1.2, "dash": "dot"},
                    yaxis="y2",
                    hovertemplate="DXY inv: <b>%{y:.1f}</b><extra></extra>",
                ))
                fig.update_layout(yaxis2={
                    "overlaying": "y", "side": "right",
                    "gridcolor": "transparent",
                    "tickfont": {"size": 9, "color": COLORS["accent"]},
                })

            layout = get_base_layout(height=320, title="EEM vs DXY Invertido — Correlacion Inversa")
            layout["xaxis"] = {**layout.get("xaxis", {}), "rangeselector": get_time_range_buttons()}
            layout["yaxis"] = {**layout.get("yaxis", {}), "title": {"text": "EEM USD"}}
            layout["legend"] = {"orientation": "h", "y": -0.18, "font": {"size": 10}}
            fig.update_layout(**layout)

        # Panel paises vulnerables resumido
        em_data = load_json_data("em_vulnerability.json") or {}
        vuln = em_data.get("most_vulnerable", [])
        risk_colors = {"critical": COLORS["red"], "high": COLORS["orange"], "medium": COLORS["yellow"]}
        items = []
        for c in vuln:
            rc = risk_colors.get(c.get("risk", ""), COLORS["text_muted"])
            items.append(html.Div([
                html.Span(f"• {c.get('country')}: ", style={"color": COLORS["text_muted"], "fontSize": "0.76rem"}),
                html.Span(f"Deuda ext. {c.get('external_debt_gdp')}% PIB", style={"color": rc, "fontSize": "0.76rem"}),
            ]))

        panel = html.Div(items, style={"marginTop": "10px"}) if items else html.Div()
        return fig, panel

    # ── Tab 4: USD/JPY carry trade ────────────────────────────────────────────

    @app.callback(
        Output("m9-usdjpy-chart", "figure"),
        Output("m9-carry-trade-panel", "children"),
        Input("m9-interval", "n_intervals"),
        Input("m9-tabs", "value"),
    )
    def update_usdjpy(_, tab):
        if tab != "tab4":
            return no_update, no_update

        df = get_series(ID_USDJPY, days=365 * 3)
        usdjpy_val, _ = get_latest_value(ID_USDJPY)

        if df.empty:
            fig = _empty_fig("Sin datos USD/JPY — ejecutar colector Yahoo Finance")
        else:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.sort_values("timestamp")

            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=df["timestamp"], y=df["value"],
                name="USD/JPY",
                line={"color": COLORS["yellow"], "width": 1.8},
                fill="tozeroy", fillcolor=_rgba(COLORS["yellow"], 0.08),
                hovertemplate="USD/JPY: <b>%{y:.2f}</b><extra></extra>",
            ))

            # Zonas de riesgo
            for val, label, color in [
                (140, "140 (riesgo elevado)", COLORS["yellow"]),
                (150, "150 (muy elevado)", COLORS["orange"]),
                (160, "160 (extremo)", COLORS["red"]),
            ]:
                fig.add_hline(y=val, line_dash="dot", line_color=color, line_width=1,
                              annotation_text=label, annotation_position="right",
                              annotation_font_color=color, annotation_font_size=9)

            # Anotacion agosto 2024
            try:
                fig.add_annotation(
                    x="2024-08-05", y=144,
                    text="Deshacimiento<br>carry trade<br>Ago 2024",
                    showarrow=True, arrowhead=2, arrowcolor=COLORS["red"],
                    font={"color": COLORS["red"], "size": 9}, ax=60, ay=-50,
                )
            except Exception:
                pass

            layout = get_base_layout(height=320, title="USD/JPY — Monitor del Carry Trade del Yen")
            layout["xaxis"] = {**layout.get("xaxis", {}), "rangeselector": get_time_range_buttons()}
            layout["yaxis"] = {**layout.get("yaxis", {}), "title": {"text": "USD por JPY"}}
            fig.update_layout(**layout)

        risk_txt, risk_color = _usdjpy_risk(usdjpy_val)
        panel = html.Div([
            html.Div([
                html.Span("USD/JPY actual: ", style={"fontSize": "0.82rem", "color": COLORS["text_muted"]}),
                html.Span(f"{_safe(usdjpy_val, '.2f')}", style={"fontSize": "1rem", "fontWeight": "700", "color": COLORS["text"]}),
                html.Span(f" — Riesgo carry trade: ", style={"fontSize": "0.82rem", "color": COLORS["text_muted"], "marginLeft": "8px"}),
                html.Span(risk_txt, style={"fontSize": "0.82rem", "fontWeight": "700", "color": risk_color}),
            ], style={"marginTop": "10px"}),
        ])

        return fig, panel

    # ── Tab 4: Reservas de divisas globales ───────────────────────────────────

    @app.callback(
        Output("m9-reserves-chart", "figure"),
        Input("m9-tabs", "value"),
    )
    def update_reserves(tab):
        if tab != "tab4":
            return no_update

        # Datos estaticos de composicion de reservas (FMI COFER)
        years = [2000, 2005, 2010, 2015, 2018, 2020, 2022, 2024]
        usd   = [71.1, 66.9, 62.2, 65.7, 61.9, 59.0, 58.4, 57.8]
        eur   = [18.3, 24.3, 26.0, 20.2, 20.7, 21.2, 20.6, 20.0]
        jpy   = [6.3,  3.7,  3.7,  3.8,  5.2,  5.9,  5.5,  5.7]
        gbp   = [2.8,  3.6,  3.9,  4.9,  4.4,  4.7,  4.8,  4.9]
        cny   = [0.0,  0.0,  0.0,  1.1,  1.8,  2.3,  2.7,  2.8]
        other = [1.5,  1.5,  4.2,  4.3,  6.0,  6.9,  8.0,  8.8]

        palette = [COLORS["accent"], COLORS["orange"], COLORS["yellow"],
                   COLORS["green"], COLORS["red"], COLORS["text_muted"]]

        fig = go.Figure()
        for name, vals, color in [
            ("USD", usd, palette[0]),
            ("EUR", eur, palette[1]),
            ("JPY", jpy, palette[2]),
            ("GBP", gbp, palette[3]),
            ("CNY", cny, palette[4]),
            ("Otras", other, palette[5]),
        ]:
            fig.add_trace(go.Bar(
                x=years, y=vals,
                name=name,
                marker_color=_rgba(color, 0.75),
                hovertemplate=f"{name}: <b>%{{y:.1f}}%</b><extra></extra>",
            ))

        layout = get_base_layout(height=380, title="Composicion de Reservas de Divisas Globales (% del total)")
        layout["barmode"] = "stack"
        layout["yaxis"] = {**layout.get("yaxis", {}), "title": {"text": "% del total de reservas"}}
        layout["legend"] = {"orientation": "h", "y": -0.15, "font": {"size": 10}}
        fig.update_layout(**layout)
        return fig

    # ── Tab 5: Radar del 2008 ─────────────────────────────────────────────────

    @app.callback(
        Output("m9-radar-chart", "figure"),
        Output("m9-radar-interpretation", "children"),
        Input("m9-interval", "n_intervals"),
        Input("m9-tabs", "value"),
    )
    def update_radar(_, tab):
        if tab != "tab5":
            return no_update, no_update

        # Valores historicos 2007 (pre-crisis) y 2008-2009 (pico)
        # Escala 0-10 donde 10 = maximo riesgo
        dimensions = [
            "Spread HY",
            "VIX",
            "STLFSI4",
            "Crecimiento Credito",
            "Prima Riesgo Europa",
            "Deuda/PIB Global",
            "Spread Interbancario",
            "Precio Inmobiliario",
        ]

        vals_2007 = [1.0, 1.2, 0.5, 0.5, 0.8, 4.0, 0.3, 8.5]
        vals_2009 = [9.5, 9.8, 9.0, 7.0, 6.5, 6.0, 9.0, 9.5]

        # Valores actuales (calculados en tiempo real)
        def _norm(val, min_v, max_v, scale=10):
            if val is None:
                return 3.0
            return max(0, min(scale, (float(val) - min_v) / (max_v - min_v) * scale))

        hy_spread = calculate_hy_spread_proxy()
        vix_val, _ = get_latest_value(ID_VIX)
        stlfsi_val, _ = get_latest_value(ID_STLFSI4)
        it_spread_val, _ = get_latest_value(ID_IT_SPREAD)

        vals_now = [
            _norm(hy_spread, 200, 2000),
            _norm(vix_val, 10, 80),
            _norm(stlfsi_val, -5, 10),
            3.0,  # Crecimiento credito — sin dato en tiempo real
            _norm(it_spread_val, 0, 600) if it_spread_val else 2.5,
            5.5,  # Deuda/PIB global ~ 105% vs 60% min → escala aproximada
            _norm(0.05, 0, 4),  # Spread interbancario SOFR ~bajo actualmente
            3.0,  # Inmobiliario — dato estatico aproximado
        ]

        dims_closed = dimensions + [dimensions[0]]
        v2007 = vals_2007 + [vals_2007[0]]
        v2009 = vals_2009 + [vals_2009[0]]
        vnow  = vals_now  + [vals_now[0]]

        fig = go.Figure()
        fig.add_trace(go.Scatterpolar(
            r=v2009, theta=dims_closed,
            fill="toself", fillcolor=_rgba(COLORS["red"], 0.12),
            line={"color": COLORS["red"], "width": 2},
            name="Crisis 2008-2009 (pico)",
        ))
        fig.add_trace(go.Scatterpolar(
            r=v2007, theta=dims_closed,
            fill="toself", fillcolor=_rgba(COLORS["orange"], 0.10),
            line={"color": COLORS["orange"], "width": 1.5, "dash": "dot"},
            name="2007 (pre-crisis)",
        ))
        fig.add_trace(go.Scatterpolar(
            r=vnow, theta=dims_closed,
            fill="toself", fillcolor=_rgba(COLORS["accent"], 0.15),
            line={"color": COLORS["accent"], "width": 2},
            name="Actual (2026)",
        ))

        layout = get_base_layout(height=450)
        layout["polar"] = {
            "bgcolor": "#111827",
            "radialaxis": {
                "range": [0, 10],
                "tickfont": {"size": 9, "color": COLORS["text_muted"]},
                "gridcolor": COLORS["border"],
                "linecolor": COLORS["border"],
            },
            "angularaxis": {
                "tickfont": {"size": 10, "color": COLORS["text"]},
                "gridcolor": COLORS["border"],
                "linecolor": COLORS["border"],
            },
        }
        layout["legend"] = {"orientation": "h", "y": -0.1, "font": {"size": 10}}
        layout.pop("hovermode", None)
        fig.update_layout(**layout)

        # Interpretacion automatica
        avg_now = sum(vals_now) / len(vals_now)
        avg_2007 = sum(vals_2007) / len(vals_2007)
        avg_2009 = sum(vals_2009) / len(vals_2009)

        if avg_now < avg_2007 * 1.2:
            similar_to = "2007 o por debajo — perfil de riesgo moderado"
            color = COLORS["green"]
        elif avg_now < (avg_2007 + avg_2009) / 2:
            similar_to = "un nivel intermedio entre 2007 y el pico de 2009"
            color = COLORS["yellow"]
        else:
            similar_to = "niveles comparables al pico de la crisis 2008-2009"
            color = COLORS["red"]

        interp = html.Div([
            html.Span("El perfil de riesgo actual se asemeja a ", style={"fontSize": "0.78rem", "color": COLORS["text_muted"]}),
            html.Span(similar_to, style={"fontSize": "0.78rem", "fontWeight": "600", "color": color}),
            html.Span(f". Puntuacion media actual: {avg_now:.1f}/10.", style={"fontSize": "0.78rem", "color": COLORS["text_muted"]}),
        ], style={"marginTop": "8px"})

        return fig, interp

    # ── Refresco del header ───────────────────────────────────────────────────

    @app.callback(
        Output("m9-header-metrics", "children"),
        Input("m9-interval", "n_intervals"),
    )
    def refresh_header(_):
        return _build_header_metrics()
