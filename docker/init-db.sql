-- Initialize TimescaleDB extensions and tables

-- Enable TimescaleDB
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- OHLCV Table
CREATE TABLE IF NOT EXISTS ohlcv (
    time TIMESTAMPTZ NOT NULL,
    asset VARCHAR(10) NOT NULL,
    interval VARCHAR(5) NOT NULL,
    open DOUBLE PRECISION,
    high DOUBLE PRECISION,
    low DOUBLE PRECISION,
    close DOUBLE PRECISION,
    volume DOUBLE PRECISION,
    quote_volume DOUBLE PRECISION,
    trades INTEGER,
    taker_buy_volume DOUBLE PRECISION
);

-- Convert to hypertable
SELECT create_hypertable('ohlcv', 'time', if_not_exists => TRUE);

-- Create index
CREATE INDEX IF NOT EXISTS idx_ohlcv_asset_interval ON ohlcv (asset, interval, time DESC);

-- Market Structure Table
CREATE TABLE IF NOT EXISTS market_structure (
    time TIMESTAMPTZ NOT NULL,
    asset VARCHAR(10) NOT NULL,
    funding_rate DOUBLE PRECISION,
    open_interest DOUBLE PRECISION,
    long_liquidations DOUBLE PRECISION,
    short_liquidations DOUBLE PRECISION
);

SELECT create_hypertable('market_structure', 'time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_ms_asset ON market_structure (asset, time DESC);

-- Predictions Table (for tracking accuracy)
CREATE TABLE IF NOT EXISTS predictions (
    id SERIAL,
    time TIMESTAMPTZ NOT NULL,
    asset VARCHAR(10) NOT NULL,
    horizon_hours INTEGER,
    p_up DOUBLE PRECISION,
    expected_move DOUBLE PRECISION,
    volatility DOUBLE PRECISION,
    confidence VARCHAR(10),
    regime VARCHAR(20),
    model_version VARCHAR(20),
    -- Actual outcome (filled later)
    actual_direction INTEGER,
    actual_move DOUBLE PRECISION,
    PRIMARY KEY (id, time)
);

SELECT create_hypertable('predictions', 'time', if_not_exists => TRUE);

-- Model Metrics Table
CREATE TABLE IF NOT EXISTS model_metrics (
    time TIMESTAMPTZ NOT NULL,
    model_version VARCHAR(20) NOT NULL,
    metric_name VARCHAR(50) NOT NULL,
    metric_value DOUBLE PRECISION
);

SELECT create_hypertable('model_metrics', 'time', if_not_exists => TRUE);

-- Continuous Aggregates for faster queries
CREATE MATERIALIZED VIEW IF NOT EXISTS ohlcv_hourly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS bucket,
    asset,
    first(open, time) AS open,
    max(high) AS high,
    min(low) AS low,
    last(close, time) AS close,
    sum(volume) AS volume
FROM ohlcv
WHERE interval = '1m'
GROUP BY bucket, asset
WITH NO DATA;

-- Refresh policy
SELECT add_continuous_aggregate_policy('ohlcv_hourly',
    start_offset => INTERVAL '3 hours',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => TRUE
);

-- Data retention policy (keep 1 year of minute data)
SELECT add_retention_policy('ohlcv', INTERVAL '365 days', if_not_exists => TRUE);
SELECT add_retention_policy('market_structure', INTERVAL '365 days', if_not_exists => TRUE);
SELECT add_retention_policy('predictions', INTERVAL '365 days', if_not_exists => TRUE);

-- Grant permissions
GRANT ALL ON ALL TABLES IN SCHEMA public TO postgres;

