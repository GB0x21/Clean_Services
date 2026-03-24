"""
Cliente de Supabase — CRUD para todas las tablas del sistema.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from supabase import create_client, Client
from config.settings import config

logger = logging.getLogger("cleanflow.db")


class SupabaseDB:
    """Wrapper sobre el cliente de Supabase con métodos específicos de CleanFlow."""

    def __init__(self):
        if not config.supabase.url or not config.supabase.service_key:
            raise ValueError("SUPABASE_URL y SUPABASE_SERVICE_KEY son requeridos")
        self.client: Client = create_client(
            config.supabase.url, config.supabase.service_key
        )

    # ─── OPPORTUNITIES ────────────────────────────

    def insert_opportunity(self, data: Dict[str, Any]) -> Dict:
        data["scraped_at"] = datetime.now(timezone.utc).isoformat()
        data.setdefault("status", "new")
        result = self.client.table("opportunities").insert(data).execute()
        logger.info(f"Opportunity inserted: {data.get('title', 'N/A')}")
        return result.data[0] if result.data else {}

    def get_opportunities(
        self,
        status: Optional[str] = None,
        min_score: Optional[float] = None,
        limit: int = 50,
    ) -> List[Dict]:
        query = self.client.table("opportunities").select("*")
        if status:
            query = query.eq("status", status)
        if min_score is not None:
            query = query.gte("quality_score", min_score)
        query = query.order("scraped_at", desc=True).limit(limit)
        result = query.execute()
        return result.data or []

    def update_opportunity(self, opp_id: str, data: Dict[str, Any]) -> Dict:
        result = (
            self.client.table("opportunities").update(data).eq("id", opp_id).execute()
        )
        return result.data[0] if result.data else {}

    def check_duplicate(self, source_url: str) -> bool:
        result = (
            self.client.table("opportunities")
            .select("id")
            .eq("source_url", source_url)
            .execute()
        )
        return bool(result.data)

    # ─── SUBCONTRACTORS ────────────────────────────

    def get_subcontractors(
        self,
        city: Optional[str] = None,
        service_type: Optional[str] = None,
        active_only: bool = True,
    ) -> List[Dict]:
        query = self.client.table("subcontractors").select("*")
        if active_only:
            query = query.eq("status", "active")
        if city:
            query = query.eq("primary_city", city)
        query = query.order("quality_score", desc=True)
        result = query.execute()
        return result.data or []

    def update_subcontractor(self, sub_id: str, data: Dict[str, Any]) -> Dict:
        result = (
            self.client.table("subcontractors")
            .update(data)
            .eq("id", sub_id)
            .execute()
        )
        return result.data[0] if result.data else {}

    # ─── BIDS ──────────────────────────────────────

    def insert_bid(self, data: Dict[str, Any]) -> Dict:
        data["created_at"] = datetime.now(timezone.utc).isoformat()
        data.setdefault("status", "draft")
        data.setdefault("generated_by_ai", True)
        result = self.client.table("bids").insert(data).execute()
        logger.info(f"Bid created for opportunity: {data.get('opportunity_id')}")
        return result.data[0] if result.data else {}

    def get_bids(self, opportunity_id: Optional[str] = None) -> List[Dict]:
        query = self.client.table("bids").select("*")
        if opportunity_id:
            query = query.eq("opportunity_id", opportunity_id)
        result = query.order("created_at", desc=True).execute()
        return result.data or []

    def update_bid(self, bid_id: str, data: Dict[str, Any]) -> Dict:
        result = self.client.table("bids").update(data).eq("id", bid_id).execute()
        return result.data[0] if result.data else {}

    # ─── SCRAPING LOGS ─────────────────────────────

    def log_scraping_run(self, data: Dict[str, Any]) -> Dict:
        data["timestamp"] = datetime.now(timezone.utc).isoformat()
        result = self.client.table("scraping_logs").insert(data).execute()
        return result.data[0] if result.data else {}

    # ─── FOLLOW-UPS ────────────────────────────────

    def get_pending_followups(self) -> List[Dict]:
        now = datetime.now(timezone.utc).isoformat()
        result = (
            self.client.table("bids")
            .select("*, opportunities(*)")
            .eq("status", "sent")
            .lte("next_followup_date", now)
            .execute()
        )
        return result.data or []

    def log_followup(self, bid_id: str, followup_number: int, method: str) -> Dict:
        data = {
            "bid_id": bid_id,
            "followup_number": followup_number,
            "method": method,
            "sent_at": datetime.now(timezone.utc).isoformat(),
        }
        result = self.client.table("followup_logs").insert(data).execute()
        return result.data[0] if result.data else {}


# Singleton
db = SupabaseDB()
