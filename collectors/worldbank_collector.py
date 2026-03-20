"""
Colector de datos del Banco Mundial (World Bank / WDI).

No requiere API key. Alimenta los modulos: M02 (Macro Global), M03 (Inflacion),
M06 (Mercado Laboral), M08 (Deuda), M12 (China), M13 (Demografia).

Descarga 43 indicadores para 45 paises/regiones desde 1990.
Datos anuales — 1-2 anos de retraso es normal en el Banco Mundial.
Las revisiones retroactivas son frecuentes: run_update() rehace los ultimos
3 anos usando DELETE+INSERT para capturarlas.
"""

import logging
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import wbdata
from sqlalchemy import func, insert, text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collectors.base_collector import BaseCollector
from database.database import SessionLocal, TimeSeries

logger = logging.getLogger(__name__)

HISTORY_START       = 1990   # Primer ano del historico
UPDATE_WINDOW_YEARS = 3      # Anos a rehacer en run_update (por revisiones WB)
RATE_LIMIT_DELAY    = 1.0    # Segundos entre llamadas a la API

# ── Paises y regiones objetivo ────────────────────────────────────────────────

COUNTRIES_ISO3: list[str] = [
    # Economias principales
    "USA", "DEU", "FRA", "ESP", "ITA", "GBR", "JPN", "CHN", "IND", "BRA",
    "MEX", "RUS", "CAN", "AUS", "KOR", "NLD", "CHE", "SWE", "NOR", "DNK",
    "POL", "TUR", "SAU", "ZAF", "ARG", "COL", "CHL", "PER", "IDN", "THA",
    "VNM", "MYS", "SGP", "NGA", "EGY", "PAK", "BGD",
    # Agregados regionales del Banco Mundial
    "WLD", "EUU", "EMU", "EAP", "LAC", "SSA", "SAS", "MNA",
]

# Mapeo: nombre WB (nivel 0 del MultiIndex) -> codigo ISO3
# Validado contra la API real (2026-03)
_WB_NAME_TO_ISO3: dict[str, str] = {
    "United States":                                                      "USA",
    "Germany":                                                            "DEU",
    "France":                                                             "FRA",
    "Spain":                                                              "ESP",
    "Italy":                                                              "ITA",
    "United Kingdom":                                                     "GBR",
    "Japan":                                                              "JPN",
    "China":                                                              "CHN",
    "India":                                                              "IND",
    "Brazil":                                                             "BRA",
    "Mexico":                                                             "MEX",
    "Russian Federation":                                                 "RUS",
    "Canada":                                                             "CAN",
    "Australia":                                                          "AUS",
    "Korea, Rep.":                                                        "KOR",
    "Netherlands":                                                        "NLD",
    "Switzerland":                                                        "CHE",
    "Sweden":                                                             "SWE",
    "Norway":                                                             "NOR",
    "Denmark":                                                            "DNK",
    "Poland":                                                             "POL",
    "Turkiye":                                                            "TUR",
    "Turkey":                                                             "TUR",  # Nombre anterior
    "Saudi Arabia":                                                       "SAU",
    "South Africa":                                                       "ZAF",
    "Argentina":                                                          "ARG",
    "Colombia":                                                           "COL",
    "Chile":                                                              "CHL",
    "Peru":                                                               "PER",
    "Indonesia":                                                          "IDN",
    "Thailand":                                                           "THA",
    "Viet Nam":                                                           "VNM",
    "Malaysia":                                                           "MYS",
    "Singapore":                                                          "SGP",
    "Nigeria":                                                            "NGA",
    "Egypt, Arab Rep.":                                                   "EGY",
    "Pakistan":                                                           "PAK",
    "Bangladesh":                                                         "BGD",
    # Agregados regionales
    "World":                                                              "WLD",
    "European Union":                                                     "EUU",
    "Euro area":                                                          "EMU",
    "East Asia & Pacific (excluding high income)":                        "EAP",
    "Latin America & Caribbean (excluding high income)":                  "LAC",
    "Sub-Saharan Africa (excluding high income)":                         "SSA",
    "South Asia":                                                         "SAS",
    "Middle East, North Africa, Afghanistan & Pakistan (excluding high income)": "MNA",
    # Alias alternativos por si cambia el nombre en la API
    "East Asia & Pacific":                                                "EAP",
    "Latin America & Caribbean":                                          "LAC",
    "Sub-Saharan Africa":                                                 "SSA",
    "Middle East & North Africa":                                         "MNA",
}

