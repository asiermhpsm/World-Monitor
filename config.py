"""
Gestión centralizada de configuración.
Carga variables de entorno desde .env y expone constantes del proyecto.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Carga .env desde la raíz del proyecto
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


# ── API Keys ─────────────────────────────────────────────────────────────────

FRED_API_KEY = os.getenv("FRED_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")


# ── Base de datos ─────────────────────────────────────────────────────────────

DB_PATH = BASE_DIR / os.getenv("DB_FILENAME", "world_monitor.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"


# ── Dashboard ─────────────────────────────────────────────────────────────────

DASH_HOST = os.getenv("DASH_HOST", "127.0.0.1")
DASH_PORT = int(os.getenv("DASH_PORT", "8050"))
DASH_DEBUG = os.getenv("DASH_DEBUG", "false").lower() == "true"


# ── Colores del tema ──────────────────────────────────────────────────────────

COLORS = {
    "background":  "#0a0e1a",
    "card_bg":     "#111827",
    "border":      "#1f2937",
    "border_mid":  "#374151",
    "text":        "#e5e7eb",
    "text_muted":  "#9ca3af",
    "text_label":  "#6b7280",
    "accent":      "#3b82f6",
    # Semáforo de 5 niveles
    "green":       "#10b981",
    "green_yellow":"#84cc16",
    "yellow":      "#f59e0b",
    "orange":      "#f97316",
    "red":         "#ef4444",
}

PLOTLY_THEME = "plotly_dark"


# ── Frecuencias de actualización (segundos) ───────────────────────────────────

REFRESH_INTERVALS = {
    "yfinance_prices": 15 * 60,       # 15 minutos
    "coingecko": 5 * 60,              # 5 minutos
    "newsapi": 60 * 60,               # 1 hora
    "gdelt": 6 * 60 * 60,             # 6 horas
    "fred": 24 * 60 * 60,             # 24 horas
    "worldbank": 24 * 60 * 60,        # 24 horas
    "ecb": 24 * 60 * 60,              # 24 horas
    "eurostat": 24 * 60 * 60,         # 24 horas
}


# ── Regiones / Países cubiertos ───────────────────────────────────────────────

COUNTRIES = [
    "US", "EA", "DE", "FR", "ES", "IT", "GB",
    "CN", "JP", "IN", "BR", "MX", "RU",
]

COUNTRY_NAMES = {
    "US": "EE.UU.",
    "EA": "Eurozona",
    "DE": "Alemania",
    "FR": "Francia",
    "ES": "España",
    "IT": "Italia",
    "GB": "Reino Unido",
    "CN": "China",
    "JP": "Japón",
    "IN": "India",
    "BR": "Brasil",
    "MX": "México",
    "RU": "Rusia",
}


# ── Módulos del dashboard (sidebar) ──────────────────────────────────────────

MODULES = [
    {"id": "m01", "n": 1,  "emoji": "📊", "label": "Estado Global",          "path": "/module/1",  "section": "MERCADOS"},
    {"id": "m05", "n": 5,  "emoji": "📈", "label": "Mercados Financieros",   "path": "/module/5",  "section": "MERCADOS"},
    {"id": "m16", "n": 16, "emoji": "💹", "label": "Análisis de Mercados",   "path": "/module/16", "section": "MERCADOS"},
    {"id": "m02", "n": 2,  "emoji": "🌍", "label": "Macro Global",           "path": "/module/2",  "section": "MACRO"},
    {"id": "m03", "n": 3,  "emoji": "📉", "label": "Inflación",              "path": "/module/3",  "section": "MACRO"},
    {"id": "m04", "n": 4,  "emoji": "🏦", "label": "Política Monetaria",     "path": "/module/4",  "section": "MACRO"},
    {"id": "m06", "n": 6,  "emoji": "👷", "label": "Mercado Laboral",        "path": "/module/6",  "section": "MACRO"},
    {"id": "m07", "n": 7,  "emoji": "⚡", "label": "Energía y Mat. Primas",  "path": "/module/7",  "section": "MACRO"},
    {"id": "m08", "n": 8,  "emoji": "💰", "label": "Deuda y Fiscalidad",     "path": "/module/8",  "section": "MACRO"},
    {"id": "m09", "n": 9,  "emoji": "🏛️", "label": "Sistema Financiero",     "path": "/module/9",  "section": "RIESGO"},
    {"id": "m10", "n": 10, "emoji": "🌐", "label": "Geopolítica",            "path": "/module/10", "section": "RIESGO"},
    {"id": "m11", "n": 11, "emoji": "⚠️", "label": "Señales de Alerta",      "path": "/module/11", "section": "RIESGO"},
    {"id": "m12", "n": 12, "emoji": "🇨🇳", "label": "China",                  "path": "/module/12", "section": "RIESGO"},
    {"id": "m13", "n": 13, "emoji": "👥", "label": "Demografía",             "path": "/module/13", "section": "TENDENCIAS"},
    {"id": "m14", "n": 14, "emoji": "🕐", "label": "Histórico y Comparativas","path": "/module/14","section": "HERRAMIENTAS"},
    {"id": "m15", "n": 15, "emoji": "🤖", "label": "Análisis IA",            "path": "/module/15", "section": "HERRAMIENTAS"},
    {"id": "m17", "n": 17, "emoji": "⚙️", "label": "Configuración",          "path": "/module/17", "section": "HERRAMIENTAS"},
]

# Lookup rápido número → módulo
MODULE_BY_N = {m["n"]: m for m in MODULES}
