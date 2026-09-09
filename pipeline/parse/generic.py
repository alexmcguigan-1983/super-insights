"""Generic Schedule 8D parser for XLSX / XLS / CSV / PDF holdings files.

Schedule 8D (Corporations Regulations 2001) prescribes tables per asset class with columns such as
"Name / kind of investment item", "Security identifier", "Units held", "Value (AUD)", "Weighting (%)",
plus maturity / face value / coupon for fixed income, and "Internally managed" vs "Externally managed"
sub-tables. Funds present these with wildly different headings, so we detect header rows and section
headings heuristically rather than by fixed positions.
"""
from __future__ import annotations

import re
import datetime as dt
from pathlib import Path

import pandas as pd

STAGING_COLUMNS = [
    "option_name", "section", "subsection", "holding_name", "security_id", "units", "value", "weight",
    "currency", "maturity", "coupon", "face_value", "manager", "reporting_date", "source_file", "sheet", "row",
]

# Column-name synonyms (lower-cased, matched by substring or regex).
COLUMN_PATTERNS: dict[str, list[str]] = {
    # order matters: specific fields first so "Coupon (%)" is not swallowed by the weight pattern "%"
    "security_id": [r"security id", r"identifier", r"isin", r"sedol", r"ticker", r"code$", r"\bid\b"],
    "units": [r"^units", r"units held", r"quantity", r"number of units", r"no\.? of", r"shares held"],
    "maturity": [r"maturity"],
    "coupon": [r"coupon", r"interest rate", r"yield"],
    "face_value": [r"face value", r"par value", r"nominal", r"principal"],
    "currency": [r"^currency", r"^ccy", r"denominat"],
    "geography": [r"country", r"domicile", r"region", r"geograph"],
    "sector": [r"sector", r"industry", r"gics"],
    "asset_class": [r"asset class", r"asset type", r"asset sector", r"category", r"^table", r"investment type"],
    "management": [r"^management$", r"managed \(", r"internal.*external", r"management type", r"mandate type"],
    "manager": [r"manager", r"managed by", r"fund manager"],
    "holding_name": [r"^name", r"investment item", r"security name", r"holding", r"asset name", r"description", r"issuer", r"kind of investment", r"^investment$", r"^asset$", r"counterparty", r"institution"],
    "value": [r"value", r"aud", r"\$", r"market val", r"amount", r"dollar"],
    "weight": [r"weight", r"%", r"percent", r"proportion", r"allocation", r"portfolio"],
}
HEADER_MIN_HITS = 2
SECTION_HINTS = re.compile(
    r"(cash|bank bill|term deposit|fixed (interest|income)|bond|credit|debt|equit|share|property|real estate|infrastructure|"
    r"alternative|private|unlisted|listed|derivative|future|forward|option|swap|commodit|hedge|internally managed|externally managed|"
    r"table \d|other)", re.I)
