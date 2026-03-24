"""
Módulo 13 — Demografía y Tendencias Estructurales
Las fuerzas que moldean la economía durante décadas: población, envejecimiento,
productividad, desigualdad y tendencias disruptivas.
"""

from __future__ import annotations

import json
from pathlib import Path

import dash_bootstrap_components as dbc
import plotly.graph_objs as go
from dash import Input, Output, dcc, html

from components.chart_config import COLORS as C, get_base_layout
from config import COLORS
from modules.data_helpers import get_latest_value, get_series

# ── Constantes ─────────────────────────────────────────────────────────────────

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

_TAB_STYLE = {
    "backgroundColor": "transparent",
    "color": COLORS["text_muted"],
    "border": "none",
    "borderBottom": "2px solid transparent",
    "padding": "10px 18px",
    "fontSize": "0.82rem",
    "fontWeight": "500",
}
_TAB_SELECTED = {
    **_TAB_STYLE,
    "color": COLORS["text"],
    "borderBottom": f"2px solid {COLORS['accent']}",
    "fontWeight": "600",
}
_TABS_CONTAINER = {
    "borderBottom": f"1px solid {COLORS['border']}",
    "backgroundColor": COLORS["card_bg"],
}
_CARD = {
    "backgroundColor": COLORS["card_bg"],
    "border": f"1px solid {COLORS['border']}",
    "borderRadius": "8px",
    "padding": "16px",
    "marginBottom": "16px",
}
_INFO_BOX = {
    "backgroundColor": "#1a2332",
    "border": f"1px solid {COLORS['accent']}",
    "borderLeft": f"4px solid {COLORS['accent']}",
    "borderRadius": "6px",
    "padding": "14px 16px",
    "fontSize": "0.82rem",
    "color": COLORS["text_muted"],
    "lineHeight": "1.6",
    "marginBottom": "16px",
}
_WARNING_BOX = {
    **_INFO_BOX,
    "backgroundColor": "#2d1a1a",
    "border": f"1px solid {COLORS['red']}",
    "borderLeft": f"4px solid {COLORS['red']}",
    "color": "#fca5a5",
}

# Colores por país
_COUNTRY_COLORS = {
    "JPN": "#ec4899",
    "DEU": "#10b981",
    "ESP": "#f59e0b",
    "USA": "#3b82f6",
    "CHN": "#f97316",
    "IND": "#84cc16",
    "NGA": "#14b8a6",
    "ITA": "#ef4444",
    "FRA": "#8b5cf6",
    "GBR": "#06b6d4",
}

# ── Helpers ────────────────────────────────────────────────────────────────────


def _rgba(hex_color: str, alpha: float = 0.12) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def _safe(value, fmt=".2f", fallback="—"):
    if value is None:
        return fallback
    try:
        return f"{value:{fmt}}"
    except Exception:
        return fallback


def _load_json(filename: str) -> dict:
    try:
        path = _DATA_DIR / filename
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _metric_card(title: str, value: str, subtitle: str = "", color: str | None = None) -> html.Div:
    vc = color or COLORS["text"]
    return html.Div(
        [
            html.Div(title, style={
                "fontSize": "0.72rem", "color": COLORS["text_muted"],
                "textTransform": "uppercase", "letterSpacing": "0.05em",
                "marginBottom": "4px",
            }),
            html.Div(value, style={
                "fontSize": "1.4rem", "fontWeight": "700",
                "color": vc, "lineHeight": "1.2",
            }),
            html.Div(subtitle, style={
                "fontSize": "0.72rem", "color": COLORS["text_muted"],
                "marginTop": "2px",
            }) if subtitle else html.Div(),
        ],
        style={
            "backgroundColor": COLORS["card_bg"],
            "border": f"1px solid {COLORS['border']}",
            "borderRadius": "8px",
            "padding": "14px 16px",
        },
    )


def _badge(text: str, color: str = "#ef4444", bg: str | None = None) -> html.Span:
    bg = bg or _rgba(color, 0.15)
    return html.Span(text, style={
        "backgroundColor": bg,
        "color": color,
        "border": f"1px solid {color}",
        "borderRadius": "4px",
        "padding": "3px 10px",
        "fontSize": "0.75rem",
        "fontWeight": "600",
        "marginRight": "8px",
    })


def _section_title(text: str) -> html.Div:
    return html.Div(text, style={
        "fontSize": "1rem", "fontWeight": "600", "color": COLORS["text"],
        "marginBottom": "12px",
    })


# ── Header del módulo ──────────────────────────────────────────────────────────

def _build_header() -> html.Div:
    # Población mundial
    pop_val, _ = get_latest_value("wb_sp_pop_totl_wld")
    if pop_val is not None:
        pop_str = f"{pop_val / 1e9:.2f}B"
    else:
        pop_str = "~8.2B"

    # Fertilidad global
    fert_val, _ = get_latest_value("wb_sp_dyn_tfrt_in_wld")
    fert_str = _safe(fert_val, ".2f") if fert_val is not None else "~2.3"
    fert_color = COLORS["red"] if (fert_val is not None and fert_val < 2.1) else COLORS["yellow"]

    # País con menor fertilidad (estático — KOR suele ser el más bajo)
    low_fert_country = "Corea del Sur"
    low_fert_val, _ = get_latest_value("wb_sp_dyn_tfrt_in_kor")
    if low_fert_val is not None:
        low_fert_str = f"{low_fert_val:.2f}"
    else:
        low_fert_str = "~0.78"

    # Ratio dependencia ancianos global
    dep_val, _ = get_latest_value("wb_sp_pop_dpnd_ol_wld")
    dep_str = _safe(dep_val, ".1f") + "%" if dep_val is not None else "~15.4%"

    # I+D % PIB global
    rd_val, _ = get_latest_value("wb_gb_xpd_rsdv_gd_zs_wld")
    rd_str = _safe(rd_val, ".1f") + "%" if rd_val is not None else "~2.6%"

    # Badges
    badges = []
    fert_num = fert_val if fert_val is not None else 2.3
    if fert_num < 2.5:
        badges.append(_badge(
            "⚠️ La población mundial comenzará a decrecer antes de 2100",
            color=COLORS["yellow"],
        ))
    badges.append(_badge(
        f"🔻 {low_fert_country}: {low_fert_str} hijos/mujer — mínimo histórico mundial",
        color=COLORS["red"],
    ))

    return html.Div([
        html.Div([
            html.Div([
                html.Span("👥", style={"fontSize": "1.4rem", "marginRight": "10px"}),
                html.Div([
                    html.Div("Demografía y Tendencias Estructurales",
                             style={"fontSize": "1.2rem", "fontWeight": "700", "color": COLORS["text"]}),
                    html.Div("Las fuerzas que moldean la economía durante décadas",
                             style={"fontSize": "0.82rem", "color": COLORS["text_muted"]}),
                ]),
            ], style={"display": "flex", "alignItems": "center"}),
            html.Div(badges, style={"display": "flex", "flexWrap": "wrap", "gap": "6px", "marginTop": "8px"}),
        ], style={"marginBottom": "14px"}),

        # Métricas
        dbc.Row([
            dbc.Col(_metric_card("Población Mundial", pop_str, "Fuente: World Bank"), width=2),
            dbc.Col(_metric_card("Fertilidad Global", fert_str,
                                 "Umbral: 2.1 (reemplazo)", fert_color), width=2),
            dbc.Col(_metric_card("Menor Fertilidad", low_fert_str,
                                 low_fert_country, COLORS["red"]), width=3),
            dbc.Col(_metric_card("Ratio Dependencia Ancianos", dep_str,
                                 "Mayores/100 activos"), width=3),
            dbc.Col(_metric_card("I+D Global / PIB", rd_str,
                                 "Inversión en innovación"), width=2),
        ], className="g-2"),
    ], id="m13-header", style={
        "backgroundColor": COLORS["card_bg"],
        "border": f"1px solid {COLORS['border']}",
        "borderRadius": "8px",
        "padding": "16px",
        "marginBottom": "16px",
    })


# ── TAB 1: Población y Pirámides ───────────────────────────────────────────────

def _build_tab1() -> html.Div:
    # Selector de país para pirámide
    pyramid_selector = dcc.Dropdown(
        id="m13-pyramid-country",
        options=[
            {"label": "🇩🇪 Alemania", "value": "DEU"},
            {"label": "🇮🇳 India", "value": "IND"},
            {"label": "🇯🇵 Japón", "value": "JPN"},
            {"label": "🇳🇬 Nigeria", "value": "NGA"},
            {"label": "🇪🇸 España", "value": "ESP"},
        ],
        value="JPN",
        clearable=False,
        style={
            "backgroundColor": COLORS["card_bg"],
            "color": COLORS["text"],
            "border": f"1px solid {COLORS['border']}",
            "width": "220px",
        },
    )

    return html.Div([
        # 1.1 — Evolución Población Mundial
        html.Div([
            _section_title("1.1 — Evolución de la Población Mundial"),
            dcc.Loading(
                dcc.Graph(id="m13-world-pop-chart", config={"displayModeBar": False},
                          style={"height": "300px"}),
                color=COLORS["accent"],
            ),
            html.Div(
                "La población mundial alcanzará su pico aproximadamente en 2080-2090 y luego empezará a decrecer "
                "lentamente. Pero esta media global oculta divergencias enormes: África duplicará su población "
                "mientras Europa y Asia Oriental la verán decrecer.",
                style=_INFO_BOX,
            ),
        ], style=_CARD),

        # 1.2 — Pirámides de Población
        html.Div([
            html.Div([
                _section_title("1.2 — Pirámide de Población"),
                pyramid_selector,
            ], style={"display": "flex", "alignItems": "center", "justifyContent": "space-between",
                      "marginBottom": "12px"}),
            dbc.Row([
                dbc.Col([
                    dcc.Loading(
                        dcc.Graph(id="m13-pyramid-chart", config={"displayModeBar": False},
                                  style={"height": "380px"}),
                        color=COLORS["accent"],
                    ),
                ], width=8),
                dbc.Col([
                    html.Div(id="m13-pyramid-stats", style={"marginTop": "20px"}),
                ], width=4),
            ]),
        ], style=_CARD),

        # 1.3 — Tasa de Fertilidad
        html.Div([
            _section_title("1.3 — Tasa de Fertilidad Global: El Indicador más Predictivo"),
            dcc.Loading(
                dcc.Graph(id="m13-fertility-chart", config={"displayModeBar": False},
                          style={"height": "320px"}),
                color=COLORS["accent"],
            ),
            html.Div([
                html.Strong("Nota histórica: "),
                html.Span(
                    "Corea del Sur registró una tasa de fertilidad de 0.78 en 2023 — el valor más bajo "
                    "documentado en cualquier nación de la historia. Ningún país ha sobrevivido a largo plazo "
                    "con tasas tan bajas sin inmigración masiva. Por debajo de 2.1, la población decrece "
                    "generacionalmente; por debajo de 1.5, el declive se acelera de forma compuesta.",
                ),
            ], style=_WARNING_BOX),
        ], style=_CARD),
    ], style={"padding": "4px 0"})


