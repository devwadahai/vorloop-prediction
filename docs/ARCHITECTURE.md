# Architecture Overview

## System Design

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND                                │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │  Header  │  │  Chart   │  │ Panels   │  │  Store   │        │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘        │
│       │             │             │             │               │
│       └─────────────┴─────────────┴─────────────┘               │
│                         │                                       │
│                    HTTP/REST                                    │
└─────────────────────────┼───────────────────────────────────────┘
                          │
┌─────────────────────────┼───────────────────────────────────────┐
│                    BACKEND API                                  │
│                         │                                       │
│  ┌──────────────────────┴──────────────────────┐               │
│  │              FastAPI Router                  │               │
│  │  /predict  /market-data  /prediction-stats  │               │
│  └──────────────────────┬──────────────────────┘               │
│                         │                                       │
│  ┌─────────────┬────────┴────────┬─────────────┐               │
│  │             │                 │             │               │
│  ▼             ▼                 ▼             ▼               │
│ ┌───────┐  ┌────────┐  ┌─────────────┐  ┌──────────┐          │
│ │ Data  │  │ Model  │  │ Prediction  │  │  Config  │          │
│ │Service│  │Service │  │  Tracker    │  │          │          │
│ └───┬───┘  └────┬───┘  └──────┬──────┘  └──────────┘          │
│     │           │             │                                │
│     │           │             ▼                                │
│     │           │    ┌─────────────────┐                       │
│     │           │    │ prediction_     │                       │
│     │           │    │ history.json    │                       │
│     │           │    └─────────────────┘                       │
│     │           │                                              │
└─────┼───────────┼──────────────────────────────────────────────┘
      │           │
      ▼           ▼
┌───────────┐  ┌────────────────┐
│  Coinbase │  │ Trained Models │
│  WebSocket│  │   (pkl files)  │
└───────────┘  └────────────────┘
```

## Data Flow

### 1. Market Data Flow

```
Coinbase WebSocket
       │
       ▼
   DataService
   ├── get_latest_data()    → Current price, OHLCV
   ├── get_historical_data() → Candles + Market Structure
   └── calculate_cvd()       → Volume Delta
       │
       ▼
   Frontend Store
       │
       ▼
   Components (Chart, Panels)
```

### 2. Prediction Flow

```
User Request (horizon=5m)
       │
       ▼
   ModelService.predict()
   ├── extract_features()
   ├── fallback_direction()  → Multi-signal analysis
   ├── estimate_volatility()
   ├── detect_regime()
   ├── calculate_confidence()
   └── get_calibration_adjustment() → Adaptive tuning
       │
       ▼
   PredictionTracker.log_prediction()
       │
       ▼
   Response to Frontend
       │
       ├─── After 5 minutes ───┐
       │                       ▼
       │           PredictionTracker._validate_prediction()
       │           ├── Get current price
       │           ├── Compare prediction vs actual
       │           ├── Update accuracy stats
       │           └── Save to JSON
       │
       ▼
   Frontend displays prediction
```

### 3. Paper Trading Flow

```
User clicks LONG/SHORT
       │
       ▼
   SimulationPanel
   ├── Check balance
   ├── Calculate fees
   ├── Create Trade object
   └── Update localStorage
       │
       ▼
   Real-time P&L updates (using current price from store)
       │
       ▼
   User clicks Close
   ├── Calculate final P&L
   ├── Add exit fees
   ├── Update balance
   └── Save to trade history
```

## Component Hierarchy

```
App.tsx
├── Header.tsx
│   ├── Asset selector (BTC/ETH/SOL)
│   ├── Interval selector (1m, 3m, 5m, 10m, 15m, 1h)
│   └── Settings
│
├── PriceChart.tsx
│   ├── Lightweight Charts canvas
│   ├── Candlestick series
│   └── Volume series
│
├── MarketStructurePanel.tsx
│   ├── Funding Rate card
│   ├── Open Interest card
│   └── Volume Delta chart
│
└── Side Panel (tabbed)
    ├── PredictionPanel.tsx
    │   ├── Direction indicator
    │   ├── Probability display
    │   ├── Horizon selector
    │   └── Prediction cone visualization
    │
    ├── PredictionLogPanel.tsx
    │   ├── Accuracy stats
    │   ├── Confidence breakdown
    │   └── Prediction history list
    │
    ├── FeeCalculatorPanel.tsx
    │   ├── Trade size input
    │   ├── Exchange/Market selector
    │   └── Fee comparison table
    │
    └── SimulationPanel.tsx
        ├── Balance display
        ├── Position size controls
        ├── Open position manager
        ├── Trade buttons
        └── Trade history
```

## State Management

### Frontend (Zustand)

```typescript
interface Store {
  // Market Data
  marketData: MarketData | null
  selectedAsset: 'BTC' | 'ETH' | 'SOL'
  selectedInterval: TimeInterval
  
  // Predictions
  prediction: Prediction | null
  horizonMinutes: number
  
  // UI
  isLoading: boolean
  error: string | null
  
  // Actions
  fetchMarketData: () => Promise<void>
  fetchPrediction: () => Promise<void>
  setSelectedAsset: (asset: string) => void
  setSelectedInterval: (interval: TimeInterval) => void
  setHorizonMinutes: (mins: number) => void
}
```

### Backend (Application State)

```python
app.state.data_service      # DataService instance
app.state.model_service     # ModelService instance  
app.state.prediction_tracker # PredictionTracker instance
app.state.tracker_task      # Background validation task
```

## Error Handling

### Frontend

```typescript
// API calls wrapped in try-catch
try {
  await fetchPrediction()
} catch (error) {
  store.setError(error.message)
}

// Loading states
{isLoading && <Spinner />}
{error && <ErrorMessage>{error}</ErrorMessage>}
```

### Backend

```python
@router.post("/predict")
async def predict(request: PredictionRequest, req: Request):
    try:
        # ... prediction logic
    except Exception as e:
        logger.error(f"Prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

## Performance Considerations

### Frontend

1. **Memoization**: `useMemo` for computed values
2. **Polling intervals**: 
   - Market data: 5 seconds
   - Predictions: 60 seconds
3. **localStorage**: Persist simulation state

### Backend

1. **Async/await**: Non-blocking I/O
2. **Background tasks**: Prediction validation
3. **Data caching**: Latest price cached
4. **History limit**: Max 500 predictions stored

