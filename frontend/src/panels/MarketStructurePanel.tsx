import { useMemo } from 'react'
import { useStore } from '../state/store'
import { formatCompact, formatFunding, formatPercent, getValueColor } from '../utils/format'
import clsx from 'clsx'

export function MarketStructurePanel() {
  const { marketData } = useStore()
  
  // Get latest market structure data
  const latest = useMemo(() => {
    if (!marketData?.market_structure?.length) return null
    return marketData.market_structure[marketData.market_structure.length - 1]
  }, [marketData])
  
  // Calculate averages for context
  const averages = useMemo(() => {
    if (!marketData?.market_structure?.length) return null
    
    const data = marketData.market_structure.slice(-24) // Last 24 periods
    
    const avgFunding = data.reduce((sum, d) => sum + (d.funding_rate ?? 0), 0) / data.length
    const avgOIChange = data.reduce((sum, d) => sum + (d.oi_change_pct ?? 0), 0) / data.length
    const totalLongLiq = data.reduce((sum, d) => sum + (d.long_liquidations ?? 0), 0)
    const totalShortLiq = data.reduce((sum, d) => sum + (d.short_liquidations ?? 0), 0)
    
    return { avgFunding, avgOIChange, totalLongLiq, totalShortLiq }
  }, [marketData])
  
  if (!latest || !averages) {
    return (
      <div className="h-full bg-terminal-surface rounded-xl border border-terminal-border p-4">
        <div className="h-full flex items-center justify-center text-terminal-muted">
          Loading market structure...
        </div>
      </div>
    )
  }
  
  return (
    <div className="h-full min-h-[140px] bg-terminal-surface rounded-xl border border-terminal-border overflow-hidden">
      <div className="h-full grid grid-cols-4 divide-x divide-terminal-border">
        {/* Funding Rate */}
        <MetricSection
          title="Funding Rate"
          mainValue={formatFunding(latest.funding_rate ?? 0)}
          mainValueClass={getValueColor(latest.funding_rate ?? 0)}
          subLabel="24h Avg"
          subValue={formatFunding(averages.avgFunding)}
          chart={
            <MiniBarChart
              data={marketData!.market_structure.slice(-24).map(d => d.funding_rate ?? 0)}
              color={latest.funding_rate && latest.funding_rate > 0 ? '#00d26a' : '#ff4757'}
            />
          }
        />
        
        {/* Open Interest */}
        <MetricSection
          title="Open Interest"
          mainValue={`$${formatCompact(latest.open_interest ?? 0)}`}
          subLabel="Change"
          subValue={formatPercent(latest.oi_change_pct ?? 0)}
          subValueClass={getValueColor(latest.oi_change_pct ?? 0)}
          chart={
            <MiniAreaChart
              data={marketData!.market_structure.slice(-24).map(d => d.open_interest ?? 0)}
              color="#3b82f6"
            />
          }
        />
        
        {/* Liquidations */}
        <MetricSection
          title="Liquidations (24h)"
          mainValue={`$${formatCompact(averages.totalLongLiq + averages.totalShortLiq)}`}
          chart={
            <LiquidationChart
              longLiq={averages.totalLongLiq}
              shortLiq={averages.totalShortLiq}
            />
          }
        />
        
        {/* CVD */}
        <MetricSection
          title="Volume Delta"
          mainValue={formatCompact(latest.cvd ?? 0)}
          mainValueClass={getValueColor(latest.cvd ?? 0)}
          chart={
            <MiniBarChart
              data={marketData!.market_structure.slice(-24).map(d => d.cvd ?? 0)}
              color={latest.cvd && latest.cvd > 0 ? '#00d26a' : '#ff4757'}
              showZeroLine
            />
          }
        />
      </div>
    </div>
  )
}

interface MetricSectionProps {
  title: string
  mainValue: string
  mainValueClass?: string
  subLabel?: string
  subValue?: string
  subValueClass?: string
  chart?: React.ReactNode
}

function MetricSection({
  title,
  mainValue,
  mainValueClass,
  subLabel,
  subValue,
  subValueClass,
  chart,
}: MetricSectionProps) {
  return (
    <div className="p-3 flex flex-col">
      <div className="text-xs text-terminal-muted mb-1">{title}</div>
      <div className={clsx('font-mono font-semibold text-lg', mainValueClass)}>
        {mainValue}
      </div>
      {subLabel && subValue && (
        <div className="text-xs text-terminal-muted mt-0.5">
          {subLabel}: <span className={subValueClass}>{subValue}</span>
        </div>
      )}
      {chart && <div className="mt-2 h-[60px]">{chart}</div>}
    </div>
  )
}

