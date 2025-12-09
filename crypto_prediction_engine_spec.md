# Crypto Prediction Engine — Full Specification & Master Prompt

This document defines the full system specification for building a next-generation crypto prediction terminal that surpasses TradingView. It includes architecture, components, UI layout, required data sources, model pipeline, API definitions, and master prompts for generating code via AI agents.

---

# 1. SYSTEM OVERVIEW

A specialized **crypto prediction cockpit** that:
- Shows price candles + market microstructure
- Displays **probabilistic future cones** (1h, 4h, 8h, 24h)
- Merges CEX, on-chain, and derivatives data
- Explains *why* the model predicts something
- Provides backtest + replay mode
- Is modular and AI-agent-friendly

---

# 2. CORE FEATURES

## 2.1 Price Chart (Main Panel)
- High-performance candlestick chart (TradingView-quality or better)
- Prediction cone projected into the future
  - Center line = expected path
  - Upper/lower band = 1σ / 2σ
- Liquidation clusters (heat bands)
- Support/resistance auto-detected
- Spot–perp basis overlay
- Volume profile & regular volume

## 2.2 Future Prediction Panel
Shows predictions such as:
- `P(up): 0.63`
- `P(down): 0.37`
- Expected move: `+0.8%`
- Expected volatility: `1.5%`
- Confidence score: `medium/high`
- Regime tag (trending, chop, high vol, panic)

## 2.3 Market Structure Layers
- OI (Open Interest)
- Funding rate
- Liquidations per bar (long/short)
- CVD (Cumulative Volume Delta)
- Whale inflows/outflows
- Stablecoin netflows

All aligned on the same time-axis.

## 2.4 AI Explanation Layer
When hovering any bar:
- Shows what signals changed
- Shows what the model believed at that moment
- Shows reason breakdown:
  - Funding skew
  - CVD shift
  - Liq cluster imbalance
  - OI expansion/contraction

## 2.5 Replay & Backtest
- Select a past date → rewinds the chart
- Model replays predictions as if in real-time
- Shows accuracy vs actual market movement
- Shows ideal entry/exit points
- Shows strategy performance

---

# 3. SYSTEM ARCHITECTURE

## 3.1 Frontend
- **React + TypeScript**
- **lightweight-charts** (TradingView library) or custom WebGL renderer
- State management: Zustand / Recoil
- WebSockets for live updates
- Components:
  - PriceChart
  - PredictionConeOverlay
  - LiquidationBands
  - OIPanel
  - FundingPanel
  - CVDPanel
  - SidePredictionPanel
  - BacktestTimeline
  - AIExplanationPanel

## 3.2 Backend
- Python FastAPI
- Services:
  - `/predict` → returns probabilities + cone + expected vol
  - `/explain` → model reasoning + feature contributions
  - `/market-data` → OHLCV, order book depth, OI, funding, liqs
  - `/backtest` → runs historical simulation
- Real-time pipeline: WebSockets for streaming data

## 3.3 Model Layer
### Version 1 (quant-focused)
- LightGBM classifier → direction prediction
- LightGBM regressor → magnitude
- GARCH → volatility
- Regime classifier using rules + ML

### Version 2 (AI-enhanced)
- Temporal Fusion Transformer
- LSTM/TCN for time series
- Ensemble of quant + neural models

---

# 4. DATA PIPELINE

## 4.1 CEX Data
- OHLCV from Binance/Bybit/Coinbase
- Order book depth snapshots
- Aggressive trades (CVD)

## 4.2 Derivatives
- Funding rate
- OI (Open Interest)
- Liquidation feeds
- Perp–spot basis

## 4.3 On-Chain Data
- Whale transfers
- Exchange inflow/outflow
- Miner sell pressure
- Stablecoin supply changes

All aggregated to 1m, 5m, 15m, 1h intervals.

---

# 5. API SPECIFICATION

### 5.1 `/predict`
Input:
```json
{
  "asset": "BTC",
  "horizon_hours": 4
}
```
Output:
```json
{
  "p_up": 0.63,
  "p_down": 0.37,
  "expected_move": 0.008,
  "volatility": 0.015,
  "cone": [ {"t": "...", "upper": "...", "lower": "...", "mid": "..." } ],
  "confidence": "high",
  "regime": "trend-up"
}
```