_ISO3_SET: set[str] = set(COUNTRIES_ISO3)

# ── Catalogo de indicadores ───────────────────────────────────────────────────

@dataclass
class IndicatorConfig:
    """Metadatos de un indicador del Banco Mundial."""
    wb_code:      str   # Codigo WB, ej: "NY.GDP.MKTP.KD.ZG"
    short_name:   str   # Nombre corto para indicator_id en BD
    name_es:      str   # Descripcion en espanol
    unit:         str   # 'pct', 'usd', 'index', 'ratio', 'count', 'months', etc.
    module:       str   # Modulo del dashboard que consume el dato
    subcategory:  str   # Subcategoria
    source_detail:str   # Fuente dentro del WB (ej: 'WDI')


INDICATOR_CATALOG: list[IndicatorConfig] = [

    # ── Grupo 1: PIB y Actividad Economica ───────────────────────────────────
    IndicatorConfig("NY.GDP.MKTP.KD.ZG", "gdp_growth",     "Crecimiento PIB real (% anual)",          "pct",    "macro",        "gdp",          "WDI"),
    IndicatorConfig("NY.GDP.MKTP.CD",    "gdp_nominal",     "PIB nominal (USD corrientes)",             "usd",    "macro",        "gdp",          "WDI"),
    IndicatorConfig("NY.GDP.MKTP.KD",    "gdp_real",        "PIB real (USD const. 2015)",               "usd",    "macro",        "gdp",          "WDI"),
    IndicatorConfig("NY.GDP.PCAP.KD.ZG", "gdp_pc_growth",   "Crec. PIB per capita real (%)",            "pct",    "macro",        "gdp",          "WDI"),
    IndicatorConfig("NY.GDP.PCAP.CD",    "gdp_pc",          "PIB per capita (USD corrientes)",           "usd",    "macro",        "gdp",          "WDI"),
    IndicatorConfig("NY.GDP.PCAP.PP.CD", "gdp_pc_ppp",      "PIB per capita PPP (USD int.)",             "usd",    "macro",        "gdp",          "WDI"),
    IndicatorConfig("NE.CON.PRVT.ZS",   "consumption_pct", "Consumo privado % PIB",                    "pct",    "macro",        "gdp",          "WDI"),
    IndicatorConfig("NE.GDI.TOTL.ZS",   "investment_pct",  "Inversion bruta % PIB",                    "pct",    "macro",        "gdp",          "WDI"),
    IndicatorConfig("NE.EXP.GNFS.ZS",   "exports_pct",     "Exportaciones % PIB",                      "pct",    "macro",        "trade",        "WDI"),
    IndicatorConfig("NE.IMP.GNFS.ZS",   "imports_pct",     "Importaciones % PIB",                      "pct",    "macro",        "trade",        "WDI"),
    IndicatorConfig("NV.IND.MANF.ZS",   "manuf_pct",       "Manufactura % PIB",                        "pct",    "macro",        "gdp",          "WDI"),
    IndicatorConfig("NV.SRV.TOTL.ZS",   "services_pct",    "Servicios % PIB",                          "pct",    "macro",        "gdp",          "WDI"),

    # ── Grupo 2: Inflacion ────────────────────────────────────────────────────
    IndicatorConfig("FP.CPI.TOTL.ZG",   "cpi_inflation",   "Inflacion IPC (% anual)",                  "pct",    "inflation",    "cpi",          "WDI"),
    IndicatorConfig("FP.CPI.TOTL",       "cpi_index",       "Indice precios consumidor (2010=100)",      "index",  "inflation",    "cpi",          "WDI"),

    # ── Grupo 3: Mercado Laboral ──────────────────────────────────────────────
    IndicatorConfig("SL.UEM.TOTL.ZS",   "unemployment",    "Tasa desempleo total (%)",                 "pct",    "labor",        "employment",   "WDI"),
    IndicatorConfig("SL.UEM.1524.ZS",   "youth_unemp",     "Desempleo juvenil 15-24 (%)",              "pct",    "labor",        "employment",   "WDI"),
    IndicatorConfig("SL.TLF.CACT.ZS",   "labor_force_pct", "Participacion fuerza laboral (%)",         "pct",    "labor",        "employment",   "WDI"),
    IndicatorConfig("SL.GDP.PCAP.EM.KD","labor_product",   "PIB por empleado (USD const. 2017)",       "usd",    "labor",        "employment",   "WDI"),
    IndicatorConfig("SL.UEM.LONG.ZS",   "long_unemp",      "Desempleo larga duracion (%)",             "pct",    "labor",        "employment",   "WDI"),

    # ── Grupo 4: Deuda y Fiscalidad ───────────────────────────────────────────
    IndicatorConfig("GC.DOD.TOTL.GD.ZS","gov_debt_pct",    "Deuda gobierno central % PIB",             "pct",    "debt",         "fiscal",       "WDI"),
    IndicatorConfig("GC.BAL.CASH.GD.ZS","fiscal_balance",  "Superavit/deficit fiscal % PIB",           "pct",    "debt",         "fiscal",       "WDI"),
    IndicatorConfig("GC.REV.XGRT.GD.ZS","tax_revenue_pct", "Ingresos fiscales % PIB",                  "pct",    "debt",         "fiscal",       "WDI"),
    IndicatorConfig("GC.XPN.TOTL.GD.ZS","gov_spend_pct",   "Gasto gobierno % PIB",                     "pct",    "debt",         "fiscal",       "WDI"),
    IndicatorConfig("DT.DOD.DECT.GD.ZS","ext_debt_pct",    "Deuda externa total % PIB",                "pct",    "debt",         "fiscal",       "WDI"),
    IndicatorConfig("DT.TDS.DECT.GN.ZS","ext_debt_svc",    "Servicio deuda externa % INB",             "pct",    "debt",         "fiscal",       "WDI"),

    # ── Grupo 5: Comercio Internacional ──────────────────────────────────────
    IndicatorConfig("NE.TRD.GNFS.ZS",   "trade_pct",       "Comercio total % PIB",                     "pct",    "macro",        "trade",        "WDI"),
    IndicatorConfig("BN.CAB.XOKA.GD.ZS","curr_account",    "Cuenta corriente % PIB",                   "pct",    "macro",        "trade",        "WDI"),
    IndicatorConfig("BX.KLT.DINV.WD.GD.ZS","fdi_net_pct", "IDE neta % PIB",                            "pct",    "macro",        "trade",        "WDI"),
    IndicatorConfig("FI.RES.TOTL.CD",   "reserves_usd",    "Reservas totales (USD corrientes)",         "usd",    "macro",        "trade",        "WDI"),
    IndicatorConfig("FI.RES.TOTL.MO",   "reserves_months", "Reservas (meses de importaciones)",        "months", "macro",        "trade",        "WDI"),

    # ── Grupo 6: Sistema Financiero ───────────────────────────────────────────
    IndicatorConfig("FS.AST.DOMS.GD.ZS","domestic_credit", "Credito domestico % PIB",                  "pct",    "financial",    "banking",      "WDI"),
    IndicatorConfig("FB.AST.NPER.ZS",   "npl_ratio",       "Prestamos morosos % total (NPL)",          "pct",    "financial",    "banking",      "WDI"),
    IndicatorConfig("FB.BNK.CAPA.ZS",   "bank_capital",    "Capital bancario % activos",               "pct",    "financial",    "banking",      "WDI"),

    # ── Grupo 7: Energia y Medio Ambiente ────────────────────────────────────
    IndicatorConfig("EG.USE.PCAP.KG.OE","energy_use_pc",   "Consumo energia per capita (kgoe)",        "kgoe",   "energy",       "structural",   "WDI"),
    IndicatorConfig("EG.IMP.CONS.ZS",   "energy_imports",  "Importaciones energia % consumo",          "pct",    "energy",       "structural",   "WDI"),
    IndicatorConfig("EG.ELC.RNEW.ZS",   "renewables_pct",  "Electricidad renovable (%)",               "pct",    "energy",       "structural",   "WDI"),
    IndicatorConfig("EG.ELC.FOSL.ZS",   "fossil_elec_pct", "Electricidad fosil (%)",                   "pct",    "energy",       "structural",   "WDI"),
    IndicatorConfig("EN.ATM.CO2E.PC",   "co2_pc",          "Emisiones CO2 per capita (t)",              "tonnes", "energy",       "structural",   "WDI"),

    # ── Grupo 8: Demografia ───────────────────────────────────────────────────
    IndicatorConfig("SP.POP.TOTL",       "population",      "Poblacion total",                          "count",  "demographics", "population",   "WDI"),
    IndicatorConfig("SP.POP.GROW",       "pop_growth",      "Crecimiento poblacion (% anual)",          "pct",    "demographics", "population",   "WDI"),
    IndicatorConfig("SP.DYN.TFRT.IN",   "fertility",       "Tasa fertilidad (hijos/mujer)",             "ratio",  "demographics", "population",   "WDI"),
    IndicatorConfig("SP.POP.DPND.OL",   "old_dep_ratio",   "Ratio dependencia ancianos (65+/15-64)",   "ratio",  "demographics", "population",   "WDI"),
    IndicatorConfig("SP.POP.DPND.YG",   "young_dep_ratio", "Ratio dependencia joven (0-14/15-64)",     "ratio",  "demographics", "population",   "WDI"),
    IndicatorConfig("SP.POP.65UP.TO.ZS","pop_65plus_pct",  "Poblacion 65+ (% total)",                  "pct",    "demographics", "population",   "WDI"),
    IndicatorConfig("SP.POP.1564.TO.ZS","working_age_pct", "Poblacion 15-64 (% total)",                "pct",    "demographics", "population",   "WDI"),
    IndicatorConfig("SM.POP.NETM",       "net_migration",   "Migracion neta (personas)",                "count",  "demographics", "population",   "WDI"),
    IndicatorConfig("SP.URB.TOTL.IN.ZS","urban_pct",       "Poblacion urbana (% total)",               "pct",    "demographics", "population",   "WDI"),
    IndicatorConfig("SP.DYN.LE00.IN",   "life_expectancy", "Esperanza de vida al nacer (anos)",        "years",  "demographics", "population",   "WDI"),

    # ── Grupo 9: Desigualdad y Desarrollo ────────────────────────────────────
    IndicatorConfig("SI.POV.GINI",       "gini",            "Indice Gini (0=igualdad, 100=maxima)",     "index",  "demographics", "inequality",   "WDI"),
    IndicatorConfig("SI.POV.DDAY",       "extreme_poverty", "Pobreza extrema % (<2.15 USD/dia)",        "pct",    "demographics", "inequality",   "WDI"),
    IndicatorConfig("NY.GNP.PCAP.CD",   "gni_pc",          "INB per capita Atlas method (USD)",        "usd",    "demographics", "inequality",   "WDI"),

    # ── Grupo 10: Educacion y Productividad ──────────────────────────────────
    IndicatorConfig("GB.XPD.RSDV.GD.ZS","rd_spending",     "Gasto I+D % PIB",                          "pct",    "demographics", "productivity", "WDI"),
    IndicatorConfig("SE.TER.ENRR",       "tertiary_educ",   "Matriculacion educacion terciaria (%)",    "pct",    "demographics", "productivity", "WDI"),
    IndicatorConfig("IT.NET.USER.ZS",   "internet_users",  "Usuarios internet (% poblacion)",          "pct",    "demographics", "productivity", "WDI"),
]

