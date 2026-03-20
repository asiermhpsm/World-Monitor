# World Monitor

Dashboard financiero personal para monitorización económica global.
Corre en local en `http://localhost:8050`. Stack: Python + Dash + Plotly + SQLite.

---

## Requisitos previos

- Python 3.10 o superior
- pip

---

## Instalación

### 1. Clonar el repositorio (o descargar la carpeta)

```bash
cd "World Monitor"
```

### 2. Crear y activar entorno virtual

```bash
python -m venv venv
```

**Windows:**
```bash
venv\Scripts\activate
```

**macOS / Linux:**
```bash
source venv/bin/activate
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Configurar variables de entorno

```bash
cp .env.example .env
```

Edita `.env` y añade tus API keys:

| Variable | Dónde obtenerla | Obligatoria |
|---|---|---|
| `FRED_API_KEY` | [fred.stlouisfed.org](https://fred.stlouisfed.org/docs/api/api_key.html) — gratuita | Módulos 2, 3, 4, 6, 8, 9, 11 |
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com/) | Módulo 15 (IA) |
| `NEWS_API_KEY` | [newsapi.org/register](https://newsapi.org/register) — plan gratuito | Módulos 1, 10 |

> Los módulos de mercados (Yahoo Finance, World Bank, CoinGecko) funcionan sin API key.

### 5. Inicializar la base de datos

```bash
python database/init_db.py
```

Verás algo como:
```
Inicializando base de datos en: .../world_monitor.db
Tablas creadas:
  ✓ time_series
  ✓ snapshots
  ✓ events
  ✓ alerts
  ✓ ai_analyses
  ✓ annotations
  ✓ scenarios
Base de datos lista.
```

### 6. Arrancar el dashboard

```bash
python app.py
```

Abre el navegador en: **http://127.0.0.1:8050**

---

## Estructura del proyecto

Consulta [ARCHITECTURE.md](ARCHITECTURE.md) para la descripción completa de la arquitectura,
decisiones técnicas, fuentes de datos por módulo y convenciones de código.

---

## Módulos incluidos

| # | Módulo |
|---|---|
| 01 | Panel de Estado Global |
| 02 | Macroeconomía Global y por Regiones |
| 03 | Inflación |
| 04 | Política Monetaria |
| 05 | Mercados Financieros |
| 06 | Mercado Laboral |
| 07 | Energía y Materias Primas |
| 08 | Deuda y Sostenibilidad Fiscal |
| 09 | Sistema Financiero y Riesgo Sistémico |
| 10 | Geopolítica y Riesgos Globales |
| 11 | Indicadores Adelantados y Señales de Alerta |
| 12 | China — Panel Especial |
| 13 | Demografía y Tendencias Estructurales |
| 14 | Seguimiento Histórico y Comparativas Temporales |
| 15 | Motor de Análisis IA |
| 16 | Análisis de Mercados y Submercados |
| 17 | Personalización y Alertas |

---

## Notas

- El dashboard es funcional aunque algún colector falle: muestra "sin datos" en lugar de crashear.
- Para modo debug (recarga automática al editar código): `DASH_DEBUG=true` en `.env`.
- La base de datos SQLite se genera en la raíz del proyecto como `world_monitor.db`.
