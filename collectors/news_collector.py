"""
Colector de noticias financieras y datos geopoliticos.

Fuentes:
  - NewsAPI (https://newsapi.org/v2/everything)
    Plan gratuito: 100 peticiones/dia — se para en 90 para dejar margen.
    Counter persistido en: data/newsapi_requests.json
  - FRED API: GPR (Geopolitical Risk Index) — 7 series desde 1985/1900
    Reutiliza FRED_API_KEY del .env, igual que FREDCollector.
  - GDELT Project (sin API key): tono global de noticias mundiales.

Datos descargados:
  Grupo 1: Articulos de noticias clasificados por categoria y region
           con impact_score calculado por keywords (0.0 a 1.0)
  Grupo 2: GPR Index global + 6 paises (GPRC, GPRH, GPRC_USA/CHN/RUS/IRN/DEU)
           guardados en time_series con source='FRED_GPR'
  Grupo 3: Tono global GDELT (proxy de tension geopolitica en tiempo real)
           guardado en time_series con source='GDELT'

Modo degradado: si NEWS_API_KEY no esta configurada, descarga solo GPR y GDELT.

Alimenta los modulos: M01 (Estado Global), M10 (Geopolitica)
"""

import json
import logging
import re
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import requests
from sqlalchemy import func, insert
from sqlalchemy.exc import IntegrityError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collectors.base_collector import BaseCollector
from database.database import (
    GeopoliticalEvent,
    NewsArticle,
    SessionLocal,
    TimeSeries,
)

try:
    import config as _cfg  # noqa: F401 — solo para ejecutar load_dotenv
    from config import BASE_DIR, FRED_API_KEY, NEWS_API_KEY
except ImportError:
    import os
    FRED_API_KEY = os.getenv("FRED_API_KEY", "")
    NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")
    BASE_DIR = Path(__file__).resolve().parent.parent

logger = logging.getLogger(__name__)


# ── Constantes ────────────────────────────────────────────────────────────────

NEWS_SOURCE  = "newsapi"
GPR_SOURCE   = "FRED_GPR"
GDELT_SOURCE = "GDELT"

NEWSAPI_BASE  = "https://newsapi.org/v2/everything"
GDELT_URL     = (
    "http://api.gdeltproject.org/api/v2/summary/summary"
    "?d=web&t=summary&a=tonechart&n=global"
)

TIMEOUT               = 30   # segundos timeout HTTP
NEWSAPI_DAILY_LIMIT   = 90   # maximo de peticiones al dia (100 - 10 de margen)
HISTORY_START         = "2000-01-01"

# Valores que se interpretan como "sin key"
_NULL_VALUES = frozenset({"", "null", "none", "false", "0", "no", "off",
                           "your_news_api_key_here"})


# ── GPR: series de FRED ───────────────────────────────────────────────────────

# Fuente GPR: Caldara & Iacoviello (Federal Reserve Board)
# URL del fichero Excel con todos los datos GPR mensuales desde 1985/1900
GPR_DATA_URL = "https://www.matteoiacoviello.com/gpr_files/data_gpr_export.xls"

# Mapeo: columna del Excel -> metadatos del indicador en BD
# El fichero contiene GPR global (desde 1985), GPRH historico (desde 1900),
# y series por pais (GPRC_USA, GPRC_CHN, etc.) — NO incluye Iran (GPRC_IRN)
GPR_SERIES: dict[str, dict] = {
    "GPR":      {"indicator_id": "fred_gpr_global",  "name": "GPR Index Global (mensual, 1985+)", "region": "GLOBAL"},
    "GPRH":     {"indicator_id": "fred_gprh_global", "name": "GPR Historico (mensual, 1900+)",   "region": "GLOBAL"},
    "GPRC_USA": {"indicator_id": "fred_gpr_us",      "name": "GPR EE.UU.",                       "region": "US"},
    "GPRC_CHN": {"indicator_id": "fred_gpr_cn",      "name": "GPR China",                        "region": "CN"},
    "GPRC_RUS": {"indicator_id": "fred_gpr_ru",      "name": "GPR Rusia",                        "region": "RU"},
    "GPRC_DEU": {"indicator_id": "fred_gpr_de",      "name": "GPR Alemania",                     "region": "DE"},
    "GPRC_ISR": {"indicator_id": "fred_gpr_il",      "name": "GPR Israel (proxy Oriente Medio)", "region": "IL"},
}

# Zonas semaforo del GPR global
GPR_ZONES = [
    (0,   100, "normal",    "VERDE",    "Tension geopolitica normal"),
    (100, 150, "elevated",  "AMARILLO", "Tension elevada"),
    (150, 200, "high",      "NARANJA",  "Tension alta"),
    (200, 9999,"very_high", "ROJO",     "Tension muy alta (comparable a grandes crisis)"),
]

# Picos historicos del GPR para contexto
GPR_HISTORICAL_PEAKS = {
    "Guerra del Golfo 1990": 250,
    "11-S 2001":             450,
    "Iraq 2003":             200,
    "COVID 2020":            170,
    "Ucrania 2022":          230,
}


# ── Keywords y clasificacion ──────────────────────────────────────────────────

