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
