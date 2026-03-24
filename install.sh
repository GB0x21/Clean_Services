#!/bin/bash
# ============================================================
# CleanFlow Agents — Instalación en Droplet Ubuntu (22.04/24.04)
# 
# Uso:
#   curl -sSL https://tu-repo/install.sh | bash
#   — o —
#   chmod +x install.sh && ./install.sh
#
# Requisitos: Droplet Ubuntu fresco con root o sudo access
# ============================================================

set -euo pipefail

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; exit 1; }
step() { echo -e "\n${CYAN}━━━ $1 ━━━${NC}"; }

# ─── VERIFICACIONES ────────────────────────────

if [ "$(id -u)" -ne 0 ]; then
    SUDO="sudo"
else
    SUDO=""
fi

step "1/8 — Actualizando sistema"
$SUDO apt-get update -qq
$SUDO apt-get upgrade -y -qq
log "Sistema actualizado"

step "2/8 — Instalando dependencias del sistema"
$SUDO apt-get install -y -qq \
    python3 \
    python3-pip \
    python3-venv \
    git \
    curl \
    unzip \
    supervisor \
    ufw \
    fail2ban \
    htop
log "Dependencias instaladas"

# Verificar versión de Python
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
log "Python $PYTHON_VERSION detectado"

step "3/8 — Creando usuario cleanflow"
if id "cleanflow" &>/dev/null; then
    warn "Usuario cleanflow ya existe"
else
    $SUDO useradd -m -s /bin/bash cleanflow
    $SUDO usermod -aG sudo cleanflow
    log "Usuario cleanflow creado"
fi

APP_DIR="/home/cleanflow/app"
$SUDO mkdir -p "$APP_DIR"