CRITICAL_KEYWORDS: list[str] = [
    "crisis", "crash", "collapse", "default", "bankruptcy", "contagion",
    "panic", "meltdown", "hyperinflation", "bank run", "systemic risk",
    "war", "invasion", "nuclear", "sanctions", "embargo",
    "recession confirmed", "depression",
]

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "central_banks": [
        "Federal Reserve", "Fed", "ECB", "Bank of England", "interest rate",
        "rate hike", "rate cut", "quantitative easing", "QE", "QT",
        "inflation target", "monetary policy", "Jerome Powell",
        "Christine Lagarde", "pivot",
    ],
    "markets": [
        "stock market", "S&P 500", "Wall Street", "bear market", "bull market",
        "correction", "volatility", "VIX", "yield curve", "bond yield",
        "spread", "earnings", "IPO", "short squeeze",
    ],
    "macro": [
        "GDP", "inflation", "CPI", "unemployment", "recession", "stagflation",
        "fiscal deficit", "debt ceiling", "credit rating", "downgrade",
        "IMF", "World Bank", "G7", "G20",
    ],
    "geopolitics": [
        "NATO", "China", "Russia", "Ukraine", "Iran", "Taiwan", "Middle East",
        "OPEC", "trade war", "tariffs", "sanctions", "geopolitical",
        "conflict", "tension", "military",
    ],
    "energy": [
        "oil price", "crude oil", "Brent", "OPEC", "natural gas", "energy crisis",
        "pipeline", "Strait of Hormuz", "LNG", "renewable energy", "energy transition",
    ],
    "crypto": [
        "Bitcoin", "Ethereum", "cryptocurrency", "crypto", "blockchain",
        "SEC", "regulation", "stablecoin", "DeFi", "exchange", "hack",
    ],
}

# Keywords de region (todas las comparaciones son case-insensitive)
REGION_KEYWORDS: dict[str, list[str]] = {
    "US": [
        "united states", "federal reserve", "fed", "wall street", "washington",
        "treasury", "congress", "s&p 500", "nasdaq", "dow jones",
        "american", "u.s.", "us economy",
    ],
    "EU": [
        "ecb", "europe", "eurozone", "european union", "brussels", "germany",
        "france", "spain", "italy", "euro ", "european central bank",
    ],
    "China": [
        "china", "beijing", "shanghai", "pboc", "hong kong", "chinese",
        "yuan", "renminbi",
    ],
    "Japan": [
        "japan", "bank of japan", "tokyo", "nikkei", "yen", "japanese",
        "boj",
    ],
    "Middle_East": [
        "middle east", "iran", "israel", "saudi arabia", "opec", "gulf",
        "riyadh", "tehran", "dubai",
    ],
    "Russia_Ukraine": [
        "russia", "ukraine", "moscow", "kremlin", "kyiv", "ukrainian",
        "russian",
    ],
    "Emerging_Markets": [
        "emerging markets", " em ", "developing countries", "brics",
    ],
}


# ── Queries de NewsAPI ────────────────────────────────────────────────────────

NEWSAPI_QUERIES: list[dict] = [
    {
        "q": 'Federal Reserve OR ECB OR "Bank of England" OR "interest rate" OR "monetary policy"',
        "category": "central_banks",
        "default_region": None,
    },
    {
        "q": '"financial crisis" OR "bank collapse" OR "credit crisis" OR "systemic risk" OR contagion',
        "category": "markets",
        "default_region": None,
    },
    {
        "q": '"stock market" OR "bond market" OR "yield curve" OR recession OR "bear market"',
        "category": "markets",
        "default_region": None,
    },
    {
        "q": 'geopolitical OR sanctions OR "trade war" OR tariffs OR military OR conflict',
        "category": "geopolitics",
        "default_region": None,
    },
    {
        "q": '"oil price" OR OPEC OR "natural gas" OR "energy crisis" OR commodity',
        "category": "energy",
        "default_region": None,
    },
    {
        "q": '"China economy" OR PBOC OR "Chinese yuan" OR "Taiwan Strait" OR "emerging markets"',
        "category": "macro",
        "default_region": "China",
    },
    {
        "q": 'inflation OR CPI OR GDP OR unemployment OR "fiscal deficit" OR IMF',
        "category": "macro",
        "default_region": None,
    },
    {
        "q": 'Bitcoin OR Ethereum OR cryptocurrency OR "crypto market" OR stablecoin',
        "category": "crypto",
        "default_region": "Global",
    },
]


# ── Colector ──────────────────────────────────────────────────────────────────

