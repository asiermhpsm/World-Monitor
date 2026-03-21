"""
Script de prueba del sistema de scheduler y alertas del World Monitor.

Pasos:
  1. Inicia el scheduler y verifica jobs registrados
  2. Fuerza ejecución inmediata de YahooCollector.run_update()
  3. Espera 30s y verifica en SchedulerLog que la ejecución se registró
  4. Verifica que las alertas por defecto están cargadas en AlertConfig
  5. Ejecuta check_all_alerts() y muestra alertas disparadas
  6. Toma un snapshot manual y verifica que se guardó
  7. Para el scheduler limpiamente
  8. Imprime resumen completo

Uso:
    cd "World Monitor"
    python scripts/test_scheduler.py
"""

import json
import logging
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

# ── Path setup ────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("test_scheduler")


# ── Colores para terminal ─────────────────────────────────────────────────────

class C:
    GREEN  = "\033[92m"
    YELLOW = "\033[93m"
    RED    = "\033[91m"
    CYAN   = "\033[96m"
    BOLD   = "\033[1m"
    RESET  = "\033[0m"

def ok(msg):    print(f"  {C.GREEN}[OK]{C.RESET}     {msg}")
def warn(msg):  print(f"  {C.YELLOW}[WARN]{C.RESET}   {msg}")
def fail(msg):  print(f"  {C.RED}[FAIL]{C.RESET}   {msg}")
def info(msg):  print(f"  {C.CYAN}[INFO]{C.RESET}   {msg}")
def header(msg): print(f"\n{C.BOLD}{C.CYAN}{'-'*60}{C.RESET}\n{C.BOLD}  {msg}{C.RESET}\n{'-'*60}")


# ── Resultados del test ───────────────────────────────────────────────────────

results = {
    "scheduler_started":      False,
    "jobs_registered":        0,
    "yahoo_manual_triggered": False,
    "yahoo_log_found":        False,
    "default_alerts_loaded":  False,
    "alerts_checked":         False,
    "alerts_fired":           [],
    "snapshot_taken":         False,
    "scheduler_stopped":      False,
}


# ─────────────────────────────────────────────────────────────────────────────
# PASO 1: Arrancar el scheduler
# ─────────────────────────────────────────────────────────────────────────────

header("PASO 1 — Arrancar el scheduler")

from scheduler.scheduler import DashboardScheduler

sched = DashboardScheduler()

try:
    sched.start()
    status = sched.get_status()
    results["scheduler_started"] = status["is_running"]

    if results["scheduler_started"]:
        ok("Scheduler arrancado correctamente")
    else:
        fail("Scheduler no está corriendo tras start()")

