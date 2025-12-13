import { useState, useEffect, useCallback } from 'react'
import { 
  ArrowLeft, TrendingUp, TrendingDown, Clock, RefreshCw,
  AlertCircle, CheckCircle, Zap, DollarSign, Target
} from 'lucide-react'
import clsx from 'clsx'
import type { Market, OrderBook, Probability, Account } from '../PolymarketApp'

const API_BASE = 'http://localhost:8000/api/v1/polymarket'

interface MarketDetailProps {
  market: Market
  account: Account | null
  onBack: () => void
  onAccountCreate: () => Promise<Account | null>
  onRefresh: () => void
}

export function MarketDetail({ market, account, onBack, onAccountCreate, onRefresh }: MarketDetailProps) {
  const [orderBook, setOrderBook] = useState<OrderBook | null>(null)
  const [probability, setProbability] = useState<Probability | null>(null)
  const [loading, setLoading] = useState(true)
  const [orderSize, setOrderSize] = useState('100')
  const [submitting, setSubmitting] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null)

  const fetchMarketData = useCallback(async () => {
    setLoading(true)
    try {
      const [probRes] = await Promise.all([
        fetch(`${API_BASE}/probability/${market.market_id}`),
      ])

      if (probRes.ok) {
        const prob = await probRes.json()
        setProbability(prob)

        // Fetch order book for the token
        if (prob.token_id) {
          const obRes = await fetch(`${API_BASE}/orderbook/${prob.token_id}`)
          if (obRes.ok) {
            setOrderBook(await obRes.json())
          }
        }
      }
    } catch (e) {
      console.error('Failed to fetch market data:', e)
    }
    setLoading(false)
  }, [market.market_id])

  useEffect(() => {
    fetchMarketData()
    const interval = setInterval(fetchMarketData, 10000)
    return () => clearInterval(interval)
  }, [fetchMarketData])

  const submitOrder = async (side: 'BUY' | 'SELL') => {
    if (!probability?.token_id) return
    
    // Ensure account exists
    let acc = account
    if (!acc) {
      acc = await onAccountCreate()
      if (!acc) return
    }

    setSubmitting(true)
    setMessage(null)

    try {
      const res = await fetch(`${API_BASE}/order`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          token_id: probability.token_id,
          side,
          size: parseFloat(orderSize),
          order_type: 'MARKET',
        }),
      })

      if (res.ok) {
        setMessage({ type: 'success', text: `${side} order filled successfully!` })
        onRefresh()
        fetchMarketData()
      } else {
        const data = await res.json()
        setMessage({ type: 'error', text: data.detail || 'Order failed' })
      }
    } catch (e) {
      setMessage({ type: 'error', text: 'Failed to submit order' })
    }
    setSubmitting(false)
  }

  const formatTime = (hours: number) => {
    if (hours < 1) return `${Math.round(hours * 60)}m`
    if (hours < 24) return `${Math.round(hours)}h`
    if (hours < 168) return `${Math.round(hours / 24)}d`
    return `${Math.round(hours / 168)}w`
  }

  return (
    <div className="h-screen flex flex-col bg-[#0a0a0f]">
      {/* Header */}
      <header className="bg-[#12121a] border-b border-[#1e1e2e] px-6 py-4">
        <div className="flex items-center gap-4">
          <button
            onClick={onBack}
            className="p-2 rounded-lg hover:bg-[#1e1e2e] transition-colors"
          >
            <ArrowLeft className="w-5 h-5 text-gray-400" />
          </button>
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-1">
              <span className={clsx(
                'px-2 py-0.5 text-xs font-medium rounded-full capitalize',
                market.category === 'crypto' ? 'bg-orange-500/20 text-orange-400' :
                market.category === 'politics' ? 'bg-blue-500/20 text-blue-400' :
                market.category === 'sports' ? 'bg-green-500/20 text-green-400' :
                'bg-gray-500/20 text-gray-400'
              )}>
                {market.category}
              </span>
              <span className="flex items-center gap-1 text-xs text-gray-500">
                <Clock className="w-3 h-3" />
                {formatTime(market.time_to_resolution_hours)} until resolution
              </span>
            </div>
            <h1 className="text-xl font-bold text-white">{market.question}</h1>
          </div>
          <button
            onClick={fetchMarketData}
            disabled={loading}
            className="p-2 rounded-lg hover:bg-[#1e1e2e] transition-colors"
          >
            <RefreshCw className={clsx("w-5 h-5 text-gray-400", loading && "animate-spin")} />
          </button>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 flex overflow-hidden">
        {/* Left: Order Book */}
        <div className="w-80 border-r border-[#1e1e2e] flex flex-col">
          <div className="p-4 border-b border-[#1e1e2e]">
            <h2 className="text-sm font-semibold text-gray-400 mb-3">Order Book</h2>
            {orderBook && (
              <div className="grid grid-cols-3 gap-4 text-center">
                <div>
                  <div className="text-xs text-gray-500">Bid</div>
                  <div className="text-lg font-mono font-bold text-emerald-400">
                    {orderBook.best_bid ? (orderBook.best_bid * 100).toFixed(1) + '¢' : '-'}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-gray-500">Spread</div>
                  <div className="text-lg font-mono font-bold text-white">
                    {orderBook.spread_bps ? orderBook.spread_bps.toFixed(0) + 'bps' : '-'}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-gray-500">Ask</div>
                  <div className="text-lg font-mono font-bold text-red-400">
                    {orderBook.best_ask ? (orderBook.best_ask * 100).toFixed(1) + '¢' : '-'}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Order Book Visualization */}
          <div className="flex-1 overflow-y-auto p-4">
            {orderBook && (
              <div className="space-y-4">
                {/* Asks (sells) */}
                <div>
                  <div className="text-xs text-gray-500 mb-2">Asks (Sells)</div>
                  <div className="space-y-1">
                    {orderBook.asks.slice(0, 10).reverse().map(([price, size], i) => (
                      <div key={i} className="flex items-center gap-2">
                        <div className="w-24 h-6 bg-red-500/10 rounded relative overflow-hidden">
                          <div 
                            className="absolute inset-y-0 right-0 bg-red-500/30"
                            style={{ width: `${Math.min(100, size / 100)}%` }}
                          />
                        </div>
                        <span className="text-xs font-mono text-red-400 w-12">
                          {(price * 100).toFixed(1)}¢
                        </span>
                        <span className="text-xs font-mono text-gray-500">
                          ${size.toFixed(0)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Mid Price */}
                {orderBook.mid_price && (
                  <div className="py-2 text-center border-y border-[#1e1e2e]">
                    <span className="text-lg font-mono font-bold text-purple-400">
                      {(orderBook.mid_price * 100).toFixed(1)}¢
                    </span>
                    <span className="text-xs text-gray-500 ml-2">mid</span>
                  </div>
                )}

                {/* Bids (buys) */}
                <div>
                  <div className="text-xs text-gray-500 mb-2">Bids (Buys)</div>
                  <div className="space-y-1">
                    {orderBook.bids.slice(0, 10).map(([price, size], i) => (
                      <div key={i} className="flex items-center gap-2">
                        <div className="w-24 h-6 bg-emerald-500/10 rounded relative overflow-hidden">
                          <div 
                            className="absolute inset-y-0 left-0 bg-emerald-500/30"
                            style={{ width: `${Math.min(100, size / 100)}%` }}
                          />
                        </div>
                        <span className="text-xs font-mono text-emerald-400 w-12">
                          {(price * 100).toFixed(1)}¢
                        </span>
                        <span className="text-xs font-mono text-gray-500">
                          ${size.toFixed(0)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Depth Info */}
                <div className="pt-4 border-t border-[#1e1e2e]">
                  <div className="grid grid-cols-2 gap-4 text-center text-xs">
                    <div>
                      <div className="text-gray-500">Bid Depth</div>
                      <div className="font-mono text-emerald-400">${orderBook.bid_depth.toFixed(0)}</div>
                    </div>
                    <div>
                      <div className="text-gray-500">Ask Depth</div>
                      <div className="font-mono text-red-400">${orderBook.ask_depth.toFixed(0)}</div>
                    </div>
                  </div>
                  <div className="mt-3">
                    <div className="text-xs text-gray-500 mb-1">Imbalance</div>
                    <div className="h-2 bg-[#1e1e2e] rounded-full overflow-hidden">
                      <div 
                        className={clsx(
                          "h-full transition-all",
                          orderBook.imbalance > 0 ? "bg-emerald-500" : "bg-red-500"
                        )}
                        style={{ 
                          width: `${50 + orderBook.imbalance * 50}%`,
                          marginLeft: orderBook.imbalance < 0 ? `${50 + orderBook.imbalance * 50}%` : 0
                        }}
                      />
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Center: Probability Analysis */}
        <div className="flex-1 flex flex-col">
          {probability ? (
            <>
              {/* Probability Display */}
              <div className="p-6 border-b border-[#1e1e2e]">
                <div className="grid grid-cols-4 gap-6">
                  <div className="text-center">
                    <div className="text-sm text-gray-500 mb-2">Market Price</div>
                    <div className="text-4xl font-mono font-bold text-white">
                      {(probability.market_prob * 100).toFixed(1)}%
                    </div>
                    <div className="text-xs text-gray-500 mt-1">YES probability</div>
                  </div>
                  <div className="text-center">
                    <div className="text-sm text-gray-500 mb-2">Fair Value</div>
                    <div className="text-4xl font-mono font-bold text-purple-400">
                      {(probability.fair_prob * 100).toFixed(1)}%
                    </div>
                    <div className="text-xs text-gray-500 mt-1">our estimate</div>
                  </div>
                  <div className="text-center">
                    <div className="text-sm text-gray-500 mb-2">Edge</div>
                    <div className={clsx(
                      'text-4xl font-mono font-bold',
                      probability.edge > 0 ? 'text-emerald-400' : 'text-red-400'
                    )}>
                      {probability.edge > 0 ? '+' : ''}{probability.edge_pct.toFixed(2)}%
                    </div>
                    <div className="text-xs text-gray-500 mt-1">
                      {probability.edge > 0 ? 'YES underpriced' : 'NO underpriced'}
                    </div>
                  </div>
                  <div className="text-center">
                    <div className="text-sm text-gray-500 mb-2">Confidence</div>
                    <div className="text-4xl font-mono font-bold text-white">
                      {(probability.confidence * 100).toFixed(0)}%
                    </div>
                    <div className="text-xs text-gray-500 mt-1">model confidence</div>
                  </div>
                </div>
              </div>

              {/* Risk Assessment */}
              <div className="p-6 border-b border-[#1e1e2e]">
                <h3 className="text-sm font-semibold text-gray-400 mb-3">Risk Assessment</h3>
                <div className="flex flex-wrap gap-2">
                  {probability.risk_flags.length === 0 ? (
                    <span className="flex items-center gap-1 px-3 py-1.5 bg-emerald-500/10 text-emerald-400 rounded-lg text-sm">
                      <CheckCircle className="w-4 h-4" />
                      No major risks detected
                    </span>
                  ) : (
                    probability.risk_flags.map(flag => (
                      <span 
                        key={flag}
                        className="flex items-center gap-1 px-3 py-1.5 bg-amber-500/10 text-amber-400 rounded-lg text-sm"
                      >
                        <AlertCircle className="w-4 h-4" />
                        {flag.replace(/_/g, ' ')}
                      </span>
                    ))
                  )}
                </div>

                {/* Kelly & EV */}
                <div className="grid grid-cols-2 gap-4 mt-4">
                  <div className="p-3 bg-[#12121a] rounded-lg">
                    <div className="text-xs text-gray-500">Expected Value (per $100)</div>
                    <div className={clsx(
                      'text-xl font-mono font-bold',
                      probability.expected_value >= 0 ? 'text-emerald-400' : 'text-red-400'
                    )}>
                      {probability.expected_value >= 0 ? '+' : ''}${probability.expected_value.toFixed(2)}
                    </div>
                  </div>
                  <div className="p-3 bg-[#12121a] rounded-lg">
                    <div className="text-xs text-gray-500">Kelly Fraction</div>
                    <div className="text-xl font-mono font-bold text-white">
                      {(probability.kelly_fraction * 100).toFixed(1)}%
                    </div>
                  </div>
                </div>
              </div>

              {/* Trade Panel */}
              <div className="p-6">
                <h3 className="text-sm font-semibold text-gray-400 mb-3">Place Trade</h3>
                
                {/* Size Input */}
                <div className="mb-4">
                  <label className="text-xs text-gray-500 block mb-2">Order Size (USD)</label>
                  <div className="flex gap-2">
                    {[50, 100, 250, 500].map(size => (
                      <button
                        key={size}
                        onClick={() => setOrderSize(size.toString())}
                        className={clsx(
                          'px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                          orderSize === size.toString()
                            ? 'bg-purple-600 text-white'
                            : 'bg-[#1e1e2e] text-gray-400 hover:text-white'
                        )}
                      >
                        ${size}
                      </button>
                    ))}
                    <input
                      type="number"
                      value={orderSize}
                      onChange={e => setOrderSize(e.target.value)}
                      className="flex-1 px-3 py-2 bg-[#1e1e2e] border border-[#2a2a3e] rounded-lg text-white text-sm focus:border-purple-500 focus:outline-none"
                      placeholder="Custom"
                    />
                  </div>
                </div>

                {/* Trade Buttons */}
                <div className="grid grid-cols-2 gap-4">
                  <button
                    onClick={() => submitOrder('BUY')}
                    disabled={submitting || !probability.is_tradeable}
                    className={clsx(
                      'flex items-center justify-center gap-2 py-4 rounded-xl font-semibold text-lg transition-all',
                      probability.edge > 0
                        ? 'bg-emerald-600 hover:bg-emerald-500 text-white'
                        : 'bg-[#1e1e2e] text-gray-400',
                      (submitting || !probability.is_tradeable) && 'opacity-50 cursor-not-allowed'
                    )}
                  >
                    <TrendingUp className="w-5 h-5" />
                    Buy YES
                  </button>
                  <button
                    onClick={() => submitOrder('SELL')}
                    disabled={submitting || !probability.is_tradeable}
                    className={clsx(
                      'flex items-center justify-center gap-2 py-4 rounded-xl font-semibold text-lg transition-all',
                      probability.edge < 0
                        ? 'bg-red-600 hover:bg-red-500 text-white'
                        : 'bg-[#1e1e2e] text-gray-400',
                      (submitting || !probability.is_tradeable) && 'opacity-50 cursor-not-allowed'
                    )}
                  >
                    <TrendingDown className="w-5 h-5" />
                    Buy NO
                  </button>
                </div>

                {/* Suggested Trade */}
                {probability.is_tradeable && probability.suggested_side && (
                  <div className={clsx(
                    'mt-4 p-3 rounded-lg flex items-center gap-3',
                    probability.edge > 0 ? 'bg-emerald-500/10' : 'bg-red-500/10'
                  )}>
                    <Zap className={clsx(
                      'w-5 h-5',
                      probability.edge > 0 ? 'text-emerald-400' : 'text-red-400'
                    )} />
                    <span className={clsx(
                      'text-sm',
                      probability.edge > 0 ? 'text-emerald-400' : 'text-red-400'
                    )}>
                      Suggested: Buy {probability.edge > 0 ? 'YES' : 'NO'} — 
                      Edge of {Math.abs(probability.edge_pct).toFixed(2)}% detected
                    </span>
                  </div>
                )}

                {/* Message */}
                {message && (
                  <div className={clsx(
                    'mt-4 p-3 rounded-lg flex items-center gap-2',
                    message.type === 'success' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'
                  )}>
                    {message.type === 'success' ? (
                      <CheckCircle className="w-5 h-5" />
                    ) : (
                      <AlertCircle className="w-5 h-5" />
                    )}
                    {message.text}
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center">
              <RefreshCw className="w-8 h-8 text-gray-600 animate-spin" />
            </div>
          )}
        </div>

        {/* Right: Market Info */}
        <div className="w-80 border-l border-[#1e1e2e] p-6 overflow-y-auto">
          <h3 className="text-sm font-semibold text-gray-400 mb-4">Market Details</h3>
          
          <div className="space-y-4">
            <div>
              <div className="text-xs text-gray-500 mb-1">Description</div>
              <p className="text-sm text-gray-300">{market.description || 'No description available.'}</p>
            </div>
            
            <div className="grid grid-cols-2 gap-4">
              <div>
                <div className="text-xs text-gray-500 mb-1">24h Volume</div>
                <div className="text-lg font-mono text-white">${market.volume_24h.toLocaleString()}</div>
              </div>
              <div>
                <div className="text-xs text-gray-500 mb-1">Liquidity</div>
                <div className="text-lg font-mono text-white">${market.liquidity.toLocaleString()}</div>
              </div>
            </div>

            <div>
              <div className="text-xs text-gray-500 mb-1">Resolution</div>
              <div className="text-sm text-gray-300">
                {new Date(market.end_time).toLocaleDateString()} at {new Date(market.end_time).toLocaleTimeString()}
              </div>
            </div>

            <div>
              <div className="text-xs text-gray-500 mb-1">Status</div>
              <span className={clsx(
                'px-2 py-1 text-xs font-medium rounded',
                market.resolution_status === 'OPEN' 
                  ? 'bg-emerald-500/20 text-emerald-400'
                  : 'bg-gray-500/20 text-gray-400'
              )}>
                {market.resolution_status}
              </span>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}

