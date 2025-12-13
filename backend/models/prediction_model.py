"""
LightGBM-based prediction models for direction and magnitude.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any
import numpy as np
import pandas as pd
from pathlib import Path
import pickle
from loguru import logger

try:
    import lightgbm as lgb
    LIGHTGBM_AVAILABLE = True
except ImportError:
    LIGHTGBM_AVAILABLE = False
    logger.warning("LightGBM not available, using fallback models")


@dataclass
class ModelConfig:
    """Configuration for prediction models."""
    # Training
    training_window_days: int = 90
    validation_window_days: int = 30
    purge_gap_hours: int = 24
    
    # LightGBM params
    num_leaves: int = 31
    learning_rate: float = 0.05
    n_estimators: int = 500
    min_child_samples: int = 20
    reg_alpha: float = 0.1
    reg_lambda: float = 0.1
    
    # Features
    feature_columns: List[str] = None
    
    def __post_init__(self):
        if self.feature_columns is None:
            self.feature_columns = [
                # Price features
                "returns_5m", "returns_15m", "returns_1h", "returns_4h", "returns_24h",
                "volatility_1h", "volatility_24h",
                "high_low_range", "close_position",
                
                # Technical indicators
                "rsi_14", "rsi_7", "macd_signal", "bb_position", "ema_cross",
                
                # Microstructure
                "bid_ask_imbalance", "trade_flow_imbalance",
                "cvd_5m", "cvd_1h", "large_trade_ratio",
                
                # Derivatives
                "funding_rate", "funding_zscore",
                "oi_change_1h", "oi_change_24h",
                "long_short_ratio", "basis_annualized", "liq_imbalance_1h",
            ]


class DirectionModel:
    """LightGBM classifier for predicting price direction."""
    
    def __init__(self, config: Optional[ModelConfig] = None):
        self.config = config or ModelConfig()
        self.model = None
        self.feature_importance: Dict[str, float] = {}
        self.trained_at: Optional[datetime] = None
        self.metrics: Dict[str, float] = {}
    
    def train(
        self, 
        X: pd.DataFrame, 
        y: pd.Series,
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[pd.Series] = None
    ) -> Dict[str, float]:
        """Train the direction classifier."""
        if not LIGHTGBM_AVAILABLE:
            logger.warning("LightGBM not available, training skipped")
            return {}
        
        # Create dataset
        train_data = lgb.Dataset(X, label=y)
        val_data = lgb.Dataset(X_val, label=y_val, reference=train_data) if X_val is not None else None
        
        # Training parameters
        params = {
            "objective": "binary",
            "metric": ["binary_logloss", "auc"],
            "num_leaves": self.config.num_leaves,
            "learning_rate": self.config.learning_rate,
            "reg_alpha": self.config.reg_alpha,
            "reg_lambda": self.config.reg_lambda,
            "min_child_samples": self.config.min_child_samples,
            "verbose": -1,
            "seed": 42,
        }
        
        # Train with early stopping
        callbacks = []
        if val_data:
            callbacks.append(lgb.early_stopping(stopping_rounds=50))
        
        self.model = lgb.train(
            params,
            train_data,
            num_boost_round=self.config.n_estimators,
            valid_sets=[val_data] if val_data else None,
            callbacks=callbacks if callbacks else None,
        )
        
        self.trained_at = datetime.utcnow()
        
        # Store feature importance
        importance = self.model.feature_importance(importance_type="gain")
        self.feature_importance = dict(zip(X.columns, importance))
        
        # Calculate validation metrics
        if X_val is not None and y_val is not None:
            y_pred = self.predict_proba(X_val)
            self.metrics = self._calculate_metrics(y_val, y_pred)
        
        return self.metrics
    
    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Predict probability of up move."""
        if self.model is None:
            # Fallback to 0.5
            return np.full(len(X), 0.5)
        
        return self.model.predict(X)
    
    def predict(self, X: pd.DataFrame, threshold: float = 0.5) -> np.ndarray:
        """Predict direction (1 = up, 0 = down)."""
        proba = self.predict_proba(X)
        return (proba > threshold).astype(int)
    
    def _calculate_metrics(
        self, 
        y_true: pd.Series, 
        y_pred_proba: np.ndarray
    ) -> Dict[str, float]:
        """Calculate classification metrics."""
        from sklearn.metrics import accuracy_score, precision_score, recall_score, roc_auc_score
        
        y_pred = (y_pred_proba > 0.5).astype(int)
        
        return {
            "accuracy": accuracy_score(y_true, y_pred),
            "precision": precision_score(y_true, y_pred, zero_division=0),
            "recall": recall_score(y_true, y_pred, zero_division=0),
            "auc": roc_auc_score(y_true, y_pred_proba) if len(np.unique(y_true)) > 1 else 0.5,
        }
    
    def save(self, path: Path):
        """Save model to disk."""
        path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "model": self.model,
            "config": self.config,
            "feature_importance": self.feature_importance,
            "trained_at": self.trained_at,
            "metrics": self.metrics,
        }
        
        with open(path, "wb") as f:
            pickle.dump(data, f)
        
        logger.info(f"Direction model saved to {path}")
    
    @classmethod
    def load(cls, path: Path) -> "DirectionModel":
        """Load model from disk."""
        with open(path, "rb") as f:
            data = pickle.load(f)
        
        instance = cls(config=data.get("config"))
        instance.model = data.get("model")
        instance.feature_importance = data.get("feature_importance", {})
        instance.trained_at = data.get("trained_at")
        instance.metrics = data.get("metrics", {})
        
        logger.info(f"Direction model loaded from {path}")
        return instance


