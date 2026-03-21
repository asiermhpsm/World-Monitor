"""
Modulo 1 — Panel de Estado Global
Pantalla de inicio del dashboard.
Se renderiza cuando la URL es /module/1.

Exporta:
  render_module_1()               -> componente Dash con el layout completo
  register_callbacks_module_1(app) -> registra todos los callbacks interactivos
"""

from __future__ import annotations

import logging
from datetime import datetime, date
from typing import Optional

import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import ALL, Input, Output, State, ctx, dcc, html, no_update

from components.chart_config import COLORS as CHART_COLORS, get_base_layout, get_time_range_buttons
from components.common import (
    create_empty_state,
    create_metric_card,
    create_semaphore,
)
from components.scheduler_status import build_scheduler_panel
from config import COLORS

from modules.data_helpers import (
    format_value,
    get_active_alerts,
    get_change,
    get_db_indicator_count,
    get_db_last_update,
    get_db_source_count,
    get_geopolitical_events,
    get_latest_news,
    get_latest_value,
    get_series,
    time_ago,
)

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTES DE INDICADORES
# ══════════════════════════════════════════════════════════════════════════════

# IDs canonicos de los indicadores (segun los colectores implementados)
ID_VIX          = "yf_vix_close"
ID_SPREAD_10Y2Y = "fred_spread_10y2y_us"
ID_STLFSI       = "fred_stlfsi_us"
ID_GPR          = "fred_gpr_global"
ID_CPI_US       = "fred_cpi_yoy_us"
ID_SPREAD_IT    = "ecb_spread_it_de"
ID_SPREAD_ES    = "ecb_spread_es_de"
ID_FED_FUNDS    = "fred_fed_funds_us"
ID_UNEMP_US     = "fred_unemployment_us"
ID_SP500        = "yf_sp500_close"
ID_IBEX35       = "yf_ibex35_close"
ID_GOLD         = "yf_gc_close"
ID_BRENT        = "yf_bz_close"
ID_DXY          = "yf_dxy_close"
ID_EURUSD       = "yf_eurusd_close"
ID_BTC          = "cg_btc_price_usd"
ID_BTC_YF       = "yf_btc_usd_close"
ID_ECB_RATE     = "ecb_deposit_rate_ea"
ID_EURIBOR_3M   = "ecb_euribor_3m_ea"
ID_HICP_EA      = "estat_hicp_CP00_EA20"
ID_UNEMP_EA     = "estat_unemp_TOTAL_EA20"
ID_USDJPY       = "yf_usdjpy_close"
ID_GBPUSD       = "yf_gbpusd_close"
ID_USDCNY       = "yf_usdcny_close"
ID_EMB          = "yf_emb_close"


# ══════════════════════════════════════════════════════════════════════════════
# CALCULO DE RIESGO SISTEMICO
# ══════════════════════════════════════════════════════════════════════════════

def _score_vix(val: Optional[float]) -> int:
    if val is None:
        return 1  # valor neutro si sin datos
    if val < 15:   return 0
    if val < 25:   return 1
    if val < 35:   return 2
    return 3


def _score_spread(val: Optional[float]) -> int:
    if val is None:
        return 1
    if val > 0.5:  return 0
    if val > 0:    return 1
    if val > -0.5: return 2
    return 3


def _score_stlfsi(val: Optional[float]) -> int:
    if val is None:
        return 1
    if val < 0:  return 0
    if val < 1:  return 1
    if val < 2:  return 2
    return 3


def _score_gpr(val: Optional[float]) -> int:
    if val is None:
        return 1
    if val < 100:  return 0
    if val < 150:  return 1
    if val < 200:  return 2
    return 3


def _score_inflation_us(val: Optional[float]) -> int:
    if val is None:
        return 1
    if val < 2.5:  return 0
    if val < 4:    return 1
    if val < 6:    return 2
    return 3


def _score_italy_spread(val: Optional[float]) -> int:
    if val is None:
        return 1
    if val < 150:  return 0
    if val < 250:  return 1
    if val < 350:  return 2
    return 3


def _score_to_level(score: int) -> str:
    """Convierte puntuacion total (0-18) a nivel de semaforo."""
    if score <= 3:   return "green"
    if score <= 6:   return "yellow_green"
    if score <= 9:   return "yellow"
    if score <= 13:  return "orange"
    return "red"


def _score_to_text(score: int) -> str:
    if score <= 3:   return "RIESGO BAJO"
    if score <= 6:   return "RIESGO MODERADO-BAJO"
    if score <= 9:   return "RIESGO MODERADO"
    if score <= 13:  return "RIESGO ALTO"
    return "RIESGO CRITICO"


def _level_to_color(level: str) -> str:
    mapping = {
        "green":        COLORS["green"],
        "yellow_green": COLORS["green_yellow"],
        "yellow":       COLORS["yellow"],
        "orange":       COLORS["orange"],
        "red":          COLORS["red"],
        "gray":         COLORS["text_label"],
    }
    return mapping.get(level, COLORS["text_label"])


def _calculate_global_risk() -> dict:
    """
    Calcula el nivel de riesgo sistemico global.
    Retorna dict con: level, score, max_score, text_level, indicators
    """
    vix_val,    _ = get_latest_value(ID_VIX)
    spread_val, _ = get_latest_value(ID_SPREAD_10Y2Y)
    stlfsi_val, _ = get_latest_value(ID_STLFSI)
    gpr_val,    _ = get_latest_value(ID_GPR)
    cpi_val,    _ = get_latest_value(ID_CPI_US)
    italy_val,  _ = get_latest_value(ID_SPREAD_IT)

    scores = {
        "VIX":              _score_vix(vix_val),
        "Curva 10y-2y":     _score_spread(spread_val),
        "Estres Fed":       _score_stlfsi(stlfsi_val),
        "Riesgo Geop.":     _score_gpr(gpr_val),
        "Inflacion EE.UU.": _score_inflation_us(cpi_val),
        "Prima riesgo IT":  _score_italy_spread(italy_val),
    }
    values = {
        "VIX":              vix_val,
        "Curva 10y-2y":     spread_val,
        "Estres Fed":       stlfsi_val,
        "Riesgo Geop.":     gpr_val,
        "Inflacion EE.UU.": cpi_val,
        "Prima riesgo IT":  italy_val,
    }
    formats = {
        "VIX":              (lambda v: f"{v:.1f}" if v is not None else "\u2014"),
        "Curva 10y-2y":     (lambda v: f"{v:+.2f}%" if v is not None else "\u2014"),
        "Estres Fed":       (lambda v: f"{v:.2f}" if v is not None else "\u2014"),
        "Riesgo Geop.":     (lambda v: f"{v:.0f}" if v is not None else "\u2014"),
        "Inflacion EE.UU.": (lambda v: f"{v:.1f}%" if v is not None else "\u2014"),
        "Prima riesgo IT":  (lambda v: f"{v:.0f} pb" if v is not None else "\u2014"),
    }
    total = sum(scores.values())
    level = _score_to_level(total)
    text  = _score_to_text(total)

    indicators = [
        {
            "name": name,
            "value_str": formats[name](values[name]),
            "score": scores[name],
            "has_data": values[name] is not None,
        }
        for name in scores
    ]
    return {
        "level":      level,
        "score":      total,
        "max_score":  18,
        "text_level": text,
        "indicators": indicators,
    }


