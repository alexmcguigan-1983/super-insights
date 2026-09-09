# Super Insights

Australian superannuation holdings analytics built entirely from public disclosures: what funds hold in their
equity and fixed income books, which managers run money for them, their strategic asset allocation, and what they pay.
Refreshes itself twice a year with a GitHub Actions agent.

**Start here: [docs/SETUP.md](docs/SETUP.md)** — the numbered checklist to get this running on your own GitHub account
without prior coding experience.

## What it does

| Step | What happens | Where |
|---|---|---|
| Harvest | Finds and downloads every fund's Portfolio Holdings Disclosure file (XLSX / CSV / PDF) from `config/sources.csv` | `pipeline/harvest.py` |
| APRA | Downloads the Quarterly Superannuation Product Statistics (strategic allocation, fees, product sizes), fund-level statistics and expense data | `pipeline/apra.py` |
| Parse | Reads Schedule 8D tables in any layout; fund-specific adapters override when needed | `pipeline/parse/` |
| Normalise | One canonical schema; 10 asset buckets; geography and manager resolution; weights recomputed | `pipeline/normalise.py` |
| Validate | Six gates; failures quarantined with reasons, never silently loaded | `pipeline/validate.py` |
| Enrich | OpenFIGI security master; manager alias table | `pipeline/enrich.py` |
| Fees | Disclosed option fees, disclosed fund expenses, *estimated* manager economics | `pipeline/fees.py` |
| Build | Aggregates to small JSON files + a DuckDB database | `pipeline/build.py` |
| Dashboard | Eleven-page static site (no server, no database) | `site/index.html` |
| Automation | Six-monthly refresh, QA pull request, repair issue / Claude agent, Pages deploy | `.github/workflows/` |

## Quick start (any computer with Python 3.11+)

```bash
make setup      # install dependencies
make test       # 10 tests on synthetic Schedule 8D files
make demo       # build the dashboard from synthetic funds, offline
make serve      # open http://localhost:8000
```

Real data: `make refresh` (needs internet access to the funds' websites and apra.gov.au).
Seed with the reference dataset: `python -m pipeline.cli import-reference super_holdings_dec2025.json apra_saa_dec2025.json`
then `python -m pipeline.cli build --snapshot 2025-12-31`.

## Layout

```
config/        sources.csv (fund registry) · asset_class_map.csv · option_type_map.csv · managers.csv · fee_schedule.csv
pipeline/      the Python package (see table above)
raw/           downloaded files per snapshot (not committed; kept as workflow artifacts)
curated/       holdings.parquet + apra_*.parquet per snapshot; super_insights.duckdb
quarantine/    options that failed validation, with reasons
reports/       qa_<snapshot>.md and repair_<snapshot>.md
site/          the dashboard (index.html + data/)
tests/         synthetic fixtures and the test-suite
docs/          SETUP.md · ARCHITECTURE.md · DATA_DICTIONARY.md
```

## Honesty about the data

* Holdings are trustee-disclosed under Corporations Regulations 2001 Schedule 8D as at 30 June / 31 December and are
  published up to 90 days later. Externally managed pooled sleeves are one line per manager; derivatives are aggregated.
* Strategic allocation is APRA's MySuper collection (Table 8a). Choice options are not covered by APRA at that granularity.
* **Fees paid to each named manager are not public.** The Fees page labels every manager-level number as an estimate.
* Every row carries `geography_method` and `data_quality_flag`; every snapshot carries source-file hashes and the pipeline version.

Not investment advice.
