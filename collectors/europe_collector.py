"""
Colector europeo combinado: BCE (Banco Central Europeo) + Eurostat.

BCE: tipos oficiales, EURIBOR, balance, agregados monetarios, credito, bonos soberanos.
Eurostat: HICP, desempleo, PIB trimestral, produccion industrial, deuda/deficit,
          sentimiento economico, comercio exterior.

No requiere API key.
Alimenta los modulos: M02 (Macro), M03 (Inflacion), M04 (Politica Monetaria),
                      M05 (Mercados), M06 (Laboral), M08 (Deuda).
"""

import gzip
import json as _json
import logging
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from itertools import product as iterproduct
from pathlib import Path
from typing import Optional

import pandas as pd
import requests
from sqlalchemy import func, insert, text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collectors.base_collector import BaseCollector
from database.database import SessionLocal, TimeSeries

try:
    from config import FRED_API_KEY
except ImportError:
    FRED_API_KEY = ""

logger = logging.getLogger(__name__)

# ── Constantes ────────────────────────────────────────────────────────────────

ECB_BASE       = "https://data-api.ecb.europa.eu/service/data"
ESTAT_BASE     = "https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data"
FRED_BASE      = "https://api.stlouisfed.org/fred/series/observations"
HISTORY_START  = 1999    # Inicio del euro
UPDATE_WINDOW  = 6       # Meses a rehacer en run_update
RATE_DELAY     = 1.2     # Delay entre peticiones (s)
TIMEOUT        = 45      # Timeout HTTP (s)

ECB_SOURCE     = "ecb"
ESTAT_SOURCE   = "eurostat"
DERIVED_SOURCE = "ecb_derived"


# ── Catalogo BCE ──────────────────────────────────────────────────────────────

@dataclass
class EcbSeries:
    """Metadatos de una serie BCE."""
    key:          str   # Flow/key completo, ej: "FM/B.U2.EUR.4F.KR.MRR_FR.LEV"
    indicator_id: str   # ID canonico en BD
    name_es:      str   # Descripcion en espanol (cp1252 safe)
    unit:         str   # 'pct', 'eur_mn', etc.
    module:       str
    subcategory:  str
    region:       str = "EA"


ECB_CATALOG: list[EcbSeries] = [

    # -- Grupo 1: Tipos oficiales BCE -----------------------------------------
    EcbSeries("FM/B.U2.EUR.4F.KR.MRR_FR.LEV",        "ecb_deposit_rate_ea",   "Tipo facilidad deposito BCE",            "pct",    "monetary_policy", "ecb_rates"),
    EcbSeries("FM/B.U2.EUR.4F.KR.MRR_MBR.LEV",       "ecb_refi_rate_ea",      "Tipo principal refinanciacion BCE",      "pct",    "monetary_policy", "ecb_rates"),
    EcbSeries("FM/B.U2.EUR.4F.KR.MLFR.LEV",          "ecb_lending_rate_ea",   "Tipo facilidad marginal credito BCE",    "pct",    "monetary_policy", "ecb_rates"),

    # -- Grupo 2: Euro Short-Term Rate (sustituye EONIA, tipo a 1 dia) --------
    EcbSeries("EST/B.EU000A2X2A25.WT",                "ecb_estr_overnight_ea", "Euro Short-Term Rate overnight (ESTR)", "pct",    "monetary_policy", "estr"),

    # -- Grupo 3: Agregados monetarios M1/M2/M3 --------------------------------
    EcbSeries("BSI/M.U2.Y.V.M10.X.1.U2.2300.Z01.E", "ecb_m1_ea",             "Agregado monetario M1 eurozona",         "eur_mn", "monetary_policy", "money_supply"),
    EcbSeries("BSI/M.U2.Y.V.M20.X.1.U2.2300.Z01.E", "ecb_m2_ea",             "Agregado monetario M2 eurozona",         "eur_mn", "monetary_policy", "money_supply"),
    EcbSeries("BSI/M.U2.Y.V.M30.X.1.U2.2300.Z01.E", "ecb_m3_ea",             "Agregado monetario M3 eurozona",         "eur_mn", "monetary_policy", "money_supply"),

    # -- Grupo 4: Credito bancario --------------------------------------------
    EcbSeries("BSI/M.U2.Y.U.A20.A.1.U2.2250.Z01.E", "ecb_loans_hh_ea",       "Prestamos hogares eurozona",             "eur_mn", "financial",       "credit"),
    EcbSeries("BSI/M.U2.Y.U.A20.A.1.U2.2240.Z01.E", "ecb_loans_nfc_ea",      "Prestamos soc. no financieras",          "eur_mn", "financial",       "credit"),

    # -- Grupo 5: Curva tipos soberana eurozona (BCE YC flow) -----------------
    EcbSeries("YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y","ecb_yield_ea_10y_ea",   "Curva tipos eurozona 10 anos",           "pct",    "markets",         "sovereign_spreads"),
    # Nota: Bonos soberanos por pais se descargan via FRED (ver _FRED_BONDS)
]

