import { useEffect } from 'react'
import { motion } from 'framer-motion'
import { TrendingUp, TrendingDown, Activity, Zap, Info, RefreshCw } from 'lucide-react'
import { useStore } from '../state/store'
import { formatPercent, formatSignedPercent, formatTime } from '../utils/format'
import clsx from 'clsx'

export function PredictionPanel() {
  const { prediction, explanation, fetchExplanation, isLoading } = useStore()
  
  useEffect(() => {
    if (prediction) {
      fetchExplanation()
    }
  }, [prediction, fetchExplanation])
  
  if (!prediction) {
    return (
      <div className="h-full p-4 flex items-center justify-center">
        <div className="text-center text-terminal-muted">
          <RefreshCw className="w-8 h-8 mx-auto mb-2 animate-spin" />
          <p>Loading predictions...</p>
        </div>
      </div>
    )
  }
  
  const isBullish = prediction.p_up > 0.5
  const dominantProb = Math.max(prediction.p_up, prediction.p_down)
  
  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div className="p-4 border-b border-terminal-border">
        <div className="flex items-center justify-between mb-2">
          <h2 className="font-display font-semibold">Prediction</h2>
          <div className="flex gap-1">
            {[1, 3, 5, 10].map((mins) => (
              <button
                key={mins}
                onClick={() => useStore.getState().setHorizonMinutes(mins)}
                className={`px-2 py-0.5 text-xs rounded ${
                  prediction.horizon_minutes === mins
                    ? 'bg-accent text-white'
                    : 'bg-terminal-bg text-terminal-muted hover:text-white'
                }`}
              >
                {mins}m
              </button>
            ))}
          </div>
        </div>
        <p className="text-xs text-terminal-muted">
          Updated {formatTime(prediction.timestamp)}
        </p>
      </div>
      
      {/* Main Prediction */}
      <div className="p-4 space-y-4">
        {/* Direction Indicator */}
        <motion.div
          initial={{ scale: 0.95, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          className={clsx(
            'p-4 rounded-xl border',
            isBullish 
              ? 'bg-bull/10 border-bull/30' 
              : 'bg-bear/10 border-bear/30'
          )}
        >
          <div className="flex items-center gap-3 mb-3">
            {isBullish ? (
              <TrendingUp className="w-8 h-8 text-bull" />
            ) : (
              <TrendingDown className="w-8 h-8 text-bear" />
            )}
            <div>
              <div className={clsx(
                'text-3xl font-bold font-mono',
                isBullish ? 'text-bull' : 'text-bear'
              )}>
                {formatPercent(dominantProb, 0)}
              </div>
              <div className="text-sm text-terminal-muted">
                probability {isBullish ? 'up' : 'down'}
              </div>
            </div>
          </div>
          
          {/* Probability Bar */}
          <div className="h-2 bg-terminal-bg rounded-full overflow-hidden">
            <motion.div
              initial={{ width: '50%' }}
              animate={{ width: formatPercent(prediction.p_up, 0) }}
              transition={{ duration: 0.5, ease: 'easeOut' }}
              className="h-full bg-gradient-to-r from-bear via-terminal-muted to-bull"
              style={{ 
                marginLeft: `${(1 - prediction.p_up) * 100}%`,
                width: `${prediction.p_up * 100}%` 
              }}
            />
          </div>
          <div className="flex justify-between mt-1 text-xs text-terminal-muted">
            <span>↓ {formatPercent(prediction.p_down, 0)}</span>
            <span>↑ {formatPercent(prediction.p_up, 0)}</span>
          </div>
        </motion.div>
        
        {/* Metrics Grid */}
        <div className="grid grid-cols-2 gap-3">
          <MetricCard
            icon={<Activity className="w-4 h-4" />}
            label="Expected Move"
            value={formatSignedPercent(prediction.expected_move)}
            valueClass={prediction.expected_move >= 0 ? 'text-bull' : 'text-bear'}
          />
          <MetricCard
            icon={<Zap className="w-4 h-4" />}
            label="Volatility"
            value={formatPercent(prediction.volatility)}
          />
        </div>
        
        {/* Regime & Confidence */}
        <div className="flex gap-3">
          <div className="flex-1 p-3 rounded-lg bg-terminal-bg border border-terminal-border">
            <div className="text-xs text-terminal-muted mb-1">Regime</div>
            <div className={clsx(
              'font-mono font-medium capitalize',
              prediction.regime.includes('up') && 'text-bull',
              prediction.regime.includes('down') && 'text-bear',
              prediction.regime === 'panic' && 'text-bear',
              prediction.regime === 'high-vol' && 'text-amber-400'
            )}>
              {prediction.regime.replace('-', ' ')}
            </div>
          </div>
          <div className="flex-1 p-3 rounded-lg bg-terminal-bg border border-terminal-border">
            <div className="text-xs text-terminal-muted mb-1">Confidence</div>
            <div className={clsx(
              'font-mono font-medium capitalize',
              prediction.confidence === 'high' && 'text-bull',
              prediction.confidence === 'medium' && 'text-amber-400',
              prediction.confidence === 'low' && 'text-bear'
            )}>
              {prediction.confidence}
            </div>
          </div>
        </div>
      </div>
      
      {/* Explanation Section */}
      {explanation && (
        <div className="flex-1 overflow-auto border-t border-terminal-border">
          <div className="p-4">
            <div className="flex items-center gap-2 mb-3">
              <Info className="w-4 h-4 text-accent" />
              <h3 className="font-display font-medium">Why This Prediction?</h3>
            </div>
            
            <p className="text-sm text-terminal-muted mb-4">
              {explanation.prediction_summary}
            </p>
            
            {/* Bullish Factors */}
            {explanation.top_bullish_factors.length > 0 && (
              <div className="mb-4">
                <h4 className="text-xs font-medium text-bull mb-2">Bullish Signals</h4>
                <div className="space-y-2">
                  {explanation.top_bullish_factors.slice(0, 3).map((factor, i) => (
                    <FactorRow key={i} factor={factor} />
                  ))}
                </div>
              </div>
            )}
            
            {/* Bearish Factors */}
            {explanation.top_bearish_factors.length > 0 && (
              <div className="mb-4">
                <h4 className="text-xs font-medium text-bear mb-2">Bearish Signals</h4>
                <div className="space-y-2">
                  {explanation.top_bearish_factors.slice(0, 3).map((factor, i) => (
                    <FactorRow key={i} factor={factor} />
                  ))}
                </div>
              </div>
            )}
            
            {/* Regime Explanation */}
            <div className="p-3 rounded-lg bg-terminal-bg/50 border border-terminal-border">
              <div className="text-xs text-terminal-muted mb-1">Regime Analysis</div>
              <p className="text-sm">{explanation.regime_explanation}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

interface MetricCardProps {
  icon: React.ReactNode
  label: string
  value: string
  valueClass?: string
}

function MetricCard({ icon, label, value, valueClass }: MetricCardProps) {
  return (
    <div className="p-3 rounded-lg bg-terminal-bg border border-terminal-border">
      <div className="flex items-center gap-2 text-terminal-muted mb-1">
        {icon}
        <span className="text-xs">{label}</span>
      </div>
      <div className={clsx('font-mono font-semibold', valueClass)}>
        {value}
      </div>
    </div>
  )
}

interface FactorRowProps {
  factor: {
    feature: string
    contribution: number
    direction: 'bullish' | 'bearish' | 'neutral'
  }
}

function FactorRow({ factor }: FactorRowProps) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-terminal-muted">{factor.feature}</span>
      <span className={clsx(
        'font-mono',
        factor.direction === 'bullish' && 'text-bull',
        factor.direction === 'bearish' && 'text-bear'
      )}>
        {factor.contribution > 0 ? '+' : ''}{factor.contribution.toFixed(1)}%
      </span>
    </div>
  )
}