### 5.2 `/explain`
Output includes feature contributions & reasoning.

### 5.3 `/market-data`
Returns everything needed to render chart + ML features.

### 5.4 `/backtest`
Runs strategy + returns PnL, Sharpe, trades, drawdown.

---

# 6. MASTER PROMPT FOR AI AGENTS

Use this prompt to instruct a coding agent to generate components:

```
You are the lead engineer tasked with building a complete crypto prediction terminal.
Follow the specification exactly. Produce modular, clean, production-grade code.

Your tasks:
1. Build a React + TypeScript frontend using lightweight-charts.
2. Implement PriceChart, PredictionConeOverlay, LiquidationBands, and SidePredictionPanel.
3. Build Python FastAPI backend with endpoints /predict, /market-data, /explain, /backtest.
4. Implement LightGBM-based models for direction + magnitude and GARCH for volatility.
5. Create a real-time WebSocket pipeline for price and market structure updates.
6. Implement a replay/backtest engine.
7. Provide docker-compose setup for the entire system.
8. Use clean folder structure, SOLID principles, and fully typed code.

Always output code in separate modules and ensure testability.
```

---

# 7. FOLDER STRUCTURE

```
/crypto-terminal
  /frontend
    /src
      /components
      /charts
      /panels
      /state
      /utils
  /backend
    /api
    /models
    /signals
    /services
    /data
  /docker
  /scripts
```

---

# 8. FEATURE ENGINEERING PIPELINE

## 8.1 Price-Based Features
| Feature | Description | Window |
|---------|-------------|--------|
| `returns_5m` | 5-minute log returns | 5m |
| `returns_15m` | 15-minute log returns | 15m |
| `returns_1h` | 1-hour log returns | 1h |
| `returns_4h` | 4-hour log returns | 4h |
| `returns_24h` | 24-hour log returns | 24h |
| `volatility_1h` | Rolling std of 5m returns | 1h |
| `volatility_24h` | Rolling std of 1h returns | 24h |
| `high_low_range` | (high - low) / close | per bar |
| `close_position` | (close - low) / (high - low) | per bar |

## 8.2 Technical Indicators
| Feature | Description | Parameters |
|---------|-------------|------------|
| `rsi_14` | Relative Strength Index | period=14 |
| `rsi_7` | Fast RSI | period=7 |
| `macd_signal` | MACD histogram | 12, 26, 9 |
| `bb_position` | Position within Bollinger Bands | period=20, std=2 |
| `ema_cross` | EMA 9/21 cross signal | 9, 21 |
| `vwap_deviation` | Price deviation from VWAP | session-based |

## 8.3 Microstructure Features
| Feature | Description | Source |
|---------|-------------|--------|
| `bid_ask_imbalance` | (bid_vol - ask_vol) / total | Order book |
| `trade_flow_imbalance` | Buy vs sell aggressive trades | Trade tape |
| `cvd_5m` | Cumulative volume delta | Trade tape |
| `cvd_1h` | Hourly CVD momentum | Trade tape |
| `large_trade_ratio` | % of volume from >$100k trades | Trade tape |
| `order_book_slope` | Depth asymmetry at 0.5%, 1%, 2% | Order book |

## 8.4 Derivatives Features
| Feature | Description | Source |
|---------|-------------|--------|
| `funding_rate` | Current perpetual funding | Binance/Bybit |
| `funding_zscore` | Funding z-score (30-day) | Calculated |
| `oi_change_1h` | Open interest delta | Exchange |
| `oi_change_24h` | 24h OI change | Exchange |
| `long_short_ratio` | Trader positioning ratio | Exchange |
| `basis_annualized` | Perp-spot basis annualized | Calculated |
| `liq_imbalance_1h` | Long vs short liquidations | Exchange |

## 8.5 On-Chain Features
| Feature | Description | Source |
|---------|-------------|--------|
| `exchange_netflow_1h` | Net BTC flow to exchanges | Glassnode/CryptoQuant |
| `exchange_netflow_24h` | 24h exchange netflow | Glassnode/CryptoQuant |
| `whale_transactions` | Count of >1000 BTC moves | Whale Alert |
| `miner_outflow` | Miner wallet outflows | Glassnode |
| `stablecoin_supply_change` | USDT/USDC supply delta | On-chain |
| `nvt_signal` | Network Value to Transactions | Glassnode |

