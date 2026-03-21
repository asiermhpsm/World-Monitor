"""
AlertManager — sistema de alertas visuales del World Monitor.

Gestiona umbrales sobre indicadores clave. Cuando un indicador cruza
su umbral configurado, crea una entrada en AlertHistory visible en el
dashboard. Solo alertas visuales internas (no externas).

Tablas propias en SQLite:
  - AlertConfig   : configuración de cada alerta
  - AlertHistory  : historial de disparos
"""

import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from config import DB_PATH

logger = logging.getLogger(__name__)


# ── Alertas por defecto ───────────────────────────────────────────────────────

DEFAULT_ALERTS = [
    # VIX
    {
        "indicator_name": "VIX",
        "series_id":      "yf_vix_close",
        "condition":      "above",
        "threshold":      30.0,
        "severity":       "warning",
        "message_template": "VIX en {value:.1f} — Volatilidad elevada en mercados americanos",
    },
    {
        "indicator_name": "VIX",
        "series_id":      "yf_vix_close",
        "condition":      "above",
        "threshold":      40.0,
        "severity":       "critical",
        "message_template": "VIX en {value:.1f} — Pánico en mercados. Nivel de crisis.",
    },
    # Curva de tipos (spread 10y-2y)
    {
        "indicator_name": "T10Y2Y (Spread Curva)",
        "series_id":      "fred_spread_10y2y_us",
        "condition":      "below",
        "threshold":      0.0,
        "severity":       "warning",
        "message_template": "Curva de tipos invertida: spread 10y-2y en {value:.2f}%. Señal histórica de recesión.",
    },
    {
        "indicator_name": "T10Y2Y (Spread Curva)",
        "series_id":      "fred_spread_10y2y_us",
        "condition":      "below",
        "threshold":      -0.5,
        "severity":       "critical",
        "message_template": "Curva de tipos muy invertida: {value:.2f}%. Señal de recesión severa.",
    },
    # Inflación EE.UU.
    {
        "indicator_name": "Inflación EE.UU. (CPI YoY)",
        "series_id":      "fred_cpi_yoy_us",
        "condition":      "above",
        "threshold":      4.0,
        "severity":       "warning",
        "message_template": "Inflación EE.UU. en {value:.1f}% — Por encima del umbral de alerta",
    },
    # Prima de riesgo España
    {
        "indicator_name": "Prima de Riesgo España",
        "series_id":      "ecb_spread_es_de",
        "condition":      "above",
        "threshold":      150.0,
        "severity":       "warning",
        "message_template": "Prima de riesgo España en {value:.0f} pb — Nivel de atención",
    },
    {
        "indicator_name": "Prima de Riesgo España",
        "series_id":      "ecb_spread_es_de",
        "condition":      "above",
        "threshold":      250.0,
        "severity":       "critical",
        "message_template": "Prima de riesgo España en {value:.0f} pb — Nivel crítico",
    },
    # Prima de riesgo Italia
    {
        "indicator_name": "Prima de Riesgo Italia",
        "series_id":      "ecb_spread_it_de",
        "condition":      "above",
        "threshold":      200.0,
        "severity":       "warning",
        "message_template": "Prima de riesgo Italia en {value:.0f} pb — Nivel de atención",
    },
    # Petróleo Brent
    {
        "indicator_name": "Petróleo Brent",
        "series_id":      "yf_bz_close",
        "condition":      "above",
        "threshold":      100.0,
        "severity":       "warning",
        "message_template": "Petróleo Brent en {value:.0f} USD — Nivel de shock energético",
    },
    # GPR global
    {
        "indicator_name": "GPR Global",
        "series_id":      "fred_gpr_global",
        "condition":      "above",
        "threshold":      200.0,
        "severity":       "critical",
        "message_template": "Índice de Riesgo Geopolítico en {value:.0f} — Nivel de crisis histórica",
    },
    # Fear & Greed crypto
    {
        "indicator_name": "Fear & Greed Crypto",
        "series_id":      "cg_fear_greed_value",
        "condition":      "below",
        "threshold":      20.0,
        "severity":       "warning",
        "message_template": "Fear & Greed crypto en {value:.0f} — Miedo extremo en mercados crypto",
    },
    # DXY
    {
        "indicator_name": "DXY (Índice Dólar)",
        "series_id":      "yf_dxy_close",
        "condition":      "above",
        "threshold":      110.0,
        "severity":       "warning",
        "message_template": "Dólar muy fuerte (DXY {value:.1f}) — Presión sobre mercados emergentes",
    },
]


