"""
Script de prueba del colector World Bank.

Descarga 5 indicadores para 6 paises/regiones, verifica SQLite,
imprime tabla comparativa y rankings.

Uso:
    cd "World Monitor"
    python scripts/test_worldbank.py
"""

import logging
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collectors.worldbank_collector import (
    INDICATOR_BY_CODE,
    COUNTRIES_ISO3,
    WorldBankCollector,
)
from database.database import SessionLocal, TimeSeries

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Subconjunto para la prueba
TEST_INDICATORS = [
    "NY.GDP.MKTP.KD.ZG",   # Crecimiento PIB real
    "FP.CPI.TOTL.ZG",      # Inflacion IPC
    "SL.UEM.TOTL.ZS",      # Desempleo
    "GC.DOD.TOTL.GD.ZS",   # Deuda gobierno % PIB
    "SP.DYN.TFRT.IN",      # Tasa fertilidad
]

TEST_COUNTRIES = ["USA", "ESP", "CHN", "DEU", "BRA", "WLD"]

# Nombres legibles para la tabla
COUNTRY_NAMES = {
    "USA": "EE.UU.",
    "ESP": "Espana",
    "CHN": "China",
    "DEU": "Alemania",
    "BRA": "Brasil",
    "WLD": "Mundo",
}

START_YEAR = 2000


def sep(title: str = "", width: int = 70) -> None:
    if title:
        pad = (width - len(title) - 2) // 2
        print(f"\n{'-' * pad} {title} {'-' * (width - pad - len(title) - 2)}")
    else:
        print("-" * width)


def get_latest_value(indicator_id: str) -> tuple[float | None, int | None]:
    """Devuelve (valor, ano) del registro mas reciente para un indicator_id."""
    with SessionLocal() as session:
        row = (
            session.query(TimeSeries.timestamp, TimeSeries.value)
            .filter(TimeSeries.indicator_id == indicator_id)
            .order_by(TimeSeries.timestamp.desc())
            .first()
        )
    if row and row.value is not None:
        return row.value, row.timestamp.year
    return None, None


def count_records(indicator_id: str) -> int:
    with SessionLocal() as session:
        return (
            session.query(TimeSeries)
            .filter(TimeSeries.indicator_id == indicator_id)
            .count()
        )


