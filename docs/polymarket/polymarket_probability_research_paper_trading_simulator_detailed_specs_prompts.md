# Polymarket Probability Research & Paper Trading Simulator

## 1. Purpose & North Star

### Objective
Build a **research-grade probability + execution simulator** for Polymarket that answers:
- *Can we consistently estimate probabilities better than the market?*
- *Does that edge survive realistic execution?*

Trading is **not** the goal; **measurement, calibration, and attribution** are.

### North-Star Metrics (ranked)
1. **Mean Edge** = E[final_outcome − entry_price]
2. **Brier Score** (probability calibration)
3. **Edge Preservation Ratio** = realized_edge / theoretical_edge
4. **Execution Drag** (bps lost to slippage / partial fills)
5. Secondary: Realized PnL

---

## 2. System Architecture (Logical)

### Core Services

1. **MarketDataService**
   - Ingests live Polymarket CLOB data (WS-first)
   - Maintains in-memory L2 order books per token
   - Tracks tick size, min size, spread, depth

2. **PaperExchangeService**
   - Simulates order placement, matching, partial fills
   - Maintains balances, orders, positions
   - Applies fees, slippage, queue assumptions

3. **ProbabilityModelService**
   - Estimates fair probability for YES / NO
   - Outputs edge, EV, risk flags

4. **StrategyEngine**
   - Converts probability signals into order intents
   - Applies sizing, throttling, risk constraints

5. **Evaluation & Tracker Service**
   - Logs decisions, fills, outcomes
   - Computes Brier, EV, edge decay

---

## 3. Market Data Model

### Market
```json
{
  "market_id": "string",
  "event": "string",
  "description": "string",
  "category": "politics | crypto | sports | tech | other",
  "end_time": "timestamp",
  "resolution_status": "OPEN | ENDED | PROPOSED | RESOLVED | DISPUTED"
}
```

### Token (YES / NO)
```json
{
  "token_id": "string",
  "market_id": "string",
  "side": "YES | NO",
  "tick_size": 0.001,
  "min_size": 1
}
```

### Order Book (L2)
```json
{
  "bids": [[price, size], ...],
  "asks": [[price, size], ...],
  "timestamp": "ts"
}
```

---

## 4. Paper Exchange Specification

### Order Model
```json
{
  "order_id": "uuid",
  "token_id": "string",
  "side": "BUY | SELL",
  "price": 0.962,
  "size": 100,
  "remaining": 40,
  "type": "LIMIT | MARKET",
  "queue_mode": "CONSERVATIVE | NEUTRAL",
  "status": "OPEN | PARTIAL | FILLED | CANCELED",
  "timestamp": "ts"
}
```

### Matching Rules
- **Market orders**: walk book until filled or depth exhausted
- **Marketable limits**: behave as market orders up to limit price
- **Resting limits**:
  - Conservative: fill only if price trades *through* level
  - Neutral: fill when best crosses price

### Slippage Model
- Walk L2 book
- Partial fills allowed
- No artificial price improvement

### Fees
- Configurable per run
- Applied on fill size

---

## 5. Position & Accounting

### Position
```json
{
  "token_id": "string",
  "side": "YES | NO",
  "quantity": 500,
  "avg_price": 0.941,
  "mark_price": 0.952,
  "unrealized_pnl": 5.5,
  "realized_pnl": 0
}
```

### Mark-to-Market Modes
- Conservative: best bid
- Neutral: mid price
- Aggressive: last trade

---

## 6. Probability Model (v1 — simple but honest)

### Inputs
- Market implied probability (mid price)
- Spread
- Top-N depth
- Order book imbalance
- Time to resolution
- Market category

### Outputs
```json
{
  "fair_prob": 0.965,
  "market_prob": 0.952,
  "edge": 0.013,
  "expected_value": 6.5,
  "risk_flags": ["LOW_DEPTH", "LONG_RESOLUTION"]
}
```

### Constraints
- No future leakage
- No use of post-resolution info

---

## 7. Strategy Engine (Paper Mode Only)

### Entry Rules
- Edge ≥ threshold (e.g. 1.5%)
- Spread ≤ 1 tick
- Depth ≥ X × order size
- Time to resolution ≤ max_days

### Sizing
- Base size: fixed ($100–$500)
- Scale by:
  - edge strength
  - liquidity

### Throttles
- Max orders / minute
- Max capital deployed
- Max per market

---

## 8. Experiment Design (Critical)

### Decision Window
- Run from `t0 → t0 + X hours`
- Only decisions during this window count

### Holding Window
- Positions held until resolution (or forced exit rule)

### Cohorts
- Start new cohort every N hours (e.g. 12h)
- Track independently

---

## 9. Evaluation Metrics

### Per Trade
- Entry price
- Final outcome
- Edge
- Execution drag

### Per Cohort
- Mean edge
- Brier score
- % profitable decisions
- Capital lock-up duration

---

## 10. Prompt Pack (for LLM-assisted analysis)

### Market Analysis Prompt
```
You are a probability analyst.
Given:
- market description
- current implied probability
- order book metrics
Estimate:
- fair probability
- main uncertainty factors
- risk of dispute or ambiguity
Output JSON only.
```

### Post-Mortem Prompt
```
Given a resolved market and prior prediction:
- Was the prediction calibrated?
- Was the loss due to bad probability or execution?
Return structured analysis.
```

### Strategy Critique Prompt
```
Given cohort results:
- identify failure modes
- suggest stricter filters
- do NOT propose leverage or higher risk
```

---

## 11. What This Is NOT
- Not a high-frequency bot
- Not a guaranteed income system
- Not optimized for short-term PnL

## 12. What This Enables
- Truth-aware trading
- Probability research
- Transferable forecasting skill
- Extension beyond Polymarket

---

**Design principle:**
> If it cannot be measured honestly, it does not exist.