## 8.6 Cross-Asset Features
| Feature | Description | Source |
|---------|-------------|--------|
| `btc_dominance` | BTC market cap % | CoinGecko |
| `btc_dominance_change` | 24h dominance delta | CoinGecko |
| `eth_btc_ratio` | ETH/BTC price ratio | Exchange |
| `dxy_inverse` | Dollar index correlation | TradingView |
| `sp500_correlation` | Rolling BTC-SPX corr | Yahoo Finance |
| `gold_correlation` | Rolling BTC-Gold corr | Yahoo Finance |

## 8.7 Sentiment Features
| Feature | Description | Source |
|---------|-------------|--------|
| `fear_greed_index` | Crypto Fear & Greed | Alternative.me |
| `social_volume` | Twitter/Reddit mentions | LunarCrush |
| `funding_sentiment` | Aggregated funding across exchanges | Multiple |
| `google_trends` | "Bitcoin" search interest | Google Trends |

---

# 9. DATA SOURCES & API REFERENCE

## 9.1 Primary Data Sources

| Source | Data Type | Rate Limit | Cost | Latency |
|--------|-----------|------------|------|---------|
| **Binance** | OHLCV, OI, Funding, Trades | 1200 req/min | Free | <100ms |
| **Bybit** | OHLCV, OI, Funding, Liqs | 120 req/min | Free | <100ms |
| **Coinbase** | OHLCV, Order Book | 10 req/sec | Free | <50ms |
| **CryptoQuant** | On-chain, Exchange flows | 100 req/day | $99/mo | ~5min delay |
| **Glassnode** | On-chain metrics | 1000 req/day | $29-$799/mo | ~10min delay |
| **Coinglass** | Aggregated derivatives | 100 req/min | Free tier | <1min |

## 9.2 API Endpoints Reference

### Binance Futures
```
GET /fapi/v1/klines          # OHLCV candles
GET /fapi/v1/openInterest    # Current OI
GET /fapi/v1/fundingRate     # Funding history
GET /fapi/v1/allForceOrders  # Liquidations
WS  wss://fstream.binance.com/ws/<symbol>@kline_1m
WS  wss://fstream.binance.com/ws/<symbol>@forceOrder
```

### Bybit
```
GET /v5/market/kline         # OHLCV candles
GET /v5/market/open-interest # Open interest
GET /v5/market/funding/history
WS  wss://stream.bybit.com/v5/public/linear
```

## 9.3 Fallback Strategy
| Primary | Fallback | Tertiary |
|---------|----------|----------|
| Binance | Bybit | OKX |
| CryptoQuant | Glassnode | IntoTheBlock |
| Coinglass | Self-calculated | None |

---

# 10. MODEL TRAINING & DEPLOYMENT

## 10.1 Training Pipeline

```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐
│ Raw Data    │───▶│ Feature Eng  │───▶│ Feature     │
│ Ingestion   │    │ Pipeline     │    │ Store       │
└─────────────┘    └──────────────┘    └─────────────┘
                                              │
                                              ▼
┌─────────────┐    ┌──────────────┐    ┌─────────────┐
│ Model       │◀───│ Walk-Forward │◀───│ Training    │
│ Registry    │    │ Validation   │    │ Dataset     │
└─────────────┘    └──────────────┘    └─────────────┘
```

## 10.2 Validation Strategy
- **Walk-Forward Validation**: 30-day training window, 7-day test window
- **Purge Gap**: 24 hours between train/test to prevent leakage
- **Embargo Period**: 6 hours after each trade for fair evaluation
- **Cross-Validation Folds**: 5 expanding window folds

## 10.3 Model Versioning
```yaml
model_version: "v1.2.3"
training_date: "2024-01-15"
training_window: "2023-07-01 to 2024-01-14"
validation_metrics:
  accuracy: 0.58
  precision_up: 0.61
  recall_up: 0.55
  sharpe_ratio: 1.45
  max_drawdown: -0.12
features_used: 47
hyperparameters:
  lgb_num_leaves: 31
  lgb_learning_rate: 0.05
  lgb_n_estimators: 500
```