class MagnitudeModel:
    """LightGBM regressor for predicting move magnitude."""
    
    def __init__(self, config: Optional[ModelConfig] = None):
        self.config = config or ModelConfig()
        self.model = None
        self.feature_importance: Dict[str, float] = {}
        self.trained_at: Optional[datetime] = None
        self.metrics: Dict[str, float] = {}
    
    def train(
        self, 
        X: pd.DataFrame, 
        y: pd.Series,
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[pd.Series] = None
    ) -> Dict[str, float]:
        """Train the magnitude regressor."""
        if not LIGHTGBM_AVAILABLE:
            logger.warning("LightGBM not available, training skipped")
            return {}
        
        # Create dataset
        train_data = lgb.Dataset(X, label=y)
        val_data = lgb.Dataset(X_val, label=y_val, reference=train_data) if X_val is not None else None
        
        # Training parameters
        params = {
            "objective": "regression",
            "metric": ["mse", "mae"],
            "num_leaves": self.config.num_leaves,
            "learning_rate": self.config.learning_rate,
            "reg_alpha": self.config.reg_alpha,
            "reg_lambda": self.config.reg_lambda,
            "min_child_samples": self.config.min_child_samples,
            "verbose": -1,
            "seed": 42,
        }
        
        # Train with early stopping
        callbacks = []
        if val_data:
            callbacks.append(lgb.early_stopping(stopping_rounds=50))
        
        self.model = lgb.train(
            params,
            train_data,
            num_boost_round=self.config.n_estimators,
            valid_sets=[val_data] if val_data else None,
            callbacks=callbacks if callbacks else None,
        )
        
        self.trained_at = datetime.utcnow()
        
        # Store feature importance
        importance = self.model.feature_importance(importance_type="gain")
        self.feature_importance = dict(zip(X.columns, importance))
        
        # Calculate validation metrics
        if X_val is not None and y_val is not None:
            y_pred = self.predict(X_val)
            self.metrics = self._calculate_metrics(y_val, y_pred)
        
        return self.metrics
    
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Predict move magnitude."""
        if self.model is None:
            # Fallback to 0
            return np.zeros(len(X))
        
        return self.model.predict(X)
    
    def _calculate_metrics(
        self, 
        y_true: pd.Series, 
        y_pred: np.ndarray
    ) -> Dict[str, float]:
        """Calculate regression metrics."""
        from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
        
        return {
            "mse": mean_squared_error(y_true, y_pred),
            "rmse": np.sqrt(mean_squared_error(y_true, y_pred)),
            "mae": mean_absolute_error(y_true, y_pred),
            "r2": r2_score(y_true, y_pred),
        }
    
    def save(self, path: Path):
        """Save model to disk."""
        path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "model": self.model,
            "config": self.config,
            "feature_importance": self.feature_importance,
            "trained_at": self.trained_at,
            "metrics": self.metrics,
        }
        
        with open(path, "wb") as f:
            pickle.dump(data, f)
        
        logger.info(f"Magnitude model saved to {path}")
    
    @classmethod
    def load(cls, path: Path) -> "MagnitudeModel":
        """Load model from disk."""
        with open(path, "rb") as f:
            data = pickle.load(f)
        
        instance = cls(config=data.get("config"))
        instance.model = data.get("model")
        instance.feature_importance = data.get("feature_importance", {})
        instance.trained_at = data.get("trained_at")
        instance.metrics = data.get("metrics", {})
        
        logger.info(f"Magnitude model loaded from {path}")
        return instance


class EnsemblePredictor:
    """Ensemble of direction and magnitude models."""
    
    def __init__(
        self,
        direction_model: DirectionModel,
        magnitude_model: MagnitudeModel
    ):
        self.direction_model = direction_model
        self.magnitude_model = magnitude_model
    
    def predict(self, X: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """
        Generate predictions.
        
        Returns:
            Tuple of (direction_proba, magnitude)
        """
        p_up = self.direction_model.predict_proba(X)
        magnitude = self.magnitude_model.predict(X)
        
        # Adjust magnitude sign based on direction
        # If p_up > 0.5, magnitude is positive; else negative
        adjusted_magnitude = np.where(p_up > 0.5, np.abs(magnitude), -np.abs(magnitude))
        
        return p_up, adjusted_magnitude
    
    def get_feature_importance(self) -> Dict[str, Dict[str, float]]:
        """Get combined feature importance."""
        return {
            "direction": self.direction_model.feature_importance,
            "magnitude": self.magnitude_model.feature_importance,
        }



