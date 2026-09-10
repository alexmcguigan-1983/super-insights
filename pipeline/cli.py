"""Command line entry point.

    python -m pipeline.cli harvest   [--snapshot 2026-06-30] [--only rest,cbus]
    python -m pipeline.cli ingest    [--snapshot ...] [--only ...]      # parse + normalise + validate -> curated
    python -m pipeline.cli apra      [--snapshot ...]
    python -m pipeline.cli enrich    [--snapshot ...]                  # OpenFIGI + managers
    python -m pipeline.cli build     [--snapshot ...]                  # site/data JSON + duckdb
    python -m pipeline.cli refresh   [--snapshot ...]                  # everything above in order
    python -m pipeline.cli import-reference holdings.json [saa.json]   # seed from the reference dataset
    python -m pipeline.cli repair-context [--snapshot ...]             # write context for the repair agent
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

from . import CURATED, HOLDING_COLUMNS, QUARANTINE, RAW, ROOT
from .registry import latest_reporting_date, load_sources, snapshot_id


def _snap(args) -> str:
    return args.snapshot or snapshot_id(latest_reporting_date())


def _only(args) -> list[str] | None:
    return [x.strip() for x in args.only.split(",")] if args.only else None


def cmd_harvest(args):
    from .harvest import harvest
    m = harvest(_snap(args), only=_only(args))
    n = sum(len(v["files"]) for v in m["funds"].values())
    print(f"harvested {n} files for {len(m['funds'])} funds -> raw/{_snap(args)}")


def cmd_ingest(args):
    from .normalise import normalise
    from .parse.adapters import parse_fund
    from .validate import apply_quarantine, qa_report, run_gates
    snapshot = _snap(args)
    frames, hashes = [], {}
    for src in load_sources(only=_only(args)):
        raw_dir = RAW / snapshot / src.fund_id
        if not raw_dir.exists():
            print(f"-- {src.fund_id}: no raw directory (harvest first)")
            continue
        for p in raw_dir.iterdir():
            if p.is_file():
                hashes[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
        try:
            staging = parse_fund(src.fund_id, raw_dir)
        except Exception as e:  # noqa: BLE001
            print(f"!! {src.fund_id}: parse crashed: {e}")
            continue
        df = normalise(staging, fund_id=src.fund_id, fund_name=src.fund_name, rse_abn=src.rse_abn, snapshot_date=snapshot, file_hashes=hashes)
        print(f"-- {src.fund_id}: {len(df):,} rows, {df['option_name'].nunique()} options, ${df['market_value_aud'].sum()/1e9:,.1f}bn")
        frames.append(df)
    all_df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=HOLDING_COLUMNS)
    # prior snapshot row counts for gate G4
    prior_counts = {}
    priors = sorted(p for p in CURATED.glob("*/holdings.parquet") if p.parent.name < snapshot)
    if priors:
        prev = pd.read_parquet(priors[-1])
        prior_counts = prev.groupby(["fund_id", "option_name"]).size().to_dict()
    apra_sizes = {}
    results = run_gates(all_df, snapshot=snapshot, apra_option_sizes=apra_sizes, prior_counts=prior_counts)
    good, bad = apply_quarantine(all_df, results, snapshot)
    dest = CURATED / snapshot
    dest.mkdir(parents=True, exist_ok=True)
    if (dest / "holdings.parquet").exists():
        old = pd.read_parquet(dest / "holdings.parquet")
        loaded = good["fund_id"].unique()
        if args.append:
            keep = old[~old["fund_id"].isin(loaded)]
        else:
            # A full ingest replaces primary data, but reference-imported rows (seed dataset) are kept for
            # any fund the primary harvest did not load, so a first run never deletes day-one content.
            keep = old[(old["pipeline_version"] == "reference-import") & ~old["fund_id"].isin(loaded)]
        if len(keep):
            print(f"keeping {len(keep):,} existing rows for {keep['fund_id'].nunique()} fund(s) not loaded this run")
        good = pd.concat([keep, good], ignore_index=True)
    good.to_parquet(dest / "holdings.parquet", index=False)
    manifest_p = RAW / snapshot / "manifest.json"
    report = qa_report(results, snapshot, json.loads(manifest_p.read_text()) if manifest_p.exists() else None)
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports" / f"qa_{snapshot}.md").write_text(report)
    print(f"curated: {len(good):,} rows loaded, {len(bad):,} quarantined -> reports/qa_{snapshot}.md")


def cmd_apra(args):
    from .apra import run
    run(_snap(args))


def cmd_enrich(args):
    from .enrich import apply_security_master, build_security_master, resolve_managers
    snapshot = _snap(args)
    p = CURATED / snapshot / "holdings.parquet"
    if not p.exists():
        sys.exit("no curated holdings; run ingest first")
    df = pd.read_parquet(p)
    df = resolve_managers(df)
    if not args.skip_openfigi:
        master = build_security_master(df)
        df = apply_security_master(df, master)
    df.to_parquet(p, index=False)
    print(f"enriched {len(df):,} rows; manager_id resolved on {(df['manager_id'].astype(bool)).sum():,} rows; "
          f"gics on {(df['gics_sector'].astype(bool)).sum():,} rows")


def cmd_build(args):
    from .build import build_index, build_snapshot, export_duckdb
    snapshot = _snap(args)
    print(build_snapshot(snapshot))
    build_index()
    export_duckdb()


def cmd_refresh(args):
    cmd_harvest(args)
    cmd_apra(args)
    cmd_ingest(args)
    cmd_enrich(args)
    cmd_build(args)


def cmd_import_reference(args):
    from .reference_import import import_holdings, import_saa
    import_holdings(Path(args.holdings), snapshot=args.snapshot or "2025-12-31")
    if args.saa:
        import_saa(Path(args.saa), snapshot=args.snapshot or "2025-12-31")


def cmd_repair_context(args):
    from .llm_repair import write_context
    print(write_context(_snap(args)))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="pipeline")
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument("--snapshot", help="reporting date, e.g. 2026-06-30 (default: latest closed PHD window)")
    parent.add_argument("--only", help="comma-separated fund_ids")
    parent.add_argument("--append", action="store_true", help="ingest: keep other funds already in curated")
    parent.add_argument("--skip-openfigi", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn in [("harvest", cmd_harvest), ("ingest", cmd_ingest), ("apra", cmd_apra), ("enrich", cmd_enrich), ("build", cmd_build), ("refresh", cmd_refresh), ("repair-context", cmd_repair_context)]:
        sub.add_parser(name, parents=[parent]).set_defaults(fn=fn)
    ir = sub.add_parser("import-reference", parents=[parent])
    ir.add_argument("holdings")
    ir.add_argument("saa", nargs="?")
    ir.set_defaults(fn=cmd_import_reference)
    args = ap.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
