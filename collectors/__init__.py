"""
Colectores de datos para World Monitor.
Cada colector es independiente: si falla, el dashboard muestra "sin datos"
en ese módulo sin interrumpir el resto de la aplicación.
"""

from collectors.base_collector import BaseCollector
from collectors.fred_collector import FREDCollector

__all__ = ["BaseCollector", "FREDCollector"]
