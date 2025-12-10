"""
Prediction Tracker - Logs predictions and validates them after horizon expires.
"""
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from collections import deque
import json
from pathlib import Path
from loguru import logger


@dataclass
class PredictionRecord:
    """A single prediction record."""
    id: str
    asset: str
    timestamp: datetime
    horizon_minutes: int
    
    # Prediction at time of creation
    entry_price: float
    p_up: float
    p_down: float
    expected_move: float
    regime: str
    confidence: str
    
    # Validation (filled after horizon expires)
    exit_price: Optional[float] = None
    actual_move: Optional[float] = None
    prediction_correct: Optional[bool] = None
    validated_at: Optional[datetime] = None
    
    def to_dict(self) -> dict:
        # Add 'Z' suffix to indicate UTC timestamps for proper browser timezone conversion
        def to_utc_iso(dt):
            if dt is None:
                return None
            return dt.isoformat() + 'Z' if not dt.isoformat().endswith('Z') else dt.isoformat()
        
        return {
            'id': self.id,
            'asset': self.asset,
            'timestamp': to_utc_iso(self.timestamp),
            'horizon_minutes': int(self.horizon_minutes),
            'entry_price': float(self.entry_price),
            'p_up': float(self.p_up),
            'p_down': float(self.p_down),
            'expected_move': float(self.expected_move),
            'regime': self.regime,
            'confidence': self.confidence,
            'exit_price': float(self.exit_price) if self.exit_price is not None else None,
            'actual_move': float(self.actual_move) if self.actual_move is not None else None,
            'prediction_correct': bool(self.prediction_correct) if self.prediction_correct is not None else None,
            'validated_at': to_utc_iso(self.validated_at),
        }


