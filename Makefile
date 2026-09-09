# Super Insights — common commands. Run `make help`.
SNAP ?=
ARGS := $(if $(SNAP),--snapshot $(SNAP),)

help:
	@echo "make setup      install Python dependencies (+ Playwright browser)"
	@echo "make test       run the test-suite on synthetic fixtures"
	@echo "make refresh    harvest -> apra -> ingest -> enrich -> build   (SNAP=2026-06-30 to force a date)"
	@echo "make harvest / apra / ingest / enrich / build   individual steps"
	@echo "make serve      open the dashboard locally at http://localhost:8000"
	@echo "make demo       build the dashboard from synthetic fixture funds (no internet needed)"

setup:
	pip install -r requirements.txt
	python -m playwright install chromium

test:
	python tests/make_fixtures.py
	python -m pytest -q tests

refresh: ; python -m pipeline.cli refresh $(ARGS)
harvest: ; python -m pipeline.cli harvest $(ARGS)
apra:    ; python -m pipeline.cli apra $(ARGS)
ingest:  ; python -m pipeline.cli ingest $(ARGS)
enrich:  ; python -m pipeline.cli enrich $(ARGS)
build:   ; python -m pipeline.cli build $(ARGS)

demo:
	python tests/make_fixtures.py
	python tests/stage_fixtures.py
	SOURCES_CSV=tests/sources_test.csv python -m pipeline.cli ingest --snapshot 2025-12-31-demo --only examplesuper,examplecsv,examplepdf
	python -m pipeline.cli enrich --snapshot 2025-12-31-demo --skip-openfigi
	python -m pipeline.cli build --snapshot 2025-12-31-demo

serve:
	cd site && python -m http.server 8000
