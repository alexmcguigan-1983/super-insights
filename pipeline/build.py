"""Aggregate curated parquet into the small JSON files the static site reads.

Outputs (site/data/<snapshot>/):
  summary.json    universe tiles, aggregate allocation, AUM by option, liquidity, top holdings
  options.json    one record per option: allocation, concentration, top-20, peer deltas, drift vs APRA SAA
  managers.json   manager league table (manager x bucket x fund)
  fees.json       disclosed option fees, disclosed fund expenses, ESTIMATED manager economics
  apra.json       MySuper strategic allocation products (targets & ranges)
  quality.json    QA gates, flag distribution, harvest problems
  holdings/<fund_id>.json   line items per fund (compact arrays) for the explorer
and site/data/index.json (snapshot list) + site/data/timeseries.json (across snapshots).
Also writes curated/super_insights.duckdb so analysts can query everything with SQL.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

import pandas as pd

from . import BUCKETS, CURATED, GROWTH_BUCKETS, ILLIQUID_CLASSES, PIPELINE_VERSION, QUARANTINE, RAW, SITE_DATA
from .fees import estimate_manager_fees
from .normalise import apply_default_options, manager_info

STRATEGY_MAP: list[dict] | None = None


def _strategy_map() -> list[dict]:
    global STRATEGY_MAP
    if STRATEGY_MAP is None:
        import csv
        from . import CONFIG
        p = CONFIG / "alternatives_strategy_map.csv"
        STRATEGY_MAP = []
        if p.exists():
            with open(p, newline="", encoding="utf-8") as f:
                for r in csv.DictReader(f):
                    r["rx"] = re.compile(r["pattern"], re.I)
                    STRATEGY_MAP.append(r)
    return STRATEGY_MAP


def classify_strategy(manager_id: str, name: str) -> tuple[str, str]:
    """(strategy, style) for a manager-level or alternatives line. strategy_family from managers.csv is tried
    first, then keywords in the holding name. Returns ('Unclassified alternatives', 'Other') when nothing matches."""
    fam = (manager_info(manager_id).get("strategy_family", "") if manager_id else "").lower()
    for r in _strategy_map():
        if r["note"].startswith("strategy_family") and fam and r["rx"].search(fam):
            return r["strategy"], r["style"]
    for r in _strategy_map():
        if r["note"].startswith("name") and name and r["rx"].search(name):
            return r["strategy"], r["style"]
    return "Unclassified alternatives", "Other"

PEER_TYPES = {"Default", "Balanced", "Growth", "High Growth", "Conservative", "Sustainable"}


def _norm_name(s: str) -> str:
    s = re.sub(r"\b(super|superannuation|fund|trust|the|scheme|plan|limited|ltd|pty)\b", " ", str(s).lower())
    return re.sub(r"[^a-z0-9]+", "", s)


def _load(snapshot: str, name: str) -> pd.DataFrame | None:
    p = CURATED / snapshot / f"{name}.parquet"
    return pd.read_parquet(p) if p.exists() else None


def _alloc(g: pd.DataFrame) -> dict[str, float]:
    tot = g["market_value_aud"].sum()
    by = g.groupby("bucket")["market_value_aud"].sum()
    return {b: round(float(by.get(b, 0.0)) / tot * 100, 2) if tot else 0.0 for b in BUCKETS}


def build_snapshot(snapshot: str) -> dict:
    h = _load(snapshot, "holdings")
    if h is None or h.empty:
        raise SystemExit(f"no curated holdings for {snapshot}")
    h = h[h["market_value_aud"].notna()].copy()
    h = apply_default_options(h)
    h["is_illiquid"] = h["apra_asset_class"].isin(ILLIQUID_CLASSES)
    out_dir = SITE_DATA / snapshot
    (out_dir / "holdings").mkdir(parents=True, exist_ok=True)

    # ---- options ---------------------------------------------------------------------------------
    saa = _load(snapshot, "apra_saa")
    saa_by_fund: dict[str, dict[str, float]] = {}
    if saa is not None and len(saa):
        s = saa.copy()
        s["key"] = s["fund_name"].apply(_norm_name)
        # largest stage per fund (by assets) as the representative default target
        if "assets" in s:
            s["assets"] = pd.to_numeric(s["assets"], errors="coerce").fillna(0)
            top_stage = s.groupby(["key", "product", "stage"])["assets"].max().reset_index().sort_values("assets", ascending=False).drop_duplicates("key")
            s = s.merge(top_stage[["key", "product", "stage"]], on=["key", "product", "stage"])
        for key, g in s.groupby("key"):
            tgt = g.groupby("bucket")["target"].sum()
            tot = tgt.sum() or 1
            saa_by_fund[key] = {b: round(float(tgt.get(b, 0)) / tot * 100, 2) for b in BUCKETS}

    options = []
    for (fid, fname, opt), g in h.groupby(["fund_id", "fund_name", "option_name"], sort=False):
        aum = float(g["market_value_aud"].sum())
        if aum <= 0:
            continue
        top = g.sort_values("market_value_aud", ascending=False)
        top10 = float(top.head(10)["market_value_aud"].sum()) / aum * 100
        rec = {
            "fund_id": fid, "fund_name": fname, "option_name": opt, "option_type": g["option_type"].iloc[0],
            "is_default": int(g["is_default"].max()), "aum": aum, "rows": int(len(g)),
            "alloc": _alloc(g), "top10_pct": round(top10, 2), "largest_pct": round(float(top.iloc[0]["market_value_aud"]) / aum * 100, 2),
            "listed_pct": round(float(g.loc[g["is_listed"] == 1, "market_value_aud"].sum()) / aum * 100, 2),
            "illiquid_pct": round(float(g.loc[g["is_illiquid"], "market_value_aud"].sum()) / aum * 100, 2),
            "growth_pct": round(float(g.loc[g["bucket"].isin(GROWTH_BUCKETS), "market_value_aud"].sum()) / aum * 100, 2),
            "external_pct": round(float(g.loc[g["management_type"] == "External-pooled", "market_value_aud"].sum()) / aum * 100, 2),
            "clean_pct": round(float((g["data_quality_flag"].str.startswith("Clean") | g["data_quality_flag"].str.startswith("REFERENCE: Clean")).mean() * 100), 1),
            "top20": [{"name": r.holding_name, "bucket": r.bucket, "value": float(r.market_value_aud), "pct": round(float(r.market_value_aud) / aum * 100, 2), "geo": r.geography}
                      for r in top.head(20).itertuples()],
            "saa_target": saa_by_fund.get(_norm_name(fname)),
        }
        options.append(rec)

    # peer deltas within option type (defaults treated as Balanced/Growth by growth share when unknown)
    def peer_group(o):
        t = o["option_type"]
        if t == "Default":
            return "Growth" if o["growth_pct"] >= 75 else "Balanced"
        return t if t in PEER_TYPES else "Other"
    for o in options:
        o["peer_group"] = peer_group(o)
    for pg in {o["peer_group"] for o in options}:
        peers = [o for o in options if o["peer_group"] == pg and o["fund_id"] not in {"futuresuper", "smartmonday"}]
        if not peers:
            continue
        avg = {b: sum(o["alloc"][b] for o in peers) / len(peers) for b in BUCKETS}
        for o in options:
            if o["peer_group"] == pg:
                o["peer_n"] = len(peers)
                o["peer_delta"] = {b: round(o["alloc"][b] - avg[b], 2) for b in BUCKETS}
    options.sort(key=lambda o: -o["aum"])
    (out_dir / "options.json").write_text(json.dumps(options))

    # ---- funds (whole of loaded portfolio, AUM-weighted across every option loaded) ----------------
    funds = []
    for (fid, fname), g in h.groupby(["fund_id", "fund_name"], sort=False):
        aum = float(g["market_value_aud"].sum())
        if aum <= 0:
            continue
        fopts = [o for o in options if o["fund_id"] == fid]
        default = next((o for o in fopts if o["is_default"]), None)
        funds.append({
            "fund_id": fid, "fund_name": fname, "aum": aum, "options": len(fopts), "rows": int(len(g)),
            "alloc": _alloc(g),
            "growth_pct": round(float(g.loc[g["bucket"].isin(GROWTH_BUCKETS), "market_value_aud"].sum()) / aum * 100, 2),
            "listed_pct": round(float(g.loc[g["is_listed"] == 1, "market_value_aud"].sum()) / aum * 100, 2),
            "illiquid_pct": round(float(g.loc[g["is_illiquid"], "market_value_aud"].sum()) / aum * 100, 2),
            "external_pct": round(float(g.loc[g["management_type"] == "External-pooled", "market_value_aud"].sum()) / aum * 100, 2),
            "default_option": default["option_name"] if default else None,
            "option_types": sorted({o["option_type"] for o in fopts}),
            "source": "reference-import" if (g["pipeline_version"] == "reference-import").all() else ("mixed" if (g["pipeline_version"] == "reference-import").any() else "primary"),
        })
    funds.sort(key=lambda f: -f["aum"])
    if funds:
        avg = {b: sum(f["alloc"][b] for f in funds) / len(funds) for b in BUCKETS}
        wavg = {b: sum(f["alloc"][b] * f["aum"] for f in funds) / sum(f["aum"] for f in funds) for b in BUCKETS}
        for f in funds:
            f["delta_vs_avg"] = {b: round(f["alloc"][b] - avg[b], 2) for b in BUCKETS}
            f["delta_vs_wavg"] = {b: round(f["alloc"][b] - wavg[b], 2) for b in BUCKETS}
    (out_dir / "funds.json").write_text(json.dumps({"funds": funds, "peer_avg": avg if funds else {}, "peer_wavg": wavg if funds else {}}))

    # ---- summary ---------------------------------------------------------------------------------
    total = float(h["market_value_aud"].sum())
    top_univ = h.groupby("holding_name")["market_value_aud"].sum().sort_values(ascending=False).head(25)
    summary = {
        "snapshot": snapshot, "funds": int(h["fund_id"].nunique()), "options": len(options), "rows": int(len(h)), "aum": total,
        "alloc": _alloc(h),
        "top_holdings": [{"name": k, "value": float(v), "pct": round(float(v) / total * 100, 2)} for k, v in top_univ.items()],
        "geo": [{"geo": k, "value": float(v)} for k, v in h.groupby("geography")["market_value_aud"].sum().sort_values(ascending=False).head(20).items()],
        "listed_pct": round(float(h.loc[h["is_listed"] == 1, "market_value_aud"].sum()) / total * 100, 2),
        "illiquid_pct": round(float(h.loc[h["is_illiquid"], "market_value_aud"].sum()) / total * 100, 2),
        "external_pct": round(float(h.loc[h["management_type"] == "External-pooled", "market_value_aud"].sum()) / total * 100, 2),
        "reference_import": bool((h["pipeline_version"] == "reference-import").any()),
    }
    (out_dir / "summary.json").write_text(json.dumps(summary))

    # ---- managers --------------------------------------------------------------------------------
    ext = h[h["management_type"].isin(["External-pooled"])].copy()
    ext["manager"] = ext["manager_id"].where(ext["manager_id"].astype(bool), ext["manager_name_raw"].str.strip().str.title())
    ext["manager"] = ext["manager"].apply(lambda x: (manager_info(x).get("manager_name") or x) if x else x)
    ext = ext[~ext["manager"].fillna("").str.strip().isin(["", "-", "—", "N/A", "Na", "None"])]
    mg = ext.groupby(["manager", "bucket", "fund_id", "fund_name", "option_name"], as_index=False)["market_value_aud"].sum()
    league = ext.groupby("manager").agg(value=("market_value_aud", "sum"), funds=("fund_id", "nunique"), options=("option_name", "nunique"), buckets=("bucket", lambda s: sorted(set(s)))).reset_index().sort_values("value", ascending=False)
    managers = {
        "league": [{"manager": r.manager, "value": float(r.value), "funds": int(r.funds), "options": int(r.options), "buckets": list(r.buckets)} for r in league.itertuples()],
        "detail": [{"manager": r.manager, "bucket": r.bucket, "fund_id": r.fund_id, "fund_name": r.fund_name, "option_name": r.option_name, "value": float(r.market_value_aud)} for r in mg.itertuples()],
        "internal_vs_external": [{"fund_id": f, "internal": float(g.loc[g["management_type"] == "Internal", "market_value_aud"].sum()), "external": float(g.loc[g["management_type"] == "External-pooled", "market_value_aud"].sum()),
                                  "unknown": float(g.loc[~g["management_type"].isin(["Internal", "External-pooled"]), "market_value_aud"].sum())} for f, g in h.groupby("fund_id")],
    }
    # public-record relationships (press releases, manager lists) that PHD cannot show — config/manager_relationships.csv
    rel_p = Path(__file__).resolve().parents[1] / "config" / "manager_relationships.csv"
    if rel_p.exists():
        import csv as _csv
        with open(rel_p, newline="", encoding="utf-8") as f:
            rels = list(_csv.DictReader(f))
        for r in rels:
            r["manager"] = manager_info(r["manager_id"]).get("manager_name") or r["manager_id"]
        managers["relationships"] = rels
        # make sure every manager with a documented relationship appears in the league even with zero disclosed AUD
        seen = {m["manager"] for m in managers["league"]}
        for r in rels:
            if r["manager"] not in seen:
                managers["league"].append({"manager": r["manager"], "value": 0.0, "funds": 0, "options": 0, "buckets": [], "documented_only": True})
                seen.add(r["manager"])
    (out_dir / "managers.json").write_text(json.dumps(managers))

    # ---- alternatives & hedge funds ---------------------------------------------------------------
    # Universe: every line in the Alternatives bucket, plus every manager-level line whose manager is a hedge-fund,
    # multi-manager or real-assets house regardless of the bucket the fund (or the reference dataset) filed it under.
    alt = h.copy()
    strat = alt.apply(lambda r: classify_strategy(r["manager_id"] or "", str(r["holding_name_raw"])), axis=1)
    alt["strategy"] = [x[0] for x in strat]
    alt["style"] = [x[1] for x in strat]
    in_alt_bucket = alt["bucket"] == "Alternatives"
    hf_manager = alt["style"].isin(["Hedge fund", "Diversifier"]) & (alt["manager_id"].fillna("") != "")
    alt = alt[in_alt_bucket | hf_manager].copy()
    alt["manager"] = alt["manager_id"].where(alt["manager_id"].astype(bool), alt["holding_name_raw"].str.strip().str.title())
    by_strategy = alt.groupby(["style", "strategy"], as_index=False)["market_value_aud"].sum().sort_values("market_value_aud", ascending=False)
    by_fund = alt.groupby(["fund_id", "fund_name", "strategy"], as_index=False)["market_value_aud"].sum()
    by_mgr = alt.groupby(["manager", "strategy", "style"]).agg(value=("market_value_aud", "sum"), funds=("fund_id", "nunique"), fund_names=("fund_name", lambda s: sorted(set(s))), buckets=("bucket", lambda s: sorted(set(s)))).reset_index().sort_values("value", ascending=False)
    alternatives = {
        "total": float(alt["market_value_aud"].sum()),
        "alt_bucket_total": float(h.loc[h["bucket"] == "Alternatives", "market_value_aud"].sum()),
        "by_strategy": [{"style": r.style, "strategy": r.strategy, "value": float(r.market_value_aud)} for r in by_strategy.itertuples()],
        "by_fund": [{"fund_id": r.fund_id, "fund_name": r.fund_name, "strategy": r.strategy, "value": float(r.market_value_aud)} for r in by_fund.itertuples()],
        "managers": [{"manager": r.manager, "name": (manager_info(r.manager).get("manager_name") or r.manager), "parent": manager_info(r.manager).get("parent", ""), "hq": manager_info(r.manager).get("hq_country", ""),
                      "strategy": r.strategy, "style": r.style, "value": float(r.value), "funds": int(r.funds), "fund_names": list(r.fund_names), "buckets": list(r.buckets)} for r in by_mgr.itertuples()],
        "note": "Strategy is assigned from config/managers.csv (strategy_family) and keyword rules in config/alternatives_strategy_map.csv. Segregated hedge-fund mandates and internally run absolute-return books are disclosed as underlying securities and cannot be identified here.",
    }
    (out_dir / "alternatives.json").write_text(json.dumps(alternatives))

    # ---- fees ------------------------------------------------------------------------------------
    fees_apra = _load(snapshot, "apra_fees")
    expenses = _load(snapshot, "apra_expenses")
    inv_fee_lookup: dict[tuple[str, str], float] = {}
    option_fees = []
    if fees_apra is not None and len(fees_apra):
        f = fees_apra.copy()
        f["key"] = f["fund_name"].apply(_norm_name)
        fund_keys = {_norm_name(fn): fid for fid, fn in h[["fund_id", "fund_name"]].drop_duplicates().itertuples(index=False)}
        for r in f.itertuples():
            fid = fund_keys.get(r.key)
            rec = {"fund_id": fid, "fund_name": r.fund_name, "product": getattr(r, "product", ""), "stage": getattr(r, "stage", ""),
                   "admin_fee": getattr(r, "admin_fee", None), "inv_fee": getattr(r, "inv_fee", None), "txn_cost": getattr(r, "txn_cost", None), "total_fee": getattr(r, "total_fee", None)}
            option_fees.append({k: (None if isinstance(v, float) and pd.isna(v) else v) for k, v in rec.items()})
            if fid and rec["inv_fee"] is not None and not pd.isna(rec["inv_fee"]):
                for o in options:
                    if o["fund_id"] == fid and o["is_default"]:
                        inv_fee_lookup[(fid, o["option_name"])] = float(rec["inv_fee"])
    est = estimate_manager_fees(h, inv_fee_lookup)
    fund_exp = []
    if expenses is not None and len(expenses):
        e = expenses.copy()
        e["key"] = e["fund_name"].apply(_norm_name)
        for (fn, key), g in e.groupby(["fund_name", "key"]):
            fund_exp.append({"fund_name": fn, "investment_expenses": float(g.loc[g["is_investment"], "amount"].sum()), "total_expenses": float(g["amount"].sum()),
                             "by_type": [{"type": t, "amount": float(v)} for t, v in g.groupby("expense_type")["amount"].sum().sort_values(ascending=False).head(15).items()]})
    fees = {
        "option_fees_disclosed": option_fees,
        "fund_expenses_disclosed": fund_exp,
        "manager_fees_estimated": [{k: (None if isinstance(v, float) and pd.isna(v) else (float(v) if isinstance(v, (int, float)) else v)) for k, v in r.items()} for r in est.to_dict("records")],
        "disclaimer": "Manager-level fees are estimates (mandate size x strategy fee range from config/fee_schedule.csv). Fees paid to named managers are not publicly disclosed by Australian super funds.",
    }
    (out_dir / "fees.json").write_text(json.dumps(fees))

    # ---- apra SAA --------------------------------------------------------------------------------
    apra = []
    if saa is not None and len(saa):
        for (fn, prod, stage), g in saa.groupby(["fund_name", "product", "stage"]):
            tgt = g.groupby("bucket")["target"].sum()
            tot = tgt.sum() or 1
            rec = {"fund_name": fn, "product": prod, "stage": stage, "assets": float(pd.to_numeric(g["assets"], errors="coerce").max()) if "assets" in g else None,
                   "alloc": {b: round(float(tgt.get(b, 0)) / tot * 100, 2) for b in BUCKETS},
                   "granular": [{"c": r.asset_class, "b": r.bucket, "t": float(r.target or 0), "lo": float(r.lower) if pd.notna(r.lower) else None, "up": float(r.upper) if pd.notna(r.upper) else None} for r in g.itertuples()],
                   "has_holdings": _norm_name(fn) in {_norm_name(x) for x in h["fund_name"].unique()}}
            apra.append(rec)
    (out_dir / "apra.json").write_text(json.dumps(apra))

    # ---- quality ---------------------------------------------------------------------------------
    qdir = QUARANTINE / snapshot
    reasons = json.loads((qdir / "reasons.json").read_text()) if (qdir / "reasons.json").exists() else []
    manifest_p = RAW / snapshot / "manifest.json"
    manifest = json.loads(manifest_p.read_text()) if manifest_p.exists() else {}
    flags = h["data_quality_flag"].str.split(";").explode().str.strip().value_counts().head(30)
    quality = {
        "quarantined": reasons,
        "harvest_errors": {k: v.get("errors", []) for k, v in manifest.get("funds", {}).items() if v.get("errors")},
        "harvested_files": {k: len(v.get("files", [])) for k, v in manifest.get("funds", {}).items()},
        "flags": [{"flag": k, "rows": int(v)} for k, v in flags.items()],
        "geography_methods": [{"method": k, "rows": int(v)} for k, v in h["geography_method"].value_counts().items()],
        "identifiers": {"isin": int((h["isin"].astype(bool)).sum()), "sedol": int((h["sedol"].astype(bool)).sum()), "ticker": int((h["ticker"].astype(bool)).sum()), "rows": int(len(h))},
        "apra_status": json.loads((CURATED / snapshot / "apra_status.json").read_text()) if (CURATED / snapshot / "apra_status.json").exists() else {},
    }
    (out_dir / "quality.json").write_text(json.dumps(quality, default=str))

    # ---- holdings per fund (compact) -------------------------------------------------------------
    cols = ["option_name", "holding_name", "ticker", "isin", "apra_asset_class", "bucket", "geography", "market_value_aud", "weight_pct_calc", "is_listed", "management_type", "manager_id", "gics_sector", "data_quality_flag"]
    for fid, g in h.groupby("fund_id"):
        g = g.sort_values("market_value_aud", ascending=False)
        payload = {"columns": cols, "rows": g[cols].fillna("").values.tolist()}
        (out_dir / "holdings" / f"{fid}.json").write_text(json.dumps(payload, default=lambda x: float(x) if hasattr(x, "__float__") else str(x)))

    return {"snapshot": snapshot, "funds": summary["funds"], "options": len(options), "rows": int(len(h)), "aum": total}


def build_index() -> None:
    snaps = sorted(p.name for p in SITE_DATA.iterdir() if p.is_dir() and (p / "summary.json").exists() and "demo" not in p.name)
    if not snaps:  # nothing real yet: show demo snapshots so `make demo` renders
        snaps = sorted(p.name for p in SITE_DATA.iterdir() if p.is_dir() and (p / "summary.json").exists())
    series = {}
    for s in snaps:
        opts = json.loads((SITE_DATA / s / "options.json").read_text())
        mg = json.loads((SITE_DATA / s / "managers.json").read_text())["league"]
        series[s] = {"options": [{"fund_id": o["fund_id"], "option_name": o["option_name"], "aum": o["aum"], "alloc": o["alloc"]} for o in opts],
                     "managers": [{"manager": m["manager"], "value": m["value"]} for m in mg[:200]]}
    (SITE_DATA / "timeseries.json").write_text(json.dumps(series))
    (SITE_DATA / "index.json").write_text(json.dumps({"snapshots": snaps, "latest": snaps[-1] if snaps else None,
                                                       "built_at": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z", "pipeline_version": PIPELINE_VERSION}))


def export_duckdb() -> None:
    try:
        import duckdb
    except ImportError:
        return
    db = CURATED / "super_insights.duckdb"
    con = duckdb.connect(str(db))
    for name in ("holdings", "apra_saa", "apra_fees", "apra_products", "apra_fund_level", "apra_expenses"):
        files = sorted(CURATED.glob(f"*/{name}.parquet"))
        if files:
            con.execute(f"CREATE OR REPLACE VIEW {name} AS SELECT * FROM read_parquet({[str(f) for f in files]!r}, union_by_name=true)")
    con.close()
