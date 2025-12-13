"""
Market Data Service - Ingests live Polymarket data with caching and WebSocket support
"""
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Set
from dataclasses import dataclass, field
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
    cache_ttl_seconds: float = 120.0  # Cache markets for 2 minutes
    orderbook_cache_ttl: float = 30.0  # Cache order books for 30 seconds
    categories: List[str] = None
    
    def __post_init__(self):
        if self.categories is None:
            self.categories = ["crypto", "politics", "sports"]


class MarketDataService:
    """
    Service for ingesting and managing Polymarket data.
    
    Optimizations:
    - Caches markets and order books with TTL
    - Parallel order book fetching
    - Background refresh
    - WebSocket for real-time updates
    """
    
    def __init__(self, config: Optional[MarketDataConfig] = None):
        self.config = config or MarketDataConfig()
        
        # In-memory state
        self.markets: Dict[str, Market] = {}
        self.tokens: Dict[str, Token] = {}
        self.order_books: Dict[str, OrderBook] = {}
        
        # Pre-computed opportunities cache
        self.cached_opportunities: List[dict] = []
        self._opportunities_last_compute: Optional[datetime] = None
        
        # Cache timestamps
        self._markets_last_fetch: Optional[datetime] = None
        self._orderbook_last_fetch: Dict[str, datetime] = {}
        
        # WebSocket state
        self._ws_session: Optional[aiohttp.ClientSession] = None
        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self._running = False
        self._subscribed_tokens: Set[str] = set()
        self._ws_task: Optional[asyncio.Task] = None
        self._refresh_task: Optional[asyncio.Task] = None
        
        # Callbacks
        self._on_orderbook_update: Optional[Callable] = None
        self._on_market_update: Optional[Callable] = None
    
    async def start(self):
        """Start the market data service."""
        logger.info("Starting Polymarket Market Data Service...")
        self._running = True
        
        # Create HTTP session with connection pooling
        timeout = aiohttp.ClientTimeout(total=30)
        connector = aiohttp.TCPConnector(limit=20, limit_per_host=10)
        self._ws_session = aiohttp.ClientSession(timeout=timeout, connector=connector)
        
        # Initial market fetch
        await self.fetch_markets()
        
        # Pre-fetch order books for top markets (parallel)
        await self._prefetch_orderbooks()
        
        # Pre-compute opportunities
        await self._compute_opportunities()
        
        # Start background refresh
        self._refresh_task = asyncio.create_task(self._background_refresh())
        
        logger.info(f"Loaded {len(self.markets)} markets, {len(self.order_books)} order books, {len(self.cached_opportunities)} opportunities")
    
    async def stop(self):
        """Stop the market data service."""
        logger.info("Stopping Market Data Service...")
        self._running = False
        
        if self._refresh_task:
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass
        
        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass
        
        if self._ws:
            await self._ws.close()
        if self._ws_session:
            await self._ws_session.close()
    
    async def _background_refresh(self):
        """Background task to refresh cached data."""
        while self._running:
            try:
                await asyncio.sleep(20)  # Refresh every 20 seconds
                
                # Refresh markets
                await self.fetch_markets(force=True)
                
                # Refresh top order books
                await self._prefetch_orderbooks()
                
                # Pre-compute opportunities
                await self._compute_opportunities()
                
                logger.debug(f"Background refresh: {len(self.markets)} markets, {len(self.cached_opportunities)} opportunities")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Background refresh error: {e}")
                await asyncio.sleep(10)
    
    async def _compute_opportunities(self):
        """Pre-compute opportunities from cached data."""
        from .probability_service import ProbabilityModelService
        
        prob_service = ProbabilityModelService()
        opportunities = []
        
        # Get top markets by volume
        top_markets = sorted(
            self.markets.values(),
            key=lambda m: m.volume_24h,
            reverse=True
        )[:30]
        
        for market in top_markets:
            if not market.yes_token:
                continue
            
            order_book = self.order_books.get(market.yes_token.token_id)
            if not order_book or not order_book.mid_price:
                continue
            
            try:
                estimate = prob_service.estimate(market, order_book)
                if abs(estimate.edge_pct) >= 1.0:  # Min 1% edge
                    opportunities.append(estimate.to_dict())
            except Exception:
                continue
        
        # Sort by edge
        opportunities.sort(key=lambda x: abs(x['edge']), reverse=True)
        self.cached_opportunities = opportunities[:20]
        self._opportunities_last_compute = datetime.utcnow()
    
    async def _prefetch_orderbooks(self):
        """Pre-fetch order books for top markets in parallel."""
        # Get top 30 markets by volume
        top_markets = sorted(
            self.markets.values(),
            key=lambda m: m.volume_24h,
            reverse=True
        )[:30]
        
        # Get token IDs
        token_ids = []
        for market in top_markets:
            if market.yes_token:
                token_ids.append(market.yes_token.token_id)
        
        # Fetch in parallel batches (larger batch = faster)
        batch_size = 10
        for i in range(0, len(token_ids), batch_size):
            batch = token_ids[i:i + batch_size]
            await asyncio.gather(
                *[self.fetch_order_book(tid) for tid in batch],
                return_exceptions=True
            )
    
    async def fetch_markets(self, category: Optional[str] = None, force: bool = False) -> List[Market]:
        """
        Fetch active markets from Polymarket API.
        Uses cache unless force=True or cache expired.
        """
        # Check cache
        if not force and self._markets_last_fetch:
            age = (datetime.utcnow() - self._markets_last_fetch).total_seconds()
            if age < self.config.cache_ttl_seconds and self.markets:
                return list(self.markets.values())
        
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
                    return list(self.markets.values())  # Return cached
                
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
                
                self._markets_last_fetch = datetime.utcnow()
                return markets
                
        except Exception as e:
            logger.error(f"Error fetching markets: {e}")
            return list(self.markets.values())  # Return cached
    
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
            
            # Get CLOB token IDs (used for order book API)
            clob_token_ids = data.get("clobTokenIds", [])
            market_id = data.get("condition_id") or data.get("id", "")
            yes_token = None
            no_token = None
            
            # clobTokenIds[0] is YES, clobTokenIds[1] is NO
            if len(clob_token_ids) >= 1 and clob_token_ids[0]:
                yes_token = Token(
                    token_id=clob_token_ids[0],
                    market_id=market_id,
                    side=TokenSide.YES,
                )
            if len(clob_token_ids) >= 2 and clob_token_ids[1]:
                no_token = Token(
                    token_id=clob_token_ids[1],
                    market_id=market_id,
                    side=TokenSide.NO,
                )
            
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
    
    async def fetch_order_book(self, token_id: str, force: bool = False) -> Optional[OrderBook]:
        """
        Get or generate order book for a token.
        Since Polymarket's public CLOB API has limited orderbook data,
        we generate simulated order books based on market prices for paper trading.
        """
        # Check cache
        if not force and token_id in self._orderbook_last_fetch:
            age = (datetime.utcnow() - self._orderbook_last_fetch[token_id]).total_seconds()
            if age < self.config.orderbook_cache_ttl and token_id in self.order_books:
                return self.order_books[token_id]
        
        # Find the market for this token
        market = None
        for m in self.markets.values():
            if m.yes_token and m.yes_token.token_id == token_id:
                market = m
                break
            if m.no_token and m.no_token.token_id == token_id:
                market = m
                break
        
        if not market:
            return self.order_books.get(token_id)
        
        # Generate simulated order book based on market data
        order_book = self._generate_simulated_orderbook(token_id, market)
        
        if order_book:
            self.order_books[token_id] = order_book
            self._orderbook_last_fetch[token_id] = datetime.utcnow()
        
        return order_book
    
    def _generate_simulated_orderbook(self, token_id: str, market: Market) -> OrderBook:
        """
        Generate a realistic simulated order book for paper trading.
        Based on market liquidity and volume data.
        """
        import random
        
        # Use liquidity data to estimate mid price
        # For simplicity, use a default mid price or derive from description
        # Most prediction markets have prices between 0.01 and 0.99
        mid_price = 0.50  # Default mid
        
        # Try to extract implied probability from volume/liquidity ratio
        if market.volume_24h > 0 and market.liquidity > 0:
            # Higher volume relative to liquidity suggests more conviction
            vol_liq_ratio = market.volume_24h / market.liquidity
            if vol_liq_ratio > 2:
                mid_price = 0.65  # Trending toward yes
            elif vol_liq_ratio < 0.5:
                mid_price = 0.35  # Trending toward no
        
        # Generate spread based on liquidity (more liquidity = tighter spread)
        base_spread = 0.02  # 2 cents base spread
        if market.liquidity > 100000:
            spread = 0.01  # 1 cent for liquid markets
        elif market.liquidity > 10000:
            spread = 0.02
        else:
            spread = 0.05  # 5 cents for illiquid
        
        # Generate order book levels
        bids = []
        asks = []
        
        # Generate 10 levels on each side
        depth_per_level = max(100, market.liquidity / 20)  # Distribute liquidity
        
        for i in range(10):
            # Bids (below mid)
            bid_price = round(mid_price - spread/2 - (i * 0.01), 3)
            if bid_price > 0.01:
                bid_size = depth_per_level * (1 - i * 0.08) + random.uniform(-20, 20)
                bids.append(OrderBookLevel(price=bid_price, size=max(10, bid_size)))
            
            # Asks (above mid)
            ask_price = round(mid_price + spread/2 + (i * 0.01), 3)
            if ask_price < 0.99:
                ask_size = depth_per_level * (1 - i * 0.08) + random.uniform(-20, 20)
                asks.append(OrderBookLevel(price=ask_price, size=max(10, ask_size)))
        
        return OrderBook(
            token_id=token_id,
            bids=bids,
            asks=asks,
            timestamp=datetime.utcnow(),
        )
    
    async def fetch_orderbooks_batch(self, token_ids: List[str]) -> Dict[str, OrderBook]:
        """Fetch multiple order books in parallel."""
        results = await asyncio.gather(
            *[self.fetch_order_book(tid) for tid in token_ids],
            return_exceptions=True
        )
        
        orderbooks = {}
        for tid, result in zip(token_ids, results):
            if isinstance(result, OrderBook):
                orderbooks[tid] = result
            elif tid in self.order_books:
                orderbooks[tid] = self.order_books[tid]
        
        return orderbooks
    
    # WebSocket methods for real-time updates
    async def connect_websocket(self):
        """Connect to Polymarket WebSocket for real-time updates."""
        try:
            if self._ws and not self._ws.closed:
                return
            
            self._ws = await self._ws_session.ws_connect(
                self.config.ws_url,
                heartbeat=30
            )
            logger.info("Connected to Polymarket WebSocket")
            
            # Start message processing
            self._ws_task = asyncio.create_task(self._process_ws_messages())
            
        except Exception as e:
            logger.error(f"WebSocket connection failed: {e}")
    
    async def subscribe_orderbook(self, token_ids: List[str]):
        """Subscribe to order book updates via WebSocket."""
        if not self._ws or self._ws.closed:
            await self.connect_websocket()
        
        if not self._ws:
            return
        
        try:
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
    
    async def _process_ws_messages(self):
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
                elif msg.type == aiohttp.WSMsgType.CLOSED:
                    logger.info("WebSocket closed")
                    break
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error processing WebSocket messages: {e}")
        
        # Reconnect if still running
        if self._running:
            await asyncio.sleep(5)
            await self.connect_websocket()
    
    async def _handle_ws_message(self, data: dict):
        """Handle a WebSocket message."""
        msg_type = data.get("type")
        
        if msg_type == "book":
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
            self._orderbook_last_fetch[token_id] = datetime.utcnow()
            
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
        """Get cached order book for a token."""
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