# ── TAB 2: Envejecimiento y Pensiones ─────────────────────────────────────────

def _build_tab2() -> html.Div:
    return html.Div([
        # 2.1 — Ratio de Dependencia
        html.Div([
            _section_title("2.1 — El Tsunami Gris: Ratio de Dependencia de Ancianos"),
            dcc.Loading(
                dcc.Graph(id="m13-dependency-chart", config={"displayModeBar": False},
                          style={"height": "320px"}),
                color=COLORS["accent"],
            ),
            html.Div(
                "Cuando el ratio de dependencia supera 50, hay menos de 2 trabajadores por cada jubilado. "
                "El sistema de pensiones de reparto (en el que los trabajadores actuales pagan las pensiones "
                "de los jubilados actuales) se vuelve matemáticamente insostenible sin ajustes profundos.",
                style=_WARNING_BOX,
            ),
        ], style=_CARD),

        # 2.2 — Sostenibilidad pensiones
        html.Div([
            _section_title("2.2 — Sostenibilidad de los Sistemas de Pensiones"),
            html.Div(id="m13-pension-panel"),
            html.Div([
                html.Strong("Caso España: "),
                html.Span(
                    "España tiene una de las tasas de reemplazo más altas de la OCDE (72%), lo que significa "
                    "que las pensiones son generosas, pero con una demografía en deterioro y una economía con "
                    "alto desempleo estructural, la sostenibilidad a largo plazo es el principal riesgo fiscal "
                    "del país.",
                ),
            ], style={**_WARNING_BOX, "marginTop": "12px"}),
        ], style=_CARD),

        # 2.3 — Impacto macroeconómico
        html.Div([
            _section_title("2.3 — El Impacto Macroeconómico del Envejecimiento"),
            dcc.Loading(
                dcc.Graph(id="m13-labor-force-chart", config={"displayModeBar": False},
                          style={"height": "280px"}),
                color=COLORS["accent"],
            ),
            html.Div(
                "El crecimiento del PIB puede descomponerse en: crecimiento de la fuerza laboral + crecimiento "
                "de la productividad. En países con fuerza laboral decreciente, solo el crecimiento de la "
                "productividad puede mantener el nivel de vida. Japón es el ejemplo extremo: su PIB total "
                "apenas crece pero su PIB por persona activa ha crecido moderadamente gracias a la automatización.",
                style=_INFO_BOX,
            ),
        ], style=_CARD),

        # 2.4 — Inmigración
        html.Div([
            _section_title("2.4 — Inmigración como Variable Compensadora"),
            dcc.Loading(
                dcc.Graph(id="m13-migration-chart", config={"displayModeBar": False},
                          style={"height": "280px"}),
                color=COLORS["accent"],
            ),
            html.Div(
                "La inmigración es la única variable demográfica que puede cambiar rápidamente. Alemania y "
                "España han utilizado masivamente la inmigración para compensar su declive demográfico nativo. "
                "EE.UU. debe prácticamente todo su crecimiento demográfico a la inmigración. Sin ella, varios "
                "países desarrollados ya estarían en contracción poblacional.",
                style=_INFO_BOX,
            ),
        ], style=_CARD),
    ], style={"padding": "4px 0"})


# ── TAB 3: Productividad y Crecimiento ────────────────────────────────────────

def _build_tab3() -> html.Div:
    return html.Div([
        # 3.1 — Productividad laboral
        html.Div([
            _section_title("3.1 — El Motor del Nivel de Vida: Crecimiento de la Productividad"),
            dcc.Loading(
                dcc.Graph(id="m13-productivity-chart", config={"displayModeBar": False},
                          style={"height": "300px"}),
                color=COLORS["accent"],
            ),
            html.Div([
                html.Strong("La paradoja de la productividad tecnológica: "),
                html.Span(
                    "Vivimos en la era de mayor avance tecnológico de la historia (smartphones, internet, IA) "
                    "pero el crecimiento de la productividad en las economías avanzadas es el más lento desde "
                    "la Revolución Industrial. El economista Robert Gordon lo llama 'el gran estancamiento'.",
                ),
            ], style=_INFO_BOX),
        ], style=_CARD),

        # 3.2 — I+D
        html.Div([
            _section_title("3.2 — Inversión en I+D: Sembrando el Futuro"),
            dbc.Row([
                dbc.Col([
                    dcc.Loading(
                        dcc.Graph(id="m13-rd-bar-chart", config={"displayModeBar": False},
                                  style={"height": "280px"}),
                        color=COLORS["accent"],
                    ),
                ], width=6),
                dbc.Col([
                    dcc.Loading(
                        dcc.Graph(id="m13-rd-trend-chart", config={"displayModeBar": False},
                                  style={"height": "280px"}),
                        color=COLORS["accent"],
                    ),
                ], width=6),
            ]),
            html.Div(
                "La inversión en I+D es el indicador más predictivo de la capacidad de innovación futura "
                "de un país. China ha multiplicado por 10 su inversión en I+D desde 2000 en términos absolutos. "
                "La brecha entre EE.UU./China y el resto del mundo en I+D es uno de los factores que más "
                "contribuirá a la concentración de poder económico en las próximas décadas.",
                style=_INFO_BOX,
            ),
        ], style=_CARD),

        # 3.3 — IA y Productividad
        html.Div([
            _section_title("3.3 — La IA y la Productividad: ¿El Fin del Estancamiento?"),
            html.Div(
                "Las estimaciones de impacto de la IA en productividad varían enormemente: desde Goldman Sachs "
                "que proyecta un aumento del PIB global del 7% en 10 años gracias a la IA, hasta estudios del "
                "MIT que encuentran que el 95% de las organizaciones reportan cero retorno medible en productividad "
                "hasta 2025. La verdad probablemente esté en el medio, con impactos concentrados en sectores específicos.",
                style=_INFO_BOX,
            ),
            dbc.Row([
                dbc.Col([
                    dcc.Loading(
                        dcc.Graph(id="m13-ai-estimates-chart", config={"displayModeBar": False},
                                  style={"height": "260px"}),
                        color=COLORS["accent"],
                    ),
                ], width=6),
                dbc.Col([
                    dcc.Loading(
                        dcc.Graph(id="m13-ai-sectors-chart", config={"displayModeBar": False},
                                  style={"height": "260px"}),
                        color=COLORS["accent"],
                    ),
                ], width=6),
            ]),
        ], style=_CARD),

        # 3.4 — Educación
        html.Div([
            _section_title("3.4 — Educación como Infraestructura Económica"),
            dcc.Loading(
                dcc.Graph(id="m13-education-scatter", config={"displayModeBar": False},
                          style={"height": "300px"}),
                color=COLORS["accent"],
            ),
            html.Div(
                "La correlación positiva entre educación (matriculación terciaria) y riqueza (PIB per cápita) "
                "es una de las más robustas en economía. No implica necesariamente causalidad directa — "
                "también refleja que países más ricos pueden permitirse más educación — pero la acumulación "
                "de capital humano es universalmente reconocida como uno de los principales motores de crecimiento.",
                style=_INFO_BOX,
            ),
        ], style=_CARD),
    ], style={"padding": "4px 0"})


# ── TAB 4: Desigualdad ────────────────────────────────────────────────────────

def _build_tab4() -> html.Div:
    return html.Div([
        # 4.1 — Gini
        html.Div([
            _section_title("4.1 — El Índice de Gini: La Desigualdad en un Número"),
            dbc.Row([
                dbc.Col([
                    dcc.Loading(
                        dcc.Graph(id="m13-gini-bar-chart", config={"displayModeBar": False},
                                  style={"height": "320px"}),
                        color=COLORS["accent"],
                    ),
                ], width=7),
                dbc.Col([
                    dcc.Loading(
                        dcc.Graph(id="m13-gini-trend-chart", config={"displayModeBar": False},
                                  style={"height": "320px"}),
                        color=COLORS["accent"],
                    ),
                ], width=5),
            ]),
            html.Div(
                "El Gini de EE.UU. (~41) es el más alto de los países desarrollados. El de España (~33) es "
                "moderado para la UE. Sudáfrica (~63) y Brasil (~53) lideran la desigualdad global. "
                "China experimentó un notable aumento desde los años 80 hasta ~2008, con ligera mejora posterior.",
                style=_INFO_BOX,
            ),
        ], style=_CARD),

        # 4.2 — Productividad vs Salarios
        html.Div([
            _section_title("4.2 — La Gran Divergencia: Productividad vs Salarios (EE.UU. desde 1979)"),
            dcc.Loading(
                dcc.Graph(id="m13-wage-divergence-chart", config={"displayModeBar": False},
                          style={"height": "300px"}),
                color=COLORS["accent"],
            ),
            html.Div([
                html.Strong("Causa estructural del aumento de la desigualdad: "),
                html.Span(
                    "Desde 1979, la productividad americana ha crecido un 156% mientras que el salario real "
                    "del trabajador medio solo lo ha hecho un 38%. La diferencia — el 118% restante — ha ido "
                    "principalmente al capital (accionistas, directivos). Esta es la causa estructural del "
                    "aumento de la desigualdad en los países desarrollados.",
                ),
            ], style=_WARNING_BOX),
        ], style=_CARD),

        # 4.3 — Desigualdad y Populismo
        html.Div([
            _section_title("4.3 — Desigualdad y Riesgo Político: El Auge del Populismo"),
            dcc.Loading(
                dcc.Graph(id="m13-populism-scatter", config={"displayModeBar": False},
                          style={"height": "300px"}),
                color=COLORS["accent"],
            ),
            html.Div(
                "La investigación académica muestra una correlación moderada pero consistente entre alta "
                "desigualdad y auge del populismo. La teoría: cuando la clase media percibe que el sistema "
                "no funciona para ellos (estancamiento salarial, costes de vivienda elevados, inseguridad "
                "laboral), buscan alternativas políticas radicales. Esto es relevante para la estabilidad "
                "institucional y para el riesgo de cambios bruscos de política económica.",
                style=_INFO_BOX,
            ),
        ], style=_CARD),
    ], style={"padding": "4px 0"})


