# lob-sim

[![CI](https://github.com/DINESH-7S/lob-sim/actions/workflows/ci.yml/badge.svg)](https://github.com/DINESH-7S/lob-sim/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

An open-source limit order book, matching engine and market simulator, built from scratch
in public over six weeks. Python reference implementation first, then a C++ port.

> Status: **Week 1 of 6.** The core book works and is tested. Everything under
> "Roadmap" that is not ticked does not exist yet.

## What works today

- Limit and market orders with strict **price-time priority**
- Time-in-force: GTC, IOC, FOK
- O(1) cancel by order id; trades always print at the resting (maker) price
- Integer prices (ticks), so no floating point in the matching path
- Property-style randomised test: the book never crosses, filled quantity never
  exceeds submitted quantity

```python
from lobsim import Book, Side

book = Book()
book.submit_limit(1, Side.SELL, 10002, 300)  # prices are integer ticks (cents)
book.submit_limit(2, Side.SELL, 10003, 500)
trades = book.submit_limit(3, Side.BUY, 10003, 700)
# -> 300 @ 10002, then 400 @ 10003
```

## Roadmap

- [x] Core book, price-time priority, GTC / IOC / FOK, cancel
- [ ] Cancel/replace with correct priority rules, stop and iceberg orders
- [ ] Self-trade prevention
- [ ] Single-writer sequencer, append-only event log, deterministic replay with state hash
- [ ] Order-flow simulator (Hawkes process)
- [ ] Avellaneda-Stoikov market maker and a queue-position fill model
- [ ] Backtester and risk analytics (Sharpe, drawdown, VaR)
- [ ] C++ port with throughput and p99 latency benchmarks

Design notes live in [docs/DESIGN.md](docs/DESIGN.md).

## Development

```bash
make install   # editable install with dev tools
make check     # ruff lint + format check + tests
```

## Contributing

Issues and pull requests are welcome. Please run `make check` before opening a PR.

## License

MIT, see [LICENSE](LICENSE).
