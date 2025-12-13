import { TrendingUp, TrendingDown, Wallet, AlertCircle } from 'lucide-react'
import clsx from 'clsx'
import type { Position, Market, Account } from '../PolymarketApp'

interface PositionsPanelProps {
  positions: Position[]
  markets: Market[]
  account: Account | null
  onRefresh: () => void
}

export function PositionsPanel({ positions, markets, account, onRefresh }: PositionsPanelProps) {
  const getMarket = (marketId: string) => markets.find(m => m.market_id === marketId)

  const totalUnrealized = positions.reduce((sum, p) => sum + (p.unrealized_pnl || 0), 0)
  const totalRealized = positions.reduce((sum, p) => sum + p.realized_pnl, 0)
  const totalCostBasis = positions.reduce((sum, p) => sum + p.cost_basis, 0)

  if (!account) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center text-gray-500">
          <Wallet className="w-12 h-12 mx-auto mb-4 opacity-30" />
          <p className="text-lg font-medium">No Account</p>
          <p className="text-sm">Create a paper trading account to start</p>
        </div>
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col">
      {/* Summary */}
      <div className="p-6 bg-[#12121a] border-b border-[#1e1e2e]">
        <div className="grid grid-cols-4 gap-6">
          <div className="text-center">
            <div className="text-sm text-gray-500 mb-1">Open Positions</div>
            <div className="text-3xl font-mono font-bold text-white">{positions.length}</div>
          </div>
          <div className="text-center">
            <div className="text-sm text-gray-500 mb-1">Cost Basis</div>
            <div className="text-3xl font-mono font-bold text-white">
              ${totalCostBasis.toLocaleString()}
            </div>
          </div>
          <div className="text-center">
            <div className="text-sm text-gray-500 mb-1">Unrealized P&L</div>
            <div className={clsx(
              'text-3xl font-mono font-bold',
              totalUnrealized >= 0 ? 'text-emerald-400' : 'text-red-400'
            )}>
              {totalUnrealized >= 0 ? '+' : ''}${totalUnrealized.toFixed(2)}
            </div>
          </div>
          <div className="text-center">
            <div className="text-sm text-gray-500 mb-1">Realized P&L</div>
            <div className={clsx(
              'text-3xl font-mono font-bold',
              totalRealized >= 0 ? 'text-emerald-400' : 'text-red-400'
            )}>
              {totalRealized >= 0 ? '+' : ''}${totalRealized.toFixed(2)}
            </div>
          </div>
        </div>
      </div>

      {/* Positions List */}
      <div className="flex-1 overflow-y-auto p-6">
        {positions.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-gray-500">
            <Wallet className="w-12 h-12 mb-4 opacity-30" />
            <p className="text-lg font-medium">No Open Positions</p>
            <p className="text-sm">Browse opportunities and place some trades</p>
          </div>
        ) : (
          <div className="space-y-4">
            {positions.map(position => {
              const market = getMarket(position.market_id)
              const pnlPct = position.cost_basis > 0 
                ? ((position.unrealized_pnl || 0) / position.cost_basis) * 100 
                : 0

              return (
                <div
                  key={position.token_id}
                  className={clsx(
                    'p-4 rounded-xl border',
                    (position.unrealized_pnl || 0) >= 0
                      ? 'bg-emerald-500/5 border-emerald-500/20'
                      : 'bg-red-500/5 border-red-500/20'
                  )}
                >
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        {position.side === 'YES' ? (
                          <TrendingUp className="w-4 h-4 text-emerald-400" />
                        ) : (
                          <TrendingDown className="w-4 h-4 text-red-400" />
                        )}
                        <span className={clsx(
                          'text-sm font-semibold',
                          position.side === 'YES' ? 'text-emerald-400' : 'text-red-400'
                        )}>
                          {position.side}
                        </span>
                        <span className="text-sm text-gray-500">
                          {position.quantity} shares
                        </span>
                      </div>
                      <h3 className="text-white font-medium">
                        {market?.question || position.market_id}
                      </h3>
                    </div>
                    <div className="text-right">
                      <div className={clsx(
                        'text-xl font-mono font-bold',
                        (position.unrealized_pnl || 0) >= 0 ? 'text-emerald-400' : 'text-red-400'
                      )}>
                        {(position.unrealized_pnl || 0) >= 0 ? '+' : ''}
                        ${(position.unrealized_pnl || 0).toFixed(2)}
                      </div>
                      <div className={clsx(
                        'text-sm',
                        pnlPct >= 0 ? 'text-emerald-400' : 'text-red-400'
                      )}>
                        {pnlPct >= 0 ? '+' : ''}{pnlPct.toFixed(1)}%
                      </div>
                    </div>
                  </div>

                  <div className="grid grid-cols-3 gap-4 text-sm">
                    <div>
                      <div className="text-gray-500">Avg Entry</div>
                      <div className="font-mono text-white">
                        {(position.avg_price * 100).toFixed(1)}¢
                      </div>
                    </div>
                    <div>
                      <div className="text-gray-500">Cost Basis</div>
                      <div className="font-mono text-white">
                        ${position.cost_basis.toFixed(2)}
                      </div>
                    </div>
                    <div>
                      <div className="text-gray-500">Realized</div>
                      <div className={clsx(
                        'font-mono',
                        position.realized_pnl >= 0 ? 'text-emerald-400' : 'text-red-400'
                      )}>
                        ${position.realized_pnl.toFixed(2)}
                      </div>
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