# ── TAB 5: Tendencias Disruptivas ─────────────────────────────────────────────

def _build_tab5() -> html.Div:
    def _trend_header(emoji: str, title: str, horizon: str, summary: str) -> html.Div:
        return html.Div([
            html.Div([
                html.Span(emoji, style={"fontSize": "1.5rem", "marginRight": "10px"}),
                html.Div([
                    html.Div(title, style={"fontWeight": "700", "color": COLORS["text"], "fontSize": "1rem"}),
                    html.Span(f"Horizonte: {horizon}", style={
                        "fontSize": "0.72rem", "color": COLORS["accent"],
                        "backgroundColor": _rgba(COLORS["accent"], 0.1),
                        "border": f"1px solid {COLORS['accent']}",
                        "borderRadius": "4px", "padding": "2px 8px",
                    }),
                ]),
            ], style={"display": "flex", "alignItems": "center", "marginBottom": "10px"}),
            html.Div(summary, style={
                "fontSize": "0.83rem", "color": COLORS["text_muted"],
                "lineHeight": "1.65", "marginBottom": "12px",
            }),
        ])

    def _scenario_pills(opt: str, pes: str, real: str) -> html.Div:
        return html.Div([
            html.Div([
                html.Span("Optimista", style={"fontWeight": "600", "color": COLORS["green"], "marginRight": "4px"}),
                html.Span(opt, style={"fontSize": "0.8rem", "color": COLORS["text_muted"]}),
            ], style={"marginBottom": "4px"}),
            html.Div([
                html.Span("Pesimista", style={"fontWeight": "600", "color": COLORS["red"], "marginRight": "4px"}),
                html.Span(pes, style={"fontSize": "0.8rem", "color": COLORS["text_muted"]}),
            ], style={"marginBottom": "4px"}),
            html.Div([
                html.Span("Realista", style={"fontWeight": "600", "color": COLORS["yellow"], "marginRight": "4px"}),
                html.Span(real, style={"fontSize": "0.8rem", "color": COLORS["text_muted"]}),
            ]),
        ], style={
            "backgroundColor": "#0f1623",
            "border": f"1px solid {COLORS['border']}",
            "borderRadius": "6px",
            "padding": "12px 14px",
            "marginTop": "10px",
        })

    accordion_items = [
        dbc.AccordionItem(
            html.Div([
                _trend_header(
                    "🤖", "IA y Automatización", "2025-2040",
                    "La IA generativa está transformando el trabajo cognitivo de la misma forma que la revolución "
                    "industrial transformó el trabajo físico. A diferencia de automatizaciones anteriores, afecta "
                    "principalmente a trabajos de alta cualificación (abogados, médicos, programadores, analistas financieros).",
                ),
                dcc.Loading(
                    dcc.Graph(id="m13-ai-impact-tab5", config={"displayModeBar": False},
                              style={"height": "240px"}),
                    color=COLORS["accent"],
                ),
                _scenario_pills(
                    "Nueva ola de productividad y prosperidad: IA democratiza el conocimiento, reduce costes, crea nuevos sectores.",
                    "Desplazamiento masivo sin reemplazo suficiente: polarización del mercado laboral, conflicto social.",
                    "Transición dolorosa con ganadores y perdedores claros: alta cualificación gana, trabajo rutinario cognitivo pierde.",
                ),
            ]),
            title="🤖 IA y Automatización — La mayor disrupción del trabajo cognitivo",
            item_id="ai",
        ),

        dbc.AccordionItem(
            html.Div([
                _trend_header(
                    "⚡", "Transición Energética", "2025-2050",
                    "La economía mundial está en proceso de descarbonización acelerada, impulsada por la caída de "
                    "costes de renovables, mandatos regulatorios y presión inversora. El sector energético, que "
                    "representa el 7% del PIB mundial, está siendo reinventado.",
                ),
                dbc.Row([
                    dbc.Col(_metric_card("Caída coste solar", "-99%", "desde 1977 hasta 2024", COLORS["green"]), width=3),
                    dbc.Col(_metric_card("Caída coste baterías", "-97%", "desde 2010 hasta 2024", COLORS["green"]), width=3),
                    dbc.Col(_metric_card("Inversión renovables 2024", "$1.8T", "récord histórico", COLORS["accent"]), width=3),
                    dbc.Col(_metric_card("China — cuota solar global", "~80%", "manufactura paneles", COLORS["orange"]), width=3),
                ], className="g-2", style={"marginBottom": "12px"}),
                _scenario_pills(
                    "Descarbonización lograda en 2050: renovables baratas, minerales críticos suficientes, empleo verde neto positivo.",
                    "Transición caótica: minerales escasos, resistencia política en países productores, desinversión sin sustitución.",
                    "Descarbonización parcial: sectores difíciles (acero, cemento, aviación) siguen emitiendo hasta 2070+.",
                ),
            ]),
            title="⚡ Transición Energética — Reinventando el sector energético global",
            item_id="energy",
        ),

        dbc.AccordionItem(
            html.Div([
                _trend_header(
                    "🏙️", "Urbanización Global", "2025-2050",
                    "El 56% de la humanidad vive en ciudades. Para 2050 será el 68%. La urbanización en África y "
                    "Asia está creando megaciudades de una velocidad y escala sin precedentes. Esto concentra el "
                    "crecimiento económico pero también los riesgos: infraestructura, vivienda, servicios.",
                ),
                dcc.Loading(
                    dcc.Graph(id="m13-urbanization-chart", config={"displayModeBar": False},
                              style={"height": "240px"}),
                    color=COLORS["accent"],
                ),
                html.Div([
                    html.Div("Top 5 Megaciudades 2050 (proyectado)", style={
                        "fontWeight": "600", "color": COLORS["text"],
                        "fontSize": "0.85rem", "marginBottom": "8px",
                    }),
                    html.Div([
                        html.Div(f"{'Lagos':20s} → 35M hab.", style={"color": COLORS["text_muted"], "fontSize": "0.8rem"}),
                        html.Div(f"{'Delhi':20s} → 43M hab.", style={"color": COLORS["text_muted"], "fontSize": "0.8rem"}),
                        html.Div(f"{'Dhaka':20s} → 35M hab.", style={"color": COLORS["text_muted"], "fontSize": "0.8rem"}),
                        html.Div(f"{'Mumbai':20s} → 30M hab.", style={"color": COLORS["text_muted"], "fontSize": "0.8rem"}),
                        html.Div(f"{'Kinshasa':20s} → 35M hab.", style={"color": COLORS["text_muted"], "fontSize": "0.8rem"}),
                    ], style={"fontFamily": "monospace"}),
                ], style={**_INFO_BOX, "marginTop": "12px"}),
            ]),
            title="🏙️ Urbanización Global — El mundo se concentra en megaciudades africanas y asiáticas",
            item_id="urban",
        ),

        dbc.AccordionItem(
            html.Div([
                _trend_header(
                    "🔒", "Desglobalización", "2020-2040",
                    "El orden económico global que dominó desde 1990 — libre comercio, cadenas de suministro "
                    "globales, inversión sin fronteras — está siendo cuestionado por el auge del proteccionismo, "
                    "las tensiones geopolíticas y las lecciones de vulnerabilidad de la pandemia. El mundo se "
                    "está reorganizando en bloques regionales.",
                ),
                dbc.Row([
                    dbc.Col(_metric_card("Coste FMI (escenario fragmentación)", "2-7% PIB global", "pérdida a largo plazo", COLORS["red"]), width=4),
                    dbc.Col(_metric_card("Aranceles promedio G7 vs China", "~25%", "desde 2018", COLORS["orange"]), width=4),
                    dbc.Col(_metric_card("Nearshoring inversión 2024", "+34%", "vs 2019", COLORS["yellow"]), width=4),
                ], className="g-2", style={"marginBottom": "12px"}),
                _scenario_pills(
                    "Regionalización ordenada: bloques regionales eficientes, comercio interior crece, costes manejables.",
                    "Fragmentación caótica: guerras arancelarias en cascada, rupturas de cadenas críticas, inflación estructural.",
                    "Mundo bipolar USA/China: aliados forzados a elegir bando, costes de 3-5% PIB en 10 años.",
                ),
            ]),
            title="🔒 Desglobalización — El fin del libre comercio sin fricciones",
            item_id="deglobal",
        ),

        dbc.AccordionItem(
            html.Div([
                _trend_header(
                    "🌡️", "Cambio Climático Económico", "2025-2100",
                    "El cambio climático no es solo un problema ambiental sino un creciente riesgo económico y "
                    "financiero. El Banco Mundial estima que podría empujar a más de 100 millones de personas a "
                    "la pobreza antes de 2030. Los activos financieros más expuestos a riesgos climáticos suman "
                    "decenas de billones de dólares.",
                ),
                dcc.Loading(
                    dcc.Graph(id="m13-climate-chart", config={"displayModeBar": False},
                              style={"height": "240px"}),
                    color=COLORS["accent"],
                ),
                dbc.Row([
                    dbc.Col(_metric_card("Activos varados (stranded)", "$20T", "combustibles fósiles + costas", COLORS["red"]), width=4),
                    dbc.Col(_metric_card("Pérdidas seguros 2025", "$280B", "récord histórico", COLORS["orange"]), width=4),
                    dbc.Col(_metric_card("Regiones más vulnerables", "5", "Bangladesh, Sahel, costas Asia...", COLORS["yellow"]), width=4),
                ], className="g-2", style={"marginTop": "12px"}),
            ]),
            title="🌡️ Cambio Climático Económico — El mayor riesgo financiero no de mercado",
            item_id="climate",
        ),
    ]

    return html.Div([
        html.Div(
            "Las cinco tendencias que definirán la economía de las próximas décadas. Haz click para expandir cada tendencia.",
            style={"fontSize": "0.83rem", "color": COLORS["text_muted"], "marginBottom": "16px"},
        ),
        dbc.Accordion(
            accordion_items,
            id="m13-trends-accordion",
            active_item="ai",
            always_open=False,
            style={"backgroundColor": "transparent"},
        ),
    ], style={"padding": "4px 0"})


# ── Render principal ───────────────────────────────────────────────────────────

