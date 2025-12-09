"""
GARCH-based volatility model for prediction cones.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Tuple
import numpy as np
import pandas as pd
from pathlib import Path
import pickle
from loguru import logger

try:
    from arch import arch_model
    from arch.univariate import GARCH, EGARCH
    ARCH_AVAILABLE = True
except ImportError:
    ARCH_AVAILABLE = False
    logger.warning("arch package not available, using simple volatility estimation")


@dataclass
class VolatilityConfig:
    """Configuration for volatility models."""
    # GARCH parameters
    p: int = 1  # GARCH lag order
    q: int = 1  # ARCH lag order
    o: int = 0  # Asymmetric order (for EGARCH/GJR)
    
    # Model type
    model_type: str = "GARCH"  # GARCH, EGARCH, GJR-GARCH
    
    # Distribution
    dist: str = "t"  # normal, t, skewt
    
    # Estimation
    rescale: bool = True
    
    # Forecast
    horizon: int = 24  # hours


class GARCHVolatilityModel:
    """GARCH model for volatility forecasting."""
    
    def __init__(self, config: Optional[VolatilityConfig] = None):
        self.config = config or VolatilityConfig()
        self.model = None
        self.fitted_model = None
        self.last_variance: Optional[float] = None
        self.trained_at: Optional[datetime] = None
        self.params: Dict[str, float] = {}
    
    def fit(self, returns: pd.Series) -> Dict[str, float]:
        """
        Fit GARCH model to return series.
        
        Args:
            returns: Log returns series (should be percentage * 100)
        """
        if not ARCH_AVAILABLE:
            logger.warning("arch not available, using exponential smoothing")
            self._fit_simple(returns)
            return self.params
        
        # Scale returns for numerical stability
        scaled_returns = returns * 100
        
        # Create GARCH model
        if self.config.model_type == "EGARCH":
            vol = EGARCH(p=self.config.p, q=self.config.q, o=self.config.o)
        else:
            vol = GARCH(p=self.config.p, q=self.config.q, o=self.config.o)
        
        self.model = arch_model(
            scaled_returns,
            vol=vol,
            dist=self.config.dist,
            rescale=self.config.rescale
        )
        
        # Fit model
        try:
            self.fitted_model = self.model.fit(disp="off", show_warning=False)
            
            # Store parameters
            self.params = {
                "omega": self.fitted_model.params.get("omega", 0),
                "alpha": self.fitted_model.params.get("alpha[1]", 0),
                "beta": self.fitted_model.params.get("beta[1]", 0),
                "nu": self.fitted_model.params.get("nu", 10),  # df for t-dist
            }
            
            # Store last conditional variance
            self.last_variance = self.fitted_model.conditional_volatility.iloc[-1] ** 2
            
            self.trained_at = datetime.utcnow()
            
            logger.info(f"GARCH model fitted: {self.params}")
            
        except Exception as e:
            logger.error(f"GARCH fitting failed: {e}")
            self._fit_simple(returns)
        
        return self.params
    
    def _fit_simple(self, returns: pd.Series):
        """Simple exponential smoothing fallback."""
        # Use EWMA volatility
        ewm_var = returns.ewm(span=24).var()
        self.last_variance = ewm_var.iloc[-1] * 10000  # Scale
        self.params = {
            "omega": 0,
            "alpha": 0.1,
            "beta": 0.85,
        }
        self.trained_at = datetime.utcnow()
    
    def forecast(
        self, 
        horizon: int, 
        returns: Optional[pd.Series] = None
    ) -> np.ndarray:
        """
        Forecast volatility for given horizon.
        
        Args:
            horizon: Number of periods to forecast
            returns: Optional new returns data to update model
            
        Returns:
            Array of forecasted volatilities
        """
        if self.fitted_model is not None and ARCH_AVAILABLE:
            try:
                forecasts = self.fitted_model.forecast(horizon=horizon)
                # Convert variance to volatility and unscale
                vol_forecast = np.sqrt(forecasts.variance.values[-1, :]) / 100
                return vol_forecast
            except Exception as e:
                logger.warning(f"GARCH forecast failed: {e}")
        
        # Fallback: use analytical GARCH forecast
        return self._analytical_forecast(horizon)
    
    def _analytical_forecast(self, horizon: int) -> np.ndarray:
        """Analytical GARCH variance forecast."""
        omega = self.params.get("omega", 0.01)
        alpha = self.params.get("alpha", 0.1)
        beta = self.params.get("beta", 0.85)
        
        # Unconditional variance
        persistence = alpha + beta
        if persistence < 1:
            long_run_var = omega / (1 - persistence)
        else:
            long_run_var = self.last_variance or 0.0004  # 2% daily vol
        
        current_var = self.last_variance or long_run_var
        
        # Forecast variance
        forecasts = np.zeros(horizon)
        for h in range(horizon):
            if h == 0:
                forecasts[h] = current_var
            else:
                forecasts[h] = omega + persistence * forecasts[h-1]
        
        # Mean reversion toward unconditional variance
        forecasts = forecasts * 0.7 + long_run_var * 0.3
        
        # Convert to volatility (standard deviation) and unscale
        return np.sqrt(forecasts) / 100
    
    def get_current_volatility(self) -> float:
        """Get current volatility estimate."""
        if self.fitted_model is not None:
            return self.fitted_model.conditional_volatility.iloc[-1] / 100
        elif self.last_variance is not None:
            return np.sqrt(self.last_variance) / 100
        else:
            return 0.02  # Default 2% volatility
    
    def save(self, path: Path):
        """Save model to disk."""
        path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "config": self.config,
            "params": self.params,
            "last_variance": self.last_variance,
            "trained_at": self.trained_at,
            # Note: fitted_model not saved due to pickle issues with arch
        }
        
        with open(path, "wb") as f:
            pickle.dump(data, f)
        
        logger.info(f"Volatility model saved to {path}")
    
    @classmethod
    def load(cls, path: Path) -> "GARCHVolatilityModel":
        """Load model from disk."""
        with open(path, "rb") as f:
            data = pickle.load(f)
        
        instance = cls(config=data.get("config"))
        instance.params = data.get("params", {})
        instance.last_variance = data.get("last_variance")
        instance.trained_at = data.get("trained_at")
        
        logger.info(f"Volatility model loaded from {path}")
        return instance


class RealizedVolatilityEstimator:
    """Calculate realized volatility measures."""
    
    @staticmethod
    def calculate_rv(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        open_: Optional[pd.Series] = None
    ) -> Dict[str, pd.Series]:
        """
        Calculate various realized volatility measures.
        
        Returns dict with:
        - close_to_close: Standard close-to-close volatility
        - parkinson: Parkinson (high-low) volatility
        - garman_klass: Garman-Klass volatility
        - rogers_satchell: Rogers-Satchell volatility
        """
        log_hl = np.log(high / low)
        log_co = np.log(close / close.shift(1))
        
        # Close-to-close
        cc_vol = log_co.rolling(24).std() * np.sqrt(24)
        
        # Parkinson (high-low)
        parkinson = np.sqrt((log_hl ** 2).rolling(24).mean() / (4 * np.log(2)))
        
        # Garman-Klass (requires open)
        if open_ is not None:
            log_oc = np.log(open_ / close.shift(1))
            log_co_curr = np.log(close / open_)
            
            gk = 0.5 * log_hl ** 2 - (2 * np.log(2) - 1) * log_co_curr ** 2
            garman_klass = np.sqrt(gk.rolling(24).mean())
        else:
            garman_klass = parkinson
        
        # Rogers-Satchell
        if open_ is not None:
            log_ho = np.log(high / open_)
            log_lo = np.log(low / open_)
            log_co_curr = np.log(close / open_)
            
            rs = log_ho * (log_ho - log_co_curr) + log_lo * (log_lo - log_co_curr)
            rogers_satchell = np.sqrt(rs.rolling(24).mean())
        else:
            rogers_satchell = parkinson
        
        return {
            "close_to_close": cc_vol,
            "parkinson": parkinson,
            "garman_klass": garman_klass,
            "rogers_satchell": rogers_satchell,
        }
    
    @staticmethod
    def calculate_vol_of_vol(volatility: pd.Series, window: int = 24) -> pd.Series:
        """Calculate volatility of volatility."""
        return volatility.rolling(window).std()
    
    @staticmethod
    def calculate_vol_regime(
        volatility: pd.Series, 
        lookback: int = 168  # 7 days hourly
    ) -> pd.Series:
        """
        Classify volatility regime.
        
        Returns categorical series: low, normal, high, extreme
        """
        rolling_mean = volatility.rolling(lookback).mean()
        rolling_std = volatility.rolling(lookback).std()
        
        z_score = (volatility - rolling_mean) / rolling_std
        
        def classify(z):
            if pd.isna(z):
                return "normal"
            if z < -1:
                return "low"
            elif z < 1:
                return "normal"
            elif z < 2:
                return "high"
            else:
                return "extreme"
        
        return z_score.apply(classify)

