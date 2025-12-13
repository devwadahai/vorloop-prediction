import { useState, useEffect, useCallback } from 'react'
import { 
  Target, RefreshCw, ArrowLeft, TrendingUp, TrendingDown,
  BarChart3, Wallet, Clock, AlertCircle, Search, Filter,
  ChevronRight, Activity, PieChart, List, Grid3X3
} from 'lucide-react'
import clsx from 'clsx'
import { MarketBrowser } from './components/MarketBrowser'
import { MarketDetail } from './components/MarketDetail'
import { PositionsPanel } from './components/PositionsPanel'
import { StatsPanel } from './components/StatsPanel'

const API_BASE = 'http://localhost:8000/api/v1/polymarket'

export interface Market {
  market_id: string
  slug: string
  question: string
  description: string
  category: string
  end_time: string
  resolution_status: string
  volume_24h: number
  liquidity: number
  time_to_resolution_hours: number
}

export interface OrderBook {
  token_id: string
  bids: [number, number][]
  asks: [number, number][]
  best_bid: number | null
  best_ask: number | null
  mid_price: number | null
  spread: number | null
  spread_bps: number | null
  bid_depth: number
  ask_depth: number
  imbalance: number
}

export interface Probability {
  market_id: string
  token_id: string
  fair_prob: number
  market_prob: number
  edge: number
  edge_pct: number
  expected_value: number
  kelly_fraction: number
  confidence: number
  risk_flags: string[]
  risk_score: number
  is_tradeable: boolean
  suggested_side: string | null
}

export interface Account {
  account_id: string
  balance: number
  initial_balance: number
  total_pnl: number
  equity: number
  total_trades: number
  win_rate: number
  total_fees_paid: number
  open_positions: number
}

export interface Position {
  token_id: string
  market_id: string
  side: string
  quantity: number
  avg_price: number
  cost_basis: number
  unrealized_pnl: number | null
  realized_pnl: number
}

export interface Stats {
  total_decisions: number
  resolved_decisions: number
  pending_decisions: number
  brier_score: number
  mean_edge: number
  edge_preservation_ratio: number
  mean_execution_drag_bps: number
  total_pnl: number
  win_rate: number
  prediction_accuracy: number
}

interface PolymarketAppProps {
  onBack: () => void
}

