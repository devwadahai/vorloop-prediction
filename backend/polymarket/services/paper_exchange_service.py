"""
Paper Exchange Service - Simulates order matching and execution
"""
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from loguru import logger

from ..models.market import OrderBook, TokenSide
from ..models.order import Order, OrderSide, OrderType, OrderStatus, QueueMode, Fill
from ..models.position import Position, Account


@dataclass
class ExchangeConfig:
    """Configuration for paper exchange."""
    fee_rate: float = 0.001  # 0.1% fee per trade
    slippage_model: str = "realistic"  # "none", "fixed", "realistic"
    fixed_slippage_bps: float = 5.0  # For fixed slippage model
    partial_fills: bool = True
    queue_priority: str = "fifo"  # "fifo", "pro_rata"


@dataclass
class ExecutionResult:
    """Result of an order execution attempt."""
    success: bool
    order: Order
    fills: List[Fill]
    message: str
    avg_price: Optional[float] = None
    total_size: float = 0.0
    total_fee: float = 0.0
    slippage_bps: float = 0.0


class PaperExchangeService:
    """
    Simulates a trading exchange for paper trading.
    
    Features:
    - Market and limit order execution
    - Realistic order book matching
    - Slippage modeling
    - Fee calculation
    - Position and balance management
    """
    
    def __init__(self, config: Optional[ExchangeConfig] = None):
        self.config = config or ExchangeConfig()
        
        # Accounts by account_id
        self.accounts: Dict[str, Account] = {}
        
        # All orders (for history)
        self.order_history: List[Order] = []
        
        # Active resting orders by token_id
        self.resting_orders: Dict[str, List[Order]] = {}
    
    def create_account(self, initial_balance: float = 10000.0) -> Account:
        """Create a new paper trading account."""
        account = Account(
            account_id=str(uuid.uuid4()),
            balance=initial_balance,
            initial_balance=initial_balance,
        )
        self.accounts[account.account_id] = account
        logger.info(f"Created account {account.account_id} with ${initial_balance:,.2f}")
        return account
    
    def get_account(self, account_id: str) -> Optional[Account]:
        """Get account by ID."""
        return self.accounts.get(account_id)
    
    def submit_order(
        self,
        account_id: str,
        order: Order,
        order_book: OrderBook,
        market_id: str,
        token_side: TokenSide,
    ) -> ExecutionResult:
        """
        Submit an order for execution.
        
        Args:
            account_id: Account placing the order
            order: The order to execute
            order_book: Current order book for the token
            market_id: Market ID for position tracking
            token_side: YES or NO side of the token
        
        Returns:
            ExecutionResult with fill details
        """
        account = self.accounts.get(account_id)
        if not account:
            return ExecutionResult(
                success=False,
                order=order,
                fills=[],
                message="Account not found",
            )
        
        # Validate order
        validation_error = self._validate_order(account, order, order_book)
        if validation_error:
            order.status = OrderStatus.REJECTED
            return ExecutionResult(
                success=False,
                order=order,
                fills=[],
                message=validation_error,
            )
        
        # Execute based on order type
        if order.order_type == OrderType.MARKET:
            result = self._execute_market_order(account, order, order_book, market_id, token_side)
        else:
            result = self._execute_limit_order(account, order, order_book, market_id, token_side)
        
        # Record in history
        self.order_history.append(order)
        account.orders[order.order_id] = order
        
        return result
    
    def _validate_order(self, account: Account, order: Order, order_book: OrderBook) -> Optional[str]:
        """Validate an order before execution."""
        # Check balance for buy orders
        if order.side == OrderSide.BUY:
            # Estimate max cost (size * worst case price)
            if order.order_type == OrderType.MARKET:
                # Use worst ask price
                if not order_book.asks:
                    return "No liquidity on ask side"
                max_price = order_book.asks[-1].price if order_book.asks else 1.0
            else:
                max_price = order.price
            
            max_cost = order.size * max_price * (1 + self.config.fee_rate)
            if max_cost > account.balance:
                return f"Insufficient balance: need ${max_cost:.2f}, have ${account.balance:.2f}"
        
        # Check position for sell orders
        elif order.side == OrderSide.SELL:
            position = account.get_position(order.token_id)
            if not position or position.quantity < order.size:
                available = position.quantity if position else 0
                return f"Insufficient position: need {order.size}, have {available}"
        
        return None
    
    def _execute_market_order(
        self,
        account: Account,
        order: Order,
        order_book: OrderBook,
        market_id: str,
        token_side: TokenSide,
    ) -> ExecutionResult:
        """Execute a market order by walking the book."""
        book = order_book.asks if order.side == OrderSide.BUY else order_book.bids
        
        if not book:
            order.status = OrderStatus.REJECTED
            return ExecutionResult(
                success=False,
                order=order,
                fills=[],
                message="No liquidity available",
            )
        
        # Walk the book
        fills = []
        remaining = order.size
        total_cost = 0.0
        total_fee = 0.0
        
        for level in book:
            if remaining <= 0:
                break
            
            fill_size = min(remaining, level.size)
            fill_price = level.price
            
            # Apply slippage
            if self.config.slippage_model == "fixed":
                slippage = self.config.fixed_slippage_bps / 10000
                if order.side == OrderSide.BUY:
                    fill_price *= (1 + slippage)
                else:
                    fill_price *= (1 - slippage)
            
            # Calculate fee
            fill_fee = fill_size * fill_price * self.config.fee_rate
            
            # Create fill
            fill = Fill(
                fill_id=str(uuid.uuid4()),
                price=fill_price,
                size=fill_size,
                fee=fill_fee,
            )
            fills.append(fill)
            order.add_fill(fill_price, fill_size, fill_fee)
            
            total_cost += fill_size * fill_price
            total_fee += fill_fee
            remaining -= fill_size
            
            if not self.config.partial_fills:
                break
        
        if not fills:
            order.status = OrderStatus.REJECTED
            return ExecutionResult(
                success=False,
                order=order,
                fills=[],
                message="Could not fill any quantity",
            )
        
        # Update account
        avg_price = total_cost / order.filled if order.filled > 0 else 0
        self._update_account_from_fill(account, order, avg_price, total_cost, total_fee, market_id, token_side)
        
        # Calculate slippage
        reference_price = book[0].price if book else avg_price
        slippage_bps = abs(avg_price - reference_price) / reference_price * 10000 if reference_price else 0
        
        return ExecutionResult(
            success=True,
            order=order,
            fills=fills,
            message=f"Filled {order.filled} @ avg ${avg_price:.4f}",
            avg_price=avg_price,
            total_size=order.filled,
            total_fee=total_fee,
            slippage_bps=slippage_bps,
        )
    
    def _execute_limit_order(
        self,
        account: Account,
        order: Order,
        order_book: OrderBook,
        market_id: str,
        token_side: TokenSide,
    ) -> ExecutionResult:
        """Execute a limit order."""
        # Check if order is marketable (crosses the spread)
        is_marketable = False
        if order.side == OrderSide.BUY and order_book.best_ask:
            is_marketable = order.price >= order_book.best_ask
        elif order.side == OrderSide.SELL and order_book.best_bid:
            is_marketable = order.price <= order_book.best_bid
        
        if is_marketable:
            # Execute like a market order up to limit price
            return self._execute_marketable_limit(account, order, order_book, market_id, token_side)
        else:
            # Rest the order (for paper trading, we'll simulate immediate fill based on queue mode)
            return self._rest_limit_order(account, order, order_book, market_id, token_side)
    
    def _execute_marketable_limit(
        self,
        account: Account,
        order: Order,
        order_book: OrderBook,
        market_id: str,
        token_side: TokenSide,
    ) -> ExecutionResult:
        """Execute a marketable limit order."""
        book = order_book.asks if order.side == OrderSide.BUY else order_book.bids
        
        fills = []
        remaining = order.size
        total_cost = 0.0
        total_fee = 0.0
        
        for level in book:
            if remaining <= 0:
                break
            
            # Check price limit
            if order.side == OrderSide.BUY and level.price > order.price:
                break
            if order.side == OrderSide.SELL and level.price < order.price:
                break
            
            fill_size = min(remaining, level.size)
            fill_price = level.price
            fill_fee = fill_size * fill_price * self.config.fee_rate
            
            fill = Fill(
                fill_id=str(uuid.uuid4()),
                price=fill_price,
                size=fill_size,
                fee=fill_fee,
            )
            fills.append(fill)
            order.add_fill(fill_price, fill_size, fill_fee)
            
            total_cost += fill_size * fill_price
            total_fee += fill_fee
            remaining -= fill_size
        
        if fills:
            avg_price = total_cost / order.filled if order.filled > 0 else 0
            self._update_account_from_fill(account, order, avg_price, total_cost, total_fee, market_id, token_side)
            
            return ExecutionResult(
                success=True,
                order=order,
                fills=fills,
                message=f"Filled {order.filled} @ avg ${avg_price:.4f}",
                avg_price=avg_price,
                total_size=order.filled,
                total_fee=total_fee,
            )
        
        # If no fills, rest the remaining
        return self._rest_limit_order(account, order, order_book, market_id, token_side)
    
    def _rest_limit_order(
        self,
        account: Account,
        order: Order,
        order_book: OrderBook,
        market_id: str,
        token_side: TokenSide,
    ) -> ExecutionResult:
        """
        Rest a limit order on the book.
        
        In paper trading, we simulate fills based on queue mode:
        - CONSERVATIVE: Assume we're last in queue, only fill if price trades through
        - NEUTRAL: Assume we get filled when price reaches our level
        """
        # For now, we'll add to resting orders and return success
        if order.token_id not in self.resting_orders:
            self.resting_orders[order.token_id] = []
        
        self.resting_orders[order.token_id].append(order)
        
        return ExecutionResult(
            success=True,
            order=order,
            fills=[],
            message=f"Order resting @ ${order.price:.4f}",
        )
    
    def _update_account_from_fill(
        self,
        account: Account,
        order: Order,
        avg_price: float,
        total_cost: float,
        total_fee: float,
        market_id: str,
        token_side: TokenSide,
    ):
        """Update account balance and positions after a fill."""
        if order.side == OrderSide.BUY:
            # Deduct cost from balance
            account.balance -= (total_cost + total_fee)
            
            # Add to position
            position = account.get_or_create_position(order.token_id, market_id, token_side)
            position.add_quantity(order.filled, avg_price, total_fee)
            
        else:  # SELL
            # Add proceeds to balance
            account.balance += (total_cost - total_fee)
            
            # Reduce position
            position = account.get_position(order.token_id)
            if position:
                pnl = position.reduce_quantity(order.filled, avg_price, total_fee)
                if pnl > 0:
                    account.winning_trades += 1
        
        account.total_trades += 1
        account.total_fees_paid += total_fee
    
    def cancel_order(self, account_id: str, order_id: str) -> bool:
        """Cancel a resting order."""
        account = self.accounts.get(account_id)
        if not account:
            return False
        
        order = account.orders.get(order_id)
        if not order or not order.is_active:
            return False
        
        order.cancel()
        
        # Remove from resting orders
        for token_id, orders in self.resting_orders.items():
            self.resting_orders[token_id] = [o for o in orders if o.order_id != order_id]
        
        logger.info(f"Canceled order {order_id}")
        return True
    
    def resolve_positions(
        self,
        account_id: str,
        market_id: str,
        outcome: TokenSide,
    ) -> Tuple[float, float]:
        """
        Resolve positions for a market when it settles.
        
        Returns:
            (total_pnl, total_quantity_resolved)
        """
        account = self.accounts.get(account_id)
        if not account:
            return (0.0, 0.0)
        
        total_pnl = 0.0
        total_quantity = 0.0
        
        for position in account.positions.values():
            if position.market_id == market_id and position.is_open:
                pnl = position.resolve(outcome)
                total_pnl += pnl
                total_quantity += position.quantity
                
                # Add settlement to balance
                if position.side == outcome:
                    account.balance += position.quantity  # $1 per winning token
                
                logger.info(
                    f"Resolved position {position.token_id}: "
                    f"outcome={outcome.value}, pnl=${pnl:.2f}"
                )
        
        return (total_pnl, total_quantity)
    
    def get_open_positions(self, account_id: str) -> List[Position]:
        """Get all open positions for an account."""
        account = self.accounts.get(account_id)
        if not account:
            return []
        return [p for p in account.positions.values() if p.is_open]
    
    def get_position_value(
        self,
        account_id: str,
        mark_prices: Dict[str, float],
    ) -> float:
        """Calculate total value of open positions."""
        account = self.accounts.get(account_id)
        if not account:
            return 0.0
        
        total = 0.0
        for position in account.positions.values():
            if position.is_open and position.token_id in mark_prices:
                total += position.quantity * mark_prices[position.token_id]
        
        return total