ECB_BY_ID: dict[str, EcbSeries] = {s.indicator_id: s for s in ECB_CATALOG}

# Bonos soberanos via FRED (ECB no expone por pais en su nueva API)
# Tuplas: (fred_series_id, indicator_id, nombre_es, region)
_FRED_BONDS: list[tuple] = [
    ("IRLTLT01DEM156N", "ecb_bund_10y_de",  "Bund aleman 10 anos",    "DE"),
    ("IRLTLT01ESM156N", "ecb_yield_10y_es", "Bono espanol 10 anos",   "ES"),
    ("IRLTLT01ITM156N", "ecb_yield_10y_it", "Bono italiano 10 anos",  "IT"),
    ("IRLTLT01FRM156N", "ecb_yield_10y_fr", "Bono frances 10 anos",   "FR"),
    ("IRLTLT01PTM156N", "ecb_yield_10y_pt", "Bono portugues 10 anos", "PT"),
    ("IRLTLT01GRM156N", "ecb_yield_10y_gr", "Bono griego 10 anos",    "GR"),
    ("IR3TIB01EZM156N", "ecb_euribor_3m_ea","EURIBOR 3M interbanc EA","EA"),
]

# Spreads: (country, yield_id, bund_id, spread_id, name, region)
SPREAD_CONFIGS: list[tuple] = [
    ("ES", "ecb_yield_10y_es", "ecb_bund_10y_de", "ecb_spread_es_de", "Prima riesgo Espana", "ES"),
    ("IT", "ecb_yield_10y_it", "ecb_bund_10y_de", "ecb_spread_it_de", "Prima riesgo Italia",  "IT"),
    ("FR", "ecb_yield_10y_fr", "ecb_bund_10y_de", "ecb_spread_fr_de", "Prima riesgo Francia", "FR"),
    ("PT", "ecb_yield_10y_pt", "ecb_bund_10y_de", "ecb_spread_pt_de", "Prima riesgo Portugal","PT"),
    ("GR", "ecb_yield_10y_gr", "ecb_bund_10y_de", "ecb_spread_gr_de", "Prima riesgo Grecia",  "GR"),
]


# ── Catalogo Eurostat ─────────────────────────────────────────────────────────

@dataclass
class EurostatDataset:
    """Metadatos de un dataset Eurostat."""
    code:             str
    indicator_prefix: str        # Prefijo del indicator_id, ej: "estat_hicp"
    name_es:          str
    unit:             str
    module:           str
    subcategory:      str
    params:           dict                # Valores de filtro por dimension
    id_dims:          list[str]           # Dims a incluir en indicator_id (ademas de geo)
    sdmx_key_dims:    list[str] = field(default_factory=list)
    # Dims en orden para clave SDMX (incl. freq, excl. time). Si vacio, sin path filter.


# Listas de paises para los filtros
_EU_ALL  = ["EU27_2020", "EA20", "BE", "BG", "CZ", "DK", "DE", "EE", "IE", "GR",
            "ES", "FR", "HR", "IT", "CY", "LV", "LT", "LU", "HU", "MT", "NL",
            "AT", "PL", "PT", "RO", "SI", "SK", "FI", "SE"]
_EU_MAIN = ["EU27_2020", "EA20", "DE", "FR", "ES", "IT", "PT", "GR", "NL", "PL", "SE"]
_EU_SENT = ["EU27_2020", "EA20", "DE", "FR", "ES", "IT", "NL", "PL"]
_EU_IND  = ["EU27_2020", "EA20", "DE", "FR", "ES", "IT", "NL", "PL"]

