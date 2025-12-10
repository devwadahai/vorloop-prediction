import { useState, useMemo } from 'react'
import { Calculator, DollarSign, TrendingUp, ArrowRight, Info } from 'lucide-react'
import clsx from 'clsx'

// Fee structures (as of Dec 2024)
const EXCHANGES = {
  binance: {
    name: 'Binance',
    color: '#F0B90B',
    spot: {
      maker: 0.10,  // 0.10%
      taker: 0.10,  // 0.10%
      makerBnb: 0.075,  // with 25% BNB discount
      takerBnb: 0.075,
    },
    futures: {
      maker: 0.02,  // 0.02%
      taker: 0.04,  // 0.04%
      makerBnb: 0.018,
      takerBnb: 0.036,
    },
    note: 'USA restricted - use VPN or non-US account',
  },
  mexc: {
    name: 'MEXC',
    color: '#00B897',
    spot: {
      maker: 0.00,  // 0% maker!
      taker: 0.10,  // 0.10%
      makerMx: 0.00,
      takerMx: 0.08,
    },
    futures: {
      maker: 0.00,  // 0% maker!
      taker: 0.02,  // 0.02%
      makerMx: 0.00,
      takerMx: 0.016,
    },
    note: 'USA friendly - 0% maker fees!',
  },
}

const TRADE_SIZES = [1000, 5000, 10000, 30000, 50000, 100000]

interface FeeResult {
  exchange: string
  tradeSize: number
  entryFee: number
  exitFee: number
  totalFees: number
  breakeven: number // % move needed to breakeven
  netProfit1Pct: number // net profit if price moves 1%
  netProfit2Pct: number
  netProfit5Pct: number
}

function calculateFees(
  exchange: typeof EXCHANGES.binance | typeof EXCHANGES.mexc,
  tradeSize: number,
  market: 'spot' | 'futures',
  useDiscount: boolean,
  orderType: 'taker' | 'maker'
): FeeResult {
  const fees = exchange[market]
  
  let entryRate: number
  let exitRate: number
  
  if (orderType === 'taker') {
    entryRate = useDiscount 
      ? (fees as any).takerBnb || (fees as any).takerMx || fees.taker
      : fees.taker
    exitRate = entryRate
  } else {
    entryRate = useDiscount
      ? (fees as any).makerBnb || (fees as any).makerMx || fees.maker
      : fees.maker
    exitRate = entryRate
  }
  
  const entryFee = tradeSize * (entryRate / 100)
  const exitFee = tradeSize * (exitRate / 100)
  const totalFees = entryFee + exitFee
  
  // Breakeven = total fees as % of position
  const breakeven = (totalFees / tradeSize) * 100
  
  // Net profit calculations
  const profit1Pct = (tradeSize * 0.01) - totalFees
  const profit2Pct = (tradeSize * 0.02) - totalFees
  const profit5Pct = (tradeSize * 0.05) - totalFees
  
  return {
    exchange: exchange.name,
    tradeSize,
    entryFee,
    exitFee,
    totalFees,
    breakeven,
    netProfit1Pct: profit1Pct,
    netProfit2Pct: profit2Pct,
    netProfit5Pct: profit5Pct,
  }
}

