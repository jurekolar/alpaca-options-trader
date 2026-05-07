"""Command-line interface for the Alpaca options trader."""

from __future__ import annotations

import argparse
from datetime import date, datetime, time, timedelta, timezone
import logging
from pathlib import Path
import sys

from options_trader.alpaca import (
    AlpacaClientFactory,
    AlpacaExecutionClient,
    AlpacaMarketData,
    AlpacaSettings,
    parse_occ_option_symbol,
)
from options_trader.alpaca.execution import OrderBuilder
from options_trader.backtesting import BacktestEngine
from options_trader.config import BotConfig, load_config
from options_trader.domain import OptionContract, StrategyKind, UnderlyingSnapshot
from options_trader.exceptions import LiveTradingBlockedError, OptionsTraderError
from options_trader.logging_utils import configure_logging
from options_trader.orchestration import generate_and_filter_candidates
from options_trader.reporting import format_backtest_report, format_scan_report
from options_trader.risk import assert_live_trading_allowed
from options_trader.signals.technical import TechnicalSnapshot
from options_trader.universe import UniverseScanner

LOGGER = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(args.verbose)

    try:
        config = load_config(args.config)
        return args.func(args, config)
    except LiveTradingBlockedError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except OptionsTraderError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        return 130


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Alpaca small-account options trading bot")
    parser.add_argument("--config", default="config/default.toml", help="TOML config path")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan = subparsers.add_parser("scan", help="Scan option chains and rank trade candidates")
    scan.set_defaults(func=cmd_scan)

    backtest = subparsers.add_parser("backtest", help="Backtest using Alpaca historical options data")
    backtest.add_argument(
        "--strategy",
        choices=[StrategyKind.LONG_OPTIONS.value, StrategyKind.VERTICAL_SPREADS.value],
        default=StrategyKind.LONG_OPTIONS.value,
    )
    backtest.add_argument("--option-symbol", action="append", default=[], help="Option contract symbol")
    backtest.add_argument("--long-symbol", help="Long leg option symbol for vertical spread backtest")
    backtest.add_argument("--short-symbol", help="Short leg option symbol for vertical spread backtest")
    backtest.add_argument("--start", help="Backtest start ISO datetime/date")
    backtest.add_argument("--end", help="Backtest end ISO datetime/date")
    backtest.add_argument("--report-path", default="reports/latest_backtest.md")
    backtest.set_defaults(func=cmd_backtest)

    paper = subparsers.add_parser("paper-trade", help="Scan and submit the top candidate in paper mode")
    paper.add_argument("--dry-run", action="store_true", help="Scan only; do not submit paper order")
    paper.set_defaults(func=cmd_paper_trade)

    live = subparsers.add_parser("live-trade", help="Scan and submit the top candidate in live mode")
    live.add_argument("--i-understand-this-can-lose-money", action="store_true")
    live.add_argument("--dry-run", action="store_true", help="Run all live gates and scan, but do not submit")
    live.set_defaults(func=cmd_live_trade)

    status = subparsers.add_parser("status", help="Show Alpaca account/options readiness")
    status.add_argument("--live", action="store_true", help="Check live account instead of paper")
    status.set_defaults(func=cmd_status)

    close = subparsers.add_parser("close-position", help="Close an option or stock position")
    close.add_argument("symbol")
    close.add_argument("--qty")
    close.add_argument("--live", action="store_true")
    close.add_argument("--i-understand-this-can-lose-money", action="store_true")
    close.set_defaults(func=cmd_close_position)

    report = subparsers.add_parser("report", help="Print a saved report")
    report.add_argument("--path", default="reports/latest_backtest.md")
    report.set_defaults(func=cmd_report)
    return parser


def cmd_scan(_args: argparse.Namespace, config: BotConfig) -> int:
    ranked, decision, _factory = run_scan(config, paper=True)
    print(format_scan_report(ranked, decision))
    return 0


