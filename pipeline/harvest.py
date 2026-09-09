"""Discover and download Portfolio Holdings Disclosure files for every fund in the registry.

Strategy (per fund):
  1. Fetch the landing page (requests; Playwright fallback for JavaScript-rendered pages).
  2. Collect candidate links: anything ending in .xlsx/.xls/.csv/.pdf/.zip, or whose link text / URL
     contains a discovery keyword ("portfolio holdings", "holdings disclosure" ...).
  3. Follow keyword pages one level deep and repeat step 2.
  4. Download every candidate file into raw/<snapshot>/<fund_id>/ with a manifest of URL, sha256,
     size, content-type and download time. Raw files are never modified.

The harvester is deliberately generous: it is cheaper to download an extra PDS than to miss a
holdings file. The parser decides what is actually a Schedule 8D table.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from . import RAW
from .registry import Source, load_sources

UA = "SuperInsightsBot/1.0 (+public portfolio holdings disclosure research; contact via repo issues)"
FILE_EXT = re.compile(r"\.(xlsx|xlsm|xls|csv|pdf|zip|txt)(\?.*)?$", re.I)
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": UA})


def _get(url: str, timeout: int = 60) -> requests.Response | None:
    try:
        r = SESSION.get(url, timeout=timeout, allow_redirects=True)
        if r.status_code == 200:
            return r
        print(f"    ! {r.status_code} {url}")
    except requests.RequestException as e:
        print(f"    ! {type(e).__name__} {url}")
    return None


def _render_with_playwright(url: str) -> str | None:
    """Fallback for pages that only expose links after JavaScript runs."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(user_agent=UA)
            page.goto(url, wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(1500)
            html = page.content()
            browser.close()
            return html
    except Exception as e:  # noqa: BLE001
        print(f"    ! playwright failed: {e}")
        return None


def _links(html: str, base: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for a in soup.find_all("a", href=True):
        href = urljoin(base, a["href"].strip())
        text = " ".join(a.get_text(" ", strip=True).split())
        out.append((href, text))
    return out


def discover(source: Source, max_pages: int = 8) -> list[dict]:
    """Return candidate file URLs for one fund."""
    seen_pages, seen_files, queue, files = set(), set(), [source.phd_landing_url], []
    host = urlparse(source.phd_landing_url).netloc
    while queue and len(seen_pages) < max_pages:
        url = queue.pop(0)
        if url in seen_pages:
            continue
        seen_pages.add(url)
        r = _get(url)
        html = r.text if r is not None else None
        if html is None or "<a" not in html.lower():
            html = _render_with_playwright(url) or ""
        for href, text in _links(html, url):
            blob = f"{href} {text}".lower()
            kw_hit = any(k in blob for k in source.keywords) or "holding" in blob
            if FILE_EXT.search(href) or "GetPortfolioHoldingsFile" in href or "coredownload" in href:
                if (kw_hit or FILE_EXT.search(href)) and href not in seen_files:
                    seen_files.add(href)
                    files.append({"url": href, "text": text, "found_on": url, "keyword_hit": kw_hit})
            elif kw_hit and urlparse(href).netloc == host and href not in seen_pages and len(queue) < 40:
                queue.append(href)
    # Prefer keyword hits; drop obvious non-holdings documents when we have keyword hits
    if any(f["keyword_hit"] for f in files):
        noise = re.compile(r"pds|product disclosure|insurance|fact ?sheet|annual report|policy|form", re.I)
        files = [f for f in files if f["keyword_hit"] or not noise.search(f["url"] + " " + f["text"])]
    return files


def _safe_name(url: str) -> str:
    name = urlparse(url).path.rsplit("/", 1)[-1] or "download"
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)[:120]
    return name


def harvest(snapshot: str, only: list[str] | None = None, sleep: float = 1.0) -> dict:
    """Download all discovered files for every fund. Returns the manifest."""
    manifest = {"snapshot": snapshot, "harvested_at": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z", "funds": {}}
    for src in load_sources(only=only):
        print(f"== {src.fund_name} ({src.fund_id})")
        fund_dir = RAW / snapshot / src.fund_id
        fund_dir.mkdir(parents=True, exist_ok=True)
        entry = {"fund_name": src.fund_name, "landing": src.phd_landing_url, "files": [], "errors": []}
        if src.expected_format == "powerbi":
            entry["errors"].append("Power BI disclosure: export manually or extend harvest.py with a Playwright exporter")
            manifest["funds"][src.fund_id] = entry
            continue
        try:
            candidates = discover(src)
        except Exception as e:  # noqa: BLE001
            entry["errors"].append(f"discovery failed: {e}")
            candidates = []
        if not candidates:
            entry["errors"].append("no candidate files found on landing page; check phd_landing_url in config/sources.csv")
        for c in candidates:
            r = _get(c["url"], timeout=180)
            time.sleep(sleep)
            if r is None:
                entry["errors"].append(f"download failed: {c['url']}")
                continue
            data = r.content
            name = _safe_name(c["url"])
            ctype = r.headers.get("content-type", "")
            if not FILE_EXT.search(name):
                ext = ".xlsx" if "spreadsheet" in ctype else ".csv" if "csv" in ctype else ".pdf" if "pdf" in ctype else ".bin"
                name += ext
            sha = hashlib.sha256(data).hexdigest()
            path = fund_dir / f"{sha[:10]}_{name}"
            path.write_bytes(data)
            entry["files"].append({
                "url": c["url"], "link_text": c["text"], "found_on": c["found_on"], "file": str(path.relative_to(RAW)),
                "sha256": sha, "bytes": len(data), "content_type": ctype,
            })
            print(f"    + {name} ({len(data)//1024} KB)")
        manifest["funds"][src.fund_id] = entry
    (RAW / snapshot / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest
