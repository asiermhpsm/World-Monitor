"""
Funciones reutilizables para leer datos de SQLite.
Usadas por todos los modulos del dashboard.
Todas las funciones son seguras ante datos faltantes: devuelven None o listas vacias.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple

import pandas as pd

from database.database import (
    GeopoliticalEvent,
    NewsArticle,
    SessionLocal,
    TimeSeries,
)

logger = logging.getLogger(__name__)


# ── Lectura de series temporales ───────────────────────────────────────────────

def get_latest_value(
    series_id: str,
    source: Optional[str] = None,
) -> Tuple[Optional[float], Optional[datetime]]:
    """
    Devuelve (valor, timestamp) del dato mas reciente de una serie.
    Retorna (None, None) si no existe o hay error.
    """
    try:
        with SessionLocal() as db:
            q = db.query(TimeSeries).filter(TimeSeries.indicator_id == series_id)
            if source:
                q = q.filter(TimeSeries.source == source)
            row = q.order_by(TimeSeries.timestamp.desc()).first()
            if row is None:
                return None, None
            return row.value, row.timestamp
    except Exception as exc:
        logger.debug("get_latest_value(%s): %s", series_id, exc)
        return None, None


def get_series(
    series_id: str,
    days: int = 365,
    source: Optional[str] = None,
) -> pd.DataFrame:
    """
    Devuelve un DataFrame(timestamp, value) con la serie temporal
    de los ultimos N dias, ordenado por fecha ascendente.
    Devuelve DataFrame vacio si no hay datos.
    """
    try:
        since = datetime.utcnow() - timedelta(days=days)
        with SessionLocal() as db:
            q = db.query(TimeSeries).filter(
                TimeSeries.indicator_id == series_id,
                TimeSeries.timestamp >= since,
            )
            if source:
                q = q.filter(TimeSeries.source == source)
            rows = q.order_by(TimeSeries.timestamp.asc()).all()
        if not rows:
            return pd.DataFrame(columns=["timestamp", "value"])
        return pd.DataFrame(
            [{"timestamp": r.timestamp, "value": r.value} for r in rows]
        )
    except Exception as exc:
        logger.debug("get_series(%s): %s", series_id, exc)
        return pd.DataFrame(columns=["timestamp", "value"])


def get_change(
    series_id: str,
    period_days: int = 1,
    source: Optional[str] = None,
) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
    """
    Devuelve (valor_actual, valor_hace_N_dias, variacion_abs, variacion_pct).
    Devuelve (None, None, None, None) si no hay datos suficientes.
    """
    try:
        with SessionLocal() as db:
            q = db.query(TimeSeries).filter(TimeSeries.indicator_id == series_id)
            if source:
                q = q.filter(TimeSeries.source == source)
            current_row = q.order_by(TimeSeries.timestamp.desc()).first()
            if current_row is None or current_row.value is None:
                return None, None, None, None
            current_val = current_row.value

            ref_dt = datetime.utcnow() - timedelta(days=period_days)
            ref_q = db.query(TimeSeries).filter(
                TimeSeries.indicator_id == series_id,
                TimeSeries.timestamp <= ref_dt,
            )
            if source:
                ref_q = ref_q.filter(TimeSeries.source == source)
            ref_row = ref_q.order_by(TimeSeries.timestamp.desc()).first()

        if ref_row is None or ref_row.value is None:
            return current_val, None, None, None

        prev_val = ref_row.value
        abs_change = current_val - prev_val
        pct_change = (abs_change / abs(prev_val) * 100) if prev_val != 0 else None
        return current_val, prev_val, abs_change, pct_change
    except Exception as exc:
        logger.debug("get_change(%s): %s", series_id, exc)
        return None, None, None, None


# ── Noticias ───────────────────────────────────────────────────────────────────

def get_latest_news(
    n: int = 10,
    category: Optional[str] = None,
    hours: int = 48,
) -> list[dict]:
    """
    Devuelve los N articulos mas recientes por impact_score
    publicados en las ultimas `hours` horas.
    """
    try:
        since = datetime.utcnow() - timedelta(hours=hours)
        with SessionLocal() as db:
            q = db.query(NewsArticle).filter(NewsArticle.published_at >= since)
            if category:
                q = q.filter(NewsArticle.category == category)
            rows = q.order_by(NewsArticle.impact_score.desc()).limit(n).all()
        return [
            {
                "id": r.id,
                "title": r.title,
                "description": r.description,
                "url": r.url,
                "source_name": r.source_name,
                "published_at": r.published_at,
                "category": r.category,
                "region": r.region,
                "impact_score": r.impact_score or 0.0,
            }
            for r in rows
        ]
    except Exception as exc:
        logger.debug("get_latest_news: %s", exc)
        return []


# ── Alertas ────────────────────────────────────────────────────────────────────

def get_active_alerts(hours: int = 48) -> list[dict]:
    """Devuelve las alertas no leidas de las ultimas N horas."""
    try:
        from alerts.alert_manager import AlertManager
        return AlertManager().get_active_alerts(hours=hours)
    except Exception as exc:
        logger.debug("get_active_alerts: %s", exc)
        return []


# ── Eventos geopoliticos ───────────────────────────────────────────────────────

def get_geopolitical_events(months: int = 24) -> list[dict]:
    """Devuelve los eventos geopoliticos de los ultimos N meses."""
    try:
        since = datetime.utcnow() - timedelta(days=months * 30)
        with SessionLocal() as db:
            rows = (
                db.query(GeopoliticalEvent)
                .filter(GeopoliticalEvent.date >= since)
                .order_by(GeopoliticalEvent.date.asc())
                .all()
            )
        return [
            {
                "id": r.id,
                "date": r.date,
                "title": r.title,
                "description": r.description,
                "category": r.category,
                "region": r.region,
                "severity": r.severity,
                "market_impact": r.market_impact,
                "source_url": r.source_url,
                "is_manual": r.is_manual,
            }
            for r in rows
        ]
    except Exception as exc:
        logger.debug("get_geopolitical_events: %s", exc)
        return []


# ── Formateo ───────────────────────────────────────────────────────────────────

def format_value(
    value,
    unit: str = "",
    decimals: int = 2,
    show_sign: bool = False,
) -> str:
    """
    Formatea un numero para mostrar en el dashboard.
    Ejemplos: 1234567 -> '1.23M', 45.6 -> '45.60', None -> '-'
    """
    if value is None:
        return "\u2014"
    try:
        v = float(value)
        sign = "+" if show_sign and v > 0 else ""
        if abs(v) >= 1_000_000_000:
            return f"{sign}{v / 1_000_000_000:.{decimals}f}B{unit}"
        if abs(v) >= 1_000_000:
            return f"{sign}{v / 1_000_000:.{decimals}f}M{unit}"
        if abs(v) >= 10_000:
            return f"{sign}{v:,.0f}{unit}"
        if abs(v) >= 1_000:
            return f"{sign}{v:,.{decimals}f}{unit}"
        return f"{sign}{v:.{decimals}f}{unit}"
    except (TypeError, ValueError):
        return "\u2014"


def time_ago(dt: Optional[datetime]) -> str:
    """
    Convierte un datetime a texto relativo.
    Ejemplos: 'hace 3 horas', 'hace 2 dias', 'hace menos de 1 min'
    """
    if dt is None:
        return "\u2014"
    try:
        if hasattr(dt, "tzinfo") and dt.tzinfo is not None:
            dt = dt.replace(tzinfo=None)
        delta = datetime.utcnow() - dt
        total_seconds = delta.total_seconds()
        if total_seconds < 0:
            return "ahora"
        if total_seconds < 60:
            return "hace menos de 1 min"
        minutes = int(total_seconds // 60)
        if minutes < 60:
            return f"hace {minutes} min"
        hours = minutes // 60
        if hours < 24:
            unit = "hora" if hours == 1 else "horas"
            return f"hace {hours} {unit}"
        days = hours // 24
        if days == 1:
            return "ayer"
        if days < 7:
            return f"hace {days} dias"
        weeks = days // 7
        if weeks < 5:
            unit = "semana" if weeks == 1 else "semanas"
            return f"hace {weeks} {unit}"
        months = days // 30
        unit = "mes" if months == 1 else "meses"
        return f"hace {months} {unit}"
    except Exception:
        return "\u2014"


# ── Contadores de base de datos ────────────────────────────────────────────────

def get_db_indicator_count() -> int:
    """Numero de series distintas en time_series."""
    try:
        from sqlalchemy import func, distinct
        with SessionLocal() as db:
            return db.query(func.count(distinct(TimeSeries.indicator_id))).scalar() or 0
    except Exception:
        return 0


def get_db_source_count() -> int:
    """Numero de fuentes distintas en time_series."""
    try:
        from sqlalchemy import func, distinct
        with SessionLocal() as db:
            return db.query(func.count(distinct(TimeSeries.source))).scalar() or 0
    except Exception:
        return 0


def get_db_last_update() -> Optional[datetime]:
    """Timestamp del ultimo registro insertado en time_series."""
    try:
        from sqlalchemy import func
        with SessionLocal() as db:
            result = db.query(func.max(TimeSeries.timestamp)).scalar()
        return result
    except Exception:
        return None
