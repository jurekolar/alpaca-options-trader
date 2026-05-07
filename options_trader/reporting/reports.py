"""Human-readable reports for CLI output and saved artifacts."""

from __future__ import annotations

from dataclasses import asdict

from options_trader.backtesting.engine import BacktestResult
from options_trader.backtesting.reporting import compute_metrics
from options_trader.domain import TradeCandidate, TradeDecision
from options_trader.universe.scanner import RankedSymbol


def format_scan_report(
    ranked_symbols: list[RankedSymbol],
    decision: TradeDecision,
    limit: int = 10,
) -> str:
    lines = ["# Scan Report", ""]
    lines.append("## Ranked Symbols")
    for symbol in ranked_symbols[:limit]:
        lines.append(f"- {symbol.symbol}: {symbol.score:.1f} ({'; '.join(symbol.reasons)})")
    if not ranked_symbols:
        lines.append("- no symbols ranked")

    lines.extend(["", "## Accepted Candidates"])
    for candidate in decision.accepted[:limit]:
        lines.append(_candidate_line(candidate))
    if not decision.accepted:
        lines.append("- no accepted candidates")

    lines.extend(["", "## Rejected Trades"])
    for rejection in decision.rejected[:limit]:
        detail = f" {rejection.candidate.symbols}" if rejection.candidate else ""
        lines.append(f"- {rejection.reason.value}:{detail} {rejection.message}")
    if not decision.rejected:
        lines.append("- none")
    return "\n".join(lines)


def format_backtest_report(result: BacktestResult) -> str:
    metrics = compute_metrics(result)
    lines = [
        "# Backtest Report",
        "",
        f"Starting cash: ${result.starting_cash:.2f}",
        f"Ending cash: ${result.ending_cash:.2f}",
        "",
        "## Metrics",
    ]
    for key, value in asdict(metrics).items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Trades"])
    for trade in result.trades:
        lines.append(
            f"- {trade.symbol}: pnl=${trade.pnl:.2f}, entry={trade.entry_price:.4f}, "
            f"exit={trade.exit_price:.4f}, reason={trade.reason}"
        )
    if not result.trades:
        lines.append("- no executed trades")
    lines.extend(["", "## Notes"])
    for note in result.notes:
        lines.append(f"- {note}")
    if not result.notes:
        lines.append("- none")
    return "\n".join(lines)


def _candidate_line(candidate: TradeCandidate) -> str:
    return (
        f"- {candidate.strategy.value} {candidate.underlying_symbol} {candidate.symbols} "
        f"qty={candidate.quantity} score={candidate.score:.1f} "
        f"max_loss=${candidate.max_loss:.2f} expected_reward=${candidate.expected_reward:.2f} "
        f"why={'; '.join(candidate.rationale)}"
    )

