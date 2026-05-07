"""Human-readable reports for CLI output and saved artifacts."""

from __future__ import annotations

from dataclasses import asdict

from options_trader.backtesting.engine import BacktestResult
from options_trader.backtesting.reporting import compute_metrics
from options_trader.domain import TradeCandidate, TradeDecision
from options_trader.research import CandidateBacktest
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


def format_universe_research_report(
    screened_symbols: list[str],
    ranked_symbols: list[RankedSymbol],
    decision: TradeDecision,
    backtests: list[CandidateBacktest],
    notes: list[str] | None = None,
    limit: int = 20,
) -> str:
    lines = [
        "# Universe Research Report",
        "",
        f"Screened underlyings: {len(screened_symbols)}",
        f"Symbols: {', '.join(screened_symbols)}",
        "",
        "## Ranked Symbols",
    ]
    for symbol in ranked_symbols[:limit]:
        lines.append(f"- {symbol.symbol}: {symbol.score:.1f} ({'; '.join(symbol.reasons)})")
    if not ranked_symbols:
        lines.append("- no symbols ranked")

    lines.extend(["", "## Accepted Candidates"])
    for candidate in decision.accepted[:limit]:
        lines.append(_candidate_line(candidate))
    if not decision.accepted:
        lines.append("- no accepted candidates")

    lines.extend(["", "## Candidate Backtests"])
    for item in backtests:
        symbols = "/".join(item.symbols)
        if item.result is None:
            lines.append(f"- {item.strategy.value} {symbols}: unavailable ({item.error})")
            continue
        result = item.result
        lines.append(
            f"- {item.strategy.value} {symbols}: pnl=${item.pnl:.2f}, "
            f"ending_cash=${result.ending_cash:.2f}, trades={len(result.trades)}, "
            f"rejected={result.rejected_trade_count}"
        )
    if not backtests:
        lines.append("- no candidates backtested")

    profitable_underlyings = _profitable_underlyings(backtests)
    ranked_positive = [item.symbol for item in ranked_symbols if item.score > 0]
    recommended = _dedupe(profitable_underlyings + ranked_positive)[:limit]
    lines.extend(["", "## Recommended Symbols"])
    if recommended:
        lines.append(f"- {', '.join(recommended)}")
    else:
        lines.append("- none")

    lines.extend(["", "## Notes"])
    for note in notes or []:
        lines.append(f"- {note}")
    if not notes:
        lines.append("- none")
    return "\n".join(lines)


def _candidate_line(candidate: TradeCandidate) -> str:
    return (
        f"- {candidate.strategy.value} {candidate.underlying_symbol} {candidate.symbols} "
        f"qty={candidate.quantity} score={candidate.score:.1f} "
        f"max_loss=${candidate.max_loss:.2f} expected_reward=${candidate.expected_reward:.2f} "
        f"why={'; '.join(candidate.rationale)}"
    )


def _profitable_underlyings(backtests: list[CandidateBacktest]) -> list[str]:
    symbols: list[str] = []
    for item in backtests:
        if item.profitable is not True:
            continue
        for trade in item.result.trades if item.result else []:
            root = trade.symbol.split("/")[0]
            symbols.append(_occ_underlying(root))
    return symbols


def _occ_underlying(symbol: str) -> str:
    chars: list[str] = []
    for char in symbol:
        if char.isdigit():
            break
        chars.append(char)
    return "".join(chars)


def _dedupe(symbols: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for symbol in symbols:
        if symbol in seen:
            continue
        seen.add(symbol)
        result.append(symbol)
    return result
