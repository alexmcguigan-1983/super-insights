"""Fund registry (config/sources.csv) and snapshot helpers."""
from __future__ import annotations

import csv
import datetime as dt
from dataclasses import dataclass
from pathlib import Path

from . import CONFIG


@dataclass
class Source:
    fund_id: str
    fund_name: str
    rse_abn: str
    fund_type: str
    phd_landing_url: str
    expected_format: str
    discovery_keywords: str
    notes: str
    verified: str

    @property
    def formats(self) -> list[str]:
        return [f.strip() for f in self.expected_format.split("|") if f.strip()]

    @property
    def keywords(self) -> list[str]:
        return [k.strip().lower() for k in self.discovery_keywords.split(";") if k.strip()]


def load_sources(path: Path | None = None, only: list[str] | None = None) -> list[Source]:
    import os
    path = path or Path(os.environ.get("SOURCES_CSV", CONFIG / "sources.csv"))
    with open(path, newline="", encoding="utf-8") as f:
        rows = [Source(**{k: (v or "") for k, v in r.items()}) for r in csv.DictReader(f)]
    if only:
        rows = [r for r in rows if r.fund_id in only]
    return rows


def latest_reporting_date(today: dt.date | None = None) -> dt.date:
    """The most recent PHD reporting day whose 90-day publication window has closed.

    Reporting days are 30 June and 31 December; trustees have 90 days to publish.
    """
    today = today or dt.date.today()
    candidates = [dt.date(today.year, 6, 30), dt.date(today.year - 1, 12, 31), dt.date(today.year - 1, 6, 30)]
    for c in candidates:
        if (today - c).days >= 90:
            return c
    return dt.date(today.year - 2, 12, 31)


def snapshot_id(reporting_date: dt.date) -> str:
    return reporting_date.isoformat()