TOTAL_RE = re.compile(r"^(sub[- ]?)?total|^grand total|^aggregate", re.I)
DATE_RES = [
    (re.compile(r"(\d{1,2})[ /-](jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[ /-](\d{4})", re.I), "dmy_text"),
    (re.compile(r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[ ,-]+(\d{4})", re.I), "my_text"),
    (re.compile(r"(\d{4})-(\d{2})-(\d{2})"), "iso"),
    (re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})"), "dmy"),
    (re.compile(r"(\d{4})(\d{2})(\d{2})"), "ymd_compact"),
]
MONTHS = {m: i + 1 for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}


def find_date(text: str) -> dt.date | None:
    """Find a plausible PHD reporting date (30 June / 31 December) in free text; else any date."""
    if not text:
        return None
    found: list[dt.date] = []
    for rx, kind in DATE_RES:
        for m in rx.finditer(text):
            try:
                if kind == "dmy_text":
                    d = dt.date(int(m.group(3)), MONTHS[m.group(2).lower()[:3]], int(m.group(1)))
                elif kind == "my_text":
                    mo = MONTHS[m.group(1).lower()[:3]]
                    y = int(m.group(2))
                    d = dt.date(y, mo, 30 if mo == 6 else 31 if mo == 12 else 28)
                elif kind == "iso":
                    d = dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                elif kind == "dmy":
                    d = dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
                else:
                    d = dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                if 2019 <= d.year <= 2040:
                    found.append(d)
            except (ValueError, KeyError):
                continue
    if not found:
        return None
    phd = [d for d in found if (d.month, d.day) in ((6, 30), (12, 31))]
    return max(phd) if phd else max(found)


def _cell(x) -> str:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return ""
    return str(x).strip()


def _to_num(x):
    s = _cell(x)
    if not s or s in {"-", "—", "n/a", "N/A", "nil"}:
        return None
    neg = s.startswith("(") and s.endswith(")")
    s = re.sub(r"[^\d.\-eE]", "", s.replace(",", ""))
    if s in {"", "-", ".", "-."}:
        return None
    try:
        v = float(s)
    except ValueError:
        return None
    return -v if neg else v


def _match_columns(cells: list[str]) -> dict[int, str]:
    """Map column index -> canonical field for a candidate header row."""
    mapping: dict[int, str] = {}
    taken: set[str] = set()
    for i, c in enumerate(cells):
        lc = c.lower()
        if not lc:
            continue
        for field, pats in COLUMN_PATTERNS.items():
            if field in taken:
                continue
            if any(re.search(p, lc) for p in pats):
                # avoid mapping "Value" to weight etc: value/weight ambiguity resolved by order of dict
                mapping[i] = field
                taken.add(field)
                break
    return mapping


def _is_header(cells: list[str]) -> bool:
    m = _match_columns(cells)
    return len(m) >= HEADER_MIN_HITS and ("holding_name" in m.values() or "manager" in m.values()) and (
        "value" in m.values() or "weight" in m.values() or "units" in m.values())


def _is_section(cells: list[str]) -> str | None:
    non_empty = [c for c in cells if c]
    if len(non_empty) == 1 and 3 <= len(non_empty[0]) <= 120 and SECTION_HINTS.search(non_empty[0]) and not _to_num(non_empty[0]):
        return non_empty[0]
    return None


def _split_section(text: str, current_section: str) -> tuple[str, str]:
    """'Fixed income — Externally managed' -> ('Fixed income', 'Externally managed');
    'Externally managed' -> (current_section, 'Externally managed'); 'Cash' -> ('Cash', '')."""
    parts = re.split(r"\s+[—–-]\s+|\s*[:|]\s*", text, maxsplit=1)
    managed = re.compile(r"internally|externally", re.I)
    if len(parts) == 2 and managed.search(parts[1]) and not managed.search(parts[0]):
        return parts[0].strip(), parts[1].strip()
    if managed.search(text):
        rest = managed.sub("", text)
        rest = re.sub(r"\bmanaged\b|[—–:()-]", "", rest, flags=re.I).strip()
        # "Externally managed fixed income" style: the remainder names the asset class
        return (rest if rest and SECTION_HINTS.search(rest) else current_section), text.strip()
    return text.strip(), ""


def parse_frame(df: pd.DataFrame, *, source_file: str, sheet: str, option_hint: str, date_hint: dt.date | None) -> pd.DataFrame:
    """Walk a raw sheet and emit staging rows."""
    rows: list[dict] = []
    section, subsection, mapping, header_row = "", "", {}, -1
    text_blob = " ".join(_cell(v) for v in df.head(15).values.flatten())
    blob_date = find_date(text_blob)
    if blob_date and (blob_date.month, blob_date.day) in ((6, 30), (12, 31)):
        reporting_date = blob_date
    else:
        reporting_date = date_hint or blob_date
    option_name = option_hint
    m_opt = re.search(r"(?:investment )?option[:\s-]+([A-Za-z0-9 &/()'+-]{3,60})", text_blob, re.I)
    if m_opt and not option_hint:
        option_name = m_opt.group(1).strip()

    for idx, raw in enumerate(df.itertuples(index=False)):
        cells = [_cell(v) for v in raw]
        if not any(cells):
            continue
        sec = _is_section(cells)
        if sec:
            section, subsection = _split_section(sec, section)
            continue
        if _is_header(cells):
            mapping, header_row = _match_columns(cells), idx
            continue
        if not mapping:
            continue
        rec = {f: cells[i] if i < len(cells) else "" for i, f in mapping.items()}
        name = rec.get("holding_name", "") or rec.get("manager", "")
        if not name:
            continue
        if TOTAL_RE.match(name):
            continue
        value, weight = _to_num(rec.get("value")), _to_num(rec.get("weight"))
        if value is None and weight is None and _to_num(rec.get("units")) is None:
            # A row of text under a data header is most likely a sub-heading (e.g. "Externally managed")
            if re.search(r"internally|externally", name, re.I) or (SECTION_HINTS.search(name) and len(name) < 60):
                section, subsection = _split_section(name, section)
            continue
        row_section = rec.get("asset_class", "") or section
        row_sub = rec.get("management", "") or subsection
        rows.append({
            "option_name": option_name, "section": row_section, "subsection": row_sub,
            "holding_name": name, "security_id": rec.get("security_id", ""), "units": _to_num(rec.get("units")),
            "value": value, "weight": weight, "currency": rec.get("currency", ""), "maturity": rec.get("maturity", ""),
            "coupon": _to_num(rec.get("coupon")), "face_value": _to_num(rec.get("face_value")),
            "manager": rec.get("manager", ""), "geography_raw": rec.get("geography", ""), "sector_raw": rec.get("sector", ""),
            "reporting_date": reporting_date, "source_file": source_file, "sheet": sheet, "row": idx + 1,
        })
    return pd.DataFrame(rows)


PDF_LINE = re.compile(r"^(?P<name>.+?)\s+(?P<id>[A-Z]{2}[A-Z0-9]{9}\d|[A-Z0-9]{6,7}|[A-Z]{2,6}(?: [A-Z]{2})?)?\s*(?P<v1>\(?-?[\d,]+(?:\.\d+)?\)?)\s+(?P<v2>\(?-?[\d,]+(?:\.\d+)?%?\)?)\s*$")


def _pdf_text_table(text: str) -> pd.DataFrame:
    """Rebuild a table from PDF text lines: heading lines become single-cell rows, data lines split into
    name / id / value / weight. Header lines are synthesised so the generic walker recognises them."""
    rows: list[list] = []
    in_table = False
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        low = line.lower()
        if re.search(r"\bvalue\b", low) and re.search(r"weight|%", low):
            rows.append(["Name", "Security identifier", "Value (AUD)", "Weighting (%)"])
            in_table = True
            continue
        m = PDF_LINE.match(line)
        if m and _to_num(m.group("v1")) is not None:
            if not in_table:
                rows.append(["Name", "Security identifier", "Value (AUD)", "Weighting (%)"])
                in_table = True
            ident = m.group("id") or ""
            if ident.upper() in {"LP", "LLC", "LTD", "PLC", "INC", "CO", "SA", "NV", "AG", "PTY", "SE", "AB", "AS", "OYJ", "SPA", "BV", "KK", "CORP", "GROUP", "TRUST", "FUND", "REIT"}:
                rows.append([(m.group("name") + " " + ident).strip(" -—:"), "", m.group("v1"), m.group("v2")])
            else:
                rows.append([m.group("name").strip(" -—:"), ident, m.group("v1"), m.group("v2")])
        else:
            rows.append([line])
            if SECTION_HINTS.search(line) and len(line) < 80:
                in_table = False
    return pd.DataFrame(rows)


def _read_pdf(path: Path) -> list[tuple[str, pd.DataFrame]]:
    import pdfplumber
    out = []
    with pdfplumber.open(path) as pdf:
        texts = []
        for pno, page in enumerate(pdf.pages, 1):
            tables = [t for t in (page.extract_tables() or []) if t and len(t) > 2 and len(t[0]) >= 3]
            for t_i, table in enumerate(tables):
                out.append((f"p{pno}t{t_i}", pd.DataFrame(table)))
            texts.append(page.extract_text() or "")
        if not out:  # no ruled tables: fall back to text-line reconstruction across the whole document
            out.append(("ptext", _pdf_text_table("\n".join(texts))))
    return out


def read_raw(path: Path) -> list[tuple[str, pd.DataFrame]]:
    ext = path.suffix.lower()
    if ext in {".xlsx", ".xlsm", ".xls"}:
        sheets = pd.read_excel(path, sheet_name=None, header=None, dtype=object)
        return list(sheets.items())
    if ext in {".csv", ".txt"}:
        for enc in ("utf-8-sig", "latin-1"):
            try:
                return [("csv", pd.read_csv(path, header=None, dtype=object, encoding=enc, on_bad_lines="skip", engine="python"))]
            except Exception:  # noqa: BLE001
                continue
        return []
    if ext == ".pdf":
        return _read_pdf(path)
    return []


def option_from_filename(path: Path) -> str:
    stem = re.sub(r"^[0-9a-f]{10}_", "", path.stem)
    stem = re.sub(r"(phd|portfolio[-_ ]holdings?|holdings?[-_ ]disclosure|table\s*\d+|\d{1,2}[-_ ]?(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[-_ ]?\d{2,4}|\d{4}[-_]\d{2}[-_]\d{2}|\d{6,8})", " ", stem, flags=re.I)
    stem = re.sub(r"[-_\s]+", " ", stem).strip()
    return stem.title() if stem else path.stem


def parse_file(path: Path, option_hint: str | None = None) -> pd.DataFrame:
    """Parse one raw file into staging rows (may contain several options / sections)."""
    frames = []
    date_hint = find_date(path.name)
    opt = option_hint or option_from_filename(path)
    for sheet, df in read_raw(path):
        if df is None or df.empty:
            continue
        # multi-sheet workbooks often use one sheet per option
        sheet_opt = opt if len(frames) == 0 and sheet in {"csv", "Sheet1", 0} else (str(sheet) if isinstance(sheet, str) and not str(sheet).startswith("p") and not re.match(r"sheet ?\d", str(sheet), re.I) else opt)
        out = parse_frame(df, source_file=str(path), sheet=str(sheet), option_hint=sheet_opt or opt, date_hint=date_hint)
        if not out.empty:
            frames.append(out)
    if not frames:
        return pd.DataFrame(columns=STAGING_COLUMNS)
    return pd.concat(frames, ignore_index=True)