def cmd_paper_trade(args: argparse.Namespace, config: BotConfig) -> int:
    ranked, decision, factory = run_scan(config, paper=True)
    print(format_scan_report(ranked, decision))
    if args.dry_run or not decision.accepted:
        return 0
    execution = AlpacaExecutionClient(factory.trading_client(), OrderBuilder())
    order = execution.submit_candidate(
        decision.accepted[0],
        config.execution.slippage_tolerance_pct,
    )
    print(f"Submitted paper order: {getattr(order, 'id', order)}")
    return 0


def cmd_live_trade(args: argparse.Namespace, config: BotConfig) -> int:
    assert_live_trading_allowed(config, args.i_understand_this_can_lose_money)
    ranked, decision, factory = run_scan(config, paper=False)
    print(format_scan_report(ranked, decision))
    if args.dry_run or not decision.accepted:
        return 0
    execution = AlpacaExecutionClient(factory.trading_client(), OrderBuilder())
    order = execution.submit_candidate(
        decision.accepted[0],
        config.execution.slippage_tolerance_pct,
    )
    print(f"Submitted live order: {getattr(order, 'id', order)}")
    return 0


def cmd_backtest(args: argparse.Namespace, config: BotConfig) -> int:
    if args.strategy == StrategyKind.LONG_OPTIONS.value:
        if not args.option_symbol:
            raise OptionsTraderError(
                "backtest --strategy long_options requires at least one --option-symbol. "
                "Historical option backtests must use real Alpaca option contract symbols."
            )
    elif not args.long_symbol or not args.short_symbol:
        raise OptionsTraderError(
            "backtest --strategy vertical_spreads requires --long-symbol and --short-symbol."
        )

    settings = AlpacaSettings.from_env(paper=True)
    factory = AlpacaClientFactory(settings)
    market_data = AlpacaMarketData(
        factory.option_data_client(),
        factory.stock_data_client(),
        stock_feed=config.market_data.stock_feed,
    )
    engine = BacktestEngine(config, market_data)
    symbols = _backtest_symbols(args)
    start, end = _resolve_backtest_window(args, config, symbols)
    if args.strategy == StrategyKind.LONG_OPTIONS.value:
        result = engine.run_long_option_backtest(args.option_symbol, start, end)
    else:
        result = engine.run_vertical_spread_backtest(
            args.long_symbol,
            args.short_symbol,
            start,
            end,
        )
    report = format_backtest_report(result)
    report_path = Path(args.report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report + "\n", encoding="utf-8")
    print(report)
    print(f"\nSaved report: {report_path}")
    return 0


def cmd_status(args: argparse.Namespace, config: BotConfig) -> int:
    settings = AlpacaSettings.from_env(paper=not args.live)
    factory = AlpacaClientFactory(settings)
    account = factory.account_state(verify_market_data=True)
    print("Account status")
    print(f"- mode: {'paper' if account.paper else 'live'}")
    print(f"- equity: ${account.equity:.2f}")
    print(f"- cash: ${account.cash:.2f}")
    print(f"- options_buying_power: ${account.effective_options_buying_power:.2f}")
    print(f"- options_approved: {account.options_approved}")
    print(f"- options_trading_level: {account.options_trading_level}")
    print(f"- multi_leg_supported: {account.multi_leg_supported}")
    print(f"- market_data_entitled: {account.market_data_entitled}")
    print(f"- live_trading_enabled_in_config: {config.execution.live_trading_enabled}")
    return 0


def cmd_close_position(args: argparse.Namespace, config: BotConfig) -> int:
    if args.live:
        assert_live_trading_allowed(config, args.i_understand_this_can_lose_money)
    settings = AlpacaSettings.from_env(paper=not args.live)
    factory = AlpacaClientFactory(settings)
    execution = AlpacaExecutionClient(factory.trading_client(), OrderBuilder())
    order = execution.close_position(args.symbol, args.qty)
    print(f"Close request submitted: {getattr(order, 'id', order)}")
    return 0


def cmd_report(args: argparse.Namespace, _config: BotConfig) -> int:
    report_path = Path(args.path)
    if not report_path.exists():
        raise OptionsTraderError(f"Report not found: {report_path}")
    print(report_path.read_text(encoding="utf-8"))
    return 0