## 10.4 Retraining Schedule
| Model | Frequency | Trigger | Fallback |
|-------|-----------|---------|----------|
| Direction Classifier | Daily @ 00:00 UTC | Scheduled | Use previous model |
| Magnitude Regressor | Daily @ 00:30 UTC | Scheduled | Use previous model |
| Volatility (GARCH) | Hourly | Rolling | Exponential smoothing |
| Regime Classifier | Weekly | Scheduled + drift detection | Rule-based classifier |

## 10.5 A/B Testing Framework
```python
class ModelABTest:
    champion_model: str  # Current production model
    challenger_model: str  # New candidate
    traffic_split: float = 0.1  # 10% to challenger
    min_samples: int = 1000
    significance_level: float = 0.05
    primary_metric: str = "sharpe_ratio"
```

---

# 11. PREDICTION CONE METHODOLOGY

## 11.1 Cone Generation Algorithm

```python
def generate_prediction_cone(
    current_price: float,
    expected_return: float,
    volatility: float,
    horizon_hours: int,
    n_simulations: int = 10000
) -> PredictionCone:
    """
    Monte Carlo simulation for prediction cone.
    Uses GBM with regime-adjusted parameters.
    """
    dt = 1 / 24  # hourly steps
    steps = horizon_hours
    
    # Simulate paths
    paths = np.zeros((n_simulations, steps + 1))
    paths[:, 0] = current_price
    
    for t in range(1, steps + 1):
        z = np.random.standard_normal(n_simulations)
        drift = (expected_return - 0.5 * volatility**2) * dt
        diffusion = volatility * np.sqrt(dt) * z
        paths[:, t] = paths[:, t-1] * np.exp(drift + diffusion)
    
    # Calculate percentiles
    return PredictionCone(
        timestamps=[...],
        mid=np.median(paths, axis=0),
        upper_1sigma=np.percentile(paths, 84.1, axis=0),
        lower_1sigma=np.percentile(paths, 15.9, axis=0),
        upper_2sigma=np.percentile(paths, 97.7, axis=0),
        lower_2sigma=np.percentile(paths, 2.3, axis=0),
    )
```

## 11.2 Regime-Adjusted Parameters
| Regime | Vol Multiplier | Drift Adjustment | Cone Width |
|--------|----------------|------------------|------------|
| Low Vol | 0.7x | 0 | Narrow |
| Normal | 1.0x | 0 | Standard |
| High Vol | 1.5x | 0 | Wide |
| Trending Up | 1.0x | +0.5σ | Standard |
| Trending Down | 1.0x | -0.5σ | Standard |
| Panic | 2.0x | -1.0σ | Very Wide |

## 11.3 Cone Calibration
- Backtest cone coverage: target 68% within 1σ, 95% within 2σ
- Weekly recalibration of volatility scaling factors
- Dynamic adjustment based on recent prediction accuracy

---

# 12. BACKTESTING ENGINE

## 12.1 Backtest Architecture

```python
class BacktestEngine:
    def __init__(self, config: BacktestConfig):
        self.data_loader = HistoricalDataLoader()
        self.model = PredictionModel()
        self.portfolio = Portfolio(initial_capital=config.capital)
        self.execution_model = ExecutionModel(
            slippage_bps=config.slippage_bps,
            commission_bps=config.commission_bps
        )
    
    def run(self, start_date: str, end_date: str) -> BacktestResult:
        for timestamp in self.data_loader.iterate(start_date, end_date):
            # Get prediction as of this timestamp (no look-ahead)
            prediction = self.model.predict_at(timestamp)
            
            # Generate signal
            signal = self.strategy.generate_signal(prediction)
            
            # Execute with realistic slippage
            if signal:
                self.execution_model.execute(signal, self.portfolio)
            
            # Update portfolio MTM
            self.portfolio.mark_to_market(timestamp)
        
        return self.compute_metrics()
```

## 12.2 Execution Model
| Parameter | Default | Range |
|-----------|---------|-------|
| Slippage (market) | 5 bps | 2-10 bps |
| Slippage (limit) | 0 bps | 0-2 bps |
| Fill probability (limit) | 70% | 50-90% |
| Commission | 4 bps | 2-10 bps |
| Funding cost | Actual | From exchange |

