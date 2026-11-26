import random

import pytest

from lobsim import Book, Side, TimeInForce

BUY, SELL = Side.BUY, Side.SELL


def book_with(*orders):
    b = Book()
    for oid, side, price, qty in orders:
        assert b.submit_limit(oid, side, price, qty) == []
    return b


def test_better_price_fills_first():
    b = book_with((1, SELL, 101, 10), (2, SELL, 100, 10))
    trades = b.submit_limit(3, BUY, 101, 10)
    assert [(t.maker_id, t.price) for t in trades] == [(2, 100)]


def test_time_priority_within_a_level():
    b = book_with((1, SELL, 100, 5), (2, SELL, 100, 5))
    trades = b.submit_limit(3, BUY, 100, 5)
    assert [t.maker_id for t in trades] == [1]
    assert 2 in b and 1 not in b


def test_trade_prints_at_maker_price():
    b = book_with((1, SELL, 100, 10))
    (t,) = b.submit_limit(2, BUY, 105, 10)
    assert t.price == 100 and t.qty == 10 and t.taker_side is BUY


def test_partial_fill_keeps_queue_position():
    b = book_with((1, SELL, 100, 10), (2, SELL, 100, 10))
    b.submit_limit(3, BUY, 100, 4)
    trades = b.submit_limit(4, BUY, 100, 8)
    assert [(t.maker_id, t.qty) for t in trades] == [(1, 6), (2, 2)]


def test_remainder_rests_on_the_book():
    b = book_with((1, SELL, 100, 5))
    trades = b.submit_limit(2, BUY, 100, 8)
    assert sum(t.qty for t in trades) == 5
    assert b.best_bid() == 100 and b.best_ask() is None
    assert b.depth(BUY) == [(100, 3)]


def test_cancel():
    b = book_with((1, BUY, 99, 10), (2, BUY, 99, 5))
    assert b.cancel(1) is True
    assert b.cancel(1) is False
    assert b.depth(BUY) == [(99, 5)]
    assert b.cancel(2) and b.best_bid() is None


def test_ioc_discards_remainder():
    b = book_with((1, SELL, 100, 5))
    trades = b.submit_limit(2, BUY, 100, 8, TimeInForce.IOC)
    assert sum(t.qty for t in trades) == 5
    assert 2 not in b and b.best_bid() is None


def test_fok_is_all_or_nothing():
    b = book_with((1, SELL, 100, 5), (2, SELL, 101, 5))
    assert b.submit_limit(3, BUY, 100, 8, TimeInForce.FOK) == []
    assert b.depth(SELL) == [(100, 5), (101, 5)]
    trades = b.submit_limit(4, BUY, 101, 8, TimeInForce.FOK)
    assert sum(t.qty for t in trades) == 8


def test_market_order_sweeps_levels_and_discards_remainder():
    b = book_with((1, SELL, 100, 5), (2, SELL, 101, 5))
    trades = b.submit_market(3, BUY, 20)
    assert [(t.price, t.qty) for t in trades] == [(100, 5), (101, 5)]
    assert b.best_ask() is None and 3 not in b


def test_rejects_bad_input():
    b = book_with((1, BUY, 99, 10))
    with pytest.raises(ValueError):
        b.submit_limit(1, BUY, 99, 10)  # duplicate live id
    with pytest.raises(ValueError):
        b.submit_limit(2, BUY, 99, 0)
    with pytest.raises(ValueError):
        b.submit_limit(3, BUY, 0, 5)


def test_worked_example_from_the_design_slides():
    # Prices in cents. Asks 100.04/100.03/100.02, bids 100.01/100.00/99.99.
    b = book_with(
        (1, SELL, 10004, 800),
        (2, SELL, 10003, 500),
        (3, SELL, 10002, 300),
        (4, BUY, 10001, 400),
        (5, BUY, 10000, 650),
        (6, BUY, 9999, 900),
    )
    trades = b.submit_limit(7, BUY, 10003, 700)
    assert [(t.qty, t.price) for t in trades] == [(300, 10002), (400, 10003)]
    vwap = sum(t.qty * t.price for t in trades) / 700 / 100
    assert round(vwap, 4) == 100.0257
    assert b.best_ask() == 10003 and b.depth(SELL)[0] == (10003, 100)
    assert b.best_bid() == 10001


def test_random_flow_keeps_invariants():
    rng = random.Random(7)
    b = Book()
    live: set[int] = set()
    submitted = filled = 0
    for oid in range(1, 4001):
        action = rng.random()
        if action < 0.2 and live:
            victim = rng.choice(sorted(live))
            assert b.cancel(victim)
            live.discard(victim)
            continue
        side = rng.choice([BUY, SELL])
        qty = rng.randint(1, 50)
        price = 1000 + rng.randint(-10, 10)
        submitted += qty
        trades = b.submit_limit(oid, side, price, qty)
        filled += sum(t.qty for t in trades)
        live.add(oid)
        live = {i for i in live if i in b}
        bid, ask = b.best_bid(), b.best_ask()
        assert bid is None or ask is None or bid < ask  # never crossed
    assert filled <= submitted
