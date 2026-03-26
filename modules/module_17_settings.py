"""
Módulo 17 — Configuración y Alertas.

Tabs:
  1. Gestión de Alertas        — tabla AlertConfig, nueva alerta, historial
  2. Widgets Favoritos         — checkboxes por módulo, máx. 20, guardados en UserPreferences
  3. Fuentes de Datos          — estado, botón actualizar, log, uso NewsAPI
  4. Exportación de Datos      — CSV / JSON snapshot
  5. Notas y Anotaciones       — notas libres por indicador/fecha (UserNotes)

Prefijo IDs: 'm17-'
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import dash_bootstrap_components as dbc
import pandas as pd
from dash import ALL, Input, Output, State, ctx, dcc, html, no_update

from config import COLORS, DB_PATH
from modules.data_helpers import get_all_indicator_ids

# ── Estilos de tabs (igual que módulo 05) ─────────────────────────────────────

_TAB_STYLE = {
    "backgroundColor": "transparent",
    "color": COLORS["text_muted"],
    "borderBottom": "none",
    "borderTop": "none",
    "padding": "8px 20px",
    "fontSize": "0.82rem",
    "fontWeight": "500",
}
_TAB_SELECTED_STYLE = {
    **_TAB_STYLE,
    "color": COLORS["text"],
    "borderBottom": f"2px solid {COLORS['accent']}",
    "fontWeight": "600",
}
_TABS_STYLE = {
    "borderBottom": f"1px solid {COLORS['border']}",
    "backgroundColor": COLORS["card_bg"],
}

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"

# ── Colores de severidad ───────────────────────────────────────────────────────

SEV_COLOR = {"critical": COLORS["red"], "warning": COLORS["yellow"], "info": COLORS["accent"]}
SEV_BADGE = {"critical": "danger", "warning": "warning", "info": "info"}

# ── Mapeo de indicadores por módulo (Tab 2 Favoritos) ─────────────────────────

INDICATOR_MODULES = {
    "Mercados": [
        ("S&P 500",         "yf_sp500_close"),
        ("IBEX 35",         "yf_ibex35_close"),
        ("DAX",             "yf_dax_close"),
        ("FTSE 100",        "yf_ftse100_close"),
        ("Nikkei 225",      "yf_nikkei_close"),
        ("VIX (Volatilidad)","yf_vix_close"),
        ("Oro (GC=F)",      "yf_gc_close"),
        ("Petróleo Brent",  "yf_bz_close"),
        ("DXY (Dólar)",     "yf_dxy_close"),
        ("EUR/USD",         "yf_eurusd_close"),
        ("Bitcoin USD",     "cg_btc_price_usd"),
        ("Ethereum USD",    "cg_eth_price_usd"),
    ],
    "Macro EE.UU.": [
        ("CPI YoY USA",         "fred_cpi_yoy_us"),
        ("Fed Funds Rate",      "fred_fed_funds_us"),
        ("Tasa Desempleo USA",  "fred_unemployment_us"),
        ("Spread 10y-2y",       "fred_spread_10y2y_us"),
        ("STLFSI",              "fred_stlfsi_us"),
        ("GPR Global",          "fred_gpr_global"),
    ],
    "Europa": [
        ("Tipo Depósito BCE",   "ecb_deposit_rate_ea"),
        ("EURIBOR 3M",          "ecb_euribor_3m_ea"),
        ("HICP Eurozona",       "estat_hicp_CP00_EA20"),
        ("Desempleo Eurozona",  "estat_unemp_TOTAL_EA20"),
        ("Prima Riesgo España", "ecb_spread_es_de"),
        ("Prima Riesgo Italia", "ecb_spread_it_de"),
    ],
    "Macro Global": [
        ("PIB China",           "wb_gdp_growth_chn"),
        ("PIB India",           "wb_gdp_growth_ind"),
        ("Desempleo Global",    "wb_unemployment_wld"),
    ],
    "Crypto": [
        ("Bitcoin Dominance %", "cg_bitcoin_dominance_pct"),
        ("Fear & Greed",        "cg_fear_greed_value"),
        ("Market Cap Total",    "cg_total_market_cap_usd"),
    ],
}

# ── Metadatos de fuentes de datos ─────────────────────────────────────────────

DATASOURCE_META: Dict[str, Dict] = {
    "FREDCollector":      {"label": "FRED (Fed Reserve)",  "frequency": "Cada 24h",   "max_age_h": 30,  "series": 55},
    "YahooCollector":     {"label": "Yahoo Finance",       "frequency": "Cada 15 min","max_age_h": 1,   "series": 111},
    "WorldBankCollector": {"label": "World Bank",          "frequency": "Semanal",    "max_age_h": 200, "series": 54},
    "EuropeCollector":    {"label": "BCE + Eurostat",      "frequency": "Cada 24h",   "max_age_h": 30,  "series": 30},
    "CoinGeckoCollector": {"label": "CoinGecko",           "frequency": "Cada 30 min","max_age_h": 2,   "series": 22},
    "NewsCollector":      {"label": "Noticias / GPR",      "frequency": "2× al día",  "max_age_h": 14,  "series": 8},
}

# Source → values en time_series.source
_SOURCE_MAP: Dict[str, List[str]] = {
    "FREDCollector":      ["fred", "FRED_GPR"],
    "YahooCollector":     ["yfinance"],
    "WorldBankCollector": ["worldbank"],
    "EuropeCollector":    ["ecb", "ecb_derived", "eurostat"],
    "CoinGeckoCollector": ["coingecko", "alternativeme", "coingecko_derived"],
    "NewsCollector":      ["newsapi", "GDELT"],
}


# ══════════════════════════════════════════════════════════════════════════════
# SettingsDB — UserPreferences + UserNotes
# ══════════════════════════════════════════════════════════════════════════════

class SettingsDB:
    """Gestiona tablas UserPreferences y UserNotes en la BD SQLite del proyecto."""

    def __init__(self):
        self._init_tables()

    def _init_tables(self):
        conn = sqlite3.connect(str(DB_PATH))
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS UserPreferences (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    key        TEXT UNIQUE NOT NULL,
                    value      TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS UserNotes (
                    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                    date                TEXT,
                    indicator_series_id TEXT,
                    note_text           TEXT NOT NULL,
                    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
                );
                CREATE INDEX IF NOT EXISTS ix_usernotes_ind  ON UserNotes(indicator_series_id);
                CREATE INDEX IF NOT EXISTS ix_usernotes_date ON UserNotes(date);
            """)
            conn.commit()
        finally:
            conn.close()

    def get_pref(self, key: str, default=None):
        conn = sqlite3.connect(str(DB_PATH))
        try:
            row = conn.execute("SELECT value FROM UserPreferences WHERE key=?", (key,)).fetchone()
            return json.loads(row[0]) if row else default
        except Exception:
            return default
        finally:
            conn.close()

    def set_pref(self, key: str, value) -> bool:
        conn = sqlite3.connect(str(DB_PATH))
        try:
            conn.execute(
                "INSERT OR REPLACE INTO UserPreferences (key, value, updated_at) VALUES (?, ?, datetime('now'))",
                (key, json.dumps(value)),
            )
            conn.commit()
            return True
        except Exception as e:
            logger.warning("SettingsDB.set_pref error: %s", e)
            return False
        finally:
            conn.close()

    def get_notes(self) -> List[Dict]:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        try:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM UserNotes ORDER BY created_at DESC"
            ).fetchall()]
        except Exception:
            return []
        finally:
            conn.close()

    def add_note(self, note_text: str, indicator_series_id: str = None, date_str: str = None) -> bool:
        conn = sqlite3.connect(str(DB_PATH))
        try:
            conn.execute(
                "INSERT INTO UserNotes (date, indicator_series_id, note_text) VALUES (?, ?, ?)",
                (date_str, indicator_series_id or None, note_text),
            )
            conn.commit()
            return True
        except Exception as e:
            logger.warning("SettingsDB.add_note error: %s", e)
            return False
        finally:
            conn.close()

    def delete_note(self, note_id: int) -> bool:
        conn = sqlite3.connect(str(DB_PATH))
        try:
            conn.execute("DELETE FROM UserNotes WHERE id=?", (note_id,))
            conn.commit()
            return True
        except Exception:
            return False
        finally:
            conn.close()