## 12.3 Performance Metrics
```python
@dataclass
class BacktestResult:
    total_return: float
    annualized_return: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    max_drawdown_duration: timedelta
    win_rate: float
    profit_factor: float
    avg_trade_duration: timedelta
    total_trades: int
    long_trades: int
    short_trades: int
    exposure_time: float  # % of time in market
    
    # Benchmark comparison
    buy_hold_return: float
    alpha: float
    beta: float
    information_ratio: float
```

## 12.4 Walk-Forward Optimization
```
Train Window: 90 days
Test Window: 30 days
Step: 30 days

Period 1: Train [Jan-Mar] → Test [Apr]
Period 2: Train [Feb-Apr] → Test [May]
Period 3: Train [Mar-May] → Test [Jun]
...
```

---

# 13. INFRASTRUCTURE & DEPLOYMENT

## 13.1 System Architecture

```
                    ┌─────────────────────────────────────┐
                    │           Load Balancer             │
                    │           (Nginx/Traefik)           │
                    └─────────────┬───────────────────────┘
                                  │
          ┌───────────────────────┼───────────────────────┐
          │                       │                       │
          ▼                       ▼                       ▼
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│   Frontend      │   │   API Server    │   │   WebSocket     │
│   (React SPA)   │   │   (FastAPI)     │   │   Server        │
│   Port: 3000    │   │   Port: 8000    │   │   Port: 8001    │
└─────────────────┘   └────────┬────────┘   └────────┬────────┘
                               │                     │
                    ┌──────────┴─────────────────────┴──────────┐
                    │                                           │
          ┌─────────▼─────────┐                    ┌────────────▼────────────┐
          │      Redis        │                    │      TimescaleDB        │
          │   (Cache/Pub-Sub) │                    │   (Time Series Data)    │
          │   Port: 6379      │                    │   Port: 5432            │
          └───────────────────┘                    └─────────────────────────┘
                    │
          ┌─────────▼─────────┐
          │   Celery Workers  │
          │ (Async Tasks)     │
          └───────────────────┘
```

## 13.2 Container Specifications

```yaml
# docker-compose.yml structure
services:
  frontend:
    build: ./frontend
    ports: ["3000:3000"]
    environment:
      - REACT_APP_API_URL=http://api:8000
      - REACT_APP_WS_URL=ws://ws:8001
  
  api:
    build: ./backend
    ports: ["8000:8000"]
    environment:
      - DATABASE_URL=postgresql://...
      - REDIS_URL=redis://redis:6379
    depends_on: [db, redis]
  
  ws:
    build: ./backend
    command: python -m uvicorn ws_server:app --port 8001
    ports: ["8001:8001"]
  
  worker:
    build: ./backend
    command: celery -A tasks worker --loglevel=info
    depends_on: [redis, db]
  
  scheduler:
    build: ./backend
    command: celery -A tasks beat --loglevel=info
  
  db:
    image: timescale/timescaledb:latest-pg14
    volumes: [db_data:/var/lib/postgresql/data]
  
  redis:
    image: redis:7-alpine
    volumes: [redis_data:/data]
```

## 13.3 Resource Requirements

| Service | CPU | Memory | Storage |
|---------|-----|--------|---------|
| Frontend | 0.5 | 512MB | 100MB |
| API Server | 2 | 2GB | 500MB |
| WebSocket | 1 | 1GB | 100MB |
| Celery Worker | 2 | 4GB | 1GB |
| TimescaleDB | 4 | 8GB | 100GB+ |
| Redis | 1 | 2GB | 10GB |

## 13.4 Monitoring Stack

```yaml
monitoring:
  prometheus:
    image: prom/prometheus
    ports: ["9090:9090"]
  
  grafana:
    image: grafana/grafana
    ports: ["3001:3000"]
    volumes: [./grafana/dashboards:/etc/grafana/provisioning/dashboards]
  
  alertmanager:
    image: prom/alertmanager
    ports: ["9093:9093"]
```

### Key Metrics to Monitor
| Metric | Alert Threshold | Severity |
|--------|-----------------|----------|
| API latency p99 | >500ms | Warning |
| API latency p99 | >2000ms | Critical |
| WebSocket connections | >10000 | Warning |
| Prediction accuracy (24h) | <50% | Warning |
| Model drift score | >0.3 | Warning |
| Data freshness | >5min stale | Critical |
| Error rate | >1% | Warning |
| Error rate | >5% | Critical |

