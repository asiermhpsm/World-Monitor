"""
Panel de estado del Scheduler para el Módulo 1 del World Monitor.

Muestra una tabla con el estado de cada colector: última ejecución,
resultado, próxima ejecución y botón "Actualizar ahora".
Se refresca automáticamente cada 60 segundos.

Los callbacks se registran en app.py (necesitan acceso a la instancia global
del scheduler). Este módulo solo expone el layout y funciones de renderizado.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

import dash_bootstrap_components as dbc
from dash import dcc, html

from config import COLORS

# ── Constantes de semáforo ────────────────────────────────────────────────────

# Tiempo máximo (horas) antes de considerar el dato desactualizado
FRESHNESS_THRESHOLDS = {
    "YahooCollector":     2,    # frecuente: máx 2h
    "CoinGeckoCollector": 2,    # frecuente: máx 2h
    "FREDCollector":      26,   # diario:    máx 26h
    "EuropeCollector":    26,
    "NewsCollector":      26,
    "WorldBankCollector": 200,  # semanal:   máx ~8 días
}

SEVERITY_COLORS = {
    "critical": "#d50000",
    "warning":  "#ffd600",
    "info":     "#00b4d8",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _format_relative_time(dt: Optional[datetime]) -> str:
    """Convierte un datetime a texto legible ('hace 23 min', 'ayer a las 07:00')."""
    if dt is None:
        return "Nunca"

    # Asegurar que dt sea offset-naive para poder comparar
    if dt.tzinfo is not None:
        dt = dt.replace(tzinfo=None)

    now = datetime.utcnow()
    delta = now - dt

    if delta.total_seconds() < 0:
        return "En unos momentos"

    total_minutes = int(delta.total_seconds() // 60)
    total_hours   = total_minutes // 60
    total_days    = total_hours // 24

    if total_minutes < 1:
        return "Hace menos de 1 min"
    if total_minutes < 60:
        return f"Hace {total_minutes} min"
    if total_hours < 24:
        return f"Hace {total_hours} h"
    if total_days == 1:
        return f"Ayer a las {dt.strftime('%H:%M')}"
    if total_days < 7:
        days_es = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
        return f"El {days_es[dt.weekday()]} a las {dt.strftime('%H:%M')}"
    return dt.strftime("%d/%m/%Y %H:%M")


def _format_next_run(dt: Optional[datetime]) -> str:
    """Formatea la próxima ejecución programada."""
    if dt is None:
        return "—"
    # APScheduler devuelve datetimes con timezone, convertimos a UTC naive
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    now = datetime.utcnow()
    delta = dt - now
    total_minutes = int(delta.total_seconds() // 60)
    if total_minutes < 1:
        return "En unos momentos"
    if total_minutes < 60:
        return f"En {total_minutes} min"
    hours = total_minutes // 60
    if hours < 24:
        return f"En {hours} h ({dt.strftime('%H:%M')} UTC)"
    return dt.strftime("%d/%m %H:%M UTC")


def _status_badge(collector_key: str, col_info: Dict[str, Any]) -> html.Span:
    """Devuelve un badge de semáforo según el estado del colector."""
    last_status = col_info.get("last_status", "never_run")
    last_run    = col_info.get("last_run")

    if last_status == "never_run" or last_run is None:
        color = COLORS.get("text_muted", "#888888")
        label = "Sin datos"
        icon  = "●"
    elif last_status == "error":
        color = COLORS.get("red", "#d50000")
        label = "Error"
        icon  = "●"
    elif last_status == "running":
        color = COLORS.get("accent", "#00b4d8")
        label = "Ejecutando"
        icon  = "◌"
    else:
        # Verificar frescura
        if last_run.tzinfo is not None:
            last_run = last_run.replace(tzinfo=None)
        hours_since = (datetime.utcnow() - last_run).total_seconds() / 3600
        max_hours   = FRESHNESS_THRESHOLDS.get(collector_key, 26)

        if hours_since <= max_hours * 0.75:
            color = COLORS.get("green", "#00c853")
            label = "OK"
            icon  = "●"
        elif hours_since <= max_hours:
            color = COLORS.get("yellow", "#ffd600")
            label = "Atención"
            icon  = "●"
        else:
            color = COLORS.get("orange", "#ff6d00")
            label = "Desactualizado"
            icon  = "●"

    return html.Span(
        [icon, " ", label],
        style={"color": color, "fontWeight": "600", "fontSize": "0.78rem"},
    )


# ── Layout del panel ──────────────────────────────────────────────────────────

def build_scheduler_panel() -> html.Div:
    """
    Retorna el layout estático del panel de scheduler.
    El contenido se rellena por callbacks.
    """
    return html.Div(
        [
            # Intervalo de refresco automático (60 s)
            dcc.Interval(
                id="scheduler-refresh-interval",
                interval=60_000,
                n_intervals=0,
            ),

            # Cabecera del panel
            html.Div(
                [
                    html.H6(
                        "ESTADO DE LAS FUENTES DE DATOS",
                        style={
                            "color":         COLORS["text_muted"],
                            "letterSpacing": "0.1em",
                            "fontSize":      "0.72rem",
                            "margin":        "0",
                        },
                    ),
                    html.Small(
                        "Actualización automática cada 60 s",
                        style={"color": COLORS["text_muted"], "fontSize": "0.65rem"},
                    ),
                ],
                style={
                    "display":        "flex",
                    "justifyContent": "space-between",
                    "alignItems":     "center",
                    "marginBottom":   "10px",
                },
            ),

            # Tabla (se rellena por callback)
            html.Div(id="scheduler-status-table"),

            # Estadísticas globales (se rellenan por callback)
            html.Div(id="scheduler-global-stats", style={"marginTop": "12px"}),
        ],
        style={
            "backgroundColor": COLORS["card_bg"],
            "border":          f"1px solid {COLORS['border']}",
            "borderRadius":    "4px",
            "padding":         "16px",
        },
    )


def render_status_table(scheduler_status: Dict[str, Any]) -> html.Div:
    """
    Renderiza la tabla de estado a partir del dict devuelto por
    DashboardScheduler.get_status().
    """
    collectors = scheduler_status.get("collectors", {})
    if not collectors:
        return dbc.Alert(
            "El scheduler no está disponible o no hay colectores registrados.",
            color="secondary",
            style={"fontSize": "0.82rem"},
        )

    header = html.Thead(
        html.Tr(
            [
                html.Th("Fuente",            style=_th_style()),
                html.Th("Estado",            style=_th_style()),
                html.Th("Última actualiz.",  style=_th_style()),
                html.Th("Próxima ejec.",     style=_th_style()),
                html.Th("Registros",         style={**_th_style(), "textAlign": "right"}),
                html.Th("Acción",            style={**_th_style(), "textAlign": "center"}),
            ]
        ),
        style={"borderBottom": f"1px solid {COLORS['border']}"},
    )

    rows = []
    for key, info in collectors.items():
        is_running = info.get("is_running", False)
        btn_text   = "Actualizando..." if is_running else "Actualizar ahora"
        btn_color  = "secondary" if is_running else "outline-info"

        rows.append(
            html.Tr(
                [
                    html.Td(
                        info.get("label", key),
                        style={**_td_style(), "fontWeight": "500"},
                    ),
                    html.Td(
                        _status_badge(key, info),
                        style=_td_style(),
                    ),
                    html.Td(
                        _format_relative_time(info.get("last_run")),
                        style={**_td_style(), "fontFamily": "monospace", "fontSize": "0.78rem"},
                    ),
                    html.Td(
                        _format_next_run(info.get("next_run")),
                        style={**_td_style(), "fontFamily": "monospace", "fontSize": "0.78rem"},
                    ),
                    html.Td(
                        f"{info.get('last_records', 0):,}",
                        style={**_td_style(), "textAlign": "right", "fontFamily": "monospace"},
                    ),
                    html.Td(
                        dbc.Button(
                            btn_text,
                            id={"type": "run-collector-btn", "collector": key},
                            color=btn_color,
                            size="sm",
                            disabled=is_running,
                            style={"fontSize": "0.72rem", "padding": "2px 8px"},
                        ),
                        style={**_td_style(), "textAlign": "center"},
                    ),
                ],
                style={"borderBottom": f"1px solid {COLORS['border']}20"},
            )
        )

    return dbc.Table(
        [header, html.Tbody(rows)],
        dark=True,
        bordered=False,
        hover=True,
        size="sm",
        style={
            "fontSize":      "0.82rem",
            "color":         COLORS["text"],
            "marginBottom":  "0",
        },
    )


def render_global_stats(
    scheduler_status: Dict[str, Any],
    db_stats:        Dict[str, Any],
    log_stats:       Dict[str, int],
) -> html.Div:
    """Renderiza las estadísticas globales debajo de la tabla."""
    started_at   = scheduler_status.get("started_at")
    is_running   = scheduler_status.get("is_running", False)
    total_jobs   = scheduler_status.get("total_jobs", 0)

    uptime = "—"
    if started_at and is_running:
        delta = datetime.utcnow() - started_at
        h, rem = divmod(int(delta.total_seconds()), 3600)
        m = rem // 60
        uptime = f"{h}h {m}m"

    ok_24h    = log_stats.get("success", 0)
    err_24h   = log_stats.get("error", 0)
    total_rec = db_stats.get("total_records", 0)
    db_mb     = db_stats.get("db_size_mb", 0.0)

    stats_items = [
        ("Base de datos", f"{total_rec:,} registros  ·  {db_mb} MB"),
        ("Uptime scheduler", uptime),
        ("Ejecuciones 24h", f"{ok_24h} exitosas  ·  {err_24h} fallidas"),
        ("Jobs activos", str(total_jobs)),
    ]

    pills = []
    for label, value in stats_items:
        pills.append(
            html.Span(
                [
                    html.Span(label + ": ", style={"color": COLORS["text_muted"]}),
                    html.Span(value, style={"color": COLORS["text"], "fontWeight": "500"}),
                ],
                style={
                    "display":       "inline-block",
                    "marginRight":   "20px",
                    "fontSize":      "0.75rem",
                    "fontFamily":    "monospace",
                },
            )
        )

    scheduler_badge = html.Span(
        "● ACTIVO" if is_running else "○ INACTIVO",
        style={
            "color":       COLORS["green"] if is_running else COLORS["red"],
            "fontSize":    "0.7rem",
            "fontWeight":  "700",
            "float":       "right",
        },
    )

    return html.Div(
        [scheduler_badge] + pills,
        style={
            "borderTop":    f"1px solid {COLORS['border']}",
            "paddingTop":   "10px",
            "marginTop":    "10px",
        },
    )


# ── Estilos de celda ──────────────────────────────────────────────────────────

def _th_style() -> dict:
    return {
        "color":          COLORS["text_muted"],
        "fontSize":       "0.68rem",
        "letterSpacing":  "0.06em",
        "fontWeight":     "600",
        "textTransform":  "uppercase",
        "padding":        "6px 8px",
        "backgroundColor": COLORS["card_bg"],
        "border":         "none",
    }


def _td_style() -> dict:
    return {
        "padding":         "7px 8px",
        "verticalAlign":   "middle",
        "border":          "none",
        "backgroundColor": COLORS["card_bg"],
    }


# ── Barra de alertas ──────────────────────────────────────────────────────────

def build_alerts_bar() -> html.Div:
    """
    Retorna el layout del contenedor de alertas (se rellena por callback).
    Ocupa el ancho completo sobre el contenido y se oculta si no hay alertas.
    """
    return html.Div(
        [
            dcc.Interval(
                id="alerts-refresh-interval",
                interval=60_000,
                n_intervals=0,
            ),
            html.Div(id="alerts-bar-content"),
        ]
    )


def render_alerts_bar(alerts: list) -> html.Div:
    """Renderiza las alertas activas como banners."""
    if not alerts:
        return html.Div()

    items = []
    for alert in alerts[:5]:   # Máximo 5 alertas visibles
        severity = alert.get("severity", "warning")
        color_map = {
            "critical": "danger",
            "warning":  "warning",
            "info":     "info",
        }
        dash_color = color_map.get(severity, "warning")

        items.append(
            dbc.Alert(
                [
                    html.Span(
                        alert.get("message", "Alerta sin mensaje"),
                        style={"fontSize": "0.8rem", "flex": "1"},
                    ),
                    dbc.Button(
                        "×",
                        id={"type": "dismiss-alert-btn", "alert_id": alert.get("id", 0)},
                        color="link",
                        size="sm",
                        style={
                            "color":      "inherit",
                            "fontSize":   "1.1rem",
                            "padding":    "0 6px",
                            "lineHeight": "1",
                        },
                    ),
                ],
                color=dash_color,
                style={
                    "display":      "flex",
                    "alignItems":   "center",
                    "padding":      "6px 12px",
                    "marginBottom": "2px",
                    "fontSize":     "0.8rem",
                    "borderRadius": "0",
                },
                dismissable=False,
            )
        )

    if len(alerts) > 5:
        items.append(
            html.Div(
                f"... y {len(alerts) - 5} alertas más",
                style={
                    "fontSize":      "0.73rem",
                    "color":         COLORS["text_muted"],
                    "textAlign":     "right",
                    "paddingRight":  "12px",
                },
            )
        )

    return html.Div(items)
