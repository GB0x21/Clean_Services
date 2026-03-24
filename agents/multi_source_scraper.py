"""
Multi-Source Lead Scraper — APIs públicas de USA para contratos de limpieza.

Fuentes implementadas:
  1. SAM.gov API (Federal) — contratos gubernamentales federales, NAICS 561720
  2. Google Custom Search — RFPs municipales, estatales, privados
  3. USASpending.gov API — premios y contratos federales ejecutados
  4. RFPdb.com RSS — RFPs públicos sin subscripción
  5. Data.gov / OpenData Portals — portales de datos abiertos de ciudades
  6. Google Maps/Places API — property managers y facilities companies
  7. State Procurement Portals — scraping de portales estatales (AZ, TX, NV, FL)

NAICS codes relevantes:
  561720 — Janitorial Services
  561730 — Landscaping Services
  561790 — Other Services to Buildings and Dwellings
  238990 — All Other Specialty Trade Contractors
"""
import time
import logging
import json
import re
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse, quote_plus

import requests

from agents.base_agent import BaseAgent
from config.settings import (
    config, SEARCH_PATTERNS, EXCLUDED_DOMAINS, RELEVANCE_KEYWORDS
)

logger = logging.getLogger("cleanflow.multi_scraper")

# NAICS codes para limpieza comercial
CLEANING_NAICS = ["561720", "561730", "561790", "238990"]

# Keywords de limpieza para filtrado
CLEANING_KEYWORDS = [
    "janitorial", "cleaning", "custodial", "housekeeping", "sanitation",
    "maintenance", "janitor", "floor care", "window cleaning",
    "building maintenance", "facilities maintenance", "commercial cleaning",
    "office cleaning", "carpet cleaning", "pressure washing",
    "landscaping", "grounds maintenance", "post construction",
]

# Portales de procurement estatal
STATE_PROCUREMENT_URLS = {
    "AZ": "https://procure.az.gov",
    "TX": "https://www.txsmartbuy.com",
    "NV": "https://purchasing.state.nv.us",
    "FL": "https://vendor.myfloridamarketplace.com",
    "GA": "https://doas.ga.gov/state-purchasing",
}


