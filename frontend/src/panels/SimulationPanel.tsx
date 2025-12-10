import { useState, useEffect, useMemo } from 'react'
import { 
  Play, Pause, RotateCcw, TrendingUp, TrendingDown, 
  DollarSign, Target, Clock, History, Zap, AlertCircle
} from 'lucide-react'
import { useStore } from '../state/store'
import clsx from 'clsx'

interface Trade {
  id: string
  type: 'buy' | 'sell'
  entryPrice: number
  entryTime: Date
  exitPrice?: number
  exitTime?: Date
  size: number  // USD value
  fees: number
  pnl?: number
  pnlPct?: number
  status: 'open' | 'closed'
  prediction?: {
    direction: 'up' | 'down'
    confidence: number
  }
}

interface SimulationState {
  startingBalance: number
  currentBalance: number
  trades: Trade[]
  isRunning: boolean
  startTime?: Date
  exchange: 'binance' | 'mexc'
  market: 'spot' | 'futures'
}

// Fee rates
const FEES = {
  binance: { spot: 0.001, futures: 0.0004 },  // 0.1% spot, 0.04% futures
  mexc: { spot: 0.001, futures: 0.0002 },     // 0.1% spot, 0.02% futures
}

export function SimulationPanel() {
  const { marketData, prediction } = useStore()
  const currentPrice = marketData?.candles?.slice(-1)[0]?.close || 0
  
  const [sim, setSim] = useState<SimulationState>({
    startingBalance: 100000,
    currentBalance: 100000,
    trades: [],
    isRunning: false,
    exchange: 'mexc',
    market: 'futures',
  })
  
  const [positionSize, setPositionSize] = useState(10) // % of balance
  const [customSize, setCustomSize] = useState('')
  const [openPosition, setOpenPosition] = useState<Trade | null>(null)
  
  // Calculate effective position size
  const effectiveSize = customSize 
    ? parseFloat(customSize) || 0 
    : (sim.currentBalance * positionSize / 100)
  
  // Get current fee rate
  const feeRate = FEES[sim.exchange][sim.market]
  
  // Calculate stats
  const stats = useMemo(() => {
    const closedTrades = sim.trades.filter(t => t.status === 'closed')
    const wins = closedTrades.filter(t => (t.pnl || 0) > 0)
    const losses = closedTrades.filter(t => (t.pnl || 0) <= 0)
    
    const totalPnl = closedTrades.reduce((sum, t) => sum + (t.pnl || 0), 0)
    const totalFees = sim.trades.reduce((sum, t) => sum + t.fees, 0)
    const grossPnl = closedTrades.reduce((sum, t) => {
      if (!t.exitPrice) return sum
      const gross = t.type === 'buy' 
        ? (t.exitPrice - t.entryPrice) / t.entryPrice * t.size
        : (t.entryPrice - t.exitPrice) / t.entryPrice * t.size
      return sum + gross
    }, 0)
    
    const bestTrade = closedTrades.reduce((best, t) => 
      (t.pnl || 0) > (best?.pnl || -Infinity) ? t : best, null as Trade | null)
    const worstTrade = closedTrades.reduce((worst, t) => 
      (t.pnl || 0) < (worst?.pnl || Infinity) ? t : worst, null as Trade | null)
    
    return {
      totalTrades: closedTrades.length,
      wins: wins.length,
      losses: losses.length,
      winRate: closedTrades.length > 0 ? (wins.length / closedTrades.length * 100) : 0,
      totalPnl,
      totalFees,
      grossPnl,
      netPnl: totalPnl,
      pnlPct: sim.startingBalance > 0 ? (totalPnl / sim.startingBalance * 100) : 0,
      bestTrade,
      worstTrade,
    }
  }, [sim.trades, sim.startingBalance])
  
  // Open a position
  const openTrade = (type: 'buy' | 'sell') => {
    if (!currentPrice || openPosition) return
    
    const entryFee = effectiveSize * feeRate
    const trade: Trade = {
      id: `trade_${Date.now()}`,
      type,
      entryPrice: currentPrice,
      entryTime: new Date(),
      size: effectiveSize,
      fees: entryFee,
      status: 'open',
      prediction: prediction ? {
        direction: prediction.p_up > 0.5 ? 'up' : 'down',
        confidence: Math.max(prediction.p_up, prediction.p_down) * 100
      } : undefined
    }
    
    setOpenPosition(trade)
    setSim(prev => ({
      ...prev,
      currentBalance: prev.currentBalance - entryFee,
      trades: [...prev.trades, trade],
      isRunning: true,
      startTime: prev.startTime || new Date(),
    }))
  }
  
  // Close position
  const closePosition = () => {
    if (!openPosition || !currentPrice) return
    
    const exitFee = openPosition.size * feeRate
    const grossPnl = openPosition.type === 'buy'
      ? (currentPrice - openPosition.entryPrice) / openPosition.entryPrice * openPosition.size
      : (openPosition.entryPrice - currentPrice) / openPosition.entryPrice * openPosition.size
    
    const netPnl = grossPnl - exitFee
    const totalFees = openPosition.fees + exitFee
    
    const closedTrade: Trade = {
      ...openPosition,
      exitPrice: currentPrice,
      exitTime: new Date(),
      fees: totalFees,
      pnl: netPnl,
      pnlPct: netPnl / openPosition.size * 100,
      status: 'closed',
    }
    
    setSim(prev => ({
      ...prev,
      currentBalance: prev.currentBalance + openPosition.size + netPnl - exitFee,
      trades: prev.trades.map(t => t.id === openPosition.id ? closedTrade : t),
    }))
    
    setOpenPosition(null)
  }
  
  // Reset simulation
  const resetSimulation = () => {
    setSim({
      startingBalance: sim.startingBalance,
      currentBalance: sim.startingBalance,
      trades: [],
      isRunning: false,
      exchange: sim.exchange,
      market: sim.market,
    })
    setOpenPosition(null)
  }
  
  // Format helpers
  const formatUsd = (val: number) => {
    const sign = val >= 0 ? '' : '-'
    return `${sign}$${Math.abs(val).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
  }
  
  const formatPct = (val: number) => {
    const sign = val >= 0 ? '+' : ''
    return `${sign}${val.toFixed(2)}%`
  }
  
  // Current position P&L
  const currentPnl = openPosition && currentPrice ? (
    openPosition.type === 'buy'
      ? (currentPrice - openPosition.entryPrice) / openPosition.entryPrice * openPosition.size
      : (openPosition.entryPrice - currentPrice) / openPosition.entryPrice * openPosition.size
  ) : 0
  
  const currentPnlPct = openPosition ? (currentPnl / openPosition.size * 100) : 0
  
  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div className="p-4 border-b border-terminal-border">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <Zap className="w-5 h-5 text-accent" />
            <h2 className="font-display font-semibold">Paper Trading</h2>
          </div>
          <button
            onClick={resetSimulation}
            className="p-1.5 rounded hover:bg-terminal-border transition-colors"
            title="Reset Simulation"
          >
            <RotateCcw className="w-4 h-4 text-terminal-muted" />
          </button>
        </div>
        
        {/* Exchange & Market Selection */}
        <div className="flex gap-2 text-xs">
          <select
            value={sim.exchange}
            onChange={(e) => setSim(prev => ({ ...prev, exchange: e.target.value as any }))}
            className="px-2 py-1 bg-terminal-bg border border-terminal-border rounded"
          >
            <option value="mexc">MEXC</option>
            <option value="binance">Binance</option>
          </select>
          <select
            value={sim.market}
            onChange={(e) => setSim(prev => ({ ...prev, market: e.target.value as any }))}
            className="px-2 py-1 bg-terminal-bg border border-terminal-border rounded"
          >
            <option value="futures">Futures</option>
            <option value="spot">Spot</option>
          </select>
          <span className="text-terminal-muted self-center">
            Fee: {(feeRate * 100).toFixed(2)}%
          </span>
        </div>
      </div>
      
      {/* Balance Display */}
      <div className="p-4 bg-terminal-surface/30 border-b border-terminal-border">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <div className="text-xs text-terminal-muted mb-1">Balance</div>
            <div className="font-mono text-xl font-bold">
              {formatUsd(sim.currentBalance)}
            </div>
            <div className={clsx(
              'text-xs font-mono',
              stats.totalPnl >= 0 ? 'text-bull' : 'text-bear'
            )}>
              {formatPct(stats.pnlPct)} all time
            </div>
          </div>
          <div>
            <div className="text-xs text-terminal-muted mb-1">Current Price</div>
            <div className="font-mono text-xl">
              ${currentPrice.toLocaleString(undefined, { minimumFractionDigits: 2 })}
            </div>
            {prediction && (
              <div className={clsx(
                'text-xs',
                prediction.p_up > 0.5 ? 'text-bull' : 'text-bear'
              )}>
                Pred: {prediction.p_up > 0.5 ? '↑' : '↓'} {(Math.max(prediction.p_up, prediction.p_down) * 100).toFixed(0)}%
              </div>
            )}
          </div>
        </div>
      </div>
      
      {/* Position Size */}
      <div className="p-4 border-b border-terminal-border">
        <div className="text-xs text-terminal-muted mb-2">Position Size</div>
        <div className="flex gap-1 mb-2">
          {[5, 10, 25, 50, 100].map((pct) => (
            <button
              key={pct}
              onClick={() => { setPositionSize(pct); setCustomSize('') }}
              className={clsx(
                'flex-1 px-2 py-1 text-xs rounded',
                positionSize === pct && !customSize
                  ? 'bg-accent text-white'
                  : 'bg-terminal-bg text-terminal-muted hover:text-white'
              )}
            >
              {pct}%
            </button>
          ))}
        </div>
        <div className="flex gap-2">
          <input
            type="number"
            placeholder="Custom $..."
            value={customSize}
            onChange={(e) => setCustomSize(e.target.value)}
            className="flex-1 px-3 py-1.5 text-sm bg-terminal-bg border border-terminal-border rounded focus:border-accent outline-none"
          />
          <div className="self-center text-sm text-terminal-muted">
            = {formatUsd(effectiveSize)}
          </div>
        </div>
      </div>
      
      {/* Open Position */}
      {openPosition && (() => {
        const exitFee = openPosition.size * feeRate
        const totalFees = openPosition.fees + exitFee
        const netPnl = currentPnl - exitFee
        const netPnlPct = netPnl / openPosition.size * 100
        const breakeven = (totalFees / openPosition.size) * 100
        
        return (
          <div className={clsx(
            'p-4 border-b-2',
            netPnl >= 0 ? 'bg-bull/10 border-bull' : 'bg-bear/10 border-bear'
          )}>
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                {openPosition.type === 'buy' ? (
                  <TrendingUp className="w-4 h-4 text-bull" />
                ) : (
                  <TrendingDown className="w-4 h-4 text-bear" />
                )}
                <span className="font-semibold uppercase">{openPosition.type}</span>
                <span className="text-terminal-muted text-sm">
                  @ ${openPosition.entryPrice.toFixed(2)}
                </span>
              </div>
              <button
                onClick={closePosition}
                className={clsx(
                  'px-3 py-1 text-sm font-semibold rounded transition-colors',
                  netPnl >= 0 
                    ? 'bg-bull hover:bg-bull/80 text-white' 
                    : 'bg-bear hover:bg-bear/80 text-white'
                )}
              >
                Close {netPnl >= 0 ? `+${formatUsd(netPnl)}` : formatUsd(netPnl)}
              </button>
            </div>
            
            {/* Position Details */}
            <div className="grid grid-cols-2 gap-2 text-sm mb-3">
              <div>
                <div className="text-xs text-terminal-muted">Position Size</div>
                <div className="font-mono">{formatUsd(openPosition.size)}</div>
              </div>
              <div>
                <div className="text-xs text-terminal-muted">Current Price</div>
                <div className="font-mono">${currentPrice.toFixed(2)}</div>
              </div>
            </div>
            
            {/* P&L Breakdown */}
            <div className="bg-terminal-bg/50 rounded p-2 space-y-1 text-xs">
              <div className="flex justify-between">
                <span className="text-terminal-muted">Gross P&L:</span>
                <span className={clsx('font-mono', currentPnl >= 0 ? 'text-bull' : 'text-bear')}>
                  {formatUsd(currentPnl)} ({formatPct(currentPnlPct)})
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-terminal-muted">Entry Fee (paid):</span>
                <span className="font-mono text-amber-400">-{formatUsd(openPosition.fees)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-terminal-muted">Exit Fee (on close):</span>
                <span className="font-mono text-amber-400">-{formatUsd(exitFee)}</span>
              </div>
              <div className="flex justify-between border-t border-terminal-border pt-1 mt-1">
                <span className="font-semibold">Net P&L (after fees):</span>
                <span className={clsx('font-mono font-bold', netPnl >= 0 ? 'text-bull' : 'text-bear')}>
                  {formatUsd(netPnl)} ({formatPct(netPnlPct)})
                </span>
              </div>
            </div>
            
            {/* Breakeven Warning */}
            {netPnl < 0 && currentPnl >= 0 && (
              <div className="mt-2 p-2 bg-amber-400/10 rounded text-xs text-amber-400">
                ⚠️ Gross profit but net loss due to fees! Need +{breakeven.toFixed(3)}% to breakeven.
              </div>
            )}
            {netPnl < 0 && currentPnl < 0 && (
              <div className="mt-2 p-2 bg-bear/10 rounded text-xs text-bear">
                📉 Position is in loss. Breakeven needs +{breakeven.toFixed(3)}% from entry.
              </div>
            )}
            {netPnl > 0 && (
              <div className="mt-2 p-2 bg-bull/10 rounded text-xs text-bull">
                ✅ Profitable after fees! Safe to close.
              </div>
            )}
          </div>
        )
      })()}
      
      {/* Trade Buttons */}
      {!openPosition && (
        <div className="p-4 border-b border-terminal-border">
          <div className="grid grid-cols-2 gap-3">
            <button
              onClick={() => openTrade('buy')}
              disabled={!currentPrice || effectiveSize <= 0}
              className={clsx(
                'flex items-center justify-center gap-2 py-3 rounded font-semibold transition-all',
                'bg-bull hover:bg-bull/80 text-white',
                'disabled:opacity-50 disabled:cursor-not-allowed'
              )}
            >
              <TrendingUp className="w-5 h-5" />
              {sim.market === 'spot' ? 'BUY' : 'LONG'}
            </button>
            <button
              onClick={() => openTrade('sell')}
              disabled={!currentPrice || effectiveSize <= 0 || sim.market === 'spot'}
              title={sim.market === 'spot' ? 'Shorting not available in Spot trading' : ''}
              className={clsx(
                'flex items-center justify-center gap-2 py-3 rounded font-semibold transition-all',
                'bg-bear hover:bg-bear/80 text-white',
                'disabled:opacity-50 disabled:cursor-not-allowed'
              )}
            >
              <TrendingDown className="w-5 h-5" />
              {sim.market === 'spot' ? 'SELL' : 'SHORT'}
            </button>
          </div>
          {sim.market === 'spot' && (
            <div className="mt-2 p-2 rounded text-xs text-center bg-amber-400/10 text-amber-400">
              ⚠️ Spot trading: Buy low, sell high. No shorting available.
            </div>
          )}
          {prediction && sim.market === 'futures' && (
            <div className={clsx(
              'mt-2 p-2 rounded text-xs text-center',
              prediction.p_up > 0.5 ? 'bg-bull/10 text-bull' : 'bg-bear/10 text-bear'
            )}>
              💡 Prediction suggests: <strong>{prediction.p_up > 0.5 ? 'LONG' : 'SHORT'}</strong>
              {' '}({(Math.max(prediction.p_up, prediction.p_down) * 100).toFixed(0)}% confidence)
            </div>
          )}
          {prediction && sim.market === 'spot' && (
            <div className={clsx(
              'mt-2 p-2 rounded text-xs text-center',
              prediction.p_up > 0.5 ? 'bg-bull/10 text-bull' : 'bg-amber-400/10 text-amber-400'
            )}>
              {prediction.p_up > 0.5 
                ? `💡 Good time to BUY (${(prediction.p_up * 100).toFixed(0)}% up probability)`
                : `⏳ Wait for better entry (${(prediction.p_down * 100).toFixed(0)}% down probability)`
              }
            </div>
          )}
        </div>
      )}
      
      {/* Stats */}
      <div className="p-4 border-b border-terminal-border bg-terminal-surface/30">
        <div className="text-xs text-terminal-muted mb-2">Performance</div>
        <div className="grid grid-cols-4 gap-2 text-center">
          <div>
            <div className="font-mono font-bold">{stats.totalTrades}</div>
            <div className="text-xs text-terminal-muted">Trades</div>
          </div>
          <div>
            <div className={clsx('font-mono font-bold', stats.winRate >= 50 ? 'text-bull' : 'text-bear')}>
              {stats.winRate.toFixed(0)}%
            </div>
            <div className="text-xs text-terminal-muted">Win Rate</div>
          </div>
          <div>
            <div className={clsx('font-mono font-bold', stats.totalPnl >= 0 ? 'text-bull' : 'text-bear')}>
              {formatUsd(stats.totalPnl)}
            </div>
            <div className="text-xs text-terminal-muted">Net P&L</div>
          </div>
          <div>
            <div className="font-mono font-bold text-amber-400">
              {formatUsd(stats.totalFees)}
            </div>
            <div className="text-xs text-terminal-muted">Fees Paid</div>
          </div>
        </div>
      </div>
      
      {/* Trade History */}
      <div className="flex-1 overflow-y-auto">
        <div className="p-4">
          <div className="flex items-center gap-2 text-xs text-terminal-muted mb-2">
            <History className="w-3.5 h-3.5" />
            Recent Trades
          </div>
          
          {sim.trades.filter(t => t.status === 'closed').length === 0 ? (
            <div className="text-center text-terminal-muted text-sm py-8">
              No closed trades yet.
              <br />
              <span className="text-xs">Open a position to start trading!</span>
            </div>
          ) : (
            <div className="space-y-2">
              {[...sim.trades]
                .filter(t => t.status === 'closed')
                .reverse()
                .slice(0, 10)
                .map((trade) => (
                  <div
                    key={trade.id}
                    className={clsx(
                      'p-3 rounded border-l-2',
                      (trade.pnl || 0) >= 0 
                        ? 'bg-bull/5 border-bull' 
                        : 'bg-bear/5 border-bear'
                    )}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-2">
                        {trade.type === 'buy' ? (
                          <TrendingUp className="w-3.5 h-3.5 text-bull" />
                        ) : (
                          <TrendingDown className="w-3.5 h-3.5 text-bear" />
                        )}
                        <span className="text-sm font-medium uppercase">
                          {trade.type}
                        </span>
                        <span className="text-xs text-terminal-muted">
                          {formatUsd(trade.size)}
                        </span>
                      </div>
                      <div className={clsx(
                        'font-mono text-sm font-bold',
                        (trade.pnl || 0) >= 0 ? 'text-bull' : 'text-bear'
                      )}>
                        {formatUsd(trade.pnl || 0)}
                        <span className="text-xs ml-1">
                          ({formatPct(trade.pnlPct || 0)})
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 text-xs text-terminal-muted">
                      <span>${trade.entryPrice.toFixed(2)}</span>
                      <span>→</span>
                      <span>${trade.exitPrice?.toFixed(2)}</span>
                      <span className="ml-auto">Fee: {formatUsd(trade.fees)}</span>
                    </div>
                    {trade.prediction && (
                      <div className={clsx(
                        'text-xs mt-1',
                        (trade.prediction.direction === 'up' && trade.type === 'buy') ||
                        (trade.prediction.direction === 'down' && trade.type === 'sell')
                          ? 'text-bull' : 'text-terminal-muted'
                      )}>
                        {(trade.prediction.direction === 'up' && trade.type === 'buy') ||
                         (trade.prediction.direction === 'down' && trade.type === 'sell')
                          ? '✓ Followed prediction' : '✗ Against prediction'}
                      </div>
                    )}
                  </div>
                ))}
            </div>
          )}
        </div>
      </div>
      
      {/* Footer Stats */}
      {stats.totalTrades > 0 && (
        <div className="p-4 border-t border-terminal-border bg-terminal-surface/50 text-xs">
          <div className="grid grid-cols-2 gap-4">
            {stats.bestTrade && (
              <div>
                <span className="text-terminal-muted">Best: </span>
                <span className="text-bull font-mono">
                  {formatUsd(stats.bestTrade.pnl || 0)}
                </span>
              </div>
            )}
            {stats.worstTrade && (
              <div>
                <span className="text-terminal-muted">Worst: </span>
                <span className="text-bear font-mono">
                  {formatUsd(stats.worstTrade.pnl || 0)}
                </span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

