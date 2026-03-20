"""
Script de prueba del colector Yahoo Finance.

Descarga 6 tickers principales + 3 auxiliares para métricas derivadas,
verifica los datos en SQLite e imprime análisis de mercado.

Uso:
    cd "World Monitor"
    python scripts/test_yahoo.py
"""

import logging
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collectors.yahoo_collector import TICKER_CATALOG, YahooCollector
from database.database import SessionLocal, TimeSeries

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Tickers principales del test
TEST_TICKERS = ["^GSPC", "^IBEX", "GC=F", "EURUSD=X", "^VIX", "BTC-USD"]

# Auxiliares necesarios para métricas derivadas (ratio oro/plata, RSP/SPY)
AUX_TICKERS = ["SI=F", "RSP", "SPY"]

# Todos los que se descargan
ALL_TICKERS = TEST_TICKERS + AUX_TICKERS

# Inicio del histórico para el test (5 años — rápido)
TEST_START = "2020-01-01"


def sep(title: str = "", width: int = 62) -> None:
    if title:
        pad = (width - len(title) - 2) // 2
        print(f"\n{'-' * pad} {title} {'-' * (width - pad - len(title) - 2)}")
    else:
        print("-" * width)


def get_latest(collector: YahooCollector, indicator_id: str):
    """Retorna (valor, fecha) más reciente de un indicator_id."""
    with SessionLocal() as session:
        row = (
            session.query(TimeSeries.timestamp, TimeSeries.value)
            .filter(TimeSeries.indicator_id == indicator_id)
            .order_by(TimeSeries.timestamp.desc())
            .first()
        )
    if row:
        return row.value, row.timestamp
    return None, None


