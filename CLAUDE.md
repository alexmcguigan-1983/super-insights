# Instructions for Claude Code working in this repository

You are maintaining a data pipeline that turns Australian superannuation funds' public Portfolio Holdings Disclosures
and APRA statistics into a dashboard. Read `docs/ARCHITECTURE.md` first, then `docs/DATA_DICTIONARY.md`.

## Rules
- Never modify anything under `raw/`. Never fabricate, estimate or "fill in" holdings, values or weights.
- Every change to parsing must come with a fixture in `tests/fixtures/<fund_id>/` and a test in `tests/`.
- Run `make test` before committing. Run `python -m pipeline.cli ingest --snapshot <s> --only <fund_id> --append`
  and then `python -m pipeline.cli build --snapshot <s>` to verify a fund end to end.
- Business judgement lives only in `config/*.csv` (asset-class patterns, manager aliases, fee assumptions, option types).
  Prefer adding a CSV row over adding code.
- If a fund cannot be parsed reliably, leave it quarantined and say why in `reports/repair_notes.md`. A quarantined
  fund is better than a wrong one.
- Fee figures for named managers are estimates and must stay labelled as such everywhere they appear.
- Do not change the ten buckets, the schema in `pipeline/__init__.py`, or the validation gates without a note in the PR.

## Common tasks
- A manager shows too little AUM in the league table: add its disclosed spellings to `config/managers.csv` (manager-level
  lines are matched by name only when the line is unlisted and has no ISIN/ticker), re-run `enrich` then `build`.
  Segregated listed mandates can never be attributed — they are disclosed as securities.
- A manager relationship is known from the press or an investor's manager list but invisible in PHD (segregated
  mandate, non-super investor): add a row to `config/manager_relationships.csv` with a source URL; it appears in the
  Manager League detail pane and keeps the manager in the league even with zero disclosed AUD.
- A fund's default option is not flagged: fix its pattern in `config/default_options.csv` (set verified=1 once checked
  against the PDS) and re-run `build`.
- Reclassify a hedge-fund strategy: edit strategy_family in `config/managers.csv` or add a keyword row to
  `config/alternatives_strategy_map.csv`, then `build`.
- Repair a fund after a refresh: open `reports/repair_<snapshot>.md` and follow its "How to repair" section.
- Add a fund: row in `config/sources.csv`, then harvest → ingest → (adapter if needed) → build.
- APRA column renamed: adjust `COLUMN_HINTS` in `pipeline/apra.py`.
- Update a fund's member profile or press themes: edit `config/build_fund_profiles.py` (every claim needs a source URL
  and date; mark heritage-based reasoning as "Inferred:"), run it, commit the regenerated `site/data/fund_profiles.json`.
- Update a sovereign fund / state insurer / life insurer entry: edit `config/build_asset_owners.py` (same rules), run it,
  commit `site/data/asset_owners.json`. NZ Super Fund's six-monthly Excel disclosure is the first candidate for real
  holdings ingestion outside super.