def render_module_13() -> html.Div:
    tabs = dcc.Tabs(
        id="m13-tabs",
        value="tab-1",
        children=[
            dcc.Tab(label="👥 Población y Pirámides",     value="tab-1",
                    style=_TAB_STYLE, selected_style=_TAB_SELECTED),
            dcc.Tab(label="👴 Envejecimiento y Pensiones", value="tab-2",
                    style=_TAB_STYLE, selected_style=_TAB_SELECTED),
            dcc.Tab(label="⚙️ Productividad y Crecimiento", value="tab-3",
                    style=_TAB_STYLE, selected_style=_TAB_SELECTED),
            dcc.Tab(label="⚖️ Desigualdad",                value="tab-4",
                    style=_TAB_STYLE, selected_style=_TAB_SELECTED),
            dcc.Tab(label="🚀 Tendencias Disruptivas",    value="tab-5",
                    style=_TAB_STYLE, selected_style=_TAB_SELECTED),
        ],
        style=_TABS_CONTAINER,
    )

    return html.Div([
        _build_header(),
        dcc.Interval(id="m13-interval", interval=600_000, n_intervals=0),
        html.Div([
            tabs,
            html.Div(id="m13-tab-content", style={"padding": "16px 0"}),
        ], style={
            "backgroundColor": COLORS["card_bg"],
            "border": f"1px solid {COLORS['border']}",
            "borderRadius": "8px",
            "padding": "0",
            "overflow": "hidden",
        }),
    ], style={
        "padding": "16px",
        "backgroundColor": COLORS["background"],
        "minHeight": "100vh",
    })


# ── Callbacks ─────────────────────────────────────────────────────────────────

