// Market Data Types
export interface OHLCV {
  timestamp: string
  open: number
  high: number
  low: number
  close: number
  volume: number
}

export interface MarketStructure {
  timestamp: string
  funding_rate: number | null
  open_interest: number | null
  oi_change_pct: number | null
  long_liquidations: number | null
  short_liquidations: number | null
  cvd: number | null
}

export interface MarketData {
  asset: string
  interval: string
  candles: OHLCV[]
  market_structure: MarketStructure[]
}

// Prediction Types
export interface ConePoint {
  timestamp: string
  mid: number
  upper_1sigma: number
  lower_1sigma: number
  upper_2sigma: number
  lower_2sigma: number
}

export interface Prediction {
  asset: string
  timestamp: string
  horizon_minutes: number
  p_up: number
  p_down: number
  expected_move: number
  volatility: number
  confidence: 'low' | 'medium' | 'high'
  regime: 'trend-up' | 'trend-down' | 'ranging' | 'high-vol' | 'panic'
  cone: ConePoint[]
}

// Explanation Types
export interface FeatureContribution {
  feature: string
  value: number
  contribution: number
  direction: 'bullish' | 'bearish' | 'neutral'
}

export interface Explanation {
  asset: string
  timestamp: string
  prediction_summary: string
  top_bullish_factors: FeatureContribution[]
  top_bearish_factors: FeatureContribution[]
  regime_explanation: string
  confidence_factors: string[]
}

// Backtest Types
export interface Trade {
  entry_time: string
  exit_time: string
  direction: 'long' | 'short'
  entry_price: number
  exit_price: number
  pnl: number
  pnl_pct: number
}

export interface BacktestResult {
  asset: string
  start_date: string
  end_date: string
  strategy: string
  total_return: number
  annualized_return: number
  sharpe_ratio: number
  sortino_ratio: number
  max_drawdown: number
  win_rate: number
  profit_factor: number
  total_trades: number
  buy_hold_return: number
  alpha: number
  trades: Trade[]
  equity_curve: { date: string; equity: number; drawdown: number }[]
}

// UI State Types
export interface Asset {
  symbol: string
  name: string
  enabled: boolean
}

export type TimeInterval = '1m' | '5m' | '15m' | '1h' | '4h' | '1d'

export type ChartOverlay = 'prediction' | 'liquidations' | 'volume' | 'oi'

