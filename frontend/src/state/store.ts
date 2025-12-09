import { create } from 'zustand'
import { api } from '../utils/api'
import type { 
  MarketData, 
  Prediction, 
  Explanation, 
  TimeInterval,
  ChartOverlay 
} from '../types'

interface Store {
  // State
  selectedAsset: string
  selectedInterval: TimeInterval
  marketData: MarketData | null
  prediction: Prediction | null
  explanation: Explanation | null
  isLoading: boolean
  error: string | null
  activeOverlays: ChartOverlay[]
  
  // Actions
  setSelectedAsset: (asset: string) => void
  setSelectedInterval: (interval: TimeInterval) => void
  toggleOverlay: (overlay: ChartOverlay) => void
  fetchMarketData: () => Promise<void>
  fetchPrediction: () => Promise<void>
  fetchExplanation: () => Promise<void>
}

export const useStore = create<Store>((set, get) => ({
  // Initial state
  selectedAsset: 'BTC',
  selectedInterval: '1h',
  marketData: null,
  prediction: null,
  explanation: null,
  isLoading: false,
  error: null,
  activeOverlays: ['prediction'],
  
  // Actions
  setSelectedAsset: (asset) => {
    set({ selectedAsset: asset, marketData: null, prediction: null })
    get().fetchMarketData()
    get().fetchPrediction()
  },
  
  setSelectedInterval: (interval) => {
    set({ selectedInterval: interval, marketData: null })
    get().fetchMarketData()
  },
  
  toggleOverlay: (overlay) => {
    const { activeOverlays } = get()
    if (activeOverlays.includes(overlay)) {
      set({ activeOverlays: activeOverlays.filter(o => o !== overlay) })
    } else {
      set({ activeOverlays: [...activeOverlays, overlay] })
    }
  },
  
  fetchMarketData: async () => {
    const { selectedAsset, selectedInterval } = get()
    set({ isLoading: true, error: null })
    
    try {
      const data = await api.getMarketData(selectedAsset, selectedInterval)
      set({ marketData: data, isLoading: false })
    } catch (error) {
      set({ error: 'Failed to fetch market data', isLoading: false })
      console.error('Market data fetch error:', error)
    }
  },
  
  fetchPrediction: async () => {
    const { selectedAsset } = get()
    
    try {
      const prediction = await api.getPrediction(selectedAsset, 4)
      set({ prediction })
    } catch (error) {
      console.error('Prediction fetch error:', error)
    }
  },
  
  fetchExplanation: async () => {
    const { selectedAsset } = get()
    
    try {
      const explanation = await api.getExplanation(selectedAsset)
      set({ explanation })
    } catch (error) {
      console.error('Explanation fetch error:', error)
    }
  },
}))