def main() -> None:
    print()
    sep("WORLD MONITOR - TEST COLECTOR WORLD BANK")
    print(f"  Indicadores de prueba : {len(TEST_INDICATORS)}")
    print(f"  Paises de prueba      : {TEST_COUNTRIES}")
    print(f"  Periodo               : {START_YEAR} -> hoy (datos anuales)")

    # ── 1. Inicializar colector ───────────────────────────────────────────────
    sep("1. INICIALIZACION")
    collector = WorldBankCollector()
    print("  OK WorldBankCollector listo (sin API key requerida)")

    # ── 2. Descarga ───────────────────────────────────────────────────────────
    sep("2. DESCARGA")
    result = collector.download_indicators(
        indicator_codes=TEST_INDICATORS,
        countries=TEST_COUNTRIES,
        start_year=START_YEAR,
    )
    print()
    print(f"  Indicadores OK      : {result['ok']}")
    print(f"  Indicadores FAIL    : {result['failed']}")
    print(f"  Registros nuevos    : {result['total_records']:,}")
    if result.get("errors"):
        print(f"  Errores             :")
        for e in result["errors"]:
            print(f"    - {e}")

    # ── 3. Verificacion en SQLite ─────────────────────────────────────────────
    sep("3. VERIFICACION EN SQLITE")
    print()
    print(f"  {'indicator_id':<35}  {'Registros':>9}  {'Ultimo ano':>10}")
    sep()
    for wb_code in TEST_INDICATORS:
        cfg = INDICATOR_BY_CODE[wb_code]
        for iso3 in TEST_COUNTRIES:
            iid = f"wb_{cfg.short_name}_{iso3.lower()}"
            cnt = count_records(iid)
            _, yr = get_latest_value(iid)
            yr_str = str(yr) if yr else "N/A"
            print(f"  {iid:<35}  {cnt:>9,}  {yr_str:>10}")

    # ── 4. Tabla comparativa por pais ─────────────────────────────────────────
    sep("4. TABLA COMPARATIVA - ULTIMO ANO DISPONIBLE")
    print()

    # Recopilar datos
    table: dict[str, dict] = {iso3: {} for iso3 in TEST_COUNTRIES}
    for wb_code in TEST_INDICATORS:
        cfg = INDICATOR_BY_CODE[wb_code]
        for iso3 in TEST_COUNTRIES:
            iid = f"wb_{cfg.short_name}_{iso3.lower()}"
            val, yr = get_latest_value(iid)
            table[iso3][cfg.short_name] = (val, yr)

    # Cabecera
    h_country  = f"{'Pais':<12}"
    h_gdp      = f"{'PIB crecim':>12}"
    h_infl     = f"{'Inflacion':>11}"
    h_unemp    = f"{'Desempleo':>11}"
    h_debt     = f"{'Deuda/PIB':>11}"
    h_fertil   = f"{'Fertilidad':>12}"
    print(f"  {h_country}  {h_gdp}  {h_infl}  {h_unemp}  {h_debt}  {h_fertil}")
    print(f"  {'':<12}  {'(%)':<12}  {'(%)':<11}  {'(%)':<11}  {'(%)':<11}  {'(h/mujer)':<12}")
    sep()

    for iso3 in TEST_COUNTRIES:
        name = COUNTRY_NAMES.get(iso3, iso3)
        d = table[iso3]

        def fmt(key, decimals=1):
            v, _ = d.get(key, (None, None))
            if v is None:
                return "N/A"
            return f"{v:+.{decimals}f}" if key in ("gdp_growth", "fiscal_balance") else f"{v:.{decimals}f}"

        gdp_str   = fmt("gdp_growth")
        infl_str  = fmt("cpi_inflation")
        unemp_str = fmt("unemployment")
        debt_str  = fmt("gov_debt_pct")
        fert_str  = fmt("fertility", 2)

        # Ano de referencia (usa el de PIB)
        _, yr_gdp = d.get("gdp_growth", (None, None))
        yr_str = f"({yr_gdp})" if yr_gdp else ""

        print(
            f"  {name:<12}  {gdp_str:>12}  {infl_str:>11}  "
            f"{unemp_str:>11}  {debt_str:>11}  {fert_str:>12}  {yr_str}"
        )

    # ── 5. Ranking PIB crecimiento ────────────────────────────────────────────
    sep("5. RANKING - MAYOR CRECIMIENTO DEL PIB (todos los paises)")
    print()
    ranking_gdp = collector.get_indicator_ranking(
        "NY.GDP.MKTP.KD.ZG", exclude_aggregates=True
    )
    if not ranking_gdp.empty:
        top10 = ranking_gdp.head(10)
        print(f"  {'Pos':>4}  {'Pais':<8}  {'Crecim. PIB %':>15}  {'Ano':>6}")
        sep()
        for rank, row in enumerate(top10.itertuples(), 1):
            print(
                f"  {rank:>4}  {row.country_iso3:<8}  {row.value:>+15.2f}  {row.year:>6}"
            )
    else:
        print("  Sin datos disponibles.")

    # ── 6. Ranking deuda/PIB ──────────────────────────────────────────────────
    sep("6. RANKING - MAYOR DEUDA GOBIERNO / PIB")
    print()
    ranking_debt = collector.get_indicator_ranking(
        "GC.DOD.TOTL.GD.ZS", exclude_aggregates=True
    )
    if not ranking_debt.empty:
        top10 = ranking_debt.head(10)
        print(f"  {'Pos':>4}  {'Pais':<8}  {'Deuda/PIB %':>13}  {'Ano':>6}")
        sep()
        for rank, row in enumerate(top10.itertuples(), 1):
            print(
                f"  {rank:>4}  {row.country_iso3:<8}  {row.value:>13.1f}  {row.year:>6}"
            )
    else:
        print("  Sin datos disponibles.")

    # ── 7. Ranking fertilidad (menor = mas envejecido) ────────────────────────
    sep("7. RANKING - MENOR TASA DE FERTILIDAD (mas envejecidos)")
    print()
    ranking_fert = collector.get_indicator_ranking(
        "SP.DYN.TFRT.IN", exclude_aggregates=True
    )
    if not ranking_fert.empty:
        # Menor fertilidad = bottom of ranking (ya viene desc, tomamos el tail)
        bot10 = ranking_fert.tail(10).iloc[::-1].reset_index(drop=True)
        print(f"  {'Pos':>4}  {'Pais':<8}  {'Fertilidad':>12}  {'Umbral 2.1':>12}  {'Ano':>6}")
        sep()
        for rank, row in enumerate(bot10.itertuples(), 1):
            diff = row.value - 2.1
            diff_str = f"{diff:+.2f}"
            print(
                f"  {rank:>4}  {row.country_iso3:<8}  {row.value:>12.2f}  {diff_str:>12}  {row.year:>6}"
            )
    else:
        print("  Sin datos disponibles.")

    # ── Resumen final ─────────────────────────────────────────────────────────
    sep("RESUMEN DEL COLECTOR")
    status = collector.get_status()
    print()
    print(f"  Fuente              : {status['source'].upper()}")
    print(f"  Estado              : {status['status'].upper()}")
    print(f"  Total registros BD  : {status['total_records']:,}")
    print(f"  Series unicas BD    : {status['series_count']}")
    print(f"  Ultima actualiz.    : {status['last_update']}")
    if status["errors"]:
        print(f"  Errores ({len(status['errors'])}):")
        for e in status["errors"]:
            print(f"    - {e}")
    print()
    sep()
    print("  Test completado.")
    print("  Para el historico completo: collector.run_full_history()")
    print()


if __name__ == "__main__":
    main()
