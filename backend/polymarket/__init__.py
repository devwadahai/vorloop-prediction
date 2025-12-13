"""
Polymarket Probability Research & Paper Trading Simulator

A research-grade probability + execution simulator for Polymarket that answers:
- Can we consistently estimate probabilities better than the market?
- Does that edge survive realistic execution?

Trading is NOT the goal; measurement, calibration, and attribution are.

North-Star Metrics (ranked):
1. Mean Edge = E[final_outcome - entry_price]
2. Brier Score (probability calibration)
3. Edge Preservation Ratio = realized_edge / theoretical_edge
4. Execution Drag (bps lost to slippage / partial fills)
5. Secondary: Realized PnL
"""

from .services import (
    MarketDataService,
    PaperExchangeService,
    ProbabilityModelService,
    StrategyEngine,
    EvaluationService,
)
from .api import router

__all__ = [
    'MarketDataService',
    'PaperExchangeService',
    'ProbabilityModelService',
    'StrategyEngine',
    'EvaluationService',
    'router',
]

