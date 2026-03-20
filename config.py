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
    "background": "#0a0a0a",
    "card_bg": "#1a1a1a",
    "border": "#2a2a2a",
    "text": "#e0e0e0",
    "text_muted": "#888888",
    "accent": "#00b4d8",
    # Semáforo de 5 niveles (consistente en todos los módulos)
    "green": "#00c853",
    "green_yellow": "#76ff03",
    "yellow": "#ffd600",
    "orange": "#ff6d00",
    "red": "#d50000",
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
    {"id": "m01", "label": "01 · Estado Global",               "path": "/"},
    {"id": "m02", "label": "02 · Macro Global",                "path": "/macro"},
    {"id": "m03", "label": "03 · Inflación",                   "path": "/inflacion"},
    {"id": "m04", "label": "04 · Política Monetaria",          "path": "/monetaria"},
    {"id": "m05", "label": "05 · Mercados Financieros",        "path": "/mercados"},
    {"id": "m06", "label": "06 · Mercado Laboral",             "path": "/laboral"},
    {"id": "m07", "label": "07 · Energía y Materias Primas",   "path": "/energia"},
    {"id": "m08", "label": "08 · Deuda y Sostenibilidad",      "path": "/deuda"},
    {"id": "m09", "label": "09 · Riesgo Sistémico",            "path": "/riesgo"},
    {"id": "m10", "label": "10 · Geopolítica",                 "path": "/geopolitica"},
    {"id": "m11", "label": "11 · Indicadores Adelantados",     "path": "/adelantados"},
    {"id": "m12", "label": "12 · China",                       "path": "/china"},
    {"id": "m13", "label": "13 · Demografía",                  "path": "/demografia"},
    {"id": "m14", "label": "14 · Histórico",                   "path": "/historico"},
    {"id": "m15", "label": "15 · Motor IA",                    "path": "/ia"},
    {"id": "m16", "label": "16 · Análisis de Mercados",        "path": "/analisis"},
    {"id": "m17", "label": "17 · Personalización",             "path": "/config"},
]