def main() -> None:
    print()
    sep("WORLD MONITOR - TEST COLECTOR YAHOO FINANCE")
    print(f"  Fecha/hora  : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Tickers     : {TEST_TICKERS}")
    print(f"  Auxiliares  : {AUX_TICKERS}  (para ratios derivados)")
    print(f"  Periodo     : {TEST_START} -> hoy")

    # -- 1. Inicializar colector -----------------------------------------------
    sep("1. INICIALIZACION")
    collector = YahooCollector()
    print("  OK YahooCollector listo (sin API key requerida)")

    # -- 2. Descarga -----------------------------------------------------------
    sep("2. DESCARGA DE TICKERS")
    result = collector.download_tickers(ALL_TICKERS, start=TEST_START)
    print()
    print(f"  Tickers descargados : {result['ok']}")
    print(f"  Tickers con error   : {result['failed']}")
    print(f"  Registros nuevos    : {result['total_records']:,}")
    if result.get("errors"):
        print(f"  Errores             : {result['errors']}")

    # -- 3. Verificar datos en SQLite ------------------------------------------
    sep("3. VERIFICACIÓN EN SQLITE")
    print()
    print(f"  {'Ticker':<15}  {'indicator_id':<30}  {'Registros':>9}")
    sep()
    with SessionLocal() as session:
        for ticker in TEST_TICKERS:
            cfg = TICKER_CATALOG.get(ticker)
            if cfg is None:
                print(f"  {ticker:<15}  {'(no en catálogo)':<30}  {'—':>9}")
                continue
            close_id = f"{cfg.indicator_id}_close"
            count = (
                session.query(TimeSeries)
                .filter(TimeSeries.indicator_id == close_id)
                .count()
            )
            print(f"  {ticker:<15}  {close_id:<30}  {count:>9,}")

    # -- 4. Últimos 3 valores por serie ----------------------------------------
    sep("4. ÚLTIMOS 3 VALORES POR TICKER")
    with SessionLocal() as session:
        for ticker in TEST_TICKERS:
            cfg = TICKER_CATALOG.get(ticker)
            if cfg is None:
                continue
            close_id = f"{cfg.indicator_id}_close"
            rows = (
                session.query(TimeSeries.timestamp, TimeSeries.value)
                .filter(TimeSeries.indicator_id == close_id)
                .order_by(TimeSeries.timestamp.desc())
                .limit(3)
                .all()
            )
            print(f"\n  {ticker}  —  {cfg.name}  [{cfg.unit}]")
            print(f"  {'Fecha':<14}  {'Valor':>14}")
            print(f"  {'-'*14}  {'-'*14}")
            for ts, val in reversed(rows):
                date_str = ts.strftime("%Y-%m-%d")
                val_str = f"{val:>14.4f}" if val is not None else f"{'N/A':>14}"
                print(f"  {date_str:<14}  {val_str}")

    # -- 5. Métricas derivadas -------------------------------------------------
    sep("5. MÉTRICAS DE MERCADO ACTUALES")
    print()

    # S&P 500 — YTD
    sp500 = collector._load_indicator_from_db("yf_sp500_close")
    if not sp500.empty:
        year_start = pd.Timestamp(f"{datetime.now().year}-01-01")
        before = sp500[sp500.index < year_start]
        after = sp500[sp500.index >= year_start]
        current_price = sp500.iloc[-1]
        current_date = sp500.index[-1].strftime("%Y-%m-%d")
        if not before.empty and not after.empty:
            ytd_base = before.iloc[-1]
            ytd_pct = (current_price / ytd_base - 1) * 100
            print(f"  S&P 500        : {current_price:>10,.2f}  pts  ({current_date})")
            print(f"  S&P 500 YTD    : {ytd_pct:>+10.2f}  %")
        else:
            print(f"  S&P 500        : {current_price:>10,.2f}  pts  ({current_date})")
    else:
        print("  S&P 500        : sin datos")

    # IBEX 35 — YTD
    ibex = collector._load_indicator_from_db("yf_ibex35_close")
    if not ibex.empty:
        year_start = pd.Timestamp(f"{datetime.now().year}-01-01")
        before = ibex[ibex.index < year_start]
        after = ibex[ibex.index >= year_start]
        current_price = ibex.iloc[-1]
        current_date = ibex.index[-1].strftime("%Y-%m-%d")
        if not before.empty and not after.empty:
            ytd_base = before.iloc[-1]
            ytd_pct = (current_price / ytd_base - 1) * 100
            print(f"  IBEX 35        : {current_price:>10,.2f}  pts  ({current_date})")
            print(f"  IBEX 35 YTD    : {ytd_pct:>+10.2f}  %")
        else:
            print(f"  IBEX 35        : {current_price:>10,.2f}  pts  ({current_date})")
    else:
        print("  IBEX 35        : sin datos")

    # Oro
    gold_val, gold_date = get_latest(collector, "yf_gc_close")
    if gold_val:
        print(f"  Oro (GC=F)     : {gold_val:>10,.2f}  USD/oz  ({gold_date.strftime('%Y-%m-%d')})")
    else:
        print("  Oro            : sin datos")

    # EUR/USD
    eurusd_val, eurusd_date = get_latest(collector, "yf_eurusd_close")
    if eurusd_val:
        print(f"  EUR/USD        : {eurusd_val:>10.4f}  ({eurusd_date.strftime('%Y-%m-%d')})")
    else:
        print("  EUR/USD        : sin datos")

    # VIX con interpretación
    vix_val, vix_date = get_latest(collector, "yf_vix_close")
    if vix_val:
        if vix_val < 15:
            interpretation = "CALMA (< 15) — complacencia"
        elif vix_val < 25:
            interpretation = "NORMAL (15-25) — incertidumbre moderada"
        elif vix_val < 35:
            interpretation = "TENSIÓN (25-35) — volatilidad elevada"
        else:
            interpretation = "PÁNICO (> 35) — crisis"
        print(f"  VIX            : {vix_val:>10.2f}  pts  ({vix_date.strftime('%Y-%m-%d')})")
        print(f"  VIX estado     : {interpretation}")
    else:
        print("  VIX            : sin datos")

    # Bitcoin
    btc_val, btc_date = get_latest(collector, "yf_btc_usd_close")
    if btc_val:
        print(f"  Bitcoin        : {btc_val:>10,.2f}  USD  ({btc_date.strftime('%Y-%m-%d')})")
    else:
        print("  Bitcoin        : sin datos")

    # -- 6. Ratio oro/plata ----------------------------------------------------
    sep("6. RATIO ORO/PLATA")
    print()
    gold_s = collector._load_indicator_from_db("yf_gc_close")
    silver_s = collector._load_indicator_from_db("yf_si_close")

    if not gold_s.empty and not silver_s.empty:
        aligned = pd.concat([gold_s, silver_s], axis=1).dropna()
        aligned.columns = ["gold", "silver"]
        if not aligned.empty:
            last = aligned.iloc[-1]
            ratio = last["gold"] / last["silver"]
            ratio_date = aligned.index[-1].strftime("%Y-%m-%d")

            # Percentil histórico del ratio
            all_ratios = aligned["gold"] / aligned["silver"]
            pct = (all_ratios <= ratio).mean() * 100

            print(f"  Oro            : {last['gold']:>10.2f} USD/oz")
            print(f"  Plata          : {last['silver']:>10.2f} USD/oz")
            print(f"  Ratio Oro/Plata: {ratio:>10.2f}  ({ratio_date})")
            print(f"  Percentil hist.: {pct:>10.1f} %  (desde {TEST_START})")
            if ratio > 80:
                print("  -> Ratio muy alto: plata históricamente barata vs oro")
            elif ratio < 50:
                print("  -> Ratio bajo: plata cara vs oro")
            else:
                print("  -> Ratio en zona normal (50-80)")
    else:
        print("  -> Datos insuficientes (¿SI=F descargado?)")

    # -- 7. Ratio RSP/SPY (amplitud de mercado) --------------------------------
    sep("7. AMPLITUD DE MERCADO — RATIO RSP/SPY")
    print()
    rsp_s = collector._load_indicator_from_db("yf_rsp_close")
    spy_s = collector._load_indicator_from_db("yf_spy_close")

    if not rsp_s.empty and not spy_s.empty:
        aligned = pd.concat([rsp_s, spy_s], axis=1).dropna()
        aligned.columns = ["rsp", "spy"]
        if not aligned.empty:
            ratio_series = aligned["rsp"] / aligned["spy"]
            current_ratio = ratio_series.iloc[-1]
            ratio_date = ratio_series.index[-1].strftime("%Y-%m-%d")

            # Tendencia: comparar con hace 20 días
            trend_str = "—"
            if len(ratio_series) > 20:
                ratio_20d = ratio_series.iloc[-21]
                change_20d = (current_ratio / ratio_20d - 1) * 100
                trend_str = f"{change_20d:+.2f}% vs hace 20 días"

            print(f"  RSP (equal-wt) : {aligned['rsp'].iloc[-1]:>10.4f}")
            print(f"  SPY (cap-wt)   : {aligned['spy'].iloc[-1]:>10.4f}")
            print(f"  Ratio RSP/SPY  : {current_ratio:>10.4f}  ({ratio_date})")
            print(f"  Tendencia      : {trend_str}")
            print()

            # Percentil del ratio
            pct = (ratio_series <= current_ratio).mean() * 100
            if pct < 25:
                print("  -> [ALERTA] Amplitud muy estrecha — pocas empresas suben")
                print("     Solo los valores grandes tiran del índice (señal de fragilidad)")
            elif pct < 45:
                print("  -> Amplitud por debajo de la media — mercado algo concentrado")
            elif pct > 75:
                print("  -> Amplitud amplia — mercado con base sólida y participación generalizada")
            else:
                print("  -> Amplitud normal")
    else:
        print("  -> Datos insuficientes (¿RSP y SPY descargados?)")

    # -- Resumen final ---------------------------------------------------------
    sep("RESUMEN DEL COLECTOR")
    status = collector.get_status()
    print()
    print(f"  Fuente             : {status['source'].upper()}")
    print(f"  Estado             : {status['status'].upper()}")
    print(f"  Total registros BD : {status['total_records']:,}")
    print(f"  Series únicas BD   : {status['series_count']}")
    print(f"  Última actualiz.   : {status['last_update']}")
    if status["errors"]:
        print(f"  Errores            : {len(status['errors'])} ticker(s) fallaron")
        for err in status["errors"]:
            print(f"    X {err}")
    print()
    sep()
    print("  Test completado.")
    print("  Para el histórico completo: collector.run_full_history()")
    print()


if __name__ == "__main__":
    main()
