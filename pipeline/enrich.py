"""Enrichment: security master via OpenFIGI, manager resolution, look-through flags.

OpenFIGI (https://www.openfigi.com/api) is free; without a key you get 25 requests/minute with up to
10 jobs per request, with a key 250 jobs/request. Results are cached in curated/security_master.parquet
so each identifier is looked up once ever.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import pandas as pd
import requests

from . import CURATED
from .normalise import resolve_manager, resolve_manager_from_holding_name

OPENFIGI_URL = "https://api.openfigi.com/v3/mapping"
CACHE = CURATED / "security_master.parquet"


def _load_cache() -> pd.DataFrame:
    if CACHE.exists():
        return pd.read_parquet(CACHE)
    return pd.DataFrame(columns=["id_type", "id_value", "name", "ticker", "exchange", "security_type", "market_sector", "figi"])


def openfigi_lookup(ids: list[tuple[str, str]], api_key: str | None = None, batch: int | None = None, sleep: float = 2.6) -> pd.DataFrame:
    """ids: list of (id_type, id_value) with id_type in {ID_ISIN, ID_SEDOL, TICKER}. Returns rows for hits."""
    key = api_key or os.environ.get("OPENFIGI_API_KEY")
    headers = {"Content-Type": "application/json"}
    if key:
        headers["X-OPENFIGI-APIKEY"] = key
    batch = batch or (100 if key else 10)
    rows = []
    for i in range(0, len(ids), batch):
        chunk = ids[i:i + batch]
        jobs = [{"idType": t, "idValue": v} for t, v in chunk]
        try:
            r = requests.post(OPENFIGI_URL, json=jobs, headers=headers, timeout=60)
            if r.status_code == 429:
                time.sleep(30)
                r = requests.post(OPENFIGI_URL, json=jobs, headers=headers, timeout=60)
            r.raise_for_status()
            for (t, v), res in zip(chunk, r.json()):
                d = (res.get("data") or [{}])[0]
                rows.append({"id_type": t, "id_value": v, "name": d.get("name"), "ticker": d.get("ticker"), "exchange": d.get("exchCode"),
                             "security_type": d.get("securityType"), "market_sector": d.get("marketSector"), "figi": d.get("figi")})
        except requests.RequestException as e:
            print(f"  ! openfigi batch failed: {e}")
        time.sleep(0 if key else sleep)
    return pd.DataFrame(rows)


def build_security_master(holdings: pd.DataFrame, max_new: int = 5000) -> pd.DataFrame:
    cache = _load_cache()
    known = set(zip(cache["id_type"], cache["id_value"]))
    todo = []
    for isin in holdings["isin"].dropna().unique():
        if isin and ("ID_ISIN", isin) not in known:
            todo.append(("ID_ISIN", isin))
    for sedol in holdings["sedol"].dropna().unique():
        if sedol and ("ID_SEDOL", sedol) not in known:
            todo.append(("ID_SEDOL", sedol))
    todo = todo[:max_new]
    if todo:
        print(f"  openfigi: looking up {len(todo)} new identifiers")
        new = openfigi_lookup(todo)
        if len(new):
            cache = pd.concat([cache, new], ignore_index=True).drop_duplicates(["id_type", "id_value"], keep="last")
            CACHE.parent.mkdir(parents=True, exist_ok=True)
            cache.to_parquet(CACHE, index=False)
    return cache


def apply_security_master(holdings: pd.DataFrame, master: pd.DataFrame) -> pd.DataFrame:
    if master.empty:
        return holdings
    df = holdings.copy()
    m_isin = master[master["id_type"] == "ID_ISIN"].set_index("id_value")
    m_sedol = master[master["id_type"] == "ID_SEDOL"].set_index("id_value")
    for col_id, m in (("isin", m_isin), ("sedol", m_sedol)):
        hit = df[col_id].map(m["name"]) if len(m) else pd.Series([None] * len(df), index=df.index)
        df["holding_name"] = df["holding_name"].where(hit.isna(), hit)
        tick = df[col_id].map(m["ticker"]) if len(m) else pd.Series([None] * len(df), index=df.index)
        df["ticker"] = df["ticker"].where(df["ticker"].astype(bool) | tick.isna(), tick)
        sec = df[col_id].map(m["market_sector"]) if len(m) else pd.Series([None] * len(df), index=df.index)
        df["gics_sector"] = df["gics_sector"].where(df["gics_sector"].astype(bool) | sec.isna(), sec)
    return df


def resolve_managers(holdings: pd.DataFrame) -> pd.DataFrame:
    """Two passes. (1) manager_name_raw through the alias table. (2) For unlisted lines with no security identifier
    whose holding name IS a manager entity (the way pooled mandates are disclosed: 'IFM Investors', 'Blackrock'),
    match the holding name against the alias table and mark the line External-pooled. Pass 2 is what makes the
    manager league table complete for reference-imported rows, which carry no management_type."""
    df = holdings.copy()
    missing = df["manager_id"].fillna("") == ""
    df.loc[missing, "manager_id"] = df.loc[missing, "manager_name_raw"].fillna("").apply(resolve_manager)
    no_id = (df["isin"].fillna("") == "") & (df["ticker"].fillna("") == "") & (df["sedol"].fillna("") == "")
    cand = (df["manager_id"].fillna("") == "") & no_id & (pd.to_numeric(df["is_listed"], errors="coerce").fillna(0) == 0)
    hit = df.loc[cand, "holding_name_raw"].fillna("").apply(resolve_manager_from_holding_name)
    ok = hit.astype(bool)
    idx = hit[ok].index
    df.loc[idx, "manager_id"] = hit[ok]
    df.loc[idx, "manager_name_raw"] = df.loc[idx, "holding_name_raw"]
    df.loc[idx, "management_type"] = "External-pooled"
    df.loc[idx, "data_quality_flag"] = df.loc[idx, "data_quality_flag"].fillna("").astype(str) + "; manager resolved from holding name"
    return df
