# Data dictionary — `curated/<snapshot>/holdings.parquet`

| Column | Type | Meaning |
|---|---|---|
| holding_id | text | Stable hash of (snapshot, fund, option, section, name, id, value, row) |
| snapshot_date | date | PHD reporting day this snapshot represents (30 June / 31 December) |
| fund_id | text | Registry key from `config/sources.csv` |
| fund_name | text | Fund display name |
| rse_abn | text | Registrable Superannuation Entity ABN (filled from APRA Product Structure when matched) |
| option_name | text | Investment option as named in the disclosure |
| option_id | text | APRA product/option identifier when matched |
| option_type | text | Default · Balanced · Growth · High Growth · Conservative · Sustainable · Indexed · Cash · Single Sector · Pension · Other (`config/option_type_map.csv`) |
| is_default | int | 1 when the option is the MySuper default |
| reporting_date | date | Date found in the file (or the snapshot date if absent) |
| source_table | text | Schedule 8D section heading the row sat under, verbatim |
| apra_asset_class | text | APRA vocabulary class (e.g. International Equity Unhedged, Australian Unlisted Property, Private Credit) |
| bucket | text | One of the ten display buckets |
| management_type | text | Internal · External-pooled · External-segregated · Unknown |
| manager_name_raw | text | Manager name as disclosed (externally managed lines) |
| manager_id | text | Resolved manager key from `config/managers.csv` |
| holding_name_raw / holding_name | text | Name as disclosed / after security-master enrichment |
| security_id_raw | text | Identifier exactly as disclosed |
| isin / sedol / ticker | text | Parsed identifiers |
| units, face_value, coupon, maturity_date | numeric/date | Fixed-income and unit fields where disclosed |
| currency | text | ISO code where disclosed |
| market_value_aud | numeric | Value in AUD as disclosed |
| weight_pct_disclosed | numeric | Weight printed in the file (validation only) |
| weight_pct_calc | numeric | value ÷ option total × 100, always recomputed |
| is_listed | int | 1 for listed securities |
| geography | text | Country/region |
| geography_method | text | disclosed · isin_prefix · name_marker_adr · name_marker_currency · asset_class_default · name_hint · currency_column · unknown · reference |
| gics_sector | text | Sector where disclosed or from the security master |
| hedge_status | text | Hedged · Unhedged · Domestic |
| data_quality_flag | text | "Clean" or a semicolon-separated list of inferences/issues; "REFERENCE: …" for imported rows |
| source_file / source_file_hash | text | Raw file path and SHA-256 |
| pipeline_version | text | Version of this pipeline (or `reference-import`) |

## APRA tables (`curated/<snapshot>/apra_*.parquet`)

* **apra_saa** — fund_name, product, stage, asset_class (APRA granular), target, lower, upper, bucket, assets, accounts
* **apra_fees** — fund_name, product, stage, admin_fee, inv_fee, txn_cost, total_fee (MySuper representative member)
* **apra_products** — fund_name, product, stage/option, assets (every option; used for size validation)
* **apra_fund_level** — fund_name, assets (whole-of-fund)
* **apra_expenses** — fund_name, expense_type, amount, is_investment (SRS 332.0)

## Config files

* `sources.csv` — fund registry; `phd_landing_url` is where discovery starts; `verified` flips to `yes` once a run has succeeded.
* `asset_class_map.csv` — regex → APRA class → bucket → is_listed, priority-ordered (lower runs first).
* `option_type_map.csv` — regex → option type.
* `managers.csv` — alias → manager_id, canonical name, parent, HQ, strategy family, related_party_of.
* `fee_schedule.csv` — bucket × management type × strategy family → fee range in bps (the estimate assumptions).
