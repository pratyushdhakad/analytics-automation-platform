.PHONY: generate ingest metrics forecast scenarios monitor dashboard run test

generate:
	PYTHONPATH=src python3 -m analytics_automation_platform.history

ingest: generate
	PYTHONPATH=src python3 -m analytics_automation_platform.ingestion

metrics: ingest
	PYTHONPATH=src python3 -m analytics_automation_platform.metrics

forecast: metrics
	PYTHONPATH=src python3 -m analytics_automation_platform.forecast_pipeline

scenarios: forecast
	PYTHONPATH=src python3 -m analytics_automation_platform.scenario_pipeline

monitor: scenarios
	PYTHONPATH=src python3 -m analytics_automation_platform.monitoring

dashboard: monitor
	PYTHONPATH=src python3 -m analytics_automation_platform.dashboard

run:
	PYTHONPATH=src python3 -m analytics_automation_platform.pipeline

test:
	PYTHONPATH=src python3 -m unittest discover -s tests -v
