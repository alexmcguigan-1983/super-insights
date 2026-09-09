"""Import the reference dataset (Graeme's Super Insights JSON) as a snapshot so the dashboard has
day-one content while the first real harvest runs.

Usage:  python -m pipeline.cli import-reference path/to/super_holdings_dec2025.json [path/to/apra_saa_dec2025.json]

The reference schema is a subset of ours; imported rows are tagged pipeline_version='reference-import'
and data_quality_flag keeps the original flag with a 'REFERENCE:' prefix so they are never confused with
rows this pipeline parsed from primary sources.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

from . import CURATED, HOLDING_COLUMNS
from .normalise import classify_asset, option_type_for, resolve_manager, split_identifier

FUND_IDS = {"AustralianSuper": "australiansuper", "ART": "art", "Hostplus": "hostplus", "HESTA": "hesta", "UniSuper": "unisuper",
            "Care Super": "caresuper", "Aware Super": "aware", "REST Super": "rest", "Brighter Super": "brighter", "Equip Super": "equip",
            "NGS Super": "ngs", "Team Super": "team", "Australian Ethical": "australianethical", "Future Super": "futuresuper",
            "smartMonday": "smartmonday", "Legalsuper": "legalsuper", "Cbus": "cbus", "Vision Super": "vision", "Prime Super": "prime",
            "First Super": "firstsuper", "BUSSQ": "bussq", "GuildSuper": "guild"}


def import_holdings(path: Path, snapshot: str = "2025-12-31") -> pd.DataFrame:
    raw = json.loads(Path(path).read_text())
    df = pd.DataFrame(raw)
    fam_opt = df["fund_name"].str.split(" — ", n=1, expand=True)
    df["fund_family"], df["option_name"] = fam_opt[0].str.strip(), fam_opt[1].fillna("Default").str.strip()
    df["fund_id"] = df["fund_family"].map(FUND_IDS).fillna(df["fund_family"].str.lower().str.replace(r"\W+", "", regex=True))
    cls = df["apra_asset_class"].fillna("").apply(lambda s: classify_asset(s))
    df["bucket"] = [c[1] for c in cls]
    df["apra_asset_class"] = df["apra_asset_class"].fillna("Other")
    ids = df["isin"].fillna("").apply(split_identifier)
    df["isin"] = [i[0] for i in ids]
    df["sedol"] = ""
    df["ticker"] = df["ticker"].fillna("")
    df["management_type"] = df["sub_asset_class"].map({"Externally Managed": "External-pooled", "Internally Managed": "Internal"}).fillna("Unknown")
    mgr_level = df["data_quality_flag"].fillna("").str.contains("Manager Level", case=False)
    df.loc[mgr_level, "management_type"] = "External-pooled"
    df["manager_name_raw"] = df["holding_name"].where(df["management_type"] == "External-pooled", "")
    df["manager_id"] = df["manager_name_raw"].apply(resolve_manager)
    df["holding_name_raw"] = df["holding_name"]
    df["option_type"] = df["option_name"].apply(option_type_for)
    df["is_default"] = (df["option_type"] == "Default").astype(int)
    df["market_value_aud"] = pd.to_numeric(df["market_value_aud"], errors="coerce")
    df["weight_pct_disclosed"] = pd.to_numeric(df["weight_pct"], errors="coerce")
    totals = df.groupby(["fund_id", "option_name"])["market_value_aud"].transform("sum")
    df["weight_pct_calc"] = (df["market_value_aud"] / totals * 100).round(4)
    df["geography"] = df["geography"].fillna("Unknown")
    df["geography_method"] = "reference"
    df["gics_sector"] = df["gics_sector"].fillna("")
    df["hedge_status"] = df["hedge_status"].fillna("")
    df["data_quality_flag"] = "REFERENCE: " + df["data_quality_flag"].fillna("Clean").astype(str)
    df["snapshot_date"], df["reporting_date"] = snapshot, df["reporting_date"].fillna(snapshot)
    df["fund_name"] = df["fund_family"]
    df["rse_abn"], df["option_id"], df["source_table"], df["security_id_raw"] = "", "", df["apra_asset_class"], df["isin"]
    df["units"] = df["face_value"] = df["coupon"] = None
    df["maturity_date"] = ""
    df["currency"] = df["currency"].fillna("")
    df["source_file"], df["source_file_hash"], df["pipeline_version"] = str(path), "", "reference-import"
    df["holding_id"] = [f"ref{i:07d}" for i in range(len(df))]
    df["is_listed"] = pd.to_numeric(df["is_listed"], errors="coerce").fillna(0).astype(int)
    out = df[HOLDING_COLUMNS]
    dest = CURATED / snapshot
    dest.mkdir(parents=True, exist_ok=True)
    out.to_parquet(dest / "holdings.parquet", index=False)
    print(f"imported {len(out):,} reference rows -> {dest/'holdings.parquet'}")
    return out


def import_saa(path: Path, snapshot: str = "2025-12-31") -> pd.DataFrame:
    raw = json.loads(Path(path).read_text())
    rows = []
    for r in raw:
        for g in r.get("granular", []):
            rows.append({"fund_name": r["rse"], "product": r["product"], "stage": r["stage"], "assets": r.get("assets"),
                         "accounts": r.get("accounts"), "asset_class": g["c"], "bucket": g["b"], "target": g["t"], "lower": g["lo"], "upper": g["up"],
                         "growth_weight": r.get("growthWeight"), "return_target": r.get("returnTarget"), "risk_label": r.get("riskLabel")})
    df = pd.DataFrame(rows)
    dest = CURATED / snapshot
    dest.mkdir(parents=True, exist_ok=True)
    df.to_parquet(dest / "apra_saa.parquet", index=False)
    print(f"imported {len(df):,} SAA rows -> {dest/'apra_saa.parquet'}")
    return df