---

# 14. RISK CONTROLS & CIRCUIT BREAKERS

## 14.1 Model Risk Controls

```python
class RiskController:
    def __init__(self):
        self.max_volatility = 0.15  # 15% daily vol
        self.min_confidence = 0.55
        self.max_consecutive_losses = 5
        self.circuit_breaker_triggered = False
    
    def should_generate_signal(self, prediction: Prediction) -> bool:
        # Check volatility regime
        if prediction.volatility > self.max_volatility:
            logger.warning("High vol regime - reducing signal strength")
            return False
        
        # Check confidence threshold
        if prediction.confidence < self.min_confidence:
            return False
        
        # Check for circuit breaker
        if self.circuit_breaker_triggered:
            return False
        
        return True
    
    def check_circuit_breaker(self, recent_trades: List[Trade]):
        consecutive_losses = count_consecutive_losses(recent_trades)
        if consecutive_losses >= self.max_consecutive_losses:
            self.trigger_circuit_breaker()
```

## 14.2 Circuit Breaker Conditions
| Condition | Action | Duration |
|-----------|--------|----------|
| 5 consecutive losses | Pause signals | 4 hours |
| Daily drawdown >5% | Reduce position size 50% | End of day |
| Flash crash (>10% in 1h) | Halt all signals | 2 hours |
| API errors >10% | Fallback to conservative | Until resolved |
| Data staleness >5min | Mark predictions as stale | Until fresh |

## 14.3 Position Sizing

```python
def calculate_position_size(
    prediction: Prediction,
    portfolio: Portfolio,
    risk_params: RiskParams
) -> float:
    # Kelly Criterion with half-sizing
    edge = prediction.p_up - 0.5 if prediction.p_up > 0.5 else 0.5 - prediction.p_up
    odds = prediction.expected_move / prediction.volatility
    kelly_fraction = (edge * odds - (1 - edge)) / odds
    half_kelly = kelly_fraction / 2
    
    # Volatility adjustment
    vol_scalar = risk_params.target_vol / prediction.volatility
    
    # Max position cap
    position_pct = min(half_kelly * vol_scalar, risk_params.max_position_pct)
    
    return portfolio.equity * position_pct
```

---

# 15. SECURITY & AUTHENTICATION

## 15.1 Authentication Flow

```
┌──────────┐    ┌──────────┐    ┌──────────┐
│  Client  │───▶│  Auth0/  │───▶│  API     │
│          │◀───│  Clerk   │◀───│  Server  │
└──────────┘    └──────────┘    └──────────┘
     │                               │
     │         JWT Token             │
     └───────────────────────────────┘
```

## 15.2 API Security
- **Authentication**: JWT tokens with 1-hour expiry
- **Rate Limiting**: 100 req/min per user, 1000 req/min per IP
- **Input Validation**: Pydantic models with strict typing
- **CORS**: Whitelist production domains only
- **HTTPS**: TLS 1.3 required

## 15.3 Secrets Management
```yaml
# .env.example
DATABASE_URL=postgresql://user:pass@localhost:5432/crypto
REDIS_URL=redis://localhost:6379
BINANCE_API_KEY=your_key
BINANCE_API_SECRET=your_secret
JWT_SECRET=your_jwt_secret
SENTRY_DSN=https://...
```

---

# 16. PERFORMANCE REQUIREMENTS

## 16.1 Frontend Performance
| Metric | Target | Measurement |
|--------|--------|-------------|
| Initial load | <2s | Lighthouse |
| Chart render (1K candles) | <100ms | Performance API |
| Chart render (10K candles) | <500ms | Performance API |
| Prediction update | <50ms | Performance API |
| WebSocket reconnect | <1s | Manual test |

## 16.2 Backend Performance
| Endpoint | p50 | p95 | p99 |
|----------|-----|-----|-----|
| `/predict` | <50ms | <100ms | <200ms |
| `/market-data` | <30ms | <80ms | <150ms |
| `/explain` | <100ms | <200ms | <400ms |
| `/backtest` | <5s | <15s | <30s |

