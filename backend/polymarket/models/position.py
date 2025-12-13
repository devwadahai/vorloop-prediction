"""
Position and Account Models
"""
from datetime import datetime
from typing import Optional, List
from dataclasses import dataclass, field
from enum import Enum

from .market import TokenSide
from .order import Order, Fill


class MarkToMarketMode(str, Enum):
    """How to value open positions."""
    CONSERVATIVE = "CONSERVATIVE"  # Best bid for longs, best ask for shorts
    NEUTRAL = "NEUTRAL"            # Mid price
    AGGRESSIVE = "AGGRESSIVE"      # Last trade price


@dataclass
class Position:
    """A position in a token."""
    token_id: str
    market_id: str
    side: TokenSide  # YES or NO
    
    # Position details
    quantity: float = 0.0
    avg_price: float = 0.0
    
    # P&L tracking
    realized_pnl: float = 0.0
    total_fees: float = 0.0
    
    # Timestamps
    opened_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    
    # For tracking entries
    entries: List[dict] = field(default_factory=list)
    
    def __post_init__(self):
        if isinstance(self.side, str):
            self.side = TokenSide(self.side)
    
    def add_quantity(self, quantity: float, price: float, fee: float):
        """Add to position (buy more)."""
        if self.quantity == 0:
            self.opened_at = datetime.utcnow()
        
        # Update average price
        old_value = self.quantity * self.avg_price
        new_value = quantity * price
        self.quantity += quantity
        self.avg_price = (old_value + new_value) / self.quantity if self.quantity > 0 else 0
        
        self.total_fees += fee
        self.entries.append({
            'quantity': quantity,
            'price': price,
            'fee': fee,
            'timestamp': datetime.utcnow().isoformat() + 'Z',
        })
    
    def reduce_quantity(self, quantity: float, price: float, fee: float) -> float:
        """
        Reduce position (sell).
        Returns realized P&L for this reduction.
        """
        if quantity > self.quantity:
            quantity = self.quantity
        
        # Calculate P&L
        # For YES tokens: profit if sold higher than avg_price
        # (Simplified: we always track as if we're long the token)
        pnl = (price - self.avg_price) * quantity - fee
        
        self.quantity -= quantity
        self.realized_pnl += pnl
        self.total_fees += fee
        
        if self.quantity <= 0:
            self.quantity = 0
            self.closed_at = datetime.utcnow()
        
        return pnl
    
    def get_unrealized_pnl(self, mark_price: float) -> float:
        """Calculate unrealized P&L at a given mark price."""
        if self.quantity == 0:
            return 0.0
        return (mark_price - self.avg_price) * self.quantity
    
    def get_total_pnl(self, mark_price: float) -> float:
        """Total P&L including realized and unrealized."""
        return self.realized_pnl + self.get_unrealized_pnl(mark_price)
    
    def resolve(self, outcome: TokenSide) -> float:
        """
        Resolve position based on market outcome.
        Returns final P&L.
        
        - If we hold YES and outcome is YES: each token worth $1
        - If we hold YES and outcome is NO: each token worth $0
        """
        if self.quantity == 0:
            return self.realized_pnl
        
        # Determine settlement price
        if self.side == outcome:
            settlement_price = 1.0  # Winner
        else:
            settlement_price = 0.0  # Loser
        
        # Final P&L
        final_pnl = (settlement_price - self.avg_price) * self.quantity
        self.realized_pnl += final_pnl
        self.quantity = 0
        self.closed_at = datetime.utcnow()
        
        return self.realized_pnl
    
    @property
    def is_open(self) -> bool:
        return self.quantity > 0
    
    @property
    def cost_basis(self) -> float:
        """Total cost of position."""
        return self.quantity * self.avg_price
    
    def to_dict(self, mark_price: Optional[float] = None) -> dict:
        result = {
            'token_id': self.token_id,
            'market_id': self.market_id,
            'side': self.side.value,
            'quantity': self.quantity,
            'avg_price': self.avg_price,
            'cost_basis': self.cost_basis,
            'realized_pnl': self.realized_pnl,
            'total_fees': self.total_fees,
            'is_open': self.is_open,
            'opened_at': self.opened_at.isoformat() + 'Z' if self.opened_at else None,
            'closed_at': self.closed_at.isoformat() + 'Z' if self.closed_at else None,
            'num_entries': len(self.entries),
        }
        
        if mark_price is not None:
            result['mark_price'] = mark_price
            result['unrealized_pnl'] = self.get_unrealized_pnl(mark_price)
            result['total_pnl'] = self.get_total_pnl(mark_price)
        
        return result


@dataclass
class Account:
    """Paper trading account."""
    account_id: str
    balance: float = 10000.0  # Starting balance
    initial_balance: float = 10000.0
    
    # Positions by token_id
    positions: dict = field(default_factory=dict)  # token_id -> Position
    
    # Order tracking
    orders: dict = field(default_factory=dict)  # order_id -> Order
    
    # Stats
    total_trades: int = 0
    winning_trades: int = 0
    total_fees_paid: float = 0.0
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def get_position(self, token_id: str) -> Optional[Position]:
        """Get position for a token."""
        return self.positions.get(token_id)
    
    def get_or_create_position(self, token_id: str, market_id: str, side: TokenSide) -> Position:
        """Get existing position or create new one."""
        if token_id not in self.positions:
            self.positions[token_id] = Position(
                token_id=token_id,
                market_id=market_id,
                side=side,
            )
        return self.positions[token_id]
    
    @property
    def total_pnl(self) -> float:
        """Total realized P&L across all positions."""
        return sum(p.realized_pnl for p in self.positions.values())
    
    @property
    def equity(self) -> float:
        """Current account equity (balance + realized P&L)."""
        return self.balance + self.total_pnl
    
    def get_equity_with_unrealized(self, mark_prices: dict) -> float:
        """Get equity including unrealized P&L."""
        equity = self.balance
        for token_id, position in self.positions.items():
            if position.is_open and token_id in mark_prices:
                equity += position.get_total_pnl(mark_prices[token_id])
            else:
                equity += position.realized_pnl
        return equity
    
    def to_dict(self, mark_prices: Optional[dict] = None) -> dict:
        return {
            'account_id': self.account_id,
            'balance': self.balance,
            'initial_balance': self.initial_balance,
            'total_pnl': self.total_pnl,
            'equity': self.equity,
            'equity_with_unrealized': self.get_equity_with_unrealized(mark_prices or {}),
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'win_rate': (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0,
            'total_fees_paid': self.total_fees_paid,
            'open_positions': len([p for p in self.positions.values() if p.is_open]),
            'created_at': self.created_at.isoformat() + 'Z',
        }