def _calculate_region_risk(region_key: str) -> dict:
    """
    Calcula el nivel de riesgo para una region especifica.
    Retorna dict con: level, score, worst_indicator_text, has_data
    """
    region_configs = {
        "us": {
            "indicators": [
                (ID_VIX, _score_vix, "VIX"),
                (ID_SPREAD_10Y2Y, _score_spread, "Curva"),
                (ID_CPI_US, _score_inflation_us, "IPC"),
                (ID_UNEMP_US, lambda v: 0 if v is None else (0 if v < 4 else (1 if v < 5 else (2 if v < 6 else 3))), "Desempleo"),
            ],
            "max": 12,
        },
        "eurozone": {
            "indicators": [
                (ID_SPREAD_IT, _score_italy_spread, "Prima IT"),
                (ID_HICP_EA, lambda v: _score_inflation_us(v), "HICP"),
                (ID_UNEMP_EA, lambda v: 0 if v is None else (0 if v < 7 else (1 if v < 9 else (2 if v < 11 else 3))), "Desempleo"),
                (ID_SPREAD_ES, lambda v: 0 if v is None else (0 if v < 100 else (1 if v < 200 else (2 if v < 300 else 3))), "Prima ES"),
            ],
            "max": 12,
        },
        "china": {
            "indicators": [
                (ID_USDCNY, lambda v: 0 if v is None else (0 if v < 7 else (1 if v < 7.2 else (2 if v < 7.5 else 3))), "CNY/USD"),
            ],
            "max": 3,
        },
        "japan": {
            "indicators": [
                (ID_USDJPY, lambda v: 0 if v is None else (0 if v < 130 else (1 if v < 145 else (2 if v < 160 else 3))), "USD/JPY"),
            ],
            "max": 3,
        },
        "emerging": {
            "indicators": [
                (ID_DXY, lambda v: 0 if v is None else (0 if v < 100 else (1 if v < 104 else (2 if v < 110 else 3))), "DXY"),
                (ID_VIX, _score_vix, "VIX"),
            ],
            "max": 6,
        },
        "uk": {
            "indicators": [
                (ID_GBPUSD, lambda v: 0 if v is None else (0 if v > 1.25 else (1 if v > 1.20 else (2 if v > 1.15 else 3))), "GBP/USD"),
                (ID_SPREAD_ES, lambda v: 0, "Gilts"),  # proxy
            ],
            "max": 6,
        },
    }

    cfg = region_configs.get(region_key, {"indicators": [], "max": 6})
    scores = []
    worst_name = None
    worst_score = 0

    for series_id, score_fn, label in cfg["indicators"]:
        val, _ = get_latest_value(series_id)
        s = score_fn(val)
        scores.append(s)
        if s > worst_score:
            worst_score = s
            if val is not None:
                worst_name = f"{label}: {val:.2f}"

    total = sum(scores)
    max_s = cfg["max"]
    # Escalar a 0-18 para usar la misma funcion de nivel
    scaled = round(total * 18 / max_s) if max_s > 0 else 0
    level = _score_to_level(scaled)
    text  = _score_to_text(scaled)
    return {
        "level":          level,
        "text_level":     text,
        "worst_indicator": worst_name or "Sin datos suficientes",
        "has_data":       len(scores) > 0 and total > 0,
    }


# ══════════════════════════════════════════════════════════════════════════════
# SECCION 1 — HEADER
# ══════════════════════════════════════════════════════════════════════════════

def _build_header() -> html.Div:
    last_dt = get_db_last_update()
    last_str = last_dt.strftime("%d/%m/%Y %H:%M") if last_dt else "Sin datos"
    n_indicators = get_db_indicator_count()
    n_sources    = get_db_source_count()

    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.Span(
                                "Panel de Estado Global",
                                style={
                                    "fontSize":   "1.4rem",
                                    "fontWeight": "700",
                                    "color":      COLORS["text"],
                                },
                            ),
                            html.Span(
                                id="m01-last-updated",
                                children=f"Actualizado: {last_str}",
                                style={
                                    "fontSize": "0.75rem",
                                    "color":    COLORS["text_muted"],
                                    "marginLeft": "16px",
                                },
                            ),
                        ],
                        style={"display": "flex", "alignItems": "baseline", "gap": "0"},
                    ),
                    html.Div(
                        id="m01-indicator-count",
                        children=(
                            f"{n_indicators} indicadores monitorizados"
                            f"  \u00b7  {n_sources} fuentes activas"
                        ),
                        style={"fontSize": "0.72rem", "color": COLORS["text_label"], "marginTop": "4px"},
                    ),
                ],
                style={"flex": "1"},
            ),
            dbc.Button(
                [html.Span("\u21ba  ", style={"fontSize": "0.9rem"}), "Actualizar datos"],
                id="m01-refresh-btn",
                color="outline-info",
                size="sm",
                style={"fontSize": "0.78rem", "whiteSpace": "nowrap"},
            ),
            dcc.Interval(
                id="m01-refresh-interval",
                interval=300_000,  # 5 minutos
                n_intervals=0,
            ),
        ],
        style={
            "display":         "flex",
            "justifyContent":  "space-between",
            "alignItems":      "center",
            "padding":         "16px 20px 14px",
            "borderBottom":    f"1px solid {COLORS['border']}",
            "backgroundColor": COLORS["card_bg"],
        },
    )


# ══════════════════════════════════════════════════════════════════════════════
# SECCION 2 — SEMAFOROS DE RIESGO
# ══════════════════════════════════════════════════════════════════════════════

def _build_global_semaphore_content() -> html.Div:
    risk = _calculate_global_risk()
    level   = risk["level"]
    score   = risk["score"]
    text    = risk["text_level"]
    indics  = risk["indicators"]
    color   = _level_to_color(level)

    # Dot grande con glow
    dot_size = 80
    dot = html.Div(
        style={
            "width":           f"{dot_size}px",
            "height":          f"{dot_size}px",
            "borderRadius":    "50%",
            "backgroundColor": color,
            "boxShadow":       f"0 0 30px {color}80, 0 0 60px {color}30",
            "margin":          "0 auto 10px",
            "flexShrink":      "0",
        }
    )

    score_bar = html.Div(
        [
            html.Div(
                style={
                    "height":          "6px",
                    "width":           f"{score / 18 * 100:.0f}%",
                    "backgroundColor": color,
                    "borderRadius":    "3px",
                    "transition":      "width 0.5s ease",
                }
            )
        ],
        style={
            "backgroundColor": COLORS["border"],
            "borderRadius":    "3px",
            "marginTop":       "6px",
            "marginBottom":    "10px",
        },
    )

    indicator_rows = []
    for ind in indics:
        pts_color = (
            COLORS["green"] if ind["score"] == 0
            else COLORS["yellow"] if ind["score"] == 1
            else COLORS["orange"] if ind["score"] == 2
            else COLORS["red"]
        )
        indicator_rows.append(
            html.Div(
                [
                    html.Span(ind["name"], style={"color": COLORS["text_muted"], "flex": "1", "fontSize": "0.72rem"}),
                    html.Span(
                        ind["value_str"],
                        style={"color": COLORS["text"], "fontFamily": "monospace", "fontSize": "0.72rem", "marginRight": "8px"},
                    ),
                    html.Span(
                        f"{ind['score']}pt",
                        style={"color": pts_color, "fontWeight": "700", "fontSize": "0.70rem", "minWidth": "24px", "textAlign": "right"},
                    ),
                ],
                style={"display": "flex", "alignItems": "center", "padding": "2px 0"},
            )
        )

    return html.Div(
        [
            dot,
            html.Div(
                text,
                style={
                    "color":       color,
                    "fontWeight":  "700",
                    "fontSize":    "0.85rem",
                    "textAlign":   "center",
                    "letterSpacing": "0.08em",
                    "marginBottom": "4px",
                },
            ),
            html.Div(
                f"{score} / 18 puntos",
                style={"color": COLORS["text_muted"], "fontSize": "0.70rem", "textAlign": "center", "marginBottom": "8px"},
            ),
            score_bar,
            html.Div(indicator_rows, style={"marginTop": "6px"}),
        ]
    )


