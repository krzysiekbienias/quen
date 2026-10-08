
# quen

Portfolio analytics in modern Python: mean-variance optimisation, efficient frontiers,
risk and performance metrics, on real market data.

> *Quen*: the Witcher's protective sign. Risk management is the portfolio's shield.

## Architecture

One rule above all: **data access, business validation and models never mix.**
Models know nothing about where their data came from.

```
pipeline           orchestration: source -> validate -> model -> result   (planned)
models · risk ·    pure quantitative code on canonical domain objects
analytics
validation         business rules: raw records -> clean, canonical panels
ingestion          read-only access to raw market data (SQLite)
domain             canonical data model (frozen dataclasses)
core               errors, shared infrastructure
```

The layering is enforced as code: `import-linter` contracts in `pyproject.toml` fail the
build if, for example, a model imports a data source.

### What exists today

| Layer                   | Highlights                                                                                                                                                                 |
| ----------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ingestion`           | `MarketDataSource` protocol; `SqliteMarketDataSource` opens the database with `mode=ro`, short-lived connections, `busy_timeout`                                   |
| `domain`              | `PricePanel` / `ReturnPanel` with invariants (sorted unique dates, no gaps, positive prices); simple and log returns                                                   |
| `validation`          | pluggable`ValidationRule`s (positive prices, stale series, internal gaps), common window, pluggable `MissingDataPolicy`, `ValidationReport` with errors and warnings |
| `models.estimation`   | `MomentEstimator`: historical mean and sample covariance behind interfaces, annualised                                                                                   |
| `models.optimization` | `PortfolioOptimizer` interface; `ClosedFormMeanVariance`: Lagrangian closed form, Cholesky solves instead of explicit inverses, GMV and efficient frontier             |

Tests check the theory, not just the code: return identities, GMV (m = B/A, sigma^2 = 1/A),
the hyperbolic frontier, the two-fund theorem, and optimality against random portfolios
(property-based, Hypothesis).

## Quick start

```bash
uv sync
echo 'QUEN_DB_PATH=/path/to/market-data.sqlite' > .env
make help
```

| Command           | What it does                                                                     |
| ----------------- | -------------------------------------------------------------------------------- |
| `make check`    | format, lint, strict types, layer contracts, unit tests: run before every commit |
| `make ci`       | the same checks without modifying files (used by GitHub Actions)                 |
| `make test-int` | integration tests against the real database (needs`.env`)                      |
| `make explore`  | peek at the raw data and the validation report                                   |
| `make frontier` | closed-form efficient frontier on real data; writes`reports/frontier.png`      |

## Tooling

uv · ruff · mypy (strict) · pytest + Hypothesis · import-linter · GitHub Actions

## Roadmap

| Phase | Scope                                                                                 | Status                |
| ----- | ------------------------------------------------------------------------------------- | --------------------- |
| 0     | Project scaffold, tooling, layer contracts                                            | done                  |
| 1     | `core`: YAML config, logging                                                        | partial (errors only) |
| 2     | `ingestion`: read-only SQLite source                                                | done                  |
| 3     | `domain` + `validation`                                                           | done                  |
| 4     | `models`: moments, closed-form frontier                                             | done                  |
| 4b    | long-only frontier (CVXPY), Ledoit–Wolf shrinkage                                    | next                  |
| 5     | `analytics` + `risk`: Sharpe, Sortino, drawdown, VaR, ES, beta, tracking error    |                       |
| 6     | `models.factors`: CAPM regression with significance                                 |                       |
| 7     | `pipeline` + CLI + reporting                                                        |                       |
| later | max Sharpe / CML, risk parity, rebalancing backtest, multi-currency, Django front end |                       |