# Instancia global
_sdb = SettingsDB()


# ══════════════════════════════════════════════════════════════════════════════
# Helpers de AlertConfig / AlertHistory (sin instanciar AlertManager)
# ══════════════════════════════════════════════════════════════════════════════

def _alert_configs() -> List[Dict]:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        try:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM AlertConfig ORDER BY severity, indicator_name"
            ).fetchall()]
        except sqlite3.OperationalError:
            return []
    finally:
        conn.close()


def _alert_history(limit: int = 50) -> List[Dict]:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        try:
            rows = conn.execute(
                """SELECT h.id, h.triggered_at, h.value_at_trigger, h.message,
                          h.is_read, c.indicator_name, c.severity, c.series_id
                   FROM   AlertHistory h
                   JOIN   AlertConfig  c ON c.id = h.alert_config_id
                   ORDER  BY h.triggered_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]
        except sqlite3.OperationalError:
            return []
    finally:
        conn.close()


def _toggle_alert(config_id: int):
    conn = sqlite3.connect(str(DB_PATH))
    try:
        row = conn.execute("SELECT is_active FROM AlertConfig WHERE id=?", (config_id,)).fetchone()
        if row:
            conn.execute("UPDATE AlertConfig SET is_active=? WHERE id=?", (1 - row[0], config_id))
            conn.commit()
    except sqlite3.OperationalError:
        pass
    finally:
        conn.close()


def _set_alert_active(config_id: int, active: bool):
    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.execute("UPDATE AlertConfig SET is_active=? WHERE id=?", (1 if active else 0, config_id))
        conn.commit()
    except sqlite3.OperationalError:
        pass
    finally:
        conn.close()


def _delete_alert(config_id: int):
    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.execute("DELETE FROM AlertHistory WHERE alert_config_id=?", (config_id,))
        conn.execute("DELETE FROM AlertConfig WHERE id=?", (config_id,))
        conn.commit()
    except sqlite3.OperationalError:
        pass
    finally:
        conn.close()


def _add_alert_config(indicator_name: str, series_id: str, condition: str,
                      threshold: float, severity: str, message_template: str) -> bool:
    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.execute(
            """INSERT INTO AlertConfig
               (indicator_name, series_id, condition, threshold,
                severity, message_template, is_active)
               VALUES (?, ?, ?, ?, ?, ?, 1)""",
            (indicator_name, series_id, condition, float(threshold), severity, message_template),
        )
        conn.commit()
        return True
    except Exception as e:
        logger.warning("_add_alert_config error: %s", e)
        return False
    finally:
        conn.close()


def _mark_read(alert_id: int):
    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.execute("UPDATE AlertHistory SET is_read=1 WHERE id=?", (alert_id,))
        conn.commit()
    except sqlite3.OperationalError:
        pass
    finally:
        conn.close()


def _mark_all_read():
    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.execute("UPDATE AlertHistory SET is_read=1 WHERE is_read=0")
        conn.commit()
    except sqlite3.OperationalError:
        pass
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# Helpers de Scheduler (Tab 3)
# ══════════════════════════════════════════════════════════════════════════════

def _scheduler_logs(collector_name: Optional[str] = None, limit: int = 20) -> List[Dict]:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        if collector_name:
            rows = conn.execute(
                "SELECT * FROM SchedulerLog WHERE collector_name=? ORDER BY started_at DESC LIMIT ?",
                (collector_name, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM SchedulerLog ORDER BY started_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


def _source_last_success(collector_name: str) -> Optional[datetime]:
    conn = sqlite3.connect(str(DB_PATH))
    try:
        row = conn.execute(
            """SELECT finished_at FROM SchedulerLog
               WHERE  collector_name=? AND status='success'
               ORDER  BY finished_at DESC LIMIT 1""",
            (collector_name,),
        ).fetchone()
        if row and row[0]:
            return datetime.fromisoformat(row[0])
        return None
    except Exception:
        return None
    finally:
        conn.close()


def _source_status(collector_name: str):
    """Returns (label, color, last_run_str)."""
    meta = DATASOURCE_META.get(collector_name, {})
    max_age_h = meta.get("max_age_h", 24)
    last_ok = _source_last_success(collector_name)

    if last_ok is None:
        conn = sqlite3.connect(str(DB_PATH))
        try:
            row = conn.execute(
                "SELECT status FROM SchedulerLog WHERE collector_name=? ORDER BY started_at DESC LIMIT 1",
                (collector_name,),
            ).fetchone()
            if row and row[0] == "error":
                return "Error", COLORS["red"], "Error"
        except Exception:
            pass
        finally:
            conn.close()
        return "Sin datos", COLORS["text_muted"], "—"

    age_h = (datetime.utcnow() - last_ok).total_seconds() / 3600
    last_str = last_ok.strftime("%Y-%m-%d %H:%M")
    if age_h > max_age_h * 2:
        return "Desactualizado", COLORS["orange"], last_str
    return "OK", COLORS["green"], last_str


def _count_series_in_db(collector_name: str) -> int:
    sources = _SOURCE_MAP.get(collector_name, [collector_name.lower()])
    conn = sqlite3.connect(str(DB_PATH))
    try:
        ph = ",".join(["?" for _ in sources])
        row = conn.execute(
            f"SELECT COUNT(DISTINCT indicator_id) FROM time_series WHERE source IN ({ph})",
            sources,
        ).fetchone()
        return row[0] if row else 0
    except Exception:
        return 0
    finally:
        conn.close()


def _newsapi_usage() -> Dict:
    try:
        fp = DATA_DIR / "newsapi_requests.json"
        if fp.exists():
            data = json.loads(fp.read_text(encoding="utf-8"))
            today = datetime.utcnow().strftime("%Y-%m-%d")
            count = data.get(today, 0)
            return {"today": count, "limit": 100, "remaining": max(0, 100 - count)}
    except Exception:
        pass
    return {"today": 0, "limit": 100, "remaining": 100}


# ══════════════════════════════════════════════════════════════════════════════
# Helpers de estilo
# ══════════════════════════════════════════════════════════════════════════════

_CARD_STYLE = {
    "backgroundColor": COLORS["card_bg"],
    "border": f"1px solid {COLORS['border']}",
    "borderRadius": "6px",
    "padding": "12px 16px",
}

_SECTION_STYLE = {
    "backgroundColor": COLORS["card_bg"],
    "border": f"1px solid {COLORS['border']}",
    "borderRadius": "6px",
    "padding": "16px",
    "marginBottom": "16px",
}

_LABEL_STYLE = {
    "fontSize": "0.65rem",
    "fontWeight": "700",
    "letterSpacing": "0.1em",
    "color": COLORS["text_muted"],
    "textTransform": "uppercase",
    "marginBottom": "2px",
}


def _section(title: str, children, extra_style: dict = None) -> html.Div:
    style = {**_SECTION_STYLE, **(extra_style or {})}
    return html.Div([
        html.Div(title, style=_LABEL_STYLE),
        html.Hr(style={"borderColor": COLORS["border"], "margin": "6px 0 12px 0"}),
        *([children] if not isinstance(children, list) else children),
    ], style=style)


def _mini_card(label: str, value, sub: str = "", color: str = None) -> html.Div:
    return html.Div([
        html.Div(label, className="metric-card-title"),
        html.Div(str(value), className="metric-card-value",
                 style={"fontSize": "1.3rem", "color": color or COLORS["text"]}),
        html.Div(sub, style={"fontSize": "0.7rem", "color": COLORS["text_muted"]}) if sub else html.Div(),
    ], className="metric-card")


def _fmt_dt(s: str) -> str:
    if not s:
        return "—"
    try:
        return datetime.fromisoformat(s).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return s[:16]


# ══════════════════════════════════════════════════════════════════════════════
# Sub-renderers: Tab 1 — Alertas
# ══════════════════════════════════════════════════════════════════════════════

def _render_alerts_table() -> html.Div:
    configs = _alert_configs()
    if not configs:
        return html.Div(
            "No hay alertas configuradas. Pulsa 'Nueva alerta' para crear la primera.",
            style={"color": COLORS["text_muted"], "fontSize": "0.82rem", "padding": "12px"},
        )

    rows = []
    for c in configs:
        sev = c.get("severity", "warning")
        active = bool(c.get("is_active", 1))
        rows.append(html.Tr(
            [
                html.Td(html.Span(c.get("indicator_name", ""), style={"fontWeight": "600"})),
                html.Td(html.Span(c.get("series_id", ""),
                                  style={"fontSize": "0.73rem", "color": COLORS["text_muted"],
                                         "fontFamily": "monospace"})),
                html.Td(html.Span(c.get("condition", ""),
                                  style={"fontSize": "0.8rem"})),
                html.Td(html.Span(f"{c.get('threshold', 0):.2f}",
                                  style={"fontFamily": "monospace"})),
                html.Td(dbc.Badge(sev.upper(), color=SEV_BADGE.get(sev, "secondary"))),
                html.Td(
                    dbc.Switch(
                        id={"type": "m17-toggle-alert", "id": c["id"]},
                        value=active,
                        style={"cursor": "pointer"},
                        persistence=False,
                    )
                ),
                html.Td(
                    dbc.Button(
                        html.I(className="bi bi-trash"),
                        id={"type": "m17-delete-alert", "id": c["id"]},
                        color="danger", size="sm", outline=True,
                        style={"padding": "2px 6px"},
                    )
                ),
            ],
            style={"opacity": "1" if active else "0.5"},
        ))

    return dbc.Table(
        [
            html.Thead(html.Tr([
                html.Th("Indicador"), html.Th("Series ID"), html.Th("Condición"),
                html.Th("Umbral"), html.Th("Severidad"), html.Th("Activa"), html.Th(""),
            ])),
            html.Tbody(rows),
        ],
        dark=True, striped=True, hover=True, size="sm",
        style={"fontSize": "0.82rem", "marginBottom": "0"},
    )


def _render_history_table() -> html.Div:
    history = _alert_history(50)
    if not history:
        return html.Div(
            "No hay historial de alertas disparadas.",
            style={"color": COLORS["text_muted"], "fontSize": "0.82rem", "padding": "12px"},
        )

    rows = []
    for h in history:
        sev = h.get("severity", "warning")
        is_read = bool(h.get("is_read", 0))
        rows.append(html.Tr(
            [
                html.Td(_fmt_dt(h.get("triggered_at", "")),
                        style={"fontSize": "0.73rem", "color": COLORS["text_muted"], "whiteSpace": "nowrap"}),
                html.Td(h.get("indicator_name", ""), style={"fontSize": "0.8rem"}),
                html.Td(dbc.Badge(sev.upper(), color=SEV_BADGE.get(sev, "secondary"))),
                html.Td(h.get("message", ""), style={"fontSize": "0.78rem"}),
                html.Td(
                    dbc.Badge("LEÍDA", color="secondary", pill=True)
                    if is_read else
                    dbc.Button(
                        "Leída",
                        id={"type": "m17-mark-read", "id": h["id"]},
                        color="secondary", size="sm", outline=True,
                        style={"fontSize": "0.7rem", "padding": "2px 8px"},
                    )
                ),
            ],
            style={"opacity": "0.55" if is_read else "1"},
        ))

    return dbc.Table(
        [
            html.Thead(html.Tr([
                html.Th("Fecha"), html.Th("Indicador"), html.Th("Severidad"),
                html.Th("Mensaje"), html.Th(""),
            ])),
            html.Tbody(rows),
        ],
        dark=True, striped=True, hover=True, size="sm",
        style={"fontSize": "0.82rem", "marginBottom": "0"},
    )


def _render_tab_alerts() -> html.Div:
    configs = _alert_configs()
    n_active = sum(1 for c in configs if c.get("is_active", 1))

    return html.Div([
        # Stats
        dbc.Row([
            dbc.Col(_mini_card("ALERTAS ACTIVAS", n_active, color=COLORS["green"]), width=3),
            dbc.Col(_mini_card("TOTAL ALERTAS", len(configs)), width=3),
            dbc.Col(_mini_card("HISTORIAL (últimas 50)", len(_alert_history(50))), width=3),
        ], className="g-3 mb-4"),

        # Config table
        _section("ALERTAS CONFIGURADAS", [
            dbc.Row([
                dbc.Col(
                    dbc.Button(
                        [html.I(className="bi bi-plus-circle me-1"), "Nueva alerta"],
                        id="m17-btn-new-alert",
                        color="primary", size="sm",
                    ),
                    width="auto",
                ),
            ], className="mb-3"),
            html.Div(id="m17-alerts-config-content", children=_render_alerts_table()),
        ]),

        # History
        _section("HISTORIAL DE ALERTAS DISPARADAS", [
            dbc.Row([
                dbc.Col(
                    dbc.Button(
                        "Marcar todas como leídas",
                        id="m17-btn-read-all",
                        color="secondary", size="sm", outline=True,
                    ),
                    width="auto",
                ),
            ], className="mb-3"),
            html.Div(id="m17-alerts-history-content", children=_render_history_table()),
        ]),

        html.Div(id="m17-alerts-feedback", style={"marginTop": "8px"}),
    ])


# ══════════════════════════════════════════════════════════════════════════════
# Sub-renderers: Tab 2 — Favoritos
# ══════════════════════════════════════════════════════════════════════════════

def _render_tab_favorites() -> html.Div:
    current = _sdb.get_pref("favorites", [])

    # Build checklist sections for known indicators
    sections_left = []
    for mod_name, indicators in INDICATOR_MODULES.items():
        opts = [{"label": f"  {lbl}", "value": sid} for lbl, sid in indicators]
        vals = [sid for _, sid in indicators if sid in current]
        sections_left.append(html.Div([
            html.Div(mod_name, style={**_LABEL_STYLE, "marginBottom": "6px"}),
            dcc.Checklist(
                id={"type": "m17-fav-check", "module": mod_name},
                options=opts,
                value=vals,
                inputStyle={"marginRight": "6px", "accentColor": COLORS["accent"]},
                labelStyle={"display": "block", "padding": "2px 0",
                            "fontSize": "0.83rem", "color": COLORS["text"]},
            ),
            html.Hr(style={"borderColor": COLORS["border"], "margin": "8px 0"}),
        ]))

    # Also show DB indicators not in the static list
    all_ids_db = get_all_indicator_ids()
    known_sids = {sid for inds in INDICATOR_MODULES.values() for _, sid in inds}
    other_ids = [i for i in all_ids_db if i["indicator_id"] not in known_sids]
    if other_ids:
        other_opts = [
            {"label": f"  {i['indicator_id']}", "value": i["indicator_id"]}
            for i in other_ids[:60]
        ]
        other_vals = [i["indicator_id"] for i in other_ids if i["indicator_id"] in current]
        sections_left.append(html.Div([
            html.Div("OTROS (BD)", style={**_LABEL_STYLE, "marginBottom": "6px"}),
            dcc.Checklist(
                id={"type": "m17-fav-check", "module": "_other"},
                options=other_opts,
                value=other_vals,
                inputStyle={"marginRight": "6px", "accentColor": COLORS["accent"]},
                labelStyle={"display": "block", "padding": "2px 0",
                            "fontSize": "0.78rem", "color": COLORS["text_muted"],
                            "fontFamily": "monospace"},
            ),
        ]))

    # Current favorites panel (right column)
    fav_items = [
        html.Div([
            html.I(className="bi bi-star-fill me-2",
                   style={"color": COLORS["yellow"], "fontSize": "0.75rem"}),
            html.Span(sid, style={"fontSize": "0.8rem", "fontFamily": "monospace",
                                  "color": COLORS["accent"]}),
        ], style={"padding": "4px 0", "borderBottom": f"1px solid {COLORS['border']}"})
        for sid in current
    ] or [html.Div("Sin favoritos seleccionados",
                   style={"color": COLORS["text_muted"], "fontSize": "0.82rem"})]

    return html.Div([
        dbc.Row([
            dbc.Col(
                _mini_card(
                    "FAVORITOS SELECCIONADOS",
                    f"{len(current)} / 20",
                    "Máximo 20 indicadores",
                    color=COLORS["green"] if len(current) <= 20 else COLORS["red"],
                ),
                width=4,
            ),
        ], className="g-3 mb-3"),

        dbc.Alert(
            [html.I(className="bi bi-info-circle me-2"),
             "Los indicadores marcados aparecerán en un panel personalizado en la parte superior del Módulo 1. "
             "Máximo 20 indicadores."],
            color="info", className="mb-3", style={"fontSize": "0.82rem"},
        ),

        dbc.Row([
            dbc.Col(
                _section("INDICADORES DISPONIBLES", sections_left),
                width=8,
            ),
            dbc.Col(
                _section("MIS FAVORITOS", fav_items),
                width=4,
            ),
        ]),

        dbc.Row([
            dbc.Col(
                dbc.Button(
                    [html.I(className="bi bi-save me-1"), "Guardar favoritos"],
                    id="m17-btn-save-favorites",
                    color="success", size="sm",
                ),
                width="auto",
            ),
        ], className="mt-2"),

        html.Div(id="m17-favorites-feedback", style={"marginTop": "8px"}),
    ])


# ══════════════════════════════════════════════════════════════════════════════
# Sub-renderers: Tab 3 — Fuentes de Datos
# ══════════════════════════════════════════════════════════════════════════════

def _render_source_log(collector_name: Optional[str]) -> html.Div:
    if collector_name is None:
        return html.Div("Selecciona una fuente para ver su log de ejecuciones.",
                        style={"color": COLORS["text_muted"], "fontSize": "0.82rem"})

    logs = _scheduler_logs(collector_name, 20)
    if not logs:
        return html.Div(f"Sin log para {collector_name}.",
                        style={"color": COLORS["text_muted"], "fontSize": "0.82rem"})

    rows = []
    for log in logs:
        status = log.get("status", "?")
        sc = COLORS["green"] if status == "success" else (COLORS["red"] if status == "error" else COLORS["yellow"])
        dur = log.get("duration_seconds")
        dur_str = f"{dur:.1f}s" if dur else "—"
        err = log.get("error_message") or ""
        rows.append(html.Tr([
            html.Td(_fmt_dt(log.get("started_at", "")),
                    style={"fontSize": "0.73rem", "color": COLORS["text_muted"], "whiteSpace": "nowrap"}),
            html.Td(html.Span(status.upper(), style={"color": sc, "fontWeight": "700", "fontSize": "0.75rem"})),
            html.Td(log.get("job_type", ""), style={"fontSize": "0.75rem"}),
            html.Td(str(log.get("records_updated", 0)),
                    style={"fontSize": "0.75rem", "fontFamily": "monospace"}),
            html.Td(dur_str, style={"fontSize": "0.75rem"}),
            html.Td((err[:60] + "…") if len(err) > 60 else err,
                    style={"fontSize": "0.72rem", "color": COLORS["red"]}),
        ]))

    return dbc.Table(
        [
            html.Thead(html.Tr([
                html.Th("Inicio"), html.Th("Estado"), html.Th("Tipo"),
                html.Th("Registros"), html.Th("Duración"), html.Th("Error"),
            ])),
            html.Tbody(rows),
        ],
        dark=True, striped=True, size="sm",
        style={"fontSize": "0.78rem", "marginBottom": "0"},
    )


def _render_tab_sources() -> html.Div:
    # Sources status table
    rows = []
    for key, meta in DATASOURCE_META.items():
        status_lbl, status_color, last_run = _source_status(key)
        n_db = _count_series_in_db(key)
        rows.append(html.Tr([
            html.Td(html.Span(meta["label"], style={"fontWeight": "600", "fontSize": "0.85rem"})),
            html.Td(last_run, style={"fontSize": "0.78rem", "color": COLORS["text_muted"]}),
            html.Td(html.Span(status_lbl, style={"color": status_color, "fontWeight": "700", "fontSize": "0.82rem"})),
            html.Td(meta["frequency"], style={"fontSize": "0.78rem"}),
            html.Td(str(n_db), style={"fontSize": "0.78rem", "fontFamily": "monospace"}),
            html.Td(
                dbc.Button(
                    [html.I(className="bi bi-arrow-clockwise me-1"), "Actualizar ahora"],
                    id={"type": "m17-run-source", "collector": key},
                    color="primary", size="sm", outline=True,
                    style={"fontSize": "0.75rem"},
                )
            ),
        ]))

    sources_tbl = dbc.Table(
        [
            html.Thead(html.Tr([
                html.Th("Fuente"), html.Th("Última actualización"),
                html.Th("Estado"), html.Th("Frecuencia"), html.Th("Series en BD"), html.Th(""),
            ])),
            html.Tbody(rows),
        ],
        dark=True, striped=True, hover=True, size="sm",
        style={"fontSize": "0.82rem", "marginBottom": "0"},
    )

    # NewsAPI
    usage = _newsapi_usage()
    pct = (usage["today"] / usage["limit"]) * 100
    bar_color = "success" if pct < 70 else ("warning" if pct < 90 else "danger")

    source_options = [{"label": m["label"], "value": k} for k, m in DATASOURCE_META.items()]

    return html.Div([
        _section("ESTADO DE FUENTES DE DATOS", sources_tbl),

        _section("LOG DE EJECUCIONES (últimas 20)", [
            dbc.Row([
                dbc.Col(
                    dcc.Dropdown(
                        id="m17-log-selector",
                        options=source_options,
                        placeholder="Selecciona una fuente...",
                        style={"fontSize": "0.85rem"},
                    ),
                    width=5,
                ),
            ], className="mb-3"),
            html.Div(id="m17-source-log-content", children=_render_source_log(None)),
        ]),

        _section("CONSUMO NEWSAPI HOY", [
            dbc.Row([
                dbc.Col([
                    html.Div(
                        f"Peticiones hoy: {usage['today']} / {usage['limit']}  ·  "
                        f"Restantes: {usage['remaining']}",
                        style={"fontSize": "0.85rem", "marginBottom": "8px"},
                    ),
                    dbc.Progress(
                        value=pct,
                        color=bar_color,
                        style={"height": "8px"},
                    ),
                ], width=6),
            ]),
        ]),

        html.Div(id="m17-sources-feedback", style={"marginTop": "8px"}),
    ])


# ══════════════════════════════════════════════════════════════════════════════
# Sub-renderers: Tab 4 — Exportación
# ══════════════════════════════════════════════════════════════════════════════

def _render_tab_export() -> html.Div:
    all_ids = get_all_indicator_ids()
    ind_opts = [{"label": i["indicator_id"], "value": i["indicator_id"]} for i in all_ids]

    today = datetime.utcnow().strftime("%Y-%m-%d")
    one_year_ago = (datetime.utcnow() - timedelta(days=365)).strftime("%Y-%m-%d")

    return html.Div([
        _section("SELECTOR DE DATOS", [
            dbc.Row([
                dbc.Col([
                    html.Label("Indicadores", style={"fontSize": "0.8rem", "color": COLORS["text_muted"]}),
                    dcc.Dropdown(
                        id="m17-export-indicator",
                        options=ind_opts,
                        multi=True,
                        placeholder="Seleccionar indicadores (vacío = todos)...",
                        style={"fontSize": "0.82rem"},
                    ),
                ], width=6),
                dbc.Col([
                    html.Label("Rango de fechas", style={"fontSize": "0.8rem", "color": COLORS["text_muted"]}),
                    dcc.DatePickerRange(
                        id="m17-export-dates",
                        start_date=one_year_ago,
                        end_date=today,
                        display_format="YYYY-MM-DD",
                        style={"width": "100%"},
                    ),
                ], width=6),
            ], className="g-3 mb-4"),

            dbc.Row([
                dbc.Col(
                    dbc.Button(
                        [html.I(className="bi bi-filetype-csv me-2"), "Exportar a CSV"],
                        id="m17-btn-export-csv",
                        color="success", size="sm",
                    ),
                    width="auto",
                ),
                dbc.Col(
                    dbc.Button(
                        [html.I(className="bi bi-filetype-json me-2"), "Snapshot actual a JSON"],
                        id="m17-btn-export-json",
                        color="info", size="sm",
                    ),
                    width="auto",
                ),
            ], className="g-2 mb-3"),

            html.Div(id="m17-export-feedback"),
        ]),

        dbc.Alert(
            [html.I(className="bi bi-info-circle me-2"),
             html.Strong("CSV:"), " descarga los valores históricos de los indicadores seleccionados "
             "en el rango de fechas elegido.  ",
             html.Strong("JSON:"), " exporta el snapshot actual (último valor de cada indicador)."],
            color="secondary",
            style={"fontSize": "0.8rem"},
        ),
    ])


# ══════════════════════════════════════════════════════════════════════════════
# Sub-renderers: Tab 5 — Notas
# ══════════════════════════════════════════════════════════════════════════════

def _render_notes_list() -> html.Div:
    notes = _sdb.get_notes()
    if not notes:
        return html.Div("No hay notas guardadas.",
                        style={"color": COLORS["text_muted"], "fontSize": "0.82rem", "padding": "8px"})

    items = []
    for note in notes:
        items.append(html.Div([
            dbc.Row([
                dbc.Col([
                    html.Span(_fmt_dt(note.get("created_at", "")),
                              style={"fontSize": "0.72rem", "color": COLORS["text_muted"]}),
                    html.Span(" · ", style={"color": COLORS["border_mid"]}),
                    html.Span(
                        note.get("indicator_series_id") or "Global",
                        style={"fontSize": "0.72rem", "color": COLORS["accent"], "fontFamily": "monospace"},
                    ),
                    html.Span(" · ", style={"color": COLORS["border_mid"]}),
                    html.Span(note.get("date") or "",
                              style={"fontSize": "0.72rem", "color": COLORS["text_muted"]}),
                ], width=10),
                dbc.Col(
                    dbc.Button(
                        html.I(className="bi bi-trash"),
                        id={"type": "m17-delete-note", "id": note["id"]},
                        color="danger", size="sm", outline=True,
                        style={"padding": "2px 6px"},
                    ),
                    width=2, className="text-end",
                ),
            ], align="center"),
            html.P(
                note.get("note_text", ""),
                style={"fontSize": "0.85rem", "margin": "4px 0 0 0", "color": COLORS["text"]},
            ),
        ], style={
            "padding": "10px 12px",
            "borderBottom": f"1px solid {COLORS['border']}",
            "backgroundColor": COLORS["card_bg"],
            "marginBottom": "4px",
            "borderRadius": "4px",
        }))

    return html.Div(items)


def _render_tab_notes() -> html.Div:
    all_ids = get_all_indicator_ids()
    ind_opts = [{"label": i["indicator_id"], "value": i["indicator_id"]} for i in all_ids]
    today = datetime.utcnow().strftime("%Y-%m-%d")

    return html.Div([
        _section("NUEVA NOTA", [
            dbc.Row([
                dbc.Col([
                    html.Label("Indicador (opcional)",
                               style={"fontSize": "0.8rem", "color": COLORS["text_muted"]}),
                    dcc.Dropdown(
                        id="m17-note-indicator",
                        options=ind_opts,
                        placeholder="Sin asociar a indicador...",
                        clearable=True,
                        style={"fontSize": "0.82rem"},
                    ),
                ], width=5),
                dbc.Col([
                    html.Label("Fecha (opcional)",
                               style={"fontSize": "0.8rem", "color": COLORS["text_muted"]}),
                    dbc.Input(
                        id="m17-note-date",
                        type="date",
                        value=today,
                        size="sm",
                        style={"backgroundColor": COLORS["card_bg"], "color": COLORS["text"],
                               "borderColor": COLORS["border"]},
                    ),
                ], width=3),
            ], className="g-3 mb-3"),
            dbc.Textarea(
                id="m17-note-text",
                placeholder="Escribe tu nota aquí...",
                rows=4,
                style={
                    "fontSize": "0.85rem",
                    "backgroundColor": COLORS["card_bg"],
                    "color": COLORS["text"],
                    "borderColor": COLORS["border"],
                },
            ),
            dbc.Button(
                [html.I(className="bi bi-save me-1"), "Guardar nota"],
                id="m17-btn-save-note",
                color="primary", size="sm",
                className="mt-2",
            ),
            html.Div(id="m17-notes-feedback", className="mt-2"),
        ]),

        _section("NOTAS GUARDADAS", html.Div(id="m17-notes-list", children=_render_notes_list())),
    ])


# ══════════════════════════════════════════════════════════════════════════════
# Modal: Nueva Alerta
# ══════════════════════════════════════════════════════════════════════════════

def _build_new_alert_modal() -> dbc.Modal:
    all_ids = get_all_indicator_ids()
    series_opts = [{"label": i["indicator_id"], "value": i["indicator_id"]} for i in all_ids]

    return dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle("Nueva alerta de umbral")),
        dbc.ModalBody([
            dbc.Row([
                dbc.Col([
                    html.Label("Series ID del indicador *",
                               style={"fontSize": "0.8rem", "color": COLORS["text_muted"]}),
                    dcc.Dropdown(
                        id="m17-modal-series-id",
                        options=series_opts,
                        placeholder="Buscar indicador...",
                        style={"fontSize": "0.85rem"},
                    ),
                ], width=12, className="mb-3"),
            ]),
            dbc.Row([
                dbc.Col([
                    html.Label("Nombre descriptivo *",
                               style={"fontSize": "0.8rem", "color": COLORS["text_muted"]}),
                    dbc.Input(id="m17-modal-name", placeholder="Ej: VIX Volatilidad",
                              type="text", size="sm"),
                ], width=6),
                dbc.Col([
                    html.Label("Condición *",
                               style={"fontSize": "0.8rem", "color": COLORS["text_muted"]}),
                    dcc.Dropdown(
                        id="m17-modal-condition",
                        options=[
                            {"label": "Por encima de (above)", "value": "above"},
                            {"label": "Por debajo de (below)", "value": "below"},
                            {"label": "Cambio % encima (change_pct_above)", "value": "change_pct_above"},
                            {"label": "Cambio % abajo (change_pct_below)", "value": "change_pct_below"},
                        ],
                        value="above",
                        clearable=False,
                        style={"fontSize": "0.85rem"},
                    ),
                ], width=6),
            ], className="mb-3"),
            dbc.Row([
                dbc.Col([
                    html.Label("Umbral numérico *",
                               style={"fontSize": "0.8rem", "color": COLORS["text_muted"]}),
                    dbc.Input(id="m17-modal-threshold", type="number",
                              placeholder="Ej: 30.0", size="sm"),
                ], width=4),
                dbc.Col([
                    html.Label("Severidad",
                               style={"fontSize": "0.8rem", "color": COLORS["text_muted"]}),
                    dcc.Dropdown(
                        id="m17-modal-severity",
                        options=[
                            {"label": "Info", "value": "info"},
                            {"label": "Warning", "value": "warning"},
                            {"label": "Critical", "value": "critical"},
                        ],
                        value="warning",
                        clearable=False,
                        style={"fontSize": "0.85rem"},
                    ),
                ], width=4),
            ], className="mb-3"),
            dbc.Row([
                dbc.Col([
                    html.Label("Mensaje template",
                               style={"fontSize": "0.8rem", "color": COLORS["text_muted"]}),
                    dbc.Input(
                        id="m17-modal-message",
                        placeholder="Ej: Indicador en {value:.1f} — umbral {threshold}",
                        type="text", size="sm",
                    ),
                    html.Div("Usa {value} y {threshold} como placeholders.",
                             style={"fontSize": "0.72rem", "color": COLORS["text_muted"],
                                    "marginTop": "4px"}),
                ], width=12),
            ]),
        ]),
        dbc.ModalFooter([
            dbc.Button("Cancelar", id="m17-btn-cancel-alert", color="secondary", size="sm",
                       className="me-2"),
            dbc.Button("Crear alerta", id="m17-btn-save-alert", color="primary", size="sm"),
        ]),
    ], id="m17-modal-new-alert", is_open=False, size="lg")


# ══════════════════════════════════════════════════════════════════════════════
# Layout principal
# ══════════════════════════════════════════════════════════════════════════════

def render_module_17() -> html.Div:
    """Retorna el layout completo del Módulo 17."""
    _sdb._init_tables()  # garantizar que las tablas existen

    return html.Div([
        # Cabecera del módulo
        html.Div([
            html.Div("⚙️ Configuración y Alertas", className="module-title"),
            html.Div("Gestión de alertas · Favoritos · Fuentes · Exportación · Notas",
                     className="module-subtitle"),
        ], style={"marginBottom": "20px"}),

        # Tabs
        dcc.Tabs(
            id="m17-tabs",
            value="tab-alerts",
            style=_TABS_STYLE,
            children=[
                dcc.Tab(label="⚡ Alertas",  value="tab-alerts",
                        style=_TAB_STYLE, selected_style=_TAB_SELECTED_STYLE),
                dcc.Tab(label="★ Favoritos", value="tab-favorites",
                        style=_TAB_STYLE, selected_style=_TAB_SELECTED_STYLE),
                dcc.Tab(label="🔌 Fuentes",  value="tab-sources",
                        style=_TAB_STYLE, selected_style=_TAB_SELECTED_STYLE),
                dcc.Tab(label="📥 Exportar", value="tab-export",
                        style=_TAB_STYLE, selected_style=_TAB_SELECTED_STYLE),
                dcc.Tab(label="📝 Notas",    value="tab-notes",
                        style=_TAB_STYLE, selected_style=_TAB_SELECTED_STYLE),
            ],
        ),

        # Contenido de la tab activa (rellenado por callback)
        html.Div(id="m17-tab-content", style={"paddingTop": "20px"}),

        # Modal nueva alerta (siempre en el DOM)
        _build_new_alert_modal(),

        # Componentes de descarga (siempre en el DOM)
        dcc.Download(id="m17-dl-csv"),
        dcc.Download(id="m17-dl-json"),

        # Interval de refresco automático (30s)
        dcc.Interval(id="m17-interval", interval=30_000, n_intervals=0),
    ], style={"padding": "20px 24px"})


# ══════════════════════════════════════════════════════════════════════════════
# Callbacks
# ══════════════════════════════════════════════════════════════════════════════

def register_callbacks_module_17(app, scheduler=None):
    """Registra todos los callbacks del Módulo 17."""

    # ── 1. Renderizar tab activa ──────────────────────────────────────────────

    @app.callback(
        Output("m17-tab-content", "children"),
        Input("m17-tabs", "value"),
        Input("m17-interval", "n_intervals"),
    )
    def render_tab(tab, _interval):
        if tab == "tab-alerts":
            return _render_tab_alerts()
        if tab == "tab-favorites":
            return _render_tab_favorites()
        if tab == "tab-sources":
            return _render_tab_sources()
        if tab == "tab-export":
            return _render_tab_export()
        if tab == "tab-notes":
            return _render_tab_notes()
        return html.Div("Tab no encontrada.")

    # ── 2. Abrir / cerrar modal nueva alerta ──────────────────────────────────

    @app.callback(
        Output("m17-modal-new-alert", "is_open"),
        Input("m17-btn-new-alert", "n_clicks"),
        Input("m17-btn-cancel-alert", "n_clicks"),
        State("m17-modal-new-alert", "is_open"),
        prevent_initial_call=True,
    )
    def toggle_modal(open_n, cancel_n, is_open):
        if ctx.triggered_id == "m17-btn-new-alert":
            return True
        return False

    # ── 3. Guardar nueva alerta ────────────────────────────────────────────────

    @app.callback(
        Output("m17-modal-new-alert", "is_open", allow_duplicate=True),
        Output("m17-alerts-config-content", "children", allow_duplicate=True),
        Output("m17-alerts-feedback", "children", allow_duplicate=True),
        Input("m17-btn-save-alert", "n_clicks"),
        State("m17-modal-series-id", "value"),
        State("m17-modal-name", "value"),
        State("m17-modal-condition", "value"),
        State("m17-modal-threshold", "value"),
        State("m17-modal-severity", "value"),
        State("m17-modal-message", "value"),
        prevent_initial_call=True,
    )
    def save_new_alert(n, series_id, name, condition, threshold, severity, message):
        if not n:
            return no_update, no_update, no_update
        if not series_id or threshold is None:
            return (
                True,
                no_update,
                dbc.Alert("Completa al menos el indicador y el umbral.", color="danger",
                          dismissable=True, style={"fontSize": "0.82rem"}),
            )
        tpl = message or f"Alerta: {{value:.2f}} {'>' if condition == 'above' else '<'} {threshold}"
        ok = _add_alert_config(name or series_id, series_id, condition or "above",
                               float(threshold), severity or "warning", tpl)
        if ok:
            return (
                False,
                _render_alerts_table(),
                dbc.Alert("Alerta creada correctamente.", color="success",
                          dismissable=True, style={"fontSize": "0.82rem"}),
            )
        return (
            True,
            no_update,
            dbc.Alert("Error al crear la alerta.", color="danger",
                      dismissable=True, style={"fontSize": "0.82rem"}),
        )

    # ── 4. Toggle alerta (Switch on/off) ──────────────────────────────────────

    @app.callback(
        Output("m17-alerts-config-content", "children", allow_duplicate=True),
        Input({"type": "m17-toggle-alert", "id": ALL}, "value"),
        prevent_initial_call=True,
    )
    def toggle_alert(values):
        triggered = ctx.triggered_id
        if not triggered or not isinstance(triggered, dict):
            return no_update
        config_id = triggered["id"]
        # Buscar el nuevo valor en la lista inputs
        try:
            idx = next(i for i, item in enumerate(ctx.inputs_list[0])
                       if item["id"]["id"] == config_id)
            new_val = values[idx]
        except (StopIteration, IndexError):
            return no_update
        _set_alert_active(config_id, bool(new_val))
        return _render_alerts_table()

    # ── 5. Eliminar alerta ────────────────────────────────────────────────────

    @app.callback(
        Output("m17-alerts-config-content", "children", allow_duplicate=True),
        Input({"type": "m17-delete-alert", "id": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def delete_alert(n_clicks):
        triggered = ctx.triggered_id
        if not triggered or not isinstance(triggered, dict):
            return no_update
        if not any(n for n in (n_clicks or []) if n):
            return no_update
        _delete_alert(triggered["id"])
        return _render_alerts_table()

    # ── 6. Marcar alerta del historial como leída ─────────────────────────────

    @app.callback(
        Output("m17-alerts-history-content", "children", allow_duplicate=True),
        Input({"type": "m17-mark-read", "id": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def mark_read(n_clicks):
        triggered = ctx.triggered_id
        if not triggered or not isinstance(triggered, dict):
            return no_update
        if not any(n for n in (n_clicks or []) if n):
            return no_update
        _mark_read(triggered["id"])
        return _render_history_table()

    # ── 7. Marcar todas las alertas como leídas ───────────────────────────────

    @app.callback(
        Output("m17-alerts-history-content", "children", allow_duplicate=True),
        Input("m17-btn-read-all", "n_clicks"),
        prevent_initial_call=True,
    )
    def mark_all_read(n):
        if not n:
            return no_update
        _mark_all_read()
        return _render_history_table()

    # ── 8. Guardar favoritos ──────────────────────────────────────────────────

    @app.callback(
        Output("m17-favorites-feedback", "children"),
        Input("m17-btn-save-favorites", "n_clicks"),
        State({"type": "m17-fav-check", "module": ALL}, "value"),
        prevent_initial_call=True,
    )
    def save_favorites(n, all_values):
        if not n:
            return no_update
        # Aplanar y deduplicar
        seen: set = set()
        selected = []
        for lst in (all_values or []):
            for sid in (lst or []):
                if sid not in seen:
                    seen.add(sid)
                    selected.append(sid)
        if len(selected) > 20:
            return dbc.Alert(
                f"Máximo 20 favoritos. Tienes {len(selected)} seleccionados.",
                color="warning", dismissable=True, style={"fontSize": "0.82rem"},
            )
        ok = _sdb.set_pref("favorites", selected)
        if ok:
            return dbc.Alert(
                f"{len(selected)} favorito(s) guardado(s) correctamente.",
                color="success", dismissable=True, style={"fontSize": "0.82rem"},
            )
        return dbc.Alert("Error al guardar favoritos.", color="danger",
                         dismissable=True, style={"fontSize": "0.82rem"})

    # ── 9. Selector de log de fuente ──────────────────────────────────────────

    @app.callback(
        Output("m17-source-log-content", "children"),
        Input("m17-log-selector", "value"),
        prevent_initial_call=True,
    )
    def update_source_log(collector):
        return _render_source_log(collector)

    # ── 10. Actualizar fuente ahora ────────────────────────────────────────────

    @app.callback(
        Output("m17-sources-feedback", "children"),
        Input({"type": "m17-run-source", "collector": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def run_source_now(n_clicks):
        triggered = ctx.triggered_id
        if not triggered or not isinstance(triggered, dict):
            return no_update
        if not any(n for n in (n_clicks or []) if n):
            return no_update
        key = triggered["collector"]
        label = DATASOURCE_META.get(key, {}).get("label", key)
        if scheduler is None:
            return dbc.Alert(
                "Scheduler no disponible. Arranca la aplicación con el scheduler activo.",
                color="warning", dismissable=True, style={"fontSize": "0.82rem"},
            )
        try:
            launched = scheduler.run_collector_now(key)
            if launched:
                return dbc.Alert(
                    f"Actualización de '{label}' lanzada en background. "
                    "Recarga la página en unos segundos para ver el nuevo estado.",
                    color="success", dismissable=True, style={"fontSize": "0.82rem"},
                )
            return dbc.Alert(
                f"Colector '{label}' no encontrado en el scheduler.",
                color="warning", dismissable=True, style={"fontSize": "0.82rem"},
            )
        except Exception as e:
            return dbc.Alert(f"Error: {e}", color="danger",
                             dismissable=True, style={"fontSize": "0.82rem"})

    # ── 11. Exportar CSV ──────────────────────────────────────────────────────

    @app.callback(
        Output("m17-dl-csv", "data"),
        Output("m17-export-feedback", "children"),
        Input("m17-btn-export-csv", "n_clicks"),
        State("m17-export-indicator", "value"),
        State("m17-export-dates", "start_date"),
        State("m17-export-dates", "end_date"),
        prevent_initial_call=True,
    )
    def export_csv(n, indicators, start_date, end_date):
        if not n:
            return no_update, no_update
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        try:
            start = start_date or "2000-01-01"
            end = end_date or datetime.utcnow().strftime("%Y-%m-%d")
            if indicators:
                ph = ",".join(["?" for _ in indicators])
                rows = conn.execute(
                    f"SELECT indicator_id, source, timestamp, value, unit "
                    f"FROM time_series "
                    f"WHERE indicator_id IN ({ph}) AND timestamp >= ? AND timestamp <= ? "
                    f"ORDER BY indicator_id, timestamp",
                    indicators + [start, end],
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT indicator_id, source, timestamp, value, unit "
                    "FROM time_series WHERE timestamp >= ? AND timestamp <= ? "
                    "ORDER BY indicator_id, timestamp",
                    [start, end],
                ).fetchall()
        except Exception as e:
            return no_update, dbc.Alert(f"Error al leer datos: {e}", color="danger",
                                        dismissable=True, style={"fontSize": "0.82rem"})
        finally:
            conn.close()

        if not rows:
            return no_update, dbc.Alert(
                "Sin datos para los parámetros seleccionados.",
                color="info", dismissable=True, style={"fontSize": "0.82rem"},
            )

        df = pd.DataFrame([dict(r) for r in rows])
        csv_str = df.to_csv(index=False)
        fname = f"world_monitor_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
        return (
            dcc.send_string(csv_str, fname),
            dbc.Alert(f"{len(df):,} registros exportados a {fname}.",
                      color="success", dismissable=True, style={"fontSize": "0.82rem"}),
        )

    # ── 12. Exportar JSON (snapshot) ──────────────────────────────────────────

    @app.callback(
        Output("m17-dl-json", "data"),
        Output("m17-export-feedback", "children", allow_duplicate=True),
        Input("m17-btn-export-json", "n_clicks"),
        State("m17-export-indicator", "value"),
        prevent_initial_call=True,
    )
    def export_json(n, indicators):
        if not n:
            return no_update, no_update
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        try:
            if indicators:
                ph = ",".join(["?" for _ in indicators])
                rows = conn.execute(
                    f"SELECT indicator_id, source, MAX(timestamp) as timestamp, value, unit "
                    f"FROM time_series WHERE indicator_id IN ({ph}) GROUP BY indicator_id",
                    indicators,
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT indicator_id, source, MAX(timestamp) as timestamp, value, unit "
                    "FROM time_series GROUP BY indicator_id ORDER BY indicator_id"
                ).fetchall()
        except Exception as e:
            return no_update, dbc.Alert(f"Error al leer datos: {e}", color="danger",
                                        dismissable=True, style={"fontSize": "0.82rem"})
        finally:
            conn.close()

        snapshot = {
            "exported_at": datetime.utcnow().isoformat(),
            "n_indicators": len(rows),
            "indicators": [dict(r) for r in rows],
        }
        fname = f"world_monitor_snapshot_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        return (
            dcc.send_string(json.dumps(snapshot, indent=2, default=str), fname),
            dbc.Alert(f"Snapshot de {len(rows):,} indicadores exportado a {fname}.",
                      color="success", dismissable=True, style={"fontSize": "0.82rem"}),
        )

    # ── 13. Guardar nota ──────────────────────────────────────────────────────

    @app.callback(
        Output("m17-notes-list", "children", allow_duplicate=True),
        Output("m17-notes-feedback", "children"),
        Output("m17-note-text", "value"),
        Input("m17-btn-save-note", "n_clicks"),
        State("m17-note-indicator", "value"),
        State("m17-note-date", "value"),
        State("m17-note-text", "value"),
        prevent_initial_call=True,
    )
    def save_note(n, indicator, date_val, text):
        if not n:
            return no_update, no_update, no_update
        if not text or not text.strip():
            return (
                no_update,
                dbc.Alert("El texto de la nota no puede estar vacío.", color="warning",
                          dismissable=True, style={"fontSize": "0.82rem"}),
                no_update,
            )
        ok = _sdb.add_note(text.strip(), indicator, date_val)
        if ok:
            return (
                _render_notes_list(),
                dbc.Alert("Nota guardada.", color="success",
                          dismissable=True, style={"fontSize": "0.82rem"}),
                "",  # limpiar textarea
            )
        return (
            no_update,
            dbc.Alert("Error al guardar la nota.", color="danger",
                      dismissable=True, style={"fontSize": "0.82rem"}),
            no_update,
        )

    # ── 14. Eliminar nota ─────────────────────────────────────────────────────

    @app.callback(
        Output("m17-notes-list", "children", allow_duplicate=True),
        Input({"type": "m17-delete-note", "id": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def delete_note(n_clicks):
        triggered = ctx.triggered_id
        if not triggered or not isinstance(triggered, dict):
            return no_update
        if not any(n for n in (n_clicks or []) if n):
            return no_update
        _sdb.delete_note(triggered["id"])
        return _render_notes_list()
