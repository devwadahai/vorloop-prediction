"""
Model Service - Manages ML models for prediction.
"""
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import numpy as np
import pandas as pd
from loguru import logger
import pickle
from pathlib import Path

from core.config import settings


class ModelService:
    """Service for managing and running prediction models."""
    
    def __init__(self):
        self.direction_model = None
        self.magnitude_model = None
        self.volatility_model = None
        self.regime_model = None
        
        self.version = settings.model_version
        self.last_trained: Optional[datetime] = None
        self.features_count = 47
        self.validation_metrics = {}
        
        self._models_loaded = False
    
    async def load_models(self):
        """Load trained models from disk."""
        models_dir = Path("models/trained")
        
        try:
            # Try to load existing models
            if (models_dir / "direction_model.pkl").exists():
                with open(models_dir / "direction_model.pkl", "rb") as f:
                    self.direction_model = pickle.load(f)
                logger.info("Loaded direction model")
            
            if (models_dir / "magnitude_model.pkl").exists():
                with open(models_dir / "magnitude_model.pkl", "rb") as f:
                    self.magnitude_model = pickle.load(f)
                logger.info("Loaded magnitude model")
            
            if (models_dir / "metadata.pkl").exists():
                with open(models_dir / "metadata.pkl", "rb") as f:
                    metadata = pickle.load(f)
                    self.last_trained = metadata.get("last_trained")
                    self.validation_metrics = metadata.get("validation_metrics", {})
            
            self._models_loaded = True
            
        except Exception as e:
            logger.warning(f"Could not load models: {e}. Using fallback.")
            self._models_loaded = False
    
    async def predict(
        self,
        asset: str,
        horizon_minutes: int,
        market_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate prediction for an asset."""
        timestamp = datetime.utcnow()
        
        # Extract features from market data
        features = self._extract_features(market_data)
        
        # Get predictions
        if self._models_loaded and self.direction_model:
            p_up = self._predict_direction(features)
            expected_move = self._predict_magnitude(features)
        else:
            # Fallback: simple momentum-based prediction
            p_up = self._fallback_direction(market_data)
            expected_move = self._fallback_magnitude(market_data, horizon_minutes)
        
        p_down = 1.0 - p_up
        
        # Estimate volatility
        volatility = self._estimate_volatility(market_data, horizon_minutes)
        
        # Detect regime
        regime = self._detect_regime(market_data, p_up, volatility)
        
        # Calculate confidence
        confidence = self._calculate_confidence(p_up, volatility, regime)
        
        # Generate prediction cone
        current_price = market_data["price"]
        cone = self._generate_cone(
            current_price=current_price,
            expected_return=expected_move,
            volatility=volatility,
            horizon_minutes=horizon_minutes,
            regime=regime
        )
        
        return {
            "asset": asset,
            "timestamp": timestamp,
            "horizon_minutes": horizon_minutes,
            "p_up": round(p_up, 4),
            "p_down": round(p_down, 4),
            "expected_move": round(expected_move, 6),
            "volatility": round(volatility, 6),
            "confidence": confidence,
            "regime": regime,
            "cone": cone,
        }
    
    async def explain(
        self,
        asset: str,
        timestamp: datetime,
        market_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Explain a prediction."""
        features = self._extract_features(market_data)
        
        # Calculate feature contributions
        contributions = self._calculate_contributions(features)
        
        # Separate bullish and bearish factors
        bullish = [c for c in contributions if c["direction"] == "bullish"]
        bearish = [c for c in contributions if c["direction"] == "bearish"]
        
        bullish.sort(key=lambda x: abs(x["contribution"]), reverse=True)
        bearish.sort(key=lambda x: abs(x["contribution"]), reverse=True)
        
        # Regime explanation
        regime = self._detect_regime(
            market_data, 
            self._fallback_direction(market_data),
            self._estimate_volatility(market_data, 4)
        )
        regime_explanation = self._explain_regime(regime, market_data)
        
        # Confidence factors
        confidence_factors = self._get_confidence_factors(market_data)
        
        # Generate summary
        p_up = self._fallback_direction(market_data)
        if p_up > 0.55:
            direction = "bullish"
        elif p_up < 0.45:
            direction = "bearish"
        else:
            direction = "neutral"
        
        summary = f"Model is {direction} with {len(bullish)} bullish and {len(bearish)} bearish signals."
        
        return {
            "asset": asset,
            "timestamp": timestamp,
            "prediction_summary": summary,
            "top_bullish_factors": bullish[:5],
            "top_bearish_factors": bearish[:5],
            "regime_explanation": regime_explanation,
            "confidence_factors": confidence_factors,
        }
    
    async def backtest(
        self,
        asset: str,
        start_date: datetime,
        end_date: datetime,
        strategy: str,
        initial_capital: float,
        position_size_pct: float
    ) -> Dict[str, Any]:
        """Run backtest simulation."""
        # For demo, generate synthetic results
        # In production, this would load historical data and simulate
        
        days = (end_date - start_date).days
        
        # Generate synthetic equity curve
        np.random.seed(42)
        daily_returns = np.random.normal(0.002, 0.02, days)
        equity = initial_capital * np.cumprod(1 + daily_returns)
        
        # Calculate metrics
        total_return = (equity[-1] - initial_capital) / initial_capital
        annualized_return = (1 + total_return) ** (365 / days) - 1
        sharpe = np.mean(daily_returns) / np.std(daily_returns) * np.sqrt(365)
        
        # Calculate drawdown
        peak = np.maximum.accumulate(equity)
        drawdown = (peak - equity) / peak
        max_drawdown = drawdown.max()
        
        # Generate trades
        num_trades = int(days * 0.3)  # ~30% of days have trades
        trades = []
        
        for i in range(num_trades):
            entry_idx = np.random.randint(0, days - 1)
            exit_idx = entry_idx + np.random.randint(1, min(5, days - entry_idx))
            
            entry_time = start_date + timedelta(days=int(entry_idx))
            exit_time = start_date + timedelta(days=int(exit_idx))
            
            direction = "long" if np.random.random() > 0.5 else "short"
            entry_price = 40000 + np.random.normal(0, 2000)
            pnl_pct = np.random.normal(0.005, 0.02)
            exit_price = entry_price * (1 + pnl_pct if direction == "long" else 1 - pnl_pct)
            
            trades.append({
                "entry_time": entry_time,
                "exit_time": exit_time,
                "direction": direction,
                "entry_price": round(entry_price, 2),
                "exit_price": round(exit_price, 2),
                "pnl": round(entry_price * pnl_pct * position_size_pct, 2),
                "pnl_pct": round(pnl_pct, 4),
            })
        
        # Win rate
        winning_trades = sum(1 for t in trades if t["pnl"] > 0)
        win_rate = winning_trades / len(trades) if trades else 0
        
        # Profit factor
        gross_profit = sum(t["pnl"] for t in trades if t["pnl"] > 0)
        gross_loss = abs(sum(t["pnl"] for t in trades if t["pnl"] < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
        
        # Buy and hold
        buy_hold_return = np.random.uniform(0.1, 0.3) if days > 30 else np.random.uniform(-0.1, 0.1)
        
        # Equity curve (sampled)
        equity_curve = []
        sample_indices = np.linspace(0, len(equity) - 1, min(100, len(equity)), dtype=int)
        for idx in sample_indices:
            equity_curve.append({
                "date": (start_date + timedelta(days=int(idx))).isoformat(),
                "equity": round(equity[idx], 2),
                "drawdown": round(drawdown[idx], 4),
            })
        
        # Sortino ratio
        downside_returns = daily_returns[daily_returns < 0]
        sortino = np.mean(daily_returns) / np.std(downside_returns) * np.sqrt(365) if len(downside_returns) > 0 else 0
        
        return {
            "asset": asset,
            "start_date": start_date,
            "end_date": end_date,
            "strategy": strategy,
            "total_return": round(total_return, 4),
            "annualized_return": round(annualized_return, 4),
            "sharpe_ratio": round(sharpe, 2),
            "sortino_ratio": round(sortino, 2),
            "max_drawdown": round(max_drawdown, 4),
            "win_rate": round(win_rate, 4),
            "profit_factor": round(profit_factor, 2),
            "total_trades": len(trades),
            "buy_hold_return": round(buy_hold_return, 4),
            "alpha": round(total_return - buy_hold_return, 4),
            "trades": trades[:20],  # Limit to 20 trades in response
            "equity_curve": equity_curve,
        }
    
    # ========================================================================
    # Private Methods
    # ========================================================================
    
    def _extract_features(self, market_data: Dict[str, Any]) -> Dict[str, float]:
        """Extract ML features from market data."""
        features = {}
        
        # Price features
        features["returns_1h"] = market_data.get("returns_1h", 0) or 0
        features["returns_24h"] = market_data.get("returns_24h", 0) or 0
        features["volatility_1h"] = market_data.get("volatility_1h", 0.02) or 0.02
        
        # Derivatives features
        features["funding_rate"] = market_data.get("funding_rate", 0) or 0
        features["open_interest"] = market_data.get("open_interest", 0) or 0
        
        # Microstructure
        features["cvd"] = market_data.get("cvd", 0) or 0
        
        return features
    
    def _predict_direction(self, features: Dict[str, float]) -> float:
        """Predict direction using trained model."""
        if self.direction_model is None:
            return 0.5
        
        X = np.array([[features.get(f, 0) for f in sorted(features.keys())]])
        prob = self.direction_model.predict_proba(X)[0][1]
        return float(prob)
    
    def _predict_magnitude(self, features: Dict[str, float]) -> float:
        """Predict magnitude using trained model."""
        if self.magnitude_model is None:
            return 0.0
        
        X = np.array([[features.get(f, 0) for f in sorted(features.keys())]])
        magnitude = self.magnitude_model.predict(X)[0]
        return float(magnitude)
    
    def _fallback_direction(self, market_data: Dict[str, Any]) -> float:
        """
        Multi-signal direction prediction using:
        - Price momentum (strongest signal)
        - CVD (volume delta) - buying/selling pressure
        - Funding rate (contrarian)
        - Open Interest changes
        """
        # Get all available signals
        returns_1h = market_data.get("returns_1h", 0) or 0
        volatility = market_data.get("volatility_1h", 0.02) or 0.02
        funding = market_data.get("funding_rate", 0) or 0
        cvd = market_data.get("cvd", 0) or 0
        oi_change = market_data.get("oi_change_24h", 0) or 0
        
        # Initialize score at neutral
        score = 0.0
        
        # 1. MOMENTUM SIGNAL (weight: 40%)
        # Normalize returns by volatility for comparable signal strength
        momentum_z = returns_1h / (volatility + 0.001)
        momentum_signal = np.tanh(momentum_z * 0.5)  # Squash to [-1, 1]
        score += momentum_signal * 0.40
        
        # 2. CVD SIGNAL (weight: 25%)
        # Positive CVD = buying pressure = bullish
        if cvd != 0:
            # Normalize CVD - typical range is -10M to +10M USD
            cvd_normalized = cvd / 5_000_000  # $5M as baseline
            cvd_signal = np.tanh(cvd_normalized)
            score += cvd_signal * 0.25
        
        # 3. FUNDING RATE SIGNAL (weight: 20%)
        # High positive funding = longs paying shorts = contrarian bearish
        # High negative funding = shorts paying longs = contrarian bullish
        if funding != 0:
            # Funding typically ranges from -0.01 to +0.01 (1%)
            funding_signal = -np.tanh(funding * 200)  # Contrarian
            score += funding_signal * 0.20
        
        # 4. OI CHANGE SIGNAL (weight: 15%)
        # Rising OI with momentum = trend continuation
        # Falling OI = position unwinding
        if oi_change != 0:
            # OI change as percentage, typically -5% to +5%
            oi_signal = np.tanh(oi_change * 10)
            # Align with momentum direction
            if returns_1h > 0:
                score += oi_signal * 0.15
            else:
                score += -oi_signal * 0.15
        
        # Convert score [-1, 1] to probability [0.15, 0.85]
        # Allow more extreme predictions but not 0% or 100%
        p_up = 0.5 + (score * 0.35)
        
        return max(0.15, min(0.85, p_up))
    
    def _fallback_magnitude(self, market_data: Dict[str, Any], horizon_minutes: int = 5) -> float:
        """Simple magnitude prediction scaled for minute horizons."""
        volatility = market_data.get("volatility_1h", 0.02) or 0.02
        returns_1h = market_data.get("returns_1h", 0) or 0
        
        # Scale volatility for minute horizon (sqrt of time)
        minute_vol = volatility * np.sqrt(horizon_minutes / 60)
        
        # Expected move is fraction of volatility in direction of momentum
        direction = 1 if returns_1h > 0 else -1
        return direction * minute_vol * 0.3
    
    def _estimate_volatility(
        self, 
        market_data: Dict[str, Any], 
        horizon_minutes: int
    ) -> float:
        """Estimate volatility for minute horizon."""
        base_vol = market_data.get("volatility_1h", 0.02) or 0.02
        
        # Scale by square root of time (convert minutes to hours)
        horizon_vol = base_vol * np.sqrt(horizon_minutes / 60)
        
        return horizon_vol
    
    def _detect_regime(
        self, 
        market_data: Dict[str, Any], 
        p_up: float,
        volatility: float
    ) -> str:
        """Detect market regime based on multiple factors."""
        returns_1h = market_data.get("returns_1h", 0) or 0
        funding = market_data.get("funding_rate", 0) or 0
        cvd = market_data.get("cvd", 0) or 0
        
        # Panic: Sharp drop with high volatility
        if returns_1h < -0.02 and volatility > 0.03:
            return "panic"
        
        # High volatility regime
        if volatility > 0.04:
            return "high-vol"
        
        # Strong trending regimes (use actual probability)
        if p_up > 0.65:
            return "trend-up"
        elif p_up < 0.35:
            return "trend-down"
        
        # Moderate trends
        if p_up > 0.55 and returns_1h > 0:
            return "trend-up"
        elif p_up < 0.45 and returns_1h < 0:
            return "trend-down"
        
        # Ranging
        return "ranging"
    
    def _calculate_confidence(
        self, 
        p_up: float, 
        volatility: float, 
        regime: str
    ) -> str:
        """Calculate prediction confidence based on signal strength."""
        # How far from 50% is our prediction?
        prob_strength = abs(p_up - 0.5) * 2  # 0 to 1 scale
        
        # Adjust for regime
        if regime == "panic":
            prob_strength *= 0.4  # Very uncertain in panic
        elif regime == "high-vol":
            prob_strength *= 0.6  # Uncertain in high vol
        elif regime in ["trend-up", "trend-down"]:
            prob_strength *= 1.2  # More confident in trends
        
        # Classify confidence
        if prob_strength > 0.25:
            return "high"
        elif prob_strength > 0.12:
            return "medium"
        else:
            return "low"
    
    def _generate_cone(
        self,
        current_price: float,
        expected_return: float,
        volatility: float,
        horizon_minutes: int,
        regime: str
    ) -> List[Dict]:
        """Generate prediction cone for minute horizons."""
        # Regime adjustments
        vol_multiplier = {
            "low-vol": 0.7,
            "ranging": 1.0,
            "trend-up": 1.0,
            "trend-down": 1.0,
            "high-vol": 1.5,
            "panic": 2.0,
        }.get(regime, 1.0)
        
        adjusted_vol = volatility * vol_multiplier
        
        # Generate minute steps (up to horizon)
        cone = []
        steps = min(horizon_minutes + 1, 11)  # Cap at 11 points (0 to 10)
        step_size = horizon_minutes / (steps - 1) if steps > 1 else 1
        
        for i in range(steps):
            m = i * step_size
            t = m / (24 * 60)  # Convert minutes to fraction of day
            sqrt_t = np.sqrt(t) if t > 0 else 0
            
            # Expected price at time t
            drift = expected_return * (m / 60)  # Scale drift for minutes
            mid_price = current_price * np.exp(drift)
            
            # Volatility bands
            vol_band = adjusted_vol * sqrt_t * 3  # Scale for visualization
            
            timestamp = datetime.utcnow() + timedelta(minutes=m)
            
            cone.append({
                "timestamp": timestamp,
                "mid": round(mid_price, 2),
                "upper_1sigma": round(current_price * np.exp(drift + vol_band), 2),
                "lower_1sigma": round(current_price * np.exp(drift - vol_band), 2),
                "upper_2sigma": round(current_price * np.exp(drift + 2 * vol_band), 2),
                "lower_2sigma": round(current_price * np.exp(drift - 2 * vol_band), 2),
            })
        
        return cone
    
    def _calculate_contributions(
        self, 
        features: Dict[str, float]
    ) -> List[Dict]:
        """Calculate feature contributions to prediction."""
        contributions = []
        
        # Define feature interpretations with proper scaling
        # contribution_scale converts raw value to a 0-100 contribution score
        feature_config = {
            "returns_1h": {
                "name": "Momentum (1h)",
                "direction": "bullish" if features.get("returns_1h", 0) > 0 else "bearish",
                "scale": 1000,  # 0.01 (1%) becomes 10 contribution
            },
            "returns_24h": {
                "name": "Momentum (24h)",
                "direction": "bullish" if features.get("returns_24h", 0) > 0 else "bearish",
                "scale": 500,
            },
            "funding_rate": {
                "name": "Funding Rate",
                "direction": "bearish" if features.get("funding_rate", 0) > 0.0001 else "bullish",
                "scale": 50000,  # 0.0001 becomes 5 contribution
            },
            "cvd": {
                "name": "Volume Delta",
                "direction": "bullish" if features.get("cvd", 0) > 0 else "bearish",
                "scale": 0.00001,  # $1M becomes 10 contribution
            },
            "volatility_1h": {
                "name": "Volatility",
                "direction": "neutral",
                "scale": 500,
            },
        }
        
        for feature, value in features.items():
            if feature in feature_config:
                config = feature_config[feature]
                # Scale contribution to reasonable 0-100 range
                contribution = min(abs(value) * config["scale"], 50)  # Cap at 50
                contributions.append({
                    "feature": config["name"],
                    "value": round(value, 6) if abs(value) < 1000 else round(value / 1e6, 2),
                    "contribution": round(contribution, 1),
                    "direction": config["direction"],
                })
        
        return contributions
    
    def _explain_regime(self, regime: str, market_data: Dict[str, Any]) -> str:
        """Generate regime explanation."""
        explanations = {
            "trend-up": "Market showing bullish momentum with positive returns and buyer dominance.",
            "trend-down": "Market showing bearish momentum with negative returns and seller dominance.",
            "ranging": "Market in consolidation with no clear directional bias.",
            "high-vol": "Elevated volatility detected. Price swings are larger than normal.",
            "panic": "Extreme volatility with sharp downward pressure. Risk is elevated.",
            "low-vol": "Low volatility environment. Smaller moves expected.",
        }
        return explanations.get(regime, "Unknown regime.")
    
    def _get_confidence_factors(self, market_data: Dict[str, Any]) -> List[str]:
        """Get factors affecting prediction confidence."""
        factors = []
        
        volatility = market_data.get("volatility_1h", 0.02) or 0.02
        funding = market_data.get("funding_rate", 0) or 0
        
        if volatility > 0.04:
            factors.append("High volatility reduces confidence")
        elif volatility < 0.01:
            factors.append("Low volatility increases confidence")
        
        if abs(funding) > 0.001:
            factors.append("Extreme funding rate suggests crowded positioning")
        
        if not factors:
            factors.append("Normal market conditions")
        
        return factors

