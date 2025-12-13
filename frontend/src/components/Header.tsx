import { Settings, Bell, ChevronDown } from 'lucide-react'
import { useStore } from '../state/store'
import { formatPrice, formatSignedPercent } from '../utils/format'
import type { TimeInterval } from '../types'

const ASSETS = ['BTC', 'ETH', 'SOL', 'BNB']
const INTERVALS: { value: TimeInterval; label: string }[] = [
  { value: '1m', label: '1m' },
  { value: '3m', label: '3m' },
  { value: '5m', label: '5m' },
  { value: '10m', label: '10m' },
  { value: '15m', label: '15m' },
  { value: '1h', label: '1H' },
  { value: '4h', label: '4H' },
  { value: '1d', label: '1D' },
]

export function Header() {
  const { 
    selectedAsset, 
    setSelectedAsset, 
    selectedInterval, 
    setSelectedInterval,
    marketData,
    prediction 
  } = useStore()
  
  // Get current price from latest candle
  const currentPrice = marketData?.candles?.slice(-1)[0]?.close ?? 0
  const previousPrice = marketData?.candles?.slice(-2, -1)[0]?.close ?? currentPrice
  const priceChange = currentPrice && previousPrice 
    ? (currentPrice - previousPrice) / previousPrice 
    : 0
  
  return (
    <header className="h-16 border-b border-terminal-border bg-terminal-surface/50 backdrop-blur-sm">
      <div className="h-full px-4 flex items-center justify-between">
        {/* Logo & Asset Selector */}
        <div className="flex items-center gap-6">
          {/* Asset Selector */}
          <div className="flex items-center gap-1 bg-terminal-bg rounded-lg p-1">
            {ASSETS.map((asset) => (
              <button
                key={asset}
                onClick={() => setSelectedAsset(asset)}
                className={`px-3 py-1.5 rounded-md font-mono text-sm transition-all ${
                  selectedAsset === asset
                    ? 'bg-accent text-white'
                    : 'text-terminal-muted hover:text-terminal-text hover:bg-terminal-border/50'
                }`}
              >
                {asset}
              </button>
            ))}
          </div>
          
          {/* Interval Selector */}
          <div className="flex items-center gap-1 bg-terminal-bg rounded-lg p-1">
            {INTERVALS.map(({ value, label }) => (
              <button
                key={value}
                onClick={() => setSelectedInterval(value)}
                className={`px-2.5 py-1.5 rounded-md font-mono text-xs transition-all ${
                  selectedInterval === value
                    ? 'bg-terminal-border text-terminal-text'
                    : 'text-terminal-muted hover:text-terminal-text'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
        
        {/* Price Display */}
        <div className="flex items-center gap-8">
          {/* Current Price */}
          <div className="text-right">
            <div className="flex items-center gap-2">
              <span className="font-mono text-2xl font-semibold tabular-nums">
                ${formatPrice(currentPrice)}
              </span>
              <span className={`font-mono text-sm ${priceChange >= 0 ? 'text-bull' : 'text-bear'}`}>
                {formatSignedPercent(priceChange)}
              </span>
            </div>
            <div className="text-xs text-terminal-muted">
              {selectedAsset}/USDT
            </div>
          </div>
          
          {/* Prediction Indicator */}
          {prediction && (
            <div className="flex items-center gap-3 px-4 py-2 rounded-lg bg-terminal-bg border border-terminal-border">
              <div className="text-center">
                <div className="text-xs text-terminal-muted mb-0.5">Prediction</div>
                <div className={`font-mono font-semibold ${prediction.p_up > 0.5 ? 'text-bull' : 'text-bear'}`}>
                  {prediction.p_up > 0.5 ? '↑' : '↓'} {Math.round(Math.max(prediction.p_up, prediction.p_down) * 100)}%
                </div>
              </div>
              <div className="w-px h-8 bg-terminal-border" />
              <div className="text-center">
                <div className="text-xs text-terminal-muted mb-0.5">Regime</div>
                <div className="font-mono text-sm capitalize">
                  {prediction.regime.replace('-', ' ')}
                </div>
              </div>
              <div className="w-px h-8 bg-terminal-border" />
              <div className="text-center">
                <div className="text-xs text-terminal-muted mb-0.5">Confidence</div>
                <div className={`font-mono text-sm capitalize ${
                  prediction.confidence === 'high' ? 'text-bull' :
                  prediction.confidence === 'low' ? 'text-bear' :
                  'text-terminal-text'
                }`}>
                  {prediction.confidence}
                </div>
              </div>
            </div>
          )}
        </div>
        
        {/* Right Actions */}
        <div className="flex items-center gap-2">
          <button className="p-2 rounded-lg hover:bg-terminal-border/50 text-terminal-muted hover:text-terminal-text transition-colors">
            <Bell className="w-5 h-5" />
          </button>
          <button className="p-2 rounded-lg hover:bg-terminal-border/50 text-terminal-muted hover:text-terminal-text transition-colors">
            <Settings className="w-5 h-5" />
          </button>
        </div>
      </div>
    </header>
  )
}