def _build_regional_semaphores_content() -> html.Div:
    regions = [
        ("us",       "\U0001f1fa\U0001f1f8", "EE.UU."),
        ("eurozone", "\U0001f1ea\U0001f1fa", "Eurozona"),
        ("china",    "\U0001f1e8\U0001f1f3", "China"),
        ("japan",    "\U0001f1ef\U0001f1f5", "Japon"),
        ("emerging", "\U0001f30d",           "Emergentes"),
        ("uk",       "\U0001f1ec\U0001f1e7", "Reino Unido"),
    ]

    cards = []
    for key, flag, name in regions:
        r = _calculate_region_risk(key)
        color = _level_to_color(r["level"])

        dot = html.Div(
            style={
                "width":           "20px",
                "height":          "20px",
                "borderRadius":    "50%",
                "backgroundColor": color,
                "boxShadow":       f"0 0 8px {color}80",
                "flexShrink":      "0",
                "marginBottom":    "6px",
            }
        )

        cards.append(
            html.Div(
                [
                    dot,
                    html.Div(
                        f"{flag} {name}",
                        style={"fontWeight": "600", "fontSize": "0.78rem", "color": COLORS["text"], "marginBottom": "2px"},
                    ),
                    html.Div(
                        r["text_level"],
                        style={"fontSize": "0.65rem", "color": color, "fontWeight": "700", "marginBottom": "4px"},
                    ),
                    html.Div(
                        r["worst_indicator"],
                        style={"fontSize": "0.60rem", "color": COLORS["text_label"],
                               "overflow": "hidden", "textOverflow": "ellipsis", "whiteSpace": "nowrap"},
                    ),
                ],
                style={
                    "backgroundColor": COLORS["background"],
                    "border":          f"1px solid {COLORS['border']}",
                    "borderRadius":    "6px",
                    "padding":         "10px 12px",
                    "minWidth":        "0",
                },
            )
        )

    # Grid 3x2
    return html.Div(
        [
            html.Div(
                cards[:3],
                style={"display": "grid", "gridTemplateColumns": "1fr 1fr 1fr", "gap": "8px", "marginBottom": "8px"},
            ),
            html.Div(
                cards[3:],
                style={"display": "grid", "gridTemplateColumns": "1fr 1fr 1fr", "gap": "8px"},
            ),
        ]
    )


def _build_semaphore_section() -> html.Div:
    return html.Div(
        id="m01-semaphore-container",
        children=_build_semaphore_section_content(),
    )


def _build_semaphore_section_content() -> html.Div:
    return dbc.Row(
        [
            # Parte A — Semaforo global grande (4/12)
            dbc.Col(
                html.Div(
                    [
                        html.Div(
                            "RIESGO SISTEMICO GLOBAL",
                            style={
                                "fontSize":      "0.68rem",
                                "letterSpacing": "0.1em",
                                "color":         COLORS["text_muted"],
                                "marginBottom":  "14px",
                                "fontWeight":    "600",
                            },
                        ),
                        _build_global_semaphore_content(),
                    ],
                    style={
                        "backgroundColor": COLORS["card_bg"],
                        "border":          f"1px solid {COLORS['border']}",
                        "borderRadius":    "6px",
                        "padding":         "16px",
                        "height":          "100%",
                    },
                ),
                md=4,
            ),
            # Parte B — Semaforos regionales (8/12)
            dbc.Col(
                html.Div(
                    [
                        html.Div(
                            "RIESGO POR REGION",
                            style={
                                "fontSize":      "0.68rem",
                                "letterSpacing": "0.1em",
                                "color":         COLORS["text_muted"],
                                "marginBottom":  "14px",
                                "fontWeight":    "600",
                            },
                        ),
                        _build_regional_semaphores_content(),
                    ],
                    style={
                        "backgroundColor": COLORS["card_bg"],
                        "border":          f"1px solid {COLORS['border']}",
                        "borderRadius":    "6px",
                        "padding":         "16px",
                        "height":          "100%",
                    },
                ),
                md=8,
            ),
        ],
        className="g-3",
    )


# ══════════════════════════════════════════════════════════════════════════════
# SECCION 3 — METRICAS CLAVE
# ══════════════════════════════════════════════════════════════════════════════

def _get_metric(series_id: str, period_days: int = 1):
    """Retorna (value, pct_change) para una metrica."""
    val, prev, abs_c, pct_c = get_change(series_id, period_days=period_days)
    return val, pct_c


