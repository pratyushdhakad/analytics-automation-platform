.PHONY: generate ingest metrics run test

generate:
	PYTHONPATH=src python3 -m analytics_automation_platform.history

ingest: generate
	PYTHONPATH=src python3 -m analytics_automation_platform.ingestion

metrics: ingest
	PYTHONPATH=src python3 -m analytics_automation_platform.metrics

run:
	PYTHONPATH=src python3 -m analytics_automation_platform.pipeline

test:
	PYTHONPATH=src python3 -m unittest discover -s tests -v
