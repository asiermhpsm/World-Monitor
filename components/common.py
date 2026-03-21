"""
Componentes Dash reutilizables para World Monitor.
Importar las funciones de este módulo en los módulos del dashboard.
"""

from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import html

# Mapa de banderas ISO2 → emoji
_FLAG_MAP = {
    "US": "🇺🇸", "GB": "🇬🇧", "DE": "🇩🇪", "FR": "🇫🇷", "ES": "🇪🇸",
    "IT": "🇮🇹", "PT": "🇵🇹", "GR": "🇬🇷", "NL": "🇳🇱", "JP": "🇯🇵",
    "CN": "🇨🇳", "IN": "🇮🇳", "BR": "🇧🇷", "MX": "🇲🇽", "RU": "🇷🇺",
    "CA": "🇨🇦", "AU": "🇦🇺", "CH": "🇨🇭", "SE": "🇸🇪", "NO": "🇳🇴",
    "DK": "🇩🇰", "PL": "🇵🇱", "TR": "🇹🇷", "SA": "🇸🇦", "ZA": "🇿🇦",
    "AR": "🇦🇷", "KR": "🇰🇷",
}


def create_metric_card(
    title: str,
    value: str,
    change: float | None = None,
    change_period: str = "24h",
    unit: str = "",
    color: str | None = None,
) -> html.Div:
    """Card pequeña con indicador numérico y cambio opcional."""
    if change is not None:
        if change > 0:
            arrow, cls = "↑", "positive"
            c = color or "#10b981"
        elif change < 0:
            arrow, cls = "↓", "negative"
            c = color or "#ef4444"
        else:
            arrow, cls = "→", "neutral"
            c = color or "#9ca3af"

        change_el = html.Div(
            [
                html.Span(f"{arrow} {abs(change):+.2f}{unit}", style={"color": c}),
                html.Span(f" {change_period}", style={"color": "#6b7280", "fontSize": "0.68rem"}),
            ],
            className=f"metric-card-change {cls}",
        )
    else:
        change_el = html.Div()

    value_color = color or "#e5e7eb"

    return html.Div(
        [
            html.Div(title, className="metric-card-title"),
            html.Div(
                f"{value}{unit}",
                className="metric-card-value",
                style={"color": value_color} if color else {},
            ),
            change_el,
        ],
        className="metric-card",
    )


def create_section_header(
    title: str,
    subtitle: str | None = None,
    last_updated: str | None = None,
) -> html.Div:
    """Header de sección dentro de un módulo."""
    children = []
    if last_updated:
        children.append(
            html.Span(f"Actualizado: {last_updated}", className="section-header-updated")
        )
    children.append(html.Div(title, className="section-header-title"))
    if subtitle:
        children.append(html.Div(subtitle, className="section-header-subtitle"))

    return html.Div(children, className="section-header")


def create_semaphore(
    level: str = "gray",
    label: str = "",
    size: str = "medium",
) -> html.Div:
    """
    Indicador semáforo visual.
    level: 'green' | 'yellow_green' | 'yellow' | 'orange' | 'red' | 'gray'
    size: 'small' (16px) | 'medium' (24px) | 'large' (40px)
    """
    sizes = {"small": 16, "medium": 24, "large": 40}
    px = sizes.get(size, 24)

    color_map = {
        "green":        "#10b981",
        "yellow_green": "#84cc16",
        "yellow":       "#f59e0b",
        "orange":       "#f97316",
        "red":          "#ef4444",
        "gray":         "#4b5563",
    }
    color = color_map.get(level, "#4b5563")

    dot = html.Div(
        style={
            "width":        f"{px}px",
            "height":       f"{px}px",
            "borderRadius": "50%",
            "backgroundColor": color,
            "boxShadow":    f"0 0 {px // 2}px {color}60",
            "flexShrink":   "0",
        }
    )

    if not label:
        return dot

    return html.Div(
        [dot, html.Span(label, style={"fontSize": "0.78rem", "color": "#9ca3af", "marginLeft": "8px"})],
        style={"display": "flex", "alignItems": "center"},
    )


def create_data_table(
    headers: list[str],
    rows: list[list],
    highlight_column: int | None = None,
) -> html.Div:
    """Tabla de datos estilizada con tema oscuro."""
    th_els = [html.Th(h) for h in headers]

    row_els = []
    for row in rows:
        td_els = []
        for i, cell in enumerate(row):
            style = {}
            if highlight_column is not None and i == highlight_column:
                style = {"color": "#3b82f6", "fontWeight": "600"}
            td_els.append(html.Td(cell, style=style))
        row_els.append(html.Tr(td_els))

    return html.Div(
        html.Table(
            [html.Thead(html.Tr(th_els)), html.Tbody(row_els)],
            className="data-table",
        ),
        style={"overflowX": "auto"},
    )


def create_empty_state(
    message: str = "Sin datos disponibles",
    submessage: str | None = None,
) -> html.Div:
    """Placeholder visual cuando no hay datos."""
    children = [
        html.Div("◌", className="empty-state-icon"),
        html.Div(message, className="empty-state-msg"),
    ]
    if submessage:
        children.append(html.Div(submessage, className="empty-state-sub"))
    return html.Div(children, className="empty-state")


def create_loading_state(message: str = "Cargando datos...") -> html.Div:
    """Spinner de carga."""
    return html.Div(
        [
            dbc.Spinner(size="sm", color="primary"),
            html.Span(message, style={"marginLeft": "10px", "color": "#9ca3af", "fontSize": "0.82rem"}),
        ],
        className="loading-state",
    )


def create_country_flag(country_code: str) -> str:
    """Devuelve el emoji de bandera dado el código ISO2."""
    return _FLAG_MAP.get(country_code.upper(), "🏳")