class MultiSourceScraperAgent(BaseAgent):
    """
    Scraper multi-fuente que combina APIs públicas de USA.
    Cada fuente es independiente — si una falla, las demás continúan.
    """

    def __init__(self):
        super().__init__("multi_scraper")
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "CleanFlow-LeadBot/2.0 (commercial cleaning lead generation)"
        })

    # ════════════════════════════════════════════════
    #  FUENTE 1: SAM.gov — Contratos Federales
    # ════════════════════════════════════════════════

    def _scrape_sam_gov(self) -> List[Dict]:
        """
        SAM.gov Opportunities API — contratos federales.
        API Key gratuita, 1000 requests/día.
        Registrarse en: https://sam.gov/content/entity-registration
        """
        api_key = config.google.api_key  # Reusar o usar SAM_GOV_API_KEY
        sam_key = getattr(config, 'sam_gov_api_key', '') or \
                  __import__('os').environ.get('SAM_GOV_API_KEY', '')

        if not sam_key:
            logger.info("SAM.gov API key no configurada, saltando")
            return []

        leads = []
        base_url = "https://api.sam.gov/prod/opportunities/v2/search"

        # Buscar por cada NAICS code
        for naics in CLEANING_NAICS:
            posted_from = (datetime.now() - timedelta(days=30)).strftime("%m/%d/%Y")
            posted_to = datetime.now().strftime("%m/%d/%Y")

            params = {
                "api_key": sam_key,
                "limit": 25,
                "offset": 0,
                "postedFrom": posted_from,
                "postedTo": posted_to,
                "ncode": naics,
                "ptype": "p,k,o",  # presol, combined synopsis, solicitation
            }

            try:
                resp = self.session.get(base_url, params=params, timeout=30)
                resp.raise_for_status()
                data = resp.json()

                for opp in data.get("opportunitiesData", []):
                    # Filtrar por estados target
                    place = opp.get("placeOfPerformance", {})
                    state_code = place.get("state", {}).get("code", "")
                    city_name = place.get("city", {}).get("name", "")

                    # Extraer contacto
                    contacts = opp.get("pointOfContact", [])
                    primary = next(
                        (c for c in contacts if c.get("type") == "primary"), {}
                    )

                    lead = {
                        "title": opp.get("title", ""),
                        "description": opp.get("description", "")[:500] if opp.get("description") else "",
                        "source_url": f"https://sam.gov/opp/{opp.get('noticeId', '')}/view",
                        "source_platform": "sam.gov",
                        "city": city_name,
                        "state": state_code,
                        "client_type": "government",
                        "client_name": opp.get("department", "") or opp.get("subTier", ""),
                        "deadline": opp.get("responseDeadLine"),
                        "contact_name": primary.get("fullName", ""),
                        "contact_email": primary.get("email", ""),
                        "contact_phone": primary.get("phone", ""),
                        "naics_code": naics,
                        "solicitation_number": opp.get("solicitationNumber", ""),
                        "opportunity_type": opp.get("type", ""),
                    }
                    leads.append(lead)

                logger.info(f"SAM.gov NAICS {naics}: {len(data.get('opportunitiesData', []))} results")
                time.sleep(1)  # Rate limit

            except Exception as e:
                logger.error(f"SAM.gov error (NAICS {naics}): {e}")

        logger.info(f"SAM.gov total: {len(leads)} leads")
        return leads

    # ════════════════════════════════════════════════
    #  FUENTE 2: Google Custom Search
    # ════════════════════════════════════════════════

    def _scrape_google_cse(self, max_queries: int = 40) -> List[Dict]:
        """Google Custom Search API — RFPs de todo tipo."""
        if not config.google.api_key or not config.google.cx:
            logger.info("Google CSE no configurado, saltando")
            return []

        leads = []
        queries_done = 0

        cities = config.criteria.tier_1_cities + config.criteria.tier_2_cities
        city_state = {
            "Phoenix": "AZ", "Las Vegas": "NV", "Austin": "TX",
            "Dallas": "TX", "Houston": "TX", "Tampa": "FL",
            "Atlanta": "GA", "Nashville": "TN",
        }

        for city in cities:
            state = city_state.get(city, "")
            for pattern in SEARCH_PATTERNS[:8]:  # Top 8 patterns
                if queries_done >= max_queries:
                    break

                query = f"{pattern} {city} {state}"
                try:
                    resp = self.session.get(
                        "https://www.googleapis.com/customsearch/v1",
                        params={
                            "key": config.google.api_key,
                            "cx": config.google.cx,
                            "q": query,
                            "num": 10,
                            "dateRestrict": "m1",
                        },
                        timeout=15,
                    )
                    if resp.status_code == 429:
                        logger.warning("Google CSE rate limit hit")
                        break
                    resp.raise_for_status()

                    for item in resp.json().get("items", []):
                        url = item.get("link", "")
                        domain = urlparse(url).netloc.lower()
                        if any(ex in domain for ex in EXCLUDED_DOMAINS):
                            continue

                        title = item.get("title", "")
                        snippet = item.get("snippet", "")
                        text = f"{title} {snippet}".lower()
                        if not any(kw in text for kw in RELEVANCE_KEYWORDS):
                            continue

                        leads.append({
                            "title": title,
                            "description": snippet,
                            "source_url": url,
                            "source_platform": domain,
                            "city": city,
                            "state": state,
                        })

                    queries_done += 1
                    time.sleep(2)

                except Exception as e:
                    logger.error(f"Google CSE error: {e}")
                    queries_done += 1

        logger.info(f"Google CSE: {len(leads)} leads ({queries_done} queries)")
        return leads

    # ════════════════════════════════════════════════
    #  FUENTE 3: USASpending.gov — Premios Federales
    # ════════════════════════════════════════════════

    def _scrape_usaspending(self) -> List[Dict]:
        """
        USASpending.gov API — premios y contratos federales ejecutados.
        API 100% gratuita, sin API key necesaria.
        Útil para encontrar contratos que se renuevan anualmente.
        """
        leads = []
        base_url = "https://api.usaspending.gov/api/v2/search/spending_by_award/"

        for naics in CLEANING_NAICS[:2]:  # Top 2 NAICS
            payload = {
                "filters": {
                    "time_period": [
                        {
                            "start_date": (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d"),
                            "end_date": datetime.now().strftime("%Y-%m-%d"),
                        }
                    ],
                    "naics_codes": {"require": [naics]},
                    "award_type_codes": ["A", "B", "C", "D"],  # Contracts
                    "place_of_performance_locations": [
                        {"country": "USA", "state": s}
                        for s in config.criteria.active_states
                    ],
                },
                "fields": [
                    "Award ID", "Recipient Name", "Description",
                    "Award Amount", "Awarding Agency", "Place of Performance City",
                    "Place of Performance State Code", "Start Date", "End Date",
                    "generated_internal_id",
                ],
                "limit": 25,
                "page": 1,
                "sort": "Award Amount",
                "order": "desc",
            }

            try:
                resp = self.session.post(base_url, json=payload, timeout=30)
                resp.raise_for_status()
                data = resp.json()

                for award in data.get("results", []):
                    desc = (award.get("Description") or "").lower()
                    if not any(kw in desc for kw in CLEANING_KEYWORDS):
                        continue

                    award_id = award.get("generated_internal_id", "")
                    leads.append({
                        "title": f"{award.get('Description', '')[:100]}",
                        "description": (
                            f"Agency: {award.get('Awarding Agency', '')}. "
                            f"Current vendor: {award.get('Recipient Name', '')}. "
                            f"Amount: ${award.get('Award Amount', 0):,.0f}"
                        ),
                        "source_url": f"https://www.usaspending.gov/award/{award_id}",
                        "source_platform": "usaspending.gov",
                        "city": award.get("Place of Performance City", ""),
                        "state": award.get("Place of Performance State Code", ""),
                        "client_type": "government",
                        "client_name": award.get("Awarding Agency", ""),
                        "estimated_value": award.get("Award Amount"),
                        "opportunity_type": "renewal_target",
                    })

                logger.info(
                    f"USASpending NAICS {naics}: "
                    f"{len(data.get('results', []))} awards found"
                )
                time.sleep(1)

            except Exception as e:
                logger.error(f"USASpending error: {e}")

        logger.info(f"USASpending total: {len(leads)} leads")
        return leads

    # ════════════════════════════════════════════════
    #  FUENTE 4: Google Places API — Property Managers
    # ════════════════════════════════════════════════

    def _scrape_google_places(self) -> List[Dict]:
        """
        Google Places API (Nearby Search) — encuentra property management
        companies y facilities managers que podrían necesitar limpieza.
        Usa la misma Google API key.
        """
        if not config.google.api_key:
            return []

        leads = []
        search_types = [
            "property management company",
            "commercial real estate office",
            "facilities management company",
            "building management company",
        ]

        city_coords = {
            "Phoenix": (33.4484, -112.0740),
            "Las Vegas": (36.1699, -115.1398),
            "Austin": (30.2672, -97.7431),
            "Dallas": (32.7767, -96.7970),
            "Houston": (29.7604, -95.3698),
            "Tampa": (27.9506, -82.4572),
        }

        for city, (lat, lng) in city_coords.items():
            for search_type in search_types[:2]:  # Top 2 para no agotar quota
                try:
                    resp = self.session.get(
                        "https://maps.googleapis.com/maps/api/place/nearbysearch/json",
                        params={
                            "key": config.google.api_key,
                            "location": f"{lat},{lng}",
                            "radius": 30000,  # 30km
                            "keyword": search_type,
                            "type": "establishment",
                        },
                        timeout=15,
                    )
                    resp.raise_for_status()
                    data = resp.json()

                    for place in data.get("results", [])[:5]:  # Top 5 per search
                        leads.append({
                            "title": f"Property Manager: {place.get('name', '')}",
                            "description": (
                                f"{search_type.title()} in {city}. "
                                f"Rating: {place.get('rating', 'N/A')}. "
                                f"Address: {place.get('vicinity', '')}"
                            ),
                            "source_url": f"https://www.google.com/maps/place/?q=place_id:{place.get('place_id', '')}",
                            "source_platform": "google_places",
                            "city": city,
                            "state": city_coords and self._city_to_state(city),
                            "client_type": "property_management",
                            "client_name": place.get("name", ""),
                            "opportunity_type": "outreach_target",
                        })

                    time.sleep(1)

                except Exception as e:
                    logger.error(f"Google Places error: {e}")

        logger.info(f"Google Places: {len(leads)} property managers")
        return leads

    # ════════════════════════════════════════════════
    #  FUENTE 5: State/City Open Data Portals
    # ════════════════════════════════════════════════

    def _scrape_open_data(self) -> List[Dict]:
        """
        Portales de datos abiertos de ciudades/estados.
        Muchos usan Socrata API (SODA) — 100% gratis, sin API key.
        """
        leads = []

        # Portales Socrata conocidos con datos de procurement
        socrata_portals = [
            {
                "name": "Phoenix Open Data",
                "domain": "www.phoenixopendata.com",
                "dataset": "procurement",
            },
            {
                "name": "City of Austin",
                "domain": "data.austintexas.gov",
                "dataset": "procurement",
            },
            {
                "name": "Harris County (Houston)",
                "domain": "data.harriscountytx.gov",
                "dataset": "procurement",
            },
        ]

        for portal in socrata_portals:
            try:
                # Socrata SODA API — buscar contratos de limpieza
                url = f"https://{portal['domain']}/resource/{portal['dataset']}.json"
                params = {
                    "$where": "lower(description) like '%cleaning%' OR lower(description) like '%janitorial%'",
                    "$limit": 20,
                    "$order": ":created_at DESC",
                }
                resp = self.session.get(url, params=params, timeout=15)
                if resp.status_code == 200:
                    for item in resp.json():
                        leads.append({
                            "title": item.get("title", item.get("description", ""))[:100],
                            "description": item.get("description", ""),
                            "source_url": f"https://{portal['domain']}",
                            "source_platform": portal["name"],
                            "client_type": "government",
                            "opportunity_type": "open_data",
                        })
            except Exception as e:
                logger.debug(f"Open data {portal['name']}: {e}")

        logger.info(f"Open Data portals: {len(leads)} leads")
        return leads

    # ════════════════════════════════════════════════
    #  FUENTE 6: RSS Feeds de RFPs públicos
    # ════════════════════════════════════════════════

    def _scrape_rss_feeds(self) -> List[Dict]:
        """RSS feeds públicos de procurement y RFPs."""
        leads = []

        rss_urls = [
            # BidsUSA
            "https://www.bidsusa.net/rss/bidsusa.xml",
            # PublicPurchase
            "https://www.publicpurchase.com/gems/bid/bidRSS",
        ]

        for rss_url in rss_urls:
            try:
                resp = self.session.get(rss_url, timeout=15)
                if resp.status_code != 200:
                    continue

                # Parse XML básico sin dependencia extra
                content = resp.text
                items = re.findall(
                    r"<item>(.*?)</item>", content, re.DOTALL
                )

                for item_xml in items[:20]:
                    title_match = re.search(r"<title>(.*?)</title>", item_xml)
                    desc_match = re.search(r"<description>(.*?)</description>", item_xml, re.DOTALL)
                    link_match = re.search(r"<link>(.*?)</link>", item_xml)

                    title = title_match.group(1) if title_match else ""
                    desc = desc_match.group(1) if desc_match else ""
                    link = link_match.group(1) if link_match else ""

                    # Filtrar solo limpieza
                    text = f"{title} {desc}".lower()
                    if not any(kw in text for kw in CLEANING_KEYWORDS):
                        continue

                    leads.append({
                        "title": title[:200],
                        "description": re.sub(r"<[^>]+>", "", desc)[:500],
                        "source_url": link,
                        "source_platform": urlparse(rss_url).netloc,
                        "opportunity_type": "rfp",
                    })

            except Exception as e:
                logger.debug(f"RSS {rss_url}: {e}")

        logger.info(f"RSS feeds: {len(leads)} leads")
        return leads

    # ════════════════════════════════════════════════
    #  UTILIDADES
    # ════════════════════════════════════════════════

    def _city_to_state(self, city: str) -> str:
        mapping = {
            "Phoenix": "AZ", "Las Vegas": "NV", "Austin": "TX",
            "Dallas": "TX", "Houston": "TX", "Tampa": "FL",
            "Atlanta": "GA", "Nashville": "TN", "Charlotte": "NC",
            "Raleigh": "NC", "Salt Lake City": "UT",
        }
        return mapping.get(city, "")

    def _deduplicate(self, leads: List[Dict]) -> List[Dict]:
        """Deduplica por URL y contra Supabase."""
        seen_urls = set()
        unique = []
        for lead in leads:
            url = lead.get("source_url", "")
            if not url or url in seen_urls:
                continue
            if self.db.check_duplicate(url):
                continue
            seen_urls.add(url)
            unique.append(lead)
        return unique

    # ════════════════════════════════════════════════
    #  RUN PRINCIPAL
    # ════════════════════════════════════════════════

    def run(
        self,
        max_queries: Optional[int] = None,
        sources: Optional[List[str]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Ejecuta todas las fuentes en paralelo (secuencial por ahora).
        
        sources: lista de fuentes a activar. Default = todas.
          Opciones: "sam_gov", "google_cse", "usaspending", 
                    "google_places", "open_data", "rss"
        """
        all_sources = sources or [
            "sam_gov", "google_cse", "usaspending",
            "google_places", "open_data", "rss",
        ]

        all_leads: List[Dict] = []
        source_stats = {}

        for source_name in all_sources:
            try:
                if source_name == "sam_gov":
                    results = self._scrape_sam_gov()
                elif source_name == "google_cse":
                    results = self._scrape_google_cse(max_queries=max_queries or 40)
                elif source_name == "usaspending":
                    results = self._scrape_usaspending()
                elif source_name == "google_places":
                    results = self._scrape_google_places()
                elif source_name == "open_data":
                    results = self._scrape_open_data()
                elif source_name == "rss":
                    results = self._scrape_rss_feeds()
                else:
                    logger.warning(f"Unknown source: {source_name}")
                    results = []

                source_stats[source_name] = len(results)
                all_leads.extend(results)

            except Exception as e:
                logger.error(f"Source {source_name} failed: {e}")
                source_stats[source_name] = f"ERROR: {e}"

        # Deduplicar
        unique_leads = self._deduplicate(all_leads)

        # Log
        self.db.log_scraping_run({
            "source_platform": "multi_source",
            "queries_executed": sum(
                v for v in source_stats.values() if isinstance(v, int)
            ),
            "total_results": len(all_leads),
            "unique_results": len(unique_leads),
            "status": "completed",
        })

        return {
            "leads": unique_leads,
            "total_raw": len(all_leads),
            "total_unique": len(unique_leads),
            "source_stats": source_stats,
        }
