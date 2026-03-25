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


# ── Contexto temporal ("viaje en el tiempo") ───────────────────────────────────

# Variable global que controla el filtro de fecha para todas las queries.
# None = modo normal (datos más recientes)
# datetime = modo histórico (datos hasta esa fecha)
_time_context: Optional[datetime] = None


def set_time_context(date=None) -> None:
    """
    Activa o desactiva el modo 'viaje en el tiempo'.

    Args:
        date: None → modo normal (datos actuales)
              str "YYYY-MM-DD" o datetime → modo histórico, filtra datos <= date
    """
    global _time_context
    if date is None:
        _time_context = None
        logger.info("[TimeContext] Modo normal (datos actuales)")
        return
    if isinstance(date, str):
        # Acepta "YYYY-MM-DD" o "YYYY-MM-DDTHH:MM:SS"
        try:
            if "T" in date or " " in date:
                _time_context = datetime.fromisoformat(date.replace(" ", "T"))
            else:
                _time_context = datetime.strptime(date, "%Y-%m-%d").replace(
                    hour=23, minute=59, second=59
                )
        except ValueError:
            logger.warning("[TimeContext] Fecha inválida: %s", date)
            _time_context = None
            return
    elif isinstance(date, datetime):
        _time_context = date
    else:
        logger.warning("[TimeContext] Tipo no soportado: %s", type(date))
        return
    logger.info("[TimeContext] Modo histórico activado: %s", _time_context)


def get_time_context() -> Optional[datetime]:
    """Devuelve el contexto temporal activo, o None si está en modo normal."""
    return _time_context


# ── Lectura de series temporales ───────────────────────────────────────────────

