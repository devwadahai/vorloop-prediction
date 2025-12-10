"""
API Routes for Crypto Prediction Engine
"""
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
from loguru import logger

router = APIRouter()


# ============================================================================
# Request/Response Models
# ============================================================================

class PredictionRequest(BaseModel):
    """Request model for prediction endpoint."""
    asset: str = Field(default="BTC", description="Asset symbol (BTC, ETH, etc.)")
    horizon_minutes: int = Field(default=5, ge=1, le=60, description="Prediction horizon in minutes")


class ConePoint(BaseModel):
    """Single point in the prediction cone."""
    timestamp: datetime
    mid: float
    upper_1sigma: float
    lower_1sigma: float
    upper_2sigma: float
    lower_2sigma: float


class PredictionResponse(BaseModel):
    """Response model for prediction endpoint."""
    asset: str
    timestamp: datetime
    horizon_minutes: int
    p_up: float = Field(ge=0, le=1)
    p_down: float = Field(ge=0, le=1)
    expected_move: float
    volatility: float
    confidence: str = Field(description="low, medium, high")
    regime: str = Field(description="trend-up, trend-down, ranging, high-vol, panic")
    cone: List[ConePoint]


class MarketDataRequest(BaseModel):
    """Request model for market data endpoint."""
    asset: str = Field(default="BTC")
    interval: str = Field(default="1h", description="Candle interval: 1m, 5m, 15m, 1h, 4h, 1d")
    limit: int = Field(default=500, ge=1, le=2000)


class OHLCV(BaseModel):
    """Single OHLCV candle."""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class MarketStructure(BaseModel):
    """Market structure data point."""
    timestamp: datetime
    funding_rate: Optional[float] = None
    open_interest: Optional[float] = None
    oi_change_pct: Optional[float] = None
    long_liquidations: Optional[float] = None
    short_liquidations: Optional[float] = None
    cvd: Optional[float] = None


class MarketDataResponse(BaseModel):
    """Response model for market data endpoint."""
    asset: str
    interval: str
    candles: List[OHLCV]
    market_structure: List[MarketStructure]


class ExplainRequest(BaseModel):
    """Request for explanation of a prediction."""
    asset: str = Field(default="BTC")
    timestamp: Optional[datetime] = None  # None = current


class FeatureContribution(BaseModel):
    """Feature contribution to prediction."""
    feature: str
    value: float
    contribution: float
    direction: str  # bullish, bearish, neutral


class ExplainResponse(BaseModel):
    """Explanation of model prediction."""
    asset: str
    timestamp: datetime
    prediction_summary: str
    top_bullish_factors: List[FeatureContribution]
    top_bearish_factors: List[FeatureContribution]
    regime_explanation: str
    confidence_factors: List[str]


class BacktestRequest(BaseModel):
    """Request for backtesting."""
    asset: str = Field(default="BTC")
    start_date: datetime
    end_date: datetime
    strategy: str = Field(default="momentum", description="momentum, mean-reversion, ml-signal")
    initial_capital: float = Field(default=10000.0)
    position_size_pct: float = Field(default=0.1, ge=0.01, le=1.0)


class Trade(BaseModel):
    """Single trade in backtest."""
    entry_time: datetime
    exit_time: datetime
    direction: str  # long, short
    entry_price: float
    exit_price: float
    pnl: float
    pnl_pct: float


class BacktestResponse(BaseModel):
    """Response from backtest."""
    asset: str
    start_date: datetime
    end_date: datetime
    strategy: str
    
    # Performance metrics
    total_return: float
    annualized_return: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    total_trades: int
    
    # Benchmark
    buy_hold_return: float
    alpha: float
    
    # Trade list
    trades: List[Trade]
    
    # Equity curve (sampled)
    equity_curve: List[dict]


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/predict", response_model=PredictionResponse)
async def predict(request: PredictionRequest, req: Request):
    """
    Generate price prediction with probability cone.
    
    Returns probability of up/down move, expected magnitude,
    volatility estimate, and prediction cone for visualization.
    """
    try:
        model_service = req.app.state.model_service
        data_service = req.app.state.data_service
        tracker = req.app.state.prediction_tracker
        
        # Get latest market data
        market_data = await data_service.get_latest_data(request.asset)
        
        # Generate prediction
        prediction = await model_service.predict(
            asset=request.asset,
            horizon_minutes=request.horizon_minutes,
            market_data=market_data
        )
        
        # Log prediction for tracking (only if horizon is reasonable)
        if request.horizon_minutes <= 10:
            tracker.log_prediction(
                asset=request.asset,
                entry_price=market_data["price"],
                p_up=prediction["p_up"],
                expected_move=prediction["expected_move"],
                horizon_minutes=request.horizon_minutes,
                regime=prediction["regime"],
                confidence=prediction["confidence"],
            )
        
        return prediction
        
    except Exception as e:
        logger.error(f"Prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/market-data", response_model=MarketDataResponse)
