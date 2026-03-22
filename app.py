"""
World Monitor — Punto de entrada principal.
Layout definitivo: header fijo 56px + sidebar 240px + área de contenido.
Tema visual Bloomberg/terminal financiero.
"""

import atexit
import logging
import sqlite3
from datetime import datetime

import dash
import dash_bootstrap_components as dbc
from dash import ALL, Input, Output, State, ctx, dcc, html, no_update

from config import COLORS, DASH_DEBUG, DASH_HOST, DASH_PORT, MODULE_BY_N, MODULES
from modules.module_01_global_status import register_callbacks_module_1, render_module_1
from modules.module_02_macro import register_callbacks_module_2, render_module_2
from modules.module_03_inflation import register_callbacks_module_3, render_module_3
from modules.module_04_monetary_policy import register_callbacks_module_4, render_module_4
from modules.module_05_markets import register_callbacks_module_5, render_module_5
from modules.module_06_labor import register_callbacks_module_6, render_module_6
from modules.module_07_energy import register_callbacks_module_7, render_module_7
from components.scheduler_status import (
    build_alerts_bar,
    build_scheduler_panel,
    render_alerts_bar,
    render_global_stats,
    render_status_table,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ── Scheduler ─────────────────────────────────────────────────────────────────

scheduler = None

def start_scheduler():
    global scheduler
    try:
        from scheduler.scheduler import DashboardScheduler
        scheduler = DashboardScheduler()
        scheduler.start()
        logger.info("Scheduler iniciado correctamente")
    except Exception as e:
        logger.warning("Scheduler no pudo arrancar: %s", e)
        scheduler = None

def stop_scheduler():
    global scheduler
    if scheduler is not None:
        try:
            scheduler.stop()
        except Exception:
            pass

atexit.register(stop_scheduler)
start_scheduler()


# ── AlertManager ──────────────────────────────────────────────────────────────

alert_manager = None
try:
    from alerts.alert_manager import AlertManager
    alert_manager = AlertManager()
except Exception as e:
    logger.warning("AlertManager no disponible: %s", e)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_db_last_updated() -> str:
    """Devuelve la fecha de la última inserción en time_series."""
    try:
        from config import DB_PATH
        con = sqlite3.connect(str(DB_PATH))
        row = con.execute(
            "SELECT MAX(timestamp) FROM time_series"
        ).fetchone()
        con.close()
        if row and row[0]:
            ts = row[0][:19]  # "2026-03-21 12:34:56"
            return ts.replace("T", " ")
    except Exception:
        pass
    return "—"


def _get_db_record_count() -> int:
    """Cuenta los registros aproximados relevantes para un módulo."""
    # Heurística: número total de registros en time_series
    try:
        from config import DB_PATH
        con = sqlite3.connect(str(DB_PATH))
        n = con.execute("SELECT COUNT(*) FROM time_series").fetchone()[0]
        con.close()
        return n
    except Exception:
        return 0


# ── Sidebar ───────────────────────────────────────────────────────────────────

def build_sidebar():
    sections: dict[str, list] = {}
    for mod in MODULES:
        sec = mod.get("section", "OTROS")
        sections.setdefault(sec, []).append(mod)

    section_order = ["MERCADOS", "MACRO", "RIESGO", "TENDENCIAS", "HERRAMIENTAS"]

    nav_items = []
    for i, sec in enumerate(section_order):
        if sec not in sections:
            continue
        if i > 0:
            nav_items.append(html.Hr(className="sidebar-divider"))
        nav_items.append(html.Div(sec, className="sidebar-section-label"))
        for mod in sections[sec]:
            nav_items.append(
                dbc.NavLink(
                    [
                        html.Span(mod["emoji"], style={"fontSize": "0.9em", "flexShrink": "0"}),
                        html.Span(mod["label"], style={"overflow": "hidden", "textOverflow": "ellipsis"}),
                    ],
                    href=mod["path"],
                    active="exact",
                    className="sidebar-link",
                    id=f"nav-{mod['id']}",
                )
            )

    last_updated = _get_db_last_updated()

    return html.Div(
        [
            # Zona scrolleable con los links
            html.Div(nav_items, className="sidebar-scroll"),
            # Footer fijo
            html.Div(
                [
                    html.Div("World Monitor v0.1.0", style={"marginBottom": "2px"}),
                    html.Div(
                        f"BD: {last_updated}",
                        id="sidebar-db-updated",
                        style={"color": COLORS["text_label"]},
                    ),
                ],
                className="sidebar-footer",
            ),
        ],
        id="sidebar",
    )


# ── Header ────────────────────────────────────────────────────────────────────

def build_header():
    # Semáforo global de riesgo (placeholder)
    risk_semaphore = html.Div(
        [
            html.Div(className="semaphore-dot gray", id="risk-dot"),
            html.Span("Calculando...", id="risk-label",
                      style={"fontSize": "0.7rem", "color": COLORS["text_muted"]}),
        ],
        className="risk-semaphore",
        title="Semáforo global de riesgo",
    )

    # Indicador scheduler
    scheduler_indicator = html.Div(
        [
            html.Div(
                className="pulse-dot" if scheduler is not None else "pulse-dot inactive",
                id="scheduler-dot",
            ),
            html.Span(
                "Scheduler activo" if scheduler is not None else "Sin scheduler",
                id="scheduler-status-label",
                style={"fontSize": "0.7rem", "color": COLORS["text_muted"]},
            ),
        ],
        className="scheduler-indicator",
    )

    # Badge de alertas
    alert_badge = html.Div(
        [
            html.Span("Alertas", style={"fontSize": "0.7rem", "color": COLORS["text_muted"]}),
            html.Span("0", id="alert-count-badge", className="badge-num zero"),
        ],
        className="alert-count-badge",
        title="Alertas activas no leídas",
    )

    return html.Div(
        [
            # Izquierda: logo
            html.Div(
                [
                    html.Span("🌍", style={"fontSize": "1.1rem"}),
                    html.Span("WORLD MONITOR", className="header-logo-text"),
                ],
                className="header-logo",
            ),
            # Centro: reloj
            html.Div(
                id="header-datetime",
                className="header-datetime",
            ),
            # Derecha: semáforo + scheduler + alertas
            html.Div(
                [risk_semaphore, scheduler_indicator, alert_badge],
                className="header-right",
            ),
        ],
        id="app-header",
    )


# ── Layout principal ──────────────────────────────────────────────────────────

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.DARKLY, dbc.icons.BOOTSTRAP],
    suppress_callback_exceptions=True,
    title="World Monitor",
    update_title=None,
)
server = app.server

