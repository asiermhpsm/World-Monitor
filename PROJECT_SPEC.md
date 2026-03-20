# World Monitor — Especificación Completa del Proyecto

## Descripción General
Dashboard financiero personal para monitorización económica global.
Corre en local (localhost:8050). Sin despliegue en internet.
Stack: Python puro + Dash + Plotly + SQLite + SQLAlchemy + APScheduler.
Cero JavaScript. Cero React. Cero Node (excepto para Claude Code).

## Stack Técnico
- **Frontend/Dashboard:** Dash by Plotly + Dash Bootstrap Components
- **Gráficos:** Plotly (incluido en Dash)
- **Base de datos:** SQLite con SQLAlchemy ORM
- **Scheduler:** APScheduler
- **Motor IA:** Librería oficial `anthropic` de Python
- **Estilo:** Tema oscuro tipo Bloomberg/terminal financiero

## Fuentes de Datos Gratuitas
- FRED (Federal Reserve): macro EE.UU., inflación, tipos, empleo
- Yahoo Finance (yfinance): mercados, índices, divisas, materias primas
- World Bank API (wbdata): macro global todos los países
- ECB Data Portal: datos europeos, tipos BCE
- Eurostat API: macro Europa detallada
- CoinGecko API: criptomonedas
- NewsAPI: noticias financieras
- GDELT: tensión geopolítica global

## Módulos del Dashboard

### Módulo 1 — Panel de Estado Global
- Semáforo global de riesgo sistémico (5 niveles: verde/verde-amarillo/amarillo/naranja/rojo)
- Semáforos regionales: EE.UU., Eurozona, China, Mercados Emergentes, Japón, Reino Unido
- Resumen narrativo actualizable (texto libre + generado por IA)
- Panel de los 5-10 eventos más relevantes recientes con fecha, región e impacto
- Panel de alertas activas cuando indicadores cruzan umbrales configurables
- Línea de tiempo global con eventos históricos anotados
- Resumen de variaciones 24h/7d/30d de indicadores clave
- Fecha y hora de última actualización por fuente

### Módulo 2 — Macroeconomía Global y por Regiones
Países cubiertos: EE.UU., Eurozona (agregado), Alemania, Francia, España, Italia,
Reino Unido, China, Japón, India, Brasil, México, Rusia, ASEAN, Mercados Emergentes

Por cada país/región:
- PIB real (trimestral y anual) + proyecciones FMI/Banco Mundial
- PIB per cápita real
- Producción industrial (mensual)
- PMI manufacturero y de servicios (semáforo: >50 expansión, <50 contracción)
- Ventas al por menor
- Confianza del consumidor y empresarial
- Balanza comercial + principales socios
- Balanza por cuenta corriente (% PIB)
- Déficit/superávit fiscal (% PIB)
- Deuda pública (% PIB) + proyección 10 años
- Tipo de cambio vs USD y EUR
- Reservas de divisas del banco central

Panel de comparativas: tabla lado a lado + mapa de calor mundial por indicador

### Módulo 3 — Inflación
Por cada país (misma lista Módulo 2):
- IPC general (interanual y mensual) vs objetivo banco central
- IPC subyacente (core)
- Desglose por componentes: alimentos, energía, servicios, vivienda, bienes
- IPP (Índice de Precios de Producción) — adelanta inflación futura
- Expectativas de inflación 1, 2 y 5 años (mercado y encuestas)
- Tipos de interés reales = tipo oficial - inflación (dato destacado)

Panel Represión Financiera:
- Rendimiento depósito bancario promedio vs inflación actual (por país)
- Calculadora erosión efectivo: "10.000€ desde fecha X valen Z hoy en términos reales"
- Mapa de calor tipos reales por país (verde=positivo, rojo=negativo)

### Módulo 4 — Política Monetaria
Bancos centrales: Fed, BCE, Bank of England, Bank of Japan, SNB, Bank of Canada,
RBA (Australia), PBOC (China), RBI (India), BCB (Brasil), Banxico (México)

Por cada banco central:
- Tipo oficial actual + máximo y mínimo histórico reciente
- Gráfico histórico del tipo desde 2008
- Próxima reunión + probabilidades mercado (subida/pausa/bajada)
- Últimas 5 decisiones resumidas
- Tamaño del balance (QE activo)
- Postura: Hawkish/Neutral/Dovish
- Brecha inflación actual vs objetivo 2%
- Dot plot Fed (cuando se publique)

Panel comparativa global: todos los tipos en un gráfico + tabla resumen

