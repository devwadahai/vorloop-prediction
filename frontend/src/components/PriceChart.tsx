import { useEffect, useRef, useState } from 'react'
import { createChart, IChartApi, ISeriesApi, CandlestickData, Time } from 'lightweight-charts'
import { useStore } from '../state/store'
import { PredictionCone } from './PredictionCone'

export function PriceChart() {
  const chartContainerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const volumeSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null)
  
  const { marketData, prediction, activeOverlays } = useStore()
  const [chartDimensions, setChartDimensions] = useState({ width: 0, height: 0 })
  
  // Initialize chart
  useEffect(() => {
    if (!chartContainerRef.current) return
    
    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { color: 'transparent' },
        textColor: '#8b949e',
        fontSize: 12,
        fontFamily: 'JetBrains Mono, monospace',
      },
      grid: {
        vertLines: { color: 'rgba(33, 38, 45, 0.5)' },
        horzLines: { color: 'rgba(33, 38, 45, 0.5)' },
      },
      crosshair: {
        mode: 1,
        vertLine: {
          color: '#7c3aed',
          width: 1,
          style: 2,
          labelBackgroundColor: '#7c3aed',
        },
        horzLine: {
          color: '#7c3aed',
          width: 1,
          style: 2,
          labelBackgroundColor: '#7c3aed',
        },
      },
      rightPriceScale: {
        borderColor: '#21262d',
        scaleMargins: {
          top: 0.1,
          bottom: 0.2,
        },
      },
      timeScale: {
        borderColor: '#21262d',
        timeVisible: true,
        secondsVisible: false,
      },
      handleScroll: {
        mouseWheel: true,
        pressedMouseMove: true,
        horzTouchDrag: true,
        vertTouchDrag: false,
      },
      handleScale: {
        mouseWheel: true,
        pinch: true,
        axisPressedMouseMove: true,
      },
    })
    
    // Add candlestick series
    const candleSeries = chart.addCandlestickSeries({
      upColor: '#00d26a',
      downColor: '#ff4757',
      borderUpColor: '#00d26a',
      borderDownColor: '#ff4757',
      wickUpColor: '#00d26a',
      wickDownColor: '#ff4757',
    })
    
    // Add volume series
    const volumeSeries = chart.addHistogramSeries({
      color: '#3b82f6',
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume',
    })
    
    chart.priceScale('volume').applyOptions({
      scaleMargins: {
        top: 0.85,
        bottom: 0,
      },
    })
    
    chartRef.current = chart
    candleSeriesRef.current = candleSeries
    volumeSeriesRef.current = volumeSeries
    
    // Handle resize
    const handleResize = () => {
      if (chartContainerRef.current) {
        const { width, height } = chartContainerRef.current.getBoundingClientRect()
        chart.applyOptions({ width, height })
        setChartDimensions({ width, height })
      }
    }
    
    handleResize()
    window.addEventListener('resize', handleResize)
    
    return () => {
      window.removeEventListener('resize', handleResize)
      chart.remove()
    }
  }, [])
  
  // Update data
  useEffect(() => {
    if (!marketData?.candles || !candleSeriesRef.current || !volumeSeriesRef.current) return
    
    const candleData: CandlestickData[] = marketData.candles.map((candle) => ({
      time: (new Date(candle.timestamp).getTime() / 1000) as Time,
      open: candle.open,
      high: candle.high,
      low: candle.low,
      close: candle.close,
    }))
    
    const volumeData = marketData.candles.map((candle) => ({
      time: (new Date(candle.timestamp).getTime() / 1000) as Time,
      value: candle.volume,
      color: candle.close >= candle.open 
        ? 'rgba(0, 210, 106, 0.3)' 
        : 'rgba(255, 71, 87, 0.3)',
    }))
    
    candleSeriesRef.current.setData(candleData)
    volumeSeriesRef.current.setData(volumeData)
    
    // Fit content with some padding
    if (chartRef.current) {
      chartRef.current.timeScale().fitContent()
    }
  }, [marketData])
  
  // Get chart coordinates for prediction cone
  const getTimeToCoordinate = (timestamp: string): number | null => {
    if (!chartRef.current) return null
    const time = new Date(timestamp).getTime() / 1000
    return chartRef.current.timeScale().timeToCoordinate(time as Time)
  }
  
  const getPriceToCoordinate = (price: number): number | null => {
    if (!candleSeriesRef.current) return null
    return candleSeriesRef.current.priceToCoordinate(price)
  }
  
  const showPredictionCone = activeOverlays.includes('prediction') && prediction?.cone
  
  return (
    <div className="relative w-full h-full chart-container">
      <div ref={chartContainerRef} className="w-full h-full" />
      
      {/* Prediction Cone Overlay */}
      {showPredictionCone && prediction && (
        <PredictionCone
          cone={prediction.cone}
          width={chartDimensions.width}
          height={chartDimensions.height}
          getTimeToCoordinate={getTimeToCoordinate}
          getPriceToCoordinate={getPriceToCoordinate}
        />
      )}
      
      {/* Chart Legend */}
      <div className="absolute top-4 left-4 flex items-center gap-4 text-xs">
        <div className="flex items-center gap-2 px-2 py-1 rounded bg-terminal-bg/80 backdrop-blur-sm">
          <div className="w-3 h-3 rounded-sm bg-bull" />
          <span className="text-terminal-muted">Bullish</span>
        </div>
        <div className="flex items-center gap-2 px-2 py-1 rounded bg-terminal-bg/80 backdrop-blur-sm">
          <div className="w-3 h-3 rounded-sm bg-bear" />
          <span className="text-terminal-muted">Bearish</span>
        </div>
        {showPredictionCone && (
          <div className="flex items-center gap-2 px-2 py-1 rounded bg-terminal-bg/80 backdrop-blur-sm">
            <div className="w-3 h-3 rounded-sm bg-cone-stroke" />
            <span className="text-terminal-muted">Prediction Cone</span>
          </div>
        )}
      </div>
    </div>
  )
}

