"""Position sizing helpers."""

from __future__ import annotations

from dataclasses import dataclass

from options_trader.config.models import RiskConfig
from options_trader.domain import AccountState, TradeCandidate


@dataclass(frozen=True)
class PositionSizer:
    risk: RiskConfig

    def max_trade_risk_dollars(self, account: AccountState) -> float:
        basis = min(account.equity, self.risk.starting_cash) if account.equity > 0 else self.risk.starting_cash
        return max(0.0, basis * self.risk.max_account_risk_per_trade_pct)

    def affordable_quantity(self, candidate: TradeCandidate, account: AccountState) -> int:
        if candidate.quantity <= 0:
            return 0

        risk_cap = self.max_trade_risk_dollars(account)
        per_unit_loss = max(candidate.max_loss, 0.0)
        per_unit_bp = max(candidate.buying_power_effect, 0.0)
        if per_unit_loss <= 0 and per_unit_bp <= 0:
            return candidate.quantity

        by_loss = int(risk_cap // per_unit_loss) if per_unit_loss > 0 else candidate.quantity
        by_bp = (
            int(account.effective_options_buying_power // per_unit_bp)
            if per_unit_bp > 0
            else candidate.quantity
        )
        by_notional = (
            int(self.risk.max_position_notional // per_unit_bp)
            if per_unit_bp > 0
            else candidate.quantity
        )
        return max(0, min(candidate.quantity, by_loss, by_bp, by_notional))