def run_scan(
    config: BotConfig,
    paper: bool,
) -> tuple[list[object], object, AlpacaClientFactory]:
    settings = AlpacaSettings.from_env(paper=paper)
    factory = AlpacaClientFactory(settings)
    account = factory.account_state(verify_market_data=True)
    market_data = AlpacaMarketData(
        factory.option_data_client(),
        factory.stock_data_client(),
        stock_feed=config.market_data.stock_feed,
    )
    today = date.today()
    expiration_gte = today + timedelta(days=config.universe.min_dte)
    expiration_lte = today + timedelta(days=config.universe.max_dte)
    start = datetime.now(timezone.utc) - timedelta(days=1)
    end = datetime.now(timezone.utc)

    chains: dict[str, list[OptionContract]] = {}
    underlyings: dict[str, UnderlyingSnapshot] = {}
    technicals: dict[str, TechnicalSnapshot] = {}
    for symbol in config.universe.symbols:
        chains[symbol] = market_data.get_option_chain(symbol, expiration_gte, expiration_lte)
        underlying, technical = market_data.get_underlying_intraday_context(symbol, start, end)
        underlyings[symbol] = underlying
        if technical:
            technicals[symbol] = technical
        LOGGER.info("Loaded %s contracts for %s", len(chains[symbol]), symbol)

    ranked = UniverseScanner(config).rank(list(underlyings.values()), chains)
    ranked_symbols = {item.symbol for item in ranked if item.score > 0}
    filtered_chains = {symbol: chain for symbol, chain in chains.items() if symbol in ranked_symbols}
    decision = generate_and_filter_candidates(
        config,
        account,
        filtered_chains,
        underlyings,
        technicals,
        factory.positions(),
        today=today,
    )
    return ranked, decision, factory


def _backtest_symbols(args: argparse.Namespace) -> list[str]:
    if args.strategy == StrategyKind.LONG_OPTIONS.value:
        return list(args.option_symbol)
    return [args.long_symbol, args.short_symbol]


def _resolve_backtest_window(
    args: argparse.Namespace,
    config: BotConfig,
    symbols: list[str],
    now: datetime | None = None,
) -> tuple[datetime, datetime]:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)
    latest_allowed_end = _latest_allowed_option_bar_end(
        current,
        config.market_data.option_bars_delay_minutes,
    )

    start_value = args.start if args.start is not None else config.backtest.start
    end_value = args.end if args.end is not None else config.backtest.end

    if _is_auto_datetime(end_value):
        end = _infer_auto_backtest_end(symbols, latest_allowed_end)
    else:
        end = min(_parse_datetime(str(end_value), date_as_end=True), latest_allowed_end)

    if _is_auto_datetime(start_value):
        start = end - timedelta(days=config.backtest.auto_lookback_days)
    else:
        start = _parse_datetime(str(start_value), date_as_end=False)

    if start >= end:
        raise OptionsTraderError(
            "Invalid backtest window: "
            f"start {start.isoformat()} must be before end {end.isoformat()}"
        )
    return start, end


def _is_auto_datetime(value: object) -> bool:
    return str(value).strip().lower() in {"", "auto"}


def _latest_allowed_option_bar_end(now: datetime, delay_minutes: int) -> datetime:
    if delay_minutes <= 0:
        return now
    return now - timedelta(minutes=delay_minutes)


def _infer_auto_backtest_end(symbols: list[str], now: datetime) -> datetime:
    expiration_dates = []
    for symbol in symbols:
        try:
            expiration_dates.append(parse_occ_option_symbol(symbol).expiration)
        except ValueError as exc:
            raise OptionsTraderError(
                f"Unsupported option symbol for automatic backtest dates: {symbol}"
            ) from exc
    expiration_end = datetime.combine(
        min(expiration_dates) + timedelta(days=1),
        time.min,
        tzinfo=timezone.utc,
    )
    return min(now, expiration_end)


def _parse_datetime(value: str, *, date_as_end: bool = False) -> datetime:
    if len(value) == 10:
        parsed_date = date.fromisoformat(value)
        if date_as_end:
            parsed_date += timedelta(days=1)
        return datetime.combine(parsed_date, time.min, tzinfo=timezone.utc)
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


if __name__ == "__main__":
    raise SystemExit(main())
