"""
Probability Estimation Models
"""
from datetime import datetime
from typing import List, Optional
from dataclasses import dataclass, field
from enum import Enum


class RiskFlag(str, Enum):
    """Risk flags for probability estimates."""
    LOW_DEPTH = "LOW_DEPTH"              # Insufficient liquidity
    WIDE_SPREAD = "WIDE_SPREAD"          # Spread too wide
    LONG_RESOLUTION = "LONG_RESOLUTION"  # Too far from resolution
    HIGH_VOLATILITY = "HIGH_VOLATILITY"  # Price moving rapidly
    LOW_VOLUME = "LOW_VOLUME"            # Low trading activity
    DISPUTE_RISK = "DISPUTE_RISK"        # Ambiguous resolution criteria
    IMBALANCED_BOOK = "IMBALANCED_BOOK"  # Heavily skewed order book
    NEAR_CERTAINTY = "NEAR_CERTAINTY"    # Price near 0 or 1 (low edge potential)


@dataclass
class ProbabilityEstimate:
    """
    Probability estimate for a market.
    This is the core output of the probability model.
    """
    market_id: str
    token_id: str
    
    # Probabilities
    fair_prob: float          # Our estimated fair probability
    market_prob: float        # Market implied probability (mid price)
    
    # Edge calculation
    edge: float               # fair_prob - market_prob (or adjusted)
    edge_pct: float           # Edge as percentage
    
    # Expected value
    expected_value: float     # EV of taking position
    kelly_fraction: float     # Optimal bet size (Kelly criterion)
    
    # Confidence
    confidence: float         # 0-1 confidence in our estimate
    
    # Risk assessment
    risk_flags: List[RiskFlag] = field(default_factory=list)
    risk_score: float = 0.0   # 0-1 overall risk score
    
    # Metadata
    timestamp: datetime = field(default_factory=datetime.utcnow)
    model_version: str = "v1"
    
    # Inputs used (for debugging/analysis)
    inputs: dict = field(default_factory=dict)
    
    def __post_init__(self):
        # Convert string risk flags to enums
        self.risk_flags = [
            RiskFlag(f) if isinstance(f, str) else f 
            for f in self.risk_flags
        ]
    
    @property
    def is_tradeable(self) -> bool:
        """Check if this estimate suggests a tradeable opportunity."""
        return (
            abs(self.edge) >= 0.015 and  # At least 1.5% edge
            self.confidence >= 0.5 and    # Moderate confidence
            self.risk_score < 0.7 and     # Not too risky
            RiskFlag.NEAR_CERTAINTY not in self.risk_flags
        )
    
    @property
    def suggested_side(self) -> Optional[str]:
        """Suggest which side to trade."""
        if not self.is_tradeable:
            return None
        return "BUY" if self.edge > 0 else "SELL"
    
    @property
    def has_critical_risk(self) -> bool:
        """Check for critical risk flags."""
        critical = {RiskFlag.DISPUTE_RISK, RiskFlag.LOW_DEPTH}
        return bool(critical & set(self.risk_flags))
    
    def to_dict(self) -> dict:
        return {
            'market_id': self.market_id,
            'token_id': self.token_id,
            'fair_prob': round(self.fair_prob, 4),
            'market_prob': round(self.market_prob, 4),
            'edge': round(self.edge, 4),
            'edge_pct': round(self.edge_pct, 2),
            'expected_value': round(self.expected_value, 2),
            'kelly_fraction': round(self.kelly_fraction, 4),
            'confidence': round(self.confidence, 2),
            'risk_flags': [f.value for f in self.risk_flags],
            'risk_score': round(self.risk_score, 2),
            'is_tradeable': self.is_tradeable,
            'suggested_side': self.suggested_side,
            'timestamp': self.timestamp.isoformat() + 'Z',
            'model_version': self.model_version,
        }


@dataclass
class DecisionRecord:
    """
    Record of a trading decision for evaluation.
    Used to track predictions vs outcomes.
    """
    decision_id: str
    market_id: str
    token_id: str
    
    # Decision details
    timestamp: datetime
    side: str  # BUY or SELL
    size: float
    entry_price: float
    
    # Probability estimate at decision time
    fair_prob: float
    market_prob: float
    edge: float
    confidence: float
    
    # Execution details
    fill_price: Optional[float] = None
    execution_drag: Optional[float] = None  # fill_price - entry_price
    
    # Outcome (filled after resolution)
    outcome: Optional[str] = None  # YES or NO
    final_value: Optional[float] = None  # 0 or 1
    pnl: Optional[float] = None
    
    # Evaluation metrics
    prediction_correct: Optional[bool] = None
    edge_realized: Optional[float] = None
    
    def to_dict(self) -> dict:
        return {
            'decision_id': self.decision_id,
            'market_id': self.market_id,
            'token_id': self.token_id,
            'timestamp': self.timestamp.isoformat() + 'Z',
            'side': self.side,
            'size': self.size,
            'entry_price': self.entry_price,
            'fair_prob': self.fair_prob,
            'market_prob': self.market_prob,
            'edge': self.edge,
            'confidence': self.confidence,
            'fill_price': self.fill_price,
            'execution_drag': self.execution_drag,
            'outcome': self.outcome,
            'final_value': self.final_value,
            'pnl': self.pnl,
            'prediction_correct': self.prediction_correct,
            'edge_realized': self.edge_realized,
        }


@dataclass
class CohortStats:
    """
    Statistics for a cohort of decisions.
    Used for experiment evaluation.
    """
    cohort_id: str
    start_time: datetime
    end_time: datetime
    
    # Counts
    total_decisions: int = 0
    profitable_decisions: int = 0
    
    # Edge metrics
    mean_edge: float = 0.0
    mean_edge_realized: float = 0.0
    edge_preservation_ratio: float = 0.0
    
    # Calibration
    brier_score: float = 0.0
    
    # Execution
    mean_execution_drag_bps: float = 0.0
    
    # P&L
    total_pnl: float = 0.0
    
    # Capital
    capital_deployed: float = 0.0
    avg_lockup_hours: float = 0.0
    
    def to_dict(self) -> dict:
        return {
            'cohort_id': self.cohort_id,
            'start_time': self.start_time.isoformat() + 'Z',
            'end_time': self.end_time.isoformat() + 'Z',
            'total_decisions': self.total_decisions,
            'profitable_decisions': self.profitable_decisions,
            'profitable_pct': (self.profitable_decisions / self.total_decisions * 100) if self.total_decisions > 0 else 0,
            'mean_edge': round(self.mean_edge, 4),
            'mean_edge_realized': round(self.mean_edge_realized, 4),
            'edge_preservation_ratio': round(self.edge_preservation_ratio, 2),
            'brier_score': round(self.brier_score, 4),
            'mean_execution_drag_bps': round(self.mean_execution_drag_bps, 2),
            'total_pnl': round(self.total_pnl, 2),
            'capital_deployed': round(self.capital_deployed, 2),
            'avg_lockup_hours': round(self.avg_lockup_hours, 1),
        }

