"""
World Monitor — Punto de entrada principal.
Arranca Dash con tema oscuro, sidebar de navegación y área de contenido.
"""

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, dcc, html
from datetime import datetime

from config import DASH_DEBUG, DASH_HOST, DASH_PORT, MODULES, COLORS

# ── Inicialización de la app ──────────────────────────────────────────────────

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.DARKLY, dbc.icons.BOOTSTRAP],
    suppress_callback_exceptions=True,
    title="World Monitor",
    update_title=None,
)
server = app.server


# ── Sidebar ───────────────────────────────────────────────────────────────────

def build_sidebar():
    nav_links = []
    for mod in MODULES:
        nav_links.append(
            dbc.NavLink(
                mod["label"],
                href=mod["path"],
                active="exact",
                className="sidebar-link",
                style={
                    "fontSize": "0.78rem",
                    "padding": "6px 16px",
                    "color": COLORS["text_muted"],
                    "borderLeft": f"2px solid transparent",
                    "letterSpacing": "0.02em",
                },
            )
        )

    return html.Div(
        [
            # Logo / Título sidebar
            html.Div(
                [
                    html.Span("◈", style={"color": COLORS["accent"], "fontSize": "1.1rem"}),
                    html.Span(
                        " WORLD MONITOR",
                        style={
                            "fontWeight": "700",
                            "fontSize": "0.85rem",
                            "letterSpacing": "0.12em",
                            "color": COLORS["text"],
                        },
                    ),
                ],
                style={
                    "padding": "20px 16px 12px",
                    "borderBottom": f"1px solid {COLORS['border']}",
                    "marginBottom": "8px",
                },
            ),
            # Navegación
            dbc.Nav(
                nav_links,
                vertical=True,
                pills=False,
            ),
        ],
        style={
            "width": "220px",
            "minWidth": "220px",
            "height": "100vh",
            "position": "fixed",
            "top": 0,
            "left": 0,
            "backgroundColor": COLORS["card_bg"],
            "borderRight": f"1px solid {COLORS['border']}",
            "overflowY": "auto",
            "zIndex": 100,
        },
        id="sidebar",
    )


# ── Header ────────────────────────────────────────────────────────────────────

def build_header():
    return html.Div(
        [
            html.Div(
                [
                    html.Span(
                        "WORLD MONITOR",
                        style={
                            "fontWeight": "700",
                            "fontSize": "1.05rem",
                            "letterSpacing": "0.18em",
                            "color": COLORS["text"],
                        },
                    ),
                    html.Span(
                        " · Dashboard Financiero Global",
                        style={
                            "fontSize": "0.8rem",
                            "color": COLORS["text_muted"],
                            "marginLeft": "8px",
                        },
                    ),
                ]
            ),
            html.Div(
                id="header-datetime",
                style={
                    "fontSize": "0.78rem",
                    "color": COLORS["accent"],
                    "fontFamily": "monospace",
                },
            ),
        ],
        style={
            "display": "flex",
            "justifyContent": "space-between",
            "alignItems": "center",
            "padding": "10px 24px",
            "backgroundColor": COLORS["card_bg"],
            "borderBottom": f"1px solid {COLORS['border']}",
            "position": "fixed",
            "top": 0,
            "left": "220px",
            "right": 0,
            "zIndex": 99,
            "height": "46px",
        },
    )


# ── Welcome screen ────────────────────────────────────────────────────────────

