import { useState, useEffect, useCallback } from 'react'
import { 
  TrendingUp, TrendingDown, RefreshCw, Target, 
  BarChart3, DollarSign, AlertCircle, CheckCircle,
  Clock, Zap, ChevronRight
} from 'lucide-react'
import clsx from 'clsx'

interface Market {
  market_id: string
  slug: string
  question: string
  category: string
  volume_24h: number
  time_to_resolution_hours: number
}

interface Probability {
  market_id: string
  fair_prob: number
  market_prob: number
  edge: number
  edge_pct: number
  confidence: number
  risk_flags: string[]
  is_tradeable: boolean
  suggested_side: string | null
}

interface Account {
  account_id: string
  balance: number
  total_pnl: number
  total_trades: number
  win_rate: number
  open_positions: number
}

interface Stats {
  total_decisions: number
  resolved_decisions: number
  brier_score: number
  mean_edge: number
  prediction_accuracy: number
  total_pnl: number
}

const API_BASE = 'http://localhost:8000/api/v1/polymarket'

export function PolymarketPanel() {
  const [markets, setMarkets] = useState<Market[]>([])
  const [opportunities, setOpportunities] = useState<Probability[]>([])
  const [account, setAccount] = useState<Account | null>(null)
  const [stats, setStats] = useState<Stats | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedMarket, setSelectedMarket] = useState<string | null>(null)
  const [tab, setTab] = useState<'markets' | 'opportunities' | 'stats'>('opportunities')

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [marketsRes, oppsRes, accountRes, statsRes] = await Promise.all([
        fetch(`${API_BASE}/markets?limit=20`),
        fetch(`${API_BASE}/opportunities?min_edge=1.5&limit=10`),
        fetch(`${API_BASE}/account`).catch(() => null),
        fetch(`${API_BASE}/stats`),
      ])

      if (marketsRes.ok) setMarkets(await marketsRes.json())
      if (oppsRes.ok) setOpportunities(await oppsRes.json())
      if (accountRes?.ok) setAccount(await accountRes.json())
      if (statsRes.ok) setStats(await statsRes.json())
    } catch (e) {
      setError('Failed to fetch data. Is the backend running?')
    }
    setLoading(false)
  }, [])

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 30000)
    return () => clearInterval(interval)
  }, [fetchData])

  const createAccount = async () => {
    try {
      const res = await fetch(`${API_BASE}/account?initial_balance=10000`, { method: 'POST' })
      if (res.ok) {
        setAccount(await res.json())
      }
    } catch (e) {
      setError('Failed to create account')
    }
  }

  const submitOrder = async (tokenId: string, side: string, size: number) => {
    try {
      const res = await fetch(`${API_BASE}/order`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          token_id: tokenId,
          side,
          size,
          order_type: 'MARKET',
        }),
      })
      if (res.ok) {
        fetchData()
      } else {
        const data = await res.json()
        setError(data.detail || 'Order failed')
      }
    } catch (e) {
      setError('Failed to submit order')
    }
  }

  const formatPct = (val: number) => `${val >= 0 ? '+' : ''}${val.toFixed(2)}%`
  const formatUsd = (val: number) => `$${val.toLocaleString(undefined, { maximumFractionDigits: 0 })}`

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div className="p-4 border-b border-terminal-border">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Target className="w-5 h-5 text-purple-400" />
            <h2 className="font-display font-semibold">Polymarket</h2>
          </div>
          <button
            onClick={fetchData}
            disabled={loading}
            className="p-1.5 rounded hover:bg-terminal-border transition-colors"
          >
            <RefreshCw className={clsx("w-4 h-4 text-terminal-muted", loading && "animate-spin")} />
          </button>
        </div>

        {/* Account Summary */}
        {account ? (
          <div className="grid grid-cols-3 gap-2 text-center bg-terminal-bg rounded-lg p-2">
            <div>
              <div className="text-xs text-terminal-muted">Balance</div>
              <div className="font-mono font-bold">{formatUsd(account.balance)}</div>
            </div>
            <div>
              <div className="text-xs text-terminal-muted">P&L</div>
              <div className={clsx("font-mono font-bold", account.total_pnl >= 0 ? "text-bull" : "text-bear")}>
                {formatUsd(account.total_pnl)}
              </div>
            </div>
            <div>
              <div className="text-xs text-terminal-muted">Trades</div>
              <div className="font-mono font-bold">{account.total_trades}</div>
            </div>
          </div>
        ) : (
          <button
            onClick={createAccount}
            className="w-full py-2 bg-purple-500 hover:bg-purple-600 text-white rounded-lg font-medium transition-colors"
          >
            Create Paper Account ($10,000)
          </button>
        )}
      </div>

      {/* Tabs */}
      <div className="flex border-b border-terminal-border bg-terminal-surface/50">
        {(['opportunities', 'markets', 'stats'] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={clsx(
              'flex-1 px-3 py-2 text-xs font-medium transition-colors capitalize',
              tab === t
                ? 'text-white border-b-2 border-purple-400'
                : 'text-terminal-muted hover:text-white'
            )}
          >
            {t}
          </button>
        ))}
      </div>

      {/* Error */}
      {error && (
        <div className="p-3 bg-bear/10 border-b border-bear text-bear text-sm flex items-center gap-2">
          <AlertCircle className="w-4 h-4" />
          {error}
          <button onClick={() => setError(null)} className="ml-auto text-xs underline">
            Dismiss
          </button>
        </div>
      )}

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {tab === 'opportunities' && (
          <div className="p-4 space-y-3">
            {opportunities.length === 0 ? (
              <div className="text-center text-terminal-muted py-8">
                <Target className="w-8 h-8 mx-auto mb-2 opacity-50" />
                <p>No tradeable opportunities found</p>
                <p className="text-xs mt-1">Looking for markets with &gt;1.5% edge</p>
              </div>
            ) : (
              opportunities.map((opp) => {
                const market = markets.find(m => m.market_id === opp.market_id)
                return (
                  <div
                    key={opp.market_id}
                    className={clsx(
                      "p-3 rounded-lg border-l-2",
                      opp.edge > 0 ? "bg-bull/5 border-bull" : "bg-bear/5 border-bear"
                    )}
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium truncate">
                          {market?.question || opp.market_id}
                        </div>
                        <div className="text-xs text-terminal-muted">
                          {market?.category} • {(market?.time_to_resolution_hours || 0 / 24).toFixed(0)}d left
                        </div>
                      </div>
                      <div className={clsx(
                        "text-lg font-mono font-bold",
                        opp.edge > 0 ? "text-bull" : "text-bear"
                      )}>
                        {formatPct(opp.edge_pct)}
                      </div>
                    </div>

                    <div className="grid grid-cols-3 gap-2 text-xs mb-3">
                      <div>
                        <div className="text-terminal-muted">Fair</div>
                        <div className="font-mono">{(opp.fair_prob * 100).toFixed(1)}%</div>
                      </div>
                      <div>
                        <div className="text-terminal-muted">Market</div>
                        <div className="font-mono">{(opp.market_prob * 100).toFixed(1)}%</div>
                      </div>
                      <div>
                        <div className="text-terminal-muted">Confidence</div>
                        <div className="font-mono">{(opp.confidence * 100).toFixed(0)}%</div>
                      </div>
                    </div>

                    {opp.risk_flags.length > 0 && (
                      <div className="flex flex-wrap gap-1 mb-2">
                        {opp.risk_flags.map(flag => (
                          <span key={flag} className="px-1.5 py-0.5 text-xs bg-amber-400/10 text-amber-400 rounded">
                            {flag}
                          </span>
                        ))}
                      </div>
                    )}

                    {account && opp.is_tradeable && (
                      <div className="flex gap-2">
                        <button
                          onClick={() => submitOrder(opp.token_id, 'BUY', 100)}
                          className="flex-1 py-1.5 bg-bull hover:bg-bull/80 text-white rounded text-sm font-medium"
                        >
                          Buy YES $100
                        </button>
                        <button
                          onClick={() => submitOrder(opp.token_id, 'SELL', 100)}
                          className="flex-1 py-1.5 bg-bear hover:bg-bear/80 text-white rounded text-sm font-medium"
                        >
                          Buy NO $100
                        </button>
                      </div>
                    )}
                  </div>
                )
              })
            )}
          </div>
        )}

        {tab === 'markets' && (
          <div className="p-4 space-y-2">
            {markets.map((market) => (
              <div
                key={market.market_id}
                className="p-3 bg-terminal-surface rounded-lg hover:bg-terminal-border/30 transition-colors cursor-pointer"
                onClick={() => setSelectedMarket(market.market_id)}
              >
                <div className="flex items-center justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium truncate">{market.question}</div>
                    <div className="text-xs text-terminal-muted flex items-center gap-2">
                      <span className="px-1.5 py-0.5 bg-terminal-bg rounded">{market.category}</span>
                      <span>Vol: {formatUsd(market.volume_24h)}</span>
                    </div>
                  </div>
                  <ChevronRight className="w-4 h-4 text-terminal-muted" />
                </div>
              </div>
            ))}
          </div>
        )}

        {tab === 'stats' && stats && (
          <div className="p-4 space-y-4">
            {/* Key Metrics */}
            <div className="grid grid-cols-2 gap-3">
              <div className="p-3 bg-terminal-surface rounded-lg text-center">
                <div className="text-2xl font-mono font-bold text-purple-400">
                  {stats.brier_score.toFixed(3)}
                </div>
                <div className="text-xs text-terminal-muted">Brier Score</div>
                <div className="text-xs text-terminal-muted mt-1">
                  {stats.brier_score < 0.2 ? '✅ Good' : stats.brier_score < 0.25 ? '⚠️ Average' : '❌ Poor'}
                </div>
              </div>
              <div className="p-3 bg-terminal-surface rounded-lg text-center">
                <div className={clsx(
                  "text-2xl font-mono font-bold",
                  stats.mean_edge >= 0 ? "text-bull" : "text-bear"
                )}>
                  {formatPct(stats.mean_edge)}
                </div>
                <div className="text-xs text-terminal-muted">Mean Edge</div>
              </div>
            </div>

            {/* Secondary Stats */}
            <div className="space-y-2">
              <div className="flex justify-between p-2 bg-terminal-bg rounded">
                <span className="text-sm text-terminal-muted">Prediction Accuracy</span>
                <span className="font-mono">{stats.prediction_accuracy.toFixed(1)}%</span>
              </div>
              <div className="flex justify-between p-2 bg-terminal-bg rounded">
                <span className="text-sm text-terminal-muted">Total Decisions</span>
                <span className="font-mono">{stats.total_decisions}</span>
              </div>
              <div className="flex justify-between p-2 bg-terminal-bg rounded">
                <span className="text-sm text-terminal-muted">Resolved</span>
                <span className="font-mono">{stats.resolved_decisions}</span>
              </div>
              <div className="flex justify-between p-2 bg-terminal-bg rounded">
                <span className="text-sm text-terminal-muted">Total P&L</span>
                <span className={clsx("font-mono", stats.total_pnl >= 0 ? "text-bull" : "text-bear")}>
                  {formatUsd(stats.total_pnl)}
                </span>
              </div>
            </div>

            {/* Info Box */}
            <div className="p-3 bg-purple-400/10 rounded-lg text-xs text-purple-300">
              <div className="font-semibold mb-1">📊 Research Mode</div>
              <p>
                This simulator measures probability calibration (Brier score) and edge preservation.
                Trading is not the goal—accurate forecasting is.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

