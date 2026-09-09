"""Generate synthetic Schedule 8D-style PHD files in the three layouts we meet in the wild.

Values are invented. They exist only to prove the parser, gates and site build work end to end.
Run:  python tests/make_fixtures.py   (writes tests/fixtures/<fund>/... and raw/2025-12-31/<fund>/...)
"""
from __future__ import annotations

import random
import shutil
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures"
random.seed(7)

AU_EQ = [("Commonwealth Bank of Australia", "AU000000CBA7"), ("BHP Group Ltd", "AU000000BHP4"), ("CSL Ltd", "AU000000CSL8"), ("National Australia Bank", "AU000000NAB4"),
         ("Westpac Banking Corp", "AU000000WBC1"), ("Macquarie Group", "AU000000MQG1"), ("Wesfarmers", "AU000000WES1"), ("Woodside Energy", "AU0000224040"),
         ("Fortescue", "AU000000FMG4"), ("Transurban Group", "AU000000TCL6"), ("Goodman Group", "AU000000GMG5"), ("Rio Tinto Ltd", "AU000000RIO1")]
INTL_EQ = [("NVIDIA CORP COMMON STOCK USD", "US67066G1040"), ("MICROSOFT CORP COMMON STOCK USD", "US5949181045"), ("APPLE INC COMMON STOCK USD", "US0378331005"),
           ("ALPHABET INC CLASS A", "US02079K3059"), ("AMAZON.COM INC", "US0231351067"), ("TAIWAN SEMICONDUCTOR MANUFACTURING", "TW0002330008"),
           ("NESTLE SA REG", "CH0038863350"), ("ASML HOLDING NV", "NL0010273215"), ("TOYOTA MOTOR CORP", "JP3633400001"), ("SAMSUNG ELECTRONICS CO LTD", "KR7005930003"),
           ("HSBC HOLDINGS PLC", "GB0005405286"), ("TENCENT HOLDINGS LTD", "KYG875721634"), ("NOVO NORDISK A/S", "DK0062498333"), ("SHELL PLC", "GB00BP6MXD84")]
FI = [("Commonwealth of Australia 3.00% 21/11/2033", "AU3TB0000200", "21/11/2033", 3.0), ("Treasury Corp of Victoria 4.25% 20/12/2032", "AU3SG0002199", "20/12/2032", 4.25),
      ("Queensland Treasury Corp 3.50% 21/08/2030", "AU3SG0001878", "21/08/2030", 3.5), ("NSW Treasury Corp 3.00% 20/02/2030", "AU3SG0001621", "20/02/2030", 3.0),
      ("Westpac Banking Corp FRN 2029", "AU3FN0071234", "15/05/2029", 5.1), ("United States Treasury 4.00% 15/02/2034", "US91282CJZ59", "15/02/2034", 4.0),
      ("Bundesrepublik Deutschland 2.30% 15/02/2033", "DE000BU2Z015", "15/02/2033", 2.3)]
CASH = [("Commonwealth Bank of Australia", "Cash"), ("Westpac Banking Corp", "Cash"), ("ANZ Banking Group", "Term deposit"), ("BNP Paribas SA (Australia)", "Cash")]
EXT = {"Unlisted infrastructure": [("IFM Investors Pty Ltd", 2.5e9), ("Macquarie Asset Management", 1.4e9), ("Global Infrastructure Partners", 0.9e9)],
       "Unlisted property": [("ISPT", 1.6e9), ("Charter Hall Funds Management Limited", 1.2e9), ("Dexus", 0.8e9)],
       "Private equity": [("StepStone Group", 1.1e9), ("Kohlberg Kravis Roberts & Co LP", 0.9e9), ("Blackbird Ventures Pty Limited", 0.4e9)],
       "Alternatives": [("Fermat Capital Management, LLC", 0.5e9), ("Tangency Capital Limited", 0.3e9)]}


def option_rows(aum: float, mix: dict[str, float]):
    """Return list of (section, subsection, name, sec_id, units, value, weight, maturity, coupon)."""
    rows = []

    def spread(names, total, sec, sub="", extra=None):
        w = [random.random() + 0.3 for _ in names]
        s = sum(w)
        for (n, i), wi in zip(names, w):
            v = round(total * wi / s, 2)
            rows.append((sec, sub, n, i, round(v / random.uniform(20, 400)), v, round(v / aum * 100, 4), *(extra(n) if extra else ("", ""))))
    spread(CASH, aum * mix["cash"], "Cash", "", lambda n: ("", ""))
    spread([(n, i) for n, i, _, _ in FI], aum * mix["fi"], "Fixed income", "Internally managed", lambda n: next(((m, c) for nn, _, m, c in FI if nn == n), ("", "")))
    rows.append(("Fixed income", "Externally managed", "PIMCO Australia Pty Ltd", "", None, round(aum * mix["fi_ext"], 2), round(mix["fi_ext"] * 100, 4), "", ""))
    rows.append(("Fixed income", "Externally managed", "Ardea", "", None, round(aum * mix["fi_ext"] * 0.6, 2), round(mix["fi_ext"] * 60, 4), "", ""))
    spread(AU_EQ, aum * mix["au_eq"], "Listed equity - Australian", "Internally managed")
    spread(INTL_EQ, aum * mix["intl_eq"], "Listed equity - International (unhedged)", "Internally managed")
    for sec, mgrs in EXT.items():
        tot = aum * mix.get(sec, 0)
        s = sum(v for _, v in mgrs)
        for n, v in mgrs:
            val = round(tot * v / s, 2)
            rows.append((sec, "Externally managed", n, "", None, val, round(val / aum * 100, 4), "", ""))
    total = sum(r[5] for r in rows)
    return [(*r[:6], round(r[5] / total * 100, 4), *r[7:]) for r in rows]