def _build_metrics_section_content() -> html.Div:
    # Helpers de formato — valor ya lleva su unidad, nunca "—%"
    def _pct(v, d=1):
        return "\u2014" if v is None else f"{v:.{d}f}%"

    def _pct_signed(v, d=2):
        return "\u2014" if v is None else f"{v:+.{d}f}%"

    def _num(v, d=0):
        return "\u2014" if v is None else f"{v:,.{d}f}"

    def _bwp(abs_chg):
        """Color 'bad when positive': subir es malo (VIX, CPI, desempleo)."""
        if abs_chg is None or abs_chg == 0:
            return None
        return COLORS["red"] if abs_chg > 0 else COLORS["green"]

    # ── Col 1: Mercados ────────────────────────────────────────────────────────
    sp500_v, _, sp500_a, _ = get_change(ID_SP500)
    ibex_v,  _, ibex_a,  _ = get_change(ID_IBEX35)
    vix_v,   _, vix_a,   _ = get_change(ID_VIX)
    gold_v,  _, gold_a,  _ = get_change(ID_GOLD)

    col1 = [
        # Cambio absoluto en pts (más claro que %, y no conflicto de unidad)
        create_metric_card("S&P 500",      _num(sp500_v, 0), sp500_a, "24h"),
        create_metric_card("IBEX 35",      _num(ibex_v, 0),  ibex_a,  "24h"),
        create_metric_card(
            "VIX",
            _num(vix_v, 1),
            vix_a,
            "24h",
            color=_bwp(vix_a),      # subir VIX = malo = rojo
        ),
        create_metric_card("Oro (USD/oz)", _num(gold_v, 0),  gold_a,  "24h"),
    ]

    # ── Col 2: Macro EE.UU. ────────────────────────────────────────────────────
    cpi_v,   _, cpi_a,   _ = get_change(ID_CPI_US,   period_days=30)
    unemp_v, _, unemp_a, _ = get_change(ID_UNEMP_US, period_days=30)
    fed_v,   _             = get_latest_value(ID_FED_FUNDS)
    spread_v, _            = get_latest_value(ID_SPREAD_10Y2Y)

    spread_label = "Spread 10y-2y"
    if spread_v is not None:
        spread_label += " (Inv.)" if spread_v < 0 else " (Normal)"
    spread_color = COLORS["red"] if (spread_v is not None and spread_v < 0) else COLORS["green"]

    col2 = [
        create_metric_card(
            "Inflacion EE.UU. (YoY)",
            _pct(cpi_v),
            cpi_a,              # pp absolutos vs mes anterior
            "vs mes ant.",
            color=_bwp(cpi_a),
        ),
        create_metric_card("Fed Funds Rate",  _pct(fed_v, 2), None),
        create_metric_card(
            "Desempleo EE.UU.",
            _pct(unemp_v),
            unemp_a,
            "vs mes ant.",
            color=_bwp(unemp_a),
        ),
        create_metric_card(
            spread_label,
            _pct_signed(spread_v) if spread_v is not None else "\u2014",
            None,
            color=spread_color,
        ),
    ]

    # ── Col 3: Europa ──────────────────────────────────────────────────────────
    hicp_v,  _, hicp_a,  _ = get_change(ID_HICP_EA,  period_days=30)
    es_v,    _, es_a,    _ = get_change(ID_SPREAD_ES, period_days=30)
    ecb_v,   _             = get_latest_value(ID_ECB_RATE)
    eur_v,   _, eur_a,   _ = get_change(ID_EURUSD)

    col3 = [
        create_metric_card(
            "Inflacion Eurozona (HICP)",
            _pct(hicp_v),
            hicp_a,
            "vs mes ant.",
            color=_bwp(hicp_a),
        ),
        create_metric_card("Tipo BCE (deposito)", _pct(ecb_v, 2), None),
        create_metric_card("EUR/USD",
            _num(eur_v, 4) if eur_v else "\u2014",
            eur_a,
            "24h",
        ),
        create_metric_card(
            "Prima riesgo Espana",
            f"{es_v:.0f} pb" if es_v is not None else "\u2014",
            es_a,
            "vs mes ant.",
        ),
    ]

    # ── Col 4: Global ──────────────────────────────────────────────────────────
    brent_v, _, brent_a, _ = get_change(ID_BRENT)
    btc_v,   _, btc_a,   _ = get_change(ID_BTC)
    if btc_v is None:
        btc_v, _, btc_a, _ = get_change(ID_BTC_YF)
    gpr_v,   _             = get_latest_value(ID_GPR)
    euribor_v, _           = get_latest_value(ID_EURIBOR_3M)

    gpr_label = "GPR Global"
    gpr_color = None
    if gpr_v is not None:
        if gpr_v < 100:
            gpr_label += " (Normal)";  gpr_color = COLORS["green"]
        elif gpr_v < 150:
            gpr_label += " (Elevado)"; gpr_color = COLORS["yellow"]
        elif gpr_v < 200:
            gpr_label += " (Alto)";    gpr_color = COLORS["orange"]
        else:
            gpr_label += " (Critico)"; gpr_color = COLORS["red"]

    col4 = [
        create_metric_card("Petroleo Brent (USD)", _num(brent_v, 1), brent_a, "24h"),
        create_metric_card("Bitcoin (USD)",         _num(btc_v, 0),   btc_a,   "24h"),
        create_metric_card(gpr_label, _num(gpr_v, 0), None, color=gpr_color),
        create_metric_card("EURIBOR 3M", _pct(euribor_v, 2), None),
    ]

    def _metric_col(cards: list, title: str) -> dbc.Col:
        # Envolver cada card en un div con height:auto para romper la herencia
        # de .metric-card{height:100%} que causaria desbordamiento con 4 cards apiladas
        wrapped_cards = [
            html.Div(c, style={"height": "auto", "marginBottom": "10px"})
            for c in cards
        ]
        return dbc.Col(
            html.Div(
                [
                    html.Div(
                        title,
                        style={
                            "fontSize":      "0.65rem",
                            "letterSpacing": "0.09em",
                            "color":         COLORS["text_muted"],
                            "fontWeight":    "600",
                            "paddingBottom": "8px",
                            "borderBottom":  f"1px solid {COLORS['border']}",
                            "marginBottom":  "10px",
                        },
                    ),
                    *wrapped_cards,
                ],
                style={
                    "backgroundColor": COLORS["card_bg"],
                    "border":          f"1px solid {COLORS['border']}",
                    "borderRadius":    "6px",
                    "padding":         "14px",
                },
            ),
            md=3,
        )

    return dbc.Row(
        [
            _metric_col(col1, "MERCADOS"),
            _metric_col(col2, "MACRO EE.UU."),
            _metric_col(col3, "EUROPA"),
            _metric_col(col4, "GLOBAL"),
        ],
        className="g-3",
    )


def _build_metrics_section() -> html.Div:
    return html.Div(id="m01-metrics-container", children=_build_metrics_section_content())


# ══════════════════════════════════════════════════════════════════════════════
# SECCION 4A — NOTICIAS
# ══════════════════════════════════════════════════════════════════════════════

_CATEGORY_COLORS = {
    "macro":         CHART_COLORS["primary"],
    "markets":       CHART_COLORS["positive"],
    "geopolitics":   CHART_COLORS["negative"],
    "energy":        CHART_COLORS["orange"],
    "crypto":        CHART_COLORS["bitcoin"],
    "central_banks": "#8b5cf6",
}

_CATEGORY_LABELS = {
    "macro":         "Macro",
    "markets":       "Mercados",
    "geopolitics":   "Geopolitica",
    "energy":        "Energia",
    "crypto":        "Crypto",
    "central_banks": "BC",
}


def _build_news_content() -> html.Div:
    from config import NEWS_API_KEY
    articles = get_latest_news(n=8, hours=48)

    if not articles and not NEWS_API_KEY:
        return create_empty_state(
            "NewsAPI no configurado",
            "Anade NEWS_API_KEY al fichero .env",
        )

    if not articles:
        return create_empty_state(
            "Sin noticias recientes",
            "Los datos se cargan automaticamente cada hora",
        )

    items = []
    for art in articles:
        cat  = art.get("category") or "macro"
        score = float(art.get("impact_score") or 0)
        title = art.get("title") or ""
        if len(title) > 80:
            title = title[:77] + "..."

        cat_color = _CATEGORY_COLORS.get(cat, CHART_COLORS["primary"])
        cat_label = _CATEGORY_LABELS.get(cat, cat)

        source_str = art.get("source_name") or ""
        rel_time   = time_ago(art.get("published_at"))

        impact_bar = html.Div(
            html.Div(
                style={
                    "width":           f"{score * 100:.0f}%",
                    "height":          "3px",
                    "backgroundColor": cat_color,
                    "borderRadius":    "1px",
                    "opacity":         "0.7",
                }
            ),
            style={
                "backgroundColor": COLORS["border"],
                "borderRadius":    "1px",
                "marginTop":       "4px",
            },
        )

        url = art.get("url") or "#"
        items.append(
            html.Div(
                [
                    html.Div(
                        [
                            html.A(
                                title,
                                href=url,
                                target="_blank",
                                style={
                                    "color":          COLORS["text"],
                                    "textDecoration": "none",
                                    "fontSize":       "0.78rem",
                                    "lineHeight":     "1.4",
                                    "flex":           "1",
                                    "fontWeight":     "500",
                                },
                            ),
                            html.Span(
                                cat_label,
                                style={
                                    "backgroundColor": cat_color + "22",
                                    "color":           cat_color,
                                    "border":          f"1px solid {cat_color}44",
                                    "borderRadius":    "3px",
                                    "padding":         "1px 6px",
                                    "fontSize":        "0.60rem",
                                    "fontWeight":      "700",
                                    "marginLeft":      "8px",
                                    "flexShrink":      "0",
                                },
                            ),
                        ],
                        style={"display": "flex", "alignItems": "flex-start"},
                    ),
                    html.Div(
                        f"{source_str}  \u00b7  {rel_time}",
                        style={"fontSize": "0.65rem", "color": COLORS["text_label"], "marginTop": "2px"},
                    ),
                    impact_bar,
                ],
                style={
                    "padding":       "8px 0",
                    "borderBottom":  f"1px solid {COLORS['border']}20",
                },
            )
        )

    return html.Div(items)


