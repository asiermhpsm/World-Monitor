"""
Clase base abstracta para todos los colectores de datos del World Monitor.

Todos los colectores heredan de esta clase y deben implementar los 4 métodos
abstractos. Esto garantiza una interfaz uniforme independientemente de la fuente
de datos, lo que permite al scheduler y al dashboard tratarlos de forma genérica.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional


class BaseCollector(ABC):
    """
    Interfaz común para todos los colectores de datos.

    Ciclo de vida típico:
        1. Primera ejecución:   collector.run_full_history()
        2. Ejecuciones diarias: collector.run_update()
        3. Monitorización:      collector.get_status()
    """

    # Sobrescribir en cada subclase con el nombre de la fuente
    SOURCE: str = "unknown"

    # ── Métodos abstractos ────────────────────────────────────────────────────

    @abstractmethod
    def run_full_history(self) -> dict:
        """
        Descarga el histórico completo de todas las series desde el año 2000.
        Solo debe ejecutarse la primera vez o para una recarga completa.

        Retorna dict con:
            ok            : int  — series descargadas con éxito
            failed        : int  — series con error
            total_records : int  — registros nuevos insertados
            errors        : list[str] — mensajes de error por serie
        """
        ...

    @abstractmethod
    def run_update(self) -> dict:
        """
        Descarga solo los datos nuevos desde la última actualización exitosa.
        Es el método que llama el scheduler en las ejecuciones automáticas.

        Retorna el mismo dict que run_full_history().
        """
        ...

    @abstractmethod
    def get_last_update_time(self) -> Optional[datetime]:
        """
        Retorna el datetime UTC de la última actualización exitosa.
        Retorna None si el colector nunca se ha ejecutado.
        """
        ...

    @abstractmethod
    def get_status(self) -> dict:
        """
        Retorna el estado completo del colector para monitorización.

        Estructura garantizada del dict retornado:
        {
            'source'        : str            — nombre de la fuente
            'last_update'   : datetime|None  — última actualización
            'total_records' : int            — total de registros en BD
            'series_count'  : int            — número de series únicas
            'status'        : str            — 'ok' | 'error' | 'never_run'
            'errors'        : list[str]      — errores del último run
        }
        """
        ...
