"""Turn staging rows into the canonical holdings schema (see pipeline/__init__.py HOLDING_COLUMNS).

Everything inferred is recorded in geography_method / data_quality_flag so a reader can always tell
what was disclosed from what was derived.
"""
from __future__ import annotations

import csv
import hashlib
import re
from functools import lru_cache

import pandas as pd

from . import CONFIG, HOLDING_COLUMNS, PIPELINE_VERSION

ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}\d$")
SEDOL_RE = re.compile(r"^[B-DF-HJ-NP-TV-Z0-9]{6}\d$")
TICKER_RE = re.compile(r"^[A-Z0-9.]{1,8}( [A-Z]{2})?$")
CCY_MARKER = re.compile(r"\b(COMMON|ORD|ORDINARY|SHS|STOCK|SHARES)\b.*\b(AUD|USD|EUR|GBP|JPY|HKD|CNY|CNH|INR|KRW|TWD|CAD|CHF|SEK|DKK|NOK|BRL|ZAR|SGD|NZD|SAR|AED|IDR|THB|MYR|MXN|PLN)\b")
CCY_COUNTRY = {"AUD": "Australia", "USD": "United States", "EUR": "Europe", "GBP": "United Kingdom", "JPY": "Japan", "HKD": "Hong Kong",
               "CNY": "China", "CNH": "China", "INR": "India", "KRW": "South Korea", "TWD": "Taiwan", "CAD": "Canada", "CHF": "Switzerland",
               "SEK": "Sweden", "DKK": "Denmark", "NOK": "Norway", "BRL": "Brazil", "ZAR": "South Africa", "SGD": "Singapore", "NZD": "New Zealand",
               "SAR": "Saudi Arabia", "AED": "United Arab Emirates", "IDR": "Indonesia", "THB": "Thailand", "MYR": "Malaysia", "MXN": "Mexico", "PLN": "Poland"}
ISIN_COUNTRY = {"AU": "Australia", "US": "United States", "GB": "United Kingdom", "JP": "Japan", "HK": "Hong Kong", "CN": "China", "IN": "India",
                "KR": "South Korea", "TW": "Taiwan", "CA": "Canada", "CH": "Switzerland", "SE": "Sweden", "DK": "Denmark", "NO": "Norway", "FI": "Finland",
                "DE": "Germany", "FR": "France", "NL": "Netherlands", "IT": "Italy", "ES": "Spain", "BE": "Belgium", "IE": "Ireland", "AT": "Austria",
                "PT": "Portugal", "BR": "Brazil", "ZA": "South Africa", "SG": "Singapore", "NZ": "New Zealand", "SA": "Saudi Arabia", "AE": "United Arab Emirates",
                "ID": "Indonesia", "TH": "Thailand", "MY": "Malaysia", "MX": "Mexico", "PL": "Poland", "KY": "Cayman Islands", "BM": "Bermuda", "LU": "Luxembourg",
                "JE": "Jersey", "GG": "Guernsey", "VG": "British Virgin Islands", "IL": "Israel", "PH": "Philippines", "CL": "Chile", "GR": "Greece", "TR": "Türkiye",
                "QA": "Qatar", "KW": "Kuwait", "CZ": "Czechia", "HU": "Hungary", "EG": "Egypt", "VN": "Vietnam", "PE": "Peru", "CO": "Colombia"}
AU_NAME_HINTS = re.compile(r"\b(australia|commonwealth bank|westpac|nab\b|national australia|anz\b|bhp|rio tinto|woolworths|wesfarmers|telstra|macquarie|csl\b|fortescue|woodside|transurban|goodman|treasury corp|tcorp|qtc\b|nsw|queensland|victoria|pty ltd|limited\s*\(au\)|asx)", re.I)
ADR_RE = re.compile(r"\b(ADR|ADS|GDR|CDI|CHESS)\b", re.I)