def _build_news_column() -> html.Div:
    news = get_latest_news(n=8, hours=48)
    badge_n = len(news)
    return html.Div(
        [
            html.Div(
                [
                    html.Span(
                        "Eventos Recientes",
                        style={"fontWeight": "600", "fontSize": "0.82rem", "color": COLORS["text"]},
                    ),
                    html.Span(
                        str(badge_n),
                        id="m01-news-badge",
                        style={
                            "backgroundColor": COLORS["accent"],
                            "color":           "white",
                            "borderRadius":    "10px",
                            "padding":         "1px 7px",
                            "fontSize":        "0.65rem",
                            "fontWeight":      "700",
                            "marginLeft":      "8px",
                        },
                    ),
                ],
                style={"marginBottom": "12px"},
            ),
            html.Div(id="m01-news-container", children=_build_news_content()),
        ],
        style={
            "backgroundColor": COLORS["card_bg"],
            "border":          f"1px solid {COLORS['border']}",
            "borderRadius":    "6px",
            "padding":         "16px",
            "height":          "100%",
            "overflowY":       "auto",
            "maxHeight":       "500px",
        },
    )


# ══════════════════════════════════════════════════════════════════════════════
# SECCION 4B — GRAFICOS DE RIESGO
# ══════════════════════════════════════════════════════════════════════════════

def _build_vix_chart() -> dcc.Graph:
    df = get_series(ID_VIX, days=365)

    fig = go.Figure()
    if not df.empty:
        vix_latest = df["value"].iloc[-1] if len(df) > 0 else 20
        fill_color = (
            "rgba(16,185,129,0.15)"  if vix_latest < 15
            else "rgba(59,130,246,0.15)" if vix_latest < 25
            else "rgba(249,115,22,0.15)" if vix_latest < 35
            else "rgba(239,68,68,0.15)"
        )
        line_color = (
            CHART_COLORS["positive"] if vix_latest < 15
            else CHART_COLORS["primary"] if vix_latest < 25
            else CHART_COLORS["orange"] if vix_latest < 35
            else CHART_COLORS["negative"]
        )
        fig.add_trace(
            go.Scatter(
                x=df["timestamp"],
                y=df["value"],
                mode="lines",
                name="VIX",
                line={"color": line_color, "width": 1.5},
                fill="tozeroy",
                fillcolor=fill_color,
                hovertemplate="<b>%{x|%d/%m/%Y}</b><br>VIX: %{y:.1f}<extra></extra>",
            )
        )

    # Lineas de referencia
    for y_val, label, color in [
        (15, "Calma", CHART_COLORS["positive"]),
        (25, "Tension", CHART_COLORS["warning"]),
        (35, "Panico", CHART_COLORS["negative"]),
    ]:
        fig.add_hline(
            y=y_val,
            line_dash="dot",
            line_color=color,
            line_width=1,
            annotation_text=label,
            annotation_position="right",
            annotation={"font": {"size": 9, "color": color}},
        )

    layout = get_base_layout(title="VIX \u2014 Indice de Volatilidad (12 meses)", height=220)
    layout["xaxis"] = {**layout.get("xaxis", {}), "rangeselector": get_time_range_buttons()}
    layout["margin"] = {"l": 40, "r": 10, "t": 40, "b": 30}
    fig.update_layout(**layout)

    return dcc.Graph(figure=fig, config={"displayModeBar": False}, style={"height": "220px"})


def _build_gpr_chart() -> dcc.Graph:
    df = get_series(ID_GPR, days=5 * 365)

    fig = go.Figure()
    if not df.empty:
        fig.add_trace(
            go.Scatter(
                x=df["timestamp"],
                y=df["value"],
                mode="lines",
                name="GPR",
                line={"color": "#a855f7", "width": 1.5},
                fill="tozeroy",
                fillcolor="rgba(168,85,247,0.12)",
                hovertemplate="<b>%{x|%b %Y}</b><br>GPR: %{y:.0f}<extra></extra>",
            )
        )

        # Anotar picos > 200
        if len(df) > 0:
            peaks = df[df["value"] > 200].nlargest(3, "value")
            for _, row in peaks.iterrows():
                fig.add_annotation(
                    x=row["timestamp"],
                    y=row["value"],
                    text=f"{row['value']:.0f}",
                    showarrow=True,
                    arrowhead=2,
                    arrowcolor="#a855f7",
                    font={"size": 8, "color": "#a855f7"},
                    bgcolor="#1f2937",
                    bordercolor="#a855f7",
                    borderwidth=1,
                )

    for y_val, label, color in [
        (100, "Normal", CHART_COLORS["positive"]),
        (200, "Crisis", CHART_COLORS["negative"]),
    ]:
        fig.add_hline(
            y=y_val,
            line_dash="dot",
            line_color=color,
            line_width=1,
            annotation_text=label,
            annotation_position="right",
            annotation={"font": {"size": 9, "color": color}},
        )

    layout = get_base_layout(title="GPR \u2014 Riesgo Geopolitico Global (5 anos)", height=220)
    layout["margin"] = {"l": 40, "r": 10, "t": 40, "b": 30}
    fig.update_layout(**layout)

    return dcc.Graph(figure=fig, config={"displayModeBar": False}, style={"height": "220px"})


def _build_chart_column() -> html.Div:
    return html.Div(
        [
            html.Div(
                "GRAFICOS DE RIESGO",
                style={
                    "fontSize": "0.68rem", "letterSpacing": "0.1em",
                    "color": COLORS["text_muted"], "fontWeight": "600", "marginBottom": "12px",
                },
            ),
            _build_vix_chart(),
            html.Div(style={"height": "8px"}),
            _build_gpr_chart(),
        ],
        style={
            "backgroundColor": COLORS["card_bg"],
            "border":          f"1px solid {COLORS['border']}",
            "borderRadius":    "6px",
            "padding":         "16px",
            "height":          "100%",
        },
    )


# ══════════════════════════════════════════════════════════════════════════════
# SECCION 4C — ALERTAS Y SENALES
# ══════════════════════════════════════════════════════════════════════════════

