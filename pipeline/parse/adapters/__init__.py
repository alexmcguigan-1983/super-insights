"""Fund-specific parsing overrides.

Register an adapter when the generic parser cannot read a fund's layout. An adapter receives the
fund's raw directory for a snapshot and returns a staging DataFrame (see parse/__init__.py).
Everything not registered here goes through the generic parser file by file.

Adding an adapter (the repair loop does this automatically when a Claude API key is configured):
    1. Copy the failing raw file into tests/fixtures/<fund_id>/.
    2. Write parse_<fund_id>(raw_dir) below, returning STAGING_COLUMNS.
    3. Add a test in tests/test_adapters.py asserting row count, option names and value totals.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

import pandas as pd

from ..generic import parse_file, STAGING_COLUMNS

Adapter = Callable[[Path], pd.DataFrame]
ADAPTERS: dict[str, Adapter] = {}


def register(fund_id: str):
    def deco(fn: Adapter):
        ADAPTERS[fund_id] = fn
        return fn
    return deco


def _all_files(raw_dir: Path) -> list[Path]:
    return sorted(p for p in raw_dir.iterdir() if p.is_file() and p.suffix.lower() in {".xlsx", ".xlsm", ".xls", ".csv", ".pdf", ".txt"})


@register("hostplus")
def parse_hostplus(raw_dir: Path) -> pd.DataFrame:
    """Hostplus publishes one file per asset class (Cash, Fixed-Interest, Infrastructure ...) rather than per
    option, with 'super' and 'pension' variants. Treat each as the default option ('Balanced') unless the path says pension,
    and use the file name as the section so classification is deterministic."""
    frames = []
    for p in _all_files(raw_dir):
        opt = "Pension (whole-of-plan)" if "pension" in str(p).lower() else "Balanced (whole-of-fund)"
        df = parse_file(p, option_hint=opt)
        if df.empty:
            continue
        section = re.sub(r"^[0-9a-f]{10}_|investment[-_ ]holdings[-_ ]disclosure[-_ ]?|\.pdf\.coredownload|", "", p.stem, flags=re.I)
        df["section"] = df["section"].where(df["section"].astype(bool), section.replace("-", " "))
        frames.append(df)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=STAGING_COLUMNS)


@register("rest")
def parse_rest(raw_dir: Path) -> pd.DataFrame:
    """Rest publishes one CSV per option per Schedule 8D table, e.g. super-australian-shares-indexed-table3.csv.
    The file name carries the option (everything before -tableN) and the table number carries the asset class."""
    table_names = {"1": "Cash", "2": "Fixed income", "3": "Listed equity", "4": "Unlisted equity", "5": "Listed property",
                   "6": "Unlisted property", "7": "Listed infrastructure", "8": "Unlisted infrastructure", "9": "Alternatives", "10": "Derivatives"}
    frames = []
    for p in _all_files(raw_dir):
        m = re.search(r"^(?:[0-9a-f]{10}_)?(super|pension)?-?(.*?)-?table(\d+)", p.stem, re.I)
        if m:
            opt = (m.group(2) or "default").replace("-", " ").title()
            if m.group(1):
                opt = f"{opt} ({m.group(1).title()})"
            df = parse_file(p, option_hint=opt)
            if not df.empty:
                df["section"] = df["section"].where(df["section"].astype(bool), table_names.get(m.group(3), ""))
        else:
            df = parse_file(p)
        if not df.empty:
            frames.append(df)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=STAGING_COLUMNS)


def parse_fund(fund_id: str, raw_dir: Path) -> pd.DataFrame:
    if fund_id in ADAPTERS:
        return ADAPTERS[fund_id](raw_dir)
    frames = [parse_file(p) for p in _all_files(raw_dir)]
    frames = [f for f in frames if not f.empty]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=STAGING_COLUMNS)