app.layout = html.Div(
    [
        dcc.Location(id="url", refresh=False),
        dcc.Interval(id="clock-interval",          interval=1_000,  n_intervals=0),
        dcc.Interval(id="header-stats-interval",   interval=30_000, n_intervals=0),

        # Header fijo
        build_header(),

        # Sidebar fijo
        build_sidebar(),

        # Barra de alertas (sticky debajo del header, sólo en zona de contenido)
        html.Div(
            build_alerts_bar(),
            id="alerts-wrapper",
        ),

        # Área de contenido principal
        html.Div(id="page-content"),
    ],
    style={
        "backgroundColor": COLORS["background"],
        "fontFamily": "'Inter', 'Segoe UI', system-ui, sans-serif",
        "color": COLORS["text"],
    },
)


# ── Módulo placeholder ────────────────────────────────────────────────────────

def build_module_placeholder(module_n: int) -> html.Div:
    mod = MODULE_BY_N.get(module_n)
    if mod is None:
        return html.Div(
            html.H4("Módulo no encontrado", style={"color": COLORS["text_muted"]}),
            id="page-content",
            style={"padding": "24px"},
        )

    rec_count = _get_db_record_count()

    return html.Div(
        [
            # Cabecera del módulo
            html.Div(
                [
                    html.Div(
                        f"{mod['emoji']} {mod['label']}",
                        className="module-title",
                    ),
                    html.Div(
                        f"Módulo {module_n:02d} · En construcción — Los datos están cargándose",
                        className="module-subtitle",
                    ),
                    html.Div(
                        [
                            html.Span("🔧 ", style={"fontSize": "0.85rem"}),
                            html.Span(
                                "Módulo pendiente de implementación en sesión futura.",
                                style={"fontSize": "0.75rem"},
                            ),
                        ],
                        className="placeholder-badge",
                    ),
                ]
            ),

            # Stats rápidas
            dbc.Row(
                [
                    dbc.Col(
                        html.Div(
                            [
                                html.Div("REGISTROS EN BD", className="metric-card-title"),
                                html.Div(
                                    f"{rec_count:,}",
                                    className="metric-card-value",
                                    style={"fontSize": "1.8rem"},
                                ),
                            ],
                            className="metric-card",
                        ),
                        width=3,
                    ),
                    dbc.Col(
                        html.Div(
                            [
                                html.Div("MÓDULO", className="metric-card-title"),
                                html.Div(
                                    f"#{module_n:02d}",
                                    className="metric-card-value",
                                    style={"color": COLORS["accent"], "fontSize": "1.8rem"},
                                ),
                            ],
                            className="metric-card",
                        ),
                        width=3,
                    ),
                    dbc.Col(
                        html.Div(
                            [
                                html.Div("ESTADO", className="metric-card-title"),
                                html.Div(
                                    "En construcción",
                                    className="metric-card-value",
                                    style={"color": COLORS["yellow"], "fontSize": "0.9rem", "paddingTop": "6px"},
                                ),
                            ],
                            className="metric-card",
                        ),
                        width=3,
                    ),
                ],
                className="g-3 mb-4",
            ),

            # Panel del scheduler
            html.Div(
                build_scheduler_panel(),
                style={"maxWidth": "900px"},
            ),
        ],
        className="module-placeholder",
    )


# ── Callbacks ─────────────────────────────────────────────────────────────────

@app.callback(
    Output("header-datetime", "children"),
    Input("clock-interval", "n_intervals"),
)
def update_clock(_):
    now = datetime.now()
    days_es = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    months_es = [
        "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
    ]
    day_name = days_es[now.weekday()]
    month_name = months_es[now.month - 1]
    return f"{day_name}, {now.day} {month_name} {now.year} — {now.strftime('%H:%M:%S')} UTC"


