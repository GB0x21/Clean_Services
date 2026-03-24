"""
Lead Scraper Agent — Busca oportunidades de limpieza comercial.
Fuentes: Google Custom Search API, y opcionalmente Bright Data.
"""
import time
import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests
from agents.base_agent import BaseAgent
from config.settings import (
    config, SEARCH_PATTERNS, EXCLUDED_DOMAINS, RELEVANCE_KEYWORDS
)

logger = logging.getLogger("cleanflow.scraper")


class LeadScraperAgent(BaseAgent):
    """
    Genera combinaciones ciudad + patrón de búsqueda,
    ejecuta queries en Google CSE, filtra resultados,
    y retorna leads crudos para calificación.
    """

    def __init__(self):
        super().__init__("lead_scraper")

    # ─── GENERAR QUERIES ───────────────────────────

    def _build_queries(self) -> List[Dict[str, str]]:
        """Combina ciudades target con patrones de búsqueda."""
        cities = []
        criteria = config.criteria
        for city in criteria.tier_1_cities:
            state = self._city_to_state(city)
            cities.append({"city": city, "state": state})
        for city in criteria.tier_2_cities:
            state = self._city_to_state(city)
            cities.append({"city": city, "state": state})

        queries = []
        for city_info in cities:
            for pattern in SEARCH_PATTERNS:
                query_str = f'{pattern} {city_info["city"]} {city_info["state"]}'
                queries.append({
                    "query": query_str,
                    "city": city_info["city"],
                    "state": city_info["state"],
                    "pattern": pattern,
                })
        logger.info(f"Generadas {len(queries)} queries de búsqueda")
        return queries

    def _city_to_state(self, city: str) -> str:
        mapping = {
            "Phoenix": "AZ", "Las Vegas": "NV", "Austin": "TX",
            "Dallas": "TX", "Houston": "TX", "Tampa": "FL",
            "Atlanta": "GA", "Nashville": "TN", "Charlotte": "NC",
            "Raleigh": "NC", "Salt Lake City": "UT",
        }
        return mapping.get(city, "")

    # ─── GOOGLE CUSTOM SEARCH ─────────────────────

    def _search_google(self, query: str, num: int = 10) -> List[Dict]:
        """Ejecuta una búsqueda en Google Custom Search API."""
        if not config.google.api_key or not config.google.cx:
            logger.warning("Google CSE no configurado")
            return []
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": config.google.api_key,
            "cx": config.google.cx,
            "q": query,
            "num": min(num, 10),
            "dateRestrict": "m1",  # último mes
        }
        try:
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            items = data.get("items", [])
            return items
        except requests.exceptions.HTTPError as e:
            if resp.status_code == 429:
                logger.warning("Google CSE rate limit, esperando 60s...")
                time.sleep(60)
                return []
            logger.error(f"Google CSE error: {e}")
            return []
        except Exception as e:
            logger.error(f"Google CSE error: {e}")
            return []

    # ─── FILTRAR RESULTADOS ────────────────────────

    def _is_excluded_domain(self, url: str) -> bool:
        domain = urlparse(url).netloc.lower()
        return any(excl in domain for excl in EXCLUDED_DOMAINS)

    def _has_relevant_keywords(self, title: str, snippet: str) -> bool:
        text = f"{title} {snippet}".lower()
        return any(kw in text for kw in RELEVANCE_KEYWORDS)

    def _filter_results(
        self, items: List[Dict], city: str, state: str
    ) -> List[Dict[str, Any]]:
        """Filtra y estructura los resultados de búsqueda."""
        filtered = []
        for item in items:
            url = item.get("link", "")
            title = item.get("title", "")
            snippet = item.get("snippet", "")

            if self._is_excluded_domain(url):
                continue
            if not self._has_relevant_keywords(title, snippet):
                continue

            filtered.append({
                "title": title,
                "description": snippet,
                "source_url": url,
                "source_platform": urlparse(url).netloc,
                "city": city,
                "state": state,
            })
        return filtered

    # ─── DEDUPLICAR ────────────────────────────────

    def _deduplicate(self, leads: List[Dict]) -> List[Dict]:
        """Elimina duplicados por URL y verifica contra DB."""
        seen_urls = set()
        unique = []
        for lead in leads:
            url = lead.get("source_url", "")
            if url in seen_urls:
                continue
            if self.db.check_duplicate(url):
                continue
            seen_urls.add(url)
            unique.append(lead)
        logger.info(f"Dedup: {len(leads)} → {len(unique)} leads únicos")
        return unique

    # ─── RUN PRINCIPAL ─────────────────────────────

    def run(self, max_queries: Optional[int] = None, **kwargs) -> Dict[str, Any]:
        queries = self._build_queries()
        if max_queries:
            queries = queries[:max_queries]

        all_leads: List[Dict] = []
        total_raw = 0
        queries_executed = 0

        for q in queries:
            items = self._search_google(q["query"])
            total_raw += len(items)
            filtered = self._filter_results(items, q["city"], q["state"])
            all_leads.extend(filtered)
            queries_executed += 1

            # Rate limiting: 2s entre queries
            time.sleep(2)

            # Log progreso cada 10 queries
            if queries_executed % 10 == 0:
                logger.info(
                    f"Progreso: {queries_executed}/{len(queries)} queries, "
                    f"{len(all_leads)} leads"
                )

        # Deduplicar
        unique_leads = self._deduplicate(all_leads)

        # Log de la corrida
        self.db.log_scraping_run({
            "source_platform": "google_search",
            "queries_executed": queries_executed,
            "total_results": total_raw,
            "filtered_results": len(all_leads),
            "unique_results": len(unique_leads),
            "status": "completed",
        })

        return {
            "leads": unique_leads,
            "queries_executed": queries_executed,
            "total_raw": total_raw,
            "total_filtered": len(all_leads),
            "total_unique": len(unique_leads),
        }