MIX_BAL = {"cash": 0.04, "fi": 0.09, "fi_ext": 0.03, "au_eq": 0.21, "intl_eq": 0.29, "Unlisted infrastructure": 0.10, "Unlisted property": 0.06, "Private equity": 0.05, "Alternatives": 0.02}
MIX_HG = {"cash": 0.01, "fi": 0.02, "fi_ext": 0.01, "au_eq": 0.29, "intl_eq": 0.44, "Unlisted infrastructure": 0.08, "Unlisted property": 0.04, "Private equity": 0.07, "Alternatives": 0.01}


def write_xlsx_multisheet(dest: Path):
    """Layout A (e.g. Aware/HESTA style): one workbook, one sheet per option, title rows then Schedule 8D tables."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(dest) as xw:
        for opt, aum, mix in (("Balanced", 48.2e9, MIX_BAL), ("High Growth", 9.7e9, MIX_HG)):
            lines = [[f"Example Super — Portfolio Holdings Disclosure"], [f"Investment option: {opt}"], ["Reporting date: 31 December 2025"], []]
            cur = None
            for sec, sub, n, i, u, v, w, m, c in option_rows(aum, mix):
                key = (sec, sub)
                if key != cur:
                    if cur is not None:
                        lines.append([])
                    lines.append([sec])
                    if sub:
                        lines.append([sub])
                    if sec == "Fixed income":
                        lines.append(["Name / kind of investment item", "Security identifier", "Units held", "Maturity date", "Coupon (%)", "Value (AUD)", "Weighting (%)"])
                    else:
                        lines.append(["Name / kind of investment item", "Security identifier", "Units held", "Value (AUD)", "Weighting (%)"])
                    cur = key
                if sec == "Fixed income":
                    lines.append([n, i, u, m, c, v, w])
                else:
                    lines.append([n, i, u, v, w])
            lines.append(["Total", "", "", aum, 100.0])
            pd.DataFrame(lines).to_excel(xw, sheet_name=opt, header=False, index=False)


def write_csv_per_option(dest_dir: Path):
    """Layout B (e.g. Cbus/Rest style): one CSV per option, flat table with an asset-class column."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    for opt, aum, mix in (("growth-mysuper", 61.0e9, MIX_BAL), ("conservative", 1.3e9, {**MIX_BAL, "cash": 0.20, "fi": 0.25, "fi_ext": 0.03, "au_eq": 0.10, "intl_eq": 0.12, "Unlisted infrastructure": 0.05, "Unlisted property": 0.04, "Private equity": 0.0, "Alternatives": 0.0}), ("high-growth", 8.1e9, MIX_HG)):
        recs = []
        for sec, sub, n, i, u, v, w, m, c in option_rows(aum, mix):
            recs.append({"Asset class": sec, "Management": sub, "Name of investment item": n, "ISIN/Ticker": i, "Units": u, "Market value $AUD": v, "Weighting %": w, "Currency": "AUD" if i.startswith("AU") or not i else i[:2]})
        pd.DataFrame(recs).to_csv(dest_dir / f"super-{opt}-31-december-2025.csv", index=False)


def write_pdf(dest: Path):
    """Layout C (e.g. Hostplus style): PDF with one table per asset class."""
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Table, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    dest.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(dest), pagesize=A4)
    story = [Paragraph("Example Industry Super — Investment holdings disclosure", styles["Title"]), Paragraph("Reporting date 31 December 2025 — Balanced option", styles["Normal"]), Spacer(1, 12)]
    aum = 5.4e9
    cur = None
    data = []
    for sec, sub, n, i, u, v, w, m, c in option_rows(aum, MIX_BAL):
        if (sec, sub) != cur:
            if data:
                story.append(Table(data))
                story.append(Spacer(1, 10))
            story.append(Paragraph(sec + (f" — {sub}" if sub else ""), styles["Heading3"]))
            data = [["Name", "Security ID", "Value (AUD)", "Weighting (%)"]]
            cur = (sec, sub)
        data.append([n[:38], i, f"{v:,.0f}", f"{w:.2f}"])
    story.append(Table(data))
    doc.build(story)


def main():
    if FIX.exists():
        shutil.rmtree(FIX)
    write_xlsx_multisheet(FIX / "examplesuper" / "PHD-31-December-2025.xlsx")
    write_csv_per_option(FIX / "examplecsv")
    try:
        write_pdf(FIX / "examplepdf" / "Investment-Holdings-Disclosure-Balanced.pdf")
    except ImportError:
        print("reportlab not installed; skipping PDF fixture")
    print("fixtures written to", FIX)


if __name__ == "__main__":
    main()
