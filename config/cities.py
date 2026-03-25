"""
Top 10 Cities Configuration — Ciudades con mayor demanda de
servicios de limpieza comercial en USA.

Criterios de selección:
  - Volumen de construcción comercial (Sun Belt boom)
  - Contratos federales NAICS 561720 por estado
  - Crecimiento de oficinas y retail
  - Facilidad de entrada (licencias mínimas)
  - Proximidad geográfica para cobertura eficiente

Cada ciudad incluye:
  - Coordenadas GPS (para Google Places API)
  - Estado y county FIPS (para USASpending)
  - Portal de procurement estatal/municipal
  - URLs de open data (Socrata/CKAN)
  - Términos de búsqueda locales
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class CityConfig:
    """Configuración completa de una ciudad target."""
    name: str
    state: str
    state_fips: str          # Código FIPS del estado (para APIs federales)
    county: str
    lat: float
    lng: float
    tier: int                # 1=prioridad alta, 2=media

    # Procurement portals (URLs para scraping de RFPs)
    procurement_urls: List[str] = field(default_factory=list)

    # Socrata Open Data portal (API gratis, sin key)
    socrata_domain: str = ""
    socrata_datasets: List[str] = field(default_factory=list)

    # Keywords de búsqueda locales (adiciones al patrón base)
    local_keywords: List[str] = field(default_factory=list)

    # Google Places search radius (metros)
    search_radius: int = 40000  # 40km default


# ═══════════════════════════════════════════════
#  TOP 10 CITIES — Mayor demanda de limpieza comercial
# ═══════════════════════════════════════════════

CITIES: Dict[str, CityConfig] = {

    # ── TIER 1: Máxima prioridad (Sun Belt + alto volumen federal) ──

    "dallas": CityConfig(
        name="Dallas",
        state="TX",
        state_fips="48",
        county="Dallas County",
        lat=32.7767,
        lng=-96.7970,
        tier=1,
        procurement_urls=[
            "https://www.txsmartbuy.com/sp",
            "https://www.dallascityhall.com/departments/procurement/Pages/default.aspx",
            "https://www.dallascounty.org/departments/purchasing/",
        ],
        socrata_domain="www.dallasopendata.com",
        socrata_datasets=["bids", "contracts", "procurement"],
        local_keywords=[
            "DFW", "Fort Worth", "Arlington", "Plano", "Irving",
            "Dallas ISD", "DART", "Dallas County",
        ],
        search_radius=50000,
    ),

    "houston": CityConfig(
        name="Houston",
        state="TX",
        state_fips="48",
        county="Harris County",
        lat=29.7604,
        lng=-95.3698,
        tier=1,
        procurement_urls=[
            "https://www.txsmartbuy.com/sp",
            "https://purchasing.houstontx.gov/",
            "https://www.harriscountytx.gov/purchasing",
        ],
        socrata_domain="data.harriscountytx.gov",
        socrata_datasets=["purchasing"],
        local_keywords=[
            "Harris County", "Houston ISD", "The Woodlands",
            "Sugar Land", "Katy", "Port of Houston",
            "Texas Medical Center", "Energy Corridor",
        ],
        search_radius=60000,
    ),

    "phoenix": CityConfig(
        name="Phoenix",
        state="AZ",
        state_fips="04",
        county="Maricopa County",
        lat=33.4484,
        lng=-112.0740,
        tier=1,
        procurement_urls=[
            "https://procure.az.gov/bso/",
            "https://www.phoenix.gov/finance/procurement",
            "https://www.maricopa.gov/3770/Procurement",
        ],
        socrata_domain="www.phoenixopendata.com",
        socrata_datasets=["procurement", "contracts"],
        local_keywords=[
            "Maricopa County", "Scottsdale", "Mesa", "Tempe",
            "Chandler", "Gilbert", "Glendale", "Phoenix Sky Harbor",
        ],
        search_radius=50000,
    ),

    "miami": CityConfig(
        name="Miami",
        state="FL",
        state_fips="12",
        county="Miami-Dade County",
        lat=25.7617,
        lng=-80.1918,
        tier=1,
        procurement_urls=[
            "https://www.miamidade.gov/global/business/procurement.page",
            "https://vendor.myfloridamarketplace.com/",
            "https://www.miamigov.com/Government/Departments-Organizations/Department-of-Procurement",
        ],
        socrata_domain="datahub-miamidade.opendata.arcgis.com",
        local_keywords=[
            "Miami-Dade", "Brickell", "Doral", "Coral Gables",
            "Fort Lauderdale", "Broward", "Palm Beach",
            "Miami International Airport",
        ],
        search_radius=50000,
    ),

    "atlanta": CityConfig(
        name="Atlanta",
        state="GA",
        state_fips="13",
        county="Fulton County",
        lat=33.7490,
        lng=-84.3880,
        tier=1,
        procurement_urls=[
            "https://www.atlantaga.gov/government/departments/procurement",
            "https://doas.ga.gov/state-purchasing",
            "https://www.fultoncountyga.gov/services/purchasing-and-contract-compliance",
        ],
        socrata_domain="data.atlantaga.gov",
        local_keywords=[
            "Fulton County", "DeKalb County", "Cobb County",
            "Buckhead", "Midtown", "Hartsfield-Jackson Airport",
            "Sandy Springs", "Marietta", "Gwinnett",
        ],
        search_radius=50000,
    ),

    # ── TIER 1: Alto volumen + crecimiento rápido ──

    "nashville": CityConfig(
        name="Nashville",
        state="TN",
        state_fips="47",
        county="Davidson County",
        lat=36.1627,
        lng=-86.7816,
        tier=1,
        procurement_urls=[
            "https://www.nashville.gov/departments/general-services/procurement",
            "https://www.tn.gov/generalservices/procurement.html",
        ],
        socrata_domain="data.nashville.gov",
        socrata_datasets=["purchasing", "contracts"],
        local_keywords=[
            "Davidson County", "Metro Nashville", "Franklin",
            "Murfreesboro", "HCA Healthcare", "Vanderbilt",
        ],
    ),

    "tampa": CityConfig(
        name="Tampa",
        state="FL",
        state_fips="12",
        county="Hillsborough County",
        lat=27.9506,
        lng=-82.4572,
        tier=1,
        procurement_urls=[
            "https://vendor.myfloridamarketplace.com/",
            "https://www.tampagov.net/purchasing",
            "https://www.hillsboroughcounty.org/en/businesses/purchasing-and-contracts",
        ],
        socrata_domain="data.tampagov.net",
        local_keywords=[
            "Hillsborough County", "St Petersburg", "Clearwater",
            "Tampa Bay", "MacDill AFB", "USF",
        ],
    ),

    # ── TIER 2: Mercados grandes con buena oportunidad ──

    "las_vegas": CityConfig(
        name="Las Vegas",
        state="NV",
        state_fips="32",
        county="Clark County",
        lat=36.1699,
        lng=-115.1398,
        tier=2,
        procurement_urls=[
            "https://purchasing.state.nv.us/",
            "https://www.lasvegasnevada.gov/Business/Purchasing",
            "https://www.clarkcountynv.gov/government/departments/purchasing_and_contracts/index.php",
        ],
        local_keywords=[
            "Clark County", "Henderson", "North Las Vegas",
            "The Strip", "Convention Center", "McCarran",
            "Nellis AFB", "UNLV",
        ],
        search_radius=40000,
    ),

    "austin": CityConfig(
        name="Austin",
        state="TX",
        state_fips="48",
        county="Travis County",
        lat=30.2672,
        lng=-97.7431,
        tier=2,
        procurement_urls=[
            "https://www.txsmartbuy.com/sp",
            "https://www.austintexas.gov/department/purchasing",
            "https://www.traviscountytx.gov/purchasing",
        ],
        socrata_domain="data.austintexas.gov",
        socrata_datasets=["purchasing", "contract-awards"],
        local_keywords=[
            "Travis County", "Round Rock", "Cedar Park",
            "San Marcos", "Tesla Gigafactory", "Austin-Bergstrom",
            "UT Austin", "Domain",
        ],
    ),

    "charlotte": CityConfig(
        name="Charlotte",
        state="NC",
        state_fips="37",
        county="Mecklenburg County",
        lat=35.2271,
        lng=-80.8431,
        tier=2,
        procurement_urls=[
            "https://charlottenc.gov/DoingBusiness/Pages/Procurement.aspx",
            "https://www.mecknc.gov/FinancialServices/Purchasing/Pages/default.aspx",
            "https://ncadmin.nc.gov/government-agencies/purchase-contract",
        ],
        local_keywords=[
            "Mecklenburg County", "Uptown Charlotte", "SouthPark",
            "Ballantyne", "Lake Norman", "Bank of America",
            "Charlotte Douglas Airport",
        ],
    ),
}


# ═══════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════

def get_all_cities() -> List[CityConfig]:
    """Retorna todas las ciudades."""
    return list(CITIES.values())


def get_tier1_cities() -> List[CityConfig]:
    """Retorna solo ciudades Tier 1."""
    return [c for c in CITIES.values() if c.tier == 1]


def get_cities_by_state(state: str) -> List[CityConfig]:
    """Retorna ciudades de un estado específico."""
    return [c for c in CITIES.values() if c.state == state]


def get_all_states() -> List[str]:
    """Retorna lista única de estados."""
    return list(set(c.state for c in CITIES.values()))


def get_all_state_fips() -> List[str]:
    """Retorna lista única de FIPS codes."""
    return list(set(c.state_fips for c in CITIES.values()))


def get_city_coords() -> Dict[str, tuple]:
    """Retorna dict {city_name: (lat, lng)}."""
    return {c.name: (c.lat, c.lng) for c in CITIES.values()}


def get_all_local_keywords() -> List[str]:
    """Retorna todos los keywords locales combinados."""
    all_kw = []
    for c in CITIES.values():
        all_kw.extend(c.local_keywords)
    return list(set(all_kw))


# ═══════════════════════════════════════════════
#  STATE PROCUREMENT PORTALS
# ═══════════════════════════════════════════════

STATE_PORTALS = {
    "TX": {
        "name": "Texas SmartBuy",
        "url": "https://www.txsmartbuy.com/sp",
        "api": None,  # No public API — scraping required
        "notes": "Covers all TX state agencies. Search by keyword.",
    },
    "AZ": {
        "name": "Arizona Procurement Portal",
        "url": "https://procure.az.gov/bso/",
        "api": None,
        "notes": "ProcureAZ — search solicitations by category.",
    },
    "FL": {
        "name": "MyFloridaMarketplace (MFMP)",
        "url": "https://vendor.myfloridamarketplace.com/",
        "api": None,
        "notes": "Central portal for all FL state procurement. Free vendor registration.",
    },
    "NV": {
        "name": "Nevada State Purchasing",
        "url": "https://purchasing.state.nv.us/",
        "api": None,
        "notes": "Covers state agencies. Smaller volume than TX/FL.",
    },
    "GA": {
        "name": "Georgia Procurement",
        "url": "https://doas.ga.gov/state-purchasing",
        "api": None,
        "notes": "Team Georgia Marketplace. Growing procurement volume.",
    },
    "TN": {
        "name": "Tennessee Procurement",
        "url": "https://www.tn.gov/generalservices/procurement.html",
        "api": None,
        "notes": "Edison system. Search active solicitations.",
    },
    "NC": {
        "name": "NC eProcurement",
        "url": "https://ncadmin.nc.gov/government-agencies/purchase-contract",
        "api": None,
        "notes": "Covers state and many local agencies.",
    },
}


# ═══════════════════════════════════════════════
#  FREE API REGISTRY — APIs sin costo por fuente
# ═══════════════════════════════════════════════

FREE_APIS = {
    "sam_gov": {
        "name": "SAM.gov Opportunities API",
        "url": "https://api.sam.gov/prod/opportunities/v2/search",
        "auth": "API key (free, register at sam.gov)",
        "rate_limit": "1,000/day",
        "data": "Federal contract opportunities, RFPs, awards",
        "coverage": "All 50 states, all federal agencies",
        "cost": "$0",
    },
    "usaspending": {
        "name": "USASpending.gov API",
        "url": "https://api.usaspending.gov/api/v2/",
        "auth": "None (fully open)",
        "rate_limit": "Generous (no published limit)",
        "data": "Federal awards, spending, contractors",
        "coverage": "All federal spending data",
        "cost": "$0",
    },
    "google_cse": {
        "name": "Google Custom Search API",
        "url": "https://www.googleapis.com/customsearch/v1",
        "auth": "API key (free tier)",
        "rate_limit": "100/day free, $5/1000 after",
        "data": "Web search results — RFPs, bids, vendor requests",
        "coverage": "Entire internet",
        "cost": "$0 (first 100/day)",
    },
    "google_places": {
        "name": "Google Places API",
        "url": "https://maps.googleapis.com/maps/api/place/",
        "auth": "API key (same as Google CSE)",
        "rate_limit": "$200 free credit/month",
        "data": "Property managers, facilities companies, real estate offices",
        "coverage": "All US cities",
        "cost": "$0 (within free credit)",
    },
    "socrata_open_data": {
        "name": "Socrata Open Data (SODA) API",
        "url": "https://{domain}/resource/{dataset}.json",
        "auth": "None (fully open, app token optional)",
        "rate_limit": "1,000/hour without token, 40,000/hour with",
        "data": "City/county procurement, contracts, vendor data",
        "coverage": "Phoenix, Austin, Houston, Nashville, Atlanta, Tampa",
        "cost": "$0",
    },
    "census_business": {
        "name": "US Census Business Patterns API",
        "url": "https://api.census.gov/data/2022/cbp",
        "auth": "API key (free, census.gov)",
        "rate_limit": "500/day",
        "data": "Number of businesses by NAICS per county — market sizing",
        "coverage": "All US counties",
        "cost": "$0",
    },
    "rss_feeds": {
        "name": "Public RSS Feeds",
        "url": "Various (BidsUSA, PublicPurchase)",
        "auth": "None",
        "rate_limit": "Unlimited",
        "data": "New RFPs, bids, solicitations",
        "coverage": "National",
        "cost": "$0",
    },
}
