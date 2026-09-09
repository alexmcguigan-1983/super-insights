"""Super Insights pipeline.

Harvests Australian superannuation Portfolio Holdings Disclosure (PHD) files and
APRA statistics, normalises them into one canonical schema, validates, enriches,
and builds the JSON that powers the static dashboard in /site.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"
RAW = ROOT / "raw"
CURATED = ROOT / "curated"
QUARANTINE = ROOT / "quarantine"
SITE_DATA = ROOT / "site" / "data"
PIPELINE_VERSION = "1.0.0"

BUCKETS = [
    "Australian Equity",
    "International Equity",
    "Australian Fixed Income",
    "International Fixed Income",
    "Infrastructure",
    "Property",
    "Private Equity",
    "Alternatives",
    "Cash",
    "Other",
]

GROWTH_BUCKETS = {"Australian Equity", "International Equity", "Infrastructure", "Property", "Private Equity", "Alternatives"}
ILLIQUID_CLASSES = {
    "Private Equity", "Private Credit", "Australian Unlisted Property", "International Unlisted Property",
    "Australian Unlisted Infrastructure", "International Unlisted Infrastructure", "Unlisted Alternatives", "Unlisted Equity",
}

HOLDING_COLUMNS = [
    "holding_id", "snapshot_date", "fund_id", "fund_name", "rse_abn", "option_name", "option_id", "option_type",
    "is_default", "reporting_date", "source_table", "apra_asset_class", "bucket", "management_type",
    "manager_name_raw", "manager_id", "holding_name_raw", "holding_name", "security_id_raw", "isin", "sedol",
    "ticker", "units", "face_value", "coupon", "maturity_date", "currency", "market_value_aud",
    "weight_pct_disclosed", "weight_pct_calc", "is_listed", "geography", "geography_method", "gics_sector",
    "hedge_status", "data_quality_flag", "source_file", "source_file_hash", "pipeline_version",
]
