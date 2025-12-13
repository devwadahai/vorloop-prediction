import { BarChart3, Target, TrendingUp, Award, AlertTriangle } from 'lucide-react'
import clsx from 'clsx'
import type { Stats, Account } from '../PolymarketApp'

interface StatsPanelProps {
  stats: Stats | null
  account: Account | null
}

export function StatsPanel({ stats, account }: StatsPanelProps) {
  if (!stats) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center text-gray-500">
          <BarChart3 className="w-12 h-12 mx-auto mb-4 opacity-30" />
          <p className="text-lg font-medium">No Stats Yet</p>
          <p className="text-sm">Start trading to see performance metrics</p>
        </div>
      </div>
    )
  }

  const getBrierRating = (score: number) => {
    if (score < 0.15) return { label: 'Excellent', color: 'text-emerald-400', bg: 'bg-emerald-400' }
    if (score < 0.20) return { label: 'Good', color: 'text-green-400', bg: 'bg-green-400' }
    if (score < 0.25) return { label: 'Average', color: 'text-yellow-400', bg: 'bg-yellow-400' }
    if (score < 0.30) return { label: 'Poor', color: 'text-orange-400', bg: 'bg-orange-400' }
    return { label: 'Bad', color: 'text-red-400', bg: 'bg-red-400' }
  }

  const brierRating = getBrierRating(stats.brier_score)

  return (
    <div className="h-full overflow-y-auto">
      {/* Header */}
      <div className="p-6 bg-[#12121a] border-b border-[#1e1e2e]">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-purple-500/20 flex items-center justify-center">
            <BarChart3 className="w-6 h-6 text-purple-400" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-white">Performance Metrics</h2>
            <p className="text-sm text-gray-500">Research-grade probability evaluation</p>
          </div>
        </div>
      </div>

      <div className="p-6 space-y-6">
        {/* Primary Metrics */}
        <div className="grid grid-cols-2 gap-4">
          {/* Brier Score */}
          <div className="p-6 bg-[#12121a] rounded-2xl border border-[#1e1e2e]">
            <div className="flex items-center justify-between mb-4">
              <div className="text-sm text-gray-500">Brier Score</div>
              <span className={clsx(
                'px-2 py-0.5 text-xs font-medium rounded',
                brierRating.color,
                brierRating.bg + '/20'
              )}>
                {brierRating.label}
              </span>
            </div>
            <div className="text-4xl font-mono font-bold text-white mb-2">
              {stats.brier_score.toFixed(3)}
            </div>
            <div className="text-xs text-gray-500">
              Lower is better • Perfect = 0 • Random = 0.25
            </div>
            {/* Brier Scale */}
            <div className="mt-4">
              <div className="h-2 bg-[#1e1e2e] rounded-full overflow-hidden">
                <div 
                  className={clsx('h-full transition-all', brierRating.bg)}
                  style={{ width: `${Math.max(5, 100 - stats.brier_score * 400)}%` }}
                />
              </div>
              <div className="flex justify-between text-xs text-gray-600 mt-1">
                <span>0 (Perfect)</span>
                <span>0.25 (Random)</span>
              </div>
            </div>
          </div>

          {/* Mean Edge */}
          <div className="p-6 bg-[#12121a] rounded-2xl border border-[#1e1e2e]">
            <div className="text-sm text-gray-500 mb-4">Mean Edge Realized</div>
            <div className={clsx(
              'text-4xl font-mono font-bold mb-2',
              stats.mean_edge >= 0 ? 'text-emerald-400' : 'text-red-400'
            )}>
              {stats.mean_edge >= 0 ? '+' : ''}{stats.mean_edge.toFixed(2)}%
            </div>
            <div className="text-xs text-gray-500">
              Average edge captured per trade
            </div>
            <div className="mt-4 p-3 bg-[#0a0a0f] rounded-lg">
              <div className="text-xs text-gray-500">Edge Preservation Ratio</div>
              <div className="text-lg font-mono text-white">
                {(stats.edge_preservation_ratio * 100).toFixed(0)}%
              </div>
            </div>
          </div>
        </div>

        {/* Secondary Metrics */}
        <div className="grid grid-cols-3 gap-4">
          <div className="p-4 bg-[#12121a] rounded-xl border border-[#1e1e2e]">
            <div className="flex items-center gap-2 mb-2">
              <Target className="w-4 h-4 text-purple-400" />
              <span className="text-sm text-gray-500">Prediction Accuracy</span>
            </div>
            <div className="text-2xl font-mono font-bold text-white">
              {stats.prediction_accuracy.toFixed(1)}%
            </div>
          </div>

          <div className="p-4 bg-[#12121a] rounded-xl border border-[#1e1e2e]">
            <div className="flex items-center gap-2 mb-2">
              <Award className="w-4 h-4 text-amber-400" />
              <span className="text-sm text-gray-500">Win Rate</span>
            </div>
            <div className="text-2xl font-mono font-bold text-white">
              {stats.win_rate.toFixed(1)}%
            </div>
          </div>

          <div className="p-4 bg-[#12121a] rounded-xl border border-[#1e1e2e]">
            <div className="flex items-center gap-2 mb-2">
              <AlertTriangle className="w-4 h-4 text-orange-400" />
              <span className="text-sm text-gray-500">Execution Drag</span>
            </div>
            <div className="text-2xl font-mono font-bold text-white">
              {stats.mean_execution_drag_bps.toFixed(1)} bps
            </div>
          </div>
        </div>

        {/* Decision Counts */}
        <div className="p-6 bg-[#12121a] rounded-2xl border border-[#1e1e2e]">
          <h3 className="text-sm font-semibold text-gray-400 mb-4">Decision Tracking</h3>
          <div className="grid grid-cols-3 gap-4">
            <div className="text-center p-4 bg-[#0a0a0f] rounded-xl">
              <div className="text-3xl font-mono font-bold text-white">{stats.total_decisions}</div>
              <div className="text-sm text-gray-500">Total Decisions</div>
            </div>
            <div className="text-center p-4 bg-[#0a0a0f] rounded-xl">
              <div className="text-3xl font-mono font-bold text-emerald-400">{stats.resolved_decisions}</div>
              <div className="text-sm text-gray-500">Resolved</div>
            </div>
            <div className="text-center p-4 bg-[#0a0a0f] rounded-xl">
              <div className="text-3xl font-mono font-bold text-amber-400">{stats.pending_decisions}</div>
              <div className="text-sm text-gray-500">Pending</div>
            </div>
          </div>
        </div>

        {/* P&L Summary */}
        <div className="p-6 bg-[#12121a] rounded-2xl border border-[#1e1e2e]">
          <h3 className="text-sm font-semibold text-gray-400 mb-4">Profit & Loss</h3>
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm text-gray-500">Total P&L</div>
              <div className={clsx(
                'text-3xl font-mono font-bold',
                stats.total_pnl >= 0 ? 'text-emerald-400' : 'text-red-400'
              )}>
                {stats.total_pnl >= 0 ? '+' : ''}${stats.total_pnl.toFixed(2)}
              </div>
            </div>
            {account && (
              <div className="text-right">
                <div className="text-sm text-gray-500">Return on Capital</div>
                <div className={clsx(
                  'text-3xl font-mono font-bold',
                  stats.total_pnl >= 0 ? 'text-emerald-400' : 'text-red-400'
                )}>
                  {stats.total_pnl >= 0 ? '+' : ''}
                  {((stats.total_pnl / account.initial_balance) * 100).toFixed(2)}%
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Research Note */}
        <div className="p-4 bg-purple-500/10 border border-purple-500/20 rounded-xl">
          <div className="flex items-start gap-3">
            <BarChart3 className="w-5 h-5 text-purple-400 mt-0.5" />
            <div>
              <h4 className="font-medium text-purple-400 mb-1">Research Mode</h4>
              <p className="text-sm text-purple-300/80">
                This simulator prioritizes probability calibration over raw P&L. 
                A good Brier score (&lt;0.20) indicates accurate probability estimation, 
                which is the foundation of sustainable edge.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

