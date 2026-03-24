"""
Sistema de Notificaciones — Telegram y Email.
"""
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

import requests
from config.settings import config

logger = logging.getLogger("cleanflow.notify")


class Notifier:
    """Envía alertas por Telegram y email."""

    # ─── TELEGRAM ──────────────────────────────────

    def send_telegram(self, message: str, parse_mode: str = "Markdown") -> bool:
        if not config.telegram.bot_token or not config.telegram.chat_id:
            logger.warning("Telegram no configurado, saltando notificación")
            return False
        url = f"https://api.telegram.org/bot{config.telegram.bot_token}/sendMessage"
        try:
            resp = requests.post(
                url,
                json={
                    "chat_id": config.telegram.chat_id,
                    "text": message,
                    "parse_mode": parse_mode,
                },
                timeout=10,
            )
            resp.raise_for_status()
            logger.info("Telegram enviado OK")
            return True
        except Exception as e:
            logger.error(f"Telegram error: {e}")
            return False

    def alert_hot_lead(self, opportunity: dict) -> bool:
        msg = (
            "🔥 *HOT LEAD ALERT!*\n\n"
            f"📋 *{opportunity.get('title', 'Sin título')}*\n"
            f"🏢 Cliente: {opportunity.get('client_name', 'TBD')}\n"
            f"📍 {opportunity.get('city', '?')}, {opportunity.get('state', '?')}\n\n"
            f"💰 Valor: ${opportunity.get('estimated_value', 0):,.0f}\n"
            f"📊 Score: {opportunity.get('quality_score', 0)}/100\n"
            f"🔗 {opportunity.get('source_url', 'N/A')}"
        )
        return self.send_telegram(msg)

    def alert_bid_ready(self, bid: dict, opportunity: dict) -> bool:
        msg = (
            "🎯 *BID LISTA PARA REVISIÓN*\n\n"
            f"📋 *{opportunity.get('title', '')}*\n"
            f"💰 Bid: ${bid.get('bid_amount', 0):,.0f}\n"
            f"📈 Margen: {bid.get('estimated_margin', 0):.0f}%\n"
            f"👷 Sub: {bid.get('subcontractor_name', 'TBD')}\n\n"
            f"[Revisar y Enviar]"
        )
        return self.send_telegram(msg)

    def alert_error(self, agent_name: str, error: str) -> bool:
        msg = (
            f"⚠️ *ERROR en {agent_name}*\n\n"
            f"```\n{error[:500]}\n```"
        )
        return self.send_telegram(msg)

    # ─── EMAIL ─────────────────────────────────────

    def send_email(
        self,
        to_email: str,
        subject: str,
        body_html: str,
        to_name: Optional[str] = None,
    ) -> bool:
        if not config.email.smtp_user:
            logger.warning("Email no configurado, saltando")
            return False
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{config.email.from_name} <{config.email.from_email}>"
            msg["To"] = f"{to_name} <{to_email}>" if to_name else to_email
            msg.attach(MIMEText(body_html, "html"))

            with smtplib.SMTP(config.email.smtp_host, config.email.smtp_port) as server:
                server.starttls()
                server.login(config.email.smtp_user, config.email.smtp_password)
                server.send_message(msg)
            logger.info(f"Email enviado a {to_email}")
            return True
        except Exception as e:
            logger.error(f"Email error: {e}")
            return False


# Singleton
notifier = Notifier()