def _build_alerts_content() -> html.Div:
    alerts = get_active_alerts(hours=48)

    if not alerts:
        return html.Div(
            [
                html.Span(
                    "\u2705 Sin alertas activas",
                    style={"color": COLORS["green"], "fontSize": "0.80rem"},
                )
            ],
            style={"padding": "8px 0"},
        )

    items = []
    for alert in alerts:
        sev = alert.get("severity", "warning")
        icon = "\U0001f6a8" if sev == "critical" else "\u26a0\ufe0f" if sev == "warning" else "\u2139\ufe0f"
        color = COLORS["red"] if sev == "critical" else COLORS["yellow"] if sev == "warning" else CHART_COLORS["primary"]
        msg = alert.get("message", "")
        rel = time_ago(
            datetime.fromisoformat(alert["triggered_at"])
            if isinstance(alert.get("triggered_at"), str)
            else alert.get("triggered_at")
        )
        alert_id = alert.get("id", 0)

        items.append(
            html.Div(
                [
                    html.Div(
                        [
                            html.Span(icon, style={"marginRight": "6px", "fontSize": "0.85rem"}),
                            html.Span(msg, style={"fontSize": "0.73rem", "color": COLORS["text"], "flex": "1", "lineHeight": "1.4"}),
                            dbc.Button(
                                "\u00d7",
                                id={"type": "m01-dismiss-alert", "id": alert_id},
                                color="link",
                                size="sm",
                                style={"color": COLORS["text_muted"], "padding": "0 4px", "fontSize": "0.9rem", "lineHeight": "1"},
                            ),
                        ],
                        style={"display": "flex", "alignItems": "flex-start"},
                    ),
                    html.Div(
                        rel,
                        style={"fontSize": "0.63rem", "color": COLORS["text_label"], "paddingLeft": "24px", "marginTop": "2px"},
                    ),
                ],
                style={
                    "padding":       "7px 0",
                    "borderLeft":    f"2px solid {color}",
                    "paddingLeft":   "8px",
                    "marginBottom":  "6px",
                },
            )
        )

    return html.Div(items)


def _build_system_signals() -> html.Div:
    spread_val, _ = get_latest_value(ID_SPREAD_10Y2Y)
    stlfsi_val, _ = get_latest_value(ID_STLFSI)

    # Ultima captura y proxima
    last_upd = get_db_last_update()
    last_str = last_upd.strftime("%d/%m/%Y %H:%M") if last_upd else "\u2014"

    # Estado curva
    if spread_val is None:
        curva_text  = "Sin datos"
        curva_color = COLORS["text_label"]
        curva_icon  = "\u2014"
    elif spread_val < 0:
        curva_text  = f"Invertida ({spread_val:+.2f}%)"
        curva_color = COLORS["red"]
        curva_icon  = "\u26a0\ufe0f"
    else:
        curva_text  = f"Normal ({spread_val:+.2f}%)"
        curva_color = COLORS["green"]
        curva_icon  = "\u2705"

    # Estado STLFSI
    if stlfsi_val is None:
        stres_text  = "Sin datos"
        stres_color = COLORS["text_label"]
    elif stlfsi_val < 0:
        stres_text  = f"{stlfsi_val:.2f} \u2014 Bajo"
        stres_color = COLORS["green"]
    elif stlfsi_val < 1:
        stres_text  = f"{stlfsi_val:.2f} \u2014 Moderado"
        stres_color = COLORS["yellow"]
    elif stlfsi_val < 2:
        stres_text  = f"{stlfsi_val:.2f} \u2014 Elevado"
        stres_color = COLORS["orange"]
    else:
        stres_text  = f"{stlfsi_val:.2f} \u2014 Critico"
        stres_color = COLORS["red"]

    def _row(label, value, color):
        return html.Div(
            [
                html.Span(label, style={"fontSize": "0.68rem", "color": COLORS["text_muted"], "flex": "1"}),
                html.Span(value, style={"fontSize": "0.68rem", "color": color, "fontWeight": "600", "fontFamily": "monospace"}),
            ],
            style={"display": "flex", "padding": "4px 0", "borderBottom": f"1px solid {COLORS['border']}20"},
        )

    return html.Div(
        [
            html.Div(
                "SENALES DEL SISTEMA",
                style={
                    "fontSize": "0.65rem", "letterSpacing": "0.09em",
                    "color": COLORS["text_muted"], "fontWeight": "600", "marginBottom": "8px",
                },
            ),
            _row(f"{curva_icon} Curva de tipos", curva_text, curva_color),
            _row("\U0001f3db\ufe0f Estres financiero Fed", stres_text, stres_color),
            _row("\U0001f4c5 Ultimo dato BD", last_str, COLORS["text"]),
        ],
        style={
            "marginTop":       "14px",
            "backgroundColor": COLORS["background"],
            "border":          f"1px solid {COLORS['border']}",
            "borderRadius":    "4px",
            "padding":         "10px",
        },
    )


def _build_alerts_column() -> html.Div:
    alerts = get_active_alerts(hours=48)
    badge_n = len(alerts)
    return html.Div(
        [
            html.Div(
                [
                    html.Span(
                        "Alertas Activas",
                        style={"fontWeight": "600", "fontSize": "0.82rem", "color": COLORS["text"]},
                    ),
                    html.Span(
                        str(badge_n),
                        style={
                            "backgroundColor": COLORS["red"] if badge_n > 0 else COLORS["border"],
                            "color":           "white",
                            "borderRadius":    "10px",
                            "padding":         "1px 7px",
                            "fontSize":        "0.65rem",
                            "fontWeight":      "700",
                            "marginLeft":      "8px",
                        },
                    ),
                ],
                style={"marginBottom": "12px"},
            ),
            html.Div(
                id="m01-alerts-container",
                children=_build_alerts_content(),
                style={"overflowY": "auto", "maxHeight": "240px"},
            ),
            _build_system_signals(),
        ],
        style={
            "backgroundColor": COLORS["card_bg"],
            "border":          f"1px solid {COLORS['border']}",
            "borderRadius":    "6px",
            "padding":         "16px",
            "height":          "100%",
        },
    )


# ══════════════════════════════════════════════════════════════════════════════
# SECCION 5 — LINEA DE TIEMPO
# ══════════════════════════════════════════════════════════════════════════════

_EVENT_COLORS = {
    "conflict":         "#ef4444",
    "sanction":         "#f97316",
    "election":         "#3b82f6",
    "trade_war":        "#f59e0b",
    "energy":           "#10b981",
    "financial_crisis": "#8b5cf6",
    "crypto_cycle":     "#f7931a",
    "other":            "#9ca3af",
}


