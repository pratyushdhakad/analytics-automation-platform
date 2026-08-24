# CI and GitHub Pages deployment

Day 5 adds two automated workflows and a static executive dashboard. Both workflows run on GitHub-hosted infrastructure and require no repository secrets.

## Continuous integration

`.github/workflows/ci.yml` runs on pushes to `main`, pull requests, and manual dispatch. It:

1. checks out the repository;
2. installs Python 3.12;
3. runs the full automated test suite;
4. rebuilds all committed pipeline evidence;
5. fails if generated files differ from Git; and
6. validates the dashboard JavaScript syntax.

The `git diff --exit-code` step turns reproducibility into an enforced contract. A code or configuration change cannot silently leave stale forecast, scenario, or dashboard evidence in the repository.

## Dashboard generation

`make run` now writes `site/data/dashboard.json` after ingestion, metrics, forecasting, and scenario analysis pass. The dashboard reads only this generated contract. It does not call a live API, load a third-party chart library, or contain private data.

The site supports:

- 4-, 8-, and 13-week decision windows;
- net and shipped revenue views;
- base, upside, and downside daily trajectories;
- all seven scenario rankings and assumptions;
- champion model accuracy, bias, and interval coverage; and
- responsive desktop and mobile layouts.

## GitHub Pages

`.github/workflows/pages.yml` packages the `site/` directory and deploys it with GitHub's official Pages actions. The repository's Pages source must be set to **GitHub Actions** once. After that, any `main` change under `site/` or the Pages workflow triggers a deployment.

Expected public URL:

`https://pratyushdhakad.github.io/analytics-automation-platform/`

The workflow uses least-privilege permissions: read repository contents, write Pages, and mint the deployment identity token. It has one deployment concurrency group so a newer dashboard replaces an obsolete in-progress run.

## Local verification

```bash
make test
make run
node --check site/app.js
python3 -m http.server 8765 --directory site
```

Then open `http://127.0.0.1:8765/`. The committed dashboard has been checked at desktop and 390-pixel mobile widths.

## Production extension

For a live business system, the pipeline would run on a data orchestrator schedule, store point-in-time plans and forecast versions in a warehouse, and publish approved artifacts to object storage. GitHub Pages is appropriate here because the portfolio uses deterministic synthetic data and contains no authenticated operational controls.
