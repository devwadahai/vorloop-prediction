"""
API Routes for Polymarket Paper Trading Simulator
"""
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
from loguru import logger

router = APIRouter(prefix="/polymarket", tags=["polymarket"])


# ============================================================================
# Request/Response Models
# ============================================================================

class MarketResponse(BaseModel):
    """Market information."""
    market_id: str
    slug: str
    question: str
    description: str
    category: str
    end_time: str
    resolution_status: str
    volume_24h: float
    liquidity: float
    time_to_resolution_hours: float


class OrderBookResponse(BaseModel):
    """Order book snapshot."""
    token_id: str
    bids: List[List[float]]
    asks: List[List[float]]
    best_bid: Optional[float]
    best_ask: Optional[float]
    mid_price: Optional[float]
    spread: Optional[float]
    spread_bps: Optional[float]
    bid_depth: float
    ask_depth: float
    imbalance: float


class ProbabilityResponse(BaseModel):
    """Probability estimate."""
    market_id: str
    token_id: str
    fair_prob: float
    market_prob: float
    edge: float
    edge_pct: float
    expected_value: float
    kelly_fraction: float
    confidence: float
    risk_flags: List[str]
    risk_score: float
    is_tradeable: bool
    suggested_side: Optional[str]


class OrderRequest(BaseModel):
    """Order submission request."""
    token_id: str
    side: str = Field(description="BUY or SELL")
    size: float
    price: Optional[float] = None
    order_type: str = Field(default="LIMIT", description="LIMIT or MARKET")


class OrderResponse(BaseModel):
    """Order result."""
    order_id: str
    token_id: str
    side: str
    price: float
    size: float
    filled: float
    remaining: float
    status: str
    avg_fill_price: Optional[float]
    total_fees: float


class AccountResponse(BaseModel):
    """Account information."""
    account_id: str
    balance: float
    initial_balance: float
    total_pnl: float
    equity: float
    total_trades: int
    win_rate: float
    total_fees_paid: float
    open_positions: int


class PositionResponse(BaseModel):
    """Position information."""
    token_id: str
    market_id: str
    side: str
    quantity: float
    avg_price: float
    cost_basis: float
    unrealized_pnl: Optional[float]
    realized_pnl: float


class StatsResponse(BaseModel):
    """Evaluation statistics."""
    total_decisions: int
    resolved_decisions: int
    pending_decisions: int
    brier_score: float
    mean_edge: float
    edge_preservation_ratio: float
    mean_execution_drag_bps: float
    total_pnl: float
    win_rate: float
    prediction_accuracy: float


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/markets", response_model=List[MarketResponse])
async def list_markets(
    req: Request,
    category: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
):
    """
    List active markets from Polymarket.
    """
    try:
        market_service = req.app.state.pm_market_service
        
        # Fetch fresh data
        await market_service.fetch_markets()
        
        markets = list(market_service.markets.values())
        
        # Filter by category
        if category:
            markets = [m for m in markets if m.category.value == category]
        
        # Sort by volume
        markets.sort(key=lambda m: m.volume_24h, reverse=True)
        
        return [m.to_dict() for m in markets[:limit]]
        
    except Exception as e:
        logger.error(f"Error listing markets: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/markets/{market_id}", response_model=MarketResponse)
async def get_market(req: Request, market_id: str):
    """
    Get details for a specific market.
    """
    market_service = req.app.state.pm_market_service
    market = market_service.get_market(market_id)
    
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    
    return market.to_dict()


@router.get("/orderbook/{token_id}", response_model=OrderBookResponse)
async def get_orderbook(req: Request, token_id: str):
    """
    Get order book for a token.
    """
    try:
        market_service = req.app.state.pm_market_service
        
        # Fetch fresh order book
        order_book = await market_service.fetch_order_book(token_id)
        
        if not order_book:
            raise HTTPException(status_code=404, detail="Order book not found")
        
        return order_book.to_dict()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching order book: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/probability/{market_id}", response_model=ProbabilityResponse)
async def get_probability(req: Request, market_id: str):
    """
    Get probability estimate for a market.
    """
    try:
        market_service = req.app.state.pm_market_service
        prob_service = req.app.state.pm_probability_service
        
        market = market_service.get_market(market_id)
        if not market:
            raise HTTPException(status_code=404, detail="Market not found")
        
        if not market.yes_token:
            raise HTTPException(status_code=400, detail="Market has no YES token")
        
        # Get order book
        order_book = await market_service.fetch_order_book(market.yes_token.token_id)
        if not order_book:
            raise HTTPException(status_code=400, detail="Could not fetch order book")
        
        # Generate estimate
        estimate = prob_service.estimate(market, order_book)
        
        return estimate.to_dict()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting probability: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/opportunities", response_model=List[ProbabilityResponse])