### Módulo 5 — Mercados Financieros
Índices bursátiles: S&P 500, Nasdaq 100, Dow Jones, Russell 2000, Eurostoxx 50,
DAX, CAC 40, IBEX 35, FTSE MIB, FTSE 100, SMI, Nikkei 225, Hang Seng,
Shanghai Composite, CSI 300, Sensex, Bovespa, IPC México, MSCI World, MSCI EM

Por índice: precio, variación diaria/semanal/mensual/YTD/anual, distancia máximo histórico

Valoración mercado americano:
- PER S&P 500 actual vs media 20 años
- Shiller CAPE con semáforo (barato/neutral/caro/muy caro)
- Ratio Buffett (market cap total EE.UU. / PIB)
- Concentración índice (peso top 5 y top 10 empresas)
- Amplitud mercado (% empresas sobre media móvil 200 días)

Renta fija:
- Curva de tipos completa EE.UU. (3m, 6m, 1y, 2y, 3y, 5y, 7y, 10y, 20y, 30y)
- Curva Alemania y Japón
- Spread 10y-2y y 10y-3m (indicador inversión de curva + semáforo)
- Spreads crédito corporativo: IG y HY en EE.UU. y Europa
- Primas de riesgo soberanas europeas vs Bund

Divisas: DXY, EUR/USD, GBP/USD, USD/JPY, USD/CHF, AUD/USD, USD/CAD,
USD/CNY, USD/BRL, USD/MXN, EUR/GBP, EUR/CHF

Materias primas: Brent, WTI, Gas TTF, Gas Henry Hub, Carbón, Uranio,
Oro, Plata, Platino, Paladio, Cobre, Aluminio, Acero, Zinc, Níquel, Litio, Cobalto,
Trigo, Maíz, Soja, Arroz, Baltic Dry Index

Volatilidad y sentimiento: VIX, MOVE Index, SKEW, Fear&Greed CNN,
Put/Call ratio, CFTC CoT, Margin Debt

Criptos: Bitcoin, Ethereum, Total Market Cap, Dominancia BTC,
Fear&Greed Crypto, Stablecoin supply ratio, Flujos ETFs Bitcoin

### Módulo 6 — Mercado Laboral
Países: EE.UU., Eurozona, Alemania, España, Francia, Italia, Reino Unido, Japón, China

Por país: desempleo general/juvenil/larga duración, participación laboral,
crecimiento salarial nominal y real, horas trabajadas

EE.UU. específico: Non-Farm Payrolls, JOLTS, ratio ofertas/desempleados,
solicitudes desempleo semanales, ECI, quit rate

### Módulo 7 — Energía y Materias Primas Estratégicas
- Precio petróleo + contexto: producción OPEP+, inventarios, capacidad reserva Arabia Saudí
- Producción EE.UU.
- Estado rutas estratégicas: Estrecho Ormuz, Canal Suez, Estrecho Malaca (% capacidad)
- Inventarios gas natural Europa (% capacidad almacenamiento)
- Dependencia energética por país (% energía importada)
- Precios tecnologías renovables: batería kWh, panel solar W, turbina eólica MW
- Capacidad renovables instalada global vs fósiles
- Minerales críticos: litio, cobalto, níquel, cobre, neodimio, galio, germanio
- Índice FAO precios alimentos + inventarios granos + países en crisis alimentaria

### Módulo 8 — Deuda y Sostenibilidad Fiscal
Países: EE.UU., Japón, China, Alemania, Francia, España, Italia, Reino Unido, Grecia, Brasil

Por país:
- Deuda pública total y % PIB + proyección 10 años (FMI)
- Deuda privada (hogares + empresas) % PIB
- Déficit fiscal % PIB + tendencia 5 años
- Coste servicio deuda: intereses como % PIB y % ingresos fiscales
- Vencimientos próximos: deuda a refinanciar en 1, 3 y 5 años
- Rating crediticio Moody's, S&P, Fitch + perspectiva
- Tipo medio deuda existente vs tipo mercado actual

Panel EE.UU.: deuda nominal tiempo real, intereses semanales,
proyección CBO a 10/20/30 años, principales tenedores de deuda

Panel Eurozona: comparativa deuda/PIB y déficit/PIB de todos los miembros
con líneas del Pacto de Estabilidad (60% deuda, 3% déficit)

### Módulo 9 — Sistema Financiero y Riesgo Sistémico
- Índice Estrés Financiero Sistémico (STLFSI) de la Fed de St. Louis
- Salud bancos globales (JPMorgan, BofA, Citi, GS, Wells Fargo, Deutsche Bank,
  BNP Paribas, Santander, BBVA, HSBC, UBS, Barclays, UniCredit):
  ratio CET1, ROA, morosidad, exposición deuda soberana, precio acción
