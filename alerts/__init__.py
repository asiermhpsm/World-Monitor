"""
Sistema de alertas visuales del World Monitor.
Exporta AlertManager para uso desde scheduler y dashboard.
"""

from alerts.alert_manager import AlertManager

__all__ = ["AlertManager"]
