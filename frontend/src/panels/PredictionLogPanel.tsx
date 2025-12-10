import { useEffect, useState } from 'react'
import { CheckCircle, XCircle, Clock, TrendingUp, TrendingDown, RefreshCw, Target } from 'lucide-react'
import clsx from 'clsx'

interface PredictionStats {
  total_predictions: number
  correct_predictions: number
  accuracy_pct: number
  pending_validations: number
  by_confidence: {
    high: { total: number; correct: number; accuracy: number }
    medium: { total: number; correct: number; accuracy: number }
    low: { total: number; correct: number; accuracy: number }
  }
}

interface PredictionRecord {
  id: string
  asset: string
  timestamp: string
  horizon_minutes: number
  entry_price: number
  p_up: number
  exit_price: number | null
  actual_move: number | null
  prediction_correct: boolean | null
  regime: string
  confidence: string
}

export function PredictionLogPanel() {
  const [stats, setStats] = useState<PredictionStats | null>(null)
  const [history, setHistory] = useState<PredictionRecord[]>([])
  const [pending, setPending] = useState<PredictionRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<'history' | 'pending'>('history')

  const fetchData = async () => {
    try {
      const [statsRes, historyRes, pendingRes] = await Promise.all([
        fetch('/api/v1/prediction-stats'),
        fetch('/api/v1/prediction-history?limit=20'),
        fetch('/api/v1/pending-predictions'),
      ])

      if (statsRes.ok) {
        setStats(await statsRes.json())
      }
      if (historyRes.ok) {
        const data = await historyRes.json()
        setHistory(data.history || [])
      }
      if (pendingRes.ok) {
        const data = await pendingRes.json()
        setPending(data.pending || [])
      }
    } catch (err) {
      console.error('Failed to fetch prediction data:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 10000) // Refresh every 10s
    return () => clearInterval(interval)
  }, [])

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center text-terminal-muted">
        <RefreshCw className="w-5 h-5 animate-spin mr-2" />
        Loading prediction log...
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col bg-terminal-surface rounded-xl border border-terminal-border overflow-hidden">
      {/* Header with Stats */}
      <div className="p-4 border-b border-terminal-border">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-display font-semibold flex items-center gap-2">
            <Target className="w-4 h-4 text-accent" />
            Prediction Log
          </h2>
          <button
            onClick={fetchData}
            className="p-1.5 rounded hover:bg-terminal-border/50 text-terminal-muted hover:text-white transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>

        {/* Stats Grid */}
        {stats && (
          <div className="grid grid-cols-4 gap-2">
            <StatBox
              label="Total"
              value={stats.total_predictions}
              color="text-white"
            />
            <StatBox
              label="Correct"
              value={stats.correct_predictions}
              color="text-bull"
            />
            <StatBox
              label="Accuracy"
              value={`${stats.accuracy_pct.toFixed(1)}%`}
              color={stats.accuracy_pct >= 50 ? 'text-bull' : 'text-bear'}
            />
            <StatBox
              label="Pending"
              value={stats.pending_validations}
              color="text-amber-400"
            />
          </div>
        )}

        {/* Confidence Breakdown */}
        {stats && stats.total_predictions > 0 && (
          <div className="mt-3 flex gap-4 text-xs">
            {(['high', 'medium', 'low'] as const).map((conf) => {
              const s = stats.by_confidence[conf]
              if (s.total === 0) return null
              return (
                <div key={conf} className="flex items-center gap-1">
                  <span className={clsx(
                    'capitalize',
                    conf === 'high' && 'text-bull',
                    conf === 'medium' && 'text-amber-400',
                    conf === 'low' && 'text-bear'
                  )}>
                    {conf}:
                  </span>
                  <span className="text-terminal-muted">
                    {s.correct}/{s.total} ({s.accuracy.toFixed(0)}%)
                  </span>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="flex border-b border-terminal-border">
        <button
          onClick={() => setActiveTab('history')}
          className={clsx(
            'flex-1 px-4 py-2 text-sm font-medium transition-colors',
            activeTab === 'history'
              ? 'text-white border-b-2 border-accent'
              : 'text-terminal-muted hover:text-white'
          )}
        >
          History ({history.length})
        </button>
        <button
          onClick={() => setActiveTab('pending')}
          className={clsx(
            'flex-1 px-4 py-2 text-sm font-medium transition-colors',
            activeTab === 'pending'
              ? 'text-white border-b-2 border-accent'
              : 'text-terminal-muted hover:text-white'
          )}
        >
          Pending ({pending.length})
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto">
        {activeTab === 'history' ? (
          history.length === 0 ? (
            <div className="h-full flex items-center justify-center text-terminal-muted text-sm">
              No validated predictions yet
            </div>
          ) : (
            <div className="divide-y divide-terminal-border">
              {history.map((pred) => (
                <PredictionRow key={pred.id} prediction={pred} validated />
              ))}
            </div>
          )
        ) : (
          pending.length === 0 ? (
            <div className="h-full flex items-center justify-center text-terminal-muted text-sm">
              No pending predictions
            </div>
          ) : (
            <div className="divide-y divide-terminal-border">
              {pending.map((pred) => (
                <PredictionRow key={pred.id} prediction={pred} validated={false} />
              ))}
            </div>
          )
        )}
      </div>
    </div>
  )
}

function StatBox({ label, value, color }: { label: string; value: string | number; color: string }) {
  return (
    <div className="bg-terminal-bg rounded-lg p-2 text-center">
      <div className={clsx('font-mono font-bold text-lg', color)}>{value}</div>
      <div className="text-xs text-terminal-muted">{label}</div>
    </div>
  )
}

function PredictionRow({ prediction, validated }: { prediction: PredictionRecord; validated: boolean }) {
  const predictedUp = prediction.p_up > 0.5
  const actualUp = prediction.actual_move !== null ? prediction.actual_move > 0 : null
  const isCorrect = prediction.prediction_correct

  // Format time in local timezone
  const date = new Date(prediction.timestamp)
  const time = date.toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  })
  
  // Show relative time for recent predictions
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const relativeTime = diffMins < 1 ? 'just now' 
    : diffMins < 60 ? `${diffMins}m ago`
    : diffMins < 1440 ? `${Math.floor(diffMins / 60)}h ago`
    : time

  return (
    <div className="p-3 hover:bg-terminal-border/20 transition-colors">
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          {validated ? (
            isCorrect ? (
              <CheckCircle className="w-4 h-4 text-bull" />
            ) : (
              <XCircle className="w-4 h-4 text-bear" />
            )
          ) : (
            <Clock className="w-4 h-4 text-amber-400 animate-pulse" />
          )}
          <span className="font-mono font-medium">{prediction.asset}</span>
          <span className="text-xs text-terminal-muted" title={date.toLocaleString()}>
            {relativeTime}
          </span>
          <span className="text-xs px-1.5 py-0.5 rounded bg-terminal-border text-terminal-muted">
            {prediction.horizon_minutes}m
          </span>
        </div>
        <div className={clsx(
          'text-xs px-2 py-0.5 rounded capitalize',
          prediction.confidence === 'high' && 'bg-bull/20 text-bull',
          prediction.confidence === 'medium' && 'bg-amber-400/20 text-amber-400',
          prediction.confidence === 'low' && 'bg-bear/20 text-bear'
        )}>
          {prediction.confidence}
        </div>
      </div>

      <div className="flex items-center justify-between text-sm">
        <div className="flex items-center gap-3">
          {/* Entry Price */}
          <span className="text-terminal-muted">
            ${prediction.entry_price.toFixed(2)}
          </span>
          
          {/* Arrow */}
          <span className="text-terminal-muted">→</span>
          
          {/* Exit Price or Waiting */}
          {validated && prediction.exit_price !== null ? (
            <span className={clsx(
              'font-mono',
              prediction.actual_move && prediction.actual_move > 0 ? 'text-bull' : 'text-bear'
            )}>
              ${prediction.exit_price.toFixed(2)}
            </span>
          ) : (
            <span className="text-terminal-muted italic">waiting...</span>
          )}
        </div>

        <div className="flex items-center gap-4">
          {/* Prediction */}
          <div className="flex items-center gap-1">
            <span className="text-xs text-terminal-muted">Pred:</span>
            {predictedUp ? (
              <TrendingUp className="w-3.5 h-3.5 text-bull" />
            ) : (
              <TrendingDown className="w-3.5 h-3.5 text-bear" />
            )}
            <span className={clsx(
              'font-mono text-xs',
              predictedUp ? 'text-bull' : 'text-bear'
            )}>
              {(prediction.p_up * 100).toFixed(0)}%
            </span>
          </div>

          {/* Actual */}
          {validated && prediction.actual_move !== null && (
            <div className="flex items-center gap-1">
              <span className="text-xs text-terminal-muted">Actual:</span>
              <span className={clsx(
                'font-mono text-xs',
                actualUp ? 'text-bull' : 'text-bear'
              )}>
                {(prediction.actual_move * 100).toFixed(3)}%
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

