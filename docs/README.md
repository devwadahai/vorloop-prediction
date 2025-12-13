# Crypto Prediction Engine

A real-time cryptocurrency prediction terminal with market structure analysis, prediction tracking, fee calculation, and paper trading simulation.

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Getting Started](#getting-started)
- [API Reference](#api-reference)
- [Prediction Model](#prediction-model)
- [Paper Trading Simulation](#paper-trading-simulation)

---

## Overview

This application provides:

1. **Real-time BTC/ETH/SOL price charts** with multiple timeframe intervals
2. **AI-powered directional predictions** for 1m, 3m, 5m, 10m horizons
3. **Market structure analysis** (Funding Rate, Open Interest, Volume Delta)
4. **Prediction accuracy tracking** with historical validation
5. **Trading fee calculator** for Binance & MEXC
6. **Paper trading simulation** with P&L tracking

### Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | React 18, TypeScript, Vite, TailwindCSS |
| Backend | Python 3.14, FastAPI, uvicorn |
| Charts | Lightweight Charts (TradingView) |
| State | Zustand (frontend), In-memory + JSON (backend) |
| Data Sources | Coinbase (price), Coinglass (derivatives) |

---

## Features

### 🎯 Price Predictions

- **Horizons**: 1m, 3m, 5m, 10m
- **Output**: P(Up) probability, expected move %, volatility estimate
- **Regime Detection**: trend-up, trend-down, ranging, high-vol, panic
- **Confidence Levels**: low, medium, high
- **Adaptive Calibration**: Model adjusts based on recent accuracy

### 📊 Market Structure Analysis

| Metric | Description |
|--------|-------------|
| Funding Rate | Perpetual futures funding (bullish/bearish indicator) |
| Open Interest | Total contracts open (momentum confirmation) |
| Volume Delta (CVD) | Buying vs selling pressure per candle |
| Liquidations | Long/short liquidation data |

### 📈 Prediction Tracking

- Automatic validation after horizon expires
- Accuracy statistics by confidence level
- Persistent history (survives restarts)
- Adaptive model calibration

### 💰 Fee Calculator

Compare trading fees between:
- **Exchanges**: Binance, MEXC
- **Markets**: Spot, Futures
- **Fee Types**: Maker, Taker

### 🎮 Paper Trading Simulation

- Virtual $100K starting balance
- Spot & Futures trading modes
- LONG/SHORT (futures) or BUY/SELL (spot)
- Dollar Cost Averaging (DCA) support
- Real-time P&L with fee calculations
- Trade history persistence (localStorage)

---

## Architecture

```
vorloop-prediction/
├── backend/
│   ├── main.py                 # FastAPI app entry point
│   ├── api/
│   │   ├── routes.py           # REST endpoints
│   │   └── websocket.py        # WebSocket handlers
│   ├── services/
│   │   ├── data_service.py     # Market data fetching
│   │   ├── model_service.py    # Prediction engine
│   │   └── prediction_tracker.py # Accuracy tracking
│   ├── models/
│   │   └── feature_engineering.py
│   └── data/
│       └── prediction_history.json
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx             # Main layout
│   │   ├── components/
│   │   │   ├── Header.tsx      # Asset & interval selectors
│   │   │   ├── PriceChart.tsx  # Main trading chart
│   │   │   └── PredictionCone.tsx
│   │   ├── panels/
│   │   │   ├── PredictionPanel.tsx
│   │   │   ├── PredictionLogPanel.tsx
│   │   │   ├── MarketStructurePanel.tsx
│   │   │   ├── FeeCalculatorPanel.tsx
│   │   │   └── SimulationPanel.tsx
│   │   ├── state/
│   │   │   └── store.ts        # Zustand state
│   │   └── utils/
│   │       ├── api.ts          # API client
│   │       └── format.ts       # Formatting helpers
│   └── index.html
│
└── docs/
    └── README.md               # This file
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- npm or yarn

### Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

### Access

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000/api

---

## API Reference

### Predictions

#### POST `/api/predict`

Generate price prediction.

**Request:**
```json
{
  "asset": "BTC",
  "horizon_minutes": 5
}
```

**Response:**
```json
{
  "asset": "BTC",
  "timestamp": "2025-12-13T09:00:00Z",
  "horizon_minutes": 5,
  "p_up": 0.62,
  "p_down": 0.38,
  "expected_move": 0.0012,
  "volatility": 0.0045,
  "confidence": "medium",
  "regime": "trend-up",
  "cone": [...]
}
```

### Market Data

#### POST `/api/market-data`

Get OHLCV candles and market structure.

**Request:**
```json
{
  "asset": "BTC",
  "interval": "1m",
  "limit": 500
}
```

### Prediction Tracking

#### GET `/api/prediction-stats`

Get accuracy statistics.

**Response:**
```json
{
  "total_predictions": 150,
  "correct_predictions": 98,
  "accuracy_pct": 65.33,
  "by_confidence": {
    "high": { "total": 30, "correct": 22, "accuracy": 73.33 },
    "medium": { "total": 80, "correct": 52, "accuracy": 65.0 },
    "low": { "total": 40, "correct": 24, "accuracy": 60.0 }
  }
}
```

#### GET `/api/prediction-history?limit=50`

Get validated predictions history.

#### GET `/api/pending-predictions`

Get predictions awaiting validation.

---

## Prediction Model

### Signal Weights

| Signal | Weight | Description |
|--------|--------|-------------|
| Momentum | 40% | Price returns normalized by volatility |
| CVD | 25% | Cumulative Volume Delta (buy/sell pressure) |
| Funding Rate | 20% | Contrarian signal from perpetuals |
| OI Change | 15% | Open Interest trend |

### Adaptive Calibration

The model self-adjusts based on recent performance:

1. **High-confidence failing** → Reduce confidence (be humble)
2. **Low-confidence more accurate** → Stay conservative
3. **Medium-confidence accurate** → Slight boost

### Regime Detection

| Regime | Conditions |
|--------|------------|
| `panic` | Returns < -2% and volatility > 3% |
| `high-vol` | Volatility > 4% |
| `trend-up` | P(Up) > 65% or (P(Up) > 55% and returns > 0) |
| `trend-down` | P(Up) < 35% or (P(Up) < 45% and returns < 0) |
| `ranging` | None of the above |

---

## Paper Trading Simulation

### Fee Rates

| Exchange | Spot | Futures |
|----------|------|---------|
| Binance | 0.10% | 0.04% |
| MEXC | 0.10% | 0.02% |

### Features

- **DCA Support**: Add to existing positions at different prices
- **Average Entry**: Automatically calculates weighted average
- **Fee Tracking**: Entry and exit fees calculated separately
- **Net P&L**: Shows gross P&L minus all fees
- **Breakeven Warning**: Alerts when in profit but fees exceed gains

### Persistence

All simulation data is saved to `localStorage`:
- Balance changes
- Open positions
- Trade history
- Statistics

---

## Development

### Environment Variables

Create `.env` in backend:

```env
DEBUG=true
COINBASE_API_KEY=your_key
COINGLASS_API_KEY=your_key
```

### Running Tests

```bash
# Backend
cd backend
pytest tests/

# Frontend
cd frontend
npm test
```

---

## License

MIT License - See LICENSE file for details.

