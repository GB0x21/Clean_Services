"""
CleanFlow Telegram Bot — Bot interactivo con botones inline.

Funcionalidades:
  - Recibe leads del pipeline y los muestra con botones
  - Botones: ✅ Email | 📱 SMS | ✅ Ambos | ❌ Rechazar
  - Al presionar, ejecuta el envío automáticamente
  - Comandos: /start, /status, /pipeline, /leads, /help
  
Requiere: python-telegram-bot>=21.0
"""
import asyncio
import json
import logging
import os
import smtplib
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Any, Dict, Optional

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from config.settings import config
from core.database import db
from core.ai_client import ai

logger = logging.getLogger("cleanflow.telegram_bot")

# ─── CONSTANTES ────────────────────────────────

# Callback data prefixes
CB_EMAIL = "action:email:"
CB_SMS = "action:sms:"
CB_BOTH = "action:both:"
CB_REJECT = "action:reject:"
CB_DETAILS = "action:details:"


# ─── GENERACIÓN DE MENSAJES ───────────────────

def format_lead_message(lead: Dict) -> str:
    """Formatea un lead para mostrar en Telegram."""
    score = lead.get("quality_score", 0)
    value = lead.get("estimated_value", 0) or 0
    classification = lead.get("classification", "?")

    # Emoji según clasificación
    if classification == "hot":
        emoji = "🔥"
    elif classification == "warm":
        emoji = "🟡"
    else:
        emoji = "🔵"

    # Emoji de fuente
    platform = lead.get("source_platform", "")
    if "sam.gov" in platform:
        source_emoji = "🏛️"
    elif "usaspending" in platform:
        source_emoji = "💰"
    elif "google_places" in platform:
        source_emoji = "📍"
    else:
        source_emoji = "🔍"

    msg = (
        f"{emoji} *{classification.upper()} LEAD* {emoji}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📋 *{_escape_md(lead.get('title', 'Sin título')[:80])}*\n\n"
    )

    if lead.get("client_name"):
        msg += f"🏢 Cliente: {_escape_md(lead['client_name'])}\n"
    if lead.get("city") or lead.get("state"):
        msg += f"📍 {_escape_md(lead.get('city', ''))}, {_escape_md(lead.get('state', ''))}\n"
    if value > 0:
        msg += f"💰 Valor: ${value:,.0f}\n"
    msg += f"📊 Score: {score}/100\n"

    if lead.get("deadline"):
        msg += f"⏰ Deadline: {_escape_md(str(lead['deadline']))}\n"

    msg += f"\n{source_emoji} Fuente: {_escape_md(platform)}\n"

    if lead.get("contact_name"):
        msg += f"👤 Contacto: {_escape_md(lead['contact_name'])}\n"
    if lead.get("contact_email"):
        msg += f"📧 Email: {_escape_md(lead['contact_email'])}\n"
    if lead.get("contact_phone"):
        msg += f"📱 Tel: {_escape_md(lead['contact_phone'])}\n"

    if lead.get("description"):
        desc = lead["description"][:150]
        msg += f"\n📝 _{_escape_md(desc)}_\n"

    if lead.get("source_url"):
        msg += f"\n🔗 [Ver oportunidad]({lead['source_url']})"

    return msg


def build_lead_keyboard(lead_id: str, has_email: bool, has_phone: bool) -> InlineKeyboardMarkup:
    """Construye el teclado inline con botones de acción."""
    buttons = []

    row1 = []
    if has_email:
        row1.append(InlineKeyboardButton("📧 Enviar Email", callback_data=f"{CB_EMAIL}{lead_id}"))
    if has_phone:
        row1.append(InlineKeyboardButton("📱 Enviar SMS", callback_data=f"{CB_SMS}{lead_id}"))
    if row1:
        buttons.append(row1)

    row2 = []
    if has_email and has_phone:
        row2.append(InlineKeyboardButton("✅ Email + SMS", callback_data=f"{CB_BOTH}{lead_id}"))
    row2.append(InlineKeyboardButton("❌ Rechazar", callback_data=f"{CB_REJECT}{lead_id}"))
    buttons.append(row2)

    buttons.append([
        InlineKeyboardButton("🔍 Ver Detalles", callback_data=f"{CB_DETAILS}{lead_id}")
    ])

    return InlineKeyboardMarkup(buttons)


def _escape_md(text: str) -> str:
    """Escapa caracteres especiales para Markdown v2."""
    if not text:
        return ""
    # Para MarkdownV1, escapar menos
    return text.replace("_", "\\_").replace("*", "\\*").replace("`", "\\`").replace("[", "\\[")


# ─── GENERACIÓN DE OUTREACH ───────────────────

