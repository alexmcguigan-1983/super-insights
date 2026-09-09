"""Fee and manager economics.

Three layers, each labelled with its provenance:
  1. option_fees     — disclosed (APRA QSPS fee tables / PDS): admin, investment fees & costs, transaction costs
  2. fund_expenses   — disclosed (APRA SRS 332.0): investment expenses in dollars, by category
  3. manager_fees    — ESTIMATED: mandate size × strategy fee range from config/fee_schedule.csv, scaled so
                       the option's implied total reconciles to its disclosed investment fee (when known).
Nothing in layer 3 is a disclosed number and the dashboard says so on every tile.
"""
from __future__ import annotations

import csv
from functools import lru_cache

import pandas as pd

from . import CONFIG


@lru_cache(maxsize=1)
def _schedule() -> list[dict]:
    with open(CONFIG / "fee_schedule.csv", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


@lru_cache(maxsize=1)
def _manager_strategy() -> dict[str, str]:
    with open(CONFIG / "managers.csv", newline="", encoding="utf-8") as f:
        return {r["manager_id"]: r["strategy_family"] for r in csv.DictReader(f)}


def _rate(bucket: str, mgmt: str, strategy: str) -> tuple[float, float]:
    m = "Internal" if mgmt == "Internal" else "External"
    rows = [r for r in _schedule() if r["bucket"] == bucket and r["management_type"] == m]
    hit = next((r for r in rows if r["strategy_family"] == strategy), None) or next((r for r in rows if not r["strategy_family"]), None)
    if not hit:
        return 20.0, 40.0
    return float(hit["fee_bps_low"]), float(hit["fee_bps_high"])


def estimate_manager_fees(holdings: pd.DataFrame, option_inv_fee_pct: dict[tuple[str, str], float] | None = None) -> pd.DataFrame:
    """One row per (fund, option, bucket, manager_id or 'Internal/Direct'): AUD, low/high bps, low/high AUD, and a
    reconciliation factor if the option's disclosed investment fee is known."""
    df = holdings.copy()
    df["mgr"] = df["manager_id"].where(df["manager_id"].astype(bool), df["management_type"].map({"Internal": "Internal", "External-pooled": "Unresolved external"}).fillna("Direct / segregated"))
    g = df.groupby(["fund_id", "fund_name", "option_name", "bucket", "management_type", "mgr"], as_index=False)["market_value_aud"].sum()
    g = g[g["market_value_aud"] > 0].reset_index(drop=True)
    strat = _manager_strategy()
    lo, hi = zip(*[_rate(b, m, strat.get(mg, "")) for b, m, mg in zip(g["bucket"], g["management_type"], g["mgr"])]) if len(g) else ([], [])
    g["fee_bps_low"], g["fee_bps_high"] = list(lo), list(hi)
    g["fee_aud_low"] = g["market_value_aud"] * g["fee_bps_low"] / 1e4
    g["fee_aud_high"] = g["market_value_aud"] * g["fee_bps_high"] / 1e4
    g["scale_factor"] = 1.0
    if option_inv_fee_pct:
        for (fid, opt), pct in option_inv_fee_pct.items():
            mask = (g["fund_id"] == fid) & (g["option_name"] == opt)
            if mask.any():
                implied_mid = (g.loc[mask, "fee_aud_low"].sum() + g.loc[mask, "fee_aud_high"].sum()) / 2
                disclosed = g.loc[mask, "market_value_aud"].sum() * pct / 100
                if implied_mid > 0 and disclosed > 0:
                    g.loc[mask, "scale_factor"] = disclosed / implied_mid
    g["fee_aud_low_scaled"] = g["fee_aud_low"] * g["scale_factor"]
    g["fee_aud_high_scaled"] = g["fee_aud_high"] * g["scale_factor"]
    g["basis"] = "ESTIMATE: mandate size x strategy fee range (config/fee_schedule.csv)" + g["scale_factor"].apply(lambda s: "" if abs(s - 1) < 1e-9 else f", scaled x{s:.2f} to disclosed option investment fee")
    return g