welcome_layout = html.Div(
    [
        html.Div(
            [
                html.H1(
                    "◈ WORLD MONITOR",
                    style={
                        "fontWeight": "700",
                        "letterSpacing": "0.2em",
                        "color": COLORS["accent"],
                        "marginBottom": "8px",
                        "fontSize": "2.2rem",
                    },
                ),
                html.P(
                    "Dashboard de monitorización económica y financiera global",
                    style={"color": COLORS["text_muted"], "marginBottom": "40px", "fontSize": "1rem"},
                ),
                # Estado de la base de datos
                dbc.Alert(
                    [
                        html.I(className="bi bi-database-check me-2"),
                        "Base de datos inicializada. Selecciona un módulo en el sidebar para comenzar.",
                    ],
                    color="info",
                    style={"maxWidth": "600px", "fontSize": "0.85rem"},
                ),
                # Grid de módulos
                html.H6(
                    "MÓDULOS DISPONIBLES",
                    style={
                        "color": COLORS["text_muted"],
                        "letterSpacing": "0.12em",
                        "fontSize": "0.72rem",
                        "marginTop": "40px",
                        "marginBottom": "16px",
                    },
                ),
                dbc.Row(
                    [
                        dbc.Col(
                            dbc.Card(
                                dbc.CardBody(
                                    [
                                        html.P(
                                            mod["label"],
                                            style={
                                                "fontSize": "0.75rem",
                                                "color": COLORS["text"],
                                                "marginBottom": 0,
                                            },
                                        )
                                    ]
                                ),
                                style={
                                    "backgroundColor": COLORS["card_bg"],
                                    "border": f"1px solid {COLORS['border']}",
                                    "marginBottom": "8px",
                                    "cursor": "pointer",
                                },
                            ),
                            width=4,
                        )
                        for mod in MODULES
                    ],
                    style={"maxWidth": "820px"},
                ),
            ],
            style={
                "padding": "48px 24px",
                "maxWidth": "860px",
            },
        )
    ]
)


# ── Layout principal ──────────────────────────────────────────────────────────

app.layout = html.Div(
    [
        dcc.Location(id="url", refresh=False),
        dcc.Interval(id="clock-interval", interval=1000, n_intervals=0),   # Reloj cada segundo
        build_sidebar(),
        build_header(),
        # Área de contenido principal
        html.Div(
            id="page-content",
            style={
                "marginLeft": "220px",
                "marginTop": "46px",
                "backgroundColor": COLORS["background"],
                "minHeight": "calc(100vh - 46px)",
                "padding": "0",
            },
        ),
    ],
    style={
        "backgroundColor": COLORS["background"],
        "fontFamily": "'Inter', 'Segoe UI', sans-serif",
        "color": COLORS["text"],
    },
)


# ── Callbacks ─────────────────────────────────────────────────────────────────

@app.callback(Output("header-datetime", "children"), Input("clock-interval", "n_intervals"))
def update_clock(_):
    now = datetime.now()
    return now.strftime("%Y-%m-%d  %H:%M:%S")


@app.callback(Output("page-content", "children"), Input("url", "pathname"))
def render_page(pathname):
    """Routing: carga el módulo correspondiente a la URL."""
    if pathname is None or pathname == "/":
        return welcome_layout

    # Busca el módulo por path
    module_map = {mod["path"]: mod["id"] for mod in MODULES}
    mod_id = module_map.get(pathname)

    if mod_id is None:
        return html.Div(
            [
                html.H3("404 — Módulo no encontrado", style={"color": COLORS["text_muted"]}),
                dcc.Link("← Volver al inicio", href="/"),
            ],
            style={"padding": "48px 24px"},
        )

    # Placeholder para módulos aún no implementados
    mod_label = next((m["label"] for m in MODULES if m["id"] == mod_id), mod_id)
    return html.Div(
        [
            html.H4(
                mod_label,
                style={
                    "color": COLORS["accent"],
                    "letterSpacing": "0.08em",
                    "marginBottom": "24px",
                    "borderBottom": f"1px solid {COLORS['border']}",
                    "paddingBottom": "12px",
                },
            ),
            dbc.Alert(
                [
                    html.I(className="bi bi-tools me-2"),
                    f"Módulo en construcción. Se implementará en una sesión futura.",
                ],
                color="secondary",
                style={"fontSize": "0.85rem", "maxWidth": "480px"},
            ),
        ],
        style={"padding": "32px 24px"},
    )


# ── Arranque ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(
        host=DASH_HOST,
        port=DASH_PORT,
        debug=DASH_DEBUG,
    )
