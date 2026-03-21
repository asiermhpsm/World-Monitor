"""
Script de prueba del NewsCollector.

Ejecuta un subconjunto reducido de operaciones para validar el colector
sin agotar el limite de 100 peticiones/dia de NewsAPI:
  - Solo 2 queries de NewsAPI (bancos centrales y geopolitica)
  - Las 7 series GPR de FRED
  - Tono global de GDELT
  - Auto-generacion de eventos geopoliticos
  - Evento manual de prueba

Uso:
    cd "World Monitor"
    python scripts/test_news.py
"""

import logging
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collectors.news_collector import (
    GPR_HISTORICAL_PEAKS,
    GPR_SERIES,
    GPR_ZONES,
    GPR_SOURCE,
    GDELT_SOURCE,
    NEWS_SOURCE,
    NewsCollector,
)
from database.database import (
    GeopoliticalEvent,
    NewsArticle,
    SessionLocal,
    TimeSeries,
)

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


def get_latest_ts(indicator_id: str):
    """Devuelve (valor, timestamp) del registro mas reciente en time_series."""
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


def count_ts(indicator_id: str) -> int:
    with SessionLocal() as session:
        return session.query(TimeSeries).filter(
            TimeSeries.indicator_id == indicator_id
        ).count()


def gpr_semaforo(value: float) -> str:
    for low, high, level, color, desc in GPR_ZONES:
        if low <= value < high:
            return f"[{color}] {desc}"
    return "[ROJO] Tension extrema"


# ── Script principal ──────────────────────────────────────────────────────────