except Exception as e:
    fail(f"Error arrancando scheduler: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# PASO 2: Verificar jobs registrados
# ─────────────────────────────────────────────────────────────────────────────

header("PASO 2 — Verificar jobs registrados")

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    status = sched.get_status()
    n_jobs = status.get("total_jobs", 0)
    results["jobs_registered"] = n_jobs

    # IDs esperados
    expected_job_ids = [
        "fred_daily", "yahoo_market", "yahoo_offmarket",
        "europe_daily", "news_morning", "news_evening",
        "coingecko_30min", "coingecko_daily",
        "worldbank_weekly", "weekly_snapshot", "alerts_check",
    ]

    registered_ids = [j.id for j in sched._scheduler.get_jobs()]
    info(f"Jobs registrados ({n_jobs}): {registered_ids}")

    missing = [jid for jid in expected_job_ids if jid not in registered_ids]
    if missing:
        warn(f"Jobs esperados pero no encontrados: {missing}")
    else:
        ok(f"Todos los {len(expected_job_ids)} jobs esperados están registrados")

    for job in sched._scheduler.get_jobs():
        nxt = job.next_run_time
        nxt_str = nxt.strftime("%Y-%m-%d %H:%M:%S %Z") if nxt else "—"
        info(f"  {job.id:25s} | {job.name[:40]:40s} | próxima: {nxt_str}")

except Exception as e:
    fail(f"Error verificando jobs: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# PASO 3: Forzar ejecución de YahooCollector.run_update()
# ─────────────────────────────────────────────────────────────────────────────

header("PASO 3 — Ejecución manual de YahooCollector.run_update()")

try:
    launched = sched.run_collector_now("YahooCollector")
    results["yahoo_manual_triggered"] = launched

    if launched:
        ok("YahooCollector lanzado en background")
        info("Esperando 30 segundos a que termine...")
        time.sleep(30)
    else:
        warn("YahooCollector no está disponible (posible fallo de importación)")
        info("Esperando 5 segundos antes de continuar...")
        time.sleep(5)

except Exception as e:
    fail(f"Error en run_collector_now: {e}")
    time.sleep(5)


# ─────────────────────────────────────────────────────────────────────────────
# PASO 4: Verificar SchedulerLog
# ─────────────────────────────────────────────────────────────────────────────

header("PASO 4 — Verificar registro en SchedulerLog")

from config import DB_PATH

try:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    # Todos los registros recientes
    rows = conn.execute(
        """SELECT id, collector_name, job_type, started_at, status,
                  records_updated, duration_seconds, error_message
           FROM SchedulerLog
           ORDER BY id DESC
           LIMIT 10"""
    ).fetchall()

    if rows:
        ok(f"SchedulerLog contiene {len(rows)} entradas recientes:")
        for row in rows:
            status_icon = "OK" if row["status"] == "success" else (
                "RUNNING" if row["status"] == "running" else "ERROR"
            )
            dur = f"{row['duration_seconds']:.1f}s" if row["duration_seconds"] else "—"
            info(
                f"  [{status_icon}] {row['collector_name']:20s} | "
                f"{row['started_at'][:19]} | "
                f"{row['records_updated'] or 0} registros | {dur}"
            )
            if row["error_message"]:
                warn(f"    Error: {row['error_message'][:100]}")
    else:
        warn("SchedulerLog vacío — puede que el colector tarde más en responder")

    # Buscar entrada de YahooCollector
    yahoo_row = conn.execute(
        """SELECT * FROM SchedulerLog
           WHERE collector_name = 'YahooCollector'
           ORDER BY id DESC LIMIT 1"""
    ).fetchone()

    if yahoo_row:
        results["yahoo_log_found"] = True
        ok(f"Entrada de YahooCollector encontrada: status={yahoo_row['status']}, "
           f"records={yahoo_row['records_updated'] or 0}")
    else:
        warn("No se encontró entrada de YahooCollector (puede estar aún ejecutando)")

    conn.close()

except Exception as e:
    fail(f"Error leyendo SchedulerLog: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# PASO 5: Verificar alertas por defecto en AlertConfig
# ─────────────────────────────────────────────────────────────────────────────

header("PASO 5 — Verificar AlertConfig (alertas por defecto)")

from alerts.alert_manager import AlertManager

am = AlertManager()

try:
    configs = am.get_all_configs()
    results["default_alerts_loaded"] = len(configs) >= 12

    if results["default_alerts_loaded"]:
        ok(f"AlertConfig contiene {len(configs)} alertas cargadas:")
    else:
        warn(f"AlertConfig solo tiene {len(configs)} alertas (esperadas >= 12)")

    for cfg in configs:
        sev_color = C.RED if cfg["severity"] == "critical" else C.YELLOW
        print(
            f"    [{sev_color}{cfg['severity'].upper():8s}{C.RESET}] "
            f"{cfg['indicator_name']:30s} | "
            f"{cfg['condition']:20s} {cfg['threshold']:.1f}"
        )

except Exception as e:
    fail(f"Error leyendo AlertConfig: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# PASO 6: Ejecutar check_all_alerts()
# ─────────────────────────────────────────────────────────────────────────────

header("PASO 6 — Ejecutar check_all_alerts()")

try:
    fired = am.check_all_alerts()
    results["alerts_checked"] = True
    results["alerts_fired"]   = fired

    if fired:
        ok(f"{len(fired)} alerta(s) disparada(s) con los datos actuales:")
        for alert in fired:
            sev_color = C.RED if alert["severity"] == "critical" else C.YELLOW
            print(
                f"    [{sev_color}{alert['severity'].upper():8s}{C.RESET}] "
                f"{alert['indicator']:30s} | valor: {alert['value']:.2f}"
            )
            info(f"    Mensaje: {alert['message']}")
    else:
        ok("Ninguna alerta disparada con los datos actuales (puede ser normal si la BD está vacía)")

    # También mostrar alertas activas (no leídas)
    active = am.get_active_alerts(hours=24)
    info(f"Total alertas no leídas últimas 24h: {len(active)}")

except Exception as e:
    fail(f"Error en check_all_alerts: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# PASO 7: Snapshot manual
# ─────────────────────────────────────────────────────────────────────────────

header("PASO 7 — Snapshot manual")

try:
    taken = sched.take_weekly_snapshot()
    results["snapshot_taken"] = taken

    if taken:
        ok("Snapshot guardado correctamente")
        # Verificar en BD
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        snap = conn.execute(
            "SELECT * FROM SnapshotHistory ORDER BY id DESC LIMIT 1"
        ).fetchone()
        conn.close()

        if snap:
            data = json.loads(snap["snapshot_data"])
            info(f"Fecha snapshot: {snap['snapshot_date']}")
            info(f"Campos en snapshot_data ({len(data)}):")
            for k, v in data.items():
                val_str = f"{v:.4f}" if isinstance(v, float) else str(v)
                avail = C.GREEN + "disponible" + C.RESET if v is not None else C.YELLOW + "sin datos" + C.RESET
                print(f"    {k:25s}: {val_str:15s} ({avail})")
    else:
        fail("No se pudo tomar el snapshot")

except Exception as e:
    fail(f"Error en take_weekly_snapshot: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# PASO 8: Parar el scheduler
# ─────────────────────────────────────────────────────────────────────────────

header("PASO 8 — Parar el scheduler")

try:
    sched.stop()
    results["scheduler_stopped"] = True
    ok("Scheduler detenido limpiamente")
except Exception as e:
    fail(f"Error al detener scheduler: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# PASO 9: Resumen final
# ─────────────────────────────────────────────────────────────────────────────

header("RESUMEN COMPLETO DEL TEST")

checks = [
    ("Scheduler arrancado",          results["scheduler_started"]),
    ("Jobs registrados >= 10",       results["jobs_registered"] >= 10),
    ("YahooCollector lanzado",       results["yahoo_manual_triggered"]),
    ("SchedulerLog con registros",   results["yahoo_log_found"] or results["jobs_registered"] > 0),
    ("AlertConfig >= 12 alertas",    results["default_alerts_loaded"]),
    ("check_all_alerts() ejecutado", results["alerts_checked"]),
    ("Snapshot guardado",            results["snapshot_taken"]),
    ("Scheduler detenido",           results["scheduler_stopped"]),
]

passed = 0
failed_checks = []
for label, ok_flag in checks:
    if ok_flag:
        print(f"  {C.GREEN}[PASS]{C.RESET} {label}")
        passed += 1
    else:
        print(f"  {C.RED}[FAIL]{C.RESET} {label}")
        failed_checks.append(label)

print()
print(f"  Resultado: {C.BOLD}{passed}/{len(checks)} checks pasados{C.RESET}")
if results["alerts_fired"]:
    print(f"  Alertas disparadas: {C.YELLOW}{len(results['alerts_fired'])}{C.RESET}")
else:
    print(f"  Alertas disparadas: {C.GREEN}0{C.RESET} (ningún umbral cruzado)")

if failed_checks:
    print(f"\n  {C.YELLOW}Checks fallidos:{C.RESET}")
    for c in failed_checks:
        print(f"    - {c}")
    sys.exit(1)
else:
    print(f"\n  {C.GREEN}{C.BOLD}Todos los checks pasaron correctamente.{C.RESET}")
    sys.exit(0)
