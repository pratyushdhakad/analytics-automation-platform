"""Day 1 pipeline entry point."""

from pathlib import Path

from .ingestion import run_ingestion


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    manifest = run_ingestion(root)
    print(
        "Ingestion gate {gate}: {sources} sources, {rows} rows, run {run_id}".format(
            gate=manifest["publish_gate"],
            sources=manifest["source_count"],
            rows=manifest["total_rows"],
            run_id=manifest["run_id"],
        )
    )


if __name__ == "__main__":
    main()