def generate_outreach_email(lead: Dict) -> Dict[str, str]:
    """Genera email de outreach personalizado con IA."""
    system = (
        "You are a professional business development writer for a commercial "
        "cleaning company. Write short, professional cold outreach emails. "
        "Max 150 words. Include a clear value proposition and soft CTA."
    )
    user = (
        f"Write a cold outreach email for this lead:\n"
        f"Client: {lead.get('client_name', 'Property Manager')}\n"
        f"City: {lead.get('city', '')}, {lead.get('state', '')}\n"
        f"Context: {lead.get('title', '')}\n"
        f"Contact: {lead.get('contact_name', 'Sir/Madam')}\n\n"
        f"Offer: Professional commercial cleaning services with insured, "
        f"background-checked teams. Flexible scheduling, competitive pricing.\n\n"
        f"Return ONLY JSON: {{\"subject\": \"...\", \"body\": \"...\"}}"
    )
    result = ai.ask_json(system, user)
    return {
        "subject": result.get("subject", "Commercial Cleaning Services Inquiry"),
        "body": result.get("body", ""),
    }


def generate_outreach_sms(lead: Dict) -> str:
    """Genera SMS de outreach corto."""
    system = (
        "You are writing a professional but brief SMS for a commercial cleaning company. "
        "Max 160 characters. Include company name 'CleanFlow'. Be direct and professional."
    )
    user = (
        f"Write a cold outreach SMS for:\n"
        f"Client: {lead.get('client_name', 'a business')}\n"
        f"City: {lead.get('city', '')}\n"
        f"Context: {lead.get('title', 'commercial cleaning needs')}\n\n"
        f"Return ONLY the SMS text, nothing else."
    )
    return ai.ask(system, user, max_tokens=100)


def send_email(to_email: str, subject: str, body: str) -> bool:
    """Envía un email via SMTP."""
    if not config.email.smtp_user:
        logger.warning("SMTP no configurado")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{config.email.from_name} <{config.email.from_email}>"
        msg["To"] = to_email
        html_body = f"<div style='font-family:Arial,sans-serif;font-size:14px;'>{body.replace(chr(10), '<br>')}</div>"
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(config.email.smtp_host, config.email.smtp_port) as server:
            server.starttls()
            server.login(config.email.smtp_user, config.email.smtp_password)
            server.send_message(msg)
        return True
    except Exception as e:
        logger.error(f"Email send error: {e}")
        return False


def send_sms_via_twilio(to_phone: str, message: str) -> bool:
    """
    Envía SMS via Twilio API.
    Necesita: TWILIO_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE en .env
    """
    sid = os.environ.get("TWILIO_SID", "")
    token = os.environ.get("TWILIO_AUTH_TOKEN", "")
    from_phone = os.environ.get("TWILIO_PHONE", "")

    if not all([sid, token, from_phone]):
        logger.warning("Twilio no configurado")
        return False

    try:
        import requests
        resp = requests.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
            auth=(sid, token),
            data={
                "From": from_phone,
                "To": to_phone,
                "Body": message,
            },
            timeout=15,
        )
        resp.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Twilio SMS error: {e}")
        return False


