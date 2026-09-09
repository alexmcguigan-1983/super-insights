"""Prepare everything a repair agent (Claude Code) needs to fix parsing failures.

The agent never runs blind: this module writes reports/repair_<snapshot>.md containing, for every fund
that harvested nothing, parsed nothing, or was quarantined, a preview of the raw file(s) (first rows of each
sheet / first page of each PDF), the gate reasons, and the exact instructions for the fix (new adapter,
mapping-table row, or registry URL). The GitHub workflow hands this file to the agent; without an API key
it is simply attached to the issue for a human to work through.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from . import QUARANTINE, RAW, ROOT
from .parse.generic import read_raw
from .registry import load_sources

INSTRUCTIONS = """
## How to repair

For each fund below, do ONE of:
1. **Wrong landing page / no files harvested** → fix `phd_landing_url` in `config/sources.csv` (find the fund's
   "Portfolio holdings disclosure" page; the file links must be reachable from it), set `verified=yes`.
2. **Files harvested but 0 rows parsed / partial parse** → write an adapter in `pipeline/parse/adapters/__init__.py`
   using `@register("<fund_id>")`. Use the raw preview to see the real header row and section headings. Return the
   staging columns listed in `pipeline/parse/__init__.py`. Copy the raw file to `tests/fixtures/<fund_id>/` and add a
   test in `tests/test_adapters.py` asserting row count and option total.
3. **Quarantined for classification (G3 'Other' too high)** → add a pattern row to `config/asset_class_map.csv`.
4. **Quarantined for G2 size mismatch** → check whether the file is per-option or whole-of-fund and whether values
   are in $ or $'000 (add a `value_multiplier` in the adapter).
Then run `make test` and `python -m pipeline.cli ingest --snapshot <snapshot> --only <fund_id> --append` until the fund
passes, and open a pull request titled `repair(<fund_id>): <what you changed>`.
"""


def _preview(path: Path, rows: int = 25) -> str:
    try:
        parts = []
        for sheet, df in read_raw(path)[:6]:
            head = df.head(rows).fillna("").astype(str)
            parts.append(f"--- sheet/page: {sheet} ({len(df)} rows x {df.shape[1]} cols)\n" + head.to_string(index=True, header=False, max_colwidth=40))
        return "\n".join(parts) if parts else "(unreadable)"
    except Exception as e:  # noqa: BLE001
        return f"(preview failed: {e})"


def write_context(snapshot: str) -> Path:
    manifest_p = RAW / snapshot / "manifest.json"
    manifest = json.loads(manifest_p.read_text()) if manifest_p.exists() else {"funds": {}}
    reasons_p = QUARANTINE / snapshot / "reasons.json"
    reasons = json.loads(reasons_p.read_text()) if reasons_p.exists() else []
    by_fund: dict[str, list] = {}
    for r in reasons:
        by_fund.setdefault(r["fund_id"], []).append(r)
    curated_funds = set()
    cp = ROOT / "curated" / snapshot / "holdings.parquet"
    if cp.exists():
        curated_funds = set(pd.read_parquet(cp, columns=["fund_id"])["fund_id"].unique())
    lines = [f"# Repair context — snapshot {snapshot}", INSTRUCTIONS, ""]
    for src in load_sources():
        entry = manifest["funds"].get(src.fund_id, {})
        files = entry.get("files", [])
        problems = list(entry.get("errors", []))
        if files and src.fund_id not in curated_funds and src.fund_id not in by_fund:
            problems.append("files harvested but no rows loaded (parser returned nothing)")
        for q in by_fund.get(src.fund_id, []):
            problems.append(f"quarantined option '{q['option_name']}': " + "; ".join(q["reasons"]))
        if not problems:
            continue
        lines += [f"## {src.fund_name} (`{src.fund_id}`)", "", f"- landing: {src.phd_landing_url}", f"- expected format: {src.expected_format}"]
        lines += [f"- problem: {p}" for p in problems]
        lines.append("")
        for f in files[:4]:
            p = RAW / f["file"]
            lines += [f"### raw preview: `{p.name}` ({f['bytes']//1024} KB) from {f['url']}", "```", _preview(p), "```", ""]
    out = ROOT / "reports" / f"repair_{snapshot}.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join(lines))
    return out