def _build_timeline_content() -> dcc.Graph:
    events = get_geopolitical_events(months=24)

    # Halvings de Bitcoin conocidos (aproximados)
    halvings = [
        {"date": datetime(2024, 4, 19), "title": "Halving Bitcoin #4", "category": "crypto_cycle", "severity": 3, "region": "Global"},
        {"date": datetime(2020, 5, 11), "title": "Halving Bitcoin #3", "category": "crypto_cycle", "severity": 3, "region": "Global"},
    ]
    # Anadir halvings al listado si estan en el rango
    since = datetime.utcnow() - __import__("datetime").timedelta(days=24 * 30)
    for h in halvings:
        if h["date"] >= since:
            events.append({**h, "description": "Reduccion a la mitad del bloque de recompensa de Bitcoin"})

    if not events:
        return dcc.Graph(
            figure=go.Figure(
                layout=get_base_layout("Linea de Tiempo \u2014 Sin eventos registrados", height=160)
            ),
            config={"displayModeBar": False},
            style={"height": "160px"},
        )

    x_vals, y_vals, sizes, colors_list, texts, hovers = [], [], [], [], [], []
    for ev in events:
        dt = ev.get("date")
        if dt is None:
            continue
        if isinstance(dt, date) and not isinstance(dt, datetime):
            dt = datetime.combine(dt, datetime.min.time())
        sev     = ev.get("severity") or 2
        cat     = ev.get("category") or "other"
        title   = ev.get("title") or ""
        desc    = (ev.get("description") or "")[:120]
        region  = ev.get("region") or ""
        x_vals.append(dt)
        y_vals.append(0)
        sizes.append(8 + sev * 3)
        colors_list.append(_EVENT_COLORS.get(cat, "#9ca3af"))
        texts.append(title[:20] + ("..." if len(title) > 20 else ""))
        hovers.append(
            f"<b>{dt.strftime('%d/%m/%Y')}</b><br>"
            f"{title}<br>"
            f"<i>{desc}</i><br>"
            f"Region: {region}  |  Severidad: {sev}/5"
        )

    fig = go.Figure(
        go.Scatter(
            x=x_vals,
            y=y_vals,
            mode="markers+text",
            marker={
                "size":  sizes,
                "color": colors_list,
                "line":  {"width": 1, "color": "#1f2937"},
                "opacity": 0.85,
            },
            text=texts,
            textposition="top center",
            textfont={"size": 8, "color": "#9ca3af"},
            hovertemplate="%{customdata}<extra></extra>",
            customdata=hovers,
        )
    )

    layout = get_base_layout("Linea de Tiempo \u2014 Eventos Geopoliticos (24 meses)", height=180)
    layout["yaxis"] = {
        **layout.get("yaxis", {}),
        "showticklabels": False,
        "zeroline": True,
        "zerolinecolor": COLORS["border"],
        "range": [-0.5, 1.2],
    }
    layout["margin"] = {"l": 20, "r": 20, "t": 40, "b": 40}
    fig.update_layout(**layout)

    return dcc.Graph(
        id="m01-timeline-graph",
        figure=fig,
        config={"displayModeBar": False, "scrollZoom": True},
        style={"height": "180px"},
    )


def _build_event_modal() -> dbc.Modal:
    return dbc.Modal(
        [
            dbc.ModalHeader(
                dbc.ModalTitle("Anadir Evento Geopolitico"),
                style={"backgroundColor": COLORS["card_bg"]},
            ),
            dbc.ModalBody(
                [
                    dbc.Row(
                        [
                            dbc.Col(
                                dbc.Input(
                                    id="m01-ev-title",
                                    placeholder="Titulo del evento *",
                                    type="text",
                                    style={"backgroundColor": COLORS["background"], "color": COLORS["text"]},
                                ),
                                md=8,
                            ),
                            dbc.Col(
                                dbc.Input(
                                    id="m01-ev-date",
                                    placeholder="Fecha (YYYY-MM-DD) *",
                                    type="date",
                                    style={"backgroundColor": COLORS["background"], "color": COLORS["text"]},
                                ),
                                md=4,
                            ),
                        ],
                        className="mb-3",
                    ),
                    dbc.Textarea(
                        id="m01-ev-desc",
                        placeholder="Descripcion (opcional)",
                        rows=2,
                        style={"backgroundColor": COLORS["background"], "color": COLORS["text"]},
                        className="mb-3",
                    ),
                    dbc.Row(
                        [
                            dbc.Col(
                                dbc.Select(
                                    id="m01-ev-category",
                                    options=[
                                        {"label": "Conflicto",         "value": "conflict"},
                                        {"label": "Sancion",           "value": "sanction"},
                                        {"label": "Eleccion",          "value": "election"},
                                        {"label": "Guerra comercial",  "value": "trade_war"},
                                        {"label": "Energia",           "value": "energy"},
                                        {"label": "Crisis financiera", "value": "financial_crisis"},
                                        {"label": "Ciclo crypto",      "value": "crypto_cycle"},
                                        {"label": "Otro",              "value": "other"},
                                    ],
                                    value="conflict",
                                    style={"backgroundColor": COLORS["background"], "color": COLORS["text"]},
                                ),
                                md=4,
                            ),
                            dbc.Col(
                                dbc.Input(
                                    id="m01-ev-region",
                                    placeholder="Region (ej: Europa, EE.UU.)",
                                    type="text",
                                    style={"backgroundColor": COLORS["background"], "color": COLORS["text"]},
                                ),
                                md=4,
                            ),
                            dbc.Col(
                                dbc.Select(
                                    id="m01-ev-severity",
                                    options=[{"label": f"Severidad {i}", "value": str(i)} for i in range(1, 6)],
                                    value="3",
                                    style={"backgroundColor": COLORS["background"], "color": COLORS["text"]},
                                ),
                                md=2,
                            ),
                        ],
                        className="mb-3",
                    ),
                    dbc.Input(
                        id="m01-ev-url",
                        placeholder="URL de referencia (opcional)",
                        type="url",
                        style={"backgroundColor": COLORS["background"], "color": COLORS["text"]},
                        className="mb-2",
                    ),
                    html.Div(id="m01-ev-feedback", style={"fontSize": "0.78rem"}),
                ],
                style={"backgroundColor": COLORS["card_bg"]},
            ),
            dbc.ModalFooter(
                [
                    dbc.Button("Cancelar", id="m01-ev-cancel-btn", color="secondary", size="sm"),
                    dbc.Button("Guardar evento", id="m01-ev-save-btn", color="primary", size="sm"),
                ],
                style={"backgroundColor": COLORS["card_bg"]},
            ),
        ],
        id="m01-add-event-modal",
        is_open=False,
        size="lg",
        backdrop="static",
    )


def _build_timeline_section() -> html.Div:
    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        "LINEA DE TIEMPO — EVENTOS GEOPOLITICOS Y CICLOS (24 MESES)",
                        style={
                            "fontSize": "0.68rem", "letterSpacing": "0.1em",
                            "color": COLORS["text_muted"], "fontWeight": "600",
                        },
                    ),
                    dbc.Button(
                        "+ Anadir evento",
                        id="m01-add-event-btn",
                        color="outline-secondary",
                        size="sm",
                        style={"fontSize": "0.70rem"},
                    ),
                ],
                style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "marginBottom": "12px"},
            ),
            html.Div(
                id="m01-timeline-container",
                children=_build_timeline_content(),
            ),
            # Leyenda de colores
            html.Div(
                [
                    html.Span(
                        [
                            html.Span(
                                style={
                                    "display":         "inline-block",
                                    "width":           "10px",
                                    "height":          "10px",
                                    "borderRadius":    "50%",
                                    "backgroundColor": color,
                                    "marginRight":     "4px",
                                    "verticalAlign":   "middle",
                                }
                            ),
                            html.Span(label, style={"fontSize": "0.63rem", "color": COLORS["text_muted"]}),
                        ],
                        style={"marginRight": "12px"},
                    )
                    for cat, color in _EVENT_COLORS.items()
                    for label in [cat.replace("_", " ").capitalize()]
                    if cat != "other"
                ],
                style={"marginTop": "8px", "display": "flex", "flexWrap": "wrap"},
            ),
            _build_event_modal(),
        ],
        style={
            "backgroundColor": COLORS["card_bg"],
            "border":          f"1px solid {COLORS['border']}",
            "borderRadius":    "6px",
            "padding":         "16px",
        },
    )


