import { useMemo } from 'react'
import type { ConePoint } from '../types'

interface PredictionConeProps {
  cone: ConePoint[]
  width: number
  height: number
  getTimeToCoordinate: (timestamp: string) => number | null
  getPriceToCoordinate: (price: number) => number | null
}

export function PredictionCone({
  cone,
  width,
  height,
  getTimeToCoordinate,
  getPriceToCoordinate,
}: PredictionConeProps) {
  // Convert cone data to SVG paths
  const paths = useMemo(() => {
    if (!cone || cone.length < 2) return null
    
    const points: {
      x: number
      mid: number
      upper1: number
      lower1: number
      upper2: number
      lower2: number
    }[] = []
    
    for (const point of cone) {
      const x = getTimeToCoordinate(point.timestamp)
      const mid = getPriceToCoordinate(point.mid)
      const upper1 = getPriceToCoordinate(point.upper_1sigma)
      const lower1 = getPriceToCoordinate(point.lower_1sigma)
      const upper2 = getPriceToCoordinate(point.upper_2sigma)
      const lower2 = getPriceToCoordinate(point.lower_2sigma)
      
      if (x !== null && mid !== null && upper1 !== null && 
          lower1 !== null && upper2 !== null && lower2 !== null) {
        points.push({ x, mid, upper1, lower1, upper2, lower2 })
      }
    }
    
    if (points.length < 2) return null
    
    // Create path strings
    // 2-sigma band (outer)
    const outer2SigmaPath = `
      M ${points[0].x} ${points[0].upper2}
      ${points.slice(1).map(p => `L ${p.x} ${p.upper2}`).join(' ')}
      ${points.slice().reverse().map(p => `L ${p.x} ${p.lower2}`).join(' ')}
      Z
    `
    
    // 1-sigma band (inner)
    const outer1SigmaPath = `
      M ${points[0].x} ${points[0].upper1}
      ${points.slice(1).map(p => `L ${p.x} ${p.upper1}`).join(' ')}
      ${points.slice().reverse().map(p => `L ${p.x} ${p.lower1}`).join(' ')}
      Z
    `
    
    // Mid line
    const midLinePath = `
      M ${points[0].x} ${points[0].mid}
      ${points.slice(1).map(p => `L ${p.x} ${p.mid}`).join(' ')}
    `
    
    // Upper/lower 1-sigma lines
    const upper1Line = `
      M ${points[0].x} ${points[0].upper1}
      ${points.slice(1).map(p => `L ${p.x} ${p.upper1}`).join(' ')}
    `
    
    const lower1Line = `
      M ${points[0].x} ${points[0].lower1}
      ${points.slice(1).map(p => `L ${p.x} ${p.lower1}`).join(' ')}
    `
    
    return {
      outer2SigmaPath,
      outer1SigmaPath,
      midLinePath,
      upper1Line,
      lower1Line,
    }
  }, [cone, getTimeToCoordinate, getPriceToCoordinate])
  
  if (!paths) return null
  
  return (
    <svg
      className="prediction-cone absolute top-0 left-0"
      width={width}
      height={height}
      style={{ pointerEvents: 'none' }}
    >
      <defs>
        {/* Gradient for 2-sigma band */}
        <linearGradient id="cone2SigmaGradient" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.05" />
          <stop offset="50%" stopColor="#3b82f6" stopOpacity="0.1" />
          <stop offset="100%" stopColor="#3b82f6" stopOpacity="0.05" />
        </linearGradient>
        
        {/* Gradient for 1-sigma band */}
        <linearGradient id="cone1SigmaGradient" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.1" />
          <stop offset="50%" stopColor="#3b82f6" stopOpacity="0.2" />
          <stop offset="100%" stopColor="#3b82f6" stopOpacity="0.1" />
        </linearGradient>
        
        {/* Glow filter for mid line */}
        <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="2" result="coloredBlur" />
          <feMerge>
            <feMergeNode in="coloredBlur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>
      
      {/* 2-sigma band (outer, lighter) */}
      <path
        d={paths.outer2SigmaPath}
        fill="url(#cone2SigmaGradient)"
        stroke="none"
      />
      
      {/* 1-sigma band (inner, darker) */}
      <path
        d={paths.outer1SigmaPath}
        fill="url(#cone1SigmaGradient)"
        stroke="none"
      />
      
      {/* 1-sigma boundary lines */}
      <path
        d={paths.upper1Line}
        fill="none"
        stroke="#3b82f6"
        strokeWidth="1"
        strokeDasharray="4 2"
        opacity="0.6"
      />
      <path
        d={paths.lower1Line}
        fill="none"
        stroke="#3b82f6"
        strokeWidth="1"
        strokeDasharray="4 2"
        opacity="0.6"
      />
      
      {/* Mid line (expected path) */}
      <path
        d={paths.midLinePath}
        fill="none"
        stroke="#60a5fa"
        strokeWidth="2"
        filter="url(#glow)"
      />
    </svg>
  )
}



