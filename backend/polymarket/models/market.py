"""
Market and Order Book Models for Polymarket
"""
from datetime import datetime
from typing import List, Optional, Literal
from dataclasses import dataclass, field
from enum import Enum


class MarketCategory(str, Enum):
    POLITICS = "politics"
    CRYPTO = "crypto"
    SPORTS = "sports"
    TECH = "tech"
    ECONOMICS = "economics"
    OTHER = "other"


class ResolutionStatus(str, Enum):
    OPEN = "OPEN"
    ENDED = "ENDED"
    PROPOSED = "PROPOSED"
    RESOLVED = "RESOLVED"
    DISPUTED = "DISPUTED"


class TokenSide(str, Enum):
    YES = "YES"
    NO = "NO"


@dataclass
class Token:
    """A tradeable token representing YES or NO outcome."""
    token_id: str
    market_id: str
    side: TokenSide
    tick_size: float = 0.001  # Minimum price increment
    min_size: float = 1.0    # Minimum order size
    
    def __post_init__(self):
        if isinstance(self.side, str):
            self.side = TokenSide(self.side)


@dataclass
class Market:
    """A prediction market event."""
    market_id: str
    slug: str
    question: str
    description: str
    category: MarketCategory
    end_time: datetime
    resolution_status: ResolutionStatus = ResolutionStatus.OPEN
    
    # Tokens for this market
    yes_token: Optional[Token] = None
    no_token: Optional[Token] = None
    
    # Resolution outcome (set when resolved)
    outcome: Optional[TokenSide] = None
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    volume_24h: float = 0.0
    liquidity: float = 0.0
    
    def __post_init__(self):
        if isinstance(self.category, str):
            self.category = MarketCategory(self.category)
        if isinstance(self.resolution_status, str):
            self.resolution_status = ResolutionStatus(self.resolution_status)
    
    @property
    def is_active(self) -> bool:
        return self.resolution_status == ResolutionStatus.OPEN
    
    @property
    def time_to_resolution(self) -> float:
        """Hours until end_time."""
        delta = self.end_time - datetime.utcnow()
        return max(0, delta.total_seconds() / 3600)
    
    def to_dict(self) -> dict:
        return {
            'market_id': self.market_id,
            'slug': self.slug,
            'question': self.question,
            'description': self.description,
            'category': self.category.value,
            'end_time': self.end_time.isoformat() + 'Z',
            'resolution_status': self.resolution_status.value,
            'outcome': self.outcome.value if self.outcome else None,
            'volume_24h': self.volume_24h,
            'liquidity': self.liquidity,
            'time_to_resolution_hours': self.time_to_resolution,
        }


@dataclass
class OrderBookLevel:
    """A single price level in the order book."""
    price: float
    size: float
    
    def to_list(self) -> List[float]:
        return [self.price, self.size]


@dataclass
class OrderBook:
    """L2 Order Book for a token."""
    token_id: str
    bids: List[OrderBookLevel] = field(default_factory=list)  # Buy orders (sorted high to low)
    asks: List[OrderBookLevel] = field(default_factory=list)  # Sell orders (sorted low to high)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def best_bid(self) -> Optional[float]:
        """Highest bid price."""
        return self.bids[0].price if self.bids else None
    
    @property
    def best_ask(self) -> Optional[float]:
        """Lowest ask price."""
        return self.asks[0].price if self.asks else None
    
    @property
    def mid_price(self) -> Optional[float]:
        """Mid price between best bid and ask."""
        if self.best_bid and self.best_ask:
            return (self.best_bid + self.best_ask) / 2
        return self.best_bid or self.best_ask
    
    @property
    def spread(self) -> Optional[float]:
        """Spread in absolute terms."""
        if self.best_bid and self.best_ask:
            return self.best_ask - self.best_bid
        return None
    
    @property
    def spread_bps(self) -> Optional[float]:
        """Spread in basis points."""
        if self.spread and self.mid_price:
            return (self.spread / self.mid_price) * 10000
        return None
    
    @property
    def bid_depth(self) -> float:
        """Total size on bid side."""
        return sum(level.size for level in self.bids)
    
    @property
    def ask_depth(self) -> float:
        """Total size on ask side."""
        return sum(level.size for level in self.asks)
    
    @property
    def imbalance(self) -> float:
        """
        Order book imbalance: (bid_depth - ask_depth) / (bid_depth + ask_depth)
        Positive = more bids (bullish), Negative = more asks (bearish)
        """
        total = self.bid_depth + self.ask_depth
        if total == 0:
            return 0.0
        return (self.bid_depth - self.ask_depth) / total
    
    def get_depth_at_price(self, price: float, side: Literal['bid', 'ask']) -> float:
        """Get cumulative depth up to a price level."""
        levels = self.bids if side == 'bid' else self.asks
        total = 0.0
        for level in levels:
            if side == 'bid' and level.price >= price:
                total += level.size
            elif side == 'ask' and level.price <= price:
                total += level.size
        return total
    
    def simulate_market_order(self, side: Literal['buy', 'sell'], size: float) -> tuple:
        """
        Simulate a market order and return (avg_price, filled_size, remaining).
        """
        book = self.asks if side == 'buy' else self.bids
        filled = 0.0
        cost = 0.0
        remaining = size
        
        for level in book:
            if remaining <= 0:
                break
            fill_size = min(remaining, level.size)
            cost += fill_size * level.price
            filled += fill_size
            remaining -= fill_size
        
        avg_price = cost / filled if filled > 0 else None
        return (avg_price, filled, remaining)
    
    def to_dict(self) -> dict:
        return {
            'token_id': self.token_id,
            'bids': [l.to_list() for l in self.bids],
            'asks': [l.to_list() for l in self.asks],
            'timestamp': self.timestamp.isoformat() + 'Z',
            'best_bid': self.best_bid,
            'best_ask': self.best_ask,
            'mid_price': self.mid_price,
            'spread': self.spread,
            'spread_bps': self.spread_bps,
            'bid_depth': self.bid_depth,
            'ask_depth': self.ask_depth,
            'imbalance': self.imbalance,
        }