def main() -> None:
    print()
    sep("WORLD MONITOR - TEST COLECTOR NOTICIAS & GEOPOLITICA")
    print("  Prueba: 2 queries NewsAPI + 7 series GPR + GDELT + eventos")
    print()

    # Inicializar el colector
    collector = NewsCollector()
    print("  OK NewsCollector inicializado")
    print(f"  NewsAPI habilitado : {collector._newsapi_enabled}")
    print(f"  FRED/GPR habilitado: {collector._fred_enabled}")

    total_articles = 0
    total_gpr_records = 0

    # ──────────────────────────────────────────────────────────────────────────
    # 1. NewsAPI: solo 2 queries para no gastar peticiones
    # ──────────────────────────────────────────────────────────────────────────
    sep("1. NEWSAPI — 2 QUERIES DE PRUEBA")

    if collector._newsapi_enabled:
        # Query 1: Bancos centrales
        print("\n  Query 1: Bancos centrales y politica monetaria")
        from_date = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")
        r1 = collector._fetch_newsapi(
            query='Federal Reserve OR ECB OR "Bank of England" OR "interest rate"',
            category="central_banks",
            from_date=from_date,
        )
        print(f"    Nuevos articulos: {r1['new']}  |  Duplicados: {r1['duplicates']}")
        total_articles += r1["new"]

        # Query 2: Geopolitica
        print("\n  Query 2: Geopolitica y tensiones globales")
        r2 = collector._fetch_newsapi(
            query='geopolitical OR sanctions OR "trade war" OR tariffs OR military OR conflict',
            category="geopolitics",
            from_date=from_date,
        )
        print(f"    Nuevos articulos: {r2['new']}  |  Duplicados: {r2['duplicates']}")
        total_articles += r2["new"]

        # Contador de peticiones
        reqs = collector._get_request_count()
        print(f"\n  Peticiones NewsAPI usadas hoy: {reqs}/{collector._newsapi_enabled and 100}")
    else:
        print("  SKIP — NEWS_API_KEY no configurada (modo degradado)")

    # ──────────────────────────────────────────────────────────────────────────
    # 2. GPR desde FRED (7 series)
    # ──────────────────────────────────────────────────────────────────────────
    sep("2. GPR INDEX — 7 SERIES (Caldara & Iacoviello / Fed)")

    print()
    gpr_result = collector._fetch_gpr_index(start="2000-01-01")
    print(f"\n  GPR descargado: OK={gpr_result['ok']}  Fail={gpr_result['failed']}  "
          f"Nuevos registros={gpr_result['records']:,}")
    total_gpr_records = gpr_result["records"]

    # Verificar cada serie
    print()
    print(f"  {'Columna Excel':<14}  {'indicator_id':<22}  {'Registros':>9}  {'Ultimo dato':>12}  {'Valor':>8}")
    sep()
    for col_name, cfg in GPR_SERIES.items():
        cnt = count_ts(cfg["indicator_id"])
        val, ts = get_latest_ts(cfg["indicator_id"])
        ts_str  = ts.strftime("%Y-%m-%d") if ts else "N/A"
        val_str = f"{val:.1f}" if val is not None else "N/A"
        ok_mark = "OK" if cnt > 0 else "SIN DATOS"
        print(f"  {col_name:<14}  {cfg['indicator_id']:<22}  {cnt:>9,}  "
              f"{ts_str:>12}  {val_str:>8}  {ok_mark}")

    # ──────────────────────────────────────────────────────────────────────────
    # 3. Tono global GDELT
    # ──────────────────────────────────────────────────────────────────────────
    sep("3. GDELT — TONO GLOBAL DE NOTICIAS")

    print()
    gdelt_result = collector._fetch_gdelt_tensions()
    if gdelt_result.get("ok"):
        tone = gdelt_result["tone"]
        print(f"  Tono global GDELT  : {tone:.3f}")
        if tone < -2:
            interp = "Noticias globales muy negativas — tension elevada"
        elif tone < -1:
            interp = "Noticias globales negativas — moderada tension"
        elif tone < 0:
            interp = "Noticias globales ligeramente negativas — normal"
        else:
            interp = "Noticias globales neutrales o positivas"
        print(f"  Interpretacion     : {interp}")
        print(f"  Referencia         : 0.0 = neutral  |  -5.0 = crisis global")
    else:
        print(f"  GDELT no disponible: {gdelt_result.get('error', 'sin detalle')}")
        print("  (GDELT es complemento, no dato critico — el colector continua sin el)")

    # ──────────────────────────────────────────────────────────────────────────
    # 4. Resumen de articulos descargados
    # ──────────────────────────────────────────────────────────────────────────
    sep("4. ARTICULOS DESCARGADOS EN TOTAL")

    with SessionLocal() as session:
        db_article_count = session.query(NewsArticle).count()

    print(f"\n  Articulos nuevos en esta prueba   : {total_articles}")
    print(f"  Total articulos en la base de datos: {db_article_count}")

    # ──────────────────────────────────────────────────────────────────────────
    # 5. Top 5 articulos por impact_score
    # ──────────────────────────────────────────────────────────────────────────
    sep("5. TOP 5 ARTICULOS POR IMPACT SCORE")

    top5 = collector.get_top_stories(n=5)
    if top5:
        print()
        for i, art in enumerate(top5, 1):
            pub_str = art["published_at"].strftime("%Y-%m-%d %H:%M") if art["published_at"] else "N/A"
            print(f"  [{i}] Impact: {art['impact_score']:.3f}  |  {pub_str}  |  {art['source_name']}")
            print(f"      {art['title'][:80]}")
            print(f"      Cat: {art['category']}  |  Region: {art['region']}")
            if art["keywords_matched"]:
                print(f"      Keywords: {art['keywords_matched'][:80]}")
            print()
    else:
        print("\n  Sin articulos aun (puede que NewsAPI no este configurada)")

    # ──────────────────────────────────────────────────────────────────────────
    # 6. Estado GPR global y comparativa historica
    # ──────────────────────────────────────────────────────────────────────────
    sep("6. GPR GLOBAL — SEMAFORO Y COMPARATIVA HISTORICA")

    gpr_val, gpr_ts = get_latest_ts("fred_gpr_global")
    if gpr_val is not None:
        print(f"\n  GPR Global actual  : {gpr_val:.1f}  ({gpr_ts.strftime('%Y-%m')})")
        print(f"  Semaforo           : {gpr_semaforo(gpr_val)}")
        print()
        print("  Comparativa con picos historicos:")
        print(f"  {'Evento':<28}  {'Nivel GPR':>9}  {'vs Actual':>12}")
        sep()
        for event_name, peak_val in GPR_HISTORICAL_PEAKS.items():
            ratio = gpr_val / peak_val * 100
            if ratio >= 100:
                comparison = f"SIMILAR o superior ({ratio:.0f}%)"
            elif ratio >= 75:
                comparison = f"Tension alta ({ratio:.0f}% del pico)"
            elif ratio >= 50:
                comparison = f"Tension moderada ({ratio:.0f}% del pico)"
            else:
                comparison = f"Mucho menor ({ratio:.0f}% del pico)"
            print(f"  {event_name:<28}  {peak_val:>9.0f}  {comparison}")
        print()
        # Pregunta directa: estamos mas o menos tensos que en el 11-S?
        sep_11s = GPR_HISTORICAL_PEAKS.get("11-S 2001", 450)
        sep_ukr = GPR_HISTORICAL_PEAKS.get("Ucrania 2022", 230)
        print(f"  Respuesta directa:")
        print(f"    vs 11-S 2001 (GPR={sep_11s}):     ", end="")
        if gpr_val >= sep_11s:
            print(f"IGUAL O MAS tenso — nivel historico excepcional")
        else:
            print(f"{sep_11s - gpr_val:.0f} puntos MENOS tenso que el 11-S")
        print(f"    vs Ucrania 2022 (GPR={sep_ukr}):  ", end="")
        if gpr_val >= sep_ukr:
            print(f"IGUAL O MAS tenso — nivel equiparable a invasion Ucrania")
        else:
            print(f"{sep_ukr - gpr_val:.0f} puntos MENOS tenso que Ucrania 2022")
    else:
        print("\n  GPR no disponible (FRED no configurado o sin datos aun)")

    # ──────────────────────────────────────────────────────────────────────────
    # 7. Auto-generacion de eventos geopoliticos
    # ──────────────────────────────────────────────────────────────────────────
    sep("7. AUTO-GENERACION DE EVENTOS GEOPOLITICOS")

    with SessionLocal() as session:
        high_impact_count = session.query(NewsArticle).filter(
            NewsArticle.impact_score > 0.5
        ).count()

    print(f"\n  Articulos con impact_score > 0.5: {high_impact_count}")

    if high_impact_count > 0:
        events_before = 0
        with SessionLocal() as session:
            events_before = session.query(GeopoliticalEvent).filter(
                GeopoliticalEvent.is_manual == False
            ).count()

        n_generated = collector._auto_generate_geopolitical_events()
        print(f"  Eventos generados en esta ejecucion: {n_generated}")

        with SessionLocal() as session:
            events_after = session.query(GeopoliticalEvent).filter(
                GeopoliticalEvent.is_manual == False
            ).count()
            auto_events = session.query(GeopoliticalEvent).filter(
                GeopoliticalEvent.is_manual == False
            ).order_by(GeopoliticalEvent.created_at.desc()).limit(5).all()

        print(f"  Total eventos auto en BD: {events_after}")
        if auto_events:
            print()
            print("  Ultimos eventos auto-generados:")
            for ev in auto_events:
                dt_str = ev.date.strftime("%Y-%m-%d") if ev.date else "N/A"
                print(f"    [{ev.severity}*] {dt_str}  |  {ev.region}  |  {ev.title[:60]}")
    else:
        print("  Sin articulos de alto impacto todavia — no se generan eventos")
        print("  (Con newsapi configurada y mas articulos, esto funcionara)")

    # ──────────────────────────────────────────────────────────────────────────
    # 8. Evento manual de prueba
    # ──────────────────────────────────────────────────────────────────────────
    sep("8. EVENTO MANUAL DE PRUEBA (add_manual_event)")

    test_date  = date(2026, 3, 21)
    test_title = "[TEST] Reunion de emergencia G7 por tension en Estrecho de Taiwan"
    test_desc  = (
        "Los lideres del G7 se reunen de urgencia ante el escalamiento "
        "de tensiones militares en el Estrecho de Taiwan. China ha aumentado "
        "sus ejercicios navales cerca de las aguas territoriales de Taiwan."
    )

    print(f"\n  Anadiendo evento de prueba: '{test_title[:60]}...'")

    manual_event = collector.add_manual_event(
        date_=test_date,
        title=test_title,
        description=test_desc,
        category="conflict",
        region="China",
        severity=4,
        market_impact="TSM, semiconductores, indices asiaticos, USD/CNY, USD/TWD",
        source_url="https://example.com/test-event",
    )

    # Verificar que se guardo en SQLite
    with SessionLocal() as session:
        saved = session.query(GeopoliticalEvent).filter(
            GeopoliticalEvent.id == manual_event.id
        ).first()

    if saved:
        print(f"  OK — Evento guardado en SQLite con id={saved.id}")
        print(f"       Titulo   : {saved.title}")
        print(f"       Fecha    : {saved.date.strftime('%Y-%m-%d')}")
        print(f"       Region   : {saved.region}")
        print(f"       Severidad: {saved.severity}/5")
        print(f"       Manual   : {saved.is_manual}")
        print(f"       Impacto  : {saved.market_impact}")
    else:
        print("  ERROR — Evento no encontrado en la base de datos")

    # ──────────────────────────────────────────────────────────────────────────
    # 9. Resumen final del colector
    # ──────────────────────────────────────────────────────────────────────────
    sep("RESUMEN FINAL DEL COLECTOR")

    status = collector.get_status()
    print()
    print(f"  Fuente principal     : {status['source'].upper()}")
    print(f"  Estado               : {status['status'].upper()}")
    print(f"  Total registros BD   : {status['total_records']:,}")
    print(f"    - Articulos        : {status['articles']:,}")
    print(f"    - Series GPR       : {status['series_count']}")
    print(f"    - Eventos geopolit.: {status['events']:,}")
    print(f"  Ultima actualizacion : {status['last_update']}")

    if status["errors"]:
        print(f"\n  Errores ({len(status['errors'])}):")
        for e in status["errors"][:5]:
            print(f"    - {e}")
    else:
        print("\n  Sin errores.")

    print()
    sep()
    print("  Test completado.")
    print()
    print("  Para historico completo (30 dias noticias + GPR full):")
    print("      collector.run_full_history()")
    print()
    print("  Para actualizacion periodica (cada hora):")
    print("      collector.run_update()")
    print()


if __name__ == "__main__":
    main()