def get_latest_value(
    series_id: str,
    source: Optional[str] = None,
) -> Tuple[Optional[float], Optional[datetime]]:
    """
    Devuelve (valor, timestamp) del dato mas reciente de una serie.
    Si hay contexto temporal activo, filtra por timestamp <= context_date.
    Retorna (None, None) si no existe o hay error.
    """
    try:
        ctx = _time_context
        with SessionLocal() as db:
            q = db.query(TimeSeries).filter(TimeSeries.indicator_id == series_id)
            if source:
                q = q.filter(TimeSeries.source == source)
            if ctx is not None:
                q = q.filter(TimeSeries.timestamp <= ctx)
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
    Si hay contexto temporal activo, los días se calculan relativos a context_date.
    Devuelve DataFrame vacio si no hay datos.
    """
    try:
        ctx = _time_context
        ref_date = ctx if ctx is not None else datetime.utcnow()
        since = ref_date - timedelta(days=days)
        with SessionLocal() as db:
            q = db.query(TimeSeries).filter(
                TimeSeries.indicator_id == series_id,
                TimeSeries.timestamp >= since,
            )
            if ctx is not None:
                q = q.filter(TimeSeries.timestamp <= ctx)
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


def get_value_at_date(
    series_id: str,
    target_date: datetime,
    source: Optional[str] = None,
) -> Tuple[Optional[float], Optional[datetime]]:
    """
    Devuelve (valor, timestamp) del dato más reciente en o antes de target_date.
    Útil para el comparador temporal del Módulo 14.
    """
    try:
        with SessionLocal() as db:
            q = db.query(TimeSeries).filter(
                TimeSeries.indicator_id == series_id,
                TimeSeries.timestamp <= target_date,
            )
            if source:
                q = q.filter(TimeSeries.source == source)
            row = q.order_by(TimeSeries.timestamp.desc()).first()
            if row is None:
                return None, None
            return row.value, row.timestamp
    except Exception as exc:
        logger.debug("get_value_at_date(%s): %s", series_id, exc)
        return None, None


def get_series_between(
    series_id: str,
    date_from: datetime,
    date_to: datetime,
    source: Optional[str] = None,
) -> pd.DataFrame:
    """
    Devuelve un DataFrame(timestamp, value) entre dos fechas, ordenado ascendente.
    """
    try:
        with SessionLocal() as db:
            q = db.query(TimeSeries).filter(
                TimeSeries.indicator_id == series_id,
                TimeSeries.timestamp >= date_from,
                TimeSeries.timestamp <= date_to,
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
        logger.debug("get_series_between(%s): %s", series_id, exc)
        return pd.DataFrame(columns=["timestamp", "value"])


def get_all_indicator_ids() -> list[dict]:
    """
    Devuelve todos los indicator_ids distintos en la BD,
    con su fuente más reciente y último timestamp.
    Útil para construir el dropdown del comparador temporal.
    """
    try:
        from sqlalchemy import func
        with SessionLocal() as db:
            rows = (
                db.query(
                    TimeSeries.indicator_id,
                    TimeSeries.source,
                    func.max(TimeSeries.timestamp).label("last_ts"),
                )
                .group_by(TimeSeries.indicator_id, TimeSeries.source)
                .order_by(TimeSeries.indicator_id)
                .all()
            )
        return [
            {"indicator_id": r.indicator_id, "source": r.source, "last_ts": r.last_ts}
            for r in rows
        ]
    except Exception as exc:
        logger.debug("get_all_indicator_ids: %s", exc)
        return []


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


# ── World Bank helpers ─────────────────────────────────────────────────────────

# Mapeo indicador corto → columna en la comparativa global
_WB_SHORT_TO_LABEL = {
    "gdp_growth":    "Crecimiento PIB (%)",
    "gdp_pc_ppp":    "PIB per cápita PPP (USD)",
    "cpi_inflation": "Inflación (%)",
    "unemployment":  "Desempleo (%)",
    "youth_unemp":   "Desempleo juvenil (%)",
    "gov_debt_pct":  "Deuda/PIB (%)",
    "fiscal_balance":"Déficit fiscal (% PIB)",
    "curr_account":  "Cuenta corriente (% PIB)",
    "trade_pct":     "Apertura comercial (% PIB)",
    "fertility":     "Tasa de fertilidad",
    "pop_growth":    "Crecimiento población (%)",
    "old_dep_ratio": "Ratio dependencia ancianos",
    "gini":          "Índice de Gini",
    "rd_spending":   "Gasto I+D (% PIB)",
    "internet_users":"Usuarios internet (%)",
    "gdp_nominal":   "PIB nominal (USD)",
    "population":    "Población",
    "reserves_usd":  "Reservas divisas (USD)",
}


def get_world_bank_indicator(
    indicator_short_name: str,
    countries: Optional[list] = None,
    year: Optional[int] = None,
) -> pd.DataFrame:
    """
    Devuelve un DataFrame con el valor de un indicador del Banco Mundial
    para todos los países (o los especificados) en un año dado.

    Columns: country_iso3, value, year
    Si year=None, usa el último año disponible por país.
    """
    try:
        with SessionLocal() as db:
            # Buscar todos los series que coincidan con el patrón wb_{indicator_short_name}_%
            pattern = f"wb_{indicator_short_name}_%"
            from sqlalchemy import or_
            rows_q = db.query(
                TimeSeries.indicator_id,
                TimeSeries.value,
                TimeSeries.timestamp,
            ).filter(
                TimeSeries.indicator_id.like(pattern),
                TimeSeries.source == "worldbank",
            )
            all_rows = rows_q.all()
    except Exception as exc:
        logger.debug("get_world_bank_indicator(%s): %s", indicator_short_name, exc)
        return pd.DataFrame(columns=["country_iso3", "value", "year"])

    if not all_rows:
        return pd.DataFrame(columns=["country_iso3", "value", "year"])

    prefix = f"wb_{indicator_short_name}_"

    records = []
    for row in all_rows:
        iso3_raw = row.indicator_id[len(prefix):]
        iso3 = iso3_raw.upper()
        # Filtrar agregados regionales no útiles para mapa (WLD, EUU, etc.)
        if iso3 in ("WLD", "EUU", "EMU", "EAP", "LAC", "SSA", "SAS", "MNA"):
            continue
        if countries and iso3 not in [c.upper() for c in countries]:
            continue
        if row.timestamp is None or row.value is None:
            continue
        yr = row.timestamp.year if hasattr(row.timestamp, "year") else None
        if yr is None:
            continue
        records.append({"country_iso3": iso3, "value": float(row.value), "year": yr})

    if not records:
        return pd.DataFrame(columns=["country_iso3", "value", "year"])

    df = pd.DataFrame(records)

    if year is not None:
        df = df[df["year"] == year]
        if df.empty:
            # Si no hay datos para ese año, buscar el más cercano anterior
            all_years_df = pd.DataFrame(records)
            closest_year = all_years_df[all_years_df["year"] <= year]["year"].max() if not all_years_df[all_years_df["year"] <= year].empty else all_years_df["year"].max()
            df = all_years_df[all_years_df["year"] == closest_year] if not pd.isna(closest_year) else pd.DataFrame(columns=["country_iso3", "value", "year"])
    else:
        # Para cada país: último año con datos
        df = df.sort_values("year", ascending=False).drop_duplicates(subset="country_iso3")

    return df.reset_index(drop=True)


def get_country_comparison(
    indicator_short_names: list,
    countries: Optional[list] = None,
    year: Optional[int] = None,
) -> pd.DataFrame:
    """
    Devuelve un DataFrame con múltiples indicadores en columnas y países en filas.
    Columnas: country_iso3 + cada indicador. NaN si no hay dato.
    """
    result_df = None

    for ind in indicator_short_names:
        df_ind = get_world_bank_indicator(ind, countries=countries, year=year)
        if df_ind.empty:
            continue
        df_ind = df_ind[["country_iso3", "value"]].rename(columns={"value": ind})
        if result_df is None:
            result_df = df_ind
        else:
            result_df = result_df.merge(df_ind, on="country_iso3", how="outer")

    if result_df is None:
        cols = ["country_iso3"] + indicator_short_names
        return pd.DataFrame(columns=cols)

    return result_df.reset_index(drop=True)


# ── Poder adquisitivo ──────────────────────────────────────────────────────────

def calculate_mortgage_payment(
    principal: float,
    years: int,
    euribor_rate: float,
    spread: float,
) -> float:
    """
    Calcula la cuota mensual de una hipoteca variable (amortizacion francesa).

    Parametros:
      principal   : capital pendiente en euros
      years       : años restantes de hipoteca
      euribor_rate: EURIBOR actual en porcentaje (ej. 3.5 para 3.5%)
      spread      : diferencial en porcentaje (ej. 0.99 para +0.99%)

    Devuelve la cuota mensual en euros.
    Fórmula: cuota = P × (r × (1+r)^n) / ((1+r)^n − 1)
    donde r = tipo_anual / 12, n = años × 12
    """
    tipo_anual = (euribor_rate + spread) / 100.0
    if tipo_anual <= 0:
        # Tipo negativo o cero: amortización lineal simple
        n = years * 12
        return round(principal / n, 2) if n > 0 else 0.0
    r = tipo_anual / 12.0
    n = years * 12
    if n <= 0:
        return 0.0
    cuota = principal * (r * (1 + r) ** n) / ((1 + r) ** n - 1)
    return round(cuota, 2)


def calculate_real_purchasing_power(
    amount: float,
    start_date: str,
    country_code: str,
    end_date: Optional[str] = None,
) -> Optional[dict]:
    """
    Calcula la erosion del poder adquisitivo de una cantidad por inflacion acumulada.

    Parametros:
      amount      : cantidad inicial (ej. 10000)
      start_date  : fecha de inicio en formato 'YYYY-MM-DD'
      country_code: 'US', 'EA', 'DE', 'ES', 'IT'
      end_date    : fecha de fin (por defecto hoy)

    Devuelve un dict con:
      valor_nominal, valor_real, perdida_absoluta, perdida_porcentual,
      inflacion_acumulada, serie_temporal (DataFrame mensual)
    O None si no hay datos suficientes.
    """
    CPI_SERIES = {
        "US": "fred_cpi_us",          # nivel mensual → se calcula acumulado
        "EA": "estat_hicp_cp00_ea20",  # YoY anual → se usa acumulado
        "DE": "estat_hicp_cp00_de",
        "ES": "estat_hicp_cp00_es",
        "IT": "estat_hicp_cp00_it",
    }

    sid = CPI_SERIES.get(country_code.upper())
    if sid is None:
        logger.debug("calculate_real_purchasing_power: pais desconocido %s", country_code)
        return None

    try:
        start_dt = datetime.strptime(start_date[:10], "%Y-%m-%d")
    except ValueError:
        return None

    end_dt = datetime.utcnow()
    if end_date:
        try:
            end_dt = datetime.strptime(end_date[:10], "%Y-%m-%d")
        except ValueError:
            pass

    # Pedir datos con suficiente margen
    days_needed = (end_dt - start_dt).days + 60
    df = get_series(sid, days=days_needed)
    if df.empty:
        return None

    df = df.sort_values("timestamp").reset_index(drop=True)

    # Para series de nivel (fred_cpi_us), calcular inflacion acumulada directamente
    if country_code.upper() == "US":
        # Serie de niveles → buscar valor inicio y valor fin
        sub_start = df[df["timestamp"] <= start_dt + timedelta(days=40)]
        sub_end   = df[df["timestamp"] <= end_dt]
        if sub_start.empty or sub_end.empty:
            return None
        cpi_start = float(sub_start.iloc[-1]["value"])
        cpi_end   = float(sub_end.iloc[-1]["value"])
        if cpi_start == 0:
            return None
        acc_inflation = (cpi_end / cpi_start - 1) * 100

        # Serie temporal mensual de valor real
        mask = (df["timestamp"] >= start_dt - timedelta(days=40)) & \
               (df["timestamp"] <= end_dt + timedelta(days=10))
        df_range = df[mask].copy()
        if not df_range.empty:
            df_range["nominal"] = amount
            df_range["real"] = amount * (cpi_start / df_range["value"])
        else:
            df_range = pd.DataFrame(columns=["timestamp", "nominal", "real"])

    else:
        # Serie de YoY% → acumulamos
        sub_start = df[df["timestamp"] <= start_dt + timedelta(days=400)]
        sub_end   = df[df["timestamp"] <= end_dt + timedelta(days=30)]
        if sub_start.empty or sub_end.empty:
            return None

        # Calcular inflacion acumulada compuesta desde los YoY anuales
        mask = (df["timestamp"] >= start_dt - timedelta(days=30)) & \
               (df["timestamp"] <= end_dt + timedelta(days=30))
        df_range = df[mask].copy()

        if df_range.empty:
            return None

        # Deflactar usando acumulado compuesto
        nominal_vals = []
        real_vals = []
        cum_factor = 1.0
        prev_ts = None
        for _, row in df_range.iterrows():
            if prev_ts is not None:
                years_frac = (row["timestamp"] - prev_ts).days / 365.0
                cum_factor *= (1 + row["value"] / 100) ** years_frac
            nominal_vals.append(amount)
            real_vals.append(amount / cum_factor)
            prev_ts = row["timestamp"]

        df_range = df_range.copy()
        df_range["nominal"] = nominal_vals
        df_range["real"] = real_vals
        acc_inflation = (cum_factor - 1) * 100

    valor_real = amount / (1 + acc_inflation / 100)
    perdida = valor_real - amount

    return {
        "valor_nominal":      amount,
        "valor_real":         round(valor_real, 2),
        "perdida_absoluta":   round(perdida, 2),
        "perdida_porcentual": round(perdida / amount * 100, 2),
        "inflacion_acumulada": round(acc_inflation, 2),
        "serie_temporal":     df_range if "timestamp" in df_range.columns else None,
    }


# ── Mercado Laboral (Módulo 6) ─────────────────────────────────────────────────

def calculate_sahm_indicator():
    """
    Calcula el Indicador de Sahm de recesión a partir de fred_unemployment_us.

    Devuelve:
      (sahm_current, alert_level, df_history)
      sahm_current : float o None
      alert_level  : 'green' | 'yellow' | 'red' | None
      df_history   : DataFrame(timestamp, sahm) ordenado ascendente, o vacío
    """
    df = get_series("fred_unemployment_us", days=365 * 30)
    if df.empty or len(df) < 15:
        return None, None, pd.DataFrame(columns=["timestamp", "sahm"])

    df = df.sort_values("timestamp").reset_index(drop=True)
    df["roll3m"] = df["value"].rolling(3).mean()
    df["min12m"] = df["value"].rolling(12).min()
    df["sahm"] = df["roll3m"] - df["min12m"]
    df = df.dropna(subset=["sahm"])

    if df.empty:
        return None, None, pd.DataFrame(columns=["timestamp", "sahm"])

    sahm_current = float(df.iloc[-1]["sahm"])
    if sahm_current < 0.3:
        level = "green"
    elif sahm_current < 0.5:
        level = "yellow"
    else:
        level = "red"

    return sahm_current, level, df[["timestamp", "sahm"]].reset_index(drop=True)


# ── Energía (Módulo 7) ─────────────────────────────────────────────────────────

def load_json_data(filename: str) -> Optional[dict]:
    """
    Carga un fichero JSON de la carpeta data/ del proyecto.
    Devuelve el contenido como diccionario Python.
    Si el fichero no existe, devuelve None con log de warning.
    """
    from pathlib import Path
    data_dir = Path(__file__).resolve().parent.parent / "data"
    filepath = data_dir / filename
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            import json
            return json.load(f)
    except FileNotFoundError:
        logger.warning("load_json_data: fichero no encontrado: %s", filepath)
        return None
    except Exception as exc:
        logger.warning("load_json_data(%s): %s", filename, exc)
        return None


# ── Geopolítica (Módulo 10) ────────────────────────────────────────────────────

def get_conflict_asset_impact(
    affected_assets: list,
    start_date: str,
) -> list:
    """
    Para cada ticker en affected_assets, obtiene el precio en start_date
    y el precio mas reciente de SQLite, calcula la variacion desde el inicio
    del conflicto.

    Parametros:
        affected_assets: lista de indicator_ids (ej. ["yf_bz_close", "yf_gc_close"])
                         o tickers de Yahoo Finance (ej. ["BZ=F", "GC=F"])
        start_date: fecha de inicio del conflicto en formato "YYYY-MM-DD"

    Retorna lista de dicts:
        ticker, nombre_legible, precio_inicio, precio_actual, variacion_pct, variacion_abs
    Si no hay dato para un ticker, devuelve None para ese ticker.
    """
    from datetime import datetime, timedelta

    # Mapeo de tickers Yahoo -> indicator_id SQLite y nombres legibles
    TICKER_TO_ID = {
        "BZ=F":     ("yf_bz_close",      "Brent Crude"),
        "NG=F":     ("yf_ng_close",       "Gas Natural"),
        "GC=F":     ("yf_gc_close",       "Oro"),
        "^VIX":     ("yf_vix_close",      "VIX"),
        "DX-Y.NYB": ("yf_dxy_close",      "Dólar (DXY)"),
        "ZW=F":     ("yf_zw_close",       "Trigo"),
        "ZC=F":     ("yf_zc_close",       "Maíz"),
        "EURUSD=X": ("yf_eurusd_close",   "EUR/USD"),
        "SOXX":     ("yf_soxx_close",     "Semiconductores (SOXX)"),
        "TSM":      ("yf_tsm_close",      "TSMC"),
        "MCHI":     ("yf_mchi_close",     "China ETF"),
        "EEM":      ("yf_eem_close",      "Emergentes (EEM)"),
        "^GSPC":    ("yf_sp500_close",    "S&P 500"),
    }

    results = []
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    except (ValueError, TypeError):
        return []

    window = timedelta(days=3)

    for ticker in affected_assets:
        entry = TICKER_TO_ID.get(ticker)
        if entry is None:
            # Intentar construir el indicator_id a partir del ticker directamente
            indicator_id = f"yf_{ticker.lower().replace('=', '').replace('^', '').replace('-', '_')}_close"
            nombre = ticker
        else:
            indicator_id, nombre = entry

        try:
            with SessionLocal() as db:
                # Precio en start_date (±3 dias)
                row_start = (
                    db.query(TimeSeries)
                    .filter(
                        TimeSeries.indicator_id == indicator_id,
                        TimeSeries.timestamp >= start_dt - window,
                        TimeSeries.timestamp <= start_dt + window,
                    )
                    .order_by(
                        # Ordenar por distancia a la fecha objetivo
                        (TimeSeries.timestamp - start_dt).desc()
                    )
                    .first()
                )
                # Precio actual
                row_current = (
                    db.query(TimeSeries)
                    .filter(TimeSeries.indicator_id == indicator_id)
                    .order_by(TimeSeries.timestamp.desc())
                    .first()
                )

            if row_start is None or row_current is None:
                results.append(None)
                continue

            p_start = float(row_start.value) if row_start.value is not None else None
            p_current = float(row_current.value) if row_current.value is not None else None

            if p_start is None or p_current is None or p_start == 0:
                results.append(None)
                continue

            var_abs = p_current - p_start
            var_pct = (var_abs / abs(p_start)) * 100

            results.append({
                "ticker":         ticker,
                "nombre":         nombre,
                "indicator_id":   indicator_id,
                "precio_inicio":  p_start,
                "precio_actual":  p_current,
                "variacion_abs":  var_abs,
                "variacion_pct":  var_pct,
            })
        except Exception as exc:
            logger.debug("get_conflict_asset_impact(%s): %s", ticker, exc)
            results.append(None)

    return results


def calculate_gpr_percentile(
    current_gpr: float,
    series_id: str = "GPRC",
) -> dict:
    """
    Calcula en que percentil historico esta el valor actual del GPR.

    Parametros:
        current_gpr: valor actual del GPR
        series_id:   'GPRC' (desde 1985) o 'GPRH' (desde 1900)

    Retorna dict con:
        percentile: valor 0-100
        interpretation: texto descriptivo
        n_months_total: total de meses en la serie historica
        n_months_higher: meses historicos con GPR mas alto
        comparative_events: lista de eventos historicos con GPR similar
    """
    # Mapeo del series_id al indicator_id en BD
    ID_MAP = {
        "GPRC": "fred_gpr_gprc",
        "GPRH": "fred_gpr_gprh",
        "GPR":  "fred_gpr_gprc",
    }
    indicator_id = ID_MAP.get(series_id, "fred_gpr_gprc")

    # Eventos historicos de referencia (GPR aproximado)
    HISTORICAL_EVENTS = [
        {"label": "11-S (2001)",            "gpr": 450},
        {"label": "Guerra Golfo (1990)",    "gpr": 280},
        {"label": "Ucrania (2022)",         "gpr": 230},
        {"label": "Irak (2003)",            "gpr": 200},
        {"label": "COVID-19 (2020)",        "gpr": 160},
        {"label": "Corea del Norte (2017)", "gpr": 150},
        {"label": "Crimea (2014)",          "gpr": 130},
        {"label": "Nivel normal",           "gpr": 100},
    ]

    default = {
        "percentile": None,
        "interpretation": "Datos históricos no disponibles",
        "n_months_total": 0,
        "n_months_higher": 0,
        "comparative_events": [],
    }

    if current_gpr is None:
        return default

    try:
        with SessionLocal() as db:
            rows = (
                db.query(TimeSeries.value)
                .filter(
                    TimeSeries.indicator_id == indicator_id,
                    TimeSeries.value.isnot(None),
                )
                .all()
            )

        if not rows:
            return default

        values = [float(r.value) for r in rows if r.value is not None]
        if len(values) < 10:
            return default

        n_total = len(values)
        n_higher = sum(1 for v in values if v > current_gpr)
        percentile = round((1 - n_higher / n_total) * 100, 1)

        # Generar interpretacion textual
        if percentile >= 99:
            interp = f"GPR en el percentil {percentile} — nivel prácticamente sin precedentes históricos"
        elif percentile >= 95:
            interp = f"GPR en el percentil {percentile} — zona de crisis histórica (top 5% de todos los registros)"
        elif percentile >= 90:
            interp = f"GPR en el percentil {percentile} — tensión muy elevada (top 10% histórico)"
        elif percentile >= 75:
            interp = f"GPR en el percentil {percentile} — tensión significativa (cuartil superior)"
        elif percentile >= 50:
            interp = f"GPR en el percentil {percentile} — por encima de la mediana histórica"
        else:
            interp = f"GPR en el percentil {percentile} — nivel moderado o bajo históricamente"

        # Eventos comparativos cercanos
        comparative = [
            ev for ev in HISTORICAL_EVENTS
            if abs(ev["gpr"] - current_gpr) <= 60
        ]
        comparative.sort(key=lambda e: abs(e["gpr"] - current_gpr))

        return {
            "percentile":         percentile,
            "interpretation":     interp,
            "n_months_total":     n_total,
            "n_months_higher":    n_higher,
            "comparative_events": comparative[:3],
        }

    except Exception as exc:
        logger.debug("calculate_gpr_percentile: %s", exc)
        return default


# ── Sistema Financiero (Módulo 9) ──────────────────────────────────────────────

def calculate_hy_spread_proxy() -> Optional[float]:
    """
    Calcula un proxy del spread High Yield (HY) en puntos basicos.
    Metodo: diferencia de yield implicita entre HYG e IEF.
    yield_implicito = (cupon_anual_estimado / precio) * 100
    spread = yield_HYG - yield_IEF  (en %)  → convertir a pb × 100

    Cupon anual estimado:
      HYG ≈ 4.5 USD/year (distribucion mensual ~0.375)
      IEF ≈ 2.5 USD/year (bono tesoro 7-10y)

    Si el calculo falla o hay override activado en credit_spreads_override.json,
    devuelve el valor estatico.
    """
    # Comprobar override primero
    try:
        from pathlib import Path
        import json
        override_path = Path(__file__).resolve().parent.parent / "data" / "credit_spreads_override.json"
        with open(override_path, "r", encoding="utf-8") as f:
            override = json.load(f)
        if override.get("use_override", False):
            return float(override.get("hy_spread_bp", 380))
    except Exception:
        pass

    try:
        hyg_val, _ = get_latest_value("yf_hyg_close")
        ief_val, _ = get_latest_value("yf_ief_close")

        if hyg_val is None or ief_val is None or hyg_val <= 0 or ief_val <= 0:
            return None

        # Cupones anuales estimados (distribuciones historicas tipicas)
        CUPON_HYG = 4.5   # USD/año estimado
        CUPON_IEF = 2.5   # USD/año estimado

        yield_hyg = (CUPON_HYG / float(hyg_val)) * 100
        yield_ief = (CUPON_IEF / float(ief_val)) * 100

        spread_pct = yield_hyg - yield_ief
        spread_bp = spread_pct * 100  # Convertir % a puntos basicos

        # Sanity check: spread HY debe estar entre 100 y 3000 pb
        if 100 <= spread_bp <= 3000:
            return round(spread_bp, 0)

        # Si el resultado es irreal, intentar con valores de fallback
        return None
    except Exception as exc:
        logger.debug("calculate_hy_spread_proxy: %s", exc)
        return None


def calculate_ig_spread_proxy() -> Optional[float]:
    """
    Calcula un proxy del spread Investment Grade (IG) en puntos basicos.
    Metodo analogo a calculate_hy_spread_proxy() con LQD e IEF.
    Cupon estimado LQD ≈ 3.0 USD/año
    """
    try:
        from pathlib import Path
        import json
        override_path = Path(__file__).resolve().parent.parent / "data" / "credit_spreads_override.json"
        with open(override_path, "r", encoding="utf-8") as f:
            override = json.load(f)
        if override.get("use_override", False):
            return float(override.get("ig_spread_bp", 95))
    except Exception:
        pass

    try:
        lqd_val, _ = get_latest_value("yf_lqd_close")
        ief_val, _ = get_latest_value("yf_ief_close")

        if lqd_val is None or ief_val is None or lqd_val <= 0 or ief_val <= 0:
            return None

        CUPON_LQD = 3.0
        CUPON_IEF = 2.5

        yield_lqd = (CUPON_LQD / float(lqd_val)) * 100
        yield_ief = (CUPON_IEF / float(ief_val)) * 100

        spread_pct = yield_lqd - yield_ief
        spread_bp = spread_pct * 100

        if 20 <= spread_bp <= 800:
            return round(spread_bp, 0)
        return None
    except Exception as exc:
        logger.debug("calculate_ig_spread_proxy: %s", exc)
        return None


def calculate_systemic_risk_index() -> dict:
    """
    Calcula el Indice Compuesto de Riesgo Sistemico (0-100).

    Componentes y pesos:
      - STLFSI4 (estres financiero Fed St. Louis): peso 30%
        Normalizado: min=-10 → 0, max=10 → 100
      - Spread HY (proxy HYG/IEF): peso 25%
        Normalizado: min=200pb → 0, max=2000pb → 100
      - Spread IG (proxy LQD/IEF): peso 15%
        Normalizado: min=50pb → 0, max=500pb → 100
      - VIX: peso 20%
        Normalizado: min=10 → 0, max=80 → 100
      - Prima de riesgo Italia (ecb_spread_it_de): peso 10%
        Normalizado: min=0pb → 0, max=600pb → 100

    Si un componente no esta disponible, se excluye y se redistribuyen pesos.

    Devuelve dict con:
      indice_compuesto (0-100)
      nivel ('green' | 'yellow_green' | 'yellow' | 'orange' | 'red')
      componentes: lista de dicts con nombre, valor_raw, valor_normalizado, peso, contribucion
    """

    def _normalize(val, min_val, max_val):
        """Normaliza val a [0, 100] segun los rangos historicos."""
        if val is None:
            return None
        v = float(val)
        rng = max_val - min_val
        if rng == 0:
            return 0.0
        norm = (v - min_val) / rng * 100.0
        return max(0.0, min(100.0, norm))

    # Definicion de los 5 componentes
    spec = [
        {
            "nombre": "STLFSI4 (Estres Fed)",
            "series_id": "fred_stlfsi4_us",
            "min_val": -10.0,
            "max_val": 10.0,
            "peso_base": 0.30,
            "unit": "",
        },
        {
            "nombre": "Spread HY (pb)",
            "series_id": None,  # Calculado via funcion
            "min_val": 200.0,
            "max_val": 2000.0,
            "peso_base": 0.25,
            "unit": "pb",
        },
        {
            "nombre": "Spread IG (pb)",
            "series_id": None,
            "min_val": 50.0,
            "max_val": 500.0,
            "peso_base": 0.15,
            "unit": "pb",
        },
        {
            "nombre": "VIX",
            "series_id": "yf_vix_close",
            "min_val": 10.0,
            "max_val": 80.0,
            "peso_base": 0.20,
            "unit": "",
        },
        {
            "nombre": "Prima Riesgo Italia (pb)",
            "series_id": "ecb_spread_it_de",
            "min_val": 0.0,
            "max_val": 600.0,
            "peso_base": 0.10,
            "unit": "pb",
        },
    ]

    # Obtener valores crudos
    raw_values = []
    for s in spec:
        if s["series_id"] is not None:
            val, _ = get_latest_value(s["series_id"])
        elif s["nombre"].startswith("Spread HY"):
            val = calculate_hy_spread_proxy()
        elif s["nombre"].startswith("Spread IG"):
            val = calculate_ig_spread_proxy()
        else:
            val = None
        raw_values.append(val)

    # Normalizar y calcular pesos redistribuidos
    normalized = []
    for i, s in enumerate(spec):
        n = _normalize(raw_values[i], s["min_val"], s["max_val"])
        normalized.append(n)

    # Redistribuir pesos si hay componentes sin datos
    pesos_activos = []
    for i, n in enumerate(normalized):
        if n is not None:
            pesos_activos.append((i, spec[i]["peso_base"]))

    if not pesos_activos:
        return {
            "indice_compuesto": None,
            "nivel": "gray",
            "componentes": [],
        }

    total_peso_activo = sum(p for _, p in pesos_activos)
    pesos_finales = {}
    for idx, peso in pesos_activos:
        pesos_finales[idx] = peso / total_peso_activo  # Redistribuir a 100%

    # Calcular indice compuesto
    indice = 0.0
    componentes = []
    for i, s in enumerate(spec):
        n = normalized[i]
        peso_final = pesos_finales.get(i, 0.0)
        contribucion = (n * peso_final) if n is not None else None

        if contribucion is not None:
            indice += contribucion

        componentes.append({
            "nombre": s["nombre"],
            "valor_raw": raw_values[i],
            "valor_normalizado": round(n, 1) if n is not None else None,
            "peso_base_pct": round(s["peso_base"] * 100, 0),
            "peso_final_pct": round(peso_final * 100, 1),
            "contribucion": round(contribucion, 2) if contribucion is not None else None,
            "unit": s["unit"],
        })

    indice = round(indice, 1)

    # Determinar nivel
    if indice < 25:
        nivel = "green"
    elif indice < 50:
        nivel = "yellow_green"
    elif indice < 65:
        nivel = "yellow"
    elif indice < 80:
        nivel = "orange"
    else:
        nivel = "red"

    return {
        "indice_compuesto": indice,
        "nivel": nivel,
        "componentes": componentes,
    }


def calculate_oil_inflation_correlation(months: int = 60) -> Optional[dict]:
    """
    Calcula la correlación de Pearson entre el precio del Brent y la inflación americana.

    - Lee BZ=F (yf_bz_close) y CPI americano (fred_cpi_us) de SQLite.
    - Desplaza el CPI 3 meses hacia atrás para capturar el efecto retardado.
    - Calcula correlación de Pearson y p-valor.
    - También estima cuánto sube la inflación por cada 10$ de subida del Brent.

    Devuelve dict con: correlation, p_value, slope_per_10usd, n_obs
    O None si hay menos de 24 meses de datos solapados.
    """
    try:
        from scipy import stats as sp_stats
    except ImportError:
        sp_stats = None

    days = months * 32 + 120
    df_brent = get_series("yf_bz_close", days=days)
    df_cpi   = get_series("fred_cpi_us", days=days)

    if df_brent.empty or df_cpi.empty:
        return None

    # Resamplear ambas series a frecuencia mensual (último valor del mes)
    df_brent["timestamp"] = pd.to_datetime(df_brent["timestamp"])
    df_cpi["timestamp"]   = pd.to_datetime(df_cpi["timestamp"])

    df_brent = df_brent.set_index("timestamp").resample("MS").last().rename(columns={"value": "brent"})
    df_cpi   = df_cpi.set_index("timestamp").resample("MS").last().rename(columns={"value": "cpi"})

    # Calcular YoY del CPI si son datos de nivel (fred_cpi_us es nivel)
    df_cpi["cpi_yoy"] = df_cpi["cpi"].pct_change(12) * 100

    # Desplazar el CPI 3 meses hacia atrás (el petróleo adelanta a la inflación)
    df_cpi_shifted = df_cpi[["cpi_yoy"]].shift(-3)

    merged = df_brent.join(df_cpi_shifted, how="inner").dropna()
    merged = merged.tail(months)

    if len(merged) < 24:
        return None

    brent_vals = merged["brent"].values
    cpi_vals   = merged["cpi_yoy"].values

    if sp_stats is not None:
        slope, intercept, r_value, p_value, std_err = sp_stats.linregress(brent_vals, cpi_vals)
        correlation = r_value
    else:
        # Fallback: correlación de numpy
        correlation = float(pd.Series(brent_vals).corr(pd.Series(cpi_vals)))
        # Estimación de la pendiente por mínimos cuadrados manual
        x = brent_vals - brent_vals.mean()
        y = cpi_vals - cpi_vals.mean()
        slope = float((x * y).sum() / (x ** 2).sum()) if (x ** 2).sum() > 0 else 0.0
        p_value = None

    slope_per_10usd = slope * 10

    return {
        "correlation":    round(float(correlation), 3),
        "p_value":        round(float(p_value), 4) if p_value is not None else None,
        "slope_per_10usd": round(float(slope_per_10usd), 3),
        "n_obs":          len(merged),
        "df":             merged.reset_index(),
    }


# ── Deuda y Sostenibilidad Fiscal (Módulo 8) ───────────────────────────────────

def calculate_debt_sustainability(country_iso3: str) -> Optional[dict]:
    """
    Calcula la dinámica de sostenibilidad de la deuda para un país.

    Ecuación: Δ(D/Y) = (r - g) × (D/Y) - pb
    Donde:
      r  = tipo de interés real
      g  = tasa de crecimiento real del PIB
      D/Y = ratio deuda/PIB
      pb = superávit primario como % del PIB

    Devuelve un dict con: r, g, r_minus_g, primary_balance,
    delta_debt_gdp, debt_gdp, classification, interpretation.
    Devuelve None si no hay datos suficientes.
    """
    iso3 = country_iso3.upper()
    iso3_lower = iso3.lower()

    # -- Deuda/PIB (World Bank: gov_debt_pct) --
    df_debt = get_series(f"wb_gov_debt_pct_{iso3_lower}", days=365 * 5)
    if df_debt.empty:
        logger.debug("calculate_debt_sustainability(%s): sin datos de deuda", iso3)
        return None
    debt_gdp = float(df_debt.sort_values("timestamp").iloc[-1]["value"])

    # -- Superávit primario: fiscal_balance (% PIB) --
    df_fiscal = get_series(f"wb_fiscal_balance_{iso3_lower}", days=365 * 5)
    if df_fiscal.empty:
        # Aproximación: ingresos - gastos excl. intereses (si disponible)
        df_rev = get_series(f"wb_tax_revenue_pct_{iso3_lower}", days=365 * 5)
        df_exp = get_series(f"wb_gov_spend_pct_{iso3_lower}", days=365 * 5)
        if not df_rev.empty and not df_exp.empty:
            rev = float(df_rev.sort_values("timestamp").iloc[-1]["value"])
            exp = float(df_exp.sort_values("timestamp").iloc[-1]["value"])
            primary_balance = rev - exp   # aproximación burda
        else:
            primary_balance = 0.0
    else:
        primary_balance = float(df_fiscal.sort_values("timestamp").iloc[-1]["value"])

    # -- Crecimiento del PIB (g) --
    df_gdp = get_series(f"wb_gdp_growth_{iso3_lower}", days=365 * 5)
    if df_gdp.empty:
        g = 2.0  # fallback neutro
    else:
        g = float(df_gdp.sort_values("timestamp").iloc[-1]["value"])

    # -- Tipo de interés real (r) --
    # Para EE.UU. usamos la serie derivada de FRED
    if iso3 == "USA":
        df_r = get_series("fred_real_rate_us", days=365 * 2)
        r = float(df_r.sort_values("timestamp").iloc[-1]["value"]) if not df_r.empty else 2.0
    else:
        # Aproximación: usamos tipo BCE/global de referencia + diferencial CDS (simplificado)
        # Sin datos directos, estimamos r ≈ inflación objetivo 2% + prima de riesgo implícita
        # Para países europeos: tipo real ≈ rendimiento bono 10Y real (si disponible)
        spread_map = {
            "ESP": "ecb_spread_es_de", "ITA": "ecb_spread_it_de",
            "FRA": "ecb_spread_fr_de", "PRT": "ecb_spread_pt_de",
            "GRC": "ecb_spread_gr_de",
        }
        sid_spread = spread_map.get(iso3)
        if sid_spread:
            df_sp = get_series(sid_spread, days=365)
            spread = float(df_sp.sort_values("timestamp").iloc[-1]["value"]) if not df_sp.empty else 0.0
            # r real ≈ base BCE real (≈0.5%) + spread / 100 convertido a pct
            r = 0.5 + spread  # spread ya en puntos porcentuales
        else:
            r = 2.5  # fallback global (ej. JPN, CHN, GBR, BRA)

    r_minus_g = r - g
    delta_debt_gdp = (r_minus_g / 100) * debt_gdp - primary_balance

    # Clasificación
    if delta_debt_gdp < -0.5:
        classification = "sostenible"
        interpretation = f"La deuda de {iso3} está bajando a ritmo de {abs(delta_debt_gdp):.1f}pp/año"
    elif delta_debt_gdp < 0.5:
        classification = "estabilizando"
        interpretation = f"La deuda de {iso3} se mantiene estable (Δ ≈ {delta_debt_gdp:.1f}pp/año)"
    elif delta_debt_gdp < 2.0:
        classification = "insostenible_leve"
        interpretation = f"La deuda de {iso3} sube ~{delta_debt_gdp:.1f}pp/año (insostenible moderado)"
    else:
        classification = "insostenible_grave"
        interpretation = f"La deuda de {iso3} sube ~{delta_debt_gdp:.1f}pp/año (insostenible grave)"

    return {
        "country": iso3,
        "r": round(r, 2),
        "g": round(g, 2),
        "r_minus_g": round(r_minus_g, 2),
        "primary_balance": round(primary_balance, 2),
        "debt_gdp": round(debt_gdp, 1),
        "delta_debt_gdp": round(delta_debt_gdp, 2),
        "classification": classification,
        "interpretation": interpretation,
    }


def calculate_financial_repression_transfer(
    debt_total_bn: float,
    real_rate_pct: float,
    population_millions: float,
) -> Optional[dict]:
    """
    Calcula la transferencia de riqueza implícita en la represión financiera.

    Parámetros:
      debt_total_bn      : deuda total en miles de millones USD
      real_rate_pct      : tipo real en % (negativo = represión financiera)
      population_millions: población en millones

    Devuelve dict con transferencia_total_bn y transferencia_per_capita,
    o None si el tipo real no es negativo (no hay represión).
    """
    if real_rate_pct >= 0:
        return None   # No hay represión financiera
    transferencia_total_bn = debt_total_bn * abs(real_rate_pct) / 100.0
    if population_millions > 0:
        transferencia_per_capita = (transferencia_total_bn * 1_000) / population_millions
    else:
        transferencia_per_capita = 0.0
    return {
        "real_rate_pct": real_rate_pct,
        "transferencia_total_bn": round(transferencia_total_bn, 1),
        "transferencia_per_capita": round(transferencia_per_capita, 0),
    }


def get_nfp_history(months: int = 24) -> pd.DataFrame:
    """
    Devuelve el historial de NFP de los últimos N meses.
    Como el DB almacena el nivel acumulado (miles de empleos), calcula las
    variaciones mensuales cuando hay suficiente historia.

    Columns: fecha, nfp_level, nfp_mom, avg_3m, avg_12m
    """
    days = months * 32 + 400
    df = get_series("fred_nfp_us", days=days)
    if df.empty:
        return pd.DataFrame(columns=["fecha", "nfp_level", "nfp_mom", "avg_3m", "avg_12m"])

    df = df.sort_values("timestamp").reset_index(drop=True)
    df["nfp_mom"] = df["value"].diff()   # variación mensual en miles
    df["avg_3m"]  = df["nfp_mom"].rolling(3).mean()
    df["avg_12m"] = df["nfp_mom"].rolling(12).mean()
    df = df.rename(columns={"timestamp": "fecha", "value": "nfp_level"})
    df = df.tail(months).reset_index(drop=True)
    return df[["fecha", "nfp_level", "nfp_mom", "avg_3m", "avg_12m"]]


# ── Indicadores Adelantados (Módulo 11) ────────────────────────────────────────

def calculate_recession_probability() -> dict:
    """
    Calcula la probabilidad de recesión en los próximos 12 meses.

    Modelo de puntos:
      T10Y2Y < 0           → +30 pts
      Sahm >= 0.5          → +40 pts  (o +20 si >= 0.3)
      LEI caída >4% 6m     → +20 pts
      ICSA media4s > 300k  → +15 pts
      STLFSI4 > 2          → +20 pts  (o +10 si > 1)
    Cap: 95%

    Retorna dict: probability, level, components, interpretation
    """
    pts = 0
    max_pts = 135  # suma máxima posible
    available_pts = 0
    components = []

    # 1. Curva T10Y2Y
    t10y2y, _ = get_latest_value("fred_t10y2y_us")
    if t10y2y is not None:
        available_pts += 30
        if t10y2y < 0:
            pts += 30
            components.append({"name": "Curva 10Y-2Y", "value": f"{t10y2y:.2f}%", "contribution": 30, "alert": True})
        else:
            components.append({"name": "Curva 10Y-2Y", "value": f"{t10y2y:.2f}%", "contribution": 0, "alert": False})

    # 2. Regla de Sahm
    sahm_val, _, _ = calculate_sahm_indicator()
    if sahm_val is not None:
        available_pts += 40
        if sahm_val >= 0.5:
            pts += 40
            components.append({"name": "Regla de Sahm", "value": f"{sahm_val:.2f}", "contribution": 40, "alert": True})
        elif sahm_val >= 0.3:
            pts += 20
            components.append({"name": "Regla de Sahm", "value": f"{sahm_val:.2f}", "contribution": 20, "alert": True})
        else:
            components.append({"name": "Regla de Sahm", "value": f"{sahm_val:.2f}", "contribution": 0, "alert": False})

    # 3. LEI tendencia (USSLIND)
    lei_df = get_series("fred_lei_us", days=210)
    if not lei_df.empty and len(lei_df) >= 6:
        lei_df = lei_df.sort_values("timestamp")
        lei_current = float(lei_df.iloc[-1]["value"])
        lei_6m_ago  = float(lei_df.iloc[-6]["value"])
        available_pts += 20
        if lei_6m_ago != 0:
            lei_chg = (lei_current - lei_6m_ago) / abs(lei_6m_ago) * 100
            if lei_chg < -4:
                pts += 20
                components.append({"name": "LEI (6m cambio)", "value": f"{lei_chg:.1f}%", "contribution": 20, "alert": True})
            else:
                components.append({"name": "LEI (6m cambio)", "value": f"{lei_chg:.1f}%", "contribution": 0, "alert": False})

    # 4. Solicitudes desempleo ICSA (media 4 semanas)
    icsa_df = get_series("fred_jobless_claims_us", days=40)
    if not icsa_df.empty and len(icsa_df) >= 4:
        icsa_df = icsa_df.sort_values("timestamp")
        icsa_4w = float(icsa_df.tail(4)["value"].mean())
        available_pts += 15
        if icsa_4w > 300_000:
            pts += 15
            components.append({"name": "Solicitudes desempleo (4s)", "value": f"{icsa_4w:,.0f}", "contribution": 15, "alert": True})
        else:
            components.append({"name": "Solicitudes desempleo (4s)", "value": f"{icsa_4w:,.0f}", "contribution": 0, "alert": False})

    # 5. STLFSI4
    stlfsi, _ = get_latest_value("fred_financial_stress_us")
    if stlfsi is not None:
        available_pts += 20
        if stlfsi > 2:
            pts += 20
            components.append({"name": "STLFSI4", "value": f"{stlfsi:.2f}", "contribution": 20, "alert": True})
        elif stlfsi > 1:
            pts += 10
            components.append({"name": "STLFSI4", "value": f"{stlfsi:.2f}", "contribution": 10, "alert": True})
        else:
            components.append({"name": "STLFSI4", "value": f"{stlfsi:.2f}", "contribution": 0, "alert": False})

    # Calcular probabilidad proporcional
    if available_pts == 0:
        prob = 0.0
    else:
        prob = min(95.0, (pts / available_pts) * 100)

    if prob < 15:
        level = "green"
        interp = "Riesgo de recesión bajo. Los indicadores adelantados no señalan deterioro inminente."
    elif prob < 30:
        level = "yellow_green"
        interp = "Riesgo de recesión moderado-bajo. Algunos indicadores merecen seguimiento."
    elif prob < 50:
        level = "yellow"
        interp = "Riesgo de recesión moderado. Varios indicadores adelantados muestran señales de alerta."
    elif prob < 70:
        level = "orange"
        interp = "Riesgo de recesión elevado. La mayoría de indicadores apuntan a desaceleración significativa."
    else:
        level = "red"
        interp = "Riesgo de recesión muy alto. Los indicadores adelantados señalan recesión probable en los próximos 12 meses."

    return {
        "probability": round(prob, 1),
        "level": level,
        "components": components,
        "interpretation": interp,
        "pts": pts,
        "available_pts": available_pts,
    }


def calculate_inflation_pressure() -> dict:
    """
    Calcula el índice de presión inflacionaria (0-100).

    Componentes:
      IPP YoY > 3%         → +20 pts
      T5YIE > 2.5%         → +20 pts
      Crecimiento salarial > 4.5% → +20 pts
      Brent YoY > +20%     → +20 pts
      Cobre YoY > +15%     → +20 pts

    Retorna dict: index, level, components, interpretation
    """
    pts = 0
    available_pts = 0
    components = []

    # 1. IPP YoY
    ppi_val, ppi_prev, _, _ = get_change("fred_ppi_us", period_days=365)
    if ppi_val is not None and ppi_prev is not None and ppi_prev != 0:
        ppi_yoy = (ppi_val - ppi_prev) / abs(ppi_prev) * 100
        available_pts += 20
        if ppi_yoy > 3:
            pts += 20
            components.append({"name": "IPP (YoY)", "value": f"{ppi_yoy:.1f}%", "contribution": 20, "alert": True})
        elif ppi_yoy > 0:
            pts += 10
            components.append({"name": "IPP (YoY)", "value": f"{ppi_yoy:.1f}%", "contribution": 10, "alert": True})
        else:
            components.append({"name": "IPP (YoY)", "value": f"{ppi_yoy:.1f}%", "contribution": 0, "alert": False})

    # 2. Expectativas inflación 5Y
    t5yie, _ = get_latest_value("fred_inflation_exp_5y_us")
    if t5yie is not None:
        available_pts += 20
        if t5yie > 3:
            pts += 20
            components.append({"name": "Expectativas 5Y (T5YIE)", "value": f"{t5yie:.2f}%", "contribution": 20, "alert": True})
        elif t5yie > 2.5:
            pts += 10
            components.append({"name": "Expectativas 5Y (T5YIE)", "value": f"{t5yie:.2f}%", "contribution": 10, "alert": True})
        else:
            components.append({"name": "Expectativas 5Y (T5YIE)", "value": f"{t5yie:.2f}%", "contribution": 0, "alert": False})

    # 3. Crecimiento salarial (CES0500000003 YoY)
    wage_val, wage_prev, _, _ = get_change("fred_wages_us", period_days=365)
    if wage_val is not None and wage_prev is not None and wage_prev != 0:
        wage_yoy = (wage_val - wage_prev) / abs(wage_prev) * 100
        available_pts += 20
        if wage_yoy > 5:
            pts += 20
            components.append({"name": "Crecimiento salarial (YoY)", "value": f"{wage_yoy:.1f}%", "contribution": 20, "alert": True})
        elif wage_yoy > 4.5:
            pts += 10
            components.append({"name": "Crecimiento salarial (YoY)", "value": f"{wage_yoy:.1f}%", "contribution": 10, "alert": True})
        else:
            components.append({"name": "Crecimiento salarial (YoY)", "value": f"{wage_yoy:.1f}%", "contribution": 0, "alert": False})

    # 4. Brent YoY
    brent_val, brent_prev, _, _ = get_change("yf_bz_close", period_days=365)
    if brent_val is not None and brent_prev is not None and brent_prev != 0:
        brent_yoy = (brent_val - brent_prev) / abs(brent_prev) * 100
        available_pts += 20
        if brent_yoy > 20:
            pts += 20
            components.append({"name": "Brent (YoY)", "value": f"{brent_yoy:+.1f}%", "contribution": 20, "alert": True})
        elif brent_yoy > 10:
            pts += 10
            components.append({"name": "Brent (YoY)", "value": f"{brent_yoy:+.1f}%", "contribution": 10, "alert": True})
        else:
            components.append({"name": "Brent (YoY)", "value": f"{brent_yoy:+.1f}%", "contribution": 0, "alert": False})

    # 5. Cobre YoY
    copper_val, copper_prev, _, _ = get_change("yf_hg_close", period_days=365)
    if copper_val is not None and copper_prev is not None and copper_prev != 0:
        copper_yoy = (copper_val - copper_prev) / abs(copper_prev) * 100
        available_pts += 20
        if copper_yoy > 15:
            pts += 20
            components.append({"name": "Cobre (YoY)", "value": f"{copper_yoy:+.1f}%", "contribution": 20, "alert": True})
        elif copper_yoy > 5:
            pts += 10
            components.append({"name": "Cobre (YoY)", "value": f"{copper_yoy:+.1f}%", "contribution": 10, "alert": True})
        else:
            components.append({"name": "Cobre (YoY)", "value": f"{copper_yoy:+.1f}%", "contribution": 0, "alert": False})

    if available_pts == 0:
        idx = 0.0
    else:
        idx = min(100.0, (pts / available_pts) * 100)

    if idx < 25:
        level = "green"
        interp = "Presión inflacionaria baja. Los indicadores no anticipan repunte de inflación próximo."
    elif idx < 50:
        level = "yellow"
        interp = "Presión inflacionaria moderada. Algunos indicadores señalan posible repunte de inflación."
    elif idx < 75:
        level = "orange"
        interp = "Presión inflacionaria alta. Varios indicadores sugieren que la inflación puede acelerarse."
    else:
        level = "red"
        interp = "Presión inflacionaria muy alta. Los indicadores anticipan un repunte significativo de la inflación."

    return {
        "index": round(idx, 1),
        "level": level,
        "components": components,
        "interpretation": interp,
    }


def generate_indicator_summary() -> dict:
    """
    Genera un resumen narrativo del estado de todos los indicadores adelantados.

    Retorna dict: text, counts (por nivel), top3_concerns
    """
    from datetime import date

    rec = calculate_recession_probability()
    fin = calculate_systemic_risk_index()
    inf = calculate_inflation_pressure()

    gpr_val, _ = get_latest_value("fred_gpr_gprc")

    # Mapa nivel → número
    _level_order = {"green": 0, "yellow_green": 1, "yellow": 2, "orange": 3, "red": 4}

    concerns = []
    concerns.append({"name": "Riesgo recesión", "level": rec["level"], "value": f"{rec['probability']:.0f}%"})
    fin_level = fin.get("level", "gray")
    fin_idx   = fin.get("composite_index", fin.get("index", 0))
    concerns.append({"name": "Riesgo sistémico", "level": fin_level, "value": f"{fin_idx:.0f}/100"})
    concerns.append({"name": "Presión inflacionaria", "level": inf["level"], "value": f"{inf['index']:.0f}/100"})
    if gpr_val is not None:
        gpr_level = "green" if gpr_val < 100 else ("yellow" if gpr_val < 150 else ("orange" if gpr_val < 200 else "red"))
        concerns.append({"name": "GPR Global", "level": gpr_level, "value": f"{gpr_val:.0f}"})

    counts = {"green": 0, "yellow_green": 0, "yellow": 0, "orange": 0, "red": 0}
    for c in concerns:
        lv = c["level"]
        if lv in counts:
            counts[lv] += 1

    n_alert = counts["orange"] + counts["red"]
    n_total = len(concerns)

    top3 = sorted(concerns, key=lambda x: _level_order.get(x["level"], 0), reverse=True)[:3]

    today_str = date.today().strftime("%d de %B de %Y")

    parts = [f"A {today_str}, {n_alert} de {n_total} indicadores principales muestran señal de alerta o crítica."]

    if top3:
        top_names = ", ".join(f"{c['name']} ({c['value']})" for c in top3 if _level_order.get(c["level"], 0) >= 2)
        if top_names:
            parts.append(f"Los más preocupantes son: {top_names}.")

    if rec["probability"] >= 50:
        parts.append(f"La probabilidad de recesión estimada es del {rec['probability']:.0f}%: {rec['interpretation']}")
    else:
        parts.append(f"El riesgo de recesión es del {rec['probability']:.0f}%, nivel {rec['level']}.")

    sahm_val, sahm_lvl, _ = calculate_sahm_indicator()
    if sahm_val is not None:
        if sahm_val >= 0.5:
            parts.append(f"La Regla de Sahm ({sahm_val:.2f}) está en zona de recesión activa.")
        else:
            parts.append(f"La Regla de Sahm ({sahm_val:.2f}) no señala recesión en curso.")

    t5yie, _ = get_latest_value("fred_inflation_exp_5y_us")
    if t5yie is not None:
        if t5yie > 3:
            parts.append(f"Las expectativas de inflación a 5 años ({t5yie:.2f}%) están desancladas por encima del 3%.")
        else:
            parts.append(f"Las expectativas de inflación a 5 años ({t5yie:.2f}%) permanecen relativamente ancladas.")

    text = " ".join(parts)

    return {
        "text": text,
        "counts": counts,
        "top3_concerns": top3,
        "recession_prob": rec["probability"],
        "systemic_risk": fin_idx,
        "inflation_pressure": inf["index"],
    }


def get_indicator_history_for_dashboard(weeks: int = 52) -> pd.DataFrame:
    """
    Para cada semana de los últimos N semanas, calcula el estado de los indicadores
    clave del cuadro de mando y devuelve la composición semanal.

    Retorna DataFrame: semana, n_normal, n_attention, n_alert, n_critical
    """
    try:
        now = datetime.utcnow()
        records = []

        for w in range(weeks, -1, -1):
            week_end = now - timedelta(weeks=w)
            week_start = week_end - timedelta(days=7)
            n_normal = 0
            n_attention = 0
            n_alert = 0
            n_critical = 0

            def _get_val_at(series_id: str, dt: datetime) -> Optional[float]:
                try:
                    with SessionLocal() as db:
                        row = (
                            db.query(TimeSeries)
                            .filter(
                                TimeSeries.indicator_id == series_id,
                                TimeSeries.timestamp <= dt,
                            )
                            .order_by(TimeSeries.timestamp.desc())
                            .first()
                        )
                    return float(row.value) if row and row.value is not None else None
                except Exception:
                    return None

            # T10Y2Y
            t10y2y = _get_val_at("fred_t10y2y_us", week_end)
            if t10y2y is not None:
                if t10y2y < -0.5:   n_critical += 1
                elif t10y2y < 0:    n_alert += 1
                elif t10y2y < 0.5:  n_attention += 1
                else:               n_normal += 1

            # VIX
            vix = _get_val_at("yf_vix_close", week_end)
            if vix is not None:
                if vix > 35:    n_critical += 1
                elif vix > 25:  n_alert += 1
                elif vix > 18:  n_attention += 1
                else:           n_normal += 1

            # STLFSI4
            stlfsi = _get_val_at("fred_financial_stress_us", week_end)
            if stlfsi is not None:
                if stlfsi > 2:    n_critical += 1
                elif stlfsi > 1:  n_alert += 1
                elif stlfsi > 0:  n_attention += 1
                else:             n_normal += 1

            # T5YIE
            t5yie = _get_val_at("fred_inflation_exp_5y_us", week_end)
            if t5yie is not None:
                if t5yie > 3:     n_critical += 1
                elif t5yie > 2.5: n_alert += 1
                elif t5yie > 2.3: n_attention += 1
                else:             n_normal += 1

            records.append({
                "semana": week_end,
                "n_normal": n_normal,
                "n_attention": n_attention,
                "n_alert": n_alert,
                "n_critical": n_critical,
            })

        return pd.DataFrame(records)
    except Exception as exc:
        logger.debug("get_indicator_history_for_dashboard: %s", exc)
        return pd.DataFrame(columns=["semana", "n_normal", "n_attention", "n_alert", "n_critical"])


# ── Índice Li Keqiang (proxy) ──────────────────────────────────────────────────

def calculate_li_keqiang_proxy(country_iso3: str = "CHN") -> Optional[pd.Series]:
    """
    Proxy del índice Li Keqiang para China.

    Combina:
      - Consumo energético per cápita (EG.USE.PCAP.KG.OE) → variación YoY → peso 40%
      - Comercio como % del PIB (NE.TRD.GNFS.ZS) → variación YoY → peso 30%
      - ETF MCHI como proxy del crédito bancario → variación YoY → peso 30%

    Devuelve una pd.Series con índice DatetimeIndex y valores en % (comparable al PIB YoY).
    Devuelve None si hay menos de 2 componentes disponibles.
    """
    iso = country_iso3.upper()
    components: list[tuple[pd.Series, float, str]] = []

    # Componente 1: consumo energético
    try:
        energy_id = f"wb_energy_use_per_capita_{iso.lower()}"
        energy_df = get_series(energy_id, days=12000)
        if energy_df is not None and not energy_df.empty:
            s = energy_df.set_index("timestamp")["value"].dropna()
            s_annual = s.resample("A").mean().dropna()
            yoy = s_annual.pct_change(1) * 100
            yoy = yoy.dropna()
            if len(yoy) >= 3:
                components.append((yoy, 0.40, "energia"))
    except Exception as exc:
        logger.debug("LK proxy — energía: %s", exc)

    # Componente 2: comercio como % PIB
    try:
        trade_id = f"wb_trade_pct_gdp_{iso.lower()}"
        trade_df = get_series(trade_id, days=12000)
        if trade_df is not None and not trade_df.empty:
            s = trade_df.set_index("timestamp")["value"].dropna()
            s_annual = s.resample("A").mean().dropna()
            yoy = s_annual.pct_change(1) * 100
            yoy = yoy.dropna()
            if len(yoy) >= 3:
                components.append((yoy, 0.30, "comercio"))
    except Exception as exc:
        logger.debug("LK proxy — comercio: %s", exc)

    # Componente 3: ETF MCHI como proxy crédito/bolsa china
    try:
        mchi_df = get_series("yf_mchi_close", days=5000)
        if mchi_df is not None and not mchi_df.empty:
            s = mchi_df.set_index("timestamp")["value"].dropna()
            s_annual = s.resample("A").last().dropna()
            yoy = s_annual.pct_change(1) * 100
            yoy = yoy.dropna()
            if len(yoy) >= 3:
                components.append((yoy, 0.30, "credito"))
    except Exception as exc:
        logger.debug("LK proxy — MCHI: %s", exc)

    if len(components) < 2:
        logger.info(
            "calculate_li_keqiang_proxy: solo %d componentes disponibles (mínimo 2). "
            "Proxy no calculado.", len(components)
        )
        return None

    # Normalizar pesos a 1.0 con los componentes disponibles
    total_weight = sum(w for _, w, _ in components)
    if total_weight == 0:
        return None

    # Alinear todas las series en un índice común
    try:
        all_series = [comp.rename(name) for comp, _, name in components]
        df_all = pd.concat(all_series, axis=1).dropna(how="all")

        result = pd.Series(0.0, index=df_all.index)
        for (comp_series, weight, name) in components:
            reindexed = comp_series.reindex(df_all.index)
            norm_weight = weight / total_weight
            result = result.add(reindexed.fillna(0) * norm_weight)

        # Eliminar filas donde todos los componentes eran NaN
        valid_mask = df_all.notna().any(axis=1)
        result = result[valid_mask].dropna()

        if result.empty:
            return None
        return result
    except Exception as exc:
        logger.debug("calculate_li_keqiang_proxy — combinación: %s", exc)
        return None


# ── Demografía: comparativa entre países ──────────────────────────────────────

def get_demographic_comparison(
    indicator_series_id: str,
    countries: list[str],
    include_projections: bool = False,
    projection_data: Optional[dict] = None,
) -> pd.DataFrame:
    """
    Lee datos demográficos del World Bank para los países especificados.

    - indicator_series_id: ID de la serie en time_series (ej. 'wb_sp_pop_totl_wld')
      Se reemplaza la parte de país dinámicamente por cada código de país.
    - countries: lista de códigos ISO3 (ej. ['JPN', 'DEU', 'ESP'])
    - include_projections: si True y se proporciona projection_data, combina
      los datos históricos con las proyecciones hasta 2050.
    - projection_data: dict con estructura {iso3: {year_str: value}} para proyecciones.

    Devuelve un DataFrame con años en índice y países en columnas.
    Maneja correctamente la ausencia de datos con NaN.
    """
    import json
    from pathlib import Path

    result_frames: dict[str, pd.Series] = {}

    for country in countries:
        # Intentar leer de la BD — el indicator_id se construye reemplazando
        # el último segmento por el código de país en minúsculas
        series_id = indicator_series_id.replace("{country}", country.lower())
        try:
            df = get_series(series_id, days=25 * 365)
            if df is not None and not df.empty:
                df["timestamp"] = pd.to_datetime(df["timestamp"])
                df["year"] = df["timestamp"].dt.year
                # Agregado anual: media del año
                annual = df.groupby("year")["value"].mean()
                result_frames[country] = annual
        except Exception as exc:
            logger.debug("get_demographic_comparison(%s, %s): %s", series_id, country, exc)

    if not result_frames:
        # Devolver DataFrame vacío con columnas
        return pd.DataFrame(columns=countries)

    df_combined = pd.DataFrame(result_frames)
    df_combined.index.name = "year"

    # Combinar con proyecciones si se solicita
    if include_projections and projection_data:
        proj_frames: dict[str, pd.Series] = {}
        for country in countries:
            if country in projection_data:
                proj = projection_data[country]
                proj_series = pd.Series(
                    {int(y): v for y, v in proj.items()},
                    name=country,
                )
                proj_frames[country] = proj_series

        if proj_frames:
            df_proj = pd.DataFrame(proj_frames)
            df_proj.index.name = "year"
            # Solo añadir años futuros que no están ya en el histórico
            max_hist_year = df_combined.index.max() if not df_combined.empty else 0
            df_proj_future = df_proj[df_proj.index > max_hist_year]
            df_combined = pd.concat([df_combined, df_proj_future])

    df_combined = df_combined.sort_index()
    return df_combined


# ── Análisis de sectores ────────────────────────────────────────────────────────

def calculate_sector_performance(period_days: int = 365) -> pd.DataFrame:
    """
    Lee los ETFs sectoriales del S&P 500 desde SQLite y calcula rendimientos.

    ETFs cubiertos: XLK, XLE, XLF, XLV, XLP, XLY, XLB, XLI, XLU, XLRE, XLC
    También lee ^GSPC como benchmark.

    Devuelve DataFrame con columnas:
      ticker, name, current_price, change_1d_pct, change_period_pct,
      change_ytd_pct, vs_sp500_pct, best_sector (bool), worst_sector (bool)
    """
    sector_map = {
        "XLK":  "Tecnología",
        "XLE":  "Energía",
        "XLF":  "Financiero",
        "XLV":  "Salud",
        "XLP":  "Consumo básico",
        "XLY":  "Consumo discrecional",
        "XLB":  "Materiales",
        "XLI":  "Industrial",
        "XLU":  "Utilities",
        "XLRE": "Inmobiliario REITs",
        "XLC":  "Comunicaciones",
    }

    records = []
    sp500_ytd = None

    for ticker, name in sector_map.items():
        series_id = f"yf_{ticker.lower()}_close"
        try:
            df = get_series(series_id, days=max(period_days + 30, 400))
            if df is None or df.empty:
                records.append({
                    "ticker": ticker, "name": name,
                    "current_price": None,
                    "change_1d_pct": None,
                    "change_period_pct": None,
                    "change_ytd_pct": None,
                    "vs_sp500_pct": None,
                })
                continue

            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.sort_values("timestamp")

            current = df["value"].iloc[-1]
            prev_day = df["value"].iloc[-2] if len(df) > 1 else current
            chg_1d = (current - prev_day) / prev_day * 100 if prev_day else None

            # Período seleccionado
            cutoff_period = df["timestamp"].max() - pd.Timedelta(days=period_days)
            df_period = df[df["timestamp"] >= cutoff_period]
            if not df_period.empty:
                start_period = df_period["value"].iloc[0]
                chg_period = (current - start_period) / start_period * 100 if start_period else None
            else:
                chg_period = None

            # YTD
            from datetime import datetime as _dt
            ytd_start = pd.Timestamp(_dt.utcnow().year, 1, 1)
            df_ytd = df[df["timestamp"] >= ytd_start]
            if not df_ytd.empty:
                start_ytd = df_ytd["value"].iloc[0]
                chg_ytd = (current - start_ytd) / start_ytd * 100 if start_ytd else None
            else:
                chg_ytd = None

            records.append({
                "ticker": ticker, "name": name,
                "current_price": round(current, 2),
                "change_1d_pct": round(chg_1d, 2) if chg_1d is not None else None,
                "change_period_pct": round(chg_period, 2) if chg_period is not None else None,
                "change_ytd_pct": round(chg_ytd, 2) if chg_ytd is not None else None,
                "vs_sp500_pct": None,  # se calcula tras leer SP500
            })
        except Exception as exc:
            logger.debug("calculate_sector_performance(%s): %s", ticker, exc)
            records.append({
                "ticker": ticker, "name": name,
                "current_price": None, "change_1d_pct": None,
                "change_period_pct": None, "change_ytd_pct": None,
                "vs_sp500_pct": None,
            })

    # SP500 YTD
    try:
        sp_df = get_series("yf_gspc_close", days=400)
        if sp_df is not None and not sp_df.empty:
            sp_df["timestamp"] = pd.to_datetime(sp_df["timestamp"])
            sp_df = sp_df.sort_values("timestamp")
            from datetime import datetime as _dt
            ytd_start = pd.Timestamp(_dt.utcnow().year, 1, 1)
            sp_ytd = sp_df[sp_df["timestamp"] >= ytd_start]
            if not sp_ytd.empty:
                sp500_ytd = (sp_df["value"].iloc[-1] - sp_ytd["value"].iloc[0]) / sp_ytd["value"].iloc[0] * 100
    except Exception:
        pass

    result = pd.DataFrame(records)
    if sp500_ytd is not None and "change_ytd_pct" in result.columns:
        result["vs_sp500_pct"] = result["change_ytd_pct"].apply(
            lambda x: round(x - sp500_ytd, 2) if x is not None else None
        )

    # Marcar mejor y peor sector por YTD
    if not result.empty and result["change_ytd_pct"].notna().any():
        max_idx = result["change_ytd_pct"].idxmax()
        min_idx = result["change_ytd_pct"].idxmin()
        result["best_sector"] = False
        result["worst_sector"] = False
        result.loc[max_idx, "best_sector"] = True
        result.loc[min_idx, "worst_sector"] = True

    return result


def calculate_bond_duration_impact(
    current_yield: float,
    yield_change_pp: float,
    duration_years: float,
) -> float:
    """
    Calcula el impacto aproximado en el precio de un bono ante una variación de tipos.

    Fórmula simplificada (duración modificada):
      impacto_precio ≈ -duration_mod × yield_change_pp
      donde duration_mod = duration / (1 + current_yield/100)

    Parámetros:
      current_yield: rendimiento actual del bono en % (ej. 4.3)
      yield_change_pp: variación de tipos en puntos porcentuales (ej. +1.0 = sube 1pp)
      duration_years: duración del bono en años (ej. 10 para bono a 10Y)

    Devuelve el cambio porcentual estimado en el precio del bono (negativo si tipos suben).
    """
    try:
        duration_mod = duration_years / (1 + current_yield / 100)
        price_change_pct = -duration_mod * yield_change_pp
        return round(price_change_pct, 2)
    except Exception:
        return 0.0