class AlertManager:
    """
    Gestiona las alertas visuales del World Monitor.

    Las alertas se evalúan comparando el último valor de cada indicador
    con su umbral configurado en AlertConfig. Los disparos se registran
    en AlertHistory y son visibles en el dashboard.
    """

    def __init__(self):
        self._init_db()
        self._load_default_alerts()

    # ─────────────────────────────────────────────────────────────────────────
    # Inicialización
    # ─────────────────────────────────────────────────────────────────────────

    def _init_db(self):
        """Crea las tablas AlertConfig y AlertHistory si no existen."""
        conn = sqlite3.connect(str(DB_PATH))
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS AlertConfig (
                    id                INTEGER PRIMARY KEY AUTOINCREMENT,
                    indicator_name    TEXT NOT NULL,
                    series_id         TEXT NOT NULL,
                    condition         TEXT NOT NULL,
                    threshold         REAL NOT NULL,
                    severity          TEXT NOT NULL DEFAULT 'warning',
                    message_template  TEXT NOT NULL,
                    is_active         INTEGER NOT NULL DEFAULT 1,
                    created_at        TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS AlertHistory (
                    id                INTEGER PRIMARY KEY AUTOINCREMENT,
                    alert_config_id   INTEGER NOT NULL,
                    triggered_at      TEXT NOT NULL,
                    value_at_trigger  REAL NOT NULL,
                    message           TEXT NOT NULL,
                    is_read           INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY (alert_config_id) REFERENCES AlertConfig(id)
                );

                CREATE INDEX IF NOT EXISTS ix_alert_history_triggered
                    ON AlertHistory(triggered_at);
                CREATE INDEX IF NOT EXISTS ix_alert_history_read
                    ON AlertHistory(is_read);
            """)
            conn.commit()
        finally:
            conn.close()

    def _load_default_alerts(self):
        """Carga las alertas por defecto si AlertConfig está vacía."""
        conn = sqlite3.connect(str(DB_PATH))
        try:
            count = conn.execute("SELECT COUNT(*) FROM AlertConfig").fetchone()[0]
            if count > 0:
                return

            for alert in DEFAULT_ALERTS:
                conn.execute(
                    """INSERT INTO AlertConfig
                       (indicator_name, series_id, condition, threshold,
                        severity, message_template, is_active)
                       VALUES (?, ?, ?, ?, ?, ?, 1)""",
                    (
                        alert["indicator_name"],
                        alert["series_id"],
                        alert["condition"],
                        alert["threshold"],
                        alert["severity"],
                        alert["message_template"],
                    ),
                )
            conn.commit()
            logger.info("[AlertManager] %d alertas por defecto cargadas.", len(DEFAULT_ALERTS))
        finally:
            conn.close()

    # ─────────────────────────────────────────────────────────────────────────
    # Evaluación de alertas
    # ─────────────────────────────────────────────────────────────────────────

    def check_all_alerts(self) -> List[Dict[str, Any]]:
        """
        Evalúa todos los AlertConfig activos contra el último valor
        de su indicador en time_series.

        Devuelve lista de alertas disparadas en esta ejecución.
        No duplica alertas: solo dispara si no hay un disparo idéntico
        en las últimas 6 horas (evita spam).
        """
        fired: List[Dict[str, Any]] = []
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row

        try:
            configs = conn.execute(
                "SELECT * FROM AlertConfig WHERE is_active = 1"
            ).fetchall()

            for cfg in configs:
                try:
                    # Obtener último valor del indicador
                    row = conn.execute(
                        """SELECT value FROM time_series
                           WHERE indicator_id = ?
                           ORDER BY timestamp DESC LIMIT 1""",
                        (cfg["series_id"],),
                    ).fetchone()

                    if row is None or row["value"] is None:
                        continue

                    value = float(row["value"])

                    # Evaluar condición
                    triggered = self._evaluate(
                        value, cfg["condition"], float(cfg["threshold"])
                    )
                    if not triggered:
                        continue

                    # Anti-spam: no disparar si ya se disparó en las últimas 6h
                    since_6h = (datetime.utcnow() - timedelta(hours=6)).isoformat()
                    existing = conn.execute(
                        """SELECT id FROM AlertHistory
                           WHERE alert_config_id = ? AND triggered_at >= ?""",
                        (cfg["id"], since_6h),
                    ).fetchone()
                    if existing:
                        continue

                    # Formatear mensaje
                    message = cfg["message_template"].format(
                        value=value, threshold=float(cfg["threshold"])
                    )

                    # Insertar en AlertHistory
                    conn.execute(
                        """INSERT INTO AlertHistory
                           (alert_config_id, triggered_at, value_at_trigger, message, is_read)
                           VALUES (?, ?, ?, ?, 0)""",
                        (cfg["id"], datetime.utcnow().isoformat(), value, message),
                    )
                    conn.commit()

                    fired.append({
                        "indicator": cfg["indicator_name"],
                        "severity":  cfg["severity"],
                        "message":   message,
                        "value":     value,
                    })
                    logger.info(
                        "[AlertManager] ALERTA [%s] %s — valor: %.2f",
                        cfg["severity"], cfg["indicator_name"], value
                    )

                except Exception as e:
                    logger.warning(
                        "[AlertManager] Error evaluando alerta %s: %s",
                        cfg.get("indicator_name", "?"), e
                    )

        finally:
            conn.close()

        return fired

    @staticmethod
    def _evaluate(value: float, condition: str, threshold: float) -> bool:
        """Evalúa si value cumple la condición respecto al threshold."""
        if condition == "above":
            return value > threshold
        elif condition == "below":
            return value < threshold
        elif condition == "change_pct_above":
            return value > threshold
        elif condition == "change_pct_below":
            return value < threshold
        return False

    # ─────────────────────────────────────────────────────────────────────────
    # Consultas públicas
    # ─────────────────────────────────────────────────────────────────────────

    def get_active_alerts(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Devuelve las alertas no leídas de las últimas `hours` horas,
        ordenadas por severidad (critical primero) y fecha descendente.
        """
        since = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """SELECT h.id,
                          h.triggered_at,
                          h.value_at_trigger,
                          h.message,
                          h.is_read,
                          c.indicator_name,
                          c.severity,
                          c.series_id
                   FROM   AlertHistory h
                   JOIN   AlertConfig  c ON c.id = h.alert_config_id
                   WHERE  h.is_read = 0
                     AND  h.triggered_at >= ?
                   ORDER  BY
                          CASE c.severity
                            WHEN 'critical' THEN 1
                            WHEN 'warning'  THEN 2
                            ELSE 3
                          END,
                          h.triggered_at DESC""",
                (since,),
            ).fetchall()

            return [dict(row) for row in rows]
        finally:
            conn.close()

    def mark_as_read(self, alert_id: int) -> bool:
        """Marca una alerta de AlertHistory como leída."""
        conn = sqlite3.connect(str(DB_PATH))
        try:
            conn.execute(
                "UPDATE AlertHistory SET is_read = 1 WHERE id = ?", (alert_id,)
            )
            conn.commit()
            return True
        except Exception as e:
            logger.warning("[AlertManager] mark_as_read error: %s", e)
            return False
        finally:
            conn.close()

    def mark_all_as_read(self) -> int:
        """Marca todas las alertas no leídas como leídas. Devuelve cuántas."""
        conn = sqlite3.connect(str(DB_PATH))
        try:
            cur = conn.execute("UPDATE AlertHistory SET is_read = 1 WHERE is_read = 0")
            conn.commit()
            return cur.rowcount
        finally:
            conn.close()

    def add_alert(
        self,
        indicator_name: str,
        series_id: str,
        condition: str,
        threshold: float,
        severity: str,
        message_template: str,
    ) -> int:
        """
        Añade una nueva alerta a AlertConfig.
        Devuelve el id del nuevo registro.
        """
        conn = sqlite3.connect(str(DB_PATH))
        try:
            cur = conn.execute(
                """INSERT INTO AlertConfig
                   (indicator_name, series_id, condition, threshold,
                    severity, message_template, is_active)
                   VALUES (?, ?, ?, ?, ?, ?, 1)""",
                (indicator_name, series_id, condition, threshold, severity, message_template),
            )
            conn.commit()
            logger.info("[AlertManager] Alerta añadida: %s %s %.2f", indicator_name, condition, threshold)
            return cur.lastrowid
        finally:
            conn.close()

    def get_all_configs(self) -> List[Dict[str, Any]]:
        """Devuelve todos los AlertConfig (activos e inactivos)."""
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute("SELECT * FROM AlertConfig ORDER BY severity, indicator_name").fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()
