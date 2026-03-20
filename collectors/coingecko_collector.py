"""
Colector CoinGecko + Alternative.me para datos de criptomonedas.

Fuentes:
  - CoinGecko API v3 (https://api.coingecko.com/api/v3/)
    Plan publico sin key o plan Demo con COINGECKO_API_KEY en .env
  - Alternative.me Fear & Greed Index (https://api.alternative.me/fng/)
    Endpoint publico, sin key

Datos descargados:
  Grupo 1: Precios, market cap y volumen (BTC, ETH, USDT, USDC, BNB, SOL, XRP)
           en USD; ademas BTC y ETH en EUR
  Grupo 2: Snapshot diario del mercado global (total market cap, dominancias,
           volumen, datos DeFi)
  Grupo 3: Fear & Greed Index -- hasta 365 dias historico
  Grupo 4: Top 10 stablecoins -- total market cap y dominancia
  Grupo 5: Halvings de Bitcoin (eventos estaticos en tabla events)

Metricas derivadas:
  - Correlacion BTC-SP500 30 dias (usa datos yfinance ya en SQLite)
  - Correlacion BTC-Oro 30 dias
  - Ratio BTC/Oro
  - Stablecoin Supply Ratio (SSR)

Rate limiting: 2 s entre llamadas, retry 60 s en 429 (max 3 intentos).
Nunca supera 25 llamadas/minuto para mantener margen de seguridad.

Alimenta los modulos: M01 (Estado Global), M05 (Mercados), M16 (Ciclos Crypto)
"""

import logging
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
import requests
from sqlalchemy import func, insert, text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collectors.base_collector import BaseCollector
from database.database import SessionLocal, TimeSeries, Event

# Cargar .env via config (trigger load_dotenv)
try:
    import config as _cfg  # noqa: F401 -- solo para cargar dotenv
except ImportError:
    pass

# Valores que se interpretan como "sin key" (plan publico).
# Para desactivar la key sin borrarla del .env, pon: COINGECKO_API_KEY=null
_NULL_VALUES = frozenset({"", "null", "none", "false", "0", "no", "off"})


def _resolve_api_key() -> str:
    """
    Lee COINGECKO_API_KEY del entorno y devuelve la key activa.
    Devuelve cadena vacia si la variable no esta definida o contiene
    un valor nulo (null, none, false, 0, no, off -- case-insensitive).
    """
    raw = os.getenv("COINGECKO_API_KEY", "").strip()
    if raw.lower() in _NULL_VALUES:
        return ""
    return raw


COINGECKO_API_KEY: str = _resolve_api_key()

logger = logging.getLogger(__name__)


# ── Constantes ────────────────────────────────────────────────────────────────

CG_BASE       = "https://api.coingecko.com/api/v3"
FNG_URL       = "https://api.alternative.me/fng/"
RATE_DELAY    = 2.0   # segundos de espera entre llamadas a la API
MAX_RETRIES   = 3     # max reintentos en error 429
RETRY_WAIT    = 60    # segundos de espera en error 429
TIMEOUT       = 30    # timeout HTTP (s)

CRYPTO_SOURCE  = "coingecko"
ALT_SOURCE     = "alternativeme"
DERIVED_SOURCE = "coingecko_derived"


# ── Catalogo de criptomonedas ─────────────────────────────────────────────────

# (coingecko_id, symbol_corto, nombre_display)
COINS: list[tuple[str, str, str]] = [
    ("bitcoin",     "btc",  "Bitcoin"),
    ("ethereum",    "eth",  "Ethereum"),
    ("tether",      "usdt", "Tether"),
    ("usd-coin",    "usdc", "USD Coin"),
    ("binancecoin", "bnb",  "BNB"),
    ("solana",      "sol",  "Solana"),
    ("ripple",      "xrp",  "XRP"),
]

# Criptos que se descargan tambien en EUR
EUR_COINS: frozenset[str] = frozenset({"bitcoin", "ethereum"})


# ── Halvings de Bitcoin ───────────────────────────────────────────────────────

