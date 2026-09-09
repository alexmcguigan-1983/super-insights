"""Validation gates. Each (fund, option) must pass before it is loaded into curated/.

Gates
  G1  weights sum to 100 ± tolerance (using recomputed weights this is trivially true, so we check the
      *disclosed* weights where present: |sum - 100| <= 3)
  G2  option total within ±X% of the option size in APRA Product Structure (when available)
  G3  no bucket is negative and no single bucket exceeds 100%
  G4  row count within ±30% of the prior snapshot for the same fund/option (when a prior exists)
  G5  at least N line items for a diversified option (guards against a header-only parse)
  G6  reporting date matches the snapshot (or is missing)
Failures are written to quarantine/<snapshot>/<fund_id>.parquet + reasons.json and excluded from curated.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from . import BUCKETS, QUARANTINE


@dataclass
class GateResult:
    fund_id: str
    option_name: str
    passed: bool
    reasons: list[str] = field(default_factory=list)
    rows: int = 0
    total_aud: float = 0.0


def run_gates(df: pd.DataFrame, *, snapshot: str, apra_option_sizes: dict[tuple[str, str], float] | None = None,
              prior_counts: dict[tuple[str, str], int] | None = None, size_tol: float = 0.25, min_rows_diversified: int = 25) -> list[GateResult]:
    results = []
    for (fund_id, option), g in df.groupby(["fund_id", "option_name"], sort=False):
        r = GateResult(fund_id, option, True, rows=len(g), total_aud=float(g["market_value_aud"].fillna(0).sum()))
        disclosed = g["weight_pct_disclosed"].dropna()
        if len(disclosed) >= 0.8 * len(g) and len(g) > 5:
            s = disclosed.sum()
            if abs(s - 100) > 3:
                r.reasons.append(f"G1 disclosed weights sum to {s:.1f}% (expected ~100%)")
        if r.total_aud <= 0:
            r.reasons.append("G3 no market values parsed")
        else:
            by_bucket = g.groupby("bucket")["market_value_aud"].sum() / r.total_aud * 100
            neg = by_bucket[by_bucket < -0.5]
            if len(neg):
                r.reasons.append(f"G3 negative bucket(s): {', '.join(neg.index)}")
            if "Other" in by_bucket and by_bucket["Other"] > 25:
                r.reasons.append(f"G3 {by_bucket['Other']:.1f}% unclassified (Other) — check asset_class_map.csv")
        if apra_option_sizes and (fund_id, option) in apra_option_sizes:
            apra = apra_option_sizes[(fund_id, option)]
            if apra > 0 and abs(r.total_aud - apra) / apra > size_tol:
                r.reasons.append(f"G2 option total {r.total_aud/1e9:.2f}bn vs APRA {apra/1e9:.2f}bn (>{size_tol:.0%} apart)")
        if prior_counts and (fund_id, option) in prior_counts:
            prev = prior_counts[(fund_id, option)]
            if prev > 0 and abs(len(g) - prev) / prev > 0.3:
                r.reasons.append(f"G4 row count {len(g)} vs prior {prev} (>30% change)")
        otype = g["option_type"].iloc[0]
        if otype in {"Default", "Balanced", "Growth", "High Growth", "Conservative", "Sustainable"} and len(g) < min_rows_diversified:
            r.reasons.append(f"G5 only {len(g)} rows for a diversified option — likely partial parse")
        dates = set(g["reporting_date"].dropna().astype(str)) - {"", snapshot, snapshot[:10]}
        if dates:
            r.reasons.append(f"G6 reporting date {sorted(dates)} differs from snapshot {snapshot}")
        r.passed = not r.reasons
        results.append(r)
    return results


def apply_quarantine(df: pd.DataFrame, results: list[GateResult], snapshot: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    failed = {(r.fund_id, r.option_name) for r in results if not r.passed}
    mask = df.apply(lambda r: (r["fund_id"], r["option_name"]) in failed, axis=1) if len(df) else pd.Series([], dtype=bool)
    bad, good = df[mask], df[~mask]
    qdir = QUARANTINE / snapshot
    qdir.mkdir(parents=True, exist_ok=True)
    if len(bad):
        bad.to_parquet(qdir / "quarantined_holdings.parquet", index=False)
    (qdir / "reasons.json").write_text(json.dumps([r.__dict__ for r in results if not r.passed], indent=2, default=str))
    return good, bad


def qa_report(results: list[GateResult], snapshot: str, harvest_manifest: dict | None = None) -> str:
    lines = [f"# QA report — snapshot {snapshot}", ""]
    ok = [r for r in results if r.passed]
    ko = [r for r in results if not r.passed]
    lines += [f"- Options passed: **{len(ok)}**", f"- Options quarantined: **{len(ko)}**",
              f"- AUM loaded: **${sum(r.total_aud for r in ok)/1e9:,.1f}bn**", ""]
    if harvest_manifest:
        errs = {k: v["errors"] for k, v in harvest_manifest.get("funds", {}).items() if v.get("errors")}
        if errs:
            lines += ["## Harvest problems", ""]
            for k, v in errs.items():
                lines += [f"- **{k}**: " + "; ".join(v)]
            lines.append("")
    if ko:
        lines += ["## Quarantined options", "", "| Fund | Option | Rows | Total AUD | Reasons |", "|---|---|---:|---:|---|"]
        for r in ko:
            lines.append(f"| {r.fund_id} | {r.option_name} | {r.rows} | {r.total_aud/1e6:,.0f}m | {'<br>'.join(r.reasons)} |")
        lines.append("")
    lines += ["## Loaded options", "", "| Fund | Option | Rows | Total AUD |", "|---|---|---:|---:|"]
    for r in sorted(ok, key=lambda x: -x.total_aud):
        lines.append(f"| {r.fund_id} | {r.option_name} | {r.rows} | {r.total_aud/1e6:,.0f}m |")
    return "\n".join(lines)
