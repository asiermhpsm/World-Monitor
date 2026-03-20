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

## Estado del Proyecto

### Sesión 1 (scaffolding)
- [x] Estructura de carpetas
- [x] requirements.txt
- [x] ARCHITECTURE.md (este fichero)
- [x] config.py
- [x] .env.example / .gitignore
- [x] database/database.py (7 tablas SQLAlchemy)
- [x] database/init_db.py
- [x] app.py (layout base + sidebar + routing)
- [x] README.md

### Sesión 2 (colector FRED)
- [x] collectors/base_collector.py — clase base abstracta (interfaz común)
- [x] collectors/fred_collector.py — colector FRED completo (55 series, 8 grupos)
- [x] collectors/__init__.py
- [x] scripts/test_fred.py — script de prueba con 5 series

### Sesión 3 (colector Yahoo Finance)
- [x] collectors/yahoo_collector.py — 111 tickers, 8 categorías, batch de 20, métricas derivadas
- [x] scripts/test_yahoo.py — prueba con 6 tickers + ratio oro/plata + RSP/SPY

### Sesión 4 (bug fix Yahoo Finance)
- [x] Actualizado yfinance 0.2.40 → 1.2.0 + curl_cffi (anti-bot Yahoo Finance 2024)
- [x] Eliminado parámetro `threads` (removido en yfinance 1.x)
- [x] Reescrito `_download_batch()` para manejar siempre MultiIndex (yfinance 1.x)
- [x] Añadida sesión curl_cffi a `yf.Ticker()` para impersonación Chrome
- [x] Corregidos caracteres Unicode en scripts y colector (compatibilidad Windows cp1252)
- [x] Test exitoso: 29,714 registros, 9 tickers, 0 fallos

### Sesión 5 (colector World Bank)
- [x] collectors/worldbank_collector.py — 54 indicadores, 45 paises/regiones, sin API key
- [x] collectors/__init__.py — actualizado con WorldBankCollector
- [x] scripts/test_worldbank.py — descarga 5 indicadores x 6 paises, tabla comparativa + 3 rankings
- [x] Test exitoso: 664 registros, 5 indicadores, 0 fallos, dedup OK

### Sesión 6 (colector Europe: BCE + Eurostat)
- [x] collectors/europe_collector.py — BCE (tipos, ESTR, M1/M2/M3, crédito, curva EA) + Eurostat (HICP, desempleo, PIB, producción industrial, deuda EDP, confianza consumidor, comercio exterior)
- [x] collectors/__init__.py — actualizado con EuropeCollector
- [x] scripts/test_europe.py — prueba con 4 series BCE + 3 FRED + HICP eurostat, spreads, semáforo
- [x] Test exitoso: 2,092 registros, 11 series, 0 fallos

### Sesión 7 (colector CoinGecko + Alternative.me)
- [x] collectors/coingecko_collector.py — 7 criptos (USD + EUR para BTC/ETH), datos globales, F&G, stablecoins, halvings, 4 metricas derivadas
- [x] collectors/__init__.py — actualizado con CoinGeckoCollector
- [x] scripts/test_coingecko.py — prueba 30 dias BTC/ETH, snapshot global, F&G, SSR, halvings
- [x] Test exitoso: 304 registros, 22 series, 0 fallos, halvings OK, 429 handled

### Pendiente (sesión 8+)
- [ ] collectors/newsapi_collector.py
- [ ] collectors/gdelt_collector.py
- [ ] Módulos individuales (modules/mXX_*.py)
- [ ] scheduler/jobs.py

---

## Notas sobre el colector Europe (BCE + Eurostat)

- **BCE (ECB SDMX-JSON API)**: `https://data-api.ecb.europa.eu/service/data/{FLOW}/{KEY}?format=jsondata`
  - Funciona: tipos oficiales (FM), ESTR (EST), M1/M2/M3 + crédito (BSI), curva EA 10Y (YC)
  - No disponible vía nueva API: EURIBOR (claves de 8 dims con flow FM/BB), bonos soberanos por país
- **Bonos soberanos por país**: Vía FRED API (`IRLTLT01DEMxxx`, `IRLTLT01ESMxxx`, etc.), almacenados con source='ecb' e IDs `ecb_bund_10y_de`, `ecb_yield_10y_es`, etc. Requiere FRED_API_KEY.
- **EURIBOR 3M proxy**: FRED serie `IR3TIB01EZM156N` → `ecb_euribor_3m_ea`
- **Eurostat SDMX 2.1**: `https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/{dataset}/{key}`
  - La clave SDMX se construye con formato `.{unit}.{coicop}.{geo}` (punto inicial = wildcard para FREQ)
  - Parámetro de tiempo: `sinceTimePeriod` (no `startPeriod`)
  - La respuesta puede venir gzip-comprimida sin declarar `Content-Encoding` — requiere detección manual (magic bytes `1f8b`)
  - Dimensiones confirmadas por dataset:
    - `prc_hicp_aind`: `[freq, unit, coicop, geo]`
    - `une_rt_m`: `[freq, s_adj, age, unit, sex, geo]`
    - `namq_10_gdp`: `[freq, unit, s_adj, na_item, geo]`
    - `sts_inpr_m`: `[freq, indic_bt, nace_r2, s_adj, unit, geo]`
    - `gov_10dd_edpt1`: `[freq, unit, sector, na_item, geo]`
    - `ei_bsco_m` (confianza consumidor, reemplaza ei_bssi_m que da 404): `[freq, indic, s_adj, unit, geo]`
    - `ext_lt_maineu`: `[freq, indic_et, sitc06, partner, geo]` (geo solo `EU27_2020`)
- **Spreads soberanos**: `(yield_país - bund_DE) × 100` en puntos básicos. Calculados y persistidos con source='ecb_derived'. Requieren bonos de ambos países en BD.

---

## Notas sobre el colector FRED

- **55 series** agrupadas en 8 grupos: PIB, Inflación, Fed, Curva tipos, Laboral, Deuda, Estrés Financiero, Inmobiliario.
- **Anti-duplicados**: usa `MAX(timestamp)` por indicator_id para insertar solo datos nuevos (eficiente, sin UniqueConstraint).
- **Derived series** calculadas y persistidas automáticamente:
  - YoY de 8 series de inflación → `fred_*_yoy_us`
  - MoM del IPC → `fred_cpi_mom_us`
  - Tipo real = FEDFUNDS – CPI YoY → `fred_real_rate_us`
  - Spread 10y-2y calculado → `fred_spread_10y2y_calc_us`
- **`download_series(list, start)`**: método público para descargar subconjuntos (pruebas).
- **`run_update()`** usa buffer de 30 días para capturar revisiones retroactivas de FRED.
