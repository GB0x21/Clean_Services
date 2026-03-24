# 🧹 CleanFlow Agents

Sistema de agentes de IA en Python para automatizar la prospección, calificación, y gestión de contratos de limpieza comercial.

## Arquitectura

```
                    ┌──────────────────┐
                    │   ORCHESTRATOR   │
                    │  (orchestrator)  │
                    └────────┬─────────┘
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                  │
    ┌─────┴─────┐    ┌──────┴──────┐   ┌───────┴───────┐
    │  PIPELINE  │    │  FOLLOW-UP  │   │   MONITOR     │
    │  COMPLETO  │    │   AGENT     │   │   AGENT       │
    └─────┬─────┘    └─────────────┘   └───────────────┘
          │
    ┌─────┴─────────────────────────────────┐
    │                                       │
    ▼                                       │
┌──────────┐   ┌───────────┐   ┌─────────┐ │ ┌──────────┐
│  LEAD    │──▶│   LEAD    │──▶│ SUBCON  │─┤▶│ PROPOSAL │
│ SCRAPER  │   │ QUALIFIER │   │ MATCHER │ │ │GENERATOR │
└──────────┘   └───────────┘   └─────────┘ │ └──────────┘
                                           │
                                    ┌──────┴──────┐
                                    │  SUPABASE   │
                                    │  DATABASE   │
                                    └─────────────┘
```

## Agentes

| Agente | Función | Input | Output |
|--------|---------|-------|--------|
| **Lead Scraper** | Busca oportunidades en Google CSE | Patrones + ciudades | Leads crudos |
| **Lead Qualifier** | Califica con IA + scoring | Leads crudos | Oportunidades scored |
| **Subcontractor Matcher** | Empareja con subs | Oportunidades | Matches + pricing |
| **Proposal Generator** | Genera propuestas con IA | Matches | Bids en Supabase |
| **Follow-up Agent** | Seguimiento automático | Bids enviadas | Emails de follow-up |
| **Performance Monitor** | Monitorea contratos | Contratos activos | Alertas de riesgo |

## Instalación

```bash
# 1. Clonar el repositorio
git clone <tu-repo>
cd cleanflow_agents

# 2. Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# o: venv\Scripts\activate  # Windows

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar variables de entorno
cp .env.example .env
# Editar .env con tus credenciales

# 5. Crear tablas en Supabase
# Copiar el contenido de supabase_schema.sql en el SQL Editor de Supabase
```

## Uso

### Ejecución manual

```bash
# Pipeline completo (scrape → qualify → match → propose)
python orchestrator.py full

# Solo scraping + calificación
python orchestrator.py scrape

# Solo matching + propuestas (usa leads ya calificados en DB)
python orchestrator.py match

# Solo follow-ups
python orchestrator.py followup

# Solo monitoreo de performance
python orchestrator.py monitor

# Testing con pocas queries
python orchestrator.py full --max-queries 5
```

### Ejecución automática (scheduler)

```bash
# Inicia el scheduler que ejecuta automáticamente:
#   - Pipeline completo: cada 6 horas
#   - Follow-ups: diario a las 10am
#   - Monitor: cada 12 horas
python scheduler.py
```

## Configuración

### Variables de Entorno Requeridas

| Variable | Descripción | Obligatorio |
|----------|-------------|:-----------:|
| `SUPABASE_URL` | URL de tu proyecto Supabase | ✅ |
| `SUPABASE_SERVICE_KEY` | Service role key (NO la anon) | ✅ |
| `OPENAI_API_KEY` | API key de OpenAI | ✅ |
| `GOOGLE_API_KEY` | API key de Google Custom Search | ✅ |
| `GOOGLE_CX` | Search Engine ID de Google CSE | ✅ |
| `TELEGRAM_BOT_TOKEN` | Token del bot de Telegram | ⭐ |
| `TELEGRAM_CHAT_ID` | Chat ID para notificaciones | ⭐ |
| `SMTP_USER` | Email para enviar propuestas | ⭐ |
| `SMTP_PASSWORD` | App password del email | ⭐ |

⭐ = Recomendado pero no bloqueante

### Criterios de Negocio

Edita `config/settings.py` para ajustar:

- **Ciudades target** (tier 1, 2, 3)
- **Rango de valor de contratos** ($3K-$50K)
- **Términos de pago aceptables** (Net 0-30)
- **Servicios preferidos/rechazados**
- **Fórmula de scoring** (pesos por factor)
- **Umbrales de decisión** (auto-pursue, review, reject)

## Estructura del Proyecto

```
cleanflow_agents/
├── __init__.py              # Init + carga de .env
├── orchestrator.py          # Orquestador principal + CLI
├── scheduler.py             # Scheduler automático (APScheduler)
├── requirements.txt         # Dependencias Python
├── .env.example             # Template de variables de entorno
├── supabase_schema.sql      # SQL para crear tablas en Supabase
│
├── config/
│   ├── __init__.py
│   └── settings.py          # Configuración central + reglas de negocio
│
├── core/
│   ├── __init__.py
│   ├── database.py          # Cliente Supabase (CRUD)
│   ├── ai_client.py         # Cliente OpenAI (wrapper)
│   └── notifications.py     # Telegram + Email
│
├── agents/
│   ├── __init__.py
│   ├── base_agent.py        # Clase base abstracta
│   ├── lead_scraper.py      # Agente 1: Búsqueda de leads
│   ├── lead_qualifier.py    # Agente 2: Calificación con IA
│   ├── subcontractor_matcher.py  # Agente 3: Match con subs
│   ├── proposal_generator.py     # Agente 4: Propuestas
│   ├── followup_agent.py    # Agente 5: Follow-ups
│   └── performance_monitor.py    # Agente 6: Monitoreo
│
├── utils/                   # Utilidades compartidas
└── templates/               # Templates de emails/propuestas
```

## Pipeline de Datos

```
Google CSE → Leads crudos → IA califica → Score (0-100) → Clasificación
                                                            │
                                          ┌─────────────────┼────────────────┐
                                          ▼                 ▼                ▼
                                        HOT (≥75)      WARM (50-74)     COLD (<50)
                                          │                 │                │
                                          ▼                 ▼                ▼
                                     Match Sub +       Requiere          Rechazar
                                     Generar Bid       Revisión          Auto
                                          │
                                          ▼
                                    Bid en Supabase
                                    (status: draft)
                                          │
                                          ▼ (manual)
                                    Enviar al cliente
                                    (status: sent)
                                          │
                                    ┌─────┼─────┐
                                    ▼     ▼     ▼
                                  3 días 7 días 14 días
                                  F/U #1 F/U #2 F/U #3 → Cold
```

## Costos Estimados

| Servicio | Costo | Notas |
|----------|-------|-------|
| Google CSE | Gratis (100/día) | $5/1000 queries extra |
| OpenAI (gpt-4o-mini) | ~$0.01-0.05/lead | ~$5-15/mes |
| Supabase | Gratis (tier free) | Hasta 500MB |
| Telegram Bot | Gratis | — |
| Gmail SMTP | Gratis | App password requerido |

**Total estimado: $10-30/mes** para ~500 leads/mes

## Integración con v0/CleanFlow

Los agentes Python escriben directamente a Supabase. El dashboard en v0 (Next.js)
lee de las mismas tablas con Supabase Realtime, así que los datos aparecen
automáticamente en el frontend sin necesidad de API intermediaria.
