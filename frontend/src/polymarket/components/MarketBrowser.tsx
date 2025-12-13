import { useState, useMemo } from 'react'
import { 
  Search, Filter, TrendingUp, TrendingDown, Clock, 
  ChevronRight, Zap, AlertTriangle, DollarSign
} from 'lucide-react'
import clsx from 'clsx'
import type { Market, Probability } from '../PolymarketApp'

interface MarketBrowserProps {
  markets: Market[]
  opportunities: Probability[]
  onSelectMarket: (market: Market) => void
  showOpportunitiesOnly?: boolean
}

const CATEGORIES = ['all', 'crypto', 'politics', 'sports', 'tech', 'economics', 'other']

export function MarketBrowser({ 
  markets, 
  opportunities, 
  onSelectMarket,
  showOpportunitiesOnly = false 
}: MarketBrowserProps) {
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState('all')
  const [sortBy, setSortBy] = useState<'edge' | 'volume' | 'time'>('edge')

  // Create a map of market_id -> opportunity for quick lookup
  const opportunityMap = useMemo(() => {
    const map = new Map<string, Probability>()
    opportunities.forEach(o => map.set(o.market_id, o))
    return map
  }, [opportunities])

  // Filter and sort markets
  const displayMarkets = useMemo(() => {
    let filtered = showOpportunitiesOnly
      ? markets.filter(m => opportunityMap.has(m.market_id))
      : markets

    // Search filter
    if (search) {
      const lower = search.toLowerCase()
      filtered = filtered.filter(m => 
        m.question.toLowerCase().includes(lower) ||
        m.slug.toLowerCase().includes(lower)
      )
    }

    // Category filter
    if (category !== 'all') {
      filtered = filtered.filter(m => m.category === category)
    }

    // Sort
    return filtered.sort((a, b) => {
      if (sortBy === 'edge') {
        const aEdge = Math.abs(opportunityMap.get(a.market_id)?.edge_pct || 0)
        const bEdge = Math.abs(opportunityMap.get(b.market_id)?.edge_pct || 0)
        return bEdge - aEdge
      } else if (sortBy === 'volume') {
        return b.volume_24h - a.volume_24h
      } else {
        return a.time_to_resolution_hours - b.time_to_resolution_hours
      }
    })
  }, [markets, opportunities, search, category, sortBy, showOpportunitiesOnly, opportunityMap])

  const formatTime = (hours: number) => {
    if (hours < 24) return `${Math.round(hours)}h`
    if (hours < 168) return `${Math.round(hours / 24)}d`
    return `${Math.round(hours / 168)}w`
  }

  const formatUsd = (val: number) => {
    if (val >= 1000000) return `$${(val / 1000000).toFixed(1)}M`
    if (val >= 1000) return `$${(val / 1000).toFixed(0)}K`
    return `$${val.toFixed(0)}`
  }

  return (
    <div className="h-full flex flex-col">
      {/* Filters */}
      <div className="p-4 bg-[#12121a] border-b border-[#1e1e2e]">
        <div className="flex gap-4 items-center">
          {/* Search */}
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
            <input
              type="text"
              placeholder="Search markets..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-[#1e1e2e] border border-[#2a2a3e] rounded-lg text-white placeholder-gray-500 focus:border-purple-500 focus:outline-none"
            />
          </div>

          {/* Category */}
          <div className="flex gap-1 bg-[#1e1e2e] rounded-lg p-1">
            {CATEGORIES.map(cat => (
              <button
                key={cat}
                onClick={() => setCategory(cat)}
                className={clsx(
                  'px-3 py-1.5 text-xs font-medium rounded-md transition-colors capitalize',
                  category === cat
                    ? 'bg-purple-600 text-white'
                    : 'text-gray-400 hover:text-white'
                )}
              >
                {cat}
              </button>
            ))}
          </div>

          {/* Sort */}
          <select
            value={sortBy}
            onChange={e => setSortBy(e.target.value as any)}
            className="px-3 py-2 bg-[#1e1e2e] border border-[#2a2a3e] rounded-lg text-white text-sm focus:border-purple-500 focus:outline-none"
          >
            <option value="edge">Sort by Edge</option>
            <option value="volume">Sort by Volume</option>
            <option value="time">Sort by Time</option>
          </select>
        </div>
      </div>

      {/* Market Grid */}
      <div className="flex-1 overflow-y-auto p-4">
        {displayMarkets.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-gray-500">
            <Zap className="w-12 h-12 mb-4 opacity-30" />
            <p className="text-lg font-medium">No markets found</p>
            <p className="text-sm">Try adjusting your filters</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
            {displayMarkets.map(market => {
              const opp = opportunityMap.get(market.market_id)
              const hasEdge = opp && Math.abs(opp.edge_pct) >= 1.0
              
              return (
                <div
                  key={market.market_id}
                  onClick={() => onSelectMarket(market)}
                  className={clsx(
                    'p-4 rounded-xl border cursor-pointer transition-all hover:scale-[1.02]',
                    hasEdge
                      ? opp.edge > 0
                        ? 'bg-emerald-500/5 border-emerald-500/30 hover:border-emerald-500/50'
                        : 'bg-red-500/5 border-red-500/30 hover:border-red-500/50'
                      : 'bg-[#12121a] border-[#1e1e2e] hover:border-[#2a2a3e]'
                  )}
                >
                  {/* Category & Time */}
                  <div className="flex items-center justify-between mb-2">
                    <span className={clsx(
                      'px-2 py-0.5 text-xs font-medium rounded-full capitalize',
                      market.category === 'crypto' ? 'bg-orange-500/20 text-orange-400' :
                      market.category === 'politics' ? 'bg-blue-500/20 text-blue-400' :
                      market.category === 'sports' ? 'bg-green-500/20 text-green-400' :
                      'bg-gray-500/20 text-gray-400'
                    )}>
                      {market.category}
                    </span>
                    <div className="flex items-center gap-1 text-xs text-gray-500">
                      <Clock className="w-3 h-3" />
                      {formatTime(market.time_to_resolution_hours)}
                    </div>
                  </div>

                  {/* Question */}
                  <h3 className="text-white font-medium mb-3 line-clamp-2 min-h-[48px]">
                    {market.question}
                  </h3>

                  {/* Probability & Edge */}
                  {opp ? (
                    <div className="grid grid-cols-3 gap-2 mb-3">
                      <div>
                        <div className="text-xs text-gray-500">Market</div>
                        <div className="text-lg font-mono font-bold text-white">
                          {(opp.market_prob * 100).toFixed(0)}%
                        </div>
                      </div>
                      <div>
                        <div className="text-xs text-gray-500">Fair</div>
                        <div className="text-lg font-mono font-bold text-purple-400">
                          {(opp.fair_prob * 100).toFixed(0)}%
                        </div>
                      </div>
                      <div>
                        <div className="text-xs text-gray-500">Edge</div>
                        <div className={clsx(
                          'text-lg font-mono font-bold',
                          opp.edge > 0 ? 'text-emerald-400' : 'text-red-400'
                        )}>
                          {opp.edge > 0 ? '+' : ''}{opp.edge_pct.toFixed(1)}%
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="h-[52px] flex items-center text-sm text-gray-500">
                      Click to analyze
                    </div>
                  )}

                  {/* Risk Flags */}
                  {opp?.risk_flags && opp.risk_flags.length > 0 && (
                    <div className="flex flex-wrap gap-1 mb-3">
                      {opp.risk_flags.slice(0, 3).map(flag => (
                        <span 
                          key={flag}
                          className="px-1.5 py-0.5 text-xs bg-amber-500/10 text-amber-400 rounded"
                        >
                          {flag.replace('_', ' ')}
                        </span>
                      ))}
                    </div>
                  )}

                  {/* Footer */}
                  <div className="flex items-center justify-between pt-3 border-t border-[#1e1e2e]">
                    <div className="flex items-center gap-1 text-xs text-gray-500">
                      <DollarSign className="w-3 h-3" />
                      Vol: {formatUsd(market.volume_24h)}
                    </div>
                    <div className="flex items-center gap-1 text-purple-400 text-xs font-medium">
                      View Details
                      <ChevronRight className="w-4 h-4" />
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

