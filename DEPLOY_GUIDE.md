# CleanFlow Agents — Guía de instalación en DigitalOcean Droplet

## Paso 1: Crear el Droplet

En DigitalOcean (cloud.digitalocean.com):

1. Click **Create → Droplets**
2. Configuración recomendada:
   - **Region:** San Francisco (SFO3) — cercano a tus ciudades target
   - **Image:** Ubuntu 24.04 LTS
   - **Size:** Basic → Regular → **$6/mes** (1 vCPU, 1GB RAM, 25GB SSD)
   - **Authentication:** SSH Key (recomendado) o Password
   - **Hostname:** `cleanflow-agents`
3. Click **Create Droplet**
4. Copia la IP que te asignan (ejemplo: `164.92.xxx.xxx`)

> El Droplet de $6/mes es suficiente. Los agentes usan poca memoria porque
> el trabajo pesado lo hacen las APIs (OpenAI, Google, Supabase).


## Paso 2: Conectarte al Droplet

```bash
ssh root@164.92.xxx.xxx
```

Si usaste password, te lo pedirá. Si usaste SSH key, entra directo.


## Paso 3: Subir el proyecto

Desde tu computadora local (otra terminal):

```bash
# Opción A: SCP directo
scp cleanflow_agents.zip root@164.92.xxx.xxx:/root/

# Opción B: Si lo tienes en GitHub
# (lo clonas directo en el droplet, ver paso 4)
```


## Paso 4: Ejecutar la instalación

De vuelta en el Droplet (la sesión SSH):

```bash
# Si subiste el ZIP:
cd /root
unzip cleanflow_agents.zip
cd cleanflow_agents
chmod +x install.sh
./install.sh

# Si lo clonaste de GitHub:
git clone https://github.com/tu-usuario/cleanflow-agents.git
cd cleanflow-agents
chmod +x install.sh
./install.sh
```

El script hace todo automáticamente:
- Actualiza Ubuntu
- Instala Python 3, pip, supervisor, firewall
- Crea usuario `cleanflow`
- Configura entorno virtual con dependencias
- Crea archivo `.env` template
- Configura Supervisor para auto-restart
- Activa firewall (solo SSH abierto)
- Instala el comando `cleanflow` para gestión fácil


## Paso 5: Configurar credenciales

```bash
cleanflow edit-env
```

Esto abre nano. Edita cada valor:

```
SUPABASE_URL=https://abcdefgh.supabase.co       ← tu URL real
SUPABASE_SERVICE_KEY=eyJhbGci...                 ← tu service_role key
OPENAI_API_KEY=sk-proj-...                       ← tu API key de OpenAI
GOOGLE_API_KEY=AIzaSy...                         ← tu API key de Google
GOOGLE_CX=a1b2c3d4e5...                          ← tu Search Engine ID
TELEGRAM_BOT_TOKEN=7123456:AAH...                ← tu bot token
TELEGRAM_CHAT_ID=-1001234567890                  ← tu chat ID
```

Guarda con `Ctrl+O`, `Enter`, `Ctrl+X`.


## Paso 6: Crear tablas en Supabase

Ve a tu Supabase Dashboard → SQL Editor y ejecuta:

```bash
# Ver el SQL que necesitas copiar:
cat /home/cleanflow/app/supabase_schema.sql
```

Copia todo el contenido y pégalo en el SQL Editor de Supabase. Click **Run**.


## Paso 7: Test rápido

```bash
cleanflow test
```

Esto ejecuta el pipeline con solo 2 queries en modo dry-run (no envía nada,
no genera propuestas). Deberías ver:

```
2026-03-23 10:00:00 │ cleanflow.orchestrator.v2 │ INFO    │ ENHANCED PIPELINE v2 INICIANDO
2026-03-23 10:00:01 │ cleanflow.scraper         │ INFO    │ Generadas 2 queries de búsqueda
2026-03-23 10:00:05 │ cleanflow.scraper         │ INFO    │ Dedup: 8 → 6 leads únicos
2026-03-23 10:00:06 │ cleanflow.qualifier       │ INFO    │ [HOT] City of Phoenix Cleaning... → Score: 82.5
...
```

Si ves errores:
- `SUPABASE_URL y SUPABASE_SERVICE_KEY son requeridos` → revisa .env
- `Google CSE error: 403` → verifica GOOGLE_API_KEY y GOOGLE_CX
- `OpenAI error` → verifica OPENAI_API_KEY


## Paso 8: Ejecución manual completa

```bash
# Pipeline completo con 5 queries por ciudad (modo seguro)
cleanflow run full --max-queries 5

# Pipeline completo sin límite
cleanflow run full

# Solo scraping (sin propuestas)
cleanflow run scrape

# Solo follow-ups
cleanflow run followup
```


## Paso 9: Activar scheduler automático

```bash
cleanflow start
```

Esto inicia el scheduler que ejecuta automáticamente:
- Pipeline completo cada 6 horas (3am, 9am, 3pm, 9pm)
- Follow-ups diarios a las 10am
- Monitor de performance cada 12 horas

Verificar que está corriendo:

```bash
cleanflow status
# Debería mostrar: cleanflow-scheduler   RUNNING   pid 12345
```


## Paso 10: Monitoreo

```bash
# Ver logs en tiempo real
cleanflow logs

# Ver dashboard de agentes
cleanflow dashboard

# Estado del scheduler
cleanflow status
```


## Comandos útiles del día a día

```bash
cleanflow help          # Ver todos los comandos
cleanflow start         # Iniciar scheduler
cleanflow stop          # Detener scheduler
cleanflow restart       # Reiniciar scheduler
cleanflow status        # Estado del scheduler
cleanflow run full      # Pipeline manual
cleanflow test          # Test rápido
cleanflow logs          # Ver logs
cleanflow dashboard     # Estado de agentes
cleanflow edit-env      # Editar credenciales
```


## Troubleshooting

### El scheduler no inicia
```bash
# Ver logs de supervisor
sudo tail -50 /var/log/cleanflow/scheduler.log

# Reiniciar supervisor
sudo supervisorctl restart cleanflow-scheduler

# Si hay error de Python:
cd /home/cleanflow/app
./venv/bin/python -c "from config import config; print(config.supabase.url)"
```

### No encuentra leads
```bash
# Verificar Google CSE funciona:
cd /home/cleanflow/app
./venv/bin/python -c "
import requests
from config import config
r = requests.get('https://www.googleapis.com/customsearch/v1', params={
    'key': config.google.api_key,
    'cx': config.google.cx,
    'q': 'RFP commercial cleaning Phoenix AZ',
    'num': 1
})
print(r.status_code, r.json().get('searchInformation', {}).get('totalResults', 0), 'results')
"
```

### Telegram no envía
```bash
cd /home/cleanflow/app
./venv/bin/python -c "
from core import notifier
notifier.send_telegram('🧪 Test desde CleanFlow')
"
```

### Actualizar el código
```bash
# Sube el nuevo ZIP
scp cleanflow_agents.zip root@164.92.xxx.xxx:/root/

# En el droplet:
cd /root && unzip -o cleanflow_agents.zip
sudo cp -r cleanflow_agents/* /home/cleanflow/app/
sudo chown -R cleanflow:cleanflow /home/cleanflow/app/
cleanflow restart
```


## Costos mensuales estimados

| Servicio | Costo |
|----------|-------|
| DigitalOcean Droplet | $6/mes |
| OpenAI (gpt-4o-mini) | $5-15/mes |
| Google CSE | Gratis (100/día) |
| Supabase | Gratis (tier free) |
| Telegram Bot | Gratis |
| **Total** | **~$15-25/mes** |