# Indices de acceso rapido
INDICATOR_BY_CODE:  dict[str, IndicatorConfig] = {c.wb_code:     c for c in INDICATOR_CATALOG}
INDICATOR_BY_SHORT: dict[str, IndicatorConfig] = {c.short_name:  c for c in INDICATOR_CATALOG}


# ── Clase principal ───────────────────────────────────────────────────────────

class WorldBankCollector(BaseCollector):
    """
    Colector del Banco Mundial.
    Descarga datos anuales de 43 indicadores para 45 paises/regiones.
    No requiere API key.
    """

    SOURCE = "worldbank"

    def __init__(self) -> None:
        self._errors: list[str] = []
        logger.info(
            "WorldBankCollector inicializado. %d indicadores, %d paises/regiones.",
            len(INDICATOR_CATALOG), len(COUNTRIES_ISO3),
        )

    # ── Metodos publicos principales ──────────────────────────────────────────

    def run_full_history(self) -> dict:
        """
        Descarga el historico completo desde HISTORY_START para todos los
        indicadores y paises. Solo ejecutar la primera vez o para recarga total.
        """
        self._errors = []
        logger.info(
            "WB >> Inicio historico completo: %d indicadores desde %d",
            len(INDICATOR_CATALOG), HISTORY_START,
        )
        return self._run_download(
            start_year=HISTORY_START,
            end_year=datetime.now().year,
            countries=COUNTRIES_ISO3,
            upsert=False,
        )

    def run_update(self) -> dict:
        """
        Rehace los ultimos UPDATE_WINDOW_YEARS anos con DELETE+INSERT
        para capturar las revisiones retroactivas frecuentes del Banco Mundial.
        """
        self._errors = []
        current_year = datetime.now().year
        start_year   = current_year - UPDATE_WINDOW_YEARS
        logger.info(
            "WB >> Actualizacion: indicadores %d-%d (%d anos)",
            start_year, current_year, UPDATE_WINDOW_YEARS,
        )
        return self._run_download(
            start_year=start_year,
            end_year=current_year,
            countries=COUNTRIES_ISO3,
            upsert=True,
        )

    def download_indicators(
        self,
        indicator_codes: list[str],
        countries:        Optional[list[str]] = None,
        start_year:       int = HISTORY_START,
    ) -> dict:
        """
        Descarga un subconjunto de indicadores. Util para tests y depuracion.

        Args:
            indicator_codes: lista de codigos WB (ej: ['NY.GDP.MKTP.KD.ZG'])
            countries:       lista de ISO3; si None usa COUNTRIES_ISO3
            start_year:      primer ano del historico

        Returns:
            dict con ok, failed, total_records, errors
        """
        self._errors = []
        cfgs = []
        for code in indicator_codes:
            cfg = INDICATOR_BY_CODE.get(code)
            if cfg is None:
                logger.warning("Indicador desconocido: %s — ignorado", code)
                self._errors.append(f"Indicador desconocido: {code}")
                continue
            cfgs.append(cfg)

        return self._run_download(
            start_year=start_year,
            end_year=datetime.now().year,
            countries=countries or COUNTRIES_ISO3,
            upsert=False,
            indicator_subset=cfgs,
        )

    def get_last_update_time(self) -> Optional[datetime]:
        """Retorna el datetime UTC de la ultima actualizacion de este colector."""
        with SessionLocal() as session:
            ts = session.query(func.max(TimeSeries.created_at)).filter(
                TimeSeries.source == self.SOURCE
            ).scalar()
        return ts

    def get_status(self) -> dict:
        """Retorna el estado del colector para monitorizacion."""
        with SessionLocal() as session:
            total = session.query(func.count(TimeSeries.id)).filter(
                TimeSeries.source == self.SOURCE
            ).scalar() or 0

            series_count = session.query(
                func.count(TimeSeries.indicator_id.distinct())
            ).filter(TimeSeries.source == self.SOURCE).scalar() or 0

        last_update = self.get_last_update_time()
        status = "never_run" if last_update is None else (
            "error" if self._errors else "ok"
        )
        return {
            "source":        self.SOURCE,
            "last_update":   last_update,
            "total_records": total,
            "series_count":  series_count,
            "status":        status,
            "errors":        list(self._errors),
        }

    # ── Metodos de utilidad publica ───────────────────────────────────────────

    def get_country_data(
        self,
        country_iso3: str,
        indicator_code: str,
        start_date: Optional[datetime] = None,
    ) -> pd.DataFrame:
        """
        Devuelve la serie temporal completa de un pais e indicador como DataFrame.

        Args:
            country_iso3:    Codigo ISO3 del pais (ej: 'ESP')
            indicator_code:  Codigo WB (ej: 'NY.GDP.MKTP.KD.ZG')
            start_date:      Filtro de fecha inicial (opcional)

        Returns:
            DataFrame con columnas [timestamp, value, unit, indicator_id]
            Vacio si no hay datos.
        """
        cfg = INDICATOR_BY_CODE.get(indicator_code)
        if cfg is None:
            logger.warning("get_country_data: indicador desconocido %s", indicator_code)
            return pd.DataFrame()

        indicator_id = f"wb_{cfg.short_name}_{country_iso3.lower()}"

        with SessionLocal() as session:
            query = (
                session.query(
                    TimeSeries.timestamp,
                    TimeSeries.value,
                    TimeSeries.unit,
                    TimeSeries.indicator_id,
                )
                .filter(TimeSeries.indicator_id == indicator_id)
            )
            if start_date is not None:
                query = query.filter(TimeSeries.timestamp >= start_date)
            rows = query.order_by(TimeSeries.timestamp).all()

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows, columns=["timestamp", "value", "unit", "indicator_id"])
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["year"] = df["timestamp"].dt.year
        return df

    def get_indicator_ranking(
        self,
        indicator_code: str,
        year: Optional[int] = None,
        exclude_aggregates: bool = True,
    ) -> pd.DataFrame:
        """
        Devuelve todos los paises ordenados por valor de un indicador en un ano dado.

        Args:
            indicator_code:     Codigo WB
            year:               Ano de referencia; si None, usa el mas reciente disponible
            exclude_aggregates: Si True, excluye WLD, EUU, EMU, EAP, LAC, SSA, SAS, MNA

        Returns:
            DataFrame con columnas [country_iso3, value, year] ordenado desc.
            Vacio si no hay datos.
        """
        cfg = INDICATOR_BY_CODE.get(indicator_code)
        if cfg is None:
            return pd.DataFrame()

        _aggregates = {"WLD", "EUU", "EMU", "EAP", "LAC", "SSA", "SAS", "MNA"}

        rows_all: list[dict] = []
        for iso3 in COUNTRIES_ISO3:
            if exclude_aggregates and iso3 in _aggregates:
                continue
            indicator_id = f"wb_{cfg.short_name}_{iso3.lower()}"
            with SessionLocal() as session:
                if year is not None:
                    ts_from = datetime(year, 1, 1)
                    ts_to   = datetime(year, 12, 31)
                    row = (
                        session.query(TimeSeries.timestamp, TimeSeries.value)
                        .filter(
                            TimeSeries.indicator_id == indicator_id,
                            TimeSeries.timestamp >= ts_from,
                            TimeSeries.timestamp <= ts_to,
                        )
                        .order_by(TimeSeries.timestamp.desc())
                        .first()
                    )
                else:
                    row = (
                        session.query(TimeSeries.timestamp, TimeSeries.value)
                        .filter(TimeSeries.indicator_id == indicator_id)
                        .order_by(TimeSeries.timestamp.desc())
                        .first()
                    )
            if row and row.value is not None:
                rows_all.append({
                    "country_iso3": iso3,
                    "value":        row.value,
                    "year":         row.timestamp.year,
                })

        if not rows_all:
            return pd.DataFrame()

        df = pd.DataFrame(rows_all).sort_values("value", ascending=False).reset_index(drop=True)
        return df

    # ── Metodos privados ──────────────────────────────────────────────────────

    def _run_download(
        self,
        start_year:        int,
        end_year:          int,
        countries:         list[str],
        upsert:            bool,
        indicator_subset:  Optional[list[IndicatorConfig]] = None,
    ) -> dict:
        """Bucle principal de descarga: itera sobre indicadores con rate limiting."""
        catalog = indicator_subset if indicator_subset is not None else INDICATOR_CATALOG
        ok_count      = 0
        failed_count  = 0
        total_records = 0

        for i, cfg in enumerate(catalog, 1):
            logger.info(
                "WB [%d/%d] %s — %s",
                i, len(catalog), cfg.wb_code, cfg.name_es,
            )
            try:
                n, with_data, without_data = self._download_indicator(
                    cfg, countries, start_year, end_year, upsert=upsert,
                )
                total_records += n
                ok_count += 1
                logger.info(
                    "  OK %s: %d registros | %d paises con datos, %d sin datos",
                    cfg.short_name, n, with_data, without_data,
                )
            except Exception as exc:
                msg = f"{cfg.wb_code}: {exc}"
                self._errors.append(msg)
                failed_count += 1
                logger.error("  FAIL %s: %s", cfg.wb_code, exc)

            if i < len(catalog):
                time.sleep(RATE_LIMIT_DELAY)

        return {
            "ok":            ok_count,
            "failed":        failed_count,
            "total_records": total_records,
            "errors":        list(self._errors),
        }

    def _download_indicator(
        self,
        cfg:        IndicatorConfig,
        countries:  list[str],
        start_year: int,
        end_year:   int,
        upsert:     bool = False,
    ) -> tuple[int, int, int]:
        """
        Descarga un indicador para todos los paises y lo persiste en SQLite.

        Returns:
            (registros_insertados, paises_con_datos, paises_sin_datos)
        """
        try:
            raw_df = wbdata.get_dataframe(
                {cfg.wb_code: "value"},
                country=countries,
                date=(str(start_year), str(end_year)),
            )
        except Exception as exc:
            raise RuntimeError(f"wbdata API error: {exc}") from exc

        if raw_df is None or (hasattr(raw_df, "empty") and raw_df.empty):
            return 0, 0, len(countries)

        # Parsear el DataFrame a {iso3: pd.Series(float, index=DatetimeIndex)}
        country_series = self._parse_wb_dataframe(raw_df, countries)

        total_saved   = 0
        with_data     = 0
        without_data  = 0

        for iso3 in countries:
            series = country_series.get(iso3)
            if series is None or series.dropna().empty:
                without_data += 1
                continue

            indicator_id = f"wb_{cfg.short_name}_{iso3.lower()}"
            try:
                n = self._save_series(
                    indicator_id=indicator_id,
                    data=series.dropna(),
                    region=iso3,
                    module=cfg.module,
                    unit=cfg.unit,
                    upsert=upsert,
                )
                total_saved += n
                with_data   += 1
            except Exception as exc:
                logger.debug("  Skip %s/%s: %s", iso3, cfg.short_name, exc)
                without_data += 1

        return total_saved, with_data, without_data

    def _parse_wb_dataframe(
        self,
        df:                pd.DataFrame,
        requested_iso3:    list[str],
    ) -> dict[str, pd.Series]:
        """
        Convierte el DataFrame devuelto por wbdata en un dict {iso3: pd.Series}.

        wbdata devuelve MultiIndex (country_name, year_string) con columna 'value'.
        El nivel 0 usa el nombre oficial del pais en ingles (ej: "Viet Nam"),
        no el codigo ISO3.  Usamos _WB_NAME_TO_ISO3 para el mapeo inverso.
        """
        result: dict[str, pd.Series] = {}

        if not isinstance(df.index, pd.MultiIndex):
            # Caso inesperado: serie de un solo pais con DatetimeIndex
            try:
                s = df["value"].dropna() if "value" in df.columns else df.iloc[:, 0].dropna()
                s.index = pd.to_datetime(s.index.astype(str).str[:4] + "-01-01")
                s = s.sort_index()
                if requested_iso3:
                    result[requested_iso3[0]] = s
            except Exception:
                pass
            return result

        level0_vals = df.index.get_level_values(0).unique().tolist()

        for idx_val in level0_vals:
            # 1) Puede que el nivel 0 YA sea un codigo ISO3
            iso3 = idx_val if idx_val in _ISO3_SET else _WB_NAME_TO_ISO3.get(idx_val)
            if iso3 is None or iso3 not in _ISO3_SET:
                logger.debug("  Nombre pais no reconocido: %r", idx_val)
                continue

            try:
                subset = df.loc[idx_val]["value"] if "value" in df.columns else df.loc[idx_val].iloc[:, 0]
                # El index es el ano como string ("2023", "2022", ...)
                subset = subset.dropna()
                if subset.empty:
                    continue
                # Convertir "2023" -> datetime(2023, 1, 1)
                subset.index = pd.to_datetime(subset.index.astype(str).str[:4] + "-01-01")
                subset = subset.sort_index()
                result[iso3] = subset
            except Exception as exc:
                logger.debug("  Error parseando %s (%s): %s", idx_val, iso3, exc)

        return result

    def _save_series(
        self,
        indicator_id: str,
        data:         pd.Series,
        region:       str,
        module:       str,
        unit:         str,
        upsert:       bool = False,
    ) -> int:
        """
        Persiste una serie en SQLite.

        - upsert=False (run_full_history): solo inserta registros mas recientes
          que el MAX(timestamp) existente (identico a FRED/Yahoo).
        - upsert=True  (run_update):       borra los registros existentes en el
          rango de la nueva descarga y los reinserta, capturando revisiones WB.
        """
        data = data.dropna()
        if data.empty:
            return 0

        if not upsert:
            with SessionLocal() as session:
                max_ts = session.query(func.max(TimeSeries.timestamp)).filter(
                    TimeSeries.indicator_id == indicator_id
                ).scalar()
            if max_ts is not None:
                data = data[data.index > pd.Timestamp(max_ts)]
            if data.empty:
                return 0

        now = datetime.utcnow()
        records = [
            {
                "indicator_id": indicator_id,
                "source":       self.SOURCE,
                "region":       region,
                "timestamp":    pd.Timestamp(ts).to_pydatetime().replace(tzinfo=None),
                "value":        float(val),
                "unit":         unit,
                "created_at":   now,
            }
            for ts, val in data.items()
            if not pd.isna(val)
        ]

        if not records:
            return 0

        with SessionLocal() as session:
            if upsert:
                min_ts = min(r["timestamp"] for r in records)
                session.execute(
                    text(
                        "DELETE FROM time_series "
                        "WHERE indicator_id = :iid AND timestamp >= :min_ts"
                    ),
                    {"iid": indicator_id, "min_ts": min_ts},
                )
            session.execute(insert(TimeSeries), records)
            session.commit()

        return len(records)

    def _load_indicator_from_db(
        self,
        indicator_id: str,
        start_date:   Optional[datetime] = None,
    ) -> pd.Series:
        """Carga un indicador de SQLite como pd.Series(float, DatetimeIndex)."""
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

        idx  = pd.to_datetime([r.timestamp for r in rows])
        vals = [r.value for r in rows]
        return pd.Series(vals, index=idx, name=indicator_id)