async def get_market_data(request: MarketDataRequest, req: Request):
    """
    Get OHLCV candles and market structure data.
    
    Includes funding rate, open interest, liquidations, and CVD.
    """
    try:
        data_service = req.app.state.data_service
        
        data = await data_service.get_historical_data(
            asset=request.asset,
            interval=request.interval,
            limit=request.limit
        )
        
        return data
        
    except Exception as e:
        logger.error(f"Market data error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/explain", response_model=ExplainResponse)
async def explain_prediction(request: ExplainRequest, req: Request):
    """
    Explain the model's prediction.
    
    Shows feature contributions, regime analysis, and confidence factors.
    """
    try:
        model_service = req.app.state.model_service
        data_service = req.app.state.data_service
        
        # Get data at timestamp
        timestamp = request.timestamp or datetime.utcnow()
        market_data = await data_service.get_data_at(request.asset, timestamp)
        
        # Generate explanation
        explanation = await model_service.explain(
            asset=request.asset,
            timestamp=timestamp,
            market_data=market_data
        )
        
        return explanation
        
    except Exception as e:
        logger.error(f"Explain error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/backtest", response_model=BacktestResponse)
async def run_backtest(request: BacktestRequest, req: Request):
    """
    Run historical backtest of prediction strategy.
    
    Returns performance metrics, trade list, and equity curve.
    """
    try:
        model_service = req.app.state.model_service
        data_service = req.app.state.data_service
        
        # Validate date range
        if request.end_date <= request.start_date:
            raise HTTPException(
                status_code=400,
                detail="end_date must be after start_date"
            )
        
        if (request.end_date - request.start_date).days > 365:
            raise HTTPException(
                status_code=400,
                detail="Backtest period cannot exceed 365 days"
            )
        
        # Run backtest
        result = await model_service.backtest(
            asset=request.asset,
            start_date=request.start_date,
            end_date=request.end_date,
            strategy=request.strategy,
            initial_capital=request.initial_capital,
            position_size_pct=request.position_size_pct
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Backtest error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/assets")
async def list_assets():
    """List available assets for prediction."""
    return {
        "assets": [
            {"symbol": "BTC", "name": "Bitcoin", "enabled": True},
            {"symbol": "ETH", "name": "Ethereum", "enabled": True},
            {"symbol": "SOL", "name": "Solana", "enabled": True},
            {"symbol": "BNB", "name": "Binance Coin", "enabled": True},
            {"symbol": "XRP", "name": "Ripple", "enabled": False},
        ]
    }


@router.get("/model-info")
async def model_info(req: Request):
    """Get current model information."""
    model_service = req.app.state.model_service
    
    return {
        "version": model_service.version,
        "last_trained": model_service.last_trained,
        "features_count": model_service.features_count,
        "training_window_days": 90,
        "validation_metrics": model_service.validation_metrics,
    }


@router.get("/prediction-history")
async def prediction_history(
    req: Request,
    limit: int = Query(default=50, ge=1, le=200),
    asset: Optional[str] = Query(default=None)
):
    """
    Get validated prediction history with results.
    Shows past predictions and whether they were correct.
    """
    tracker = req.app.state.prediction_tracker
    history = tracker.get_history(limit=limit, asset=asset)
    stats = tracker.get_stats()
    
    return {
        "history": history,
        "stats": stats,
    }


@router.get("/prediction-stats")
async def prediction_stats(req: Request):
    """
    Get prediction accuracy statistics.
    """
    tracker = req.app.state.prediction_tracker
    return tracker.get_stats()


@router.get("/pending-predictions")
async def pending_predictions(req: Request):
    """
    Get predictions waiting for validation.
    """
    tracker = req.app.state.prediction_tracker
    return {
        "pending": tracker.get_pending(),
        "count": len(tracker.pending_validations),
    }

