"""APRA statistics loaders.

Publications used
  * Quarterly Superannuation Product Statistics (QSPS) — "Performance" workbook
        Table 8a Investment Strategy (MySuper SAA targets & ranges, SRF 550.0)
        Fees and costs tables (MySuper representative member)
    and the "Product Structure" workbook (every product / investment menu / option and its size)
  * Quarterly Superannuation Fund-level Statistics — whole-of-fund assets by asset sector
  * Annual Fund-level Superannuation Statistics — expenses (SRS 332.0) incl. investment expenses

APRA republishes these workbooks every quarter under new file names, so we *discover* the links on
the publication page rather than hard-coding them, then locate sheets and header rows by content.
Column names are matched by regex; if APRA renames a column the loader raises a clear error that the
repair step (or you) can fix in COLUMN_HINTS below.
"""
from __future__ import annotations

import io
import json
import re
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

from . import BUCKETS, CURATED, RAW
from .harvest import UA

PAGES = {
    "qsps": "https://www.apra.gov.au/quarterly-superannuation-product-statistics",
    "fund_level": "https://www.apra.gov.au/quarterly-fund-level-statistics",
    "annual_fund_level": "https://www.apra.gov.au/annual-fund-level-superannuation-statistics",
}

# APRA granular strategy classes -> our 10 buckets
APRA_CLASS_TO_BUCKET = [
    (re.compile(r"australian.*listed equity|australian equity", re.I), "Australian Equity"),
    (re.compile(r"international.*listed equity|international equity|emerging", re.I), "International Equity"),
    (re.compile(r"unlisted equity|private equity", re.I), "Private Equity"),
    (re.compile(r"property|real estate", re.I), "Property"),
    (re.compile(r"infrastructure", re.I), "Infrastructure"),
    (re.compile(r"australian.*(fixed income|credit|bond)", re.I), "Australian Fixed Income"),
    (re.compile(r"international.*(fixed income|credit|bond)|credit", re.I), "International Fixed Income"),
    (re.compile(r"fixed income|bond", re.I), "Australian Fixed Income"),
    (re.compile(r"cash", re.I), "Cash"),
    (re.compile(r"alternative|commodit|hedge|other", re.I), "Alternatives"),
]

COLUMN_HINTS = {
    "fund_name": [r"^rse name", r"fund name", r"^rse$", r"superannuation entity"],
    "rse_abn": [r"abn"],
    "product": [r"product name", r"mysuper product", r"^product"],
    "stage": [r"lifecycle stage", r"stage name", r"^stage", r"investment option name", r"option name"],
    "asset_class": [r"asset class", r"asset sector", r"strategic asset"],
    "target": [r"strategic.*(target|allocation)", r"^target", r"benchmark allocation"],
    "lower": [r"lower|minimum|min\b"],
    "upper": [r"upper|maximum|max\b"],
    "assets": [r"total assets|member assets|net assets|assets \(\$|fum"],
    "accounts": [r"member accounts|number of member"],
    "period": [r"period|quarter|date"],
    "admin_fee": [r"admin"],
    "inv_fee": [r"investment fee"],
    "txn_cost": [r"transaction"],
    "total_fee": [r"total fee|total annual"],
    "expense_type": [r"expense (type|category|group)"],
    "amount": [r"amount|expense \(\$|value"],
}


def _hdr(cols: list[str]) -> dict[str, int]:
    out = {}
    for field, pats in COLUMN_HINTS.items():
        for i, c in enumerate(cols):
            lc = str(c).lower()
            if any(re.search(p, lc) for p in pats):
                out[field] = i
                break
    return out


def _find_header_row(df: pd.DataFrame, must: list[str], scan: int = 40) -> tuple[int, dict[str, int]] | None:
    for i in range(min(scan, len(df))):
        cols = [str(x) for x in df.iloc[i].tolist()]
        h = _hdr(cols)
        if all(m in h for m in must):
            return i, h
    return None


