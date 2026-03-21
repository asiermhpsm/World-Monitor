"""
Modulo 4 — Política Monetaria Global
Se renderiza cuando la URL es /module/4.

Exporta:
  render_module_4()                -> layout completo
  register_callbacks_module_4(app) -> registra todos los callbacks
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, date
from typing import Optional

import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import pandas as pd
from dash import Input, Output, State, ctx, dcc, html, no_update

from components.chart_config import COLORS as C, get_base_layout, get_time_range_buttons
from components.common import create_empty_state, create_metric_card, create_semaphore
from config import COLORS
from modules.data_helpers import (
    format_value,
    get_change,
    get_latest_value,
    get_series,
    time_ago,
)

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTES — IDs de indicadores
# ══════════════════════════════════════════════════════════════════════════════

ID_FED_FUNDS       = "fred_fed_funds_us"
ID_FED_BALANCE     = "fred_walcl_us"
ID_CPI_YOY_US      = "fred_cpi_yoy_us"
ID_CPI_US          = "fred_cpi_us"
ID_REAL_RATE_US    = "fred_real_rate_us"
ID_ECB_RATE        = "ecb_deposit_rate_ea"
ID_ECB_MAIN_RATE   = "ecb_main_rate_ea"
ID_ECB_MARGINAL    = "ecb_marginal_rate_ea"
ID_ECB_BALANCE     = "ecb_total_assets_ea"
ID_HICP_EA         = "estat_hicp_cp00_ea20"
ID_EURIBOR_12M     = "ecb_euribor_12m_ea"
ID_EURUSD          = "yf_eurusd_price"
ID_USDJPY          = "yf_usdjpy_price"
ID_JGB_10Y         = "boj_jgb_10y_jp"
ID_BOE_RATE        = "boe_rate_gb"
ID_BOJ_RATE        = "boj_rate_jp"
ID_SNB_RATE        = "snb_rate_ch"
ID_BOC_RATE        = "boc_rate_ca"
ID_RBA_RATE        = "rba_rate_au"
ID_PBOC_LPR        = "pboc_lpr_1y_cn"
ID_PBOC_RRR        = "pboc_rrr_cn"
ID_RBI_RATE        = "rbi_rate_in"
ID_BCB_SELIC       = "bcb_selic_br"
ID_BANXICO_RATE    = "banxico_rate_mx"
ID_HICP_DE         = "estat_hicp_cp00_de"
ID_HICP_ES         = "estat_hicp_cp00_es"

# ── Estilos de tabs ───────────────────────────────────────────────────────────
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

# ── Datos estáticos de bancos centrales ───────────────────────────────────────
# fallback cuando no hay datos en BD; rate_id y inflation_id se consultan primero.
CB_CATALOG = [
    {
        "key": "FED",  "flag": "🇺🇸", "name": "Fed",
        "rate_id": ID_FED_FUNDS, "inflation_id": ID_CPI_YOY_US,
        "rate_1y_id": ID_FED_FUNDS,
        "static_rate": 4.50, "static_inf": 2.8,
        "next_meeting": "2026-05-07",
    },
    {
        "key": "ECB",  "flag": "🇪🇺", "name": "BCE",
        "rate_id": ID_ECB_RATE, "inflation_id": ID_HICP_EA,
        "rate_1y_id": ID_ECB_RATE,
        "static_rate": 2.50, "static_inf": 2.3,
        "next_meeting": "2026-04-17",
    },
    {
        "key": "BOE",  "flag": "🇬🇧", "name": "Bank of England",
        "rate_id": ID_BOE_RATE, "inflation_id": None,
        "rate_1y_id": ID_BOE_RATE,
        "static_rate": 4.50, "static_inf": 3.0,
        "next_meeting": "2026-05-08",
    },
    {
        "key": "BOJ",  "flag": "🇯🇵", "name": "Bank of Japan",
        "rate_id": ID_BOJ_RATE, "inflation_id": None,
        "rate_1y_id": ID_BOJ_RATE,
        "static_rate": 0.50, "static_inf": 2.8,
        "next_meeting": "2026-04-30",
    },
    {
        "key": "SNB",  "flag": "🇨🇭", "name": "SNB Suiza",
        "rate_id": ID_SNB_RATE, "inflation_id": None,
        "rate_1y_id": ID_SNB_RATE,
        "static_rate": 0.50, "static_inf": 0.3,
        "next_meeting": "2026-06-19",
    },
    {
        "key": "BOC",  "flag": "🇨🇦", "name": "Bank of Canada",
        "rate_id": ID_BOC_RATE, "inflation_id": None,
        "rate_1y_id": ID_BOC_RATE,
        "static_rate": 2.75, "static_inf": 2.6,
        "next_meeting": "2026-04-16",
    },
    {
        "key": "RBA",  "flag": "🇦🇺", "name": "RBA Australia",
        "rate_id": ID_RBA_RATE, "inflation_id": None,
        "rate_1y_id": ID_RBA_RATE,
        "static_rate": 4.10, "static_inf": 3.2,
        "next_meeting": "2026-05-20",
    },
    {
        "key": "PBOC", "flag": "🇨🇳", "name": "PBOC China",
        "rate_id": ID_PBOC_LPR, "inflation_id": None,
        "rate_1y_id": ID_PBOC_LPR,
        "static_rate": 3.10, "static_inf": 0.1,
        "next_meeting": "2026-04-20",
    },
    {
        "key": "RBI",  "flag": "🇮🇳", "name": "RBI India",
        "rate_id": ID_RBI_RATE, "inflation_id": None,
        "rate_1y_id": ID_RBI_RATE,
        "static_rate": 6.25, "static_inf": 4.0,
        "next_meeting": "2026-06-06",
    },
    {
        "key": "BCB",  "flag": "🇧🇷", "name": "BCB Brasil",
        "rate_id": ID_BCB_SELIC, "inflation_id": None,
        "rate_1y_id": ID_BCB_SELIC,
        "static_rate": 14.75, "static_inf": 5.1,
        "next_meeting": "2026-05-07",
    },
    {
        "key": "BANXICO", "flag": "🇲🇽", "name": "Banxico México",
        "rate_id": ID_BANXICO_RATE, "inflation_id": None,
        "rate_1y_id": ID_BANXICO_RATE,
        "static_rate": 9.00, "static_inf": 3.7,
        "next_meeting": "2026-05-15",
    },
]

# Datos del dot plot de la Fed (última publicación disponible, dic 2025)
DOT_PLOT_DATA = {
    "mediana_2025": 4.375,
    "mediana_2026": 3.875,
    "mediana_2027": 3.375,
    "mediana_largo_plazo": 3.000,
    "publicado": "Diciembre 2025",
    "dots": {
        2025: [4.375]*18,
        2026: [3.375, 3.625, 3.625, 3.875, 3.875, 3.875, 3.875, 4.125, 4.125, 4.125,
               4.125, 4.375, 4.375, 4.375, 4.375, 4.625, 4.625, 4.875],
        2027: [2.875, 3.125, 3.125, 3.375, 3.375, 3.375, 3.625, 3.625, 3.625, 3.625,
               3.875, 3.875, 3.875, 3.875, 4.125, 4.125, 4.125, 4.375],
    },
}

# Ciclos históricos Fed (estático educativo)
FED_CYCLES = [
    {"inicio_subida": "1954-07", "fin_subida": "1957-09", "tipo_max": 3.50, "inicio_bajada": "1957-11", "tipo_min": 0.50, "meses": 40},
    {"inicio_subida": "1958-09", "fin_subida": "1959-12", "tipo_max": 4.00, "inicio_bajada": "1960-06", "tipo_min": 1.00, "meses": 27},
    {"inicio_subida": "1977-01", "fin_subida": "1981-06", "tipo_max": 20.00, "inicio_bajada": "1981-07", "tipo_min": 5.75, "meses": 72},
    {"inicio_subida": "1994-02", "fin_subida": "1995-02", "tipo_max": 6.00, "inicio_bajada": "1995-07", "tipo_min": 4.75, "meses": 18},
    {"inicio_subida": "1999-06", "fin_subida": "2000-05", "tipo_max": 6.50, "inicio_bajada": "2001-01", "tipo_min": 1.00, "meses": 30},
    {"inicio_subida": "2004-06", "fin_subida": "2006-06", "tipo_max": 5.25, "inicio_bajada": "2007-09", "tipo_min": 0.25, "meses": 42},
    {"inicio_subida": "2015-12", "fin_subida": "2018-12", "tipo_max": 2.50, "inicio_bajada": "2019-07", "tipo_min": 0.25, "meses": 61},
    {"inicio_subida": "2022-03", "fin_subida": "2023-07", "tipo_max": 5.50, "inicio_bajada": "2024-09", "tipo_min": 4.50, "meses": None},  # actual
]


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _safe(val, fmt=".2f", suffix=""):
    if val is None:
        return "—"
    try:
        return f"{val:{fmt}}{suffix}"
    except Exception:
        return "—"


def _pct(val, decimals=2):
    if val is None:
        return "—"
    try:
        return f"{val:.{decimals}f}%"
    except Exception:
        return "—"


def _section_label(text: str) -> html.Div:
    return html.Div(text, style={
        "fontSize": "0.65rem", "letterSpacing": "0.1em",
        "color": COLORS["text_label"], "fontWeight": "600", "marginBottom": "10px",
    })


def _card_style() -> dict:
    return {
        "backgroundColor": COLORS["card_bg"],
        "border": f"1px solid {COLORS['border']}",
        "borderRadius": "8px",
        "padding": "16px",
    }


def _compact_metric(title: str, value_str: str, sub: str = "", sub_color: str = "") -> html.Div:
    return html.Div([
        html.Div(title, style={
            "fontSize": "0.60rem", "color": COLORS["text_label"],
            "fontWeight": "600", "letterSpacing": "0.08em", "marginBottom": "2px",
        }),
        html.Div(value_str, style={
            "fontSize": "0.95rem", "fontWeight": "700",
            "color": COLORS["text"], "fontFamily": "monospace",
        }),
        html.Div(sub, style={
            "fontSize": "0.68rem",
            "color": sub_color or COLORS["text_muted"],
            "fontWeight": "500",
        }),
    ], style={
        "backgroundColor": COLORS["card_bg"],
        "border": f"1px solid {COLORS['border']}",
        "borderRadius": "6px",
        "padding": "8px 12px",
        "minWidth": "110px",
        "flex": "1",
    })


def _posture_badge(real_rate: Optional[float]) -> html.Span:
    if real_rate is None:
        return html.Span("N/D", style={
            "backgroundColor": COLORS["border"],
            "color": COLORS["text_muted"],
            "padding": "2px 8px", "borderRadius": "10px",
            "fontSize": "0.70rem", "fontWeight": "600",
        })
    if real_rate > 1.0:
        label, bg, color = "Hawkish", "#7f1d1d", "#ef4444"
    elif real_rate >= -0.5:
        label, bg, color = "Neutral", "#1f2937", "#9ca3af"
    else:
        label, bg, color = "Dovish", "#052e16", "#10b981"
    return html.Span(label, style={
        "backgroundColor": bg,
        "color": color,
        "padding": "2px 8px", "borderRadius": "10px",
        "fontSize": "0.70rem", "fontWeight": "600",
        "border": f"1px solid {color}40",
    })


def _days_until(date_str: str) -> Optional[int]:
    try:
        target = datetime.strptime(date_str, "%Y-%m-%d").date()
        today = date.today()
        delta = (target - today).days
        return delta if delta >= 0 else None
    except Exception:
        return None


def _btn_style(active: bool = False) -> dict:
    return {
        "backgroundColor": COLORS["accent"] if active else COLORS["card_bg"],
        "border": f"1px solid {COLORS['border']}",
        "color": "#ffffff" if active else COLORS["text_muted"],
        "padding": "2px 10px",
        "fontSize": "0.72rem",
        "borderRadius": "4px",
        "cursor": "pointer",
        "marginRight": "4px",
    }


# ══════════════════════════════════════════════════════════════════════════════
# HEADER DEL MÓDULO
# ══════════════════════════════════════════════════════════════════════════════

def _build_m4_header() -> html.Div:
    # 1) Fed Funds Rate
    fed, fed_ts = get_latest_value(ID_FED_FUNDS)
    _, fed_prev, fed_chg, _ = get_change(ID_FED_FUNDS, period_days=60)

    # 2) BCE tipo depósito
    ecb, ecb_ts = get_latest_value(ID_ECB_RATE)
    _, ecb_prev, ecb_chg, _ = get_change(ID_ECB_RATE, period_days=60)

    # 3) EURIBOR 12M
    eur12, eur12_ts = get_latest_value(ID_EURIBOR_12M)
    _, eur12_prev, eur12_chg, _ = get_change(ID_EURIBOR_12M, period_days=60)

    # 4) Balance Fed en billones USD (WALCL está en millones → dividir por 1M para billones)
    walcl, walcl_ts = get_latest_value(ID_FED_BALANCE)
    walcl_bn = walcl / 1_000_000 if walcl is not None else None  # millones → billones

    # 5) Tipo real US (DFF - CPI)
    real_us, _ = get_latest_value(ID_REAL_RATE_US)
    if real_us is None and fed is not None:
        cpi_us, _ = get_latest_value(ID_CPI_YOY_US)
        real_us = (fed - cpi_us) if cpi_us is not None else None

    # 6) Tipo real Eurozona (ECB rate - HICP)
    hicp_ea, _ = get_latest_value(ID_HICP_EA)
    real_ea = (ecb - hicp_ea) if (ecb is not None and hicp_ea is not None) else None

    def _arrow(chg):
        if chg is None or abs(chg) < 0.01:
            return "→"
        return "↑" if chg > 0 else "↓"

    def _chg_color(chg):
        if chg is None:
            return COLORS["text_muted"]
        return C["positive"] if chg > 0 else C["negative"]

    def _subtext(val, ts, chg):
        if val is None:
            return "Sin datos", COLORS["text_muted"]
        arrow = _arrow(chg)
        ts_str = ts.strftime("%d/%m/%y") if ts else "—"
        chg_str = f" {arrow} {abs(chg):.2f}pp" if chg is not None and abs(chg) >= 0.01 else f" {arrow} Sin cambio"
        return f"{ts_str}{chg_str}", _chg_color(chg)

    sub1, col1 = _subtext(fed, fed_ts, fed_chg)
    sub2, col2 = _subtext(ecb, ecb_ts, ecb_chg)
    sub3, col3 = _subtext(eur12, eur12_ts, eur12_chg)

    # Próximas reuniones
    fed_next = "2026-05-07"
    ecb_next = "2026-04-17"
    fed_days = _days_until(fed_next)
    ecb_days = _days_until(ecb_next)

    next_meetings = html.Div([
        html.Span("Próximas reuniones: ", style={"fontSize": "0.68rem", "color": COLORS["text_muted"]}),
        html.Span(f"Fed {fed_next} ({fed_days}d) ", style={"fontSize": "0.68rem", "color": COLORS["accent"]}),
        html.Span("· ", style={"color": COLORS["border"]}),
        html.Span(f"BCE {ecb_next} ({ecb_days}d)", style={"fontSize": "0.68rem", "color": "#10b981"}),
    ], style={"marginTop": "8px"})

    metrics = html.Div([
        _compact_metric("FED FUNDS RATE", _pct(fed), sub1, col1),
        _compact_metric("TIPO BCE (DEP.)", _pct(ecb), sub2, col2),
        _compact_metric("EURIBOR 12M", _pct(eur12, 3) if eur12 else "—", sub3, col3),
        _compact_metric("BALANCE FED", f"{walcl_bn:.2f}T$" if walcl_bn else "—", "Billones USD"),
        _compact_metric("TIPO REAL EE.UU.", _pct(real_us) if real_us else "—",
                        "DFF − IPC",
                        C["positive"] if real_us and real_us > 0 else C["negative"] if real_us else COLORS["text_muted"]),
        _compact_metric("TIPO REAL EUROZONA", _pct(real_ea) if real_ea else "—",
                        "BCE − HICP",
                        C["positive"] if real_ea and real_ea > 0 else C["negative"] if real_ea else COLORS["text_muted"]),
    ], style={"display": "flex", "gap": "8px", "flexWrap": "wrap", "marginTop": "12px"})

    return html.Div([
        html.Div([
            html.Span("Política Monetaria Global", style={
                "fontSize": "1.4rem", "fontWeight": "700", "color": COLORS["text"],
            }),
            html.Span("FRED · ECB · BIS · Fuentes oficiales", style={
                "fontSize": "0.72rem", "color": COLORS["text_muted"], "marginLeft": "16px",
            }),
        ], style={"display": "flex", "alignItems": "baseline"}),
        metrics,
        next_meetings,
        dcc.Interval(id="m4-refresh-interval", interval=300_000, n_intervals=0),
    ], style={
        "padding": "16px 20px 14px",
        "borderBottom": f"1px solid {COLORS['border']}",
        "backgroundColor": COLORS["card_bg"],
    })


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — VISIÓN GLOBAL
# ══════════════════════════════════════════════════════════════════════════════

def _build_cb_table() -> html.Div:
    """Tabla comparativa de bancos centrales."""
    headers = ["Banco Central", "Tipo actual", "Hace 1 año", "Variación", "Inflación", "Tipo real", "Postura", "Próx. reunión"]

    rows = []
    for cb in CB_CATALOG:
        # Tipo actual
        rate, rate_ts = get_latest_value(cb["rate_id"])
        if rate is None:
            rate = cb["static_rate"]
            rate_ts = None

        # Tipo hace 1 año
        _, rate_1y, _, _ = get_change(cb["rate_id"], period_days=365)
        if rate_1y is None:
            rate_1y = None  # No fallback — mostrar —

        # Variación
        var = (rate - rate_1y) if (rate is not None and rate_1y is not None) else None
        if var is not None:
            arrow = "↑" if var > 0.01 else ("↓" if var < -0.01 else "→")
            var_color = C["negative"] if var > 0 else (C["positive"] if var < 0 else COLORS["text_muted"])
            var_el = html.Span(f"{arrow} {abs(var):.2f}pp", style={"color": var_color, "fontFamily": "monospace", "fontSize": "0.78rem"})
        else:
            var_el = html.Span("—", style={"color": COLORS["text_muted"]})

        # Inflación
        inf_val = None
        if cb["inflation_id"]:
            inf_val, _ = get_latest_value(cb["inflation_id"])
        if inf_val is None:
            inf_val = cb["static_inf"]

        # Tipo real
        real = (rate - inf_val) if (rate is not None and inf_val is not None) else None
        real_color = C["positive"] if real and real > 0 else C["negative"] if real and real < 0 else COLORS["text_muted"]

        # Próxima reunión
        days = _days_until(cb["next_meeting"])
        meet_str = f"{cb['next_meeting']} ({days}d)" if days is not None else cb["next_meeting"]

        rows.append([
            html.Span(f"{cb['flag']} {cb['name']}", style={"fontWeight": "600", "fontSize": "0.80rem"}),
            html.Span(_pct(rate), style={"fontFamily": "monospace", "fontWeight": "700", "color": COLORS["text"]}),
            html.Span(_pct(rate_1y), style={"fontFamily": "monospace", "color": COLORS["text_muted"], "fontSize": "0.78rem"}),
            var_el,
            html.Span(_pct(inf_val, 1) if inf_val else "—", style={"fontFamily": "monospace", "fontSize": "0.78rem"}),
            html.Span(_pct(real) if real else "—", style={"fontFamily": "monospace", "color": real_color, "fontSize": "0.78rem"}),
            _posture_badge(real),
            html.Span(meet_str, style={"fontSize": "0.72rem", "color": COLORS["text_muted"]}),
        ])

    # Build HTML table
    th_els = [html.Th(h, style={"fontSize": "0.65rem", "letterSpacing": "0.06em", "color": COLORS["text_label"]}) for h in headers]
    row_els = [html.Tr([html.Td(c, style={"padding": "7px 10px", "borderBottom": f"1px solid {COLORS['border']}"}) for c in row]) for row in rows]

    return html.Div([
        _section_label("TABLA COMPARATIVA DE BANCOS CENTRALES GLOBALES"),
        html.Div(
            html.Table(
                [html.Thead(html.Tr(th_els)), html.Tbody(row_els)],
                style={"width": "100%", "borderCollapse": "collapse", "fontSize": "0.80rem"},
            ),
            style={"overflowX": "auto"},
        ),
        html.Div(
            "Postura calculada automáticamente: Hawkish = tipo real > +1%, Neutral = entre −0.5% y +1%, Dovish = tipo real < −0.5%. "
            "Para inflaciones sin datos, se usa el último valor conocido como referencia.",
            style={"fontSize": "0.68rem", "color": COLORS["text_muted"], "marginTop": "8px", "fontStyle": "italic"},
        ),
    ], style={"marginBottom": "28px"})


def _build_global_rates_chart() -> html.Div:
    """Gráfico comparativo de tipos de interés globales con selector."""
    options = [
        {"label": "🇺🇸 Fed", "value": "FED"},
        {"label": "🇪🇺 BCE", "value": "ECB"},
        {"label": "🇬🇧 BoE", "value": "BOE"},
        {"label": "🇯🇵 BoJ", "value": "BOJ"},
        {"label": "🇨🇭 SNB", "value": "SNB"},
        {"label": "🇨🇦 BoC", "value": "BOC"},
        {"label": "🇦🇺 RBA", "value": "RBA"},
        {"label": "🇧🇷 BCB", "value": "BCB"},
    ]

    checklist = dcc.Checklist(
        id="m4-cb-checklist",
        options=options,
        value=["FED", "ECB", "BOE", "BOJ"],
        inline=True,
        style={"fontSize": "0.78rem", "color": COLORS["text_muted"], "marginBottom": "8px"},
        inputStyle={"marginRight": "4px", "marginLeft": "12px"},
    )

    range_btns = html.Div([
        html.Button(r, id=f"m4-rates-range-{r}", n_clicks=0, style=_btn_style())
        for r in ["1A", "2A", "5A", "10A", "MÁX"]
    ], style={"display": "flex", "alignItems": "center", "marginBottom": "8px"})

    return html.Div([
        _section_label("TIPOS DE INTERÉS GLOBALES COMPARADOS"),
        checklist,
        range_btns,
        dcc.Graph(id="m4-global-rates-chart", config={"displayModeBar": False}),
        dcc.Store(id="m4-rates-range-store", data="5A"),
    ], style={"marginBottom": "28px"})


def _build_policy_divergence() -> html.Div:
    """Scatter de divergencia de políticas: inflación vs tipo oficial."""
    data_points = []
    gdp_sizes = {
        "FED": 27000, "ECB": 17000, "BOE": 3100, "BOJ": 4200, "SNB": 800,
        "BOC": 2100, "RBA": 1700, "PBOC": 18000, "RBI": 3500, "BCB": 2100, "BANXICO": 1300,
    }

    for cb in CB_CATALOG:
        rate, _ = get_latest_value(cb["rate_id"])
        if rate is None:
            rate = cb["static_rate"]
        inf_val = None
        if cb["inflation_id"]:
            inf_val, _ = get_latest_value(cb["inflation_id"])
        if inf_val is None:
            inf_val = cb["static_inf"]

        real = (rate - inf_val) if (rate is not None and inf_val is not None) else 0.0

        if real > 1.0:
            color = C["negative"]  # hawkish = rojo
        elif real >= -0.5:
            color = COLORS["text_muted"]  # neutral = gris
        else:
            color = C["positive"]  # dovish = verde

        data_points.append({
            "key": cb["key"], "name": cb["name"], "flag": cb["flag"],
            "inf": inf_val or 0, "rate": rate or 0,
            "real": real, "color": color,
            "size": max(10, min(50, gdp_sizes.get(cb["key"], 500) / 500)),
        })

    if not data_points:
        return html.Div([
            _section_label("MAPA DE DIVERGENCIA DE POLÍTICAS"),
            create_empty_state("Sin datos disponibles"),
        ], style={"marginBottom": "28px"})

    fig = go.Figure()

    for pt in data_points:
        fig.add_trace(go.Scatter(
            x=[pt["inf"]],
            y=[pt["rate"]],
            mode="markers+text",
            marker={"size": pt["size"], "color": pt["color"], "opacity": 0.85, "line": {"width": 1, "color": COLORS["border"]}},
            text=[f"{pt['flag']} {pt['key']}"],
            textposition="top center",
            textfont={"size": 10, "color": COLORS["text_muted"]},
            name=f"{pt['flag']} {pt['name']}",
            hovertemplate=(
                f"<b>{pt['flag']} {pt['name']}</b><br>"
                f"Inflación: {pt['inf']:.1f}%<br>"
                f"Tipo oficial: {pt['rate']:.2f}%<br>"
                f"Tipo real: {pt['real']:+.2f}%<extra></extra>"
            ),
            showlegend=False,
        ))

    # Línea tipo real = 0 (diagonal)
    max_val = max(pt["inf"] for pt in data_points) + 2
    fig.add_shape(type="line", x0=0, y0=0, x1=max_val, y1=max_val,
                  line={"color": "#374151", "width": 1.5, "dash": "dash"})
    fig.add_annotation(x=max_val - 1, y=max_val + 0.3, text="Tipo real = 0%",
                       font={"color": "#6b7280", "size": 9}, showarrow=False)

    layout = get_base_layout("Divergencia de Políticas Monetarias (inflación vs tipo oficial)", height=420)
    layout["xaxis"] = {**layout.get("xaxis", {}), "title": {"text": "Inflación actual (%)", "font": {"color": "#9ca3af", "size": 11}}, "ticksuffix": "%"}
    layout["yaxis"] = {**layout.get("yaxis", {}), "title": {"text": "Tipo oficial (%)", "font": {"color": "#9ca3af", "size": 11}}, "ticksuffix": "%"}
    fig.update_layout(**layout)

    return html.Div([
        _section_label("MAPA DE DIVERGENCIA DE POLÍTICAS MONETARIAS"),
        dcc.Graph(figure=fig, config={"displayModeBar": False}),
        html.Div(
            "Puntos por encima de la línea diagonal = tipo real positivo (política restrictiva). "
            "Por debajo = represión financiera. Tamaño del punto proporcional al PIB del país. "
            "🔴 Hawkish · ⚫ Neutral · 🟢 Dovish",
            style={"fontSize": "0.70rem", "color": COLORS["text_muted"], "marginTop": "8px", "fontStyle": "italic"},
        ),
    ], style={"marginBottom": "28px"})


def _build_tab1_content() -> html.Div:
    return html.Div([
        _build_cb_table(),
        _build_global_rates_chart(),
        _build_policy_divergence(),
    ], style={"padding": "20px"})


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — LA FED EN DETALLE
# ══════════════════════════════════════════════════════════════════════════════

def _build_fed_historical() -> html.Div:
    """Sección 2.1 — Histórico del Fed Funds Rate con ciclos."""
    df = get_series(ID_FED_FUNDS, days=365 * 10)

    recessions = [
        ("2001-03-01", "2001-11-01"),
        ("2007-12-01", "2009-06-01"),
        ("2020-02-01", "2020-04-01"),
    ]

    if df.empty:
        empty = create_empty_state("Sin datos del Fed Funds Rate", "Requiere serie fred_fed_funds_us en BD")
        chart_el = empty
    else:
        df = df.sort_values("timestamp")
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df["timestamp"], y=df["value"],
            name="Fed Funds Rate",
            line={"color": C["primary"], "width": 2},
            fill="tozeroy",
            fillcolor="rgba(59,130,246,0.10)",
            hovertemplate="<b>Fed Funds</b>: %{y:.2f}%<br>%{x|%b %Y}<extra></extra>",
        ))
        for r_start, r_end in recessions:
            fig.add_vrect(x0=r_start, x1=r_end, fillcolor="#374151", opacity=0.25, layer="below", line_width=0,
                          annotation_text="Recesión", annotation_position="top left",
                          annotation_font={"size": 8, "color": "#6b7280"})

        # Anotaciones clave
        annotations = [
            ("2022-03-17", "Primera subida post-COVID"),
            ("2023-07-27", "Máximo ciclo"),
            ("2024-09-18", "Primera bajada"),
        ]
        for ann_date, ann_text in annotations:
            try:
                ann_dt = datetime.strptime(ann_date, "%Y-%m-%d")
                sub = df[df["timestamp"] <= ann_dt]
                if not sub.empty:
                    y_val = float(sub.iloc[-1]["value"])
                    fig.add_annotation(x=ann_dt, y=y_val, text=ann_text,
                                       showarrow=True, arrowhead=2, arrowcolor=C["primary"],
                                       font={"color": "#9ca3af", "size": 8},
                                       arrowsize=0.6, ax=30, ay=-30)
            except Exception:
                pass

        latest_rate, _ = get_latest_value(ID_FED_FUNDS)
        if latest_rate:
            fig.add_hline(y=latest_rate, line_dash="dot", line_color=C["primary"], line_width=1,
                          annotation_text=f"Actual: {latest_rate:.2f}%",
                          annotation_font={"color": C["primary"], "size": 10})

        range_btns_config = dict(
            buttons=[
                {"count": 5,  "label": "5A",  "step": "year", "stepmode": "backward"},
                {"count": 10, "label": "10A", "step": "year", "stepmode": "backward"},
                {"count": 20, "label": "20A", "step": "year", "stepmode": "backward"},
                {"step": "all", "label": "MÁX"},
            ],
            bgcolor="#111827", activecolor=C["primary"],
            bordercolor="#1f2937", font={"color": "#9ca3af", "size": 11},
            x=0, xanchor="left", y=1.08, yanchor="top",
        )
        layout = get_base_layout("Fed Funds Rate — Histórico con Recesiones", height=380)
        layout["xaxis"] = {**layout.get("xaxis", {}), "rangeselector": range_btns_config}
        layout["yaxis"] = {**layout.get("yaxis", {}), "ticksuffix": "%"}
        fig.update_layout(**layout)
        chart_el = dcc.Graph(figure=fig, config={"displayModeBar": False})

    # Tabla de ciclos históricos
    cycle_headers = ["Inicio subida", "Fin subida", "Tipo máx.", "Inicio bajada", "Tipo mín.", "Duración"]
    cycle_rows = []
    for i, cyc in enumerate(FED_CYCLES):
        is_current = cyc["meses"] is None
        style_current = {"backgroundColor": "#1e3a5f", "fontWeight": "600"} if is_current else {}
        dur = f"{cyc['meses']}M" if cyc["meses"] else "En curso ●"
        cycle_rows.append(html.Tr([
            html.Td(cyc["inicio_subida"], style={**style_current, "padding": "5px 10px", "fontSize": "0.75rem"}),
            html.Td(cyc["fin_subida"], style={**style_current, "padding": "5px 10px", "fontSize": "0.75rem"}),
            html.Td(f"{cyc['tipo_max']:.2f}%", style={**style_current, "padding": "5px 10px", "fontSize": "0.75rem", "fontFamily": "monospace", "color": C["negative"]}),
            html.Td(cyc["inicio_bajada"], style={**style_current, "padding": "5px 10px", "fontSize": "0.75rem"}),
            html.Td(f"{cyc['tipo_min']:.2f}%", style={**style_current, "padding": "5px 10px", "fontSize": "0.75rem", "fontFamily": "monospace", "color": C["positive"]}),
            html.Td(dur, style={**style_current, "padding": "5px 10px", "fontSize": "0.75rem", "color": C["warning"] if is_current else COLORS["text_muted"]}),
        ], style={"borderBottom": f"1px solid {COLORS['border']}"}))

    cycle_table = html.Div(
        html.Table([
            html.Thead(html.Tr([
                html.Th(h, style={"padding": "6px 10px", "fontSize": "0.62rem", "letterSpacing": "0.06em", "color": COLORS["text_label"]})
                for h in cycle_headers
            ])),
            html.Tbody(cycle_rows),
        ], style={"width": "100%", "borderCollapse": "collapse"}),
        style={"overflowX": "auto", "marginTop": "12px"},
    )

    return html.Div([
        _section_label("HISTÓRICO DEL FED FUNDS RATE — CICLOS DE POLÍTICA MONETARIA"),
        chart_el,
        html.Div([
            html.Div("CICLOS HISTÓRICOS DE TIPOS (selección)", style={
                "fontSize": "0.62rem", "color": COLORS["text_label"], "fontWeight": "600",
                "letterSpacing": "0.08em", "marginTop": "16px", "marginBottom": "4px",
            }),
            cycle_table,
        ], style=_card_style()),
    ], style={"marginBottom": "28px"})


def _build_fed_balance() -> html.Div:
    """Sección 2.2 — Balance de la Fed (QE y QT)."""
    df = get_series(ID_FED_BALANCE, days=365 * 17)

    if df.empty:
        return html.Div([
            _section_label("BALANCE DE LA FED — QE Y QT"),
            create_empty_state("Sin datos del balance de la Fed", "Requiere serie fred_walcl_us en BD"),
        ], style={"marginBottom": "28px"})

    df = df.sort_values("timestamp").copy()
    # WALCL está en millones → dividir por 1,000,000 para billones
    df["value_bn"] = df["value"] / 1_000_000

    latest_bn = float(df.iloc[-1]["value_bn"])
    peak_bn = float(df["value_bn"].max())
    change_from_peak = latest_bn - peak_bn

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["timestamp"], y=df["value_bn"],
        name="Balance Fed",
        line={"color": C["primary"], "width": 2},
        fill="tozeroy",
        fillcolor="rgba(59,130,246,0.12)",
        hovertemplate="<b>Balance Fed</b>: $%{y:.2f}T<br>%{x|%b %Y}<extra></extra>",
    ))

    # Anotaciones QE/QT
    qe_annotations = [
        ("2009-01-01", "QE1", 1.5),
        ("2010-10-01", "QE2", 2.0),
        ("2012-09-01", "QE3", 2.5),
        ("2020-03-01", "QE COVID", 4.0),
        ("2022-06-01", "QT", 9.0),
    ]
    for ann_date, label, y_pos in qe_annotations:
        try:
            fig.add_annotation(
                x=ann_date, y=y_pos,
                text=label, showarrow=False,
                font={"color": "#6b7280", "size": 9},
                bgcolor="rgba(17,24,39,0.8)",
            )
        except Exception:
            pass

    # Línea pre-COVID (~4T)
    fig.add_hline(y=4.0, line_dash="dot", line_color="#6b7280", line_width=1,
                  annotation_text="Nivel pre-COVID (~4T$)",
                  annotation_font={"color": "#6b7280", "size": 9})

    layout = get_base_layout("Balance Total de la Reserva Federal (billones USD)", height=380)
    layout["yaxis"] = {**layout.get("yaxis", {}), "tickprefix": "$", "ticksuffix": "T"}
    fig.update_layout(**layout)

    # Métricas clave
    kpis = html.Div([
        _compact_metric("BALANCE ACTUAL", f"${latest_bn:.2f}T", "Billones USD"),
        _compact_metric("PICO MÁXIMO", f"${peak_bn:.2f}T", "Billones USD"),
        _compact_metric("CAMBIO DESDE PICO", f"{change_from_peak:+.2f}T",
                        "QT acumulado",
                        C["negative"] if change_from_peak < 0 else C["positive"]),
        _compact_metric("% REDUCCIÓN", f"{change_from_peak/peak_bn*100:.1f}%" if peak_bn else "—",
                        "vs máximo histórico",
                        C["negative"] if change_from_peak < 0 else C["positive"]),
    ], style={"display": "flex", "gap": "8px", "flexWrap": "wrap", "marginTop": "12px"})

    return html.Div([
        _section_label("BALANCE DE LA FED — QE Y QT HISTÓRICO"),
        dcc.Graph(figure=fig, config={"displayModeBar": False}),
        kpis,
    ], style={"marginBottom": "28px"})


def _build_dot_plot() -> html.Div:
    """Sección 2.3 — Dot Plot de la Fed."""
    d = DOT_PLOT_DATA

    fig = go.Figure()
    colors_by_year = {2025: C["primary"], 2026: C["positive"], 2027: C["warning"]}

    for year, dots in d["dots"].items():
        color = colors_by_year.get(year, "#9ca3af")
        jittered_x = [year + (i - len(dots)/2) * 0.05 for i in range(len(dots))]
        fig.add_trace(go.Scatter(
            x=jittered_x, y=dots,
            mode="markers",
            name=str(year),
            marker={"size": 10, "color": color, "opacity": 0.75, "symbol": "circle"},
            hovertemplate=f"<b>{year}</b>: %{{y:.3f}}%<extra></extra>",
        ))
        # Mediana
        median_key = f"mediana_{year}"
        if median_key in d:
            fig.add_shape(type="line",
                          x0=year - 0.3, y0=d[median_key],
                          x1=year + 0.3, y1=d[median_key],
                          line={"color": color, "width": 3})
            fig.add_annotation(x=year + 0.35, y=d[median_key],
                                text=f"Mediana: {d[median_key]:.3f}%",
                                font={"color": color, "size": 9},
                                showarrow=False, xanchor="left")

    layout = get_base_layout(f"Dot Plot del FOMC — {d['publicado']}", height=380)
    layout["xaxis"] = {**layout.get("xaxis", {}), "tickvals": [2025, 2026, 2027], "ticktext": ["2025", "2026 (proyección)", "2027 (proyección)"]}
    layout["yaxis"] = {**layout.get("yaxis", {}), "ticksuffix": "%", "range": [2.5, 5.5]}
    fig.update_layout(**layout)

    proyecciones = html.Div([
        html.Div([
            html.Span("Proyección mediana del FOMC: ", style={"fontSize": "0.75rem", "color": COLORS["text_muted"]}),
            html.Span(f"Fin 2026: {d['mediana_2026']:.3f}% · ", style={"fontSize": "0.75rem", "fontFamily": "monospace", "color": C["positive"]}),
            html.Span(f"Fin 2027: {d['mediana_2027']:.3f}% · ", style={"fontSize": "0.75rem", "fontFamily": "monospace", "color": C["warning"]}),
            html.Span(f"Largo plazo (neutral): {d['mediana_largo_plazo']:.3f}%", style={"fontSize": "0.75rem", "fontFamily": "monospace", "color": C["primary"]}),
        ]),
        html.Div(
            "Nota: El dot plot se actualiza trimestralmente (marzo, junio, septiembre, diciembre). "
            "Cada punto representa la proyección de un miembro del FOMC. La mediana es el consenso del comité.",
            style={"fontSize": "0.68rem", "color": COLORS["text_muted"], "marginTop": "6px", "fontStyle": "italic"},
        ),
    ], style={"padding": "10px 14px", "backgroundColor": COLORS["card_bg"],
               "border": f"1px solid {COLORS['border']}", "borderRadius": "6px",
               "borderLeft": f"3px solid {C['primary']}", "marginTop": "10px"})

    return html.Div([
        _section_label("DOT PLOT DEL FOMC — PROYECCIONES DE TIPOS"),
        dcc.Graph(figure=fig, config={"displayModeBar": False}),
        proyecciones,
    ], style={"marginBottom": "28px"})


def _build_fed_probabilities() -> html.Div:
    """Sección 2.4 — Probabilidades implícitas del mercado (CME FedWatch)."""
    fed_now, fed_ts = get_latest_value(ID_FED_FUNDS)
    date_str = fed_ts.strftime("%d/%m/%Y") if fed_ts else "—"

    info_panel = html.Div([
        html.Div("PROBABILIDADES IMPLÍCITAS CME FEDWATCH", style={
            "fontSize": "0.60rem", "color": COLORS["text_label"],
            "fontWeight": "600", "letterSpacing": "0.08em", "marginBottom": "12px",
        }),
        html.Div([
            html.Span("📊 ", style={"fontSize": "1.2rem"}),
            html.Div([
                html.Div(f"Fed Funds Rate actual: {_pct(fed_now)}", style={
                    "fontSize": "1.1rem", "fontWeight": "700", "fontFamily": "monospace", "color": COLORS["text"],
                }),
                html.Div(f"Última actualización: {date_str}", style={"fontSize": "0.72rem", "color": COLORS["text_muted"]}),
            ]),
        ], style={"display": "flex", "alignItems": "center", "gap": "12px", "marginBottom": "14px"}),

        html.Div([
            html.Div(
                "Para probabilidades en tiempo real de cada reunión del FOMC, consultar la herramienta oficial del CME Group:",
                style={"fontSize": "0.78rem", "color": COLORS["text_muted"], "marginBottom": "8px"},
            ),
            html.Div("CME FedWatch Tool", style={
                "fontSize": "0.85rem", "fontWeight": "600", "color": C["primary"],
                "fontFamily": "monospace",
            }),
            html.Div(
                "Buscar 'CME FedWatch' en tu navegador para acceder a las probabilidades implícitas derivadas "
                "de los futuros del Fed Funds Rate.",
                style={"fontSize": "0.72rem", "color": COLORS["text_muted"], "marginTop": "6px", "fontStyle": "italic"},
            ),
        ], style={
            "padding": "12px 16px",
            "backgroundColor": COLORS["background"],
            "border": f"1px solid {COLORS['border']}",
            "borderRadius": "6px",
            "borderLeft": f"3px solid {C['primary']}",
        }),

        # Escenarios interpretativos
        html.Div([
            html.Div("INTERPRETACIÓN DE ESCENARIOS TÍPICOS", style={
                "fontSize": "0.60rem", "color": COLORS["text_label"],
                "fontWeight": "600", "letterSpacing": "0.08em", "marginTop": "14px", "marginBottom": "8px",
            }),
            *[
                html.Div([
                    html.Span(f"{scenario}: ", style={"fontWeight": "600", "fontSize": "0.75rem", "color": COLORS["text"]}),
                    html.Span(desc, style={"fontSize": "0.72rem", "color": COLORS["text_muted"]}),
                ], style={"marginBottom": "4px"})
                for scenario, desc in [
                    ("+25pb", "Decisión de subir tipos 25 puntos básicos → señal hawkish"),
                    ("Sin cambio", "Pausa — la Fed mantiene el tipo actual"),
                    ("−25pb", "Bajada de 25pb → relajación monetaria, señal dovish"),
                    ("−50pb", "Bajada agresiva → suele ocurrir en crisis o recesión"),
                ]
            ],
        ]),
    ], style={**_card_style(), "marginTop": "0"})

    return html.Div([
        _section_label("PROBABILIDADES IMPLÍCITAS DEL MERCADO — REUNIONES FOMC"),
        info_panel,
    ], style={"marginBottom": "28px"})


def _build_taylor_rule() -> html.Div:
    """Sección 2.5 — Brecha Inflación-Objetivo y Taylor Rule."""
    df_cpi = get_series(ID_CPI_YOY_US, days=365 * 3)
    fed_now, _ = get_latest_value(ID_FED_FUNDS)

    if df_cpi.empty:
        return html.Div([
            _section_label("INFLACIÓN VS OBJETIVO Y TAYLOR RULE"),
            create_empty_state("Sin datos de inflación US", "Requiere serie fred_cpi_yoy_us en BD"),
        ], style={"marginBottom": "28px"})

    df_cpi = df_cpi.sort_values("timestamp")
    cpi_now = float(df_cpi.iloc[-1]["value"]) if not df_cpi.empty else None

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_cpi["timestamp"], y=df_cpi["value"],
        name="IPC EE.UU. (YoY)",
        line={"color": C["negative"], "width": 2},
        hovertemplate="<b>IPC</b>: %{y:.2f}%<br>%{x|%b %Y}<extra></extra>",
    ))
    fig.add_hline(y=2.0, line_dash="dash", line_color="#6b7280", line_width=1.5,
                  annotation_text="Objetivo Fed: 2%",
                  annotation_font={"color": "#9ca3af", "size": 10})

    # Relleno rojo cuando supera 2%
    target = pd.Series([2.0] * len(df_cpi), index=df_cpi.index)
    over = df_cpi["value"].clip(lower=2.0)
    fig.add_trace(go.Scatter(
        x=df_cpi["timestamp"], y=over,
        fill="tonexty",
        fillcolor="rgba(239,68,68,0.12)",
        line={"color": "rgba(0,0,0,0)"},
        name="Brecha > objetivo",
        showlegend=True,
    ))

    layout = get_base_layout("Inflación EE.UU. vs Objetivo 2% (Fed)", height=320)
    layout["yaxis"] = {**layout.get("yaxis", {}), "ticksuffix": "%"}
    fig.update_layout(**layout)

    # Cálculo Taylor Rule simplificado
    taylor_rate = None
    taylor_text = ""
    if cpi_now is not None:
        neutral_rate = 2.0
        output_gap = 0.0  # simplificación
        taylor_rate = neutral_rate + 1.5 * (cpi_now - 2.0) + 0.5 * output_gap

        if fed_now is not None:
            diff = taylor_rate - fed_now
            if abs(diff) < 0.25:
                stance = "en línea con lo que sugiere la regla"
                stance_color = C["positive"]
            elif diff > 0:
                stance = f"por DEBAJO de lo que sugiere la regla (diferencia: {abs(diff):.2f}pp)"
                stance_color = C["warning"]
            else:
                stance = f"por ENCIMA de lo que sugiere la regla (diferencia: {abs(diff):.2f}pp)"
                stance_color = C["primary"]

            taylor_text = (
                f"Con una inflación del {cpi_now:.2f}% y un output gap estimado de ~0%, "
                f"la Taylor Rule sugiere un tipo óptimo de aproximadamente **{taylor_rate:.2f}%**. "
                f"El tipo actual de la Fed ({fed_now:.2f}%) está {stance}."
            )
        else:
            taylor_text = (
                f"Con una inflación del {cpi_now:.2f}%, "
                f"la Taylor Rule sugiere un tipo óptimo de aproximadamente **{taylor_rate:.2f}%**."
            )

    taylor_panel = html.Div([
        html.Div("TAYLOR RULE — TIPO ÓPTIMO IMPLÍCITO", style={
            "fontSize": "0.60rem", "color": COLORS["text_label"],
            "fontWeight": "600", "letterSpacing": "0.08em", "marginBottom": "8px",
        }),
        dbc.Row([
            dbc.Col([
                html.Div("Tipo según Taylor Rule", style={"fontSize": "0.68rem", "color": COLORS["text_muted"]}),
                html.Div(_pct(taylor_rate) if taylor_rate else "—", style={
                    "fontSize": "1.6rem", "fontWeight": "700",
                    "fontFamily": "monospace", "color": C["warning"],
                }),
            ], width=3),
            dbc.Col([
                html.Div("Tipo actual Fed", style={"fontSize": "0.68rem", "color": COLORS["text_muted"]}),
                html.Div(_pct(fed_now) if fed_now else "—", style={
                    "fontSize": "1.6rem", "fontWeight": "700",
                    "fontFamily": "monospace", "color": C["primary"],
                }),
            ], width=3),
            dbc.Col(
                dcc.Markdown(taylor_text, style={"fontSize": "0.78rem", "color": COLORS["text_muted"]}),
                width=6,
            ),
        ]),
        html.Div(
            "Fórmula: Tipo Taylor ≈ 2% (tipo neutral) + 1.5 × (inflación − 2%) + 0.5 × output gap. "
            "Es una guía académica, no una regla que la Fed siga mecánicamente.",
            style={"fontSize": "0.68rem", "color": COLORS["text_label"], "marginTop": "8px", "fontStyle": "italic"},
        ),
    ], style={**_card_style(), "marginTop": "12px"})

    return html.Div([
        _section_label("INFLACIÓN VS OBJETIVO 2% Y TAYLOR RULE"),
        dcc.Graph(figure=fig, config={"displayModeBar": False}),
        taylor_panel,
    ], style={"marginBottom": "28px"})


def _build_tab2_content() -> html.Div:
    return html.Div([
        _build_fed_historical(),
        _build_fed_balance(),
        _build_dot_plot(),
        _build_fed_probabilities(),
        _build_taylor_rule(),
    ], style={"padding": "20px"})


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — EL BCE EN DETALLE
# ══════════════════════════════════════════════════════════════════════════════

def _build_ecb_rates_history() -> html.Div:
    """Sección 3.1 — Los tres tipos del BCE desde 1999."""
    df_dep = get_series(ID_ECB_RATE, days=365 * 27)      # facilidad depósito
    df_main = get_series(ID_ECB_MAIN_RATE, days=365 * 27)  # tipo principal
    df_marg = get_series(ID_ECB_MARGINAL, days=365 * 27)  # facilidad crédito

    has_data = not df_dep.empty or not df_main.empty or not df_marg.empty

    if not has_data:
        return html.Div([
            _section_label("TIPOS OFICIALES DEL BCE — CORREDOR DE TIPOS (DESDE 1999)"),
            create_empty_state("Sin datos de tipos del BCE", "Requiere series ecb_*_rate_ea en BD"),
        ], style={"marginBottom": "28px"})

    fig = go.Figure()
    for df, name, color in [
        (df_main, "Tipo principal (MRO)", "#3b82f6"),
        (df_dep, "Facilidad depósito", "#10b981"),
        (df_marg, "Facilidad crédito marginal", "#f59e0b"),
    ]:
        if not df.empty:
            df = df.sort_values("timestamp")
            fig.add_trace(go.Scatter(
                x=df["timestamp"], y=df["value"],
                name=name, line={"color": color, "width": 2},
                hovertemplate=f"<b>{name}</b>: %{{y:.2f}}%<br>%{{x|%b %Y}}<extra></extra>",
            ))

    fig.add_hline(y=0, line_dash="solid", line_color="#374151", line_width=1)

    # Anotaciones clave
    ecb_annotations = [
        ("2014-06-01", "Tipos negativos"),
        ("2022-07-21", "Primera subida post-COVID"),
        ("2024-06-06", "Primera bajada"),
    ]
    for ann_date, ann_text in ecb_annotations:
        try:
            ann_dt = datetime.strptime(ann_date, "%Y-%m-%d")
            sub = df_dep[df_dep["timestamp"] <= ann_dt] if not df_dep.empty else pd.DataFrame()
            y_val = float(sub.iloc[-1]["value"]) if not sub.empty else 0
            fig.add_annotation(x=ann_dt, y=y_val, text=ann_text,
                               showarrow=True, arrowhead=2, arrowcolor="#10b981",
                               font={"color": "#9ca3af", "size": 8},
                               arrowsize=0.6, ax=30, ay=-30)
        except Exception:
            pass

    range_btns_config = dict(
        buttons=[
            {"count": 2,  "label": "2A",  "step": "year", "stepmode": "backward"},
            {"count": 5,  "label": "5A",  "step": "year", "stepmode": "backward"},
            {"count": 10, "label": "10A", "step": "year", "stepmode": "backward"},
            {"step": "all", "label": "MÁX"},
        ],
        bgcolor="#111827", activecolor=C["primary"],
        bordercolor="#1f2937", font={"color": "#9ca3af", "size": 11},
        x=0, xanchor="left", y=1.08, yanchor="top",
    )
    layout = get_base_layout("Tipos Oficiales del BCE — Corredor de Tipos (desde 1999)", height=380)
    layout["xaxis"] = {**layout.get("xaxis", {}), "rangeselector": range_btns_config}
    layout["yaxis"] = {**layout.get("yaxis", {}), "ticksuffix": "%"}
    fig.update_layout(**layout)

    return html.Div([
        _section_label("TIPOS OFICIALES DEL BCE — CORREDOR DE TIPOS"),
        dcc.Graph(figure=fig, config={"displayModeBar": False}),
        html.Div(
            "El corredor de tipos muestra los tres instrumentos de política monetaria del BCE. "
            "La facilidad de depósito (verde) es el tipo más seguido actualmente — es el suelo del mercado interbancario.",
            style={"fontSize": "0.70rem", "color": COLORS["text_muted"], "marginTop": "8px", "fontStyle": "italic"},
        ),
    ], style={"marginBottom": "28px"})


def _build_ecb_balance() -> html.Div:
    """Sección 3.2 — Balance del BCE."""
    df_ecb = get_series(ID_ECB_BALANCE, days=365 * 17)

    if df_ecb.empty:
        return html.Div([
            _section_label("BALANCE DEL BCE — COMPARATIVA CON LA FED"),
            create_empty_state("Sin datos del balance del BCE", "Requiere serie ecb_total_assets_ea en BD"),
        ], style={"marginBottom": "28px"})

    df_ecb = df_ecb.sort_values("timestamp").copy()
    # Asumimos valores en millones EUR → billones
    df_ecb["value_bn"] = df_ecb["value"] / 1_000_000

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_ecb["timestamp"], y=df_ecb["value_bn"],
        name="Balance BCE",
        line={"color": "#10b981", "width": 2},
        fill="tozeroy",
        fillcolor="rgba(16,185,129,0.10)",
        hovertemplate="<b>Balance BCE</b>: €%{y:.2f}T<br>%{x|%b %Y}<extra></extra>",
    ))

    qe_ecb_annotations = [
        ("2015-03-01", "QE APP"),
        ("2020-03-18", "PEPP COVID"),
        ("2023-01-01", "Reducción"),
    ]
    for ann_date, label in qe_ecb_annotations:
        try:
            fig.add_annotation(x=ann_date, y=3.0, text=label, showarrow=False,
                               font={"color": "#6b7280", "size": 9},
                               bgcolor="rgba(17,24,39,0.8)")
        except Exception:
            pass

    layout = get_base_layout("Balance Total del BCE (billones EUR)", height=340)
    layout["yaxis"] = {**layout.get("yaxis", {}), "tickprefix": "€", "ticksuffix": "T"}
    fig.update_layout(**layout)

    latest = float(df_ecb.iloc[-1]["value_bn"])
    peak = float(df_ecb["value_bn"].max())

    kpis = html.Div([
        _compact_metric("BALANCE ACTUAL BCE", f"€{latest:.2f}T", "Billones EUR"),
        _compact_metric("PICO MÁXIMO", f"€{peak:.2f}T", "Post-PEPP COVID"),
        _compact_metric("REDUCCIÓN", f"{(latest-peak)/peak*100:.1f}%", "vs pico", C["negative"]),
    ], style={"display": "flex", "gap": "8px", "flexWrap": "wrap", "marginTop": "12px"})

    return html.Div([
        _section_label("BALANCE DEL BCE — PROGRAMAS DE COMPRAS"),
        dcc.Graph(figure=fig, config={"displayModeBar": False}),
        kpis,
    ], style={"marginBottom": "28px"})


def _build_euribor_section() -> html.Div:
    """Sección 3.3 — EURIBOR 12M y calculadora de hipoteca variable."""
    df_eur = get_series(ID_EURIBOR_12M, days=365 * 20)
    eur_now, eur_ts = get_latest_value(ID_EURIBOR_12M)
    _, eur_1y, _, _ = get_change(ID_EURIBOR_12M, period_days=365)
    _, eur_2y, _, _ = get_change(ID_EURIBOR_12M, period_days=730)

    # Gráfico EURIBOR histórico
    if df_eur.empty:
        chart_el = create_empty_state("Sin datos del EURIBOR 12M", "Requiere serie ecb_euribor_12m_ea en BD")
    else:
        df_eur = df_eur.sort_values("timestamp")
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df_eur["timestamp"], y=df_eur["value"],
            name="EURIBOR 12M",
            line={"color": "#8b5cf6", "width": 2},
            fill="tozeroy",
            fillcolor="rgba(139,92,246,0.10)",
            hovertemplate="<b>EURIBOR 12M</b>: %{y:.3f}%<br>%{x|%b %Y}<extra></extra>",
        ))
        fig.add_hline(y=0, line_dash="solid", line_color="#374151", line_width=1)

        eur_annotations = [
            ("2008-10-01", "Máx. pre-crisis: 5.5%"),
            ("2016-02-01", "Entra en negativo"),
            ("2022-07-01", "Sale del negativo"),
            ("2023-10-01", "Pico reciente: ~4.2%"),
        ]
        for ann_date, label in eur_annotations:
            try:
                ann_dt = datetime.strptime(ann_date, "%Y-%m-%d")
                sub = df_eur[df_eur["timestamp"] <= ann_dt]
                if not sub.empty:
                    y_val = float(sub.iloc[-1]["value"])
                    fig.add_annotation(x=ann_dt, y=y_val, text=label,
                                       showarrow=True, arrowhead=2, arrowcolor="#8b5cf6",
                                       font={"color": "#9ca3af", "size": 8},
                                       arrowsize=0.6, ax=-40, ay=-25)
            except Exception:
                pass

        layout = get_base_layout("EURIBOR 12 Meses — Histórico", height=340)
        layout["yaxis"] = {**layout.get("yaxis", {}), "ticksuffix": "%"}
        fig.update_layout(**layout)
        chart_el = dcc.Graph(figure=fig, config={"displayModeBar": False})

    # Calculadora de hipoteca
    calc_section = html.Div([
        html.Div("CALCULADORA DE HIPOTECA VARIABLE", style={
            "fontSize": "0.65rem", "letterSpacing": "0.1em",
            "color": COLORS["text_label"], "fontWeight": "600",
            "marginBottom": "14px", "marginTop": "20px",
        }),
        dbc.Row([
            dbc.Col([
                html.Label("Capital pendiente (€)", style={"fontSize": "0.72rem", "color": COLORS["text_muted"], "display": "block", "marginBottom": "4px"}),
                dcc.Input(
                    id="m4-mortgage-capital", type="number",
                    value=150000, min=10000, max=2000000, step=1000,
                    style={"backgroundColor": COLORS["background"],
                           "border": f"1px solid {COLORS['border']}",
                           "color": COLORS["text"], "borderRadius": "4px",
                           "padding": "6px 10px", "fontSize": "0.82rem", "width": "100%"},
                    debounce=True,
                ),
            ], width=4),
            dbc.Col([
                html.Label("Años restantes", style={"fontSize": "0.72rem", "color": COLORS["text_muted"], "display": "block", "marginBottom": "4px"}),
                dcc.Input(
                    id="m4-mortgage-years", type="number",
                    value=20, min=1, max=40, step=1,
                    style={"backgroundColor": COLORS["background"],
                           "border": f"1px solid {COLORS['border']}",
                           "color": COLORS["text"], "borderRadius": "4px",
                           "padding": "6px 10px", "fontSize": "0.82rem", "width": "100%"},
                    debounce=True,
                ),
            ], width=4),
            dbc.Col([
                html.Label("Diferencial sobre EURIBOR (%)", style={"fontSize": "0.72rem", "color": COLORS["text_muted"], "display": "block", "marginBottom": "4px"}),
                dcc.Input(
                    id="m4-mortgage-spread", type="number",
                    value=0.99, min=0, max=5, step=0.01,
                    style={"backgroundColor": COLORS["background"],
                           "border": f"1px solid {COLORS['border']}",
                           "color": COLORS["text"], "borderRadius": "4px",
                           "padding": "6px 10px", "fontSize": "0.82rem", "width": "100%"},
                    debounce=True,
                ),
            ], width=4),
        ], className="g-3 mb-3"),
        html.Div(id="m4-mortgage-result"),
    ], style=_card_style())

    eur_date_str = eur_ts.strftime("%d/%m/%Y") if eur_ts else "—"

    return html.Div([
        _section_label("EURIBOR 12M — EL TIPO QUE MÁS TE AFECTA"),
        html.Div([
            html.Span(f"EURIBOR 12M actual: ", style={"fontSize": "0.75rem", "color": COLORS["text_muted"]}),
            html.Span(f"{eur_now:.3f}%" if eur_now else "—",
                      style={"fontSize": "1.0rem", "fontWeight": "700", "fontFamily": "monospace", "color": "#8b5cf6"}),
            html.Span(f"  ({eur_date_str})", style={"fontSize": "0.72rem", "color": COLORS["text_muted"]}),
        ], style={"marginBottom": "10px"}),
        chart_el,
        calc_section,
    ], style={"marginBottom": "28px"})


def _build_ecb_fed_divergence() -> html.Div:
    """Sección 3.4 — Divergencia BCE-Fed y EUR/USD."""
    df_fed = get_series(ID_FED_FUNDS, days=365 * 11)
    df_ecb = get_series(ID_ECB_RATE, days=365 * 11)
    df_fx = get_series(ID_EURUSD, days=365 * 11)

    has_rate_data = not df_fed.empty or not df_ecb.empty
    if not has_rate_data:
        return html.Div([
            _section_label("DIVERGENCIA BCE-FED Y EUR/USD"),
            create_empty_state("Sin datos de tipos", "Requiere fred_fed_funds_us y ecb_deposit_rate_ea en BD"),
        ], style={"marginBottom": "28px"})

    from plotly.subplots import make_subplots
    has_fx = not df_fx.empty

    if has_fx:
        fig = make_subplots(specs=[[{"secondary_y": True}]])
    else:
        fig = go.Figure()

    if not df_fed.empty:
        df_fed = df_fed.sort_values("timestamp")
        if has_fx:
            fig.add_trace(go.Scatter(
                x=df_fed["timestamp"], y=df_fed["value"],
                name="Fed Funds Rate", line={"color": C["primary"], "width": 2},
                hovertemplate="<b>Fed</b>: %{y:.2f}%<extra></extra>",
            ), secondary_y=False)
        else:
            fig.add_trace(go.Scatter(
                x=df_fed["timestamp"], y=df_fed["value"],
                name="Fed Funds Rate", line={"color": C["primary"], "width": 2},
                hovertemplate="<b>Fed</b>: %{y:.2f}%<extra></extra>",
            ))

    if not df_ecb.empty:
        df_ecb = df_ecb.sort_values("timestamp")
        if has_fx:
            fig.add_trace(go.Scatter(
                x=df_ecb["timestamp"], y=df_ecb["value"],
                name="Tipo BCE (depósito)", line={"color": "#10b981", "width": 2},
                hovertemplate="<b>BCE</b>: %{y:.2f}%<extra></extra>",
            ), secondary_y=False)
        else:
            fig.add_trace(go.Scatter(
                x=df_ecb["timestamp"], y=df_ecb["value"],
                name="Tipo BCE (depósito)", line={"color": "#10b981", "width": 2},
                hovertemplate="<b>BCE</b>: %{y:.2f}%<extra></extra>",
            ))

    # Diferencial
    if not df_fed.empty and not df_ecb.empty:
        df_merged = pd.merge_asof(
            df_fed.rename(columns={"value": "fed"}),
            df_ecb.rename(columns={"value": "ecb"}),
            on="timestamp", direction="nearest",
        )
        df_merged["spread"] = df_merged["fed"] - df_merged["ecb"]
        if has_fx:
            fig.add_trace(go.Scatter(
                x=df_merged["timestamp"], y=df_merged["spread"],
                name="Diferencial Fed-BCE",
                line={"color": "#f59e0b", "width": 1.5, "dash": "dot"},
                hovertemplate="<b>Diferencial</b>: %{y:.2f}pp<extra></extra>",
            ), secondary_y=False)
        else:
            fig.add_trace(go.Scatter(
                x=df_merged["timestamp"], y=df_merged["spread"],
                name="Diferencial Fed-BCE",
                line={"color": "#f59e0b", "width": 1.5, "dash": "dot"},
                hovertemplate="<b>Diferencial</b>: %{y:.2f}pp<extra></extra>",
            ))

    if has_fx:
        df_fx = df_fx.sort_values("timestamp")
        fig.add_trace(go.Scatter(
            x=df_fx["timestamp"], y=df_fx["value"],
            name="EUR/USD",
            line={"color": "#ec4899", "width": 1.5},
            hovertemplate="<b>EUR/USD</b>: %{y:.4f}<extra></extra>",
        ), secondary_y=True)

    layout = get_base_layout("Divergencia BCE-Fed y EUR/USD", height=380)
    layout["yaxis"] = {**layout.get("yaxis", {}), "ticksuffix": "%", "title": {"text": "Tipo de interés (%)"}}
    if has_fx:
        layout["yaxis2"] = {"tickformat": ".4f", "title": {"text": "EUR/USD", "font": {"color": "#9ca3af"}},
                            "gridcolor": "rgba(0,0,0,0)", "tickfont": {"color": "#9ca3af"}}
    fig.update_layout(**layout)

    return html.Div([
        _section_label("DIVERGENCIA BCE-FED Y TIPO DE CAMBIO EUR/USD"),
        dcc.Graph(figure=fig, config={"displayModeBar": False}),
        html.Div(
            "Cuando la Fed sube tipos más rápido que el BCE, el diferencial se amplía → el dólar se aprecia (EUR/USD baja). "
            "Cuando el BCE es más restrictivo, el euro se aprecia. La divergencia de políticas es uno de los principales "
            "impulsores del tipo de cambio EUR/USD.",
            style={"fontSize": "0.70rem", "color": COLORS["text_muted"], "marginTop": "8px", "fontStyle": "italic"},
        ),
    ], style={"marginBottom": "28px"})


def _build_tab3_content() -> html.Div:
    return html.Div([
        _build_ecb_rates_history(),
        _build_ecb_balance(),
        _build_euribor_section(),
        _build_ecb_fed_divergence(),
    ], style={"padding": "20px"})


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — OTROS BANCOS CENTRALES
# ══════════════════════════════════════════════════════════════════════════════

OTHER_CB_OPTIONS = [
    {"label": "🇬🇧 Bank of England", "value": "BOE"},
    {"label": "🇯🇵 Bank of Japan", "value": "BOJ"},
    {"label": "🇨🇭 SNB Suiza", "value": "SNB"},
    {"label": "🇨🇦 Bank of Canada", "value": "BOC"},
    {"label": "🇦🇺 RBA Australia", "value": "RBA"},
    {"label": "🇨🇳 PBOC China", "value": "PBOC"},
    {"label": "🇧🇷 BCB Brasil", "value": "BCB"},
    {"label": "🇲🇽 Banxico México", "value": "BANXICO"},
]

CB_DESCRIPTIONS = {
    "BOE": "El Bank of England es el banco central más antiguo del mundo (1694). Fija el tipo bancario (Bank Rate) en reuniones del MPC (Monetary Policy Committee). El Brexit generó una incertidumbre significativa en su mandato.",
    "BOJ": "El Bank of Japan fue el último banco central del G7 en abandonar los tipos negativos (marzo 2024). Durante años aplicó 'Yield Curve Control' (YCC), fijando artificialmente el rendimiento del bono a 10 años. Su normalización tiene implicaciones globales por el 'carry trade' del yen.",
    "SNB": "El Banco Nacional Suizo tiene mandato de estabilidad de precios y tipo de cambio. Suiza es considerada un puerto seguro — en crisis, el franco suizo se aprecia y el SNB interviene activamente en el mercado de divisas.",
    "BOC": "El Bank of Canada sigue de cerca a la Fed dada la estrecha relación económica con EE.UU. Su mandato es mantener la inflación en el rango 1-3%, con un objetivo del 2%.",
    "RBA": "El Reserve Bank of Australia fija la cash rate. Australia tiene una de las tasas de inflación vivienda más altas del mundo desarrollado, lo que complica la política monetaria.",
    "PBOC": "El Banco Popular de China no es independiente del gobierno y usa herramientas más variadas que los bancos centrales occidentales: LPR (Loan Prime Rate), RRR (Ratio de Reserva Requerida) y controles directos del crédito. Gestiona también el tipo de cambio del yuan.",
    "BCB": "El Banco Central do Brasil (BCB) fija la tasa Selic, una de las tasas de referencia más altas del mundo. Brasil tiene historial de inflación crónica, lo que mantiene la tasa en niveles elevados incluso en periodos de baja inflación global.",
    "BANXICO": "El Banco de México (Banxico) sigue estrechamente a la Fed dado el volumen de comercio con EE.UU. y la dolarización informal de la economía mexicana.",
}


def _build_other_cb_panel(cb_key: str) -> html.Div:
    cb = next((c for c in CB_CATALOG if c["key"] == cb_key), None)
    if cb is None:
        return create_empty_state("Banco central no encontrado")

    rate, rate_ts = get_latest_value(cb["rate_id"])
    if rate is None:
        rate = cb["static_rate"]
        rate_ts = None

    _, rate_1m, _, _ = get_change(cb["rate_id"], period_days=30)
    _, rate_3m, _, _ = get_change(cb["rate_id"], period_days=90)
    _, rate_6m, _, _ = get_change(cb["rate_id"], period_days=180)
    _, rate_1y, _, _ = get_change(cb["rate_id"], period_days=365)

    inf_val = cb["static_inf"]
    if cb["inflation_id"]:
        inf_db, _ = get_latest_value(cb["inflation_id"])
        if inf_db is not None:
            inf_val = inf_db

    real = (rate - inf_val) if (rate is not None and inf_val is not None) else None
    date_str = rate_ts.strftime("%d/%m/%Y") if rate_ts else "Fallback estático"
    days = _days_until(cb["next_meeting"])
    next_meet_str = f"{cb['next_meeting']} (en {days} días)" if days is not None else cb["next_meeting"]

    def _delta(val, ref):
        if val is None or ref is None:
            return "—"
        d = val - ref
        s = "+" if d >= 0 else ""
        return f"{s}{d:.2f}pp"

    left_panel = html.Div([
        html.Div(f"{cb['flag']} {cb['name']}", style={
            "fontSize": "1.1rem", "fontWeight": "700", "color": COLORS["text"], "marginBottom": "12px",
        }),
        html.Div([
            html.Div("TIPO OFICIAL ACTUAL", style={"fontSize": "0.60rem", "color": COLORS["text_label"], "fontWeight": "600", "letterSpacing": "0.08em"}),
            html.Div(_pct(rate), style={"fontSize": "2.0rem", "fontWeight": "700", "fontFamily": "monospace", "color": COLORS["text"]}),
            html.Div(date_str, style={"fontSize": "0.68rem", "color": COLORS["text_muted"]}),
        ], style={"marginBottom": "14px"}),

        html.Div([
            html.Div("CAMBIOS RECIENTES", style={"fontSize": "0.60rem", "color": COLORS["text_label"], "fontWeight": "600", "letterSpacing": "0.08em", "marginBottom": "6px"}),
            *[
                html.Div([
                    html.Span(label, style={"fontSize": "0.72rem", "color": COLORS["text_muted"], "width": "80px", "display": "inline-block"}),
                    html.Span(delta_str, style={"fontSize": "0.72rem", "fontFamily": "monospace", "color": COLORS["text"]}),
                ], style={"marginBottom": "3px"})
                for label, delta_str in [
                    ("1 mes:", _delta(rate, rate_1m)),
                    ("3 meses:", _delta(rate, rate_3m)),
                    ("6 meses:", _delta(rate, rate_6m)),
                    ("1 año:", _delta(rate, rate_1y)),
                ]
            ],
        ], style={"marginBottom": "14px"}),

        html.Div([
            html.Div("MÉTRICAS CLAVE", style={"fontSize": "0.60rem", "color": COLORS["text_label"], "fontWeight": "600", "letterSpacing": "0.08em", "marginBottom": "6px"}),
            *[
                html.Div([
                    html.Span(label, style={"fontSize": "0.72rem", "color": COLORS["text_muted"], "width": "110px", "display": "inline-block"}),
                    html.Span(val_str, style={"fontSize": "0.72rem", "fontFamily": "monospace", "color": val_color}),
                ], style={"marginBottom": "3px"})
                for label, val_str, val_color in [
                    ("Inflación:", _pct(inf_val, 1), COLORS["text"]),
                    ("Tipo real:", _pct(real) if real else "—",
                     C["positive"] if real and real > 0 else C["negative"] if real and real < 0 else COLORS["text_muted"]),
                    ("Próx. reunión:", next_meet_str, COLORS["accent"]),
                ]
            ],
        ], style={"marginBottom": "14px"}),

        html.Div([
            html.Div("POSTURA", style={"fontSize": "0.60rem", "color": COLORS["text_label"], "fontWeight": "600", "letterSpacing": "0.08em", "marginBottom": "6px"}),
            _posture_badge(real),
        ], style={"marginBottom": "14px"}),

        html.Div([
            html.Div("CONTEXTO", style={"fontSize": "0.60rem", "color": COLORS["text_label"], "fontWeight": "600", "letterSpacing": "0.08em", "marginBottom": "6px"}),
            html.Div(CB_DESCRIPTIONS.get(cb_key, ""), style={
                "fontSize": "0.72rem", "color": COLORS["text_muted"],
                "lineHeight": "1.5",
            }),
        ]),
    ], style={**_card_style(), "height": "100%"})

    # Panel derecho — gráfico histórico
    df_hist = get_series(cb["rate_id"], days=365 * 10)
    if df_hist.empty:
        right_panel = html.Div([
            create_empty_state(
                "Datos históricos no disponibles",
                f"Se mostrará cuando el colector tenga datos para {cb['name']}.",
            ),
        ], style={**_card_style(), "height": "100%", "display": "flex", "alignItems": "center", "justifyContent": "center"})
    else:
        df_hist = df_hist.sort_values("timestamp")
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df_hist["timestamp"], y=df_hist["value"],
            name=f"Tipo {cb['name']}",
            line={"color": C["primary"], "width": 2},
            fill="tozeroy", fillcolor="rgba(59,130,246,0.10)",
            hovertemplate=f"<b>{cb['name']}</b>: %{{y:.2f}}%<br>%{{x|%b %Y}}<extra></extra>",
        ))
        if rate:
            fig.add_hline(y=rate, line_dash="dot", line_color=C["primary"], line_width=1,
                          annotation_text=f"Actual: {rate:.2f}%",
                          annotation_font={"color": C["primary"], "size": 10})
        layout = get_base_layout(f"Tipo oficial {cb['name']} — Histórico 10 años", height=400)
        layout["yaxis"] = {**layout.get("yaxis", {}), "ticksuffix": "%"}
        fig.update_layout(**layout)
        right_panel = html.Div([
            dcc.Graph(figure=fig, config={"displayModeBar": False}),
            _build_special_panel(cb_key),
        ], style={**_card_style()})

    return dbc.Row([
        dbc.Col(left_panel, width=4),
        dbc.Col(right_panel, width=8),
    ], className="g-3")


def _build_special_panel(cb_key: str) -> html.Div:
    """Paneles especiales para BOJ y PBOC."""
    if cb_key == "BOJ":
        df_jgb = get_series(ID_JGB_10Y, days=365 * 10)
        df_jpy = get_series(ID_USDJPY, days=365 * 10)

        elements = [html.Div("BANK OF JAPAN — YIELD CURVE CONTROL Y YEN", style={
            "fontSize": "0.65rem", "letterSpacing": "0.1em",
            "color": COLORS["text_label"], "fontWeight": "600",
            "marginTop": "16px", "marginBottom": "8px",
        })]

        if not df_jgb.empty or not df_jpy.empty:
            from plotly.subplots import make_subplots
            fig2 = make_subplots(specs=[[{"secondary_y": True}]])

            if not df_jgb.empty:
                df_jgb = df_jgb.sort_values("timestamp")
                fig2.add_trace(go.Scatter(
                    x=df_jgb["timestamp"], y=df_jgb["value"],
                    name="JGB 10Y", line={"color": "#ec4899", "width": 2},
                    hovertemplate="<b>JGB 10Y</b>: %{y:.2f}%<extra></extra>",
                ), secondary_y=False)
                # Banda YCC
                fig2.add_hrect(y0=-0.5, y1=0.5, fillcolor="rgba(245,158,11,0.1)",
                               layer="below", line_width=0,
                               annotation_text="Banda YCC (±0.5%)",
                               annotation_font={"color": "#f59e0b", "size": 9})

            if not df_jpy.empty:
                df_jpy = df_jpy.sort_values("timestamp")
                fig2.add_trace(go.Scatter(
                    x=df_jpy["timestamp"], y=df_jpy["value"],
                    name="USD/JPY", line={"color": "#f59e0b", "width": 1.5},
                    hovertemplate="<b>USD/JPY</b>: %{y:.2f}<extra></extra>",
                ), secondary_y=True)

            layout2 = get_base_layout("JGB 10Y y USD/JPY — Impacto del YCC", height=280)
            layout2["yaxis"] = {**layout2.get("yaxis", {}), "ticksuffix": "%"}
            layout2["yaxis2"] = {"title": {"text": "USD/JPY"}, "gridcolor": "rgba(0,0,0,0)", "tickfont": {"color": "#9ca3af"}}
            fig2.update_layout(**layout2)
            elements.append(dcc.Graph(figure=fig2, config={"displayModeBar": False}))
        else:
            elements.append(create_empty_state("Sin datos de JGB o USD/JPY"))

        elements.append(html.Div(
            "El BOJ fue el último banco central en abandonar los tipos negativos (marzo 2024), "
            "después de 8 años. Su normalización tiene implicaciones globales por el 'carry trade' del yen: "
            "inversores pedían prestado en yenes (barato) para invertir en activos de mayor rentabilidad.",
            style={"fontSize": "0.70rem", "color": COLORS["text_muted"], "marginTop": "8px", "fontStyle": "italic"},
        ))
        return html.Div(elements)

    elif cb_key == "PBOC":
        df_rrr = get_series(ID_PBOC_RRR, days=365 * 10)
        df_cny = get_series("yf_usdcny_price", days=365 * 10)

        elements = [html.Div("PBOC — LPR, RRR Y YUAN", style={
            "fontSize": "0.65rem", "letterSpacing": "0.1em",
            "color": COLORS["text_label"], "fontWeight": "600",
            "marginTop": "16px", "marginBottom": "8px",
        })]

        if not df_rrr.empty:
            df_rrr = df_rrr.sort_values("timestamp")
            fig3 = go.Figure()
            fig3.add_trace(go.Scatter(
                x=df_rrr["timestamp"], y=df_rrr["value"],
                name="RRR (%)", line={"color": "#f97316", "width": 2},
                fill="tozeroy", fillcolor="rgba(249,115,22,0.10)",
                hovertemplate="<b>RRR</b>: %{y:.2f}%<extra></extra>",
            ))
            layout3 = get_base_layout("Ratio de Reservas Requeridas PBOC (RRR)", height=220)
            layout3["yaxis"] = {**layout3.get("yaxis", {}), "ticksuffix": "%"}
            fig3.update_layout(**layout3)
            elements.append(dcc.Graph(figure=fig3, config={"displayModeBar": False}))
        else:
            elements.append(create_empty_state("Sin datos del RRR"))

        elements.append(html.Div(
            "El PBOC no es independiente del gobierno y usa herramientas más variadas: "
            "LPR (tipo de referencia crediticia), RRR (reservas requeridas de bancos) y controles "
            "directos del crédito. El yuan tiene un tipo de cambio gestionado, no libre.",
            style={"fontSize": "0.70rem", "color": COLORS["text_muted"], "marginTop": "8px", "fontStyle": "italic"},
        ))
        return html.Div(elements)

    return html.Div()


def _build_tab4_content(selected_cb: str = "BOE") -> html.Div:
    dropdown = dcc.Dropdown(
        id="m4-other-cb-selector",
        options=OTHER_CB_OPTIONS,
        value=selected_cb,
        clearable=False,
        style={
            "backgroundColor": COLORS["card_bg"],
            "color": COLORS["text"],
            "border": f"1px solid {COLORS['border']}",
            "maxWidth": "320px",
            "marginBottom": "16px",
        },
    )
    return html.Div([
        dropdown,
        html.Div(id="m4-other-cb-content"),
    ], style={"padding": "20px"})


# ══════════════════════════════════════════════════════════════════════════════
# MORTGAGE RESULT HELPER
# ══════════════════════════════════════════════════════════════════════════════

def _render_mortgage_result(capital: float, years: int, spread: float) -> html.Div:
    from modules.data_helpers import calculate_mortgage_payment

    eur_now, _ = get_latest_value(ID_EURIBOR_12M)
    _, eur_1y, _, _ = get_change(ID_EURIBOR_12M, period_days=365)
    _, eur_2y, _, _ = get_change(ID_EURIBOR_12M, period_days=730)

    euribor_min = -0.502  # mínimo histórico ~2022
    euribor_max_recent = 4.16  # máximo reciente ~oct 2023

    scenarios = []
    for label, eur_rate, color in [
        ("Actual", eur_now, C["primary"]),
        ("Hace 1 año", eur_1y, COLORS["text_muted"]),
        ("Hace 2 años", eur_2y, COLORS["text_muted"]),
        ("Mínimo histórico (~-0.50%)", euribor_min, C["positive"]),
        ("Máximo reciente (~4.16%)", euribor_max_recent, C["negative"]),
    ]:
        if eur_rate is None and label == "Actual":
            eur_rate = 3.0  # fallback si no hay dato
        if eur_rate is None:
            scenarios.append((label, None, color, eur_rate))
            continue
        cuota = calculate_mortgage_payment(capital, years, eur_rate, spread)
        scenarios.append((label, cuota, color, eur_rate))

    cuota_actual = scenarios[0][1]
    cuota_max = scenarios[4][1]

    # Gráfico de barras
    valid = [(lbl, cuota, color) for lbl, cuota, color, _ in scenarios if cuota is not None]
    if valid:
        labels, cuotas, colors = zip(*valid)
        fig = go.Figure(go.Bar(
            x=list(cuotas), y=list(labels),
            orientation="h",
            marker_color=list(colors),
            text=[f"€{c:,.0f}/mes" for c in cuotas],
            textposition="outside",
            hovertemplate="<b>%{y}</b>: €%{x:,.0f}/mes<extra></extra>",
        ))
        layout = get_base_layout("Cuota mensual hipoteca variable según EURIBOR", height=280)
        layout["xaxis"] = {**layout.get("xaxis", {}), "tickprefix": "€"}
        layout["margin"] = {"l": 200, "r": 80, "t": 40, "b": 40}
        fig.update_layout(**layout)
        bar_chart = dcc.Graph(figure=fig, config={"displayModeBar": False})
    else:
        bar_chart = html.Div()

    text_summary = ""
    if cuota_actual and cuota_max:
        diff = cuota_max - cuota_actual
        eur_str = f"{eur_now:.3f}%" if eur_now else "~3.00%"
        text_summary = (
            f"Con el EURIBOR actual de {eur_str} + diferencial {spread:.2f}%, "
            f"tu cuota mensual sería de **€{cuota_actual:,.0f}**. "
            f"En el peor momento reciente (EURIBOR al {euribor_max_recent:.2f}%), era de **€{cuota_max:,.0f}**. "
            f"La diferencia es de **€{diff:,.0f}/mes**."
        )

    return html.Div([
        bar_chart,
        dcc.Markdown(text_summary, style={
            "fontSize": "0.78rem", "color": COLORS["text_muted"],
            "marginTop": "12px", "padding": "10px 14px",
            "backgroundColor": COLORS["background"],
            "borderRadius": "6px",
            "borderLeft": f"3px solid {C['primary']}",
        }) if text_summary else html.Div(),
        html.Div([
            html.Div("TABLA DE ESCENARIOS", style={
                "fontSize": "0.60rem", "color": COLORS["text_label"],
                "fontWeight": "600", "letterSpacing": "0.08em", "marginTop": "12px", "marginBottom": "6px",
            }),
            html.Table([
                html.Thead(html.Tr([
                    html.Th("Escenario", style={"padding": "5px 12px", "fontSize": "0.65rem", "color": COLORS["text_label"]}),
                    html.Th("EURIBOR", style={"padding": "5px 12px", "fontSize": "0.65rem", "color": COLORS["text_label"]}),
                    html.Th("Tipo total", style={"padding": "5px 12px", "fontSize": "0.65rem", "color": COLORS["text_label"]}),
                    html.Th("Cuota/mes", style={"padding": "5px 12px", "fontSize": "0.65rem", "color": COLORS["text_label"]}),
                ])),
                html.Tbody([
                    html.Tr([
                        html.Td(lbl, style={"padding": "5px 12px", "fontSize": "0.75rem", "borderBottom": f"1px solid {COLORS['border']}"}),
                        html.Td(_pct(eur_rate, 3) if eur_rate is not None else "—", style={"padding": "5px 12px", "fontSize": "0.75rem", "fontFamily": "monospace", "borderBottom": f"1px solid {COLORS['border']}"}),
                        html.Td(_pct(eur_rate + spread, 3) if eur_rate is not None else "—", style={"padding": "5px 12px", "fontSize": "0.75rem", "fontFamily": "monospace", "borderBottom": f"1px solid {COLORS['border']}"}),
                        html.Td(f"€{cuota:,.0f}" if cuota else "—", style={"padding": "5px 12px", "fontSize": "0.75rem", "fontFamily": "monospace", "fontWeight": "700", "color": color, "borderBottom": f"1px solid {COLORS['border']}"}),
                    ])
                    for (lbl, cuota, color, eur_rate) in scenarios
                ]),
            ], style={"width": "100%", "borderCollapse": "collapse"}),
        ]),
    ])


# ══════════════════════════════════════════════════════════════════════════════
# RENDER PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

def render_module_4() -> html.Div:
    return html.Div([
        _build_m4_header(),
        dcc.Tabs(
            id="m4-tabs",
            value="tab-global",
            children=[
                dcc.Tab(label="🌍 Visión Global",       value="tab-global",   style=TAB_STYLE, selected_style=TAB_SELECTED_STYLE),
                dcc.Tab(label="🇺🇸 La Fed en Detalle", value="tab-fed",      style=TAB_STYLE, selected_style=TAB_SELECTED_STYLE),
                dcc.Tab(label="🇪🇺 El BCE en Detalle", value="tab-ecb",      style=TAB_STYLE, selected_style=TAB_SELECTED_STYLE),
                dcc.Tab(label="🌐 Otros Bancos Centrales", value="tab-other", style=TAB_STYLE, selected_style=TAB_SELECTED_STYLE),
            ],
            style=TABS_STYLE,
            colors={"border": COLORS["border"], "primary": COLORS["accent"], "background": COLORS["card_bg"]},
        ),
        html.Div(id="m4-tab-content"),
        dcc.Store(id="m4-active-tab-store", storage_type="session", data="tab-global"),
        dcc.Store(id="m4-rates-range-store", data="5A"),
    ], id="m4-root", style={"minHeight": "100vh", "backgroundColor": COLORS["background"]})


# ══════════════════════════════════════════════════════════════════════════════
# CALLBACKS
# ══════════════════════════════════════════════════════════════════════════════

def register_callbacks_module_4(app) -> None:
    """Registra todos los callbacks del Módulo 4."""

    # ── 1. Tab routing ────────────────────────────────────────────────────────
    @app.callback(
        Output("m4-tab-content",      "children"),
        Output("m4-active-tab-store", "data"),
        Input("m4-tabs",              "value"),
        Input("m4-refresh-interval",  "n_intervals"),
    )
    def render_tab(tab_value, _n):
        try:
            if tab_value == "tab-global":
                return _build_tab1_content(), tab_value
            elif tab_value == "tab-fed":
                return _build_tab2_content(), tab_value
            elif tab_value == "tab-ecb":
                return _build_tab3_content(), tab_value
            elif tab_value == "tab-other":
                return _build_tab4_content("BOE"), tab_value
            return _build_tab1_content(), "tab-global"
        except Exception as e:
            logger.error("m4 tab render error: %s", e, exc_info=True)
            return html.Div(
                f"Error renderizando tab: {e}",
                style={"color": COLORS["text_muted"], "padding": "24px"},
            ), tab_value

    # ── 2. Restaurar tab ──────────────────────────────────────────────────────
    @app.callback(
        Output("m4-tabs", "value"),
        Input("m4-active-tab-store", "data"),
        prevent_initial_call=True,
    )
    def restore_tab(stored_tab):
        return stored_tab or "tab-global"

    # ── 3. Selector banco central (Tab 4) ─────────────────────────────────────
    @app.callback(
        Output("m4-other-cb-content", "children"),
        Input("m4-other-cb-selector", "value"),
    )
    def update_other_cb(cb_key):
        if not cb_key:
            return create_empty_state("Selecciona un banco central")
        try:
            return _build_other_cb_panel(cb_key)
        except Exception as e:
            logger.error("m4 other cb error: %s", e, exc_info=True)
            return create_empty_state(f"Error cargando {cb_key}: {e}")

    # ── 4. Gráfico tipos globales (Tab 1) ─────────────────────────────────────
    @app.callback(
        Output("m4-global-rates-chart", "figure"),
        Output("m4-rates-range-store",  "data"),
        Input("m4-cb-checklist",        "value"),
        Input("m4-rates-range-1A",      "n_clicks"),
        Input("m4-rates-range-2A",      "n_clicks"),
        Input("m4-rates-range-5A",      "n_clicks"),
        Input("m4-rates-range-10A",     "n_clicks"),
        Input("m4-rates-range-MÁX",     "n_clicks"),
        State("m4-rates-range-store",   "data"),
        prevent_initial_call=False,
    )
    def update_global_rates_chart(selected, n1a, n2a, n5a, n10a, nmax, current_range):
        triggered = ctx.triggered_id
        range_map = {
            "m4-rates-range-1A":  "1A",
            "m4-rates-range-2A":  "2A",
            "m4-rates-range-5A":  "5A",
            "m4-rates-range-10A": "10A",
            "m4-rates-range-MÁX": "MÁX",
        }
        new_range = range_map.get(triggered, current_range or "5A")
        days_map = {"1A": 365, "2A": 730, "5A": 1825, "10A": 3650, "MÁX": 10000}
        days = days_map.get(new_range, 1825)

        cb_series_map = {
            "FED":    (ID_FED_FUNDS,   "#3b82f6"),
            "ECB":    (ID_ECB_RATE,    "#10b981"),
            "BOE":    (ID_BOE_RATE,    "#06b6d4"),
            "BOJ":    (ID_BOJ_RATE,    "#ec4899"),
            "SNB":    (ID_SNB_RATE,    "#8b5cf6"),
            "BOC":    (ID_BOC_RATE,    "#f59e0b"),
            "RBA":    (ID_RBA_RATE,    "#f97316"),
            "BCB":    (ID_BCB_SELIC,   "#84cc16"),
        }

        fig = go.Figure()
        for key in (selected or []):
            if key not in cb_series_map:
                continue
            sid, color = cb_series_map[key]
            df = get_series(sid, days=days)
            if df.empty:
                continue
            df = df.sort_values("timestamp")
            cb_info = next((c for c in CB_CATALOG if c["key"] == key), {})
            name = cb_info.get("name", key)
            fig.add_trace(go.Scatter(
                x=df["timestamp"], y=df["value"],
                name=f"{cb_info.get('flag','')} {name}",
                line={"color": color, "width": 2},
                hovertemplate=f"<b>{name}</b>: %{{y:.2f}}%<br>%{{x|%b %Y}}<extra></extra>",
            ))

        fig.add_hline(y=0, line_dash="solid", line_color="#374151", line_width=1)
        layout = get_base_layout("Tipos Oficiales de Bancos Centrales Globales", height=420)
        layout["yaxis"] = {**layout.get("yaxis", {}), "ticksuffix": "%"}
        fig.update_layout(**layout)
        return fig, new_range

    # ── 5. Calculadora hipoteca ───────────────────────────────────────────────
    @app.callback(
        Output("m4-mortgage-result",   "children"),
        Input("m4-mortgage-capital",   "value"),
        Input("m4-mortgage-years",     "value"),
        Input("m4-mortgage-spread",    "value"),
        prevent_initial_call=False,
    )
    def update_mortgage(capital, years, spread):
        try:
            capital = float(capital) if capital else 150000.0
            years   = int(years)     if years   else 20
            spread  = float(spread)  if spread is not None else 0.99
            return _render_mortgage_result(capital, years, spread)
        except Exception as e:
            logger.error("m4 mortgage error: %s", e, exc_info=True)
            return create_empty_state(f"Error en calculadora: {e}")