step "4/8 — Copiando proyecto"
# Si el ZIP está en el directorio actual
if [ -f "cleanflow_agents.zip" ]; then
    $SUDO cp cleanflow_agents.zip /tmp/
    cd /tmp && $SUDO unzip -o cleanflow_agents.zip
    $SUDO cp -r cleanflow_agents/* "$APP_DIR/"
    log "Proyecto copiado desde ZIP"
# Si el directorio existe
elif [ -d "cleanflow_agents" ]; then
    $SUDO cp -r cleanflow_agents/* "$APP_DIR/"
    log "Proyecto copiado desde directorio"
else
    warn "No se encontró cleanflow_agents.zip ni directorio"
    warn "Sube el ZIP al droplet y cópialo manualmente a $APP_DIR/"
    # Crear estructura vacía para que el resto del script funcione
    $SUDO mkdir -p "$APP_DIR"/{agents,core,config,utils,templates}
fi

step "5/8 — Configurando entorno virtual"
cd "$APP_DIR"
$SUDO python3 -m venv venv
$SUDO "$APP_DIR/venv/bin/pip" install --upgrade pip setuptools wheel
$SUDO "$APP_DIR/venv/bin/pip" install -r requirements.txt 2>/dev/null || {
    warn "requirements.txt no encontrado, instalando dependencias manualmente"
    $SUDO "$APP_DIR/venv/bin/pip" install \
        supabase>=2.0.0 \
        openai>=1.12.0 \
        requests>=2.31.0 \
        APScheduler>=3.10.0 \
        python-dotenv>=1.0.0 \
        tenacity>=8.2.0
}
log "Entorno virtual configurado"

step "6/8 — Configurando variables de entorno"
ENV_FILE="$APP_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
    cat > "$ENV_FILE" << 'ENVEOF'
# ============================================================
# CleanFlow Agents — Variables de Entorno
# EDITA ESTOS VALORES con tus credenciales reales
# ============================================================

# ─── SUPABASE (REQUERIDO) ─────────────────────
SUPABASE_URL=https://tu-proyecto.supabase.co
SUPABASE_SERVICE_KEY=eyJ...tu-service-role-key
SUPABASE_ANON_KEY=eyJ...tu-anon-key

# ─── OPENAI (REQUERIDO) ──────────────────────
OPENAI_API_KEY=sk-...tu-api-key
OPENAI_MODEL=gpt-4o-mini

# ─── GOOGLE CUSTOM SEARCH (REQUERIDO) ────────
GOOGLE_API_KEY=AIza...tu-api-key
GOOGLE_CX=tu-search-engine-id

# ─── BRIGHT DATA (OPCIONAL) ──────────────────
BRIGHTDATA_API_KEY=
BRIGHTDATA_ZONE=scraping_browser
BRIGHTDATA_ENABLED=false

# ─── TELEGRAM (RECOMENDADO) ──────────────────
TELEGRAM_BOT_TOKEN=123456:ABC-tu-bot-token
TELEGRAM_CHAT_ID=-100tu-chat-id

# ─── EMAIL SMTP (RECOMENDADO) ────────────────
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=tu-email@gmail.com
SMTP_PASSWORD=tu-app-password
FROM_NAME=CleanFlow Services
FROM_EMAIL=tu-email@gmail.com
ENVEOF
    warn "Archivo .env creado — EDÍTALO con tus credenciales:"
    warn "  nano $ENV_FILE"
else
    log ".env ya existe, no se sobreescribe"
fi

step "7/8 — Configurando Supervisor (auto-restart)"

# Proceso principal: Scheduler
$SUDO cat > /etc/supervisor/conf.d/cleanflow-scheduler.conf << SUPEOF
[program:cleanflow-scheduler]
command=$APP_DIR/venv/bin/python $APP_DIR/scheduler.py
directory=$APP_DIR
user=cleanflow
autostart=true
autorestart=true
startsecs=10
startretries=5
redirect_stderr=true
stdout_logfile=/var/log/cleanflow/scheduler.log
stdout_logfile_maxbytes=10MB
stdout_logfile_backups=5
environment=HOME="/home/cleanflow",PATH="$APP_DIR/venv/bin:/usr/bin"
SUPEOF

# Proceso de pipeline manual (one-shot, no autostart)
$SUDO cat > /etc/supervisor/conf.d/cleanflow-pipeline.conf << SUPEOF
[program:cleanflow-pipeline]
command=$APP_DIR/venv/bin/python $APP_DIR/enhanced_orchestrator.py full
directory=$APP_DIR
user=cleanflow
autostart=false
autorestart=false
redirect_stderr=true
stdout_logfile=/var/log/cleanflow/pipeline.log
stdout_logfile_maxbytes=10MB
stdout_logfile_backups=3
environment=HOME="/home/cleanflow",PATH="$APP_DIR/venv/bin:/usr/bin"
SUPEOF

# Telegram Bot interactivo
$SUDO cat > /etc/supervisor/conf.d/cleanflow-telegram.conf << SUPEOF
[program:cleanflow-telegram]
command=$APP_DIR/venv/bin/python $APP_DIR/telegram_bot.py
directory=$APP_DIR
user=cleanflow
autostart=true
autorestart=true
startsecs=5
startretries=5
redirect_stderr=true
stdout_logfile=/var/log/cleanflow/telegram_bot.log
stdout_logfile_maxbytes=10MB
stdout_logfile_backups=5
environment=HOME="/home/cleanflow",PATH="$APP_DIR/venv/bin:/usr/bin"
SUPEOF

$SUDO mkdir -p /var/log/cleanflow
$SUDO chown -R cleanflow:cleanflow /var/log/cleanflow
$SUDO chown -R cleanflow:cleanflow "$APP_DIR"

$SUDO supervisorctl reread
$SUDO supervisorctl update
log "Supervisor configurado"

step "8/8 — Configurando firewall y seguridad"
$SUDO ufw default deny incoming
$SUDO ufw default allow outgoing
$SUDO ufw allow ssh
$SUDO ufw --force enable
$SUDO systemctl enable fail2ban
$SUDO systemctl start fail2ban
log "Firewall y fail2ban activos"

# ─── CREAR SCRIPT DE GESTIÓN ──────────────────

$SUDO cat > /usr/local/bin/cleanflow << 'MGMTEOF'
#!/bin/bash
APP_DIR="/home/cleanflow/app"
VENV="$APP_DIR/venv/bin/python"

case "${1:-help}" in
    start)
        sudo supervisorctl start cleanflow-scheduler
        sudo supervisorctl start cleanflow-telegram
        echo "Scheduler + Telegram Bot iniciados"
        ;;
    stop)
        sudo supervisorctl stop cleanflow-scheduler
        sudo supervisorctl stop cleanflow-telegram
        echo "Scheduler + Telegram Bot detenidos"
        ;;
    restart)
        sudo supervisorctl restart cleanflow-scheduler
        sudo supervisorctl restart cleanflow-telegram
        echo "Scheduler + Telegram Bot reiniciados"
        ;;
    status)
        sudo supervisorctl status cleanflow-scheduler cleanflow-telegram
        ;;
    bot)
        case "${2:-status}" in
            start)  sudo supervisorctl start cleanflow-telegram ;;
            stop)   sudo supervisorctl stop cleanflow-telegram ;;
            restart) sudo supervisorctl restart cleanflow-telegram ;;
            logs)   tail -f /var/log/cleanflow/telegram_bot.log ;;
            *)      sudo supervisorctl status cleanflow-telegram ;;
        esac
        ;;
    run)
        shift
        cd "$APP_DIR" && $VENV enhanced_orchestrator.py "$@"
        ;;
    test)
        cd "$APP_DIR" && $VENV enhanced_orchestrator.py full --max-queries 2 --dry-run
        ;;
    logs)
        tail -f /var/log/cleanflow/scheduler.log
        ;;
    bot-logs)
        tail -f /var/log/cleanflow/telegram_bot.log
        ;;
    dashboard)
        cd "$APP_DIR" && $VENV enhanced_orchestrator.py dashboard
        ;;
    edit-env)
        nano "$APP_DIR/.env"
        ;;
    help|*)
        echo ""
        echo "  CleanFlow Agents — Comandos de gestión"
        echo "  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        echo "  cleanflow start         Inicia scheduler + telegram bot"
        echo "  cleanflow stop          Detiene todo"
        echo "  cleanflow restart       Reinicia todo"
        echo "  cleanflow status        Ver estado de servicios"
        echo ""
        echo "  cleanflow bot start     Inicia solo el bot de Telegram"
        echo "  cleanflow bot stop      Detiene solo el bot"
        echo "  cleanflow bot logs      Logs del bot en tiempo real"
        echo ""
        echo "  cleanflow run full      Pipeline completo (manual)"
        echo "  cleanflow run scrape    Solo scraping + calificación"
        echo "  cleanflow run match     Solo matching + propuestas"
        echo "  cleanflow run followup  Solo follow-ups"
        echo ""
        echo "  cleanflow test          Test rápido (2 queries, dry-run)"
        echo "  cleanflow dashboard     Ver estado de agentes"
        echo "  cleanflow logs          Logs del scheduler"
        echo "  cleanflow bot-logs      Logs del telegram bot"
        echo "  cleanflow edit-env      Editar variables de entorno"
        echo ""
        ;;
esac
MGMTEOF

$SUDO chmod +x /usr/local/bin/cleanflow

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  ✅ CleanFlow Agents instalado exitosamente!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "  ${CYAN}PASOS SIGUIENTES:${NC}"
echo ""
echo -e "  1. Edita las credenciales:"
echo -e "     ${YELLOW}cleanflow edit-env${NC}"
echo ""
echo -e "  2. Ejecuta el SQL en Supabase:"
echo -e "     ${YELLOW}cat $APP_DIR/supabase_schema.sql${NC}"
echo ""
echo -e "  3. Test rápido (sin enviar nada):"
echo -e "     ${YELLOW}cleanflow test${NC}"
echo ""
echo -e "  4. Pipeline completo manual:"
echo -e "     ${YELLOW}cleanflow run full --max-queries 5${NC}"
echo ""
echo -e "  5. Iniciar scheduler automático:"
echo -e "     ${YELLOW}cleanflow start${NC}"
echo ""
echo -e "  6. Ver logs:"
echo -e "     ${YELLOW}cleanflow logs${NC}"
echo ""
echo -e "  ${CYAN}Ayuda: ${YELLOW}cleanflow help${NC}"
echo ""