def register_callbacks_module_13(app) -> None:

    # ── Tab routing ───────────────────────────────────────────────────────────
    @app.callback(
        Output("m13-tab-content", "children"),
        Input("m13-tabs", "value"),
    )
    def render_tab(tab):
        if tab == "tab-1":
            return _build_tab1()
        if tab == "tab-2":
            return _build_tab2()
        if tab == "tab-3":
            return _build_tab3()
        if tab == "tab-4":
            return _build_tab4()
        if tab == "tab-5":
            return _build_tab5()
        return _build_tab1()

    # ── Header refresh ────────────────────────────────────────────────────────
    @app.callback(
        Output("m13-header", "children"),
        Input("m13-interval", "n_intervals"),
    )
    def refresh_header(_n):
        return _build_header().children

    # ═══════════════════════════════════════════════════════════════════════════
    # TAB 1 — POBLACIÓN
    # ═══════════════════════════════════════════════════════════════════════════

    @app.callback(
        Output("m13-world-pop-chart", "figure"),
        Input("m13-tabs", "value"),
        Input("m13-interval", "n_intervals"),
    )
    def update_world_pop(tab, _n):
        if tab != "tab-1":
            return go.Figure()

        proj = _load_json("population_projections.json")
        pop_data = proj.get("world_population_billions", {})

        layout = get_base_layout(height=285)
        layout.update(
            title=dict(text="Población Mundial (miles de millones)", font=dict(size=12)),
            yaxis_title="Miles de millones",
            margin=dict(l=55, r=15, t=40, b=45),
            hovermode="x unified",
        )
        fig = go.Figure(layout=layout)

        # Separar histórico (≤2025) de proyecciones (>2025)
        hist_years = sorted([int(y) for y in pop_data if int(y) <= 2025])
        proj_years = sorted([int(y) for y in pop_data if int(y) > 2025])

        hist_vals = [pop_data[str(y)] for y in hist_years]
        proj_vals = [pop_data[str(y)] for y in proj_years]

        # Unir el último histórico con el primero de proyección para la línea continua
        link_years = hist_years[-1:] + proj_years
        link_vals = hist_vals[-1:] + proj_vals

        fig.add_trace(go.Scatter(
            x=hist_years, y=hist_vals,
            name="Histórico",
            mode="lines",
            fill="tozeroy",
            line=dict(color="#3b82f6", width=2),
            fillcolor=_rgba("#3b82f6", 0.15),
            hovertemplate="%{y:.1f}B<extra>Histórico</extra>",
        ))
        fig.add_trace(go.Scatter(
            x=link_years, y=link_vals,
            name="Proyección ONU (variante media)",
            mode="lines",
            line=dict(color="#f97316", width=2, dash="dash"),
            hovertemplate="%{y:.1f}B<extra>Proyección</extra>",
        ))
        # Línea vertical "hoy"
        fig.add_vline(x=2026, line_color="#9ca3af", line_width=1, line_dash="dot",
                      annotation_text="Hoy", annotation_font_size=9,
                      annotation_font_color="#9ca3af")
        return fig

    # ── Pirámide de población ─────────────────────────────────────────────────
    @app.callback(
        Output("m13-pyramid-chart", "figure"),
        Output("m13-pyramid-stats", "children"),
        Input("m13-pyramid-country", "value"),
        Input("m13-tabs", "value"),
    )
    def update_pyramid(country, tab):
        if tab != "tab-1":
            return go.Figure(), html.Div()

        country = country or "JPN"
        pyramids = _load_json("population_pyramids.json")
        countries = pyramids.get("countries", {})
        data = countries.get(country, {})

        if not data:
            return go.Figure(), html.Div("Sin datos para este país.")

        age_groups = data.get("age_groups", [])
        males = data.get("male_millions", [])
        females = data.get("female_millions", [])
        country_name = data.get("name", country)

        layout = get_base_layout(height=365)
        layout.update(
            title=dict(text=f"Pirámide de Población — {country_name} ({data.get('year', 2025)})",
                       font=dict(size=12)),
            xaxis_title="Millones de personas",
            yaxis_title="",
            margin=dict(l=65, r=25, t=45, b=45),
            barmode="overlay",
            hovermode="y unified",
            bargap=0.1,
        )
        fig = go.Figure(layout=layout)

        fig.add_trace(go.Bar(
            y=age_groups,
            x=[-m for m in males],
            name="Hombres",
            orientation="h",
            marker_color="#3b82f6",
            hovertemplate="Hombres: %{customdata:.1f}M<extra></extra>",
            customdata=males,
        ))
        fig.add_trace(go.Bar(
            y=age_groups,
            x=females,
            name="Mujeres",
            orientation="h",
            marker_color="#ec4899",
            hovertemplate="Mujeres: %{x:.1f}M<extra></extra>",
        ))

        # Eje X con valores absolutos
        total = sum(males) + sum(females)
        max_val = max(max(males), max(females))
        fig.update_xaxes(
            tickvals=[-round(max_val * 0.75, 0), -round(max_val * 0.5, 0),
                      -round(max_val * 0.25, 0), 0,
                      round(max_val * 0.25, 0), round(max_val * 0.5, 0),
                      round(max_val * 0.75, 0)],
            ticktext=[f"{round(max_val * 0.75, 0):.0f}M", f"{round(max_val * 0.5, 0):.0f}M",
                      f"{round(max_val * 0.25, 0):.0f}M", "0",
                      f"{round(max_val * 0.25, 0):.0f}M", f"{round(max_val * 0.5, 0):.0f}M",
                      f"{round(max_val * 0.75, 0):.0f}M"],
        )

        # Calcular estadísticas
        total_pop = sum(males) + sum(females)
        young = sum(males[:3]) + sum(females[:3])   # 0-14
        old = sum(males[-4:]) + sum(females[-4:])   # 65+
        young_old_ratio = young / old if old > 0 else 0

        # Mediana de edad aproximada
        cum = 0
        median_age_group = age_groups[-1]
        for i, ag in enumerate(age_groups):
            cum += males[i] + females[i]
            if cum >= total_pop / 2:
                median_age_group = ag
                break

        # Forma de la pirámide
        base_pct = (sum(males[:3]) + sum(females[:3])) / total_pop * 100 if total_pop > 0 else 0
        top_pct = (sum(males[-4:]) + sum(females[-4:])) / total_pop * 100 if total_pop > 0 else 0
        if base_pct > 35:
            shape = ("Expansiva", "Base ancha — alta natalidad, joven", COLORS["green"])
        elif top_pct > 25:
            shape = ("Contractiva", "Base estrecha — envejecimiento avanzado", COLORS["red"])
        else:
            shape = ("Estacionaria", "Perfil más cilíndrico — transición", COLORS["yellow"])

        def _stat_row(label, value, color=None):
            return html.Div([
                html.Div(label, style={"fontSize": "0.72rem", "color": COLORS["text_muted"],
                                       "marginBottom": "2px"}),
                html.Div(value, style={"fontSize": "1rem", "fontWeight": "700",
                                       "color": color or COLORS["text"]}),
            ], style={
                "backgroundColor": COLORS["card_bg"],
                "border": f"1px solid {COLORS['border']}",
                "borderRadius": "6px",
                "padding": "10px 12px",
                "marginBottom": "8px",
            })

        stats = html.Div([
            html.Div("Indicadores de la pirámide", style={
                "fontSize": "0.8rem", "fontWeight": "600", "color": COLORS["text"],
                "marginBottom": "10px",
            }),
            _stat_row("Población total", f"{total_pop:.1f}M"),
            _stat_row("Mediana de edad (aprox.)", median_age_group),
            _stat_row("Ratio jóvenes/mayores (<15 / 65+)", f"{young_old_ratio:.1f}x"),
            _stat_row("Forma de la pirámide", shape[0], shape[2]),
            html.Div(shape[1], style={
                "fontSize": "0.78rem", "color": COLORS["text_muted"],
                "fontStyle": "italic", "marginTop": "4px",
            }),
        ])

        return fig, stats

    # ── Fertilidad ────────────────────────────────────────────────────────────
    @app.callback(
        Output("m13-fertility-chart", "figure"),
        Input("m13-tabs", "value"),
        Input("m13-interval", "n_intervals"),
    )
    def update_fertility(tab, _n):
        if tab != "tab-1":
            return go.Figure()

        layout = get_base_layout(height=305)
        layout.update(
            title=dict(text="Tasa de Fertilidad (hijos por mujer)", font=dict(size=12)),
            yaxis_title="Hijos por mujer",
            margin=dict(l=55, r=15, t=40, b=45),
            hovermode="x unified",
        )
        fig = go.Figure(layout=layout)

        # Línea de reemplazo
        fig.add_hline(y=2.1, line_color="#f59e0b", line_width=1.5, line_dash="dash",
                      annotation_text="Tasa de reemplazo (2.1)",
                      annotation_font_size=9, annotation_font_color="#f59e0b",
                      annotation_position="top left")

        # Datos estáticos de fertilidad por región
        static_fertility = {
            "WLD": {
                "name": "Mundial",
                "color": "#3b82f6",
                "data": {1960: 4.98, 1970: 4.45, 1980: 3.66, 1990: 3.05,
                         2000: 2.65, 2010: 2.52, 2015: 2.44, 2020: 2.30, 2024: 2.25},
            },
            "SSA": {
                "name": "África Subsahariana",
                "color": "#14b8a6",
                "data": {1960: 6.60, 1970: 6.70, 1980: 6.74, 1990: 6.37,
                         2000: 5.77, 2010: 5.16, 2015: 4.85, 2020: 4.61, 2024: 4.45},
            },
            "CHN": {
                "name": "China",
                "color": "#f97316",
                "data": {1960: 5.75, 1970: 5.72, 1980: 2.63, 1990: 2.31,
                         2000: 1.73, 2010: 1.57, 2015: 1.61, 2020: 1.28, 2024: 1.09},
            },
            "IND": {
                "name": "India",
                "color": "#84cc16",
                "data": {1960: 5.82, 1970: 5.50, 1980: 4.67, 1990: 3.72,
                         2000: 3.00, 2010: 2.50, 2015: 2.30, 2020: 2.01, 2024: 1.94},
            },
            "KOR": {
                "name": "Corea del Sur",
                "color": "#ef4444",
                "data": {1960: 5.63, 1970: 4.53, 1980: 2.83, 1990: 1.57,
                         2000: 1.47, 2010: 1.23, 2015: 1.24, 2020: 0.84, 2024: 0.72},
            },
            "EU": {
                "name": "Europa",
                "color": "#8b5cf6",
                "data": {1960: 2.59, 1970: 2.38, 1980: 1.87, 1990: 1.67,
                         2000: 1.52, 2010: 1.60, 2015: 1.59, 2020: 1.51, 2024: 1.46},
            },
        }

        for iso, info in static_fertility.items():
            years = sorted(info["data"].keys())
            vals = [info["data"][y] for y in years]
            fig.add_trace(go.Scatter(
                x=years, y=vals,
                name=info["name"],
                mode="lines+markers",
                line=dict(color=info["color"], width=2),
                marker=dict(size=5),
                hovertemplate=f"{info['name']}: %{{y:.2f}}<extra></extra>",
            ))

        # Anotación Corea del Sur
        fig.add_annotation(
            x=2024, y=0.72,
            text="🇰🇷 Corea: 0.72 — mínimo histórico mundial",
            showarrow=True, arrowhead=2, arrowcolor="#ef4444",
            ax=-120, ay=-30,
            font=dict(size=9, color="#ef4444"),
            bgcolor="#1a0a0a", bordercolor="#ef4444",
        )
        return fig

    # ═══════════════════════════════════════════════════════════════════════════
    # TAB 2 — ENVEJECIMIENTO
    # ═══════════════════════════════════════════════════════════════════════════

    @app.callback(
        Output("m13-dependency-chart", "figure"),
        Input("m13-tabs", "value"),
        Input("m13-interval", "n_intervals"),
    )
    def update_dependency(tab, _n):
        if tab != "tab-2":
            return go.Figure()

        dep_data = _load_json("dependency_projections.json")
        ratios = dep_data.get("old_age_dependency_ratio", {})

        layout = get_base_layout(height=305)
        layout.update(
            title=dict(text="Ratio de Dependencia de Ancianos (mayores 65 / 100 activos)", font=dict(size=12)),
            yaxis_title="Ratio de dependencia (%)",
            margin=dict(l=55, r=15, t=40, b=45),
            hovermode="x unified",
        )
        fig = go.Figure(layout=layout)

        # Líneas de referencia
        fig.add_hline(y=30, line_color="#f59e0b", line_width=1, line_dash="dash",
                      annotation_text="Nivel de alerta (30)", annotation_font_size=9,
                      annotation_font_color="#f59e0b", annotation_position="right")
        fig.add_hline(y=50, line_color="#ef4444", line_width=1.5, line_dash="dash",
                      annotation_text="Crisis severa (50)", annotation_font_size=9,
                      annotation_font_color="#ef4444", annotation_position="right")

        country_names = {
            "JPN": "Japón", "DEU": "Alemania", "ESP": "España",
            "USA": "EE.UU.", "CHN": "China", "IND": "India", "NGA": "Nigeria",
        }

        for iso, name in country_names.items():
            if iso not in ratios:
                continue
            country_data = ratios[iso]
            years = sorted([int(y) for y in country_data.keys()])
            vals = [country_data[str(y)] for y in years]
            color = _COUNTRY_COLORS.get(iso, "#9ca3af")
            # Línea punteada para proyecciones (>2025)
            hist_y = [y for y in years if y <= 2025]
            hist_v = [country_data[str(y)] for y in hist_y]
            proj_y = [y for y in years if y >= 2025]
            proj_v = [country_data[str(y)] for y in proj_y]

            if hist_y:
                fig.add_trace(go.Scatter(
                    x=hist_y, y=hist_v, name=name,
                    mode="lines+markers",
                    line=dict(color=color, width=2),
                    marker=dict(size=5),
                    hovertemplate=f"{name}: %{{y:.0f}}%<extra></extra>",
                    legendgroup=iso,
                ))
            if proj_y:
                fig.add_trace(go.Scatter(
                    x=proj_y, y=proj_v, name=f"{name} (proj.)",
                    mode="lines",
                    line=dict(color=color, width=2, dash="dot"),
                    hovertemplate=f"{name}: %{{y:.0f}}%<extra></extra>",
                    legendgroup=iso,
                    showlegend=False,
                ))

        fig.add_vline(x=2026, line_color="#9ca3af", line_width=1, line_dash="dot",
                      annotation_text="Hoy", annotation_font_size=9,
                      annotation_font_color="#9ca3af")
        return fig

    @app.callback(
        Output("m13-pension-panel", "children"),
        Input("m13-tabs", "value"),
    )
    def update_pension_panel(tab):
        if tab != "tab-2":
            return html.Div()

        pension_data = _load_json("pension_sustainability.json")
        countries = pension_data.get("countries", {})

        level_config = {
            "critical":     {"color": COLORS["red"],    "label": "CRÍTICO",       "dot": "red"},
            "high_risk":    {"color": COLORS["orange"],  "label": "ALTO RIESGO",   "dot": "orange"},
            "moderate":     {"color": COLORS["yellow"],  "label": "MODERADO",      "dot": "yellow"},
            "emerging_risk": {"color": "#fb923c",        "label": "RIESGO EMERGENTE", "dot": "orange"},
            "sustainable":  {"color": COLORS["green"],   "label": "SOSTENIBLE",    "dot": "green"},
        }
        country_names = {
            "JPN": "Japón 🇯🇵", "DEU": "Alemania 🇩🇪", "ESP": "España 🇪🇸",
            "ITA": "Italia 🇮🇹", "FRA": "Francia 🇫🇷", "USA": "EE.UU. 🇺🇸",
            "CHN": "China 🇨🇳", "SWE": "Suecia 🇸🇪",
        }

        cards = []
        for iso, info in countries.items():
            cfg = level_config.get(info.get("level", "moderate"), level_config["moderate"])
            dot_color = cfg["color"]
            cards.append(
                dbc.Col(html.Div([
                    html.Div([
                        html.Div(style={
                            "width": "10px", "height": "10px",
                            "borderRadius": "50%",
                            "backgroundColor": dot_color,
                            "boxShadow": f"0 0 6px {dot_color}",
                            "flexShrink": "0",
                        }),
                        html.Span(country_names.get(iso, iso), style={
                            "fontWeight": "600", "fontSize": "0.88rem",
                            "color": COLORS["text"], "marginLeft": "8px",
                        }),
                        html.Span(cfg["label"], style={
                            "marginLeft": "auto",
                            "fontSize": "0.68rem",
                            "backgroundColor": _rgba(dot_color, 0.15),
                            "color": dot_color,
                            "border": f"1px solid {dot_color}",
                            "borderRadius": "4px",
                            "padding": "2px 6px",
                            "fontWeight": "600",
                        }),
                    ], style={"display": "flex", "alignItems": "center", "marginBottom": "8px"}),
                    html.Div([
                        html.Span("Dependencia: ", style={"color": COLORS["text_muted"], "fontSize": "0.78rem"}),
                        html.Span(f"{info.get('dependency_ratio', '?')}%",
                                  style={"fontWeight": "600", "color": COLORS["text"], "fontSize": "0.82rem"}),
                        html.Span("  |  Jubilación: ", style={"color": COLORS["text_muted"], "fontSize": "0.78rem"}),
                        html.Span(f"{info.get('retirement_age', '?')} años",
                                  style={"fontWeight": "600", "color": COLORS["text"], "fontSize": "0.82rem"}),
                        html.Span("  |  Tasa reemplazo: ", style={"color": COLORS["text_muted"], "fontSize": "0.78rem"}),
                        html.Span(f"{info.get('replacement_rate_pct', '?')}%",
                                  style={"fontWeight": "600", "color": COLORS["accent"], "fontSize": "0.82rem"}),
                    ], style={"marginBottom": "6px"}),
                    html.Div(info.get("notes", ""), style={
                        "fontSize": "0.75rem", "color": COLORS["text_muted"],
                        "fontStyle": "italic", "lineHeight": "1.5",
                    }),
                ], style={
                    "backgroundColor": COLORS["card_bg"],
                    "border": f"1px solid {COLORS['border']}",
                    "borderLeft": f"3px solid {dot_color}",
                    "borderRadius": "6px",
                    "padding": "12px 14px",
                    "height": "100%",
                }), width=6)
            )

        return dbc.Row(cards, className="g-2")

    @app.callback(
        Output("m13-labor-force-chart", "figure"),
        Input("m13-tabs", "value"),
        Input("m13-interval", "n_intervals"),
    )
    def update_labor_force(tab, _n):
        if tab != "tab-2":
            return go.Figure()

        dep_data = _load_json("dependency_projections.json")
        ratios = dep_data.get("old_age_dependency_ratio", {})

        layout = get_base_layout(height=265)
        layout.update(
            title=dict(text="Ratio de Dependencia (proxy presión fuerza laboral)", font=dict(size=12)),
            yaxis_title="Ancianos por 100 activos",
            margin=dict(l=55, r=15, t=40, b=45),
            hovermode="x unified",
        )
        fig = go.Figure(layout=layout)

        for iso in ["JPN", "DEU", "ESP", "CHN", "IND"]:
            if iso not in ratios:
                continue
            color = _COUNTRY_COLORS.get(iso, "#9ca3af")
            country_names = {"JPN": "Japón", "DEU": "Alemania", "ESP": "España",
                             "CHN": "China", "IND": "India"}
            d = ratios[iso]
            years = sorted([int(y) for y in d])
            vals = [d[str(y)] for y in years]
            fig.add_trace(go.Scatter(
                x=years, y=vals, name=country_names.get(iso, iso),
                mode="lines+markers",
                line=dict(color=color, width=2),
                marker=dict(size=4),
                hovertemplate=f"{country_names.get(iso, iso)}: %{{y:.0f}}<extra></extra>",
            ))
        return fig

    @app.callback(
        Output("m13-migration-chart", "figure"),
        Input("m13-tabs", "value"),
        Input("m13-interval", "n_intervals"),
    )
    def update_migration(tab, _n):
        if tab != "tab-2":
            return go.Figure()

        layout = get_base_layout(height=265)
        layout.update(
            title=dict(text="Migración Neta — Principales Receptores y Emisores (estimación)", font=dict(size=12)),
            yaxis_title="Millones de personas",
            margin=dict(l=55, r=15, t=40, b=45),
            hovermode="x unified",
        )
        fig = go.Figure(layout=layout)

        # Intentar datos de BD
        countries_recv = {"USA": "EE.UU.", "DEU": "Alemania", "ESP": "España", "AUS": "Australia"}
        countries_emit = {"MEX": "México", "IND": "India", "SYR": "Siria", "VEN": "Venezuela"}
        has_data = False

        for iso, name in {**countries_recv, **countries_emit}.items():
            s = get_series(f"wb_sm_pop_netm_{iso.lower()}", days=9000)
            if s is not None and not s.empty:
                import pandas as pd
                s["timestamp"] = pd.to_datetime(s["timestamp"])
                fig.add_trace(go.Bar(
                    x=s["timestamp"], y=s["value"] / 1e6,
                    name=name,
                    hovertemplate=f"{name}: %{{y:.2f}}M<extra></extra>",
                ))
                has_data = True

        if not has_data:
            # Fallback estático
            static = {
                "EE.UU.":    {"years": [2000, 2005, 2010, 2015, 2020], "vals": [1.23, 1.02, 0.98, 1.18, 0.89], "color": "#3b82f6"},
                "Alemania":  {"years": [2000, 2005, 2010, 2015, 2020], "vals": [0.35, 0.15, 0.29, 1.14, 0.56], "color": "#10b981"},
                "España":    {"years": [2000, 2005, 2010, 2015, 2020], "vals": [0.53, 0.78, -0.05, 0.22, 0.31], "color": "#f59e0b"},
                "México":    {"years": [2000, 2005, 2010, 2015, 2020], "vals": [-0.39, -0.45, -0.38, -0.30, -0.25], "color": "#ef4444"},
                "India":     {"years": [2000, 2005, 2010, 2015, 2020], "vals": [-0.51, -0.49, -0.48, -0.45, -0.42], "color": "#84cc16"},
            }
            for name, info in static.items():
                fig.add_trace(go.Bar(
                    x=info["years"], y=info["vals"],
                    name=name,
                    marker_color=info["color"],
                    hovertemplate=f"{name}: %{{y:.2f}}M<extra></extra>",
                ))
            fig.add_annotation(
                text="Datos estimados — BD sin series de migración",
                xref="paper", yref="paper", x=0.01, y=1.05,
                showarrow=False, font=dict(size=9, color=COLORS["text_muted"]),
            )

        fig.add_hline(y=0, line_color="#374151", line_width=1)
        return fig

    # ═══════════════════════════════════════════════════════════════════════════
    # TAB 3 — PRODUCTIVIDAD
    # ═══════════════════════════════════════════════════════════════════════════

    @app.callback(
        Output("m13-productivity-chart", "figure"),
        Input("m13-tabs", "value"),
        Input("m13-interval", "n_intervals"),
    )
    def update_productivity(tab, _n):
        if tab != "tab-3":
            return go.Figure()

        layout = get_base_layout(height=285)
        layout.update(
            title=dict(text="PIB per cápita real (proxy productividad) — variación YoY %", font=dict(size=12)),
            yaxis_title="Variación YoY (%)",
            margin=dict(l=55, r=15, t=40, b=45),
            hovermode="x unified",
        )
        fig = go.Figure(layout=layout)

        # Datos estáticos de crecimiento PIB per cápita como proxy productividad
        static_prod = {
            "USA": {
                "name": "EE.UU.", "color": "#3b82f6",
                "data": {1990: 1.6, 1995: 2.2, 2000: 3.8, 2005: 2.1, 2007: 1.0,
                         2008: -1.1, 2009: -4.3, 2010: 2.1, 2015: 2.5, 2018: 2.5,
                         2019: 2.1, 2020: -3.8, 2021: 5.3, 2022: 1.9, 2023: 2.5, 2024: 2.6},
            },
            "DEU": {
                "name": "Alemania", "color": "#10b981",
                "data": {1990: 5.3, 1995: 1.6, 2000: 3.0, 2005: 0.7, 2007: 3.0,
                         2008: 0.9, 2009: -5.8, 2010: 3.9, 2015: 1.5, 2018: 1.2,
                         2019: 0.6, 2020: -4.2, 2021: 2.6, 2022: 1.4, 2023: -0.3, 2024: -0.2},
            },
            "CHN": {
                "name": "China", "color": "#f97316",
                "data": {1990: 3.2, 1995: 10.0, 2000: 8.2, 2005: 10.5, 2007: 13.6,
                         2008: 8.8, 2009: 8.5, 2010: 9.7, 2015: 6.3, 2018: 6.1,
                         2019: 5.6, 2020: 2.0, 2021: 7.9, 2022: 2.5, 2023: 5.0, 2024: 4.7},
            },
            "JPN": {
                "name": "Japón", "color": "#ec4899",
                "data": {1990: 4.6, 1995: 2.1, 2000: 2.3, 2005: 1.3, 2007: 1.8,
                         2008: -1.4, 2009: -5.8, 2010: 3.9, 2015: 0.7, 2018: 0.5,
                         2019: -0.7, 2020: -4.1, 2021: 2.1, 2022: 0.9, 2023: 1.9, 2024: 0.1},
            },
        }

        for iso, info in static_prod.items():
            years = sorted(info["data"].keys())
            vals = [info["data"][y] for y in years]
            fig.add_trace(go.Scatter(
                x=years, y=vals, name=info["name"],
                mode="lines", line=dict(color=info["color"], width=2),
                hovertemplate=f"{info['name']}: %{{y:.1f}}%<extra></extra>",
            ))

        fig.add_hline(y=0, line_color="#374151", line_width=1)
        # "Gran Estancamiento" anotación
        fig.add_vrect(x0=2005, x1=2024, fillcolor="#374151", opacity=0.08,
                      annotation_text="El Gran Estancamiento (~2005+)",
                      annotation_position="top left",
                      annotation_font_size=9, annotation_font_color="#9ca3af")
        return fig

    @app.callback(
        Output("m13-rd-bar-chart", "figure"),
        Input("m13-tabs", "value"),
        Input("m13-interval", "n_intervals"),
    )
    def update_rd_bar(tab, _n):
        if tab != "tab-3":
            return go.Figure()

        # Datos de I+D estáticos (World Bank último año disponible)
        rd_static = [
            ("Corea del Sur", 4.93, "#ec4899"),
            ("Israel", 4.81, "#ef4444"),
            ("Suecia", 3.40, "#8b5cf6"),
            ("Japón", 3.26, "#ec4899"),
            ("EE.UU.", 3.46, "#3b82f6"),
            ("Alemania", 3.13, "#10b981"),
            ("China", 2.55, "#f97316"),
            ("Francia", 2.22, "#8b5cf6"),
            ("Países Bajos", 2.28, "#06b6d4"),
            ("UE (media)", 2.09, "#9ca3af"),
            ("España", 1.44, "#f59e0b"),
            ("Italia", 1.33, "#ef4444"),
        ]

        layout = get_base_layout(height=265)
        layout.update(
            title=dict(text="Gasto en I+D (% del PIB, último año disponible)", font=dict(size=12)),
            xaxis_title="% del PIB",
            margin=dict(l=130, r=55, t=40, b=35),
            showlegend=False,
        )
        fig = go.Figure(layout=layout)

        names = [r[0] for r in rd_static]
        vals = [r[1] for r in rd_static]
        colors = [r[2] for r in rd_static]

        fig.add_trace(go.Bar(
            x=vals, y=names,
            orientation="h",
            marker_color=colors,
            text=[f"{v:.2f}%" for v in vals],
            textposition="outside",
            textfont=dict(size=10, color=COLORS["text_muted"]),
            hovertemplate="<b>%{y}</b>: %{x:.2f}% del PIB<extra></extra>",
        ))
        fig.update_yaxes(autorange="reversed")
        return fig

    @app.callback(
        Output("m13-rd-trend-chart", "figure"),
        Input("m13-tabs", "value"),
        Input("m13-interval", "n_intervals"),
    )
    def update_rd_trend(tab, _n):
        if tab != "tab-3":
            return go.Figure()

        layout = get_base_layout(height=265)
        layout.update(
            title=dict(text="Evolución I+D (% PIB) — EE.UU., China, UE", font=dict(size=12)),
            yaxis_title="% del PIB",
            margin=dict(l=55, r=15, t=40, b=45),
            hovermode="x unified",
        )
        fig = go.Figure(layout=layout)

        rd_trends = {
            "USA": {
                "name": "EE.UU.", "color": "#3b82f6",
                "data": {2000: 2.62, 2005: 2.51, 2010: 2.74, 2015: 2.72, 2018: 2.83, 2020: 3.43, 2022: 3.46},
            },
            "CHN": {
                "name": "China", "color": "#f97316",
                "data": {2000: 0.90, 2005: 1.32, 2010: 1.76, 2015: 2.07, 2018: 2.19, 2020: 2.40, 2022: 2.55},
            },
            "EU": {
                "name": "UE", "color": "#8b5cf6",
                "data": {2000: 1.74, 2005: 1.74, 2010: 1.93, 2015: 2.04, 2018: 2.19, 2020: 2.30, 2022: 2.09},
            },
        }

        for iso, info in rd_trends.items():
            years = sorted(info["data"].keys())
            vals = [info["data"][y] for y in years]
            fig.add_trace(go.Scatter(
                x=years, y=vals, name=info["name"],
                mode="lines+markers",
                line=dict(color=info["color"], width=2.5),
                marker=dict(size=6),
                hovertemplate=f"{info['name']}: %{{y:.2f}}%<extra></extra>",
            ))
        return fig

    @app.callback(
        Output("m13-ai-estimates-chart", "figure"),
        Input("m13-tabs", "value"),
    )
    def update_ai_estimates(tab):
        if tab != "tab-3":
            return go.Figure()

        ai_data = _load_json("ai_productivity_estimates.json")
        estimates = ai_data.get("estimates", [])

        layout = get_base_layout(height=245)
        layout.update(
            title=dict(text="Impacto IA en PIB global — estimaciones institucionales (%)", font=dict(size=12)),
            xaxis_title="% del PIB (10 años)",
            margin=dict(l=165, r=55, t=40, b=35),
            showlegend=False,
        )
        fig = go.Figure(layout=layout)

        confidence_colors = {"high": "#10b981", "medium": "#f59e0b", "low": "#9ca3af"}
        if estimates:
            names = [e["institution"] for e in estimates]
            vals = [e["gdp_impact_pct"] for e in estimates]
            colors = [confidence_colors.get(e.get("confidence", "medium"), "#9ca3af") for e in estimates]
            # Ordenar de menor a mayor
            paired = sorted(zip(vals, names, colors))
            vals = [p[0] for p in paired]
            names = [p[1] for p in paired]
            colors = [p[2] for p in paired]

            fig.add_trace(go.Bar(
                x=vals, y=names,
                orientation="h",
                marker_color=colors,
                text=[f"+{v:.1f}%" for v in vals],
                textposition="outside",
                textfont=dict(size=10),
                hovertemplate="<b>%{y}</b>: +%{x:.1f}% PIB<extra></extra>",
            ))
        return fig

    @app.callback(
        Output("m13-ai-sectors-chart", "figure"),
        Input("m13-tabs", "value"),
    )
    def update_ai_sectors(tab):
        if tab != "tab-3":
            return go.Figure()

        ai_data = _load_json("ai_sector_impact.json")
        sectors = ai_data.get("sector_impacts", [])

        layout = get_base_layout(height=245)
        layout.update(
            title=dict(text="Impacto IA por sector — mejora de productividad medida (%)", font=dict(size=12)),
            xaxis_title="% de mejora",
            margin=dict(l=175, r=55, t=40, b=35),
            showlegend=False,
        )
        fig = go.Figure(layout=layout)

        confidence_colors = {"high": "#3b82f6", "medium": "#8b5cf6", "low": "#9ca3af"}
        if sectors:
            paired = sorted([(s["impact_pct"], s["sector"], confidence_colors.get(s.get("confidence", "medium"), "#9ca3af")) for s in sectors])
            vals = [p[0] for p in paired]
            names = [p[1] for p in paired]
            colors = [p[2] for p in paired]

            fig.add_trace(go.Bar(
                x=vals, y=names,
                orientation="h",
                marker_color=colors,
                text=[f"+{v}%" for v in vals],
                textposition="outside",
                textfont=dict(size=10),
                hovertemplate="<b>%{y}</b>: +%{x}%<extra></extra>",
            ))
        return fig

    @app.callback(
        Output("m13-education-scatter", "figure"),
        Input("m13-tabs", "value"),
        Input("m13-interval", "n_intervals"),
    )
    def update_education_scatter(tab, _n):
        if tab != "tab-3":
            return go.Figure()

        # Datos estáticos de matriculación terciaria vs PIB per cápita
        education_data = [
            ("EE.UU.", "USA", 88, 76000, 335),
            ("Alemania", "DEU", 72, 52000, 84),
            ("España", "ESP", 93, 31000, 47),
            ("Francia", "FRA", 68, 43000, 67),
            ("Reino Unido", "GBR", 60, 45000, 67),
            ("Japón", "JPN", 64, 39000, 125),
            ("Corea del Sur", "KOR", 99, 33000, 51),
            ("China", "CHN", 60, 12000, 1411),
            ("India", "IND", 28, 2300, 1428),
            ("Brasil", "BRA", 52, 8900, 215),
            ("México", "MEX", 40, 10000, 126),
            ("Nigeria", "NGA", 10, 2100, 220),
            ("Suecia", "SWE", 77, 55000, 10),
            ("Australia", "AUS", 110, 55000, 26),
            ("Israel", "ISR", 71, 43000, 9),
            ("Argentina", "ARG", 91, 10500, 45),
        ]

        layout = get_base_layout(height=285)
        layout.update(
            title=dict(text="Educación Terciaria vs PIB per cápita (PPP)", font=dict(size=12)),
            xaxis_title="Matriculación educación terciaria (%)",
            yaxis_title="PIB per cápita PPP (USD)",
            margin=dict(l=65, r=15, t=40, b=55),
            showlegend=False,
            hovermode="closest",
        )
        fig = go.Figure(layout=layout)

        names = [d[0] for d in education_data]
        enroll = [d[2] for d in education_data]
        gdp = [d[3] for d in education_data]
        pop = [d[4] for d in education_data]

        fig.add_trace(go.Scatter(
            x=enroll, y=gdp,
            mode="markers+text",
            marker=dict(
                size=[max(10, min(40, p ** 0.4)) for p in pop],
                color=gdp,
                colorscale="Blues",
                showscale=False,
                line=dict(color="#374151", width=0.5),
                opacity=0.85,
            ),
            text=names,
            textposition="top center",
            textfont=dict(size=9, color=COLORS["text_muted"]),
            hovertemplate="<b>%{text}</b><br>Matric.: %{x:.0f}%<br>PIB p.c.: $%{y:,.0f}<extra></extra>",
        ))
        return fig

    # ═══════════════════════════════════════════════════════════════════════════
    # TAB 4 — DESIGUALDAD
    # ═══════════════════════════════════════════════════════════════════════════

    @app.callback(
        Output("m13-gini-bar-chart", "figure"),
        Input("m13-tabs", "value"),
        Input("m13-interval", "n_intervals"),
    )
    def update_gini_bar(tab, _n):
        if tab != "tab-4":
            return go.Figure()

        # Intentar BD
        gini_static = [
            ("Sudáfrica", 63.0),
            ("Brasil", 52.9),
            ("Colombia", 51.3),
            ("México", 45.4),
            ("EE.UU.", 41.1),
            ("China", 38.2),
            ("Italia", 35.9),
            ("Reino Unido", 35.1),
            ("España", 33.0),
            ("Francia", 31.5),
            ("Alemania", 31.7),
            ("Japón", 32.9),
            ("Suecia", 27.6),
            ("Noruega", 26.1),
            ("Dinamarca", 28.2),
        ]

        layout = get_base_layout(height=305)
        layout.update(
            title=dict(text="Índice de Gini — Desigualdad de ingresos por país (0=igual, 100=máxima)", font=dict(size=12)),
            xaxis_title="Índice de Gini",
            margin=dict(l=110, r=55, t=40, b=35),
            showlegend=False,
        )
        fig = go.Figure(layout=layout)

        names = [d[0] for d in gini_static]
        vals = [d[1] for d in gini_static]

        def _gini_color(v):
            if v < 30:
                return "#10b981"
            if v < 40:
                return "#f59e0b"
            if v < 50:
                return "#f97316"
            return "#ef4444"

        colors = [_gini_color(v) for v in vals]

        fig.add_trace(go.Bar(
            x=vals, y=names,
            orientation="h",
            marker_color=colors,
            text=[f"{v:.1f}" for v in vals],
            textposition="outside",
            textfont=dict(size=10),
            hovertemplate="<b>%{y}</b>: Gini %{x:.1f}<extra></extra>",
        ))
        fig.update_yaxes(autorange="reversed")

        # Líneas de referencia
        fig.add_vline(x=30, line_color="#10b981", line_width=1, line_dash="dot",
                      annotation_text="30", annotation_font_size=8)
        fig.add_vline(x=40, line_color="#f59e0b", line_width=1, line_dash="dot",
                      annotation_text="40", annotation_font_size=8)
        fig.add_vline(x=50, line_color="#ef4444", line_width=1, line_dash="dot",
                      annotation_text="50", annotation_font_size=8)
        return fig

    @app.callback(
        Output("m13-gini-trend-chart", "figure"),
        Input("m13-tabs", "value"),
        Input("m13-interval", "n_intervals"),
    )
    def update_gini_trend(tab, _n):
        if tab != "tab-4":
            return go.Figure()

        layout = get_base_layout(height=305)
        layout.update(
            title=dict(text="Evolución del Gini desde 1990", font=dict(size=12)),
            yaxis_title="Índice de Gini",
            margin=dict(l=55, r=15, t=40, b=45),
            hovermode="x unified",
        )
        fig = go.Figure(layout=layout)

        gini_trends = {
            "USA": {"name": "EE.UU.", "color": "#3b82f6",
                    "data": {1990: 37.8, 1995: 38.5, 2000: 39.4, 2005: 40.1, 2010: 39.8, 2015: 41.0, 2020: 41.1, 2023: 41.1}},
            "CHN": {"name": "China", "color": "#f97316",
                    "data": {1990: 32.4, 1995: 37.4, 2000: 40.7, 2005: 42.6, 2010: 42.1, 2015: 39.5, 2020: 38.2, 2023: 38.2}},
            "ESP": {"name": "España", "color": "#f59e0b",
                    "data": {1990: 30.9, 1995: 33.9, 2000: 33.0, 2005: 32.2, 2010: 33.4, 2015: 34.5, 2020: 32.0, 2023: 33.0}},
            "BRA": {"name": "Brasil", "color": "#14b8a6",
                    "data": {1990: 60.5, 1995: 59.6, 2000: 58.9, 2005: 56.5, 2010: 53.0, 2015: 51.3, 2020: 48.9, 2023: 52.9}},
        }

        for iso, info in gini_trends.items():
            years = sorted(info["data"].keys())
            vals = [info["data"][y] for y in years]
            fig.add_trace(go.Scatter(
                x=years, y=vals, name=info["name"],
                mode="lines+markers",
                line=dict(color=info["color"], width=2),
                marker=dict(size=5),
                hovertemplate=f"{info['name']}: Gini %{{y:.1f}}<extra></extra>",
            ))
        return fig

    @app.callback(
        Output("m13-wage-divergence-chart", "figure"),
        Input("m13-tabs", "value"),
    )
    def update_wage_divergence(tab):
        if tab != "tab-4":
            return go.Figure()

        div_data = _load_json("productivity_wages_divergence.json")
        data = div_data.get("data", {})

        layout = get_base_layout(height=285)
        layout.update(
            title=dict(text="EE.UU.: Productividad vs Salarios (Índice 100 = 1979)", font=dict(size=12)),
            yaxis_title="Índice (base 100 = 1979)",
            margin=dict(l=55, r=15, t=40, b=45),
            hovermode="x unified",
        )
        fig = go.Figure(layout=layout)

        years = sorted([int(y) for y in data.keys()])
        prod = [data[str(y)]["productivity"] for y in years]
        workers = [data[str(y)]["median_worker"] for y in years]
        top1 = [data[str(y)]["top_1pct"] for y in years]

        fig.add_trace(go.Scatter(
            x=years, y=prod, name="Productividad laboral",
            mode="lines", line=dict(color="#3b82f6", width=2.5),
            hovertemplate="Productividad: %{y:.0f}<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=years, y=workers, name="Salario real trabajador medio",
            mode="lines", line=dict(color="#10b981", width=2.5),
            hovertemplate="Salario medio: %{y:.0f}<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=years, y=top1, name="Compensación total 1% más rico",
            mode="lines", line=dict(color="#ef4444", width=2.5),
            hovertemplate="Top 1%%: %{y:.0f}<extra></extra>",
        ))

        # Relleno entre productividad y salario
        fig.add_trace(go.Scatter(
            x=years + years[::-1],
            y=prod + workers[::-1],
            fill="toself",
            fillcolor=_rgba("#ef4444", 0.08),
            line=dict(color="rgba(0,0,0,0)"),
            showlegend=False, hoverinfo="skip",
            name="Brecha",
        ))

        fig.add_hline(y=100, line_color="#374151", line_width=1)
        fig.add_annotation(
            x=2024, y=256,
            text="+156%",
            showarrow=False, font=dict(size=10, color="#3b82f6"),
        )
        fig.add_annotation(
            x=2024, y=138,
            text="+38%",
            showarrow=False, font=dict(size=10, color="#10b981"),
        )
        return fig

    @app.callback(
        Output("m13-populism-scatter", "figure"),
        Input("m13-tabs", "value"),
    )
    def update_populism(tab):
        if tab != "tab-4":
            return go.Figure()

        pop_data = _load_json("populism_index.json")
        scores = pop_data.get("populism_score_0_to_10", {})

        # Gini estático para cruce
        gini_map = {
            "USA": 41.1, "HUN": 30.5, "TUR": 41.9, "ITA": 35.9,
            "FRA": 31.5, "DEU": 31.7, "ESP": 33.0, "GBR": 35.1,
            "BRA": 52.9, "ARG": 42.3, "MEX": 45.4, "IND": 35.7,
            "POL": 30.2, "SWE": 27.6, "NOR": 26.1, "JPN": 32.9,
        }
        country_labels = {
            "USA": "EE.UU.", "HUN": "Hungría", "TUR": "Turquía", "ITA": "Italia",
            "FRA": "Francia", "DEU": "Alemania", "ESP": "España", "GBR": "Reino Unido",
            "BRA": "Brasil", "ARG": "Argentina", "MEX": "México", "IND": "India",
            "POL": "Polonia", "SWE": "Suecia", "NOR": "Noruega", "JPN": "Japón",
        }

        layout = get_base_layout(height=285)
        layout.update(
            title=dict(text="Desigualdad (Gini) vs Índice de Populismo", font=dict(size=12)),
            xaxis_title="Índice de Gini",
            yaxis_title="Índice de populismo (0-10)",
            margin=dict(l=55, r=15, t=40, b=55),
            showlegend=False,
            hovermode="closest",
        )
        fig = go.Figure(layout=layout)

        xs, ys, labels = [], [], []
        for iso, score in scores.items():
            if iso in gini_map:
                xs.append(gini_map[iso])
                ys.append(score)
                labels.append(country_labels.get(iso, iso))

        fig.add_trace(go.Scatter(
            x=xs, y=ys,
            mode="markers+text",
            marker=dict(
                size=12,
                color=ys,
                colorscale="RdYlGn_r",
                showscale=True,
                colorbar=dict(title="Populismo", thickness=12, len=0.7),
            ),
            text=labels,
            textposition="top center",
            textfont=dict(size=9, color=COLORS["text_muted"]),
            hovertemplate="<b>%{text}</b><br>Gini: %{x:.1f}<br>Populismo: %{y:.1f}/10<extra></extra>",
        ))
        return fig

    # ═══════════════════════════════════════════════════════════════════════════
    # TAB 5 — TENDENCIAS DISRUPTIVAS
    # ═══════════════════════════════════════════════════════════════════════════

    @app.callback(
        Output("m13-ai-impact-tab5", "figure"),
        Input("m13-tabs", "value"),
    )
    def update_ai_impact_tab5(tab):
        if tab != "tab-5":
            return go.Figure()

        ai_data = _load_json("ai_sector_impact.json")
        sectors = ai_data.get("sector_impacts", [])

        layout = get_base_layout(height=225)
        layout.update(
            title=dict(text="Impacto medido de la IA por sector (%)", font=dict(size=12)),
            xaxis_title="% mejora productividad",
            margin=dict(l=175, r=55, t=40, b=35),
            showlegend=False,
        )
        fig = go.Figure(layout=layout)

        if sectors:
            paired = sorted([(s["impact_pct"], s["sector"]) for s in sectors])
            vals = [p[0] for p in paired]
            names = [p[1] for p in paired]
            fig.add_trace(go.Bar(
                x=vals, y=names, orientation="h",
                marker_color=["#3b82f6" if v > 40 else "#8b5cf6" if v > 25 else "#9ca3af" for v in vals],
                text=[f"+{v}%" for v in vals],
                textposition="outside",
                textfont=dict(size=10),
                hovertemplate="<b>%{y}</b>: +%{x}%<extra></extra>",
            ))
        return fig

    @app.callback(
        Output("m13-urbanization-chart", "figure"),
        Input("m13-tabs", "value"),
    )
    def update_urbanization(tab):
        if tab != "tab-5":
            return go.Figure()

        layout = get_base_layout(height=225)
        layout.update(
            title=dict(text="Tasa de Urbanización por región (%)", font=dict(size=12)),
            yaxis_title="% población urbana",
            margin=dict(l=55, r=15, t=40, b=45),
            hovermode="x unified",
        )
        fig = go.Figure(layout=layout)

        urban_data = {
            "Mundo": {
                "color": "#9ca3af",
                "data": {1960: 33.6, 1980: 39.4, 2000: 46.7, 2010: 51.6, 2020: 56.2, 2025: 57.5, 2050: 68.0},
            },
            "África": {
                "color": "#14b8a6",
                "data": {1960: 18.5, 1980: 27.3, 2000: 35.9, 2010: 39.5, 2020: 43.5, 2025: 45.5, 2050: 59.0},
            },
            "Asia": {
                "color": "#f97316",
                "data": {1960: 20.3, 1980: 26.5, 2000: 36.9, 2010: 44.0, 2020: 51.1, 2025: 53.5, 2050: 66.0},
            },
            "Europa": {
                "color": "#8b5cf6",
                "data": {1960: 57.1, 1980: 67.7, 2000: 71.1, 2010: 72.8, 2020: 74.5, 2025: 75.2, 2050: 80.0},
            },
            "América del Norte": {
                "color": "#3b82f6",
                "data": {1960: 69.9, 1980: 73.8, 2000: 79.1, 2010: 81.8, 2020: 82.6, 2025: 83.5, 2050: 87.0},
            },
        }

        for region, info in urban_data.items():
            years = sorted([int(y) for y in info["data"]])
            vals = [info["data"][y] for y in years]
            hist_y = [y for y in years if y <= 2025]
            hist_v = [info["data"][y] for y in hist_y]
            proj_y = [y for y in years if y >= 2025]
            proj_v = [info["data"][y] for y in proj_y]

            fig.add_trace(go.Scatter(
                x=hist_y, y=hist_v, name=region,
                mode="lines",
                line=dict(color=info["color"], width=2),
                legendgroup=region,
                hovertemplate=f"{region}: %{{y:.1f}}%<extra></extra>",
            ))
            if proj_y:
                fig.add_trace(go.Scatter(
                    x=proj_y, y=proj_v, name=f"{region} proj.",
                    mode="lines",
                    line=dict(color=info["color"], width=2, dash="dot"),
                    legendgroup=region, showlegend=False,
                    hovertemplate=f"{region}: %{{y:.1f}}%<extra></extra>",
                ))
        fig.add_vline(x=2026, line_color="#9ca3af", line_width=1, line_dash="dot",
                      annotation_text="Hoy", annotation_font_size=9,
                      annotation_font_color="#9ca3af")
        return fig

    @app.callback(
        Output("m13-climate-chart", "figure"),
        Input("m13-tabs", "value"),
    )
    def update_climate(tab):
        if tab != "tab-5":
            return go.Figure()

        climate = _load_json("climate_economic_risk.json")
        scenarios = climate.get("gdp_loss_scenarios", {})

        layout = get_base_layout(height=225)
        layout.update(
            title=dict(text="Pérdida de PIB global estimada por escenario climático (%)", font=dict(size=12)),
            xaxis_title="% pérdida del PIB global",
            margin=dict(l=100, r=55, t=40, b=35),
            showlegend=False,
        )
        fig = go.Figure(layout=layout)

        scenario_labels = {
            "+2C_2050": "+2°C (2050)",
            "+3C_2100": "+3°C (2100)",
            "+4C_2100": "+4°C (2100)",
        }
        scenario_colors = {
            "+2C_2050": "#f59e0b",
            "+3C_2100": "#f97316",
            "+4C_2100": "#ef4444",
        }

        if scenarios:
            names = [scenario_labels.get(k, k) for k in scenarios]
            vals = [abs(v) for v in scenarios.values()]
            colors = [scenario_colors.get(k, "#9ca3af") for k in scenarios]
            fig.add_trace(go.Bar(
                x=vals, y=names,
                orientation="h",
                marker_color=colors,
                text=[f"-{v:.0f}%" for v in vals],
                textposition="outside",
                textfont=dict(size=11, color=COLORS["text"]),
                hovertemplate="<b>%{y}</b>: -%{x:.0f}% PIB global<extra></extra>",
            ))
        return fig
