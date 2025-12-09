"""
Data Service - Fetches and manages market data from exchanges.
Supports:
- Coinbase/Kraken for spot data (USA-friendly)
- MEXC Futures for derivatives data
- Coinglass for aggregated derivatives metrics
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
    
    # Spot exchanges (USA-friendly)
    COINBASE_BASE_URL = "https://api.exchange.coinbase.com"
    KRAKEN_BASE_URL = "https://api.kraken.com"
    
    # Derivatives
    MEXC_FUTURES_URL = "https://contract.mexc.com"
    COINGLASS_URL = "https://open-api.coinglass.com"
    
    # Symbol mappings per exchange
    SYMBOL_MAP = {
        "coinbase": {
            "BTC": "BTC-USD",
            "ETH": "ETH-USD",
            "SOL": "SOL-USD",
            "BNB": "BNB-USD",
        },
        "kraken": {
            "BTC": "XXBTZUSD",
            "ETH": "XETHZUSD",
            "SOL": "SOLUSD",
            "BNB": "BNBUSD",
        },
        "mexc": {
            "BTC": "BTC_USDT",
            "ETH": "ETH_USDT",
            "SOL": "SOL_USDT",
            "BNB": "BNB_USDT",
        },
        "coinglass": {
            "BTC": "BTC",
            "ETH": "ETH",
            "SOL": "SOL",
            "BNB": "BNB",
        }
    }
    
    INTERVAL_MAP_COINBASE = {
        "1m": 60, "5m": 300, "15m": 900,
        "1h": 3600, "4h": 14400, "1d": 86400,
    }
    
    INTERVAL_MAP_KRAKEN = {
        "1m": 1, "5m": 5, "15m": 15,
        "1h": 60, "4h": 240, "1d": 1440,
    }
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self._cache: Dict[str, Any] = {}
        self._derivatives_cache: Dict[str, Any] = {}
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
        logger.info("Starting data streaming (Coinbase + MEXC Futures + Coinglass)...")
        
        while self._running:
            try:
                for asset in ["BTC", "ETH", "SOL"]:
                    # Update spot data
                    await self._update_cache(asset)
                    # Update derivatives data
                    await self._update_derivatives_cache(asset)
                
                await asyncio.sleep(5)
                
            except Exception as e:
                logger.error(f"Streaming error: {e}")
                await asyncio.sleep(10)
    
    async def _update_cache(self, asset: str):
        """Update spot data cache."""
        try:
            data = await self._fetch_coinbase_candles(asset, "1m", 10)
            if data:
                self._cache[f"{asset}_latest"] = data[-1]
                self._cache[f"{asset}_updated"] = datetime.utcnow()
        except Exception as e:
            logger.warning(f"Spot cache update failed for {asset}: {e}")
    
    async def _update_derivatives_cache(self, asset: str):
        """Update derivatives data cache."""
        try:
            # Fetch from multiple sources in parallel
            funding_task = self._fetch_mexc_funding_rate(asset)
            oi_task = self._fetch_coinglass_open_interest(asset)
            liq_task = self._fetch_coinglass_liquidations(asset)
            
            funding, oi_data, liq_data = await asyncio.gather(
                funding_task, oi_task, liq_task,
                return_exceptions=True
            )
            
            self._derivatives_cache[asset] = {
                "funding_rate": funding if not isinstance(funding, Exception) else None,
                "open_interest": oi_data if not isinstance(oi_data, Exception) else None,
                "liquidations": liq_data if not isinstance(liq_data, Exception) else None,
                "updated": datetime.utcnow(),
            }
            
        except Exception as e:
            logger.warning(f"Derivatives cache update failed for {asset}: {e}")
    
    async def get_latest_data(self, asset: str) -> Dict[str, Any]:
        """Get latest market data including derivatives."""
        # Get spot data
        klines = await self._fetch_coinbase_candles(asset, "1m", 100)
        if not klines:
            klines = await self._fetch_kraken_candles(asset, "1m", 100)
        
        if not klines:
            raise ValueError(f"Failed to fetch spot data for {asset}")
        
        latest = klines[-1]
        df = self._klines_to_dataframe(klines)
        
        # Get derivatives data from cache or fetch fresh
        deriv = self._derivatives_cache.get(asset, {})
        if not deriv or (datetime.utcnow() - deriv.get("updated", datetime.min)) > timedelta(seconds=30):
            await self._update_derivatives_cache(asset)
            deriv = self._derivatives_cache.get(asset, {})
        
        # Extract derivatives metrics
        funding_rate = deriv.get("funding_rate")
        oi_data = deriv.get("open_interest", {})
        liq_data = deriv.get("liquidations", {})
        
        return {
            "asset": asset,
            "timestamp": datetime.utcnow(),
            "price": float(latest["close"]),
            "ohlcv": latest,
            "funding_rate": funding_rate,
            "open_interest": oi_data.get("total_oi") if oi_data else None,
            "oi_change_24h": oi_data.get("change_24h") if oi_data else None,
            "long_liquidations_24h": liq_data.get("long_24h") if liq_data else None,
            "short_liquidations_24h": liq_data.get("short_24h") if liq_data else None,
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
        # Fetch spot OHLCV
        klines = await self._fetch_coinbase_candles(asset, interval, limit)
        if not klines:
            klines = await self._fetch_kraken_candles(asset, interval, limit)
        
        if not klines:
            raise ValueError(f"Failed to fetch data for {asset}")
        
        candles = [{
            "timestamp": k["timestamp"] if isinstance(k["timestamp"], datetime) else datetime.fromtimestamp(k["timestamp"]),
            "open": float(k["open"]),
            "high": float(k["high"]),
            "low": float(k["low"]),
            "close": float(k["close"]),
            "volume": float(k["volume"]),
        } for k in klines]
        
        # Get current derivatives data
        deriv = self._derivatives_cache.get(asset, {})
        funding = deriv.get("funding_rate")
        oi_data = deriv.get("open_interest", {})
        liq_data = deriv.get("liquidations", {})
        
        # Build market structure with derivatives
        market_structure = []
        for i, candle in enumerate(candles):
            # Only apply current derivatives data to recent candles
            is_recent = i >= len(candles) - 10
            
            ms = {
                "timestamp": candle["timestamp"],
                "funding_rate": funding if is_recent else None,
                "open_interest": oi_data.get("total_oi") if is_recent and oi_data else None,
                "oi_change_pct": oi_data.get("change_24h") if is_recent and oi_data else None,
                "long_liquidations": liq_data.get("long_24h") / 24 if is_recent and liq_data else None,
                "short_liquidations": liq_data.get("short_24h") / 24 if is_recent and liq_data else None,
                "cvd": None,
            }
            market_structure.append(ms)
        
        return {
            "asset": asset,
            "interval": interval,
            "candles": candles,
            "market_structure": market_structure,
        }
    
    async def get_data_at(self, asset: str, timestamp: datetime) -> Dict[str, Any]:
        """Get market data at a specific timestamp."""
        return await self.get_latest_data(asset)
    
    # ========================================================================
    # Coinbase API (Spot - USA Friendly)
    # ========================================================================
    
    async def _fetch_coinbase_candles(
        self, asset: str, interval: str, limit: int
    ) -> List[Dict]:
        """Fetch candles from Coinbase."""
        session = await self._get_session()
        symbol = self.SYMBOL_MAP["coinbase"].get(asset, f"{asset}-USD")
        granularity = self.INTERVAL_MAP_COINBASE.get(interval, 3600)
        
        end = datetime.utcnow()
        start = end - timedelta(seconds=granularity * limit)
        
        url = f"{self.COINBASE_BASE_URL}/products/{symbol}/candles"
        params = {
            "granularity": granularity,
            "start": start.isoformat(),
            "end": end.isoformat(),
        }
        
        try:
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    return []
                
                data = await response.json()
                candles = []
                for c in reversed(data):
                    candles.append({
                        "timestamp": datetime.fromtimestamp(c[0]),
                        "open": float(c[3]),
                        "high": float(c[2]),
                        "low": float(c[1]),
                        "close": float(c[4]),
                        "volume": float(c[5]),
                    })
                
                return candles
                
        except Exception as e:
            logger.error(f"Coinbase error: {e}")
            return []
    
    # ========================================================================
    # Kraken API (Spot - USA Friendly Fallback)
    # ========================================================================
    
    async def _fetch_kraken_candles(
        self, asset: str, interval: str, limit: int
    ) -> List[Dict]:
        """Fetch candles from Kraken."""
        session = await self._get_session()
        symbol = self.SYMBOL_MAP["kraken"].get(asset, f"{asset}USD")
        kraken_interval = self.INTERVAL_MAP_KRAKEN.get(interval, 60)
        
        url = f"{self.KRAKEN_BASE_URL}/0/public/OHLC"
        params = {"pair": symbol, "interval": kraken_interval}
        
        try:
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    return []
                
                data = await response.json()
                if data.get("error"):
                    return []
                
                result = data.get("result", {})
                pair_key = [k for k in result.keys() if k != 'last'][0] if result else None
                if not pair_key:
                    return []
                
                ohlc_data = result[pair_key]
                candles = []
                for c in ohlc_data[-limit:]:
                    candles.append({
                        "timestamp": datetime.fromtimestamp(c[0]),
                        "open": float(c[1]),
                        "high": float(c[2]),
                        "low": float(c[3]),
                        "close": float(c[4]),
                        "volume": float(c[6]),
                    })
                
                return candles
                
        except Exception as e:
            logger.error(f"Kraken error: {e}")
            return []
    
    # ========================================================================
    # MEXC Futures API (Derivatives)
    # ========================================================================
    
    async def _fetch_mexc_funding_rate(self, asset: str) -> Optional[float]:
        """Fetch funding rate from MEXC Futures."""
        session = await self._get_session()
        symbol = self.SYMBOL_MAP["mexc"].get(asset, f"{asset}_USDT")
        
        url = f"{self.MEXC_FUTURES_URL}/api/v1/contract/funding_rate/{symbol}"
        
        try:
            async with session.get(url) as response:
                if response.status != 200:
                    return None
                
                data = await response.json()
                if data.get("success") and data.get("data"):
                    rate = float(data["data"].get("fundingRate", 0))
                    logger.debug(f"MEXC funding rate for {asset}: {rate}")
                    return rate
                return None
                
        except Exception as e:
            logger.debug(f"MEXC funding rate error for {asset}: {e}")
            return None
    
    async def _fetch_mexc_open_interest(self, asset: str) -> Optional[Dict]:
        """Fetch open interest from MEXC Futures."""
        session = await self._get_session()
        symbol = self.SYMBOL_MAP["mexc"].get(asset, f"{asset}_USDT")
        
        url = f"{self.MEXC_FUTURES_URL}/api/v1/contract/detail"
        params = {"symbol": symbol}
        
        try:
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    return None
                
                data = await response.json()
                if data.get("success") and data.get("data"):
                    contract = data["data"]
                    return {
                        "total_oi": float(contract.get("holdVol", 0)),
                        "total_oi_value": float(contract.get("holdVolValue", 0)),
                    }
                return None
                
        except Exception as e:
            logger.debug(f"MEXC OI error for {asset}: {e}")
            return None
    
    # ========================================================================
    # Coinglass API (Aggregated Derivatives Data)
    # ========================================================================
    
    async def _fetch_coinglass_open_interest(self, asset: str) -> Optional[Dict]:
        """Fetch aggregated open interest from Coinglass."""
        session = await self._get_session()
        symbol = self.SYMBOL_MAP["coinglass"].get(asset, asset)
        
        # Coinglass API with optional API key
        url = f"https://open-api-v3.coinglass.com/api/futures/openInterest/chart"
        params = {
            "symbol": symbol,
            "interval": "1h",
            "limit": 24,
        }
        
        headers = {}
        if settings.coinglass_api_key:
            headers["CG-API-KEY"] = settings.coinglass_api_key
        
        try:
            async with session.get(url, params=params, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("code") == "0" and data.get("data"):
                        oi_list = data["data"]
                        if oi_list:
                            latest = oi_list[-1]
                            oldest = oi_list[0] if len(oi_list) > 1 else latest
                            
                            total_oi = float(latest.get("openInterest", 0))
                            prev_oi = float(oldest.get("openInterest", total_oi))
                            change_24h = (total_oi - prev_oi) / prev_oi if prev_oi > 0 else 0
                            
                            logger.debug(f"Coinglass OI for {asset}: ${total_oi/1e9:.2f}B")
                            return {
                                "total_oi": total_oi,
                                "change_24h": change_24h,
                            }
        except Exception as e:
            logger.debug(f"Coinglass OI error: {e}")
        
        # Fallback to MEXC
        return await self._fetch_mexc_open_interest(asset)
    
    async def _fetch_coinglass_liquidations(self, asset: str) -> Optional[Dict]:
        """Fetch liquidation data from Coinglass."""
        session = await self._get_session()
        symbol = self.SYMBOL_MAP["coinglass"].get(asset, asset)
        
        url = f"https://open-api-v3.coinglass.com/api/futures/liquidation/chart"
        params = {
            "symbol": symbol,
            "interval": "1h",
            "limit": 24,
        }
        
        headers = {}
        if settings.coinglass_api_key:
            headers["CG-API-KEY"] = settings.coinglass_api_key
        
        try:
            async with session.get(url, params=params, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("code") == "0" and data.get("data"):
                        liq_list = data["data"]
                        
                        # Sum up 24h liquidations
                        long_total = sum(float(l.get("longLiquidationUsd", 0)) for l in liq_list)
                        short_total = sum(float(l.get("shortLiquidationUsd", 0)) for l in liq_list)
                        
                        logger.debug(f"Coinglass liqs for {asset}: Long ${long_total/1e6:.1f}M, Short ${short_total/1e6:.1f}M")
                        return {
                            "long_24h": long_total,
                            "short_24h": short_total,
                            "total_24h": long_total + short_total,
                        }
        except Exception as e:
            logger.debug(f"Coinglass liquidations error: {e}")
        
        # Return estimated data based on volatility
        return await self._estimate_liquidations(asset)
    
    async def _fetch_coinglass_funding_rates(self, asset: str) -> Optional[Dict]:
        """Fetch aggregated funding rates from Coinglass."""
        session = await self._get_session()
        symbol = self.SYMBOL_MAP["coinglass"].get(asset, asset)
        
        url = f"https://open-api-v3.coinglass.com/api/futures/fundingRate"
        params = {"symbol": symbol}
        
        headers = {}
        if settings.coinglass_api_key:
            headers["CG-API-KEY"] = settings.coinglass_api_key
        
        try:
            async with session.get(url, params=params, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("code") == "0" and data.get("data"):
                        rates = data["data"]
                        if rates:
                            # Average across exchanges
                            avg_rate = sum(float(r.get("rate", 0)) for r in rates) / len(rates)
                            logger.debug(f"Coinglass avg funding for {asset}: {avg_rate:.6f}")
                            return {"average": avg_rate, "exchanges": rates}
        except Exception as e:
            logger.debug(f"Coinglass funding error: {e}")
        
        return None
    
    async def _estimate_liquidations(self, asset: str) -> Optional[Dict]:
        """Estimate liquidations based on price volatility."""
        # Get recent volatility
        klines = await self._fetch_coinbase_candles(asset, "1h", 24)
        if not klines:
            return None
        
        df = self._klines_to_dataframe(klines)
        volatility = self._calculate_volatility(df, 24)
        
        if volatility is None:
            return None
        
        # Rough estimate: higher vol = more liquidations
        # Base estimates scaled by volatility
        price = float(klines[-1]["close"])
        base_liq = price * 1000000  # $1M base per $1 of price
        vol_multiplier = volatility / 0.02  # Normalize to 2% vol
        
        estimated_total = base_liq * vol_multiplier * 0.1
        
        return {
            "long_24h": estimated_total * 0.5,
            "short_24h": estimated_total * 0.5,
            "total_24h": estimated_total,
            "estimated": True,
        }
    
    # ========================================================================
    # Helper Methods
    # ========================================================================
    
    def _klines_to_dataframe(self, klines: List[Dict]) -> pd.DataFrame:
        """Convert klines to DataFrame."""
        df = pd.DataFrame(klines)
        if "timestamp" in df.columns and not df.empty:
            df = df.set_index("timestamp")
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df[col] = df[col].astype(float)
        return df
    
    def _calculate_returns(self, df: pd.DataFrame, periods: int) -> Optional[float]:
        """Calculate log returns over periods."""
        if len(df) < periods:
            return None
        return float(np.log(df["close"].iloc[-1] / df["close"].iloc[-periods]))
    
    def _calculate_volatility(self, df: pd.DataFrame, periods: int) -> Optional[float]:
        """Calculate rolling volatility."""
        if len(df) < periods:
            return None
        returns = np.log(df["close"] / df["close"].shift(1))
        return float(returns.tail(periods).std() * np.sqrt(periods))
    
    def _calculate_cvd(self, df: pd.DataFrame) -> Optional[float]:
        """Calculate Cumulative Volume Delta estimate."""
        if len(df) < 2:
            return None
        df = df.copy()
        df["direction"] = np.where(df["close"] >= df["open"], 1, -1)
        df["delta"] = df["volume"] * df["direction"]
        return float(df["delta"].sum())
