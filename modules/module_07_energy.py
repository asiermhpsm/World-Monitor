"""
Modulo 7 — Energía y Materias Primas Estratégicas
Se renderiza cuando la URL es /module/7.

Exporta:
  render_module_7()               -> layout completo
  register_callbacks_module_7(app) -> registra todos los callbacks
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import dash
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import pandas as pd
from dash import ALL, Input, Output, State, dcc, html, no_update

from components.chart_config import (
    COLORS as C,
    get_base_layout,
    get_time_range_buttons,
)
from components.common import create_empty_state, create_section_header
from config import COLORS
from modules.data_helpers import (
    calculate_oil_inflation_correlation,
    format_value,
    get_change,
    get_latest_value,
    get_series,
    get_world_bank_indicator,
    load_json_data,
    time_ago,
)

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTES — IDs de indicadores
# ══════════════════════════════════════════════════════════════════════════════

ID_BRENT    = "yf_bz_close"
ID_WTI      = "yf_cl_close"
ID_GAS_HH   = "yf_ng_close"
ID_GOLD     = "yf_gc_close"
ID_COPPER   = "yf_hg_close"
ID_BDI      = "yf_bdi_close"
ID_GAS_TTF  = "yf_ttf_close"
ID_URANIUM  = "yf_ux_close"
ID_NICKEL   = "yf_znc_close"
ID_LIT_ETF  = "yf_lit_close"   # Lithium ETF proxy

# CPI para correlación petróleo-inflación
ID_CPI_US   = "fred_cpi_us"

# ══════════════════════════════════════════════════════════════════════════════
# ESTILOS COMPARTIDOS
# ══════════════════════════════════════════════════════════════════════════════

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

# ══════════════════════════════════════════════════════════════════════════════
# HELPERS INTERNOS
# ══════════════════════════════════════════════════════════════════════════════

def _safe(val, fmt=".2f", suffix="") -> str:
    if val is None:
        return "—"
    try:
        return f"{val:{fmt}}{suffix}"
    except Exception:
        return "—"


def _arrow(chg: Optional[float]) -> str:
    if chg is None:
        return ""
    return "↑" if chg > 0 else ("↓" if chg < 0 else "→")


def _chg_color(chg: Optional[float], higher_bad: bool = False) -> str:
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
            style={"fontSize": "1.15rem", "fontWeight": "700", "color": COLORS["text"],
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


def _route_badge(status: str) -> html.Span:
    cfg = {
        "normal":  ("🟢 NORMAL",   "#10b981", "#0a2218"),
        "reduced": ("🟡 REDUCIDO", "#f59e0b", "#201900"),
        "blocked": ("🔴 BLOQUEADO","#ef4444", "#200808"),
    }
    label, color, bg = cfg.get(status, ("⚪ DESCONOCIDO", "#9ca3af", "#111"))
    return html.Span(label, style={
        "fontSize": "0.70rem", "fontWeight": "700", "color": color,
        "background": bg, "padding": "2px 8px", "borderRadius": "4px",
        "border": f"1px solid {color}40",
    })


def _empty_fig(msg: str = "Sin datos disponibles") -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        **get_base_layout(height=350),
        annotations=[{"text": msg, "xref": "paper", "yref": "paper",
                       "x": 0.5, "y": 0.5, "showarrow": False,
                       "font": {"color": COLORS["text_muted"], "size": 13}}],
    )
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# HEADER — 6 métricas
# ══════════════════════════════════════════════════════════════════════════════

def _build_header_metrics() -> html.Div:
    metrics = []

    # 1. Brent
    try:
        cur, prev, chg_abs, chg_pct = get_change(ID_BRENT, period_days=1)
        val_str = f"${_safe(cur, '.2f')}" if cur else "—"
        sub = f"{_arrow(chg_pct)} {_safe(abs(chg_pct) if chg_pct else None, '.2f')}% 24h" if chg_pct else "Sin variación"
        shock_badge = None
        if cur and cur >= 100:
            shock_badge = html.Span("SHOCK ENERGÉTICO", style={
                "fontSize": "0.55rem", "fontWeight": "800", "color": "#fff",
                "background": "#ef4444", "padding": "1px 5px", "borderRadius": "3px",
                "letterSpacing": "0.05em",
            })
        metrics.append(_compact_metric("BRENT (BZ=F)", val_str, sub, _chg_color(chg_pct), badge=shock_badge))
    except Exception:
        metrics.append(_compact_metric("BRENT (BZ=F)", "—", "Sin datos", COLORS["text_muted"]))

    # 2. WTI
    try:
        cur, prev, chg_abs, chg_pct = get_change(ID_WTI, period_days=1)
        val_str = f"${_safe(cur, '.2f')}" if cur else "—"
        sub = f"{_arrow(chg_pct)} {_safe(abs(chg_pct) if chg_pct else None, '.2f')}% 24h" if chg_pct else "Sin variación"
        metrics.append(_compact_metric("WTI (CL=F)", val_str, sub, _chg_color(chg_pct)))
    except Exception:
        metrics.append(_compact_metric("WTI (CL=F)", "—", "Sin datos", COLORS["text_muted"]))

    # 3. Gas Natural HH
    try:
        cur, _, _, chg_pct = get_change(ID_GAS_HH, period_days=1)
        val_str = f"${_safe(cur, '.3f')}/MMBtu" if cur else "—"
        sub = f"{_arrow(chg_pct)} {_safe(abs(chg_pct) if chg_pct else None, '.2f')}% 24h" if chg_pct else "Sin variación"
        metrics.append(_compact_metric("GAS HENRY HUB (NG=F)", val_str, sub, _chg_color(chg_pct)))
    except Exception:
        metrics.append(_compact_metric("GAS HENRY HUB (NG=F)", "—", "Sin datos", COLORS["text_muted"]))

    # 4. Oro
    try:
        cur, _, _, chg_pct = get_change(ID_GOLD, period_days=1)
        val_str = f"${_safe(cur, ',.0f')}/oz" if cur else "—"
        sub = f"{_arrow(chg_pct)} {_safe(abs(chg_pct) if chg_pct else None, '.2f')}% 24h" if chg_pct else "Sin variación"
        metrics.append(_compact_metric("ORO (GC=F)", val_str, sub, _chg_color(chg_pct)))
    except Exception:
        metrics.append(_compact_metric("ORO (GC=F)", "—", "Sin datos", COLORS["text_muted"]))

    # 5. Cobre
    try:
        cur, _, _, chg_pct = get_change(ID_COPPER, period_days=1)
        val_str = f"${_safe(cur, '.3f')}/lb" if cur else "—"
        sub = f"{_arrow(chg_pct)} {_safe(abs(chg_pct) if chg_pct else None, '.2f')}% 24h" if chg_pct else "Sin variación"
        metrics.append(_compact_metric("COBRE (HG=F)", val_str, sub, _chg_color(chg_pct)))
    except Exception:
        metrics.append(_compact_metric("COBRE (HG=F)", "—", "Sin datos", COLORS["text_muted"]))

    # 6. Baltic Dry Index
    try:
        cur, _, _, chg_pct = get_change(ID_BDI, period_days=1)
        val_str = f"{_safe(cur, ',.0f')}" if cur else "—"
        sub = f"{_arrow(chg_pct)} {_safe(abs(chg_pct) if chg_pct else None, '.2f')}% 24h" if chg_pct else "Datos escasos"
        metrics.append(_compact_metric("BALTIC DRY INDEX", val_str, sub, _chg_color(chg_pct)))
    except Exception:
        metrics.append(_compact_metric("BALTIC DRY INDEX", "—", "Sin datos", COLORS["text_muted"]))

    ts = datetime.utcnow().strftime("%d/%m/%Y %H:%M UTC")
    return html.Div([
        html.Div(metrics, style={
            "display": "flex", "gap": "10px", "flexWrap": "wrap",
            "marginBottom": "6px",
        }),
        html.Div(f"Actualizado: {ts}", style={
            "fontSize": "0.62rem", "color": COLORS["text_label"],
            "textAlign": "right", "paddingRight": "4px",
        }),
    ])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — PETRÓLEO Y GAS
# ══════════════════════════════════════════════════════════════════════════════

def _build_tab1() -> html.Div:
    return html.Div([
        # 1.1 Panel de precios del petróleo
        create_section_header(
            "1.1 — Precios del Petróleo: Brent vs WTI",
            subtitle="Histórico con spread y niveles de referencia",
        ),
        html.Div([
            dbc.Row([
                dbc.Col(
                    dcc.Graph(id="m7-oil-price-chart", config={"displayModeBar": False}),
                    width=9,
                ),
                dbc.Col(
                    html.Div(id="m7-oil-recent-table"),
                    width=3,
                ),
            ], className="g-2"),
        ], style=_CARD),

        # 1.2 Rutas estratégicas
        create_section_header(
            "1.2 — Estado de Rutas Estratégicas de Tránsito Energético",
            subtitle="Actualización manual — fuentes: EIA, IEA, Reuters",
        ),
        html.Div([
            html.Div(id="m7-routes-table"),
            html.Div([
                html.Div(id="m7-routes-last-updated", style={
                    "fontSize": "0.70rem", "color": COLORS["text_muted"], "flex": "1",
                }),
                dbc.Button(
                    "✏️ Actualizar estado",
                    id="m7-routes-edit-btn",
                    size="sm",
                    color="secondary",
                    outline=True,
                    style={"fontSize": "0.72rem"},
                ),
            ], style={"marginTop": "10px", "display": "flex", "gap": "8px", "alignItems": "center"}),
            html.Div(
                "El Estrecho de Ormuz es el cuello de botella energético más crítico del mundo. "
                "Un bloqueo prolongado tiene impacto inmediato sobre el 20% del suministro mundial de petróleo "
                "y el 17% del gas natural licuado (LNG) global.",
                style=_NOTE,
            ),
        ], style=_CARD),

        # Modal de edición de rutas
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("Actualizar Estado de Rutas")),
            dbc.ModalBody(html.Div(id="m7-routes-modal-body")),
            dbc.ModalFooter([
                dbc.Button("Guardar", id="m7-routes-save-btn", color="primary", size="sm"),
                dbc.Button("Cancelar", id="m7-routes-cancel-btn", color="secondary",
                           outline=True, size="sm", className="ms-2"),
            ]),
        ], id="m7-routes-modal", is_open=False, size="lg"),

        # Store para estado de rutas en edición
        dcc.Store(id="m7-routes-store"),

        # 1.3 Producción global
        create_section_header(
            "1.3 — Producción Global de Petróleo por Bloque",
            subtitle="Millones de barriles/día — datos de referencia (IEA/EIA)",
        ),
        html.Div([
            dbc.Row([
                dbc.Col(
                    dcc.Graph(id="m7-oil-production-chart", config={"displayModeBar": False}),
                    width=8,
                ),
                dbc.Col(html.Div(id="m7-oil-production-table"), width=4),
            ], className="g-2"),
        ], style=_CARD),

        # 1.4 Impacto económico
        create_section_header(
            "1.4 — Impacto Económico del Precio del Petróleo",
        ),
        dbc.Row([
            dbc.Col(_build_oil_inflation_panel(), width=4),
            dbc.Col(_build_energy_dependence_panel(), width=4),
            dbc.Col(_build_oil_gdp_panel(), width=4),
        ], className="g-2", style={"marginBottom": "12px"}),

    ], style=_SECTION)


def _build_oil_inflation_panel() -> html.Div:
    return html.Div([
        html.Div("Correlación Petróleo–Inflación EE.UU.", style={
            "fontSize": "0.75rem", "fontWeight": "600", "color": COLORS["text"],
            "marginBottom": "8px",
        }),
        dcc.Graph(id="m7-oil-inflation-scatter", config={"displayModeBar": False}),
        html.Div(id="m7-oil-inflation-text", style={
            "fontSize": "0.72rem", "color": COLORS["text_muted"], "marginTop": "6px",
        }),
    ], style=_CARD)


def _build_energy_dependence_panel() -> html.Div:
    return html.Div([
        html.Div("Dependencia Energética por País (% importado)", style={
            "fontSize": "0.75rem", "fontWeight": "600", "color": COLORS["text"],
            "marginBottom": "8px",
        }),
        dcc.Graph(id="m7-energy-dependence-chart", config={"displayModeBar": False}),
    ], style=_CARD)


def _build_oil_gdp_panel() -> html.Div:
    return html.Div([
        html.Div("Precio Brent vs Crecimiento PIB Mundial", style={
            "fontSize": "0.75rem", "fontWeight": "600", "color": COLORS["text"],
            "marginBottom": "8px",
        }),
        dcc.Graph(id="m7-oil-gdp-chart", config={"displayModeBar": False}),
    ], style=_CARD)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — GAS NATURAL Y EUROPA
# ══════════════════════════════════════════════════════════════════════════════

def _build_tab2() -> html.Div:
    return html.Div([
        # 2.1 Precios del gas
        create_section_header(
            "2.1 — Precios del Gas: Henry Hub vs TTF Europeo",
            subtitle="Divergencia histórica entre el gas americano (barato) y europeo (caro desde 2021)",
        ),
        html.Div([
            dcc.Graph(id="m7-gas-prices-chart", config={"displayModeBar": False}),
            html.Div(
                "El gas natural en Europa llegó a costar en 2022 hasta 10 veces más que en EE.UU., "
                "devastando la competitividad industrial europea. La reconstrucción de infraestructura de LNG "
                "ha reducido el diferencial pero no eliminado la dependencia.",
                style=_NOTE,
            ),
        ], style=_CARD),

        # 2.2 Inventarios gas Europa
        create_section_header(
            "2.2 — Inventarios de Gas Natural en Europa",
            subtitle="Nivel actual de almacenamiento como % de capacidad total (AGSI+)",
        ),
        html.Div([
            dbc.Row([
                dbc.Col(dcc.Graph(id="m7-gas-storage-gauge", config={"displayModeBar": False}), width=5),
                dbc.Col(html.Div(id="m7-gas-storage-detail"), width=7),
            ], className="g-2"),
            html.Div(
                "El nivel de inventarios de gas europeos es crítico para determinar el precio del TTF y la "
                "vulnerabilidad de Europa ante interrupciones de suministro. La UE fijó un objetivo de llenado "
                "del 80% para el 1 de noviembre de cada año.",
                style=_NOTE,
            ),
        ], style=_CARD),

        # 2.3 Dependencia energética europea
        create_section_header(
            "2.3 — Dependencia Energética Europea Post-Rusia",
            subtitle="% energía importada — Banco Mundial",
        ),
        html.Div([
            dbc.Row([
                dbc.Col(dcc.Graph(id="m7-europe-dep-map", config={"displayModeBar": False}), width=7),
                dbc.Col(html.Div(id="m7-europe-dep-table"), width=5),
            ], className="g-2"),
            html.Div(
                "Desde la invasión de Ucrania (febrero 2022), Europa ha reducido drásticamente su dependencia "
                "del gas ruso del ~40% a menos del 10%, a costa de precios más altos y cambios estructurales "
                "en su mix energético.",
                style=_NOTE,
            ),
        ], style=_CARD),

        # 2.4 Mix energético
        create_section_header(
            "2.4 — Mix de Generación Eléctrica: Transición Energética Europea",
            subtitle="% renovables, nuclear, gas, carbón por país — Banco Mundial",
        ),
        html.Div([
            dcc.Graph(id="m7-energy-mix-chart", config={"displayModeBar": False}),
        ], style=_CARD),

    ], style=_SECTION)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — TRANSICIÓN ENERGÉTICA
# ══════════════════════════════════════════════════════════════════════════════

def _build_tab3() -> html.Div:
    return html.Div([
        # 3.1 Caída de costes tecnologías limpias
        create_section_header(
            "3.1 — La Deflación Tecnológica de las Energías Limpias",
            subtitle="Curvas de aprendizaje (Ley de Wright) — datos actualizables en data/clean_tech_costs.json",
        ),
        html.Div([
            dcc.Graph(id="m7-clean-tech-costs-chart", config={"displayModeBar": False}),
            html.Div(
                "La curva de aprendizaje de las energías renovables (Ley de Wright) sugiere que cada vez que "
                "la capacidad instalada se duplica, los costes caen entre un 15-20%. Este fenómeno hace que "
                "las proyecciones de adopción de los organismos oficiales queden sistemáticamente cortas.",
                style=_NOTE,
            ),
        ], style=_CARD),

        # 3.2 Capacidad instalada renovables
        create_section_header(
            "3.2 — Capacidad Instalada de Renovables Global (GW)",
            subtitle="Crecimiento explosivo de solar y eólica desde 2010",
        ),
        html.Div([
            dcc.Graph(id="m7-renewables-capacity-chart", config={"displayModeBar": False}),
        ], style=_CARD),

        # 3.3 Inversión global en energía
        create_section_header(
            "3.3 — Inversión Global en Energía: Limpia vs Fósil",
            subtitle="Miles de millones USD — el cruce ocurrió ~2022",
        ),
        html.Div([
            dbc.Row([
                dbc.Col(dcc.Graph(id="m7-energy-investment-chart", config={"displayModeBar": False}), width=8),
                dbc.Col(html.Div(id="m7-investment-leaders-table"), width=4),
            ], className="g-2"),
        ], style=_CARD),

        # 3.4 Adopción VE
        create_section_header(
            "3.4 — Adopción de Vehículos Eléctricos por País",
            subtitle="% cuota en ventas de coches nuevos — histórico y tendencia a 2030",
        ),
        html.Div([
            dcc.Graph(id="m7-ev-adoption-chart", config={"displayModeBar": False}),
            html.Div(
                "La adopción de vehículos eléctricos es el indicador más directo de la transición energética "
                "en el transporte, el sector que consume más petróleo. La velocidad de adopción en China es "
                "especialmente significativa dado su tamaño.",
                style=_NOTE,
            ),
        ], style=_CARD),

    ], style=_SECTION)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — MINERALES CRÍTICOS
# ══════════════════════════════════════════════════════════════════════════════

def _build_tab4() -> html.Div:
    return html.Div([
        # 4.1 Mapa de dependencia
        html.Div([
            html.Div(
                "La transición energética requiere enormes cantidades de minerales específicos: litio y cobalto "
                "para baterías, neodimio para imanes de turbinas eólicas y motores eléctricos, cobre para toda "
                "la electrificación, galio y germanio para semiconductores y paneles solares. El problema: la "
                "producción y el procesamiento de muchos de estos minerales está concentrado en un número muy "
                "pequeño de países, creando dependencias estratégicas similares a las del petróleo.",
                style={**_NOTE, "marginBottom": "12px"},
            ),
        ]),

        create_section_header(
            "4.1 — Concentración de Suministro de Minerales Críticos",
            subtitle="% producción minera top-3 países vs % procesamiento China",
        ),
        html.Div([
            dcc.Graph(id="m7-critical-minerals-chart", config={"displayModeBar": False}),
        ], style=_CARD),

        # 4.2 Precios de minerales críticos
        create_section_header(
            "4.2 — Precios de Minerales Críticos",
            subtitle="ETFs y proxies de mercado disponibles en BD",
        ),
        html.Div([
            dbc.Row([
                dbc.Col(dcc.Graph(id="m7-minerals-prices-chart", config={"displayModeBar": False}), width=8),
                dbc.Col(html.Div(id="m7-minerals-prices-table"), width=4),
            ], className="g-2"),
            html.Div(
                "El precio del litio se multiplicó por 10 entre 2021 y 2022 por la demanda de baterías, "
                "y luego colapsó un 80% en 2023-2024 por sobreproducción. Es un mercado de ciclos extremos.",
                style=_NOTE,
            ),
        ], style=_CARD),

        # 4.3 Mapa riesgo de suministro
        create_section_header(
            "4.3 — Mapa de Riesgo de Suministro por País",
            subtitle="Países productores de uno o más minerales críticos",
        ),
        html.Div([
            dcc.Graph(id="m7-supply-risk-map", config={"displayModeBar": False}),
        ], style=_CARD),

        # 4.4 La carta de China
        create_section_header(
            "4.4 — La Carta de China: Control de Minerales Críticos",
            subtitle="Cuota de China en producción y/o procesamiento",
        ),
        html.Div([
            dbc.Row([
                dbc.Col(dcc.Graph(id="m7-china-minerals-chart", config={"displayModeBar": False}), width=7),
                dbc.Col(html.Div(id="m7-china-timeline"), width=5),
            ], className="g-2"),
            html.Div(
                "En julio 2023, China impuso controles de exportación sobre galio y germanio (críticos para "
                "semiconductores y paneles solares). En diciembre 2023, añadió el grafito (esencial para baterías). "
                "Este patrón sugiere que China está convirtiendo su dominio en minerales críticos en palanca "
                "geopolítica, similar al 'arma del petróleo' de la OPEP en los años 70.",
                style=_NOTE,
            ),
        ], style=_CARD),

    ], style=_SECTION)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — SEGURIDAD ALIMENTARIA
# ══════════════════════════════════════════════════════════════════════════════

def _build_tab5() -> html.Div:
    return html.Div([
        # 5.1 Índice FAO
        create_section_header(
            "5.1 — Índice FAO de Precios de Alimentos",
            subtitle="FFPI desde 2000 — cereales, aceites vegetales, lácteos, carne, azúcar",
        ),
        html.Div([
            dcc.Graph(id="m7-fao-index-chart", config={"displayModeBar": False}),
        ], style=_CARD),

        # 5.2 Inventarios de granos
        create_section_header(
            "5.2 — Inventarios Mundiales de Granos Principales",
            subtitle="USDA WASDE — ratio stocks/consumo (meses de demanda cubiertos)",
        ),
        html.Div([
            html.Div(id="m7-grain-stocks-table"),
        ], style=_CARD),

        # 5.3 Mapa crisis alimentaria
        create_section_header(
            "5.3 — Países en Riesgo de Crisis Alimentaria",
            subtitle="WFP/FAO — escala: verde→amarillo→naranja→rojo→marrón (catástrofe)",
        ),
        html.Div([
            dbc.Row([
                dbc.Col(dcc.Graph(id="m7-food-crisis-map", config={"displayModeBar": False}), width=9),
                dbc.Col([
                    html.Div(id="m7-food-insecurity-metric"),
                ], width=3),
            ], className="g-2"),
        ], style=_CARD),

        # 5.4 Impacto conflictos
        create_section_header(
            "5.4 — Impacto de los Conflictos en la Cadena Alimentaria",
            subtitle="Datos cuantitativos sobre disrupciones al suministro global",
        ),
        html.Div([
            html.Div(id="m7-conflict-food-panel"),
        ], style=_CARD),

    ], style=_SECTION)


# ══════════════════════════════════════════════════════════════════════════════
# RENDER PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

def render_module_7() -> html.Div:
    return html.Div([
        # Header del módulo
        html.Div([
            html.Div("⚡ Energía y Materias Primas Estratégicas", className="module-title"),
            html.Div(
                "Petróleo · Gas · Transición Energética · Minerales Críticos · Seguridad Alimentaria",
                className="module-subtitle",
            ),
        ]),

        # 6 métricas fijas
        html.Div(_build_header_metrics(), style={"padding": "12px 16px 0 16px"}),

        # Intervalo de refresco de datos de mercado (5 min)
        dcc.Interval(id="m7-refresh-interval", interval=300_000, n_intervals=0),

        # Tabs principales
        dcc.Tabs(
            id="m7-main-tabs",
            value="tab-oil",
            style=TABS_STYLE,
            children=[
                dcc.Tab(label="🛢️ Petróleo y Gas",         value="tab-oil",
                        style=TAB_STYLE, selected_style=TAB_SELECTED_STYLE),
                dcc.Tab(label="🔥 Gas Natural y Europa",    value="tab-gas",
                        style=TAB_STYLE, selected_style=TAB_SELECTED_STYLE),
                dcc.Tab(label="♻️ Transición Energética",   value="tab-transition",
                        style=TAB_STYLE, selected_style=TAB_SELECTED_STYLE),
                dcc.Tab(label="💎 Minerales Críticos",      value="tab-minerals",
                        style=TAB_STYLE, selected_style=TAB_SELECTED_STYLE),
                dcc.Tab(label="🌾 Seguridad Alimentaria",   value="tab-food",
                        style=TAB_STYLE, selected_style=TAB_SELECTED_STYLE),
            ],
        ),

        # Contenido del tab seleccionado
        html.Div(id="m7-tab-content"),
    ])


# ══════════════════════════════════════════════════════════════════════════════
# FUNCIONES AUXILIARES PARA GRÁFICOS
# ══════════════════════════════════════════════════════════════════════════════

def _fig_oil_prices() -> go.Figure:
    df_b = get_series(ID_BRENT, days=365 * 6)
    df_w = get_series(ID_WTI,   days=365 * 6)

    fig = go.Figure()

    if not df_b.empty:
        fig.add_trace(go.Scatter(
            x=df_b["timestamp"], y=df_b["value"],
            name="Brent", line={"color": "#f97316", "width": 2},
        ))
    if not df_w.empty:
        fig.add_trace(go.Scatter(
            x=df_w["timestamp"], y=df_w["value"],
            name="WTI", line={"color": "#3b82f6", "width": 2},
        ))

    # Spread Brent-WTI en eje secundario
    if not df_b.empty and not df_w.empty:
        merged = pd.merge(
            df_b.rename(columns={"value": "brent"}),
            df_w.rename(columns={"value": "wti"}),
            on="timestamp", how="inner",
        )
        if not merged.empty:
            merged["spread"] = merged["brent"] - merged["wti"]
            fig.add_trace(go.Scatter(
                x=merged["timestamp"], y=merged["spread"],
                name="Spread B-W", yaxis="y2",
                line={"color": "#8b5cf6", "width": 1.5, "dash": "dot"},
                opacity=0.8,
            ))

    # Líneas de referencia
    ref_lines = [
        (60,  "#10b981", "Equilibrio fiscal Arabia Saudí (~60$)"),
        (80,  "#f59e0b", "Precio cómodo OPEP (~80$)"),
        (100, "#ef4444", "Umbral shock energético (100$)"),
        (130, "#991b1b", "Crisis energética severa (130$)"),
    ]
    for price, color, label in ref_lines:
        fig.add_hline(y=price, line_dash="dash", line_color=color,
                      line_width=1, opacity=0.6,
                      annotation_text=label,
                      annotation_position="right",
                      annotation_font_size=9,
                      annotation_font_color=color)

    # Anotaciones clave
    annotations = [
        ("2020-04-20", -37,  "COVID −37$"),
        ("2022-06-01", 124,  "Máx. 2022"),
    ]
    for date_str, y, label in annotations:
        try:
            fig.add_annotation(
                x=date_str, y=y, text=label,
                showarrow=True, arrowhead=2, arrowsize=0.8,
                font={"size": 9, "color": "#e5e7eb"},
                arrowcolor="#6b7280", ax=0, ay=-25,
            )
        except Exception:
            pass

    layout = get_base_layout("Brent y WTI (USD/barril)", height=380)
    layout.update({
        "yaxis":  {"title": {"text": "USD/barril"}, **layout.get("yaxis", {})},
        "yaxis2": {
            "title": {"text": "Spread (USD)", "font": {"color": "#8b5cf6", "size": 10}},
            "overlaying": "y", "side": "right",
            "gridcolor": "#1f2937", "tickfont": {"color": "#8b5cf6", "size": 10},
            "showgrid": False,
        },
        "xaxis": {**layout.get("xaxis", {}), "rangeselector": get_time_range_buttons()},
        "legend": {"orientation": "h", "y": -0.12},
    })
    fig.update_layout(layout)
    return fig


def _table_oil_recent() -> html.Div:
    df_b = get_series(ID_BRENT, days=15)
    df_w = get_series(ID_WTI, days=15)
    if df_b.empty and df_w.empty:
        return create_empty_state("Sin datos recientes")

    rows = []
    merged = pd.merge(
        df_b.rename(columns={"value": "brent"}),
        df_w.rename(columns={"value": "wti"}),
        on="timestamp", how="outer",
    ).sort_values("timestamp", ascending=False).head(10)

    for _, row in merged.iterrows():
        date_s = row["timestamp"].strftime("%d/%m") if pd.notna(row["timestamp"]) else "—"
        b = f"${row['brent']:.2f}" if pd.notna(row.get("brent")) else "—"
        w = f"${row['wti']:.2f}" if pd.notna(row.get("wti")) else "—"
        rows.append(html.Tr([
            html.Td(date_s, style={"fontSize": "0.70rem", "color": COLORS["text_muted"]}),
            html.Td(b, style={"fontSize": "0.72rem", "color": "#f97316"}),
            html.Td(w, style={"fontSize": "0.72rem", "color": "#3b82f6"}),
        ]))

    return html.Div([
        html.Div("Últimos 10 días", style={
            "fontSize": "0.68rem", "fontWeight": "600",
            "color": COLORS["text_label"], "marginBottom": "6px",
        }),
        html.Table([
            html.Thead(html.Tr([
                html.Th("Fecha", style={"fontSize": "0.65rem"}),
                html.Th("Brent", style={"fontSize": "0.65rem", "color": "#f97316"}),
                html.Th("WTI",   style={"fontSize": "0.65rem", "color": "#3b82f6"}),
            ])),
            html.Tbody(rows),
        ], className="data-table", style={"fontSize": "0.70rem"}),
    ])


def _build_routes_table(data: dict) -> html.Div:
    if not data:
        return create_empty_state("No se pudo cargar datos de rutas")

    header = html.Thead(html.Tr([
        html.Th("Ruta estratégica"),
        html.Th("Barr/día"),
        html.Th("% Comercio"),
        html.Th("Estado"),
        html.Th("Notas", style={"maxWidth": "260px"}),
    ]))

    rows = []
    for r in data.get("routes", []):
        bpd = f"{r['barrels_per_day'] / 1_000_000:.0f}M" if r.get("barrels_per_day", 0) > 0 else "—"
        rows.append(html.Tr([
            html.Td(r["name"], style={"fontWeight": "600", "fontSize": "0.78rem"}),
            html.Td(bpd),
            html.Td(f"{r['pct_global_trade']}%"),
            html.Td(_route_badge(r["status"])),
            html.Td(r.get("notes", ""), style={
                "fontSize": "0.70rem", "color": COLORS["text_muted"],
                "maxWidth": "260px", "whiteSpace": "normal",
            }),
        ]))

    return html.Table(
        [header, html.Tbody(rows)],
        className="data-table",
        style={"width": "100%"},
    )


def _fig_oil_production() -> go.Figure:
    # Datos estáticos de referencia (Mb/d, 2015-2024)
    years = [2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024]
    opec_plus = [33.8, 33.1, 32.5, 33.9, 34.1, 30.5, 31.8, 33.2, 34.0, 34.5]
    usa       = [9.4, 8.8, 9.4, 11.0, 12.9, 11.3, 11.2, 12.0, 13.2, 13.5]
    rest      = [14.2, 14.0, 14.1, 14.5, 14.5, 13.2, 13.5, 14.1, 14.8, 15.0]

    fig = go.Figure()
    fig.add_trace(go.Bar(x=years, y=opec_plus, name="OPEP+", marker_color="#ef4444"))
    fig.add_trace(go.Bar(x=years, y=usa,       name="EE.UU.", marker_color="#3b82f6"))
    fig.add_trace(go.Bar(x=years, y=rest,      name="Resto mundo", marker_color="#6b7280"))

    layout = get_base_layout("Producción Global de Petróleo (Mb/d)", height=340)
    layout.update({"barmode": "stack", "legend": {"orientation": "h", "y": -0.12}})
    fig.update_layout(layout)
    return fig


def _table_oil_production() -> html.Div:
    countries = [
        ("🇸🇦 Arabia Saudí", 9.0), ("🇷🇺 Rusia", 9.5), ("🇺🇸 EE.UU.", 13.5),
        ("🇮🇶 Iraq", 4.2), ("🇦🇪 EAU", 3.5), ("🇨🇦 Canadá", 5.5),
        ("🇮🇷 Irán*", 3.2), ("🇰🇼 Kuwait", 2.5),
    ]
    rows = [
        html.Tr([
            html.Td(name, style={"fontSize": "0.72rem"}),
            html.Td(f"{mb:.1f} Mb/d", style={"fontSize": "0.72rem", "color": COLORS["accent"]}),
        ])
        for name, mb in countries
    ]
    return html.Div([
        html.Div("Prod. actual est.", style={
            "fontSize": "0.68rem", "fontWeight": "600",
            "color": COLORS["text_label"], "marginBottom": "6px",
        }),
        html.Table([
            html.Thead(html.Tr([html.Th("País"), html.Th("Producción")])),
            html.Tbody(rows),
        ], className="data-table"),
        html.Div("* Reducido por sanciones", style={
            "fontSize": "0.62rem", "color": COLORS["text_label"], "marginTop": "4px",
        }),
    ])


def _fig_oil_inflation_scatter() -> tuple[go.Figure, str]:
    result = calculate_oil_inflation_correlation(months=60)
    if result is None or result.get("df") is None or result["df"].empty:
        return _empty_fig("Datos insuficientes"), "Sin datos suficientes"

    df = result["df"]
    corr = result["correlation"]
    slope = result["slope_per_10usd"]
    n = result["n_obs"]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["brent"], y=df["cpi_yoy"],
        mode="markers",
        marker={"color": "#3b82f6", "size": 6, "opacity": 0.7},
        name="Obs. mensual",
        hovertemplate="Brent: $%{x:.1f}<br>Inflación YoY: %{y:.2f}%<extra></extra>",
    ))

    # Línea de regresión
    if not df["brent"].isna().all():
        import numpy as np
        x_range = [df["brent"].min(), df["brent"].max()]
        slope_est = (df["cpi_yoy"].corr(df["brent"]) *
                     df["cpi_yoy"].std() / df["brent"].std()
                     if df["brent"].std() > 0 else 0)
        intercept_est = df["cpi_yoy"].mean() - slope_est * df["brent"].mean()
        y_range = [slope_est * x + intercept_est for x in x_range]
        fig.add_trace(go.Scatter(
            x=x_range, y=y_range,
            mode="lines",
            line={"color": "#f59e0b", "width": 2, "dash": "dash"},
            name="Regresión",
        ))

    layout = get_base_layout(height=280)
    layout.update({
        "xaxis": {**layout.get("xaxis", {}), "title": {"text": "Brent (USD/barril)"}},
        "yaxis": {**layout.get("yaxis", {}), "title": {"text": "Inflación YoY (%)"}},
        "margin": {"l": 45, "r": 15, "t": 20, "b": 40},
        "showlegend": False,
    })
    fig.update_layout(layout)

    direction = "positiva" if corr >= 0 else "negativa"
    sign = "+" if slope >= 0 else ""
    text = (
        f"Correlación {direction} de {corr:.2f} (n={n} meses). "
        f"Cada +10$ en Brent → {sign}{slope:.2f}pp en inflación americana (lag ~3m)."
    )
    return fig, text


def _fig_energy_dependence() -> go.Figure:
    df = get_world_bank_indicator("energy_imports")
    # Fallback a datos estáticos si no hay datos en BD
    if df.empty or len(df) < 5:
        data = {
            "JPN": 88, "KOR": 82, "ITA": 75, "ESP": 68, "DEU": 61,
            "FRA": 48, "GBR": 40, "CHN": 18, "BRA": 12, "USA": 8,
            "RUS": -50, "SAU": -200,
        }
        iso3 = list(data.keys())
        vals = list(data.values())
    else:
        df = df.sort_values("value", ascending=False).head(20)
        iso3 = df["country_iso3"].tolist()
        vals = df["value"].tolist()

    iso_names = {
        "JPN": "🇯🇵 Japón", "KOR": "🇰🇷 Corea S.", "ITA": "🇮🇹 Italia",
        "ESP": "🇪🇸 España", "DEU": "🇩🇪 Alemania", "FRA": "🇫🇷 Francia",
        "GBR": "🇬🇧 R.Unido", "CHN": "🇨🇳 China", "BRA": "🇧🇷 Brasil",
        "USA": "🇺🇸 EE.UU.", "RUS": "🇷🇺 Rusia", "SAU": "🇸🇦 Arabia S.",
    }
    colors = []
    for v in vals:
        if v >= 75:   colors.append("#ef4444")
        elif v >= 50: colors.append("#f97316")
        elif v >= 25: colors.append("#f59e0b")
        else:         colors.append("#10b981")

    labels = [iso_names.get(c, c) for c in iso3]
    fig = go.Figure(go.Bar(
        x=vals, y=labels, orientation="h",
        marker_color=colors, showlegend=False,
        hovertemplate="%{y}: %{x:.1f}%<extra></extra>",
    ))
    layout = get_base_layout(height=320)
    layout.update({
        "xaxis": {**layout.get("xaxis", {}), "title": {"text": "% energía importada"}},
        "margin": {"l": 90, "r": 20, "t": 15, "b": 30},
    })
    fig.update_layout(layout)
    return fig


def _fig_oil_gdp() -> go.Figure:
    df_brent = get_series(ID_BRENT, days=365 * 26)
    df_gdp   = get_world_bank_indicator("gdp_growth")

    fig = go.Figure()

    # Brent anualizado
    if not df_brent.empty:
        df_brent["timestamp"] = pd.to_datetime(df_brent["timestamp"])
        df_brent_y = (df_brent.set_index("timestamp")["value"]
                      .resample("YS").mean().reset_index())
        fig.add_trace(go.Scatter(
            x=df_brent_y["timestamp"], y=df_brent_y["value"],
            name="Brent (prom. anual)", yaxis="y",
            line={"color": "#f97316", "width": 2},
        ))

    # Crecimiento global (WLD)
    if not df_gdp.empty:
        wld = df_gdp[df_gdp["country_iso3"] == "WLD"]
        if not wld.empty:
            fig.add_trace(go.Scatter(
                x=wld.get("year", pd.Series([])),
                y=wld["value"],
                name="Crecim. PIB mundial (%)",
                yaxis="y2",
                line={"color": "#10b981", "width": 2},
                mode="lines+markers", marker_size=5,
            ))

    layout = get_base_layout("Precio del Petróleo vs Crecimiento Global", height=300)
    layout.update({
        "yaxis":  {**layout.get("yaxis", {}), "title": {"text": "USD/barril"}},
        "yaxis2": {
            "title": {"text": "PIB mundial (%)", "font": {"color": "#10b981", "size": 10}},
            "overlaying": "y", "side": "right",
            "tickfont": {"color": "#10b981", "size": 10},
            "showgrid": False,
        },
        "legend": {"orientation": "h", "y": -0.15},
        "margin": {"l": 45, "r": 50, "t": 30, "b": 45},
    })
    fig.update_layout(layout)
    return fig


# ── Tab 2 helpers ──────────────────────────────────────────────────────────────

def _fig_gas_prices() -> go.Figure:
    df_hh  = get_series(ID_GAS_HH,  days=365 * 6)
    df_ttf = get_series(ID_GAS_TTF, days=365 * 6)

    fig = go.Figure()
    if not df_hh.empty:
        fig.add_trace(go.Scatter(
            x=df_hh["timestamp"], y=df_hh["value"],
            name="Henry Hub (USD/MMBtu)",
            line={"color": "#3b82f6", "width": 2},
        ))
    if not df_ttf.empty:
        fig.add_trace(go.Scatter(
            x=df_ttf["timestamp"], y=df_ttf["value"],
            name="TTF Europeo (EUR/MWh)",
            yaxis="y2",
            line={"color": "#f97316", "width": 2},
        ))

    # Anotación pico TTF 2022
    try:
        fig.add_annotation(
            x="2022-08-26", y=350,
            text="Pico TTF<br>~350 EUR/MWh",
            showarrow=True, arrowhead=2,
            font={"size": 9, "color": "#f97316"},
            arrowcolor="#f97316", ax=0, ay=-35,
        )
    except Exception:
        pass

    layout = get_base_layout("Gas Natural: Henry Hub vs TTF Europeo", height=380)
    layout.update({
        "yaxis":  {**layout.get("yaxis", {}), "title": {"text": "USD/MMBtu (Henry Hub)"}},
        "yaxis2": {
            "title": {"text": "EUR/MWh (TTF)", "font": {"color": "#f97316", "size": 10}},
            "overlaying": "y", "side": "right",
            "tickfont": {"color": "#f97316", "size": 10},
            "showgrid": False,
        },
        "xaxis": {**layout.get("xaxis", {}), "rangeselector": get_time_range_buttons()},
        "legend": {"orientation": "h", "y": -0.12},
    })
    fig.update_layout(layout)
    return fig


def _fig_gas_storage_gauge(data: dict) -> go.Figure:
    pct = data.get("eu_gas_storage_pct", 0) if data else 0
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=pct,
        number={"suffix": "%", "font": {"color": "#e5e7eb", "size": 36}},
        delta={
            "reference": data.get("eu_gas_storage_previous_year_pct", pct) if data else pct,
            "relative": False,
            "valueformat": ".1f",
            "suffix": "pp vs año ant.",
        },
        gauge={
            "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "#9ca3af",
                     "tickfont": {"size": 10}},
            "bar": {"color": "#3b82f6", "thickness": 0.25},
            "bgcolor": "#111827",
            "borderwidth": 1,
            "bordercolor": "#1f2937",
            "steps": [
                {"range": [0, 30],  "color": "#7f1d1d"},
                {"range": [30, 60], "color": "#78350f"},
                {"range": [60, 80], "color": "#713f12"},
                {"range": [80, 100],"color": "#14532d"},
            ],
            "threshold": {
                "line": {"color": "#f59e0b", "width": 3},
                "thickness": 0.75,
                "value": data.get("eu_gas_storage_target", 80) if data else 80,
            },
        },
        title={"text": "Almacenamiento Gas UE<br><span style='font-size:0.7em;color:#9ca3af'>% capacidad total</span>"},
    ))
    fig.update_layout(
        height=300,
        paper_bgcolor="#0a0e1a",
        plot_bgcolor="#111827",
        font={"color": "#e5e7eb", "family": "'Inter', system-ui, sans-serif"},
        margin={"l": 20, "r": 20, "t": 60, "b": 10},
    )
    return fig


def _build_gas_storage_detail(data: dict) -> html.Div:
    if not data:
        return create_empty_state("Datos de almacenamiento no disponibles")
    pct     = data.get("eu_gas_storage_pct", 0)
    twh     = data.get("eu_gas_storage_twh", 0)
    target  = data.get("eu_gas_storage_target", 80)
    prev_yr = data.get("eu_gas_storage_previous_year_pct", 0)
    avg_5y  = data.get("eu_gas_storage_5y_avg_pct", 0)

    status_color = "#10b981" if pct >= 80 else ("#f59e0b" if pct >= 60 else
                   ("#f97316" if pct >= 30 else "#ef4444"))
    status_label = ("Bien abastecido" if pct >= 80 else
                    "Normal" if pct >= 60 else
                    "Atención" if pct >= 30 else "CRÍTICO")

    rows = [
        ("Nivel actual", f"{pct:.1f}%", status_color),
        ("En TWh", f"{twh:,.0f} TWh", COLORS["text"]),
        ("Objetivo UE (1 nov)", f"{target:.0f}%", "#f59e0b"),
        ("Año anterior mismo período", f"{prev_yr:.1f}%",
         _chg_color(pct - prev_yr, higher_bad=False)),
        ("Media 5 años", f"{avg_5y:.1f}%",
         _chg_color(pct - avg_5y, higher_bad=False)),
    ]

    items = [
        html.Div([
            html.Span(label, style={"fontSize": "0.72rem", "color": COLORS["text_muted"]}),
            html.Span(value, style={"fontSize": "0.82rem", "fontWeight": "700", "color": color}),
        ], style={"display": "flex", "justifyContent": "space-between",
                  "padding": "5px 0", "borderBottom": f"1px solid {COLORS['border']}"})
        for label, value, color in rows
    ]
    return html.Div([
        html.Div(status_label, style={
            "fontSize": "0.80rem", "fontWeight": "700", "color": status_color,
            "marginBottom": "10px",
            "padding": "4px 10px", "background": f"{status_color}18",
            "borderRadius": "4px", "display": "inline-block",
        }),
        *items,
        html.Div("Fuente: AGSI+ (Gas Infrastructure Europe) — actualización manual",
                 style={"fontSize": "0.62rem", "color": COLORS["text_label"], "marginTop": "6px"}),
    ])


def _fig_europe_dep_map() -> go.Figure:
    df = get_world_bank_indicator("energy_imports")

    eu_countries = ["DEU", "FRA", "ITA", "ESP", "PRT", "GRC", "NLD", "BEL",
                    "AUT", "POL", "CZE", "HUN", "SVK", "ROM", "BGR", "HRV",
                    "SVN", "EST", "LVA", "LTU", "FIN", "SWE", "DNK", "IRL",
                    "NOR", "CHE", "GBR", "UKR"]

    if df.empty or len(df) < 5:
        data = {"DEU": 61, "FRA": 48, "ITA": 75, "ESP": 68, "PRT": 72,
                "GRC": 74, "NLD": 52, "BEL": 72, "AUT": 63, "POL": 40,
                "FIN": 45, "SWE": 37, "DNK": 28, "IRL": 65, "NOR": -300,
                "CHE": 52, "GBR": 40, "UKR": 18, "HUN": 60, "ROM": 30}
        iso3 = list(data.keys())
        vals = list(data.values())
    else:
        sub = df[df["country_iso3"].isin(eu_countries)].copy()
        sub = sub.sort_values("value", ascending=False)
        iso3 = sub["country_iso3"].tolist()
        vals = sub["value"].tolist()

    import plotly.express as px
    df_map = pd.DataFrame({"iso3": iso3, "value": vals})
    fig = px.choropleth(
        df_map,
        locations="iso3",
        color="value",
        scope="europe",
        color_continuous_scale=[[0, "#14532d"], [0.3, "#f59e0b"],
                                 [0.6, "#f97316"], [1.0, "#991b1b"]],
        range_color=[0, 90],
        labels={"value": "% energía importada"},
        hover_name="iso3",
        hover_data={"value": ":.1f"},
    )
    fig.update_layout(
        height=350,
        paper_bgcolor="#0a0e1a",
        plot_bgcolor="#0a0e1a",
        geo={"bgcolor": "#0a0e1a", "lakecolor": "#111827",
             "landcolor": "#1f2937", "showframe": False,
             "showcoastlines": True, "coastlinecolor": "#374151"},
        margin={"l": 0, "r": 0, "t": 10, "b": 10},
        coloraxis_colorbar={"thickness": 12, "len": 0.6,
                            "tickfont": {"color": "#9ca3af", "size": 10},
                            "title": {"text": "%", "font": {"color": "#9ca3af"}}},
    )
    return fig


def _build_europe_dep_table() -> html.Div:
    entries = [
        ("🇩🇪 Alemania",    61, "Gasoducto Noruega, LNG EE.UU."),
        ("🇫🇷 Francia",     48, "Nuclear + LNG"),
        ("🇮🇹 Italia",      75, "Argelia, Azerbaiyán, LNG"),
        ("🇪🇸 España",      68, "LNG GNL, Argelia, Noruega"),
        ("🇵🇹 Portugal",    72, "LNG, Argelia"),
        ("🇬🇷 Grecia",      74, "Azerbaiyán, LNG, Bulgaria"),
        ("🇳🇱 Países Bajos",52, "Noruega, LNG hub"),
        ("🇵🇱 Polonia",     40, "Noruega, EEUU LNG, diversific."),
    ]
    rows = [
        html.Tr([
            html.Td(name, style={"fontSize": "0.70rem"}),
            html.Td(f"{pct}%", style={
                "fontSize": "0.70rem",
                "color": ("#ef4444" if pct >= 75 else
                          "#f97316" if pct >= 50 else "#10b981"),
                "fontWeight": "700",
            }),
            html.Td(src, style={"fontSize": "0.63rem", "color": COLORS["text_muted"]}),
        ])
        for name, pct, src in entries
    ]
    return html.Div([
        html.Div("Dep. energética Europa", style={
            "fontSize": "0.68rem", "fontWeight": "600",
            "color": COLORS["text_label"], "marginBottom": "6px",
        }),
        html.Table([
            html.Thead(html.Tr([
                html.Th("País"), html.Th("% Imp."), html.Th("Fuente sustitución"),
            ])),
            html.Tbody(rows),
        ], className="data-table"),
    ])


def _fig_energy_mix() -> go.Figure:
    countries = ["NOR", "FRA", "ESP", "DEU", "GBR", "ITA", "POL"]
    df_renew = get_world_bank_indicator("renewable_elec")
    df_fossil = get_world_bank_indicator("fossil_elec")

    # Datos de fallback
    fallback = {
        "NOR": (98, 0, 1, 1), "FRA": (22, 69, 8, 1), "ESP": (52, 19, 24, 5),
        "DEU": (46, 11, 35, 8), "GBR": (43, 14, 40, 3),
        "ITA": (42, 0, 50, 8), "POL": (24, 0, 70, 6),
    }
    labels_c = {"NOR": "🇳🇴 Noruega", "FRA": "🇫🇷 Francia", "ESP": "🇪🇸 España",
                "DEU": "🇩🇪 Alemania", "GBR": "🇬🇧 R.Unido",
                "ITA": "🇮🇹 Italia", "POL": "🇵🇱 Polonia"}

    ren, nuc, gas_mix, coal = [], [], [], []
    labels = []
    for c in sorted(fallback.keys(), key=lambda x: -fallback[x][0]):
        r, n, g, co = fallback[c]
        ren.append(r); nuc.append(n); gas_mix.append(g); coal.append(co)
        labels.append(labels_c.get(c, c))

    fig = go.Figure()
    fig.add_trace(go.Bar(name="Renovables", x=labels, y=ren,  marker_color="#10b981"))
    fig.add_trace(go.Bar(name="Nuclear",    x=labels, y=nuc,  marker_color="#8b5cf6"))
    fig.add_trace(go.Bar(name="Gas",        x=labels, y=gas_mix, marker_color="#f97316"))
    fig.add_trace(go.Bar(name="Carbón",     x=labels, y=coal, marker_color="#6b7280"))

    layout = get_base_layout("Mix de Generación Eléctrica — Europa (%)", height=340)
    layout.update({"barmode": "stack", "legend": {"orientation": "h", "y": -0.12},
                   "yaxis": {**layout.get("yaxis", {}), "title": {"text": "%"}}})
    fig.update_layout(layout)
    return fig


# ── Tab 3 helpers ──────────────────────────────────────────────────────────────

def _fig_clean_tech_costs() -> go.Figure:
    data = load_json_data("clean_tech_costs.json")
    if not data:
        return _empty_fig("No se pudo cargar data/clean_tech_costs.json")

    fig = go.Figure()

    bat = data.get("battery_cost_usd_kwh", {})
    if bat:
        years_b = [int(y) for y in bat.keys()]
        vals_b  = list(bat.values())
        fig.add_trace(go.Scatter(
            x=years_b, y=vals_b, name="Batería Li-ion (USD/kWh)",
            mode="lines+markers", line={"color": "#3b82f6", "width": 2},
            marker_size=6, yaxis="y",
        ))

    sol = data.get("solar_pv_cost_usd_w", {})
    if sol:
        years_s = [int(y) for y in sol.keys()]
        vals_s  = list(sol.values())
        fig.add_trace(go.Scatter(
            x=years_s, y=vals_s, name="Solar FV (USD/W)",
            mode="lines+markers", line={"color": "#f59e0b", "width": 2},
            marker_size=6, yaxis="y2",
        ))

    wind = data.get("onshore_wind_cost_usd_kw", {})
    if wind:
        years_w = [int(y) for y in wind.keys()]
        vals_w  = [v / 1000 for v in wind.values()]  # USD/kW
        fig.add_trace(go.Scatter(
            x=years_w, y=vals_w, name="Eólica terrestre (USD/kW, ÷1000)",
            mode="lines+markers", line={"color": "#10b981", "width": 2},
            marker_size=6, yaxis="y2",
        ))

    last_upd = data.get("last_updated", "?")
    layout = get_base_layout(f"Caída de Costes: Tecnologías Limpias (datos: {last_upd})", height=380)
    layout.update({
        "yaxis":  {**layout.get("yaxis", {}),
                   "title": {"text": "USD/kWh (batería)"},
                   "type": "log"},
        "yaxis2": {
            "title": {"text": "USD/W (solar) · USD/kW÷1000 (eólica)",
                      "font": {"color": "#9ca3af", "size": 10}},
            "overlaying": "y", "side": "right",
            "type": "log",
            "tickfont": {"size": 10, "color": "#9ca3af"},
            "showgrid": False,
        },
        "legend": {"orientation": "h", "y": -0.12},
    })
    fig.update_layout(layout)
    return fig


def _fig_renewables_capacity() -> go.Figure:
    # Datos IEA/IRENA (GW instalados totales globales)
    years  = [2010, 2012, 2014, 2016, 2018, 2020, 2021, 2022, 2023, 2024]
    solar  = [40,   100,  177,  295,  500,  714,  843, 1050, 1418, 1900]
    wind   = [197,  283,  370,  487,  591,  733,  824,  899,  999, 1100]
    hydro  = [1013, 1055, 1100, 1150, 1290, 1330, 1360, 1400, 1420, 1440]
    nuclear= [375,  373,  376,  391,  396,  393,  393,  394,  415,  420]
    gas    = [1550, 1620, 1700, 1800, 1900, 1980, 2000, 2080, 2130, 2180]
    coal   = [1200, 1350, 1490, 1620, 1670, 1680, 1720, 1740, 1740, 1730]

    fig = go.Figure()
    fig.add_trace(go.Bar(x=years, y=solar,  name="Solar",    marker_color="#f59e0b"))
    fig.add_trace(go.Bar(x=years, y=wind,   name="Eólica",   marker_color="#3b82f6"))
    fig.add_trace(go.Bar(x=years, y=hydro,  name="Hidráulica",marker_color="#06b6d4"))
    fig.add_trace(go.Bar(x=years, y=nuclear,name="Nuclear",  marker_color="#8b5cf6"))
    fig.add_trace(go.Bar(x=years, y=gas,    name="Gas",      marker_color="#f97316"))
    fig.add_trace(go.Bar(x=years, y=coal,   name="Carbón",   marker_color="#6b7280"))

    layout = get_base_layout("Capacidad de Generación Global Instalada (GW)", height=380)
    layout.update({
        "barmode": "stack",
        "legend": {"orientation": "h", "y": -0.12},
        "yaxis": {**layout.get("yaxis", {}), "title": {"text": "GW"}},
    })
    fig.update_layout(layout)
    return fig


def _fig_energy_investment() -> go.Figure:
    years    = [2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024]
    clean    = [286,  297,  333,  365,  381,  367,  480,  574,  735,  850]
    fossil   = [620,  510,  540,  590,  630,  490,  570,  650,  600,  580]

    fig = go.Figure()
    fig.add_trace(go.Bar(x=years, y=fossil, name="Energía fósil", marker_color="#f97316", opacity=0.8))
    fig.add_trace(go.Bar(x=years, y=clean,  name="Energía limpia", marker_color="#10b981"))

    # Anotación del cruce
    fig.add_annotation(
        x=2022, y=650, text="Cruce: limpia > fósil",
        showarrow=True, arrowhead=2, ax=0, ay=-40,
        font={"size": 9, "color": "#10b981"}, arrowcolor="#10b981",
    )

    layout = get_base_layout("Inversión Global en Energía (Miles M USD)", height=360)
    layout.update({
        "barmode": "group",
        "legend": {"orientation": "h", "y": -0.12},
        "yaxis": {**layout.get("yaxis", {}), "title": {"text": "Miles de millones USD"}},
    })
    fig.update_layout(layout)
    return fig


def _table_investment_leaders() -> html.Div:
    leaders = [
        ("🇨🇳 China",   "~380"),
        ("🇺🇸 EE.UU.",  "~160"),
        ("🇪🇺 UE",      "~90"),
        ("🇩🇪 Alemania","~60"),
        ("🇬🇧 R.Unido", "~40"),
        ("🇯🇵 Japón",   "~35"),
        ("🇮🇳 India",   "~30"),
    ]
    rows = [
        html.Tr([
            html.Td(name, style={"fontSize": "0.72rem"}),
            html.Td(val, style={"fontSize": "0.72rem", "color": "#10b981", "fontWeight": "700"}),
        ])
        for name, val in leaders
    ]
    return html.Div([
        html.Div("Inversión limpia 2024 (est.)", style={
            "fontSize": "0.68rem", "fontWeight": "600",
            "color": COLORS["text_label"], "marginBottom": "6px",
        }),
        html.Table([
            html.Thead(html.Tr([html.Th("País/Bloque"), html.Th("MMM USD")])),
            html.Tbody(rows),
        ], className="data-table"),
    ])


def _fig_ev_adoption() -> go.Figure:
    years_hist = [2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024]
    years_proj = [2024, 2025, 2026, 2027, 2028, 2029, 2030]

    ev_data = {
        "🇳🇴 Noruega":  ([3, 15, 22, 31, 42, 55, 65, 79, 82, 88], "#10b981"),
        "🇨🇳 China":    ([0.7, 1.4, 2.2, 4.3, 4.7, 5.7, 13, 25, 35, 45], "#f97316"),
        "🇩🇪 Alemania": ([0.2, 0.3, 0.6, 1.0, 1.8, 6.7, 13, 18, 20, 22], "#3b82f6"),
        "🇫🇷 Francia":  ([1.2, 1.5, 1.7, 2.0, 2.8, 6.7, 9.8, 13, 16, 18], "#8b5cf6"),
        "🇪🇸 España":   ([0.1, 0.1, 0.2, 0.5, 0.6, 1.3, 2.5, 5.0, 7.0, 9.0], "#f59e0b"),
        "🇺🇸 EE.UU.":   ([0.4, 0.7, 1.2, 2.0, 1.9, 2.2, 3.5, 5.8, 7.6, 9.0], "#ef4444"),
    }
    proj_slope = {
        "🇳🇴 Noruega": 2.0, "🇨🇳 China": 4.0, "🇩🇪 Alemania": 2.5,
        "🇫🇷 Francia": 2.0, "🇪🇸 España": 3.0, "🇺🇸 EE.UU.": 2.5,
    }

    fig = go.Figure()
    for name, (vals, color) in ev_data.items():
        fig.add_trace(go.Scatter(
            x=years_hist, y=vals, name=name,
            mode="lines+markers", line={"color": color, "width": 2},
            marker_size=5,
        ))
        # Proyección 2025-2030 (línea punteada)
        last_val = vals[-1]
        slope = proj_slope.get(name, 2.0)
        proj_vals = [min(last_val + slope * i, 100) for i in range(len(years_proj))]
        fig.add_trace(go.Scatter(
            x=years_proj, y=proj_vals, name=f"{name} (proj.)",
            mode="lines", line={"color": color, "width": 1.5, "dash": "dot"},
            showlegend=False, opacity=0.6,
        ))

    layout = get_base_layout("Cuota VE en Ventas de Coches Nuevos (%)", height=400)
    layout.update({
        "yaxis": {**layout.get("yaxis", {}), "title": {"text": "% ventas nuevos coches"}},
        "legend": {"orientation": "h", "y": -0.15},
        "xaxis": {**layout.get("xaxis", {}), "range": [2015, 2030]},
    })
    fig.add_vline(x=2024, line_dash="dash", line_color="#6b7280",
                  annotation_text="Real / Proyección", annotation_font_size=9)
    fig.update_layout(layout)
    return fig


# ── Tab 4 helpers ──────────────────────────────────────────────────────────────

_MINERALS_DATA = [
    # (mineral, top3_mining_pct, china_processing_pct)
    ("Litio",       78, 68),
    ("Cobalto",     72, 80),
    ("Tierras raras",93, 85),
    ("Cobre",       41, 40),
    ("Níquel",      55, 35),
    ("Galio",       95, 98),
    ("Germanio",    75, 94),
    ("Grafito",     55, 90),
]


def _fig_critical_minerals() -> go.Figure:
    minerals = [m[0] for m in _MINERALS_DATA]
    top3     = [m[1] for m in _MINERALS_DATA]
    china    = [m[2] for m in _MINERALS_DATA]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Top-3 países producción minera (%)",
        x=minerals, y=top3, marker_color="#3b82f6",
    ))
    fig.add_trace(go.Bar(
        name="China procesamiento/refinado (%)",
        x=minerals, y=china, marker_color="#ef4444",
    ))

    layout = get_base_layout("Concentración de Suministro de Minerales Críticos (%)", height=360)
    layout.update({
        "barmode": "group",
        "legend": {"orientation": "h", "y": -0.12},
        "yaxis": {**layout.get("yaxis", {}), "title": {"text": "% concentración"}},
    })
    fig.update_layout(layout)
    return fig


def _fig_minerals_prices() -> go.Figure:
    df_cu  = get_series(ID_COPPER,  days=365 * 2)
    df_lit = get_series(ID_LIT_ETF, days=365 * 2)
    df_ni  = get_series(ID_NICKEL,  days=365 * 2)
    df_ur  = get_series(ID_URANIUM, days=365 * 2)

    fig = go.Figure()
    plots = [
        (df_cu,  "Cobre (HG=F)",    "#f97316", "y"),
        (df_lit, "Litio ETF (LIT)", "#3b82f6", "y2"),
        (df_ni,  "Níquel",          "#10b981", "y"),
        (df_ur,  "Uranio (UX=F)",   "#8b5cf6", "y2"),
    ]
    for df, name, color, yaxis in plots:
        if not df.empty:
            fig.add_trace(go.Scatter(
                x=df["timestamp"], y=df["value"],
                name=name, line={"color": color, "width": 2},
                yaxis=yaxis,
            ))

    layout = get_base_layout("Precios de Minerales Críticos (2 años)", height=340)
    layout.update({
        "yaxis":  {**layout.get("yaxis", {}), "title": {"text": "USD (Cobre, Níquel)"}},
        "yaxis2": {
            "title": {"text": "USD (Litio ETF, Uranio)",
                      "font": {"color": "#9ca3af", "size": 10}},
            "overlaying": "y", "side": "right",
            "tickfont": {"size": 10}, "showgrid": False,
        },
        "legend": {"orientation": "h", "y": -0.12},
    })
    fig.update_layout(layout)
    return fig


def _table_minerals_prices() -> html.Div:
    entries = [
        ("Cobre (HG=F)",    ID_COPPER,  "$/lb"),
        ("Litio ETF (LIT)", ID_LIT_ETF, "$/acción"),
        ("Níquel",          ID_NICKEL,  "$/lb"),
        ("Uranio (UX=F)",   ID_URANIUM, "$/lb"),
    ]
    rows = []
    for name, sid, unit in entries:
        val, ts = get_latest_value(sid)
        val_str = f"{val:.2f} {unit}" if val else "—"
        age = time_ago(ts) if ts else "—"
        rows.append(html.Tr([
            html.Td(name, style={"fontSize": "0.70rem"}),
            html.Td(val_str, style={"fontSize": "0.70rem", "color": COLORS["accent"], "fontWeight": "700"}),
            html.Td(age, style={"fontSize": "0.62rem", "color": COLORS["text_muted"]}),
        ]))
    return html.Div([
        html.Div("Cotizaciones actuales", style={
            "fontSize": "0.68rem", "fontWeight": "600",
            "color": COLORS["text_label"], "marginBottom": "6px",
        }),
        html.Table([
            html.Thead(html.Tr([html.Th("Mineral"), html.Th("Precio"), html.Th("Actualiz.")])),
            html.Tbody(rows),
        ], className="data-table"),
    ])


def _fig_supply_risk_map() -> go.Figure:
    import plotly.express as px
    supply_index = {
        "CHL": 90, "COD": 95, "CHN": 92, "AUS": 75, "PER": 70,
        "ZMB": 65, "RUS": 72, "IDN": 68, "PHL": 60, "BRA": 55,
        "USA": 40, "CAN": 38, "KAZ": 62, "GUY": 45, "ARG": 70,
        "ZAF": 58, "CUB": 50, "PAP": 42,
    }
    names_map = {
        "CHL": "Chile (Litio, Cobre)", "COD": "R.D. Congo (Cobalto)",
        "CHN": "China (Tierras raras, Galio, Grafito)", "AUS": "Australia (Litio, Cobre)",
        "PER": "Perú (Cobre, Zinc)", "ZMB": "Zambia (Cobalto, Cobre)",
        "RUS": "Rusia (Níquel, Paladio)", "IDN": "Indonesia (Níquel)",
        "PHL": "Filipinas (Níquel)", "BRA": "Brasil (Niobio, Tierras raras)",
        "USA": "EE.UU. (Cobre, Molibdeno)", "CAN": "Canadá (Níquel, Cobalto)",
    }

    df_map = pd.DataFrame([
        {"iso3": iso, "value": val,
         "description": names_map.get(iso, iso)}
        for iso, val in supply_index.items()
    ])

    fig = px.choropleth(
        df_map, locations="iso3",
        color="value",
        color_continuous_scale=[[0, "#1f2937"], [0.4, "#f59e0b"], [1.0, "#ef4444"]],
        range_color=[30, 100],
        labels={"value": "Índice concentración"},
        hover_name="description",
        hover_data={"value": ":d", "iso3": False},
    )
    fig.update_layout(
        height=360,
        paper_bgcolor="#0a0e1a",
        geo={"bgcolor": "#0a0e1a", "showframe": False,
             "showcoastlines": True, "coastlinecolor": "#374151",
             "landcolor": "#1f2937"},
        margin={"l": 0, "r": 0, "t": 20, "b": 10},
        coloraxis_colorbar={
            "thickness": 12, "len": 0.6, "title": {"text": "Concentración"},
            "tickfont": {"color": "#9ca3af", "size": 10},
        },
    )
    return fig


def _fig_china_minerals() -> go.Figure:
    minerals = [m[0] for m in _MINERALS_DATA]
    china    = [m[2] for m in _MINERALS_DATA]
    colors   = ["#ef4444" if v >= 80 else "#f97316" if v >= 60 else "#f59e0b" for v in china]

    fig = go.Figure(go.Bar(
        x=china, y=minerals, orientation="h",
        marker_color=colors, showlegend=False,
        hovertemplate="%{y}: %{x}%<extra></extra>",
    ))
    fig.add_vline(x=80, line_dash="dash", line_color="#ef4444",
                  annotation_text="Umbral dominancia 80%",
                  annotation_position="top", annotation_font_size=9,
                  annotation_font_color="#ef4444")

    layout = get_base_layout("Cuota China en Procesamiento/Refinado (%)", height=360)
    layout.update({
        "xaxis": {**layout.get("xaxis", {}), "title": {"text": "%"}, "range": [0, 105]},
        "margin": {"l": 90, "r": 20, "t": 30, "b": 30},
    })
    fig.update_layout(layout)
    return fig


def _build_china_timeline() -> html.Div:
    events = [
        ("2010", "Cuotas exportación tierras raras → dispara precios mundiales"),
        ("2019", "Restricciones cobalto procesado"),
        ("2023-07", "Controles exportación Galio y Germanio"),
        ("2023-12", "Controles exportación Grafito"),
        ("2024-02", "Restricciones tecnología procesado litio"),
        ("2024-12", "Prohibición exportación Galio/Ge/Antimonio a EE.UU."),
    ]
    items = []
    for date, desc in events:
        items.append(html.Div([
            html.Span(date, style={
                "fontSize": "0.65rem", "fontWeight": "700",
                "color": "#ef4444", "minWidth": "60px", "flexShrink": "0",
            }),
            html.Span(desc, style={
                "fontSize": "0.68rem", "color": COLORS["text_muted"], "lineHeight": "1.4",
            }),
        ], style={
            "display": "flex", "gap": "8px", "alignItems": "flex-start",
            "padding": "6px 0", "borderBottom": f"1px solid {COLORS['border']}",
        }))
    return html.Div([
        html.Div("Cronología: restricciones de exportación", style={
            "fontSize": "0.72rem", "fontWeight": "600", "color": COLORS["text"],
            "marginBottom": "8px",
        }),
        *items,
    ])


# ── Tab 5 helpers ──────────────────────────────────────────────────────────────

def _fig_fao_index() -> go.Figure:
    data = load_json_data("fao_food_index.json")
    if not data or not data.get("monthly_data"):
        return _empty_fig("No se pudo cargar data/fao_food_index.json")

    monthly = data["monthly_data"]
    dates = sorted(monthly.keys())
    vals  = [monthly[d] for d in dates]
    key_events = data.get("key_events", {})

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates, y=vals, name="FAO FFPI",
        mode="lines+markers", marker_size=4,
        line={"color": "#f97316", "width": 2},
        fill="tozeroy", fillcolor="rgba(249,115,22,0.07)",
    ))

    # Líneas de referencia
    ref_lines = [
        (236.0, "#ef4444", "Pico 2011"),
        (159.3, "#f59e0b", "Pico 2022 (Ucrania)"),
    ]
    for y_val, color, label in ref_lines:
        fig.add_hline(y=y_val, line_dash="dash", line_color=color,
                      line_width=1, opacity=0.7,
                      annotation_text=label, annotation_position="right",
                      annotation_font_size=9, annotation_font_color=color)

    # Anotaciones de eventos clave
    for date_str, label in key_events.items():
        if date_str in monthly:
            fig.add_annotation(
                x=date_str, y=monthly[date_str],
                text=label[:30], showarrow=True, arrowhead=2,
                font={"size": 8, "color": "#e5e7eb"},
                arrowcolor="#6b7280", ax=0, ay=-30,
            )

    src = data.get("source", "FAO")
    upd = data.get("last_updated", "?")
    layout = get_base_layout(f"Índice FAO de Precios de Alimentos (FFPI) — {src}", height=380)
    layout.update({
        "xaxis": {**layout.get("xaxis", {}), "rangeselector": get_time_range_buttons()},
        "yaxis": {**layout.get("yaxis", {}), "title": {"text": "Índice (2014-16=100)"}},
        "annotations": [a for a in layout.get("annotations", [])],
    })
    fig.update_layout(layout)
    return fig


def _build_grain_stocks_table() -> html.Div:
    data = load_json_data("grain_stocks.json")
    if not data or not data.get("grains"):
        return create_empty_state("No se pudo cargar data/grain_stocks.json")

    upd = data.get("last_updated", "?")
    src = data.get("source", "USDA WASDE")

    rows = []
    for g in data["grains"]:
        name      = g["name"]
        stocks    = g["stocks_mt"]
        prev      = g["stocks_prev_year_mt"]
        consump   = g["consumption_mt"]
        threshold = g["alert_threshold_months"]
        months_cov = stocks / (consump / 12) if consump > 0 else 0
        chg_pct   = (stocks - prev) / prev * 100 if prev > 0 else 0

        alert = months_cov < threshold
        mc_color = "#ef4444" if alert else "#10b981"
        mc_label = f"⚠️ {months_cov:.1f}m" if alert else f"✓ {months_cov:.1f}m"

        chg_color = "#10b981" if chg_pct >= 0 else "#ef4444"
        chg_str   = f"{'↑' if chg_pct >= 0 else '↓'} {abs(chg_pct):.1f}%"

        rows.append(html.Tr([
            html.Td(name, style={"fontWeight": "600", "fontSize": "0.78rem"}),
            html.Td(f"{stocks:,.0f} Mt", style={"fontSize": "0.75rem"}),
            html.Td(chg_str, style={"fontSize": "0.75rem", "color": chg_color}),
            html.Td(f"{consump:,.0f} Mt", style={"fontSize": "0.75rem"}),
            html.Td(mc_label, style={"fontSize": "0.75rem", "color": mc_color, "fontWeight": "700"}),
        ]))

    return html.Div([
        html.Div(f"Fuente: {src} — Actualizado: {upd}", style={
            "fontSize": "0.65rem", "color": COLORS["text_muted"], "marginBottom": "8px",
        }),
        html.Table([
            html.Thead(html.Tr([
                html.Th("Grano"),
                html.Th("Inventario"),
                html.Th("vs año ant."),
                html.Th("Consumo anual"),
                html.Th("Cobertura"),
            ])),
            html.Tbody(rows),
        ], className="data-table", style={"width": "100%"}),
        html.Div(
            "⚠️ = por debajo del umbral histórico de alerta. La cobertura mide cuántos meses de consumo "
            "mundial están cubiertos por los inventarios actuales.",
            style={"fontSize": "0.68rem", "color": COLORS["text_muted"], "marginTop": "8px"},
        ),
    ])


def _fig_food_crisis_map() -> go.Figure:
    import plotly.express as px
    # Escala IPC: 1=mínimo, 5=catástrofe
    food_crisis = {
        "ETH": 4, "YEM": 5, "SOM": 5, "SDN": 5, "COD": 4,
        "SYR": 4, "AFG": 5, "HTI": 4, "NGA": 3, "CAF": 4,
        "NER": 3, "MLI": 3, "BFA": 4, "ZWE": 3, "MDG": 3,
        "MOZ": 3, "KEN": 3, "TZA": 2, "UGA": 2, "GIN": 2,
        "PRK": 3, "MMR": 3, "PAK": 3, "BGD": 2, "GTM": 2,
        "HND": 2, "VEN": 3, "CMR": 3, "TCD": 4, "SSD": 5,
    }
    df_map = pd.DataFrame([
        {"iso3": iso, "ipc_phase": val}
        for iso, val in food_crisis.items()
    ])

    color_scale = [
        [0.0, "#1f2937"],
        [0.2, "#10b981"],
        [0.4, "#f59e0b"],
        [0.6, "#f97316"],
        [0.8, "#ef4444"],
        [1.0, "#7c2d12"],
    ]
    fig = px.choropleth(
        df_map, locations="iso3",
        color="ipc_phase",
        color_continuous_scale=color_scale,
        range_color=[1, 5],
        labels={"ipc_phase": "Fase IPC"},
        hover_name="iso3",
        hover_data={"ipc_phase": True},
    )
    fig.update_layout(
        height=360,
        paper_bgcolor="#0a0e1a",
        geo={"bgcolor": "#0a0e1a", "showframe": False,
             "showcoastlines": True, "coastlinecolor": "#374151",
             "landcolor": "#1f2937"},
        margin={"l": 0, "r": 0, "t": 10, "b": 10},
        coloraxis_colorbar={
            "thickness": 12, "len": 0.6,
            "tickvals": [1, 2, 3, 4, 5],
            "ticktext": ["1-Mínimo", "2-Estrés", "3-Crisis", "4-Emergencia", "5-Catástrofe"],
            "title": {"text": "Fase IPC", "font": {"color": "#9ca3af"}},
            "tickfont": {"color": "#9ca3af", "size": 9},
        },
    )
    return fig


def _build_food_insecurity_metric() -> html.Div:
    data = load_json_data("conflict_food_impact.json")
    if not data:
        return create_empty_state("Sin datos")
    total  = data.get("people_in_acute_food_insecurity", 0)
    source = data.get("people_source", "WFP/FAO")
    ctries = data.get("countries_crisis_or_worse", 0)
    return html.Div([
        html.Div("Personas en inseguridad alimentaria aguda", style={
            "fontSize": "0.65rem", "color": COLORS["text_muted"],
            "fontWeight": "600", "marginBottom": "6px",
        }),
        html.Div(f"{total / 1_000_000:.0f}M", style={
            "fontSize": "2.2rem", "fontWeight": "800",
            "color": "#ef4444", "lineHeight": "1",
        }),
        html.Div("personas afectadas", style={
            "fontSize": "0.68rem", "color": COLORS["text_muted"],
        }),
        html.Div(f"{ctries} países en Fase IPC ≥3", style={
            "fontSize": "0.72rem", "color": "#f97316",
            "fontWeight": "600", "marginTop": "8px",
        }),
        html.Div(f"Fuente: {source}", style={
            "fontSize": "0.60rem", "color": COLORS["text_label"], "marginTop": "4px",
        }),
    ], style={
        "background": "#200808", "border": "1px solid #ef444430",
        "borderRadius": "6px", "padding": "14px", "textAlign": "center",
    })


def _build_conflict_food_panel() -> html.Div:
    data = load_json_data("conflict_food_impact.json")
    if not data:
        return create_empty_state("No se pudo cargar data/conflict_food_impact.json")

    ukr  = data.get("ukraine_russia", {})
    red  = data.get("red_sea_houthi", {})
    iran = data.get("iran_conflict", {})

    def _bloc(title: str, color: str, items: list, note: str = "") -> html.Div:
        return html.Div([
            html.Div(title, style={
                "fontSize": "0.78rem", "fontWeight": "700", "color": color,
                "marginBottom": "6px",
            }),
            *[html.Div([
                html.Span("▸ ", style={"color": color}),
                html.Span(item, style={"fontSize": "0.72rem", "color": COLORS["text"]}),
            ], style={"marginBottom": "3px"}) for item in items],
            html.Div(note, style={"fontSize": "0.68rem", "color": COLORS["text_muted"],
                                   "marginTop": "6px"}) if note else html.Div(),
        ], style={
            "background": "#0d1320", "border": f"1px solid {color}30",
            "borderLeft": f"3px solid {color}",
            "borderRadius": "0 6px 6px 0", "padding": "12px 14px",
        })

    return html.Div([
        dbc.Row([
            dbc.Col(_bloc(
                "🌾 Ucrania y Rusia — Granero de Europa",
                "#f97316",
                [
                    f"Trigo exportado mundial: {ukr.get('wheat_pct_world', '—')}%",
                    f"Maíz exportado mundial: {ukr.get('corn_pct_world', '—')}%",
                    f"Aceite de girasol: {ukr.get('sunflower_oil_pct_world', '—')}%",
                    f"Fertilizantes: {ukr.get('fertilizer_pct_world', '—')}% producción global",
                ],
                ukr.get("notes", ""),
            ), width=4),
            dbc.Col(_bloc(
                "🚢 Mar Rojo — Ataques Houthi",
                "#ef4444",
                [
                    f"Comercio alimentario vía Suez: {red.get('pct_food_trade_suez', '—')}%",
                    "Desvío por Cabo de Buena Esperanza: +10-14 días",
                    "Aumento coste transporte: +150-300%",
                ] + [f"Afectado: {r}" for r in red.get("affected_routes", [])],
                red.get("notes", ""),
            ), width=4),
            dbc.Col(_bloc(
                "⚓ Conflicto Irán — Estrecho de Ormuz",
                "#8b5cf6",
                [
                    "Ormuz: crítico para fertilizantes del Golfo Pérsico",
                    "Arabia Saudí y EAU: exportadores netos de urea y fosfatos",
                    "Impacto indirecto en precios agrícolas globales",
                ],
                iran.get("notes", ""),
            ), width=4),
        ], className="g-3"),
    ])


# ══════════════════════════════════════════════════════════════════════════════
# REGISTRO DE CALLBACKS
# ══════════════════════════════════════════════════════════════════════════════

def register_callbacks_module_7(app) -> None:

    # ── 1. Renderizar contenido del tab seleccionado ──────────────────────────

    @app.callback(
        Output("m7-tab-content", "children"),
        Input("m7-main-tabs", "value"),
        Input("m7-refresh-interval", "n_intervals"),
    )
    def render_tab_content(tab: str, _n: int) -> html.Div:
        try:
            if tab == "tab-oil":
                return _build_tab1()
            if tab == "tab-gas":
                return _build_tab2()
            if tab == "tab-transition":
                return _build_tab3()
            if tab == "tab-minerals":
                return _build_tab4()
            if tab == "tab-food":
                return _build_tab5()
        except Exception as exc:
            logger.exception("render_tab_content(%s): %s", tab, exc)
        return html.Div("Error cargando contenido del módulo.", style={"padding": "24px", "color": "#ef4444"})

    # ── 2. Gráfico de precios de petróleo ─────────────────────────────────────

    @app.callback(
        Output("m7-oil-price-chart", "figure"),
        Output("m7-oil-recent-table", "children"),
        Input("m7-main-tabs", "value"),
        Input("m7-refresh-interval", "n_intervals"),
    )
    def update_oil_chart(tab: str, _n: int):
        if tab != "tab-oil":
            return no_update, no_update
        try:
            return _fig_oil_prices(), _table_oil_recent()
        except Exception as exc:
            logger.exception("update_oil_chart: %s", exc)
            return _empty_fig("Error cargando precios"), create_empty_state("Error")

    # ── 3. Rutas estratégicas ─────────────────────────────────────────────────

    @app.callback(
        Output("m7-routes-table", "children"),
        Output("m7-routes-last-updated", "children"),
        Input("m7-main-tabs", "value"),
        Input("m7-refresh-interval", "n_intervals"),
        Input("m7-routes-store", "data"),
    )
    def update_routes_table(tab: str, _n: int, _store):
        if tab != "tab-oil":
            return no_update, no_update
        try:
            data = load_json_data("route_status.json")
            upd  = data.get("last_updated", "—") if data else "—"
            return _build_routes_table(data), f"Última actualización manual: {upd}"
        except Exception as exc:
            logger.exception("update_routes_table: %s", exc)
            return create_empty_state("Error cargando rutas"), "—"

    # ── 4. Abrir/cerrar modal de edición de rutas ─────────────────────────────

    @app.callback(
        Output("m7-routes-modal", "is_open"),
        Output("m7-routes-modal-body", "children"),
        Input("m7-routes-edit-btn", "n_clicks"),
        Input("m7-routes-cancel-btn", "n_clicks"),
        Input("m7-routes-save-btn", "n_clicks"),
        State("m7-routes-modal", "is_open"),
        prevent_initial_call=True,
    )
    def toggle_routes_modal(open_clicks, cancel_clicks, save_clicks, is_open):
        from dash import callback_context as ctx
        triggered = ctx.triggered_id if ctx.triggered_id else ""

        if triggered == "m7-routes-edit-btn":
            data = load_json_data("route_status.json")
            if not data:
                return True, html.Div("Error: no se pudo cargar route_status.json",
                                       style={"color": "#ef4444"})
            form_rows = []
            for i, route in enumerate(data.get("routes", [])):
                form_rows.append(dbc.Row([
                    dbc.Col(html.Strong(route["name"], style={"fontSize": "0.82rem"}), width=4),
                    dbc.Col(dbc.Select(
                        id={"type": "m7-route-status", "index": i},
                        options=[
                            {"label": "🟢 Normal",   "value": "normal"},
                            {"label": "🟡 Reducido",  "value": "reduced"},
                            {"label": "🔴 Bloqueado", "value": "blocked"},
                        ],
                        value=route["status"],
                        style={"fontSize": "0.78rem"},
                    ), width=3),
                    dbc.Col(dbc.Input(
                        id={"type": "m7-route-notes", "index": i},
                        value=route.get("notes", ""),
                        placeholder="Notas...",
                        style={"fontSize": "0.75rem"},
                        size="sm",
                    ), width=5),
                ], className="g-2 mb-2"))
            form_rows.append(
                html.Div(
                    "Los cambios se guardarán en data/route_status.json",
                    style={"fontSize": "0.68rem", "color": COLORS["text_muted"],
                           "marginTop": "8px"},
                )
            )
            return True, html.Div(form_rows)

        if triggered == "m7-routes-cancel-btn":
            return False, no_update

        # Save — manejado en callback separado
        return False, no_update

    # ── 5. Guardar rutas desde modal ──────────────────────────────────────────

    @app.callback(
        Output("m7-routes-store", "data"),
        Input("m7-routes-save-btn", "n_clicks"),
        State({"type": "m7-route-status", "index": ALL}, "value"),
        State({"type": "m7-route-notes",  "index": ALL}, "value"),
        prevent_initial_call=True,
    )
    def save_routes(n_clicks, statuses, notes):
        if not n_clicks:
            return no_update
        try:
            data = load_json_data("route_status.json")
            if data is None:
                return no_update
            routes = data.get("routes", [])
            for i, route in enumerate(routes):
                if i < len(statuses) and statuses[i]:
                    route["status"] = statuses[i]
                if i < len(notes) and notes[i] is not None:
                    route["notes"] = notes[i]
            data["last_updated"] = datetime.utcnow().strftime("%Y-%m-%d")
            filepath = DATA_DIR / "route_status.json"
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return {"saved": True, "ts": datetime.utcnow().isoformat()}
        except Exception as exc:
            logger.exception("save_routes: %s", exc)
            return no_update

    # ── 6. Gráficos producción petróleo ───────────────────────────────────────

    @app.callback(
        Output("m7-oil-production-chart", "figure"),
        Output("m7-oil-production-table", "children"),
        Input("m7-main-tabs", "value"),
    )
    def update_oil_production(tab: str):
        if tab != "tab-oil":
            return no_update, no_update
        try:
            return _fig_oil_production(), _table_oil_production()
        except Exception as exc:
            logger.exception("update_oil_production: %s", exc)
            return _empty_fig("Error"), create_empty_state("Error")

    # ── 7. Correlación petróleo–inflación ─────────────────────────────────────

    @app.callback(
        Output("m7-oil-inflation-scatter", "figure"),
        Output("m7-oil-inflation-text", "children"),
        Input("m7-main-tabs", "value"),
    )
    def update_oil_inflation(tab: str):
        if tab != "tab-oil":
            return no_update, no_update
        try:
            return _fig_oil_inflation_scatter()
        except Exception as exc:
            logger.exception("update_oil_inflation: %s", exc)
            return _empty_fig("Error"), "—"

    # ── 8. Dependencia energética y PIB ──────────────────────────────────────

    @app.callback(
        Output("m7-energy-dependence-chart", "figure"),
        Output("m7-oil-gdp-chart", "figure"),
        Input("m7-main-tabs", "value"),
    )
    def update_dependence_gdp(tab: str):
        if tab != "tab-oil":
            return no_update, no_update
        try:
            return _fig_energy_dependence(), _fig_oil_gdp()
        except Exception as exc:
            logger.exception("update_dependence_gdp: %s", exc)
            return _empty_fig("Error"), _empty_fig("Error")

    # ── 9. Tab 2: Gas precios, almacenamiento, mapa Europa, mix ───────────────

    @app.callback(
        Output("m7-gas-prices-chart",  "figure"),
        Output("m7-gas-storage-gauge", "figure"),
        Output("m7-gas-storage-detail","children"),
        Output("m7-europe-dep-map",    "figure"),
        Output("m7-europe-dep-table",  "children"),
        Output("m7-energy-mix-chart",  "figure"),
        Input("m7-main-tabs", "value"),
        Input("m7-refresh-interval", "n_intervals"),
    )
    def update_tab2(tab: str, _n: int):
        if tab != "tab-gas":
            return (no_update,) * 6
        try:
            storage_data = load_json_data("energy_status.json")
            return (
                _fig_gas_prices(),
                _fig_gas_storage_gauge(storage_data),
                _build_gas_storage_detail(storage_data),
                _fig_europe_dep_map(),
                _build_europe_dep_table(),
                _fig_energy_mix(),
            )
        except Exception as exc:
            logger.exception("update_tab2: %s", exc)
            empty = _empty_fig("Error")
            return empty, empty, create_empty_state("Error"), empty, create_empty_state("Error"), empty

    # ── 10. Tab 3: Transición energética ─────────────────────────────────────

    @app.callback(
        Output("m7-clean-tech-costs-chart",   "figure"),
        Output("m7-renewables-capacity-chart", "figure"),
        Output("m7-energy-investment-chart",   "figure"),
        Output("m7-investment-leaders-table",  "children"),
        Output("m7-ev-adoption-chart",         "figure"),
        Input("m7-main-tabs", "value"),
    )
    def update_tab3(tab: str):
        if tab != "tab-transition":
            return (no_update,) * 5
        try:
            return (
                _fig_clean_tech_costs(),
                _fig_renewables_capacity(),
                _fig_energy_investment(),
                _table_investment_leaders(),
                _fig_ev_adoption(),
            )
        except Exception as exc:
            logger.exception("update_tab3: %s", exc)
            empty = _empty_fig("Error")
            return empty, empty, empty, create_empty_state("Error"), empty

    # ── 11. Tab 4: Minerales críticos ─────────────────────────────────────────

    @app.callback(
        Output("m7-critical-minerals-chart", "figure"),
        Output("m7-minerals-prices-chart",   "figure"),
        Output("m7-minerals-prices-table",   "children"),
        Output("m7-supply-risk-map",         "figure"),
        Output("m7-china-minerals-chart",    "figure"),
        Output("m7-china-timeline",          "children"),
        Input("m7-main-tabs", "value"),
        Input("m7-refresh-interval", "n_intervals"),
    )
    def update_tab4(tab: str, _n: int):
        if tab != "tab-minerals":
            return (no_update,) * 6
        try:
            return (
                _fig_critical_minerals(),
                _fig_minerals_prices(),
                _table_minerals_prices(),
                _fig_supply_risk_map(),
                _fig_china_minerals(),
                _build_china_timeline(),
            )
        except Exception as exc:
            logger.exception("update_tab4: %s", exc)
            empty = _empty_fig("Error")
            return empty, empty, create_empty_state("Error"), empty, empty, create_empty_state("Error")

    # ── 12. Tab 5: Seguridad alimentaria ──────────────────────────────────────

    @app.callback(
        Output("m7-fao-index-chart",       "figure"),
        Output("m7-grain-stocks-table",    "children"),
        Output("m7-food-crisis-map",       "figure"),
        Output("m7-food-insecurity-metric","children"),
        Output("m7-conflict-food-panel",   "children"),
        Input("m7-main-tabs", "value"),
    )
    def update_tab5(tab: str):
        if tab != "tab-food":
            return (no_update,) * 5
        try:
            return (
                _fig_fao_index(),
                _build_grain_stocks_table(),
                _fig_food_crisis_map(),
                _build_food_insecurity_metric(),
                _build_conflict_food_panel(),
            )
        except Exception as exc:
            logger.exception("update_tab5: %s", exc)
            empty = _empty_fig("Error")
            return empty, create_empty_state("Error"), empty, create_empty_state("Error"), create_empty_state("Error")
