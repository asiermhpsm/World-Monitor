"""
Script de prueba del colector CoinGecko + Alternative.me.

Descarga un subconjunto rapido de datos (30 dias BTC/ETH, snapshot global,
30 dias Fear & Greed), verifica SQLite e imprime un resumen del mercado crypto.

Uso:
    cd "World Monitor"
    python scripts/test_coingecko.py
"""

import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collectors.coingecko_collector import (
    CG_BASE,
    BITCOIN_HALVINGS,
    COINS,
    CRYPTO_SOURCE,
    ALT_SOURCE,
    DERIVED_SOURCE,
    CoinGeckoCollector,
)
from database.database import SessionLocal, TimeSeries, Event

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def sep(title: str = "", width: int = 72) -> None:
    if title:
        pad = max(2, (width - len(title) - 2) // 2)
        print(f"\n{'-' * pad} {title} {'-' * (width - pad - len(title) - 2)}")
    else:
        print("-" * width)


def get_latest(indicator_id: str):
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


def get_value_7d_ago(indicator_id: str):
    """Devuelve el valor mas proximo a hace 7 dias."""
    cutoff = datetime.utcnow() - timedelta(days=7)
    with SessionLocal() as session:
        row = (
            session.query(TimeSeries.value, TimeSeries.timestamp)
            .filter(
                TimeSeries.indicator_id == indicator_id,
                TimeSeries.timestamp <= cutoff,
            )
            .order_by(TimeSeries.timestamp.desc())
            .first()
        )
    if row and row.value is not None:
        return row.value
    return None


def fmt_big(n: float) -> str:
    """Formatea numeros grandes con sufijos T/B/M."""
    if n >= 1e12:
        return f"${n / 1e12:.2f}T"
    elif n >= 1e9:
        return f"${n / 1e9:.2f}B"
    elif n >= 1e6:
        return f"${n / 1e6:.2f}M"
    return f"${n:,.0f}"


# ── Script principal ──────────────────────────────────────────────────────────

def main() -> None:
    print()
    sep("WORLD MONITOR - TEST COLECTOR COINGECKO + ALTERNATIVE.ME")
    print("  Prueba rapida: BTC + ETH (30 dias), snapshot global, F&G (30 dias)")
    print()

    collector = CoinGeckoCollector()
    print("  OK CoinGeckoCollector listo")

    # ── 1. Descarga rapida: BTC y ETH (30 dias, USD y EUR) ───────────────────
    sep("1. DESCARGA MARKET CHART - BTC y ETH (30 dias)")

    quick_coins = [
        ("bitcoin",  "btc"),
        ("ethereum", "eth"),
    ]
    total_market = 0

    for coin_id, symbol in quick_coins:
        for currency in ["usd", "eur"]:
            url    = f"{CG_BASE}/coins/{coin_id}/market_chart"
            params = {"vs_currency": currency, "days": 30, "interval": "daily"}
            logger.info("Descargando %s/%s...", symbol, currency)
            try:
                data = collector._fetch_with_rate_limit(url, params)
                if data is None:
                    print(f"  SKIP {symbol}/{currency} -- sin datos")
                    continue

                # Precio
                price_s = collector._parse_market_chart(data.get("prices", []))
                if not price_s.empty:
                    n = collector._save_series(
                        f"cg_{symbol}_price_{currency}",
                        price_s, CRYPTO_SOURCE, "GLOBAL", "crypto", currency, upsert=False,
                    )
                    total_market += n
                    logger.info("  OK cg_%s_price_%s -- %d nuevos registros", symbol, currency, n)

                # Market cap y volumen solo en USD
                if currency == "usd":
                    mcap_s = collector._parse_market_chart(data.get("market_caps", []))
                    if not mcap_s.empty:
                        n = collector._save_series(
                            f"cg_{symbol}_market_cap_usd",
                            mcap_s, CRYPTO_SOURCE, "GLOBAL", "crypto", "usd", upsert=False,
                        )
                        total_market += n

                    vol_s = collector._parse_market_chart(data.get("total_volumes", []))
                    if not vol_s.empty:
                        n = collector._save_series(
                            f"cg_{symbol}_volume_24h_usd",
                            vol_s, CRYPTO_SOURCE, "GLOBAL", "crypto", "usd", upsert=False,
                        )
                        total_market += n

            except Exception as exc:
                print(f"  FAIL {symbol}/{currency}: {exc}")

    print(f"\n  Market chart OK -- registros nuevos: {total_market:,}")

    # ── 2. Descarga datos globales del mercado ────────────────────────────────
    sep("2. DESCARGA DATOS GLOBALES (snapshot actual)")

    r_global = collector._fetch_global_data(upsert=False)
    print(f"  Global OK: {r_global['ok']}  Fail: {r_global['failed']}  "
          f"Registros: {r_global['records']:,}")

    # ── 3. Descarga Fear & Greed (30 dias) ────────────────────────────────────
    sep("3. DESCARGA FEAR & GREED INDEX (30 dias)")

    r_fng = collector._fetch_fear_greed(days=30, upsert=False)
    print(f"  F&G OK: {r_fng['ok']}  Fail: {r_fng['failed']}  "
          f"Registros: {r_fng['records']:,}")

    # ── 4. Descarga stablecoins ───────────────────────────────────────────────
    sep("4. DESCARGA STABLECOINS TOP 10")

    r_stable = collector._fetch_stablecoins_data(upsert=False)
    print(f"  Stablecoins OK: {r_stable['ok']}  Fail: {r_stable['failed']}  "
          f"Registros: {r_stable['records']:,}")

    # ── 5. Halvings de Bitcoin ────────────────────────────────────────────────
    sep("5. HALVINGS DE BITCOIN")

    collector._insert_bitcoin_halving_data()

    with SessionLocal() as session:
        halvings_in_db = session.query(Event).filter(
            Event.category == "crypto_cycle"
        ).order_by(Event.date).all()

    print(f"\n  Halvings en tabla events: {len(halvings_in_db)}")
    for hv in halvings_in_db:
        fecha = hv.date.strftime("%Y-%m-%d")
        estimado = " (ESTIMADO)" if "estimado" in hv.title.lower() else ""
        print(f"  {fecha}  {hv.title}{estimado}")

    # ── 6. Metricas derivadas ─────────────────────────────────────────────────
    sep("6. METRICAS DERIVADAS (correlaciones, ratios, SSR)")

    collector._compute_derived_metrics()
    print("  Metricas derivadas calculadas.")

    # ── 7. Verificacion SQLite ────────────────────────────────────────────────
    sep("7. VERIFICACION EN SQLITE")
    print()

    check_ids = [
        "cg_btc_price_usd",
        "cg_btc_price_eur",
        "cg_eth_price_usd",
        "cg_eth_price_eur",
        "cg_btc_market_cap_usd",
        "cg_btc_volume_24h_usd",
        "cg_total_market_cap_usd",
        "cg_bitcoin_dominance_pct",
        "cg_ethereum_dominance_pct",
        "cg_defi_market_cap_usd",
        "cg_defi_to_eth_ratio",
        "cg_fear_greed_value",
        "cg_total_stablecoin_mcap_usd",
        "cg_stablecoin_dominance_pct",
        "cg_btc_sp500_corr_30d",
        "cg_btc_gold_corr_30d",
        "cg_btc_gold_ratio",
        "cg_ssr",
    ]

    print(f"  {'indicator_id':<35}  {'Registros':>9}  {'Ultimo dato':>12}")
    sep()
    for iid in check_ids:
        cnt      = count_records(iid)
        _, ts    = get_latest(iid)
        ts_str   = ts.strftime("%Y-%m-%d") if ts else "N/A"
        ok_mark  = "OK" if cnt > 0 else "SIN DATOS"
        print(f"  {iid:<35}  {cnt:>9,}  {ts_str:>12}  {ok_mark}")

    # ── 8. Resumen del mercado crypto ─────────────────────────────────────────
    sep("8. ESTADO ACTUAL DEL MERCADO CRYPTO")
    print()

    snapshot = collector.get_current_market_snapshot()

    # Precio BTC (USD y EUR)
    btc_usd = snapshot.get("btc_price_usd")
    btc_eur = snapshot.get("btc_price_eur")
    if btc_usd is not None:
        eur_str = f"  |  EUR: {btc_eur:,.0f}" if btc_eur else ""
        print(f"  Bitcoin (BTC)         : ${btc_usd:,.0f}{eur_str}")
    else:
        print("  Bitcoin (BTC)         : sin datos")

    # Precio ETH
    eth_usd = snapshot.get("eth_price_usd")
    _, eth_ts = get_latest("cg_eth_price_eur")
    eth_eur_val, _ = get_latest("cg_eth_price_eur")
    if eth_usd is not None:
        eur_str = f"  |  EUR: {eth_eur_val:,.0f}" if eth_eur_val else ""
        print(f"  Ethereum (ETH)        : ${eth_usd:,.0f}{eur_str}")
    else:
        print("  Ethereum (ETH)        : sin datos")

    print()

    # Total market cap
    total_mcap = snapshot.get("total_market_cap")
    if total_mcap is not None:
        print(f"  Total crypto market cap : {fmt_big(total_mcap)}")
    else:
        print("  Total crypto market cap : sin datos")

    # Dominancia BTC con interpretacion
    btc_dom = snapshot.get("btc_dominance")
    if btc_dom is not None:
        if btc_dom >= 60:
            dom_interp = "mercado dominado por BTC -- modo defensivo"
        elif btc_dom >= 40:
            dom_interp = "equilibrado -- BTC y altcoins en balance"
        else:
            dom_interp = "altcoin season -- capital fluyendo a altcoins"
        print(f"  Dominancia BTC          : {btc_dom:.1f}%  ({dom_interp})")
    else:
        print("  Dominancia BTC          : sin datos")

    # Dominancia ETH
    eth_dom, _ = get_latest("cg_ethereum_dominance_pct")
    if eth_dom is not None:
        print(f"  Dominancia ETH          : {eth_dom:.1f}%")

    print()

    # Fear & Greed
    fg_val = snapshot.get("fear_greed_value")
    fg_lbl = snapshot.get("fear_greed_label") or "N/A"
    if fg_val is not None:
        # Barra visual simple
        bar_len = int(fg_val / 5)
        bar     = "#" * bar_len + "." * (20 - bar_len)
        if fg_val <= 24:
            interp = "mercado con miedo extremo, oportunidad historica de compra"
        elif fg_val <= 44:
            interp = "predomina el miedo, posible zona de acumulacion"
        elif fg_val <= 55:
            interp = "mercado neutral, sin sesgo claro"
        elif fg_val <= 75:
            interp = "euforia moderada, atencion a correcciones"
        else:
            interp = "euforia extrema, alta probabilidad de correccion"
        print(f"  Fear & Greed Index      : {fg_val}  [{fg_lbl}]")
        print(f"  [{bar}] 0 -- 100")
        print(f"  Interpretacion          : {interp}")
    else:
        print("  Fear & Greed Index      : sin datos")

    print()

    # Total stablecoin market cap con tendencia
    stable_mcap, stable_ts = get_latest("cg_total_stablecoin_mcap_usd")
    stable_7d = get_value_7d_ago("cg_total_stablecoin_mcap_usd")
    if stable_mcap is not None:
        trend_str = ""
        if stable_7d and stable_7d > 0:
            delta = ((stable_mcap - stable_7d) / stable_7d) * 100
            if delta > 0.5:
                trend_str = f"  subiendo {delta:+.1f}% vs hace 7 dias -- mas liquidez lista"
            elif delta < -0.5:
                trend_str = f"  bajando {delta:+.1f}% vs hace 7 dias -- capital saliendo"
            else:
                trend_str = "  estable vs hace 7 dias"
        print(f"  Stablecoin market cap   : {fmt_big(stable_mcap)}{trend_str}")
    else:
        print("  Stablecoin market cap   : sin datos")

    stab_dom = snapshot.get("stablecoin_dominance")
    if stab_dom is not None:
        print(f"  Stablecoin dominance    : {stab_dom:.2f}%")

    print()

    # Correlaciones
    btc_sp500_corr, _ = get_latest("cg_btc_sp500_corr_30d")
    if btc_sp500_corr is not None:
        if btc_sp500_corr >= 0.7:
            corr_interp = "BTC se comporta como activo de riesgo (correlacion alta con RV)"
        elif btc_sp500_corr >= 0.3:
            corr_interp = "correlacion moderada -- BTC parcialmente desacoplado"
        elif btc_sp500_corr >= 0:
            corr_interp = "correlacion baja -- BTC independiente de la renta variable"
        else:
            corr_interp = "correlacion negativa -- BTC actua como refugio o es independiente"
        print(f"  Corr BTC-SP500 (30d)    : {btc_sp500_corr:.3f}  ({corr_interp})")
    else:
        print("  Corr BTC-SP500 (30d)    : sin datos (necesita yfinance ejecutado)")

    btc_gold_corr, _ = get_latest("cg_btc_gold_corr_30d")
    if btc_gold_corr is not None:
        if btc_gold_corr >= 0.6:
            gold_interp = "BTC actua como 'oro digital' (alta correlacion con XAU)"
        elif btc_gold_corr >= 0.3:
            gold_interp = "correlacion parcial con oro -- comportamiento mixto"
        else:
            gold_interp = "BTC desacoplado del oro -- drivers independientes"
        print(f"  Corr BTC-Oro (30d)      : {btc_gold_corr:.3f}  ({gold_interp})")
    else:
        print("  Corr BTC-Oro (30d)      : sin datos (necesita yfinance ejecutado)")

    btc_gold_ratio, _ = get_latest("cg_btc_gold_ratio")
    if btc_gold_ratio is not None:
        print(f"  Ratio BTC/Oro           : {btc_gold_ratio:.2f}x  "
              f"(1 BTC = {btc_gold_ratio:.1f} onzas de oro)")

    print()

    # SSR con interpretacion historica
    ssr, _ = get_latest("cg_ssr")
    if ssr is not None:
        # Rangos historicos aproximados del SSR
        # SSR < 3: zona alcista (mucha liquidez en stablecoins)
        # SSR 3-6: zona neutra
        # SSR > 6: zona de sobrecompra (poca liquidez relativa a BTC)
        if ssr < 3:
            ssr_interp = "ZONA ALCISTA -- gran liquidez en stablecoins relativa a BTC"
        elif ssr < 6:
            ssr_interp = "zona neutra"
        else:
            ssr_interp = "ZONA DE SOBRECOMPRA -- poca liquidez relativa al precio de BTC"
        print(f"  Stablecoin Supply Ratio : {ssr:.4f}  ({ssr_interp})")
        print(f"  Referencia historica    : SSR < 3 = potencial alcista / > 6 = sobrecompra")
    else:
        print("  Stablecoin Supply Ratio : sin datos (necesita stablecoin mcap)")

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
    print("  Para historico completo (365 dias): collector.run_full_history()")
    print("  Para actualizacion periodica:       collector.run_update()")
    print()


if __name__ == "__main__":
    main()
