"""Order building and execution boundary for Alpaca."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from options_trader.domain import StrategyKind, TradeAction, TradeCandidate
from options_trader.exceptions import RiskLimitError
from options_trader.retry import retry_call

LOGGER = logging.getLogger(__name__)


class OrderBuilder:
    """Build alpaca-py order request objects from internal trade candidates."""

    def build_limit_order(self, candidate: TradeCandidate, limit_price: float) -> Any:
        if candidate.strategy == StrategyKind.VERTICAL_SPREADS:
            return self._build_mleg_limit(candidate, limit_price)
        return self._build_simple_limit(candidate, limit_price)

    def _build_simple_limit(self, candidate: TradeCandidate, limit_price: float) -> Any:
        if len(candidate.legs) != 1:
            raise RiskLimitError("simple option order requires exactly one leg")
        try:
            from alpaca.trading.enums import OrderSide, PositionIntent, TimeInForce
            from alpaca.trading.requests import LimitOrderRequest
        except ImportError as exc:
            raise RiskLimitError("alpaca-py is not installed. Run: pip install alpaca-py") from exc

        leg = candidate.legs[0]
        return LimitOrderRequest(
            symbol=leg.contract.symbol,
            qty=candidate.quantity,
            side=self._side(leg.action, OrderSide),
            time_in_force=TimeInForce.DAY,
            limit_price=round(limit_price, 2),
            position_intent=self._position_intent(leg.action, PositionIntent),
        )

    def _build_mleg_limit(self, candidate: TradeCandidate, limit_price: float) -> Any:
        if len(candidate.legs) < 2:
            raise RiskLimitError("multi-leg option order requires at least two legs")
        try:
            from alpaca.trading.enums import OrderClass, OrderSide, PositionIntent, TimeInForce
            from alpaca.trading.requests import LimitOrderRequest, OptionLegRequest
        except ImportError as exc:
            raise RiskLimitError("alpaca-py is not installed. Run: pip install alpaca-py") from exc

        legs = [
            OptionLegRequest(
                symbol=leg.contract.symbol,
                ratio_qty=leg.ratio,
                side=self._side(leg.action, OrderSide),
                position_intent=self._position_intent(leg.action, PositionIntent),
            )
            for leg in candidate.legs
        ]
        return LimitOrderRequest(
            qty=candidate.quantity,
            order_class=OrderClass.MLEG,
            time_in_force=TimeInForce.DAY,
            limit_price=round(limit_price, 2),
            legs=legs,
        )

    def recommended_limit_price(self, candidate: TradeCandidate, slippage_tolerance_pct: float) -> float:
        if candidate.strategy == StrategyKind.VERTICAL_SPREADS:
            debit = 0.0
            for leg in candidate.legs:
                if leg.action == TradeAction.BUY_TO_OPEN:
                    if leg.contract.ask is None:
                        raise RiskLimitError("missing ask for long spread leg")
                    debit += leg.contract.ask
                elif leg.action == TradeAction.SELL_TO_OPEN:
                    if leg.contract.bid is None:
                        raise RiskLimitError("missing bid for short spread leg")
                    debit -= leg.contract.bid
            return max(0.01, debit * (1.0 + slippage_tolerance_pct))

        leg = candidate.legs[0]
        if leg.action in {TradeAction.BUY_TO_OPEN, TradeAction.BUY_TO_CLOSE}:
            if leg.contract.ask is None:
                raise RiskLimitError("missing ask for buy order")
            return leg.contract.ask * (1.0 + slippage_tolerance_pct)
        if leg.contract.bid is None:
            raise RiskLimitError("missing bid for sell order")
        return leg.contract.bid * (1.0 - slippage_tolerance_pct)

    def _side(self, action: TradeAction, order_side_enum: Any) -> Any:
        if action in {TradeAction.BUY_TO_OPEN, TradeAction.BUY_TO_CLOSE}:
            return order_side_enum.BUY
        return order_side_enum.SELL

    def _position_intent(self, action: TradeAction, position_intent_enum: Any) -> Any:
        mapping = {
            TradeAction.BUY_TO_OPEN: position_intent_enum.BUY_TO_OPEN,
            TradeAction.BUY_TO_CLOSE: position_intent_enum.BUY_TO_CLOSE,
            TradeAction.SELL_TO_OPEN: position_intent_enum.SELL_TO_OPEN,
            TradeAction.SELL_TO_CLOSE: position_intent_enum.SELL_TO_CLOSE,
        }
        return mapping[action]


@dataclass
class AlpacaExecutionClient:
    trading_client: Any
    order_builder: OrderBuilder

    def submit_candidate(self, candidate: TradeCandidate, slippage_tolerance_pct: float) -> Any:
        limit_price = self.order_builder.recommended_limit_price(candidate, slippage_tolerance_pct)
        request = self.order_builder.build_limit_order(candidate, limit_price)
        LOGGER.info(
            "Submitting %s order for %s qty=%s limit=%.2f",
            candidate.strategy.value,
            ",".join(candidate.symbols),
            candidate.quantity,
            limit_price,
        )
        return retry_call(
            lambda: self.trading_client.submit_order(order_data=request),
            operation_name="submit order",
        )

    def close_position(self, symbol: str, qty: str | None = None) -> Any:
        try:
            from alpaca.trading.requests import ClosePositionRequest
        except ImportError as exc:
            raise RiskLimitError("alpaca-py is not installed. Run: pip install alpaca-py") from exc
        request = ClosePositionRequest(qty=qty) if qty else None
        return retry_call(
            lambda: self.trading_client.close_position(symbol, close_options=request),
            operation_name=f"close position {symbol}",
        )
