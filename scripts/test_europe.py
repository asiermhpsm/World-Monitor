"""
Script de prueba del colector Europe (BCE + Eurostat).

Descarga un subconjunto rapido de datos BCE y Eurostat, verifica SQLite
e imprime un resumen de indicadores clave europeos.

Uso:
    cd "World Monitor"
    python scripts/test_europe.py
"""

import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collectors.europe_collector import (
    ECB_CATALOG,
    ECB_BY_ID,
    EUROSTAT_CATALOG,
    SPREAD_CONFIGS,
    DERIVED_SOURCE,
    _FRED_BONDS,
    EuropeCollector,
    EcbSeries,
    EurostatDataset,
)
from database.database import SessionLocal, TimeSeries

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Series de prueba (subconjunto rapido) ─────────────────────────────────────

# Serie BCE a descargar en la prueba (solo series disponibles via ECB API)
TEST_ECB_IDS = [
    "ecb_deposit_rate_ea",   # Tipo deposito BCE
    "ecb_refi_rate_ea",      # Tipo refinanciacion BCE
    "ecb_estr_overnight_ea", # Euro Short-Term Rate (ESTR)
    "ecb_m3_ea",             # Agregado M3
]

# Series FRED a descargar en la prueba (bonos soberanos + EURIBOR proxy)
TEST_FRED_IDS = [
    "ecb_bund_10y_de",   # Bund aleman (FRED: IRLTLT01DEM156N)
    "ecb_yield_10y_es",  # Bono espanol (FRED: IRLTLT01ESM156N)
    "ecb_euribor_3m_ea", # EURIBOR 3M proxy (FRED: IR3TIB01EZM156N)
]

# Paises Eurostat para HICP
TEST_HICP_GEOS = ["ES", "DE", "IT", "EA20"]


# ── Helpers ───────────────────────────────────────────────────────────────────

def sep(title: str = "", width: int = 70) -> None:
    if title:
        pad = (width - len(title) - 2) // 2
        print(f"\n{'-' * pad} {title} {'-' * (width - pad - len(title) - 2)}")
    else:
        print("-" * width)


def get_latest(indicator_id: str) -> tuple:
    """Devuelve (valor, fecha) del registro mas reciente en SQLite."""
    with SessionLocal() as session:
        row = (
            session.query(TimeSeries.value, TimeSeries.timestamp)
            .filter(TimeSeries.indicator_id == indicator_id)
            .order_by(TimeSeries.timestamp.desc())
            .first()
        )
    if row and row.value is not None:
        return row.value, row.timestamp
    return None, None


def count_records(indicator_id: str) -> int:
    with SessionLocal() as session:
        return (
            session.query(TimeSeries)
            .filter(TimeSeries.indicator_id == indicator_id)
            .count()
        )


def spread_semaforo(bps: float) -> str:
    """Devuelve etiqueta de semaforo segun puntos basicos de prima de riesgo."""
    if bps < 100:
        return "[VERDE < 100 bps]"
    elif bps < 200:
        return "[AMARILLO 100-200 bps]"
    elif bps < 300:
        return "[NARANJA 200-300 bps]"
    else:
        return "[ROJO > 300 bps]"


# ── Script principal ──────────────────────────────────────────────────────────

