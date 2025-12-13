"""
Order Models for Paper Exchange
"""
from datetime import datetime
from typing import Optional, List
from dataclasses import dataclass, field
from enum import Enum
import uuid


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    LIMIT = "LIMIT"
    MARKET = "MARKET"


class OrderStatus(str, Enum):
    OPEN = "OPEN"
    PARTIAL = "PARTIAL"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"


class QueueMode(str, Enum):
    """
    Determines how resting limit orders get filled:
    - CONSERVATIVE: Only fill if price trades *through* the level
    - NEUTRAL: Fill when best price crosses our price
    """
    CONSERVATIVE = "CONSERVATIVE"
    NEUTRAL = "NEUTRAL"


@dataclass
class Fill:
    """A single fill event for an order."""
    fill_id: str
    price: float
    size: float
    fee: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> dict:
        return {
            'fill_id': self.fill_id,
            'price': self.price,
            'size': self.size,
            'fee': self.fee,
            'timestamp': self.timestamp.isoformat() + 'Z',
        }


@dataclass
class Order:
    """An order in the paper exchange."""
    order_id: str
    token_id: str
    side: OrderSide
    price: float
    size: float
    order_type: OrderType = OrderType.LIMIT
    queue_mode: QueueMode = QueueMode.NEUTRAL
    status: OrderStatus = OrderStatus.OPEN
    
    # Tracking
    remaining: float = None
    filled: float = 0.0
    avg_fill_price: Optional[float] = None
    fills: List[Fill] = field(default_factory=list)
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    # Fees
    total_fees: float = 0.0
    
    def __post_init__(self):
        if self.remaining is None:
            self.remaining = self.size
        if isinstance(self.side, str):
            self.side = OrderSide(self.side)
        if isinstance(self.order_type, str):
            self.order_type = OrderType(self.order_type)
        if isinstance(self.queue_mode, str):
            self.queue_mode = QueueMode(self.queue_mode)
        if isinstance(self.status, str):
            self.status = OrderStatus(self.status)
    
    @classmethod
    def create_market_order(cls, token_id: str, side: OrderSide, size: float) -> 'Order':
        """Create a market order."""
        return cls(
            order_id=str(uuid.uuid4()),
            token_id=token_id,
            side=side,
            price=0.0,  # Market orders don't have a price
            size=size,
            order_type=OrderType.MARKET,
        )
    
    @classmethod
    def create_limit_order(
        cls, 
        token_id: str, 
        side: OrderSide, 
        price: float, 
        size: float,
        queue_mode: QueueMode = QueueMode.NEUTRAL
    ) -> 'Order':
        """Create a limit order."""
        return cls(
            order_id=str(uuid.uuid4()),
            token_id=token_id,
            side=side,
            price=price,
            size=size,
            order_type=OrderType.LIMIT,
            queue_mode=queue_mode,
        )
    
    def add_fill(self, price: float, size: float, fee: float):
        """Record a fill for this order."""
        fill = Fill(
            fill_id=str(uuid.uuid4()),
            price=price,
            size=size,
            fee=fee,
        )
        self.fills.append(fill)
        
        # Update order state
        old_filled = self.filled
        self.filled += size
        self.remaining -= size
        self.total_fees += fee
        
        # Update average fill price
        if self.avg_fill_price is None:
            self.avg_fill_price = price
        else:
            self.avg_fill_price = (
                (self.avg_fill_price * old_filled + price * size) / self.filled
            )
        
        # Update status
        if self.remaining <= 0:
            self.status = OrderStatus.FILLED
        elif self.filled > 0:
            self.status = OrderStatus.PARTIAL
        
        self.updated_at = datetime.utcnow()
    
    def cancel(self):
        """Cancel the order."""
        if self.status in [OrderStatus.OPEN, OrderStatus.PARTIAL]:
            self.status = OrderStatus.CANCELED
            self.updated_at = datetime.utcnow()
    
    @property
    def is_active(self) -> bool:
        return self.status in [OrderStatus.OPEN, OrderStatus.PARTIAL]
    
    @property
    def is_marketable(self) -> bool:
        """Check if this limit order would cross the spread."""
        return self.order_type == OrderType.MARKET
    
    def to_dict(self) -> dict:
        return {
            'order_id': self.order_id,
            'token_id': self.token_id,
            'side': self.side.value,
            'price': self.price,
            'size': self.size,
            'remaining': self.remaining,
            'filled': self.filled,
            'avg_fill_price': self.avg_fill_price,
            'order_type': self.order_type.value,
            'queue_mode': self.queue_mode.value,
            'status': self.status.value,
            'total_fees': self.total_fees,
            'fills': [f.to_dict() for f in self.fills],
            'created_at': self.created_at.isoformat() + 'Z',
            'updated_at': self.updated_at.isoformat() + 'Z',
        }

