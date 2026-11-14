# Run `make pipeline` for the whole thing: generate -> ingest -> quality gate -> dbt build -> export.

VENV    ?= .venv
PYTHON  ?= $(if $(wildcard $(VENV)/bin/python),$(VENV)/bin/python,python3)
DBT     ?= $(if $(wildcard $(VENV)/bin/dbt),$(VENV)/bin/dbt,dbt)
RUFF    ?= $(if $(wildcard $(VENV)/bin/ruff),$(VENV)/bin/ruff,ruff)
DAYS    ?= 90
VOLUME  ?= 2000
SEED    ?= 42

export PYTHONPATH := $(CURDIR)

.PHONY: setup pipeline data ingest quality transform export serve test lint clean

setup:            ## create .venv and install everything
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install -q -r requirements.txt -r requirements-dev.txt

pipeline: clean   ## run every stage in order on fresh data
	$(MAKE) data
	$(MAKE) ingest
	$(MAKE) quality
	$(MAKE) transform
	$(MAKE) export

data:             ## simulate the upstream exports into data/raw
	$(PYTHON) -m src.utils.data_generator --out data/raw --days $(DAYS) --daily-volume $(VOLUME) --seed $(SEED)

ingest:           ## land data/raw in the lake as date partitions
	$(PYTHON) -m src.ingestion

quality:          ## fail if any error-level check fails
	$(PYTHON) -m src.utils.quality_checks

transform:        ## build and test every dbt model (DuckDB)
	$(DBT) build --project-dir . --profiles-dir .

export:           ## write the dashboard's data file from the marts
	$(PYTHON) -m src.export

serve:            ## open the dashboard at http://localhost:8000
	$(PYTHON) -m http.server 8000 --directory docs

test:
	$(PYTHON) -m pytest

lint:
	$(RUFF) check src tests dags

clean:            ## remove generated data, lake, and warehouse (keeps docs/data)
	rm -rf data/raw/*.parquet data/lake data/quality data/warehouse.duckdb data/warehouse.duckdb.wal target logs
