# World Monitor — Arquitectura del Proyecto

> **Leer este fichero al inicio de cada sesión para recuperar el contexto completo.**

---

## Estructura de Carpetas

```
World Monitor/
│
├── app.py                  # Punto de entrada. Arranca Dash con sidebar y layout base.
├── config.py               # Gestión centralizada de configuración (API keys, rutas, constantes).
├── requirements.txt        # Dependencias Python del proyecto completo.
│
├── database/
│   ├── database.py         # Esquema SQLAlchemy completo (todas las tablas).
│   └── init_db.py          # Script de inicialización: crea las tablas en SQLite.
│
├── collectors/             # Un fichero por fuente de datos. Responsable de fetch + parse.
│   ├── fred_collector.py         # FRED API → macro EE.UU., tipos, inflación, empleo
│   ├── yfinance_collector.py     # Yahoo Finance → índices, divisas, materias primas, crypto
│   ├── worldbank_collector.py    # World Bank API → macro global todos los países
│   ├── ecb_collector.py          # ECB Data Portal → tipos BCE, datos europeos
│   ├── eurostat_collector.py     # Eurostat API → macro Europa detallada
│   ├── coingecko_collector.py    # CoinGecko → precios y métricas crypto
│   ├── newsapi_collector.py      # NewsAPI → noticias financieras recientes
│   └── gdelt_collector.py        # GDELT → tensión geopolítica global
│
├── modules/                # Un fichero por módulo del dashboard. Retorna layout Dash.
│   ├── m01_estado_global.py
│   ├── m02_macro_global.py
│   ├── m03_inflacion.py
│   ├── m04_politica_monetaria.py
│   ├── m05_mercados.py
│   ├── m06_mercado_laboral.py
│   ├── m07_energia_materias_primas.py
│   ├── m08_deuda_fiscal.py
│   ├── m09_sistema_financiero.py
│   ├── m10_geopolitica.py
│   ├── m11_indicadores_adelantados.py
│   ├── m12_china.py
│   ├── m13_demografia.py
│   ├── m14_historico.py
│   ├── m15_ia.py
│   ├── m16_mercados_submercados.py
│   └── m17_personalizacion.py
│
├── scheduler/
│   └── jobs.py             # APScheduler: define los jobs de refresco periódico.
│
├── assets/
│   └── custom.css          # Overrides CSS para el tema oscuro Bloomberg.
│
├── .env                    # Variables de entorno reales (NO subir a git).
├── .env.example            # Plantilla con nombres y descripciones (SÍ subir a git).
├── .gitignore
└── world_monitor.db        # Base de datos SQLite (generada en runtime, NO subir a git).
```

---

## Decisiones Técnicas

### Stack
| Componente | Tecnología | Motivo |
|---|---|---|
| Frontend/Dashboard | Dash 2.x + DBC | Cero JS. Componentes reactivos en Python puro. |
| Gráficos | Plotly (incluido en Dash) | Interactivo, tooltips nativos, sin config adicional. |
| Base de datos | SQLite + SQLAlchemy ORM | Local, sin servidor, query tipado. |
| Scheduler | APScheduler | Soporta cron, interval y one-shot jobs en proceso. |
| IA | Librería `anthropic` oficial | Acceso a Claude para Módulo 15. |
| Configuración | python-dotenv | Carga .env automáticamente, sin exponer secrets. |
| Tema | dash-bootstrap-components DARKLY | Tema oscuro tipo terminal financiero, sin CSS custom. |

### Base de datos (SQLite)
- **Una sola tabla de series temporales** (`time_series`) para todos los indicadores. Clave compuesta `(indicator_id, timestamp, source)`. Este diseño permite añadir nuevos indicadores sin migración de esquema.
- **Tabla `snapshots`** para guardar el estado completo del dashboard (Módulo 14, viaje en el tiempo).
- **Tabla `events`** para la línea de tiempo anotada (Módulo 1 y 14).
- **Tabla `alerts`** para las alertas configurables por umbral (Módulo 17).
- **Tabla `ai_analyses`** para guardar los análisis del Módulo 15 con contexto.
- **Tabla `annotations`** para notas de usuario por indicador/fecha (Módulo 17).
- **Tabla `scenarios`** para el log de predicciones/escenarios del Módulo 14.

