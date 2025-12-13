"""
Strategy Engine - Converts probability signals into order intents
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import uuid
from loguru import logger

from ..models.market import Market, OrderBook, TokenSide
from ..models.order import Order, OrderSide, OrderType, QueueMode
from ..models.probability import ProbabilityEstimate, RiskFlag


class OrderIntent(str, Enum):
    """What the strategy wants to do."""
    BUY_YES = "BUY_YES"
    BUY_NO = "BUY_NO"
    SELL_YES = "SELL_YES"
    SELL_NO = "SELL_NO"
    HOLD = "HOLD"
    CLOSE = "CLOSE"


@dataclass
class StrategySignal:
    """Output from strategy engine."""
    market_id: str
    token_id: str
    intent: OrderIntent
    size: float
    price: Optional[float]  # None for market orders
    order_type: OrderType
    reason: str
    estimate: ProbabilityEstimate
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> dict:
        return {
            'market_id': self.market_id,
            'token_id': self.token_id,
            'intent': self.intent.value,
            'size': self.size,
            'price': self.price,
            'order_type': self.order_type.value,
            'reason': self.reason,
            'timestamp': self.timestamp.isoformat() + 'Z',
        }


@dataclass
class StrategyConfig:
    """Strategy configuration."""
    # Entry thresholds
    min_edge_pct: float = 1.5
    max_spread_ticks: int = 1
    min_depth_multiple: float = 3.0  # Depth must be 3x order size
    max_resolution_days: float = 30.0
    min_resolution_hours: float = 1.0
    
    # Sizing
    base_size: float = 100.0  # Base position size in $
    max_size: float = 500.0
    size_by_edge: bool = True  # Scale size by edge strength
    size_by_liquidity: bool = True  # Scale size by liquidity
    use_kelly: bool = False  # Use Kelly sizing
    kelly_fraction: float = 0.25  # Fraction of Kelly to use
    
    # Throttles
    max_orders_per_minute: int = 5
    max_capital_deployed_pct: float = 50.0  # Max % of balance deployed
    max_per_market: float = 500.0  # Max position per market
    
    # Risk controls
    max_risk_score: float = 0.5
    blocked_risk_flags: List[RiskFlag] = field(default_factory=lambda: [
        RiskFlag.DISPUTE_RISK,
        RiskFlag.LOW_DEPTH,
    ])


class StrategyEngine:
    """
    Converts probability estimates into actionable order signals.
    
    This is a conservative, research-focused strategy:
    - Only trades when edge exceeds threshold
    - Checks liquidity before sizing
    - Respects risk limits
    - Throttles order frequency
    """
    
    def __init__(self, config: Optional[StrategyConfig] = None):
        self.config = config or StrategyConfig()
        
        # Throttle tracking
        self._order_timestamps: List[datetime] = []
        self._positions_by_market: Dict[str, float] = {}
    
    def evaluate(
        self,
        estimate: ProbabilityEstimate,
        market: Market,
        order_book: OrderBook,
        current_balance: float,
        current_position: Optional[float] = None,
    ) -> StrategySignal:
        """
        Evaluate a probability estimate and generate a trading signal.
        
        Args:
            estimate: The probability estimate
            market: Market metadata
            order_book: Current order book
            current_balance: Available balance
            current_position: Current position size (if any)
        
        Returns:
            StrategySignal with intent and sizing
        """
        # Check if we should hold/skip
        skip_reason = self._check_skip_conditions(estimate, market, order_book, current_balance)
        if skip_reason:
            return StrategySignal(
                market_id=market.market_id,
                token_id=estimate.token_id,
                intent=OrderIntent.HOLD,
                size=0,
                price=None,
                order_type=OrderType.LIMIT,
                reason=skip_reason,
                estimate=estimate,
            )
        
        # Determine direction
        if estimate.edge > 0:
            intent = OrderIntent.BUY_YES
            token_side = TokenSide.YES
        else:
            intent = OrderIntent.BUY_NO
            token_side = TokenSide.NO
        
        # Calculate size
        size = self._calculate_size(estimate, order_book, current_balance)
        
        # Determine price and order type
        price, order_type = self._determine_price(estimate, order_book, intent)
        
        reason = (
            f"Edge: {estimate.edge_pct:.2f}%, "
            f"Confidence: {estimate.confidence:.0%}, "
            f"Fair: {estimate.fair_prob:.1%} vs Market: {estimate.market_prob:.1%}"
        )
        
        return StrategySignal(
            market_id=market.market_id,
            token_id=estimate.token_id,
            intent=intent,
            size=size,
            price=price,
            order_type=order_type,
            reason=reason,
            estimate=estimate,
        )
    
    def _check_skip_conditions(
        self,
        estimate: ProbabilityEstimate,
        market: Market,
        order_book: OrderBook,
        current_balance: float,
    ) -> Optional[str]:
        """Check if we should skip trading this opportunity."""
        
        # Check edge threshold
        if abs(estimate.edge_pct) < self.config.min_edge_pct:
            return f"Edge too small: {estimate.edge_pct:.2f}% < {self.config.min_edge_pct}%"
        
        # Check risk score
        if estimate.risk_score > self.config.max_risk_score:
            return f"Risk too high: {estimate.risk_score:.2f}"
        
        # Check blocked risk flags
        for flag in self.config.blocked_risk_flags:
            if flag in estimate.risk_flags:
                return f"Blocked risk flag: {flag.value}"
        
        # Check spread
        if order_book.spread:
            spread_ticks = int(order_book.spread / 0.001)  # Assuming 0.1% tick
            if spread_ticks > self.config.max_spread_ticks:
                return f"Spread too wide: {spread_ticks} ticks"
        
        # Check resolution time
        hours = market.time_to_resolution
        if hours > self.config.max_resolution_days * 24:
            return f"Resolution too far: {hours/24:.1f} days"
        if hours < self.config.min_resolution_hours:
            return f"Resolution too soon: {hours:.1f} hours"
        
        # Check capital limits
        deployed_pct = (1 - current_balance / 10000) * 100  # Assuming 10k starting
        if deployed_pct > self.config.max_capital_deployed_pct:
            return f"Max capital deployed: {deployed_pct:.0f}%"
        
        # Check per-market limit
        current_in_market = self._positions_by_market.get(market.market_id, 0)
        if current_in_market >= self.config.max_per_market:
            return f"Max position in market: ${current_in_market:.0f}"
        
        # Check throttle
        if not self._check_throttle():
            return "Order throttle limit reached"
        
        return None
    
    def _calculate_size(
        self,
        estimate: ProbabilityEstimate,
        order_book: OrderBook,
        current_balance: float,
    ) -> float:
        """Calculate position size."""
        size = self.config.base_size
        
        # Scale by edge
        if self.config.size_by_edge:
            edge_multiple = abs(estimate.edge_pct) / self.config.min_edge_pct
            size *= min(2.0, edge_multiple)  # Max 2x for edge
        
        # Scale by liquidity
        if self.config.size_by_liquidity:
            depth = min(order_book.bid_depth, order_book.ask_depth)
            if depth < size * self.config.min_depth_multiple:
                size = depth / self.config.min_depth_multiple
        
        # Kelly sizing
        if self.config.use_kelly and estimate.kelly_fraction > 0:
            kelly_size = current_balance * estimate.kelly_fraction * self.config.kelly_fraction
            size = min(size, kelly_size)
        
        # Cap at max size
        size = min(size, self.config.max_size)
        
        # Cap at available balance (with buffer)
        size = min(size, current_balance * 0.9)
        
        # Round to reasonable increment
        size = round(size, 0)
        
        return max(10, size)  # Minimum $10
    
    def _determine_price(
        self,
        estimate: ProbabilityEstimate,
        order_book: OrderBook,
        intent: OrderIntent,
    ) -> tuple:
        """Determine order price and type."""
        # For now, use limit orders at best price
        if intent in [OrderIntent.BUY_YES, OrderIntent.BUY_NO]:
            # Join the bid
            price = order_book.best_bid
            if price is None:
                # No bids, use fair value
                price = estimate.fair_prob - 0.01
        else:
            # Join the ask
            price = order_book.best_ask
            if price is None:
                price = estimate.fair_prob + 0.01
        
        # Clamp price
        price = max(0.01, min(0.99, price))
        
        return (price, OrderType.LIMIT)
    
    def _check_throttle(self) -> bool:
        """Check if we're within order rate limits."""
        now = datetime.utcnow()
        cutoff = now - timedelta(minutes=1)
        
        # Clean old timestamps
        self._order_timestamps = [
            ts for ts in self._order_timestamps if ts > cutoff
        ]
        
        if len(self._order_timestamps) >= self.config.max_orders_per_minute:
            return False
        
        self._order_timestamps.append(now)
        return True
    
    def record_position(self, market_id: str, size: float):
        """Record a position for tracking."""
        current = self._positions_by_market.get(market_id, 0)
        self._positions_by_market[market_id] = current + size
    
    def clear_position(self, market_id: str):
        """Clear position tracking for a market."""
        self._positions_by_market.pop(market_id, None)
    
    def create_order(
        self,
        signal: StrategySignal,
        token_id: str,
    ) -> Order:
        """Create an order from a strategy signal."""
        # Determine order side
        if signal.intent in [OrderIntent.BUY_YES, OrderIntent.BUY_NO]:
            side = OrderSide.BUY
        else:
            side = OrderSide.SELL
        
        return Order.create_limit_order(
            token_id=token_id,
            side=side,
            price=signal.price,
            size=signal.size,
            queue_mode=QueueMode.NEUTRAL,
        )

