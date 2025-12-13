#!/usr/bin/env python3
"""
Model Training Script for VorLoop Prediction Engine.

Usage:
    python scripts/train_model.py --asset BTC --days 90
"""
import argparse
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

import numpy as np
import pandas as pd
from loguru import logger

from models.prediction_model import DirectionModel, MagnitudeModel, ModelConfig
from models.volatility_model import GARCHVolatilityModel, VolatilityConfig
from models.feature_engineering import FeatureEngineer, TargetCreator


def generate_synthetic_data(days: int = 90) -> pd.DataFrame:
    """Generate synthetic OHLCV data for testing."""
    logger.info(f"Generating {days} days of synthetic data...")
    
    periods = days * 24  # Hourly data
    timestamps = pd.date_range(
        end=datetime.utcnow(),
        periods=periods,
        freq='H'
    )
    
    # Generate random walk price
    np.random.seed(42)
    returns = np.random.normal(0.0001, 0.01, periods)
    price = 40000 * np.exp(np.cumsum(returns))
    
    # Add some structure
    volatility = 0.01 + 0.005 * np.sin(np.arange(periods) * 2 * np.pi / 168)  # Weekly cycle
    
    df = pd.DataFrame({
        'timestamp': timestamps,
        'open': price * (1 + np.random.normal(0, 0.001, periods)),
        'high': price * (1 + np.abs(np.random.normal(0, volatility))),
        'low': price * (1 - np.abs(np.random.normal(0, volatility))),
        'close': price,
        'volume': np.random.exponential(100, periods),
    })
    
    # Ensure high >= low
    df['high'] = df[['open', 'high', 'low', 'close']].max(axis=1)
    df['low'] = df[['open', 'high', 'low', 'close']].min(axis=1)
    
    return df.set_index('timestamp')


def train_models(asset: str, days: int, output_dir: Path):
    """Train all prediction models."""
    logger.info(f"Training models for {asset} with {days} days of data")
    
    # Generate or load data
    df = generate_synthetic_data(days)
    logger.info(f"Data shape: {df.shape}")
    
    # Create features
    fe = FeatureEngineer()
    features = fe.create_features(df)
    logger.info(f"Features shape: {features.shape}")
    
    # Create targets
    tc = TargetCreator()
    horizon = 4  # 4 hours ahead
    
    y_direction = tc.create_direction_target(df['close'], horizon)
    y_magnitude = tc.create_magnitude_target(df['close'], horizon)
    
    # Align features and targets
    valid_idx = features.dropna().index.intersection(y_direction.dropna().index)
    X = features.loc[valid_idx]
    y_dir = y_direction.loc[valid_idx]
    y_mag = y_magnitude.loc[valid_idx]
    
    logger.info(f"Training samples: {len(X)}")
    
    # Train/test split (walk-forward style)
    split_idx = int(len(X) * 0.8)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_dir_train, y_dir_test = y_dir.iloc[:split_idx], y_dir.iloc[split_idx:]
    y_mag_train, y_mag_test = y_mag.iloc[:split_idx], y_mag.iloc[split_idx:]
    
    # Train Direction Model
    logger.info("Training direction model...")
    config = ModelConfig()
    direction_model = DirectionModel(config)
    dir_metrics = direction_model.train(X_train, y_dir_train, X_test, y_dir_test)
    logger.info(f"Direction metrics: {dir_metrics}")
    
    # Train Magnitude Model
    logger.info("Training magnitude model...")
    magnitude_model = MagnitudeModel(config)
    mag_metrics = magnitude_model.train(X_train, y_mag_train, X_test, y_mag_test)
    logger.info(f"Magnitude metrics: {mag_metrics}")
    
    # Train Volatility Model
    logger.info("Training volatility model...")
    returns = np.log(df['close'] / df['close'].shift(1)).dropna()
    vol_config = VolatilityConfig()
    volatility_model = GARCHVolatilityModel(vol_config)
    vol_params = volatility_model.fit(returns)
    logger.info(f"Volatility params: {vol_params}")
    
    # Save models
    output_dir.mkdir(parents=True, exist_ok=True)
    
    direction_model.save(output_dir / "direction_model.pkl")
    magnitude_model.save(output_dir / "magnitude_model.pkl")
    volatility_model.save(output_dir / "volatility_model.pkl")
    
    # Save metadata
    import pickle
    metadata = {
        "asset": asset,
        "training_days": days,
        "last_trained": datetime.utcnow(),
        "validation_metrics": {
            "direction": dir_metrics,
            "magnitude": mag_metrics,
        },
        "features": list(X.columns),
    }
    
    with open(output_dir / "metadata.pkl", "wb") as f:
        pickle.dump(metadata, f)
    
    logger.info(f"Models saved to {output_dir}")
    
    return dir_metrics, mag_metrics


def main():
    parser = argparse.ArgumentParser(description="Train prediction models")
    parser.add_argument("--asset", type=str, default="BTC", help="Asset to train on")
    parser.add_argument("--days", type=int, default=90, help="Days of training data")
    parser.add_argument("--output", type=str, default="backend/models/trained", help="Output directory")
    
    args = parser.parse_args()
    
    output_dir = Path(args.output)
    
    try:
        train_models(args.asset, args.days, output_dir)
        logger.info("Training complete!")
    except Exception as e:
        logger.error(f"Training failed: {e}")
        raise


if __name__ == "__main__":
    main()



