"""
Colector de datos de Yahoo Finance (via librería yfinance).

No requiere API key. Alimenta los módulos: M05 (Mercados), M07 (Energía/Materias
Primas), M09 (Sistema Financiero), M16 (Análisis de Mercados).

Descarga ~111 tickers en 8 categorías: índices, divisas, materias primas,
renta fija ETFs, volatilidad, bancos, sectores y crypto.
Calcula métricas derivadas: retornos (1d/1w/1m/1y/YTD), distancia al ATH,
ratio oro/plata, ratio oro/Brent, spread Brent-WTI y ratio RSP/SPY (amplitud).
"""

import logging
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
import yfinance as yf
from sqlalchemy import func, insert

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collectors.base_collector import BaseCollector
from database.database import SessionLocal, TimeSeries

logger = logging.getLogger(__name__)

HISTORY_START    = "2000-01-01"
RATE_LIMIT_DELAY = 0.5   # segundos entre llamadas a Yahoo Finance
BATCH_SIZE       = 20    # tickers por llamada a yf.download()

# curl_cffi: impersonación de navegador para esquivar los filtros anti-bot de Yahoo Finance.
# Requerido desde ~2024. yfinance 1.x lo usa internamente en yf.download(); aquí lo
# exponemos explícitamente para yf.Ticker().history() (fallback individual).
try:
    from curl_cffi import requests as _curl_requests
    _CURL_SESSION = _curl_requests.Session(impersonate="chrome")
    logger.debug("curl_cffi disponible — usando impersonación Chrome.")
except Exception:
    _CURL_SESSION = None
    logger.debug("curl_cffi no disponible — usando requests estándar.")


# -- Catálogo de tickers -------------------------------------------------------

@dataclass
class TickerConfig:
    """Metadatos de un ticker de Yahoo Finance."""
    indicator_id: str       # Base del ID canónico en BD, ej: 'yf_sp500'
    name: str               # Nombre legible
    unit: str               # 'usd', 'eur', 'index', 'ratio', 'pct', etc.
    category: str           # 'equity_indices', 'forex', 'commodities', etc.
    subcategory: str        # Subcategoría más específica
    module: str             # Módulo del dashboard que consume el dato
    region: str             # Código de región/país
    fields: tuple           # Campos OHLCV a guardar: ('close',) o ('close','volume','high','low')