# ─── HANDLERS DE TELEGRAM ─────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para /start."""
    await update.message.reply_text(
        "🧹 *CleanFlow Bot*\n\n"
        "Recibo leads de limpieza comercial y te dejo decidir qué hacer\\.\n\n"
        "📋 *Comandos:*\n"
        "/leads \\- Ver leads pendientes\n"
        "/pipeline \\- Ejecutar pipeline ahora\n"
        "/status \\- Estado del sistema\n"
        "/help \\- Ayuda\n\n"
        "Cuando llegue un lead, verás botones para:\n"
        "📧 Enviar Email\n"
        "📱 Enviar SMS\n"
        "✅ Ambos\n"
        "❌ Rechazar",
        parse_mode="MarkdownV2",
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para /status."""
    try:
        opps = db.get_opportunities(limit=1000)
        total = len(opps)
        by_status = {}
        for o in opps:
            s = o.get("status", "unknown")
            by_status[s] = by_status.get(s, 0) + 1

        bids = db.get_bids()

        msg = (
            f"📊 *CleanFlow Status*\n\n"
            f"📋 Oportunidades: {total}\n"
        )
        for status, count in sorted(by_status.items()):
            msg += f"  • {status}: {count}\n"
        msg += f"\n📝 Bids: {len(bids)}\n"

        await update.message.reply_text(msg, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")


async def cmd_leads(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para /leads — muestra leads pendientes con botones."""
    try:
        leads = db.get_opportunities(status="qualified", limit=10)
        if not leads:
            leads = db.get_opportunities(status="new", limit=10)

        if not leads:
            await update.message.reply_text("No hay leads pendientes 👍")
            return

        await update.message.reply_text(
            f"📋 *{len(leads)} leads pendientes:*\n", parse_mode="Markdown"
        )

        for lead in leads[:5]:  # Max 5 a la vez
            msg = format_lead_message(lead)
            keyboard = build_lead_keyboard(
                lead_id=lead.get("id", ""),
                has_email=bool(lead.get("contact_email")),
                has_phone=bool(lead.get("contact_phone")),
            )
            await update.message.reply_text(
                msg, parse_mode="Markdown", reply_markup=keyboard,
                disable_web_page_preview=True,
            )
            await asyncio.sleep(0.5)  # Anti-flood

    except Exception as e:
        await update.message.reply_text(f"Error cargando leads: {e}")


async def cmd_pipeline(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para /pipeline — ejecuta pipeline manual."""
    await update.message.reply_text("🚀 Ejecutando pipeline... esto puede tomar unos minutos")
    # Se ejecutará en background
    context.application.create_task(
        _run_pipeline_and_notify(update.effective_chat.id, context)
    )


async def _run_pipeline_and_notify(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Ejecuta el pipeline y envía los resultados como leads con botones."""
    try:
        from agents.multi_source_scraper import MultiSourceScraperAgent
        from agents.lead_qualifier import LeadQualifierAgent

        scraper = MultiSourceScraperAgent()
        qualifier = LeadQualifierAgent()

        # Scrape
        scrape_result = scraper.run(max_queries=10)
        leads = scrape_result.get("leads", [])

        await context.bot.send_message(
            chat_id,
            f"🔍 Encontrados {len(leads)} leads de {len(scrape_result.get('source_stats', {}))} fuentes"
        )

        if not leads:
            return

        # Qualify
        qualify_result = qualifier.run(leads=leads)
        qualified = qualify_result.get("qualified_leads", [])

        await context.bot.send_message(
            chat_id,
            f"✅ {len(qualified)} calificados | 🔥 {qualify_result.get('hot_leads', 0)} hot"
        )

        # Enviar cada lead calificado con botones
        for lead in qualified[:10]:
            msg = format_lead_message(lead)
            keyboard = build_lead_keyboard(
                lead_id=lead.get("id", ""),
                has_email=bool(lead.get("contact_email")),
                has_phone=bool(lead.get("contact_phone")),
            )
            await context.bot.send_message(
                chat_id, msg, parse_mode="Markdown",
                reply_markup=keyboard, disable_web_page_preview=True,
            )
            await asyncio.sleep(1)

    except Exception as e:
        await context.bot.send_message(chat_id, f"❌ Pipeline error: {e}")


# ─── CALLBACK HANDLERS (BOTONES) ──────────────

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler central para todos los botones inline."""
    query = update.callback_query
    await query.answer()  # Quita animación de loading

    data = query.data
    if not data:
        return

    # Parsear acción y lead_id
    if data.startswith(CB_EMAIL):
        lead_id = data[len(CB_EMAIL):]
        await _handle_send_email(query, lead_id)
    elif data.startswith(CB_SMS):
        lead_id = data[len(CB_SMS):]
        await _handle_send_sms(query, lead_id)
    elif data.startswith(CB_BOTH):
        lead_id = data[len(CB_BOTH):]
        await _handle_send_both(query, lead_id)
    elif data.startswith(CB_REJECT):
        lead_id = data[len(CB_REJECT):]
        await _handle_reject(query, lead_id)
    elif data.startswith(CB_DETAILS):
        lead_id = data[len(CB_DETAILS):]
        await _handle_details(query, lead_id)


async def _get_lead(lead_id: str) -> Optional[Dict]:
    """Obtiene un lead de la DB."""
    try:
        result = db.client.table("opportunities").select("*").eq("id", lead_id).execute()
        return result.data[0] if result.data else None
    except Exception:
        return None


async def _handle_send_email(query, lead_id: str):
    """Genera y envía email de outreach."""
    lead = await _get_lead(lead_id)
    if not lead or not lead.get("contact_email"):
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text("❌ No hay email de contacto para este lead")
        return

    await query.message.reply_text("📧 Generando email personalizado...")

    # Generar con IA
    email_content = generate_outreach_email(lead)

    # Enviar
    success = send_email(
        lead["contact_email"],
        email_content["subject"],
        email_content["body"],
    )

    if success:
        db.update_opportunity(lead_id, {"status": "contacted", "ai_notes": "Email sent via Telegram bot"})
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            f"✅ *Email enviado\\!*\n"
            f"📧 A: {_escape_md(lead['contact_email'])}\n"
            f"📝 Subject: _{_escape_md(email_content['subject'])}_",
            parse_mode="MarkdownV2",
        )
    else:
        await query.message.reply_text("❌ Error enviando email. Revisa configuración SMTP.")


async def _handle_send_sms(query, lead_id: str):
    """Genera y envía SMS."""
    lead = await _get_lead(lead_id)
    if not lead or not lead.get("contact_phone"):
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text("❌ No hay teléfono para este lead")
        return

    await query.message.reply_text("📱 Generando SMS...")

    sms_text = generate_outreach_sms(lead)
    success = send_sms_via_twilio(lead["contact_phone"], sms_text)

    if success:
        db.update_opportunity(lead_id, {"status": "contacted", "ai_notes": "SMS sent via Telegram bot"})
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            f"✅ *SMS enviado\\!*\n"
            f"📱 A: {_escape_md(lead['contact_phone'])}\n"
            f"📝 _{_escape_md(sms_text[:100])}_",
            parse_mode="MarkdownV2",
        )
    else:
        await query.message.reply_text("❌ Error enviando SMS. Revisa configuración Twilio.")


async def _handle_send_both(query, lead_id: str):
    """Envía email + SMS."""
    await _handle_send_email(query, lead_id)
    await asyncio.sleep(1)
    await _handle_send_sms(query, lead_id)


async def _handle_reject(query, lead_id: str):
    """Rechaza el lead."""
    db.update_opportunity(lead_id, {"status": "disqualified", "ai_notes": "Rejected via Telegram bot"})
    await query.edit_message_reply_markup(reply_markup=None)
    await query.message.reply_text("❌ Lead rechazado y archivado")


async def _handle_details(query, lead_id: str):
    """Muestra detalles completos del lead."""
    lead = await _get_lead(lead_id)
    if not lead:
        await query.message.reply_text("Lead no encontrado")
        return

    details = (
        f"🔍 *Detalles completos*\n\n"
        f"📋 {lead.get('title', 'N/A')}\n"
        f"🏢 Cliente: {lead.get('client_name', 'N/A')}\n"
        f"📍 {lead.get('city', '')}, {lead.get('state', '')}\n"
        f"💰 Valor: ${lead.get('estimated_value', 0) or 0:,.0f}\n"
        f"📊 Score: {lead.get('quality_score', 0)}/100\n"
        f"🏷️ Tipo: {lead.get('client_type', 'N/A')}\n"
        f"♻️ Recurrente: {'Sí' if lead.get('is_recurring') else 'No'}\n"
        f"📄 NAICS: {lead.get('naics_code', 'N/A')}\n"
        f"🔢 Solicitation: {lead.get('solicitation_number', 'N/A')}\n\n"
        f"👤 Contacto: {lead.get('contact_name', 'N/A')}\n"
        f"📧 Email: {lead.get('contact_email', 'N/A')}\n"
        f"📱 Tel: {lead.get('contact_phone', 'N/A')}\n\n"
        f"📝 {lead.get('description', 'Sin descripción')[:300]}\n\n"
        f"🔗 {lead.get('source_url', 'N/A')}"
    )
    await query.message.reply_text(details, parse_mode="Markdown",
                                    disable_web_page_preview=True)


# ─── FUNCIÓN PARA ENVIAR LEADS DESDE EL PIPELINE ──

async def send_lead_to_telegram(bot_token: str, chat_id: str, lead: Dict):
    """
    Función standalone para enviar un lead desde el pipeline.
    Usable desde el orchestrator sin correr el bot completo.
    """
    from telegram import Bot
    bot = Bot(token=bot_token)
    msg = format_lead_message(lead)
    keyboard = build_lead_keyboard(
        lead_id=lead.get("id", ""),
        has_email=bool(lead.get("contact_email")),
        has_phone=bool(lead.get("contact_phone")),
    )
    await bot.send_message(
        chat_id=chat_id,
        text=msg,
        parse_mode="Markdown",
        reply_markup=keyboard,
        disable_web_page_preview=True,
    )


# ─── MAIN ─────────────────────────────────────

def main():
    """Inicia el bot de Telegram."""
    token = config.telegram.bot_token
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN no configurado")
        return

    # Crear aplicación
    app = Application.builder().token(token).build()

    # Registrar handlers
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("leads", cmd_leads))
    app.add_handler(CommandHandler("pipeline", cmd_pipeline))
    app.add_handler(CommandHandler("help", cmd_start))
    app.add_handler(CallbackQueryHandler(handle_button))

    logger.info("🤖 CleanFlow Telegram Bot iniciado")
    logger.info("Esperando mensajes... (Ctrl+C para detener)")

    # Iniciar polling
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    # Cargar .env
    from pathlib import Path
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        from dotenv import load_dotenv
        load_dotenv(env_path)

    main()