export function PolymarketApp({ onBack }: PolymarketAppProps) {
  const [markets, setMarkets] = useState<Market[]>([])
  const [opportunities, setOpportunities] = useState<Probability[]>([])
  const [account, setAccount] = useState<Account | null>(null)
  const [positions, setPositions] = useState<Position[]>([])
  const [stats, setStats] = useState<Stats | null>(null)
  const [loading, setLoading] = useState(true)
  const [initialLoad, setInitialLoad] = useState(true)
  const [error, setError] = useState<string | null>(null)
  
  const [selectedMarket, setSelectedMarket] = useState<Market | null>(null)
  const [view, setView] = useState<'browse' | 'opportunities' | 'positions' | 'stats'>('opportunities')

  const fetchData = useCallback(async (isBackground = false) => {
    if (!isBackground) setLoading(true)
    setError(null)
    try {
      // Fetch critical data first (opportunities for main view)
      const oppsRes = await fetch(`${API_BASE}/opportunities?min_edge=1.0&limit=20`)
      if (oppsRes.ok) {
        setOpportunities(await oppsRes.json())
        setInitialLoad(false)
      }

      // Then fetch rest in parallel
      const [marketsRes, accountRes, positionsRes, statsRes] = await Promise.all([
        fetch(`${API_BASE}/markets?limit=50`),
        fetch(`${API_BASE}/account`).catch(() => null),
        fetch(`${API_BASE}/positions`).catch(() => null),
        fetch(`${API_BASE}/stats`),
      ])

      if (marketsRes.ok) setMarkets(await marketsRes.json())
      if (accountRes?.ok) setAccount(await accountRes.json())
      if (positionsRes?.ok) setPositions(await positionsRes.json())
      if (statsRes.ok) setStats(await statsRes.json())
    } catch (e) {
      setError('Failed to connect to backend. Make sure the server is running.')
      setInitialLoad(false)
    }
    setLoading(false)
  }, [])

  useEffect(() => {
    fetchData()
    // Background refresh every 30 seconds (non-blocking)
    const interval = setInterval(() => fetchData(true), 30000)
    return () => clearInterval(interval)
  }, [fetchData])

  const createAccount = async () => {
    try {
      const res = await fetch(`${API_BASE}/account?initial_balance=10000`, { method: 'POST' })
      if (res.ok) {
        const acc = await res.json()
        setAccount(acc)
        return acc
      }
    } catch (e) {
      setError('Failed to create account')
    }
    return null
  }

  const resetSimulation = async () => {
    if (!confirm('Reset simulation? This will clear all trades and positions.')) return
    try {
      await fetch(`${API_BASE}/reset`, { method: 'POST' })
      setAccount(null)
      setPositions([])
      fetchData()
    } catch (e) {
      setError('Failed to reset')
    }
  }

  const formatUsd = (val: number) => 
    `$${Math.abs(val).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`

  // If a market is selected, show detail view
  if (selectedMarket) {
    return (
      <MarketDetail
        market={selectedMarket}
        account={account}
        onBack={() => setSelectedMarket(null)}
        onAccountCreate={createAccount}
        onRefresh={fetchData}
      />
    )
  }

  return (
    <div className="h-screen flex flex-col bg-[#0a0a0f]">
      {/* Header */}
      <header className="bg-[#12121a] border-b border-[#1e1e2e] px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={onBack}
              className="p-2 rounded-lg hover:bg-[#1e1e2e] transition-colors"
            >
              <ArrowLeft className="w-5 h-5 text-gray-400" />
            </button>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center">
                <Target className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-lg font-bold text-white">Polymarket Simulator</h1>
                <p className="text-xs text-gray-500">Probability Research & Paper Trading</p>
              </div>
            </div>
          </div>

          {/* Account Info */}
          <div className="flex items-center gap-6">
            {account ? (
              <>
                <div className="text-right">
                  <div className="text-xs text-gray-500">Balance</div>
                  <div className="text-lg font-mono font-bold text-white">{formatUsd(account.balance)}</div>
                </div>
                <div className="text-right">
                  <div className="text-xs text-gray-500">P&L</div>
                  <div className={clsx(
                    "text-lg font-mono font-bold",
                    account.total_pnl >= 0 ? "text-emerald-400" : "text-red-400"
                  )}>
                    {account.total_pnl >= 0 ? '+' : ''}{formatUsd(account.total_pnl)}
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-xs text-gray-500">Positions</div>
                  <div className="text-lg font-mono font-bold text-white">{account.open_positions}</div>
                </div>
                <button
                  onClick={resetSimulation}
                  className="px-3 py-1.5 text-xs text-gray-400 hover:text-white border border-gray-700 rounded-lg hover:border-gray-500 transition-colors"
                >
                  Reset
                </button>
              </>
            ) : (
              <button
                onClick={createAccount}
                className="px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white rounded-lg font-medium transition-colors"
              >
                Create Account ($10,000)
              </button>
            )}
            <button
              onClick={fetchData}
              disabled={loading}
              className="p-2 rounded-lg hover:bg-[#1e1e2e] transition-colors"
            >
              <RefreshCw className={clsx("w-5 h-5 text-gray-400", loading && "animate-spin")} />
            </button>
          </div>
        </div>
      </header>

      {/* Navigation */}
      <nav className="bg-[#12121a] border-b border-[#1e1e2e] px-6">
        <div className="flex gap-1">
          {[
            { id: 'opportunities', label: 'Opportunities', icon: TrendingUp, count: opportunities.length },
            { id: 'browse', label: 'All Markets', icon: Grid3X3, count: markets.length },
            { id: 'positions', label: 'Positions', icon: Wallet, count: positions.length },
            { id: 'stats', label: 'Performance', icon: BarChart3 },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setView(tab.id as any)}
              className={clsx(
                'flex items-center gap-2 px-4 py-3 text-sm font-medium transition-colors border-b-2',
                view === tab.id
                  ? 'text-purple-400 border-purple-400'
                  : 'text-gray-500 border-transparent hover:text-gray-300'
              )}
            >
              <tab.icon className="w-4 h-4" />
              {tab.label}
              {tab.count !== undefined && (
                <span className={clsx(
                  "px-1.5 py-0.5 text-xs rounded-full",
                  view === tab.id ? "bg-purple-400/20" : "bg-gray-700"
                )}>
                  {tab.count}
                </span>
              )}
            </button>
          ))}
        </div>
      </nav>

      {/* Error Banner */}
      {error && (
        <div className="bg-red-500/10 border-b border-red-500/30 px-6 py-3 flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-red-400" />
          <span className="text-red-400 text-sm">{error}</span>
          <button 
            onClick={() => setError(null)}
            className="ml-auto text-xs text-red-400 hover:text-red-300 underline"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Main Content */}
      <main className="flex-1 overflow-hidden">
        {initialLoad ? (
          <div className="h-full flex flex-col items-center justify-center">
            <div className="w-12 h-12 border-4 border-purple-500/30 border-t-purple-500 rounded-full animate-spin mb-4" />
            <p className="text-gray-400">Loading Polymarket data...</p>
            <p className="text-sm text-gray-600 mt-1">Fetching markets and order books</p>
          </div>
        ) : (
          <>
            {view === 'opportunities' && (
              <MarketBrowser
                markets={markets}
                opportunities={opportunities}
                onSelectMarket={setSelectedMarket}
                showOpportunitiesOnly
              />
            )}
            {view === 'browse' && (
              <MarketBrowser
                markets={markets}
                opportunities={opportunities}
                onSelectMarket={setSelectedMarket}
              />
            )}
            {view === 'positions' && (
              <PositionsPanel
                positions={positions}
                markets={markets}
                account={account}
                onRefresh={() => fetchData()}
              />
            )}
            {view === 'stats' && (
              <StatsPanel stats={stats} account={account} />
            )}
          </>
        )}
      </main>
    </div>
  )
}