BITCOIN_HALVINGS: list[dict] = [
    {
        "date":  datetime(2012, 11, 28),
        "title": "Bitcoin Halving 1 - Bloque 210.000",
        "desc":  "Recompensa por bloque: 50 BTC -> 25 BTC (bloque 210.000)",
    },
    {
        "date":  datetime(2016, 7, 9),
        "title": "Bitcoin Halving 2 - Bloque 420.000",
        "desc":  "Recompensa por bloque: 25 BTC -> 12.5 BTC (bloque 420.000)",
    },
    {
        "date":  datetime(2020, 5, 11),
        "title": "Bitcoin Halving 3 - Bloque 630.000",
        "desc":  "Recompensa por bloque: 12.5 BTC -> 6.25 BTC (bloque 630.000)",
    },
    {
        "date":  datetime(2024, 4, 20),
        "title": "Bitcoin Halving 4 - Bloque 840.000",
        "desc":  "Recompensa por bloque: 6.25 BTC -> 3.125 BTC (bloque 840.000)",
    },
    {
        "date":  datetime(2028, 4, 1),
        "title": "Bitcoin Halving 5 estimado - Bloque 1.050.000",
        "desc":  "Recompensa estimada: 3.125 BTC -> 1.5625 BTC (aprox. abril 2028)",
    },
]


# ── Colector principal ────────────────────────────────────────────────────────