class NewsCollector(BaseCollector):
    """
    Colector de noticias financieras y datos geopoliticos.

    - NewsAPI: articulos clasificados con impact_score por keywords
    - FRED: GPR (Geopolitical Risk Index) en 7 variantes geograficas
    - GDELT: tono global de noticias mundiales

    Modo degradado: si NEWS_API_KEY no esta configurada, solo descarga GPR y GDELT.

    Uso tipico:
        collector = NewsCollector()
        collector.run_full_history()   # Primera vez: 30 dias + GPR historico
        collector.run_update()         # Ejecuciones horarias automaticas
    """

    SOURCE = "newsapi"

    def __init__(self) -> None:
        self._errors: list[str] = []

        # ── NewsAPI ──────────────────────────────────────────────────────────
        raw_news_key = NEWS_API_KEY.strip() if NEWS_API_KEY else ""
        if raw_news_key.lower() in _NULL_VALUES:
            self._newsapi_enabled = False
            logger.warning(
                "NewsCollector: NEWS_API_KEY no configurada. "
                "Modo degradado: solo GPR (FRED) y GDELT."
            )
        else:
            self._newsapi_key = raw_news_key
            self._newsapi_enabled = True

        # ── FRED para GPR ────────────────────────────────────────────────────
        raw_fred_key = FRED_API_KEY.strip() if FRED_API_KEY else ""
        if raw_fred_key and raw_fred_key.lower() not in _NULL_VALUES:
            try:
                from fredapi import Fred
                self._fred = Fred(api_key=raw_fred_key)
                self._fred_enabled = True
            except ImportError:
                self._fred_enabled = False
                logger.warning("NewsCollector: fredapi no instalado. GPR no disponible.")
        else:
            self._fred_enabled = False
            logger.warning("NewsCollector: FRED_API_KEY no configurada. GPR no disponible.")

        # ── Session HTTP ─────────────────────────────────────────────────────
        self._session = requests.Session()
        self._session.headers.update({
            "Accept": "application/json",
            "User-Agent": "WorldMonitor/1.0",
        })

        # ── Directorio y fichero contador de peticiones ──────────────────────
        self._data_dir = BASE_DIR / "data"
        self._data_dir.mkdir(exist_ok=True)
        self._counter_file = self._data_dir / "newsapi_requests.json"

        logger.info(
            "NewsCollector inicializado. NewsAPI: %s | FRED/GPR: %s",
            "ACTIVO" if self._newsapi_enabled else "DESHABILITADO",
            "ACTIVO" if self._fred_enabled else "DESHABILITADO",
        )

    # ── BaseCollector interface ───────────────────────────────────────────────

    def run_full_history(self) -> dict:
        """
        Descarga el maximo historico disponible:
          - NewsAPI: ultimos 30 dias (limite plan gratuito)
          - GPR FRED: desde HISTORY_START (2000 para GPRC, desde 1900 para GPRH)
          - GDELT: tono global actual

        Returns:
            dict con ok, failed, total_records, errors
        """
        self._errors = []
        t0 = time.time()
        logger.info("=" * 64)
        logger.info("NewsCollector >> Inicio historico completo")
        logger.info("=" * 64)

        ok = failed = total_records = 0

        # ── 1. NewsAPI: ultimos 30 dias (todas las queries) ──────────────────
        if self._newsapi_enabled:
            logger.info("NewsCollector >> Descargando noticias (ultimos 30 dias)...")
            from_date = (datetime.utcnow() - timedelta(days=29)).strftime("%Y-%m-%d")
            for q_cfg in NEWSAPI_QUERIES:
                if self._get_request_count() >= NEWSAPI_DAILY_LIMIT:
                    logger.warning(
                        "NewsCollector >> Limite diario (%d peticiones). "
                        "Saltando queries restantes.", NEWSAPI_DAILY_LIMIT,
                    )
                    break
                result = self._fetch_newsapi(
                    query=q_cfg["q"],
                    category=q_cfg["category"],
                    default_region=q_cfg.get("default_region"),
                    from_date=from_date,
                )
                ok += result["new"]
                total_records += result["new"]
                logger.info(
                    "  Query '%.40s...': %d nuevos, %d duplicados",
                    q_cfg["q"], result["new"], result["duplicates"],
                )
                time.sleep(1)
        else:
            logger.info("NewsCollector >> NewsAPI deshabilitado, saltando noticias.")

        # ── 2. GPR desde FRED ────────────────────────────────────────────────
        if self._fred_enabled:
            logger.info("NewsCollector >> Descargando GPR historico (FRED)...")
            gpr = self._fetch_gpr_index(start=HISTORY_START)
            ok += gpr["ok"]
            failed += gpr["failed"]
            total_records += gpr["records"]
        else:
            logger.info("NewsCollector >> FRED no disponible, saltando GPR.")

        # ── 3. GDELT ─────────────────────────────────────────────────────────
        gdelt = self._fetch_gdelt_tensions()
        if gdelt.get("ok"):
            total_records += gdelt.get("records", 0)
        else:
            logger.warning("NewsCollector >> GDELT no disponible: %s", gdelt.get("error", ""))

        elapsed = time.time() - t0
        logger.info("=" * 64)
        logger.info(
            "NewsCollector >> Historico completo en %.1fs | Registros: %d | Errores: %d",
            elapsed, total_records, failed,
        )
        logger.info("=" * 64)
        return {"ok": ok, "failed": failed, "total_records": total_records, "errors": list(self._errors)}

    def run_update(self) -> dict:
        """
        Actualizacion periodica (cada hora):
          - NewsAPI: ultimas 24 horas (max 8 queries respetando limite diario)
          - GPR FRED: ultimos 60 dias (captura revisiones retroactivas)
          - GDELT: tono global actual
          - Limpieza automatica: borra articulos con > 90 dias de antiguedad
          - Auto-genera eventos geopoliticos desde articulos de alto impacto

        Returns:
            dict con ok, failed, total_records, errors
        """
        self._errors = []
        t0 = time.time()
        logger.info("NewsCollector >> Actualizacion periodica...")

        ok = failed = total_records = 0

        # ── 1. NewsAPI: ultimas 25 horas (un poco de buffer) ─────────────────
        if self._newsapi_enabled:
            from_date = (datetime.utcnow() - timedelta(hours=25)).strftime("%Y-%m-%dT%H:%M:%S")
            for q_cfg in NEWSAPI_QUERIES:
                if self._get_request_count() >= NEWSAPI_DAILY_LIMIT:
                    logger.warning(
                        "NewsCollector >> Limite diario de NewsAPI (%d). "
                        "Saltando queries restantes.", NEWSAPI_DAILY_LIMIT,
                    )
                    break
                result = self._fetch_newsapi(
                    query=q_cfg["q"],
                    category=q_cfg["category"],
                    default_region=q_cfg.get("default_region"),
                    from_date=from_date,
                )
                ok += result["new"]
                total_records += result["new"]
                logger.info(
                    "  Query '%.40s...': %d nuevos, %d duplicados",
                    q_cfg["q"], result["new"], result["duplicates"],
                )
                time.sleep(1)

        # ── 2. GPR FRED: ultimos 60 dias ─────────────────────────────────────
        if self._fred_enabled:
            gpr_start = (datetime.utcnow() - timedelta(days=60)).strftime("%Y-%m-%d")
            gpr = self._fetch_gpr_index(start=gpr_start)
            ok += gpr["ok"]
            failed += gpr["failed"]
            total_records += gpr["records"]

        # ── 3. GDELT ─────────────────────────────────────────────────────────
        gdelt = self._fetch_gdelt_tensions()
        if gdelt.get("ok"):
            total_records += gdelt.get("records", 0)

        # ── 4. Auto-generar eventos geopoliticos ──────────────────────────────
        events_generated = self._auto_generate_geopolitical_events()
        logger.info("NewsCollector >> Eventos geopoliticos auto-generados: %d", events_generated)

        # ── 5. Limpiar articulos antiguos (> 90 dias) ─────────────────────────
        deleted = self._cleanup_old_articles()
        if deleted:
            logger.info("NewsCollector >> Articulos eliminados (>90 dias): %d", deleted)

        elapsed = time.time() - t0
        logger.info(
            "NewsCollector >> Actualizacion en %.1fs | Nuevos: %d",
            elapsed, total_records,
        )
        return {"ok": ok, "failed": failed, "total_records": total_records, "errors": list(self._errors)}

    def get_last_update_time(self) -> Optional[datetime]:
        """Retorna el datetime UTC de la ultima actualizacion exitosa."""
        with SessionLocal() as session:
            last_article = session.query(func.max(NewsArticle.created_at)).scalar()
            last_gpr = session.query(func.max(TimeSeries.created_at)).filter(
                TimeSeries.source == GPR_SOURCE
            ).scalar()

        candidates = [t for t in [last_article, last_gpr] if t is not None]
        return max(candidates) if candidates else None

    def get_status(self) -> dict:
        """Retorna el estado completo del colector para monitorizacion."""
        with SessionLocal() as session:
            article_count = session.query(func.count(NewsArticle.id)).scalar() or 0
            event_count = session.query(func.count(GeopoliticalEvent.id)).scalar() or 0
            gpr_count = session.query(func.count(TimeSeries.id)).filter(
                TimeSeries.source == GPR_SOURCE
            ).scalar() or 0

        last = self.get_last_update_time()
        status = "never_run" if last is None else ("error" if self._errors else "ok")

        return {
            "source": self.SOURCE,
            "last_update": last,
            "total_records": article_count + gpr_count,
            "series_count": len(GPR_SERIES),
            "status": status,
            "errors": list(self._errors),
            "articles": article_count,
            "events": event_count,
        }

    # ── Metodos publicos adicionales ──────────────────────────────────────────

    def get_top_stories(
        self,
        n: int = 10,
        category: Optional[str] = None,
        region: Optional[str] = None,
    ) -> list[dict]:
        """
        Devuelve los n articulos mas relevantes segun impact_score.

        Args:
            n: Numero maximo de articulos a devolver.
            category: Filtro opcional por categoria.
            region: Filtro opcional por region.

        Returns:
            Lista de dicts con campos del articulo.
        """
        with SessionLocal() as session:
            q = session.query(NewsArticle).order_by(
                NewsArticle.impact_score.desc(),
                NewsArticle.published_at.desc(),
            )
            if category:
                q = q.filter(NewsArticle.category == category)
            if region:
                q = q.filter(NewsArticle.region == region)
            articles = q.limit(n).all()

        return [
            {
                "title": a.title,
                "description": a.description,
                "url": a.url,
                "source_name": a.source_name,
                "published_at": a.published_at,
                "category": a.category,
                "region": a.region,
                "impact_score": a.impact_score,
                "keywords_matched": a.keywords_matched,
            }
            for a in articles
        ]

    def add_manual_event(
        self,
        date_: "date | datetime",
        title: str,
        description: str,
        category: str,
        region: str,
        severity: int,
        market_impact: str,
        source_url: str,
    ) -> GeopoliticalEvent:
        """
        Anade un evento geopolitico manualmente (is_manual=True).

        Permite al usuario registrar eventos desde el frontend del Modulo 10.

        Args:
            date_: Fecha del evento (date o datetime).
            title: Titulo del evento.
            description: Descripcion detallada.
            category: Tipo (conflict, sanction, election, trade_war, energy, financial_crisis).
            region: Region o paises afectados.
            severity: Severidad 1-5 (1=menor, 5=critico).
            market_impact: Activos financieros afectados.
            source_url: URL de referencia.

        Returns:
            El GeopoliticalEvent creado y guardado en BD.
        """
        # Normalizar a datetime
        if isinstance(date_, datetime):
            event_dt = date_
        else:
            event_dt = datetime(date_.year, date_.month, date_.day)

        event = GeopoliticalEvent(
            date=event_dt,
            title=title[:300],
            description=description[:1000],
            category=category[:50],
            region=region[:100],
            severity=max(1, min(5, int(severity))),
            market_impact=market_impact[:200],
            source_url=source_url[:500],
            is_manual=True,
            created_at=datetime.utcnow(),
        )

        with SessionLocal() as session:
            session.add(event)
            session.commit()
            session.refresh(event)
            event_id = event.id

        logger.info(
            "NewsCollector >> Evento manual anadido [id=%d]: '%s' (%s, sev=%d)",
            event_id, title[:60], region, severity,
        )
        return event

    # ── Metodo privado: NewsAPI ───────────────────────────────────────────────

    def _fetch_newsapi(
        self,
        query: str,
        category: str,
        default_region: Optional[str] = None,
        from_date: Optional[str] = None,
        language: str = "en",
    ) -> dict:
        """
        Llama a NewsAPI, clasifica los articulos y los guarda en SQLite.

        Respeta el limite diario y evita duplicados por URL (UniqueConstraint).

        Returns:
            dict con new (nuevos insertados), duplicates (ya existian)
        """
        if not self._newsapi_enabled:
            return {"new": 0, "duplicates": 0}

        if self._get_request_count() >= NEWSAPI_DAILY_LIMIT:
            logger.warning("NewsCollector >> Limite diario alcanzado. Skipping query.")
            return {"new": 0, "duplicates": 0}

        params: dict = {
            "q":        query,
            "language": language,
            "sortBy":   "relevancy",
            "pageSize": 20,
            "apiKey":   self._newsapi_key,
        }
        if from_date:
            params["from"] = from_date

        try:
            resp = self._session.get(NEWSAPI_BASE, params=params, timeout=TIMEOUT)
            self._increment_request_count()

            if resp.status_code == 401:
                logger.error("NewsCollector >> NewsAPI key invalida (401). Deshabilitando.")
                self._newsapi_enabled = False
                self._errors.append("NewsAPI: API key invalida (401)")
                return {"new": 0, "duplicates": 0}

            if resp.status_code == 429:
                logger.warning("NewsCollector >> NewsAPI rate limit (429). Espera 60s.")
                time.sleep(60)
                return {"new": 0, "duplicates": 0}

            resp.raise_for_status()
            data = resp.json()

            if data.get("status") != "ok":
                msg = data.get("message", "NewsAPI: respuesta inesperada")
                logger.error("NewsCollector >> NewsAPI error: %s", msg)
                self._errors.append(msg)
                return {"new": 0, "duplicates": 0}

            articles_raw = data.get("articles", [])

        except requests.exceptions.RequestException as exc:
            msg = f"NewsAPI request error: {exc}"
            logger.error("NewsCollector >> %s", msg)
            self._errors.append(msg)
            return {"new": 0, "duplicates": 0}

        if not articles_raw:
            return {"new": 0, "duplicates": 0}

        # ── Recoger URLs, filtrar los que ya existen ──────────────────────────
        raw_urls = [
            a.get("url", "")[:500]
            for a in articles_raw
            if a.get("url")
        ]
        with SessionLocal() as session:
            existing_urls: set[str] = {
                r[0]
                for r in session.query(NewsArticle.url).filter(
                    NewsArticle.url.in_(raw_urls)
                ).all()
            }

        new_count = 0
        dup_count = 0
        now = datetime.utcnow()

        for art in articles_raw:
            url = (art.get("url") or "")[:500]
            if not url:
                continue
            if url in existing_urls:
                dup_count += 1
                continue

            title       = (art.get("title") or "")[:500]
            description = (art.get("description") or "")[:1000]
            source_name = ""
            if isinstance(art.get("source"), dict):
                source_name = (art["source"].get("name") or "")[:100]

            published_at: Optional[datetime] = None
            raw_pub = art.get("publishedAt", "")
            if raw_pub:
                try:
                    published_at = datetime.strptime(raw_pub, "%Y-%m-%dT%H:%M:%SZ")
                except ValueError:
                    pass

            classification = self._classify_article(title, description)

            # Si el colector tiene region por defecto y no se detecto automaticamente
            if default_region and classification["region"] == "Global":
                classification["region"] = default_region

            article = NewsArticle(
                title            = title,
                description      = description,
                url              = url,
                source_name      = source_name,
                published_at     = published_at,
                category         = (classification["category"] or category)[:50],
                region           = classification["region"][:50],
                impact_score     = classification["impact_score"],
                keywords_matched = classification["keywords_matched"][:200],
                created_at       = now,
            )

            try:
                with SessionLocal() as session:
                    session.add(article)
                    session.commit()
                new_count += 1
                existing_urls.add(url)  # evitar duplicados dentro del mismo batch
            except IntegrityError:
                dup_count += 1

        return {"new": new_count, "duplicates": dup_count}

    # ── Metodo privado: clasificacion de articulos ────────────────────────────

    def _classify_article(self, title: str, description: str) -> dict:
        """
        Clasifica un articulo: detecta categoria, region, impact_score y keywords.

        impact_score = min(1.0, critical_matches * 0.3 + relevant_matches * 0.1)

        Returns:
            dict con category, region, impact_score, keywords_matched
        """
        text_lower = (title + " " + (description or "")).lower()

        # ── Keywords criticas ─────────────────────────────────────────────────
        critical_matches = [kw for kw in CRITICAL_KEYWORDS if kw.lower() in text_lower]

        # ── Keywords relevantes por categoria ─────────────────────────────────
        category_scores: dict[str, int] = {}
        all_relevant: list[str] = []

        for cat, keywords in CATEGORY_KEYWORDS.items():
            matches = [kw for kw in keywords if kw.lower() in text_lower]
            if matches:
                category_scores[cat] = len(matches)
                all_relevant.extend(matches)

        detected_category: Optional[str] = None
        if category_scores:
            detected_category = max(category_scores, key=lambda c: category_scores[c])

        # ── Region ────────────────────────────────────────────────────────────
        region_scores: dict[str, int] = {}
        for reg, keywords in REGION_KEYWORDS.items():
            matches = sum(1 for kw in keywords if kw in text_lower)
            if matches:
                region_scores[reg] = matches

        if not region_scores:
            detected_region = "Global"
        elif len(region_scores) == 1:
            detected_region = next(iter(region_scores))
        else:
            sorted_r = sorted(region_scores.items(), key=lambda x: x[1], reverse=True)
            # Si el top supera claramente al segundo, asignamos esa region
            if sorted_r[0][1] > sorted_r[1][1]:
                detected_region = sorted_r[0][0]
            else:
                detected_region = "Global"

        # ── Impact score ──────────────────────────────────────────────────────
        impact_score = min(1.0, len(critical_matches) * 0.3 + len(all_relevant) * 0.1)

        # ── Keywords combinadas (dedup, orden de aparicion) ───────────────────
        seen: set[str] = set()
        combined: list[str] = []
        for kw in critical_matches + all_relevant:
            if kw not in seen:
                seen.add(kw)
                combined.append(kw)
        keywords_matched = ", ".join(combined[:20])

        return {
            "category":        detected_category,
            "region":          detected_region,
            "impact_score":    round(impact_score, 3),
            "keywords_matched": keywords_matched,
        }

    # ── Metodo privado: GPR desde Caldara & Iacoviello ───────────────────────

    def _fetch_gpr_index(self, start: str = HISTORY_START) -> dict:
        """
        Descarga las series del GPR (Geopolitical Risk Index) desde el fichero
        Excel publicado por Caldara & Iacoviello (Federal Reserve Board).

        URL: https://www.matteoiacoviello.com/gpr_files/data_gpr_export.xls

        No usa FRED API — descarga directamente el fichero XLS del autor.
        Requiere: xlrd (para .xls) y/o openpyxl (para .xlsx).

        Los datos se guardan en time_series con source='FRED_GPR' para
        mantener compatibilidad con los modulos que los consumen.

        Returns:
            dict con ok, failed, records
        """
        import io
        import pandas as pd

        ok = failed = records = 0

        # ── Descargar el fichero XLS ──────────────────────────────────────────
        try:
            logger.info("  GPR: descargando fichero Excel de Caldara & Iacoviello...")
            resp = self._session.get(GPR_DATA_URL, timeout=60)
            resp.raise_for_status()
            xl = pd.ExcelFile(io.BytesIO(resp.content))
            df_raw = xl.parse("Sheet1")
            logger.info("  GPR: fichero descargado — %d filas x %d cols", len(df_raw), len(df_raw.columns))
        except Exception as exc:
            msg = f"GPR: error descargando fichero Excel: {exc}"
            logger.error("  %s", msg)
            self._errors.append(msg)
            return {"ok": 0, "failed": len(GPR_SERIES), "records": 0}

        # ── Filtrar por fecha de inicio ───────────────────────────────────────
        try:
            start_dt = pd.Timestamp(start)
        except Exception:
            start_dt = pd.Timestamp("2000-01-01")

        now = datetime.utcnow()

        # ── Procesar cada serie ───────────────────────────────────────────────
        for col_name, cfg in GPR_SERIES.items():
            if col_name not in df_raw.columns:
                logger.warning("  GPR: columna '%s' no encontrada en el fichero", col_name)
                failed += 1
                continue

            try:
                # La columna de fecha puede llamarse 'month' o 'Date'
                date_col = "month" if "month" in df_raw.columns else "Date"
                series_df = df_raw[[date_col, col_name]].copy()
                series_df.columns = ["date", "value"]

                # Limpiar: quitar NaN, convertir fechas
                series_df = series_df.dropna(subset=["value"])
                series_df["date"] = pd.to_datetime(series_df["date"], errors="coerce")
                series_df = series_df.dropna(subset=["date"])
                series_df = series_df[series_df["date"] >= start_dt]

                if series_df.empty:
                    logger.info("  GPR: %s — sin datos desde %s", col_name, start)
                    ok += 1
                    continue

                indicator_id = cfg["indicator_id"]
                region       = cfg["region"]

                # Anti-duplicados: obtener MAX timestamp en BD
                with SessionLocal() as session:
                    max_ts = session.query(func.max(TimeSeries.timestamp)).filter(
                        TimeSeries.indicator_id == indicator_id
                    ).scalar()

                if max_ts is not None:
                    series_df = series_df[series_df["date"] > pd.Timestamp(max_ts)]

                if series_df.empty:
                    logger.info("  GPR: %s — sin datos nuevos", col_name)
                    ok += 1
                    continue

                rows = [
                    {
                        "indicator_id": indicator_id,
                        "source":       GPR_SOURCE,
                        "region":       region,
                        "timestamp":    row["date"].to_pydatetime().replace(tzinfo=None),
                        "value":        float(row["value"]),
                        "unit":         "index",
                        "created_at":   now,
                    }
                    for _, row in series_df.iterrows()
                ]

                if rows:
                    with SessionLocal() as session:
                        session.execute(insert(TimeSeries), rows)
                        session.commit()
                    records += len(rows)
                    logger.info("  GPR: %s (%s) — %d nuevos registros", col_name, cfg["name"], len(rows))

                ok += 1

            except Exception as exc:
                msg = f"GPR {col_name}: {exc}"
                logger.error("  GPR ERROR: %s", msg)
                self._errors.append(msg)
                failed += 1

        return {"ok": ok, "failed": failed, "records": records}

    # ── Metodo privado: GDELT ─────────────────────────────────────────────────

    def _fetch_gdelt_tensions(self) -> dict:
        """
        Obtiene el tono global de noticias de GDELT y lo guarda como serie temporal.

        Extrae el tono medio de la respuesta (valor negativo = mayor tension).
        Si el endpoint no responde o cambia de formato, lo marca como no disponible
        y continua sin el — GDELT es complemento, no dato critico.

        Returns:
            dict con ok (bool), records (int), tone (float), error (str si falla)
        """
        try:
            resp = self._session.get(GDELT_URL, timeout=TIMEOUT)
            resp.raise_for_status()

            # GDELT puede devolver JSON, CSV, o texto plano segun el endpoint
            tone_value: Optional[float] = None
            content_type = resp.headers.get("Content-Type", "")

            if "json" in content_type or resp.text.strip().startswith("{"):
                try:
                    data = resp.json()
                    # Intentar distintos formatos conocidos de GDELT
                    if isinstance(data, dict):
                        for key in ("tonechart", "data", "results", "articles"):
                            entries = data.get(key)
                            if isinstance(entries, list) and entries:
                                last = entries[-1]
                                for tkey in ("tone", "avgtone", "avg_tone", "value"):
                                    if tkey in last:
                                        tone_value = float(last[tkey])
                                        break
                            if tone_value is not None:
                                break
                        if tone_value is None:
                            # Busqueda generica en el JSON serializado
                            raw = json.dumps(data)
                            m = re.search(r'"(?:avgtone|tone|avg_tone)"\s*:\s*(-?\d+\.?\d*)', raw)
                            if m:
                                tone_value = float(m.group(1))
                except (ValueError, KeyError):
                    pass

            # Fallback: buscar numero en el texto plano
            if tone_value is None:
                m = re.search(r'-?\d+\.\d+', resp.text)
                if m:
                    tone_value = float(m.group(0))

            if tone_value is None:
                return {
                    "ok":      False,
                    "records": 0,
                    "error":   "No se pudo extraer el tono de GDELT (formato desconocido)",
                }

            tone_f = float(tone_value)
            now = datetime.utcnow()

            row = {
                "indicator_id": "gdelt_global_tone",
                "source":       GDELT_SOURCE,
                "region":       "GLOBAL",
                "timestamp":    now,
                "value":        tone_f,
                "unit":         "index",
                "created_at":   now,
            }
            with SessionLocal() as session:
                session.execute(insert(TimeSeries), [row])
                session.commit()

            logger.info("GDELT >> Tono global: %.3f (OK)", tone_f)
            return {"ok": True, "records": 1, "tone": tone_f}

        except requests.exceptions.RequestException as exc:
            logger.warning("GDELT >> No disponible: %s", exc)
            return {"ok": False, "records": 0, "error": str(exc)}
        except Exception as exc:
            logger.warning("GDELT >> Error inesperado: %s", exc)
            return {"ok": False, "records": 0, "error": str(exc)}

    # ── Metodo privado: auto-generacion de eventos geopoliticos ───────────────

    def _auto_generate_geopolitical_events(self) -> int:
        """
        Analiza articulos con impact_score > 0.5 de las ultimas 48 horas.
        Agrupa en clusters los que comparten >= 2 keywords.
        Crea un GeopoliticalEvent por cluster (si no existe ya).

        Severidad segun impact_score medio del cluster:
          0.50 - 0.69  ->  severity 2
          0.70 - 0.84  ->  severity 3
          0.85 - 0.94  ->  severity 4
          0.95 - 1.00  ->  severity 5

        Returns:
            Numero de eventos creados.
        """
        cutoff = datetime.utcnow() - timedelta(hours=48)

        with SessionLocal() as session:
            high_impact = session.query(NewsArticle).filter(
                NewsArticle.impact_score > 0.5,
                NewsArticle.created_at >= cutoff,
            ).order_by(NewsArticle.impact_score.desc()).limit(100).all()

        if not high_impact:
            return 0

        # Construir el conjunto global de keywords de referencia
        all_keywords: set[str] = set(CRITICAL_KEYWORDS)
        for kws in CATEGORY_KEYWORDS.values():
            all_keywords.update(kws)

        def article_kws(art: NewsArticle) -> frozenset:
            text = ((art.title or "") + " " + (art.description or "")).lower()
            return frozenset(kw for kw in all_keywords if kw.lower() in text)

        keyed = [(a, article_kws(a)) for a in high_impact]

        # ── Clustering union-find simple ──────────────────────────────────────
        clusters: list[list[int]] = []
        for i, (_, kws_i) in enumerate(keyed):
            placed = False
            for cluster in clusters:
                for j in cluster:
                    if len(kws_i & keyed[j][1]) >= 2:
                        cluster.append(i)
                        placed = True
                        break
                if placed:
                    break
            if not placed:
                clusters.append([i])

        events_created = 0
        for cluster_indices in clusters:
            cluster_arts = [keyed[i][0] for i in cluster_indices]
            avg_impact = sum(a.impact_score or 0.0 for a in cluster_arts) / len(cluster_arts)

            if avg_impact < 0.5:
                continue

            # Severidad
            if avg_impact >= 0.95:
                severity = 5
            elif avg_impact >= 0.85:
                severity = 4
            elif avg_impact >= 0.70:
                severity = 3
            else:
                severity = 2

            lead = max(cluster_arts, key=lambda a: a.impact_score or 0.0)

            # Combinar descripciones (max 3 articulos, sin repetir)
            seen_descs: set[str] = set()
            desc_parts: list[str] = []
            for a in sorted(cluster_arts, key=lambda x: x.impact_score or 0, reverse=True)[:3]:
                if a.description and a.description not in seen_descs:
                    desc_parts.append(a.description)
                    seen_descs.add(a.description)
            combined_desc = " | ".join(desc_parts)[:1000]

            regions    = [a.region for a in cluster_arts if a.region]
            categories = [a.category for a in cluster_arts if a.category]
            region   = max(set(regions),    key=regions.count)    if regions    else "Global"
            category = max(set(categories), key=categories.count) if categories else "geopolitics"

            # Verificar si ya existe evento con el mismo titular reciente
            with SessionLocal() as session:
                existing = session.query(GeopoliticalEvent).filter(
                    GeopoliticalEvent.title     == lead.title[:300],
                    GeopoliticalEvent.is_manual == False,
                    GeopoliticalEvent.created_at >= cutoff,
                ).first()

                if existing:
                    continue

                event = GeopoliticalEvent(
                    date        = lead.published_at or datetime.utcnow(),
                    title       = lead.title[:300],
                    description = combined_desc,
                    category    = category[:50],
                    region      = region[:100],
                    severity    = severity,
                    market_impact = "",
                    source_url  = (lead.url or "")[:500],
                    is_manual   = False,
                    created_at  = datetime.utcnow(),
                )
                session.add(event)
                session.commit()
                events_created += 1
                logger.info(
                    "  -> Evento auto-generado [sev=%d, impact=%.2f]: '%.60s'",
                    severity, avg_impact, lead.title,
                )

        return events_created

    # ── Metodo privado: limpieza ──────────────────────────────────────────────

    def _cleanup_old_articles(self) -> int:
        """Elimina articulos con mas de 90 dias de antiguedad."""
        cutoff = datetime.utcnow() - timedelta(days=90)
        with SessionLocal() as session:
            deleted = session.query(NewsArticle).filter(
                NewsArticle.published_at < cutoff
            ).delete(synchronize_session=False)
            session.commit()
        return deleted or 0

    # ── Metodo privado: contador de peticiones NewsAPI ────────────────────────

    def _get_request_count(self) -> int:
        """Lee el contador de peticiones del dia actual desde el fichero JSON."""
        today = date.today().isoformat()
        if not self._counter_file.exists():
            return 0
        try:
            with open(self._counter_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("date") != today:
                return 0  # Nuevo dia: contador en cero
            return int(data.get("count", 0))
        except (json.JSONDecodeError, KeyError, TypeError):
            return 0

    def _increment_request_count(self) -> int:
        """Incrementa y persiste el contador del dia. Retorna el nuevo valor."""
        today = date.today().isoformat()
        new_count = self._get_request_count() + 1
        with open(self._counter_file, "w", encoding="utf-8") as f:
            json.dump({"date": today, "count": new_count}, f)
        return new_count