- Spreads interbancarios (SOFR spreads)
- Exposición sectorial banca: inmobiliario comercial, residencial, HY corporativo
- Flujos capital hacia/desde mercados emergentes
- Reservas bancarias en banco central
- CDS países y grandes bancos

### Módulo 10 — Geopolítica y Riesgos Globales
- Mapa mundial interactivo con nivel de riesgo por país/región
- Panel por conflicto activo: intensidad, activos afectados, impacto económico,
  escenarios con probabilidades
- Índice GPR (Geopolitical Risk Index) con histórico
- Panel especial Taiwán: incursiones militares, actividad naval, probabilidad conflicto
- Panel especial Rusia/Ucrania: sanciones, impacto energía y granos
- Sanciones económicas activas en el mundo
- Relaciones comerciales China-EE.UU.: aranceles, volumen, reuniones diplomáticas
- Calendario político: elecciones próximos 12 meses + reuniones G7/G20/OPEP+
- Índice fragmentación geoeconómica

### Módulo 11 — Indicadores Adelantados y Señales de Alerta
Indicadores de recesión:
- Inversión curva de tipos (10y-2y y 10y-3m) con semáforo + tiempo acumulado en inversión
- LEI Conference Board EE.UU. y Europa
- ISM nuevos pedidos
- Variación crédito bancario
- Permisos de construcción
- Solicitudes desempleo semanales con tendencia 4 semanas
- Ventas bienes duraderos

Indicadores de crisis financiera:
- CDS top 10 bancos globales (alerta si suben >50% en 30 días)
- Spreads interbancarios (SOFR OIS spread)
- Spreads crédito High Yield
- Volatilidad implícita del oro

Indicadores de inflación:
- IPP, precios materias primas, expectativas inflación mercado, crecimiento salarial

Panel señales compuestas:
- Semáforo probabilidad recesión a 6 y 12 meses
- Semáforo riesgo crisis financiera
- Semáforo riesgo inflacionario
- Indicador Buffett con zonas históricas
- Shiller CAPE con probabilidad histórica de retorno a 10 años

### Módulo 12 — China Panel Especial
- PIB real y composición (consumo, inversión, gasto público, exportaciones)
- CPI y PPI chino
- Indicadores proxy de actividad real:
  consumo electricidad, tráfico ferroviario mercancías, Índice de Li Keqiang
- Sector inmobiliario: precios 70 ciudades, ventas nuevas viviendas,
  inventario meses, estado promotores (deuda, impagos)
- Superávit comercial global + desglose por destino
- Reservas divisas PBOC
- Flujos inversión extranjera (entrada y salida)
- Tipo cambio CNY/CNH y divergencia entre ambos
- Aranceles China-EE.UU. y China-Europa
- Tensión Estrecho Taiwan

### Módulo 13 — Demografía y Tendencias Estructurales
- Tasa de fertilidad por país (mapa de calor, umbral 2.1)
- Pirámide de población países clave
- Ratio de dependencia (jubilados/población activa) + proyecciones 2030/2040/2050
- Proyecciones población activa por región
- Crecimiento productividad total de factores por región
- Inversión I+D como % PIB por país
- Penetración internet, smartphones, cloud por región
- Índice de Gini por país
- Evolución patrimonio clase media vs top 1%

### Módulo 14 — Seguimiento Histórico y Comparativas Temporales
Funcionalidad 1 - Viaje en el Tiempo:
- Selector de fecha → todos los módulos muestran datos de ese momento exacto
- Snapshots automáticos completos cada domingo a las 23:59
- Guardado automático con timestamp en cada actualización

Funcionalidad 2 - Comparador Temporal:
- Selecciona cualquier indicador + dos fechas → gráficos superpuestos
- Diferencia en valor absoluto y porcentaje

Funcionalidad 3 - Línea de Tiempo Anotada:
- Barra cronológica con todos los eventos registrados
- Cada evento: fecha, título, categoría, impacto en mercados 48h
- Añadir eventos manualmente
- Click en evento → activa viaje en el tiempo a esa fecha

Funcionalidad 4 - Comparativa con Crisis Históricas:
- Para cualquier indicador deteriorado, botón "comparar con crisis históricas"
- Muestra el indicador en semanas previas a: 1929, 1973, 2000, 2008, 2020

Funcionalidad 5 - Registro de Escenarios:
- Log de predicciones con fecha, probabilidad y condiciones
- Seguimiento posterior de si se cumplieron

