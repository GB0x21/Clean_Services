"""
CleanFlow Agents — Configuración Central
Todas las variables de entorno y constantes del sistema.
"""
import os
from dataclasses import dataclass, field
from typing import List, Dict

# ──────────────────────────────────────────────
#  ENVIRONMENT VARIABLES (.env)
# ──────────────────────────────────────────────

@dataclass
class SupabaseConfig:
    url: str = os.getenv("SUPABASE_URL", "")
    service_key: str = os.getenv("SUPABASE_SERVICE_KEY", "")
    anon_key: str = os.getenv("SUPABASE_ANON_KEY", "")

@dataclass
class OpenAIConfig:
    api_key: str = os.getenv("OPENAI_API_KEY", "")
    model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    temperature: float = 0.3

@dataclass
class GoogleSearchConfig:
    api_key: str = os.getenv("GOOGLE_API_KEY", "")
    cx: str = os.getenv("GOOGLE_CX", "")
    max_results_per_query: int = 10
    daily_limit: int = 100

@dataclass
class BrightDataConfig:
    api_key: str = os.getenv("BRIGHTDATA_API_KEY", "")
    zone: str = os.getenv("BRIGHTDATA_ZONE", "scraping_browser")
    enabled: bool = bool(os.getenv("BRIGHTDATA_ENABLED", ""))

@dataclass
class TelegramConfig:
    bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")

@dataclass
class EmailConfig:
    smtp_host: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_user: str = os.getenv("SMTP_USER", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    from_name: str = os.getenv("FROM_NAME", "CleanFlow Services")
    from_email: str = os.getenv("FROM_EMAIL", "")


# ──────────────────────────────────────────────
#  BUSINESS RULES — Deal Qualification Matrix
# ──────────────────────────────────────────────

@dataclass
class ContractCriteria:
    # Valor del contrato
    min_value: float = 3_000
    ideal_min: float = 8_000
    ideal_max: float = 40_000
    max_without_review: float = 50_000

    # Términos de pago
    ideal_payment_days: int = 15
    max_payment_days: int = 30
    reject_payment_days: int = 45

    # Licencias
    max_licenses: int = 2
    max_license_cost: float = 1_000
    max_license_time_days: int = 30

    # Scoring thresholds
    auto_pursue_threshold: float = 0.75
    review_threshold: float = 0.50
    auto_reject_threshold: float = 0.50

    # Ciudades target por tier
    tier_1_cities: List[str] = field(default_factory=lambda: [
        "Phoenix", "Las Vegas", "Austin", "Dallas", "Houston"
    ])
    tier_2_cities: List[str] = field(default_factory=lambda: [
        "Tampa", "Atlanta", "Nashville"
    ])
    tier_3_cities: List[str] = field(default_factory=lambda: [
        "Charlotte", "Raleigh", "Salt Lake City"
    ])

    # Estados actuales
    active_states: List[str] = field(default_factory=lambda: [
        "AZ", "TX", "NV", "FL"
    ])

    # Servicios preferidos
    preferred_services: List[str] = field(default_factory=lambda: [
        "commercial_cleaning",
        "office_cleaning",
        "post_construction_cleaning",
        "landscaping_basic",
        "window_cleaning_low_rise",
        "parking_lot_maintenance",
        "janitorial",
        "floor_care",
    ])

    # Servicios a rechazar
    reject_services: List[str] = field(default_factory=lambda: [
        "hazmat",
        "high_rise_exterior",
        "specialized_medical",
        "security_clearance",
        "biohazard",
    ])


# ──────────────────────────────────────────────
#  SEARCH PATTERNS
# ──────────────────────────────────────────────

SEARCH_PATTERNS: List[str] = [
    "RFP commercial cleaning services",
    "request for proposal janitorial services",
    "bid commercial cleaning contract",
    "seeking commercial cleaning vendor",
    "need janitorial services office",
    "hiring cleaning company commercial",
    "property management cleaning services needed",
    "facilities cleaning contract RFP",
    "post construction cleaning services needed",
    "office cleaning services request for quote",
]

EXCLUDED_DOMAINS: List[str] = [
    "yelp.com", "yellowpages.com", "bbb.org",
    "facebook.com", "instagram.com", "twitter.com",
    "linkedin.com", "pinterest.com", "tiktok.com",
    "wikipedia.org", "dictionary.com",
]

RELEVANCE_KEYWORDS: List[str] = [
    "cleaning", "janitorial", "maintenance", "facilities",
    "rfp", "bid", "proposal", "vendor", "procurement",
    "custodial", "sanitation", "housekeeping",
]


# ──────────────────────────────────────────────
#  SCORING WEIGHTS
# ──────────────────────────────────────────────

SCORING_WEIGHTS: Dict[str, float] = {
    "contract_value": 0.25,
    "payment_speed": 0.30,
    "low_requirements": 0.20,
    "recurrence": 0.15,
    "proximity": 0.10,
}


# ──────────────────────────────────────────────
#  SINGLETON CONFIG
# ──────────────────────────────────────────────

class Config:
    """Acceso central a toda la configuración."""
    supabase = SupabaseConfig()
    openai = OpenAIConfig()
    google = GoogleSearchConfig()
    brightdata = BrightDataConfig()
    telegram = TelegramConfig()
    email = EmailConfig()
    criteria = ContractCriteria()

config = Config()
