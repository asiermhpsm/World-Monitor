"""
DashboardScheduler — gestión central de tareas automáticas del World Monitor.

Usa APScheduler 3.x con BackgroundScheduler (hilo separado, no bloquea el dashboard).
Todas las tablas propias (SchedulerLog, SnapshotHistory) se crean directamente en
el mismo SQLite del proyecto sin alterar el esquema de database.py.
"""

import json
import logging
import sqlite3
import threading
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from config import DB_PATH

logger = logging.getLogger(__name__)


class DashboardScheduler:
    """
    Scheduler principal del World Monitor.

    Ejecuta todos los colectores en background con sus frecuencias programadas.
    Registra cada ejecución en SchedulerLog y guarda snapshots semanales en
    SnapshotHistory. Nunca deja que un fallo de colector tumbe el scheduler.
    """

    # Nombres legibles por colector
    COLLECTOR_LABELS = {
        "FREDCollector":      "FRED (Fed Reserve)",
        "YahooCollector":     "Yahoo Finance",
        "WorldBankCollector": "World Bank",
        "EuropeCollector":    "BCE + Eurostat",
        "CoinGeckoCollector": "CoinGecko",
        "NewsCollector":      "Noticias / GPR",
        "AlertManager":       "Sistema de Alertas",
    }

    def __init__(self):
        self._scheduler = BackgroundScheduler(
            job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 300}
        )
        self._started_at: Optional[datetime] = None
        self._lock = threading.Lock()

        # Importación diferida para evitar arranques lentos si un colector falla
        self._collectors: Dict[str, Any] = {}
        self._alert_manager = None
        self._init_collectors()
        self._init_db()

    # ─────────────────────────────────────────────────────────────────────────
    # Inicialización
    # ─────────────────────────────────────────────────────────────────────────

    def _init_collectors(self):
        """Instancia todos los colectores. Fallo individual no bloquea el resto."""
        collector_specs = [
            ("FREDCollector",      "collectors.fred_collector",      "FREDCollector"),
            ("YahooCollector",     "collectors.yahoo_collector",     "YahooCollector"),
            ("WorldBankCollector", "collectors.worldbank_collector", "WorldBankCollector"),
            ("EuropeCollector",    "collectors.europe_collector",    "EuropeCollector"),
            ("CoinGeckoCollector", "collectors.coingecko_collector", "CoinGeckoCollector"),
            ("NewsCollector",      "collectors.news_collector",      "NewsCollector"),
        ]
        for key, module_path, class_name in collector_specs:
            try:
                import importlib
                mod = importlib.import_module(module_path)
                cls = getattr(mod, class_name)
                self._collectors[key] = cls()
                logger.info("[Scheduler] Colector instanciado: %s", key)
            except Exception as e:
                logger.warning("[Scheduler] No se pudo instanciar %s: %s", key, e)

    def _init_db(self):
        """Crea las tablas SchedulerLog y SnapshotHistory si no existen."""
        conn = sqlite3.connect(str(DB_PATH))
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS SchedulerLog (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    collector_name   TEXT    NOT NULL,
                    job_type         TEXT    NOT NULL DEFAULT 'update',
                    started_at       TEXT    NOT NULL,
                    finished_at      TEXT,
                    status           TEXT    NOT NULL DEFAULT 'running',
                    records_updated  INTEGER DEFAULT 0,
                    error_message    TEXT,
                    duration_seconds REAL
                );

                CREATE TABLE IF NOT EXISTS SnapshotHistory (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    snapshot_date TEXT    UNIQUE NOT NULL,
                    snapshot_data TEXT    NOT NULL,
                    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
                );
            """)
            conn.commit()
            logger.info("[Scheduler] Tablas SchedulerLog y SnapshotHistory listas")
        finally:
            conn.close()

    # ─────────────────────────────────────────────────────────────────────────
    # Arranque y parada
    # ─────────────────────────────────────────────────────────────────────────

    def start(self):
        """Registra todos los jobs y arranca el scheduler en background."""
        self._register_jobs()
        self._scheduler.start()
        self._started_at = datetime.utcnow()
        logger.info("[Scheduler] Arrancado. %d jobs registrados.", len(self._scheduler.get_jobs()))

    def stop(self):
        """Para el scheduler limpiamente."""
        try:
            if self._scheduler.running:
                self._scheduler.shutdown(wait=False)
                logger.info("[Scheduler] Detenido correctamente.")
        except Exception as e:
            logger.warning("[Scheduler] Error al detener: %s", e)

    # ─────────────────────────────────────────────────────────────────────────
    # Registro de jobs
    # ─────────────────────────────────────────────────────────────────────────

    def _register_jobs(self):
        """Registra todos los jobs con sus frecuencias."""
        fred   = self._collectors.get("FREDCollector")
        yahoo  = self._collectors.get("YahooCollector")
        wb     = self._collectors.get("WorldBankCollector")
        europe = self._collectors.get("EuropeCollector")
        cg     = self._collectors.get("CoinGeckoCollector")
        news   = self._collectors.get("NewsCollector")

        # ── Yahoo Finance: cada 15 min en horario de mercado (14-22 UTC L-V) ──
        if yahoo:
            self._scheduler.add_job(
                func=self._yahoo_market_update,
                trigger=CronTrigger(minute="0,15,30,45", hour="14-22", day_of_week="mon-fri"),
                id="yahoo_market",
                name="Yahoo — horario mercado (15 min)",
                replace_existing=True,
            )
            # Fuera de horario: cada 2h (para mercados asiáticos y fines de semana)
            self._scheduler.add_job(
                func=self._yahoo_offmarket_update,
                trigger=IntervalTrigger(hours=2),
                id="yahoo_offmarket",
                name="Yahoo — fuera horario (2h)",
                replace_existing=True,
            )

        # ── CoinGecko: cada 30 min todos los días ─────────────────────────────
        if cg:
            self._scheduler.add_job(
                func=lambda: self._execute_collector(cg, "run_update", "CoinGeckoCollector", "update"),
                trigger=IntervalTrigger(minutes=30),
                id="coingecko_30min",
                name="CoinGecko — cada 30 min",
                replace_existing=True,
            )
            # Job diario adicional a las 00:30 UTC para cierre de día
            self._scheduler.add_job(
                func=lambda: self._execute_collector(cg, "run_update", "CoinGeckoCollector", "update"),
                trigger=CronTrigger(hour=0, minute=30),
                id="coingecko_daily",
                name="CoinGecko — cierre diario 00:30 UTC",
                replace_existing=True,
            )

        # ── FRED: diario a las 06:00 UTC ──────────────────────────────────────
        if fred:
            self._scheduler.add_job(
                func=lambda: self._execute_collector(fred, "run_update", "FREDCollector", "update"),
                trigger=CronTrigger(hour=6, minute=0),
                id="fred_daily",
                name="FRED — diario 06:00 UTC",
                replace_existing=True,
            )

        # ── Europe (BCE + Eurostat): diario a las 07:00 UTC ──────────────────
        if europe:
            self._scheduler.add_job(
                func=lambda: self._execute_collector(europe, "run_update", "EuropeCollector", "update"),
                trigger=CronTrigger(hour=7, minute=0),
                id="europe_daily",
                name="BCE/Eurostat — diario 07:00 UTC",
                replace_existing=True,
            )

        # ── News: dos veces al día (08:00 y 18:00 UTC) ────────────────────────
        if news:
            self._scheduler.add_job(
                func=lambda: self._execute_collector(news, "run_update", "NewsCollector", "update"),
                trigger=CronTrigger(hour=8, minute=0),
                id="news_morning",
                name="Noticias — mañana 08:00 UTC",
                replace_existing=True,
            )
            self._scheduler.add_job(
                func=lambda: self._execute_collector(news, "run_update", "NewsCollector", "update"),
                trigger=CronTrigger(hour=18, minute=0),
                id="news_evening",
                name="Noticias — tarde 18:00 UTC",
                replace_existing=True,
            )

        # ── World Bank: semanal los domingos a las 03:00 UTC ──────────────────
        if wb:
            self._scheduler.add_job(
                func=lambda: self._execute_collector(wb, "run_update", "WorldBankCollector", "update"),
                trigger=CronTrigger(day_of_week="sun", hour=3, minute=0),
                id="worldbank_weekly",
                name="World Bank — domingos 03:00 UTC",
                replace_existing=True,
            )

        # ── Snapshot semanal: domingos a las 23:59 UTC ────────────────────────
        self._scheduler.add_job(
            func=self.take_weekly_snapshot,
            trigger=CronTrigger(day_of_week="sun", hour=23, minute=59),
            id="weekly_snapshot",
            name="Snapshot semanal — domingos 23:59 UTC",
            replace_existing=True,
        )

        # ── Alertas: cada 15 minutos ──────────────────────────────────────────
        self._scheduler.add_job(
            func=self._check_alerts_job,
            trigger=IntervalTrigger(minutes=15),
            id="alerts_check",
            name="Verificar alertas — cada 15 min",
            replace_existing=True,
        )

        logger.info("[Scheduler] %d jobs registrados.", len(self._scheduler.get_jobs()))

    # ─────────────────────────────────────────────────────────────────────────
    # Wrappers de ejecución Yahoo (con control de horario)
    # ─────────────────────────────────────────────────────────────────────────

    def _is_market_hours(self) -> bool:
        """True si estamos en horario de mercado: 14:00–22:59 UTC, lunes a viernes."""
        now = datetime.utcnow()
        if now.weekday() >= 5:   # sábado=5, domingo=6
            return False
        return 14 <= now.hour <= 22

    def _yahoo_market_update(self):
        yahoo = self._collectors.get("YahooCollector")
        if yahoo:
            self._execute_collector(yahoo, "run_update", "YahooCollector", "update")

    def _yahoo_offmarket_update(self):
        """Ejecuta update de Yahoo solo cuando NO estamos en horario de mercado."""
        if not self._is_market_hours():
            yahoo = self._collectors.get("YahooCollector")
            if yahoo:
                self._execute_collector(yahoo, "run_update", "YahooCollector", "update")

    # ─────────────────────────────────────────────────────────────────────────
    # Wrapper de alertas
    # ─────────────────────────────────────────────────────────────────────────

    def _check_alerts_job(self):
        """Job que ejecuta check_all_alerts() del AlertManager."""
        try:
            from alerts.alert_manager import AlertManager
            am = AlertManager()
            fired = am.check_all_alerts()
            logger.info("[Scheduler] Alertas comprobadas — %d disparadas", len(fired))
        except Exception as e:
            logger.error("[Scheduler] Error comprobando alertas: %s", e)

    # ─────────────────────────────────────────────────────────────────────────
    # Ejecución con logging
    # ─────────────────────────────────────────────────────────────────────────

    def _execute_collector(
        self,
        collector,
        method_name: str,
        collector_name: str,
        job_type: str = "update",
    ):
        """
        Ejecuta un método de colector con:
        - Registro en SchedulerLog al inicio y al final
        - Captura total de excepciones (nunca tumba el scheduler)
        - Logging detallado
        """
        started_at = datetime.utcnow()
        log_id = self._log_start(collector_name, job_type, started_at)

        try:
            method = getattr(collector, method_name)
            result = method()

            duration = (datetime.utcnow() - started_at).total_seconds()
            records = result.get("total_records", 0) if isinstance(result, dict) else 0
            self._log_finish(log_id, "success", records, duration, None)
            logger.info(
                "[Scheduler] %s.%s OK — %.1fs — %d registros",
                collector_name, method_name, duration, records
            )

        except Exception as e:
            duration = (datetime.utcnow() - started_at).total_seconds()
            error_msg = str(e)[:500]
            self._log_finish(log_id, "error", 0, duration, error_msg)
            logger.error(
                "[Scheduler] %s.%s ERROR (%.1fs): %s",
                collector_name, method_name, duration, error_msg
            )

    # ─────────────────────────────────────────────────────────────────────────
    # SchedulerLog helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _log_start(self, collector_name: str, job_type: str, started_at: datetime) -> int:
        """Inserta una entrada 'running' en SchedulerLog y devuelve su id."""
        conn = sqlite3.connect(str(DB_PATH))
        try:
            cur = conn.execute(
                """INSERT INTO SchedulerLog
                   (collector_name, job_type, started_at, status)
                   VALUES (?, ?, ?, 'running')""",
                (collector_name, job_type, started_at.isoformat()),
            )
            conn.commit()
            return cur.lastrowid
        except Exception as e:
            logger.warning("[Scheduler] No se pudo escribir en SchedulerLog: %s", e)
            return -1
        finally:
            conn.close()

    def _log_finish(
        self,
        log_id: int,
        status: str,
        records: int,
        duration: float,
        error_msg: Optional[str],
    ):
        """Actualiza la entrada de SchedulerLog con el resultado final."""
        if log_id < 0:
            return
        conn = sqlite3.connect(str(DB_PATH))
        try:
            conn.execute(
                """UPDATE SchedulerLog
                   SET finished_at      = ?,
                       status           = ?,
                       records_updated  = ?,
                       duration_seconds = ?,
                       error_message    = ?
                   WHERE id = ?""",
                (
                    datetime.utcnow().isoformat(),
                    status,
                    records,
                    duration,
                    error_msg,
                    log_id,
                ),
            )
            conn.commit()
        except Exception as e:
            logger.warning("[Scheduler] No se pudo actualizar SchedulerLog: %s", e)
        finally:
            conn.close()

    # ─────────────────────────────────────────────────────────────────────────
    # API pública
    # ─────────────────────────────────────────────────────────────────────────

    def get_status(self) -> Dict[str, Any]:
        """
        Devuelve el estado de todos los jobs.

        Estructura por colector:
        {
            'label':        str,
            'last_run':     datetime|None,
            'last_status':  'success'|'error'|'never_run',
            'last_records': int,
            'next_run':     datetime|None,
            'is_running':   bool,
            'error_msg':    str|None,
        }
        """
        jobs = self._scheduler.get_jobs() if self._scheduler.running else []
        next_runs: Dict[str, datetime] = {}
        for job in jobs:
            # Agrupa por colector (nombre simple del job)
            next_runs[job.id] = job.next_run_time

        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        status: Dict[str, Any] = {}

        try:
            # Última ejecución por colector
            rows = conn.execute("""
                SELECT collector_name,
                       MAX(started_at)   AS last_started,
                       status,
                       records_updated,
                       error_message,
                       finished_at
                FROM   SchedulerLog
                WHERE  id IN (
                    SELECT MAX(id) FROM SchedulerLog GROUP BY collector_name
                )
                GROUP  BY collector_name
            """).fetchall()

            for row in rows:
                name = row["collector_name"]
                last_started = None
                if row["last_started"]:
                    try:
                        last_started = datetime.fromisoformat(row["last_started"])
                    except ValueError:
                        pass

                status[name] = {
                    "label":        self.COLLECTOR_LABELS.get(name, name),
                    "last_run":     last_started,
                    "last_status":  row["status"],
                    "last_records": row["records_updated"] or 0,
                    "next_run":     None,
                    "is_running":   row["status"] == "running",
                    "error_msg":    row["error_message"],
                }

            # Completar con colectores que nunca han corrido
            for key in self._collectors:
                if key not in status:
                    status[key] = {
                        "label":        self.COLLECTOR_LABELS.get(key, key),
                        "last_run":     None,
                        "last_status":  "never_run",
                        "last_records": 0,
                        "next_run":     None,
                        "is_running":   False,
                        "error_msg":    None,
                    }

        finally:
            conn.close()

        # Asignar próxima ejecución por job_id → colector
        job_to_collector = {
            "fred_daily":       "FREDCollector",
            "yahoo_market":     "YahooCollector",
            "yahoo_offmarket":  "YahooCollector",
            "europe_daily":     "EuropeCollector",
            "news_morning":     "NewsCollector",
            "news_evening":     "NewsCollector",
            "coingecko_30min":  "CoinGeckoCollector",
            "coingecko_daily":  "CoinGeckoCollector",
            "worldbank_weekly": "WorldBankCollector",
        }
        for job_id, collector_key in job_to_collector.items():
            nxt = next_runs.get(job_id)
            if nxt and collector_key in status:
                current = status[collector_key].get("next_run")
                # Toma la próxima más cercana
                if current is None or nxt < current:
                    status[collector_key]["next_run"] = nxt

        return {
            "collectors":   status,
            "started_at":   self._started_at,
            "is_running":   self._scheduler.running,
            "total_jobs":   len(jobs),
        }

    def run_collector_now(self, collector_name: str) -> bool:
        """
        Ejecuta inmediatamente un colector en un hilo separado.
        No espera a que termine — retorna True si el colector existe.
        """
        collector = self._collectors.get(collector_name)
        if not collector:
            logger.warning("[Scheduler] run_collector_now: '%s' no encontrado", collector_name)
            return False

        def _run():
            self._execute_collector(collector, "run_update", collector_name, "manual_update")

        t = threading.Thread(target=_run, daemon=True, name=f"manual_{collector_name}")
        t.start()
        logger.info("[Scheduler] Ejecución manual lanzada: %s", collector_name)
        return True

    # ─────────────────────────────────────────────────────────────────────────
    # Snapshot semanal
    # ─────────────────────────────────────────────────────────────────────────

    def take_weekly_snapshot(self) -> bool:
        """
        Guarda el estado completo de los indicadores clave en SnapshotHistory.
        Se ejecuta automáticamente cada domingo a las 23:59 UTC.
        """
        logger.info("[Scheduler] Iniciando snapshot semanal...")
        try:
            snapshot_data = self._collect_snapshot_data()
            today = date.today().isoformat()

            conn = sqlite3.connect(str(DB_PATH))
            try:
                conn.execute(
                    """INSERT OR REPLACE INTO SnapshotHistory
                       (snapshot_date, snapshot_data, created_at)
                       VALUES (?, ?, ?)""",
                    (today, json.dumps(snapshot_data, default=str), datetime.utcnow().isoformat()),
                )
                conn.commit()
                logger.info("[Scheduler] Snapshot semanal guardado para %s", today)
                return True
            finally:
                conn.close()

        except Exception as e:
            logger.error("[Scheduler] Error en snapshot semanal: %s", e)
            return False

    def _collect_snapshot_data(self) -> Dict[str, Any]:
        """Recoge los últimos valores de los indicadores clave desde SQLite."""
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row

        def latest(indicator_id: str, source: str = None) -> Optional[float]:
            """Devuelve el último valor de un indicador."""
            try:
                if source:
                    row = conn.execute(
                        """SELECT value FROM time_series
                           WHERE indicator_id = ? AND source = ?
                           ORDER BY timestamp DESC LIMIT 1""",
                        (indicator_id, source),
                    ).fetchone()
                else:
                    row = conn.execute(
                        """SELECT value FROM time_series
                           WHERE indicator_id = ?
                           ORDER BY timestamp DESC LIMIT 1""",
                        (indicator_id,),
                    ).fetchone()
                return float(row["value"]) if row and row["value"] is not None else None
            except Exception:
                return None

        try:
            snapshot = {
                "timestamp":         datetime.utcnow().isoformat(),
                # Mercados
                "sp500":             latest("yf_sp500_close"),
                "ibex35":            latest("yf_ibex35_close"),
                "vix":               latest("yf_vix_close"),
                # Política monetaria
                "fed_funds_rate":    latest("fred_fed_funds_us"),
                "bce_deposit_rate":  latest("ecb_deposit_rate_ea"),
                # Inflación
                "cpi_yoy_us":        latest("fred_cpi_yoy_us"),
                "hicp_ea":           latest("estat_hicp_cp00_ea20"),
                # Mercado laboral
                "unemployment_us":   latest("fred_unemployment_us"),
                "unemployment_es":   latest("estat_unemp_total_es"),
                # Curva de tipos y spreads
                "spread_10y2y_us":   latest("fred_spread_10y2y_us"),
                "spread_10y2y_calc": latest("fred_spread_10y2y_calc_us"),
                "risk_premium_es":   latest("ecb_spread_es_de"),
                # Materias primas
                "gold_usd":          latest("yf_gc_close"),
                "brent_usd":         latest("yf_bz_close"),
                # Crypto
                "bitcoin_usd":       latest("cg_btc_price_usd"),
                "fear_greed_crypto": latest("cg_fear_greed_value"),
                # Divisas
                "dxy":               latest("yf_dxy_close"),
                "eurusd":            latest("yf_eurusd_close"),
                # Geopolítica
                "gpr_global":        latest("fred_gpr_global"),
                # Estrés financiero
                "stlfsi":            latest("fred_stlfsi_us"),
                # Regla de Sahm
                "sahm_rule":         latest("fred_sahm_rule_us"),
            }
            return {k: v for k, v in snapshot.items()}
        finally:
            conn.close()

    def take_manual_snapshot(self, label: Optional[str] = None) -> bool:
        """
        Guarda un snapshot inmediato con etiqueta opcional.
        Usa datetime completo como clave para permitir múltiples snapshots por día.
        """
        logger.info("[Scheduler] Iniciando snapshot manual (label=%s)...", label)
        try:
            snapshot_data = self._collect_snapshot_data()
            if label:
                snapshot_data["label"] = label
            snapshot_data["trigger"] = "manual"
            now_str = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")

            conn = sqlite3.connect(str(DB_PATH))
            try:
                conn.execute(
                    """INSERT OR REPLACE INTO SnapshotHistory
                       (snapshot_date, snapshot_data, created_at)
                       VALUES (?, ?, ?)""",
                    (now_str, json.dumps(snapshot_data, default=str), datetime.utcnow().isoformat()),
                )
                conn.commit()
                logger.info("[Scheduler] Snapshot manual guardado: %s", now_str)
                return True
            finally:
                conn.close()
        except Exception as e:
            logger.error("[Scheduler] Error en snapshot manual: %s", e)
            return False

    def get_snapshots(self, limit: int = 50) -> list:
        """Devuelve los snapshots más recientes de SnapshotHistory."""
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """SELECT id, snapshot_date, snapshot_data, created_at
                   FROM SnapshotHistory
                   ORDER BY snapshot_date DESC
                   LIMIT ?""",
                (limit,),
            ).fetchall()
            result = []
            for row in rows:
                try:
                    data = json.loads(row["snapshot_data"])
                except Exception:
                    data = {}
                result.append({
                    "id": row["id"],
                    "snapshot_date": row["snapshot_date"],
                    "label": data.get("label", ""),
                    "trigger": data.get("trigger", "scheduled"),
                    "created_at": row["created_at"],
                    "data": data,
                })
            return result
        finally:
            conn.close()

    # ─────────────────────────────────────────────────────────────────────────
    # Estadísticas del log
    # ─────────────────────────────────────────────────────────────────────────

    def get_log_stats_24h(self) -> Dict[str, int]:
        """Devuelve conteo de ejecuciones exitosas y fallidas en las últimas 24h."""
        since = (datetime.utcnow() - timedelta(hours=24)).isoformat()
        conn = sqlite3.connect(str(DB_PATH))
        try:
            rows = conn.execute(
                """SELECT status, COUNT(*) AS cnt
                   FROM SchedulerLog
                   WHERE started_at >= ?
                   GROUP BY status""",
                (since,),
            ).fetchall()
            counts = {"success": 0, "error": 0, "running": 0}
            for row in rows:
                st = row[0] if row[0] else "unknown"
                counts[st] = row[1]
            return counts
        finally:
            conn.close()

    def get_db_stats(self) -> Dict[str, Any]:
        """Devuelve estadísticas de la base de datos (total registros, tamaño)."""
        import os
        stats: Dict[str, Any] = {"total_records": 0, "db_size_mb": 0.0}
        try:
            db_path = str(DB_PATH)
            if os.path.exists(db_path):
                stats["db_size_mb"] = round(os.path.getsize(db_path) / 1_048_576, 2)
            conn = sqlite3.connect(db_path)
            try:
                row = conn.execute("SELECT COUNT(*) FROM time_series").fetchone()
                stats["total_records"] = row[0] if row else 0
            finally:
                conn.close()
        except Exception as e:
            logger.warning("[Scheduler] get_db_stats error: %s", e)
        return stats
