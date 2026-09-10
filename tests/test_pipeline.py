"""End-to-end tests on synthetic Schedule 8D fixtures. Run: make test"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from pipeline.normalise import classify_asset, infer_geography, normalise, option_type_for, resolve_manager, split_identifier  # noqa: E402
from pipeline.parse.generic import find_date, parse_file  # noqa: E402
from pipeline.validate import run_gates  # noqa: E402
from pipeline.registry import latest_reporting_date  # noqa: E402
import datetime as dt  # noqa: E402

FIX = ROOT / "tests" / "fixtures"


@pytest.fixture(scope="session", autouse=True)
def fixtures():
    if not (FIX / "examplesuper").exists():
        subprocess.run([sys.executable, "tests/make_fixtures.py"], check=True)


def test_parse_multisheet_xlsx():
    df = parse_file(FIX / "examplesuper" / "PHD-31-December-2025.xlsx")
    assert set(df["option_name"]) == {"Balanced", "High Growth"}
    assert len(df) == 100
    assert (df["reporting_date"] == dt.date(2025, 12, 31)).all()
    fi = df[df["section"].str.contains("Fixed income") & df["maturity"].astype(str).str.len().gt(0)]
    assert len(fi) == 14 and fi["coupon"].notna().all()
    assert df["value"].sum() > 5e10


def test_parse_flat_csv_uses_asset_class_column():
    df = parse_file(FIX / "examplecsv" / "super-growth-mysuper-31-december-2025.csv")
    assert len(df) == 50
    assert "Unlisted infrastructure" in set(df["section"])
    assert "Externally managed" in set(df["subsection"])
    assert df["reporting_date"].iloc[0] == dt.date(2025, 12, 31)  # from the file name


def test_parse_pdf_text_fallback():
    df = parse_file(FIX / "examplepdf" / "Investment-Holdings-Disclosure-Balanced.pdf")
    assert len(df) == 50
    assert df["value"].sum() > 4e9
    assert {"Cash", "Fixed income", "Private equity"} <= set(df["section"])


def test_classification_and_buckets():
    assert classify_asset("Listed equity - Australian")[1] == "Australian Equity"
    assert classify_asset("Listed equity - International (unhedged)")[1] == "International Equity"
    assert classify_asset("Unlisted infrastructure")[0] == "Australian Unlisted Infrastructure"
    assert classify_asset("Listed infrastructure")[2] == 1
    assert classify_asset("Private credit")[0] == "Private Credit"
    assert classify_asset("", "", "Nvidia Corp")[1] == "Other"


def test_identifiers_geography_managers():
    assert split_identifier("US67066G1040") == ("US67066G1040", "", "")
    assert split_identifier("BHP AU") == ("", "", "BHP AU")
    g, m = infer_geography(pd.Series({"holding_name": "NVIDIA CORP COMMON STOCK USD", "isin": "", "apra_asset_class": "International Equity Unhedged"}))
    assert g == "United States" and m == "name_marker_currency"
    g, m = infer_geography(pd.Series({"holding_name": "X", "isin": "JP3633400001", "apra_asset_class": "International Equity"}))
    assert g == "Japan" and m == "isin_prefix"
    assert resolve_manager("IFM Investors Pty Ltd") == "IFM"
    assert resolve_manager("Fermat Capital Management, LLC") == "FERMAT"
    assert option_type_for("Growth (MySuper)") == "Default"
    assert option_type_for("High Growth") == "High Growth"


def test_normalise_recomputes_weights_and_flags():
    df = parse_file(FIX / "examplesuper" / "PHD-31-December-2025.xlsx")
    h = normalise(df, fund_id="examplesuper", fund_name="Example Super", rse_abn="", snapshot_date="2025-12-31-demo")
    for _, g in h.groupby("option_name"):
        assert abs(g["weight_pct_calc"].sum() - 100) < 0.01
    assert (h.loc[h["management_type"] == "External-pooled", "manager_name_raw"] != "").all()
    assert h["data_quality_flag"].str.len().gt(0).all()
    assert "Australia" in set(h["geography"]) and "United States" in set(h["geography"])


def test_gates_catch_partial_parse_and_bad_weights():
    df = parse_file(FIX / "examplesuper" / "PHD-31-December-2025.xlsx")
    h = normalise(df, fund_id="examplesuper", fund_name="Example Super", rse_abn="", snapshot_date="2025-12-31-demo")
    ok = run_gates(h, snapshot="2025-12-31-demo")
    assert all(r.passed for r in ok)
    bad = h.copy()
    bad.loc[bad["option_name"] == "Balanced", "weight_pct_disclosed"] *= 1.3
    res = run_gates(bad, snapshot="2025-12-31-demo")
    assert any("G1" in " ".join(r.reasons) for r in res if r.option_name == "Balanced")
    tiny = h[h["option_name"] == "Balanced"].head(5)
    res = run_gates(tiny, snapshot="2025-12-31-demo")
    assert any("G5" in " ".join(r.reasons) for r in res)


def test_find_date_prefers_phd_dates():
    assert find_date("Maturity 15/02/2034 as at 31 December 2025") == dt.date(2025, 12, 31)
    assert find_date("PHD-June-2026-Super-Balanced.xlsx") == dt.date(2026, 6, 30)


def test_reporting_window():
    assert latest_reporting_date(dt.date(2026, 9, 8)) == dt.date(2025, 12, 31)  # 30 June window (90 days) has not closed yet
    assert latest_reporting_date(dt.date(2026, 10, 5)) == dt.date(2026, 6, 30)
    assert latest_reporting_date(dt.date(2026, 4, 5)) == dt.date(2025, 12, 31)


def test_full_build(tmp_path):
    subprocess.run([sys.executable, "tests/stage_fixtures.py"], check=True)
    env = {**os.environ, "SOURCES_CSV": "tests/sources_test.csv"}
    subprocess.run([sys.executable, "-m", "pipeline.cli", "ingest", "--snapshot", "2025-12-31-demo", "--only", "examplesuper,examplecsv,examplepdf"], check=True, env=env)
    subprocess.run([sys.executable, "-m", "pipeline.cli", "enrich", "--snapshot", "2025-12-31-demo", "--skip-openfigi"], check=True)
    subprocess.run([sys.executable, "-m", "pipeline.cli", "build", "--snapshot", "2025-12-31-demo"], check=True)
    s = json.loads((ROOT / "site/data/2025-12-31-demo/summary.json").read_text())
    assert s["options"] == 6 and s["funds"] == 3
    assert abs(sum(s["alloc"].values()) - 100) < 0.5
    opts = json.loads((ROOT / "site/data/2025-12-31-demo/options.json").read_text())
    assert all("peer_delta" in o for o in opts)
    mg = json.loads((ROOT / "site/data/2025-12-31-demo/managers.json").read_text())
    assert mg["league"][0]["manager"] == "IFM Investors"
