"""
Feature engineering pipeline for prediction models.
"""
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from dataclasses import dataclass
from loguru import logger

try:
    import ta
    TA_AVAILABLE = True
except ImportError:
    TA_AVAILABLE = False
    logger.warning("ta library not available, using manual indicators")


@dataclass
class FeatureConfig:
    """Configuration for feature engineering."""
    # Price windows
    return_windows: List[int] = None
    volatility_windows: List[int] = None
    
    # Technical indicators
    rsi_periods: List[int] = None
    macd_params: Tuple[int, int, int] = (12, 26, 9)
    bb_params: Tuple[int, float] = (20, 2.0)
    ema_periods: List[int] = None
    
    # Rolling windows for microstructure
    cvd_windows: List[int] = None
    
    def __post_init__(self):
        self.return_windows = self.return_windows or [5, 15, 60, 240, 1440]
        self.volatility_windows = self.volatility_windows or [60, 1440]
        self.rsi_periods = self.rsi_periods or [7, 14]
        self.ema_periods = self.ema_periods or [9, 21, 50]
        self.cvd_windows = self.cvd_windows or [5, 60]


class FeatureEngineer:
    """Feature engineering for crypto prediction."""
    
    def __init__(self, config: Optional[FeatureConfig] = None):
        self.config = config or FeatureConfig()
    
    def create_features(
        self,
        ohlcv: pd.DataFrame,
        funding: Optional[pd.Series] = None,
        oi: Optional[pd.Series] = None,
        cvd: Optional[pd.Series] = None,
        liquidations: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        Create all features from raw data.
        
        Args:
            ohlcv: DataFrame with columns [open, high, low, close, volume]
            funding: Funding rate series
            oi: Open interest series
            cvd: Cumulative volume delta series
            liquidations: DataFrame with [long_liq, short_liq]
            
        Returns:
            DataFrame with all features
        """
        features = pd.DataFrame(index=ohlcv.index)
        
        # Price features
        price_features = self._price_features(ohlcv)
        features = pd.concat([features, price_features], axis=1)
        
        # Technical indicators
        tech_features = self._technical_indicators(ohlcv)
        features = pd.concat([features, tech_features], axis=1)
        
        # Microstructure features
        micro_features = self._microstructure_features(ohlcv, cvd)
        features = pd.concat([features, micro_features], axis=1)
        
        # Derivatives features
        if funding is not None or oi is not None:
            deriv_features = self._derivatives_features(funding, oi, liquidations)
            features = pd.concat([features, deriv_features], axis=1)
        
        return features
    
    def _price_features(self, ohlcv: pd.DataFrame) -> pd.DataFrame:
        """Create price-based features."""
        features = pd.DataFrame(index=ohlcv.index)
        close = ohlcv["close"]
        high = ohlcv["high"]
        low = ohlcv["low"]
        
        # Log returns at various windows
        for window in self.config.return_windows:
            features[f"returns_{window}m"] = np.log(close / close.shift(window))
        
        # Volatility at various windows
        log_returns = np.log(close / close.shift(1))
        for window in self.config.volatility_windows:
            features[f"volatility_{window}m"] = log_returns.rolling(window).std() * np.sqrt(window)
        
        # Price position features
        features["high_low_range"] = (high - low) / close
        features["close_position"] = (close - low) / (high - low + 1e-10)
        
        # Gap features
        features["gap"] = ohlcv["open"] / close.shift(1) - 1
        
        # Rolling highs/lows
        for window in [24, 168]:  # 1 day, 7 days
            features[f"dist_from_high_{window}h"] = close / high.rolling(window).max() - 1
            features[f"dist_from_low_{window}h"] = close / low.rolling(window).min() - 1
        
        return features
    
    def _technical_indicators(self, ohlcv: pd.DataFrame) -> pd.DataFrame:
        """Create technical indicator features."""
        features = pd.DataFrame(index=ohlcv.index)
        close = ohlcv["close"]
        high = ohlcv["high"]
        low = ohlcv["low"]
        volume = ohlcv["volume"]
        
        if TA_AVAILABLE:
            # Use ta library
            for period in self.config.rsi_periods:
                features[f"rsi_{period}"] = ta.momentum.rsi(close, window=period)
            
            # MACD
            macd = ta.trend.MACD(
                close,
                window_slow=self.config.macd_params[1],
                window_fast=self.config.macd_params[0],
                window_sign=self.config.macd_params[2]
            )
            features["macd_signal"] = macd.macd_diff()
            features["macd_normalized"] = macd.macd_diff() / close
            
            # Bollinger Bands
            bb = ta.volatility.BollingerBands(
                close,
                window=self.config.bb_params[0],
                window_dev=self.config.bb_params[1]
            )
            features["bb_position"] = (close - bb.bollinger_lband()) / (bb.bollinger_hband() - bb.bollinger_lband() + 1e-10)
            features["bb_width"] = (bb.bollinger_hband() - bb.bollinger_lband()) / bb.bollinger_mavg()
            
            # ATR
            features["atr_14"] = ta.volatility.AverageTrueRange(high, low, close, window=14).average_true_range()
            features["atr_normalized"] = features["atr_14"] / close
            
        else:
            # Manual calculations
            for period in self.config.rsi_periods:
                features[f"rsi_{period}"] = self._calculate_rsi(close, period)
            
            # Simple MACD
            ema_fast = close.ewm(span=self.config.macd_params[0]).mean()
            ema_slow = close.ewm(span=self.config.macd_params[1]).mean()
            macd_line = ema_fast - ema_slow
            signal_line = macd_line.ewm(span=self.config.macd_params[2]).mean()
            features["macd_signal"] = macd_line - signal_line
            features["macd_normalized"] = features["macd_signal"] / close
            
            # Simple Bollinger Bands
            bb_mid = close.rolling(self.config.bb_params[0]).mean()
            bb_std = close.rolling(self.config.bb_params[0]).std()
            bb_upper = bb_mid + self.config.bb_params[1] * bb_std
            bb_lower = bb_mid - self.config.bb_params[1] * bb_std
            features["bb_position"] = (close - bb_lower) / (bb_upper - bb_lower + 1e-10)
            features["bb_width"] = (bb_upper - bb_lower) / bb_mid
            
            # ATR
            features["atr_14"] = self._calculate_atr(high, low, close, 14)
            features["atr_normalized"] = features["atr_14"] / close
        
        # EMA crosses
        emas = {}
        for period in self.config.ema_periods:
            emas[period] = close.ewm(span=period).mean()
        
        if len(self.config.ema_periods) >= 2:
            features["ema_cross_9_21"] = (emas.get(9, emas[self.config.ema_periods[0]]) > 
                                          emas.get(21, emas[self.config.ema_periods[1]])).astype(int)
        
        # Volume features
        features["volume_sma_ratio"] = volume / volume.rolling(24).mean()
        features["volume_zscore"] = (volume - volume.rolling(168).mean()) / (volume.rolling(168).std() + 1e-10)
        
        return features
    
    def _microstructure_features(
        self, 
        ohlcv: pd.DataFrame,
        cvd: Optional[pd.Series] = None
    ) -> pd.DataFrame:
        """Create market microstructure features."""
        features = pd.DataFrame(index=ohlcv.index)
        
        # Estimate CVD from taker buy volume if available
        if "taker_buy_volume" in ohlcv.columns:
            buy_vol = ohlcv["taker_buy_volume"]
            sell_vol = ohlcv["volume"] - buy_vol
            cvd_series = (buy_vol - sell_vol).cumsum()
        elif cvd is not None:
            cvd_series = cvd
        else:
            cvd_series = None
        
        if cvd_series is not None:
            for window in self.config.cvd_windows:
                features[f"cvd_{window}m"] = cvd_series.diff(window)
            
            # CVD momentum
            features["cvd_momentum"] = cvd_series.diff(60) / (ohlcv["volume"].rolling(60).sum() + 1e-10)
        
        # Trade imbalance proxy
        close = ohlcv["close"]
        high = ohlcv["high"]
        low = ohlcv["low"]
        
        # Close position in bar as proxy for buying/selling pressure
        features["trade_imbalance_proxy"] = (close - low) / (high - low + 1e-10) - 0.5
        
        # Large move detection
        log_returns = np.log(close / close.shift(1))
        vol = log_returns.rolling(24).std()
        features["large_move"] = (np.abs(log_returns) > 2 * vol).astype(int)
        
        return features
    
    def _derivatives_features(
        self,
        funding: Optional[pd.Series],
        oi: Optional[pd.Series],
        liquidations: Optional[pd.DataFrame]
    ) -> pd.DataFrame:
        """Create derivatives-based features."""
        features = pd.DataFrame()
        
        if funding is not None:
            funding = funding.reindex(features.index if len(features) > 0 else funding.index)
            features = pd.DataFrame(index=funding.index)
            
            features["funding_rate"] = funding
            features["funding_zscore"] = (funding - funding.rolling(168).mean()) / (funding.rolling(168).std() + 1e-10)
            features["funding_cumsum_24h"] = funding.rolling(3).sum()  # 3 funding periods = 24h
        
        if oi is not None:
            oi = oi.reindex(features.index if len(features) > 0 else oi.index)
            if len(features) == 0:
                features = pd.DataFrame(index=oi.index)
            
            features["oi"] = oi
            features["oi_change_1h"] = oi.pct_change(periods=1)
            features["oi_change_24h"] = oi.pct_change(periods=24)
            features["oi_zscore"] = (oi - oi.rolling(168).mean()) / (oi.rolling(168).std() + 1e-10)
        
        if liquidations is not None and len(features) > 0:
            liquidations = liquidations.reindex(features.index)
            
            if "long_liq" in liquidations.columns and "short_liq" in liquidations.columns:
                features["liq_imbalance"] = (
                    (liquidations["long_liq"] - liquidations["short_liq"]) /
                    (liquidations["long_liq"] + liquidations["short_liq"] + 1e-10)
                )
                features["total_liq"] = liquidations["long_liq"] + liquidations["short_liq"]
                features["liq_1h"] = features["total_liq"].rolling(60).sum()
        
        return features
    
    def _calculate_rsi(self, close: pd.Series, period: int) -> pd.Series:
        """Calculate RSI manually."""
        delta = close.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        
        rs = avg_gain / (avg_loss + 1e-10)
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def _calculate_atr(
        self, 
        high: pd.Series, 
        low: pd.Series, 
        close: pd.Series, 
        period: int
    ) -> pd.Series:
        """Calculate ATR manually."""
        tr1 = high - low
        tr2 = np.abs(high - close.shift(1))
        tr3 = np.abs(low - close.shift(1))
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        
        return atr


class TargetCreator:
    """Create target variables for training."""
    
    @staticmethod
    def create_direction_target(
        close: pd.Series,
        horizon: int,
        threshold: float = 0.0
    ) -> pd.Series:
        """
        Create binary direction target.
        
        Args:
            close: Close price series
            horizon: Forward-looking periods
            threshold: Minimum move to count as direction (default 0)
            
        Returns:
            Binary series (1 = up, 0 = down)
        """
        future_return = close.shift(-horizon) / close - 1
        return (future_return > threshold).astype(int)
    
    @staticmethod
    def create_magnitude_target(
        close: pd.Series,
        horizon: int
    ) -> pd.Series:
        """
        Create magnitude target (log return).
        
        Args:
            close: Close price series
            horizon: Forward-looking periods
            
        Returns:
            Log return series
        """
        return np.log(close.shift(-horizon) / close)
    
    @staticmethod
    def create_volatility_target(
        close: pd.Series,
        horizon: int
    ) -> pd.Series:
        """
        Create realized volatility target.
        
        Args:
            close: Close price series
            horizon: Forward-looking periods
            
        Returns:
            Realized volatility series
        """
        log_returns = np.log(close / close.shift(1))
        
        # Forward-looking realized volatility
        rv = log_returns.shift(-horizon).rolling(horizon).std() * np.sqrt(horizon)
        
        return rv



