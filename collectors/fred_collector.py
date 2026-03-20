"""
Colector de datos de FRED (Federal Reserve Economic Data).

Alimenta los módulos: M02 (Macro), M03 (Inflación), M04 (Política Monetaria),
M05 (Mercados - curva de tipos), M06 (Mercado Laboral), M08 (Deuda),
M09 (Riesgo Sistémico), M11 (Indicadores Adelantados), M16 (Submercados).

Descarga ~55 series históricas desde 2000 y las guarda en SQLite.
Calcula automáticamente series derivadas: YoY inflación, MoM CPI,
tipo de interés real y spread 10y-2y calculado.
"""

import logging
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
from fredapi import Fred
from sqlalchemy import func, insert

# Permite importar desde la raíz del proyecto cuando se ejecuta directamente
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collectors.base_collector import BaseCollector
from config import FRED_API_KEY
from database.database import SessionLocal, TimeSeries

logger = logging.getLogger(__name__)

# Fecha de inicio del histórico
HISTORY_START = "2000-01-01"


# ── Catálogo de series ────────────────────────────────────────────────────────

@dataclass
class SeriesConfig:
    """Metadatos de una serie FRED."""
    indicator_id: str   # ID canónico en BD, ej: 'fred_cpi_us'
    name: str           # Nombre legible en español
    unit: str           # 'pct', 'index', 'usd', 'usd_mn', 'usd_bn', 'thousands', etc.
    frequency: str      # 'daily', 'weekly', 'monthly', 'quarterly', 'annual'
    module: str         # Módulo principal que consume esta serie
    region: str         # Código de región, siempre 'US' para FRED


