import { useEffect } from 'react'
import { PriceChart } from './components/PriceChart'
import { PredictionPanel } from './panels/PredictionPanel'
import { MarketStructurePanel } from './panels/MarketStructurePanel'
import { Header } from './components/Header'
import { useStore } from './state/store'

function App() {
  const { fetchMarketData, fetchPrediction, selectedAsset } = useStore()

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
        
        {/* Side Panel - Predictions */}
        <div className="w-80 border-l border-terminal-border">
          <PredictionPanel />
        </div>
      </main>
    </div>
  )
}

export default App

