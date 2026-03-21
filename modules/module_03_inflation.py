"""
Modulo 3 — Inflación Global
Se renderiza cuando la URL es /module/3.

Exporta:
  render_module_3()               -> layout completo
  register_callbacks_module_3(app) -> registra todos los callbacks
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
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

ID_CPI_YOY_US       = "fred_cpi_yoy_us"        # US CPI YoY %
ID_CPI_US           = "fred_cpi_us"             # US CPI nivel (para calcular YoY)
ID_CORE_CPI_US      = "fred_core_cpi_us"        # US Core CPI nivel
ID_CPI_ENERGY_US    = "fred_cpi_energy_us"      # CPI Energía
ID_CPI_FOOD_US      = "fred_cpi_food_us"        # CPI Alimentos
ID_CPI_HOUSING_US   = "fred_cpi_housing_us"     # CPI Vivienda
ID_CPI_SERVICES_US  = "fred_cpi_services_us"    # CPI Servicios
ID_PPI_US           = "fred_ppi_all_us"         # PPI nivel
ID_PPI_FINISHED_US  = "fred_ppi_finished_us"    # PPI bienes terminados
ID_REAL_RATE_US     = "fred_real_rate_us"       # Tipo real US (DFF - CPI)
ID_REAL_YIELD_10Y   = "fred_real_yield_10y_us"  # TIPS 10Y
ID_BREAKEVEN_5Y     = "fred_breakeven_5y_us"    # Expectativas 5Y
ID_BREAKEVEN_10Y    = "fred_breakeven_10y_us"   # Expectativas 10Y
ID_FED_FUNDS        = "fred_fed_funds_us"       # Fed Funds Rate
ID_HICP_EA          = "estat_hicp_cp00_ea20"    # Eurozone HICP YoY
ID_HICP_DE          = "estat_hicp_cp00_de"      # Germany HICP
ID_HICP_ES          = "estat_hicp_cp00_es"      # Spain HICP
ID_HICP_IT          = "estat_hicp_cp00_it"      # Italy HICP
ID_ECB_RATE         = "ecb_deposit_rate_ea"     # ECB deposit rate
ID_BUND_10Y         = "ecb_bund_10y_de"         # German Bund 10Y
ID_YIELD_ES         = "ecb_yield_10y_es"        # Spain 10Y
ID_YIELD_IT         = "ecb_yield_10y_it"        # Italy 10Y
ID_YIELD_EA_10Y     = "ecb_yield_ea_10y_ea"     # EA avg 10Y

# Países con datos disponibles: (code, label, flag, cpi_series_id, rate_series_id)
COUNTRY_CATALOG = [
    ("US",  "EE.UU.",    "🇺🇸", ID_CPI_YOY_US,  ID_FED_FUNDS,  2.0),
    ("EA",  "Eurozona",  "🇪🇺", ID_HICP_EA,     ID_ECB_RATE,   2.0),
    ("DE",  "Alemania",  "🇩🇪", ID_HICP_DE,     ID_ECB_RATE,   2.0),
    ("ES",  "España",    "🇪🇸", ID_HICP_ES,     ID_ECB_RATE,   2.0),
    ("IT",  "Italia",    "🇮🇹", ID_HICP_IT,     ID_ECB_RATE,   2.0),
]

# Estilos tabs (consistente con módulo 5)
TAB_STYLE = {
    "backgroundColor": "transparent",
    "color": COLORS["text_muted"],
    "border": "none",
    "borderBottom": f"2px solid transparent",
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

# Países del Tab 2
TAB2_COUNTRIES = [
    {"label": "🇺🇸 EE.UU.", "value": "US"},
    {"label": "🇪🇺 Eurozona", "value": "EA"},
    {"label": "🇩🇪 Alemania", "value": "DE"},
    {"label": "🇪🇸 España", "value": "ES"},
    {"label": "🇮🇹 Italia", "value": "IT"},
]

# Países del Tab 3 calculadora
CALC_COUNTRIES = [
    {"label": "🇺🇸 EE.UU. (USD)", "value": "US"},
    {"label": "🇪🇺 Eurozona (EUR)", "value": "EA"},
    {"label": "🇩🇪 Alemania (EUR)", "value": "DE"},
    {"label": "🇪🇸 España (EUR)", "value": "ES"},
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


def _color_inf(val: Optional[float]) -> str:
    """Color según si supera el objetivo del 2%."""
    if val is None:
        return COLORS["text_muted"]
    if val > 4:
        return C["negative"]
    if val > 2:
        return C["warning"]
    if val < 0:
        return "#60a5fa"  # deflación → azul
    return C["positive"]


def _warning_triangle(val: Optional[float]) -> html.Span:
    """Triángulo de advertencia si inflación > 2%."""
    if val is not None and val > 2:
        return html.Span("▲ ", style={"color": C["negative"], "fontSize": "0.7rem"})
    return html.Span()


def _pct_str(val: Optional[float], sign: bool = True) -> str:
    if val is None:
        return "—"
    s = "+" if sign and val > 0 else ""
    return f"{s}{val:.2f}%"


def _compute_yoy_from_series(series_id: str, days: int = 400) -> Optional[pd.DataFrame]:
    """
    Calcula YoY desde una serie de niveles mensuales.
    Devuelve DataFrame(timestamp, value) con % YoY o None.
    """
    df = get_series(series_id, days=days)
    if df.empty or len(df) < 13:
        return None
    df = df.sort_values("timestamp").reset_index(drop=True)
    df["yoy"] = df["value"].pct_change(periods=12) * 100
    df = df.dropna(subset=["yoy"])
    if df.empty:
        return None
    return df[["timestamp", "yoy"]].rename(columns={"yoy": "value"})


def _compact_metric_m3(title: str, value_str: str, change_str: str,
                        change_color: str, warn: bool = False) -> html.Div:
    """Card compacta para el header del módulo 3."""
    warn_el = html.Span("▲ ", style={"color": C["negative"], "fontSize": "0.65rem"}) if warn else html.Span()
    return html.Div(
        [
            html.Div(title, style={
                "fontSize": "0.60rem", "color": COLORS["text_label"],
                "fontWeight": "600", "letterSpacing": "0.08em", "marginBottom": "2px",
            }),
            html.Div(
                [warn_el, html.Span(value_str)],
                style={
                    "fontSize": "0.95rem", "fontWeight": "700",
                    "color": COLORS["text"], "fontFamily": "monospace",
                },
            ),
            html.Div(change_str, style={
                "fontSize": "0.68rem", "color": change_color, "fontWeight": "600",
            }),
        ],
        style={
            "backgroundColor": COLORS["card_bg"],
            "border": f"1px solid {COLORS['border']}",
            "borderRadius": "6px",
            "padding": "8px 12px",
            "minWidth": "110px",
            "flex": "1",
        },
    )


# ══════════════════════════════════════════════════════════════════════════════
# HEADER DEL MÓDULO
# ══════════════════════════════════════════════════════════════════════════════

def _build_m3_header() -> html.Div:
    # 1) US CPI YoY
    cpi_us, _ = get_latest_value(ID_CPI_YOY_US)
    _, _, _, cpi_chg = get_change(ID_CPI_YOY_US, period_days=35)
    cpi_str = _safe(cpi_us, ".2f", "%") if cpi_us is not None else "—"

    # 2) Eurozone HICP
    hicp_ea, _ = get_latest_value(ID_HICP_EA)
    _, _, _, hicp_chg = get_change(ID_HICP_EA, period_days=60)
    hicp_str = _safe(hicp_ea, ".1f", "%") if hicp_ea is not None else "—"

    # 3) Tipo real US (DFF - CPI) → fred_real_rate_us
    real_us, _ = get_latest_value(ID_REAL_RATE_US)
    _, _, _, real_chg = get_change(ID_REAL_RATE_US, period_days=35)
    real_str = _safe(real_us, ".2f", "%") if real_us is not None else "—"

    # 4) Expectativas 5Y mercado
    be5y, _ = get_latest_value(ID_BREAKEVEN_5Y)
    _, _, _, be5y_chg = get_change(ID_BREAKEVEN_5Y, period_days=7)
    be5y_str = _safe(be5y, ".2f", "%") if be5y is not None else "—"

    # 5) IPP US (solo el nivel, no tenemos YoY del PPI de FRED en la BD)
    ppi, _ = get_latest_value(ID_PPI_US)
    _, _, _, ppi_chg = get_change(ID_PPI_US, period_days=35)
    ppi_str = _safe(ppi, ".1f") if ppi is not None else "—"

    def _chg_color(v):
        if v is None:
            return COLORS["text_muted"]
        return C["positive"] if v >= 0 else C["negative"]

    def _chg_str(v, suffix="%"):
        if v is None:
            return ""
        s = "+" if v > 0 else ""
        return f"{s}{v:.2f}{suffix} 1M"

    metrics_row = html.Div(
        [
            _compact_metric_m3(
                "IPC EE.UU. (YoY)", cpi_str,
                _chg_str(cpi_chg, "pp"), _chg_color(cpi_chg),
                warn=cpi_us is not None and cpi_us > 2,
            ),
            _compact_metric_m3(
                "IPC Eurozona (HICP)", hicp_str,
                _chg_str(hicp_chg, "pp"), _chg_color(hicp_chg),
                warn=hicp_ea is not None and hicp_ea > 2,
            ),
            _compact_metric_m3(
                "Tipo Real EE.UU.", real_str,
                _chg_str(real_chg, "pp"), _chg_color(real_chg),
            ),
            _compact_metric_m3(
                "Expect. Inflación 5Y", be5y_str,
                _chg_str(be5y_chg, "pp"), _chg_color(be5y_chg),
                warn=be5y is not None and be5y > 2,
            ),
            _compact_metric_m3(
                "IPP EE.UU. (nivel)", ppi_str,
                _chg_str(ppi_chg, " pts"), _chg_color(ppi_chg),
            ),
        ],
        style={"display": "flex", "gap": "8px", "flexWrap": "wrap", "marginTop": "12px"},
    )

    _, ts = get_latest_value(ID_CPI_YOY_US)
    last_str = ts.strftime("%d/%m/%Y") if ts else "Sin datos"

    return html.Div(
        [
            html.Div(
                [
                    html.Span(
                        "Inflación Global",
                        style={"fontSize": "1.4rem", "fontWeight": "700", "color": COLORS["text"]},
                    ),
                    html.Span(
                        f"FRED · Eurostat · ECB · {last_str}",
                        id="m3-last-updated",
                        style={"fontSize": "0.72rem", "color": COLORS["text_muted"], "marginLeft": "16px"},
                    ),
                ],
                style={"display": "flex", "alignItems": "baseline"},
            ),
            metrics_row,
            dcc.Interval(id="m3-refresh-interval", interval=300_000, n_intervals=0),
        ],
        style={
            "padding": "16px 20px 14px",
            "borderBottom": f"1px solid {COLORS['border']}",
            "backgroundColor": COLORS["card_bg"],
        },
    )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — VISIÓN GLOBAL
# ══════════════════════════════════════════════════════════════════════════════

def _build_inflation_heatmap() -> html.Div:
    """Sección 1.1 — Heatmap de inflación por país (datos disponibles)."""
    # Países y sus series
    heatmap_data = [
        ("EE.UU.",   "US",  ID_CPI_YOY_US),
        ("Eurozona", "EA",  ID_HICP_EA),
        ("Alemania", "DE",  ID_HICP_DE),
        ("España",   "ES",  ID_HICP_ES),
        ("Italia",   "IT",  ID_HICP_IT),
    ]

    countries = []
    z_data = []
    text_data = []
    periods_label = ["Actual", "Hace 3M", "Hace 6M", "Hace 1A", "Hace 2A"]

    for name, code, sid in heatmap_data:
        df = get_series(sid, days=730)
        if df.empty:
            row_z = [None] * 5
            row_t = ["—"] * 5
        else:
            df = df.sort_values("timestamp")
            now = datetime.utcnow()
            def _closest(days_back):
                target = now - timedelta(days=days_back)
                sub = df[df["timestamp"] <= target]
                if sub.empty:
                    return None
                return float(sub.iloc[-1]["value"])

            pts = [
                _closest(0),
                _closest(90),
                _closest(180),
                _closest(365),
                _closest(730),
            ]
            row_z = pts
            row_t = [f"{v:.1f}%" if v is not None else "—" for v in pts]

        countries.append(name)
        z_data.append(row_z)
        text_data.append(row_t)

    fig = go.Figure(go.Heatmap(
        z=z_data,
        x=periods_label,
        y=countries,
        text=text_data,
        texttemplate="%{text}",
        colorscale=[
            [0.0,  "#1e40af"],   # deflación: azul oscuro
            [0.2,  "#3b82f6"],   # negativo: azul
            [0.4,  "#e5e7eb"],   # ~2% objetivo: blanco
            [0.6,  "#f59e0b"],   # elevado: amarillo
            [0.8,  "#f97316"],   # alto: naranja
            [1.0,  "#ef4444"],   # muy alto: rojo
        ],
        zmin=-2,
        zmax=12,
        colorbar={
            "title": "% YoY",
            "ticksuffix": "%",
            "thickness": 14,
            "len": 0.8,
            "tickfont": {"color": "#9ca3af", "size": 10},
            "titlefont": {"color": "#9ca3af", "size": 10},
        },
        hovertemplate="<b>%{y}</b><br>%{x}: %{text}<extra></extra>",
    ))
    fig.update_layout(**get_base_layout(height=280))
    fig.update_layout(
        margin={"l": 80, "r": 20, "t": 20, "b": 40},
        xaxis={"side": "bottom"},
    )

    # Ranking top 5 / bottom 5
    ranking_items = []
    current_vals = []
    for (name, code, sid), row_z in zip(heatmap_data, z_data):
        if row_z[0] is not None:
            current_vals.append((name, row_z[0]))

    if current_vals:
        sorted_vals = sorted(current_vals, key=lambda x: x[1], reverse=True)
        top5 = sorted_vals[:3]
        bot5 = sorted_vals[-3:]

        top_items = [
            html.Div(
                [
                    html.Span(f"#{i+1}", style={"color": C["negative"], "fontWeight": "700",
                                                 "fontSize": "0.75rem", "marginRight": "6px"}),
                    html.Span(name, style={"fontSize": "0.78rem"}),
                    html.Span(f"{val:.1f}%", style={"color": C["negative"], "fontSize": "0.78rem",
                                                      "marginLeft": "auto", "fontFamily": "monospace"}),
                ],
                style={"display": "flex", "padding": "3px 0"},
            )
            for i, (name, val) in enumerate(top5)
        ]
        bot_items = [
            html.Div(
                [
                    html.Span(f"#{i+1}", style={"color": C["positive"], "fontWeight": "700",
                                                  "fontSize": "0.75rem", "marginRight": "6px"}),
                    html.Span(name, style={"fontSize": "0.78rem"}),
                    html.Span(f"{val:.1f}%", style={"color": C["positive"] if val <= 2 else C["warning"],
                                                      "fontSize": "0.78rem",
                                                      "marginLeft": "auto", "fontFamily": "monospace"}),
                ],
                style={"display": "flex", "padding": "3px 0"},
            )
            for i, (name, val) in enumerate(sorted(bot5, key=lambda x: x[1]))
        ]

        ranking_items = dbc.Row(
            [
                dbc.Col([
                    html.Div("MAYOR INFLACIÓN", style={"fontSize": "0.60rem", "color": C["negative"],
                                                        "fontWeight": "700", "letterSpacing": "0.1em",
                                                        "marginBottom": "6px"}),
                    *top_items,
                ], width=6),
                dbc.Col([
                    html.Div("MENOR INFLACIÓN", style={"fontSize": "0.60rem", "color": C["positive"],
                                                         "fontWeight": "700", "letterSpacing": "0.1em",
                                                         "marginBottom": "6px"}),
                    *bot_items,
                ], width=6),
            ],
            style={"marginTop": "12px"},
        )
    else:
        ranking_items = html.Div()

    return html.Div(
        [
            html.Div("MAPA DE CALOR DE INFLACIÓN", style={
                "fontSize": "0.65rem", "letterSpacing": "0.1em",
                "color": COLORS["text_label"], "fontWeight": "600", "marginBottom": "10px",
            }),
            dcc.Graph(figure=fig, config={"displayModeBar": False}),
            html.Div(
                ranking_items,
                style={
                    "backgroundColor": COLORS["card_bg"],
                    "border": f"1px solid {COLORS['border']}",
                    "borderRadius": "6px",
                    "padding": "12px 16px",
                    "marginTop": "12px",
                },
            ),
        ],
        style={"marginBottom": "24px"},
    )


def _build_international_comparison() -> html.Div:
    """Sección 1.2 — Comparativa histórica internacional."""
    country_series = [
        ("EE.UU.",   ID_CPI_YOY_US, "#3b82f6"),
        ("Eurozona", ID_HICP_EA,    "#10b981"),
        ("Alemania", ID_HICP_DE,    "#8b5cf6"),
        ("España",   ID_HICP_ES,    "#f59e0b"),
        ("Italia",   ID_HICP_IT,    "#ef4444"),
    ]
    default_checked = ["EE.UU.", "Eurozona", "España"]

    checklist = dcc.Checklist(
        id="m3-country-checklist",
        options=[{"label": f" {name}", "value": name} for name, _, _ in country_series],
        value=default_checked,
        inline=True,
        style={"fontSize": "0.78rem", "color": COLORS["text_muted"], "marginBottom": "8px"},
        inputStyle={"marginRight": "4px", "marginLeft": "12px"},
    )

    range_btns = html.Div(
        [
            html.Button(r, id=f"m3-intl-range-{r}", n_clicks=0,
                        style={
                            "backgroundColor": COLORS["card_bg"],
                            "border": f"1px solid {COLORS['border']}",
                            "color": COLORS["text_muted"],
                            "padding": "2px 10px",
                            "fontSize": "0.72rem",
                            "borderRadius": "4px",
                            "cursor": "pointer",
                            "marginRight": "4px",
                        })
            for r in ["1A", "2A", "5A", "MÁX"]
        ],
        style={"display": "flex", "alignItems": "center", "marginBottom": "8px"},
    )

    return html.Div(
        [
            html.Div("COMPARATIVA INTERNACIONAL — INFLACIÓN HISTÓRICA", style={
                "fontSize": "0.65rem", "letterSpacing": "0.1em",
                "color": COLORS["text_label"], "fontWeight": "600", "marginBottom": "10px",
            }),
            dbc.Row([
                dbc.Col(checklist, width=8),
                dbc.Col(range_btns, width=4, style={"textAlign": "right"}),
            ]),
            dcc.Graph(id="m3-intl-chart", config={"displayModeBar": False}),
            dcc.Store(id="m3-intl-range-store", data="5A"),
        ],
        style={"marginBottom": "24px"},
    )


def _build_global_table() -> html.Div:
    """Sección 1.3 — Tabla resumen global."""
    rows = []
    for (name, code, sid, rate_sid, target) in [
        ("🇺🇸 EE.UU.",   "US", ID_CPI_YOY_US, ID_FED_FUNDS,   2.0),
        ("🇪🇺 Eurozona", "EA", ID_HICP_EA,     ID_ECB_RATE,    2.0),
        ("🇩🇪 Alemania", "DE", ID_HICP_DE,     ID_ECB_RATE,    2.0),
        ("🇪🇸 España",   "ES", ID_HICP_ES,     ID_ECB_RATE,    2.0),
        ("🇮🇹 Italia",   "IT", ID_HICP_IT,     ID_ECB_RATE,    2.0),
    ]:
        cpi, _ = get_latest_value(sid)
        cpi_old, _ = get_latest_value(sid)  # misma serie, comparamos con periodo anterior
        _, cpi_prev, _, _ = get_change(sid, period_days=60)
        rate, _ = get_latest_value(rate_sid)

        # desviación del objetivo
        if cpi is not None:
            dev = cpi - target
            if abs(dev) <= 0.5:
                dev_color = C["positive"]
            elif abs(dev) <= 2:
                dev_color = C["warning"]
            else:
                dev_color = C["negative"]
            dev_str = f"{dev:+.1f}pp"
        else:
            dev = None
            dev_color = COLORS["text_muted"]
            dev_str = "—"

        # tipo real
        if cpi is not None and rate is not None:
            real = rate - cpi
            real_color = C["positive"] if real > 0 else C["negative"]
            real_str = f"{real:+.2f}%"
        else:
            real_color = COLORS["text_muted"]
            real_str = "—"

        # flecha tendencia
        if cpi is not None and cpi_prev is not None:
            arrow = "↑" if cpi > cpi_prev else "↓" if cpi < cpi_prev else "→"
            arrow_color = C["negative"] if cpi > cpi_prev else C["positive"]
        else:
            arrow = "→"
            arrow_color = COLORS["text_muted"]

        rows.append(html.Tr([
            html.Td(name, style={"whiteSpace": "nowrap", "fontSize": "0.82rem"}),
            html.Td(
                f"{cpi:.1f}%" if cpi is not None else "—",
                style={"textAlign": "right", "fontFamily": "monospace",
                       "color": _color_inf(cpi), "fontWeight": "600"},
            ),
            html.Td(
                f"{cpi_prev:.1f}%" if cpi_prev is not None else "—",
                style={"textAlign": "right", "fontFamily": "monospace",
                       "color": COLORS["text_muted"], "fontSize": "0.78rem"},
            ),
            html.Td(
                html.Span(arrow, style={"color": arrow_color, "fontWeight": "700"}),
                style={"textAlign": "center"},
            ),
            html.Td(f"{target:.1f}%", style={"textAlign": "right", "color": COLORS["text_muted"]}),
            html.Td(
                dev_str,
                style={"textAlign": "right", "color": dev_color, "fontWeight": "600",
                       "fontFamily": "monospace"},
            ),
            html.Td(
                f"{rate:.2f}%" if rate is not None else "—",
                style={"textAlign": "right", "fontFamily": "monospace"},
            ),
            html.Td(
                real_str,
                style={"textAlign": "right", "color": real_color,
                       "fontWeight": "700", "fontFamily": "monospace"},
            ),
        ]))

    headers = ["País", "Inflación actual", "Hace 1-2M", "Tendencia",
               "Objetivo BC", "Desviación", "Tipo oficial", "Tipo real"]
    thead = html.Thead(html.Tr([
        html.Th(h, style={
            "fontSize": "0.70rem", "color": COLORS["text_label"], "fontWeight": "600",
            "textAlign": "right" if i > 0 else "left",
            "borderBottom": f"2px solid {COLORS['border']}",
            "paddingBottom": "6px", "whiteSpace": "nowrap",
        })
        for i, h in enumerate(headers)
    ]))

    return html.Div(
        [
            html.Div("RESUMEN GLOBAL — INFLACIÓN Y TIPOS REALES", style={
                "fontSize": "0.65rem", "letterSpacing": "0.1em",
                "color": COLORS["text_label"], "fontWeight": "600", "marginBottom": "10px",
            }),
            html.Div(
                html.Table(
                    [thead, html.Tbody(rows)],
                    style={"width": "100%", "borderCollapse": "collapse"},
                    className="data-table",
                ),
                style={"overflowX": "auto"},
            ),
            html.Div(
                "💡 El tipo real negativo indica represión financiera: el efectivo pierde poder adquisitivo.",
                style={"fontSize": "0.72rem", "color": COLORS["text_muted"],
                       "marginTop": "8px", "fontStyle": "italic"},
            ),
        ],
        style={"marginBottom": "24px"},
    )


def _build_tab1_content() -> html.Div:
    return html.Div(
        [
            _build_inflation_heatmap(),
            _build_international_comparison(),
            _build_global_table(),
        ],
        style={"padding": "20px"},
    )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — INFLACIÓN EN DETALLE
# ══════════════════════════════════════════════════════════════════════════════

def _get_country_cpi_sid(country: str) -> str:
    mapping = {
        "US": ID_CPI_YOY_US,
        "EA": ID_HICP_EA,
        "DE": ID_HICP_DE,
        "ES": ID_HICP_ES,
        "IT": ID_HICP_IT,
    }
    return mapping.get(country, ID_CPI_YOY_US)


def _get_country_name(country: str) -> str:
    return {"US": "EE.UU.", "EA": "Eurozona", "DE": "Alemania",
            "ES": "España", "IT": "Italia"}.get(country, country)


def _build_tab2_layout() -> html.Div:
    """Devuelve el layout estático de la tab 2 (selección de país + placeholders)."""
    country_selector = html.Div(
        [
            html.Div("PAÍS SELECCIONADO", style={
                "fontSize": "0.60rem", "color": COLORS["text_label"],
                "fontWeight": "600", "letterSpacing": "0.08em", "marginBottom": "4px",
            }),
            dcc.Dropdown(
                id="m3-country-selector",
                options=TAB2_COUNTRIES,
                value="US",
                clearable=False,
                style={
                    "width": "220px",
                    "backgroundColor": COLORS["card_bg"],
                    "color": COLORS["text"],
                    "border": f"1px solid {COLORS['border']}",
                    "fontSize": "0.82rem",
                },
            ),
        ],
        style={"marginBottom": "16px"},
    )

    return html.Div(
        [
            country_selector,
            html.Div(id="m3-detail-content"),
        ],
        style={"padding": "20px"},
    )


def _render_country_detail(country: str) -> html.Div:
    """Genera los gráficos de detalle para el país seleccionado."""
    name = _get_country_name(country)
    cpi_sid = _get_country_sid_info(country)

    sections = []

    # ── 2.1 IPC vs Core ───────────────────────────────────────────────────────
    sections.append(_build_cpi_vs_core(country, name))

    # ── 2.2 Desglose componentes (sólo US) ───────────────────────────────────
    sections.append(_build_components_breakdown(country, name))

    # ── 2.3 Servicios vs Bienes ───────────────────────────────────────────────
    sections.append(_build_services_vs_goods(country, name))

    # ── 2.4 IPP como indicador adelantado (sólo US) ──────────────────────────
    sections.append(_build_ppi_leading(country, name))

    # ── 2.5 Expectativas de inflación del mercado (sólo US) ──────────────────
    sections.append(_build_inflation_expectations(country, name))

    return html.Div(sections)


def _get_country_sid_info(country: str) -> str:
    return _get_country_cpi_sid(country)


def _build_cpi_vs_core(country: str, name: str) -> html.Div:
    """Sección 2.1: IPC general vs IPC subyacente."""
    # Para US: fred_cpi_yoy_us vs computar core yoy desde fred_core_cpi_us
    # Para Europa: solo HICP total disponible

    if country == "US":
        # CPI general: usamos la serie YoY directo
        df_cpi = get_series(ID_CPI_YOY_US, days=4000)
        # Core: calcular YoY desde nivel
        df_core_level = get_series(ID_CORE_CPI_US, days=4000)
        df_core = _compute_yoy_df_from_level(df_core_level)
        label_general = "IPC General"
        label_core = "IPC Subyacente (Core)"
        target = 2.0
    else:
        # Para Europa solo tenemos HICP total
        cpi_sid = _get_country_cpi_sid(country)
        df_cpi = get_series(cpi_sid, days=4000)
        df_core = pd.DataFrame(columns=["timestamp", "value"])
        label_general = "HICP General"
        label_core = "HICP Subyacente"
        target = 2.0

    if df_cpi.empty:
        return html.Div(
            [
                html.Div("IPC GENERAL VS SUBYACENTE", style=_section_label_style()),
                create_empty_state(f"Sin datos de IPC para {name}",
                                   "Comprueba que el colector FRED/Eurostat ha ejecutado correctamente."),
            ],
            style={"marginBottom": "20px"},
        )

    fig = go.Figure()

    if not df_cpi.empty:
        fig.add_trace(go.Scatter(
            x=df_cpi["timestamp"], y=df_cpi["value"],
            name=label_general,
            line={"color": "#3b82f6", "width": 2},
            hovertemplate=f"<b>{label_general}</b>: %{{y:.2f}}%<extra></extra>",
        ))

    if not df_core.empty:
        fig.add_trace(go.Scatter(
            x=df_core["timestamp"], y=df_core["value"],
            name=label_core,
            line={"color": "#f59e0b", "width": 2, "dash": "dot"},
            hovertemplate=f"<b>{label_core}</b>: %{{y:.2f}}%<extra></extra>",
        ))

    # Línea de referencia 2%
    fig.add_hline(
        y=target,
        line_dash="dash",
        line_color="#6b7280",
        line_width=1,
        annotation_text=f"Objetivo {target}%",
        annotation_font_color="#9ca3af",
        annotation_font_size=10,
    )

    # Indicador automático
    cpi_latest, _ = get_latest_value(ID_CPI_YOY_US if country == "US" else _get_country_cpi_sid(country))
    core_df = df_core
    interp = ""
    if country == "US" and not core_df.empty and cpi_latest is not None:
        core_latest = float(core_df.iloc[-1]["value"])
        diff = abs(cpi_latest - core_latest) if cpi_latest is not None else 0
        if diff > 1.5:
            interp = f"La inflación tiene componente energético/alimentario dominante (diferencia general-core: {cpi_latest-core_latest:+.1f}pp). Más transitoria."
        else:
            interp = f"IPC general y core están próximos ({cpi_latest:.1f}% vs {core_latest:.1f}%). Inflación más asentada."

    fig.update_layout(**get_base_layout(f"IPC General vs Subyacente — {name}", height=340))

    return html.Div(
        [
            html.Div("IPC GENERAL VS SUBYACENTE (CORE)", style=_section_label_style()),
            dcc.Graph(figure=fig, config={"displayModeBar": False}),
            html.Div(interp, style={
                "fontSize": "0.75rem", "color": COLORS["text_muted"],
                "marginTop": "6px", "fontStyle": "italic",
                "padding": "6px 10px",
                "backgroundColor": COLORS["card_bg"],
                "borderRadius": "4px",
                "borderLeft": f"3px solid {COLORS['accent']}",
            }) if interp else html.Div(),
        ],
        style={"marginBottom": "20px"},
    )


def _compute_yoy_df_from_level(df: pd.DataFrame) -> pd.DataFrame:
    """Calcula YoY desde DataFrame de niveles mensuales."""
    if df.empty or len(df) < 13:
        return pd.DataFrame(columns=["timestamp", "value"])
    df = df.sort_values("timestamp").reset_index(drop=True)
    df["yoy"] = df["value"].pct_change(periods=12) * 100
    df = df.dropna(subset=["yoy"])
    return df[["timestamp", "yoy"]].rename(columns={"yoy": "value"})


def _build_components_breakdown(country: str, name: str) -> html.Div:
    """Sección 2.2: Desglose por componentes (solo US)."""
    if country != "US":
        return html.Div(
            [
                html.Div("DESGLOSE POR COMPONENTES", style=_section_label_style()),
                create_empty_state(
                    f"Desglose no disponible para {name}",
                    "Los datos detallados de componentes solo están disponibles para EE.UU. (FRED).",
                ),
            ],
            style={"marginBottom": "20px"},
        )

    # Calcular YoY aproximado de componentes (necesitamos 13+ meses)
    components = [
        ("Energía",   ID_CPI_ENERGY_US,   "#f97316"),
        ("Alimentos", ID_CPI_FOOD_US,      "#84cc16"),
        ("Vivienda",  ID_CPI_HOUSING_US,   "#3b82f6"),
        ("Servicios", ID_CPI_SERVICES_US,  "#8b5cf6"),
    ]

    comp_data = []
    for label, sid, color in components:
        df_level = get_series(sid, days=500)
        df_yoy = _compute_yoy_df_from_level(df_level)
        if not df_yoy.empty:
            val = float(df_yoy.iloc[-1]["value"])
            comp_data.append((label, val, color))

    # Valor total CPI
    cpi_latest, _ = get_latest_value(ID_CPI_YOY_US)

    if not comp_data:
        return html.Div(
            [
                html.Div("DESGLOSE POR COMPONENTES", style=_section_label_style()),
                create_empty_state("Sin datos suficientes para calcular YoY de componentes",
                                   "Se necesitan al menos 13 meses de datos históricos por componente."),
            ],
            style={"marginBottom": "20px"},
        )

    # Barras por componente
    labels = [d[0] for d in comp_data]
    values = [d[1] for d in comp_data]
    colors = [d[2] for d in comp_data]

    fig = go.Figure(go.Bar(
        x=labels,
        y=values,
        marker_color=colors,
        text=[f"{v:.1f}%" for v in values],
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>YoY: %{y:.2f}%<extra></extra>",
    ))

    if cpi_latest is not None:
        fig.add_hline(
            y=cpi_latest,
            line_dash="dash",
            line_color="#e5e7eb",
            line_width=1,
            annotation_text=f"IPC total: {cpi_latest:.2f}%",
            annotation_font_color="#e5e7eb",
            annotation_font_size=10,
        )

    fig.update_layout(**get_base_layout("Contribución por Componente — EE.UU.", height=320))
    fig.update_layout(yaxis_title="% YoY")

    # Componente principal
    if comp_data:
        max_comp = max(comp_data, key=lambda x: x[1])
        interp = (
            f"El componente con mayor inflación en EE.UU. es "
            f"<b>{max_comp[0]}</b> con un {max_comp[1]:.1f}% interanual."
        )
    else:
        interp = ""

    return html.Div(
        [
            html.Div("DESGLOSE POR COMPONENTES DEL IPC — EE.UU.", style=_section_label_style()),
            dcc.Graph(figure=fig, config={"displayModeBar": False}),
            html.Div(
                dcc.Markdown(interp),
                style={
                    "fontSize": "0.75rem", "color": COLORS["text_muted"],
                    "marginTop": "6px", "fontStyle": "italic",
                    "padding": "6px 10px",
                    "backgroundColor": COLORS["card_bg"],
                    "borderRadius": "4px",
                    "borderLeft": f"3px solid {COLORS['accent']}",
                },
            ) if interp else html.Div(),
        ],
        style={"marginBottom": "20px"},
    )


def _build_services_vs_goods(country: str, name: str) -> html.Div:
    """Sección 2.3: Inflación servicios vs bienes (solo US)."""
    if country != "US":
        return html.Div(
            [
                html.Div("SERVICIOS VS BIENES", style=_section_label_style()),
                create_empty_state(
                    f"No disponible para {name}",
                    "Datos de servicios/bienes separados solo disponibles para EE.UU.",
                ),
            ],
            style={"marginBottom": "20px"},
        )

    df_serv_level = get_series(ID_CPI_SERVICES_US, days=500)
    df_serv = _compute_yoy_df_from_level(df_serv_level)

    if df_serv.empty:
        return html.Div(
            [
                html.Div("SERVICIOS VS BIENES", style=_section_label_style()),
                create_empty_state("Sin datos suficientes de componentes",
                                   "Se necesitan al menos 13 meses de datos."),
            ],
            style={"marginBottom": "20px"},
        )

    # Servicios disponibles; Bienes = CPI general - Servicios (aproximación)
    df_cpi_level = get_series(ID_CPI_US, days=500)
    df_cpi = _compute_yoy_df_from_level(df_cpi_level)

    fig = go.Figure()
    if not df_serv.empty:
        fig.add_trace(go.Scatter(
            x=df_serv["timestamp"], y=df_serv["value"],
            name="Servicios",
            line={"color": "#8b5cf6", "width": 2},
            hovertemplate="<b>Servicios</b>: %{y:.2f}%<extra></extra>",
            fill="tozeroy",
            fillcolor="rgba(139,92,246,0.08)",
        ))

    if not df_cpi.empty:
        fig.add_trace(go.Scatter(
            x=df_cpi["timestamp"], y=df_cpi["value"],
            name="IPC General",
            line={"color": "#3b82f6", "width": 2, "dash": "dot"},
            hovertemplate="<b>IPC General</b>: %{y:.2f}%<extra></extra>",
        ))

    fig.add_hline(y=2.0, line_dash="dash", line_color="#6b7280", line_width=1)
    fig.update_layout(**get_base_layout("Servicios vs IPC General — EE.UU.", height=320))

    # Anotación automática
    interp = ""
    if not df_serv.empty:
        latest_serv = float(df_serv.iloc[-1]["value"])
        if len(df_serv) >= 3:
            prev_serv = float(df_serv.iloc[-3]["value"])
            trend = "subido" if latest_serv > prev_serv + 0.2 else \
                    "bajado" if latest_serv < prev_serv - 0.2 else "permanecido estable"
        else:
            trend = "evolucionado"
        interp = (f"La inflación de servicios ha {trend} en los últimos 3 meses ({latest_serv:.1f}%). "
                  "Es el componente más vigilado por los bancos centrales porque refleja presiones salariales.")

    return html.Div(
        [
            html.Div("INFLACIÓN DE SERVICIOS — COMPONENTE PEGAJOSO", style=_section_label_style()),
            dcc.Graph(figure=fig, config={"displayModeBar": False}),
            html.Div(interp, style={
                "fontSize": "0.75rem", "color": COLORS["text_muted"],
                "marginTop": "6px", "fontStyle": "italic",
                "padding": "6px 10px",
                "backgroundColor": COLORS["card_bg"],
                "borderRadius": "4px",
                "borderLeft": f"3px solid #8b5cf6",
            }) if interp else html.Div(),
        ],
        style={"marginBottom": "20px"},
    )


def _build_ppi_leading(country: str, name: str) -> html.Div:
    """Sección 2.4: IPP como indicador adelantado."""
    if country != "US":
        return html.Div(
            [
                html.Div("IPP COMO INDICADOR ADELANTADO", style=_section_label_style()),
                create_empty_state(
                    f"No disponible para {name}",
                    "Datos de IPP solo disponibles para EE.UU. (FRED PPIACO).",
                ),
            ],
            style={"marginBottom": "20px"},
        )

    df_cpi = get_series(ID_CPI_YOY_US, days=1825)  # 5 años
    df_ppi_level = get_series(ID_PPI_US, days=2200)
    df_ppi = _compute_yoy_df_from_level(df_ppi_level)

    if df_cpi.empty:
        return html.Div(
            [html.Div("IPP COMO INDICADOR ADELANTADO", style=_section_label_style()),
             create_empty_state("Sin datos de CPI")],
            style={"marginBottom": "20px"},
        )

    fig = go.Figure()
    if not df_cpi.empty:
        fig.add_trace(go.Scatter(
            x=df_cpi["timestamp"], y=df_cpi["value"],
            name="IPC (consumidor)",
            line={"color": "#3b82f6", "width": 2},
            hovertemplate="<b>IPC</b>: %{y:.2f}%<extra></extra>",
        ))
    if not df_ppi.empty:
        fig.add_trace(go.Scatter(
            x=df_ppi["timestamp"], y=df_ppi["value"],
            name="IPP (productor, adelantado ~6M)",
            line={"color": "#f59e0b", "width": 2, "dash": "dash"},
            hovertemplate="<b>IPP</b>: %{y:.2f}%<extra></extra>",
        ))

    fig.add_hline(y=0, line_dash="dot", line_color="#374151", line_width=1)

    # Calcular dirección del IPP
    ppi_latest = None
    cpi_latest, _ = get_latest_value(ID_CPI_YOY_US)
    direction = "mantenerse estable"
    if not df_ppi.empty and len(df_ppi) >= 3:
        ppi_latest = float(df_ppi.iloc[-1]["value"])
        ppi_prev = float(df_ppi.iloc[-3]["value"])
        if ppi_latest > ppi_prev + 1:
            direction = "subir"
        elif ppi_latest < ppi_prev - 1:
            direction = "bajar"

    fig.update_layout(**get_base_layout("IPP vs IPC — Señal Adelantada (5 años)", height=340))

    interp = ""
    if ppi_latest is not None:
        interp = (
            f"IPP actual: {ppi_latest:.1f}% YoY. Basado en la tendencia reciente del IPP, "
            f"la inflación al consumidor podría {direction} en los próximos 3-6 meses. "
            f"El IPP anticipa al IPC con aprox. 3-6 meses de adelanto."
        )

    return html.Div(
        [
            html.Div("IPP COMO INDICADOR ADELANTADO DEL IPC", style=_section_label_style()),
            dcc.Graph(figure=fig, config={"displayModeBar": False}),
            html.Div(interp, style={
                "fontSize": "0.75rem", "color": COLORS["text_muted"],
                "marginTop": "6px", "padding": "6px 10px",
                "backgroundColor": COLORS["card_bg"],
                "borderRadius": "4px",
                "borderLeft": f"3px solid {C['warning']}",
            }) if interp else html.Div(),
        ],
        style={"marginBottom": "20px"},
    )


def _build_inflation_expectations(country: str, name: str) -> html.Div:
    """Sección 2.5: Expectativas de inflación del mercado."""
    if country != "US":
        return html.Div(
            [
                html.Div("EXPECTATIVAS DE INFLACIÓN", style=_section_label_style()),
                create_empty_state(
                    f"No disponible para {name}",
                    "Expectativas de mercado solo disponibles para EE.UU. (FRED breakeven).",
                ),
            ],
            style={"marginBottom": "20px"},
        )

    df_5y = get_series(ID_BREAKEVEN_5Y, days=1095)   # 3 años
    df_10y = get_series(ID_BREAKEVEN_10Y, days=1095)

    if df_5y.empty and df_10y.empty:
        return html.Div(
            [html.Div("EXPECTATIVAS DE INFLACIÓN DEL MERCADO", style=_section_label_style()),
             create_empty_state("Sin datos de breakeven inflation")],
            style={"marginBottom": "20px"},
        )

    fig = go.Figure()
    if not df_5y.empty:
        fig.add_trace(go.Scatter(
            x=df_5y["timestamp"], y=df_5y["value"],
            name="Breakeven 5Y",
            line={"color": "#10b981", "width": 2},
            hovertemplate="<b>5Y</b>: %{y:.2f}%<extra></extra>",
        ))
    if not df_10y.empty:
        fig.add_trace(go.Scatter(
            x=df_10y["timestamp"], y=df_10y["value"],
            name="Breakeven 10Y",
            line={"color": "#3b82f6", "width": 2, "dash": "dot"},
            hovertemplate="<b>10Y</b>: %{y:.2f}%<extra></extra>",
        ))

    fig.add_hline(y=2.0, line_dash="dash", line_color="#6b7280", line_width=1,
                  annotation_text="Objetivo Fed 2%", annotation_font_color="#9ca3af",
                  annotation_font_size=10)

    fig.update_layout(**get_base_layout("Expectativas de Inflación del Mercado (breakeven)", height=320))

    # Semáforo expectativas
    be5y_latest, _ = get_latest_value(ID_BREAKEVEN_5Y)
    semaforo_color = "gray"
    semaforo_text = ""
    if be5y_latest is not None:
        if 1.8 <= be5y_latest <= 2.5:
            semaforo_color = "green"
            estado = "bien ancladas"
            margen = "da margen al Fed para mantener/bajar tipos"
        elif 2.5 < be5y_latest <= 3.5:
            semaforo_color = "yellow"
            estado = "ligeramente elevadas"
            margen = "limita el margen del Fed para bajar tipos"
        else:
            semaforo_color = "red"
            estado = "desancladas"
            margen = "fuerza al Fed a mantener tipos elevados"
        semaforo_text = (
            f"Las expectativas de inflación a 5 años ({be5y_latest:.2f}%) están {estado}, "
            f"lo que {margen}."
        )

    interp_panel = html.Div(
        [
            html.Div(
                create_semaphore(semaforo_color, label=semaforo_text, size="small"),
                style={"fontSize": "0.75rem"},
            ),
        ],
        style={
            "marginTop": "8px", "padding": "8px 12px",
            "backgroundColor": COLORS["card_bg"],
            "borderRadius": "4px",
            "borderLeft": f"3px solid {COLORS['accent']}",
        },
    ) if semaforo_text else html.Div()

    return html.Div(
        [
            html.Div("EXPECTATIVAS DE INFLACIÓN DEL MERCADO (BREAKEVEN)", style=_section_label_style()),
            dcc.Graph(figure=fig, config={"displayModeBar": False}),
            interp_panel,
        ],
        style={"marginBottom": "20px"},
    )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — REPRESIÓN FINANCIERA
# ══════════════════════════════════════════════════════════════════════════════

def _build_repression_thermometers() -> html.Div:
    """Sección 3.1: Termómetros de represión financiera."""
    zones = [
        ("EE.UU.",  ID_FED_FUNDS, ID_CPI_YOY_US, "USD"),
        ("Eurozona", ID_ECB_RATE, ID_HICP_EA,     "EUR"),
        ("España",   ID_ECB_RATE, ID_HICP_ES,     "EUR"),
    ]

    cols = []
    for label, rate_sid, cpi_sid, currency in zones:
        rate, _ = get_latest_value(rate_sid)
        cpi, _  = get_latest_value(cpi_sid)

        if rate is not None and cpi is not None:
            real = rate - cpi
            is_negative = real < 0
            color_real = C["negative"] if is_negative else C["positive"]
            thermometer_fill = min(abs(real) / 5 * 100, 100)
            thermo_color = C["negative"] if is_negative else C["positive"]

            # Termómetro visual
            thermo = html.Div(
                [
                    html.Div(
                        style={
                            "width": "30px",
                            "height": "120px",
                            "backgroundColor": COLORS["border"],
                            "borderRadius": "15px",
                            "position": "relative",
                            "margin": "0 auto 8px",
                            "overflow": "hidden",
                        },
                        children=[
                            html.Div(
                                style={
                                    "position": "absolute",
                                    "bottom": "0",
                                    "width": "100%",
                                    "height": f"{thermometer_fill}%",
                                    "backgroundColor": thermo_color,
                                    "borderRadius": "15px",
                                    "transition": "height 0.5s",
                                },
                            ),
                        ],
                    ),
                    html.Div(
                        f"{'−' if is_negative else '+'}{abs(real):.2f}%",
                        style={
                            "fontSize": "1.1rem", "fontWeight": "700",
                            "color": color_real, "fontFamily": "monospace",
                            "textAlign": "center",
                        },
                    ),
                    html.Div(
                        f"Tu efectivo {'pierde' if is_negative else 'gana'} {abs(real):.2f}% real/año",
                        style={
                            "fontSize": "0.70rem", "color": color_real,
                            "textAlign": "center", "marginTop": "4px",
                            "fontWeight": "700",
                        },
                    ),
                ]
            )
        else:
            thermo = create_empty_state("Sin datos")
            real = None
            color_real = COLORS["text_muted"]

        card = html.Div(
            [
                html.Div(label, style={
                    "fontSize": "0.80rem", "fontWeight": "700",
                    "color": COLORS["text"], "textAlign": "center",
                    "marginBottom": "12px",
                }),
                thermo,
                html.Hr(style={"borderColor": COLORS["border"], "margin": "10px 0"}),
                html.Div([
                    _mini_row("Tipo depósito:", f"{rate:.2f}%" if rate is not None else "—",
                              COLORS["text"]),
                    _mini_row("Inflación:", f"{cpi:.1f}%" if cpi is not None else "—",
                              _color_inf(cpi)),
                    _mini_row("Tipo real:", f"{real:+.2f}%" if real is not None else "—",
                              color_real if real is not None else COLORS["text_muted"]),
                ]),
            ],
            style={
                "backgroundColor": COLORS["card_bg"],
                "border": f"1px solid {COLORS['border']}",
                "borderRadius": "8px",
                "padding": "16px",
                "textAlign": "center",
                "flex": "1",
            },
        )
        cols.append(card)

    return html.Div(
        [
            html.Div("TERMÓMETRO DE REPRESIÓN FINANCIERA", style=_section_label_style()),
            html.Div(
                cols,
                style={"display": "flex", "gap": "16px", "flexWrap": "wrap"},
            ),
        ],
        style={"marginBottom": "24px"},
    )


def _mini_row(label: str, value: str, color: str) -> html.Div:
    return html.Div(
        [
            html.Span(label, style={"fontSize": "0.72rem", "color": COLORS["text_muted"]}),
            html.Span(value, style={"fontSize": "0.78rem", "color": color,
                                     "fontWeight": "600", "fontFamily": "monospace",
                                     "marginLeft": "6px"}),
        ],
        style={"display": "flex", "justifyContent": "space-between",
               "padding": "2px 0"},
    )


def _build_cash_erosion_calculator() -> html.Div:
    """Sección 3.2: Calculadora de erosión del efectivo."""
    return html.Div(
        [
            html.Div("CALCULADORA DE EROSIÓN DEL EFECTIVO", style=_section_label_style()),
            html.Div(
                [
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    html.Label("Cantidad (€/$)", style=_label_style()),
                                    dbc.Input(
                                        id="m3-calc-amount",
                                        type="number",
                                        value=10000,
                                        min=1,
                                        style={"backgroundColor": COLORS["card_bg"],
                                               "color": COLORS["text"],
                                               "border": f"1px solid {COLORS['border']}",
                                               "fontSize": "0.85rem"},
                                    ),
                                ],
                                width=3,
                            ),
                            dbc.Col(
                                [
                                    html.Label("Fecha de inicio", style=_label_style()),
                                    dcc.DatePickerSingle(
                                        id="m3-calc-date",
                                        date=(datetime.now() - timedelta(days=3 * 365)).strftime("%Y-%m-%d"),
                                        display_format="DD/MM/YYYY",
                                        style={"backgroundColor": COLORS["card_bg"]},
                                    ),
                                ],
                                width=3,
                            ),
                            dbc.Col(
                                [
                                    html.Label("País / Zona", style=_label_style()),
                                    dcc.Dropdown(
                                        id="m3-calc-country",
                                        options=CALC_COUNTRIES,
                                        value="US",
                                        clearable=False,
                                        style={
                                            "backgroundColor": COLORS["card_bg"],
                                            "color": COLORS["text"],
                                            "border": f"1px solid {COLORS['border']}",
                                            "fontSize": "0.82rem",
                                        },
                                    ),
                                ],
                                width=3,
                            ),
                            dbc.Col(
                                [
                                    html.Label("\u00a0", style=_label_style()),
                                    dbc.Button(
                                        "Calcular",
                                        id="m3-calc-btn",
                                        color="primary",
                                        size="sm",
                                        style={"width": "100%"},
                                    ),
                                ],
                                width=3,
                            ),
                        ],
                        className="g-2",
                    ),
                    html.Div(id="m3-calc-result", style={"marginTop": "16px"}),
                ],
                style={
                    "backgroundColor": COLORS["card_bg"],
                    "border": f"1px solid {COLORS['border']}",
                    "borderRadius": "8px",
                    "padding": "16px",
                },
            ),
        ],
        style={"marginBottom": "24px"},
    )


def _build_real_yield_history() -> html.Div:
    """Sección 3.3: Histórico tipo real EE.UU. (TIPS 10Y)."""
    df = get_series(ID_REAL_YIELD_10Y, days=9125)  # 25 años

    if df.empty:
        return html.Div(
            [
                html.Div("HISTÓRICO TIPO REAL EE.UU. (TIPS 10Y)", style=_section_label_style()),
                create_empty_state("Sin datos de TIPS 10Y (DFII10)",
                                   "Ejecuta el colector FRED para obtener este indicador."),
            ],
            style={"marginBottom": "24px"},
        )

    df = df.sort_values("timestamp")

    fig = go.Figure()

    # Área rellena: positivo=verde, negativo=rojo
    pos = df[df["value"] >= 0]
    neg = df[df["value"] < 0]

    # Serie completa como línea
    fig.add_trace(go.Scatter(
        x=df["timestamp"], y=df["value"],
        name="Tipo real TIPS 10Y",
        line={"color": "#3b82f6", "width": 1.5},
        fill="tozeroy",
        fillcolor="rgba(16,185,129,0.12)",
        hovertemplate="<b>TIPS 10Y</b>: %{y:.2f}%<br>%{x|%b %Y}<extra></extra>",
    ))

    # Máscara zona negativa
    if not neg.empty:
        fig.add_trace(go.Scatter(
            x=neg["timestamp"], y=neg["value"],
            name="Represión financiera",
            fill="tozeroy",
            fillcolor="rgba(239,68,68,0.18)",
            line={"width": 0},
            hoverinfo="skip",
            showlegend=True,
        ))

    fig.add_hline(y=0, line_dash="solid", line_color="#374151", line_width=1)
    fig.update_layout(**get_base_layout("Tipo Real EE.UU. — TIPS 10Y (Represión Financiera)", height=360))

    # Valor actual
    latest, _ = get_latest_value(ID_REAL_YIELD_10Y)
    latest_str = f"{latest:.2f}%" if latest is not None else "—"

    return html.Div(
        [
            html.Div("HISTÓRICO TIPO REAL EE.UU. — TIPS 10Y", style=_section_label_style()),
            dcc.Graph(figure=fig, config={"displayModeBar": False}),
            html.Div(
                [
                    html.Span("Tipo real actual: ", style={"color": COLORS["text_muted"]}),
                    html.Span(latest_str, style={"color": _color_inf_real(latest),
                                                  "fontWeight": "700", "fontFamily": "monospace"}),
                    html.Span(
                        " — La zona roja indica períodos de represión financiera (tipo real negativo), "
                        "herramienta silenciosa con la que los gobiernos reducen el valor real de su deuda.",
                        style={"color": COLORS["text_muted"], "fontStyle": "italic"},
                    ),
                ],
                style={"fontSize": "0.75rem", "marginTop": "8px",
                       "padding": "6px 10px",
                       "backgroundColor": COLORS["card_bg"],
                       "borderRadius": "4px",
                       "borderLeft": f"3px solid {C['negative']}"},
            ),
        ],
        style={"marginBottom": "24px"},
    )


def _color_inf_real(val: Optional[float]) -> str:
    if val is None:
        return COLORS["text_muted"]
    return C["positive"] if val > 0 else C["negative"]


def _build_real_rates_heatmap() -> html.Div:
    """Sección 3.4: Mapa de calor de tipos reales por país."""
    zones = [
        ("EE.UU.",   ID_FED_FUNDS, ID_CPI_YOY_US),
        ("Eurozona", ID_ECB_RATE,  ID_HICP_EA),
        ("Alemania", ID_ECB_RATE,  ID_HICP_DE),
        ("España",   ID_ECB_RATE,  ID_HICP_ES),
        ("Italia",   ID_ECB_RATE,  ID_HICP_IT),
    ]

    periods_label = ["Actual", "Hace 6M", "Hace 1A", "Hace 2A"]
    periods_days  = [0, 180, 365, 730]

    countries = []
    z_rows = []
    text_rows = []

    for name, rate_sid, cpi_sid in zones:
        df_rate = get_series(rate_sid, days=800)
        df_cpi  = get_series(cpi_sid, days=800)
        now = datetime.utcnow()

        row_z = []
        row_t = []
        for d in periods_days:
            target = now - timedelta(days=d)

            def _get_val(df):
                if df.empty:
                    return None
                sub = df[df["timestamp"] <= target]
                return float(sub.iloc[-1]["value"]) if not sub.empty else None

            r = _get_val(df_rate)
            c = _get_val(df_cpi)
            if r is not None and c is not None:
                real = r - c
                row_z.append(real)
                row_t.append(f"{real:+.2f}%")
            else:
                row_z.append(None)
                row_t.append("—")

        countries.append(name)
        z_rows.append(row_z)
        text_rows.append(row_t)

    fig = go.Figure(go.Heatmap(
        z=z_rows,
        x=periods_label,
        y=countries,
        text=text_rows,
        texttemplate="%{text}",
        colorscale=[
            [0.0,  "#7f1d1d"],   # muy negativo: rojo intenso
            [0.35, "#ef4444"],   # negativo
            [0.5,  "#e5e7eb"],   # cero: blanco
            [0.65, "#86efac"],   # ligeramente positivo
            [1.0,  "#166534"],   # muy positivo: verde oscuro
        ],
        zmid=0,
        zmin=-5,
        zmax=3,
        colorbar={
            "title": "Tipo real %",
            "ticksuffix": "%",
            "thickness": 14,
            "len": 0.8,
            "tickfont": {"color": "#9ca3af", "size": 10},
            "titlefont": {"color": "#9ca3af", "size": 10},
        },
        hovertemplate="<b>%{y}</b><br>%{x}: %{text}<extra></extra>",
    ))
    fig.update_layout(**get_base_layout(height=260))
    fig.update_layout(margin={"l": 80, "r": 20, "t": 20, "b": 40})

    return html.Div(
        [
            html.Div("TIPOS REALES POR ZONA (tipo oficial − inflación)", style=_section_label_style()),
            dcc.Graph(figure=fig, config={"displayModeBar": False}),
        ],
        style={"marginBottom": "24px"},
    )


def _build_sovereign_real_cost() -> html.Div:
    """Sección 3.5: Coste real de la deuda soberana."""
    bonds = [
        ("🇺🇸 EE.UU. 10Y",  "fred_yield_10y_us",  ID_CPI_YOY_US),
        ("🇩🇪 Alemania 10Y", "ecb_bund_10y_de",    ID_HICP_DE),
        ("🇪🇸 España 10Y",   "ecb_yield_10y_es",   ID_HICP_ES),
        ("🇮🇹 Italia 10Y",   "ecb_yield_10y_it",   ID_HICP_IT),
        ("🇫🇷 Francia 10Y",  "ecb_yield_10y_fr",   None),
    ]

    names, real_rates, colors, texts = [], [], [], []
    for label, yield_sid, cpi_sid in bonds:
        y_val, _ = get_latest_value(yield_sid)
        c_val = None
        if cpi_sid:
            c_val, _ = get_latest_value(cpi_sid)
        if y_val is not None and c_val is not None:
            real = y_val - c_val
            names.append(label)
            real_rates.append(real)
            colors.append(C["negative"] if real < 0 else C["positive"])
            texts.append(f"{real:+.2f}%")
        elif y_val is not None:
            names.append(label)
            real_rates.append(None)
            colors.append(COLORS["text_muted"])
            texts.append("Sin IPC")

    if not names:
        return html.Div(
            [
                html.Div("COSTE REAL DE LA DEUDA SOBERANA", style=_section_label_style()),
                create_empty_state("Sin datos de rendimientos de bonos"),
            ],
            style={"marginBottom": "24px"},
        )

    valid = [(n, r, c, t) for n, r, c, t in zip(names, real_rates, colors, texts)
             if r is not None]
    if not valid:
        return html.Div(
            [
                html.Div("COSTE REAL DE LA DEUDA SOBERANA", style=_section_label_style()),
                create_empty_state("Sin datos suficientes para calcular tipos reales soberanos"),
            ],
            style={"marginBottom": "24px"},
        )

    v_names, v_rates, v_colors, v_texts = zip(*valid)

    fig = go.Figure(go.Bar(
        x=list(v_rates),
        y=list(v_names),
        orientation="h",
        marker_color=list(v_colors),
        text=list(v_texts),
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>Tipo real: %{text}<extra></extra>",
    ))

    fig.add_vline(x=0, line_dash="solid", line_color="#6b7280", line_width=1.5)
    fig.update_layout(**get_base_layout("Tipo Real Deuda Soberana (yield 10Y − inflación)", height=300))
    fig.update_layout(
        xaxis={"ticksuffix": "%"},
        margin={"l": 140, "r": 60, "t": 40, "b": 40},
    )

    return html.Div(
        [
            html.Div("COSTE REAL DE LA DEUDA SOBERANA", style=_section_label_style()),
            dcc.Graph(figure=fig, config={"displayModeBar": False}),
            html.Div(
                "Barras rojas: el Estado paga tipo real negativo (la inflación erosiona el valor de su deuda, "
                "subvencionado por los ahorradores). Barras verdes: coste real positivo.",
                style={
                    "fontSize": "0.72rem", "color": COLORS["text_muted"],
                    "marginTop": "8px", "fontStyle": "italic",
                },
            ),
        ],
        style={"marginBottom": "24px"},
    )


def _build_tab3_content() -> html.Div:
    return html.Div(
        [
            _build_repression_thermometers(),
            _build_cash_erosion_calculator(),
            _build_real_yield_history(),
            _build_real_rates_heatmap(),
            _build_sovereign_real_cost(),
        ],
        style={"padding": "20px"},
    )


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS DE ESTILO
# ══════════════════════════════════════════════════════════════════════════════

def _section_label_style() -> dict:
    return {
        "fontSize": "0.65rem", "letterSpacing": "0.1em",
        "color": COLORS["text_label"], "fontWeight": "600", "marginBottom": "10px",
    }


def _label_style() -> dict:
    return {
        "fontSize": "0.72rem", "color": COLORS["text_muted"],
        "marginBottom": "4px", "display": "block",
    }


# ══════════════════════════════════════════════════════════════════════════════
# CALCULADORA — lógica
# ══════════════════════════════════════════════════════════════════════════════

def _run_erosion_calc(amount: float, start_date_str: str, country: str) -> html.Div:
    """Ejecuta el cálculo de erosión y devuelve el panel de resultado."""
    from modules.data_helpers import calculate_real_purchasing_power

    result = calculate_real_purchasing_power(amount, start_date_str, country)
    if result is None:
        return create_empty_state(
            "No hay datos suficientes para calcular",
            f"El IPC de {country} no está disponible desde {start_date_str} en la base de datos.",
        )

    nom    = result["valor_nominal"]
    real   = result["valor_real"]
    loss   = result["perdida_absoluta"]
    pct    = result["perdida_porcentual"]
    acc    = result["inflacion_acumulada"]
    serie  = result.get("serie_temporal")
    currency = "USD" if country == "US" else "EUR"
    color = C["positive"] if real >= nom else C["negative"]

    # Gráfico de evolución
    fig = go.Figure()
    if serie is not None and not serie.empty:
        fig.add_trace(go.Scatter(
            x=serie["timestamp"], y=serie["nominal"],
            name="Valor nominal",
            line={"color": "#6b7280", "width": 1.5, "dash": "dot"},
            hovertemplate="Nominal: %{y:,.0f}<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=serie["timestamp"], y=serie["real"],
            name="Valor real (poder adquisitivo)",
            line={"color": color, "width": 2},
            fill="tonexty",
            fillcolor="rgba(239,68,68,0.08)" if real < nom else "rgba(16,185,129,0.08)",
            hovertemplate="Real: %{y:,.0f}<extra></extra>",
        ))
        fig.update_layout(**get_base_layout("Evolución del Poder Adquisitivo", height=280))

    summary = html.Div(
        [
            dbc.Row(
                [
                    dbc.Col(
                        html.Div([
                            html.Div("VALOR NOMINAL HOY", style=_section_label_style()),
                            html.Div(
                                f"{nom:,.0f} {currency}",
                                style={"fontSize": "1.4rem", "fontWeight": "700",
                                       "color": COLORS["text"], "fontFamily": "monospace"},
                            ),
                        ], style=_kpi_card_style()),
                        width=4,
                    ),
                    dbc.Col(
                        html.Div([
                            html.Div("VALOR REAL HOY", style=_section_label_style()),
                            html.Div(
                                f"{real:,.0f} {currency}",
                                style={"fontSize": "1.4rem", "fontWeight": "700",
                                       "color": color, "fontFamily": "monospace"},
                            ),
                        ], style=_kpi_card_style()),
                        width=4,
                    ),
                    dbc.Col(
                        html.Div([
                            html.Div("PÉRDIDA DE PODER ADQUISITIVO", style=_section_label_style()),
                            html.Div(
                                f"{abs(loss):,.0f} {currency} ({abs(pct):.1f}%)",
                                style={"fontSize": "1.1rem", "fontWeight": "700",
                                       "color": C["negative"] if loss < 0 else C["positive"],
                                       "fontFamily": "monospace"},
                            ),
                            html.Div(
                                f"Inflación acumulada: {acc:.1f}%",
                                style={"fontSize": "0.72rem", "color": COLORS["text_muted"]},
                            ),
                        ], style=_kpi_card_style()),
                        width=4,
                    ),
                ],
                className="g-2 mb-3",
            ),
            dcc.Graph(figure=fig, config={"displayModeBar": False}) if serie is not None and not serie.empty
            else html.Div(),
            html.Div(
                f"Si guardaste {nom:,.0f} {currency} en efectivo desde {start_date_str}, "
                f"hoy tendrías el equivalente a {real:,.0f} {currency} en poder adquisitivo. "
                f"Has perdido {abs(pct):.1f}% de valor real por la inflación acumulada ({acc:.1f}%).",
                style={
                    "fontSize": "0.78rem", "color": COLORS["text_muted"],
                    "marginTop": "8px", "padding": "8px 12px",
                    "backgroundColor": COLORS["card_bg"],
                    "borderRadius": "4px",
                    "borderLeft": f"3px solid {C['negative']}",
                    "fontStyle": "italic",
                },
            ),
        ]
    )

    return summary


def _kpi_card_style() -> dict:
    return {
        "backgroundColor": COLORS["card_bg"],
        "border": f"1px solid {COLORS['border']}",
        "borderRadius": "6px",
        "padding": "12px 14px",
    }


# ══════════════════════════════════════════════════════════════════════════════
# RENDER PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

def render_module_3() -> html.Div:
    """Retorna el layout completo del Módulo 3 — Inflación Global."""
    return html.Div(
        [
            _build_m3_header(),
            dcc.Tabs(
                id="m3-tabs",
                value="tab-global",
                children=[
                    dcc.Tab(
                        label="🌍 Visión Global",
                        value="tab-global",
                        style=TAB_STYLE,
                        selected_style=TAB_SELECTED_STYLE,
                    ),
                    dcc.Tab(
                        label="🔍 Inflación en Detalle",
                        value="tab-detail",
                        style=TAB_STYLE,
                        selected_style=TAB_SELECTED_STYLE,
                    ),
                    dcc.Tab(
                        label="💸 Represión Financiera",
                        value="tab-repression",
                        style=TAB_STYLE,
                        selected_style=TAB_SELECTED_STYLE,
                    ),
                ],
                style=TABS_STYLE,
                colors={
                    "border":     COLORS["border"],
                    "primary":    COLORS["accent"],
                    "background": COLORS["card_bg"],
                },
            ),
            html.Div(id="m3-tab-content"),
            dcc.Store(id="m3-active-tab-store", storage_type="session", data="tab-global"),
        ],
        id="m3-root",
        style={"minHeight": "100vh", "backgroundColor": COLORS["background"]},
    )


# ══════════════════════════════════════════════════════════════════════════════
# REGISTRO DE CALLBACKS
# ══════════════════════════════════════════════════════════════════════════════

def register_callbacks_module_3(app) -> None:
    """Registra todos los callbacks del Módulo 3."""

    # ── 1. Tab routing ────────────────────────────────────────────────────────
    @app.callback(
        Output("m3-tab-content",      "children"),
        Output("m3-active-tab-store", "data"),
        Input("m3-tabs",              "value"),
        Input("m3-refresh-interval",  "n_intervals"),
    )
    def render_tab(tab_value, _n):
        try:
            if tab_value == "tab-global":
                return _build_tab1_content(), tab_value
            elif tab_value == "tab-detail":
                return _build_tab2_layout(), tab_value
            elif tab_value == "tab-repression":
                return _build_tab3_content(), tab_value
            return _build_tab1_content(), "tab-global"
        except Exception as e:
            logger.error("m3 tab render error: %s", e, exc_info=True)
            return html.Div(
                f"Error renderizando tab: {e}",
                style={"color": COLORS["text_muted"], "padding": "24px"},
            ), tab_value

    # ── 2. Restaurar tab ──────────────────────────────────────────────────────
    @app.callback(
        Output("m3-tabs", "value"),
        Input("m3-active-tab-store", "data"),
        prevent_initial_call=True,
    )
    def restore_tab(stored_tab):
        return stored_tab or "tab-global"

    # ── 3. Detalle de país (Tab 2) ────────────────────────────────────────────
    @app.callback(
        Output("m3-detail-content", "children"),
        Input("m3-country-selector", "value"),
    )
    def update_country_detail(country):
        if not country:
            return create_empty_state("Selecciona un país")
        try:
            return _render_country_detail(country)
        except Exception as e:
            logger.error("m3 country detail error: %s", e, exc_info=True)
            return create_empty_state(f"Error: {e}")

    # ── 4. Gráfico comparativo internacional (Tab 1) ──────────────────────────
    @app.callback(
        Output("m3-intl-chart",       "figure"),
        Output("m3-intl-range-store", "data"),
        Input("m3-country-checklist", "value"),
        Input("m3-intl-range-1A",     "n_clicks"),
        Input("m3-intl-range-2A",     "n_clicks"),
        Input("m3-intl-range-5A",     "n_clicks"),
        Input("m3-intl-range-MÁX",   "n_clicks"),
        State("m3-intl-range-store",  "data"),
        prevent_initial_call=False,
    )
    def update_intl_chart(selected, n1a, n2a, n5a, nmax, current_range):
        triggered = ctx.triggered_id
        range_map = {
            "m3-intl-range-1A":  "1A",
            "m3-intl-range-2A":  "2A",
            "m3-intl-range-5A":  "5A",
            "m3-intl-range-MÁX": "MÁX",
        }
        new_range = range_map.get(triggered, current_range or "5A")

        days_map = {"1A": 365, "2A": 730, "5A": 1825, "MÁX": 5000}
        days = days_map.get(new_range, 1825)

        country_series = {
            "EE.UU.":   (ID_CPI_YOY_US, "#3b82f6"),
            "Eurozona": (ID_HICP_EA,    "#10b981"),
            "Alemania": (ID_HICP_DE,    "#8b5cf6"),
            "España":   (ID_HICP_ES,    "#f59e0b"),
            "Italia":   (ID_HICP_IT,    "#ef4444"),
        }

        fig = go.Figure()
        for name in (selected or []):
            if name not in country_series:
                continue
            sid, color = country_series[name]
            df = get_series(sid, days=days)
            if df.empty:
                continue
            fig.add_trace(go.Scatter(
                x=df["timestamp"], y=df["value"],
                name=name,
                line={"color": color, "width": 2},
                hovertemplate=f"<b>{name}</b>: %{{y:.1f}}%<br>%{{x|%b %Y}}<extra></extra>",
            ))

            # Anotación en el máximo
            if not df.empty:
                max_idx = df["value"].idxmax()
                max_row = df.loc[max_idx]
                fig.add_annotation(
                    x=max_row["timestamp"],
                    y=float(max_row["value"]),
                    text=f"{float(max_row['value']):.1f}%",
                    showarrow=True,
                    arrowhead=2,
                    arrowcolor=color,
                    font={"color": color, "size": 9},
                    arrowsize=0.6,
                    ax=20, ay=-20,
                )

        fig.add_hline(
            y=2.0,
            line_dash="dash",
            line_color="#6b7280",
            line_width=1,
            annotation_text="Objetivo 2%",
            annotation_font_color="#9ca3af",
            annotation_font_size=10,
        )

        layout = get_base_layout("Inflación Histórica — Comparativa Internacional", height=380)
        layout["yaxis"] = {**layout.get("yaxis", {}), "ticksuffix": "%"}
        fig.update_layout(**layout)

        return fig, new_range

    # ── 5. Calculadora de erosión ─────────────────────────────────────────────
    @app.callback(
        Output("m3-calc-result", "children"),
        Input("m3-calc-btn",     "n_clicks"),
        State("m3-calc-amount",  "value"),
        State("m3-calc-date",    "date"),
        State("m3-calc-country", "value"),
        prevent_initial_call=True,
    )
    def run_calc(n_clicks, amount, date_str, country):
        if not n_clicks or amount is None or date_str is None:
            return html.Div()
        try:
            return _run_erosion_calc(float(amount), date_str, country or "US")
        except Exception as e:
            logger.error("m3 calc error: %s", e, exc_info=True)
            return create_empty_state(f"Error en cálculo: {e}")
