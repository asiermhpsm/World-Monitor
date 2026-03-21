"""
Esquema SQLAlchemy completo para World Monitor.

Tablas:
  - time_series      : series temporales de todos los indicadores
  - snapshots        : estado completo del dashboard (Módulo 14)
  - events           : línea de tiempo anotada (Módulos 1 y 14)
  - alerts           : alertas configuradas por umbral (Módulo 17)
  - ai_analyses      : análisis guardados del Módulo 15
  - annotations      : notas de usuario por indicador/fecha (Módulo 17)
  - scenarios        : log de predicciones/escenarios (Módulo 14)
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config import DATABASE_URL


class Base(DeclarativeBase):
    pass


# ── 1. Series temporales ──────────────────────────────────────────────────────

class TimeSeries(Base):
    """
    Tabla central. Almacena todos los valores de todos los indicadores.

    indicator_id: identificador canónico del indicador, ej: 'fred_cpi_yoy_us'
    source: colector que lo generó, ej: 'fred', 'yfinance', 'worldbank'
    region: código ISO o región, ej: 'US', 'EA', 'DE'
    unit: 'pct', 'usd', 'eur', 'index', 'ratio', 'count'
    """
    __tablename__ = "time_series"

    id = Column(Integer, primary_key=True, autoincrement=True)
    indicator_id = Column(String(128), nullable=False)
    source = Column(String(64), nullable=False)
    region = Column(String(16), nullable=True)
    timestamp = Column(DateTime, nullable=False)
    value = Column(Float, nullable=True)
    unit = Column(String(32), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_ts_indicator_timestamp", "indicator_id", "timestamp"),
        Index("ix_ts_source", "source"),
        Index("ix_ts_region", "region"),
    )

    def __repr__(self):
        return f"<TimeSeries {self.indicator_id} @ {self.timestamp} = {self.value}>"


# ── 2. Snapshots completos (Módulo 14) ────────────────────────────────────────

class Snapshot(Base):
    """
    Guarda el estado completo del dashboard en un momento dado.
    El campo `data_json` contiene un JSON con todos los indicadores del momento.
    Se genera automáticamente cada domingo a las 23:59 y tras cada actualización.
    """
    __tablename__ = "snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    label = Column(String(256), nullable=True)           # Etiqueta descriptiva opcional
    trigger = Column(String(64), nullable=True)          # 'scheduled', 'manual', 'auto'
    data_json = Column(Text, nullable=False)             # JSON con todos los valores
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Snapshot {self.timestamp} [{self.trigger}]>"


# ── 3. Eventos de la línea de tiempo (Módulos 1 y 14) ────────────────────────

class Event(Base):
    """
    Eventos históricos para la línea de tiempo anotada.
    Impacto en mercados medido 48h tras el evento.
    """
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(DateTime, nullable=False, index=True)
    title = Column(String(512), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(64), nullable=True)         # 'macro', 'monetary', 'geopolitical', 'market', 'energy'
    region = Column(String(64), nullable=True)
    severity = Column(String(16), nullable=True)         # 'low', 'medium', 'high', 'critical'
    market_impact_48h = Column(Text, nullable=True)      # JSON con impacto por activo
    source = Column(String(128), nullable=True)          # URL o fuente del evento
    is_manual = Column(Boolean, default=False)           # True si fue añadido por el usuario
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Event '{self.title}' @ {self.date}>"


# ── 4. Alertas (Módulo 17) ────────────────────────────────────────────────────

class Alert(Base):
    """
    Alertas configuradas por el usuario para un indicador y umbral dados.
    Se evalúan en cada actualización del colector correspondiente.
    """
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    indicator_id = Column(String(128), nullable=False)
    label = Column(String(256), nullable=True)
    condition = Column(String(16), nullable=False)       # 'above', 'below', 'change_pct'
    threshold = Column(Float, nullable=False)
    is_active = Column(Boolean, default=True)
    notify_sound = Column(Boolean, default=False)
    last_triggered = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_alerts_indicator", "indicator_id"),
    )

    def __repr__(self):
        return f"<Alert {self.indicator_id} {self.condition} {self.threshold}>"


# ── 5. Análisis IA (Módulo 15) ────────────────────────────────────────────────

class AIAnalysis(Base):
    """
    Historial de análisis generados por Claude.
    Guarda el prompt, el modo, los datos de contexto y la respuesta completa.
    """
    __tablename__ = "ai_analyses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    mode = Column(String(64), nullable=False)            # 'full_analysis', 'external_text', 'chat', 'scenario'
    title = Column(String(512), nullable=True)
    context_json = Column(Text, nullable=True)           # JSON con datos del dashboard en ese momento
    prompt = Column(Text, nullable=True)                 # Prompt enviado a Claude
    response = Column(Text, nullable=False)              # Respuesta de Claude
    model = Column(String(128), nullable=True)           # Modelo Claude usado
    tokens_used = Column(Integer, nullable=True)

    def __repr__(self):
        return f"<AIAnalysis [{self.mode}] @ {self.timestamp}>"


# ── 6. Anotaciones de usuario (Módulo 17) ────────────────────────────────────

class Annotation(Base):
    """
    Notas libres que el usuario puede añadir a cualquier indicador o fecha.
    """
    __tablename__ = "annotations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    indicator_id = Column(String(128), nullable=True)    # None = anotación global
    date = Column(DateTime, nullable=True)
    title = Column(String(256), nullable=True)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Annotation {self.indicator_id} @ {self.date}>"


# ── 7. Escenarios / Predicciones (Módulo 14) ─────────────────────────────────

class Scenario(Base):
    """
    Log de predicciones y escenarios con seguimiento posterior.
    """
    __tablename__ = "scenarios"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    title = Column(String(512), nullable=False)
    description = Column(Text, nullable=True)
    probability = Column(Float, nullable=True)           # 0.0 - 1.0
    conditions = Column(Text, nullable=True)             # Condiciones necesarias (texto libre)
    target_date = Column(DateTime, nullable=True)        # Fecha objetivo de la predicción
    outcome = Column(String(64), nullable=True)          # 'pending', 'correct', 'incorrect', 'partial'
    outcome_notes = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<Scenario '{self.title}' prob={self.probability}>"


# ── 8. Artículos de noticias (NewsCollector / Módulo 10) ──────────────────────

class NewsArticle(Base):
    """
    Artículos de noticias clasificados y puntuados por relevancia financiera.

    url: clave única — evita duplicados entre ejecuciones.
    impact_score: 0.0 – 1.0 calculado por coincidencia de keywords críticas/relevantes.
    category: macro | markets | geopolitics | energy | crypto | central_banks
    region: US | EU | China | Japan | Middle_East | Russia_Ukraine | Emerging_Markets | Global
    """
    __tablename__ = "news_articles"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    title           = Column(String(500), nullable=False)
    description     = Column(String(1000), nullable=True)
    url             = Column(String(500), nullable=False)
    source_name     = Column(String(100), nullable=True)
    published_at    = Column(DateTime, nullable=True)
    category        = Column(String(50), nullable=True)
    region          = Column(String(50), nullable=True)
    impact_score    = Column(Float, nullable=True, default=0.0)
    keywords_matched = Column(String(200), nullable=True)
    created_at      = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("url", name="uq_news_articles_url"),
        Index("ix_news_articles_impact", "impact_score"),
        Index("ix_news_articles_published", "published_at"),
        Index("ix_news_articles_category", "category"),
    )

    def __repr__(self):
        return f"<NewsArticle '{self.title[:50]}' score={self.impact_score}>"


# ── 9. Eventos geopolíticos (NewsCollector / Módulo 10) ───────────────────────

class GeopoliticalEvent(Base):
    """
    Eventos geopolíticos relevantes para los mercados financieros.

    Pueden generarse automáticamente (is_manual=False) a partir de artículos
    de alto impacto, o añadirse manualmente por el usuario (is_manual=True).
    severity: 1=menor, 2=moderado, 3=significativo, 4=alto, 5=crítico
    """
    __tablename__ = "geopolitical_events"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    date          = Column(DateTime, nullable=False)
    title         = Column(String(300), nullable=False)
    description   = Column(String(1000), nullable=True)
    category      = Column(String(50), nullable=True)   # conflict, sanction, election, trade_war, energy, financial_crisis
    region        = Column(String(100), nullable=True)
    severity      = Column(Integer, nullable=True)       # 1-5
    market_impact = Column(String(200), nullable=True)
    source_url    = Column(String(500), nullable=True)
    is_manual     = Column(Boolean, default=False)
    created_at    = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_geopolitical_events_date",     "date"),
        Index("ix_geopolitical_events_severity", "severity"),
        Index("ix_geopolitical_events_created",  "created_at"),
    )

    def __repr__(self):
        return f"<GeopoliticalEvent '{self.title[:50]}' sev={self.severity}>"


# ── Engine y Session factory ──────────────────────────────────────────────────

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},   # Necesario para SQLite con Dash
    echo=False,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    """Dependency para obtener una sesión de base de datos."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