### Colectores
- Cada colector es **independiente**: si falla, el dashboard muestra "sin datos" en ese módulo sin crashear.
- Todos persisten datos en `time_series` con su `source` y `unit` correspondiente.
- Los colectores no se llaman desde los módulos directamente; el **scheduler** los ejecuta en background y los módulos leen de la base de datos.

### Módulos Dash
- Cada módulo exporta una función `layout()` que retorna un componente Dash.
- El routing lo gestiona el callback en `app.py` según la URL de la sidebar.
- Los módulos leen **siempre de SQLite**, nunca llaman a APIs externas directamente.

### Refresh Schedule (por colector)
| Colector | Frecuencia |
|---|---|
| yfinance (precios) | Cada 15 minutos |
| FRED, World Bank, Eurostat | Cada 24 horas |
| ECB | Cada 24 horas |
| CoinGecko | Cada 5 minutos |
| NewsAPI | Cada hora |
| GDELT | Cada 6 horas |
| Snapshot completo (Módulo 14) | Cada domingo 23:59 |

---

## Fuente de Datos por Módulo

| Módulo | Fuentes principales |
|---|---|
| 01 Estado Global | FRED (STLFSI), yfinance (VIX), GDELT, NewsAPI, DB local (alertas/eventos) |
| 02 Macro Global | World Bank, FRED, Eurostat, ECB |
| 03 Inflación | FRED, World Bank, ECB, Eurostat |
| 04 Política Monetaria | FRED, ECB, yfinance (fed futures) |
| 05 Mercados | yfinance (índices, divisas, renta fija, materias primas), FRED (CAPE/Shiller) |
| 06 Mercado Laboral | FRED, Eurostat, World Bank |
| 07 Energía y Materias | yfinance (commodities), FRED (inventarios), World Bank |
| 08 Deuda Fiscal | FRED, World Bank, Eurostat |
| 09 Sistema Financiero | FRED (STLFSI, SOFR), yfinance (CDS proxies) |
| 10 Geopolítica | GDELT, NewsAPI, DB local (eventos manuales) |
| 11 Indicadores Adelantados | FRED (LEI, PMI, yield curve), yfinance |
| 12 China | World Bank, yfinance (CNY, indices chinos), FRED |
| 13 Demografía | World Bank (indicadores demográficos) |
| 14 Histórico | DB local (snapshots, events, scenarios) |
| 15 Motor IA | Anthropic API + todos los datos de la DB |
| 16 Mercados/Submercados | yfinance, FRED, CoinGecko |
| 17 Personalización | DB local (alerts, annotations, user settings) |

---

## Convenciones de Código

- **IDs de indicadores**: `{source}_{metric}_{region}` — ej: `fred_cpi_yoy_us`, `yf_sp500_price`
- **Unidades estándar**: `pct` (porcentaje), `usd`, `eur`, `index`, `ratio`, `count`
- **Colores semáforo**: `#00c853` verde / `#76ff03` verde-amarillo / `#ffd600` amarillo / `#ff6d00` naranja / `#d50000` rojo
- **Fondo principal**: `#0a0a0a` | **Fondo card**: `#1a1a1a` | **Borde**: `#2a2a2a` | **Texto**: `#e0e0e0`

---

## Estado del Proyecto (inicio sesión 1)

- [x] Estructura de carpetas
- [x] requirements.txt
- [x] ARCHITECTURE.md (este fichero)
- [x] config.py
- [x] .env.example
- [x] .gitignore
- [x] database/database.py
- [x] database/init_db.py
- [x] app.py (layout base + sidebar + routing)
- [x] README.md
- [ ] Colectores (sesión 2+)
- [ ] Módulos individuales (sesión 2+)
- [ ] Scheduler jobs (sesión 2+)