@app.callback(
    Output("alert-count-badge", "children"),
    Output("alert-count-badge", "className"),
    Input("header-stats-interval", "n_intervals"),
)
def update_alert_count(_):
    if alert_manager is None:
        return "0", "badge-num zero"
    try:
        alerts = alert_manager.get_active_alerts(hours=24)
        n = len(alerts)
        cls = "badge-num" if n > 0 else "badge-num zero"
        return str(n), cls
    except Exception:
        return "0", "badge-num zero"


@app.callback(
    Output("page-content", "children"),
    Input("url", "pathname"),
)
def render_page(pathname):
    if pathname is None or pathname == "/" or pathname == "":
        # Redirigir al módulo 1
        return dcc.Location(id="redirect", pathname="/module/1", refresh=True)

    if pathname.startswith("/module/"):
        try:
            n = int(pathname.split("/module/")[1])
        except (ValueError, IndexError):
            return html.Div(
                [
                    html.H4("404 — Módulo no encontrado",
                            style={"color": COLORS["text_muted"]}),
                    dcc.Link("← Volver al inicio", href="/module/1"),
                ],
                style={"padding": "48px 24px"},
            )
        if n not in MODULE_BY_N:
            return html.Div(
                [
                    html.H4(f"Módulo {n} no existe",
                            style={"color": COLORS["text_muted"]}),
                    dcc.Link("← Volver al inicio", href="/module/1"),
                ],
                style={"padding": "48px 24px"},
            )
        if n == 1:
            return render_module_1()
        if n == 2:
            return render_module_2()
        if n == 3:
            return render_module_3()
        if n == 4:
            return render_module_4()
        if n == 5:
            return render_module_5()
        if n == 6:
            return render_module_6()
        if n == 7:
            return render_module_7()
        return build_module_placeholder(n)

    # Cualquier otra ruta → 404
    return html.Div(
        [
            html.H4("404 — Página no encontrada",
                    style={"color": COLORS["text_muted"]}),
            dcc.Link("← Ir al dashboard", href="/module/1"),
        ],
        style={"padding": "48px 24px"},
    )


# ── Callback: tabla de estado del scheduler ───────────────────────────────────

@app.callback(
    Output("scheduler-status-table", "children"),
    Output("scheduler-global-stats", "children"),
    Input("scheduler-refresh-interval", "n_intervals"),
    Input({"type": "run-collector-btn", "collector": ALL}, "n_clicks"),
    prevent_initial_call=False,
)
def update_scheduler_panel(_n_intervals, _btn_clicks):
    triggered = ctx.triggered_id
    if (
        triggered is not None
        and isinstance(triggered, dict)
        and triggered.get("type") == "run-collector-btn"
    ):
        collector_key = triggered["collector"]
        if scheduler is not None:
            scheduler.run_collector_now(collector_key)

    if scheduler is None:
        table = dbc.Alert(
            "Scheduler no disponible. Sin actualización automática.",
            color="warning",
            style={"fontSize": "0.82rem"},
        )
        return table, html.Div()

    try:
        status    = scheduler.get_status()
        db_stats  = scheduler.get_db_stats()
        log_stats = scheduler.get_log_stats_24h()
        return render_status_table(status), render_global_stats(status, db_stats, log_stats)
    except Exception as e:
        logger.warning("Error actualizando panel scheduler: %s", e)
        err = dbc.Alert(f"Error: {e}", color="danger", style={"fontSize": "0.82rem"})
        return err, html.Div()


# ── Callback: barra de alertas ────────────────────────────────────────────────

@app.callback(
    Output("alerts-bar-content", "children"),
    Input("alerts-refresh-interval", "n_intervals"),
    Input({"type": "dismiss-alert-btn", "alert_id": ALL}, "n_clicks"),
    prevent_initial_call=False,
)
def update_alerts_bar(n_intervals, dismiss_clicks):
    triggered = ctx.triggered_id
    if (
        triggered is not None
        and isinstance(triggered, dict)
        and triggered.get("type") == "dismiss-alert-btn"
    ):
        alert_id = triggered["alert_id"]
        if alert_manager is not None and alert_id:
            try:
                alert_manager.mark_as_read(int(alert_id))
            except Exception:
                pass

    if alert_manager is None:
        return html.Div()

    try:
        active_alerts = alert_manager.get_active_alerts(hours=24)
        return render_alerts_bar(active_alerts)
    except Exception as e:
        logger.warning("Error actualizando barra de alertas: %s", e)
        return html.Div()


# ── Registro de callbacks de modulos ──────────────────────────────────────────

register_callbacks_module_1(app)
register_callbacks_module_2(app)
register_callbacks_module_3(app)
register_callbacks_module_4(app)
register_callbacks_module_5(app)
register_callbacks_module_6(app)
register_callbacks_module_7(app)


# ── Arranque ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(
        host=DASH_HOST,
        port=DASH_PORT,
        debug=DASH_DEBUG,
    )
