"""
Evaluation Service - Tracks decisions and computes metrics
"""
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from pathlib import Path
import math
from loguru import logger

from ..models.market import Market, TokenSide
from ..models.probability import ProbabilityEstimate, DecisionRecord, CohortStats


@dataclass
class EvaluationConfig:
    """Configuration for evaluation service."""
    cohort_duration_hours: float = 12.0  # New cohort every 12 hours
    history_file: str = "data/polymarket_history.json"
    max_history: int = 1000


class EvaluationService:
    """
    Service for tracking decisions and computing evaluation metrics.
    
    Key Metrics:
    1. Mean Edge: E[final_outcome - entry_price]
    2. Brier Score: Mean squared error of probability predictions
    3. Edge Preservation Ratio: realized_edge / theoretical_edge
    4. Execution Drag: Average slippage in bps
    """
    
    def __init__(self, config: Optional[EvaluationConfig] = None):
        self.config = config or EvaluationConfig()
        self.history_file = Path(self.config.history_file)
        
        # In-memory state
        self.decisions: List[DecisionRecord] = []
        self.cohorts: Dict[str, CohortStats] = {}
        self._current_cohort_id: Optional[str] = None
        self._current_cohort_start: Optional[datetime] = None
        
        # Load history
        self._load_history()
    
    def log_decision(
        self,
        market: Market,
        estimate: ProbabilityEstimate,
        side: str,
        size: float,
        entry_price: float,
        fill_price: Optional[float] = None,
    ) -> DecisionRecord:
        """
        Log a trading decision.
        
        Args:
            market: The market
            estimate: Probability estimate at decision time
            side: BUY or SELL
            size: Position size
            entry_price: Intended entry price
            fill_price: Actual fill price (if executed)
        
        Returns:
            DecisionRecord for tracking
        """
        # Ensure we have a cohort
        self._ensure_cohort()
        
        execution_drag = None
        if fill_price:
            execution_drag = (fill_price - entry_price) / entry_price * 10000  # bps
        
        record = DecisionRecord(
            decision_id=str(uuid.uuid4()),
            market_id=market.market_id,
            token_id=estimate.token_id,
            timestamp=datetime.utcnow(),
            side=side,
            size=size,
            entry_price=entry_price,
            fair_prob=estimate.fair_prob,
            market_prob=estimate.market_prob,
            edge=estimate.edge,
            confidence=estimate.confidence,
            fill_price=fill_price,
            execution_drag=execution_drag,
        )
        
        self.decisions.append(record)
        self._save_history()
        
        logger.info(
            f"📝 Logged decision: {market.slug} | "
            f"{side} @ ${entry_price:.3f} | "
            f"Edge: {estimate.edge_pct:.2f}%"
        )
        
        return record
    
    def resolve_decision(
        self,
        decision_id: str,
        outcome: TokenSide,
    ) -> Optional[DecisionRecord]:
        """
        Resolve a decision when the market settles.
        
        Args:
            decision_id: ID of the decision
            outcome: Market outcome (YES or NO)
        
        Returns:
            Updated DecisionRecord
        """
        record = next((d for d in self.decisions if d.decision_id == decision_id), None)
        if not record:
            return None
        
        # Determine final value
        # If we bought YES and outcome is YES, value = 1
        # If we bought YES and outcome is NO, value = 0
        bought_yes = record.side == "BUY"  # Assuming YES token
        record.outcome = outcome.value
        record.final_value = 1.0 if (bought_yes == (outcome == TokenSide.YES)) else 0.0
        
        # Calculate P&L
        fill_price = record.fill_price or record.entry_price
        if bought_yes:
            record.pnl = (record.final_value - fill_price) * record.size
        else:
            record.pnl = (fill_price - record.final_value) * record.size
        
        # Was prediction correct?
        # Correct if we predicted YES (edge > 0) and outcome was YES, or vice versa
        predicted_yes = record.edge > 0
        record.prediction_correct = predicted_yes == (outcome == TokenSide.YES)
        
        # Calculate realized edge
        if bought_yes:
            record.edge_realized = record.final_value - fill_price
        else:
            record.edge_realized = fill_price - record.final_value
        
        self._save_history()
        
        logger.info(
            f"✅ Resolved decision {decision_id}: "
            f"outcome={outcome.value}, pnl=${record.pnl:.2f}, "
            f"correct={record.prediction_correct}"
        )
        
        return record
    
    def get_brier_score(self, decisions: Optional[List[DecisionRecord]] = None) -> float:
        """
        Calculate Brier score for probability calibration.
        
        Brier Score = (1/N) * Σ(forecast - outcome)²
        
        Lower is better. Perfect = 0, Random = 0.25
        """
        decisions = decisions or [d for d in self.decisions if d.outcome is not None]
        if not decisions:
            return 0.0
        
        total = 0.0
        for d in decisions:
            # Our forecast for YES
            forecast = d.fair_prob
            # Actual outcome (1 for YES, 0 for NO)
            outcome = 1.0 if d.outcome == "YES" else 0.0
            total += (forecast - outcome) ** 2
        
        return total / len(decisions)
    
    def get_mean_edge(self, decisions: Optional[List[DecisionRecord]] = None) -> float:
        """Calculate mean edge across decisions."""
        decisions = decisions or [d for d in self.decisions if d.edge_realized is not None]
        if not decisions:
            return 0.0
        return sum(d.edge_realized for d in decisions) / len(decisions)
    
    def get_edge_preservation_ratio(self, decisions: Optional[List[DecisionRecord]] = None) -> float:
        """
        Calculate edge preservation ratio.
        
        EPR = mean(realized_edge) / mean(theoretical_edge)
        
        EPR > 1 means we did better than expected
        EPR < 1 means execution/timing hurt us
        """
        decisions = decisions or [d for d in self.decisions if d.edge_realized is not None]
        if not decisions:
            return 0.0
        
        mean_realized = sum(d.edge_realized for d in decisions) / len(decisions)
        mean_theoretical = sum(abs(d.edge) for d in decisions) / len(decisions)
        
        if mean_theoretical == 0:
            return 0.0
        
        return mean_realized / mean_theoretical
    
    def get_execution_drag(self, decisions: Optional[List[DecisionRecord]] = None) -> float:
        """Calculate mean execution drag in bps."""
        decisions = decisions or [d for d in self.decisions if d.execution_drag is not None]
        if not decisions:
            return 0.0
        return sum(d.execution_drag for d in decisions) / len(decisions)
    
    def get_cohort_stats(self, cohort_id: Optional[str] = None) -> Optional[CohortStats]:
        """Get stats for a specific cohort or current cohort."""
        if cohort_id is None:
            cohort_id = self._current_cohort_id
        
        if cohort_id is None:
            return None
        
        # Get decisions in this cohort
        cohort = self.cohorts.get(cohort_id)
        if not cohort:
            return None
        
        cohort_decisions = [
            d for d in self.decisions
            if cohort.start_time <= d.timestamp <= cohort.end_time
        ]
        
        resolved = [d for d in cohort_decisions if d.outcome is not None]
        
        if not resolved:
            return cohort
        
        # Update stats
        cohort.total_decisions = len(resolved)
        cohort.profitable_decisions = len([d for d in resolved if (d.pnl or 0) > 0])
        cohort.mean_edge = self.get_mean_edge(resolved)
        cohort.mean_edge_realized = self.get_mean_edge(resolved)
        cohort.edge_preservation_ratio = self.get_edge_preservation_ratio(resolved)
        cohort.brier_score = self.get_brier_score(resolved)
        cohort.mean_execution_drag_bps = self.get_execution_drag(resolved)
        cohort.total_pnl = sum(d.pnl or 0 for d in resolved)
        cohort.capital_deployed = sum(d.size for d in resolved)
        
        return cohort
    
    def get_overall_stats(self) -> dict:
        """Get overall performance statistics."""
        resolved = [d for d in self.decisions if d.outcome is not None]
        
        return {
            'total_decisions': len(self.decisions),
            'resolved_decisions': len(resolved),
            'pending_decisions': len(self.decisions) - len(resolved),
            'brier_score': round(self.get_brier_score(), 4),
            'mean_edge': round(self.get_mean_edge() * 100, 2),  # As percentage
            'edge_preservation_ratio': round(self.get_edge_preservation_ratio(), 2),
            'mean_execution_drag_bps': round(self.get_execution_drag(), 2),
            'total_pnl': round(sum(d.pnl or 0 for d in resolved), 2),
            'win_rate': round(
                len([d for d in resolved if (d.pnl or 0) > 0]) / len(resolved) * 100, 1
            ) if resolved else 0,
            'prediction_accuracy': round(
                len([d for d in resolved if d.prediction_correct]) / len(resolved) * 100, 1
            ) if resolved else 0,
            'cohorts': len(self.cohorts),
        }
    
    def _ensure_cohort(self):
        """Ensure we have an active cohort."""
        now = datetime.utcnow()
        
        if self._current_cohort_start is None:
            self._start_new_cohort(now)
            return
        
        elapsed = (now - self._current_cohort_start).total_seconds() / 3600
        if elapsed >= self.config.cohort_duration_hours:
            self._start_new_cohort(now)
    
    def _start_new_cohort(self, start_time: datetime):
        """Start a new cohort."""
        cohort_id = f"cohort_{start_time.strftime('%Y%m%d_%H%M')}"
        
        cohort = CohortStats(
            cohort_id=cohort_id,
            start_time=start_time,
            end_time=start_time + timedelta(hours=self.config.cohort_duration_hours),
        )
        
        self.cohorts[cohort_id] = cohort
        self._current_cohort_id = cohort_id
        self._current_cohort_start = start_time
        
        logger.info(f"Started new cohort: {cohort_id}")
    
    def _load_history(self):
        """Load decision history from disk."""
        try:
            if self.history_file.exists():
                with open(self.history_file, 'r') as f:
                    data = json.load(f)
                
                for d in data.get('decisions', []):
                    try:
                        record = DecisionRecord(
                            decision_id=d['decision_id'],
                            market_id=d['market_id'],
                            token_id=d['token_id'],
                            timestamp=datetime.fromisoformat(d['timestamp'].replace('Z', '')),
                            side=d['side'],
                            size=d['size'],
                            entry_price=d['entry_price'],
                            fair_prob=d['fair_prob'],
                            market_prob=d['market_prob'],
                            edge=d['edge'],
                            confidence=d['confidence'],
                            fill_price=d.get('fill_price'),
                            execution_drag=d.get('execution_drag'),
                            outcome=d.get('outcome'),
                            final_value=d.get('final_value'),
                            pnl=d.get('pnl'),
                            prediction_correct=d.get('prediction_correct'),
                            edge_realized=d.get('edge_realized'),
                        )
                        self.decisions.append(record)
                    except Exception as e:
                        logger.warning(f"Failed to load decision: {e}")
                
                logger.info(f"📂 Loaded {len(self.decisions)} decisions from history")
        except Exception as e:
            logger.warning(f"Could not load history: {e}")
    
    def _save_history(self):
        """Save decision history to disk."""
        try:
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                'decisions': [d.to_dict() for d in self.decisions[-self.config.max_history:]],
                'saved_at': datetime.utcnow().isoformat() + 'Z',
            }
            
            with open(self.history_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save history: {e}")
    
    def get_history(self, limit: int = 50) -> List[dict]:
        """Get recent decision history."""
        return [d.to_dict() for d in self.decisions[-limit:]]
    
    def get_pending_resolutions(self) -> List[DecisionRecord]:
        """Get decisions awaiting resolution."""
        return [d for d in self.decisions if d.outcome is None]