SERIES_CATALOG: dict[str, SeriesConfig] = {

    # ── Grupo 1: PIB y Actividad Económica (M02) ──────────────────────────────
    "GDPC1":            SeriesConfig("fred_gdpc1_us",            "PIB Real EE.UU.",                        "usd_bn",    "quarterly", "M02", "US"),
    "A191RL1Q225SBEA":  SeriesConfig("fred_gdp_growth_us",       "Crecimiento PIB Real (anualizado)",      "pct",       "quarterly", "M02", "US"),
    "INDPRO":           SeriesConfig("fred_indpro_us",           "Producción Industrial",                  "index",     "monthly",   "M02", "US"),
    "RSAFS":            SeriesConfig("fred_retail_sales_us",     "Ventas al por Menor",                    "usd_mn",    "monthly",   "M02", "US"),
    "UMCSENT":          SeriesConfig("fred_consumer_conf_us",    "Confianza Consumidor (Michigan)",        "index",     "monthly",   "M02", "US"),
    "BOPGSTB":          SeriesConfig("fred_trade_balance_us",    "Balanza Comercial Bienes y Servicios",   "usd_mn",    "monthly",   "M02", "US"),
    "NETFI":            SeriesConfig("fred_current_account_us",  "Balanza Cuenta Corriente",               "usd_bn",    "quarterly", "M02", "US"),
    "GFDEGDQ188S":      SeriesConfig("fred_debt_gdp_us",         "Deuda Federal % PIB",                    "pct",       "quarterly", "M02", "US"),
    "FYFSGDA188S":      SeriesConfig("fred_deficit_gdp_us",      "Déficit Fiscal Federal % PIB",           "pct",       "annual",    "M02", "US"),

    # ── Grupo 2: Inflación (M03) ──────────────────────────────────────────────
    "CPIAUCSL":         SeriesConfig("fred_cpi_us",              "IPC General EE.UU.",                     "index",     "monthly",   "M03", "US"),
    "CPILFESL":         SeriesConfig("fred_core_cpi_us",         "IPC Subyacente (Core)",                  "index",     "monthly",   "M03", "US"),
    "CPIUFDSL":         SeriesConfig("fred_cpi_food_us",         "IPC Alimentos",                          "index",     "monthly",   "M03", "US"),
    "CPIENGSL":         SeriesConfig("fred_cpi_energy_us",       "IPC Energía",                            "index",     "monthly",   "M03", "US"),
    "CUSR0000SASLE":    SeriesConfig("fred_cpi_services_us",     "IPC Servicios",                          "index",     "monthly",   "M03", "US"),
    "CUSR0000SAH1":     SeriesConfig("fred_cpi_housing_us",      "IPC Vivienda y Alquiler",                "index",     "monthly",   "M03", "US"),
    "PPIACO":           SeriesConfig("fred_ppi_all_us",          "IPP Materias Primas",                    "index",     "monthly",   "M03", "US"),
    "PPIFIS":           SeriesConfig("fred_ppi_finished_us",     "IPP Bienes Finales",                     "index",     "monthly",   "M03", "US"),
    "MICH":             SeriesConfig("fred_infl_exp_1y_us",      "Expectativas Inflación 1a (Michigan)",   "pct",       "monthly",   "M03", "US"),
    "T5YIE":            SeriesConfig("fred_breakeven_5y_us",     "Breakeven Inflación 5 años",             "pct",       "daily",     "M03", "US"),
    "T10YIE":           SeriesConfig("fred_breakeven_10y_us",    "Breakeven Inflación 10 años",            "pct",       "daily",     "M03", "US"),
    "DFII10":           SeriesConfig("fred_real_yield_10y_us",   "Tipo Real 10 años (TIPS)",               "pct",       "daily",     "M03", "US"),

    # ── Grupo 3: Política Monetaria y Fed (M04) ───────────────────────────────
    "DFF":              SeriesConfig("fred_fed_funds_daily_us",  "Federal Funds Rate (diario)",            "pct",       "daily",     "M04", "US"),
    "FEDFUNDS":         SeriesConfig("fred_fed_funds_us",        "Federal Funds Rate (mensual)",           "pct",       "monthly",   "M04", "US"),
    "WALCL":            SeriesConfig("fred_fed_balance_us",      "Balance Reserva Federal",                "usd_mn",    "weekly",    "M04", "US"),
    "WRESBAL":          SeriesConfig("fred_bank_reserves_us",    "Reservas Bancarias en Fed",              "usd_mn",    "weekly",    "M04", "US"),

    # ── Grupo 4: Curva de Tipos (M05 y M11) ──────────────────────────────────
    "DTB3":             SeriesConfig("fred_yield_3m_us",         "Bono Tesoro 3 meses",                    "pct",       "daily",     "M05", "US"),
    "DTB6":             SeriesConfig("fred_yield_6m_us",         "Bono Tesoro 6 meses",                    "pct",       "daily",     "M05", "US"),
    "DGS1":             SeriesConfig("fred_yield_1y_us",         "Bono Tesoro 1 año",                      "pct",       "daily",     "M05", "US"),
    "DGS2":             SeriesConfig("fred_yield_2y_us",         "Bono Tesoro 2 años",                     "pct",       "daily",     "M05", "US"),
    "DGS3":             SeriesConfig("fred_yield_3y_us",         "Bono Tesoro 3 años",                     "pct",       "daily",     "M05", "US"),
    "DGS5":             SeriesConfig("fred_yield_5y_us",         "Bono Tesoro 5 años",                     "pct",       "daily",     "M05", "US"),
    "DGS7":             SeriesConfig("fred_yield_7y_us",         "Bono Tesoro 7 años",                     "pct",       "daily",     "M05", "US"),
    "DGS10":            SeriesConfig("fred_yield_10y_us",        "Bono Tesoro 10 años",                    "pct",       "daily",     "M05", "US"),
    "DGS20":            SeriesConfig("fred_yield_20y_us",        "Bono Tesoro 20 años",                    "pct",       "daily",     "M05", "US"),
    "DGS30":            SeriesConfig("fred_yield_30y_us",        "Bono Tesoro 30 años",                    "pct",       "daily",     "M05", "US"),
    "T10Y2Y":           SeriesConfig("fred_spread_10y2y_us",     "Spread 10y-2y",                          "pct",       "daily",     "M11", "US"),
    "T10Y3M":           SeriesConfig("fred_spread_10y3m_us",     "Spread 10y-3m",                          "pct",       "daily",     "M11", "US"),

    # ── Grupo 5: Mercado Laboral EE.UU. (M06) ────────────────────────────────
    "UNRATE":           SeriesConfig("fred_unemployment_us",     "Tasa de Desempleo",                      "pct",       "monthly",   "M06", "US"),
    "LNS14000012":      SeriesConfig("fred_youth_unemp_us",      "Desempleo Juvenil (16-24)",              "pct",       "monthly",   "M06", "US"),
    "UEMPLT5":          SeriesConfig("fred_short_unemp_us",      "Desempleo Corta Duración",               "thousands", "monthly",   "M06", "US"),
    "UEMP27OV":         SeriesConfig("fred_long_unemp_us",       "Desempleo Larga Duración (≥27 sem)",     "thousands", "monthly",   "M06", "US"),
    "CIVPART":          SeriesConfig("fred_labor_partic_us",     "Participación Fuerza Laboral",           "pct",       "monthly",   "M06", "US"),
    "PAYEMS":           SeriesConfig("fred_nfp_us",              "Non-Farm Payrolls",                      "thousands", "monthly",   "M06", "US"),
    "JTSJOL":           SeriesConfig("fred_jolts_us",            "Ofertas de Empleo (JOLTS)",              "thousands", "monthly",   "M06", "US"),
    "JTSQUR":           SeriesConfig("fred_quit_rate_us",        "Quit Rate",                              "pct",       "monthly",   "M06", "US"),
    "ICSA":             SeriesConfig("fred_initial_claims_us",   "Solicitudes Iniciales Desempleo",        "count",     "weekly",    "M06", "US"),
    "CCSA":             SeriesConfig("fred_cont_claims_us",      "Solicitudes Continuas Desempleo",        "count",     "weekly",    "M06", "US"),
    "ECIALLCIV":        SeriesConfig("fred_eci_us",              "Índice Coste Empleo (ECI)",              "index",     "quarterly", "M06", "US"),
    "CES0500000003":    SeriesConfig("fred_avg_wages_us",        "Salario Medio por Hora (privado)",       "usd",       "monthly",   "M06", "US"),
    "AWHAETP":          SeriesConfig("fred_avg_hours_us",        "Horas Semanales Medias",                 "hours",     "monthly",   "M06", "US"),
    "OPHNFB":           SeriesConfig("fred_productivity_us",     "Productividad Laboral",                  "index",     "quarterly", "M06", "US"),

    # ── Grupo 6: Deuda y Fiscalidad EE.UU. (M08) ─────────────────────────────
    "GFDEBTN":          SeriesConfig("fred_federal_debt_us",     "Deuda Federal Total",                    "usd_mn",    "quarterly", "M08", "US"),
    "A091RC1Q027SBEA":  SeriesConfig("fred_interest_pay_us",    "Intereses Netos Gobierno Federal",       "usd_bn",    "quarterly", "M08", "US"),
    "W006RC1Q027SBEA":  SeriesConfig("fred_tax_revenues_us",    "Ingresos Fiscales Federales",            "usd_bn",    "quarterly", "M08", "US"),
    "W019RCQ027SBEA":   SeriesConfig("fred_fed_spending_us",    "Gasto Federal Total",                    "usd_bn",    "quarterly", "M08", "US"),

    # ── Grupo 7: Estrés Financiero e Indicadores Adelantados (M09 y M11) ─────
    "STLFSI4":          SeriesConfig("fred_stlfsi_us",           "Índice Estrés Financiero (STLFSI)",      "index",     "weekly",    "M09", "US"),
    "USSLIND":          SeriesConfig("fred_lei_us",              "Leading Economic Index (LEI)",           "index",     "monthly",   "M11", "US"),
    "PERMIT":           SeriesConfig("fred_building_permit_us",  "Permisos de Construcción",               "thousands", "monthly",   "M11", "US"),
    "DGORDER":          SeriesConfig("fred_durable_goods_us",    "Pedidos Bienes Duraderos",               "usd_mn",    "monthly",   "M11", "US"),
    "ISRATIO":          SeriesConfig("fred_inventory_ratio_us",  "Ratio Inventarios/Ventas Manuf.",        "ratio",     "monthly",   "M11", "US"),
    "TOTALSL":          SeriesConfig("fred_consumer_credit_us",  "Crédito al Consumo Total",               "usd_mn",    "monthly",   "M11", "US"),
    "BUSLOANS":         SeriesConfig("fred_biz_loans_us",        "Préstamos Comerciales e Industriales",   "usd_mn",    "monthly",   "M11", "US"),

    # ── Grupo 8: Mercado Inmobiliario (M16) ───────────────────────────────────
    "CSUSHPINSA":       SeriesConfig("fred_case_shiller_nat_us", "Case-Shiller Nacional",                  "index",     "monthly",   "M16", "US"),
    "CSUSHPISA":        SeriesConfig("fred_case_shiller_20c_us", "Case-Shiller 20 Ciudades",               "index",     "monthly",   "M16", "US"),
    "HOUST":            SeriesConfig("fred_housing_starts_us",   "Inicio Construcción Viviendas",          "thousands", "monthly",   "M16", "US"),
    "MORTGAGE30US":     SeriesConfig("fred_mortgage_30y_us",     "Tipo Hipotecario 30 años",               "pct",       "weekly",    "M16", "US"),
    "MORTGAGE15US":     SeriesConfig("fred_mortgage_15y_us",     "Tipo Hipotecario 15 años",               "pct",       "weekly",    "M16", "US"),
}

