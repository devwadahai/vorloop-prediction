import { useEffect, useState } from 'react'
import { PriceChart } from './components/PriceChart'
import { PredictionPanel } from './panels/PredictionPanel'
import { MarketStructurePanel } from './panels/MarketStructurePanel'
import { PredictionLogPanel } from './panels/PredictionLogPanel'
import { Header } from './components/Header'
import { useStore } from './state/store'
import { BarChart3, Brain } from 'lucide-react'
import clsx from 'clsx'

function App() {
  const { fetchMarketData, fetchPrediction, selectedAsset } = useStore()
  const [sideTab, setSideTab] = useState<'prediction' | 'log'>('prediction')

  useEffect(() => {
    // Initial data fetch
    fetchMarketData()
    fetchPrediction()

    // Set up polling
    const marketInterval = setInterval(fetchMarketData, 5000)
    const predictionInterval = setInterval(fetchPrediction, 60000)

    return () => {
      clearInterval(marketInterval)
      clearInterval(predictionInterval)
    }
  }, [selectedAsset, fetchMarketData, fetchPrediction])

  return (
    <div className="h-screen flex flex-col bg-terminal-bg">
      <Header />
      
      <main className="flex-1 flex overflow-hidden">
        {/* Main Chart Area */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* Price Chart */}
          <div className="flex-1 min-h-0 p-4">
            <div className="h-full bg-terminal-surface rounded-xl border border-terminal-border overflow-hidden">
              <PriceChart />
            </div>
          </div>
          
          {/* Market Structure Panels */}
          <div className="h-48 p-4 pt-0">
            <MarketStructurePanel />
          </div>
        </div>
        
        {/* Side Panel */}
        <div className="w-96 border-l border-terminal-border flex flex-col">
          {/* Tab Switcher */}
          <div className="flex border-b border-terminal-border bg-terminal-surface/50">
            <button
              onClick={() => setSideTab('prediction')}
              className={clsx(
                'flex-1 flex items-center justify-center gap-2 px-4 py-3 text-sm font-medium transition-colors',
                sideTab === 'prediction'
                  ? 'text-white border-b-2 border-accent bg-terminal-surface'
                  : 'text-terminal-muted hover:text-white'
              )}
            >
              <Brain className="w-4 h-4" />
              Prediction
            </button>
            <button
              onClick={() => setSideTab('log')}
              className={clsx(
                'flex-1 flex items-center justify-center gap-2 px-4 py-3 text-sm font-medium transition-colors',
                sideTab === 'log'
                  ? 'text-white border-b-2 border-accent bg-terminal-surface'
                  : 'text-terminal-muted hover:text-white'
              )}
            >
              <BarChart3 className="w-4 h-4" />
              Accuracy Log
            </button>
          </div>
          
          {/* Tab Content */}
          <div className="flex-1 overflow-hidden">
            {sideTab === 'prediction' ? (
              <PredictionPanel />
            ) : (
              <PredictionLogPanel />
            )}
          </div>
        </div>
      </main>
    </div>
  )
}

export default App

