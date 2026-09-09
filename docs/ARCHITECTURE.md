# Architecture

## Flow

```
config/sources.csv ──► harvest.py ──► raw/<snapshot>/<fund>/*.xlsx|csv|pdf  + manifest.json (url, sha256)
                                          │
apra.py ──► raw/<snapshot>/apra/*.xlsx    │  parse/generic.py (+ parse/adapters)  ──► staging rows
     │                                    ▼
     │                               normalise.py ──► canonical holdings (HOLDING_COLUMNS)
     │                                    │
     │                               validate.py ──► gates G1–G6 ──► curated/<snapshot>/holdings.parquet
     │                                    │                      └─► quarantine/<snapshot>/ (reasons.json)
     ▼                                    ▼
curated/<snapshot>/apra_*.parquet    enrich.py (OpenFIGI, managers.csv)
                       │                  │
                       └────────► build.py (+ fees.py) ──► site/data/<snapshot>/*.json, index.json, timeseries.json
                                                       └─► curated/super_insights.duckdb
                                              site/index.html reads the JSON — no server, no database
```

## Design rules the code follows

1. **Raw is immutable.** Files under `raw/` are never edited. Every curated row carries `source_file` and `source_file_hash`.
2. **Parse, then classify.** Parsers only extract (name, id, value, weight, section text). Classification into APRA
   classes and the ten buckets happens once, in `normalise.py`, driven by `config/asset_class_map.csv` (regex, priority-ordered).
3. **Recompute, don't trust.** `weight_pct_calc` is always value ÷ option total. The disclosed weight is kept only for gate G1.
4. **Fail loudly, load nothing partial.** An option either passes all gates or goes to quarantine with reasons. There is no
   "Listed Equities (aggregate)" escape hatch.
5. **Provenance on every row.** `geography_method`, `data_quality_flag`, `management_type` say how each value was determined.
6. **Estimates are labelled.** Manager-level fees carry `basis = "ESTIMATE: ..."` and the dashboard shows an amber pill.
7. **Small JSON for the browser.** The site never loads the full holdings table; per-fund holdings files are loaded on demand.
8. **Snapshots are dates.** `<snapshot>` = the PHD reporting day (`2026-06-30`). Anything containing `demo` is synthetic and
   is hidden once a real snapshot exists.

## Adding a fund

Add a row to `config/sources.csv` (fund_id, name, landing page, expected format). Run
`python -m pipeline.cli harvest --only <fund_id>` then `ingest --only <fund_id> --append`. If the generic parser
returns nothing or the option is quarantined, write an adapter (see `pipeline/parse/adapters/__init__.py`) with a fixture and a test.

## Adding a manager alias, asset-class pattern or fee assumption

All three are CSV files in `config/`. They are the only places business judgement lives; everything else is mechanical.

## Where the agent fits

`refresh.yml` runs the pipeline on GitHub's runners (which have internet access). If anything fails it writes
`reports/repair_<snapshot>.md` — raw-file previews plus explicit instructions — and opens an issue. With
`ANTHROPIC_API_KEY` set, the `repair` job runs Claude Code against that report on the refresh branch; its changes
arrive as commits for review. `ci.yml` runs the test-suite on every pull request so a repair cannot silently break
an adapter that used to work. `deploy.yml` publishes `site/` to GitHub Pages on every merge to `main`.

## Local analysis

`curated/super_insights.duckdb` exposes views `holdings`, `apra_saa`, `apra_fees`, `apra_products`, `apra_fund_level`,
`apra_expenses` across all snapshots:

```sql
SELECT snapshot_date, manager_id, bucket, SUM(market_value_aud)/1e9 AS bn
FROM holdings WHERE management_type = 'External-pooled'
GROUP BY 1,2,3 ORDER BY bn DESC;
```