interface MiniBarChartProps {
  data: number[]
  color: string
  showZeroLine?: boolean
}

function MiniBarChart({ data, color, showZeroLine }: MiniBarChartProps) {
  const max = Math.max(...data.map(Math.abs), 1)
  const barCount = data.length || 1
  
  return (
    <div className="w-full h-full relative" style={{ minHeight: '60px' }}>
      {showZeroLine && (
        <div className="absolute left-0 right-0 top-1/2 h-px bg-terminal-border/50 z-0" />
      )}
      <div className="absolute inset-0 flex items-center gap-px">
        {data.map((value, i) => {
          const heightPct = max > 0 ? (Math.abs(value) / max) * 100 : 0
          const isPositive = value >= 0
          const barHeight = Math.max(heightPct * 0.45, 4)
          
          return (
            <div
              key={i}
              className="flex-1 h-full relative"
              style={{ minWidth: '3px' }}
            >
              {/* Positive bar (above center) */}
              {isPositive && (
                <div 
                  className="absolute left-0 right-0 rounded-t-sm"
                  style={{
                    bottom: '50%',
                    height: `${barHeight}%`,
                    backgroundColor: '#00d26a',
                    opacity: 0.6 + (i / barCount) * 0.4,
                  }}
                />
              )}
              {/* Negative bar (below center) */}
              {!isPositive && (
                <div 
                  className="absolute left-0 right-0 rounded-b-sm"
                  style={{
                    top: '50%',
                    height: `${barHeight}%`,
                    backgroundColor: '#ff4757',
                    opacity: 0.6 + (i / barCount) * 0.4,
                  }}
                />
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

interface MiniAreaChartProps {
  data: number[]
  color: string
}

function MiniAreaChart({ data, color }: MiniAreaChartProps) {
  const min = Math.min(...data)
  const max = Math.max(...data)
  const range = max - min || 1
  
  const points = data.map((value, i) => {
    const x = (i / (data.length - 1)) * 100
    const y = 100 - ((value - min) / range) * 100
    return `${x},${y}`
  })
  
  const pathD = `M 0,100 L ${points.join(' L ')} L 100,100 Z`
  const lineD = `M ${points.join(' L ')}`
  
  return (
    <div className="w-full h-full" style={{ minHeight: '60px' }}>
      <svg className="w-full h-full" viewBox="0 0 100 100" preserveAspectRatio="none">
        <defs>
          <linearGradient id={`gradient-${color}`} x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor={color} stopOpacity="0.3" />
            <stop offset="100%" stopColor={color} stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d={pathD} fill={`url(#gradient-${color})`} />
        <path d={lineD} fill="none" stroke={color} strokeWidth="2" vectorEffect="non-scaling-stroke" />
      </svg>
    </div>
  )
}

interface LiquidationChartProps {
  longLiq: number
  shortLiq: number
}

function LiquidationChart({ longLiq, shortLiq }: LiquidationChartProps) {
  const total = longLiq + shortLiq
  const longPct = total > 0 ? (longLiq / total) * 100 : 50
  const shortPct = total > 0 ? (shortLiq / total) * 100 : 50
  
  return (
    <div className="w-full flex flex-col justify-center gap-2" style={{ minHeight: '60px' }}>
      <div className="flex items-center gap-2">
        <span className="text-xs text-bear w-12">Longs</span>
        <div className="flex-1 h-3 bg-terminal-bg rounded-full overflow-hidden">
          <div
            className="h-full bg-bear rounded-full"
            style={{ width: `${longPct}%` }}
          />
        </div>
        <span className="text-xs text-terminal-muted w-10 text-right">
          {longPct.toFixed(0)}%
        </span>
      </div>
      <div className="flex items-center gap-2">
        <span className="text-xs text-bull w-12">Shorts</span>
        <div className="flex-1 h-3 bg-terminal-bg rounded-full overflow-hidden">
          <div
            className="h-full bg-bull rounded-full"
            style={{ width: `${shortPct}%` }}
          />
        </div>
        <span className="text-xs text-terminal-muted w-10 text-right">
          {shortPct.toFixed(0)}%
        </span>
      </div>
    </div>
  )
}

