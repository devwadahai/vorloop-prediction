"""
Market Data Service - Ingests live Polymarket data
"""
import asyncio
import json
from datetime import datetime
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
import aiohttp
from loguru import logger

from ..models.market import Market, Token, OrderBook, OrderBookLevel, MarketCategory, ResolutionStatus, TokenSide


# Polymarket API endpoints
POLYMARKET_API_BASE = "https://clob.polymarket.com"
POLYMARKET_GAMMA_API = "https://gamma-api.polymarket.com"


@dataclass
class MarketDataConfig:
    """Configuration for market data service."""
    api_base: str = POLYMARKET_API_BASE
    gamma_api: str = POLYMARKET_GAMMA_API
    ws_url: str = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
    max_markets: int = 100
    update_interval: float = 5.0  # seconds
    categories: List[str] = None
    
    def __post_init__(self):
        if self.categories is None:
            self.categories = ["crypto", "politics", "sports"]


class MarketDataService:
    """
    Service for ingesting and managing Polymarket data.
    
    Capabilities:
    - Fetch active markets from REST API
    - Subscribe to order book updates via WebSocket
    - Maintain in-memory order books
    - Track market metadata and resolution status
    """
    
    def __init__(self, config: Optional[MarketDataConfig] = None):
        self.config = config or MarketDataConfig()
        
        # In-memory state
        self.markets: Dict[str, Market] = {}
        self.tokens: Dict[str, Token] = {}
        self.order_books: Dict[str, OrderBook] = {}
        
        # WebSocket state
        self._ws_session: Optional[aiohttp.ClientSession] = None
        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self._running = False
        self._subscribed_tokens: set = set()
        
        # Callbacks
        self._on_orderbook_update: Optional[Callable] = None
        self._on_market_update: Optional[Callable] = None
    
    async def start(self):
        """Start the market data service."""
        logger.info("Starting Polymarket Market Data Service...")
        self._running = True
        
        # Create HTTP session
        self._ws_session = aiohttp.ClientSession()
        
        # Initial market fetch
        await self.fetch_markets()
        
        logger.info(f"Loaded {len(self.markets)} markets")
    
    async def stop(self):
        """Stop the market data service."""
        logger.info("Stopping Market Data Service...")
        self._running = False
        
        if self._ws:
            await self._ws.close()
        if self._ws_session:
            await self._ws_session.close()
    
    async def fetch_markets(self, category: Optional[str] = None) -> List[Market]:
        """
        Fetch active markets from Polymarket API.
        """
        try:
            url = f"{self.config.gamma_api}/markets"
            params = {
                "active": "true",
                "closed": "false",
                "limit": self.config.max_markets,
            }
            
            async with self._ws_session.get(url, params=params) as resp:
                if resp.status != 200:
                    logger.error(f"Failed to fetch markets: {resp.status}")
                    return []
                
                data = await resp.json()
                
                markets = []
                for m in data:
                    try:
                        market = self._parse_market(m)
                        if market:
                            self.markets[market.market_id] = market
                            markets.append(market)
                            
                            # Store tokens
                            if market.yes_token:
                                self.tokens[market.yes_token.token_id] = market.yes_token
                            if market.no_token:
                                self.tokens[market.no_token.token_id] = market.no_token
                    except Exception as e:
                        logger.warning(f"Failed to parse market: {e}")
                
                return markets
                
        except Exception as e:
            logger.error(f"Error fetching markets: {e}")
            return []
    
    def _parse_market(self, data: dict) -> Optional[Market]:
        """Parse market data from API response."""
        try:
            # Determine category
            tags = data.get("tags", [])
            category = MarketCategory.OTHER
            for tag in tags:
                tag_lower = tag.lower()
                if "crypto" in tag_lower or "bitcoin" in tag_lower:
                    category = MarketCategory.CRYPTO
                    break
                elif "politic" in tag_lower or "election" in tag_lower:
                    category = MarketCategory.POLITICS
                    break
                elif "sport" in tag_lower:
                    category = MarketCategory.SPORTS
                    break
                elif "tech" in tag_lower:
                    category = MarketCategory.TECH
                    break
            
            # Parse end time
            end_time_str = data.get("endDate") or data.get("end_date_iso")
            if end_time_str:
                end_time = datetime.fromisoformat(end_time_str.replace('Z', '+00:00'))
            else:
                end_time = datetime.utcnow()
            
            # Get tokens
            tokens = data.get("tokens", [])
            yes_token = None
            no_token = None
            
            for t in tokens:
                token = Token(
                    token_id=t.get("token_id", ""),
                    market_id=data.get("condition_id", data.get("id", "")),
                    side=TokenSide.YES if t.get("outcome", "").upper() == "YES" else TokenSide.NO,
                )
                if token.side == TokenSide.YES:
                    yes_token = token
                else:
                    no_token = token
            
            market = Market(
                market_id=data.get("condition_id", data.get("id", "")),
                slug=data.get("slug", ""),
                question=data.get("question", ""),
                description=data.get("description", ""),
                category=category,
                end_time=end_time,
                resolution_status=ResolutionStatus.OPEN if data.get("active") else ResolutionStatus.ENDED,
                yes_token=yes_token,
                no_token=no_token,
                volume_24h=float(data.get("volume24hr", 0) or 0),
                liquidity=float(data.get("liquidity", 0) or 0),
            )
            
            return market
            
        except Exception as e:
            logger.warning(f"Error parsing market: {e}")
            return None
    
    async def fetch_order_book(self, token_id: str) -> Optional[OrderBook]:
        """
        Fetch order book for a token from REST API.
        """
        try:
            url = f"{self.config.api_base}/book"
            params = {"token_id": token_id}
            
            async with self._ws_session.get(url, params=params) as resp:
                if resp.status != 200:
                    logger.warning(f"Failed to fetch order book for {token_id}: {resp.status}")
                    return None
                
                data = await resp.json()
                
                # Parse bids and asks
                bids = [
                    OrderBookLevel(price=float(b["price"]), size=float(b["size"]))
                    for b in data.get("bids", [])
                ]
                asks = [
                    OrderBookLevel(price=float(a["price"]), size=float(a["size"]))
                    for a in data.get("asks", [])
                ]
                
                # Sort: bids high to low, asks low to high
                bids.sort(key=lambda x: x.price, reverse=True)
                asks.sort(key=lambda x: x.price)
                
                order_book = OrderBook(
                    token_id=token_id,
                    bids=bids,
                    asks=asks,
                    timestamp=datetime.utcnow(),
                )
                
                self.order_books[token_id] = order_book
                return order_book
                
        except Exception as e:
            logger.error(f"Error fetching order book: {e}")
            return None
    
    async def subscribe_orderbook(self, token_ids: List[str]):
        """
        Subscribe to order book updates via WebSocket.
        """
        try:
            if not self._ws or self._ws.closed:
                self._ws = await self._ws_session.ws_connect(self.config.ws_url)
                logger.info("Connected to Polymarket WebSocket")
            
            # Subscribe to each token
            for token_id in token_ids:
                if token_id not in self._subscribed_tokens:
                    msg = {
                        "type": "subscribe",
                        "channel": "book",
                        "assets_ids": [token_id],
                    }
                    await self._ws.send_json(msg)
                    self._subscribed_tokens.add(token_id)
                    logger.debug(f"Subscribed to order book for {token_id}")
            
        except Exception as e:
            logger.error(f"Error subscribing to order book: {e}")
    
    async def process_ws_messages(self):
        """Process incoming WebSocket messages."""
        if not self._ws:
            return
        
        try:
            async for msg in self._ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    await self._handle_ws_message(data)
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error(f"WebSocket error: {self._ws.exception()}")
                    break
        except Exception as e:
            logger.error(f"Error processing WebSocket messages: {e}")
    
    async def _handle_ws_message(self, data: dict):
        """Handle a WebSocket message."""
        msg_type = data.get("type")
        
        if msg_type == "book":
            # Order book update
            token_id = data.get("asset_id")
            if token_id:
                await self._update_orderbook(token_id, data)
    
    async def _update_orderbook(self, token_id: str, data: dict):
        """Update order book from WebSocket data."""
        try:
            bids = [
                OrderBookLevel(price=float(b["price"]), size=float(b["size"]))
                for b in data.get("bids", [])
            ]
            asks = [
                OrderBookLevel(price=float(a["price"]), size=float(a["size"]))
                for a in data.get("asks", [])
            ]
            
            bids.sort(key=lambda x: x.price, reverse=True)
            asks.sort(key=lambda x: x.price)
            
            order_book = OrderBook(
                token_id=token_id,
                bids=bids,
                asks=asks,
                timestamp=datetime.utcnow(),
            )
            
            self.order_books[token_id] = order_book
            
            if self._on_orderbook_update:
                await self._on_orderbook_update(order_book)
                
        except Exception as e:
            logger.warning(f"Error updating order book: {e}")
    
    def get_market(self, market_id: str) -> Optional[Market]:
        """Get market by ID."""
        return self.markets.get(market_id)
    
    def get_token(self, token_id: str) -> Optional[Token]:
        """Get token by ID."""
        return self.tokens.get(token_id)
    
    def get_order_book(self, token_id: str) -> Optional[OrderBook]:
        """Get order book for a token."""
        return self.order_books.get(token_id)
    
    def get_mid_price(self, token_id: str) -> Optional[float]:
        """Get mid price for a token."""
        ob = self.order_books.get(token_id)
        return ob.mid_price if ob else None
    
    def get_active_markets(self, category: Optional[MarketCategory] = None) -> List[Market]:
        """Get all active markets, optionally filtered by category."""
        markets = [m for m in self.markets.values() if m.is_active]
        if category:
            markets = [m for m in markets if m.category == category]
        return markets
    
    def on_orderbook_update(self, callback: Callable):
        """Register callback for order book updates."""
        self._on_orderbook_update = callback
    
    def on_market_update(self, callback: Callable):
        """Register callback for market updates."""
        self._on_market_update = callback