export function FeeCalculatorPanel() {
  const [tradeSize, setTradeSize] = useState(10000)
  const [customSize, setCustomSize] = useState('')
  const [market, setMarket] = useState<'spot' | 'futures'>('futures')
  const [orderType, setOrderType] = useState<'taker' | 'maker'>('taker')
  const [useDiscount, setUseDiscount] = useState(false)
  
  const effectiveSize = customSize ? parseFloat(customSize) || tradeSize : tradeSize
  
  const results = useMemo(() => {
    return {
      binance: calculateFees(EXCHANGES.binance, effectiveSize, market, useDiscount, orderType),
      mexc: calculateFees(EXCHANGES.mexc, effectiveSize, market, useDiscount, orderType),
    }
  }, [effectiveSize, market, useDiscount, orderType])
  
  const formatUsd = (val: number) => {
    if (val >= 0) return `$${val.toFixed(2)}`
    return `-$${Math.abs(val).toFixed(2)}`
  }
  
  const formatPct = (val: number) => `${val.toFixed(3)}%`
  
  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div className="p-4 border-b border-terminal-border">
        <div className="flex items-center gap-2 mb-2">
          <Calculator className="w-5 h-5 text-accent" />
          <h2 className="font-display font-semibold">Fee Calculator</h2>
        </div>
        <p className="text-xs text-terminal-muted">
          Compare trading fees & breakeven prices
        </p>
      </div>
      
      {/* Controls */}
      <div className="p-4 space-y-4 border-b border-terminal-border">
        {/* Trade Size */}
        <div>
          <label className="text-xs text-terminal-muted block mb-2">Trade Size</label>
          <div className="flex flex-wrap gap-1 mb-2">
            {TRADE_SIZES.map((size) => (
              <button
                key={size}
                onClick={() => { setTradeSize(size); setCustomSize('') }}
                className={clsx(
                  'px-2 py-1 text-xs rounded transition-colors',
                  tradeSize === size && !customSize
                    ? 'bg-accent text-white'
                    : 'bg-terminal-bg text-terminal-muted hover:text-white'
                )}
              >
                ${(size / 1000).toFixed(0)}K
              </button>
            ))}
          </div>
          <input
            type="number"
            placeholder="Custom amount..."
            value={customSize}
            onChange={(e) => setCustomSize(e.target.value)}
            className="w-full px-3 py-1.5 text-sm bg-terminal-bg border border-terminal-border rounded focus:border-accent outline-none"
          />
        </div>
        
        {/* Market Type */}
        <div className="flex gap-4">
          <div>
            <label className="text-xs text-terminal-muted block mb-2">Market</label>
            <div className="flex gap-1">
              {(['spot', 'futures'] as const).map((m) => (
                <button
                  key={m}
                  onClick={() => setMarket(m)}
                  className={clsx(
                    'px-3 py-1 text-xs rounded capitalize',
                    market === m
                      ? 'bg-accent text-white'
                      : 'bg-terminal-bg text-terminal-muted hover:text-white'
                  )}
                >
                  {m}
                </button>
              ))}
            </div>
          </div>
          
          <div>
            <label className="text-xs text-terminal-muted block mb-2">Order Type</label>
            <div className="flex gap-1">
              {(['taker', 'maker'] as const).map((o) => (
                <button
                  key={o}
                  onClick={() => setOrderType(o)}
                  className={clsx(
                    'px-3 py-1 text-xs rounded capitalize',
                    orderType === o
                      ? 'bg-accent text-white'
                      : 'bg-terminal-bg text-terminal-muted hover:text-white'
                  )}
                >
                  {o}
                </button>
              ))}
            </div>
          </div>
        </div>
        
        {/* Token Discount */}
        <label className="flex items-center gap-2 text-xs cursor-pointer">
          <input
            type="checkbox"
            checked={useDiscount}
            onChange={(e) => setUseDiscount(e.target.checked)}
            className="rounded border-terminal-border"
          />
          <span className="text-terminal-muted">
            Use token discount (BNB/MX)
          </span>
        </label>
      </div>
      
      {/* Results */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Comparison Cards */}
        {Object.entries(results).map(([key, result]) => {
          const exchange = EXCHANGES[key as keyof typeof EXCHANGES]
          return (
            <div
              key={key}
              className="bg-terminal-bg rounded-lg p-4 border border-terminal-border"
              style={{ borderLeftColor: exchange.color, borderLeftWidth: 3 }}
            >
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <span className="font-semibold" style={{ color: exchange.color }}>
                    {exchange.name}
                  </span>
                  <span className="text-xs px-2 py-0.5 rounded bg-terminal-border text-terminal-muted">
                    {market}
                  </span>
                </div>
                <span className="text-xs text-terminal-muted">
                  {exchange.note}
                </span>
              </div>
              
              {/* Fee Breakdown */}
              <div className="grid grid-cols-3 gap-3 mb-4">
                <div className="text-center">
                  <div className="text-xs text-terminal-muted mb-1">Entry Fee</div>
                  <div className="font-mono text-bear">{formatUsd(result.entryFee)}</div>
                  <div className="text-xs text-terminal-muted">
                    {formatPct(exchange[market][orderType])}
                  </div>
                </div>
                <div className="text-center">
                  <div className="text-xs text-terminal-muted mb-1">Exit Fee</div>
                  <div className="font-mono text-bear">{formatUsd(result.exitFee)}</div>
                  <div className="text-xs text-terminal-muted">
                    {formatPct(exchange[market][orderType])}
                  </div>
                </div>
                <div className="text-center">
                  <div className="text-xs text-terminal-muted mb-1">Total Fees</div>
                  <div className="font-mono text-bear font-bold">{formatUsd(result.totalFees)}</div>
                  <div className="text-xs text-terminal-muted">
                    {formatPct(result.breakeven)} of trade
                  </div>
                </div>
              </div>
              
              {/* Breakeven */}
              <div className="bg-terminal-surface/50 rounded p-3 mb-3">
                <div className="flex items-center gap-2 text-sm">
                  <TrendingUp className="w-4 h-4 text-amber-400" />
                  <span className="text-terminal-muted">Breakeven move:</span>
                  <span className="font-mono font-bold text-amber-400">
                    {formatPct(result.breakeven)}
                  </span>
                </div>
                <p className="text-xs text-terminal-muted mt-1">
                  Price must move {formatPct(result.breakeven)} to cover fees
                </p>
              </div>
              
              {/* Profit Scenarios */}
              <div className="text-xs text-terminal-muted mb-2">Net Profit After Fees:</div>
              <div className="grid grid-cols-3 gap-2">
                {[
                  { label: '+1%', profit: result.netProfit1Pct },
                  { label: '+2%', profit: result.netProfit2Pct },
                  { label: '+5%', profit: result.netProfit5Pct },
                ].map(({ label, profit }) => (
                  <div
                    key={label}
                    className={clsx(
                      'text-center p-2 rounded',
                      profit > 0 ? 'bg-bull/10' : 'bg-bear/10'
                    )}
                  >
                    <div className="text-xs text-terminal-muted">{label} move</div>
                    <div className={clsx(
                      'font-mono font-bold',
                      profit > 0 ? 'text-bull' : 'text-bear'
                    )}>
                      {formatUsd(profit)}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )
        })}
        
        {/* Quick Comparison */}
        <div className="bg-terminal-surface rounded-lg p-4">
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <Info className="w-4 h-4" />
            Quick Comparison
          </h3>
          <div className="space-y-2 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-terminal-muted">Fee Difference:</span>
              <span className={clsx(
                'font-mono',
                results.mexc.totalFees < results.binance.totalFees ? 'text-bull' : 'text-bear'
              )}>
                {results.mexc.totalFees < results.binance.totalFees ? 'MEXC saves ' : 'Binance saves '}
                {formatUsd(Math.abs(results.binance.totalFees - results.mexc.totalFees))}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-terminal-muted">Best for {orderType}:</span>
              <span className="font-semibold" style={{
                color: results.mexc.totalFees <= results.binance.totalFees 
                  ? EXCHANGES.mexc.color 
                  : EXCHANGES.binance.color
              }}>
                {results.mexc.totalFees <= results.binance.totalFees ? 'MEXC' : 'Binance'}
              </span>
            </div>
            {market === 'futures' && (
              <div className="mt-3 p-2 bg-amber-400/10 rounded text-xs text-amber-400">
                💡 Tip: Use limit orders (maker) on MEXC for 0% fees!
              </div>
            )}
          </div>
        </div>
        
        {/* Take Profit Guide */}
        <div className="bg-terminal-surface rounded-lg p-4">
          <h3 className="text-sm font-semibold mb-3">📈 Take Profit Guide</h3>
          <div className="text-xs text-terminal-muted space-y-2">
            <p>
              Based on ${effectiveSize.toLocaleString()} position on {market}:
            </p>
            <ul className="list-disc list-inside space-y-1">
              <li>
                <strong>Minimum target:</strong> {formatPct(Math.max(results.binance.breakeven, results.mexc.breakeven) * 1.5)} 
                {' '}(1.5x breakeven)
              </li>
              <li>
                <strong>Safe target:</strong> {formatPct(Math.max(results.binance.breakeven, results.mexc.breakeven) * 2)}
                {' '}(2x breakeven)
              </li>
              <li>
                <strong>Conservative target:</strong> {formatPct(Math.max(results.binance.breakeven, results.mexc.breakeven) * 3)}
                {' '}(3x breakeven)
              </li>
            </ul>
            <p className="text-amber-400 mt-2">
              ⚠️ Always account for slippage (0.01-0.05%) on large orders
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

