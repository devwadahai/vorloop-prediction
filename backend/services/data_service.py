"""
Data Service - Fetches and manages market data from exchanges.
"""
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import aiohttp
from loguru import logger
import numpy as np
import pandas as pd

from core.config import settings


class DataService:
    """Service for fetching and managing market data."""
    
    BINANCE_BASE_URL = "https://fapi.binance.com"
    BYBIT_BASE_URL = "https://api.bybit.com"
    
    INTERVAL_MAP = {
        "1m": "1m",
        "5m": "5m",
        "15m": "15m",
        "1h": "1h",
        "4h": "4h",
        "1d": "1d",
    }
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self._cache: Dict[str, Any] = {}
        self._running = False
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def close(self):
        """Close HTTP session."""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def start_streaming(self):
        """Start background data streaming."""
        self._running = True
        logger.info("Starting data streaming...")
        
        while self._running:
            try:
                # Update cache for main assets
                for asset in ["BTC", "ETH", "SOL"]:
                    await self._update_cache(asset)
                
                await asyncio.sleep(5)  # Update every 5 seconds
                
            except Exception as e:
                logger.error(f"Streaming error: {e}")
                await asyncio.sleep(10)
    
    async def _update_cache(self, asset: str):
        """Update cache for an asset."""
        try:
            data = await self._fetch_binance_klines(asset, "1m", 10)
            if data:
                self._cache[f"{asset}_latest"] = data[-1]
                self._cache[f"{asset}_updated"] = datetime.utcnow()
        except Exception as e:
            logger.warning(f"Cache update failed for {asset}: {e}")
    
    async def get_latest_data(self, asset: str) -> Dict[str, Any]:
        """Get latest market data for an asset."""
        # Try cache first
        cache_key = f"{asset}_latest"
        if cache_key in self._cache:
            cache_age = datetime.utcnow() - self._cache.get(f"{asset}_updated", datetime.min)
            if cache_age < timedelta(seconds=10):
                return self._cache[cache_key]
        
        # Fetch fresh data
        klines = await self._fetch_binance_klines(asset, "1m", 100)
        funding = await self._fetch_funding_rate(asset)
        oi = await self._fetch_open_interest(asset)
        
        if not klines:
            raise ValueError(f"Failed to fetch data for {asset}")
        
        latest = klines[-1]
        df = self._klines_to_dataframe(klines)
        
        return {
            "asset": asset,
            "timestamp": datetime.utcnow(),
            "price": float(latest["close"]),
            "ohlcv": latest,
            "funding_rate": funding,
            "open_interest": oi,
            "returns_1h": self._calculate_returns(df, 60),
            "returns_24h": self._calculate_returns(df, 1440) if len(df) >= 1440 else None,
            "volatility_1h": self._calculate_volatility(df, 60),
            "cvd": self._calculate_cvd(df),
        }
    
    async def get_historical_data(
        self, 
        asset: str, 
        interval: str, 
        limit: int
    ) -> Dict[str, Any]:
        """Get historical OHLCV and market structure data."""
        # Fetch OHLCV
        klines = await self._fetch_binance_klines(asset, interval, limit)
        
        if not klines:
            raise ValueError(f"Failed to fetch data for {asset}")
        
        # Fetch market structure data
        funding_history = await self._fetch_funding_history(asset, limit)
        oi_history = await self._fetch_oi_history(asset, interval, limit)
        
        candles = []
        for k in klines:
            candles.append({
                "timestamp": datetime.fromtimestamp(k["timestamp"] / 1000),
                "open": float(k["open"]),
                "high": float(k["high"]),
                "low": float(k["low"]),
                "close": float(k["close"]),
                "volume": float(k["volume"]),
            })
        
        # Build market structure
        market_structure = []
        for i, candle in enumerate(candles):
            ms = {
                "timestamp": candle["timestamp"],
                "funding_rate": None,
                "open_interest": None,
                "oi_change_pct": None,
                "long_liquidations": None,
                "short_liquidations": None,
                "cvd": None,
            }
            
            # Match funding rate by timestamp
            for fr in funding_history:
                if abs((fr["timestamp"] - candle["timestamp"]).total_seconds()) < 3600:
                    ms["funding_rate"] = fr["rate"]
                    break
            
            # Match OI
            if i < len(oi_history):
                ms["open_interest"] = oi_history[i].get("oi")
                if i > 0 and oi_history[i-1].get("oi"):
                    prev_oi = oi_history[i-1]["oi"]
                    curr_oi = oi_history[i]["oi"]
                    ms["oi_change_pct"] = (curr_oi - prev_oi) / prev_oi if prev_oi else None
            
            market_structure.append(ms)
        
        return {
            "asset": asset,
            "interval": interval,
            "candles": candles,
            "market_structure": market_structure,
        }
    
    async def get_data_at(
        self, 
        asset: str, 
        timestamp: datetime
    ) -> Dict[str, Any]:
        """Get market data at a specific timestamp."""
        # For now, return latest data
        # In production, query historical database
        return await self.get_latest_data(asset)
    
    # ========================================================================
    # Binance API Methods
    # ========================================================================
    
    async def _fetch_binance_klines(
        self, 
        asset: str, 
        interval: str, 
        limit: int
    ) -> List[Dict]:
        """Fetch klines from Binance Futures."""
        session = await self._get_session()
        symbol = f"{asset}USDT"
        
        url = f"{self.BINANCE_BASE_URL}/fapi/v1/klines"
        params = {
            "symbol": symbol,
            "interval": self.INTERVAL_MAP.get(interval, "1h"),
            "limit": min(limit, 1500),
        }
        
        try:
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    logger.warning(f"Binance API error: {response.status}")
                    return []
                
                data = await response.json()
                
                return [
                    {
                        "timestamp": k[0],
                        "open": k[1],
                        "high": k[2],
                        "low": k[3],
                        "close": k[4],
                        "volume": k[5],
                        "close_time": k[6],
                        "quote_volume": k[7],
                        "trades": k[8],
                        "taker_buy_volume": k[9],
                        "taker_buy_quote_volume": k[10],
                    }
                    for k in data
                ]
                
        except Exception as e:
            logger.error(f"Binance klines fetch error: {e}")
            return []
    
    async def _fetch_funding_rate(self, asset: str) -> Optional[float]:
        """Fetch current funding rate."""
        session = await self._get_session()
        symbol = f"{asset}USDT"
        
        url = f"{self.BINANCE_BASE_URL}/fapi/v1/fundingRate"
        params = {"symbol": symbol, "limit": 1}
        
        try:
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    return None
                
                data = await response.json()
                if data:
                    return float(data[0]["fundingRate"])
                return None
                
        except Exception as e:
            logger.error(f"Funding rate fetch error: {e}")
            return None
    
    async def _fetch_funding_history(
        self, 
        asset: str, 
        limit: int
    ) -> List[Dict]:
        """Fetch funding rate history."""
        session = await self._get_session()
        symbol = f"{asset}USDT"
        
        url = f"{self.BINANCE_BASE_URL}/fapi/v1/fundingRate"
        params = {"symbol": symbol, "limit": min(limit, 1000)}
        
        try:
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    return []
                
                data = await response.json()
                return [
                    {
                        "timestamp": datetime.fromtimestamp(d["fundingTime"] / 1000),
                        "rate": float(d["fundingRate"]),
                    }
                    for d in data
                ]
                
        except Exception as e:
            logger.error(f"Funding history fetch error: {e}")
            return []
    
    async def _fetch_open_interest(self, asset: str) -> Optional[float]:
        """Fetch current open interest."""
        session = await self._get_session()
        symbol = f"{asset}USDT"
        
        url = f"{self.BINANCE_BASE_URL}/fapi/v1/openInterest"
        params = {"symbol": symbol}
        
        try:
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    return None
                
                data = await response.json()
                return float(data["openInterest"])
                
        except Exception as e:
            logger.error(f"Open interest fetch error: {e}")
            return None
    
    async def _fetch_oi_history(
        self, 
        asset: str, 
        interval: str, 
        limit: int
    ) -> List[Dict]:
        """Fetch open interest history."""
        session = await self._get_session()
        symbol = f"{asset}USDT"
        
        url = f"{self.BINANCE_BASE_URL}/futures/data/openInterestHist"
        params = {
            "symbol": symbol,
            "period": self.INTERVAL_MAP.get(interval, "1h"),
            "limit": min(limit, 500),
        }
        
        try:
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    return []
                
                data = await response.json()
                return [
                    {
                        "timestamp": datetime.fromtimestamp(d["timestamp"] / 1000),
                        "oi": float(d["sumOpenInterest"]),
                        "oi_value": float(d["sumOpenInterestValue"]),
                    }
                    for d in data
                ]
                
        except Exception as e:
            logger.error(f"OI history fetch error: {e}")
            return []
    
    # ========================================================================
    # Helper Methods
    # ========================================================================
    
    def _klines_to_dataframe(self, klines: List[Dict]) -> pd.DataFrame:
        """Convert klines to DataFrame."""
        df = pd.DataFrame(klines)
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)
        return df.set_index("timestamp")
    
    def _calculate_returns(self, df: pd.DataFrame, periods: int) -> Optional[float]:
        """Calculate log returns over periods."""
        if len(df) < periods:
            return None
        return np.log(df["close"].iloc[-1] / df["close"].iloc[-periods])
    
    def _calculate_volatility(self, df: pd.DataFrame, periods: int) -> Optional[float]:
        """Calculate rolling volatility."""
        if len(df) < periods:
            return None
        returns = np.log(df["close"] / df["close"].shift(1))
        return returns.tail(periods).std() * np.sqrt(periods)
    
    def _calculate_cvd(self, df: pd.DataFrame) -> Optional[float]:
        """Calculate Cumulative Volume Delta."""
        if "taker_buy_volume" not in df.columns:
            return None
        
        buy_vol = df["taker_buy_volume"].astype(float)
        total_vol = df["volume"]
        sell_vol = total_vol - buy_vol
        
        return (buy_vol - sell_vol).sum()