class PredictionTracker:
    """
    Tracks predictions and validates them after their horizon expires.
    Persists history to disk so it survives restarts.
    """
    
    MAX_HISTORY = 500  # Keep last 500 predictions
    HISTORY_FILE = Path("data/prediction_history.json")
    
    def __init__(self, data_service=None):
        self.data_service = data_service
        self.predictions: deque = deque(maxlen=self.MAX_HISTORY)
        self.pending_validations: Dict[str, PredictionRecord] = {}
        self._running = False
        self._counter = 0
        
        # Stats
        self.total_predictions = 0
        self.correct_predictions = 0
        self.stats_by_confidence = {
            'high': {'total': 0, 'correct': 0},
            'medium': {'total': 0, 'correct': 0},
            'low': {'total': 0, 'correct': 0},
        }
        
        # Load history from disk
        self._load_history()
    
    def log_prediction(
        self,
        asset: str,
        entry_price: float,
        p_up: float,
        expected_move: float,
        horizon_minutes: int,
        regime: str,
        confidence: str,
    ) -> PredictionRecord:
        """Log a new prediction."""
        self._counter += 1
        record = PredictionRecord(
            id=f"{asset}_{datetime.utcnow().strftime('%H%M%S')}_{self._counter}",
            asset=asset,
            timestamp=datetime.utcnow(),
            horizon_minutes=horizon_minutes,
            entry_price=entry_price,
            p_up=p_up,
            p_down=1 - p_up,
            expected_move=expected_move,
            regime=regime,
            confidence=confidence,
        )
        
        self.predictions.append(record)
        self.pending_validations[record.id] = record
        
        logger.info(
            f"📊 Logged prediction: {asset} @ ${entry_price:.2f} | "
            f"P(Up)={p_up*100:.1f}% | {horizon_minutes}m horizon | {confidence} confidence"
        )
        
        return record
    
    async def start_validation_loop(self):
        """Background task to validate expired predictions."""
        self._running = True
        logger.info("Starting prediction validation loop...")
        
        while self._running:
            try:
                await self._validate_expired_predictions()
                await asyncio.sleep(10)  # Check every 10 seconds
            except Exception as e:
                logger.error(f"Validation loop error: {e}")
                await asyncio.sleep(30)
    
    def stop(self):
        """Stop the validation loop."""
        self._running = False
    
    async def _validate_expired_predictions(self):
        """Check and validate any predictions past their horizon."""
        now = datetime.utcnow()
        to_validate = []
        
        for pred_id, pred in list(self.pending_validations.items()):
            try:
                # Handle timezone-aware timestamps by removing tzinfo for comparison
                pred_ts = pred.timestamp.replace(tzinfo=None) if pred.timestamp.tzinfo else pred.timestamp
                expiry = pred_ts + timedelta(minutes=pred.horizon_minutes)
                if now >= expiry:
                    to_validate.append(pred)
            except Exception as e:
                logger.warning(f"Error checking prediction {pred_id}: {e}")
                continue
        
        for pred in to_validate:
            await self._validate_prediction(pred)
    
    async def _validate_prediction(self, pred: PredictionRecord):
        """Validate a single prediction."""
        try:
            # Get current price
            if self.data_service:
                data = await self.data_service.get_latest_data(pred.asset)
                exit_price = data.get('price', 0)
            else:
                # Fallback: can't validate without data service
                logger.warning(f"No data service, skipping validation for {pred.id}")
                del self.pending_validations[pred.id]
                return
            
            # Calculate actual move
            actual_move = (exit_price - pred.entry_price) / pred.entry_price
            
            # Determine if prediction was correct
            predicted_up = pred.p_up > 0.5
            actual_up = actual_move > 0
            prediction_correct = predicted_up == actual_up
            
            # Update record
            pred.exit_price = exit_price
            pred.actual_move = actual_move
            pred.prediction_correct = prediction_correct
            pred.validated_at = datetime.utcnow()
            
            # Update stats
            self.total_predictions += 1
            if prediction_correct:
                self.correct_predictions += 1
            
            # Update confidence-specific stats
            if pred.confidence in self.stats_by_confidence:
                self.stats_by_confidence[pred.confidence]['total'] += 1
                if prediction_correct:
                    self.stats_by_confidence[pred.confidence]['correct'] += 1
            
            # Log result
            result_emoji = "✅" if prediction_correct else "❌"
            accuracy = (self.correct_predictions / self.total_predictions * 100) if self.total_predictions > 0 else 0
            
            logger.info(
                f"{result_emoji} Validated: {pred.asset} | "
                f"Entry: ${pred.entry_price:.2f} → Exit: ${exit_price:.2f} | "
                f"Predicted: {'UP' if predicted_up else 'DOWN'} ({pred.p_up*100:.0f}%) | "
                f"Actual: {actual_move*100:+.3f}% | "
                f"Overall Accuracy: {accuracy:.1f}% ({self.correct_predictions}/{self.total_predictions})"
            )
            
            # Remove from pending
            del self.pending_validations[pred.id]
            
            # Save to disk
            self._save_history()
            
        except Exception as e:
            logger.error(f"Error validating prediction {pred.id}: {e}")
            del self.pending_validations[pred.id]
    
    def get_history(self, limit: int = 50, asset: Optional[str] = None) -> List[dict]:
        """Get prediction history."""
        history = list(self.predictions)
        
        if asset:
            history = [p for p in history if p.asset == asset]
        
        # Return most recent first, only validated ones
        validated = [p for p in history if p.validated_at is not None]
        validated.sort(key=lambda x: x.timestamp, reverse=True)
        
        return [p.to_dict() for p in validated[:limit]]
    
    def get_stats(self) -> dict:
        """Get prediction accuracy statistics."""
        accuracy = (self.correct_predictions / self.total_predictions * 100) if self.total_predictions > 0 else 0
        
        # Calculate confidence breakdown
        confidence_stats = {}
        for conf, stats in self.stats_by_confidence.items():
            if stats['total'] > 0:
                confidence_stats[conf] = {
                    'total': stats['total'],
                    'correct': stats['correct'],
                    'accuracy': stats['correct'] / stats['total'] * 100
                }
            else:
                confidence_stats[conf] = {'total': 0, 'correct': 0, 'accuracy': 0}
        
        return {
            'total_predictions': self.total_predictions,
            'correct_predictions': self.correct_predictions,
            'accuracy_pct': round(accuracy, 2),
            'pending_validations': len(self.pending_validations),
            'by_confidence': confidence_stats,
        }
    
    def get_pending(self) -> List[dict]:
        """Get predictions waiting for validation."""
        pending = list(self.pending_validations.values())
        pending.sort(key=lambda x: x.timestamp, reverse=True)
        return [p.to_dict() for p in pending]
    
    def _load_history(self):
        """Load prediction history from disk."""
        try:
            if self.HISTORY_FILE.exists():
                with open(self.HISTORY_FILE, 'r') as f:
                    data = json.load(f)
                
                # Restore stats
                self.total_predictions = data.get('total_predictions', 0)
                self.correct_predictions = data.get('correct_predictions', 0)
                self.stats_by_confidence = data.get('stats_by_confidence', {
                    'high': {'total': 0, 'correct': 0},
                    'medium': {'total': 0, 'correct': 0},
                    'low': {'total': 0, 'correct': 0},
                })
                
                # Restore validated predictions
                for p_dict in data.get('history', []):
                    try:
                        record = PredictionRecord(
                            id=p_dict['id'],
                            asset=p_dict['asset'],
                            timestamp=datetime.fromisoformat(p_dict['timestamp']),
                            horizon_minutes=p_dict['horizon_minutes'],
                            entry_price=p_dict['entry_price'],
                            p_up=p_dict['p_up'],
                            p_down=p_dict['p_down'],
                            expected_move=p_dict['expected_move'],
                            regime=p_dict['regime'],
                            confidence=p_dict['confidence'],
                            exit_price=p_dict.get('exit_price'),
                            actual_move=p_dict.get('actual_move'),
                            prediction_correct=p_dict.get('prediction_correct'),
                            validated_at=datetime.fromisoformat(p_dict['validated_at']) if p_dict.get('validated_at') else None,
                        )
                        self.predictions.append(record)
                    except Exception as e:
                        logger.warning(f"Failed to restore prediction: {e}")
                
                logger.info(f"📂 Loaded {len(self.predictions)} predictions from history (Accuracy: {self.total_predictions}/{self.correct_predictions})")
        except Exception as e:
            logger.warning(f"Could not load prediction history: {e}")
    
    def _save_history(self):
        """Save prediction history to disk."""
        try:
            # Ensure directory exists
            self.HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
            
            # Get validated predictions only
            validated = [p for p in self.predictions if p.validated_at is not None]
            
            data = {
                'total_predictions': self.total_predictions,
                'correct_predictions': self.correct_predictions,
                'stats_by_confidence': self.stats_by_confidence,
                'history': [p.to_dict() for p in validated[-100:]],  # Keep last 100
                'saved_at': datetime.utcnow().isoformat(),
            }
            
            with open(self.HISTORY_FILE, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            logger.warning(f"Could not save prediction history: {e}")

