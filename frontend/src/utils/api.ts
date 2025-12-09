import axios from 'axios'
import type { MarketData, Prediction, Explanation, BacktestResult } from '../types'

const API_BASE = '/api/v1'

// Create axios instance
const client = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Mock data for development
const MOCK_MODE = true // Set to false when backend is running

const generateMockCandles = (count: number) => {
  const candles = []
  let price = 42000 + Math.random() * 1000
  const now = Date.now()
  
  for (let i = count - 1; i >= 0; i--) {
    const change = (Math.random() - 0.5) * 200
    const open = price
    price = price + change
    const high = Math.max(open, price) + Math.random() * 50
    const low = Math.min(open, price) - Math.random() * 50
    
    candles.push({
      timestamp: new Date(now - i * 3600000).toISOString(),
      open,
      high,
      low,
      close: price,
      volume: 100 + Math.random() * 500,
    })
  }
  
  return candles
}

const generateMockMarketStructure = (count: number) => {
  const structure = []
  const now = Date.now()
  
  for (let i = count - 1; i >= 0; i--) {
    structure.push({
      timestamp: new Date(now - i * 3600000).toISOString(),
      funding_rate: (Math.random() - 0.5) * 0.001,
      open_interest: 15000000000 + Math.random() * 1000000000,
      oi_change_pct: (Math.random() - 0.5) * 0.05,
      long_liquidations: Math.random() * 10000000,
      short_liquidations: Math.random() * 10000000,
      cvd: (Math.random() - 0.5) * 100000,
    })
  }
  
  return structure
}

const generateMockCone = (currentPrice: number) => {
  const cone = []
  const now = Date.now()
  const volatility = 0.02
  
  for (let h = 0; h <= 4; h++) {
    const drift = 0.001 * h
    const vol = volatility * Math.sqrt(h / 24)
    
    cone.push({
      timestamp: new Date(now + h * 3600000).toISOString(),
      mid: currentPrice * (1 + drift),
      upper_1sigma: currentPrice * (1 + drift + vol),
      lower_1sigma: currentPrice * (1 + drift - vol),
      upper_2sigma: currentPrice * (1 + drift + 2 * vol),
      lower_2sigma: currentPrice * (1 + drift - 2 * vol),
    })
  }
  
  return cone
}

export const api = {
  async getMarketData(asset: string, interval: string, limit = 200): Promise<MarketData> {
    if (MOCK_MODE) {
      return {
        asset,
        interval,
        candles: generateMockCandles(limit),
        market_structure: generateMockMarketStructure(limit),
      }
    }
    
    const response = await client.post('/market-data', {
      asset,
      interval,
      limit,
    })
    return response.data
  },
  
  async getPrediction(asset: string, horizonHours: number): Promise<Prediction> {
    if (MOCK_MODE) {
      const p_up = 0.5 + (Math.random() - 0.5) * 0.3
      const currentPrice = 42500
      
      return {
        asset,
        timestamp: new Date().toISOString(),
        horizon_hours: horizonHours,
        p_up: parseFloat(p_up.toFixed(4)),
        p_down: parseFloat((1 - p_up).toFixed(4)),
        expected_move: parseFloat(((p_up - 0.5) * 0.02).toFixed(6)),
        volatility: 0.015 + Math.random() * 0.01,
        confidence: p_up > 0.6 || p_up < 0.4 ? 'high' : 'medium',
        regime: p_up > 0.55 ? 'trend-up' : p_up < 0.45 ? 'trend-down' : 'ranging',
        cone: generateMockCone(currentPrice),
      }
    }
    
    const response = await client.post('/predict', {
      asset,
      horizon_hours: horizonHours,
    })
    return response.data
  },
  
  async getExplanation(asset: string): Promise<Explanation> {
    if (MOCK_MODE) {
      return {
        asset,
        timestamp: new Date().toISOString(),
        prediction_summary: 'Model is bullish with 3 bullish and 2 bearish signals.',
        top_bullish_factors: [
          { feature: 'Momentum (1h)', value: 0.012, contribution: 25.5, direction: 'bullish' },
          { feature: 'Volume Delta', value: 15000, contribution: 18.2, direction: 'bullish' },
          { feature: 'OI Change', value: 0.03, contribution: 12.1, direction: 'bullish' },
        ],
        top_bearish_factors: [
          { feature: 'Funding Rate', value: 0.0003, contribution: -15.3, direction: 'bearish' },
          { feature: 'RSI Overbought', value: 72, contribution: -8.5, direction: 'bearish' },
        ],
        regime_explanation: 'Market showing bullish momentum with positive returns.',
        confidence_factors: ['Normal volatility', 'Strong volume confirmation'],
      }
    }
    
    const response = await client.post('/explain', { asset })
    return response.data
  },
  
  async runBacktest(
    asset: string,
    startDate: Date,
    endDate: Date,
    strategy: string
  ): Promise<BacktestResult> {
    const response = await client.post('/backtest', {
      asset,
      start_date: startDate.toISOString(),
      end_date: endDate.toISOString(),
      strategy,
      initial_capital: 10000,
      position_size_pct: 0.1,
    })
    return response.data
  },
}