@lru_cache(maxsize=1)
def _asset_map() -> list[dict]:
    with open(CONFIG / "asset_class_map.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    rows.sort(key=lambda r: int(r["priority"]))
    for r in rows:
        r["rx"] = re.compile(r["pattern"], re.I)
    return rows


@lru_cache(maxsize=1)
def _option_map() -> list[dict]:
    with open(CONFIG / "option_type_map.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    rows.sort(key=lambda r: int(r["priority"]))
    for r in rows:
        r["rx"] = re.compile(r["pattern"], re.I)
    return rows


def _mkey(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", (s or "").lower())).strip()


@lru_cache(maxsize=1)
def _managers() -> dict[str, dict]:
    with open(CONFIG / "managers.csv", newline="", encoding="utf-8") as f:
        return {_mkey(r["alias"]): r for r in csv.DictReader(f)}


def classify_asset(*texts: str) -> tuple[str, str, int, str]:
    """Return (apra_asset_class, bucket, is_listed, matched_on). First text that matches wins."""
    for label, text in zip(("section", "sheet", "holding_name"), texts):
        if not text:
            continue
        for r in _asset_map():
            if r["rx"].search(text):
                return r["apra_asset_class"], r["bucket"], int(r["is_listed"]), label
    return "Other", "Other", 0, "none"


def option_type_for(name: str) -> str:
    for r in _option_map():
        if r["rx"].search(name or ""):
            return r["option_type"]
    return "Other"


def resolve_manager(name: str) -> str:
    key = _mkey(name)
    if not key:
        return ""
    m = _managers()
    if key in m:
        return m[key]["manager_id"]
    # fuzzy: alias contained in name or name contained in alias
    for alias, row in m.items():
        if len(alias) >= 5 and (alias in key or key in alias):
            return row["manager_id"]
    return ""


def split_identifier(raw: str) -> tuple[str, str, str]:
    s = (raw or "").strip().upper()
    if ISIN_RE.match(s):
        return s, "", ""
    if SEDOL_RE.match(s) and len(s) == 7:
        return "", s, ""
    if s and TICKER_RE.match(s):
        return "", "", s
    return "", "", ""


def infer_geography(row: pd.Series) -> tuple[str, str]:
    name, isin, cur = row.get("holding_name", "") or "", row.get("isin", "") or "", (row.get("currency", "") or "").upper()
    geo_raw = (row.get("geography_raw", "") or "").strip()
    if geo_raw:
        return geo_raw, "disclosed"
    if isin and isin[:2] in ISIN_COUNTRY:
        return ISIN_COUNTRY[isin[:2]], "isin_prefix"
    if ADR_RE.search(name):
        return "International (depositary receipt)", "name_marker_adr"
    m = CCY_MARKER.search(name.upper())
    if m:
        return CCY_COUNTRY.get(m.group(2), "International"), "name_marker_currency"
    cls = row.get("apra_asset_class", "")
    if cls.startswith("Australian") or cls in {"Cash", "Australian Cash"}:
        return "Australia", "asset_class_default"
    if AU_NAME_HINTS.search(name):
        return "Australia", "name_hint"
    if cur and cur in CCY_COUNTRY and cur != "AUD":
        return CCY_COUNTRY[cur], "currency_column"
    if cls.startswith("International") or cls in {"Private Equity", "Alternatives"}:
        return "International", "asset_class_default"
    return "Unknown", "unknown"


def _hedge(section: str, subsection: str, cls: str) -> str:
    text = f"{section} {subsection}".lower()
    if "unhedged" in text:
        return "Unhedged"
    if "hedged" in text:
        return "Hedged"
    return "Domestic" if cls.startswith("Australian") or cls == "Cash" else "Unhedged" if cls.startswith("International") else ""


def normalise(staging: pd.DataFrame, *, fund_id: str, fund_name: str, rse_abn: str, snapshot_date: str, file_hashes: dict[str, str] | None = None) -> pd.DataFrame:
    if staging.empty:
        return pd.DataFrame(columns=HOLDING_COLUMNS)
    df = staging.copy()
    df["holding_name"] = df["holding_name"].astype(str).str.strip()
    cls = df.apply(lambda r: classify_asset(str(r.get("section", "")) + " " + str(r.get("subsection", "")), str(r.get("sheet", "")), r["holding_name"]), axis=1, result_type="expand")
    df[["apra_asset_class", "bucket", "is_listed", "_cls_on"]] = cls
    ids = df["security_id"].fillna("").astype(str).apply(split_identifier)
    df[["isin", "sedol", "ticker"]] = pd.DataFrame(ids.tolist(), index=df.index)
    geo = df.apply(infer_geography, axis=1, result_type="expand")
    df[["geography", "geography_method"]] = geo
    df["manager_name_raw"] = df["manager"].fillna("").astype(str).str.strip()

    def mgmt(r):
        sub = str(r.get("subsection", "")).lower()
        if "extern" in sub:
            return "External-pooled"
        if "intern" in sub:
            return "Internal"
        if r["manager_name_raw"]:
            return "External-pooled"
        if not (r["isin"] or r["sedol"] or r["ticker"]) and resolve_manager(r["holding_name"]):
            return "External-pooled"
        return "Unknown"
    df["management_type"] = df.apply(mgmt, axis=1)
    df.loc[(df["management_type"] == "External-pooled") & (df["manager_name_raw"] == ""), "manager_name_raw"] = df["holding_name"]
    df["manager_id"] = df["manager_name_raw"].apply(resolve_manager)
    df["hedge_status"] = df.apply(lambda r: _hedge(str(r.get("section", "")), str(r.get("subsection", "")), r["apra_asset_class"]), axis=1)
    df["option_type"] = df["option_name"].astype(str).apply(option_type_for)
    df["is_default"] = (df["option_type"] == "Default").astype(int)
    df["market_value_aud"] = pd.to_numeric(df["value"], errors="coerce")
    df["weight_pct_disclosed"] = pd.to_numeric(df["weight"], errors="coerce")
    # weights disclosed as fractions (0.0123) rather than percent
    frac = df.groupby("option_name")["weight_pct_disclosed"].transform("sum")
    df.loc[(frac > 0.5) & (frac < 1.5), "weight_pct_disclosed"] *= 100
    totals = df.groupby("option_name")["market_value_aud"].transform("sum")
    df["weight_pct_calc"] = (df["market_value_aud"] / totals * 100).round(4)

    def flag(r):
        parts = []
        if r["_cls_on"] == "holding_name":
            parts.append("asset class inferred from holding name (no section heading)")
        elif r["_cls_on"] == "none":
            parts.append("asset class unresolved -> Other")
        if r["geography_method"] not in {"disclosed", "isin_prefix"}:
            parts.append(f"geography via {r['geography_method']}")
        if pd.isna(r["market_value_aud"]):
            parts.append("no market value disclosed")
        if r["management_type"] == "External-pooled" and not r["manager_id"]:
            parts.append("manager not in managers.csv")
        return "; ".join(parts) if parts else "Clean"
    df["data_quality_flag"] = df.apply(flag, axis=1)

    df["fund_id"], df["fund_name"], df["rse_abn"], df["snapshot_date"] = fund_id, fund_name, rse_abn, snapshot_date
    df["option_id"] = ""
    df["source_table"] = df["section"].fillna("").astype(str)
    df["holding_name_raw"] = df["holding_name"]
    df["security_id_raw"] = df["security_id"].fillna("").astype(str)
    df["maturity_date"] = pd.to_datetime(df["maturity"], errors="coerce", dayfirst=True).dt.date.astype(str).replace("NaT", "")
    df["gics_sector"] = df.get("sector_raw", "").fillna("") if "sector_raw" in df else ""
    df["reporting_date"] = df["reporting_date"].astype(str).replace({"None": snapshot_date, "NaT": snapshot_date, "nan": snapshot_date})
    df["source_file_hash"] = df["source_file"].map(file_hashes or {}).fillna("")
    df["pipeline_version"] = PIPELINE_VERSION
    df["currency"] = df["currency"].fillna("").astype(str).str.upper().str[:3]
    df["holding_id"] = df.apply(lambda r: hashlib.sha1(f"{snapshot_date}|{fund_id}|{r['option_name']}|{r['source_table']}|{r['holding_name']}|{r['security_id_raw']}|{r['market_value_aud']}|{r['row']}".encode()).hexdigest()[:16], axis=1)
    for c in HOLDING_COLUMNS:
        if c not in df:
            df[c] = None
    return df[HOLDING_COLUMNS]
