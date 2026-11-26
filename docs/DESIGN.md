# Design notes

## Matching rules

1. **Price priority**: a better price always trades first (highest bid, lowest ask).
2. **Time priority**: at the same price, the order that arrived first trades first.
3. **Maker price**: a trade prints at the resting order's price, never the taker's limit.
4. A partially filled resting order keeps its place in the queue.

## Data structures (current)

| Operation              | Cost       | How                                                         |
| ---------------------- | ---------- | ----------------------------------------------------------- |
| Best bid / ask         | O(1) amortised | lazy-deletion heap, stale entries popped on read        |
| Add at an existing level | O(1)     | append to the level's ordered dict                          |
| Add a new level        | O(log P)   | heap push (P = active price levels)                         |
| Cancel by id           | O(1)       | id index, then delete from the level's ordered dict         |
| Match k fills          | O(k)       | take the head of the best level                             |
| FOK pre-check          | O(P log P) | sorts levels; fine for the reference engine, not the C++ one |
| Depth snapshot         | O(P log P) | sorts levels; query path only                               |

The C++ port is expected to index levels by tick in a flat array and use an intrusive
doubly linked list per level, which removes the sorting and heap costs.

## Planned

- **Sequencer and event log**: one writer assigns a global sequence number to every
  event and appends it to a log. State is rebuilt from snapshot plus journal, and CI
  checks a hash of the final state so any run replays bit for bit.
- **Cancel/replace**: reducing size keeps queue priority; changing price or increasing
  size sends the order to the back of the queue.
- **Stops and icebergs**: stops trigger off the last trade price; an iceberg's refreshed
  slice loses time priority.
- **Simulation**: Hawkes-process order arrivals (keeping the branching ratio below 1),
  an Avellaneda-Stoikov market maker, and a queue-position fill model so passive
  orders do not get optimistic fills.
- **Backtest integrity**: event-time clock with no lookahead, explicit fee and slippage
  model, walk-forward splits, seeded RNG.
