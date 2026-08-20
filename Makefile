.PHONY: ingest run test

ingest:
	PYTHONPATH=src python3 -m analytics_automation_platform.pipeline

run: ingest

test:
	PYTHONPATH=src python3 -m unittest discover -s tests -v