TICKER_CATALOG: dict[str, TickerConfig] = {

    # -- Categoría 1: Índices Bursátiles --------------------------------------
    "^GSPC":        TickerConfig("yf_sp500",         "S&P 500",                     "usd",   "equity_indices", "us",       "markets",          "US",     ("close","volume","high","low")),
    "^NDX":         TickerConfig("yf_ndx100",        "Nasdaq 100",                  "usd",   "equity_indices", "us",       "markets",          "US",     ("close","volume","high","low")),
    "^DJI":         TickerConfig("yf_dji",           "Dow Jones Industrial",        "usd",   "equity_indices", "us",       "markets",          "US",     ("close","volume","high","low")),
    "^RUT":         TickerConfig("yf_rut2000",       "Russell 2000",                "usd",   "equity_indices", "us",       "markets",          "US",     ("close","volume","high","low")),
    "^STOXX50E":    TickerConfig("yf_eurostoxx50",   "Eurostoxx 50",                "eur",   "equity_indices", "europe",   "markets",          "EA",     ("close","volume","high","low")),
    "^GDAXI":       TickerConfig("yf_dax",           "DAX",                         "eur",   "equity_indices", "europe",   "markets",          "DE",     ("close","volume","high","low")),
    "^FCHI":        TickerConfig("yf_cac40",         "CAC 40",                      "eur",   "equity_indices", "europe",   "markets",          "FR",     ("close","volume","high","low")),
    "^IBEX":        TickerConfig("yf_ibex35",        "IBEX 35",                     "eur",   "equity_indices", "europe",   "markets",          "ES",     ("close","volume","high","low")),
    "FTSEMIB.MI":   TickerConfig("yf_ftsemib",       "FTSE MIB Italia",             "eur",   "equity_indices", "europe",   "markets",          "IT",     ("close","volume","high","low")),
    "^FTSE":        TickerConfig("yf_ftse100",       "FTSE 100",                    "gbp",   "equity_indices", "europe",   "markets",          "GB",     ("close","volume","high","low")),
    "^SSMI":        TickerConfig("yf_smi",           "SMI Suiza",                   "chf",   "equity_indices", "europe",   "markets",          "CH",     ("close","volume","high","low")),
    "^N225":        TickerConfig("yf_nikkei225",     "Nikkei 225",                  "jpy",   "equity_indices", "asia",     "markets",          "JP",     ("close","volume","high","low")),
    "^HSI":         TickerConfig("yf_hangseng",      "Hang Seng",                   "hkd",   "equity_indices", "asia",     "markets",          "HK",     ("close","volume","high","low")),
    "000001.SS":    TickerConfig("yf_shanghai",      "Shanghai Composite",          "cny",   "equity_indices", "asia",     "markets",          "CN",     ("close","volume","high","low")),
    "000300.SS":    TickerConfig("yf_csi300",        "CSI 300",                     "cny",   "equity_indices", "asia",     "markets",          "CN",     ("close","volume","high","low")),
    "^BSESN":       TickerConfig("yf_sensex",        "Sensex India",                "inr",   "equity_indices", "asia",     "markets",          "IN",     ("close","volume","high","low")),
    "^BVSP":        TickerConfig("yf_bovespa",       "Bovespa Brasil",              "brl",   "equity_indices", "latam",    "markets",          "BR",     ("close","volume","high","low")),
    "^MXX":         TickerConfig("yf_ipc_mexico",    "IPC México",                  "mxn",   "equity_indices", "latam",    "markets",          "MX",     ("close","volume","high","low")),
    "URTH":         TickerConfig("yf_msci_world",    "MSCI World ETF",              "usd",   "equity_indices", "global",   "markets",          "GLOBAL", ("close","volume")),
    "EEM":          TickerConfig("yf_msci_em",       "MSCI Emerging Markets ETF",   "usd",   "equity_indices", "global",   "markets",          "GLOBAL", ("close","volume")),
    "MCHI":         TickerConfig("yf_msci_china",    "MSCI China ETF",              "usd",   "equity_indices", "asia",     "markets",          "CN",     ("close","volume")),

    # -- Categoría 2: Divisas --------------------------------------------------
    "DX-Y.NYB":     TickerConfig("yf_dxy",           "DXY Índice Dólar",            "index", "forex",          "dxy",      "markets",          "US",     ("close",)),
    "EURUSD=X":     TickerConfig("yf_eurusd",        "EUR/USD",                     "ratio", "forex",          "major",    "markets",          "EA",     ("close",)),
    "GBPUSD=X":     TickerConfig("yf_gbpusd",        "GBP/USD",                     "ratio", "forex",          "major",    "markets",          "GB",     ("close",)),
    "JPY=X":        TickerConfig("yf_usdjpy",        "USD/JPY",                     "ratio", "forex",          "major",    "markets",          "JP",     ("close",)),
    "CHF=X":        TickerConfig("yf_usdchf",        "USD/CHF",                     "ratio", "forex",          "major",    "markets",          "CH",     ("close",)),
    "AUDUSD=X":     TickerConfig("yf_audusd",        "AUD/USD",                     "ratio", "forex",          "major",    "markets",          "AU",     ("close",)),
    "CAD=X":        TickerConfig("yf_usdcad",        "USD/CAD",                     "ratio", "forex",          "major",    "markets",          "CA",     ("close",)),
    "CNY=X":        TickerConfig("yf_usdcny",        "USD/CNY",                     "ratio", "forex",          "em",       "markets",          "CN",     ("close",)),
    "BRL=X":        TickerConfig("yf_usdbrl",        "USD/BRL",                     "ratio", "forex",          "em",       "markets",          "BR",     ("close",)),
    "MXN=X":        TickerConfig("yf_usdmxn",        "USD/MXN",                     "ratio", "forex",          "em",       "markets",          "MX",     ("close",)),
    "INR=X":        TickerConfig("yf_usdinr",        "USD/INR",                     "ratio", "forex",          "em",       "markets",          "IN",     ("close",)),
    "TRY=X":        TickerConfig("yf_usdtry",        "USD/TRY",                     "ratio", "forex",          "em",       "markets",          "TR",     ("close",)),
    "ARS=X":        TickerConfig("yf_usdars",        "USD/ARS",                     "ratio", "forex",          "em",       "markets",          "AR",     ("close",)),
    "EURGBP=X":     TickerConfig("yf_eurgbp",        "EUR/GBP",                     "ratio", "forex",          "cross",    "markets",          "EA",     ("close",)),
    "EURCHF=X":     TickerConfig("yf_eurchf",        "EUR/CHF",                     "ratio", "forex",          "cross",    "markets",          "EA",     ("close",)),
    "EURJPY=X":     TickerConfig("yf_eurjpy",        "EUR/JPY",                     "ratio", "forex",          "cross",    "markets",          "EA",     ("close",)),
    "EURCNY=X":     TickerConfig("yf_eurcny",        "EUR/CNY",                     "ratio", "forex",          "cross",    "markets",          "EA",     ("close",)),

    # -- Categoría 3: Materias Primas — Energía --------------------------------
    "BZ=F":         TickerConfig("yf_bz",            "Petróleo Brent",              "usd",   "commodities",    "energy",   "commodities",      "GLOBAL", ("close",)),
    "CL=F":         TickerConfig("yf_cl",            "Petróleo WTI",                "usd",   "commodities",    "energy",   "commodities",      "US",     ("close",)),
    "NG=F":         TickerConfig("yf_ng",            "Gas Natural Henry Hub",       "usd",   "commodities",    "energy",   "commodities",      "US",     ("close",)),
    "TTF=F":        TickerConfig("yf_ttf",           "Gas Natural TTF Europa",      "eur",   "commodities",    "energy",   "commodities",      "EA",     ("close",)),
    "UX=F":         TickerConfig("yf_ux",            "Uranio",                      "usd",   "commodities",    "energy",   "commodities",      "GLOBAL", ("close",)),

    # -- Categoría 3: Materias Primas — Metales Preciosos ---------------------
    "GC=F":         TickerConfig("yf_gc",            "Oro",                         "usd",   "commodities",    "precious_metals", "commodities", "GLOBAL", ("close",)),
    "SI=F":         TickerConfig("yf_si",            "Plata",                       "usd",   "commodities",    "precious_metals", "commodities", "GLOBAL", ("close",)),
    "PL=F":         TickerConfig("yf_pl",            "Platino",                     "usd",   "commodities",    "precious_metals", "commodities", "GLOBAL", ("close",)),
    "PA=F":         TickerConfig("yf_pa",            "Paladio",                     "usd",   "commodities",    "precious_metals", "commodities", "GLOBAL", ("close",)),

    # -- Categoría 3: Materias Primas — Metales Industriales ------------------
    "HG=F":         TickerConfig("yf_hg",            "Cobre",                       "usd",   "commodities",    "industrial_metals", "commodities", "GLOBAL", ("close",)),
    "ALI=F":        TickerConfig("yf_ali",           "Aluminio",                    "usd",   "commodities",    "industrial_metals", "commodities", "GLOBAL", ("close",)),
    "ZNC=F":        TickerConfig("yf_znc",           "Zinc",                        "usd",   "commodities",    "industrial_metals", "commodities", "GLOBAL", ("close",)),

    # -- Categoría 3: Materias Primas — Agrícolas ------------------------------
    "ZW=F":         TickerConfig("yf_zw",            "Trigo",                       "usd",   "commodities",    "agricultural", "commodities",  "GLOBAL", ("close",)),
    "ZC=F":         TickerConfig("yf_zc",            "Maíz",                        "usd",   "commodities",    "agricultural", "commodities",  "GLOBAL", ("close",)),
    "ZS=F":         TickerConfig("yf_zs",            "Soja",                        "usd",   "commodities",    "agricultural", "commodities",  "GLOBAL", ("close",)),
    "ZR=F":         TickerConfig("yf_zr",            "Arroz",                       "usd",   "commodities",    "agricultural", "commodities",  "GLOBAL", ("close",)),
    "SB=F":         TickerConfig("yf_sb",            "Azúcar",                      "usd",   "commodities",    "agricultural", "commodities",  "GLOBAL", ("close",)),
    "KC=F":         TickerConfig("yf_kc",            "Café",                        "usd",   "commodities",    "agricultural", "commodities",  "GLOBAL", ("close",)),
    "CC=F":         TickerConfig("yf_cc",            "Cacao",                       "usd",   "commodities",    "agricultural", "commodities",  "GLOBAL", ("close",)),

    # -- Categoría 4: Renta Fija ETFs ------------------------------------------
    "TLT":          TickerConfig("yf_tlt",           "iShares 20Y+ Treasury",       "usd",   "fixed_income_etfs", "us_gov", "markets",        "US",     ("close","volume")),
    "IEF":          TickerConfig("yf_ief",           "iShares 7-10Y Treasury",      "usd",   "fixed_income_etfs", "us_gov", "markets",        "US",     ("close","volume")),
    "SHY":          TickerConfig("yf_shy",           "iShares 1-3Y Treasury",       "usd",   "fixed_income_etfs", "us_gov", "markets",        "US",     ("close","volume")),
    "HYG":          TickerConfig("yf_hyg",           "iShares High Yield Corp",     "usd",   "fixed_income_etfs", "credit", "markets",        "US",     ("close","volume")),
    "LQD":          TickerConfig("yf_lqd",           "iShares IG Corporate",        "usd",   "fixed_income_etfs", "credit", "markets",        "US",     ("close","volume")),
    "EMB":          TickerConfig("yf_emb",           "iShares EM Bond USD",         "usd",   "fixed_income_etfs", "em",    "markets",         "GLOBAL", ("close","volume")),
    "TIP":          TickerConfig("yf_tip",           "iShares TIPS Bond",           "usd",   "fixed_income_etfs", "tips",  "markets",         "US",     ("close","volume")),
    "BNDX":         TickerConfig("yf_bndx",          "Vanguard Intl Bond",          "usd",   "fixed_income_etfs", "global","markets",         "GLOBAL", ("close","volume")),

    # -- Categoría 5: Volatilidad y Sentimiento --------------------------------
    "^VIX":         TickerConfig("yf_vix",           "VIX (Índice del Miedo)",      "index", "volatility",     "equity",   "markets",          "US",     ("close",)),
    "^VXN":         TickerConfig("yf_vxn",           "VXN Nasdaq Volatility",       "index", "volatility",     "equity",   "markets",          "US",     ("close",)),
    "^SKEW":        TickerConfig("yf_skew",          "SKEW (Riesgo de Cola)",       "index", "volatility",     "equity",   "markets",          "US",     ("close",)),
    "^OVX":         TickerConfig("yf_ovx",           "OVX Crude Oil Volatility",    "index", "volatility",     "commodity","markets",          "US",     ("close",)),
    "^GVZ":         TickerConfig("yf_gvz",           "GVZ Gold Volatility",         "index", "volatility",     "commodity","markets",          "US",     ("close",)),

    # -- Categoría 6: Bancos Globales ------------------------------------------
    "JPM":          TickerConfig("yf_jpm",           "JPMorgan Chase",              "usd",   "banks",          "us",       "financial_system", "US",     ("close","volume")),
    "BAC":          TickerConfig("yf_bac",           "Bank of America",             "usd",   "banks",          "us",       "financial_system", "US",     ("close","volume")),
    "C":            TickerConfig("yf_citi",          "Citigroup",                   "usd",   "banks",          "us",       "financial_system", "US",     ("close","volume")),
    "GS":           TickerConfig("yf_gs",            "Goldman Sachs",               "usd",   "banks",          "us",       "financial_system", "US",     ("close","volume")),
    "WFC":          TickerConfig("yf_wfc",           "Wells Fargo",                 "usd",   "banks",          "us",       "financial_system", "US",     ("close","volume")),
    "MS":           TickerConfig("yf_ms",            "Morgan Stanley",              "usd",   "banks",          "us",       "financial_system", "US",     ("close","volume")),
    "DB":           TickerConfig("yf_db",            "Deutsche Bank",               "usd",   "banks",          "europe",   "financial_system", "DE",     ("close","volume")),
    "BNP.PA":       TickerConfig("yf_bnp_pa",        "BNP Paribas",                 "eur",   "banks",          "europe",   "financial_system", "FR",     ("close","volume")),
    "SAN.MC":       TickerConfig("yf_san_mc",        "Banco Santander",             "eur",   "banks",          "europe",   "financial_system", "ES",     ("close","volume")),
    "BBVA.MC":      TickerConfig("yf_bbva_mc",       "BBVA",                        "eur",   "banks",          "europe",   "financial_system", "ES",     ("close","volume")),
    "HSBA.L":       TickerConfig("yf_hsba_l",        "HSBC",                        "gbp",   "banks",          "europe",   "financial_system", "GB",     ("close","volume")),
    "UBSG.SW":      TickerConfig("yf_ubsg_sw",       "UBS",                         "chf",   "banks",          "europe",   "financial_system", "CH",     ("close","volume")),
    "BARC.L":       TickerConfig("yf_barc_l",        "Barclays",                    "gbp",   "banks",          "europe",   "financial_system", "GB",     ("close","volume")),
    "UCG.MI":       TickerConfig("yf_ucg_mi",        "UniCredit",                   "eur",   "banks",          "europe",   "financial_system", "IT",     ("close","volume")),
    "8306.T":       TickerConfig("yf_8306_t",        "Mitsubishi UFJ",              "jpy",   "banks",          "asia",     "financial_system", "JP",     ("close","volume")),
    "1398.HK":      TickerConfig("yf_1398_hk",       "ICBC",                        "hkd",   "banks",          "asia",     "financial_system", "CN",     ("close","volume")),

    # -- Categoría 7: ETFs Sectoriales S&P 500 --------------------------------
    "XLK":          TickerConfig("yf_xlk",           "Technology Select Sector",    "usd",   "sectors",        "sp500_sectors", "sectors",   "US",     ("close","volume")),
    "XLE":          TickerConfig("yf_xle",           "Energy Select Sector",        "usd",   "sectors",        "sp500_sectors", "sectors",   "US",     ("close","volume")),
    "XLF":          TickerConfig("yf_xlf",           "Financial Select Sector",     "usd",   "sectors",        "sp500_sectors", "sectors",   "US",     ("close","volume")),
    "XLV":          TickerConfig("yf_xlv",           "Health Care Select Sector",   "usd",   "sectors",        "sp500_sectors", "sectors",   "US",     ("close","volume")),
    "XLP":          TickerConfig("yf_xlp",           "Consumer Staples Sector",     "usd",   "sectors",        "sp500_sectors", "sectors",   "US",     ("close","volume")),
    "XLY":          TickerConfig("yf_xly",           "Consumer Discret. Sector",    "usd",   "sectors",        "sp500_sectors", "sectors",   "US",     ("close","volume")),
    "XLB":          TickerConfig("yf_xlb",           "Materials Select Sector",     "usd",   "sectors",        "sp500_sectors", "sectors",   "US",     ("close","volume")),
    "XLI":          TickerConfig("yf_xli",           "Industrials Select Sector",   "usd",   "sectors",        "sp500_sectors", "sectors",   "US",     ("close","volume")),
    "XLU":          TickerConfig("yf_xlu",           "Utilities Select Sector",     "usd",   "sectors",        "sp500_sectors", "sectors",   "US",     ("close","volume")),
    "XLRE":         TickerConfig("yf_xlre",          "Real Estate Select Sector",   "usd",   "sectors",        "sp500_sectors", "sectors",   "US",     ("close","volume")),
    "XLC":          TickerConfig("yf_xlc",           "Comm. Services Sector",       "usd",   "sectors",        "sp500_sectors", "sectors",   "US",     ("close","volume")),

    # -- Categoría 7: ETFs Temáticos -------------------------------------------
    "ITA":          TickerConfig("yf_ita",           "Aerospace & Defense ETF",     "usd",   "sectors",        "thematic", "sectors",          "US",     ("close","volume")),
    "SOXX":         TickerConfig("yf_soxx",          "Semiconductor ETF",           "usd",   "sectors",        "thematic", "sectors",          "US",     ("close","volume")),
    "BOTZ":         TickerConfig("yf_botz",          "Robotics & AI ETF",           "usd",   "sectors",        "thematic", "sectors",          "GLOBAL", ("close","volume")),
    "ICLN":         TickerConfig("yf_icln",          "Clean Energy ETF",            "usd",   "sectors",        "thematic", "sectors",          "GLOBAL", ("close","volume")),
    "LIT":          TickerConfig("yf_lit",           "Lithium & Battery Tech ETF",  "usd",   "sectors",        "thematic", "sectors",          "GLOBAL", ("close","volume")),
    "COPX":         TickerConfig("yf_copx",          "Copper Miners ETF",           "usd",   "sectors",        "thematic", "sectors",          "GLOBAL", ("close","volume")),
    "GDX":          TickerConfig("yf_gdx",           "Gold Miners ETF",             "usd",   "sectors",        "thematic", "sectors",          "GLOBAL", ("close","volume")),
    "VNQ":          TickerConfig("yf_vnq",           "Vanguard Real Estate ETF",    "usd",   "sectors",        "thematic", "sectors",          "US",     ("close","volume")),
    "REM":          TickerConfig("yf_rem",           "Mortgage Real Estate ETF",    "usd",   "sectors",        "thematic", "sectors",          "US",     ("close","volume")),

    # -- Categoría 8: Criptomonedas --------------------------------------------
    "BTC-USD":      TickerConfig("yf_btc_usd",       "Bitcoin (USD)",               "usd",   "crypto",         "major",    "crypto",           "GLOBAL", ("close","volume")),
    "ETH-USD":      TickerConfig("yf_eth_usd",       "Ethereum (USD)",              "usd",   "crypto",         "major",    "crypto",           "GLOBAL", ("close","volume")),
    "BTC-EUR":      TickerConfig("yf_btc_eur",       "Bitcoin (EUR)",               "eur",   "crypto",         "major",    "crypto",           "GLOBAL", ("close",)),

    # -- Amplitud de Mercado (para ratio RSP/SPY) ------------------------------
    "RSP":          TickerConfig("yf_rsp",           "S&P 500 Equal Weight ETF",    "usd",   "breadth",        "us",       "markets",          "US",     ("close","volume")),
    "SPY":          TickerConfig("yf_spy",           "S&P 500 ETF (SPY)",           "usd",   "breadth",        "us",       "markets",          "US",     ("close","volume")),
}