async def get_opportunities(
    req: Request,
    min_edge: float = Query(default=1.5, description="Minimum edge %"),
    limit: int = Query(default=10, ge=1, le=50),
):
    """
    Get tradeable opportunities across all markets.
    """
    try:
        market_service = req.app.state.pm_market_service
        prob_service = req.app.state.pm_probability_service
        
        # Fetch markets and order books
        await market_service.fetch_markets()
        
        opportunities = []
        for market in list(market_service.markets.values())[:50]:  # Limit scan
            if not market.yes_token:
                continue
            
            try:
                order_book = await market_service.fetch_order_book(market.yes_token.token_id)
                if order_book:
                    estimate = prob_service.estimate(market, order_book)
                    if estimate.is_tradeable and abs(estimate.edge_pct) >= min_edge:
                        opportunities.append(estimate.to_dict())
            except Exception:
                continue
        
        # Sort by edge
        opportunities.sort(key=lambda x: abs(x['edge']), reverse=True)
        
        return opportunities[:limit]
        
    except Exception as e:
        logger.error(f"Error getting opportunities: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/account", response_model=AccountResponse)
async def create_account(
    req: Request,
    initial_balance: float = Query(default=10000.0),
):
    """
    Create a new paper trading account.
    """
    try:
        exchange = req.app.state.pm_exchange_service
        account = exchange.create_account(initial_balance)
        
        # Store as current account
        req.app.state.pm_current_account = account.account_id
        
        return account.to_dict()
        
    except Exception as e:
        logger.error(f"Error creating account: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/account", response_model=AccountResponse)
async def get_account(req: Request):
    """
    Get current account information.
    """
    exchange = req.app.state.pm_exchange_service
    account_id = getattr(req.app.state, 'pm_current_account', None)
    
    if not account_id:
        raise HTTPException(status_code=404, detail="No account created")
    
    account = exchange.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    # Get mark prices for unrealized P&L
    market_service = req.app.state.pm_market_service
    mark_prices = {
        token_id: ob.mid_price
        for token_id, ob in market_service.order_books.items()
        if ob.mid_price
    }
    
    return account.to_dict(mark_prices)


@router.post("/order", response_model=OrderResponse)
async def submit_order(req: Request, order_req: OrderRequest):
    """
    Submit an order.
    """
    try:
        exchange = req.app.state.pm_exchange_service
        market_service = req.app.state.pm_market_service
        eval_service = req.app.state.pm_evaluation_service
        
        account_id = getattr(req.app.state, 'pm_current_account', None)
        if not account_id:
            raise HTTPException(status_code=400, detail="No account created")
        
        # Get token and order book
        token = market_service.get_token(order_req.token_id)
        if not token:
            raise HTTPException(status_code=404, detail="Token not found")
        
        order_book = await market_service.fetch_order_book(order_req.token_id)
        if not order_book:
            raise HTTPException(status_code=400, detail="Could not fetch order book")
        
        # Get market
        market = market_service.get_market(token.market_id)
        if not market:
            raise HTTPException(status_code=404, detail="Market not found")
        
        # Create order
        from ..models.order import Order, OrderSide, OrderType
        
        if order_req.order_type == "MARKET":
            order = Order.create_market_order(
                token_id=order_req.token_id,
                side=OrderSide(order_req.side),
                size=order_req.size,
            )
        else:
            order = Order.create_limit_order(
                token_id=order_req.token_id,
                side=OrderSide(order_req.side),
                price=order_req.price or order_book.mid_price or 0.5,
                size=order_req.size,
            )
        
        # Execute
        result = exchange.submit_order(
            account_id=account_id,
            order=order,
            order_book=order_book,
            market_id=token.market_id,
            token_side=token.side,
        )
        
        if not result.success:
            raise HTTPException(status_code=400, detail=result.message)
        
        # Log decision for evaluation
        prob_service = req.app.state.pm_probability_service
        estimate = prob_service.estimate(market, order_book)
        
        eval_service.log_decision(
            market=market,
            estimate=estimate,
            side=order_req.side,
            size=order_req.size,
            entry_price=order_req.price or order_book.mid_price or 0.5,
            fill_price=result.avg_price,
        )
        
        return result.order.to_dict()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting order: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/positions", response_model=List[PositionResponse])
async def get_positions(req: Request):
    """
    Get open positions.
    """
    exchange = req.app.state.pm_exchange_service
    market_service = req.app.state.pm_market_service
    
    account_id = getattr(req.app.state, 'pm_current_account', None)
    if not account_id:
        return []
    
    positions = exchange.get_open_positions(account_id)
    
    # Add mark prices
    result = []
    for p in positions:
        mark_price = market_service.get_mid_price(p.token_id)
        result.append(p.to_dict(mark_price))
    
    return result


@router.get("/stats", response_model=StatsResponse)
async def get_stats(req: Request):
    """
    Get evaluation statistics.
    """
    eval_service = req.app.state.pm_evaluation_service
    return eval_service.get_overall_stats()


@router.get("/history")
async def get_history(
    req: Request,
    limit: int = Query(default=50, ge=1, le=200),
):
    """
    Get decision history.
    """
    eval_service = req.app.state.pm_evaluation_service
    return {
        "history": eval_service.get_history(limit),
        "pending": len(eval_service.get_pending_resolutions()),
    }


@router.post("/reset")
async def reset_simulation(req: Request):
    """
    Reset the paper trading simulation.
    """
    try:
        # Create fresh services
        from ..services import PaperExchangeService, EvaluationService
        
        req.app.state.pm_exchange_service = PaperExchangeService()
        req.app.state.pm_evaluation_service = EvaluationService()
        req.app.state.pm_current_account = None
        
        return {"status": "reset", "message": "Simulation reset successfully"}
        
    except Exception as e:
        logger.error(f"Error resetting simulation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

