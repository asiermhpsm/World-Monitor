"""
Colectores de datos para World Monitor.
Cada colector es independiente: si falla, el dashboard muestra "sin datos"
en ese módulo sin interrumpir el resto de la aplicación.
"""

from collectors.base_collector import BaseCollector
from collectors.fred_collector import FREDCollector
from collectors.yahoo_collector import YahooCollector
from collectors.worldbank_collector import WorldBankCollector
from collectors.europe_collector import EuropeCollector
from collectors.coingecko_collector import CoinGeckoCollector
from collectors.news_collector import NewsCollector

__all__ = [
    "BaseCollector",
    "FREDCollector",
    "YahooCollector",
    "WorldBankCollector",
    "EuropeCollector",
    "CoinGeckoCollector",
    "NewsCollector",
]