# -- Colector ------------------------------------------------------------------

class YahooCollector(BaseCollector):
    """
    Colector de datos de Yahoo Finance (via yfinance).

    Uso típico:
        collector = YahooCollector()
        collector.run_full_history()   # Primera vez (~8-12 min)
        collector.run_update()         # Ejecuciones automáticas cada 15 min
    """

    SOURCE = "yfinance"

    def __init__(self) -> None:
        self._errors: list[str] = []
        logger.info("YahooCollector inicializado. %d tickers en catálogo.", len(TICKER_CATALOG))

    # -- Interfaz pública (BaseCollector) --------------------------------------

    def run_full_history(self) -> dict:
        """Descarga el histórico completo desde 2000. Solo para primera ejecución."""
        logger.info("=" * 64)
        logger.info("Yahoo >> Inicio descarga histórico completo (desde %s)", HISTORY_START)
        logger.info("        %d tickers en catálogo, lotes de %d", len(TICKER_CATALOG), BATCH_SIZE)
        logger.info("=" * 64)
        t0 = time.time()
        self._errors = []

        result = self._download_all_tickers(start=HISTORY_START, end=None)
        self._calculate_derived_metrics()

        elapsed = time.time() - t0
        logger.info("=" * 64)
        logger.info(
            "Yahoo OK Histórico completo en %.1fs | OK: %d | Fail: %d | Registros: %d",
            elapsed, result["ok"], result["failed"], result["total_records"],
        )
        if self._errors:
            logger.warning("Yahoo FAIL Tickers con error: %d", len(self._errors))
        logger.info("=" * 64)
        return result

    def run_update(self) -> dict:
        """Descarga los últimos 5 días de datos (solapamiento de 7 días para seguridad)."""
        start = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        logger.info("Yahoo >> Actualización desde %s", start)
        t0 = time.time()
        self._errors = []

        result = self._download_all_tickers(start=start, end=None)
        self._calculate_derived_metrics()

        elapsed = time.time() - t0
        logger.info(
            "Yahoo OK Actualización en %.1fs | Nuevos registros: %d",
            elapsed, result["total_records"],
        )
        return result

    def download_tickers(
        self,
        tickers: list[str],
        start: str = HISTORY_START,
        end: Optional[str] = None,
    ) -> dict:
        """
        Descarga y guarda un subconjunto específico de tickers.
        Útil para pruebas y para añadir tickers individuales.

        Args:
            tickers: Lista de símbolos Yahoo Finance (ej: ['^GSPC', 'GC=F'])
            start:   Fecha de inicio 'YYYY-MM-DD'
            end:     Fecha de fin 'YYYY-MM-DD' (None = hoy)

        Returns:
            dict con ok, failed, total_records, errors
        """
        logger.info("Yahoo >> Descargando %d tickers desde %s", len(tickers), start)
        self._errors = []
        ok = failed = total_records = 0

        for ticker in tickers:
            cfg = TICKER_CATALOG.get(ticker)
            if cfg is None:
                logger.warning("  SKIP %s — no está en el catálogo", ticker)
                failed += 1
                continue

            try:
                n = self._download_ticker(
                    ticker=ticker,
                    name=cfg.name,
                    category=cfg.category,
                    subcategory=cfg.subcategory,
                    country_or_region=cfg.region,
                    unit=cfg.unit,
                    fields=cfg.fields,
                    start=start,
                    end=end,
                )
                logger.info("  OK %-20s %s — %d registros", ticker, cfg.name[:35], n)
                ok += 1
                total_records += n
            except Exception as exc:
                msg = f"{ticker}: {exc}"
                logger.error("  FAIL %s", msg)
                self._errors.append(msg)
                failed += 1

        return {"ok": ok, "failed": failed, "total_records": total_records, "errors": self._errors}

    def get_last_update_time(self) -> Optional[datetime]:
        """Retorna el datetime UTC de la última inserción de datos Yahoo Finance."""
        with SessionLocal() as session:
            return session.query(func.max(TimeSeries.created_at)).filter(
                TimeSeries.source == self.SOURCE
            ).scalar()

    def get_status(self) -> dict:
        """Retorna estado completo del colector."""
        with SessionLocal() as session:
            total = session.query(func.count(TimeSeries.id)).filter(
                TimeSeries.source == self.SOURCE
            ).scalar() or 0

            series_count = (
                session.query(TimeSeries.indicator_id)
                .filter(TimeSeries.source == self.SOURCE)
                .distinct()
                .count()
            )

            last = session.query(func.max(TimeSeries.created_at)).filter(
                TimeSeries.source == self.SOURCE
            ).scalar()

        if last is None:
            status = "never_run"
        elif self._errors:
            status = "error"
        else:
            status = "ok"

        return {
            "source": self.SOURCE,
            "last_update": last,
            "total_records": total,
            "series_count": series_count,
            "status": status,
            "errors": list(self._errors),
        }

    # -- Métodos privados ------------------------------------------------------

    def _download_all_tickers(self, start: str, end: Optional[str]) -> dict:
        """Descarga todos los tickers del catálogo en lotes de BATCH_SIZE."""
        ok = failed = total_records = 0
        all_tickers = list(TICKER_CATALOG.keys())
        total_batches = (len(all_tickers) + BATCH_SIZE - 1) // BATCH_SIZE

        for batch_idx in range(0, len(all_tickers), BATCH_SIZE):
            batch = all_tickers[batch_idx:batch_idx + BATCH_SIZE]
            batch_num = batch_idx // BATCH_SIZE + 1
            logger.info("-- Lote [%d/%d] (%d tickers) --", batch_num, total_batches, len(batch))

            # Descarga del lote completo
            try:
                batch_data = self._download_batch(batch, start, end)
            except Exception as exc:
                logger.error("  FAIL Fallo total en lote %d: %s", batch_num, exc)
                for ticker in batch:
                    self._errors.append(f"{ticker}: batch error — {exc}")
                    failed += 1
                continue

            # Procesar cada ticker del lote
            for ticker in batch:
                cfg = TICKER_CATALOG[ticker]

                if ticker not in batch_data or batch_data[ticker].empty:
                    # Fallback: descarga individual
                    logger.warning("  WARN %s — sin datos en lote, intentando individual...", ticker)
                    try:
                        n = self._download_ticker(
                            ticker=ticker,
                            name=cfg.name,
                            category=cfg.category,
                            subcategory=cfg.subcategory,
                            country_or_region=cfg.region,
                            unit=cfg.unit,
                            fields=cfg.fields,
                            start=start,
                            end=end,
                        )
                        logger.info("  OK %-20s (individual) — %d registros", ticker, n)
                        ok += 1
                        total_records += n
                    except Exception as exc:
                        msg = f"{ticker}: {exc}"
                        logger.error("  FAIL %s", msg)
                        self._errors.append(msg)
                        failed += 1
                    continue

                df = batch_data[ticker]
                n = 0
                for field in cfg.fields:
                    if field not in df.columns:
                        continue
                    series = df[field].dropna()
                    if series.empty:
                        continue
                    try:
                        saved = self._save_series(
                            indicator_id=f"{cfg.indicator_id}_{field}",
                            data=series,
                            module=cfg.module,
                            region=cfg.region,
                            unit=cfg.unit,
                        )
                        n += saved
                    except Exception as exc:
                        logger.warning("  WARN Error guardando %s.%s: %s", ticker, field, exc)

                logger.info("  OK %-20s %s — %d registros", ticker, cfg.name[:30], n)
                ok += 1
                total_records += n

        return {"ok": ok, "failed": failed, "total_records": total_records, "errors": self._errors}

    def _download_batch(
        self,
        ticker_batch: list[str],
        start: str,
        end: Optional[str],
        max_retries: int = 3,
    ) -> dict[str, pd.DataFrame]:
        """
        Descarga múltiples tickers de golpe con yf.download().
        Retorna dict {ticker: DataFrame(columns=[campo_lowercase])}.

        Nota yfinance 1.x: yf.download() siempre devuelve columnas MultiIndex
        (Price, Ticker) independientemente de si hay uno o varios tickers.
        El parámetro 'threads' fue eliminado en yfinance 1.0.
        """
        last_exc: Exception = RuntimeError("Sin intentos")
        raw = pd.DataFrame()

        for attempt in range(max_retries):
            try:
                raw = yf.download(
                    ticker_batch,       # lista, incluso con un solo elemento
                    start=start,
                    end=end,
                    auto_adjust=True,
                    progress=False,
                    # 'threads' eliminado en yfinance 1.x — no se pasa
                )
                time.sleep(RATE_LIMIT_DELAY)
                break
            except Exception as exc:
                last_exc = exc
                if attempt < max_retries - 1:
                    wait = 2 ** attempt
                    logger.warning("  Reintento %d para lote (%.0fs): %s", attempt + 1, wait, exc)
                    time.sleep(wait)
        else:
            raise RuntimeError(f"Fallo lote tras {max_retries} intentos: {last_exc}")

        if raw is None or raw.empty:
            return {}

        result: dict[str, pd.DataFrame] = {}
        fields_map = {"Close": "close", "High": "high", "Low": "low",
                      "Open": "open", "Volume": "volume"}

        # yfinance 1.x: siempre MultiIndex (Price, Ticker) — mismo código para 1 o N tickers
        level0 = raw.columns.get_level_values(0).unique().tolist()
        for ticker in ticker_batch:
            ticker_data = {}
            for raw_col, clean_col in fields_map.items():
                if raw_col not in level0:
                    continue
                try:
                    col_data = raw[raw_col]
                    if isinstance(col_data, pd.DataFrame):
                        if ticker in col_data.columns:
                            s = col_data[ticker].dropna()
                            if not s.empty:
                                ticker_data[clean_col] = s
                    elif isinstance(col_data, pd.Series):
                        # Fallback: solo un ticker y pandas colapsó el nivel
                        s = col_data.dropna()
                        if not s.empty:
                            ticker_data[clean_col] = s
                except Exception:
                    pass
            if ticker_data:
                result[ticker] = pd.DataFrame(ticker_data)

        return result

    def _download_ticker(
        self,
        ticker: str,
        name: str,
        category: str,
        subcategory: str,
        country_or_region: str,
        unit: str,
        fields: tuple,
        start: str,
        end: Optional[str] = None,
        max_retries: int = 3,
    ) -> int:
        """
        Descarga un ticker individual con yf.Ticker().history() y lo guarda en SQLite.
        Usado como fallback cuando la descarga en lote falla para ese ticker.

        Args:
            ticker:            Símbolo Yahoo Finance (ej: '^GSPC')
            name:              Nombre legible
            category:          Categoría ('equity_indices', 'forex', etc.)
            subcategory:       Subcategoría
            country_or_region: Código de región (ej: 'US')
            unit:              Unidad de medida
            fields:            Campos a guardar (ej: ('close', 'volume'))
            start:             Fecha inicio 'YYYY-MM-DD'
            end:               Fecha fin 'YYYY-MM-DD' o None

        Returns:
            Número total de registros insertados.
        """
        cfg = TICKER_CATALOG.get(ticker)
        if cfg is None:
            raise ValueError(f"Ticker {ticker} no está en TICKER_CATALOG")

        last_exc: Exception = RuntimeError("Sin intentos")
        df = pd.DataFrame()

        for attempt in range(max_retries):
            try:
                # Pasar curl_cffi session para esquivar filtros anti-bot de Yahoo Finance
                t = yf.Ticker(ticker, session=_CURL_SESSION) if _CURL_SESSION else yf.Ticker(ticker)
                df = t.history(start=start, end=end, auto_adjust=True)
                time.sleep(RATE_LIMIT_DELAY)
                break
            except Exception as exc:
                last_exc = exc
                if attempt < max_retries - 1:
                    wait = 2 ** attempt
                    logger.warning(
                        "  Reintento %d/%d para %s (%.0fs): %s",
                        attempt + 1, max_retries - 1, ticker, wait, exc,
                    )
                    time.sleep(wait)
        else:
            raise RuntimeError(f"Fallo {ticker} tras {max_retries} intentos: {last_exc}")

        if df.empty:
            logger.warning("  WARN %s — DataFrame vacío (delisted o no disponible)", ticker)
            return 0

        # Normalizar nombres de columna a minúsculas
        df.columns = [str(c).lower() for c in df.columns]

        total = 0
        for field in fields:
            if field not in df.columns:
                continue
            series = df[field].dropna()
            if series.empty:
                continue
            saved = self._save_series(
                indicator_id=f"{cfg.indicator_id}_{field}",
                data=series,
                module=cfg.module,
                region=country_or_region,
                unit=unit,
            )
            total += saved

        return total

    def _calculate_derived_metrics(self) -> None:
        """
        Calcula y guarda métricas derivadas después de la descarga de precios.

        Para índices bursátiles:
          - Retornos: 1d, 5d (semana), 21d (mes), 252d (año), YTD
          - Distancia al máximo de 52 semanas (%)
          - Distancia al máximo histórico ATH (%)

        Para materias primas:
          - Ratio oro/plata
          - Ratio oro/Brent
          - Spread Brent-WTI

        Para divisas: variación anual vs USD

        Para bancos: variación anual del precio de la acción

        Amplitud de mercado: ratio RSP/SPY
        """
        logger.info("Yahoo >> Calculando métricas derivadas...")

        # 1. Retornos y distancias para índices bursátiles
        equity_tickers = [t for t, c in TICKER_CATALOG.items() if c.category == "equity_indices"]

        for ticker in equity_tickers:
            cfg = TICKER_CATALOG[ticker]
            close = self._load_indicator_from_db(f"{cfg.indicator_id}_close")
            if close.empty or len(close) < 5:
                continue

            base_id = cfg.indicator_id

            # Retornos por período
            for periods, suffix in [(1, "return_1d"), (5, "return_1w"), (21, "return_1m"), (252, "return_1y")]:
                if len(close) <= periods:
                    continue
                ret = (close.pct_change(periods) * 100).dropna()
                self._save_series(f"{base_id}_{suffix}", ret, cfg.module, cfg.region, "pct")

            # Retorno YTD
            year_start = pd.Timestamp(f"{datetime.now().year}-01-01")
            before_year = close[close.index < year_start]
            if not before_year.empty:
                ytd_base = before_year.iloc[-1]
                after_year = close[close.index >= year_start]
                if not after_year.empty and ytd_base != 0:
                    ytd_ret = (after_year / ytd_base - 1) * 100
                    self._save_series(f"{base_id}_return_ytd", ytd_ret, cfg.module, cfg.region, "pct")

            # Distancia al máximo de 52 semanas
            if len(close) >= 10:
                window = min(252, len(close))
                rolling_max = close.rolling(window).max()
                dist_52w = ((close / rolling_max - 1) * 100).dropna()
                self._save_series(f"{base_id}_dist_52w_high", dist_52w, cfg.module, cfg.region, "pct")

            # Distancia al ATH (máximo histórico)
            cummax = close.cummax()
            dist_ath = ((close / cummax - 1) * 100).dropna()
            self._save_series(f"{base_id}_dist_ath", dist_ath, cfg.module, cfg.region, "pct")

        logger.info("  OK Retornos y distancias índices calculados")

        # 2. Ratio oro/plata
        gold = self._load_indicator_from_db("yf_gc_close")
        silver = self._load_indicator_from_db("yf_si_close")
        if not gold.empty and not silver.empty:
            aligned = pd.concat([gold, silver], axis=1).dropna()
            aligned.columns = ["g", "s"]
            ratio = (aligned["g"] / aligned["s"]).dropna()
            n = self._save_series("yf_gold_silver_ratio", ratio, "commodities", "GLOBAL", "ratio")
            logger.info("  OK Ratio Oro/Plata: %d registros", n)

        # 3. Ratio oro/Brent
        brent = self._load_indicator_from_db("yf_bz_close")
        if not gold.empty and not brent.empty:
            aligned = pd.concat([gold, brent], axis=1).dropna()
            aligned.columns = ["g", "b"]
            ratio = (aligned["g"] / aligned["b"]).dropna()
            n = self._save_series("yf_gold_brent_ratio", ratio, "commodities", "GLOBAL", "ratio")
            logger.info("  OK Ratio Oro/Brent: %d registros", n)

        # 4. Spread Brent-WTI
        wti = self._load_indicator_from_db("yf_cl_close")
        if not brent.empty and not wti.empty:
            aligned = pd.concat([brent, wti], axis=1).dropna()
            aligned.columns = ["b", "w"]
            spread = (aligned["b"] - aligned["w"]).dropna()
            n = self._save_series("yf_brent_wti_spread", spread, "commodities", "GLOBAL", "usd")
            logger.info("  OK Spread Brent-WTI: %d registros", n)

        # 5. Variación anual divisas vs USD
        forex_tickers = [t for t, c in TICKER_CATALOG.items() if c.category == "forex"]
        for ticker in forex_tickers:
            cfg = TICKER_CATALOG[ticker]
            close = self._load_indicator_from_db(f"{cfg.indicator_id}_close")
            if close.empty or len(close) < 252:
                continue
            annual = (close.pct_change(252) * 100).dropna()
            self._save_series(f"{cfg.indicator_id}_return_1y", annual, cfg.module, cfg.region, "pct")

        logger.info("  OK Variaciones anuales forex calculadas")

        # 6. Variación anual bancos
        bank_tickers = [t for t, c in TICKER_CATALOG.items() if c.category == "banks"]
        for ticker in bank_tickers:
            cfg = TICKER_CATALOG[ticker]
            close = self._load_indicator_from_db(f"{cfg.indicator_id}_close")
            if close.empty or len(close) < 252:
                continue
            annual = (close.pct_change(252) * 100).dropna()
            self._save_series(f"{cfg.indicator_id}_return_1y", annual, cfg.module, cfg.region, "pct")

        logger.info("  OK Variaciones anuales bancos calculadas")

        # 7. Ratio RSP/SPY (amplitud de mercado)
        rsp = self._load_indicator_from_db("yf_rsp_close")
        spy = self._load_indicator_from_db("yf_spy_close")
        if not rsp.empty and not spy.empty:
            aligned = pd.concat([rsp, spy], axis=1).dropna()
            aligned.columns = ["rsp", "spy"]
            breadth = (aligned["rsp"] / aligned["spy"]).dropna()
            n = self._save_series("yf_rsp_spy_ratio", breadth, "markets", "US", "ratio")
            logger.info("  OK Ratio RSP/SPY (amplitud): %d registros", n)

        logger.info("Yahoo OK Métricas derivadas completadas.")

    def _save_series(
        self,
        indicator_id: str,
        data: pd.Series,
        module: str,
        region: str,
        unit: str,
    ) -> int:
        """
        Guarda una serie en SQLite sin duplicar registros existentes.
        Idéntica estrategia anti-duplicados que FREDCollector:
        MAX(timestamp) por indicator_id → solo inserta registros más recientes.

        Returns:
            Número de registros nuevos insertados.
        """
        data = data.dropna()
        if data.empty:
            return 0

        with SessionLocal() as session:
            max_ts = session.query(func.max(TimeSeries.timestamp)).filter(
                TimeSeries.indicator_id == indicator_id
            ).scalar()

        if max_ts is not None:
            # yfinance 1.x returns tz-aware index; SQLite stores naive → strip tz for comparison
            idx_naive = data.index.tz_localize(None) if data.index.tz is not None else data.index
            data = data.loc[idx_naive > pd.Timestamp(max_ts)]

        if data.empty:
            return 0

        now = datetime.utcnow()
        records = [
            {
                "indicator_id": indicator_id,
                "source": self.SOURCE,
                "region": region,
                "timestamp": pd.Timestamp(ts).to_pydatetime().replace(tzinfo=None),
                "value": float(val),
                "unit": unit,
                "created_at": now,
            }
            for ts, val in data.items()
            if not pd.isna(val)
        ]

        if not records:
            return 0

        with SessionLocal() as session:
            session.execute(insert(TimeSeries), records)
            session.commit()

        return len(records)

    def _load_indicator_from_db(
        self,
        indicator_id: str,
        start_date: Optional[datetime] = None,
    ) -> pd.Series:
        """
        Carga un indicador de SQLite como pandas Series (DatetimeIndex, float).
        Retorna Series vacía si no hay datos.
        """
        with SessionLocal() as session:
            query = (
                session.query(TimeSeries.timestamp, TimeSeries.value)
                .filter(TimeSeries.indicator_id == indicator_id)
            )
            if start_date is not None:
                query = query.filter(TimeSeries.timestamp >= start_date)
            rows = query.order_by(TimeSeries.timestamp).all()

        if not rows:
            return pd.Series(dtype=float)

        dates, values = zip(*rows)
        return pd.Series(list(values), index=pd.DatetimeIndex(list(dates)), dtype=float)
