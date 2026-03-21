"""
Configuración visual estándar de Plotly para World Monitor.
Importar PLOTLY_THEME, COLORS, COUNTRY_COLORS, get_base_layout(),
get_time_range_buttons() en todos los módulos que generen gráficos.
"""

# ── Colores estándar ──────────────────────────────────────────────────────────

COLORS = {
    "primary":  "#3b82f6",
    "positive": "#10b981",
    "negative": "#ef4444",
    "warning":  "#f59e0b",
    "neutral":  "#9ca3af",
    "gold":     "#f59e0b",
    "silver":   "#9ca3af",
    "bitcoin":  "#f7931a",
    "orange":   "#f97316",
}

COUNTRY_COLORS = {
    "USA": "#3b82f6",
    "DEU": "#10b981",
    "FRA": "#8b5cf6",
    "ESP": "#f59e0b",
    "ITA": "#ef4444",
    "GBR": "#06b6d4",
    "JPN": "#ec4899",
    "CHN": "#f97316",
    "IND": "#84cc16",
    "BRA": "#14b8a6",
}

# ── Layout base de Plotly ─────────────────────────────────────────────────────

PLOTLY_THEME = {
    "paper_bgcolor": "#0a0e1a",
    "plot_bgcolor":  "#111827",
    "font": {
        "color":  "#e5e7eb",
        "family": "'Inter', 'Segoe UI', system-ui, sans-serif",
        "size":   12,
    },
    "xaxis": {
        "gridcolor":     "#1f2937",
        "zerolinecolor": "#374151",
        "linecolor":     "#1f2937",
        "tickcolor":     "#6b7280",
        "tickfont":      {"color": "#9ca3af", "size": 11},
        "title":         {"font": {"color": "#9ca3af", "size": 11}},
    },
    "yaxis": {
        "gridcolor":     "#1f2937",
        "zerolinecolor": "#374151",
        "linecolor":     "#1f2937",
        "tickcolor":     "#6b7280",
        "tickfont":      {"color": "#9ca3af", "size": 11},
        "title":         {"font": {"color": "#9ca3af", "size": 11}},
    },
    "legend": {
        "bgcolor":     "rgba(0,0,0,0)",
        "bordercolor": "#1f2937",
        "font":        {"color": "#9ca3af", "size": 11},
    },
    "margin": {"l": 50, "r": 20, "t": 40, "b": 40},
    "hovermode": "x unified",
    "hoverlabel": {
        "bgcolor":     "#1f2937",
        "bordercolor": "#374151",
        "font":        {"color": "#e5e7eb", "size": 12},
    },
}


def get_base_layout(title: str | None = None, height: int = 400) -> dict:
    """Devuelve un layout Plotly con el tema oscuro aplicado."""
    layout = {**PLOTLY_THEME, "height": height}
    if title:
        layout["title"] = {
            "text":    title,
            "font":    {"color": "#e5e7eb", "size": 13},
            "x":       0.0,
            "xanchor": "left",
            "pad":     {"l": 4},
        }
    return layout


def get_time_range_buttons() -> dict:
    """Configuración estándar de selectores de rango temporal para series."""
    return {
        "buttons": [
            {"count": 1,  "label": "1M", "step": "month", "stepmode": "backward"},
            {"count": 3,  "label": "3M", "step": "month", "stepmode": "backward"},
            {"count": 6,  "label": "6M", "step": "month", "stepmode": "backward"},
            {"count": 1,  "label": "1A", "step": "year",  "stepmode": "backward"},
            {"count": 5,  "label": "5A", "step": "year",  "stepmode": "backward"},
            {"step": "all", "label": "MÁX"},
        ],
        "bgcolor":        "#111827",
        "activecolor":    "#3b82f6",
        "bordercolor":    "#1f2937",
        "font":           {"color": "#9ca3af", "size": 11},
        "x":              0,
        "xanchor":        "left",
        "y":              1.08,
        "yanchor":        "top",
    }