## 16.3 Data Freshness
| Data Type | Max Staleness |
|-----------|---------------|
| Price (OHLCV) | 5 seconds |
| Funding rate | 1 minute |
| Open interest | 1 minute |
| Liquidations | 10 seconds |
| On-chain data | 10 minutes |

---

# 17. ERROR HANDLING & EDGE CASES

## 17.1 API Error Responses
```json
{
  "error": {
    "code": "PREDICTION_UNAVAILABLE",
    "message": "Prediction model temporarily unavailable",
    "details": {
      "reason": "model_retraining",
      "retry_after_seconds": 300
    }
  },
  "fallback": {
    "regime": "unknown",
    "confidence": "low",
    "recommendation": "wait"
  }
}
```

## 17.2 Edge Cases to Handle
| Scenario | Handling |
|----------|----------|
| Exchange API down | Switch to fallback exchange |
| Extreme volatility (>5σ) | Widen cones, reduce confidence |
| Low liquidity | Mark predictions as unreliable |
| Market closed (holidays) | Show last known state, disable trading signals |
| Model prediction failure | Return last valid prediction with stale flag |
| WebSocket disconnect | Auto-reconnect with exponential backoff |

---

# 18. TESTING STRATEGY

## 18.1 Test Coverage Requirements
| Layer | Coverage Target | Focus Areas |
|-------|-----------------|-------------|
| Unit Tests | >80% | Feature engineering, model logic |
| Integration Tests | >70% | API endpoints, data pipeline |
| E2E Tests | Critical paths | Chart rendering, predictions |

## 18.2 Model Testing
```python
class ModelTestSuite:
    def test_no_look_ahead_bias(self):
        """Ensure features use only past data."""
        pass
    
    def test_prediction_distribution(self):
        """Verify predictions are calibrated."""
        pass
    
    def test_regime_detection(self):
        """Test regime classification accuracy."""
        pass
    
    def test_cone_coverage(self):
        """Verify 68% of outcomes fall within 1σ."""
        pass
```

## 18.3 Load Testing
```yaml
# k6 load test config
scenarios:
  constant_load:
    executor: constant-vus
    vus: 100
    duration: 5m
  
  spike_test:
    executor: ramping-vus
    startVUs: 10
    stages:
      - duration: 1m, target: 500
      - duration: 2m, target: 500
      - duration: 1m, target: 10
```

---

# 19. ROADMAP & MILESTONES

## Phase 1: MVP (Weeks 1-3)
- [ ] Basic price chart with lightweight-charts
- [ ] Simple LightGBM prediction model
- [ ] `/predict` and `/market-data` endpoints
- [ ] Funding rate and OI overlays
- [ ] Docker development setup

## Phase 2: Core Features (Weeks 4-6)
- [ ] Prediction cone visualization
- [ ] Liquidation heatmap
- [ ] CVD panel
- [ ] Real-time WebSocket updates
- [ ] Basic backtesting

## Phase 3: Advanced (Weeks 7-9)
- [ ] AI explanation layer
- [ ] Replay mode
- [ ] On-chain data integration
- [ ] Advanced backtest analytics
- [ ] Mobile responsive design

## Phase 4: Production (Weeks 10-12)
- [ ] Authentication & user accounts
- [ ] Alerting system
- [ ] Multi-asset support
- [ ] Performance optimization
- [ ] Monitoring & observability

---

# 20. APPENDIX

## 20.1 Glossary
| Term | Definition |
|------|------------|
| **CVD** | Cumulative Volume Delta - net aggressive buying vs selling |
| **OI** | Open Interest - total outstanding derivative contracts |
| **Funding Rate** | Periodic payment between long/short perpetual traders |
| **Liquidation** | Forced closing of leveraged position |
| **Basis** | Price difference between spot and perpetual |
| **GARCH** | Generalized Autoregressive Conditional Heteroskedasticity |
| **Regime** | Market state (trending, ranging, high-vol, etc.) |

## 20.2 References
- TradingView Lightweight Charts: https://github.com/tradingview/lightweight-charts
- LightGBM Documentation: https://lightgbm.readthedocs.io/
- Binance API: https://binance-docs.github.io/apidocs/
- Temporal Fusion Transformers: https://arxiv.org/abs/1912.09363
- Walk-Forward Optimization: https://www.quantstart.com/articles/walk-forward-optimization/