class CoinGeckoCollector(BaseCollector):
    """
    Colector de datos crypto usando CoinGecko API v3 y Alternative.me.

    Soporta plan publico (sin key) y plan Demo gratuito (COINGECKO_API_KEY en .env).
    Rate limit: 30 llamadas/minuto. Implementa delay de 2 s entre llamadas y
    retry automatico de 60 s en error 429.

    Uso tipico:
        collector = CoinGeckoCollector()
        collector.run_full_history()   # Primera vez: 365 dias
        collector.run_update()         # Ejecuciones periodicas: 7 dias
    """

    SOURCE = "coingecko"

    def __init__(self) -> None:
        self._errors: list[str] = []
        self._cached_stable_mcap: Optional[float] = None  # cache para SSR

        headers = {
            "Accept":     "application/json",
            "User-Agent": "WorldMonitor/1.0",
        }
        if COINGECKO_API_KEY:
            headers["x-cg-demo-api-key"] = COINGECKO_API_KEY
            logger.info("CoinGeckoCollector: API key Demo configurada.")
        else:
            logger.info("CoinGeckoCollector: Sin API key, usando plan publico.")

        self._session = requests.Session()
        self._session.headers.update(headers)
        logger.info(
            "CoinGeckoCollector inicializado. %d criptos | EUR extra: %s",
            len(COINS), ", ".join(sorted(EUR_COINS)),
        )

    # ── BaseCollector interface ───────────────────────────────────────────────

    def run_full_history(self) -> dict:
        """Descarga los ultimos 365 dias de todos los datos disponibles."""
        self._errors = []
        t0 = time.time()
        logger.info("=" * 64)
        logger.info("CoinGecko >> Inicio historico completo (365 dias)")
        logger.info("=" * 64)

        r_market = self._fetch_market_data(days=365, upsert=False)
        r_global = self._fetch_global_data(upsert=False)
        r_fng    = self._fetch_fear_greed(days=365, upsert=False)
        r_stable = self._fetch_stablecoins_data(upsert=False)
        self._insert_bitcoin_halving_data()
        self._compute_derived_metrics()

        ok      = r_market["ok"] + r_global["ok"] + r_fng["ok"] + r_stable["ok"]
        failed  = r_market["failed"] + r_global["failed"] + r_fng["failed"] + r_stable["failed"]
        records = r_market["records"] + r_global["records"] + r_fng["records"] + r_stable["records"]
        elapsed = time.time() - t0

        logger.info("=" * 64)
        logger.info(
            "CoinGecko >> Completo en %.1fs | OK: %d | Fail: %d | Registros: %d",
            elapsed, ok, failed, records,
        )
        logger.info("=" * 64)
        return {"ok": ok, "failed": failed, "total_records": records, "errors": list(self._errors)}

    def run_update(self) -> dict:
        """Descarga los ultimos 7 dias para mantener datos frescos."""
        self._errors = []
        t0 = time.time()
        logger.info("CoinGecko >> Actualizacion (7 dias)")

        r_market = self._fetch_market_data(days=7, upsert=True)
        r_global = self._fetch_global_data(upsert=True)
        r_fng    = self._fetch_fear_greed(days=30, upsert=True)
        r_stable = self._fetch_stablecoins_data(upsert=True)
        self._compute_derived_metrics()

        ok      = r_market["ok"] + r_global["ok"] + r_fng["ok"] + r_stable["ok"]
        failed  = r_market["failed"] + r_global["failed"] + r_fng["failed"] + r_stable["failed"]
        records = r_market["records"] + r_global["records"] + r_fng["records"] + r_stable["records"]

        logger.info(
            "CoinGecko >> Actualizacion en %.1fs | Nuevos registros: %d",
            time.time() - t0, records,
        )
        return {"ok": ok, "failed": failed, "total_records": records, "errors": list(self._errors)}

    def get_last_update_time(self) -> Optional[datetime]:
        with SessionLocal() as session:
            return session.query(func.max(TimeSeries.created_at)).filter(
                TimeSeries.source.in_([CRYPTO_SOURCE, ALT_SOURCE, DERIVED_SOURCE])
            ).scalar()

    def get_status(self) -> dict:
        with SessionLocal() as session:
            total = session.query(func.count(TimeSeries.id)).filter(
                TimeSeries.source.in_([CRYPTO_SOURCE, ALT_SOURCE, DERIVED_SOURCE])
            ).scalar() or 0

            series_count = session.query(
                func.count(TimeSeries.indicator_id.distinct())
            ).filter(
                TimeSeries.source.in_([CRYPTO_SOURCE, ALT_SOURCE, DERIVED_SOURCE])
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

    def get_current_market_snapshot(self) -> dict:
        """
        Devuelve el estado actual del mercado crypto para el M01 (Estado Global).

        Returns:
            dict con:
                btc_price_usd        : float|None  precio BTC en USD
                btc_price_eur        : float|None  precio BTC en EUR
                eth_price_usd        : float|None  precio ETH en USD
                total_market_cap     : float|None  capitalizacion total (USD)
                btc_dominance        : float|None  dominancia BTC (%)
                fear_greed_value     : int|None    Fear & Greed (0-100)
                fear_greed_label     : str|None    etiqueta textual
                stablecoin_dominance : float|None  dominancia stablecoins (%)
        """
        fg = self._load_latest_value("cg_fear_greed_value")
        return {
            "btc_price_usd":        self._load_latest_value("cg_btc_price_usd"),
            "btc_price_eur":        self._load_latest_value("cg_btc_price_eur"),
            "eth_price_usd":        self._load_latest_value("cg_eth_price_usd"),
            "total_market_cap":     self._load_latest_value("cg_total_market_cap_usd"),
            "btc_dominance":        self._load_latest_value("cg_bitcoin_dominance_pct"),
            "fear_greed_value":     int(fg) if fg is not None else None,
            "fear_greed_label":     self._fng_label(fg) if fg is not None else None,
            "stablecoin_dominance": self._load_latest_value("cg_stablecoin_dominance_pct"),
        }

    @staticmethod
    def _fng_label(value: float) -> str:
        """Devuelve la clasificacion textual del Fear & Greed Index."""
        v = float(value)
        if v <= 24:
            return "Extreme Fear"
        elif v <= 44:
            return "Fear"
        elif v <= 55:
            return "Neutral"
        elif v <= 75:
            return "Greed"
        else:
            return "Extreme Greed"

    # ── Grupo 1: Precios y metricas de mercado ────────────────────────────────

    def _fetch_market_data(self, days: int, upsert: bool) -> dict:
        """
        Descarga market_chart de cada cripto en USD (y EUR para BTC/ETH).
        Por cada cripto guarda: precio, market cap y volumen 24h.
        """
        ok = failed = total = 0

        for coin_id, symbol, name in COINS:
            currencies = ["usd"]
            if coin_id in EUR_COINS:
                currencies.append("eur")

            for currency in currencies:
                url    = f"{CG_BASE}/coins/{coin_id}/market_chart"
                params = {
                    "vs_currency": currency,
                    "days":        days,
                    "interval":    "daily",
                }
                logger.info("CG market_chart [%s/%s] days=%d", symbol, currency, days)
                try:
                    data = self._fetch_with_rate_limit(url, params)
                    if data is None:
                        logger.info("  CG SKIP %s/%s -- sin datos", symbol, currency)
                        ok += 1
                        continue

                    # Precio
                    price_s = self._parse_market_chart(data.get("prices", []))
                    if not price_s.empty:
                        n = self._save_series(
                            f"cg_{symbol}_price_{currency}",
                            price_s, CRYPTO_SOURCE, "GLOBAL", "crypto", currency, upsert,
                        )
                        total += n
                        logger.info(
                            "  CG OK cg_%s_price_%s -- %d nuevos registros",
                            symbol, currency, n,
                        )

                    # Market cap y volumen solo en USD
                    if currency == "usd":
                        mcap_s = self._parse_market_chart(data.get("market_caps", []))
                        if not mcap_s.empty:
                            n = self._save_series(
                                f"cg_{symbol}_market_cap_usd",
                                mcap_s, CRYPTO_SOURCE, "GLOBAL", "crypto", "usd", upsert,
                            )
                            total += n

                        vol_s = self._parse_market_chart(data.get("total_volumes", []))
                        if not vol_s.empty:
                            n = self._save_series(
                                f"cg_{symbol}_volume_24h_usd",
                                vol_s, CRYPTO_SOURCE, "GLOBAL", "crypto", "usd", upsert,
                            )
                            total += n

                    ok += 1

                except Exception as exc:
                    msg = f"market_chart {coin_id}/{currency}: {exc}"
                    logger.error("  CG FAIL %s/%s: %s", coin_id, currency, exc)
                    self._errors.append(msg)
                    failed += 1

        return {"ok": ok, "failed": failed, "records": total}

    # ── Grupo 2: Datos globales del mercado ───────────────────────────────────

    def _fetch_global_data(self, upsert: bool) -> dict:
        """
        Descarga snapshot global del mercado crypto (/global y /global/defi).
        Guarda como punto de datos diario (12:00 UTC del dia actual).
        """
        ok = failed = total = 0
        now_day = datetime.utcnow().replace(hour=12, minute=0, second=0, microsecond=0)

        # -- /global ----------------------------------------------------------
        logger.info("CG >> /global (snapshot global crypto)")
        try:
            data = self._fetch_with_rate_limit(f"{CG_BASE}/global", {})
            if data:
                gdata = data.get("data", {})
                tmcap = gdata.get("total_market_cap", {})
                tvol  = gdata.get("total_volume", {})
                mpct  = gdata.get("market_cap_percentage", {})

                indicators = {
                    "cg_total_market_cap_usd":  (tmcap.get("usd"),     "usd"),
                    "cg_total_volume_24h_usd":  (tvol.get("usd"),      "usd"),
                    "cg_bitcoin_dominance_pct": (mpct.get("btc"),      "pct"),
                    "cg_ethereum_dominance_pct":(mpct.get("eth"),      "pct"),
                }

                for iid, (val, unit) in indicators.items():
                    if val is None:
                        continue
                    s = pd.Series([float(val)], index=pd.DatetimeIndex([now_day]))
                    n = self._save_series(iid, s, CRYPTO_SOURCE, "GLOBAL", "crypto", unit, upsert)
                    total += n

                ok += 1
                logger.info("  CG /global OK -- registros: %d", total)
        except Exception as exc:
            msg = f"global: {exc}"
            logger.error("  CG FAIL /global: %s", exc)
            self._errors.append(msg)
            failed += 1

        # -- /global/decentralized_finance_defi --------------------------------
        logger.info("CG >> /global/defi (snapshot DeFi)")
        try:
            data = self._fetch_with_rate_limit(
                f"{CG_BASE}/global/decentralized_finance_defi", {}
            )
            if data:
                ddata = data.get("data", {})

                def _safe_float(v) -> Optional[float]:
                    try:
                        return float(v) if v not in (None, "", "null") else None
                    except (ValueError, TypeError):
                        return None

                defi_mcap  = _safe_float(ddata.get("defi_market_cap"))
                defi_ratio = _safe_float(ddata.get("defi_to_eth_ratio"))

                if defi_mcap is not None:
                    s = pd.Series([defi_mcap], index=pd.DatetimeIndex([now_day]))
                    n = self._save_series(
                        "cg_defi_market_cap_usd",
                        s, CRYPTO_SOURCE, "GLOBAL", "crypto", "usd", upsert,
                    )
                    total += n

                if defi_ratio is not None:
                    s = pd.Series([defi_ratio], index=pd.DatetimeIndex([now_day]))
                    n = self._save_series(
                        "cg_defi_to_eth_ratio",
                        s, CRYPTO_SOURCE, "GLOBAL", "crypto", "ratio", upsert,
                    )
                    total += n

                ok += 1
                logger.info("  CG /global/defi OK")
        except Exception as exc:
            msg = f"global/defi: {exc}"
            logger.error("  CG FAIL /global/defi: %s", exc)
            self._errors.append(msg)
            failed += 1

        return {"ok": ok, "failed": failed, "records": total}

    # ── Grupo 3: Fear & Greed Index ───────────────────────────────────────────

    def _fetch_fear_greed(self, days: int, upsert: bool) -> dict:
        """
        Descarga el Fear & Greed Index de Alternative.me.
        Fuente: https://api.alternative.me/fng/ (sin key, no tiene rate limit CoinGecko)
        El valor numerico (0-100) se guarda como cg_fear_greed_value.
        La clasificacion textual se deriva del valor numerico via _fng_label().
        """
        ok = failed = total = 0
        limit = min(days, 365)
        logger.info("AlternativeMe >> Fear & Greed Index (%d dias)", limit)

        try:
            resp = self._session.get(
                FNG_URL,
                params={"limit": limit, "format": "json"},
                timeout=TIMEOUT,
            )
            if resp.status_code != 200:
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:100]}")

            entries = resp.json().get("data", [])
            dates: list[datetime] = []
            vals:  list[float]    = []

            for entry in entries:
                try:
                    ts  = datetime.utcfromtimestamp(int(entry["timestamp"]))
                    ts  = ts.replace(hour=0, minute=0, second=0, microsecond=0)
                    val = float(entry["value"])
                    dates.append(ts)
                    vals.append(val)
                except (KeyError, ValueError, TypeError):
                    continue

            if dates:
                series = pd.Series(vals, index=pd.DatetimeIndex(dates), dtype=float)
                series = series[~series.index.duplicated(keep="last")].sort_index()
                n = self._save_series(
                    "cg_fear_greed_value",
                    series, ALT_SOURCE, "GLOBAL", "crypto", "index", upsert,
                )
                total += n
                ok    += 1
                logger.info("  AlternativeMe OK -- %d nuevos registros", n)
            else:
                logger.warning("  AlternativeMe: respuesta sin datos validos")
                ok += 1

        except Exception as exc:
            msg = f"Fear & Greed: {exc}"
            logger.error("  AlternativeMe FAIL: %s", exc)
            self._errors.append(msg)
            failed += 1

        return {"ok": ok, "failed": failed, "records": total}

    # ── Grupo 4: Stablecoins ──────────────────────────────────────────────────

    def _fetch_stablecoins_data(self, upsert: bool) -> dict:
        """
        Descarga el top 10 stablecoins, calcula total market cap y dominancia.
        Endpoint: /coins/markets?category=stablecoins
        """
        ok = failed = total = 0
        now_day = datetime.utcnow().replace(hour=12, minute=0, second=0, microsecond=0)
        logger.info("CG >> Stablecoins top 10")

        params = {
            "vs_currency": "usd",
            "category":    "stablecoins",
            "order":       "market_cap_desc",
            "per_page":    10,
            "page":        1,
            "sparkline":   "false",
        }
        try:
            data = self._fetch_with_rate_limit(f"{CG_BASE}/coins/markets", params)
            if not data:
                ok += 1
                return {"ok": ok, "failed": failed, "records": total}

            total_stable = float(sum(
                coin.get("market_cap") or 0
                for coin in data
                if isinstance(coin.get("market_cap"), (int, float))
            ))

            if total_stable > 0:
                # Cache para SSR
                self._cached_stable_mcap = total_stable

                # Total stablecoin market cap
                s = pd.Series([total_stable], index=pd.DatetimeIndex([now_day]))
                n = self._save_series(
                    "cg_total_stablecoin_mcap_usd",
                    s, CRYPTO_SOURCE, "GLOBAL", "crypto", "usd", upsert,
                )
                total += n

                # Stablecoin dominance (necesita total market cap en BD)
                global_mcap = self._load_latest_value("cg_total_market_cap_usd")
                if global_mcap and global_mcap > 0:
                    dom = (total_stable / global_mcap) * 100.0
                    s = pd.Series([dom], index=pd.DatetimeIndex([now_day]))
                    n = self._save_series(
                        "cg_stablecoin_dominance_pct",
                        s, DERIVED_SOURCE, "GLOBAL", "crypto", "pct", upsert,
                    )
                    total += n

                # Stablecoin volume 24h % del volumen total
                stable_vol = float(sum(
                    coin.get("total_volume") or 0
                    for coin in data
                    if isinstance(coin.get("total_volume"), (int, float))
                ))
                global_vol = self._load_latest_value("cg_total_volume_24h_usd")
                if global_vol and global_vol > 0 and stable_vol > 0:
                    vol_pct = (stable_vol / global_vol) * 100.0
                    s = pd.Series([vol_pct], index=pd.DatetimeIndex([now_day]))
                    n = self._save_series(
                        "cg_stablecoin_volume_pct",
                        s, DERIVED_SOURCE, "GLOBAL", "crypto", "pct", upsert,
                    )
                    total += n

            ok += 1
            logger.info(
                "  CG stablecoins OK -- total mcap: $%.2fB", total_stable / 1e9
            )

        except Exception as exc:
            msg = f"stablecoins: {exc}"
            logger.error("  CG FAIL stablecoins: %s", exc)
            self._errors.append(msg)
            failed += 1

        return {"ok": ok, "failed": failed, "records": total}

    # ── Grupo 5: Halvings de Bitcoin ──────────────────────────────────────────

    def _insert_bitcoin_halving_data(self) -> None:
        """
        Inserta los halvings historicos de Bitcoin en la tabla events.
        Solo inserta si el evento no existe ya (sin duplicados por titulo).
        """
        logger.info("CG >> Insertando halvings de Bitcoin en tabla events...")
        inserted = 0
        with SessionLocal() as session:
            for hv in BITCOIN_HALVINGS:
                exists = session.query(Event).filter(Event.title == hv["title"]).first()
                if exists:
                    logger.debug("  SKIP halving ya existente: %s", hv["title"])
                    continue
                event = Event(
                    date        = hv["date"],
                    title       = hv["title"],
                    description = hv["desc"],
                    category    = "crypto_cycle",
                    region      = "GLOBAL",
                    severity    = "high",
                    source      = "CoinGeckoCollector",
                    is_manual   = False,
                )
                session.add(event)
                inserted += 1
            session.commit()

        logger.info(
            "  Halvings insertados: %d (total definidos: %d)",
            inserted, len(BITCOIN_HALVINGS),
        )

    # ── Metricas derivadas ────────────────────────────────────────────────────

    def _compute_derived_metrics(self) -> None:
        """
        Calcula y persiste metricas derivadas usando datos ya en SQLite:
          1. Correlacion BTC-SP500 (30 dias): cg_btc_sp500_corr_30d
          2. Correlacion BTC-Oro (30 dias):   cg_btc_gold_corr_30d
          3. Ratio BTC/Oro:                   cg_btc_gold_ratio
          4. Stablecoin Supply Ratio (SSR):   cg_ssr

        Los datos de SP500 y Oro vienen del colector Yahoo Finance (yf_sp500_close,
        yf_gc_close). Si esos datos no estan en BD las metricas no se calculan.
        """
        now     = datetime.utcnow()
        now_day = now.replace(hour=12, minute=0, second=0, microsecond=0)
        cutoff  = now - timedelta(days=35)  # 35 dias para ventana 30d con margen

        btc   = self._load_from_db("cg_btc_price_usd", start_date=cutoff)
        sp500 = self._load_from_db("yf_sp500_close",   start_date=cutoff)
        gold  = self._load_from_db("yf_gc_close",      start_date=cutoff)

        # ── Correlacion BTC-SP500 ─────────────────────────────────────────────
        if not btc.empty and not sp500.empty:
            try:
                btc_d   = btc.resample("D").last().dropna()
                sp500_d = sp500.resample("D").last().dropna()
                aligned = pd.concat([btc_d, sp500_d], axis=1).dropna()
                aligned.columns = ["btc", "sp500"]
                if len(aligned) >= 10:
                    corr = aligned["btc"].corr(aligned["sp500"])
                    if pd.notna(corr):
                        s = pd.Series([float(corr)], index=pd.DatetimeIndex([now_day]))
                        n = self._save_series(
                            "cg_btc_sp500_corr_30d",
                            s, DERIVED_SOURCE, "GLOBAL", "crypto", "ratio", upsert=True,
                        )
                        logger.info("  Derived: BTC-SP500 corr = %.3f (%d nuevos)", corr, n)
            except Exception as exc:
                logger.debug("  Error correlacion BTC-SP500: %s", exc)

        # ── Correlacion BTC-Oro ───────────────────────────────────────────────
        if not btc.empty and not gold.empty:
            try:
                btc_d  = btc.resample("D").last().dropna()
                gold_d = gold.resample("D").last().dropna()
                aligned = pd.concat([btc_d, gold_d], axis=1).dropna()
                aligned.columns = ["btc", "gold"]
                if len(aligned) >= 10:
                    corr = aligned["btc"].corr(aligned["gold"])
                    if pd.notna(corr):
                        s = pd.Series([float(corr)], index=pd.DatetimeIndex([now_day]))
                        n = self._save_series(
                            "cg_btc_gold_corr_30d",
                            s, DERIVED_SOURCE, "GLOBAL", "crypto", "ratio", upsert=True,
                        )
                        logger.info("  Derived: BTC-Oro corr = %.3f (%d nuevos)", corr, n)
            except Exception as exc:
                logger.debug("  Error correlacion BTC-Oro: %s", exc)

        # ── Ratio BTC/Oro ─────────────────────────────────────────────────────
        if not btc.empty and not gold.empty:
            try:
                btc_d  = btc.resample("D").last().dropna()
                gold_d = gold.resample("D").last().dropna()
                aligned = pd.concat([btc_d, gold_d], axis=1).dropna()
                aligned.columns = ["btc", "gold"]
                if not aligned.empty:
                    ratio = aligned["btc"] / aligned["gold"]
                    n = self._save_series(
                        "cg_btc_gold_ratio",
                        ratio, DERIVED_SOURCE, "GLOBAL", "crypto", "ratio", upsert=True,
                    )
                    logger.info("  Derived: BTC/Oro ratio -- %d nuevos", n)
            except Exception as exc:
                logger.debug("  Error ratio BTC/Oro: %s", exc)

        # ── Stablecoin Supply Ratio (SSR) ─────────────────────────────────────
        # SSR = precio BTC / (total stablecoin mcap en billones USD)
        # Cuando SSR bajo: mucha liquidez en stablecoins relativa a BTC -> potencial alcista
        if not btc.empty:
            try:
                stable_mcap = (
                    self._cached_stable_mcap
                    or self._load_latest_value("cg_total_stablecoin_mcap_usd")
                )
                if stable_mcap and stable_mcap > 0:
                    btc_price = float(btc.iloc[-1])
                    ssr = btc_price / (stable_mcap / 1e9)
                    s   = pd.Series([ssr], index=pd.DatetimeIndex([now_day]))
                    n   = self._save_series(
                        "cg_ssr",
                        s, DERIVED_SOURCE, "GLOBAL", "crypto", "ratio", upsert=True,
                    )
                    logger.info("  Derived: SSR = %.4f (%d nuevos)", ssr, n)
            except Exception as exc:
                logger.debug("  Error SSR: %s", exc)

    # ── HTTP con gestion de rate limiting ────────────────────────────────────

    def _fetch_with_rate_limit(
        self,
        url:    str,
        params: dict,
    ) -> Optional[dict]:
        """
        Realiza GET con gestion automatica de rate limiting.

        - Espera RATE_DELAY segundos antes de cada llamada.
        - Si recibe 429, espera RETRY_WAIT segundos y reintenta.
        - Maximo MAX_RETRIES intentos. Lanza RuntimeError si se superan.
        - Devuelve None si la respuesta es vacia o 404.
        """
        time.sleep(RATE_DELAY)  # delay preventivo antes de cada llamada

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = self._session.get(url, params=params, timeout=TIMEOUT)
            except requests.RequestException as exc:
                raise RuntimeError(f"Error de red en {url}: {exc}") from exc

            if resp.status_code == 200:
                if not resp.content:
                    return None
                try:
                    return resp.json()
                except Exception as exc:
                    raise RuntimeError(f"Error parseando JSON de {url}: {exc}") from exc

            elif resp.status_code == 429:
                logger.warning(
                    "  CG 429 rate limit (intento %d/%d) -- esperando %ds...",
                    attempt, MAX_RETRIES, RETRY_WAIT,
                )
                time.sleep(RETRY_WAIT)
                # El proximo intento del bucle no duerme RATE_DELAY de nuevo
                # porque el RETRY_WAIT ya es suficiente espera
                continue

            elif resp.status_code == 404:
                logger.warning("  CG 404: %s", url)
                return None

            else:
                raise RuntimeError(
                    f"HTTP {resp.status_code} para {url}: {resp.text[:120]}"
                )

        raise RuntimeError(
            f"Superado maximo de reintentos ({MAX_RETRIES}) para {url}"
        )

    # ── Parsers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_market_chart(data_list: list) -> pd.Series:
        """
        Convierte [[timestamp_ms, value], ...] de CoinGecko en
        pd.Series(float, DatetimeIndex UTC normalizado a medianoche).
        """
        dates: list[datetime] = []
        vals:  list[float]    = []

        for item in data_list:
            try:
                ts_ms = int(item[0])
                val   = float(item[1])
                dt    = datetime.utcfromtimestamp(ts_ms / 1000.0).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                dates.append(dt)
                vals.append(val)
            except (IndexError, TypeError, ValueError):
                continue

        if not dates:
            return pd.Series(dtype=float)

        s = pd.Series(vals, index=pd.DatetimeIndex(dates), dtype=float)
        # Eliminar duplicados de mismo dia (tomar el ultimo valor del dia)
        s = s[~s.index.duplicated(keep="last")]
        return s.sort_index()

    # ── Soporte comun (mismo patron que EuropeCollector) ──────────────────────

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
        Persiste una serie en SQLite. Sin duplicados.

        upsert=False: inserta solo registros mas recientes que MAX(timestamp).
        upsert=True:  DELETE+INSERT desde el timestamp minimo del lote.
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

    def _load_latest_value(self, indicator_id: str) -> Optional[float]:
        """Devuelve el valor mas reciente de un indicador en SQLite, o None."""
        with SessionLocal() as session:
            row = (
                session.query(TimeSeries.value)
                .filter(TimeSeries.indicator_id == indicator_id)
                .order_by(TimeSeries.timestamp.desc())
                .first()
            )
        return float(row.value) if row and row.value is not None else None