EUROSTAT_CATALOG: list[EurostatDataset] = [

    # -- Grupo 7: Inflacion HICP (variacion anual %) --------------------------
    # dims: [freq, unit, coicop, geo, time]  -> clave: .{unit}.{coicop}.{geo}
    EurostatDataset(
        "prc_hicp_aind", "estat_hicp",
        "Inflacion HICP por pais europeo",
        "pct", "inflation", "hicp",
        {"freq": "M", "unit": "RCH_A_AVG",
         "coicop": ["CP00", "SERV", "FOOD", "NRG", "IGD_NNRG", "CP041"],
         "geo": _EU_ALL},
        id_dims=["coicop"],
        sdmx_key_dims=["freq", "unit", "coicop", "geo"],
    ),

    # -- Grupo 8: Desempleo mensual (%) ----------------------------------------
    # dims: [freq, s_adj, age, unit, sex, geo, time]  -> .{s_adj}.{age}.{unit}.{sex}.{geo}
    EurostatDataset(
        "une_rt_m", "estat_unemp",
        "Tasa desempleo mensual Europa",
        "pct", "labor", "unemployment",
        {"freq": "M", "s_adj": "SA",
         "age": ["TOTAL", "Y_LT25"],
         "unit": "PC_ACT",
         "sex": ["T"],
         "geo": _EU_ALL},
        id_dims=["age"],
        sdmx_key_dims=["freq", "s_adj", "age", "unit", "sex", "geo"],
    ),

    # -- Grupo 9: PIB trimestral -----------------------------------------------
    # dims: [freq, unit, s_adj, na_item, geo, time]  -> .{unit}.{s_adj}.{na_item}.{geo}
    EurostatDataset(
        "namq_10_gdp", "estat_gdp_q",
        "PIB trimestral Europa",
        "pct", "macro", "gdp_quarterly",
        {"freq": "Q", "unit": ["CLV_PCH_SM", "CLV_PCH_PRE"],
         "s_adj": "SCA", "na_item": "B1GQ",
         "geo": _EU_MAIN},
        id_dims=["unit"],
        sdmx_key_dims=["freq", "unit", "s_adj", "na_item", "geo"],
    ),

    # -- Grupo 10: Produccion industrial (mensual) ----------------------------
    # dims: [freq, indic_bt, nace_r2, s_adj, unit, geo, time] -> ..{nace_r2}.{s_adj}.{unit}.{geo}
    EurostatDataset(
        "sts_inpr_m", "estat_indpro",
        "Produccion industrial mensual Europa",
        "index", "macro", "industrial",
        {"freq": "M",
         "nace_r2": "B-D", "s_adj": "SCA",
         "unit": ["I15", "PCH_SM"],
         "geo": _EU_IND},
        id_dims=["unit"],
        sdmx_key_dims=["freq", "indic_bt", "nace_r2", "s_adj", "unit", "geo"],
    ),

    # -- Grupo 11: Deuda y deficit oficial (EDP, anual) -----------------------
    # dims: [freq, unit, sector, na_item, geo, time]  -> .{unit}.{sector}.{na_item}.{geo}
    EurostatDataset(
        "gov_10dd_edpt1", "estat_edp",
        "Deuda y deficit EDP Europa",
        "pct", "debt", "edp",
        {"freq": "A", "unit": "PC_GDP",
         "sector": "S13",
         "na_item": ["B9", "GD"],
         "geo": _EU_ALL},
        id_dims=["na_item"],
        sdmx_key_dims=["freq", "unit", "sector", "na_item", "geo"],
    ),

    # -- Grupo 12: Confianza consumidor (mensual) - sustituye ei_bssi_m -------
    # dims: [freq, indic, s_adj, unit, geo, time]  -> .{indic}.{s_adj}.{unit}.{geo}
    EurostatDataset(
        "ei_bsco_m", "estat_consconf",
        "Confianza consumidor Europa",
        "index", "macro", "sentiment",
        {"freq": "M",
         "indic": ["BS-CSMCI", "BS-FS-NY", "BS-GES-NY", "BS-UE-NY"],
         "s_adj": "SA",
         "unit": "BAL",
         "geo": _EU_SENT},
        id_dims=["indic"],
        sdmx_key_dims=["freq", "indic", "s_adj", "unit", "geo"],
    ),

    # -- Grupo 13: Comercio exterior UE (anual) --------------------------------
    # dims: [freq, indic_et, sitc06, partner, geo, time] -> .{indic_et}.{sitc06}.{partner}.{geo}
    # Nota: geo solo tiene EU27_2020 (no EA20)
    EurostatDataset(
        "ext_lt_maineu", "estat_trade",
        "Comercio exterior UE con principales socios",
        "eur_mn", "macro", "trade",
        {"freq": "A",
         "indic_et": ["MIO_EXP_VAL", "MIO_IMP_VAL", "MIO_BAL_VAL"],
         "sitc06": "TOTAL",
         "partner": ["US", "CN_X_HK", "UK", "JP", "RU"],
         "geo": ["EU27_2020"]},
        id_dims=["indic_et", "partner"],
        sdmx_key_dims=["freq", "indic_et", "sitc06", "partner", "geo"],
    ),
]


# ── Colector principal ────────────────────────────────────────────────────────