### Módulo 15 — Motor de Análisis IA
Modo 1: "Analiza situación actual"
- Recoge todos los datos actuales de la BD
- Envía a API de Claude con prompt detallado
- Muestra análisis narrativo profundo: resumen ejecutivo, análisis por tema,
  escenarios con probabilidades, alertas clave, sorpresas posibles

Modo 2: "Analiza texto externo"
- Área de texto para pegar artículos, informes, transcripciones
- Análisis crítico: qué dice bien, qué dice mal, qué falta, coherencia con datos del dashboard

Modo 3: "Chat con contexto del dashboard"
- Chat integrado con los datos actuales como contexto
- Preguntas específicas sobre la situación actual

Modo 4: "Escenario hipotético"
- Define un evento hipotético → análisis de impacto en cascada sobre todos los módulos

Historial: todos los análisis guardados en SQLite con fecha y datos del momento

### Módulo 16 — Análisis de Mercados y Submercados
Mercado 1 - Renta Variable:
- Submercado IA/Tecnología: capitalización sector tech, PER sector vs mercado,
  revenue gap IA, capex hyperscalers, señales burbuja vs puntocom 2000
- Submercado Energía: sector vs S&P, E&P capex, renovables
- Submercado Financiero: bancos vs mercado, precio/valor libros, margen intermediación
- Submercado Salud/Farmacia: pipeline medicamentos, impacto GLP-1
- Submercado Consumo Básico y Discrecional
- Submercado Defensa/Aeroespacial: presupuestos OTAN, carteras de pedidos
- Submercado Materiales y Minería

Mercado 2 - Renta Fija:
- Deuda soberana: curvas comparadas, flujos
- Crédito IG: spread, flujos, tasa impagos
- High Yield: spread, muro vencimientos, tasa impago
- Deuda emergente: spreads moneda fuerte y local

Mercado 3 - Materias Primas:
- Petróleo: estructura contango/backwardation, inventarios, producción por bloque
- Metales preciosos: ratio oro/petróleo, ratio oro/plata, demanda por tipo
- Metales industriales: cobre vs crecimiento global
- Agrícolas: inventarios, impacto climático, precios fertilizantes

Mercado 4 - Divisas:
- Dólar como reserva: % reservas globales, uso en comercio, tendencia desdolarización
- Euro: flujos, riesgos específicos
- Divisas refugio: CHF y JPY como indicadores de apetito por riesgo
- Divisas emergentes: monitor crisis (caída >15% en 6 meses = alerta)

Mercado 5 - Inmobiliario:
- Residencial: Case-Shiller EE.UU., índices España/Alemania/UK/Australia/China,
  ratio precio/ingresos, ratio precio/alquiler, permisos construcción, tipos hipotecarios
- Comercial: oficinas (vacancia, impacto teletrabajo), retail, logística
- REITs: rendimiento por subsector

Mercado 6 - Crypto:
- Bitcoin y ETH: precio, cap, volatilidad, correlación S&P y oro
- Total market cap y composición
- Stablecoins: emisión total y respaldo reservas
- DeFi: TVL
- ETFs Bitcoin: flujos netos diarios/semanales
- Ciclos históricos Bitcoin (halvings)

### Módulo 17 — Personalización y Alertas
- Configuración de alertas: umbral configurable por cualquier indicador
  (notificación visual dentro del dashboard + sonido opcional)
- Widgets favoritos: panel personalizado con los indicadores más consultados
- Frecuencia de actualización configurable por módulo
- Gestión de fuentes de datos con estado (activa/inactiva/error)
- Exportación de datos a CSV
- Notas y anotaciones en cualquier indicador o fecha

## Variables de Entorno Necesarias
- FRED_API_KEY: API key de FRED (fred.stlouisfed.org) — gratuita
- ANTHROPIC_API_KEY: API key de Claude para Módulo 15 — tiene plan gratuito
- NEWS_API_KEY: API key de NewsAPI (newsapi.org) — plan gratuito 100 req/día

## Decisiones de Diseño
- Tema oscuro tipo Bloomberg/terminal financiero
- Sidebar de navegación con todos los módulos
- Cada módulo carga sus datos de forma independiente (no bloquear el dashboard)
- Los gráficos deben tener selector de rango temporal: 1m, 3m, 6m, 1a, 5a, máx
- Todos los gráficos con tooltips informativos
- Semáforos consistentes en todo el dashboard: verde/amarillo-verde/amarillo/naranja/rojo
- El dashboard debe ser funcional aunque algunos colectores fallen (mostrar "sin datos" en lugar de crashear)