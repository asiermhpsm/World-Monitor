"""
Modulo 2 — Macroeconomía Global
Se renderiza cuando la URL es /module/2.

Exporta:
  render_module_2()               -> layout completo
  register_callbacks_module_2(app) -> registra todos los callbacks
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from dash import Input, Output, State, dcc, html, no_update, callback_context

from components.chart_config import (
    COLORS as C,
    COUNTRY_COLORS,
    get_base_layout,
    get_time_range_buttons,
)
from components.common import (
    create_empty_state,
    create_metric_card,
    create_section_header,
)
from config import COLORS
from modules.data_helpers import (
    format_value,
    get_change,
    get_latest_value,
    get_series,
    get_world_bank_indicator,
    get_country_comparison,
    time_ago,
)

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTES
# ══════════════════════════════════════════════════════════════════════════════

# ── IDs en BD ─────────────────────────────────────────────────────────────────

# FRED
ID_GDP_GROWTH_US    = "fred_gdp_growth_us"       # PIB Real EE.UU. (anualizado %)
ID_INDPRO_US        = "fred_indpro_us"            # Producción Industrial (índice)
ID_RETAIL_US        = "fred_retail_sales_us"      # Ventas al por menor
ID_CONF_US          = "fred_consumer_conf_us"     # Confianza consumidor Michigan
ID_TRADE_US         = "fred_trade_balance_us"     # Balanza comercial
ID_DEBT_GDP_US      = "fred_debt_gdp_us"          # Deuda federal % PIB
ID_DEFICIT_GDP_US   = "fred_deficit_gdp_us"       # Déficit fiscal % PIB
ID_CURR_ACC_US      = "fred_current_account_us"   # Cuenta corriente

# World Bank (World aggregate)
ID_WB_GDP_WLD       = "wb_gdp_growth_wld"

# Eurostat (PIB trimestral YoY)
ID_ESTAT_GDP_EA     = "estat_gdp_q_clv_pch_sm_ea20"
ID_ESTAT_GDP_DE     = "estat_gdp_q_clv_pch_sm_de"
ID_ESTAT_GDP_FR     = "estat_gdp_q_clv_pch_sm_fr"
ID_ESTAT_GDP_ES     = "estat_gdp_q_clv_pch_sm_es"
ID_ESTAT_GDP_IT     = "estat_gdp_q_clv_pch_sm_it"
ID_ESTAT_GDP_PL     = "estat_gdp_q_clv_pch_sm_pl"
ID_ESTAT_GDP_NL     = "estat_gdp_q_clv_pch_sm_nl"
ID_ESTAT_GDP_PT     = "estat_gdp_q_clv_pch_sm_pt"
ID_ESTAT_GDP_GR     = "estat_gdp_q_clv_pch_sm_gr"
ID_ESTAT_GDP_SE     = "estat_gdp_q_clv_pch_sm_se"

# Eurostat industrial production YoY
ID_ESTAT_IND_DE     = "estat_indpro_pch_sm_de"
ID_ESTAT_IND_FR     = "estat_indpro_pch_sm_fr"
ID_ESTAT_IND_ES     = "estat_indpro_pch_sm_es"
ID_ESTAT_IND_IT     = "estat_indpro_pch_sm_it"
ID_ESTAT_IND_PL     = "estat_indpro_pch_sm_pl"

# Eurostat consumer confidence
ID_ESTAT_CONF_EA    = "estat_consconf_bs_csmci_ea20"
ID_ESTAT_CONF_DE    = "estat_consconf_bs_csmci_de"
ID_ESTAT_CONF_FR    = "estat_consconf_bs_csmci_fr"
ID_ESTAT_CONF_ES    = "estat_consconf_bs_csmci_es"
ID_ESTAT_CONF_IT    = "estat_consconf_bs_csmci_it"


# ── Estilos de tabs (consistentes con módulos 3 y 5) ─────────────────────────

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


# ── Mapa de indicadores → WB short_name ──────────────────────────────────────

CHOROPLETH_INDICATORS = {
    "gdp_growth":        {"label": "Crecimiento PIB real (%)",          "wb": "gdp_growth",    "higher_better": True,  "scale": "RdYlGn",   "unit": "%"},
    "gdp_per_capita":    {"label": "PIB per cápita PPP (USD)",          "wb": "gdp_pc_ppp",    "higher_better": True,  "scale": "RdYlGn",   "unit": "USD"},
    "inflation":         {"label": "Inflación IPC (% YoY)",             "wb": "cpi_inflation", "higher_better": False, "scale": "RdYlGn_r", "unit": "%"},
    "unemployment":      {"label": "Desempleo (%)",                     "wb": "unemployment",  "higher_better": False, "scale": "RdYlGn_r", "unit": "%"},
    "youth_unemployment":{"label": "Desempleo juvenil (%)",             "wb": "youth_unemp",   "higher_better": False, "scale": "RdYlGn_r", "unit": "%"},
    "debt_gdp":          {"label": "Deuda pública (% PIB)",             "wb": "gov_debt_pct",  "higher_better": False, "scale": "RdYlGn_r", "unit": "%"},
    "deficit_gdp":       {"label": "Déficit fiscal (% PIB)",            "wb": "fiscal_balance","higher_better": True,  "scale": "RdYlGn",   "unit": "%"},
    "fertility":         {"label": "Tasa de fertilidad (hijos/mujer)",  "wb": "fertility",     "higher_better": None,  "scale": "RdYlBu",   "unit": ""},
    "population_growth": {"label": "Crecimiento población (%)",         "wb": "pop_growth",    "higher_better": None,  "scale": "RdYlGn",   "unit": "%"},
    "dependency_ratio":  {"label": "Ratio dependencia ancianos",        "wb": "old_dep_ratio", "higher_better": False, "scale": "RdYlGn_r", "unit": ""},
    "current_account":   {"label": "Balanza cuenta corriente (% PIB)",  "wb": "curr_account",  "higher_better": None,  "scale": "RdBu",     "unit": "%"},
    "trade_openness":    {"label": "Apertura comercial (% PIB)",        "wb": "trade_pct",     "higher_better": True,  "scale": "RdYlGn",   "unit": "%"},
    "gini":              {"label": "Índice de Gini (desigualdad)",       "wb": "gini",          "higher_better": False, "scale": "RdYlGn_r", "unit": ""},
    "rd_spending":       {"label": "Gasto en I+D (% PIB)",              "wb": "rd_spending",   "higher_better": True,  "scale": "RdYlGn",   "unit": "%"},
    "internet_users":    {"label": "Usuarios de internet (%)",          "wb": "internet_users","higher_better": True,  "scale": "RdYlGn",   "unit": "%"},
}

CHOROPLETH_GROUPS = [
    {"label": "Crecimiento", "options": ["gdp_growth", "gdp_per_capita"]},
    {"label": "Precios",     "options": ["inflation"]},
    {"label": "Empleo",      "options": ["unemployment", "youth_unemployment"]},
    {"label": "Deuda y Fiscal", "options": ["debt_gdp", "deficit_gdp"]},
    {"label": "Demografía",  "options": ["fertility", "population_growth", "dependency_ratio"]},
    {"label": "Comercio",    "options": ["current_account", "trade_openness"]},
    {"label": "Desarrollo",  "options": ["gini", "rd_spending", "internet_users"]},
]


# Países especiales siempre visibles en Tab 1
SPECIAL_COUNTRIES_ISO3 = ["USA", "DEU", "ESP", "CHN", "BRA"]

# Países para Tab 5 (ordenados por PIB nominal aprox.)
COMPARISON_COUNTRIES_ISO3 = [
    "USA", "CHN", "DEU", "JPN", "IND", "GBR", "FRA", "ITA", "BRA", "CAN",
    "KOR", "AUS", "ESP", "MEX", "RUS", "NLD", "CHE", "POL", "TUR", "ARG",
    "ZAF", "SAU", "EGY", "IDN", "NGA",
]

# Colores de región para bubble chart
REGION_COLORS = {
    "Americas":   "#3b82f6",
    "Europe":     "#10b981",
    "Asia":       "#ef4444",
    "Lat. Am.":   "#f97316",
    "Africa":     "#8b5cf6",
    "Oceania":    "#06b6d4",
    "Middle East":"#f59e0b",
}

ISO3_REGIONS = {
    "USA": "Americas", "CAN": "Americas",
    "GBR": "Europe", "DEU": "Europe", "FRA": "Europe", "ITA": "Europe",
    "ESP": "Europe", "NLD": "Europe", "CHE": "Europe", "SWE": "Europe",
    "NOR": "Europe", "POL": "Europe", "PRT": "Europe", "GRC": "Europe",
    "CHN": "Asia", "JPN": "Asia", "KOR": "Asia", "IND": "Asia",
    "IDN": "Asia", "THA": "Asia", "VNM": "Asia", "SGP": "Asia",
    "MYS": "Asia", "BGD": "Asia", "PAK": "Asia",
    "BRA": "Lat. Am.", "MEX": "Lat. Am.", "ARG": "Lat. Am.",
    "COL": "Lat. Am.", "CHL": "Lat. Am.", "PER": "Lat. Am.",
    "AUS": "Oceania",
    "ZAF": "Africa", "NGA": "Africa", "EGY": "Africa",
    "SAU": "Middle East", "TUR": "Middle East", "RUS": "Europe",
}

# Nombres en español
ISO3_NAMES = {
    "USA": "🇺🇸 EE.UU.", "CHN": "🇨🇳 China", "DEU": "🇩🇪 Alemania",
    "JPN": "🇯🇵 Japón", "IND": "🇮🇳 India", "GBR": "🇬🇧 Reino Unido",
    "FRA": "🇫🇷 Francia", "ITA": "🇮🇹 Italia", "BRA": "🇧🇷 Brasil",
    "CAN": "🇨🇦 Canadá", "KOR": "🇰🇷 Corea del Sur", "AUS": "🇦🇺 Australia",
    "ESP": "🇪🇸 España", "MEX": "🇲🇽 México", "RUS": "🇷🇺 Rusia",
    "NLD": "🇳🇱 Países Bajos", "CHE": "🇨🇭 Suiza", "POL": "🇵🇱 Polonia",
    "TUR": "🇹🇷 Turquía", "ARG": "🇦🇷 Argentina", "ZAF": "🇿🇦 Sudáfrica",
    "SAU": "🇸🇦 Arabia Saudí", "EGY": "🇪🇬 Egipto", "IDN": "🇮🇩 Indonesia",
    "NGA": "🇳🇬 Nigeria",
}


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _safe(val, fmt=".1f", suffix=""):
    if val is None:
        return "—"
    try:
        return f"{val:{fmt}}{suffix}"
    except Exception:
        return "—"


def _color_gdp(val: Optional[float]) -> str:
    if val is None:
        return COLORS["text_muted"]
    if val >= 3:
        return C["positive"]
    if val >= 0:
        return COLORS["text"]
    return C["negative"]


def _pct_str(val: Optional[float], sign: bool = True) -> str:
    if val is None:
        return "—"
    s = "+" if sign and val > 0 else ""
    return f"{s}{val:.1f}%"


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


def _build_header_metrics() -> html.Div:
    """Fila de 6 métricas siempre visibles sobre las tabs."""

    # 1. Crecimiento PIB Mundial (World Bank)
    wb_wld, ts_wld = get_latest_value(ID_WB_GDP_WLD)
    wb_wld_prev_val = None
    if wb_wld is not None:
        df_wld = get_series(ID_WB_GDP_WLD, days=800)
        if len(df_wld) >= 2:
            df_wld = df_wld.sort_values("timestamp")
            wb_wld_prev_val = float(df_wld.iloc[-2]["value"])
    wld_chg = (wb_wld - wb_wld_prev_val) if (wb_wld is not None and wb_wld_prev_val is not None) else None
    m1 = _compact_metric(
        "PIB MUNDIAL",
        _safe(wb_wld, ".1f", "%"),
        _pct_str(wld_chg, True) + " vs año ant." if wld_chg is not None else "—",
        _color_gdp(wld_chg),
        "Anual · Banco Mundial",
    )

    # 2. PIB EE.UU. trimestral (FRED)
    us_gdp, ts_us = get_latest_value(ID_GDP_GROWTH_US)
    us_gdp_prev = None
    df_us_gdp = get_series(ID_GDP_GROWTH_US, days=400)
    if len(df_us_gdp) >= 2:
        df_us_gdp = df_us_gdp.sort_values("timestamp")
        us_gdp_prev = float(df_us_gdp.iloc[-2]["value"])
    us_gdp_chg = (us_gdp - us_gdp_prev) if (us_gdp is not None and us_gdp_prev is not None) else None
    m2 = _compact_metric(
        "PIB EE.UU.",
        _safe(us_gdp, ".1f", "%"),
        _pct_str(us_gdp_chg) + " vs trim. ant." if us_gdp_chg is not None else "—",
        _color_gdp(us_gdp_chg),
        "Trimestral · FRED",
    )

    # 3. PIB Eurozona trimestral (Eurostat)
    ea_gdp, ts_ea = get_latest_value(ID_ESTAT_GDP_EA)
    ea_gdp_prev = None
    df_ea_gdp = get_series(ID_ESTAT_GDP_EA, days=400)
    if len(df_ea_gdp) >= 2:
        df_ea_gdp = df_ea_gdp.sort_values("timestamp")
        ea_gdp_prev = float(df_ea_gdp.iloc[-2]["value"])
    ea_gdp_chg = (ea_gdp - ea_gdp_prev) if (ea_gdp is not None and ea_gdp_prev is not None) else None
    m3 = _compact_metric(
        "PIB EUROZONA",
        _safe(ea_gdp, ".1f", "%"),
        _pct_str(ea_gdp_chg) + " vs trim. ant." if ea_gdp_chg is not None else "—",
        _color_gdp(ea_gdp_chg),
        "Trimestral · Eurostat",
    )

    # 4. Producción industrial EE.UU. YoY (INDPRO)
    df_indpro = get_series(ID_INDPRO_US, days=400)
    indpro_yoy = None
    indpro_chg = None
    if len(df_indpro) >= 13:
        df_indpro = df_indpro.sort_values("timestamp")
        last_val = float(df_indpro.iloc[-1]["value"])
        prev_12_val = float(df_indpro.iloc[-13]["value"])
        if prev_12_val != 0:
            indpro_yoy = (last_val / prev_12_val - 1) * 100
        if len(df_indpro) >= 14:
            prev_val = float(df_indpro.iloc[-2]["value"])
            prev_12_prev = float(df_indpro.iloc[-14]["value"])
            if prev_12_prev != 0:
                prev_yoy = (prev_val / prev_12_prev - 1) * 100
                if indpro_yoy is not None:
                    indpro_chg = indpro_yoy - prev_yoy
    m4 = _compact_metric(
        "PROD. INDUSTRIAL EE.UU.",
        _safe(indpro_yoy, ".1f", "%"),
        _pct_str(indpro_chg) + " vs mes ant." if indpro_chg is not None else "—",
        _color_gdp(indpro_chg),
        "Mensual · FRED",
    )

    # 5. Ventas al por menor EE.UU. YoY
    df_retail = get_series(ID_RETAIL_US, days=400)
    retail_yoy = None
    retail_chg = None
    if len(df_retail) >= 13:
        df_retail = df_retail.sort_values("timestamp")
        last_r = float(df_retail.iloc[-1]["value"])
        prev_12_r = float(df_retail.iloc[-13]["value"])
        if prev_12_r != 0:
            retail_yoy = (last_r / prev_12_r - 1) * 100
        if len(df_retail) >= 14:
            prev_r = float(df_retail.iloc[-2]["value"])
            prev_12_prev_r = float(df_retail.iloc[-14]["value"])
            if prev_12_prev_r != 0:
                prev_retail_yoy = (prev_r / prev_12_prev_r - 1) * 100
                if retail_yoy is not None:
                    retail_chg = retail_yoy - prev_retail_yoy
    m5 = _compact_metric(
        "VENTAS MINORISTAS EE.UU.",
        _safe(retail_yoy, ".1f", "%"),
        _pct_str(retail_chg) + " vs mes ant." if retail_chg is not None else "—",
        _color_gdp(retail_chg),
        "Mensual · FRED",
    )

    # 6. Confianza consumidor EE.UU. (Michigan)
    conf_val, ts_conf = get_latest_value(ID_CONF_US)
    conf_prev = None
    df_conf = get_series(ID_CONF_US, days=100)
    if len(df_conf) >= 2:
        df_conf = df_conf.sort_values("timestamp")
        conf_prev = float(df_conf.iloc[-2]["value"])
    conf_chg = (conf_val - conf_prev) if (conf_val is not None and conf_prev is not None) else None
    m6 = _compact_metric(
        "CONFIANZA CONSUMIDOR EE.UU.",
        _safe(conf_val, ".1f"),
        _pct_str(conf_chg) + " vs mes ant." if conf_chg is not None else "—",
        C["positive"] if (conf_chg or 0) > 0 else C["negative"],
        "Mensual · Michigan",
    )

    return html.Div(
        [m1, m2, m3, m4, m5, m6],
        style={
            "display": "flex",
            "gap": "10px",
            "flexWrap": "wrap",
            "marginBottom": "16px",
        },
        id="m2-header-metrics",
    )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — MAPA MUNDIAL INTERACTIVO
# ══════════════════════════════════════════════════════════════════════════════

def _build_indicator_options():
    opts = []
    for group in CHOROPLETH_GROUPS:
        for key in group["options"]:
            meta = CHOROPLETH_INDICATORS[key]
            opts.append({"label": f"  {meta['label']}", "value": key, "group": group["label"]})
    return opts


def _build_tab1() -> html.Div:
    return html.Div(
        [
            # Controles
            html.Div(
                [
                    html.Div(
                        [
                            html.Label("Indicador", style={"fontSize": "0.75rem", "color": COLORS["text_muted"], "marginBottom": "4px"}),
                            dcc.Dropdown(
                                id="m2-map-indicator",
                                options=_build_indicator_options(),
                                value="gdp_growth",
                                clearable=False,
                                style={"minWidth": "280px"},
                                className="dash-dropdown-dark",
                            ),
                        ],
                        style={"flex": "2"},
                    ),
                    html.Div(
                        [
                            html.Label("Año", style={"fontSize": "0.75rem", "color": COLORS["text_muted"], "marginBottom": "4px"}),
                            dcc.Dropdown(
                                id="m2-map-year",
                                options=[{"label": str(y), "value": y} for y in range(2023, 1999, -1)],
                                value=2022,
                                clearable=False,
                                style={"minWidth": "100px"},
                                className="dash-dropdown-dark",
                            ),
                        ],
                        style={"flex": "1"},
                    ),
                ],
                style={"display": "flex", "gap": "16px", "marginBottom": "12px", "alignItems": "flex-end"},
            ),

            # Mapa
            dcc.Loading(
                dcc.Graph(
                    id="m2-choropleth-map",
                    config={"displayModeBar": False, "scrollZoom": False},
                    style={"height": "520px"},
                ),
                type="circle",
                color=COLORS["accent"],
            ),

            # Panel de datos debajo del mapa
            html.Div(id="m2-map-data-panel", style={"marginTop": "12px"}),
        ],
        style={"padding": "16px"},
    )


def _build_choropleth(indicator_key: str, year: int) -> go.Figure:
    """Construye el mapa choroplético con los datos del WB."""
    meta = CHOROPLETH_INDICATORS.get(indicator_key, CHOROPLETH_INDICATORS["gdp_growth"])
    wb_short = meta["wb"]

    df = get_world_bank_indicator(wb_short, year=year)
    if df.empty:
        # Intentar año anterior
        for fallback_yr in range(year - 1, max(year - 5, 1999), -1):
            df = get_world_bank_indicator(wb_short, year=fallback_yr)
            if not df.empty:
                year = fallback_yr
                break

    title_text = f"{meta['label']} · {year}"

    fig = go.Figure()

    if df.empty:
        # Mapa vacío con mensaje
        fig.add_trace(go.Choropleth(
            locations=[],
            z=[],
            colorscale=meta["scale"],
            locationmode="ISO-3",
        ))
    else:
        df = df.copy()
        df["rank"] = df["value"].rank(ascending=False, na_option="bottom").astype(int)
        n_countries = len(df)

        hover_texts = []
        for _, row in df.iterrows():
            iso3 = row["country_iso3"]
            val = row["value"]
            rank = int(row["rank"])
            name = ISO3_NAMES.get(iso3, iso3)
            unit = meta["unit"]
            if unit == "%":
                val_str = f"{val:.1f}%"
            elif unit == "USD":
                val_str = f"${val:,.0f}"
            else:
                val_str = f"{val:.1f}"
            hover_texts.append(
                f"<b>{name}</b><br>"
                f"{meta['label']}: {val_str}<br>"
                f"Ranking: #{rank} de {n_countries}"
            )

        # Color scale adaptado
        colorscale = meta["scale"]
        zmid = None
        if indicator_key == "current_account":
            zmid = 0

        kw = {}
        if zmid is not None:
            kw["zmid"] = zmid

        fig.add_trace(go.Choropleth(
            locations=df["country_iso3"],
            z=df["value"],
            locationmode="ISO-3",
            colorscale=colorscale,
            text=hover_texts,
            hovertemplate="%{text}<extra></extra>",
            colorbar=dict(
                bgcolor="#111827",
                bordercolor="#1f2937",
                tickfont={"color": "#9ca3af", "size": 10},
                title=dict(text=meta["unit"] or "", font={"color": "#9ca3af", "size": 10}),
                thickness=14,
                len=0.7,
            ),
            marker=dict(line=dict(color="#1f2937", width=0.5)),
            **kw,
        ))

    fig.update_layout(
        title=dict(
            text=title_text,
            font={"color": "#e5e7eb", "size": 13},
            x=0.0, xanchor="left", pad={"l": 4},
        ),
        geo=dict(
            projection_type="natural earth",
            showframe=False,
            showcoastlines=True,
            coastlinecolor="#1f2937",
            showland=True,
            landcolor="#111827",
            showocean=True,
            oceancolor="#0d1b2a",
            showcountries=True,
            countrycolor="#1f2937",
            bgcolor="#0a0e1a",
        ),
        paper_bgcolor="#0a0e1a",
        plot_bgcolor="#0a0e1a",
        font={"color": "#e5e7eb", "family": "'Inter', 'Segoe UI', system-ui, sans-serif", "size": 12},
        margin={"l": 0, "r": 0, "t": 40, "b": 0},
        height=520,
    )

    return fig


def _build_map_data_panel(indicator_key: str, year: int) -> html.Div:
    """Panel debajo del mapa con top/bottom 5 y países especiales."""
    meta = CHOROPLETH_INDICATORS.get(indicator_key, CHOROPLETH_INDICATORS["gdp_growth"])
    wb_short = meta["wb"]
    df = get_world_bank_indicator(wb_short, year=year)

    if df.empty:
        return create_empty_state("Sin datos para este indicador y año")

    df = df.copy().dropna(subset=["value"])
    df = df.sort_values("value", ascending=False).reset_index(drop=True)
    n = len(df)

    def _val_fmt(v):
        unit = meta["unit"]
        if unit == "%":
            return f"{v:.1f}%"
        if unit == "USD":
            return f"${v:,.0f}"
        return f"{v:.2f}"

    def _country_row(iso3: str, val: float, rank: int, highlight: bool = False) -> html.Div:
        name = ISO3_NAMES.get(iso3, iso3)
        bar_pct = 0
        if df["value"].max() != df["value"].min():
            bar_pct = int((val - df["value"].min()) / (df["value"].max() - df["value"].min()) * 100)
        return html.Div(
            [
                html.Div(f"#{rank}", style={"width": "30px", "color": COLORS["text_muted"], "fontSize": "0.72rem"}),
                html.Div(name, style={"flex": "1", "fontSize": "0.78rem",
                                      "fontWeight": "600" if highlight else "400"}),
                html.Div(_val_fmt(val), style={"fontSize": "0.78rem", "fontWeight": "600",
                                               "color": COLORS["accent"] if highlight else COLORS["text"]}),
                html.Div(
                    html.Div(style={"width": f"{bar_pct}%", "height": "4px",
                                    "background": COLORS["accent"],
                                    "borderRadius": "2px"}),
                    style={"width": "80px", "background": COLORS["border"],
                           "borderRadius": "2px", "marginLeft": "8px"},
                ),
            ],
            style={"display": "flex", "alignItems": "center", "gap": "8px",
                   "padding": "4px 0",
                   "borderBottom": f"1px solid {COLORS['border']}"},
        )

    top5 = df.head(5)
    bot5 = df.tail(5).iloc[::-1]

    # Países especiales
    special_rows = []
    for iso3 in SPECIAL_COUNTRIES_ISO3:
        sub = df[df["country_iso3"] == iso3]
        if not sub.empty:
            idx = sub.index[0]
            rank = idx + 1
            val = float(sub.iloc[0]["value"])
            special_rows.append(_country_row(iso3, val, rank, highlight=True))

    top5_rows = [_country_row(row["country_iso3"], float(row["value"]), i + 1) for i, (_, row) in enumerate(top5.iterrows())]
    bot5_rows = [_country_row(row["country_iso3"], float(row["value"]), n - i) for i, (_, row) in enumerate(bot5.iterrows())]

    higher_better = meta["higher_better"]
    if higher_better is True:
        top_label, bot_label = "Top 5 — Mayor valor", "Bottom 5 — Menor valor"
    elif higher_better is False:
        top_label, bot_label = "Top 5 — Más alto (peor)", "Bottom 5 — Más bajo (mejor)"
    else:
        top_label, bot_label = "Top 5 — Mayor valor", "Bottom 5 — Menor valor"

    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(top_label, style={"fontSize": "0.72rem", "color": COLORS["text_muted"],
                                                        "fontWeight": "600", "marginBottom": "6px"}),
                            *top5_rows,
                        ],
                        style={"flex": "1", "minWidth": "220px"},
                    ),
                    html.Div(
                        [
                            html.Div(bot_label, style={"fontSize": "0.72rem", "color": COLORS["text_muted"],
                                                        "fontWeight": "600", "marginBottom": "6px"}),
                            *bot5_rows,
                        ],
                        style={"flex": "1", "minWidth": "220px"},
                    ),
                    html.Div(
                        [html.Div("Países de referencia", style={"fontSize": "0.72rem",
                                                                   "color": COLORS["text_muted"],
                                                                   "fontWeight": "600", "marginBottom": "6px"})]
                        + (special_rows if special_rows else [create_empty_state("Sin datos")]),
                        style={"flex": "1", "minWidth": "220px"},
                    ),
                ],
                style={"display": "flex", "gap": "24px", "flexWrap": "wrap"},
            ),
            html.Div(
                f"Fuente: Banco Mundial · {n} países con datos · Año: {year}",
                style={"fontSize": "0.68rem", "color": COLORS["text_label"], "marginTop": "8px"},
            ),
        ],
        style={
            "background": COLORS["card_bg"],
            "border": f"1px solid {COLORS['border']}",
            "borderRadius": "6px",
            "padding": "12px 16px",
        },
    )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — EE.UU. EN DETALLE
# ══════════════════════════════════════════════════════════════════════════════

def _build_tab2() -> html.Div:
    return html.Div(
        [
            # 2.1 PIB EE.UU. histórico
            create_section_header("PIB EE.UU. — Crecimiento trimestral", "Tasa anualizada (FRED: A191RL1Q225SBEA)"),
            dcc.Loading(
                dcc.Graph(id="m2-us-gdp-chart", config={"displayModeBar": False}),
                type="circle", color=COLORS["accent"],
            ),
            html.Div(id="m2-us-gdp-table", style={"marginTop": "8px", "marginBottom": "24px"}),

            # 2.2 Grid 2x2 de actividad
            create_section_header("Indicadores de Actividad en Tiempo Real"),
            dbc.Row(
                [
                    dbc.Col(
                        dcc.Loading(dcc.Graph(id="m2-us-indpro-chart", config={"displayModeBar": False}),
                                    type="circle", color=COLORS["accent"]),
                        width=6,
                    ),
                    dbc.Col(
                        dcc.Loading(dcc.Graph(id="m2-us-retail-chart", config={"displayModeBar": False}),
                                    type="circle", color=COLORS["accent"]),
                        width=6,
                    ),
                    dbc.Col(
                        dcc.Loading(dcc.Graph(id="m2-us-conf-chart", config={"displayModeBar": False}),
                                    type="circle", color=COLORS["accent"]),
                        width=6,
                    ),
                    dbc.Col(
                        dcc.Loading(dcc.Graph(id="m2-us-trade-chart", config={"displayModeBar": False}),
                                    type="circle", color=COLORS["accent"]),
                        width=6,
                    ),
                ],
                className="g-3",
            ),

            # 2.3 Ciclo económico
            create_section_header(
                "Ciclo Económico EE.UU.",
                "Posición relativa en el ciclo: producción industrial vs. evolución del desempleo",
                last_updated=None,
            ),
            dbc.Row(
                [
                    dbc.Col(
                        dcc.Loading(
                            dcc.Graph(id="m2-us-cycle-chart", config={"displayModeBar": False}),
                            type="circle", color=COLORS["accent"],
                        ),
                        width=7,
                    ),
                    dbc.Col(
                        html.Div(id="m2-us-cycle-text", style={"padding": "16px"}),
                        width=5,
                    ),
                ],
                className="g-3",
            ),

            # Selector de rango (compartido por los gráficos de la tab 2)
            html.Div(
                [
                    html.Label("Período:", style={"fontSize": "0.72rem", "color": COLORS["text_muted"], "marginRight": "8px"}),
                    dcc.RadioItems(
                        id="m2-us-range",
                        options=[
                            {"label": " 1A", "value": 365},
                            {"label": " 2A", "value": 730},
                            {"label": " 5A", "value": 1825},
                            {"label": " MÁX", "value": 9999},
                        ],
                        value=1825,
                        inline=True,
                        labelStyle={"marginRight": "12px", "fontSize": "0.78rem"},
                        style={"color": COLORS["text_muted"]},
                    ),
                ],
                style={"display": "flex", "alignItems": "center", "marginTop": "16px", "marginBottom": "4px"},
            ),
        ],
        style={"padding": "16px"},
    )


def _build_us_gdp_chart(days: int = 1825) -> go.Figure:
    df = get_series(ID_GDP_GROWTH_US, days=days)
    fig = go.Figure()
    if df.empty:
        return fig

    df = df.sort_values("timestamp")
    colors = [C["negative"] if v < 0 else C["positive"] for v in df["value"]]

    fig.add_trace(go.Bar(
        x=df["timestamp"],
        y=df["value"],
        marker_color=colors,
        name="Crecimiento PIB",
        hovertemplate="<b>%{x|%Y-Q%q}</b><br>%{y:.1f}%<extra></extra>",
    ))
    fig.add_hline(y=0, line_color="#374151", line_width=1)

    layout = get_base_layout("Crecimiento PIB Real EE.UU. (% anualizado)", height=280)
    layout["yaxis"]["ticksuffix"] = "%"
    layout["margin"] = {"l": 50, "r": 20, "t": 40, "b": 30}
    fig.update_layout(**layout)
    return fig


def _build_us_gdp_table(days: int = 1825) -> html.Div:
    df = get_series(ID_GDP_GROWTH_US, days=days)
    if df.empty:
        return create_empty_state("Sin datos trimestrales del PIB EE.UU.")

    df = df.sort_values("timestamp", ascending=False).head(8)
    rows = []
    for _, row in df.iterrows():
        val = float(row["value"])
        color = C["positive"] if val > 0 else C["negative"]
        ts = row["timestamp"]
        try:
            q = (ts.month - 1) // 3 + 1
            label = f"{ts.year} Q{q}"
        except Exception:
            label = str(ts)[:7]
        rows.append(
            html.Tr([
                html.Td(label, style={"color": COLORS["text_muted"], "fontSize": "0.75rem"}),
                html.Td(f"{val:+.1f}%", style={"color": color, "fontWeight": "600", "fontSize": "0.82rem"}),
            ])
        )

    return html.Div(
        html.Table(
            [
                html.Thead(html.Tr([
                    html.Th("Trimestre", style={"fontSize": "0.72rem", "color": COLORS["text_label"]}),
                    html.Th("Crecimiento PIB", style={"fontSize": "0.72rem", "color": COLORS["text_label"]}),
                ])),
                html.Tbody(rows),
            ],
            className="data-table",
        ),
        style={"overflowX": "auto"},
    )


def _build_indpro_chart(days: int = 1825) -> go.Figure:
    df = get_series(ID_INDPRO_US, days=days + 400)
    fig = go.Figure()
    if len(df) < 13:
        return fig

    df = df.sort_values("timestamp")
    df["yoy"] = df["value"].pct_change(12) * 100
    df = df.dropna(subset=["yoy"]).tail(days // 30 + 12)

    fig.add_trace(go.Scatter(
        x=df["timestamp"], y=df["yoy"],
        name="Prod. Industrial YoY",
        line=dict(color=C["primary"], width=2),
        fill="tozeroy",
        fillcolor="rgba(59,130,246,0.12)",
        hovertemplate="%{x|%b %Y}: %{y:.1f}%<extra></extra>",
    ))
    fig.add_hline(y=0, line_color="#374151", line_width=1)

    layout = get_base_layout("Producción Industrial EE.UU. (YoY %)", height=260)
    layout["yaxis"]["ticksuffix"] = "%"
    layout["margin"] = {"l": 50, "r": 10, "t": 40, "b": 30}
    fig.update_layout(**layout)
    return fig


def _build_retail_chart(days: int = 1825) -> go.Figure:
    df = get_series(ID_RETAIL_US, days=days + 400)
    fig = go.Figure()
    if len(df) < 13:
        return fig

    df = df.sort_values("timestamp")
    df["yoy"] = df["value"].pct_change(12) * 100
    df = df.dropna(subset=["yoy"]).tail(days // 30 + 12)

    fig.add_trace(go.Scatter(
        x=df["timestamp"], y=df["yoy"],
        name="Ventas Minoristas YoY",
        line=dict(color=C["positive"], width=2),
        fill="tozeroy",
        fillcolor="rgba(16,185,129,0.12)",
        hovertemplate="%{x|%b %Y}: %{y:.1f}%<extra></extra>",
    ))
    fig.add_hline(y=0, line_color="#374151", line_width=1)

    layout = get_base_layout("Ventas al por Menor EE.UU. (YoY %)", height=260)
    layout["yaxis"]["ticksuffix"] = "%"
    layout["margin"] = {"l": 50, "r": 10, "t": 40, "b": 30}
    fig.update_layout(**layout)
    return fig


def _build_conf_chart(days: int = 1825) -> go.Figure:
    df = get_series(ID_CONF_US, days=days)
    fig = go.Figure()
    if df.empty:
        return fig

    df = df.sort_values("timestamp")

    fig.add_hrect(y0=100, y1=df["value"].max() * 1.05 if not df.empty else 120,
                  fillcolor="rgba(16,185,129,0.06)", line_width=0)
    fig.add_hrect(y0=80, y1=100, fillcolor="rgba(245,158,11,0.06)", line_width=0)
    fig.add_hrect(y0=df["value"].min() * 0.95 if not df.empty else 40, y1=80,
                  fillcolor="rgba(239,68,68,0.06)", line_width=0)
    fig.add_hline(y=100, line_dash="dash", line_color="#374151", line_width=1)

    fig.add_trace(go.Scatter(
        x=df["timestamp"], y=df["value"],
        name="Confianza",
        line=dict(color=C["gold"], width=2),
        hovertemplate="%{x|%b %Y}: %{y:.1f}<extra></extra>",
    ))

    layout = get_base_layout("Confianza Consumidor EE.UU. (Michigan)", height=260)
    layout["margin"] = {"l": 50, "r": 10, "t": 40, "b": 30}
    fig.update_layout(**layout)
    return fig


def _build_trade_chart(days: int = 1825) -> go.Figure:
    df = get_series(ID_TRADE_US, days=days)
    fig = go.Figure()
    if df.empty:
        return fig

    df = df.sort_values("timestamp")

    fig.add_trace(go.Scatter(
        x=df["timestamp"], y=df["value"],
        name="Balanza comercial",
        line=dict(color=C["negative"], width=2),
        fill="tozeroy",
        fillcolor="rgba(239,68,68,0.12)",
        hovertemplate="%{x|%b %Y}: $%{y:,.0f}M<extra></extra>",
    ))
    fig.add_hline(y=0, line_color="#374151", line_width=1)

    if not df.empty:
        last_val = float(df.iloc[-1]["value"])
        fig.add_annotation(
            x=df.iloc[-1]["timestamp"], y=last_val,
            text=f" ${last_val/1000:.1f}B",
            showarrow=False,
            font={"color": C["negative"], "size": 10},
            xanchor="left",
        )

    layout = get_base_layout("Balanza Comercial EE.UU. (USD millones)", height=260)
    layout["margin"] = {"l": 60, "r": 30, "t": 40, "b": 30}
    fig.update_layout(**layout)
    return fig


def _build_cycle_chart() -> go.Figure:
    """Gráfico estilo 'reloj del ciclo económico'."""
    from modules.data_helpers import get_series
    from config import COLORS

    # INDPRO YoY como proxy de producción
    df_ip = get_series(ID_INDPRO_US, days=1000)
    # Consumer confidence como proxy de ciclo
    df_conf = get_series(ID_CONF_US, days=1000)

    fig = go.Figure()

    if len(df_ip) < 13 or df_conf.empty:
        fig.add_annotation(text="Sin datos suficientes para el gráfico del ciclo",
                           xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False,
                           font={"color": COLORS["text_muted"]})
        layout = get_base_layout("Ciclo Económico EE.UU.", height=380)
        fig.update_layout(**layout)
        return fig

    df_ip = df_ip.sort_values("timestamp")
    df_ip["yoy"] = df_ip["value"].pct_change(12) * 100
    df_ip = df_ip.dropna(subset=["yoy"])

    # Unir por mes
    df_ip["month"] = df_ip["timestamp"].dt.to_period("M")
    df_conf["month"] = df_conf["timestamp"].dt.to_period("M")
    df_merged = df_ip[["month", "yoy"]].merge(
        df_conf[["month", "value"]].rename(columns={"value": "conf"}),
        on="month", how="inner",
    ).tail(28)

    if df_merged.empty:
        layout = get_base_layout("Ciclo Económico EE.UU.", height=380)
        fig.update_layout(**layout)
        return fig

    # Eje X = producción industrial YoY, eje Y = confianza
    x = df_merged["yoy"].values
    y = df_merged["conf"].values

    # Determinar fase actual
    curr_x = x[-1]
    curr_y = y[-1]
    conf_ref = 90  # referencia neutral aproximada
    ip_ref = 0     # referencia en 0% YoY

    if curr_x >= ip_ref and curr_y >= conf_ref:
        phase = "Expansión"
        phase_color = C["positive"]
    elif curr_x >= ip_ref and curr_y < conf_ref:
        phase = "Auge tardío / Recalentamiento"
        phase_color = C["warning"]
    elif curr_x < ip_ref and curr_y < conf_ref:
        phase = "Contracción / Recesión"
        phase_color = C["negative"]
    else:
        phase = "Recuperación"
        phase_color = C["primary"]

    # Zonas de color
    x_range = [min(x) - 2, max(x) + 2]
    y_range = [min(y) - 5, max(y) + 5]

    fig.add_hrect(y0=conf_ref, y1=y_range[1], x0=ip_ref, x1=x_range[1],
                  fillcolor="rgba(16,185,129,0.06)", line_width=0)
    fig.add_hrect(y0=y_range[0], y1=conf_ref, x0=ip_ref, x1=x_range[1],
                  fillcolor="rgba(245,158,11,0.06)", line_width=0)
    fig.add_hrect(y0=y_range[0], y1=conf_ref, x0=x_range[0], x1=ip_ref,
                  fillcolor="rgba(239,68,68,0.06)", line_width=0)
    fig.add_hrect(y0=conf_ref, y1=y_range[1], x0=x_range[0], x1=ip_ref,
                  fillcolor="rgba(59,130,246,0.06)", line_width=0)

    # Líneas de referencia
    fig.add_hline(y=conf_ref, line_color="#374151", line_width=1, line_dash="dot")
    fig.add_vline(x=ip_ref, line_color="#374151", line_width=1, line_dash="dot")

    # Anotaciones de cuadrantes
    for ann_text, ann_x, ann_y in [
        ("Expansión", max(x), max(y)),
        ("Auge tardío", max(x), min(y) + 5),
        ("Recesión", min(x) + 2, min(y) + 5),
        ("Recuperación", min(x) + 2, max(y)),
    ]:
        fig.add_annotation(
            x=ann_x if ann_x == max(x) else min(x) + 2,
            y=ann_y,
            text=ann_text,
            showarrow=False,
            font={"size": 9, "color": COLORS["text_label"]},
            xanchor="right" if ann_x == max(x) else "left",
            yanchor="top" if ann_y == max(y) else "bottom",
        )

    # Trayectoria histórica (puntos)
    n_trail = len(x)
    trail_opacity = [0.2 + 0.6 * (i / n_trail) for i in range(n_trail)]
    dates = df_merged["month"].astype(str).values

    fig.add_trace(go.Scatter(
        x=x[:-1], y=y[:-1],
        mode="lines+markers",
        name="Trayectoria (últimos 24m)",
        line=dict(color="#6b7280", width=1.5, dash="dot"),
        marker=dict(
            size=[5] * (n_trail - 1),
            color=["rgba(107,114,128," + str(round(a, 2)) + ")" for a in trail_opacity[:-1]],
        ),
        text=[f"Mes: {d}" for d in dates[:-1]],
        hovertemplate="%{text}<br>Prod. Industrial: %{x:.1f}%<br>Confianza: %{y:.1f}<extra></extra>",
        showlegend=False,
    ))

    # Punto actual "HOY"
    fig.add_trace(go.Scatter(
        x=[curr_x], y=[curr_y],
        mode="markers+text",
        name="HOY",
        marker=dict(size=14, color=phase_color, symbol="circle",
                    line=dict(color="white", width=2)),
        text=["HOY"],
        textposition="top center",
        textfont=dict(color=phase_color, size=10, family="Inter"),
        hovertemplate=f"HOY<br>Prod. Industrial: {curr_x:.1f}%<br>Confianza: {curr_y:.1f}<extra></extra>",
    ))

    layout = get_base_layout("Ciclo Económico EE.UU.", height=380)
    layout["xaxis"]["title"] = {"text": "Producción Industrial (YoY %)", "font": {"color": "#9ca3af", "size": 10}}
    layout["yaxis"]["title"] = {"text": "Confianza del Consumidor", "font": {"color": "#9ca3af", "size": 10}}
    layout["xaxis"]["range"] = x_range
    layout["yaxis"]["range"] = y_range
    layout["margin"] = {"l": 55, "r": 20, "t": 40, "b": 45}
    layout["hovermode"] = "closest"
    layout["showlegend"] = False
    fig.update_layout(**layout)

    return fig, phase, phase_color


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — EUROPA EN DETALLE
# ══════════════════════════════════════════════════════════════════════════════

def _build_tab3() -> html.Div:
    return html.Div(
        [
            # 3.1 PIB europeo comparado
            create_section_header(
                "PIB Europeo — Crecimiento Comparado",
                "Variación interanual (YoY %) — Fuente: Eurostat",
            ),
            dcc.Loading(
                dcc.Graph(id="m2-eu-gdp-chart", config={"displayModeBar": False}),
                type="circle", color=COLORS["accent"],
            ),
            html.Div(id="m2-eu-gdp-table", style={"marginTop": "8px", "marginBottom": "24px"}),

            # 3.2 Producción industrial
            create_section_header(
                "Producción Industrial Europea",
                "Variación interanual (YoY %) — Fuente: Eurostat",
            ),
            dcc.Loading(
                dcc.Graph(id="m2-eu-indpro-chart", config={"displayModeBar": False}),
                type="circle", color=COLORS["accent"],
            ),

            # 3.3 Sentimiento consumidor
            create_section_header(
                "Confianza del Consumidor Europeo",
                "Indicador de confianza BCE/Eurostat (saldo de respuestas, SA)",
            ),
            dcc.Loading(
                dcc.Graph(id="m2-eu-conf-chart", config={"displayModeBar": False}),
                type="circle", color=COLORS["accent"],
            ),

            # 3.4 Balanzas comerciales (World Bank)
            create_section_header(
                "Balanzas Comerciales Europeas",
                "Cuenta corriente como % del PIB — Fuente: Banco Mundial",
            ),
            dcc.Loading(
                dcc.Graph(id="m2-eu-trade-chart", config={"displayModeBar": False}),
                type="circle", color=COLORS["accent"],
            ),

            # Selector de rango
            html.Div(
                [
                    html.Label("Período:", style={"fontSize": "0.72rem", "color": COLORS["text_muted"], "marginRight": "8px"}),
                    dcc.RadioItems(
                        id="m2-eu-range",
                        options=[
                            {"label": " 2A", "value": 730},
                            {"label": " 5A", "value": 1825},
                            {"label": " 10A", "value": 3650},
                            {"label": " MÁX", "value": 9999},
                        ],
                        value=1825,
                        inline=True,
                        labelStyle={"marginRight": "12px", "fontSize": "0.78rem"},
                        style={"color": COLORS["text_muted"]},
                    ),
                ],
                style={"display": "flex", "alignItems": "center", "marginTop": "16px", "marginBottom": "4px"},
            ),
        ],
        style={"padding": "16px"},
    )


def _build_eu_gdp_chart(days: int = 1825) -> go.Figure:
    EU_SERIES = [
        (ID_ESTAT_GDP_EA, "Eurozona", COUNTRY_COLORS.get("DEU", "#10b981")),
        (ID_ESTAT_GDP_DE, "Alemania", COUNTRY_COLORS["DEU"]),
        (ID_ESTAT_GDP_FR, "Francia",  COUNTRY_COLORS["FRA"]),
        (ID_ESTAT_GDP_ES, "España",   COUNTRY_COLORS["ESP"]),
        (ID_ESTAT_GDP_IT, "Italia",   COUNTRY_COLORS["ITA"]),
        (ID_ESTAT_GDP_PL, "Polonia",  "#a78bfa"),
    ]

    fig = go.Figure()
    any_data = False

    for sid, name, color in EU_SERIES:
        df = get_series(sid, days=days)
        if df.empty:
            continue
        any_data = True
        df = df.sort_values("timestamp")
        fig.add_trace(go.Scatter(
            x=df["timestamp"], y=df["value"],
            name=name, line=dict(color=color, width=2),
            hovertemplate=f"<b>{name}</b><br>%{{x|%Y-Q%q}}: %{{y:.1f}}%<extra></extra>",
        ))

    fig.add_hline(y=0, line_color="#374151", line_width=1, line_dash="dash")

    layout = get_base_layout("Crecimiento PIB Europa (YoY %)", height=320)
    layout["yaxis"]["ticksuffix"] = "%"
    layout["margin"] = {"l": 50, "r": 20, "t": 40, "b": 30}
    fig.update_layout(**layout)

    if not any_data:
        fig.add_annotation(text="Sin datos de Eurostat para el período seleccionado",
                           xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False,
                           font={"color": COLORS["text_muted"]})
    return fig


def _build_eu_gdp_table() -> html.Div:
    EU_TABLE = [
        (ID_ESTAT_GDP_EA, "🇪🇺 Eurozona", "ea20"),
        (ID_ESTAT_GDP_DE, "🇩🇪 Alemania", "de"),
        (ID_ESTAT_GDP_FR, "🇫🇷 Francia",  "fr"),
        (ID_ESTAT_GDP_ES, "🇪🇸 España",   "es"),
        (ID_ESTAT_GDP_IT, "🇮🇹 Italia",   "it"),
        (ID_ESTAT_GDP_PL, "🇵🇱 Polonia",  "pl"),
        (ID_ESTAT_GDP_NL, "🇳🇱 Países Bajos", "nl"),
        (ID_ESTAT_GDP_PT, "🇵🇹 Portugal", "pt"),
        (ID_ESTAT_GDP_GR, "🇬🇷 Grecia",   "gr"),
        (ID_ESTAT_GDP_SE, "🇸🇪 Suecia",   "se"),
    ]

    rows = []
    for sid, name, _ in EU_TABLE:
        val, ts = get_latest_value(sid)
        if val is None:
            continue
        color = C["positive"] if val > 0 else C["negative"]
        try:
            q = (ts.month - 1) // 3 + 1 if ts else "?"
            label = f"{ts.year} Q{q}" if ts else "—"
        except Exception:
            label = "—"
        rows.append((name, float(val), color, label))

    rows.sort(key=lambda r: r[1], reverse=True)

    if not rows:
        return create_empty_state("Sin datos de PIB europeo disponibles")

    return html.Div(
        html.Table(
            [
                html.Thead(html.Tr([
                    html.Th("País", style={"fontSize": "0.72rem", "color": COLORS["text_label"]}),
                    html.Th("Crec. PIB", style={"fontSize": "0.72rem", "color": COLORS["text_label"]}),
                    html.Th("Período", style={"fontSize": "0.72rem", "color": COLORS["text_label"]}),
                ])),
                html.Tbody([
                    html.Tr([
                        html.Td(name, style={"fontSize": "0.78rem"}),
                        html.Td(f"{val:+.1f}%", style={"color": color, "fontWeight": "600", "fontSize": "0.82rem"}),
                        html.Td(label, style={"color": COLORS["text_muted"], "fontSize": "0.72rem"}),
                    ])
                    for name, val, color, label in rows
                ]),
            ],
            className="data-table",
        ),
        style={"overflowX": "auto"},
    )


def _build_eu_indpro_chart(days: int = 1825) -> go.Figure:
    EU_IND = [
        (ID_ESTAT_IND_DE, "Alemania", COUNTRY_COLORS["DEU"]),
        (ID_ESTAT_IND_FR, "Francia",  COUNTRY_COLORS["FRA"]),
        (ID_ESTAT_IND_ES, "España",   COUNTRY_COLORS["ESP"]),
        (ID_ESTAT_IND_IT, "Italia",   COUNTRY_COLORS["ITA"]),
        (ID_ESTAT_IND_PL, "Polonia",  "#a78bfa"),
    ]

    fig = go.Figure()
    for sid, name, color in EU_IND:
        df = get_series(sid, days=days)
        if df.empty:
            continue
        df = df.sort_values("timestamp")
        fig.add_trace(go.Scatter(
            x=df["timestamp"], y=df["value"],
            name=name, line=dict(color=color, width=1.8),
            hovertemplate=f"<b>{name}</b><br>%{{x|%b %Y}}: %{{y:.1f}}%<extra></extra>",
        ))

    fig.add_hline(y=0, line_color="#374151", line_width=1, line_dash="dash")

    layout = get_base_layout("Producción Industrial Europea (YoY %)", height=300)
    layout["yaxis"]["ticksuffix"] = "%"
    layout["margin"] = {"l": 50, "r": 20, "t": 40, "b": 30}
    fig.update_layout(**layout)
    return fig


def _build_eu_conf_chart(days: int = 1825) -> go.Figure:
    EU_CONF = [
        (ID_ESTAT_CONF_EA, "Eurozona", "#e5e7eb"),
        (ID_ESTAT_CONF_DE, "Alemania", COUNTRY_COLORS["DEU"]),
        (ID_ESTAT_CONF_FR, "Francia",  COUNTRY_COLORS["FRA"]),
        (ID_ESTAT_CONF_ES, "España",   COUNTRY_COLORS["ESP"]),
        (ID_ESTAT_CONF_IT, "Italia",   COUNTRY_COLORS["ITA"]),
    ]

    fig = go.Figure()
    for sid, name, color in EU_CONF:
        df = get_series(sid, days=days)
        if df.empty:
            continue
        df = df.sort_values("timestamp")
        width = 2.5 if name == "Eurozona" else 1.5
        fig.add_trace(go.Scatter(
            x=df["timestamp"], y=df["value"],
            name=name, line=dict(color=color, width=width),
            hovertemplate=f"<b>{name}</b><br>%{{x|%b %Y}}: %{{y:.1f}}<extra></extra>",
        ))

    fig.add_hline(y=0, line_color="#374151", line_width=1, line_dash="dot",
                  annotation_text="Nivel neutro")

    layout = get_base_layout("Confianza del Consumidor Europeo (saldo)", height=300)
    layout["margin"] = {"l": 50, "r": 20, "t": 40, "b": 30}
    fig.update_layout(**layout)
    return fig


def _build_eu_trade_chart() -> go.Figure:
    """Balanzas comerciales WB (cuenta corriente % PIB) — barras horizontales."""
    EU_COUNTRIES = ["DEU", "NLD", "CHE", "SWE", "NOR", "DNK", "POL", "FRA",
                    "ESP", "PRT", "GBR", "ITA", "GRC", "HUN", "ROU", "TUR"]

    df = get_world_bank_indicator("curr_account", countries=EU_COUNTRIES)
    fig = go.Figure()

    if df.empty:
        layout = get_base_layout("Balanza Cuenta Corriente (% PIB)", height=360)
        fig.update_layout(**layout)
        fig.add_annotation(text="Sin datos disponibles", xref="paper", yref="paper",
                           x=0.5, y=0.5, showarrow=False, font={"color": COLORS["text_muted"]})
        return fig

    name_map = {
        "DEU": "🇩🇪 Alemania", "NLD": "🇳🇱 Países Bajos", "CHE": "🇨🇭 Suiza",
        "SWE": "🇸🇪 Suecia", "NOR": "🇳🇴 Noruega", "DNK": "🇩🇰 Dinamarca",
        "POL": "🇵🇱 Polonia", "FRA": "🇫🇷 Francia", "ESP": "🇪🇸 España",
        "PRT": "🇵🇹 Portugal", "GBR": "🇬🇧 Reino Unido", "ITA": "🇮🇹 Italia",
        "GRC": "🇬🇷 Grecia", "HUN": "🇭🇺 Hungría", "ROU": "🇷🇴 Rumania", "TUR": "🇹🇷 Turquía",
    }

    df = df.copy()
    df["name"] = df["country_iso3"].map(lambda x: name_map.get(x, x))
    df = df.dropna(subset=["value"]).sort_values("value", ascending=True)
    colors = [C["positive"] if v >= 0 else C["negative"] for v in df["value"]]

    fig.add_trace(go.Bar(
        x=df["value"],
        y=df["name"],
        orientation="h",
        marker_color=colors,
        hovertemplate="<b>%{y}</b><br>%{x:.1f}% del PIB<extra></extra>",
    ))
    fig.add_vline(x=0, line_color="#374151", line_width=1)

    # Nota sobre Alemania
    fig.add_annotation(
        text="El superávit alemán es históricamente elevado",
        xref="paper", yref="paper", x=0.98, y=0.02,
        showarrow=False, font={"size": 9, "color": COLORS["text_label"]},
        xanchor="right",
    )

    layout = get_base_layout("Cuenta Corriente Europea (% PIB)", height=420)
    layout["margin"] = {"l": 140, "r": 30, "t": 40, "b": 30}
    layout["xaxis"]["ticksuffix"] = "%"
    layout["hovermode"] = "y unified"
    fig.update_layout(**layout)
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — CHINA Y ASIA
# ══════════════════════════════════════════════════════════════════════════════

def _build_tab4() -> html.Div:
    return html.Div(
        [
            # 4.1 Crecimiento PIB chino histórico
            create_section_header(
                "China: El Motor que se Enfría",
                "PIB real anual (%) — Fuente: Banco Mundial",
            ),
            dcc.Loading(
                dcc.Graph(id="m2-cn-gdp-chart", config={"displayModeBar": False}),
                type="circle", color=COLORS["accent"],
            ),

            # 4.2 Métricas clave de China + exportaciones
            create_section_header("Indicadores Clave de China"),
            html.Div(id="m2-cn-metrics"),

            # 4.3 Tabla comparativa Asia
            create_section_header(
                "Comparativa Económica Asia",
                "Datos Banco Mundial — últimos disponibles",
            ),
            html.Div(id="m2-asia-table", style={"marginBottom": "24px"}),

            # 4.4 India vs China vs EE.UU. vs Eurozona
            create_section_header(
                "India: El Nuevo Motor del Crecimiento",
                "Crecimiento PIB comparado — Fuente: Banco Mundial",
            ),
            dcc.Loading(
                dcc.Graph(id="m2-india-chart", config={"displayModeBar": False}),
                type="circle", color=COLORS["accent"],
            ),
            html.Div(
                [
                    html.Span("India se ha convertido en el país más poblado del mundo (2023) "
                              "y en la economía de mayor crecimiento entre las grandes. "
                              "El FMI proyecta que será la tercera economía mundial en PIB nominal antes de 2030.",
                              style={"fontSize": "0.78rem", "color": COLORS["text_muted"]}),
                ],
                style={
                    "background": COLORS["card_bg"],
                    "border": f"1px solid {COLORS['border']}",
                    "borderRadius": "6px",
                    "padding": "10px 14px",
                    "marginTop": "8px",
                },
            ),
        ],
        style={"padding": "16px"},
    )


def _build_cn_gdp_chart() -> go.Figure:
    df = get_series("wb_gdp_growth_chn", days=365 * 30)
    fig = go.Figure()

    if df.empty:
        layout = get_base_layout("Crecimiento PIB China (% anual)", height=320)
        fig.update_layout(**layout)
        fig.add_annotation(text="Sin datos disponibles (ejecutar colector WB)",
                           xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False,
                           font={"color": COLORS["text_muted"]})
        return fig

    df = df.sort_values("timestamp")

    TARGET = 5.0

    def bar_color(v):
        if v >= TARGET:
            return C["positive"]
        if v >= TARGET - 0.5:
            return C["warning"]
        return C["negative"]

    colors = [bar_color(float(v)) for v in df["value"]]

    fig.add_trace(go.Bar(
        x=df["timestamp"], y=df["value"],
        marker_color=colors,
        name="PIB China",
        hovertemplate="%{x|%Y}: %{y:.1f}%<extra></extra>",
    ))

    # Línea de tendencia
    if len(df) > 5:
        x_numeric = np.arange(len(df))
        coeffs = np.polyfit(x_numeric, df["value"].astype(float), 1)
        trend = np.polyval(coeffs, x_numeric)
        fig.add_trace(go.Scatter(
            x=df["timestamp"], y=trend,
            name="Tendencia",
            line=dict(color="#f97316", width=1.5, dash="dot"),
            hovertemplate="Tendencia: %{y:.1f}%<extra></extra>",
        ))

    # Anotaciones históricas
    annotations_data = [
        ("2001", "OMC"),
        ("2008", "Crisis Global"),
        ("2020", "COVID-19"),
    ]
    for yr_str, label in annotations_data:
        sub = df[df["timestamp"].dt.year == int(yr_str)]
        if not sub.empty:
            val = float(sub.iloc[0]["value"])
            fig.add_annotation(
                x=sub.iloc[0]["timestamp"], y=val,
                text=label,
                showarrow=True, arrowhead=1, arrowcolor="#6b7280",
                font={"size": 9, "color": "#9ca3af"},
                yshift=10,
            )

    # Línea objetivo gobierno
    fig.add_hline(y=TARGET, line_dash="dash", line_color="#f59e0b", line_width=1,
                  annotation_text="Objetivo gobierno ~5%",
                  annotation_font={"size": 9, "color": "#f59e0b"})

    layout = get_base_layout("Crecimiento PIB China (% anual)", height=320)
    layout["yaxis"]["ticksuffix"] = "%"
    layout["margin"] = {"l": 50, "r": 20, "t": 40, "b": 30}
    layout["showlegend"] = True
    fig.update_layout(**layout)
    return fig


def _build_cn_metrics() -> html.Div:
    """Cards con métricas clave de China."""
    indicators = [
        ("wb_gdp_growth_chn", "Crecimiento PIB China", "%", ".1f"),
        ("wb_cpi_inflation_chn", "Inflación IPC China", "%", ".1f"),
        ("wb_trade_pct_chn", "Apertura Comercial China", "% PIB", ".1f"),
        ("wb_reserves_usd_chn", "Reservas Divisas China", "USD", ".0f"),
    ]

    cards = []
    for sid, label, unit, fmt in indicators:
        val, ts = get_latest_value(sid)
        val_str = "—"
        if val is not None:
            if unit == "USD":
                val_str = format_value(val, unit="", decimals=1)
            else:
                val_str = _safe(val, fmt, "")

        cards.append(
            html.Div(
                create_metric_card(label, val_str, unit=unit),
                style={"flex": "1", "minWidth": "160px"},
            )
        )

    return html.Div(
        cards,
        style={"display": "flex", "gap": "10px", "flexWrap": "wrap", "marginBottom": "24px"},
    )


def _build_asia_table() -> html.Div:
    """Tabla comparativa economías asiáticas."""
    ASIA_COUNTRIES = ["CHN", "JPN", "IND", "KOR", "IDN", "THA", "VNM", "MYS", "SGP"]

    indicators = ["gdp_growth", "cpi_inflation", "unemployment", "gov_debt_pct", "curr_account"]

    df = get_country_comparison(indicators, countries=ASIA_COUNTRIES)

    name_map = {
        "CHN": "🇨🇳 China", "JPN": "🇯🇵 Japón", "IND": "🇮🇳 India",
        "KOR": "🇰🇷 Corea del Sur", "IDN": "🇮🇩 Indonesia", "THA": "🇹🇭 Tailandia",
        "VNM": "🇻🇳 Vietnam", "MYS": "🇲🇾 Malasia", "SGP": "🇸🇬 Singapur",
    }

    if df.empty:
        return create_empty_state("Sin datos comparativos (ejecutar colector WB)")

    col_labels = {
        "gdp_growth":    "PIB (%)",
        "cpi_inflation": "Inflación (%)",
        "unemployment":  "Desempleo (%)",
        "gov_debt_pct":  "Deuda/PIB (%)",
        "curr_account":  "Cta. Cte. (% PIB)",
    }

    headers = ["País"] + [col_labels[c] for c in indicators]
    th_els = [html.Th(h, style={"fontSize": "0.72rem", "color": COLORS["text_label"]}) for h in headers]

    rows = []
    for _, row in df.iterrows():
        iso3 = row["country_iso3"]
        cells = [html.Td(name_map.get(iso3, iso3), style={"fontSize": "0.78rem"})]
        for ind in indicators:
            val = row.get(ind)
            if pd.isna(val):
                cells.append(html.Td("—", style={"color": COLORS["text_muted"], "fontSize": "0.78rem"}))
            else:
                v = float(val)
                color = COLORS["text"]
                if ind == "gdp_growth":
                    color = C["positive"] if v >= 3 else (C["warning"] if v >= 0 else C["negative"])
                elif ind in ("unemployment", "cpi_inflation", "gov_debt_pct"):
                    color = C["negative"] if v >= 10 else COLORS["text"]
                cells.append(html.Td(f"{v:.1f}%", style={"fontSize": "0.78rem", "color": color}))
        rows.append(html.Tr(cells))

    return html.Div(
        html.Table(
            [html.Thead(html.Tr(th_els)), html.Tbody(rows)],
            className="data-table",
        ),
        style={"overflowX": "auto"},
    )


def _build_india_chart() -> go.Figure:
    """Comparativa India vs China vs EE.UU. vs Eurozona desde 2010."""
    SERIES = [
        ("wb_gdp_growth_ind", "India",    C["positive"]),
        ("wb_gdp_growth_chn", "China",    COUNTRY_COLORS.get("CHN", "#f97316")),
        ("wb_gdp_growth_usa", "EE.UU.",   COUNTRY_COLORS.get("USA", "#3b82f6")),
        ("wb_gdp_growth_emu", "Eurozona", COUNTRY_COLORS.get("DEU", "#10b981")),
    ]

    fig = go.Figure()
    any_data = False
    since = datetime(2010, 1, 1)

    for sid, name, color in SERIES:
        df = get_series(sid, days=365 * 20)
        if df.empty:
            continue
        df = df[df["timestamp"] >= since].sort_values("timestamp")
        if df.empty:
            continue
        any_data = True
        width = 2.5 if name == "India" else 1.8
        fig.add_trace(go.Scatter(
            x=df["timestamp"], y=df["value"],
            name=name,
            line=dict(color=color, width=width),
            hovertemplate=f"<b>{name}</b><br>%{{x|%Y}}: %{{y:.1f}}%<extra></extra>",
        ))

    fig.add_hline(y=0, line_color="#374151", line_width=1, line_dash="dash")

    # Anotación: India supera a China
    fig.add_annotation(
        x="2022-01-01", y=7.0,
        text="India supera a China (2022)",
        showarrow=True, arrowhead=1, arrowcolor="#10b981",
        font={"size": 9, "color": "#10b981"},
        ax=60, ay=-20,
    )

    layout = get_base_layout("Crecimiento PIB: India vs Mundo (% anual)", height=320)
    layout["yaxis"]["ticksuffix"] = "%"
    layout["margin"] = {"l": 50, "r": 20, "t": 40, "b": 30}
    fig.update_layout(**layout)

    if not any_data:
        fig.add_annotation(text="Sin datos disponibles (ejecutar colector WB)",
                           xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False,
                           font={"color": COLORS["text_muted"]})
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — COMPARATIVA GLOBAL
# ══════════════════════════════════════════════════════════════════════════════

def _build_tab5() -> html.Div:
    return html.Div(
        [
            # 5.1 La gran tabla comparativa
            create_section_header(
                "La Gran Tabla Comparativa",
                "Principales indicadores macroeconómicos por país — Banco Mundial",
            ),
            html.Div(
                [
                    html.Div(
                        [
                            dcc.Input(
                                id="m2-table-search",
                                type="text",
                                placeholder="Buscar país...",
                                debounce=True,
                                style={
                                    "background": COLORS["card_bg"],
                                    "border": f"1px solid {COLORS['border']}",
                                    "color": COLORS["text"],
                                    "borderRadius": "4px",
                                    "padding": "6px 10px",
                                    "fontSize": "0.78rem",
                                    "width": "200px",
                                },
                            ),
                        ],
                        style={"marginBottom": "8px", "display": "flex", "gap": "8px"},
                    ),
                    dcc.Loading(
                        html.Div(id="m2-global-table"),
                        type="circle", color=COLORS["accent"],
                    ),
                    html.Div(id="m2-table-pagination", style={"marginTop": "8px"}),
                    dcc.Store(id="m2-table-sort-col", data="gdp_nominal"),
                    dcc.Store(id="m2-table-sort-asc", data=False),
                    dcc.Store(id="m2-table-page", data=0),
                ],
            ),

            # 5.2 Bubble chart
            create_section_header(
                "Riqueza vs Dinamismo — Perspectiva Global",
                "Eje X: PIB per cápita PPP · Eje Y: Crecimiento PIB · Tamaño: Población",
            ),
            dbc.Row(
                [
                    dbc.Col(
                        html.Div(
                            [
                                html.Label("Año:", style={"fontSize": "0.72rem", "color": COLORS["text_muted"], "marginRight": "8px"}),
                                dcc.Dropdown(
                                    id="m2-bubble-year",
                                    options=[{"label": str(y), "value": y} for y in range(2023, 1999, -1)],
                                    value=2021,
                                    clearable=False,
                                    style={"width": "100px"},
                                    className="dash-dropdown-dark",
                                ),
                            ],
                            style={"display": "flex", "alignItems": "center", "marginBottom": "8px"},
                        ),
                        width=12,
                    ),
                    dbc.Col(
                        dcc.Loading(
                            dcc.Graph(id="m2-bubble-chart", config={"displayModeBar": False}),
                            type="circle", color=COLORS["accent"],
                        ),
                        width=12,
                    ),
                ],
                className="g-2",
            ),

            # 5.3 Heatmap de correlaciones
            create_section_header(
                "Correlaciones Macroeconómicas Globales",
                "Correlación de Pearson entre indicadores — todos los países disponibles",
            ),
            dcc.Loading(
                dcc.Graph(id="m2-corr-heatmap", config={"displayModeBar": False}),
                type="circle", color=COLORS["accent"],
            ),
        ],
        style={"padding": "16px"},
    )


def _build_global_table(search: str = "", sort_col: str = "gdp_nominal",
                        sort_asc: bool = False, page: int = 0) -> tuple:
    """Construye la tabla comparativa. Devuelve (table_html, pagination_html)."""
    PAGE_SIZE = 15

    INDICATORS = ["gdp_nominal", "gdp_growth", "gdp_pc_ppp", "cpi_inflation",
                  "unemployment", "gov_debt_pct", "fiscal_balance", "curr_account"]

    df = get_country_comparison(INDICATORS, countries=COMPARISON_COUNTRIES_ISO3)

    if df.empty:
        return create_empty_state("Sin datos disponibles (ejecutar colector WB)"), html.Div()

    # Añadir nombre y filtrar por búsqueda
    df["nombre"] = df["country_iso3"].map(lambda x: ISO3_NAMES.get(x, x))
    if search:
        df = df[df["nombre"].str.lower().str.contains(search.lower(), na=False)]

    # Ordenar
    if sort_col in df.columns:
        try:
            df = df.sort_values(sort_col, ascending=sort_asc, na_position="last")
        except Exception:
            pass
    elif sort_col == "nombre":
        df = df.sort_values("nombre", ascending=sort_asc)

    total = len(df)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    df_page = df.iloc[page * PAGE_SIZE: (page + 1) * PAGE_SIZE]

    COL_META = {
        "nombre":        ("País", lambda v: v, ""),
        "gdp_nominal":   ("PIB (USD)", lambda v: format_value(v, decimals=1), ""),
        "gdp_growth":    ("PIB (%)", lambda v: f"{v:+.1f}%", ""),
        "gdp_pc_ppp":    ("PIB pc PPP", lambda v: f"${v:,.0f}", ""),
        "cpi_inflation": ("Inflación", lambda v: f"{v:.1f}%", ""),
        "unemployment":  ("Desempleo", lambda v: f"{v:.1f}%", ""),
        "gov_debt_pct":  ("Deuda/PIB", lambda v: f"{v:.1f}%", ""),
        "fiscal_balance":("Déficit/PIB", lambda v: f"{v:+.1f}%", ""),
        "curr_account":  ("Cta. Cte.", lambda v: f"{v:+.1f}%", ""),
    }

    col_order = ["nombre"] + INDICATORS

    def _cell_style(col, val):
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return {"fontSize": "0.75rem", "color": COLORS["text_muted"]}
        style = {"fontSize": "0.75rem"}
        try:
            v = float(val)
            if col == "gdp_growth":
                if v >= 4:
                    style["color"] = C["positive"]
                    style["fontWeight"] = "600"
                elif v < 0:
                    style["color"] = C["negative"]
            elif col == "unemployment":
                if v >= 15:
                    style["color"] = C["negative"]
                    style["fontWeight"] = "600"
                elif v <= 4:
                    style["color"] = C["positive"]
            elif col == "cpi_inflation":
                if v > 8:
                    style["color"] = C["negative"]
                elif v < 0:
                    style["color"] = "#60a5fa"
            elif col == "gov_debt_pct":
                if v >= 100:
                    style["color"] = C["negative"]
                elif v >= 60:
                    style["color"] = C["warning"]
        except Exception:
            pass
        return style

    th_els = []
    for col in col_order:
        label, _, _ = COL_META[col]
        arrow = "↑" if sort_col == col and sort_asc else ("↓" if sort_col == col else "")
        th_els.append(
            html.Th(
                f"{label} {arrow}",
                style={"fontSize": "0.70rem", "color": COLORS["text_label"],
                       "cursor": "pointer", "userSelect": "none",
                       "color": COLORS["accent"] if sort_col == col else COLORS["text_label"]},
                id={"type": "m2-table-sort-btn", "col": col},
            )
        )

    row_els = []
    for _, row_data in df_page.iterrows():
        cells = []
        for col in col_order:
            _, fmt_fn, _ = COL_META[col]
            raw = row_data.get(col)
            if raw is None or (isinstance(raw, float) and pd.isna(raw)):
                txt = "—"
            else:
                try:
                    txt = fmt_fn(raw)
                except Exception:
                    txt = str(raw)
            cells.append(html.Td(txt, style=_cell_style(col, raw)))
        row_els.append(html.Tr(cells))

    table = html.Div(
        html.Table(
            [html.Thead(html.Tr(th_els)), html.Tbody(row_els)],
            className="data-table",
        ),
        style={"overflowX": "auto"},
    )

    # Paginación
    pagination = html.Div(
        [
            html.Span(f"Mostrando {page * PAGE_SIZE + 1}–{min((page + 1) * PAGE_SIZE, total)} de {total} países",
                      style={"fontSize": "0.72rem", "color": COLORS["text_muted"]}),
            html.Div(
                [
                    html.Button("← Ant.", id="m2-table-prev", n_clicks=0,
                                style={"fontSize": "0.72rem", "marginLeft": "8px",
                                       "background": COLORS["card_bg"], "border": f"1px solid {COLORS['border']}",
                                       "color": COLORS["text_muted"], "borderRadius": "4px",
                                       "padding": "3px 8px", "cursor": "pointer"},
                                disabled=page == 0),
                    html.Button("Sig. →", id="m2-table-next", n_clicks=0,
                                style={"fontSize": "0.72rem", "marginLeft": "4px",
                                       "background": COLORS["card_bg"], "border": f"1px solid {COLORS['border']}",
                                       "color": COLORS["text_muted"], "borderRadius": "4px",
                                       "padding": "3px 8px", "cursor": "pointer"},
                                disabled=page >= total_pages - 1),
                ],
                style={"display": "inline-flex", "alignItems": "center"},
            ),
        ],
        style={"display": "flex", "alignItems": "center", "gap": "16px", "flexWrap": "wrap"},
    )

    return table, pagination


def _build_bubble_chart(year: int = 2021) -> go.Figure:
    """Bubble chart: PIB pc vs crecimiento PIB, tamaño = población."""
    INDICATORS = ["gdp_pc_ppp", "gdp_growth", "population"]

    df = get_country_comparison(INDICATORS, year=year)
    fig = go.Figure()

    if df.empty or len(df) < 3:
        layout = get_base_layout("Riqueza vs Dinamismo Global", height=480)
        fig.update_layout(**layout)
        fig.add_annotation(text=f"Sin datos para {year} (ejecutar colector WB)",
                           xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False,
                           font={"color": COLORS["text_muted"]})
        return fig

    df = df.dropna(subset=["gdp_pc_ppp", "gdp_growth"])
    df["region"] = df["country_iso3"].map(lambda x: ISO3_REGIONS.get(x, "Otros"))
    df["name"] = df["country_iso3"].map(lambda x: ISO3_NAMES.get(x, x))
    df["pop_size"] = df["population"].fillna(10e6)

    # Tamaño de burbuja normalizado
    max_pop = df["pop_size"].max()
    df["bubble_size"] = (df["pop_size"] / max_pop * 50 + 5).clip(5, 55)

    for region, color in REGION_COLORS.items():
        sub = df[df["region"] == region]
        if sub.empty:
            continue
        fig.add_trace(go.Scatter(
            x=sub["gdp_pc_ppp"],
            y=sub["gdp_growth"],
            mode="markers+text",
            name=region,
            marker=dict(
                size=sub["bubble_size"],
                color=color,
                opacity=0.7,
                line=dict(color="white", width=0.5),
            ),
            text=sub["country_iso3"],
            textposition="top center",
            textfont=dict(size=9, color="#9ca3af"),
            hovertemplate=(
                "<b>%{text}</b><br>"
                "PIB pc PPP: $%{x:,.0f}<br>"
                "Crecimiento: %{y:.1f}%<extra></extra>"
            ),
        ))

    fig.add_hline(y=0, line_color="#374151", line_width=1, line_dash="dot")

    # Anotaciones de cuadrantes
    fig.add_annotation(text="Ricos + Creciendo", xref="paper", yref="paper",
                       x=0.95, y=0.95, showarrow=False,
                       font={"size": 9, "color": COLORS["text_label"]}, xanchor="right")
    fig.add_annotation(text="Ricos + Estancados", xref="paper", yref="paper",
                       x=0.95, y=0.05, showarrow=False,
                       font={"size": 9, "color": COLORS["text_label"]}, xanchor="right")
    fig.add_annotation(text="Pobres + Creciendo", xref="paper", yref="paper",
                       x=0.05, y=0.95, showarrow=False,
                       font={"size": 9, "color": COLORS["text_label"]}, xanchor="left")
    fig.add_annotation(text="Pobres + Estancados", xref="paper", yref="paper",
                       x=0.05, y=0.05, showarrow=False,
                       font={"size": 9, "color": COLORS["text_label"]}, xanchor="left")

    layout = get_base_layout(f"Riqueza vs Dinamismo Global · {year}", height=480)
    layout["xaxis"]["title"] = {"text": "PIB per cápita PPP (USD)", "font": {"color": "#9ca3af", "size": 10}}
    layout["yaxis"]["title"] = {"text": "Crecimiento PIB (%)", "font": {"color": "#9ca3af", "size": 10}}
    layout["yaxis"]["ticksuffix"] = "%"
    layout["margin"] = {"l": 60, "r": 20, "t": 50, "b": 50}
    layout["hovermode"] = "closest"
    fig.update_layout(**layout)
    return fig


def _build_corr_heatmap() -> go.Figure:
    """Heatmap de correlación entre indicadores macroeconómicos."""
    INDICATORS = ["gdp_growth", "cpi_inflation", "unemployment", "gov_debt_pct",
                  "fiscal_balance", "curr_account", "trade_pct", "rd_spending"]

    df = get_country_comparison(INDICATORS)
    fig = go.Figure()

    COL_LABELS = {
        "gdp_growth":    "PIB (%)",
        "cpi_inflation": "Inflación",
        "unemployment":  "Desempleo",
        "gov_debt_pct":  "Deuda/PIB",
        "fiscal_balance":"Déficit",
        "curr_account":  "Cta. Cte.",
        "trade_pct":     "Apertura Com.",
        "rd_spending":   "I+D (%)",
    }

    if df.empty or len(df) < 10:
        layout = get_base_layout("Correlaciones Macroeconómicas", height=380)
        fig.update_layout(**layout)
        fig.add_annotation(text="Sin datos suficientes para calcular correlaciones",
                           xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False,
                           font={"color": COLORS["text_muted"]})
        return fig

    available = [c for c in INDICATORS if c in df.columns]
    df_num = df[available].dropna(thresh=5)

    if len(df_num) < 5 or len(available) < 3:
        layout = get_base_layout("Correlaciones Macroeconómicas", height=380)
        fig.update_layout(**layout)
        fig.add_annotation(text="Datos insuficientes para correlaciones",
                           xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False,
                           font={"color": COLORS["text_muted"]})
        return fig

    corr_matrix = df_num.corr(method="pearson")
    labels = [COL_LABELS.get(c, c) for c in available]

    z = corr_matrix.values
    text_z = [[f"{v:.2f}" if not pd.isna(v) else "" for v in row] for row in z]

    fig.add_trace(go.Heatmap(
        z=z,
        x=labels,
        y=labels,
        colorscale="RdBu",
        zmid=0,
        zmin=-1,
        zmax=1,
        text=text_z,
        texttemplate="%{text}",
        textfont={"size": 10},
        hovertemplate="%{y} vs %{x}: <b>%{z:.2f}</b><extra></extra>",
        colorbar=dict(
            bgcolor="#111827",
            bordercolor="#1f2937",
            tickfont={"color": "#9ca3af", "size": 10},
            title=dict(text="r", font={"color": "#9ca3af", "size": 10}),
            thickness=14,
        ),
    ))

    layout = get_base_layout("Correlaciones Macroeconómicas Globales (Pearson)", height=420)
    layout["margin"] = {"l": 100, "r": 30, "t": 40, "b": 100}
    layout["xaxis"]["tickangle"] = -40
    layout["xaxis"]["tickfont"] = {"size": 10}
    layout["yaxis"]["tickfont"] = {"size": 10}
    fig.update_layout(**layout)
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# LAYOUT PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

def render_module_2() -> html.Div:
    return html.Div(
        [
            # Intervalo de refresco
            dcc.Interval(id="m2-refresh-interval", interval=300_000, n_intervals=0),

            # Header del módulo
            html.Div(
                [
                    html.Div("🌍 Macroeconomía Global", className="module-title"),
                    html.Div(
                        "Crecimiento, inflación, empleo, deuda y comercio — perspectiva mundial",
                        className="module-subtitle",
                    ),
                ],
            ),

            # Fila de 6 métricas
            _build_header_metrics(),

            # Tabs
            dcc.Tabs(
                [
                    dcc.Tab(
                        label="🗺 Mapa Mundial",
                        value="tab-map",
                        children=_build_tab1(),
                        style=TAB_STYLE,
                        selected_style=TAB_SELECTED_STYLE,
                    ),
                    dcc.Tab(
                        label="🇺🇸 EE.UU. en Detalle",
                        value="tab-usa",
                        children=_build_tab2(),
                        style=TAB_STYLE,
                        selected_style=TAB_SELECTED_STYLE,
                    ),
                    dcc.Tab(
                        label="🇪🇺 Europa en Detalle",
                        value="tab-eu",
                        children=_build_tab3(),
                        style=TAB_STYLE,
                        selected_style=TAB_SELECTED_STYLE,
                    ),
                    dcc.Tab(
                        label="🇨🇳 China y Asia",
                        value="tab-cn",
                        children=_build_tab4(),
                        style=TAB_STYLE,
                        selected_style=TAB_SELECTED_STYLE,
                    ),
                    dcc.Tab(
                        label="📊 Comparativa Global",
                        value="tab-global",
                        children=_build_tab5(),
                        style=TAB_STYLE,
                        selected_style=TAB_SELECTED_STYLE,
                    ),
                ],
                id="m2-tabs",
                value="tab-map",
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

def register_callbacks_module_2(app) -> None:

    # ── Tab 1: Mapa choroplético ──────────────────────────────────────────────

    @app.callback(
        Output("m2-choropleth-map", "figure"),
        Output("m2-map-data-panel", "children"),
        Input("m2-map-indicator", "value"),
        Input("m2-map-year", "value"),
        Input("m2-refresh-interval", "n_intervals"),
        prevent_initial_call=False,
    )
    def update_choropleth(indicator_key, year, _):
        try:
            fig = _build_choropleth(indicator_key or "gdp_growth", year or 2022)
            panel = _build_map_data_panel(indicator_key or "gdp_growth", year or 2022)
        except Exception as exc:
            logger.warning("update_choropleth error: %s", exc)
            fig = go.Figure()
            panel = create_empty_state("Error al cargar el mapa")
        return fig, panel

    # ── Tab 2: EE.UU. ─────────────────────────────────────────────────────────

    @app.callback(
        Output("m2-us-gdp-chart", "figure"),
        Output("m2-us-gdp-table", "children"),
        Output("m2-us-indpro-chart", "figure"),
        Output("m2-us-retail-chart", "figure"),
        Output("m2-us-conf-chart", "figure"),
        Output("m2-us-trade-chart", "figure"),
        Output("m2-us-cycle-chart", "figure"),
        Output("m2-us-cycle-text", "children"),
        Input("m2-us-range", "value"),
        Input("m2-refresh-interval", "n_intervals"),
        prevent_initial_call=False,
    )
    def update_us_charts(days, _):
        days = days or 1825
        try:
            gdp_fig = _build_us_gdp_chart(days)
        except Exception as exc:
            logger.warning("us gdp chart: %s", exc)
            gdp_fig = go.Figure()
        try:
            gdp_table = _build_us_gdp_table(days)
        except Exception:
            gdp_table = html.Div()
        try:
            indpro_fig = _build_indpro_chart(days)
        except Exception:
            indpro_fig = go.Figure()
        try:
            retail_fig = _build_retail_chart(days)
        except Exception:
            retail_fig = go.Figure()
        try:
            conf_fig = _build_conf_chart(days)
        except Exception:
            conf_fig = go.Figure()
        try:
            trade_fig = _build_trade_chart(days)
        except Exception:
            trade_fig = go.Figure()

        # Ciclo económico
        phase = "Indeterminada"
        phase_color = COLORS["text_muted"]
        try:
            result = _build_cycle_chart()
            if isinstance(result, tuple):
                cycle_fig, phase, phase_color = result
            else:
                cycle_fig = result
        except Exception as exc:
            logger.warning("cycle chart: %s", exc)
            cycle_fig = go.Figure()

        cycle_text = html.Div(
            [
                html.Div("Fase actual del ciclo:", style={"fontSize": "0.72rem",
                                                           "color": COLORS["text_muted"],
                                                           "marginBottom": "6px"}),
                html.Div(phase, style={"fontSize": "1.2rem", "fontWeight": "700",
                                        "color": phase_color, "marginBottom": "12px"}),
                html.Hr(style={"borderColor": COLORS["border"]}),
                html.Div(
                    [
                        html.P("Cuadrante superior derecho: Expansión (producción e confianza altas) — verde",
                               style={"fontSize": "0.72rem", "color": COLORS["text_muted"], "margin": "2px 0"}),
                        html.P("Cuadrante inferior derecho: Auge tardío (producción sube, confianza baja) — amarillo",
                               style={"fontSize": "0.72rem", "color": COLORS["text_muted"], "margin": "2px 0"}),
                        html.P("Cuadrante inferior izquierdo: Recesión (ambos indicadores caen) — rojo",
                               style={"fontSize": "0.72rem", "color": COLORS["text_muted"], "margin": "2px 0"}),
                        html.P("Cuadrante superior izquierdo: Recuperación (confianza sube, producción rezagada) — azul",
                               style={"fontSize": "0.72rem", "color": COLORS["text_muted"], "margin": "2px 0"}),
                    ],
                    style={"marginTop": "8px"},
                ),
            ],
            style={
                "background": COLORS["card_bg"],
                "border": f"1px solid {COLORS['border']}",
                "borderRadius": "6px",
                "padding": "14px",
            },
        )

        return gdp_fig, gdp_table, indpro_fig, retail_fig, conf_fig, trade_fig, cycle_fig, cycle_text

    # ── Tab 3: Europa ──────────────────────────────────────────────────────────

    @app.callback(
        Output("m2-eu-gdp-chart", "figure"),
        Output("m2-eu-gdp-table", "children"),
        Output("m2-eu-indpro-chart", "figure"),
        Output("m2-eu-conf-chart", "figure"),
        Output("m2-eu-trade-chart", "figure"),
        Input("m2-eu-range", "value"),
        Input("m2-refresh-interval", "n_intervals"),
        prevent_initial_call=False,
    )
    def update_eu_charts(days, _):
        days = days or 1825
        try:
            gdp_fig = _build_eu_gdp_chart(days)
        except Exception:
            gdp_fig = go.Figure()
        try:
            gdp_table = _build_eu_gdp_table()
        except Exception:
            gdp_table = html.Div()
        try:
            indpro_fig = _build_eu_indpro_chart(days)
        except Exception:
            indpro_fig = go.Figure()
        try:
            conf_fig = _build_eu_conf_chart(days)
        except Exception:
            conf_fig = go.Figure()
        try:
            trade_fig = _build_eu_trade_chart()
        except Exception:
            trade_fig = go.Figure()
        return gdp_fig, gdp_table, indpro_fig, conf_fig, trade_fig

    # ── Tab 4: China / Asia ───────────────────────────────────────────────────

    @app.callback(
        Output("m2-cn-gdp-chart", "figure"),
        Output("m2-cn-metrics", "children"),
        Output("m2-asia-table", "children"),
        Output("m2-india-chart", "figure"),
        Input("m2-refresh-interval", "n_intervals"),
        prevent_initial_call=False,
    )
    def update_cn_charts(_):
        try:
            cn_fig = _build_cn_gdp_chart()
        except Exception:
            cn_fig = go.Figure()
        try:
            cn_metrics = _build_cn_metrics()
        except Exception:
            cn_metrics = html.Div()
        try:
            asia_table = _build_asia_table()
        except Exception:
            asia_table = html.Div()
        try:
            india_fig = _build_india_chart()
        except Exception:
            india_fig = go.Figure()
        return cn_fig, cn_metrics, asia_table, india_fig

    # ── Tab 5: Tabla comparativa ──────────────────────────────────────────────

    @app.callback(
        Output("m2-global-table", "children"),
        Output("m2-table-pagination", "children"),
        Output("m2-table-sort-col", "data"),
        Output("m2-table-sort-asc", "data"),
        Output("m2-table-page", "data"),
        Input("m2-table-search", "value"),
        Input({"type": "m2-table-sort-btn", "col": "nombre"}, "n_clicks"),
        Input({"type": "m2-table-sort-btn", "col": "gdp_nominal"}, "n_clicks"),
        Input({"type": "m2-table-sort-btn", "col": "gdp_growth"}, "n_clicks"),
        Input({"type": "m2-table-sort-btn", "col": "gdp_pc_ppp"}, "n_clicks"),
        Input({"type": "m2-table-sort-btn", "col": "cpi_inflation"}, "n_clicks"),
        Input({"type": "m2-table-sort-btn", "col": "unemployment"}, "n_clicks"),
        Input({"type": "m2-table-sort-btn", "col": "gov_debt_pct"}, "n_clicks"),
        Input({"type": "m2-table-sort-btn", "col": "fiscal_balance"}, "n_clicks"),
        Input({"type": "m2-table-sort-btn", "col": "curr_account"}, "n_clicks"),
        Input("m2-table-prev", "n_clicks"),
        Input("m2-table-next", "n_clicks"),
        Input("m2-refresh-interval", "n_intervals"),
        State("m2-table-sort-col", "data"),
        State("m2-table-sort-asc", "data"),
        State("m2-table-page", "data"),
        prevent_initial_call=False,
    )
    def update_global_table(search, *args):
        # Las últimas 3 son States, las anteriores son los n_clicks + refresh
        state_sort_col = args[-3]
        state_sort_asc = args[-2]
        state_page = args[-1]

        # Detectar qué disparó el callback
        triggered = callback_context.triggered_id if callback_context.triggered else None

        sort_col = state_sort_col or "gdp_nominal"
        sort_asc = state_sort_asc if state_sort_asc is not None else False
        page = state_page or 0

        if isinstance(triggered, dict) and triggered.get("type") == "m2-table-sort-btn":
            new_col = triggered["col"]
            if new_col == sort_col:
                sort_asc = not sort_asc
            else:
                sort_col = new_col
                sort_asc = False
            page = 0

        elif triggered == "m2-table-prev":
            page = max(0, page - 1)
        elif triggered == "m2-table-next":
            page = page + 1
        elif triggered == "m2-table-search":
            page = 0

        try:
            table_html, pagination_html = _build_global_table(
                search=search or "",
                sort_col=sort_col,
                sort_asc=sort_asc,
                page=page,
            )
        except Exception as exc:
            logger.warning("global table: %s", exc)
            table_html = create_empty_state("Error al cargar la tabla")
            pagination_html = html.Div()

        return table_html, pagination_html, sort_col, sort_asc, page

    # ── Tab 5: Bubble chart ───────────────────────────────────────────────────

    @app.callback(
        Output("m2-bubble-chart", "figure"),
        Input("m2-bubble-year", "value"),
        Input("m2-refresh-interval", "n_intervals"),
        prevent_initial_call=False,
    )
    def update_bubble_chart(year, _):
        try:
            return _build_bubble_chart(year or 2021)
        except Exception as exc:
            logger.warning("bubble chart: %s", exc)
            return go.Figure()

    # ── Tab 5: Heatmap de correlaciones ───────────────────────────────────────

    @app.callback(
        Output("m2-corr-heatmap", "figure"),
        Input("m2-refresh-interval", "n_intervals"),
        prevent_initial_call=False,
    )
    def update_corr_heatmap(_):
        try:
            return _build_corr_heatmap()
        except Exception as exc:
            logger.warning("corr heatmap: %s", exc)
            return go.Figure()