def _tidy(df: pd.DataFrame, hrow: int, h: dict[str, int]) -> pd.DataFrame:
    body = df.iloc[hrow + 1:].reset_index(drop=True)
    out = pd.DataFrame({k: body.iloc[:, v] for k, v in h.items()})
    return out.dropna(how="all")


def discover_workbooks(page_key: str) -> list[dict]:
    r = requests.get(PAGES[page_key], headers={"User-Agent": UA}, timeout=60)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    out = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if re.search(r"\.(xlsx|xls|csv|zip)$", href, re.I):
            out.append({"url": href if href.startswith("http") else "https://www.apra.gov.au" + href, "text": a.get_text(" ", strip=True)})
    return out


def download(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        return dest
    r = requests.get(url, headers={"User-Agent": UA}, timeout=300)
    r.raise_for_status()
    dest.write_bytes(r.content)
    return dest


def fetch_qsps(snapshot: str) -> dict[str, Path]:
    links = discover_workbooks("qsps")
    want = {"performance": r"performance", "product_structure": r"product structure", "historical_saa": r"historical saa"}
    paths = {}
    for key, rx in want.items():
        hit = next((l for l in links if re.search(rx, l["text"], re.I) and not re.search(r"historical performance", l["text"], re.I)), None)
        if hit:
            ext = ".csv" if hit["url"].lower().endswith(".csv") else ".xlsx"
            paths[key] = download(hit["url"], RAW / snapshot / "apra" / f"qsps_{key}{ext}")
    return paths


def load_saa(performance_xlsx: Path) -> pd.DataFrame:
    """Table 8a Investment Strategy -> long rows: fund_name, product, stage, asset_class, target, lower, upper, bucket."""
    book = pd.read_excel(performance_xlsx, sheet_name=None, header=None, dtype=object)
    sheet = next((n for n in book if re.search(r"8a|investment strategy", str(n), re.I)), None)
    if sheet is None:
        raise RuntimeError(f"No 'Table 8a / Investment Strategy' sheet in {performance_xlsx.name}; sheets: {list(book)[:20]}")
    df = book[sheet]
    found = _find_header_row(df, ["fund_name", "asset_class", "target"])
    if not found:
        raise RuntimeError("Table 8a header row not recognised — update COLUMN_HINTS in pipeline/apra.py")
    t = _tidy(df, *found)
    for c in ("target", "lower", "upper"):
        if c in t:
            t[c] = pd.to_numeric(t[c], errors="coerce")
    t["bucket"] = t["asset_class"].astype(str).apply(lambda s: next((b for rx, b in APRA_CLASS_TO_BUCKET if rx.search(s)), "Other"))
    return t


def load_fees(performance_xlsx: Path) -> pd.DataFrame:
    book = pd.read_excel(performance_xlsx, sheet_name=None, header=None, dtype=object)
    sheet = next((n for n in book if re.search(r"fee", str(n), re.I)), None)
    if sheet is None:
        raise RuntimeError("No fees sheet found in QSPS Performance workbook")
    df = book[sheet]
    found = _find_header_row(df, ["fund_name", "product"])
    if not found:
        raise RuntimeError("Fees header row not recognised — update COLUMN_HINTS")
    t = _tidy(df, *found)
    for c in ("admin_fee", "inv_fee", "txn_cost", "total_fee"):
        if c in t:
            t[c] = pd.to_numeric(t[c], errors="coerce")
    return t


def load_product_structure(product_xlsx: Path) -> pd.DataFrame:
    """Every investment option with its size — used for G2 validation and whole-of-fund context."""
    book = pd.read_excel(product_xlsx, sheet_name=None, header=None, dtype=object)
    frames = []
    for name, df in book.items():
        found = _find_header_row(df, ["fund_name", "stage"])
        if found:
            t = _tidy(df, *found)
            t["sheet"] = name
            frames.append(t)
    if not frames:
        raise RuntimeError("Product Structure: no sheet with fund + option columns recognised")
    t = pd.concat(frames, ignore_index=True)
    if "assets" in t:
        t["assets"] = pd.to_numeric(t["assets"], errors="coerce")
    return t


def fetch_fund_level(snapshot: str) -> Path | None:
    links = discover_workbooks("fund_level")
    hit = next((l for l in links if l["url"].lower().endswith(".xlsx")), None)
    return download(hit["url"], RAW / snapshot / "apra" / "fund_level.xlsx") if hit else None


def load_fund_level(xlsx: Path) -> pd.DataFrame:
    book = pd.read_excel(xlsx, sheet_name=None, header=None, dtype=object)
    frames = []
    for name, df in book.items():
        found = _find_header_row(df, ["fund_name", "assets"])
        if found:
            t = _tidy(df, *found)
            t["sheet"] = name
            frames.append(t)
    if not frames:
        raise RuntimeError("Fund-level statistics: no sheet with fund + total assets recognised")
    t = pd.concat(frames, ignore_index=True)
    t["assets"] = pd.to_numeric(t["assets"], errors="coerce")
    return t


def fetch_expenses(snapshot: str) -> Path | None:
    links = discover_workbooks("annual_fund_level")
    hit = next((l for l in links if re.search(r"expense", l["text"] + l["url"], re.I) and l["url"].lower().endswith((".xlsx", ".csv"))), None)
    if not hit:
        return None
    ext = ".csv" if hit["url"].lower().endswith(".csv") else ".xlsx"
    return download(hit["url"], RAW / snapshot / "apra" / f"expenses{ext}")


def load_expenses(path: Path) -> pd.DataFrame:
    if path.suffix == ".csv":
        t = pd.read_csv(path, dtype=object)
        h = _hdr(list(t.columns))
        t = t.rename(columns={t.columns[v]: k for k, v in h.items()})
    else:
        book = pd.read_excel(path, sheet_name=None, header=None, dtype=object)
        frames = []
        for name, df in book.items():
            found = _find_header_row(df, ["fund_name", "expense_type", "amount"])
            if found:
                frames.append(_tidy(df, *found))
        if not frames:
            raise RuntimeError("Expenses workbook: no sheet with fund + expense type + amount recognised")
        t = pd.concat(frames, ignore_index=True)
    t["amount"] = pd.to_numeric(t["amount"], errors="coerce")
    t["is_investment"] = t["expense_type"].astype(str).str.contains("invest", case=False)
    return t


def run(snapshot: str) -> dict:
    """Fetch and load everything; write parquet to curated/<snapshot>/apra_*.parquet. Never fatal: each
    dataset is independent and missing ones are reported."""
    out_dir = CURATED / snapshot
    out_dir.mkdir(parents=True, exist_ok=True)
    status = {}
    try:
        paths = fetch_qsps(snapshot)
        if "performance" in paths:
            load_saa(paths["performance"]).to_parquet(out_dir / "apra_saa.parquet", index=False)
            status["saa"] = "ok"
            try:
                load_fees(paths["performance"]).to_parquet(out_dir / "apra_fees.parquet", index=False)
                status["fees"] = "ok"
            except Exception as e:  # noqa: BLE001
                status["fees"] = f"failed: {e}"
        else:
            status["saa"] = "Performance workbook link not found on APRA page"
        if "product_structure" in paths:
            load_product_structure(paths["product_structure"]).to_parquet(out_dir / "apra_products.parquet", index=False)
            status["products"] = "ok"
    except Exception as e:  # noqa: BLE001
        status["qsps"] = f"failed: {e}"
    try:
        p = fetch_fund_level(snapshot)
        if p:
            load_fund_level(p).to_parquet(out_dir / "apra_fund_level.parquet", index=False)
            status["fund_level"] = "ok"
    except Exception as e:  # noqa: BLE001
        status["fund_level"] = f"failed: {e}"
    try:
        p = fetch_expenses(snapshot)
        if p:
            load_expenses(p).to_parquet(out_dir / "apra_expenses.parquet", index=False)
            status["expenses"] = "ok"
        else:
            status["expenses"] = "no expense workbook link found"
    except Exception as e:  # noqa: BLE001
        status["expenses"] = f"failed: {e}"
    (out_dir / "apra_status.json").write_text(json.dumps(status, indent=2))
    print(json.dumps(status, indent=2))
    return status
