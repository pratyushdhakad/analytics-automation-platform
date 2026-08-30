# From an Empty Repository to a Live Forecasting Product

This is the plain-English build journal for the Revenue Forecasting Control Tower. It explains what was done, why it was done, how Git and GitHub recorded the work, what CI and GitHub Pages do, and how to reproduce the project yourself.

It is written for someone who is new to GitHub. You do not need to understand forecasting, Python, or deployment before reading it.

## 1. What we built

The final product answers four connected questions:

1. Can we trust the source data?
2. Which forecasting method performs best on data it has not seen?
3. How could marketing, affiliate, promotion, and fulfillment plans change the result?
4. Is the forecast still healthy after it is published?

The repository contains the data contracts, synthetic source data, Python pipeline, automated tests, generated evidence, dashboard, CI workflows, and documentation needed to answer those questions.

The live result is the [Revenue Forecasting Control Tower](https://pratyushdhakad.github.io/analytics-automation-platform/).

## 2. Git and GitHub words you need first

### Repository

A repository, or “repo,” is the project folder plus its saved history. The local repository lives on your computer. The public repository lives on GitHub.

### Working tree

The working tree is the current set of files on your computer. Editing a file changes the working tree, but it does not yet create a saved Git checkpoint.

### Stage

Staging means choosing exactly which file changes should enter the next checkpoint.

```bash
git add README.md
```

This command stages `README.md`. It does not publish anything.

### Commit

A commit is a named checkpoint in the project history.

```bash
git commit -m "Explain the business problem"
```

The message should say what changed. A commit is still local until it is pushed or recreated on GitHub.

### Branch

A branch is a movable label pointing to a line of commits. `main` is the public production line for this project. Dated backup branches preserve earlier local histories before alignment.

### Remote and origin

A remote is another copy of the repository. By convention, the primary GitHub repository is named `origin`.

```bash
git remote -v
```

This shows where Git fetches from and pushes to.

### Push and fetch

`push` sends local commits to GitHub. `fetch` downloads GitHub history without changing your current files.

```bash
git push origin main
git fetch origin main
```

### Commit hash

A hash such as `59190c8` is Git’s short identifier for one commit. Clicking a commit on GitHub shows the exact files changed in that checkpoint.

## 3. Before writing code: define the decision

The first commit did not contain a forecasting model. It contained the business question.

The project was framed around a decision owner who needs to know:

- expected net and shipped revenue over 4, 8, and 13 weeks;
- whether the underlying data is trustworthy;
- how different operating plans change the forecast; and
- whether forecast performance has crossed a review threshold.

This matters because a technically impressive model without a clear decision is difficult to evaluate or explain.

The repository started with `README.md`, then added the minimum project foundation: `.gitignore`, `LICENSE`, and `Makefile`.

- `.gitignore` tells Git which local files not to publish.
- `LICENSE` explains how others may use the code.
- `Makefile` gives short commands such as `make test` and `make run`.

## 4. The real build history, one phase at a time

The tables below follow the public `main` branch. Each row is one visible GitHub commit.

### Day 1: make data trust visible

The first technical goal was not “build AI.” It was “refuse to publish bad data.”

| Commit | What happened in plain language |
|---|---|
| `11e7232` | Wrote the business problem in the README so the project had a decision before it had code. |
| `abe5e5d` | Added the license, ignore rules, and repeatable command file. |
| `f19b209` | Defined what columns, types, keys, allowed values, and freshness each source must have. |
| `a4175b4` | Added small deterministic sample files for orders, refunds, and advertising spend. “Deterministic” means the same input produces the same output every time. |
| `677715f` | Built the Python validation and ingestion engine. It checks data before publishing downstream files. |
| `308d8b9` | Added tests for missing columns, duplicates, invalid values, stale files, and broken relationships. |
| `3c78bb0` | Published normalized raw snapshots only after validation passed. |
| `9f31e18` | Published machine-readable evidence containing row counts, hashes, freshness, and the PASS/HOLD decision. |
| `945c2f9` | Documented the architecture and the boundary between a portfolio fixture and a production system. |

What you learn here: schemas, primary keys, data quality, reproducibility, tests, and why validation should block publication rather than merely create a warning.

### Day 2: turn source data into revenue metrics

The project then expanded from tiny fixtures to three years of synthetic revenue, marketing, affiliate, and shipment history.

| Commit | What happened in plain language |
|---|---|
| `5812d56` | Defined the revenue source contracts and governed metric meanings. |
| `e02610c` | Generated daily revenue, four marketing channels, and three affiliate partners across 1,096 days. |
| `132107c` | Built the history generator and daily metric transformation pipeline. |
| `4339355` | Published the validated source snapshots produced by that pipeline. |
| `bad0576` | Published reconciliation evidence proving that revenue, spend, affiliates, and shipment arithmetic agree. |
| `09ed385` | Published the forecast-ready daily revenue table, often called a mart. |
| `6b0e4c1` | Added a BigQuery SQL version of the governed revenue transformation. |
| `c81f463` | Tested history coverage, seasonality, reconciliations, and repeatability. |
| `7ad00ed` | Documented the revenue data design and limitations. |
| `49eed3c` | Updated the public story and commands to make revenue forecasting the central product. |

What you learn here: metric definitions, data modeling, reconciliation, BigQuery-style SQL, seasonal signals, marketing data, affiliate data, and booked-versus-shipped revenue.

### Day 3: build and evaluate forecasts

Two forecasting methods were compared instead of assuming the more complicated method would win.

| Commit | What happened in plain language |
|---|---|
| `2a19bee` | Defined forecast targets, horizons, candidate models, intervals, and evaluation rules in configuration. |
| `b089603` | Built the seasonal baseline, driver regression, rolling-origin backtests, champion selection, and future forecast pipeline. |
| `09a2866` | Added forecast commands and explained the new phase in the README. |
| `76836d3` | Published every backtest prediction, scorecard, future driver plan, daily forecast, and executive summary. |
| `64753a8` | Tested leakage protection, model selection, interval behavior, future-driver assumptions, and byte-for-byte reproduction. |
| `36f2d40` | Documented why different targets selected different models and where the evidence stops. |

“Rolling-origin” means pretending several past dates were “today,” training only on information available before each date, and measuring predictions against what happened afterward. This prevents the model from secretly learning from the future.

What you learn here: baselines, regression, train/test boundaries, leakage, WAPE, bias, MASE, prediction intervals, champion/challenger selection, and why complexity must earn promotion.

### Day 4: turn forecasts into operating scenarios

A forecast says what is expected under one plan. A scenario engine asks what changes when the plan changes.

| Commit | What happened in plain language |
|---|---|
| `ee39e4d` | Defined seven named operating scenarios in configuration. |
| `a070257` | Built the channel, promotion, affiliate, and fulfillment scenario engine. |
| `262f143` | Expanded the forecast evidence to retain paid-search, paid-social, retargeting, and email plans. |
| `7fc67f9` | Published daily scenario forecasts, a ranking table, and multi-horizon summaries. |
| `eed1072` | Tested scenario reconciliation, isolation, direction, capacity behavior, and reproducibility. |
| `b864480` | Documented what the scenarios mean and why they are not causal ROAS estimates. |
| `c60a0ba` | Connected scenario generation to the normal project commands and README. |

What you learn here: scenario contracts, controlled assumptions, sensitivity analysis, causal-versus-predictive claims, and how fulfillment capacity affects shipments without changing booked demand.

### Day 5: create the decision experience and automate delivery

The next goal was to make the evidence usable without asking a recruiter to read raw JSON and CSV files.

| Commit | What happened in plain language |
|---|---|
| `375962b` | Built one tested JSON contract containing everything the dashboard needs. |
| `504a07c` | Built the interactive HTML, CSS, JavaScript, and visual design. |
| `84a8c33` | Published the generated dashboard data contract. |
| `c6a4b9e` | Tested dashboard completeness, privacy, accessibility, local assets, and reproduction. |
| `9981905` | Added CI and GitHub Pages workflows. |
| `b19cbcf` | Added deployment instructions and an interview walkthrough. |
| `1a67f72` | Finished the public README, command flow, and decision experience. |

What you learn here: static web development, accessibility, responsive design, data contracts, deployment automation, and communicating technical evidence to a business audience.

### Day 6: monitor the forecast after publication

Publishing a forecast is not the end. A production-style workflow needs to detect when performance becomes unhealthy.

| Commit | What happened in plain language |
|---|---|
| `267b7a7` | Defined WATCH and CRITICAL thresholds for error, bias, and interval coverage. |
| `562dcce` | Built the monitoring calculation and connected it to the main pipeline and dashboard data. |
| `6a11ee5` | Added monitoring and dashboard contract tests. |
| `0d1f3a1` | Published the monitoring scorecard and operator-ready alert file. |
| `bd1da5b` | Added health cards and an automated alert feed to the dashboard. |
| `bf4e0d1` | Refreshed the generated dashboard evidence. |
| `5ecbe5a` | Added monitoring to the standard build command and README. |
| `59190c8` | Documented monitoring thresholds, response rules, limitations, and production extension. |

The current overall status is WATCH. Net revenue is healthy, but shipped revenue is systematically under-predicting actuals on the latest holdout. The project reports that uncomfortable result instead of weakening the threshold to make the dashboard green.

What you learn here: model monitoring, threshold contracts, signed bias, uncertainty coverage, alerts, human review, and the difference between replayed holdout evidence and live telemetry.

### Apprenticeship Day 1: preserve what each forecast originally said

The larger phase begins by making forecast history append-only. “Append-only” means the project may add a new forecast, but it may not quietly replace an older forecast while keeping the same identity.

Here is the change in the order it was built:

1. Wrote `config/vintages.json` to define the issue time, actual-availability delay, evaluation time, contract version, and model versions.
2. Added `vintages.py` to convert the six historical forecast origins and the current plan into seven stable forecast vintages.
3. Gave every forecast row a vintage ID, origin date, issue timestamp, forecast version, model, and model version.
4. Added an append-only check. Publishing identical content again is safe; changing an existing identity stops the pipeline.
5. Built an “as-of join.” This is a join that behaves as though the system clock were at one exact historical time.
6. Marked 1,092 historical predictions `OBSERVED` because their actuals were available by that time.
7. Kept 182 current future predictions `PENDING`, with blank actual and error values.
8. Added tests that inject a fake future actual, attempt to rewrite an existing vintage, remove a required model version, and reproduce every generated byte.
9. Connected `make vintages` to the normal build between forecasting and scenarios.
10. Published a manifest with counts, origin dates, integrity decisions, and hashes of every source file.

The important lesson is that preventing leakage requires more than removing the target column from a model. The data system must also know when an actual became available and refuse to use it before that timestamp.

The detailed technical and production explanation is in [Immutable Forecast Vintages](forecast-vintages.md).

## 5. What happens when you run the project

Start with:

```bash
make test
make run
```

### `make test`

This discovers and runs 59 automated tests. A test is a small question with an exact expected answer, for example:

- Does a duplicate order fail validation?
- Does a forecast avoid reading the future target value?
- Does a future actual remain hidden until its availability time?
- Does the pipeline reject an attempt to rewrite a published vintage?
- Does the base scenario equal the champion forecast?
- Does capacity relief change shipments without changing booked revenue?
- Does the dashboard contain the monitoring alert?
- Are generated files identical when the pipeline runs twice?

When all tests pass, the command exits successfully. A failure prints the test name and the mismatch.

### `make run`

This executes the complete dependency chain:

```text
Generate history
→ validate and ingest sources
→ build governed metrics
→ backtest and forecast
→ calculate scenarios
→ evaluate monitoring thresholds
→ build dashboard data
```

Each later step depends on evidence from earlier steps. The dashboard cannot quietly skip the data-quality gate.

## 6. What CI means

CI stands for continuous integration. In this repository, CI is a GitHub Actions workflow stored in `.github/workflows/ci.yml`.

GitHub reads that file after a push to `main` and starts a clean temporary computer. The workflow then:

1. downloads the repository with `actions/checkout`;
2. installs the specified Python version;
3. runs all tests;
4. rebuilds every generated artifact with `make run`;
5. runs `git diff --exit-code` to prove the committed artifacts were not stale; and
6. checks the dashboard JavaScript syntax.

If every step succeeds, GitHub shows a green check. If one step fails, GitHub shows a red X and preserves the logs.

CI does not prove that every business assumption is correct. It proves that the declared automated checks pass in a fresh environment and that the repository can reproduce its own published evidence.

### Why some historical CI runs are red

Some public files were uploaded through GitHub’s browser interface because terminal push credentials were not configured. GitHub can upload only one directory group at a time, so a temporary commit sometimes contained one half of a cross-directory change. For example, a dashboard commit could arrive before its new generated data file.

CI correctly failed those incomplete intermediate states. After every required directory was present, the final CI run passed. The red runs are visible history, not hidden mistakes, and the latest `main` branch is green.

## 7. What GitHub Pages means

GitHub Pages hosts static website files from a repository. The workflow in `.github/workflows/pages.yml` packages the `site/` directory and deploys it to:

`https://pratyushdhakad.github.io/analytics-automation-platform/`

The browser loads:

- `site/index.html` for structure;
- `site/styles.css` for visual design;
- `site/app.js` for interactions; and
- `site/data/dashboard.json` for tested forecast evidence.

There is no server or database behind the public page. This keeps the portfolio demo simple, inexpensive, and reproducible. A production version would add authentication, a scheduled data platform, and governed operational write controls.

## 8. The exact Git routine used for a normal change

### Step 1: inspect the repository

```bash
git status --short --branch
```

This shows the current branch and changed files. Read it before editing so you do not overwrite someone else’s work.

### Step 2: make one focused change

Edit only the files needed for the goal. Avoid unrelated cleanup in the same commit.

### Step 3: inspect the difference

```bash
git diff
git diff --check
```

The first command shows changed lines. The second catches whitespace problems.

### Step 4: run verification

```bash
make test
make run
node --check site/app.js
```

Use only the checks relevant to the change, then run the complete gate before publication.

### Step 5: stage files

```bash
git add path/to/file1 path/to/file2
```

Stage an intentional group. Check it with:

```bash
git diff --cached
```

### Step 6: create a commit

```bash
git commit -m "Describe the completed outcome"
```

A good message is short and specific. “Build monitoring feedback loop” is more useful than “updates.”

### Step 7: publish

```bash
git push origin main
```

When command-line authentication is unavailable, the same files can be uploaded through GitHub’s interface. This creates public commits but may produce different commit hashes from the original local checkpoints.

### Step 8: verify GitHub

Check the latest commit, the Actions page, and the live Pages URL. A local test is necessary but not sufficient; publication must also be verified where users will see it.

### Step 9: compare local and public content

```bash
git fetch origin main
git rev-parse HEAD^{tree}
git rev-parse origin/main^{tree}
```

The commit histories can differ when browser uploads recreate commits. Matching tree hashes prove the final file content is identical.

Before aligning histories, preserve the original local commits:

```bash
git branch local-day6-draft-20260825 HEAD
git reset --soft origin/main
```

The backup branch keeps the original local history. The soft reset moves `main` to the public commit without discarding file content.

## 9. How AI and the human divided the work

AI accelerated implementation, test generation, edge-case discovery, documentation, browser checks, and repetitive publication work.

The human-owned decisions remained:

- which business question mattered;
- which claims were acceptable;
- where predictive evidence stopped;
- what counted as success;
- whether a model deserved promotion;
- whether an alert should remain visible; and
- what was published under the owner’s name.

Using AI well does not mean hiding AI. It means making the instructions, verification, tradeoffs, and ownership visible.

## 10. Using the Karpathy-inspired guidelines to learn while building

The next phase will use the four behaviors in [`multica-ai/andrej-karpathy-skills`](https://github.com/multica-ai/andrej-karpathy-skills) as a working discipline. The relevant source is its [`karpathy-guidelines` skill](https://github.com/multica-ai/andrej-karpathy-skills/blob/main/skills/karpathy-guidelines/SKILL.md).

### Think before coding

Before each feature, write:

- the business decision;
- assumptions;
- what is unclear;
- at least one simpler alternative; and
- the boundary of what will not be built.

Learning benefit: you practice problem framing rather than only accepting generated code.

### Simplicity first

Build the smallest version that proves the decision. Do not add frameworks, services, or abstractions merely because they look advanced.

Learning benefit: you can explain every moving part and identify when additional complexity earns its cost.

### Surgical changes

Keep each commit focused on one outcome. Every changed line should connect to the stated goal. Mention unrelated improvements instead of silently mixing them into the work.

Learning benefit: `git diff` becomes readable, reviews become easier, and mistakes are simpler to reverse.

### Goal-driven execution

Translate each task into a measurable success contract.

Example:

```text
Goal: retain immutable forecast vintages.
Success criteria:
1. Two runs with different origin dates remain queryable.
2. Actuals join only after their forecast was issued.
3. Tests fail when a future actual leaks into a vintage.
4. The beginner journal explains the new files and commit.
```

Learning benefit: you learn by predicting what “done” means, then comparing that prediction with test and CI evidence.

## 11. The bigger next phase: Forecast Operations Apprenticeship

The next phase should deepen the same product instead of adding random features. Each week combines one production capability with one learning outcome.

### Week 1: immutable forecast vintages

Build:

- versioned forecast runs with origin date, model version, horizon, and issue timestamp;
- an as-of join between forecasts and later actuals; and
- leakage tests for vintage integrity.

Learn: slowly changing data, point-in-time correctness, data lineage, and why production forecasts must be reproducible after the fact.

### Week 2: champion/challenger registry

Build:

- a small model registry;
- explicit candidate, approved, rejected, and retired states;
- promotion rules based on out-of-sample metrics; and
- a human approval record.

Learn: model governance, state machines, audit trails, and why automatic retraining should not automatically mean automatic promotion.

### Week 3: scheduled forecast operations

Build:

- a scheduled GitHub Actions workflow;
- a dry-run mode using deterministic fixtures;
- alert deduplication and acknowledgement records; and
- a generated weekly executive briefing.

Learn: orchestration, idempotency, retries, alert fatigue, and the difference between a job running and a decision being safely delivered.

### Week 4: warehouse and BI production translation

Build:

- BigQuery-ready tables for vintages, actuals, model registry, monitoring, and alerts;
- SQL reconciliation checks;
- a Looker-style semantic layer specification; and
- an architecture decision record comparing the portfolio implementation with the proposed production stack.

Learn: warehouse modeling, BI semantics, production tradeoffs, cost, access control, and how to translate a local Python project into the tools used by analytics teams.

## 12. The learning checkpoint for every future commit

Before a commit is accepted, answer these questions in plain language:

1. What problem did I solve?
2. What assumption did I make?
3. Which files changed, and why?
4. What test would fail if the change broke?
5. What did the command-line output prove?
6. What did CI prove after the push?
7. What can this project still not claim?

The point is not to memorize commands. The point is to connect the business decision, code change, test evidence, Git history, and public result into one explainable chain.
