"""
Modulo 14 — Seguimiento Historico y Comparativas Temporales.

Tabs:
  1. Selector de fecha historica / Viaje en el tiempo
  2. Comparador temporal (indicador + dos fechas)
  3. Linea de tiempo global (eventos + halvings BTC)
  4. Comparativa con crisis historicas (2000/2008/2020)
  5. Registro de escenarios / predicciones
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import ALL, Input, Output, State, dcc, html, no_update, ctx

from config import COLORS, DB_PATH
from modules.data_helpers import (
    compare_snapshots,
    get_all_indicator_ids,
    get_geopolitical_events,
    get_series_between,
    get_time_context,
    get_value_at_date,
    set_time_context,
    format_value,
)

logger = logging.getLogger(__name__)

# ── Constantes ─────────────────────────────────────────────────────────────────

DATA_DIR = Path(__file__).parent.parent / "data"
CRISES_FILE = DATA_DIR / "historical_crises.json"

# Mapeo de indicator_key (crisis JSON) → series_id en la BD
CRISIS_INDICATOR_DB_MAP = {
    "sp500": "yf_sp500_close",
    "vix": "yf_vix_close",
    "fed_funds": "fred_fed_funds_us",
    "unemployment": "fred_unemployment_us",
    "spread_10y2y": "fred_spread_10y2y_us",
    "brent": "yf_bz_close",
}

# Grupos de indicadores para el dropdown del comparador
INDICATOR_GROUPS = {
    "Mercados": [
        ("S&P 500", "yf_sp500_close"),
        ("IBEX 35", "yf_ibex35_close"),
        ("VIX", "yf_vix_close"),
        ("Oro (GC=F)", "yf_gc_close"),
        ("Petroleo Brent", "yf_bz_close"),
        ("Bitcoin (USD)", "cg_btc_price_usd"),
        ("DXY (Dolar Index)", "yf_dxy_close"),
        ("EUR/USD", "yf_eurusd_close"),
    ],
    "Macro EE.UU.": [
        ("Tipos Fed (Fed Funds)", "fred_fed_funds_us"),
        ("Inflacion EE.UU. YoY", "fred_cpi_yoy_us"),
        ("Desempleo EE.UU.", "fred_unemployment_us"),
        ("Spread 10y-2y", "fred_spread_10y2y_us"),
        ("STLFSI (Estres Fin.)", "fred_stlfsi_us"),
        ("Regla de Sahm", "fred_sahm_rule_us"),
    ],
    "Europa": [
        ("Tipo BCE deposito", "ecb_deposit_rate_ea"),
        ("HICP Eurozona", "estat_hicp_cp00_ea20"),
        ("Desempleo Eurozona", "estat_unemp_total_ea20"),
        ("Prima riesgo Espana", "ecb_spread_es_de"),
        ("Prima riesgo Italia", "ecb_spread_it_de"),
    ],
    "Geopolitica": [
        ("GPR Global", "fred_gpr_global"),
        ("GDELT Tono Global", "gdelt_global_tone"),
        ("Fear & Greed Crypto", "cg_fear_greed_value"),
    ],
}

CATEGORY_COLORS = {
    "macro": "#3b82f6",
    "markets": "#10b981",
    "geopolitics": "#ef4444",
    "energy": "#f59e0b",
    "monetary": "#8b5cf6",
    "crypto_cycle": "#f97316",
    "auto": "#6b7280",
    "manual": "#ec4899",
}

# Indicadores para el comparador de dos fechas libres.
# Cada entrada: (label, series_id, lower_is_better)
#   lower_is_better=True  → bajar el valor es señal positiva (VIX, desempleo, inflación...)
#   lower_is_better=False → subir el valor es señal positiva (índices, oro, BTC...)
#   lower_is_better=None  → neutral (tipo fed, EUR/USD, DXY)
_CMP_DATE_INDICATORS = [
    ("S&P 500",                   "yf_sp500_close",          False),
    ("IBEX 35",                   "yf_ibex35_close",         False),
    ("VIX (Volatilidad)",         "yf_vix_close",            True),
    ("Tipos Fed (%)",             "fred_fed_funds_us",       None),
    ("Tipo BCE depósito (%)",     "ecb_deposit_rate_ea",     None),
    ("Inflación EE.UU. YoY (%)", "fred_cpi_yoy_us",         True),
    ("HICP Eurozona (%)",         "estat_hicp_cp00_ea20",    True),
    ("Desempleo EE.UU. (%)",      "fred_unemployment_us",    True),
    ("Spread 10y-2y EE.UU. (%)", "fred_spread_10y2y_us",    False),
    ("Prima riesgo España (pb)",  "ecb_spread_es_de",        True),
    ("Oro (USD/oz)",              "yf_gc_close",             False),
    ("Brent (USD/barril)",        "yf_bz_close",             False),
    ("Bitcoin (USD)",             "cg_btc_price_usd",        False),
    ("Fear & Greed Crypto",       "cg_fear_greed_value",     False),
    ("DXY (Dólar Index)",         "yf_dxy_close",            None),
    ("EUR/USD",                   "yf_eurusd_close",         None),
    ("GPR Global",                "fred_gpr_global",         True),
    ("STLFSI (Estrés Fin.)",      "fred_stlfsi_us",          True),
    ("Regla de Sahm",             "fred_sahm_rule_us",       True),
]


# ── Helpers ────────────────────────────────────────────────────────────────────

def _load_crises() -> list:
    try:
        return json.loads(CRISES_FILE.read_text(encoding="utf-8"))["crises"]
    except Exception:
        return []


def _get_snapshots(limit: int = 50) -> list:
    """Lee snapshots de SnapshotHistory directamente (sin importar el scheduler)."""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, snapshot_date, snapshot_data, created_at FROM SnapshotHistory ORDER BY snapshot_date DESC LIMIT ?",
            (limit,),
        ).fetchall()
        conn.close()
        result = []
        for row in rows:
            try:
                data = json.loads(row["snapshot_date"] and row["snapshot_data"] or "{}")
            except Exception:
                data = {}
            result.append({
                "id": row["id"],
                "snapshot_date": row["snapshot_date"],
                "label": data.get("label", ""),
                "trigger": data.get("trigger", "scheduled"),
                "created_at": row["created_at"],
            })
        return result
    except Exception as exc:
        logger.debug("_get_snapshots: %s", exc)
        return []


def _save_scenario(title: str, description: str, probability: float, target_date: Optional[str], conditions: str):
    """Guarda un escenario en la tabla scenarios de SQLAlchemy."""
    try:
        from database.database import Scenario, SessionLocal
        tgt = None
        if target_date:
            try:
                tgt = datetime.strptime(target_date, "%Y-%m-%d")
            except Exception:
                pass
        prob = max(0.0, min(1.0, probability / 100.0)) if probability else None
        with SessionLocal() as db:
            sc = Scenario(
                title=title,
                description=description,
                probability=prob,
                conditions=conditions,
                target_date=tgt,
                outcome="pending",
            )
            db.add(sc)
            db.commit()
        return True
    except Exception as exc:
        logger.error("_save_scenario: %s", exc)
        return False


def _get_scenarios() -> list:
    """Lee todos los escenarios de la tabla scenarios."""
    try:
        from database.database import Scenario, SessionLocal
        with SessionLocal() as db:
            rows = db.query(Scenario).order_by(Scenario.created_at.desc()).all()
        return [
            {
                "id": r.id,
                "title": r.title,
                "description": r.description,
                "probability": r.probability,
                "conditions": r.conditions,
                "target_date": r.target_date,
                "outcome": r.outcome or "pending",
                "outcome_notes": r.outcome_notes,
                "created_at": r.created_at,
            }
            for r in rows
        ]
    except Exception as exc:
        logger.debug("_get_scenarios: %s", exc)
        return []


def _update_scenario_outcome(scenario_id: int, outcome: str, notes: str):
    try:
        from database.database import Scenario, SessionLocal
        with SessionLocal() as db:
            sc = db.query(Scenario).filter(Scenario.id == scenario_id).first()
            if sc:
                sc.outcome = outcome
                sc.outcome_notes = notes
                sc.reviewed_at = datetime.utcnow()
                db.commit()
        return True
    except Exception as exc:
        logger.error("_update_scenario_outcome: %s", exc)
        return False


def _get_timeline_events() -> list:
    """Devuelve eventos geopolíticos + halvings BTC para la línea de tiempo."""
    events = []
    # Eventos geopolíticos desde BD (últimos 10 años)
    geo = get_geopolitical_events(months=120)
    for e in geo:
        events.append({
            "date": e["date"],
            "title": e["title"],
            "category": e.get("category", "geopolitics"),
            "severity": e.get("severity", 2),
            "description": e.get("description", ""),
            "is_manual": e.get("is_manual", False),
        })
    # Halvings BTC (hardcoded)
    halvings = [
        {"date": datetime(2012, 11, 28), "title": "Bitcoin Halving #1", "category": "crypto_cycle", "severity": 3},
        {"date": datetime(2016, 7, 9),   "title": "Bitcoin Halving #2", "category": "crypto_cycle", "severity": 3},
        {"date": datetime(2020, 5, 11),  "title": "Bitcoin Halving #3", "category": "crypto_cycle", "severity": 4},
        {"date": datetime(2024, 4, 20),  "title": "Bitcoin Halving #4", "category": "crypto_cycle", "severity": 4},
    ]
    events.extend(halvings)
    return events


def _build_indicator_options():
    """Construye las opciones agrupadas para el dropdown del comparador."""
    options = []
    for group_name, indicators in INDICATOR_GROUPS.items():
        options.append({"label": f"── {group_name} ──", "value": f"__group_{group_name}", "disabled": True})
        for label, value in indicators:
            options.append({"label": label, "value": value})
    return options


def _plotly_dark_layout(title: str = "", height: int = 380) -> dict:
    return dict(
        title=dict(text=title, font=dict(size=13, color=COLORS["text"]), x=0),
        height=height,
        margin=dict(l=48, r=24, t=40, b=40),
        plot_bgcolor=COLORS["card_bg"],
        paper_bgcolor=COLORS["card_bg"],
        font=dict(color=COLORS["text"], size=11),
        xaxis=dict(gridcolor="#2a2a2a", linecolor="#3a3a3a", zeroline=False),
        yaxis=dict(gridcolor="#2a2a2a", linecolor="#3a3a3a", zeroline=False),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=10)),
        hovermode="x unified",
    )


# ── Layouts de cada tab ────────────────────────────────────────────────────────

def _build_tab1():
    """Tab 1: Viaje en el tiempo + snapshots."""
    snapshots = _get_snapshots(30)

    snap_buttons = []
    for s in snapshots[:15]:
        label_str = s.get("label") or ""
        trigger = s.get("trigger", "scheduled")
        icon = "📸" if trigger == "manual" else "🕐"
        btn_label = f"{icon} {s['snapshot_date'][:10]}"
        if label_str:
            btn_label += f" — {label_str[:25]}"
        snap_buttons.append(
            dbc.Button(
                btn_label,
                id={"type": "m14-snap-btn", "date": s["snapshot_date"][:10]},
                size="sm",
                color="secondary",
                outline=True,
                className="me-1 mb-1",
                style={"fontSize": "0.72rem"},
            )
        )

    return html.Div([
        dbc.Row([
            # Panel izquierdo: DatePicker + botones de control
            dbc.Col([
                html.Div([
                    html.Div("SELECTOR DE FECHA HISTORICA", className="metric-card-title", style={"marginBottom": "10px"}),
                    dcc.DatePickerSingle(
                        id="m14-date-picker",
                        placeholder="Selecciona una fecha...",
                        display_format="DD/MM/YYYY",
                        clearable=True,
                        style={"marginBottom": "12px", "width": "100%"},
                    ),
                    dbc.Button(
                        "Activar viaje en el tiempo",
                        id="m14-activate-btn",
                        color="warning",
                        size="sm",
                        className="mb-2 w-100",
                    ),
                    dbc.Button(
                        "Volver al presente",
                        id="m14-reset-btn",
                        color="success",
                        outline=True,
                        size="sm",
                        className="mb-3 w-100",
                    ),
                    html.Hr(style={"borderColor": "#2a2a2a"}),
                    html.Div("SNAPSHOT MANUAL", className="metric-card-title", style={"marginBottom": "6px"}),
                    dbc.Input(
                        id="m14-snap-label",
                        placeholder="Etiqueta del snapshot (opcional)...",
                        size="sm",
                        className="mb-2",
                        style={"fontSize": "0.78rem"},
                    ),
                    dbc.Button(
                        "Guardar snapshot ahora",
                        id="m14-snap-now-btn",
                        color="primary",
                        outline=True,
                        size="sm",
                        className="w-100",
                    ),
                    html.Div(id="m14-snap-feedback", style={"marginTop": "6px", "fontSize": "0.75rem"}),
                ], className="metric-card", style={"height": "100%"}),
            ], width=3),

            # Panel derecho: estado actual + acceso rápido a snapshots
            dbc.Col([
                html.Div(id="m14-time-status-panel", children=_build_time_status_panel(None)),
                html.Hr(style={"borderColor": "#2a2a2a", "margin": "16px 0"}),
                html.Div("ACCESO RAPIDO A SNAPSHOTS GUARDADOS", className="metric-card-title", style={"marginBottom": "8px"}),
                html.Div(
                    snap_buttons if snap_buttons else html.Span(
                        "No hay snapshots guardados aun. El scheduler los crea cada domingo.",
                        style={"color": COLORS["text_muted"], "fontSize": "0.78rem"}
                    ),
                    id="m14-snap-quick-access",
                ),
            ], width=9),
        ], className="g-3"),
    ])


def _build_time_status_panel(active_date: Optional[str]) -> html.Div:
    ctx_dt = get_time_context()
    if ctx_dt is None:
        badge = dbc.Badge("TIEMPO REAL", color="success", className="ms-2", style={"fontSize": "0.75rem"})
        subtitle = "Mostrando datos actuales en todos los modulos."
        style_card = {}
    else:
        date_str = ctx_dt.strftime("%d/%m/%Y %H:%M")
        badge = dbc.Badge(f"MODO HISTORICO: {date_str}", color="warning", className="ms-2",
                          style={"fontSize": "0.75rem", "backgroundColor": "#f97316"})
        subtitle = f"Todos los modulos muestran datos del {date_str}. Los valores estan filtrados por esa fecha."
        style_card = {"borderLeft": "3px solid #f97316"}

    return html.Div([
        html.Div([
            html.Span("Estado del dashboard", style={"fontWeight": "bold", "fontSize": "0.9rem"}),
            badge,
        ]),
        html.Div(subtitle, style={"color": COLORS["text_muted"], "fontSize": "0.78rem", "marginTop": "4px"}),
    ], className="metric-card", style={"marginBottom": "10px", **style_card})


def _build_tab2():
    """Tab 2: Comparador temporal — tres secciones: simple, multi-indicador, snapshots."""
    indicator_opts = _build_indicator_options()
    default_indicator = "yf_sp500_close"

    # Opciones para el multi-select (misma lista sin los headers de grupo)
    multi_opts = [o for o in indicator_opts if not o.get("disabled")]

    # Opciones de snapshots guardados
    snapshots = _get_snapshots(50)
    snap_opts = []
    for s in snapshots:
        label_str = s.get("label") or ""
        trigger = s.get("trigger", "scheduled")
        icon = "📸" if trigger == "manual" else "🕐"
        lbl = f"{icon} {s['snapshot_date'][:10]}"
        if label_str:
            lbl += f" — {label_str[:30]}"
        snap_opts.append({"label": lbl, "value": s["id"]})

    # ── Sección A: Comparador simple (un indicador, dos fechas) ──────────────
    section_simple = html.Div([
        dbc.Row([
            dbc.Col([
                html.Div("INDICADOR", className="metric-card-title", style={"marginBottom": "4px"}),
                dcc.Dropdown(
                    id="m14-cmp-indicator",
                    options=indicator_opts,
                    value=default_indicator,
                    clearable=False,
                    style={"fontSize": "0.82rem"},
                ),
            ], width=4),
            dbc.Col([
                html.Div("FECHA 1", className="metric-card-title", style={"marginBottom": "4px"}),
                dcc.DatePickerSingle(
                    id="m14-cmp-date1",
                    display_format="DD/MM/YYYY",
                    placeholder="Fecha 1...",
                    clearable=True,
                ),
            ], width=3),
            dbc.Col([
                html.Div("FECHA 2", className="metric-card-title", style={"marginBottom": "4px"}),
                dcc.DatePickerSingle(
                    id="m14-cmp-date2",
                    display_format="DD/MM/YYYY",
                    placeholder="Fecha 2...",
                    clearable=True,
                ),
            ], width=3),
            dbc.Col([
                html.Div("\u00a0", className="metric-card-title", style={"marginBottom": "4px"}),
                dbc.Button("Comparar", id="m14-cmp-btn", color="primary", className="w-100"),
            ], width=2),
        ], className="g-2 mb-3"),
        html.Div(id="m14-cmp-results"),
    ])

    # ── Sección B: Multi-indicador normalizado a base 100 ────────────────────
    section_multi = html.Div([
        dbc.Alert(
            [
                html.Strong("Base 100: "),
                "Cada indicador se normaliza a 100 en Fecha 1. Permite comparar evoluciones "
                "porcentuales de hasta 5 indicadores con escalas muy distintas.",
            ],
            color="dark",
            style={"fontSize": "0.78rem", "padding": "8px 14px", "marginBottom": "12px",
                   "border": "1px solid #374151", "backgroundColor": "rgba(59,130,246,0.06)"},
        ),
        dbc.Row([
            dbc.Col([
                html.Div("INDICADORES (máx. 5)", className="metric-card-title",
                         style={"marginBottom": "4px"}),
                dcc.Dropdown(
                    id="m14-multi-indicators",
                    options=multi_opts,
                    value=["yf_sp500_close"],
                    multi=True,
                    placeholder="Selecciona hasta 5 indicadores...",
                    style={"fontSize": "0.82rem"},
                ),
            ], width=5),
            dbc.Col([
                html.Div("FECHA INICIO (base 100)", className="metric-card-title",
                         style={"marginBottom": "4px"}),
                dcc.DatePickerSingle(
                    id="m14-multi-date1",
                    display_format="DD/MM/YYYY",
                    placeholder="Fecha inicio...",
                    clearable=True,
                ),
            ], width=3),
            dbc.Col([
                html.Div("FECHA FIN", className="metric-card-title",
                         style={"marginBottom": "4px"}),
                dcc.DatePickerSingle(
                    id="m14-multi-date2",
                    display_format="DD/MM/YYYY",
                    placeholder="Fecha fin...",
                    clearable=True,
                ),
            ], width=2),
            dbc.Col([
                html.Div("\u00a0", className="metric-card-title", style={"marginBottom": "4px"}),
                dbc.Button("Comparar", id="m14-multi-btn", color="primary", className="w-100"),
            ], width=2),
        ], className="g-2 mb-3"),
        html.Div(id="m14-multi-results"),
    ])

    # ── Sección C: Comparador de dos fechas libres ───────────────────────────
    section_snaps = html.Div([
        dbc.Alert(
            [
                html.Strong("Semáforo: "),
                html.Span("▲ Mejor  ", style={"color": "#00c853"}),
                html.Span("▼ Peor  ", style={"color": "#d50000"}),
                html.Span("● Sin cambio  ", style={"color": "#ffd600"}),
                "— Elige cualquier par de fechas. Se comparan los ~19 indicadores clave "
                "consultando el valor más reciente en o antes de cada fecha.",
            ],
            color="dark",
            style={"fontSize": "0.78rem", "padding": "8px 14px", "marginBottom": "12px",
                   "border": "1px solid #374151", "backgroundColor": "rgba(16,185,129,0.06)"},
        ),
        dbc.Row([
            dbc.Col([
                html.Div("FECHA A", className="metric-card-title",
                         style={"marginBottom": "4px"}),
                dcc.DatePickerSingle(
                    id="m14-snap-cmp-1",
                    display_format="DD/MM/YYYY",
                    placeholder="Fecha A...",
                    clearable=True,
                    style={"width": "100%"},
                ),
            ], width=3),
            dbc.Col([
                html.Div("FECHA B", className="metric-card-title",
                         style={"marginBottom": "4px"}),
                dcc.DatePickerSingle(
                    id="m14-snap-cmp-2",
                    display_format="DD/MM/YYYY",
                    placeholder="Fecha B...",
                    clearable=True,
                    style={"width": "100%"},
                ),
            ], width=3),
            dbc.Col([
                html.Div("\u00a0", className="metric-card-title",
                         style={"marginBottom": "4px"}),
                dbc.Button("Comparar fechas", id="m14-snap-cmp-btn",
                           color="primary", className="w-100"),
            ], width=3),
            dbc.Col([
                html.Div("\u00a0", className="metric-card-title",
                         style={"marginBottom": "4px"}),
                dbc.Button(
                    "Exportar CSV",
                    id="m14-snap-cmp-export-btn",
                    color="secondary",
                    outline=True,
                    className="w-100",
                    disabled=True,
                ),
                dcc.Download(id="m14-snap-cmp-download"),
            ], width=3),
        ], className="g-2 mb-3"),
        html.Div(id="m14-snap-cmp-results"),
    ])

    return html.Div([
        dbc.Tabs([
            dbc.Tab(section_simple, label="Comparador simple",      tab_id="t2-simple"),
            dbc.Tab(section_multi,  label="Multi-indicador base 100", tab_id="t2-multi"),
            dbc.Tab(section_snaps,  label="Comparar snapshots",     tab_id="t2-snaps"),
        ], id="m14-t2-subtabs", active_tab="t2-simple"),
    ])


def _build_tab3():
    """Tab 3: Linea de tiempo global."""
    cat_options = [
        {"label": "Todas las categorias", "value": "all"},
        {"label": "Geopolitica / Conflicto", "value": "geopolitics"},
        {"label": "Macro / Bancos centrales", "value": "macro"},
        {"label": "Mercados", "value": "markets"},
        {"label": "Energia", "value": "energy"},
        {"label": "Crypto (halvings BTC)", "value": "crypto_cycle"},
    ]

    return html.Div([
        # Explicación del tab
        dbc.Alert([
            html.Strong("Como funciona: "),
            "Cada punto = un evento (geopolítico, macroeconómico o crypto). ",
            html.Strong("Tamaño = severidad (1-5). "),
            "Haz clic en un punto para activar el ",
            html.Strong("viaje en el tiempo"),
            " — todos los módulos mostrarán los datos de esa fecha.",
        ], color="dark", style={"fontSize": "0.78rem", "padding": "8px 14px", "marginBottom": "12px",
                                "border": "1px solid #374151", "backgroundColor": "rgba(59,130,246,0.06)"}),

        dbc.Row([
            dbc.Col([
                html.Div("CATEGORIA", className="metric-card-title", style={"marginBottom": "4px"}),
                dcc.Dropdown(
                    id="m14-timeline-cat",
                    options=cat_options,
                    value="all",
                    clearable=False,
                    style={"fontSize": "0.82rem"},
                ),
            ], width=4),
            dbc.Col([
                html.Div("PERIODO", className="metric-card-title", style={"marginBottom": "4px"}),
                dcc.Dropdown(
                    id="m14-timeline-period",
                    options=[
                        {"label": "Ultimos 6 meses", "value": "0.5"},
                        {"label": "Ultimos 12 meses", "value": "1"},
                        {"label": "Ultimos 5 años", "value": "5"},
                        {"label": "Todo el historial", "value": "all"},
                    ],
                    value="all",
                    clearable=False,
                    style={"fontSize": "0.82rem"},
                ),
            ], width=4),
            dbc.Col([
                html.Div("\u00a0", className="metric-card-title"),
                dbc.Button(
                    "Añadir evento manual",
                    id="m14-add-event-btn",
                    color="primary",
                    outline=True,
                    size="sm",
                    className="w-100",
                ),
            ], width=4),
        ], className="g-2 mb-3"),

        html.Div(id="m14-timeline-chart"),

        # Modal para añadir evento
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("Añadir Evento a la Linea de Tiempo")),
            dbc.ModalBody([
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Titulo", style={"fontSize": "0.82rem"}),
                        dbc.Input(id="m14-evt-title", placeholder="Titulo del evento...", size="sm"),
                    ], width=8),
                    dbc.Col([
                        dbc.Label("Fecha", style={"fontSize": "0.82rem"}),
                        dcc.DatePickerSingle(id="m14-evt-date", display_format="DD/MM/YYYY"),
                    ], width=4),
                ], className="mb-2"),
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Categoria", style={"fontSize": "0.82rem"}),
                        dcc.Dropdown(
                            id="m14-evt-cat",
                            options=[
                                {"label": "Geopolitica", "value": "geopolitics"},
                                {"label": "Macro", "value": "macro"},
                                {"label": "Mercados", "value": "markets"},
                                {"label": "Energia", "value": "energy"},
                                {"label": "Crypto", "value": "crypto_cycle"},
                                {"label": "Monetaria", "value": "monetary"},
                            ],
                            value="macro",
                        ),
                    ], width=6),
                    dbc.Col([
                        dbc.Label("Severidad (1-5)", style={"fontSize": "0.82rem"}),
                        dbc.Input(id="m14-evt-severity", type="number", min=1, max=5, value=3, size="sm"),
                    ], width=6),
                ], className="mb-2"),
                dbc.Label("Descripcion", style={"fontSize": "0.82rem"}),
                dbc.Textarea(id="m14-evt-desc", placeholder="Descripcion del evento...", rows=3),
            ]),
            dbc.ModalFooter([
                dbc.Button("Guardar evento", id="m14-evt-save-btn", color="primary", size="sm"),
                dbc.Button("Cancelar", id="m14-evt-cancel-btn", color="secondary", outline=True, size="sm"),
            ]),
        ], id="m14-event-modal", is_open=False),

        html.Div(id="m14-evt-feedback", style={"marginTop": "6px", "fontSize": "0.75rem"}),
    ])


def _build_tab4():
    """Tab 4: Comparativa con crisis historicas."""
    crises = _load_crises()
    indicator_opts = [
        {"label": "S&P 500", "value": "sp500"},
        {"label": "VIX (Volatilidad)", "value": "vix"},
        {"label": "Tipos Fed (%)", "value": "fed_funds"},
        {"label": "Desempleo EE.UU. (%)", "value": "unemployment"},
        {"label": "Spread 10Y-2Y (%)", "value": "spread_10y2y"},
        {"label": "Petroleo Brent (USD)", "value": "brent"},
    ]

    return html.Div([
        dbc.Row([
            dbc.Col([
                html.Div("INDICADOR A COMPARAR", className="metric-card-title", style={"marginBottom": "4px"}),
                dcc.Dropdown(
                    id="m14-crisis-indicator",
                    options=indicator_opts,
                    value="sp500",
                    clearable=False,
                    style={"fontSize": "0.82rem"},
                ),
            ], width=5),
            dbc.Col([
                html.Div("NORMALIZACION", className="metric-card-title", style={"marginBottom": "4px"}),
                dcc.Dropdown(
                    id="m14-crisis-normalize",
                    options=[
                        {"label": "Indexado (evento = 100)", "value": "indexed"},
                        {"label": "Valores absolutos", "value": "absolute"},
                    ],
                    value="indexed",
                    clearable=False,
                    style={"fontSize": "0.82rem"},
                ),
            ], width=4),
            dbc.Col([
                html.Div("\u00a0", className="metric-card-title"),
                dbc.Button("Actualizar", id="m14-crisis-btn", color="primary", className="w-100"),
            ], width=3),
        ], className="g-2 mb-3"),
        html.Div(id="m14-crisis-chart"),
        html.Div([
            html.Hr(style={"borderColor": "#2a2a2a", "margin": "16px 0"}),
            html.Div("FICHAS DE CRISIS", className="metric-card-title", style={"marginBottom": "10px"}),
            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.Div(
                            [html.Span("●", style={"color": c["color"], "marginRight": "6px"}), c["name"]],
                            style={"fontWeight": "bold", "fontSize": "0.85rem", "marginBottom": "4px"},
                        ),
                        html.Div(c["description"], style={"fontSize": "0.75rem", "color": COLORS["text_muted"]}),
                    ], className="metric-card"),
                ], width=4)
                for c in crises
            ], className="g-2"),
        ]),
    ])


def _build_tab5():
    """Tab 5: Registro de escenarios."""
    scenarios = _get_scenarios()

    outcome_color = {
        "pending": COLORS.get("yellow", "#ffd600"),
        "correct": "#00c853",
        "incorrect": "#d50000",
        "partial": "#ff6d00",
    }
    outcome_label = {
        "pending": "Pendiente",
        "correct": "Confirmado",
        "incorrect": "No ocurrió",
        "partial": "Parcialmente",
    }

    rows = []
    for s in scenarios:
        prob_pct = f"{s['probability']*100:.0f}%" if s["probability"] is not None else "—"
        tgt = s["target_date"].strftime("%d/%m/%Y") if s["target_date"] else "—"
        created = s["created_at"].strftime("%d/%m/%Y") if s["created_at"] else "—"
        outcome = s["outcome"] or "pending"
        rows.append(
            html.Tr([
                html.Td(created, style={"fontSize": "0.75rem", "whiteSpace": "nowrap"}),
                html.Td(html.Span(s["title"], title=s.get("description") or ""), style={"fontSize": "0.78rem"}),
                html.Td(prob_pct, style={"textAlign": "center", "fontSize": "0.78rem"}),
                html.Td(tgt, style={"textAlign": "center", "fontSize": "0.75rem"}),
                html.Td(
                    dbc.Badge(
                        outcome_label.get(outcome, outcome),
                        style={"backgroundColor": outcome_color.get(outcome, "#666"), "fontSize": "0.7rem"},
                    ),
                    style={"textAlign": "center"},
                ),
            ])
        )

    table = dbc.Table(
        [
            html.Thead(html.Tr([
                html.Th("Creado", style={"fontSize": "0.75rem"}),
                html.Th("Escenario", style={"fontSize": "0.75rem"}),
                html.Th("Prob.", style={"fontSize": "0.75rem", "textAlign": "center"}),
                html.Th("Fecha limite", style={"fontSize": "0.75rem", "textAlign": "center"}),
                html.Th("Estado", style={"fontSize": "0.75rem", "textAlign": "center"}),
            ])),
            html.Tbody(rows if rows else [
                html.Tr(html.Td(
                    "No hay escenarios registrados aun.",
                    colSpan=5,
                    style={"textAlign": "center", "color": COLORS["text_muted"], "fontSize": "0.78rem", "padding": "20px"},
                ))
            ]),
        ],
        bordered=False,
        dark=True,
        hover=True,
        size="sm",
        style={"backgroundColor": COLORS["card_bg"]},
    )

    return html.Div([
        dbc.Row([
            # Formulario de nuevo escenario
            dbc.Col([
                html.Div([
                    html.Div("NUEVO ESCENARIO / PREDICCION", className="metric-card-title", style={"marginBottom": "10px"}),
                    dbc.Label("Titulo del escenario", style={"fontSize": "0.8rem"}),
                    dbc.Input(id="m14-sc-title", placeholder="Ej: Recesion EE.UU. en 2026...", size="sm", className="mb-2"),
                    dbc.Label("Descripcion (opcional)", style={"fontSize": "0.8rem"}),
                    dbc.Textarea(id="m14-sc-desc", placeholder="Contexto, razonamiento...", rows=3, className="mb-2",
                                 style={"fontSize": "0.78rem"}),
                    dbc.Row([
                        dbc.Col([
                            dbc.Label("Probabilidad (%)", style={"fontSize": "0.8rem"}),
                            dbc.Input(id="m14-sc-prob", type="number", min=0, max=100, step=5, value=50, size="sm"),
                        ], width=6),
                        dbc.Col([
                            dbc.Label("Fecha limite", style={"fontSize": "0.8rem"}),
                            dcc.DatePickerSingle(id="m14-sc-target-date", display_format="DD/MM/YYYY",
                                                 placeholder="Fecha limite..."),
                        ], width=6),
                    ], className="mb-2"),
                    dbc.Label("Condiciones necesarias", style={"fontSize": "0.8rem"}),
                    dbc.Textarea(id="m14-sc-conditions", placeholder="Ej: Fed baja tipos + desempleo >5%...", rows=2,
                                 className="mb-3", style={"fontSize": "0.78rem"}),
                    dbc.Button("Registrar prediccion", id="m14-sc-save-btn", color="primary", className="w-100"),
                    html.Div(id="m14-sc-feedback", style={"marginTop": "6px", "fontSize": "0.75rem"}),
                ], className="metric-card"),
            ], width=4),

            # Lista de escenarios
            dbc.Col([
                html.Div([
                    html.Div("HISTORIAL DE PREDICCIONES", className="metric-card-title", style={"marginBottom": "10px"}),
                    html.Div(table, style={"maxHeight": "420px", "overflowY": "auto"}),
                ], className="metric-card"),
            ], width=8),
        ], className="g-3"),
    ])


# ── Render principal ───────────────────────────────────────────────────────────

def render_module_14() -> html.Div:
    ctx_dt = get_time_context()
    if ctx_dt is not None:
        ctx_label = ctx_dt.strftime("%d/%m/%Y")
        header_badge = dbc.Badge(
            f"MODO HISTORICO: {ctx_label}",
            color="warning",
            style={"backgroundColor": "#f97316", "fontSize": "0.78rem", "marginLeft": "10px"},
        )
    else:
        header_badge = dbc.Badge("TIEMPO REAL", color="success",
                                  style={"fontSize": "0.78rem", "marginLeft": "10px"})

    return html.Div([
        # Cabecera
        html.Div([
            html.Div(
                [html.Span("MODULO 14 — HISTORICO Y COMPARATIVAS TEMPORALES"), header_badge],
                className="module-title",
            ),
            html.Div("Viaje en el tiempo · Comparador · Linea de tiempo · Crisis historicas · Escenarios",
                     className="module-subtitle"),
        ], style={"marginBottom": "16px"}),

        # Store para comunicar fecha activa entre callbacks
        dcc.Store(id="m14-active-date-store"),

        # Tabs
        dbc.Tabs(
            [
                dbc.Tab(_build_tab1(), label="Viaje en el tiempo", tab_id="m14-t1"),
                dbc.Tab(_build_tab2(), label="Comparador temporal", tab_id="m14-t2"),
                dbc.Tab(_build_tab3(), label="Linea de tiempo", tab_id="m14-t3"),
                dbc.Tab(_build_tab4(), label="Crisis historicas", tab_id="m14-t4"),
                dbc.Tab(_build_tab5(), label="Escenarios", tab_id="m14-t5"),
            ],
            id="m14-tabs",
            active_tab="m14-t1",
            className="mb-3",
        ),
    ], className="module-content")


# ── Callbacks ─────────────────────────────────────────────────────────────────

def register_callbacks_module_14(app):

    # ── Tab 1: Activar viaje en el tiempo ─────────────────────────────────────

    @app.callback(
        Output("m14-time-status-panel", "children"),
        Output("m14-active-date-store", "data"),
        Input("m14-activate-btn", "n_clicks"),
        Input("m14-reset-btn", "n_clicks"),
        Input({"type": "m14-snap-btn", "date": ALL}, "n_clicks"),
        State("m14-date-picker", "date"),
        prevent_initial_call=True,
    )
    def activate_time_travel(activate_clicks, reset_clicks, snap_clicks, picked_date):
        triggered = ctx.triggered_id
        if triggered == "m14-reset-btn":
            set_time_context(None)
            return _build_time_status_panel(None), None
        if isinstance(triggered, dict) and triggered.get("type") == "m14-snap-btn":
            date_str = triggered["date"]
            set_time_context(date_str)
            return _build_time_status_panel(date_str), date_str
        # Botón activar
        if picked_date:
            set_time_context(picked_date)
            return _build_time_status_panel(picked_date), picked_date
        return no_update, no_update

    # ── Tab 1: Snapshot manual ─────────────────────────────────────────────────

    @app.callback(
        Output("m14-snap-feedback", "children"),
        Input("m14-snap-now-btn", "n_clicks"),
        State("m14-snap-label", "value"),
        prevent_initial_call=True,
    )
    def take_manual_snapshot(n_clicks, label):
        if not n_clicks:
            return no_update
        try:
            from scheduler.scheduler import DashboardScheduler
            s = DashboardScheduler.__new__(DashboardScheduler)
            s._collectors = {}
            s._init_db()
            ok = s.take_manual_snapshot(label=label or None)
            if ok:
                return dbc.Alert("Snapshot guardado correctamente.", color="success",
                                 dismissable=True, style={"fontSize": "0.75rem"})
            return dbc.Alert("Error al guardar el snapshot.", color="danger",
                             dismissable=True, style={"fontSize": "0.75rem"})
        except Exception as exc:
            logger.error("take_manual_snapshot callback: %s", exc)
            return dbc.Alert(f"Error: {exc}", color="danger",
                             dismissable=True, style={"fontSize": "0.75rem"})

    # ── Tab 2: Comparador temporal ─────────────────────────────────────────────

    @app.callback(
        Output("m14-cmp-results", "children"),
        Input("m14-cmp-btn", "n_clicks"),
        State("m14-cmp-indicator", "value"),
        State("m14-cmp-date1", "date"),
        State("m14-cmp-date2", "date"),
        prevent_initial_call=True,
    )
    def comparar_temporal(n_clicks, indicator_id, date1_str, date2_str):
        if not n_clicks or not indicator_id:
            return no_update
        if not date1_str or not date2_str:
            return dbc.Alert("Selecciona ambas fechas.", color="warning", style={"fontSize": "0.78rem"})
        try:
            d1 = datetime.strptime(date1_str, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            d2 = datetime.strptime(date2_str, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
        except ValueError:
            return dbc.Alert("Fechas inválidas.", color="danger", style={"fontSize": "0.78rem"})

        v1, ts1 = get_value_at_date(indicator_id, d1)
        v2, ts2 = get_value_at_date(indicator_id, d2)

        # Etiqueta del indicador
        all_opts = {v: l for group in INDICATOR_GROUPS.values() for l, v in group}
        ind_label = all_opts.get(indicator_id, indicator_id)

        # Gráfico de la serie entre las dos fechas
        date_from = min(d1, d2) - timedelta(days=30)
        date_to   = max(d1, d2) + timedelta(days=30)
        series_df = get_series_between(indicator_id, date_from, date_to)

        fig = go.Figure()
        if not series_df.empty:
            fig.add_trace(go.Scatter(
                x=series_df["timestamp"],
                y=series_df["value"],
                mode="lines",
                name=ind_label,
                line=dict(color=COLORS["accent"], width=2),
            ))
        # Líneas verticales para las dos fechas (sin annotation en add_vline para evitar
        # el bug de Plotly que falla al calcular la media sobre strings ISO)
        for vdate, color, label in [
            (d1, "#10b981", f"Fecha 1: {d1.strftime('%d/%m/%Y')}"),
            (d2, "#f59e0b", f"Fecha 2: {d2.strftime('%d/%m/%Y')}"),
        ]:
            fig.add_shape(
                type="line",
                x0=vdate, x1=vdate,
                y0=0, y1=1,
                xref="x", yref="paper",
                line=dict(color=color, dash="dash", width=2),
            )
            fig.add_annotation(
                x=vdate, y=1,
                xref="x", yref="paper",
                text=label,
                showarrow=False,
                yshift=8,
                font=dict(size=10, color=color),
                bgcolor="rgba(17,24,39,0.8)",
            )

        fig.update_layout(**_plotly_dark_layout(f"{ind_label} — entre fechas seleccionadas", height=320))

        # Tabla comparativa
        if v1 is not None and v2 is not None:
            abs_diff = v2 - v1
            pct_diff = (abs_diff / abs(v1) * 100) if v1 != 0 else None
            diff_color = "#10b981" if abs_diff >= 0 else "#ef4444"
            sign = "+" if abs_diff >= 0 else ""
            rows_table = [
                ("Valor fecha 1",    ts1.strftime("%d/%m/%Y") if ts1 else date1_str,  f"{v1:,.4f}", ""),
                ("Valor fecha 2",    ts2.strftime("%d/%m/%Y") if ts2 else date2_str,  f"{v2:,.4f}", ""),
                ("Variacion abs.",   "",                                               f"{sign}{abs_diff:,.4f}", diff_color),
                ("Variacion %",      "",  f"{sign}{pct_diff:.2f}%" if pct_diff is not None else "—", diff_color),
            ]
        else:
            rows_table = [("Sin datos", "Verifica que el indicador tenga datos en esas fechas.", "—", "")]

        table = dbc.Table([
            html.Thead(html.Tr([html.Th("Metrica"), html.Th("Fecha"), html.Th("Valor")])),
            html.Tbody([
                html.Tr([
                    html.Td(r[0], style={"fontSize": "0.78rem"}),
                    html.Td(r[1], style={"fontSize": "0.75rem", "color": COLORS["text_muted"]}),
                    html.Td(r[2], style={"fontSize": "0.82rem", "fontWeight": "bold", "color": r[3] or COLORS["text"]}),
                ]) for r in rows_table
            ]),
        ], bordered=False, dark=True, size="sm",
           style={"backgroundColor": COLORS["card_bg"], "marginTop": "12px"})

        return html.Div([
            dcc.Graph(figure=fig, config={"displayModeBar": False}),
            table,
        ])

    # ── Tab 2: Comparador multi-indicador base 100 ────────────────────────────

    @app.callback(
        Output("m14-multi-results", "children"),
        Input("m14-multi-btn", "n_clicks"),
        State("m14-multi-indicators", "value"),
        State("m14-multi-date1", "date"),
        State("m14-multi-date2", "date"),
        prevent_initial_call=True,
    )
    def comparar_multi_indicador(n_clicks, indicator_ids, date1_str, date2_str):
        if not n_clicks:
            return no_update
        if not indicator_ids:
            return dbc.Alert("Selecciona al menos un indicador.", color="warning",
                             style={"fontSize": "0.78rem"})
        if not date1_str or not date2_str:
            return dbc.Alert("Selecciona ambas fechas.", color="warning",
                             style={"fontSize": "0.78rem"})
        # Limitar a 5 indicadores
        indicator_ids = list(indicator_ids)[:5]
        try:
            d1 = datetime.strptime(date1_str, "%Y-%m-%d")
            d2 = datetime.strptime(date2_str, "%Y-%m-%d")
        except ValueError:
            return dbc.Alert("Fechas inválidas.", color="danger", style={"fontSize": "0.78rem"})
        if d1 >= d2:
            return dbc.Alert("Fecha 1 debe ser anterior a Fecha 2.", color="warning",
                             style={"fontSize": "0.78rem"})

        all_opts_flat = {v: l for group in INDICATOR_GROUPS.values() for l, v in group}
        PALETTE = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6"]

        fig = go.Figure()
        summary_rows = []
        any_data = False

        for idx, ind_id in enumerate(indicator_ids):
            df = get_series_between(ind_id, d1, d2)
            color = PALETTE[idx % len(PALETTE)]
            label = all_opts_flat.get(ind_id, ind_id)

            if df.empty:
                summary_rows.append((label, "—", "—", "—", "#666"))
                continue

            # Normalizar a 100 en el primer punto
            base = df["value"].iloc[0]
            if base is None or base == 0:
                summary_rows.append((label, "—", "—", "—", "#666"))
                continue

            df = df.copy()
            df["norm"] = df["value"] / base * 100

            fig.add_trace(go.Scatter(
                x=df["timestamp"],
                y=df["norm"],
                mode="lines",
                name=label,
                line=dict(color=color, width=2),
                hovertemplate=(
                    f"<b>{label}</b><br>"
                    "Fecha: %{x|%d/%m/%Y}<br>"
                    "Base 100: <b>%{y:.2f}</b><extra></extra>"
                ),
            ))

            val_start = df["value"].iloc[0]
            val_end   = df["value"].iloc[-1]
            norm_end  = df["norm"].iloc[-1]
            pct_chg   = norm_end - 100
            sign      = "+" if pct_chg >= 0 else ""
            row_color = "#10b981" if pct_chg >= 0 else "#ef4444"
            summary_rows.append((
                label,
                f"{val_start:,.3f}",
                f"{val_end:,.3f}",
                f"{sign}{pct_chg:.2f}%",
                row_color,
            ))
            any_data = True

        if not any_data:
            return dbc.Alert(
                "No hay datos para los indicadores seleccionados en ese período.",
                color="secondary", style={"fontSize": "0.78rem"},
            )

        # Línea de referencia en 100
        fig.add_hline(y=100, line=dict(color="#555", dash="dot", width=1))

        fig.update_layout(
            **_plotly_dark_layout("Evolución comparada — base 100 en Fecha 1", height=380)
        )
        fig.update_layout(
            yaxis_title="Índice (base 100 = Fecha 1)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        )

        table = dbc.Table([
            html.Thead(html.Tr([
                html.Th("Indicador",   style={"fontSize": "0.75rem"}),
                html.Th("Val. inicio", style={"fontSize": "0.75rem", "textAlign": "right"}),
                html.Th("Val. fin",    style={"fontSize": "0.75rem", "textAlign": "right"}),
                html.Th("Variación %", style={"fontSize": "0.75rem", "textAlign": "right"}),
            ])),
            html.Tbody([
                html.Tr([
                    html.Td(r[0], style={"fontSize": "0.78rem"}),
                    html.Td(r[1], style={"fontSize": "0.78rem", "textAlign": "right",
                                         "color": COLORS["text_muted"]}),
                    html.Td(r[2], style={"fontSize": "0.78rem", "textAlign": "right",
                                         "color": COLORS["text_muted"]}),
                    html.Td(r[3], style={"fontSize": "0.82rem", "textAlign": "right",
                                         "fontWeight": "bold", "color": r[4]}),
                ]) for r in summary_rows
            ]),
        ], bordered=False, dark=True, size="sm",
           style={"backgroundColor": COLORS["card_bg"], "marginTop": "12px"})

        return html.Div([dcc.Graph(figure=fig, config={"displayModeBar": False}), table])

    # ── Tab 2: Comparador de snapshots ─────────────────────────────────────────

    # Almacén interno para pasar el DataFrame al callback de exportación
    _snap_cmp_cache: dict = {}

    @app.callback(
        Output("m14-snap-cmp-results", "children"),
        Output("m14-snap-cmp-export-btn", "disabled"),
        Input("m14-snap-cmp-btn", "n_clicks"),
        State("m14-snap-cmp-1", "date"),
        State("m14-snap-cmp-2", "date"),
        prevent_initial_call=True,
    )
    def comparar_fechas_callback(n_clicks, date1_str, date2_str):
        if not n_clicks:
            return no_update, no_update
        if not date1_str or not date2_str:
            return dbc.Alert("Selecciona ambas fechas.", color="warning",
                             style={"fontSize": "0.78rem"}), True
        try:
            d1 = datetime.strptime(date1_str, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            d2 = datetime.strptime(date2_str, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
        except ValueError:
            return dbc.Alert("Fechas inválidas.", color="danger",
                             style={"fontSize": "0.78rem"}), True

        SIGNAL_COLOR = {"mejor": "#00c853", "peor": "#d50000", "igual": "#ffd600"}
        SIGNAL_ICON  = {"mejor": "▲", "peor": "▼", "igual": "●"}

        rows_data = []   # para la exportación CSV
        rows_html = []

        for label, series_id, lower_is_better in _CMP_DATE_INDICATORS:
            v1, ts1 = get_value_at_date(series_id, d1)
            v2, ts2 = get_value_at_date(series_id, d2)

            if v1 is None and v2 is None:
                continue  # indicador sin datos en ambas fechas → omitir fila

            # Calcular diferencia (None si falta algún valor)
            if v1 is not None and v2 is not None:
                dif_abs = v2 - v1
                dif_pct = (dif_abs / abs(v1) * 100) if v1 != 0 else None
                if abs(dif_abs) < 1e-9:
                    signal = "igual"
                elif lower_is_better is True:
                    signal = "mejor" if dif_abs < 0 else "peor"
                elif lower_is_better is False:
                    signal = "mejor" if dif_abs > 0 else "peor"
                else:
                    signal = "igual"   # neutral: no emite señal
            else:
                dif_abs = None
                dif_pct = None
                signal  = "igual"

            sig_color = SIGNAL_COLOR.get(signal, "#aaa")
            sig_icon  = SIGNAL_ICON.get(signal, "●")

            v1_str  = f"{v1:,.3f}"   if v1  is not None else "—"
            v2_str  = f"{v2:,.3f}"   if v2  is not None else "—"
            dif_str = (f"{'+' if dif_abs >= 0 else ''}{dif_abs:,.3f}"
                       if dif_abs is not None else "—")
            pct_str = (f"{dif_pct:+.2f}%"
                       if dif_pct is not None else "—")

            # Fecha real más cercana para tooltip
            ts1_str = ts1.strftime("%d/%m/%Y") if ts1 else "—"
            ts2_str = ts2.strftime("%d/%m/%Y") if ts2 else "—"

            rows_html.append(html.Tr([
                html.Td(label,   style={"fontSize": "0.78rem"}),
                html.Td(
                    html.Span(v1_str, title=f"Dato real: {ts1_str}"),
                    style={"fontSize": "0.78rem", "textAlign": "right",
                           "color": COLORS["text_muted"]}
                ),
                html.Td(
                    html.Span(v2_str, title=f"Dato real: {ts2_str}"),
                    style={"fontSize": "0.78rem", "textAlign": "right",
                           "color": COLORS["text_muted"]}
                ),
                html.Td(dif_str, style={"fontSize": "0.78rem", "textAlign": "right"}),
                html.Td(pct_str, style={"fontSize": "0.78rem", "textAlign": "right"}),
                html.Td(
                    html.Span(f"{sig_icon} {signal.capitalize()}",
                              style={"color": sig_color, "fontWeight": "bold",
                                     "fontSize": "0.78rem"}),
                    style={"textAlign": "center"},
                ),
            ]))

            rows_data.append({
                "Indicador":      label,
                f"Fecha_A ({date1_str})": v1_str,
                f"Fecha_B ({date2_str})": v2_str,
                "Diferencia_Abs": dif_str,
                "Diferencia_Pct": pct_str,
                "Señal":          signal,
            })

        if not rows_html:
            return dbc.Alert(
                "No hay datos disponibles para ningún indicador en esas fechas.",
                color="secondary", style={"fontSize": "0.78rem"},
            ), True

        # Guardar para exportación
        import pandas as _pd
        _snap_cmp_cache["df_export"] = _pd.DataFrame(rows_data)
        _snap_cmp_cache["date1"] = date1_str
        _snap_cmp_cache["date2"] = date2_str

        # Contadores del semáforo (solo entre los que tienen datos en ambas fechas)
        mejor_n = sum(1 for r in rows_data if r["Señal"] == "mejor")
        peor_n  = sum(1 for r in rows_data if r["Señal"] == "peor")
        igual_n = sum(1 for r in rows_data if r["Señal"] == "igual")

        d1_label = d1.strftime("%d/%m/%Y")
        d2_label = d2.strftime("%d/%m/%Y")

        table = dbc.Table([
            html.Thead(html.Tr([
                html.Th("Indicador",  style={"fontSize": "0.75rem"}),
                html.Th(f"Fecha A ({d1_label})",
                        style={"fontSize": "0.75rem", "textAlign": "right"}),
                html.Th(f"Fecha B ({d2_label})",
                        style={"fontSize": "0.75rem", "textAlign": "right"}),
                html.Th("Dif. abs.",  style={"fontSize": "0.75rem", "textAlign": "right"}),
                html.Th("Dif. %",     style={"fontSize": "0.75rem", "textAlign": "right"}),
                html.Th("Señal",      style={"fontSize": "0.75rem", "textAlign": "center"}),
            ])),
            html.Tbody(rows_html),
        ], bordered=False, dark=True, hover=True, size="sm",
           style={"backgroundColor": COLORS["card_bg"]})

        summary = html.Div([
            html.Span(f"▲ {mejor_n} mejora{'s' if mejor_n != 1 else ''}",
                      style={"color": "#00c853", "fontWeight": "bold", "fontSize": "0.82rem",
                             "marginRight": "16px"}),
            html.Span(f"▼ {peor_n} empeora{'n' if peor_n != 1 else ''}",
                      style={"color": "#d50000", "fontWeight": "bold", "fontSize": "0.82rem",
                             "marginRight": "16px"}),
            html.Span(f"● {igual_n} sin cambio / neutral",
                      style={"color": "#ffd600", "fontSize": "0.82rem"}),
        ], style={"marginBottom": "8px"})

        return html.Div([summary, table]), False

    @app.callback(
        Output("m14-snap-cmp-download", "data"),
        Input("m14-snap-cmp-export-btn", "n_clicks"),
        prevent_initial_call=True,
    )
    def exportar_comparativa_csv(n_clicks):
        if not n_clicks:
            return no_update
        export_df = _snap_cmp_cache.get("df_export")
        if export_df is None or export_df.empty:
            return no_update
        date1 = _snap_cmp_cache.get("date1", "A").replace("-", "")
        date2 = _snap_cmp_cache.get("date2", "B").replace("-", "")
        filename = f"comparativa_{date1}_vs_{date2}.csv"
        return dcc.send_data_frame(export_df.to_csv, filename, index=False)

    # ── Tab 3: Linea de tiempo ─────────────────────────────────────────────────

    # Mapeo: categorías de la BD → categoría canónica del filtro
    _CAT_NORMALIZE = {
        "conflict":      "geopolitics",
        "geopolitical":  "geopolitics",
        "central_banks": "macro",
        "monetary":      "macro",
        "market":        "markets",
        "crypto":        "crypto_cycle",
        "halving":       "crypto_cycle",
    }
    # Etiquetas para el eje Y (swimlane)
    _SWIMLANE_LABEL = {
        "geopolitics":  "Geopolítica",
        "macro":        "Macro / BC",
        "markets":      "Mercados",
        "energy":       "Energía",
        "crypto_cycle": "Crypto",
        "auto":         "Otros",
    }
    _SWIMLANE_Y = {
        "crypto_cycle": 5,
        "geopolitics":  4,
        "macro":        3,
        "markets":      2,
        "energy":       1,
        "auto":         0,
    }

    @app.callback(
        Output("m14-timeline-chart", "children"),
        Input("m14-timeline-cat", "value"),
        Input("m14-timeline-period", "value"),
        prevent_initial_call=False,
    )
    def render_timeline(cat_filter, period_filter):
        all_events = _get_timeline_events()

        # Normalizar categorías de la BD al esquema canónico del filtro
        for e in all_events:
            raw_cat = (e.get("category") or "auto").lower()
            e["category_norm"] = _CAT_NORMALIZE.get(raw_cat, raw_cat)

        # Filtro de período
        now = datetime.utcnow()
        if period_filter and period_filter != "all":
            try:
                years = float(period_filter)
                cutoff = now - timedelta(days=years * 365)
                all_events = [e for e in all_events if e.get("date") and e["date"] >= cutoff]
            except Exception:
                pass

        # Filtro de categoría (sobre la categoría normalizada)
        if cat_filter and cat_filter != "all":
            all_events = [e for e in all_events if e.get("category_norm") == cat_filter]

        if not all_events:
            return html.Div([
                dbc.Alert(
                    "No hay eventos registrados con estos filtros. "
                    "Prueba con 'Todas las categorias' + 'Todo el historial', "
                    "o añade eventos con el botón 'Añadir evento manual'.",
                    color="secondary",
                    style={"fontSize": "0.78rem"},
                ),
            ])

        # Construir trazas por swimlane (una por categoría)
        fig = go.Figure()
        categories_present = sorted(
            set(e["category_norm"] for e in all_events),
            key=lambda c: _SWIMLANE_Y.get(c, 0),
            reverse=True,
        )

        valid_events = []  # para la tabla debajo del gráfico
        for cat in categories_present:
            cat_events = [e for e in all_events if e["category_norm"] == cat]
            lane_y = _SWIMLANE_Y.get(cat, 0)
            color = CATEGORY_COLORS.get(cat, "#6b7280")
            label = _SWIMLANE_LABEL.get(cat, cat.capitalize())

            xs, ys, sizes, hovers, custom = [], [], [], [], []
            for e in cat_events:
                d = e.get("date")
                if not d or not hasattr(d, "isoformat"):
                    continue
                try:
                    sev = int(e.get("severity") or 2)
                except (ValueError, TypeError):
                    sev = 2
                sev = max(1, min(5, sev))
                xs.append(d)
                ys.append(lane_y)
                sizes.append(sev * 7 + 8)  # min=15 max=43
                hovers.append(
                    f"<b>{e.get('title', '')[:70]}</b><br>"
                    f"<span style='color:{color}'>■ {label}</span><br>"
                    f"Fecha: <b>{d.strftime('%d/%m/%Y')}</b><br>"
                    f"Severidad: {'⬛' * sev}<br>"
                    + (f"{e.get('description','')[:120]}" if e.get("description") else "")
                )
                custom.append(d.strftime("%Y-%m-%d"))
                valid_events.append(e)

            if not xs:
                continue

            fig.add_trace(go.Scatter(
                x=xs,
                y=ys,
                mode="markers",
                name=label,
                marker=dict(
                    size=sizes,
                    color=color,
                    opacity=0.88,
                    line=dict(color="#0a0e1a", width=1.5),
                    symbol="circle",
                ),
                hovertemplate="%{hovertext}<extra></extra>",
                hovertext=hovers,
                customdata=custom,
            ))

        # Layout con swimlanes
        y_tickvals = [_SWIMLANE_Y.get(c, 0) for c in categories_present]
        y_ticktext = [_SWIMLANE_LABEL.get(c, c.capitalize()) for c in categories_present]

        n_lanes = len(categories_present)
        height = max(260, 80 + n_lanes * 70)

        fig.update_layout(**_plotly_dark_layout("", height=height))
        fig.update_layout(
            yaxis=dict(
                tickmode="array",
                tickvals=y_tickvals,
                ticktext=y_ticktext,
                showgrid=True,
                gridcolor="#1f2937",
                zeroline=False,
                range=[-0.8, max(y_tickvals) + 0.8] if y_tickvals else [0, 6],
                tickfont=dict(size=11, color=COLORS["text_muted"]),
            ),
            xaxis=dict(gridcolor="#1f2937", showgrid=True),
            showlegend=False,
            margin=dict(l=100, r=24, t=20, b=40),
        )

        # Tabla de eventos debajo del gráfico
        sorted_events = sorted(
            [e for e in valid_events if e.get("date") and hasattr(e["date"], "strftime")],
            key=lambda e: e["date"], reverse=True,
        )
        table_rows = []
        for e in sorted_events[:20]:
            d = e["date"]
            sev = e.get("severity", 2)
            try:
                sev = int(sev)
            except Exception:
                sev = 2
            cat_norm = e.get("category_norm", "auto")
            color = CATEGORY_COLORS.get(cat_norm, "#6b7280")
            table_rows.append(html.Tr([
                html.Td(
                    dbc.Button(
                        d.strftime("%d/%m/%Y"),
                        id={"type": "m14-evt-row-btn", "date": d.strftime("%Y-%m-%d")},
                        size="sm", color="link",
                        style={"fontSize": "0.75rem", "padding": "0 4px", "color": COLORS["accent"]},
                    )
                ),
                html.Td(
                    html.Span("●", style={"color": color, "fontSize": "0.9rem"}),
                    style={"textAlign": "center"},
                ),
                html.Td(
                    e.get("title", "")[:65],
                    style={"fontSize": "0.75rem", "color": COLORS["text"]},
                ),
                html.Td(
                    _SWIMLANE_LABEL.get(cat_norm, cat_norm),
                    style={"fontSize": "0.72rem", "color": COLORS["text_muted"]},
                ),
                html.Td(
                    "⬛" * min(sev, 5),
                    style={"fontSize": "0.65rem", "letterSpacing": "-2px"},
                ),
            ]))

        events_table = dbc.Table(
            [
                html.Thead(html.Tr([
                    html.Th("Fecha", style={"fontSize": "0.7rem"}),
                    html.Th("", style={"width": "20px"}),
                    html.Th("Titulo", style={"fontSize": "0.7rem"}),
                    html.Th("Categoria", style={"fontSize": "0.7rem"}),
                    html.Th("Sev.", style={"fontSize": "0.7rem"}),
                ])),
                html.Tbody(table_rows),
            ],
            bordered=False, dark=True, hover=True, size="sm",
            style={"backgroundColor": COLORS["card_bg"], "marginTop": "12px"},
        )

        return html.Div([
            dcc.Graph(
                figure=fig,
                id="m14-timeline-figure",
                config={"displayModeBar": False},
                style={"cursor": "pointer"},
            ),
            html.Div(
                "Haz clic en un punto para activar el viaje en el tiempo a esa fecha.",
                style={"fontSize": "0.72rem", "color": COLORS["text_muted"], "marginTop": "4px"},
            ),
            html.Div([
                html.Div(f"Mostrando {len(sorted_events)} evento{'s' if len(sorted_events)!=1 else ''}:",
                         className="metric-card-title", style={"margin": "12px 0 6px"}),
                events_table,
            ]),
        ])

    @app.callback(
        Output("m14-time-status-panel", "children", allow_duplicate=True),
        Output("m14-active-date-store", "data", allow_duplicate=True),
        Input("m14-timeline-figure", "clickData"),
        Input({"type": "m14-evt-row-btn", "date": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def timeline_click_time_travel(click_data, row_clicks):
        triggered = ctx.triggered_id
        # Clic en botón de fila de la tabla
        if isinstance(triggered, dict) and triggered.get("type") == "m14-evt-row-btn":
            date_str = triggered["date"]
            set_time_context(date_str)
            return _build_time_status_panel(date_str), date_str
        # Clic en punto del gráfico: usar customdata (fecha "YYYY-MM-DD")
        if click_data:
            try:
                point = click_data["points"][0]
                date_str = point.get("customdata")
                if not date_str:
                    date_str = str(point.get("x", ""))[:10]
                if date_str and len(date_str) >= 10:
                    set_time_context(date_str[:10])
                    return _build_time_status_panel(date_str[:10]), date_str[:10]
            except Exception as exc:
                logger.debug("timeline click: %s", exc)
        return no_update, no_update

    # ── Tab 3: Modal añadir evento ─────────────────────────────────────────────

    @app.callback(
        Output("m14-event-modal", "is_open"),
        Input("m14-add-event-btn", "n_clicks"),
        Input("m14-evt-cancel-btn", "n_clicks"),
        Input("m14-evt-save-btn", "n_clicks"),
        State("m14-event-modal", "is_open"),
        State("m14-evt-title", "value"),
        State("m14-evt-date", "date"),
        State("m14-evt-cat", "value"),
        State("m14-evt-severity", "value"),
        State("m14-evt-desc", "value"),
        prevent_initial_call=True,
    )
    def toggle_event_modal(open_clicks, cancel_clicks, save_clicks, is_open,
                           title, date_str, category, severity, description):
        triggered = ctx.triggered_id
        if triggered == "m14-add-event-btn":
            return True
        if triggered == "m14-evt-cancel-btn":
            return False
        if triggered == "m14-evt-save-btn":
            if title and date_str:
                try:
                    from collectors.news_collector import NewsCollector
                    nc = NewsCollector.__new__(NewsCollector)
                    evt_date = datetime.strptime(date_str, "%Y-%m-%d")
                    nc.add_manual_event(
                        title=title,
                        date=evt_date,
                        category=category or "macro",
                        severity=int(severity or 3),
                        description=description or "",
                    )
                except Exception as exc:
                    logger.error("save event: %s", exc)
            return False
        return is_open

    # ── Tab 4: Crisis historicas ───────────────────────────────────────────────

    @app.callback(
        Output("m14-crisis-chart", "children"),
        Input("m14-crisis-btn", "n_clicks"),
        Input("m14-crisis-indicator", "value"),
        Input("m14-crisis-normalize", "value"),
        prevent_initial_call=False,
    )
    def render_crisis_chart(n_clicks, indicator_key, normalize):
        crises = _load_crises()
        if not crises:
            return dbc.Alert("No se encontraron datos de crisis historicas.", color="warning")

        indicator_key = indicator_key or "sp500"
        normalize = normalize or "indexed"

        ind_labels_raw = {}
        try:
            ind_labels_raw = json.loads(CRISES_FILE.read_text(encoding="utf-8")).get("indicator_labels", {})
        except Exception:
            pass
        ind_display = ind_labels_raw.get(indicator_key, indicator_key)

        fig = go.Figure()

        for crisis in crises:
            data_points = crisis.get(indicator_key, [])
            if not data_points:
                continue

            months = [p["m"] for p in data_points]
            values = [p["v"] for p in data_points]

            if normalize == "indexed" and values:
                idx0 = next((i for i, p in enumerate(data_points) if p["m"] == 0), None)
                base = values[idx0] if idx0 is not None and values[idx0] else values[0]
                if base and base != 0:
                    values = [v / base * 100 for v in values]

            fig.add_trace(go.Scatter(
                x=months,
                y=values,
                mode="lines+markers",
                name=crisis["name"],
                line=dict(color=crisis["color"], width=2),
                marker=dict(size=5),
                fill="tozeroy",
                fillcolor=crisis["color_light"],
                hovertemplate=f"<b>{crisis['name']}</b><br>Mes: %{{x}}<br>Valor: %{{y:.2f}}<extra></extra>",
            ))

        # ── Traza ACTUAL desde la BD ──────────────────────────────────────────
        series_id = CRISIS_INDICATOR_DB_MAP.get(indicator_key)
        current_status_text = ""
        if series_id:
            try:
                now = datetime.utcnow()
                date_from = now - timedelta(days=36 * 30)
                df_live = get_series_between(series_id, date_from, now)
                if not df_live.empty:
                    df_live["timestamp"] = df_live["timestamp"].apply(
                        lambda t: t if isinstance(t, datetime) else datetime.fromisoformat(str(t))
                    )
                    # Agrupar por mes y calcular media mensual
                    df_live["month_key"] = df_live["timestamp"].apply(
                        lambda t: (t.year, t.month)
                    )
                    monthly = (
                        df_live.groupby("month_key")["value"]
                        .mean()
                        .reset_index()
                        .sort_values("month_key")
                    )
                    cur_year, cur_month = now.year, now.month
                    def _month_offset(mk):
                        return (mk[0] - cur_year) * 12 + (mk[1] - cur_month)
                    monthly["m_offset"] = monthly["month_key"].apply(_month_offset)
                    live_months = monthly["m_offset"].tolist()
                    live_values = monthly["value"].tolist()

                    if normalize == "indexed" and live_values:
                        # Normalizar respecto al valor del mes más reciente (m=0)
                        base_live = live_values[-1]
                        if base_live and base_live != 0:
                            live_values = [v / base_live * 100 for v in live_values]

                    latest_val = monthly["value"].iloc[-1]
                    current_status_text = f"Valor actual: {latest_val:,.2f}"

                    fig.add_trace(go.Scatter(
                        x=live_months,
                        y=live_values,
                        mode="lines+markers",
                        name="▶ SITUACIÓN ACTUAL",
                        line=dict(color="#ffffff", width=3, dash="solid"),
                        marker=dict(size=6, color="#ffffff"),
                        hovertemplate=f"<b>SITUACIÓN ACTUAL</b><br>Mes: %{{x}}<br>Valor: %{{y:.2f}}<extra></extra>",
                    ))
            except Exception as exc:
                logger.debug("render_crisis_chart live data: %s", exc)

        # Línea vertical en mes 0 (= hoy para ACTUAL / evento para crisis)
        fig.add_vline(x=0, line=dict(color="#666", dash="dot", width=1))

        y_title = "Valor indexado (evento = 100)" if normalize == "indexed" else "Valor absoluto"

        subtitle = "Eje X: meses desde el evento (crisis) / meses hasta hoy (actual)"
        fig.update_layout(
            **_plotly_dark_layout(
                f"{ind_display} — Comparativa con crisis históricas",
                height=420,
            ),
        )
        fig.update_xaxes(title=subtitle, gridcolor="#2a2a2a")
        fig.update_yaxes(title=y_title, gridcolor="#2a2a2a")

        children = [dcc.Graph(figure=fig, config={"displayModeBar": "hover"})]
        if current_status_text:
            children.append(
                html.Div(
                    current_status_text,
                    style={
                        "fontSize": "0.75rem",
                        "color": "#aaa",
                        "textAlign": "right",
                        "marginTop": "4px",
                    },
                )
            )
        return html.Div(children)

    # ── Tab 5: Guardar escenario ───────────────────────────────────────────────

    @app.callback(
        Output("m14-sc-feedback", "children"),
        Input("m14-sc-save-btn", "n_clicks"),
        State("m14-sc-title", "value"),
        State("m14-sc-desc", "value"),
        State("m14-sc-prob", "value"),
        State("m14-sc-target-date", "date"),
        State("m14-sc-conditions", "value"),
        prevent_initial_call=True,
    )
    def save_scenario(n_clicks, title, desc, prob, target_date, conditions):
        if not n_clicks:
            return no_update
        if not title or not title.strip():
            return dbc.Alert("El titulo es obligatorio.", color="warning",
                             dismissable=True, style={"fontSize": "0.75rem"})
        ok = _save_scenario(
            title=title.strip(),
            description=(desc or "").strip(),
            probability=float(prob) if prob is not None else 50.0,
            target_date=target_date,
            conditions=(conditions or "").strip(),
        )
        if ok:
            return dbc.Alert("Escenario registrado correctamente. Recarga la pagina para verlo.",
                             color="success", dismissable=True, style={"fontSize": "0.75rem"})
        return dbc.Alert("Error al guardar el escenario.", color="danger",
                         dismissable=True, style={"fontSize": "0.75rem"})