def main() -> None:
    print()
    sep("WORLD MONITOR - TEST COLECTOR EUROPE (BCE + Eurostat)")
    print(f"  Series BCE prueba  : {len(TEST_ECB_IDS)}")
    print(f"  Series FRED prueba : {len(TEST_FRED_IDS)}")
    print(f"  Datasets Eurostat  : 1 (HICP para ES, DE, IT, EA)")
    print()

    collector = EuropeCollector()
    print("  OK EuropeCollector listo")

    # ── 1. Descarga BCE (subconjunto) ─────────────────────────────────────────
    sep("1. DESCARGA BCE - SERIES CLAVE")

    # Construir lista de EcbSeries para las series de prueba
    test_ecb_series = [s for s in ECB_CATALOG if s.indicator_id in TEST_ECB_IDS]

    ok = failed = total_ecb = 0
    for s in test_ecb_series:
        logger.info("Descargando BCE: %s", s.key)
        try:
            data = collector._fetch_ecb_series(s.key, start_period="2020-01")
            if data is None or data.empty:
                logger.info("  SKIP %s -- sin datos", s.indicator_id)
                ok += 1
            else:
                saved = collector._save_series(
                    indicator_id=s.indicator_id,
                    data=data,
                    source="ecb",
                    region=s.region,
                    module=s.module,
                    unit=s.unit,
                    upsert=False,
                )
                total_ecb += saved
                ok        += 1
                logger.info("  OK %s -- %d nuevos registros", s.indicator_id, saved)
        except Exception as exc:
            logger.error("  FAIL %s: %s", s.key, exc)
            failed += 1

    print(f"\n  BCE OK: {ok}  |  Fail: {failed}  |  Registros nuevos: {total_ecb:,}")

    # ── 2. Descarga bonos soberanos via FRED ──────────────────────────────────
    sep("2. DESCARGA BONOS SOBERANOS (via FRED)")

    # Solo las series de prueba
    test_fred = [(fid, iid, n, r) for fid, iid, n, r in _FRED_BONDS if iid in TEST_FRED_IDS]
    ok_f = fail_f = total_fred = 0
    for fred_id, indicator_id, name_es, region in test_fred:
        logger.info("Descargando FRED: %s -> %s", fred_id, indicator_id)
        try:
            from config import FRED_API_KEY
            if not FRED_API_KEY:
                print(f"  SKIP {indicator_id} -- FRED_API_KEY no configurada")
                ok_f += 1
                continue
            resp = collector._session.get(
                "https://api.stlouisfed.org/fred/series/observations",
                params={"series_id": fred_id, "api_key": FRED_API_KEY,
                        "file_type": "json", "observation_start": "2020-01-01"},
                timeout=45,
            )
            obs = resp.json().get("observations", [])
            dates = []; vals = []
            for o in obs:
                if o["value"] != ".":
                    try:
                        dates.append(datetime.strptime(o["date"], "%Y-%m-%d"))
                        vals.append(float(o["value"]))
                    except (ValueError, KeyError):
                        pass
            if dates:
                s = pd.Series(vals, index=pd.DatetimeIndex(dates), dtype=float)
                saved = collector._save_series(indicator_id, s, "ecb", region, "markets", "pct", upsert=False)
                total_fred += saved; ok_f += 1
                logger.info("  OK %s -- %d nuevos registros", indicator_id, saved)
            else:
                logger.info("  SKIP %s -- sin datos", indicator_id); ok_f += 1
        except Exception as exc:
            logger.error("  FAIL %s: %s", fred_id, exc); fail_f += 1

    print(f"\n  FRED OK: {ok_f}  |  Fail: {fail_f}  |  Registros nuevos: {total_fred:,}")

    # Calcular spreads con lo que tenemos
    collector._compute_spreads()

    # ── 3. Descarga Eurostat (HICP Espana, Alemania, Italia, EA) ──────────────
    sep("3. DESCARGA EUROSTAT - HICP CP00 (INFLACION GENERAL)")

    # Crear dataset de prueba: solo CP00, 4 paises, desde 2020
    hicp_ds = EurostatDataset(
        code="prc_hicp_aind",
        indicator_prefix="estat_hicp",
        name_es="Inflacion HICP prueba",
        unit="pct",
        module="inflation",
        subcategory="hicp",
        params={
            "freq": "M",
            "unit": "RCH_A_AVG",
            "coicop": ["CP00"],
            "geo": TEST_HICP_GEOS,
        },
        id_dims=["coicop"],
        sdmx_key_dims=["freq", "unit", "coicop", "geo"],
    )

    try:
        saved_hicp = collector._fetch_eurostat_dataset(
            hicp_ds, start_period="2020-01", upsert=False
        )
        print(f"  Eurostat HICP OK -- {saved_hicp:,} nuevos registros")
    except Exception as exc:
        print(f"  Eurostat HICP FAIL: {exc}")
        saved_hicp = 0

    # ── 4. Verificacion SQLite ─────────────────────────────────────────────────
    sep("4. VERIFICACION EN SQLITE")
    print()
    print(f"  {'indicator_id':<38}  {'Registros':>9}  {'Ultimo dato':>12}")
    sep()

    check_ids = TEST_ECB_IDS + TEST_FRED_IDS + [
        f"ecb_spread_{cc.lower()}_de" for cc, *_ in SPREAD_CONFIGS[:2]  # ES, IT
    ] + [
        f"estat_hicp_cp00_{g.lower().replace('_', '')}" for g in TEST_HICP_GEOS
    ]

    for iid in check_ids:
        cnt  = count_records(iid)
        _, ts = get_latest(iid)
        ts_str = ts.strftime("%Y-%m-%d") if ts else "N/A"
        print(f"  {iid:<38}  {cnt:>9,}  {ts_str:>12}")

    # ── 5. Resumen de indicadores clave ───────────────────────────────────────
    sep("5. INDICADORES CLAVE ACTUALES")
    print()

    # Tipo deposito BCE
    val_dep, ts_dep = get_latest("ecb_deposit_rate_ea")
    if val_dep is not None:
        print(f"  Tipo deposito BCE     : {val_dep:.2f}%  ({ts_dep.strftime('%Y-%m')})")
    else:
        print("  Tipo deposito BCE     : sin datos")

    # EURIBOR 3M (proxy via FRED)
    val_eur, ts_eur = get_latest("ecb_euribor_3m_ea")
    if val_eur is not None:
        print(f"  EURIBOR 3M (FRED)     : {val_eur:.3f}%  ({ts_eur.strftime('%Y-%m')})")
        print(f"    -> Proxy interbanc eurozona (IR3TIB01EZM156N)")
    else:
        print("  EURIBOR 3M            : sin datos")

    # Prima de riesgo Espana
    val_es, ts_es = get_latest("ecb_spread_es_de")
    if val_es is not None:
        semaforo = spread_semaforo(val_es)
        print(f"\n  Prima riesgo Espana   : {val_es:.1f} bps  ({ts_es.strftime('%Y-%m')})  {semaforo}")
    else:
        print("\n  Prima riesgo Espana   : sin datos (necesita bono ES + Bund)")

    # Prima de riesgo Italia
    val_it, ts_it = get_latest("ecb_spread_it_de")
    if val_it is not None:
        semaforo = spread_semaforo(val_it)
        print(f"  Prima riesgo Italia   : {val_it:.1f} bps  ({ts_it.strftime('%Y-%m')})  {semaforo}")
    else:
        print("  Prima riesgo Italia   : sin datos")

    # Inflacion HICP
    print()
    hicp_map = {
        "ES":    "Espana",
        "DE":    "Alemania",
        "IT":    "Italia",
        "EA20":  "Eurozona",
    }
    print(f"  {'Pais':<12}  {'Inflacion HICP':>16}  {'Fecha':>8}")
    sep()
    for geo, nombre in hicp_map.items():
        iid = f"estat_hicp_cp00_{geo.lower().replace('_', '')}"
        val, ts = get_latest(iid)
        if val is not None:
            print(f"  {nombre:<12}  {val:>+15.2f}%  {ts.strftime('%Y-%m'):>8}")
        else:
            print(f"  {nombre:<12}  {'N/A':>16}  {'':>8}")

    # ── 6. Evolucion prima de riesgo Espana (ultimos 12 meses) ────────────────
    sep("6. EVOLUCION PRIMA DE RIESGO ESPANA (ultimos 12 meses)")
    print()

    df_spread = collector.get_spread("ES", start_date=datetime.utcnow() - timedelta(days=365))

    if not df_spread.empty:
        max_val   = df_spread["value"].max()
        min_val   = df_spread["value"].min()
        last_val  = df_spread["value"].iloc[-1]
        max_date  = df_spread.loc[df_spread["value"].idxmax(), "timestamp"].strftime("%Y-%m")
        min_date  = df_spread.loc[df_spread["value"].idxmin(), "timestamp"].strftime("%Y-%m")

        print(f"  Maximo  : {max_val:.1f} bps  ({max_date})")
        print(f"  Minimo  : {min_val:.1f} bps  ({min_date})")
        print(f"  Actual  : {last_val:.1f} bps  {spread_semaforo(last_val)}")
        print()
        print(f"  {'Fecha':<10}  {'Prima (bps)':>12}")
        sep()
        for _, row in df_spread.tail(12).iterrows():
            bar_len = int(row["value"] / 10)
            bar     = "#" * min(bar_len, 30)
            print(f"  {row['timestamp'].strftime('%Y-%m'):<10}  {row['value']:>10.1f}  {bar}")
    else:
        print("  Sin datos disponibles (se necesita bono ES 10Y + Bund 10Y descargados)")

    # ── Resumen final ──────────────────────────────────────────────────────────
    sep("RESUMEN DEL COLECTOR")
    status = collector.get_status()
    print()
    print(f"  Fuente principal    : {status['source'].upper()}")
    print(f"  Estado              : {status['status'].upper()}")
    print(f"  Total registros BD  : {status['total_records']:,}")
    print(f"  Series unicas BD    : {status['series_count']}")
    print(f"  Ultima actualizacion: {status['last_update']}")
    if status["errors"]:
        print(f"  Errores ({len(status['errors'])}):")
        for e in status["errors"][:5]:
            print(f"    - {e}")
    print()
    sep()
    print("  Test completado.")
    print("  Para historico completo: collector.run_full_history()")
    print()


if __name__ == "__main__":
    main()
