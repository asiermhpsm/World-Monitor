"""
Modulo 5 — Mercados Financieros
Renderiza cuando la URL es /module/5.

Exporta:
  render_module_5()               -> layout completo
  register_callbacks_module_5(app) -> registra todos los callbacks
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import Input, Output, State, dcc, html, no_update

from components.chart_config import COLORS as C, get_base_layout, get_time_range_buttons
from components.common import create_empty_state, create_metric_card
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

# Equity indices
ID_SP500        = "yf_sp500_close"
ID_NDX100       = "yf_ndx100_close"
ID_DJI          = "yf_dji_close"
ID_RUT2000      = "yf_rut2000_close"
ID_EUROSTOXX50  = "yf_eurostoxx50_close"
ID_DAX          = "yf_dax_close"
ID_CAC40        = "yf_cac40_close"
ID_IBEX35       = "yf_ibex35_close"
ID_FTSEMIB      = "yf_ftsemib_close"
ID_FTSE100      = "yf_ftse100_close"
ID_SMI          = "yf_smi_close"
ID_NIKKEI       = "yf_nikkei225_close"
ID_HANGSENG     = "yf_hangseng_close"
ID_SHANGHAI     = "yf_shanghai_close"
ID_CSI300       = "yf_csi300_close"
ID_SENSEX       = "yf_sensex_close"
ID_BOVESPA      = "yf_bovespa_close"
ID_IPC_MEX      = "yf_ipc_mexico_close"
ID_MSCI_WORLD   = "yf_msci_world_close"
ID_MSCI_EM      = "yf_msci_em_close"

# Market breadth
ID_RSP          = "yf_rsp_close"
ID_SPY          = "yf_spy_close"
ID_RSP_SPY      = "yf_rsp_spy_ratio"

# US Yield Curve
ID_Y3M          = "yf_irx_close"          # ^IRX proxy; también fred_yield_3m_us
ID_Y3M_FRED     = "fred_yield_3m_us"
ID_Y6M_FRED     = "fred_yield_6m_us"
ID_Y1Y_FRED     = "fred_yield_1y_us"
ID_Y2Y_FRED     = "fred_yield_2y_us"
ID_Y3Y_FRED     = "fred_yield_3y_us"
ID_Y5Y_FRED     = "fred_yield_5y_us"
ID_Y7Y_FRED     = "fred_yield_7y_us"
ID_Y10Y_FRED    = "fred_yield_10y_us"
ID_Y20Y_FRED    = "fred_yield_20y_us"
ID_Y30Y_FRED    = "fred_yield_30y_us"
ID_SPREAD_10Y2Y = "fred_spread_10y2y_us"
ID_SPREAD_10Y3M = "fred_spread_10y3m_us"

# European bonds
ID_BUND_10Y     = "ecb_bund_10y_de"
ID_YIELD_ES     = "ecb_yield_10y_es"
ID_YIELD_IT     = "ecb_yield_10y_it"
ID_YIELD_FR     = "ecb_yield_10y_fr"
ID_YIELD_PT     = "ecb_yield_10y_pt"
ID_YIELD_GR     = "ecb_yield_10y_gr"
ID_SPREAD_ES    = "ecb_spread_es_de"
ID_SPREAD_IT    = "ecb_spread_it_de"
ID_SPREAD_FR    = "ecb_spread_fr_de"
ID_SPREAD_PT    = "ecb_spread_pt_de"
ID_SPREAD_GR    = "ecb_spread_gr_de"

# Credit ETFs
ID_HYG          = "yf_hyg_close"
ID_LQD          = "yf_lqd_close"
ID_IEF          = "yf_ief_close"

# FX
ID_DXY          = "yf_dxy_close"
ID_EURUSD       = "yf_eurusd_close"
ID_GBPUSD       = "yf_gbpusd_close"
ID_USDJPY       = "yf_usdjpy_close"
ID_USDCHF       = "yf_usdchf_close"
ID_AUDUSD       = "yf_audusd_close"
ID_USDCAD       = "yf_usdcad_close"
ID_USDCNY       = "yf_usdcny_close"
ID_USDBRL       = "yf_usdbrl_close"
ID_USDMXN       = "yf_usdmxn_close"
ID_USDINR       = "yf_usdinr_close"
ID_USDTRY       = "yf_usdtry_close"
ID_USDARS       = "yf_usdars_close"

# Commodities — energy
ID_BRENT        = "yf_bz_close"
ID_WTI          = "yf_cl_close"
ID_GAS_HH       = "yf_ng_close"
ID_GAS_TTF      = "yf_ttf_close"

# Commodities — precious metals
ID_GOLD         = "yf_gc_close"
ID_SILVER       = "yf_si_close"
ID_PLATINUM     = "yf_pl_close"
ID_PALLADIUM    = "yf_pa_close"
ID_REAL_YIELD   = "fred_real_yield_10y_us"

# Commodities — industrial metals
ID_COPPER       = "yf_hg_close"
ID_ALUMINUM     = "yf_ali_close"
ID_ZINC         = "yf_znc_close"

# Commodities — agricultural
ID_WHEAT        = "yf_zw_close"
ID_CORN         = "yf_zc_close"
ID_SOY          = "yf_zs_close"
ID_RICE         = "yf_zr_close"
ID_SUGAR        = "yf_sb_close"
ID_COFFEE       = "yf_kc_close"
ID_COCOA        = "yf_cc_close"

# Volatility
ID_VIX          = "yf_vix_close"

# Crypto
ID_BTC          = "cg_btc_price_usd"
ID_ETH          = "cg_eth_price_usd"
ID_FEAR_GREED   = "cg_fear_greed_value"
ID_BTC_MCAP     = "cg_btc_market_cap_usd"
ID_ETH_MCAP     = "cg_eth_market_cap_usd"
ID_TOTAL_MCAP   = "cg_total_market_cap_usd"
ID_BTC_DOM      = "cg_bitcoin_dominance_pct"
ID_ETH_DOM      = "cg_ethereum_dominance_pct"
ID_STABLE_DOM   = "cg_stablecoin_dominance_pct"
ID_BTC_SP500    = "cg_btc_sp500_corr_30d"
ID_BTC_GOLD     = "cg_btc_gold_corr_30d"


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _safe(val, fmt=".2f", suffix=""):
    """Formatea valor de forma segura, devuelve — si None."""
    if val is None:
        return "—"
    try:
        return f"{val:{fmt}}{suffix}"
    except Exception:
        return "—"


def _pct_color(val: Optional[float]) -> str:
    if val is None:
        return COLORS["text_muted"]
    return C["positive"] if val >= 0 else C["negative"]


def _pct_str(val: Optional[float]) -> str:
    if val is None:
        return "—"
    sign = "+" if val >= 0 else ""
    return f"{sign}{val:.2f}%"


def _get_change_pct(series_id: str, days: int) -> Optional[float]:
    """Devuelve el % de cambio en los últimos N días, o None."""
    _, _, _, pct = get_change(series_id, period_days=days)
    return pct


def _get_ytd_change(series_id: str) -> Optional[float]:
    """Devuelve el % de cambio desde inicio de año."""
    try:
        from datetime import date
        now = datetime.utcnow()
        year_start = datetime(now.year, 1, 1)
        from database.database import SessionLocal, TimeSeries
        with SessionLocal() as db:
            cur = db.query(TimeSeries).filter(
                TimeSeries.indicator_id == series_id
            ).order_by(TimeSeries.timestamp.desc()).first()
            if cur is None or cur.value is None:
                return None
            ref = db.query(TimeSeries).filter(
                TimeSeries.indicator_id == series_id,
                TimeSeries.timestamp >= year_start,
            ).order_by(TimeSeries.timestamp.asc()).first()
            if ref is None or ref.value is None or ref.value == 0:
                return None
            return (cur.value - ref.value) / abs(ref.value) * 100
    except Exception:
        return None


def _get_52w_high(series_id: str) -> Optional[float]:
    df = get_series(series_id, days=365)
    if df.empty:
        return None
    return float(df["value"].max())


def _dist_to_ath(series_id: str) -> Optional[float]:
    """Distancia al máximo histórico disponible en BD (%)."""
    df = get_series(series_id, days=3650)
    if df.empty:
        return None
    cur, _ = get_latest_value(series_id)
    if cur is None:
        return None
    ath = float(df["value"].max())
    if ath == 0:
        return None
    return (cur - ath) / abs(ath) * 100


def _compact_metric(title: str, series_id: str, fmt=".2f", prefix="", suffix="") -> html.Div:
    """Metric card compacta para el header del módulo."""
    val, ts = get_latest_value(series_id)
    _, _, _, pct24h = get_change(series_id, period_days=1)
    val_str = f"{prefix}{_safe(val, fmt)}{suffix}" if val is not None else "—"
    color = _pct_color(pct24h)
    change_str = _pct_str(pct24h) if pct24h is not None else ""

    return html.Div(
        [
            html.Div(title, style={
                "fontSize": "0.60rem", "color": COLORS["text_label"],
                "fontWeight": "600", "letterSpacing": "0.08em", "marginBottom": "2px",
            }),
            html.Div(val_str, style={
                "fontSize": "0.95rem", "fontWeight": "700", "color": COLORS["text"],
                "fontFamily": "monospace",
            }),
            html.Div(change_str, style={
                "fontSize": "0.68rem", "color": color, "fontWeight": "600",
            }),
        ],
        style={
            "backgroundColor": COLORS["card_bg"],
            "border": f"1px solid {COLORS['border']}",
            "borderRadius": "6px",
            "padding": "8px 12px",
            "minWidth": "100px",
            "flex": "1",
        },
    )



def _fa(hex_color: str, hex_alpha: str) -> str:
    """Convierte color hex + alpha hex a rgba() para Plotly fillcolor."""
    try:
        h = hex_color.lstrip('#')
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        a = int(hex_alpha, 16) / 255
        return f"rgba({r},{g},{b},{a:.2f})"
    except Exception:
        return hex_color

# ══════════════════════════════════════════════════════════════════════════════
# HEADER DEL MÓDULO
# ══════════════════════════════════════════════════════════════════════════════

def _build_m05_header() -> html.Div:
    _, ts = get_latest_value(ID_SP500)
    last_str = ts.strftime("%d/%m/%Y %H:%M") if ts else "Sin datos"

    metrics_row = html.Div(
        [
            _compact_metric("S&P 500",  ID_SP500,  fmt=",.0f"),
            _compact_metric("VIX",      ID_VIX,    fmt=".2f"),
            _compact_metric("ORO",      ID_GOLD,   fmt=",.0f", prefix="$"),
            _compact_metric("BRENT",    ID_BRENT,  fmt=".2f",  prefix="$"),
            _compact_metric("EUR/USD",  ID_EURUSD, fmt=".4f"),
            _compact_metric("BITCOIN",  ID_BTC,    fmt=",.0f", prefix="$"),
        ],
        style={
            "display": "flex", "gap": "8px", "flexWrap": "wrap",
            "marginTop": "12px",
        },
    )

    return html.Div(
        [
            html.Div(
                [
                    html.Span(
                        "Mercados Financieros",
                        style={"fontSize": "1.4rem", "fontWeight": "700", "color": COLORS["text"]},
                    ),
                    html.Span(
                        f"Yahoo Finance · {last_str}",
                        id="m05-last-updated",
                        style={"fontSize": "0.72rem", "color": COLORS["text_muted"], "marginLeft": "16px"},
                    ),
                ],
                style={"display": "flex", "alignItems": "baseline"},
            ),
            metrics_row,
            dcc.Interval(id="m05-refresh-interval", interval=300_000, n_intervals=0),
        ],
        style={
            "padding": "16px 20px 14px",
            "borderBottom": f"1px solid {COLORS['border']}",
            "backgroundColor": COLORS["card_bg"],
        },
    )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — RENTA VARIABLE
# ══════════════════════════════════════════════════════════════════════════════

# Catálogo de índices: (display_name, flag_emoji, series_id)
INDICES_CATALOG = [
    ("S&P 500",          "🇺🇸", ID_SP500),
    ("Nasdaq 100",       "🇺🇸", ID_NDX100),
    ("Dow Jones",        "🇺🇸", ID_DJI),
    ("Russell 2000",     "🇺🇸", ID_RUT2000),
    ("Eurostoxx 50",     "🇪🇺", ID_EUROSTOXX50),
    ("DAX",              "🇩🇪", ID_DAX),
    ("CAC 40",           "🇫🇷", ID_CAC40),
    ("IBEX 35",          "🇪🇸", ID_IBEX35),
    ("FTSE MIB",         "🇮🇹", ID_FTSEMIB),
    ("FTSE 100",         "🇬🇧", ID_FTSE100),
    ("SMI",              "🇨🇭", ID_SMI),
    ("Nikkei 225",       "🇯🇵", ID_NIKKEI),
    ("Hang Seng",        "🇭🇰", ID_HANGSENG),
    ("Shanghai Comp.",   "🇨🇳", ID_SHANGHAI),
    ("CSI 300",          "🇨🇳", ID_CSI300),
    ("Sensex",           "🇮🇳", ID_SENSEX),
    ("Bovespa",          "🇧🇷", ID_BOVESPA),
    ("IPC México",       "🇲🇽", ID_IPC_MEX),
    ("MSCI World",       "🌍",  ID_MSCI_WORLD),
    ("MSCI EM",          "🌏",  ID_MSCI_EM),
]

DEFAULT_COMPARE_INDICES = [ID_SP500, ID_EUROSTOXX50, ID_IBEX35, ID_NIKKEI, ID_SHANGHAI]


def _build_indices_table() -> html.Div:
    """Sección 1.1 — Tabla de índices globales."""
    rows = []
    for name, flag, sid in INDICES_CATALOG:
        cur, _ = get_latest_value(sid)
        _, _, _, pct1d  = get_change(sid, period_days=1)
        _, _, _, pct7d  = get_change(sid, period_days=7)
        _, _, _, pct30d = get_change(sid, period_days=30)
        pct_ytd         = _get_ytd_change(sid)
        _, _, _, pct365 = get_change(sid, period_days=365)
        dist_ath        = _dist_to_ath(sid)

        def _pct_cell(v):
            if v is None:
                return html.Td("—", style={"color": COLORS["text_label"], "textAlign": "right"})
            color = C["positive"] if v >= 0 else C["negative"]
            sign = "+" if v >= 0 else ""
            # Barra de fondo
            bar_w = min(abs(v) * 3, 100)
            bar_color = C["positive"] if v >= 0 else C["negative"]
            return html.Td(
                html.Div(
                    [
                        html.Div(
                            style={
                                "position": "absolute", "left": "0", "top": "0",
                                "height": "100%", "width": f"{bar_w}%",
                                "backgroundColor": _fa(bar_color, "22"),
                                "borderRadius": "2px",
                            }
                        ),
                        html.Span(
                            f"{sign}{v:.2f}%",
                            style={"color": color, "position": "relative", "fontWeight": "600",
                                   "fontSize": "0.80rem"},
                        ),
                    ],
                    style={"position": "relative", "textAlign": "right"},
                ),
                style={"textAlign": "right", "paddingRight": "8px"},
            )

        rows.append(html.Tr([
            html.Td(
                html.Span([flag, " ", name]),
                style={"whiteSpace": "nowrap", "fontSize": "0.82rem"},
            ),
            html.Td(
                format_value(cur, decimals=2) if cur else "—",
                style={"textAlign": "right", "fontFamily": "monospace", "fontSize": "0.82rem"},
            ),
            _pct_cell(pct1d),
            _pct_cell(pct7d),
            _pct_cell(pct30d),
            _pct_cell(pct_ytd),
            _pct_cell(pct365),
            html.Td(
                f"{dist_ath:.1f}%" if dist_ath is not None else "—",
                style={
                    "textAlign": "right",
                    "color": C["negative"] if dist_ath is not None and dist_ath < -10 else COLORS["text_muted"],
                    "fontSize": "0.80rem",
                },
            ),
        ]))

    thead = html.Thead(html.Tr([
        html.Th(h, style={"fontSize": "0.72rem", "color": COLORS["text_label"],
                          "fontWeight": "600", "textAlign": "right" if i > 0 else "left",
                          "borderBottom": f"2px solid {COLORS['border']}",
                          "paddingBottom": "6px", "whiteSpace": "nowrap"})
        for i, h in enumerate(["Índice", "Precio", "1D", "1W", "1M", "YTD", "1A", "Dist. ATH"])
    ]))

    return html.Div(
        [
            html.Div("ÍNDICES GLOBALES", style={
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
        ],
        style={"marginBottom": "24px"},
    )


def _build_compare_chart() -> html.Div:
    """Sección 1.2 — Gráfico comparativo de rendimiento normalizado."""
    checklist_options = [
        {"label": f"{flag} {name}", "value": sid}
        for name, flag, sid in INDICES_CATALOG
    ]

    return html.Div(
        [
            html.Div("RENDIMIENTO COMPARATIVO (BASE 100)", style={
                "fontSize": "0.65rem", "letterSpacing": "0.1em",
                "color": COLORS["text_label"], "fontWeight": "600", "marginBottom": "10px",
            }),
            dbc.Row([
                dbc.Col([
                    html.Div("Seleccionar índices:", style={
                        "fontSize": "0.72rem", "color": COLORS["text_muted"], "marginBottom": "6px",
                    }),
                    dcc.Checklist(
                        id="m05-compare-checklist",
                        options=checklist_options,
                        value=DEFAULT_COMPARE_INDICES,
                        labelStyle={"display": "block", "fontSize": "0.78rem",
                                    "color": COLORS["text_muted"], "marginBottom": "3px"},
                        inputStyle={"marginRight": "6px"},
                    ),
                ], md=3),
                dbc.Col([
                    html.Div([
                        html.Div("Período:", style={"fontSize": "0.72rem", "color": COLORS["text_muted"],
                                                    "display": "inline", "marginRight": "8px"}),
                        *[
                            html.Button(
                                label, id=f"m05-compare-range-{code}",
                                n_clicks=0,
                                style={
                                    "backgroundColor": COLORS["accent"] if code == "1A" else COLORS["card_bg"],
                                    "color": COLORS["text"], "border": f"1px solid {COLORS['border']}",
                                    "borderRadius": "4px", "padding": "3px 10px",
                                    "fontSize": "0.72rem", "marginRight": "4px", "cursor": "pointer",
                                },
                            )
                            for label, code in [("1M","1M"),("3M","3M"),("6M","6M"),("1A","1A"),("5A","5A"),("MÁX","MAX")]
                        ],
                    ], style={"marginBottom": "8px"}),
                    dcc.Store(id="m05-compare-range-store", data="1A"),
                    dcc.Graph(
                        id="m05-compare-chart",
                        config={"displayModeBar": False},
                        style={"height": "360px"},
                    ),
                ], md=9),
            ], className="g-2"),
        ],
        style={"marginBottom": "24px"},
    )


def _calc_compare_fig(selected_ids: list, range_code: str) -> go.Figure:
    """Construye el gráfico normalizado base 100."""
    range_days = {"1M": 30, "3M": 90, "6M": 180, "1A": 365, "5A": 1825, "MAX": 3650}
    days = range_days.get(range_code, 365)

    palette = [
        "#3b82f6","#10b981","#f59e0b","#ef4444","#8b5cf6",
        "#06b6d4","#f97316","#84cc16","#ec4899","#14b8a6",
    ]

    fig = go.Figure()
    fig.update_layout(**get_base_layout("Rendimiento Relativo (Base 100)", height=360))

    added = 0
    for i, sid in enumerate(selected_ids or []):
        df = get_series(sid, days=days)
        if df.empty:
            continue
        base = df["value"].iloc[0]
        if base == 0:
            continue
        normalized = (df["value"] / base) * 100
        name = next((n for n, _, s in INDICES_CATALOG if s == sid), sid)
        fig.add_trace(go.Scatter(
            x=df["timestamp"], y=normalized,
            mode="lines", name=name,
            line={"color": palette[added % len(palette)], "width": 2},
            hovertemplate=f"<b>{name}</b><br>%{{x|%d/%m/%Y}}<br>Base 100: %{{y:.2f}}<extra></extra>",
        ))
        added += 1

    if added == 0:
        fig.add_annotation(text="Sin datos disponibles", xref="paper", yref="paper",
                           x=0.5, y=0.5, showarrow=False,
                           font={"color": COLORS["text_muted"], "size": 14})
    fig.add_hline(y=100, line_dash="dot", line_color=COLORS["border_mid"], line_width=1)
    return fig


def _build_valuation_panels() -> html.Div:
    """Sección 1.3 — Valoración del mercado americano (4 paneles)."""
    # Panel A: Shiller CAPE
    shiller_df = get_series("fred_shiller_cape_us", days=365 * 35)
    cape_val, _ = get_latest_value("fred_shiller_cape_us")
    if cape_val is None:
        # Fallback: intentar con PER alternativo
        cape_val, _ = get_latest_value("fred_forward_pe_us")

    cape_fig = go.Figure()
    cape_fig.update_layout(**get_base_layout("Shiller CAPE — S&P 500", height=260))
    if not shiller_df.empty:
        cape_fig.add_trace(go.Scatter(
            x=shiller_df["timestamp"], y=shiller_df["value"],
            mode="lines", name="CAPE", fill="tozeroy",
            line={"color": C["primary"], "width": 2},
            fillcolor=_fa(C["primary"], "18"),
        ))
        for y, label, color in [(15, "Infravalorado (15)", C["positive"]),
                                 (25, "Neutral (25)",       C["warning"]),
                                 (35, "Caro (35)",          C["orange"]),
                                 (45, "Burbuja (45)",       C["negative"])]:
            cape_fig.add_hline(y=y, line_dash="dot", line_color=color, line_width=1,
                               annotation_text=label, annotation_position="right",
                               annotation_font_size=9, annotation_font_color=color)
    else:
        cape_fig.add_annotation(text="Sin datos CAPE",
                                xref="paper", yref="paper", x=0.5, y=0.5,
                                showarrow=False, font={"color": COLORS["text_muted"]})

    cape_info = html.Div([
        html.Span("Valor actual: ", style={"color": COLORS["text_muted"], "fontSize": "0.78rem"}),
        html.Span(
            _safe(cape_val, ".1f") if cape_val else "—",
            style={"color": C["negative"] if cape_val and cape_val > 35 else C["positive"],
                   "fontWeight": "700", "fontFamily": "monospace"},
        ),
    ], style={"marginTop": "4px"})

    # Panel B: RSP/SPY (Amplitud)
    breadth_df = get_series(ID_RSP_SPY, days=730)
    sp500_df   = get_series(ID_SP500,   days=730)

    breadth_fig = go.Figure()
    breadth_fig.update_layout(**get_base_layout("Amplitud — RSP/SPY vs S&P 500", height=260))
    if not breadth_df.empty:
        breadth_fig.add_trace(go.Scatter(
            x=breadth_df["timestamp"], y=breadth_df["value"],
            mode="lines", name="RSP/SPY",
            line={"color": C["primary"], "width": 2},
        ))
    if not sp500_df.empty:
        sp_norm = sp500_df["value"] / sp500_df["value"].iloc[0]
        breadth_fig.add_trace(go.Scatter(
            x=sp500_df["timestamp"], y=sp_norm,
            mode="lines", name="S&P 500 (norm.)",
            line={"color": C["warning"], "width": 1.5, "dash": "dot"},
            yaxis="y2",
        ))
        breadth_fig.update_layout(
            yaxis2={"overlaying": "y", "side": "right",
                    "gridcolor": "rgba(0,0,0,0)", "tickfont": {"color": C["warning"], "size": 10}},
        )

    # Interpretación amplitud
    breadth_val, _ = get_latest_value(ID_RSP_SPY)
    breadth_interp = ""
    if breadth_val is not None:
        _, _, _, breadth_pct = get_change(ID_RSP_SPY, period_days=90)
        if breadth_pct is not None:
            if breadth_pct >= 0:
                breadth_interp = "✅ AMPLITUD SANA — mercado amplio, mayoría de acciones participando en la subida"
            else:
                breadth_interp = "⚠️ FRAGILIDAD — solo pocas empresas sustentan al índice vs equal weight"

    # Panel C: Spread de crédito (HYG-IEF proxy)
    hyg_df = get_series(ID_HYG, days=1095)
    ief_df = get_series(ID_IEF, days=1095)
    lqd_df = get_series(ID_LQD, days=1095)

    credit_fig = go.Figure()
    credit_fig.update_layout(**get_base_layout("Spreads de Crédito (proxies ETF)", height=260))

    if not hyg_df.empty and not ief_df.empty:
        merged = hyg_df.set_index("timestamp").join(
            ief_df.set_index("timestamp"), how="inner", lsuffix="_hyg", rsuffix="_ief"
        )
        if not merged.empty:
            spread_hy = (merged["value_ief"] / merged["value_hyg"] - 1) * (-100)
            credit_fig.add_trace(go.Scatter(
                x=merged.index, y=spread_hy,
                mode="lines", name="High Yield (proxy)",
                line={"color": C["negative"], "width": 2},
            ))

    if not lqd_df.empty and not ief_df.empty:
        merged_ig = lqd_df.set_index("timestamp").join(
            ief_df.set_index("timestamp"), how="inner", lsuffix="_lqd", rsuffix="_ief"
        )
        if not merged_ig.empty:
            spread_ig = (merged_ig["value_ief"] / merged_ig["value_lqd"] - 1) * (-100)
            credit_fig.add_trace(go.Scatter(
                x=merged_ig.index, y=spread_ig,
                mode="lines", name="Investment Grade (proxy)",
                line={"color": C["warning"], "width": 2},
            ))

    if credit_fig.data == ():
        credit_fig.add_annotation(text="Sin datos",
                                   xref="paper", yref="paper", x=0.5, y=0.5,
                                   showarrow=False, font={"color": COLORS["text_muted"]})

    return html.Div(
        [
            html.Div("VALORACIÓN Y AMPLITUD DEL MERCADO AMERICANO", style={
                "fontSize": "0.65rem", "letterSpacing": "0.1em",
                "color": COLORS["text_label"], "fontWeight": "600", "marginBottom": "12px",
            }),
            dbc.Row([
                dbc.Col([
                    dcc.Graph(figure=cape_fig, config={"displayModeBar": False}),
                    cape_info,
                ], md=4),
                dbc.Col([
                    dcc.Graph(figure=breadth_fig, config={"displayModeBar": False}),
                    html.Div(
                        breadth_interp,
                        style={"fontSize": "0.72rem", "color": COLORS["text_muted"], "marginTop": "4px"},
                    ),
                ], md=4),
                dbc.Col([
                    dcc.Graph(figure=credit_fig, config={"displayModeBar": False}),
                    html.Div(
                        "Spreads amplios = estrés financiero corporativo",
                        style={"fontSize": "0.72rem", "color": COLORS["text_muted"], "marginTop": "4px"},
                    ),
                ], md=4),
            ], className="g-3"),
        ],
    )


def _build_tab1_content() -> html.Div:
    return html.Div(
        [
            _build_indices_table(),
            _build_compare_chart(),
            _build_valuation_panels(),
        ],
        style={"padding": "20px"},
    )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — RENTA FIJA
# ══════════════════════════════════════════════════════════════════════════════

US_CURVE_MATURITIES = [
    ("3M", ID_Y3M_FRED), ("6M", ID_Y6M_FRED), ("1Y", ID_Y1Y_FRED),
    ("2Y", ID_Y2Y_FRED), ("3Y", ID_Y3Y_FRED), ("5Y", ID_Y5Y_FRED),
    ("7Y", ID_Y7Y_FRED), ("10Y", ID_Y10Y_FRED), ("20Y", ID_Y20Y_FRED),
    ("30Y", ID_Y30Y_FRED),
]


def _get_curve_snapshot(days_ago: int = 0) -> tuple[list, list]:
    """Devuelve (maturities_labels, yields) para la curva en un momento dado."""
    labels, vals = [], []
    cutoff = datetime.utcnow() - timedelta(days=days_ago)
    for label, sid in US_CURVE_MATURITIES:
        try:
            from database.database import SessionLocal, TimeSeries
            with SessionLocal() as db:
                row = db.query(TimeSeries).filter(
                    TimeSeries.indicator_id == sid,
                    TimeSeries.timestamp <= cutoff,
                ).order_by(TimeSeries.timestamp.desc()).first()
            if row and row.value is not None:
                labels.append(label)
                vals.append(row.value)
        except Exception:
            pass
    return labels, vals


def _build_yield_curve_section() -> html.Div:
    """Sección 2.1 — Curva de tipos EE.UU."""
    labels_now,  vals_now  = _get_curve_snapshot(0)
    labels_1m,   vals_1m   = _get_curve_snapshot(30)
    labels_6m,   vals_6m   = _get_curve_snapshot(180)
    labels_1y,   vals_1y   = _get_curve_snapshot(365)

    spread_10y2y, _  = get_latest_value(ID_SPREAD_10Y2Y)
    spread_10y3m, _  = get_latest_value(ID_SPREAD_10Y3M)

    # Estado de la curva
    inverted = spread_10y2y is not None and spread_10y2y < 0
    curve_status_color = C["negative"] if inverted else C["positive"]
    curve_status_text  = "⚠️ INVERTIDA" if inverted else "✅ NORMAL"

    fig = go.Figure()
    fig.update_layout(**get_base_layout("Curva de Tipos EE.UU.", height=380))

    if vals_now:
        # Relleno bajo la curva — rojo si invertida, verde si normal
        fill_color = _fa(C["negative"], "25") if inverted else _fa(C["positive"], "20")
        fig.add_trace(go.Scatter(
            x=labels_now, y=vals_now,
            mode="lines+markers", name="Actual",
            line={"color": C["primary"], "width": 3},
            fill="tozeroy", fillcolor=fill_color,
            marker={"size": 7},
        ))
    if vals_1m:
        fig.add_trace(go.Scatter(
            x=labels_1m, y=vals_1m, mode="lines+markers", name="Hace 1 mes",
            line={"color": C["warning"], "width": 1.5, "dash": "dot"},
            marker={"size": 5},
        ))
    if vals_6m:
        fig.add_trace(go.Scatter(
            x=labels_6m, y=vals_6m, mode="lines+markers", name="Hace 6 meses",
            line={"color": C["orange"], "width": 1.5, "dash": "dash"},
            marker={"size": 5},
        ))
    if vals_1y:
        fig.add_trace(go.Scatter(
            x=labels_1y, y=vals_1y, mode="lines+markers", name="Hace 1 año",
            line={"color": C["neutral"], "width": 1.5, "dash": "longdash"},
            marker={"size": 5},
        ))

    if not vals_now:
        fig.add_annotation(text="Sin datos de tipos del Tesoro EE.UU.",
                           xref="paper", yref="paper", x=0.5, y=0.5,
                           showarrow=False, font={"color": COLORS["text_muted"], "size": 13})

    status_row = html.Div(
        [
            html.Div(
                [
                    html.Span("Estado: ", style={"color": COLORS["text_muted"], "fontSize": "0.82rem"}),
                    html.Span(curve_status_text, style={
                        "color": curve_status_color, "fontWeight": "700", "fontSize": "1rem",
                    }),
                ],
                style={"display": "inline-block", "marginRight": "24px"},
            ),
            html.Div(
                [
                    html.Span("Spread 10y-2y: ", style={"color": COLORS["text_muted"], "fontSize": "0.82rem"}),
                    html.Span(
                        _safe(spread_10y2y, "+.2f", "%") if spread_10y2y is not None else "—",
                        style={"color": curve_status_color, "fontWeight": "700", "fontFamily": "monospace"},
                    ),
                ],
                style={"display": "inline-block", "marginRight": "24px"},
            ),
            html.Div(
                [
                    html.Span("Spread 10y-3m: ", style={"color": COLORS["text_muted"], "fontSize": "0.82rem"}),
                    html.Span(
                        _safe(spread_10y3m, "+.2f", "%") if spread_10y3m is not None else "—",
                        style={"color": C["negative"] if spread_10y3m is not None and spread_10y3m < 0 else C["positive"],
                               "fontWeight": "700", "fontFamily": "monospace"},
                    ),
                ],
                style={"display": "inline-block"},
            ),
        ],
        style={"marginBottom": "10px"},
    )

    return html.Div(
        [
            html.Div("CURVA DE TIPOS EE.UU.", style={
                "fontSize": "0.65rem", "letterSpacing": "0.1em",
                "color": COLORS["text_label"], "fontWeight": "600", "marginBottom": "8px",
            }),
            status_row,
            dcc.Graph(figure=fig, config={"displayModeBar": False}),
        ],
        style={"marginBottom": "24px"},
    )


def _build_spread_history() -> html.Div:
    """Sección 2.2 — Histórico del spread 10y-2y."""
    df = get_series(ID_SPREAD_10Y2Y, days=365 * 25)

    fig = go.Figure()
    fig.update_layout(**get_base_layout("Spread 10y-2y (histórico desde 2000)", height=320))

    if not df.empty:
        # Separar zonas positivas y negativas
        pos = df["value"].clip(lower=0)
        neg = df["value"].clip(upper=0)

        fig.add_trace(go.Scatter(
            x=df["timestamp"], y=pos,
            fill="tozeroy", mode="none", name="Normal (+)",
            fillcolor=_fa(C["positive"], "30"),
        ))
        fig.add_trace(go.Scatter(
            x=df["timestamp"], y=neg,
            fill="tozeroy", mode="none", name="Inversión (-)",
            fillcolor=_fa(C["negative"], "40"),
        ))
        fig.add_trace(go.Scatter(
            x=df["timestamp"], y=df["value"],
            mode="lines", name="Spread 10y-2y",
            line={"color": C["primary"], "width": 1.5},
        ))
        fig.add_hline(y=0, line_color=COLORS["border_mid"], line_width=1.5)

        # Anotar recesiones aproximadas
        recessions = [
            ("2001-03-01", "2001-11-01", "Recesión 2001"),
            ("2007-12-01", "2009-06-01", "GFC 2008-09"),
            ("2020-02-01", "2020-04-01", "COVID"),
        ]
        for start, end, label in recessions:
            try:
                fig.add_vrect(
                    x0=start, x1=end,
                    fillcolor=COLORS["border_mid"], opacity=0.25,
                    layer="below", line_width=0,
                    annotation_text=label, annotation_position="top left",
                    annotation_font_size=9, annotation_font_color=COLORS["text_muted"],
                )
            except Exception:
                pass
    else:
        fig.add_annotation(text="Sin datos del spread 10y-2y",
                           xref="paper", yref="paper", x=0.5, y=0.5,
                           showarrow=False, font={"color": COLORS["text_muted"]})

    note = html.Div(
        "📖 Históricamente, una inversión sostenida ha precedido cada recesión americana "
        "en los últimos 50 años con 6-18 meses de adelanto.",
        style={"fontSize": "0.72rem", "color": COLORS["text_muted"], "marginTop": "6px",
               "borderLeft": f"3px solid {C['primary']}", "paddingLeft": "8px"},
    )

    return html.Div(
        [
            html.Div("HISTÓRICO SPREAD 10y-2y", style={
                "fontSize": "0.65rem", "letterSpacing": "0.1em",
                "color": COLORS["text_label"], "fontWeight": "600", "marginBottom": "8px",
            }),
            dcc.Graph(figure=fig, config={"displayModeBar": False}),
            note,
        ],
        style={"marginBottom": "24px"},
    )


def _build_european_spreads() -> html.Div:
    """Sección 2.4 — Primas de riesgo soberanas europeas."""
    spread_series = [
        ("España",   ID_SPREAD_ES, C["warning"]),
        ("Italia",   ID_SPREAD_IT, C["negative"]),
        ("Francia",  ID_SPREAD_FR, "#8b5cf6"),
        ("Portugal", ID_SPREAD_PT, C["orange"]),
        ("Grecia",   ID_SPREAD_GR, "#ec4899"),
    ]

    fig = go.Figure()
    fig.update_layout(**get_base_layout("Primas de Riesgo vs Bund Alemán (pb)", height=320))

    has_data = False
    for name, sid, color in spread_series:
        df = get_series(sid, days=365 * 14)
        if df.empty:
            continue
        has_data = True
        fig.add_trace(go.Scatter(
            x=df["timestamp"], y=df["value"],
            mode="lines", name=name,
            line={"color": color, "width": 2},
        ))

    if has_data:
        fig.add_hline(y=100, line_dash="dot", line_color=C["warning"], line_width=1,
                      annotation_text="100pb (atención)", annotation_position="right",
                      annotation_font_size=9)
        fig.add_hline(y=200, line_dash="dot", line_color=C["negative"], line_width=1,
                      annotation_text="200pb (estrés)", annotation_position="right",
                      annotation_font_size=9)
    else:
        fig.add_annotation(text="Sin datos de primas de riesgo europeas",
                           xref="paper", yref="paper", x=0.5, y=0.5,
                           showarrow=False, font={"color": COLORS["text_muted"]})

    # Tabla resumen de spreads actuales
    table_rows = []
    for name, sid, color in spread_series:
        cur, _ = get_latest_value(sid)
        _, _, _, pct30 = get_change(sid, period_days=30)
        _, _, _, pct365 = get_change(sid, period_days=365)
        table_rows.append(html.Tr([
            html.Td(name, style={"fontSize": "0.82rem", "color": color}),
            html.Td(f"{cur:.0f} pb" if cur else "—",
                    style={"textAlign": "right", "fontFamily": "monospace", "fontSize": "0.82rem"}),
            html.Td(_pct_str(pct30), style={"textAlign": "right", "color": _pct_color(pct30), "fontSize": "0.78rem"}),
            html.Td(_pct_str(pct365), style={"textAlign": "right", "color": _pct_color(pct365), "fontSize": "0.78rem"}),
        ]))

    table = html.Table(
        [
            html.Thead(html.Tr([
                html.Th(h, style={"fontSize": "0.70rem", "color": COLORS["text_label"],
                                  "paddingBottom": "4px", "textAlign": "right" if i > 0 else "left"})
                for i, h in enumerate(["País", "Prima actual", "Var. 1M", "Var. 1A"])
            ])),
            html.Tbody(table_rows),
        ],
        className="data-table",
        style={"width": "100%", "borderCollapse": "collapse"},
    )

    return html.Div(
        [
            html.Div("PRIMAS DE RIESGO SOBERANAS EUROPEAS", style={
                "fontSize": "0.65rem", "letterSpacing": "0.1em",
                "color": COLORS["text_label"], "fontWeight": "600", "marginBottom": "8px",
            }),
            dcc.Graph(figure=fig, config={"displayModeBar": False}),
            html.Div(table, style={"marginTop": "12px", "overflowX": "auto"}),
        ],
        style={"marginBottom": "24px"},
    )


def _build_tab2_content() -> html.Div:
    return html.Div(
        [
            _build_yield_curve_section(),
            _build_spread_history(),
            _build_european_spreads(),
        ],
        style={"padding": "20px"},
    )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — DIVISAS
# ══════════════════════════════════════════════════════════════════════════════

FOREX_MAJORS = [
    ("EUR/USD", ID_EURUSD, True),
    ("GBP/USD", ID_GBPUSD, True),
    ("USD/JPY", ID_USDJPY, False),
    ("USD/CHF", ID_USDCHF, False),
    ("AUD/USD", ID_AUDUSD, True),
    ("USD/CAD", ID_USDCAD, False),
]

FOREX_EM = [
    ("USD/CNY", ID_USDCNY, False),
    ("USD/BRL", ID_USDBRL, False),
    ("USD/MXN", ID_USDMXN, False),
    ("USD/INR", ID_USDINR, False),
    ("USD/TRY", ID_USDTRY, False),
    ("USD/ARS", ID_USDARS, False),
]


def _build_dxy_panel() -> html.Div:
    """Sección 3.1 — Panel del Dólar (DXY)."""
    df = get_series(ID_DXY, days=365 * 5)
    cur, _ = get_latest_value(ID_DXY)

    fig = go.Figure()
    fig.update_layout(**get_base_layout("DXY — Índice del Dólar", height=300))

    if not df.empty:
        fig.add_trace(go.Scatter(
            x=df["timestamp"], y=df["value"],
            mode="lines", name="DXY",
            line={"color": C["primary"], "width": 2},
            fill="tozeroy", fillcolor=_fa(C["primary"], "15"),
        ))
        for level, label, color in [(90, "90 — Dólar débil", C["positive"]),
                                      (100, "100 — Neutral histórico", C["warning"]),
                                      (110, "110 — Dólar muy fuerte", C["negative"])]:
            fig.add_hline(y=level, line_dash="dot", line_color=color, line_width=1,
                          annotation_text=label, annotation_position="right",
                          annotation_font_size=9, annotation_font_color=color)

    interp = ""
    if cur is not None:
        if cur < 90:
            interp = "💚 Dólar DÉBIL — favorable para materias primas y emergentes"
        elif cur < 100:
            interp = "🟡 Dólar MODERADO — zona neutral histórica"
        elif cur < 110:
            interp = "🟠 Dólar FUERTE — presión sobre materias primas y deuda emergente en USD"
        else:
            interp = "🔴 Dólar MUY FUERTE — riesgo sistémico para mercados emergentes"

    return html.Div(
        [
            html.Div("DXY — ÍNDICE DEL DÓLAR", style={
                "fontSize": "0.65rem", "letterSpacing": "0.1em",
                "color": COLORS["text_label"], "fontWeight": "600", "marginBottom": "8px",
            }),
            dcc.Graph(figure=fig, config={"displayModeBar": False}),
            html.Div(interp, style={
                "fontSize": "0.78rem", "color": COLORS["text_muted"],
                "marginTop": "8px", "padding": "6px 10px",
                "backgroundColor": COLORS["card_bg"], "borderRadius": "4px",
            }),
        ],
        style={"marginBottom": "24px"},
    )


def _forex_table_row(pair: str, sid: str, usd_is_base: bool) -> html.Tr:
    cur, _ = get_latest_value(sid)
    _, _, _, pct1d  = get_change(sid, period_days=1)
    _, _, _, pct7d  = get_change(sid, period_days=7)
    _, _, _, pct30d = get_change(sid, period_days=30)
    _, _, _, pct365 = get_change(sid, period_days=365)

    # Señal de alerta para divisas EM que han caído > 15% en el año
    is_em = not usd_is_base  # simplificación: si USD es base, suele ser EM
    alert_style = {}
    if is_em and pct365 is not None and pct365 > 15:  # USD/EM subió > 15% = divisa cayó > 15%
        alert_style = {"backgroundColor": _fa(C["negative"], "15")}

    def pcell(v):
        if v is None:
            return html.Td("—", style={"textAlign": "right", "color": COLORS["text_label"]})
        c = C["positive"] if v <= 0 else C["negative"]  # para USD/XX: subida = EM débil
        if usd_is_base:  # para EUR/USD, GBP/USD: subida = bueno para USD
            c = C["positive"] if v >= 0 else C["negative"]
        sign = "+" if v >= 0 else ""
        return html.Td(
            f"{sign}{v:.2f}%",
            style={"textAlign": "right", "color": c, "fontSize": "0.80rem"},
        )

    return html.Tr(
        [
            html.Td(pair, style={"fontWeight": "600", "fontSize": "0.82rem"}),
            html.Td(
                f"{cur:.4f}" if cur else "—",
                style={"textAlign": "right", "fontFamily": "monospace", "fontSize": "0.82rem"},
            ),
            pcell(pct1d), pcell(pct7d), pcell(pct30d), pcell(pct365),
        ],
        style=alert_style,
    )


def _build_forex_table() -> html.Div:
    """Sección 3.2 — Tabla de pares de divisas."""
    headers = ["Par", "Precio", "1D", "1W", "1M", "1A"]
    th_style = {"fontSize": "0.72rem", "color": COLORS["text_label"], "fontWeight": "600",
                "textAlign": "right", "borderBottom": f"2px solid {COLORS['border']}",
                "paddingBottom": "6px"}

    thead = html.Thead(html.Tr([
        html.Th(h, style={**th_style, "textAlign": "left" if i == 0 else "right"})
        for i, h in enumerate(headers)
    ]))

    major_rows = [_forex_table_row(p, s, usd) for p, s, usd in FOREX_MAJORS]
    em_rows    = [_forex_table_row(p, s, usd) for p, s, usd in FOREX_EM]

    section_sep = html.Tr([
        html.Td(
            "EMERGENTES", colSpan=6,
            style={"fontSize": "0.65rem", "color": COLORS["text_label"],
                   "fontWeight": "600", "letterSpacing": "0.1em",
                   "paddingTop": "10px", "paddingBottom": "4px",
                   "borderTop": f"1px solid {COLORS['border']}"},
        )
    ])

    return html.Div(
        [
            html.Div("DIVISAS", style={
                "fontSize": "0.65rem", "letterSpacing": "0.1em",
                "color": COLORS["text_label"], "fontWeight": "600", "marginBottom": "10px",
            }),
            html.Div(
                html.Table(
                    [thead, html.Tbody(major_rows + [section_sep] + em_rows)],
                    style={"width": "100%", "borderCollapse": "collapse"},
                    className="data-table",
                ),
                style={"overflowX": "auto"},
            ),
        ],
        style={"marginBottom": "24px"},
    )


def _build_forex_heatmap() -> html.Div:
    """Sección 3.3 — Mapa de calor de variaciones."""
    all_pairs = FOREX_MAJORS + FOREX_EM
    periods = [("1D", 1), ("1W", 7), ("1M", 30), ("3M", 90), ("1A", 365)]

    z_vals, y_labels, x_labels = [], [], [p[0] for p in periods]
    text_vals = []

    for pair, sid, usd_is_base in all_pairs:
        row, text_row = [], []
        for _, days in periods:
            _, _, _, pct = get_change(sid, period_days=days)
            if pct is not None:
                # Normalizar: para USD/EM, subida es debilidad de la EM
                v = pct if usd_is_base else -pct
                row.append(v)
                sign = "+" if pct >= 0 else ""
                text_row.append(f"{sign}{pct:.1f}%")
            else:
                row.append(None)
                text_row.append("—")
        z_vals.append(row)
        text_vals.append(text_row)
        y_labels.append(pair)

    import numpy as np
    z_array = []
    for row in z_vals:
        z_array.append([v if v is not None else 0 for v in row])

    fig = go.Figure(go.Heatmap(
        z=z_array, x=x_labels, y=y_labels,
        text=text_vals, texttemplate="%{text}",
        textfont={"size": 11},
        colorscale=[
            [0.0, "#991b1b"], [0.35, "#ef4444"],
            [0.5, "#1f2937"],
            [0.65, "#10b981"], [1.0, "#065f46"],
        ],
        zmid=0, showscale=True,
        colorbar={"thickness": 12, "tickfont": {"size": 9, "color": "#9ca3af"}},
    ))
    fig.update_layout(**get_base_layout("Mapa de Calor — Variaciones de Divisas", height=360))
    fig.update_layout(margin={"l": 80, "r": 60, "t": 40, "b": 20})

    return html.Div(
        [
            html.Div("MAPA DE CALOR DE DIVISAS", style={
                "fontSize": "0.65rem", "letterSpacing": "0.1em",
                "color": COLORS["text_label"], "fontWeight": "600", "marginBottom": "8px",
            }),
            dcc.Graph(figure=fig, config={"displayModeBar": False}),
            html.Div(
                "Verde = fortaleza relativa de la divisa no-USD · Rojo = debilidad",
                style={"fontSize": "0.68rem", "color": COLORS["text_label"], "marginTop": "4px"},
            ),
        ],
        style={"marginBottom": "24px"},
    )


def _build_eurusd_chart() -> html.Div:
    """Sección 3.4 — EUR/USD histórico con contexto."""
    df = get_series(ID_EURUSD, days=365 * 10)

    fig = go.Figure()
    fig.update_layout(**get_base_layout("EUR/USD — Histórico desde 2015", height=320))

    if not df.empty:
        fig.add_trace(go.Scatter(
            x=df["timestamp"], y=df["value"],
            mode="lines", name="EUR/USD",
            line={"color": C["primary"], "width": 2},
        ))
        for level, label, color in [(1.00, "1.00 — Paridad", C["negative"]),
                                      (1.10, "1.10 — Zona neutral", C["warning"]),
                                      (1.20, "1.20 — Euro fuerte", C["positive"])]:
            fig.add_hline(y=level, line_dash="dot", line_color=color, line_width=1,
                          annotation_text=label, annotation_position="right",
                          annotation_font_size=9, annotation_font_color=color)
    else:
        fig.add_annotation(text="Sin datos EUR/USD",
                           xref="paper", yref="paper", x=0.5, y=0.5,
                           showarrow=False, font={"color": COLORS["text_muted"]})

    return html.Div(
        [
            html.Div("EUR/USD CON CONTEXTO", style={
                "fontSize": "0.65rem", "letterSpacing": "0.1em",
                "color": COLORS["text_label"], "fontWeight": "600", "marginBottom": "8px",
            }),
            dcc.Graph(figure=fig, config={"displayModeBar": False}),
        ],
    )


def _build_tab3_content() -> html.Div:
    return html.Div(
        [
            _build_dxy_panel(),
            dbc.Row([
                dbc.Col(_build_forex_table(), md=6),
                dbc.Col(_build_forex_heatmap(), md=6),
            ], className="g-3"),
            _build_eurusd_chart(),
        ],
        style={"padding": "20px"},
    )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — MATERIAS PRIMAS
# ══════════════════════════════════════════════════════════════════════════════

def _build_energy_section() -> html.Div:
    """Sección 4.1 — Panel de Energía."""
    brent_df = get_series(ID_BRENT, days=365 * 5)
    wti_df   = get_series(ID_WTI,   days=365 * 5)
    gas_df   = get_series(ID_GAS_HH, days=365 * 3)

    # Gráfico Brent + WTI
    energy_fig = go.Figure()
    energy_fig.update_layout(**get_base_layout("Petróleo — Brent y WTI", height=300))

    if not brent_df.empty:
        energy_fig.add_trace(go.Scatter(
            x=brent_df["timestamp"], y=brent_df["value"],
            mode="lines", name="Brent",
            line={"color": C["negative"], "width": 2},
        ))
    if not wti_df.empty:
        energy_fig.add_trace(go.Scatter(
            x=wti_df["timestamp"], y=wti_df["value"],
            mode="lines", name="WTI",
            line={"color": C["warning"], "width": 2},
        ))
    if not brent_df.empty and not wti_df.empty:
        # Spread Brent-WTI en eje secundario
        merged_e = brent_df.set_index("timestamp").join(
            wti_df.set_index("timestamp"), how="inner", lsuffix="_brent", rsuffix="_wti"
        )
        if not merged_e.empty:
            spread = merged_e["value_brent"] - merged_e["value_wti"]
            energy_fig.add_trace(go.Scatter(
                x=merged_e.index, y=spread,
                mode="lines", name="Spread B-W",
                line={"color": C["primary"], "width": 1.5, "dash": "dot"},
                yaxis="y2",
            ))
            energy_fig.update_layout(
                yaxis2={"overlaying": "y", "side": "right", "title": {"text": "Spread ($)", "font": {"size": 10}},
                        "gridcolor": "rgba(0,0,0,0)", "tickfont": {"color": C["primary"], "size": 10}}
            )

    # Gráfico gas
    gas_fig = go.Figure()
    gas_fig.update_layout(**get_base_layout("Gas Natural Henry Hub", height=300))
    if not gas_df.empty:
        gas_fig.add_trace(go.Scatter(
            x=gas_df["timestamp"], y=gas_df["value"],
            mode="lines", name="Gas HH",
            line={"color": "#06b6d4", "width": 2},
            fill="tozeroy", fillcolor="rgba(6,182,212,0.12)",
        ))

    # Tabla rápida de energía
    energy_items = [
        ("Brent", ID_BRENT, "$", ".2f"),
        ("WTI", ID_WTI, "$", ".2f"),
        ("Gas HH", ID_GAS_HH, "$", ".3f"),
    ]
    energy_table_rows = []
    for lbl, sid, pfx, fmt in energy_items:
        cur, _ = get_latest_value(sid)
        _, _, _, p1d = get_change(sid, period_days=1)
        _, _, _, p7d = get_change(sid, period_days=7)
        ytd = _get_ytd_change(sid)
        energy_table_rows.append(html.Tr([
            html.Td(lbl, style={"fontSize": "0.82rem"}),
            html.Td(f"{pfx}{_safe(cur, fmt)}" if cur else "—",
                    style={"textAlign": "right", "fontFamily": "monospace"}),
            html.Td(_pct_str(p1d), style={"textAlign": "right", "color": _pct_color(p1d)}),
            html.Td(_pct_str(p7d), style={"textAlign": "right", "color": _pct_color(p7d)}),
            html.Td(_pct_str(ytd), style={"textAlign": "right", "color": _pct_color(ytd)}),
        ]))

    energy_table = html.Table(
        [
            html.Thead(html.Tr([
                html.Th(h, style={"fontSize": "0.70rem", "color": COLORS["text_label"],
                                  "textAlign": "right" if i > 0 else "left"})
                for i, h in enumerate(["", "Precio", "1D", "1W", "YTD"])
            ])),
            html.Tbody(energy_table_rows),
        ],
        className="data-table",
        style={"width": "100%", "borderCollapse": "collapse"},
    )

    return html.Div(
        [
            html.Div("ENERGÍA", style={
                "fontSize": "0.65rem", "letterSpacing": "0.1em",
                "color": COLORS["text_label"], "fontWeight": "600", "marginBottom": "8px",
            }),
            dbc.Row([
                dbc.Col(dcc.Graph(figure=energy_fig, config={"displayModeBar": False}), md=6),
                dbc.Col(dcc.Graph(figure=gas_fig, config={"displayModeBar": False}), md=6),
            ], className="g-2"),
            html.Div(energy_table, style={"marginTop": "12px", "overflowX": "auto"}),
        ],
        style={"marginBottom": "24px"},
    )


def _build_precious_metals() -> html.Div:
    """Sección 4.2 — Metales preciosos."""
    gold_df  = get_series(ID_GOLD,       days=365 * 5)
    real_df  = get_series(ID_REAL_YIELD, days=365 * 5)
    ratio_df = get_series("yf_gc_si_ratio", days=365 * 3)

    gold_fig = go.Figure()
    gold_fig.update_layout(**get_base_layout("Oro — Precio y Tipos Reales 10Y", height=300))

    if not gold_df.empty:
        gold_fig.add_trace(go.Scatter(
            x=gold_df["timestamp"], y=gold_df["value"],
            mode="lines", name="Oro (USD/oz)",
            line={"color": C["gold"], "width": 2.5},
        ))
    if not real_df.empty:
        gold_fig.add_trace(go.Scatter(
            x=real_df["timestamp"], y=real_df["value"],
            mode="lines", name="Tipo Real 10Y (eje inv.)",
            line={"color": C["primary"], "width": 1.5, "dash": "dot"},
            yaxis="y2",
        ))
        gold_fig.update_layout(
            yaxis2={
                "overlaying": "y", "side": "right", "autorange": "reversed",
                "title": {"text": "Tipo Real % (invertido)", "font": {"size": 10}},
                "gridcolor": "rgba(0,0,0,0)",
                "tickfont": {"color": C["primary"], "size": 10},
            }
        )

    # Tabla metales preciosos
    metals = [
        ("Oro",      ID_GOLD,     "$", ",.0f"),
        ("Plata",    ID_SILVER,   "$", ".2f"),
        ("Platino",  ID_PLATINUM, "$", ",.0f"),
        ("Paladio",  ID_PALLADIUM,"$", ",.0f"),
    ]
    rows = []
    for lbl, sid, pfx, fmt in metals:
        cur, _ = get_latest_value(sid)
        _, _, _, p1d = get_change(sid, period_days=1)
        ytd = _get_ytd_change(sid)
        ath = _dist_to_ath(sid)
        rows.append(html.Tr([
            html.Td(lbl, style={"fontSize": "0.82rem"}),
            html.Td(f"{pfx}{_safe(cur, fmt)}" if cur else "—",
                    style={"textAlign": "right", "fontFamily": "monospace"}),
            html.Td(_pct_str(p1d), style={"textAlign": "right", "color": _pct_color(p1d)}),
            html.Td(_pct_str(ytd), style={"textAlign": "right", "color": _pct_color(ytd)}),
            html.Td(f"{ath:.1f}%" if ath is not None else "—",
                    style={"textAlign": "right", "color": C["negative"] if ath and ath < -20 else COLORS["text_muted"]}),
        ]))

    table = html.Table(
        [
            html.Thead(html.Tr([
                html.Th(h, style={"fontSize": "0.70rem", "color": COLORS["text_label"],
                                  "textAlign": "right" if i > 0 else "left"})
                for i, h in enumerate(["Metal", "Precio", "1D", "YTD", "Dist. ATH"])
            ])),
            html.Tbody(rows),
        ],
        className="data-table",
        style={"width": "100%", "borderCollapse": "collapse"},
    )

    return html.Div(
        [
            html.Div("METALES PRECIOSOS", style={
                "fontSize": "0.65rem", "letterSpacing": "0.1em",
                "color": COLORS["text_label"], "fontWeight": "600", "marginBottom": "8px",
            }),
            dcc.Graph(figure=gold_fig, config={"displayModeBar": False}),
            html.Div(table, style={"marginTop": "12px", "overflowX": "auto"}),
        ],
        style={"marginBottom": "24px"},
    )


def _build_industrial_metals() -> html.Div:
    """Sección 4.3 — Metales industriales (Doctor Copper)."""
    copper_df = get_series(ID_COPPER, days=365 * 8)

    fig = go.Figure()
    fig.update_layout(**get_base_layout("Cobre — 'Doctor Copper'", height=280))

    if not copper_df.empty:
        fig.add_trace(go.Scatter(
            x=copper_df["timestamp"], y=copper_df["value"],
            mode="lines", name="Cobre (USD/lb)",
            line={"color": C["orange"], "width": 2},
            fill="tozeroy", fillcolor=_fa(C["orange"], "15"),
        ))

    metals = [
        ("Cobre",    ID_COPPER,   "$", ".4f", "/lb"),
        ("Aluminio", ID_ALUMINUM, "$", ".4f", "/lb"),
        ("Zinc",     ID_ZINC,     "$", ".4f", "/lb"),
    ]
    rows = []
    for lbl, sid, pfx, fmt, unit in metals:
        cur, _ = get_latest_value(sid)
        _, _, _, p1d = get_change(sid, period_days=1)
        ytd = _get_ytd_change(sid)
        rows.append(html.Tr([
            html.Td(lbl, style={"fontSize": "0.82rem"}),
            html.Td(f"{pfx}{_safe(cur, fmt)}{unit}" if cur else "—",
                    style={"textAlign": "right", "fontFamily": "monospace"}),
            html.Td(_pct_str(p1d), style={"textAlign": "right", "color": _pct_color(p1d)}),
            html.Td(_pct_str(ytd), style={"textAlign": "right", "color": _pct_color(ytd)}),
        ]))

    table = html.Table(
        [
            html.Thead(html.Tr([
                html.Th(h, style={"fontSize": "0.70rem", "color": COLORS["text_label"],
                                  "textAlign": "right" if i > 0 else "left"})
                for i, h in enumerate(["Metal", "Precio", "1D", "YTD"])
            ])),
            html.Tbody(rows),
        ],
        className="data-table",
        style={"width": "100%", "borderCollapse": "collapse"},
    )

    copper_cur, _ = get_latest_value(ID_COPPER)
    _, _, _, copper_ytd = get_change(ID_COPPER, period_days=365)
    interp = ""
    if copper_cur is not None and copper_ytd is not None:
        if copper_ytd >= 5:
            interp = "📈 El cobre está por encima de su tendencia — el mercado anticipa aceleración económica global"
        elif copper_ytd <= -5:
            interp = "📉 El cobre está por debajo de su tendencia — señal de desaceleración económica anticipada"
        else:
            interp = "➡️ El cobre en rango neutro — sin señal clara sobre el ciclo económico"

    return html.Div(
        [
            html.Div("METALES INDUSTRIALES — DOCTOR COPPER", style={
                "fontSize": "0.65rem", "letterSpacing": "0.1em",
                "color": COLORS["text_label"], "fontWeight": "600", "marginBottom": "8px",
            }),
            dcc.Graph(figure=fig, config={"displayModeBar": False}),
            html.Div(interp, style={
                "fontSize": "0.75rem", "color": COLORS["text_muted"],
                "marginTop": "6px", "marginBottom": "10px",
            }),
            html.Div(table, style={"overflowX": "auto"}),
        ],
        style={"marginBottom": "24px"},
    )


def _build_agricultural() -> html.Div:
    """Sección 4.4 — Agrícolas."""
    agri = [
        ("Trigo",  ID_WHEAT,  "$", ".2f", "¢/bu"),
        ("Maíz",   ID_CORN,   "$", ".2f", "¢/bu"),
        ("Soja",   ID_SOY,    "$", ".2f", "¢/bu"),
        ("Arroz",  ID_RICE,   "$", ".2f", "$/cwt"),
        ("Azúcar", ID_SUGAR,  "$", ".2f", "¢/lb"),
        ("Café",   ID_COFFEE, "$", ".2f", "¢/lb"),
        ("Cacao",  ID_COCOA,  "$", ".0f", "$/t"),
    ]
    rows = []
    for lbl, sid, pfx, fmt, unit in agri:
        cur, _ = get_latest_value(sid)
        _, _, _, p1d = get_change(sid, period_days=1)
        ytd = _get_ytd_change(sid)
        rows.append(html.Tr([
            html.Td(lbl, style={"fontSize": "0.82rem"}),
            html.Td(f"{_safe(cur, fmt)} {unit}" if cur else "—",
                    style={"textAlign": "right", "fontFamily": "monospace", "fontSize": "0.80rem"}),
            html.Td(_pct_str(p1d), style={"textAlign": "right", "color": _pct_color(p1d)}),
            html.Td(_pct_str(ytd), style={"textAlign": "right", "color": _pct_color(ytd)}),
        ]))

    table = html.Table(
        [
            html.Thead(html.Tr([
                html.Th(h, style={"fontSize": "0.70rem", "color": COLORS["text_label"],
                                  "textAlign": "right" if i > 0 else "left"})
                for i, h in enumerate(["Producto", "Precio", "1D", "YTD"])
            ])),
            html.Tbody(rows),
        ],
        className="data-table",
        style={"width": "100%", "borderCollapse": "collapse"},
    )

    return html.Div(
        [
            html.Div("MATERIAS PRIMAS AGRÍCOLAS", style={
                "fontSize": "0.65rem", "letterSpacing": "0.1em",
                "color": COLORS["text_label"], "fontWeight": "600", "marginBottom": "8px",
            }),
            html.Div(table, style={"overflowX": "auto"}),
        ],
    )


def _build_tab4_content() -> html.Div:
    return html.Div(
        [
            _build_energy_section(),
            dbc.Row([
                dbc.Col(_build_precious_metals(), md=6),
                dbc.Col([
                    _build_industrial_metals(),
                    _build_agricultural(),
                ], md=6),
            ], className="g-3"),
        ],
        style={"padding": "20px"},
    )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — VOLATILIDAD Y SENTIMIENTO
# ══════════════════════════════════════════════════════════════════════════════

def _build_vix_detail() -> html.Div:
    """Sección 5.1 — VIX en detalle."""
    df = get_series(ID_VIX, days=365 * 5)
    cur, _ = get_latest_value(ID_VIX)

    fig = go.Figure()
    fig.update_layout(**get_base_layout("VIX — Índice del Miedo (5 años)", height=320))

    if not df.empty:
        # Zonas de color
        for y0, y1, color, label in [
            (0,  15, C["positive"],  "Calma"),
            (15, 25, C["primary"],   "Normal"),
            (25, 35, C["warning"],   "Tensión"),
            (35, 80, C["negative"],  "Pánico"),
        ]:
            fig.add_hrect(
                y0=y0, y1=y1,
                fillcolor=_fa(color, "12"),
                line_width=0, layer="below",
            )

        fig.add_trace(go.Scatter(
            x=df["timestamp"], y=df["value"],
            mode="lines", name="VIX",
            line={"color": C["primary"], "width": 2},
            fill="tozeroy", fillcolor=_fa(C["primary"], "18"),
        ))
        fig.add_hline(y=15, line_dash="dot", line_color=C["positive"], line_width=1,
                      annotation_text="15 — Calma", annotation_position="right",
                      annotation_font_size=9)
        fig.add_hline(y=25, line_dash="dot", line_color=C["warning"], line_width=1,
                      annotation_text="25 — Alerta", annotation_position="right",
                      annotation_font_size=9)
        fig.add_hline(y=35, line_dash="dot", line_color=C["negative"], line_width=1,
                      annotation_text="35 — Pánico", annotation_position="right",
                      annotation_font_size=9)

    vix_interp = ""
    if cur is not None:
        if cur < 15:
            vix_interp = f"✅ VIX {cur:.1f} — COMPLACENCIA del mercado"
        elif cur < 25:
            vix_interp = f"🟡 VIX {cur:.1f} — VOLATILIDAD NORMAL"
        elif cur < 35:
            vix_interp = f"🟠 VIX {cur:.1f} — TENSIÓN en los mercados"
        else:
            vix_interp = f"🔴 VIX {cur:.1f} — PÁNICO — Oportunidad contrarian potencial"

    return html.Div(
        [
            html.Div("VIX — ÍNDICE DE VOLATILIDAD IMPLÍCITA", style={
                "fontSize": "0.65rem", "letterSpacing": "0.1em",
                "color": COLORS["text_label"], "fontWeight": "600", "marginBottom": "8px",
            }),
            dcc.Graph(figure=fig, config={"displayModeBar": False}),
            html.Div(vix_interp, style={
                "fontSize": "0.82rem", "color": COLORS["text_muted"], "marginTop": "6px",
            }),
        ],
        style={"marginBottom": "24px"},
    )


def _build_fear_greed_gauge(value: Optional[float], title: str, gauge_id: str) -> html.Div:
    """Gauge circular Fear & Greed."""
    v = value if value is not None else 50

    if v <= 25:
        zone, color = "Miedo Extremo", C["negative"]
    elif v <= 45:
        zone, color = "Miedo",         C["orange"]
    elif v <= 55:
        zone, color = "Neutral",       C["warning"]
    elif v <= 75:
        zone, color = "Codicia",       "#84cc16"
    else:
        zone, color = "Codicia Extrema", C["positive"]

    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=v,
        title={"text": f"<b>{zone}</b>", "font": {"size": 14, "color": color}},
        number={"font": {"size": 32, "color": COLORS["text"]}},
        gauge={
            "axis": {"range": [0, 100], "tickfont": {"size": 9, "color": COLORS["text_muted"]},
                     "tickcolor": COLORS["border"]},
            "bar": {"color": color, "thickness": 0.25},
            "bgcolor": COLORS["card_bg"],
            "bordercolor": COLORS["border"],
            "steps": [
                {"range": [0,   25], "color": _fa(C["negative"], "25")},
                {"range": [25,  45], "color": _fa(C["orange"], "25")},
                {"range": [45,  55], "color": _fa(C["warning"], "25")},
                {"range": [55,  75], "color": _fa("#84cc16", "25")},
                {"range": [75, 100], "color": _fa(C["positive"], "25")},
            ],
            "threshold": {
                "line": {"color": color, "width": 3},
                "thickness": 0.75,
                "value": v,
            },
        },
    ))
    fig.update_layout(
        paper_bgcolor=COLORS["card_bg"],
        plot_bgcolor=COLORS["card_bg"],
        font={"color": COLORS["text"], "family": "'Inter', system-ui, sans-serif"},
        height=220,
        margin={"l": 20, "r": 20, "t": 40, "b": 10},
    )

    return html.Div(
        [
            html.Div(title, style={
                "fontSize": "0.65rem", "letterSpacing": "0.1em",
                "color": COLORS["text_label"], "fontWeight": "600", "marginBottom": "4px",
            }),
            dcc.Graph(id=gauge_id, figure=fig, config={"displayModeBar": False}),
        ],
    )


def _build_sentiment_section() -> html.Div:
    """Sección 5.3 — Fear & Greed."""
    vix_val, _ = get_latest_value(ID_VIX)

    # Calcular F&G aproximado: 100 - (VIX - 10) * 3, limitado a 0-100
    fg_approx = None
    if vix_val is not None:
        fg_approx = max(0, min(100, 100 - (vix_val - 10) * 3))

    # F&G Crypto
    fg_crypto, _ = get_latest_value(ID_FEAR_GREED)

    fg_hist = get_series(ID_FEAR_GREED, days=365)

    fig_hist = go.Figure()
    fig_hist.update_layout(**get_base_layout("Fear & Greed Crypto — 12 meses", height=220))
    if not fg_hist.empty:
        colors_map = fg_hist["value"].apply(
            lambda v: C["negative"] if v <= 25 else C["orange"] if v <= 45
            else C["warning"] if v <= 55 else "#84cc16" if v <= 75 else C["positive"]
        )
        fig_hist.add_trace(go.Scatter(
            x=fg_hist["timestamp"], y=fg_hist["value"],
            mode="lines", name="F&G Crypto",
            line={"color": C["primary"], "width": 2},
            fill="tozeroy", fillcolor=_fa(C["warning"], "20"),
        ))
        for y, c in [(25, C["negative"]), (45, C["orange"]), (55, C["warning"]), (75, C["positive"])]:
            fig_hist.add_hline(y=y, line_dash="dot", line_color=c, line_width=0.8)

    return html.Div(
        [
            html.Div("FEAR & GREED Y SENTIMIENTO", style={
                "fontSize": "0.65rem", "letterSpacing": "0.1em",
                "color": COLORS["text_label"], "fontWeight": "600", "marginBottom": "10px",
            }),
            dbc.Row([
                dbc.Col(
                    _build_fear_greed_gauge(fg_approx, "FEAR & GREED — Renta Variable (proxy VIX)", "m05-fg-equity-gauge"),
                    md=4,
                ),
                dbc.Col(
                    _build_fear_greed_gauge(fg_crypto, "FEAR & GREED — Criptomonedas (CoinGecko)", "m05-fg-crypto-gauge"),
                    md=4,
                ),
                dbc.Col(
                    dcc.Graph(figure=fig_hist, config={"displayModeBar": False}),
                    md=4,
                ),
            ], className="g-3"),
        ],
        style={"marginBottom": "24px"},
    )


def _build_tab5_content() -> html.Div:
    return html.Div(
        [
            _build_vix_detail(),
            _build_sentiment_section(),
        ],
        style={"padding": "20px"},
    )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 6 — CRIPTOMONEDAS
# ══════════════════════════════════════════════════════════════════════════════

def _build_btc_panel() -> html.Div:
    """Sección 6.1 — Bitcoin panel principal."""
    btc_df = get_series(ID_BTC, days=365 * 6)
    btc_cur, _ = get_latest_value(ID_BTC)
    _, _, _, btc_ytd = get_change(ID_BTC, period_days=365)
    dist_ath = _dist_to_ath(ID_BTC)
    mcap, _ = get_latest_value(ID_BTC_MCAP)
    dom, _  = get_latest_value(ID_BTC_DOM)

    btc_fig = go.Figure()
    btc_fig.update_layout(**get_base_layout("Bitcoin — Precio histórico (escala log)", height=350))

    if not btc_df.empty:
        btc_fig.add_trace(go.Scatter(
            x=btc_df["timestamp"], y=btc_df["value"],
            mode="lines", name="BTC/USD",
            line={"color": C["bitcoin"], "width": 2},
        ))
        # Halvings: fechas aproximadas
        halvings = [
            ("2012-11-28", "Halving #1"),
            ("2016-07-09", "Halving #2"),
            ("2020-05-11", "Halving #3"),
            ("2024-04-20", "Halving #4"),
        ]
        for hdate, hlabel in halvings:
            try:
                btc_fig.add_vline(
                    x=hdate, line_color=C["warning"], line_dash="dash", line_width=1.5,
                    annotation_text=hlabel, annotation_position="top",
                    annotation_font_size=9, annotation_font_color=C["warning"],
                )
            except Exception:
                pass

    btc_fig.update_layout(yaxis_type="log")

    # Métricas laterales
    metrics = html.Div(
        [
            _kv("Precio USD", f"${format_value(btc_cur, decimals=0)}" if btc_cur else "—"),
            _kv("YTD", _pct_str(btc_ytd), _pct_color(btc_ytd) if btc_ytd else None),
            _kv("Dist. ATH", f"{dist_ath:.1f}%" if dist_ath else "—",
                C["negative"] if dist_ath and dist_ath < -30 else C["warning"]),
            _kv("Market Cap", format_value(mcap, decimals=2) if mcap else "—"),
            _kv("Dominancia", f"{dom:.1f}%" if dom else "—"),
        ],
        style={
            "backgroundColor": COLORS["card_bg"],
            "border": f"1px solid {COLORS['border']}",
            "borderRadius": "6px",
            "padding": "12px",
            "height": "100%",
        },
    )

    return html.Div(
        [
            html.Div("BITCOIN", style={
                "fontSize": "0.65rem", "letterSpacing": "0.1em",
                "color": COLORS["text_label"], "fontWeight": "600", "marginBottom": "8px",
            }),
            dbc.Row([
                dbc.Col(dcc.Graph(figure=btc_fig, config={"displayModeBar": False}), md=9),
                dbc.Col(metrics, md=3),
            ], className="g-2"),
        ],
        style={"marginBottom": "24px"},
    )


def _kv(label: str, value: str, value_color: Optional[str] = None) -> html.Div:
    return html.Div(
        [
            html.Div(label, style={"fontSize": "0.68rem", "color": COLORS["text_label"],
                                   "marginBottom": "1px"}),
            html.Div(value, style={
                "fontSize": "0.92rem", "fontWeight": "700",
                "fontFamily": "monospace",
                "color": value_color or COLORS["text"],
            }),
        ],
        style={"marginBottom": "10px"},
    )


def _build_crypto_dominance() -> html.Div:
    """Sección 6.2 — Dominancia y mercado global."""
    btc_dom, _ = get_latest_value(ID_BTC_DOM)
    eth_dom, _ = get_latest_value(ID_ETH_DOM)
    stb_dom, _ = get_latest_value(ID_STABLE_DOM)

    btc_d = btc_dom or 0
    eth_d = eth_dom or 0
    stb_d = stb_dom or 0
    rest_d = max(0, 100 - btc_d - eth_d - stb_d)

    dom_fig = go.Figure()
    dom_fig.update_layout(**get_base_layout("Composición del Market Cap Crypto", height=280))
    dom_fig.add_trace(go.Pie(
        labels=["Bitcoin", "Ethereum", "Stablecoins", "Resto"],
        values=[btc_d, eth_d, stb_d, rest_d],
        marker_colors=[C["bitcoin"], C["primary"], C["positive"], COLORS["border_mid"]],
        hole=0.5,
        textinfo="label+percent",
        textfont={"size": 11},
    ))
    dom_fig.update_layout(
        showlegend=False,
        paper_bgcolor=COLORS["card_bg"],
        plot_bgcolor=COLORS["card_bg"],
        margin={"l": 20, "r": 20, "t": 40, "b": 20},
    )

    interp = ""
    if btc_d > 0:
        if btc_d > 55:
            interp = f"⚠️ Dominancia BTC alta ({btc_d:.1f}%) — mercado defensivo / ciclo bajista altcoins"
        elif btc_d < 40:
            interp = f"🚀 Dominancia BTC baja ({btc_d:.1f}%) — posible 'Altcoin Season'"
        else:
            interp = f"📊 Dominancia BTC neutral ({btc_d:.1f}%) — mercado equilibrado"

    # Histórico de dominancia
    btc_dom_df = get_series(ID_BTC_DOM, days=730)
    hist_fig = go.Figure()
    hist_fig.update_layout(**get_base_layout("Dominancia BTC — 2 años", height=280))
    if not btc_dom_df.empty:
        hist_fig.add_trace(go.Scatter(
            x=btc_dom_df["timestamp"], y=btc_dom_df["value"],
            mode="lines", name="BTC Dominance %",
            line={"color": C["bitcoin"], "width": 2},
            fill="tozeroy", fillcolor=_fa(C["bitcoin"], "18"),
        ))

    return html.Div(
        [
            html.Div("DOMINANCIA Y MERCADO GLOBAL", style={
                "fontSize": "0.65rem", "letterSpacing": "0.1em",
                "color": COLORS["text_label"], "fontWeight": "600", "marginBottom": "8px",
            }),
            dbc.Row([
                dbc.Col([
                    dcc.Graph(figure=dom_fig, config={"displayModeBar": False}),
                    html.Div(interp, style={
                        "fontSize": "0.78rem", "color": COLORS["text_muted"], "marginTop": "6px",
                    }),
                ], md=5),
                dbc.Col(
                    dcc.Graph(figure=hist_fig, config={"displayModeBar": False}),
                    md=7,
                ),
            ], className="g-3"),
        ],
        style={"marginBottom": "24px"},
    )


def _build_btc_correlations() -> html.Div:
    """Sección 6.4 — Correlaciones de Bitcoin."""
    assets = [
        ("S&P 500", ID_SP500),
        ("Oro",     ID_GOLD),
        ("DXY",     ID_DXY),
        ("Nasdaq",  ID_NDX100),
        ("Brent",   ID_BRENT),
    ]
    periods = [("30 días", 30), ("90 días", 90), ("365 días", 365)]

    import numpy as np

    corr_data = {}
    for asset_name, asset_id in assets:
        corr_data[asset_name] = {}
        btc_df = get_series(ID_BTC, days=400)
        if btc_df.empty:
            for p_name, _ in periods:
                corr_data[asset_name][p_name] = None
            continue
        for p_name, p_days in periods:
            other_df = get_series(asset_id, days=p_days + 5)
            if other_df.empty:
                corr_data[asset_name][p_name] = None
                continue
            try:
                cutoff = datetime.utcnow() - timedelta(days=p_days)
                b = btc_df[btc_df["timestamp"] >= cutoff].set_index("timestamp")["value"]
                o = other_df.set_index("timestamp")["value"]
                aligned = b.resample("D").last().dropna().align(
                    o.resample("D").last().dropna(), join="inner"
                )
                if len(aligned[0]) < 10:
                    corr_data[asset_name][p_name] = None
                else:
                    corr_data[asset_name][p_name] = float(aligned[0].corr(aligned[1]))
            except Exception:
                corr_data[asset_name][p_name] = None

    # Gráfico de barras agrupadas
    colors_periods = [C["primary"], C["warning"], C["positive"]]
    fig = go.Figure()
    fig.update_layout(**get_base_layout("Correlaciones de Bitcoin", height=280))

    for j, (p_name, _) in enumerate(periods):
        x = [a for a, _ in assets]
        y = [corr_data[a].get(p_name) or 0 for a, _ in assets]
        text = [f"{v:.2f}" if corr_data[a].get(p_name) is not None else "—"
                for a, _ in assets for v in [corr_data[a].get(p_name) or 0]]
        fig.add_trace(go.Bar(
            x=x, y=y, name=p_name,
            marker_color=colors_periods[j],
            text=[f"{v:.2f}" for v in y],
            textposition="outside",
            textfont={"size": 9},
        ))

    fig.add_hline(y=0, line_color=COLORS["border_mid"], line_width=1)
    fig.update_layout(
        barmode="group",
        yaxis={"range": [-1, 1]},
        legend={"orientation": "h", "y": 1.15},
    )

    # Interpretación basada en correlación 30 días con SP500
    sp500_corr30 = corr_data.get("S&P 500", {}).get("30 días")
    gold_corr30  = corr_data.get("Oro", {}).get("30 días")
    dxy_corr30   = corr_data.get("DXY", {}).get("30 días")

    interp = "Sin suficientes datos para interpretación automática."
    if sp500_corr30 is not None and gold_corr30 is not None:
        if sp500_corr30 > 0.6:
            interp = "📈 Bitcoin se comporta como ACTIVO DE RIESGO (alta correlación con S&P 500)"
        elif gold_corr30 > 0.5 and sp500_corr30 < 0.3:
            interp = "🥇 Bitcoin se comporta como ORO DIGITAL (correlación con oro > correlación con acciones)"
        elif abs(sp500_corr30) < 0.2 and abs(gold_corr30) < 0.2:
            interp = "🔵 Bitcoin se comporta de forma INDEPENDIENTE (correlaciones bajas con todos los activos)"
        else:
            interp = f"📊 Comportamiento MIXTO — correlación con S&P: {sp500_corr30:.2f}, con Oro: {gold_corr30:.2f}"

    return html.Div(
        [
            html.Div("CORRELACIONES DE BITCOIN", style={
                "fontSize": "0.65rem", "letterSpacing": "0.1em",
                "color": COLORS["text_label"], "fontWeight": "600", "marginBottom": "8px",
            }),
            dcc.Graph(figure=fig, config={"displayModeBar": False}),
            html.Div(interp, style={
                "fontSize": "0.78rem", "color": COLORS["text_muted"],
                "marginTop": "6px",
                "borderLeft": f"3px solid {C['bitcoin']}", "paddingLeft": "8px",
            }),
        ],
    )


def _build_tab6_content() -> html.Div:
    return html.Div(
        [
            _build_btc_panel(),
            dbc.Row([
                dbc.Col(_build_crypto_dominance(), md=7),
                dbc.Col(_build_btc_correlations(), md=5),
            ], className="g-3"),
        ],
        style={"padding": "20px"},
    )


# ══════════════════════════════════════════════════════════════════════════════
# RENDER PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

TAB_STYLE = {
    "backgroundColor": "transparent",
    "color": COLORS["text_muted"],
    "borderBottom": "none",
    "borderTop": "none",
    "padding": "8px 20px",
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


def render_module_5() -> html.Div:
    """
    Retorna el layout completo del Módulo 5.
    Llamada desde el callback de routing en app.py cuando pathname == /module/5.
    """
    return html.Div(
        [
            # Header fijo del módulo con métricas compactas
            _build_m05_header(),

            # Tabs internas
            dcc.Tabs(
                id="m05-tabs",
                value="tab-equity",
                children=[
                    dcc.Tab(
                        label="📈 Renta Variable",
                        value="tab-equity",
                        style=TAB_STYLE,
                        selected_style=TAB_SELECTED_STYLE,
                    ),
                    dcc.Tab(
                        label="💵 Renta Fija",
                        value="tab-fixed-income",
                        style=TAB_STYLE,
                        selected_style=TAB_SELECTED_STYLE,
                    ),
                    dcc.Tab(
                        label="💱 Divisas",
                        value="tab-forex",
                        style=TAB_STYLE,
                        selected_style=TAB_SELECTED_STYLE,
                    ),
                    dcc.Tab(
                        label="🛢️ Mat. Primas",
                        value="tab-commodities",
                        style=TAB_STYLE,
                        selected_style=TAB_SELECTED_STYLE,
                    ),
                    dcc.Tab(
                        label="😨 Volatilidad",
                        value="tab-volatility",
                        style=TAB_STYLE,
                        selected_style=TAB_SELECTED_STYLE,
                    ),
                    dcc.Tab(
                        label="₿ Criptomonedas",
                        value="tab-crypto",
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

            # Área de contenido de la tab activa
            html.Div(id="m05-tab-content"),

            # Store: preserva tab activa entre navegaciones
            dcc.Store(id="m05-active-tab-store", storage_type="session", data="tab-equity"),
        ],
        id="m05-root",
        style={"minHeight": "100vh", "backgroundColor": COLORS["background"]},
    )


# ══════════════════════════════════════════════════════════════════════════════
# REGISTRO DE CALLBACKS
# ══════════════════════════════════════════════════════════════════════════════

def register_callbacks_module_5(app) -> None:
    """Registra todos los callbacks del Módulo 5."""

    # ── 1. Tab routing ────────────────────────────────────────────────────────
    @app.callback(
        Output("m05-tab-content",       "children"),
        Output("m05-active-tab-store",  "data"),
        Input("m05-tabs",               "value"),
        Input("m05-refresh-interval",   "n_intervals"),
    )
    def render_tab(tab_value, _n):
        try:
            if tab_value == "tab-equity":
                return _build_tab1_content(), tab_value
            elif tab_value == "tab-fixed-income":
                return _build_tab2_content(), tab_value
            elif tab_value == "tab-forex":
                return _build_tab3_content(), tab_value
            elif tab_value == "tab-commodities":
                return _build_tab4_content(), tab_value
            elif tab_value == "tab-volatility":
                return _build_tab5_content(), tab_value
            elif tab_value == "tab-crypto":
                return _build_tab6_content(), tab_value
            return _build_tab1_content(), "tab-equity"
        except Exception as e:
            logger.error("m05 tab render error: %s", e)
            return html.Div(
                f"Error renderizando tab: {e}",
                style={"color": COLORS["text_muted"], "padding": "24px"},
            ), tab_value

    # ── 2. Restaurar tab activa al navegar de vuelta al módulo ────────────────
    @app.callback(
        Output("m05-tabs", "value"),
        Input("m05-active-tab-store", "data"),
        prevent_initial_call=True,
    )
    def restore_tab(stored_tab):
        return stored_tab or "tab-equity"

    # ── 3. Gráfico comparativo de índices ─────────────────────────────────────
    @app.callback(
        Output("m05-compare-chart",       "figure"),
        Output("m05-compare-range-store", "data"),
        Input("m05-compare-checklist",    "value"),
        Input("m05-compare-range-1M",     "n_clicks"),
        Input("m05-compare-range-3M",     "n_clicks"),
        Input("m05-compare-range-6M",     "n_clicks"),
        Input("m05-compare-range-1A",     "n_clicks"),
        Input("m05-compare-range-5A",     "n_clicks"),
        Input("m05-compare-range-MAX",    "n_clicks"),
        State("m05-compare-range-store",  "data"),
        prevent_initial_call=False,
    )
    def update_compare_chart(selected, n1m, n3m, n6m, n1a, n5a, nmax, current_range):
        from dash import ctx as dash_ctx
        triggered = dash_ctx.triggered_id
        range_map = {
            "m05-compare-range-1M": "1M",
            "m05-compare-range-3M": "3M",
            "m05-compare-range-6M": "6M",
            "m05-compare-range-1A": "1A",
            "m05-compare-range-5A": "5A",
            "m05-compare-range-MAX": "MAX",
        }
        new_range = range_map.get(triggered, current_range or "1A")
        fig = _calc_compare_fig(selected or [], new_range)
        return fig, new_range

    # ── 4. Actualizar header metrics (timestamp) ──────────────────────────────
    @app.callback(
        Output("m05-last-updated", "children"),
        Input("m05-refresh-interval", "n_intervals"),
    )
    def refresh_timestamp(_):
        _, ts = get_latest_value(ID_SP500)
        if ts:
            return f"Yahoo Finance · {ts.strftime('%d/%m/%Y %H:%M')}"
        return "Yahoo Finance · Sin datos"
