"""
Script de prueba del colector FRED.

Descarga 5 series de prueba, verifica los datos en SQLite,
imprime los últimos valores y calcula el tipo de interés real
y el estado de la curva de tipos.

Uso:
    cd "World Monitor"
    python scripts/test_fred.py
"""

import logging
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

# Permite importar desde la raíz del proyecto
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collectors.fred_collector import SERIES_CATALOG, FREDCollector
from database.database import SessionLocal, TimeSeries

# ── Logging legible en terminal ───────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Series de prueba ──────────────────────────────────────────────────────────

TEST_SERIES = ["CPIAUCSL", "DFF", "UNRATE", "DGS10", "T10Y2Y"]


# ── Helpers de presentación ───────────────────────────────────────────────────

def sep(title: str = "", width: int = 62) -> None:
    if title:
        pad = (width - len(title) - 2) // 2
        print(f"\n{'─' * pad} {title} {'─' * (width - pad - len(title) - 2)}")
    else:
        print("─" * width)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print()
    sep("WORLD MONITOR — TEST COLECTOR FRED")
    print(f"  Fecha/hora : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Series     : {TEST_SERIES}")

    # ── 1. Inicializar colector ───────────────────────────────────────────────
    sep("1. INICIALIZACIÓN")
    try:
        collector = FREDCollector()
        print("  ✓ FREDCollector listo")
    except ValueError as exc:
        print(f"  ✗ ERROR: {exc}")
        print("  → Añade FRED_API_KEY al fichero .env y vuelve a ejecutar.")
        sys.exit(1)

    # ── 2. Descargar las 5 series de prueba ───────────────────────────────────
    sep("2. DESCARGA DE SERIES (desde 2000-01-01)")
    result = collector.download_series(TEST_SERIES, observation_start="2000-01-01")
    print()
    print(f"  Series descargadas : {result['ok']}")
    print(f"  Series con error   : {result['failed']}")
    print(f"  Registros nuevos   : {result['total_records']}")
    if result.get("errors"):
        print(f"  Errores            : {result['errors']}")

    # ── 3. Verificar datos en SQLite ──────────────────────────────────────────
    sep("3. VERIFICACIÓN EN SQLITE")
    print()
    print(f"  {'Serie FRED':<20}  {'indicator_id':<38}  {'Registros':>9}")
    sep()
    with SessionLocal() as session:
        for sid in TEST_SERIES:
            cfg = SERIES_CATALOG.get(sid)
            if cfg is None:
                print(f"  {sid:<20}  {'(no en catálogo)':<38}  {'—':>9}")
                continue
            count = (
                session.query(TimeSeries)
                .filter(TimeSeries.indicator_id == cfg.indicator_id)
                .count()
            )
            print(f"  {sid:<20}  {cfg.indicator_id:<38}  {count:>9,}")

    # ── 4. Últimos 5 valores de cada serie ────────────────────────────────────
    sep("4. ÚLTIMOS 5 VALORES POR SERIE")
    with SessionLocal() as session:
        for sid in TEST_SERIES:
            cfg = SERIES_CATALOG.get(sid)
            if cfg is None:
                continue
            rows = (
                session.query(TimeSeries.timestamp, TimeSeries.value)
                .filter(TimeSeries.indicator_id == cfg.indicator_id)
                .order_by(TimeSeries.timestamp.desc())
                .limit(5)
                .all()
            )
            print(f"\n  {sid}  —  {cfg.name}  [{cfg.unit}]")
            print(f"  {'Fecha':<14}  {'Valor':>12}")
            print(f"  {'─'*14}  {'─'*12}")
            for ts, val in reversed(rows):
                date_str = ts.strftime("%Y-%m-%d")
                val_str = f"{val:>12.4f}" if val is not None else f"{'N/A':>12}"
                print(f"  {date_str:<14}  {val_str}")

    # ── 5. Tipo de interés real actual ────────────────────────────────────────
    sep("5. TIPO DE INTERÉS REAL ACTUAL")
    print()

    # Cargar DFF y CPI desde la BD y calcular en memoria
    dff_series = collector._load_indicator_from_db("fred_fed_funds_daily_us")
    cpi_series = collector._load_indicator_from_db("fred_cpi_us")

    if dff_series.empty or cpi_series.empty:
        print("  → Datos insuficientes en BD. Verifica la descarga.")
    else:
        # CPI YoY (variación interanual del nivel del índice)
        cpi_yoy = (cpi_series.pct_change(periods=12) * 100).dropna()

        # Resamplear DFF a frecuencia mensual (último valor del mes)
        dff_monthly = dff_series.resample("ME").last().dropna()

        # Alinear en fechas comunes
        aligned = pd.concat([dff_monthly, cpi_yoy], axis=1).dropna()
        aligned.columns = ["dff", "cpi_yoy"]

        if aligned.empty:
            print("  → No hay fechas comunes entre DFF y CPI YoY.")
        else:
            last = aligned.iloc[-1]
            dff_val = last["dff"]
            cpi_yoy_val = last["cpi_yoy"]
            real_rate = dff_val - cpi_yoy_val
            last_date = aligned.index[-1].strftime("%Y-%m-%d")

            print(f"  Fecha referencia       : {last_date}")
            print(f"  Federal Funds Rate     : {dff_val:>+8.2f} %")
            print(f"  CPI interanual (YoY)   : {cpi_yoy_val:>+8.2f} %")
            print(f"  {'─'*36}")
            print(f"  Tipo de interés REAL   : {real_rate:>+8.2f} %")
            print()
            if real_rate > 1.0:
                print("  → Política monetaria MUY RESTRICTIVA (tipo real > 1%)")
            elif real_rate > 0:
                print("  → Política monetaria RESTRICTIVA (tipo real positivo)")
            elif real_rate > -1.0:
                print("  → Política monetaria LIGERAMENTE ACOMODATICIA")
            else:
                print("  → Política monetaria EXPANSIVA / REPRESIÓN FINANCIERA")

    # ── 6. ¿Está invertida la curva de tipos? ─────────────────────────────────
    sep("6. CURVA DE TIPOS — ¿INVERTIDA?")
    print()

    with SessionLocal() as session:
        t10y2y_row = (
            session.query(TimeSeries.timestamp, TimeSeries.value)
            .filter(TimeSeries.indicator_id == "fred_spread_10y2y_us")
            .order_by(TimeSeries.timestamp.desc())
            .first()
        )

    if t10y2y_row:
        spread = t10y2y_row.value
        date_str = t10y2y_row.timestamp.strftime("%Y-%m-%d")
        print(f"  Spread 10y-2y : {spread:>+.3f} %  ({date_str})")
        print()
        if spread < 0:
            print("  [ROJO]   CURVA INVERTIDA — señal histórica de recesión")
            print("           (10y < 2y: mercado anticipa bajadas de tipos)")
        elif spread < 0.25:
            print("  [AMARILLO] Curva casi plana — zona de precaución")
        else:
            print("  [VERDE]  Curva normal (pendiente positiva — expansión)")
    else:
        # Fallback: calcular spread en memoria
        dgs10 = collector._load_indicator_from_db("fred_yield_10y_us")
        dgs2 = collector._load_indicator_from_db("fred_yield_2y_us")
        if not dgs10.empty and not dgs2.empty:
            aligned = pd.concat([dgs10, dgs2], axis=1).dropna()
            spread = aligned.iloc[-1, 0] - aligned.iloc[-1, 1]
            date_str = aligned.index[-1].strftime("%Y-%m-%d")
            print(f"  Spread 10y-2y (calculado) : {spread:>+.3f} %  ({date_str})")
            if spread < 0:
                print("  [ROJO]   CURVA INVERTIDA")
            elif spread < 0.25:
                print("  [AMARILLO] Casi plana")
            else:
                print("  [VERDE]  Normal")
        else:
            print("  → Dato T10Y2Y no disponible. Revisa la descarga.")

    # ── Resumen final ─────────────────────────────────────────────────────────
    sep("RESUMEN DEL COLECTOR")
    status = collector.get_status()
    print()
    print(f"  Fuente             : {status['source'].upper()}")
    print(f"  Estado             : {status['status'].upper()}")
    print(f"  Total registros BD : {status['total_records']:,}")
    print(f"  Series únicas BD   : {status['series_count']}")
    print(f"  Última actualiz.   : {status['last_update']}")
    if status["errors"]:
        print(f"  Errores            : {len(status['errors'])} serie(s) fallaron")
        for err in status["errors"]:
            print(f"    ✗ {err}")
    print()
    sep()
    print("  Test completado. Ejecuta run_full_history() para el histórico completo.")
    print()


if __name__ == "__main__":
    main()
