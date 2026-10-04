"""Capital ledger.

Identity (checked after every event):

    initial + deposits − withdrawals + net_realized_pnl == trading_capital + reserve

Rules:
* Costs are deducted before allocation.
* Net profit > 0 → 30% reserve / 70% trading capital (reserve share from Constitution).
* Net loss → trading capital only. Reserve is never touched by trading.
* Deposits are capital, not profit (no allocation, not counted as P&L).
* There is no reserve → trading transfer.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from atlas.domain.money import ZERO, paise


class LedgerError(Exception):
    pass


@dataclass(frozen=True)
class Allocation:
    gross_pnl: Decimal
    costs: Decimal
    net_pnl: Decimal
    reserve_allocation: Decimal
    compound_allocation: Decimal

    def as_payload(self) -> dict[str, str]:
        return {
            "gross_pnl": str(self.gross_pnl),
            "costs": str(self.costs),
            "net_pnl": str(self.net_pnl),
            "reserve_allocation": str(self.reserve_allocation),
            "compound_allocation": str(self.compound_allocation),
        }


def allocate(gross_pnl: Decimal, costs: Decimal, reserve_share: Decimal) -> Allocation:
    if costs < 0:
        raise LedgerError("costs cannot be negative")
    gross = paise(gross_pnl)
    c = paise(costs)
    net = gross - c
    if net > 0:
        reserve = paise(net * reserve_share)
        compound = net - reserve  # exact remainder keeps the identity exact
    else:
        reserve = ZERO
        compound = net
    return Allocation(gross, c, net, reserve, compound)


@dataclass
class LedgerState:
    initialized: bool = False
    initial_capital: Decimal = ZERO
    trading_capital: Decimal = ZERO
    reserve: Decimal = ZERO
    peak_trading_capital: Decimal = ZERO
    deposits: Decimal = ZERO
    withdrawals: Decimal = ZERO
    gross_realized_pnl: Decimal = ZERO
    costs: Decimal = ZERO
    net_realized_pnl: Decimal = ZERO
    reserve_allocated: Decimal = ZERO
    compound_allocated: Decimal = ZERO

    # ------------------------------------------------------------------ transitions
    def initialize(self, capital: Decimal) -> None:
        if self.initialized:
            raise LedgerError("ledger already initialized")
        if capital <= 0:
            raise LedgerError("initial capital must be positive")
        self.initialized = True
        self.initial_capital = paise(capital)
        self.trading_capital = paise(capital)
        self.peak_trading_capital = paise(capital)

    def deposit(self, amount: Decimal) -> None:
        self._require_init()
        if amount <= 0:
            raise LedgerError("deposit must be positive")
        amount = paise(amount)
        self.deposits += amount
        self.trading_capital += amount
        self.peak_trading_capital += amount  # deposits must not mask drawdown

    def withdraw(self, amount: Decimal, source: str) -> None:
        self._require_init()
        if amount <= 0:
            raise LedgerError("withdrawal must be positive")
        amount = paise(amount)
        if source == "RESERVE":
            if amount > self.reserve:
                raise LedgerError("withdrawal exceeds reserve")
            self.reserve -= amount
        elif source == "TRADING":
            if amount > self.trading_capital:
                raise LedgerError("withdrawal exceeds trading capital")
            self.trading_capital -= amount
            self.peak_trading_capital = max(self.trading_capital, self.peak_trading_capital - amount)
        else:
            raise LedgerError(f"unknown withdrawal source {source!r}")
        self.withdrawals += amount

    def realize(self, alloc: Allocation) -> None:
        self._require_init()
        self.gross_realized_pnl += alloc.gross_pnl
        self.costs += alloc.costs
        self.net_realized_pnl += alloc.net_pnl
        self.reserve_allocated += alloc.reserve_allocation
        self.compound_allocated += alloc.compound_allocation
        self.reserve += alloc.reserve_allocation
        self.trading_capital += alloc.compound_allocation
        self.peak_trading_capital = max(self.peak_trading_capital, self.trading_capital)

    # ------------------------------------------------------------------ checks
    def _require_init(self) -> None:
        if not self.initialized:
            raise LedgerError("ledger not initialized")

    def invariant_errors(self) -> list[str]:
        errs: list[str] = []
        if not self.initialized:
            return errs
        lhs = self.initial_capital + self.deposits - self.withdrawals + self.net_realized_pnl
        rhs = self.trading_capital + self.reserve
        if lhs != rhs:
            errs.append(f"capital identity broken: {lhs} != {rhs}")
        if self.reserve < 0:
            errs.append("reserve negative")
        if self.net_realized_pnl != self.gross_realized_pnl - self.costs:
            errs.append("net P&L != gross − costs")
        if self.reserve_allocated + self.compound_allocated != self.net_realized_pnl:
            errs.append("allocations do not sum to net P&L")
        if self.trading_capital <= 0:
            errs.append("trading capital exhausted")
        return errs

    @property
    def drawdown_pct(self) -> Decimal:
        if self.peak_trading_capital <= 0:
            return ZERO
        dd = (self.peak_trading_capital - self.trading_capital) / self.peak_trading_capital
        return max(dd, ZERO)

    def to_dict(self) -> dict[str, str | bool]:
        return {
            "initialized": self.initialized,
            "initial_capital": str(paise(self.initial_capital)),
            "trading_capital": str(paise(self.trading_capital)),
            "reserve": str(paise(self.reserve)),
            "peak_trading_capital": str(paise(self.peak_trading_capital)),
            "deposits": str(paise(self.deposits)),
            "withdrawals": str(paise(self.withdrawals)),
            "gross_realized_pnl": str(paise(self.gross_realized_pnl)),
            "costs": str(paise(self.costs)),
            "net_realized_pnl": str(paise(self.net_realized_pnl)),
            "reserve_allocated": str(paise(self.reserve_allocated)),
            "compound_allocated": str(paise(self.compound_allocated)),
        }