class EuropeCollector(BaseCollector):
    """
    Colector combinado BCE + Eurostat.

    Descarga tipos BCE, EURIBOR, balance BCE, agregados monetarios, bonos
    soberanos y datasets Eurostat (HICP, desempleo, PIB, prod. industrial,
    deuda, sentimiento, comercio). Sin API key.

    Uso tipico:
        collector = EuropeCollector()
        collector.run_full_history()   # Primera vez
        collector.run_update()         # Ejecuciones periodicas
    """

    SOURCE = "ecb"   # Fuente primaria (get_status combina ecb + eurostat + ecb_derived)

    def __init__(self) -> None:
        self._errors: list[str] = []
        self._session = requests.Session()
        self._session.headers.update({
            "Accept": "application/json, */*",
            "Accept-Encoding": "gzip, deflate",
            "User-Agent": "WorldMonitor/1.0",
        })
        logger.info(
            "EuropeCollector inicializado. BCE: %d series | Eurostat: %d datasets.",
            len(ECB_CATALOG), len(EUROSTAT_CATALOG),
        )

    # ── BaseCollector interface ───────────────────────────────────────────────

    def run_full_history(self) -> dict:
        """Descarga historico completo (BCE desde 1999, Eurostat desde 2000)."""
        self._errors = []
        t0 = time.time()
        logger.info("=" * 64)
        logger.info("Europe >> Inicio historico completo")
        logger.info("=" * 64)

        r_ecb   = self._download_all_ecb(start_period=f"{HISTORY_START}-01", upsert=False)
        r_fred  = self._download_sovereign_bonds_fred(start_date="1999-01-01", upsert=False)
        r_estat = self._download_all_eurostat(start_period="2000-01", upsert=False)
        self._compute_spreads()

        ok      = r_ecb["ok"]      + r_fred["ok"]      + r_estat["ok"]
        failed  = r_ecb["failed"]  + r_fred["failed"]  + r_estat["failed"]
        records = r_ecb["total_records"] + r_fred["total_records"] + r_estat["total_records"]
        elapsed = time.time() - t0

        logger.info("=" * 64)
        logger.info(
            "Europe >> Historico completo en %.1fs | OK: %d | Fail: %d | Registros: %d",
            elapsed, ok, failed, records,
        )
        logger.info("=" * 64)
        return {"ok": ok, "failed": failed, "total_records": records, "errors": list(self._errors)}

    def run_update(self) -> dict:
        """Rehace los ultimos UPDATE_WINDOW meses para capturar revisiones."""
        self._errors = []
        cutoff     = datetime.utcnow() - timedelta(days=UPDATE_WINDOW * 31)
        start      = cutoff.strftime("%Y-%m")
        start_date = cutoff.strftime("%Y-%m-%d")
        t0         = time.time()

        logger.info("Europe >> Actualizacion desde %s", start)
        r_ecb   = self._download_all_ecb(start_period=start, upsert=True)
        r_fred  = self._download_sovereign_bonds_fred(start_date=start_date, upsert=True)
        r_estat = self._download_all_eurostat(start_period=start, upsert=True)
        self._compute_spreads()

        ok      = r_ecb["ok"]      + r_fred["ok"]      + r_estat["ok"]
        failed  = r_ecb["failed"]  + r_fred["failed"]  + r_estat["failed"]
        records = r_ecb["total_records"] + r_fred["total_records"] + r_estat["total_records"]

        logger.info(
            "Europe >> Actualizacion en %.1fs | Nuevos registros: %d",
            time.time() - t0, records,
        )
        return {"ok": ok, "failed": failed, "total_records": records, "errors": list(self._errors)}

    def get_last_update_time(self) -> Optional[datetime]:
        with SessionLocal() as session:
            return session.query(func.max(TimeSeries.created_at)).filter(
                TimeSeries.source.in_([ECB_SOURCE, ESTAT_SOURCE, DERIVED_SOURCE])
            ).scalar()

    def get_status(self) -> dict:
        with SessionLocal() as session:
            total = session.query(func.count(TimeSeries.id)).filter(
                TimeSeries.source.in_([ECB_SOURCE, ESTAT_SOURCE, DERIVED_SOURCE])
            ).scalar() or 0

            series_count = session.query(
                func.count(TimeSeries.indicator_id.distinct())
            ).filter(
                TimeSeries.source.in_([ECB_SOURCE, ESTAT_SOURCE, DERIVED_SOURCE])
            ).scalar() or 0

        last   = self.get_last_update_time()
        status = "never_run" if last is None else ("error" if self._errors else "ok")
        return {
            "source":        self.SOURCE,
            "last_update":   last,
            "total_records": total,
            "series_count":  series_count,
            "status":        status,
            "errors":        list(self._errors),
        }

    # ── Metodo publico de utilidad ────────────────────────────────────────────

    def get_spread(
        self,
        country_code: str,
        start_date:   Optional[datetime] = None,
    ) -> pd.DataFrame:
        """
        Devuelve la prima de riesgo (spread vs Bund) de un pais europeo.

        Args:
            country_code: "ES", "IT", "FR", "PT" o "GR"
            start_date:   filtro de fecha inicial (opcional)

        Returns:
            DataFrame con columnas [timestamp, value, unit].
            value = spread en puntos basicos (bps). Vacio si sin datos.
        """
        spread_id = f"ecb_spread_{country_code.strip().upper().lower()}_de"
        with SessionLocal() as session:
            q = (
                session.query(TimeSeries.timestamp, TimeSeries.value, TimeSeries.unit)
                .filter(TimeSeries.indicator_id == spread_id)
            )
            if start_date:
                q = q.filter(TimeSeries.timestamp >= start_date)
            rows = q.order_by(TimeSeries.timestamp).all()

        if not rows:
            return pd.DataFrame(columns=["timestamp", "value", "unit"])

        df = pd.DataFrame(rows, columns=["timestamp", "value", "unit"])
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        return df

    # ── Descarga BCE ──────────────────────────────────────────────────────────

    def _download_all_ecb(self, start_period: str, upsert: bool) -> dict:
        """Itera sobre el catalogo BCE y descarga cada serie."""
        ok = failed = total = 0
        n  = len(ECB_CATALOG)

        for i, s in enumerate(ECB_CATALOG, 1):
            logger.info("ECB [%02d/%d] %s  %s", i, n, s.key, s.name_es)
            try:
                data = self._fetch_ecb_series(s.key, start_period=start_period)
                if data is None or data.empty:
                    logger.info("  ECB SKIP %s -- sin datos", s.indicator_id)
                    ok += 1
                else:
                    saved = self._save_series(
                        indicator_id=s.indicator_id,
                        data=data,
                        source=ECB_SOURCE,
                        region=s.region,
                        module=s.module,
                        unit=s.unit,
                        upsert=upsert,
                    )
                    total += saved
                    ok    += 1
                    logger.info("  ECB OK %s -- %d nuevos registros", s.indicator_id, saved)
            except Exception as exc:
                msg = f"ECB {s.key}: {exc}"
                logger.error("  ECB FAIL %s: %s", s.key, exc)
                self._errors.append(msg)
                failed += 1

            if i < n:
                time.sleep(RATE_DELAY)

        return {"ok": ok, "failed": failed, "total_records": total}

    def _fetch_ecb_series(
        self,
        series_key:   str,
        start_period: str = "1999-01",
    ) -> Optional[pd.Series]:
        """
        Descarga una serie BCE via API SDMX-JSON.

        La clave tiene formato "FLOW/dimension1.dimension2...".
        Devuelve pd.Series(float, DatetimeIndex) o None si no hay datos.
        """
        url    = f"{ECB_BASE}/{series_key}"
        params = {
            "format":      "jsondata",
            "startPeriod": start_period,
            "detail":      "dataonly",
        }

        try:
            resp = self._session.get(url, params=params, timeout=TIMEOUT)
        except requests.RequestException as exc:
            raise RuntimeError(f"Error de red: {exc}") from exc

        if resp.status_code == 404:
            logger.warning("  ECB 404: %s -- serie no encontrada en el portal", series_key)
            return None
        if resp.status_code == 400:
            logger.warning("  ECB 400: %s -- clave de serie invalida", series_key)
            return None
        if resp.status_code == 204:
            return None  # Sin contenido
        if resp.status_code != 200:
            raise RuntimeError(f"HTTP {resp.status_code} para {series_key}: {resp.text[:120]}")

        # Respuesta vacia (body en blanco aunque status=200)
        if not resp.content:
            logger.debug("  ECB respuesta vacia para %s", series_key)
            return None

        try:
            return self._parse_ecb_sdmx(resp.json(), series_key)
        except Exception as exc:
            # Si el JSON falla por respuesta vacia/malformada, tratar como sin datos
            if not resp.text.strip():
                return None
            raise RuntimeError(f"Error parseando SDMX: {exc}") from exc

    def _parse_ecb_sdmx(self, data: dict, series_key: str = "") -> Optional[pd.Series]:
        """
        Parsea respuesta SDMX-JSON del BCE.

        Estructura:
          dataSets[0].series["0:0:..."}.observations = {obs_idx_str: [value, ...]}
          structure.dimensions.observation[?].values[obs_idx] = {"id": "2020-01"}
        """
        try:
            datasets = data.get("dataSets", [])
            if not datasets:
                return None

            series_dict = datasets[0].get("series", {})
            if not series_dict:
                return None

            # Localizar la dimension TIME_PERIOD
            obs_dims = data["structure"]["dimensions"]["observation"]
            time_dim = next(
                (d for d in obs_dims if d.get("id") == "TIME_PERIOD"),
                obs_dims[0] if obs_dims else None,
            )
            if time_dim is None:
                return None

            time_values: list[str] = [v["id"] for v in time_dim["values"]]

            # Tomar la primera (normalmente unica) serie
            inner_key   = next(iter(series_dict))
            observations = series_dict[inner_key].get("observations", {})
            if not observations:
                return None

            dates: list[datetime] = []
            vals:  list[float]    = []

            for idx_str, obs_vals in observations.items():
                idx = int(idx_str)
                if idx >= len(time_values):
                    continue
                raw_val = obs_vals[0] if obs_vals else None
                if raw_val is None:
                    continue
                try:
                    ts  = self._parse_period(time_values[idx])
                    dates.append(ts)
                    vals.append(float(raw_val))
                except (ValueError, TypeError):
                    continue

            if not dates:
                return None

            s = pd.Series(vals, index=pd.DatetimeIndex(dates), dtype=float)
            return s.sort_index()

        except (KeyError, IndexError, TypeError, StopIteration) as exc:
            logger.debug("  Error parseando SDMX %s: %s", series_key, exc)
            return None

    # ── Descarga bonos soberanos via FRED ─────────────────────────────────────

    def _download_sovereign_bonds_fred(self, start_date: str, upsert: bool) -> dict:
        """
        Descarga rendimientos bonos soberanos (Bund, ES, IT, FR, PT, GR + EURIBOR 3M)
        desde FRED. Almacena con IDs ecb_bund_10y_de, ecb_yield_10y_es, etc.
        para que _compute_spreads() pueda calcular las primas de riesgo.
        """
        if not FRED_API_KEY:
            logger.warning("FRED_API_KEY no configurado -- salto descarga bonos soberanos")
            return {"ok": 0, "failed": 0, "total_records": 0}

        ok = failed = total = 0
        n  = len(_FRED_BONDS)

        for i, (fred_id, indicator_id, name_es, region) in enumerate(_FRED_BONDS, 1):
            logger.info("FRED [%02d/%d] %s  %s", i, n, fred_id, name_es)
            try:
                params = {
                    "series_id":          fred_id,
                    "api_key":            FRED_API_KEY,
                    "file_type":          "json",
                    "observation_start":  start_date,
                    "sort_order":         "asc",
                }
                resp = self._session.get(FRED_BASE, params=params, timeout=TIMEOUT)
                if resp.status_code != 200:
                    raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:100]}")

                obs = resp.json().get("observations", [])
                dates, vals = [], []
                for o in obs:
                    if o["value"] == ".":
                        continue
                    try:
                        dates.append(datetime.strptime(o["date"], "%Y-%m-%d"))
                        vals.append(float(o["value"]))
                    except (ValueError, KeyError):
                        continue

                if not dates:
                    logger.info("  FRED SKIP %s -- sin datos", indicator_id)
                    ok += 1
                    continue

                series = pd.Series(vals, index=pd.DatetimeIndex(dates), dtype=float)
                saved = self._save_series(
                    indicator_id=indicator_id,
                    data=series,
                    source=ECB_SOURCE,
                    region=region,
                    module="markets",
                    unit="pct",
                    upsert=upsert,
                )
                total += saved
                ok    += 1
                logger.info("  FRED OK %s -- %d nuevos registros", indicator_id, saved)

            except Exception as exc:
                msg = f"FRED {fred_id}: {exc}"
                logger.error("  FRED FAIL %s: %s", fred_id, exc)
                self._errors.append(msg)
                failed += 1

            if i < n:
                time.sleep(0.5)

        return {"ok": ok, "failed": failed, "total_records": total}

    # ── Descarga Eurostat ─────────────────────────────────────────────────────

    def _download_all_eurostat(self, start_period: str, upsert: bool) -> dict:
        """Itera sobre el catalogo Eurostat y descarga cada dataset."""
        ok = failed = total = 0
        n  = len(EUROSTAT_CATALOG)

        for i, ds in enumerate(EUROSTAT_CATALOG, 1):
            logger.info("ESTAT [%02d/%d] %s  %s", i, n, ds.code, ds.name_es)
            try:
                saved = self._fetch_eurostat_dataset(
                    ds, start_period=start_period, upsert=upsert
                )
                total += saved
                ok    += 1
                logger.info("  ESTAT OK %s -- %d nuevos registros", ds.code, saved)
            except Exception as exc:
                msg = f"Eurostat {ds.code}: {exc}"
                logger.error("  ESTAT FAIL %s: %s", ds.code, exc)
                self._errors.append(msg)
                failed += 1

            if i < n:
                time.sleep(RATE_DELAY)

        return {"ok": ok, "failed": failed, "total_records": total}

    @staticmethod
    def _build_sdmx_key(ds: EurostatDataset) -> str:
        """
        Construye la clave SDMX para el path de la URL Eurostat.

        Para cada dimension en sdmx_key_dims (excluyendo 'time'):
          - 'freq' siempre es wildcard (cadena vacia)
          - Si la dimension no esta en params -> wildcard
          - Si es lista -> valores unidos con '+'
          - Si es escalar -> el valor tal cual
        Las partes se unen con '.' -> resultado tipo ".RCH_A_AVG.CP00.ES+DE"
        """
        parts: list[str] = []
        for dim in ds.sdmx_key_dims:
            if dim == "time":
                continue
            if dim == "freq":
                parts.append("")          # siempre wildcard para freq
                continue
            val = ds.params.get(dim)
            if val is None:
                parts.append("")          # wildcard
            elif isinstance(val, list):
                parts.append("+".join(str(v) for v in val))
            else:
                parts.append(str(val))
        return ".".join(parts)

    def _fetch_eurostat_dataset(
        self,
        ds:           EurostatDataset,
        start_period: str  = "2000-01",
        upsert:       bool = False,
    ) -> int:
        """
        Descarga un dataset Eurostat con filtros SDMX y persiste en SQLite.
        Retorna el numero de registros nuevos insertados.

        Usa el endpoint SDMX 2.1 con path-key para filtrado eficiente.
        La respuesta puede ser JSON gzip-comprimido (Content-Encoding no declarado).
        """
        sdmx_key = self._build_sdmx_key(ds)
        url = f"{ESTAT_BASE}/{ds.code}/{sdmx_key}" if sdmx_key else f"{ESTAT_BASE}/{ds.code}"
        params   = {
            "format":          "JSON",
            "lang":            "EN",
            "sinceTimePeriod": start_period,
        }

        try:
            resp = self._session.get(url, params=params, timeout=TIMEOUT)
        except requests.RequestException as exc:
            raise RuntimeError(f"Error de red Eurostat: {exc}") from exc

        if resp.status_code == 404:
            logger.warning("  ESTAT 404 para %s", ds.code)
            return 0
        if resp.status_code == 400:
            logger.warning("  ESTAT 400 para %s (clave: %s): %s",
                           ds.code, sdmx_key, resp.text[:200])
            return 0
        if resp.status_code != 200:
            raise RuntimeError(
                f"HTTP {resp.status_code} para {ds.code}: {resp.text[:200]}"
            )

        # Eurostat puede responder con gzip aunque no declare Content-Encoding
        raw = resp.content
        if raw[:2] == b"\x1f\x8b":
            raw = gzip.decompress(raw)

        try:
            jdata = _json.loads(raw.decode("utf-8", errors="replace"))
        except Exception as exc:
            raise RuntimeError(f"Error parseando JSON Eurostat {ds.code}: {exc}") from exc

        return self._parse_and_save_eurostat(jdata, ds, upsert=upsert)

    def _parse_and_save_eurostat(
        self,
        jdata:  dict,
        ds:     EurostatDataset,
        upsert: bool = False,
    ) -> int:
        """
        Parsea la respuesta JSON-stat 2.0 de Eurostat y guarda en SQLite.

        El indicator_id se construye como:
            {ds.indicator_prefix}_{dim1_val}_{...}_{geo_code}
        donde dim1, dim2... son las dimensiones en ds.id_dims.
        """
        try:
            dim_ids   = jdata["id"]      # lista de nombres de dimensiones
            dim_sizes = jdata["size"]    # tamano de cada dimension
            dims      = jdata["dimension"]
            values    = jdata["value"]   # array plano de valores (puede ser dict)
            statuses  = jdata.get("status", {})
        except KeyError as exc:
            raise RuntimeError(f"JSON-stat malformado, campo faltante: {exc}") from exc

        # Extraer categorias ordenadas por su indice para cada dimension
        # dim_cats[i] = lista de codigos en orden
        dim_cats: list[list[str]] = []
        for dim_id in dim_ids:
            cat_index = dims[dim_id]["category"]["index"]
            if isinstance(cat_index, dict):
                ordered = sorted(cat_index.keys(), key=lambda k: cat_index[k])
            else:
                ordered = list(cat_index)
            dim_cats.append(ordered)

        # Calcular factores para mapeo multidimensional -> indice plano
        # flat_idx = sum(all_indices[i] * factors[i])
        factors = [1] * len(dim_ids)
        for i in range(len(dim_ids) - 2, -1, -1):
            factors[i] = factors[i + 1] * dim_sizes[i + 1]

        # Localizar dimension geo y time (obligatorias)
        try:
            geo_idx  = dim_ids.index("geo")
            time_idx = dim_ids.index("time")
        except ValueError as exc:
            raise RuntimeError(f"Dataset {ds.code} sin dimension geo o time: {exc}") from exc

        geo_cats  = dim_cats[geo_idx]
        time_cats = dim_cats[time_idx]

        # Indices de las dimensiones que se incluyen en el indicator_id
        id_dim_indices = [dim_ids.index(d) for d in ds.id_dims if d in dim_ids]

        # Indices de dimensiones "fijas" (todas las que no son geo ni time)
        fixed_indices = [
            i for i in range(len(dim_ids)) if i not in (geo_idx, time_idx)
        ]
        fixed_ranges  = [range(dim_sizes[i]) for i in fixed_indices]

        # JSON-stat permite que 'value' sea dict (indice -> valor) o lista
        if isinstance(values, dict):
            val_array = [values.get(str(k)) for k in range(max(int(k) for k in values) + 1)]
        else:
            val_array = values

        total_saved = 0

        for fixed_combo in iterproduct(*fixed_ranges):
            # Construir los sufijos del indicator_id (solo las id_dims)
            suffix_parts: list[str] = []
            for i, cat_i in zip(fixed_indices, fixed_combo):
                if i in id_dim_indices:
                    raw = dim_cats[i][cat_i]
                    # Limpiar: lowercase, guiones->guion_bajo, quitar chars especiales
                    clean = (
                        raw.lower()
                        .replace("-", "_")
                        .replace(" ", "_")
                        .replace("/", "_")
                        .replace(".", "_")
                    )
                    suffix_parts.append(clean)

            for gi, geo_code in enumerate(geo_cats):
                geo_clean   = geo_code.lower().replace("_", "")  # EU27_2020 -> eu272020
                id_parts    = [ds.indicator_prefix] + suffix_parts + [geo_clean]
                indicator_id = "_".join(id_parts)[:120]  # max 120 chars

                # Extraer serie temporal para esta combinacion (fixed_combo + geo)
                dates: list[datetime] = []
                vals:  list[float]    = []

                for ti, period_str in enumerate(time_cats):
                    all_idx = [0] * len(dim_ids)
                    for fi, ci in zip(fixed_indices, fixed_combo):
                        all_idx[fi] = ci
                    all_idx[geo_idx]  = gi
                    all_idx[time_idx] = ti

                    flat = sum(all_idx[k] * factors[k] for k in range(len(dim_ids)))

                    # Verificar dato disponible
                    status_val = statuses.get(str(flat))
                    if status_val == ":":
                        continue

                    raw_val = val_array[flat] if flat < len(val_array) else None
                    if raw_val is None:
                        continue

                    try:
                        ts = self._parse_period(period_str)
                        dates.append(ts)
                        vals.append(float(raw_val))
                    except (ValueError, TypeError):
                        continue

                if not dates:
                    continue

                series = pd.Series(vals, index=pd.DatetimeIndex(dates), dtype=float)
                series = series.sort_index()

                try:
                    n = self._save_series(
                        indicator_id=indicator_id,
                        data=series,
                        source=ESTAT_SOURCE,
                        region=geo_code,
                        module=ds.module,
                        unit=ds.unit,
                        upsert=upsert,
                    )
                    total_saved += n
                except Exception as exc:
                    logger.debug("  Error guardando %s: %s", indicator_id, exc)

        return total_saved

    # ── Series derivadas (spreads soberanos) ──────────────────────────────────

    def _compute_spreads(self) -> None:
        """Calcula y guarda las primas de riesgo soberanas vs Bund aleman (bps)."""
        logger.info("Europe >> Calculando spreads soberanos...")

        bund = self._load_from_db("ecb_bund_10y_de")
        if bund.empty:
            logger.warning("  SKIP spreads: sin datos del Bund aleman en BD")
            return

        for country, yield_id, _bund_id, spread_id, name, region in SPREAD_CONFIGS:
            yld = self._load_from_db(yield_id)
            if yld.empty:
                logger.debug("  SKIP %s: sin datos de bono para %s", spread_id, country)
                continue

            aligned = pd.concat([yld, bund], axis=1).dropna()
            if aligned.empty:
                continue

            aligned.columns = ["yield_c", "bund"]
            spread = (aligned["yield_c"] - aligned["bund"]) * 100  # -> bps

            n = self._save_series(
                indicator_id=spread_id,
                data=spread,
                source=DERIVED_SOURCE,
                region=region,
                module="markets",
                unit="bps",
                upsert=True,
            )
            logger.info("  OK spread %s  %s -- %d registros", spread_id, name, n)

    # ── Soporte comun ─────────────────────────────────────────────────────────

    @staticmethod
    def _parse_period(period_str: str) -> datetime:
        """
        Convierte un periodo a datetime.

        Formatos soportados:
            "2020-01-15"  diario
            "2020-01"     mensual
            "2020-Q1"     trimestral
            "2020-W01"    semanal (lunes de esa semana)
            "2020"        anual
        """
        s = period_str.strip()

        if len(s) == 4:
            return datetime(int(s), 1, 1)

        if "-Q" in s:
            year_s, q_s = s.split("-Q")
            month = (int(q_s) - 1) * 3 + 1
            return datetime(int(year_s), month, 1)

        if "-W" in s:
            import datetime as _dt
            year_s, w_s = s.split("-W")
            d = _dt.date.fromisocalendar(int(year_s), int(w_s), 1)
            return datetime(d.year, d.month, d.day)

        if len(s) == 7:   # "2020-01"
            return datetime(int(s[:4]), int(s[5:7]), 1)

        if len(s) == 10:  # "2020-01-15"
            return datetime(int(s[:4]), int(s[5:7]), int(s[8:10]))

        raise ValueError(f"Formato de periodo no reconocido: {period_str!r}")

    def _save_series(
        self,
        indicator_id: str,
        data:         pd.Series,
        source:       str,
        region:       str,
        module:       str,
        unit:         str,
        upsert:       bool = False,
    ) -> int:
        """
        Persiste una serie en SQLite.

        upsert=False: solo inserta registros mas nuevos que MAX(timestamp).
        upsert=True:  DELETE+INSERT para capturar revisiones retroactivas.
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
                "source":       source,
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

    def _load_from_db(
        self,
        indicator_id: str,
        start_date:   Optional[datetime] = None,
    ) -> pd.Series:
        """Carga un indicador de SQLite como pd.Series(float, DatetimeIndex)."""
        with SessionLocal() as session:
            q = (
                session.query(TimeSeries.timestamp, TimeSeries.value)
                .filter(TimeSeries.indicator_id == indicator_id)
            )
            if start_date:
                q = q.filter(TimeSeries.timestamp >= start_date)
            rows = q.order_by(TimeSeries.timestamp).all()

        if not rows:
            return pd.Series(dtype=float)

        return pd.Series(
            [r.value for r in rows],
            index=pd.to_datetime([r.timestamp for r in rows]),
            name=indicator_id,
            dtype=float,
        )
