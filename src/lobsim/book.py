"""Limit order book with price-time priority.

Prices are integers (ticks) so there is no floating point in the matching path.
Each price level is an insertion-ordered dict (id -> order): the first entry is the
head of the FIFO queue, and a cancel is an O(1) delete through the id index.
Best prices come from lazy-deletion heaps, so adding a new level costs O(log P).
"""

from __future__ import annotations

import heapq
from collections import OrderedDict
from dataclasses import dataclass
from enum import Enum


class Side(Enum):
    BUY = 1
    SELL = -1


class TimeInForce(Enum):
    GTC = "GTC"  # rest the remainder on the book
    IOC = "IOC"  # cancel any remainder immediately
    FOK = "FOK"  # fill completely or not at all


@dataclass(frozen=True, slots=True)
class Trade:
    seq: int
    taker_id: int
    maker_id: int
    price: int  # always the resting (maker) order's price
    qty: int
    taker_side: Side


class _Order:
    __slots__ = ("id", "side", "price", "qty")

    def __init__(self, order_id: int, side: Side, price: int, qty: int) -> None:
        self.id = order_id
        self.side = side
        self.price = price
        self.qty = qty


Level = OrderedDict  # order id -> _Order, in arrival order


class Book:
    def __init__(self) -> None:
        self._levels: dict[Side, dict[int, Level]] = {Side.BUY: {}, Side.SELL: {}}
        # Min-heaps. Bids are stored negated so the best bid sits at the top.
        self._heaps: dict[Side, list[int]] = {Side.BUY: [], Side.SELL: []}
        self._index: dict[int, _Order] = {}
        self._seq = 0

    # ------------------------------------------------------------------ queries
    def best_bid(self) -> int | None:
        return self._best(Side.BUY)

    def best_ask(self) -> int | None:
        return self._best(Side.SELL)

    def depth(self, side: Side, n: int = 10) -> list[tuple[int, int]]:
        """Top n price levels as (price, total size), best first."""
        prices = sorted(self._levels[side], reverse=side is Side.BUY)[:n]
        return [(p, sum(o.qty for o in self._levels[side][p].values())) for p in prices]

    def __contains__(self, order_id: int) -> bool:
        return order_id in self._index

    # ----------------------------------------------------------------- commands
    def submit_limit(
        self,
        order_id: int,
        side: Side,
        price: int,
        qty: int,
        tif: TimeInForce = TimeInForce.GTC,
    ) -> list[Trade]:
        self._validate(order_id, qty)
        if price <= 0:
            raise ValueError("price must be a positive number of ticks")
        if tif is TimeInForce.FOK and self._fillable(side, price, qty) < qty:
            return []
        trades, remaining = self._match(order_id, side, price, qty)
        if remaining and tif is TimeInForce.GTC:
            self._rest(_Order(order_id, side, price, remaining))
        return trades

    def submit_market(self, order_id: int, side: Side, qty: int) -> list[Trade]:
        """Sweep the book at any price; an unfilled remainder is discarded."""
        self._validate(order_id, qty)
        trades, _ = self._match(order_id, side, None, qty)
        return trades

    def cancel(self, order_id: int) -> bool:
        order = self._index.pop(order_id, None)
        if order is None:
            return False
        level = self._levels[order.side][order.price]
        del level[order_id]
        if not level:
            del self._levels[order.side][order.price]
        return True

    # ---------------------------------------------------------------- internals
    def _validate(self, order_id: int, qty: int) -> None:
        if qty <= 0:
            raise ValueError("qty must be positive")
        if order_id in self._index:
            raise ValueError(f"order id {order_id} is already live")

    def _best(self, side: Side) -> int | None:
        heap, levels = self._heaps[side], self._levels[side]
        sign = -1 if side is Side.BUY else 1
        while heap and sign * heap[0] not in levels:
            heapq.heappop(heap)  # stale entry: that level has since emptied
        return sign * heap[0] if heap else None

    def _rest(self, order: _Order) -> None:
        levels = self._levels[order.side]
        level = levels.get(order.price)
        if level is None:
            level = levels[order.price] = OrderedDict()
            sign = -1 if order.side is Side.BUY else 1
            heapq.heappush(self._heaps[order.side], sign * order.price)
        level[order.id] = order
        self._index[order.id] = order

    @staticmethod
    def _crosses(side: Side, limit: int | None, best: int) -> bool:
        if limit is None:
            return True
        return best <= limit if side is Side.BUY else best >= limit

    def _fillable(self, side: Side, limit: int, qty: int) -> int:
        """Quantity available at prices that cross `limit` (for FOK pre-checks)."""
        opposite = Side.SELL if side is Side.BUY else Side.BUY
        total = 0
        for price in sorted(self._levels[opposite], reverse=opposite is Side.BUY):
            if not self._crosses(side, limit, price):
                break
            total += sum(o.qty for o in self._levels[opposite][price].values())
            if total >= qty:
                break
        return total

    def _match(
        self, taker_id: int, side: Side, limit: int | None, qty: int
    ) -> tuple[list[Trade], int]:
        opposite = Side.SELL if side is Side.BUY else Side.BUY
        trades: list[Trade] = []
        while qty > 0:
            best = self._best(opposite)
            if best is None or not self._crosses(side, limit, best):
                break
            level = self._levels[opposite][best]
            maker = next(iter(level.values()))  # head of the FIFO queue
            fill = min(qty, maker.qty)
            self._seq += 1
            trades.append(Trade(self._seq, taker_id, maker.id, best, fill, side))
            qty -= fill
            maker.qty -= fill
            if maker.qty == 0:
                del level[maker.id]
                del self._index[maker.id]
                if not level:
                    del self._levels[opposite][best]
        return trades, qty
