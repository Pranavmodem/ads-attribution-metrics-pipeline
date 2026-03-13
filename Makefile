.PHONY: setup generate-data pipeline test quality lint clean

setup:
	python -m venv venv && source venv/bin/activate && pip install -r requirements.txt

generate-data:
	python src/utils/data_generator.py --output data/raw/ --days 90

pipeline: generate-data
	python src/ingestion/impression_loader.py
	python src/ingestion/conversion_loader.py
	python src/transform/attribution_transform.py
	cd models && dbt run --profiles-dir ../
	@echo "Pipeline complete. Check BigQuery marts for results."

test:
	pytest tests/ -v --tb=short

quality:
	cd models && dbt test --profiles-dir ../
	python src/utils/quality_checks.py

lint:
	ruff check src/ tests/
	ruff format --check src/ tests/

clean:
	rm -rf data/raw/*.parquet data/processed/* target/ dbt_packages/ __pycache__