# ══════════════════════════════════════════════════════════════════════════════
# RENDER PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

def render_module_1() -> html.Div:
    """
    Retorna el layout completo del Modulo 1.
    Llamada desde el callback de routing en app.py cuando pathname == /module/1.
    """
    return html.Div(
        [
            # ── Header ──────────────────────────────────────────────────────────
            _build_header(),

            html.Div(
                [
                    # ── Seccion 2: Semaforos ──────────────────────────────────
                    html.Div(
                        [
                            html.Div(
                                "SEMAFOROS DE RIESGO SISTEMICO",
                                className="section-label",
                                style={
                                    "fontSize": "0.65rem", "letterSpacing": "0.1em",
                                    "color": COLORS["text_label"], "fontWeight": "600",
                                    "marginBottom": "12px",
                                },
                            ),
                            _build_semaphore_section(),
                        ],
                        style={"marginBottom": "20px"},
                    ),

                    # ── Seccion 3: Metricas ───────────────────────────────────
                    html.Div(
                        [
                            html.Div(
                                "METRICAS CLAVE EN TIEMPO REAL",
                                style={
                                    "fontSize": "0.65rem", "letterSpacing": "0.1em",
                                    "color": COLORS["text_label"], "fontWeight": "600",
                                    "marginBottom": "12px",
                                },
                            ),
                            _build_metrics_section(),
                        ],
                        style={"marginBottom": "20px"},
                    ),

                    # ── Seccion 4: Tres columnas ──────────────────────────────
                    html.Div(
                        [
                            html.Div(
                                "NOTICIAS / GRAFICOS / ALERTAS",
                                style={
                                    "fontSize": "0.65rem", "letterSpacing": "0.1em",
                                    "color": COLORS["text_label"], "fontWeight": "600",
                                    "marginBottom": "12px",
                                },
                            ),
                            dbc.Row(
                                [
                                    dbc.Col(_build_news_column(),   md=5),
                                    dbc.Col(_build_chart_column(),  md=4),
                                    dbc.Col(_build_alerts_column(), md=3),
                                ],
                                className="g-3",
                            ),
                        ],
                        style={"marginBottom": "20px"},
                    ),

                    # ── Seccion 5: Linea de tiempo ────────────────────────────
                    html.Div(
                        [
                            html.Div(
                                "LINEA DE TIEMPO",
                                style={
                                    "fontSize": "0.65rem", "letterSpacing": "0.1em",
                                    "color": COLORS["text_label"], "fontWeight": "600",
                                    "marginBottom": "12px",
                                },
                            ),
                            _build_timeline_section(),
                        ],
                        style={"marginBottom": "20px"},
                    ),

                    # ── Seccion 6: Scheduler ──────────────────────────────────
                    html.Div(
                        [
                            html.Div(
                                "ESTADO DEL SCHEDULER",
                                style={
                                    "fontSize": "0.65rem", "letterSpacing": "0.1em",
                                    "color": COLORS["text_label"], "fontWeight": "600",
                                    "marginBottom": "12px",
                                },
                            ),
                            build_scheduler_panel(),
                        ],
                    ),
                ],
                style={"padding": "20px 24px"},
            ),
        ],
        id="m01-root",
        style={"minHeight": "100vh"},
    )


# ══════════════════════════════════════════════════════════════════════════════
# REGISTRO DE CALLBACKS
# ══════════════════════════════════════════════════════════════════════════════

def register_callbacks_module_1(app) -> None:
    """Registra todos los callbacks del Modulo 1 en la instancia Dash."""

    # ── Callback 1: Refresh principal (boton + intervalo 5 min) ──────────────
    @app.callback(
        Output("m01-semaphore-container", "children"),
        Output("m01-metrics-container",  "children"),
        Output("m01-news-container",     "children"),
        Output("m01-last-updated",       "children"),
        Input("m01-refresh-interval",    "n_intervals"),
        Input("m01-refresh-btn",         "n_clicks"),
        prevent_initial_call=True,
    )
    def refresh_module(_n_intervals, _btn_clicks):
        last_dt = get_db_last_update()
        last_str = last_dt.strftime("%d/%m/%Y %H:%M") if last_dt else "Sin datos"
        return (
            _build_semaphore_section_content(),
            _build_metrics_section_content(),
            _build_news_content(),
            f"Actualizado: {last_str}",
        )

    # ── Callback 2: Marcar alerta como leida ──────────────────────────────────
    @app.callback(
        Output("m01-alerts-container", "children"),
        Input({"type": "m01-dismiss-alert", "id": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def dismiss_alert(n_clicks_list):
        triggered = ctx.triggered_id
        if triggered and isinstance(triggered, dict):
            alert_id = triggered.get("id")
            if alert_id:
                try:
                    from alerts.alert_manager import AlertManager
                    AlertManager().mark_as_read(int(alert_id))
                except Exception as exc:
                    logger.warning("dismiss_alert error: %s", exc)
        return _build_alerts_content()

    # ── Callback 3a: Abrir/cerrar modal de evento ─────────────────────────────
    @app.callback(
        Output("m01-add-event-modal", "is_open"),
        Output("m01-ev-feedback",     "children"),
        Input("m01-add-event-btn",    "n_clicks"),
        Input("m01-ev-cancel-btn",    "n_clicks"),
        State("m01-add-event-modal",  "is_open"),
        prevent_initial_call=True,
    )
    def toggle_event_modal(open_clicks, cancel_clicks, is_open):
        triggered = ctx.triggered_id
        if triggered == "m01-add-event-btn":
            return True, ""
        if triggered == "m01-ev-cancel-btn":
            return False, ""
        return is_open, ""

    # ── Callback 3b: Guardar evento ────────────────────────────────────────────
    @app.callback(
        Output("m01-add-event-modal", "is_open", allow_duplicate=True),
        Output("m01-timeline-container", "children"),
        Output("m01-ev-feedback", "children", allow_duplicate=True),
        Input("m01-ev-save-btn",   "n_clicks"),
        State("m01-ev-title",      "value"),
        State("m01-ev-date",       "value"),
        State("m01-ev-desc",       "value"),
        State("m01-ev-category",   "value"),
        State("m01-ev-region",     "value"),
        State("m01-ev-severity",   "value"),
        State("m01-ev-url",        "value"),
        prevent_initial_call=True,
    )
    def save_event(n_clicks, title, ev_date, desc, category, region, severity, url):
        if not n_clicks:
            return no_update, no_update, ""

        if not title or not ev_date:
            return (
                no_update,
                no_update,
                html.Span("Titulo y fecha son obligatorios.", style={"color": COLORS["red"]}),
            )

        try:
            dt = datetime.strptime(ev_date, "%Y-%m-%d")
            sev_int = int(severity) if severity else 3

            from collectors.news_collector import NewsCollector
            nc = NewsCollector()
            nc.add_manual_event(
                date_=dt,
                title=title,
                description=desc or "",
                category=category or "other",
                region=region or "Global",
                severity=sev_int,
                market_impact="",
                source_url=url or "",
            )
            logger.info("Evento manual guardado: %s", title)
            return False, _build_timeline_content(), html.Span("Evento guardado.", style={"color": COLORS["green"]})
        except Exception as exc:
            logger.warning("save_event error: %s", exc)
            return (
                no_update,
                no_update,
                html.Span(f"Error: {exc}", style={"color": COLORS["red"]}),
            )