# Series de inflación que necesitan cálculo YoY automático
_INFLATION_YOY_MAP: dict[str, tuple[str, str]] = {
    # fred_id: (derived_indicator_id, nombre_derivado)
    "CPIAUCSL":      ("fred_cpi_yoy_us",              "IPC General YoY"),
    "CPILFESL":      ("fred_core_cpi_yoy_us",         "IPC Subyacente YoY"),
    "CPIUFDSL":      ("fred_cpi_food_yoy_us",         "IPC Alimentos YoY"),
    "CPIENGSL":      ("fred_cpi_energy_yoy_us",       "IPC Energía YoY"),
    "CUSR0000SASLE": ("fred_cpi_services_yoy_us",     "IPC Servicios YoY"),
    "CUSR0000SAH1":  ("fred_cpi_housing_yoy_us",      "IPC Vivienda YoY"),
    "PPIACO":        ("fred_ppi_all_yoy_us",          "IPP Materias Primas YoY"),
    "PPIFIS":        ("fred_ppi_finished_yoy_us",     "IPP Bienes Finales YoY"),
}


# ── Colector ──────────────────────────────────────────────────────────────────

class FREDCollector(BaseCollector):
    """
    Colector de datos de la Federal Reserve Economic Data (FRED).

    Uso típico:
        collector = FREDCollector()
        collector.run_full_history()   # Primera vez (~5 min)
        collector.run_update()         # Ejecuciones diarias automáticas
    """

    SOURCE = "fred"

    def __init__(self) -> None:
        if not FRED_API_KEY:
            raise ValueError(
                "FRED_API_KEY no está configurada. "
                "Edita el fichero .env y añade tu API key de fred.stlouisfed.org"
            )
        self.fred = Fred(api_key=FRED_API_KEY)
        self._errors: list[str] = []
        logger.info("FREDCollector inicializado. %d series en catálogo.", len(SERIES_CATALOG))

    # ── Interfaz pública (BaseCollector) ──────────────────────────────────────

    def run_full_history(self) -> dict:
        """Descarga el histórico completo desde 2000. Solo para primera ejecución."""
        logger.info("=" * 64)
        logger.info("FRED ▶ Inicio descarga histórico completo (desde %s)", HISTORY_START)
        logger.info("       %d series en catálogo", len(SERIES_CATALOG))
        logger.info("=" * 64)
        t0 = time.time()
        self._errors = []

        result = self._download_all_series(observation_start=HISTORY_START)
        self._compute_derived_series()

        elapsed = time.time() - t0
        logger.info("=" * 64)
        logger.info(
            "FRED ✓ Histórico completo en %.1fs | OK: %d | Fail: %d | Registros: %d",
            elapsed, result["ok"], result["failed"], result["total_records"],
        )
        if self._errors:
            logger.warning("FRED ✗ Series con error: %s", self._errors)
        logger.info("=" * 64)
        return result

    def run_update(self) -> dict:
        """Descarga solo datos nuevos desde la última actualización."""
        last = self.get_last_update_time()
        if last is None:
            logger.info("FRED: Sin historial previo. Ejecutando descarga completa.")
            return self.run_full_history()

        # Buffer de 30 días para capturar datos publicados con retraso y revisiones
        obs_start = (last - timedelta(days=30)).strftime("%Y-%m-%d")
        logger.info("FRED ▶ Actualización desde %s (último: %s)", obs_start, last.date())
        t0 = time.time()
        self._errors = []

        result = self._download_all_series(observation_start=obs_start)
        self._compute_derived_series()

        elapsed = time.time() - t0
        logger.info(
            "FRED ✓ Actualización en %.1fs | Nuevos registros: %d",
            elapsed, result["total_records"],
        )
        return result

    def download_series(
        self,
        series_ids: list[str],
        observation_start: str = HISTORY_START,
    ) -> dict:
        """
        Descarga y guarda un subconjunto específico de series FRED.
        Útil para pruebas y para añadir series individuales en producción.

        Args:
            series_ids: Lista de IDs de FRED (ej: ['CPIAUCSL', 'DFF'])
            observation_start: Fecha de inicio en formato 'YYYY-MM-DD'

        Returns:
            dict con ok, failed, total_records, errors
        """
        logger.info(
            "FRED ▶ Descargando %d series desde %s: %s",
            len(series_ids), observation_start, series_ids,
        )
        self._errors = []
        ok = failed = total_records = 0

        for series_id in series_ids:
            cfg = SERIES_CATALOG.get(series_id)
            if cfg is None:
                logger.warning("  SKIP %s — no está en el catálogo", series_id)
                failed += 1
                continue

            try:
                data = self._fetch_with_retry(series_id, observation_start=observation_start)
                n = self._save_series(
                    series_id=series_id,
                    data=data,
                    module=cfg.module,
                    indicator_name=cfg.name,
                    country=cfg.region,
                    unit=cfg.unit,
                    indicator_id=cfg.indicator_id,
                )
                logger.info("  ✓ %-20s %s — %d nuevos registros", series_id, cfg.name[:35], n)
                ok += 1
                total_records += n
            except Exception as exc:
                msg = f"{series_id}: {exc}"
                logger.error("  ✗ %s", msg)
                self._errors.append(msg)
                failed += 1

        return {"ok": ok, "failed": failed, "total_records": total_records, "errors": self._errors}

    def get_last_update_time(self) -> Optional[datetime]:
        """Retorna el datetime UTC de la última inserción de datos FRED."""
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

    # ── Métodos privados ──────────────────────────────────────────────────────

    def _download_all_series(self, observation_start: str) -> dict:
        """Descarga todas las series del catálogo y las persiste en SQLite."""
        ok = failed = total_records = 0
        total = len(SERIES_CATALOG)

        for i, (series_id, cfg) in enumerate(SERIES_CATALOG.items(), 1):
            logger.info("[%02d/%d] %s — %s", i, total, series_id, cfg.name)
            try:
                data = self._fetch_with_retry(series_id, observation_start=observation_start)
                n = self._save_series(
                    series_id=series_id,
                    data=data,
                    module=cfg.module,
                    indicator_name=cfg.name,
                    country=cfg.region,
                    unit=cfg.unit,
                    indicator_id=cfg.indicator_id,
                )
                logger.info("         → %d nuevos registros", n)
                ok += 1
                total_records += n
            except Exception as exc:
                msg = f"{series_id} ({cfg.name}): {exc}"
                logger.error("         ✗ %s", msg)
                self._errors.append(msg)
                failed += 1

        return {"ok": ok, "failed": failed, "total_records": total_records, "errors": self._errors}

    def _fetch_with_retry(
        self,
        series_id: str,
        max_retries: int = 3,
        **kwargs,
    ) -> pd.Series:
        """
        Descarga una serie de FRED con reintentos automáticos (backoff exponencial).
        Aplica un delay de 0.1s entre peticiones para respetar el rate limit.

        Raises:
            RuntimeError: Si falla todos los reintentos.
        """
        last_exc: Exception = RuntimeError("Sin intentos realizados")
        for attempt in range(max_retries):
            try:
                data = self.fred.get_series(series_id, **kwargs)
                time.sleep(0.1)  # Rate limiting: máx ~10 req/s con la API gratuita
                return data
            except Exception as exc:
                last_exc = exc
                if attempt < max_retries - 1:
                    wait = 2 ** attempt  # 1s → 2s → 4s
                    logger.warning(
                        "         Reintento %d/%d para %s (espera %.0fs): %s",
                        attempt + 1, max_retries - 1, series_id, wait, exc,
                    )
                    time.sleep(wait)
        raise RuntimeError(f"Fallo tras {max_retries} intentos en {series_id}: {last_exc}")

    def _save_series(
        self,
        series_id: str,
        data: pd.Series,
        module: str,
        indicator_name: str,
        country: str,
        unit: str,
        indicator_id: Optional[str] = None,
    ) -> int:
        """
        Guarda una serie en SQLite sin duplicar registros existentes.

        Estrategia anti-duplicados: consulta el MAX(timestamp) existente para
        este indicator_id y solo inserta registros más recientes. Esto es eficiente
        (una sola query) y correcto para series temporales append-only.

        Args:
            series_id: ID de FRED (ej: 'CPIAUCSL') — solo para log
            data: pandas Series con DatetimeIndex y valores float
            module: Módulo que consume la serie (ej: 'M03')
            indicator_name: Nombre legible para logs
            country: Código de región (ej: 'US')
            unit: Unidad de medida
            indicator_id: ID canónico en BD. Si None, se deriva como
                          'fred_{series_id.lower()}_{country.lower()}'

        Returns:
            Número de registros nuevos insertados.
        """
        if indicator_id is None:
            indicator_id = f"fred_{series_id.lower()}_{country.lower()}"

        # Eliminar NaN — FRED devuelve NaN para fechas sin dato
        data = data.dropna()
        if data.empty:
            return 0

        # Obtener el último timestamp ya en BD para este indicador
        with SessionLocal() as session:
            max_ts = session.query(func.max(TimeSeries.timestamp)).filter(
                TimeSeries.indicator_id == indicator_id
            ).scalar()

        # Filtrar solo registros más recientes que el último almacenado
        if max_ts is not None:
            data = data[data.index > pd.Timestamp(max_ts)]

        if data.empty:
            return 0

        now = datetime.utcnow()
        records = [
            {
                "indicator_id": indicator_id,
                "source": self.SOURCE,
                "region": country,
                "timestamp": pd.Timestamp(ts).to_pydatetime().replace(tzinfo=None),
                "value": float(val),
                "unit": unit,
                "created_at": now,
            }
            for ts, val in data.items()
        ]

        with SessionLocal() as session:
            session.execute(insert(TimeSeries), records)
            session.commit()

        return len(records)

    def _compute_derived_series(self) -> None:
        """
        Calcula y guarda automáticamente las series derivadas:

        1. YoY (%) de todas las series de inflación mensual
        2. MoM (%) del IPC general
        3. Tipo de interés real = FEDFUNDS mensual – CPI YoY
        4. Spread 10y-2y calculado = DGS10 – DGS2 (verificación del oficial T10Y2Y)
        """
        logger.info("FRED ▶ Calculando series derivadas...")

        # 1 & 2 — YoY y MoM de series de inflación
        for fred_id, (derived_id, derived_name) in _INFLATION_YOY_MAP.items():
            cfg = SERIES_CATALOG.get(fred_id)
            if cfg is None:
                continue
            raw = self._load_indicator_from_db(cfg.indicator_id)
            if raw.empty:
                continue

            # YoY: variación respecto al mismo mes del año anterior
            yoy = (raw.pct_change(periods=12) * 100).dropna()
            if not yoy.empty:
                n = self._save_series(
                    series_id=fred_id,
                    data=yoy,
                    module=cfg.module,
                    indicator_name=derived_name,
                    country="US",
                    unit="pct",
                    indicator_id=derived_id,
                )
                logger.info("  ✓ YoY %-35s %d registros", derived_id, n)

        # MoM solo para el IPC general
        cpi_raw = self._load_indicator_from_db("fred_cpi_us")
        if not cpi_raw.empty:
            cpi_mom = (cpi_raw.pct_change(periods=1) * 100).dropna()
            n = self._save_series(
                series_id="CPIAUCSL",
                data=cpi_mom,
                module="M03",
                indicator_name="IPC General MoM",
                country="US",
                unit="pct",
                indicator_id="fred_cpi_mom_us",
            )
            logger.info("  ✓ MoM  fred_cpi_mom_us                      %d registros", n)

        # 3 — Tipo de interés real = FEDFUNDS mensual – CPI YoY
        fed_funds = self._load_indicator_from_db("fred_fed_funds_us")
        cpi_yoy = self._load_indicator_from_db("fred_cpi_yoy_us")
        if not fed_funds.empty and not cpi_yoy.empty:
            aligned = pd.concat([fed_funds, cpi_yoy], axis=1).dropna()
            aligned.columns = ["ff", "cpi_yoy"]
            real_rate = aligned["ff"] - aligned["cpi_yoy"]
            n = self._save_series(
                series_id="FEDFUNDS",
                data=real_rate,
                module="M03",
                indicator_name="Tipo Interés Real (Fed Funds – CPI YoY)",
                country="US",
                unit="pct",
                indicator_id="fred_real_rate_us",
            )
            logger.info("  ✓ Derivada fred_real_rate_us                 %d registros", n)

        # 4 — Spread 10y-2y calculado (doble verificación del T10Y2Y oficial)
        dgs10 = self._load_indicator_from_db("fred_yield_10y_us")
        dgs2 = self._load_indicator_from_db("fred_yield_2y_us")
        if not dgs10.empty and not dgs2.empty:
            aligned = pd.concat([dgs10, dgs2], axis=1).dropna()
            aligned.columns = ["10y", "2y"]
            spread_calc = aligned["10y"] - aligned["2y"]
            n = self._save_series(
                series_id="DGS10",
                data=spread_calc,
                module="M11",
                indicator_name="Spread 10y-2y (calculado DGS10-DGS2)",
                country="US",
                unit="pct",
                indicator_id="fred_spread_10y2y_calc_us",
            )
            logger.info("  ✓ Derivada fred_spread_10y2y_calc_us         %d registros", n)

        logger.info("FRED ✓ Series derivadas completadas.")

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
