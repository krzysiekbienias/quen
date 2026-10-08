"""Closed-form efficient frontier (short selling allowed) on the validated equity universe.

make frontier           (reads QUEN_DB_PATH from .env; writes reports/frontier.png)
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import PercentFormatter

from quen.core.errors import QuenError
from quen.ingestion import SqliteMarketDataSource
from quen.models.estimation import MomentEstimator
from quen.models.optimization import ClosedFormMeanVariance
from quen.validation import PriceValidator

REPORT = Path("reports/frontier.png")


def main() -> int:
    db_path = os.environ.get("QUEN_DB_PATH")
    if not db_path:
        print("QUEN_DB_PATH is not set (add it to .env)", file=sys.stderr)
        return 1
    logging.basicConfig(level=logging.INFO, format="%(name)s | %(message)s")

    try:
        # ingestion -> validation -> returns -> moments -> optimiser
        source = SqliteMarketDataSource(Path(db_path))
        tickers = source.instruments("EQUITY")["provider_symbol"].tolist()
        panel = PriceValidator().validate(source.equity_closes(tickers)).panel
        moments = MomentEstimator().estimate(panel.returns())
        optimizer = ClosedFormMeanVariance(moments)
    except QuenError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    k = optimizer.coefficients
    print(f"\nA = {k.a:.4f}   B = {k.b:.4f}   C = {k.c:.4f}   D = {k.d:.4f}")

    gmv = optimizer.global_minimum_variance()
    print(
        f"\n== GMV portfolio: return {gmv.expected_return:.2%}, vol {gmv.volatility:.2%}, "
        f"gross exposure {gmv.gross_exposure:.2f}"
    )
    print(_top_weights(gmv.weights))

    best = float(moments.mean.max())
    print(f"\n== Frontier points (short selling allowed); best single asset return {best:.2%}")
    print(f"{'target':>8} {'vol':>8} {'gross':>7}  {'max long':>9} {'max short':>10}")
    for p in optimizer.efficient_frontier(max_return=best, n_points=6):
        w = p.weights
        print(
            f"{p.expected_return:8.2%} {p.volatility:8.2%} {p.gross_exposure:7.2f}"
            f"  {w.max():9.1%} {w.min():10.1%}"
        )

    _plot(optimizer, best)
    print(f"\nPlot written to {REPORT}")
    return 0


def _top_weights(weights: pd.Series, n: int = 5) -> str:
    ordered = weights.sort_values()
    rows = pd.concat([ordered.tail(n)[::-1], ordered.head(n)])
    return "\n".join(f"  {t:<6} {w:8.1%}" for t, w in rows.items())


def _plot(optimizer: ClosedFormMeanVariance, best: float) -> None:
    moments, k = optimizer.moments, optimizer.coefficients
    m = np.linspace(k.b / k.a - 0.6 * best, 1.4 * best, 300)
    sigma = np.sqrt([k.variance(float(x)) for x in m])
    efficient = m >= k.b / k.a
    gmv = optimizer.global_minimum_variance()

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(sigma[efficient], m[efficient], color="#2b5fb4", lw=2.2, label="efficient frontier")
    ax.plot(sigma[~efficient], m[~efficient], color="#2b5fb4", lw=1.2, ls="--", label="inefficient")
    ax.scatter(moments.volatilities, moments.mean, s=18, color="#5a6068", zorder=3, label="assets")
    for t in moments.tickers:
        ax.annotate(
            t,
            (moments.volatilities[t], moments.mean[t]),
            fontsize=7,
            xytext=(3, 2),
            textcoords="offset points",
        )
    ax.scatter(
        [gmv.volatility], [gmv.expected_return], marker="D", color="#d0622b", zorder=4, label="GMV"
    )
    ax.set_xlabel("volatility (annualised)")
    ax.set_ylabel("expected return (annualised)")
    ax.xaxis.set_major_formatter(PercentFormatter(1.0))
    ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax.set_xlim(left=0)
    ax.grid(color="#e6e8eb", lw=0.6)
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    ax.set_title("Mean-variance frontier, short selling allowed (closed form)")
    fig.tight_layout()
    REPORT.parent.mkdir(exist_ok=True)
    fig.savefig(REPORT, dpi=150)


if __name__ == "__main__":
    raise SystemExit(main())
