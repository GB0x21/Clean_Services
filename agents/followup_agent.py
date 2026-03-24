"""
Follow-up Agent — Gestiona el seguimiento automático de propuestas enviadas.
Lógica:
  - 3 días sin respuesta → Email de seguimiento suave
  - 7 días sin respuesta → Segundo contacto con valor añadido
  - 14 días sin respuesta → Último intento + archivar como cold
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from agents.base_agent import BaseAgent
from config.settings import config

logger = logging.getLogger("cleanflow.followup")

FOLLOWUP_TEMPLATES = {
    1: {
        "days": 3,
        "subject_prefix": "Following up: ",
        "system": (
            "You write professional, brief follow-up emails for a commercial cleaning company. "
            "This is the FIRST follow-up (3 days after initial proposal). "
            "Be polite, brief, and add a small value nugget. Max 150 words."
        ),
        "user": (
            "Write a first follow-up email for this proposal:\n"
            "Client: {client_name}\nCity: {city}, {state}\n"
            "Original bid: ${bid_amount:,.0f}\nService: {service_types}\n"
            "Original subject: {email_subject}\n\n"
            "Tone: Friendly check-in, mention you're available for questions. "
            "Add a brief tip about commercial cleaning best practices."
        ),
    },
    2: {
        "days": 7,
        "subject_prefix": "Quick update: ",
        "system": (
            "You write professional follow-up emails. This is the SECOND follow-up (7 days). "
            "Offer added value — perhaps a free walkthrough or a case study. Max 150 words."
        ),
        "user": (
            "Write a second follow-up email:\n"
            "Client: {client_name}\nCity: {city}, {state}\n"
            "Original bid: ${bid_amount:,.0f}\nService: {service_types}\n\n"
            "Offer a free on-site walkthrough to better understand their needs. "
            "Mention flexibility on pricing or schedule."
        ),
    },
    3: {
        "days": 14,
        "subject_prefix": "Last check: ",
        "system": (
            "You write final follow-up emails. This is the LAST attempt (14 days). "
            "Be gracious, leave the door open, and keep it very short. Max 100 words."
        ),
        "user": (
            "Write a final follow-up email:\n"
            "Client: {client_name}\nCity: {city}, {state}\n"
            "Service: {service_types}\n\n"
            "Be gracious. Say you understand they may have chosen another vendor. "
            "Leave the door open for future needs. Thank them for their time."
        ),
    },
}


class FollowUpAgent(BaseAgent):
    """
    Revisa bids enviadas que no han recibido respuesta,
    genera y envía follow-ups automáticos según el timeline.
    """

    def __init__(self):
        super().__init__("followup")

    # ─── DETERMINE FOLLOWUP NUMBER ─────────────────

    def _get_followup_number(self, bid: Dict) -> Optional[int]:
        """Determina qué número de follow-up corresponde."""
        sent_at = bid.get("sent_at")
        if not sent_at:
            return None

        if isinstance(sent_at, str):
            sent_at = datetime.fromisoformat(sent_at.replace("Z", "+00:00"))

        now = datetime.now(timezone.utc)
        days_since = (now - sent_at).days
        last_followup = bid.get("last_followup_number", 0)

        for num in [1, 2, 3]:
            template = FOLLOWUP_TEMPLATES[num]
            if days_since >= template["days"] and last_followup < num:
                return num
        return None

    # ─── GENERATE FOLLOWUP ─────────────────────────

    def _generate_followup_email(
        self, bid: Dict, opportunity: Dict, followup_num: int
    ) -> Dict[str, str]:
        """Genera el email de follow-up con IA."""
        template = FOLLOWUP_TEMPLATES[followup_num]

        prompt = template["user"].format(
            client_name=opportunity.get("client_name", "Valued Client"),
            city=opportunity.get("city", ""),
            state=opportunity.get("state", ""),
            bid_amount=bid.get("bid_amount", 0),
            service_types=", ".join(opportunity.get("service_types", ["cleaning"])),
            email_subject=bid.get("email_subject", "Commercial Cleaning Proposal"),
        )

        body = self.ai.ask(
            template["system"], prompt, temperature=0.6, max_tokens=500
        )

        subject = template["subject_prefix"] + bid.get(
            "email_subject", "Our Cleaning Services Proposal"
        )

        return {"subject": subject, "body": body}

    # ─── SEND FOLLOWUP ─────────────────────────────

    def _send_followup(
        self,
        bid: Dict,
        opportunity: Dict,
        followup_num: int,
        email_content: Dict[str, str],
    ) -> bool:
        """Envía el follow-up y registra en DB."""
        contact_email = opportunity.get("contact_email")

        if not contact_email:
            logger.info(
                f"Sin email de contacto para: {opportunity.get('title', '')[:40]}"
            )
            # Aún así loguear que se intentó
            self.db.log_followup(bid["id"], followup_num, "skipped_no_email")
            return False

        # Enviar email
        success = self.notifier.send_email(
            to_email=contact_email,
            subject=email_content["subject"],
            body_html=f"<div style='font-family: Arial, sans-serif;'>"
                      f"{email_content['body'].replace(chr(10), '<br>')}</div>",
            to_name=opportunity.get("contact_name"),
        )

        if success:
            # Actualizar bid
            self.db.update_bid(
                bid["id"],
                {
                    "last_followup_number": followup_num,
                    "last_followup_date": datetime.now(timezone.utc).isoformat(),
                },
            )
            self.db.log_followup(bid["id"], followup_num, "email_sent")

            # Si es el último follow-up, marcar como cold
            if followup_num >= 3:
                self.db.update_bid(bid["id"], {"status": "cold"})
                self.db.update_opportunity(
                    opportunity.get("id"), {"status": "cold"}
                )

        return success

    # ─── RUN PRINCIPAL ─────────────────────────────

    def run(self, **kwargs) -> Dict[str, Any]:
        """Revisa todos los bids enviados y ejecuta follow-ups pendientes."""
        # Obtener bids enviadas (status = 'sent')
        sent_bids = self.db.get_bids()
        sent_bids = [b for b in sent_bids if b.get("status") == "sent"]

        followups_sent = 0
        followups_skipped = 0
        archived = 0

        for bid in sent_bids:
            followup_num = self._get_followup_number(bid)
            if followup_num is None:
                continue

            # Obtener oportunidad asociada
            opp_data = bid.get("opportunities")
            if not opp_data:
                opps = self.db.get_opportunities()
                opp_data = next(
                    (o for o in opps if o.get("id") == bid.get("opportunity_id")),
                    {},
                )

            # Generar y enviar
            email_content = self._generate_followup_email(bid, opp_data, followup_num)
            sent = self._send_followup(bid, opp_data, followup_num, email_content)

            if sent:
                followups_sent += 1
                logger.info(
                    f"Follow-up #{followup_num} enviado: "
                    f"{opp_data.get('title', '')[:40]}"
                )
            else:
                followups_skipped += 1

            if followup_num >= 3:
                archived += 1

        # Notificar resumen si hubo actividad
        if followups_sent > 0:
            self.notifier.send_telegram(
                f"📬 *Follow-up Report*\n"
                f"Enviados: {followups_sent}\n"
                f"Saltados: {followups_skipped}\n"
                f"Archivados: {archived}"
            )

        return {
            "bids_checked": len(sent_bids),
            "followups_sent": followups_sent,
            "followups_skipped": followups_skipped,
            "archived_as_cold": archived,
        }
