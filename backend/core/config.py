"""
Application configuration using Pydantic Settings.
"""
from functools import lru_cache
from typing import Optional, List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    
    # Application
    app_name: str = "Crypto Prediction Engine"
    debug: bool = False
    environment: str = "development"
    
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 4
    
    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/crypto_prediction"
    
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    
    # Binance API
    binance_api_key: Optional[str] = None
    binance_api_secret: Optional[str] = None
    
    # Bybit API (fallback)
    bybit_api_key: Optional[str] = None
    bybit_api_secret: Optional[str] = None
    
    # Model Configuration
    model_version: str = "v1.0.0"
    model_retrain_hour: int = 0  # UTC hour for daily retrain
    min_confidence_threshold: float = 0.55
    
    # Risk Controls
    max_volatility_threshold: float = 0.15
    circuit_breaker_losses: int = 5
    max_position_pct: float = 0.1
    
    # CORS
    cors_origins: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    
    # Monitoring
    sentry_dsn: Optional[str] = None
    
    # Feature Flags
    enable_onchain_data: bool = False
    enable_websocket: bool = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()

