"""
Probability Model Service - Estimates fair probabilities for markets
"""
import math
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass
from loguru import logger

from ..models.market import Market, OrderBook, MarketCategory
from ..models.probability import ProbabilityEstimate, RiskFlag


@dataclass
class ProbabilityConfig:
    """Configuration for probability model."""
    # Edge thresholds
    min_edge_pct: float = 1.5  # Minimum edge to consider
    
    # Risk thresholds
    min_depth: float = 100.0  # Minimum depth in $
    max_spread_bps: float = 200.0  # Maximum spread in bps
    max_resolution_hours: float = 720.0  # 30 days
    min_resolution_hours: float = 1.0  # At least 1 hour
    
    # Confidence adjustments
    depth_confidence_scale: float = 1000.0  # Depth for full confidence
    imbalance_weight: float = 0.1  # Weight for order book imbalance
    
    # Kelly criterion
    max_kelly: float = 0.25  # Maximum Kelly fraction


class ProbabilityModelService:
    """
    Service for estimating fair probabilities.
    
    This is a simplified v1 model that uses:
    - Market mid price as base probability
    - Order book imbalance for directional bias
    - Depth and spread for confidence
    - Time to resolution for risk adjustment
    
    Future versions could incorporate:
    - Historical accuracy data
    - LLM-based analysis of market description
    - Cross-market correlations
    - News/sentiment analysis
    """
    
    def __init__(self, config: Optional[ProbabilityConfig] = None):
        self.config = config or ProbabilityConfig()
        self.model_version = "v1.0"
    
    def estimate(
        self,
        market: Market,
        order_book: OrderBook,
        external_signals: Optional[Dict] = None,
    ) -> ProbabilityEstimate:
        """
        Generate probability estimate for a market.
        
        Args:
            market: The market to analyze
            order_book: Current order book (for YES token)
            external_signals: Optional external data (news, sentiment, etc.)
        
        Returns:
            ProbabilityEstimate with fair prob, edge, and risk assessment
        """
        # Get market probability from order book
        market_prob = order_book.mid_price or 0.5
        
        # Assess risks
        risk_flags = self._assess_risks(market, order_book)
        risk_score = len(risk_flags) / 8  # Normalize by max possible flags
        
        # Calculate fair probability
        fair_prob = self._calculate_fair_prob(market, order_book, external_signals)
        
        # Calculate edge
        edge = fair_prob - market_prob
        edge_pct = edge * 100
        
        # Calculate expected value (simplified)
        # EV = edge * size - fees
        # For $100 position: EV = edge * 100
        expected_value = edge * 100
        
        # Calculate Kelly fraction
        kelly = self._calculate_kelly(fair_prob, market_prob)
        
        # Calculate confidence
        confidence = self._calculate_confidence(order_book, market, risk_flags)
        
        return ProbabilityEstimate(
            market_id=market.market_id,
            token_id=market.yes_token.token_id if market.yes_token else "",
            fair_prob=fair_prob,
            market_prob=market_prob,
            edge=edge,
            edge_pct=edge_pct,
            expected_value=expected_value,
            kelly_fraction=kelly,
            confidence=confidence,
            risk_flags=risk_flags,
            risk_score=risk_score,
            model_version=self.model_version,
            inputs={
                'mid_price': market_prob,
                'spread': order_book.spread,
                'imbalance': order_book.imbalance,
                'bid_depth': order_book.bid_depth,
                'ask_depth': order_book.ask_depth,
                'time_to_resolution': market.time_to_resolution,
                'category': market.category.value,
            }
        )
    
    def _calculate_fair_prob(
        self,
        market: Market,
        order_book: OrderBook,
        external_signals: Optional[Dict],
    ) -> float:
        """
        Calculate fair probability.
        
        This v1 implementation uses:
        1. Market mid price as base
        2. Order book imbalance adjustment
        3. Category-specific adjustments
        """
        base_prob = order_book.mid_price or 0.5
        
        # Order book imbalance adjustment
        # Positive imbalance (more bids) suggests YES underpriced
        imbalance_adj = order_book.imbalance * self.config.imbalance_weight
        
        # Category-specific adjustments
        category_adj = 0.0
        if market.category == MarketCategory.CRYPTO:
            # Crypto markets tend to be volatile, slightly discount extremes
            if base_prob > 0.9 or base_prob < 0.1:
                category_adj = -0.02 * (1 if base_prob > 0.5 else -1)
        
        # Time decay adjustment
        # As resolution approaches, market should be more accurate
        hours_to_res = market.time_to_resolution
        if hours_to_res < 24:
            # Very close to resolution - trust market more
            imbalance_adj *= 0.5
        
        # External signals (placeholder for LLM analysis, news, etc.)
        external_adj = 0.0
        if external_signals:
            external_adj = external_signals.get('probability_adjustment', 0.0)
        
        # Combine adjustments
        fair_prob = base_prob + imbalance_adj + category_adj + external_adj
        
        # Clamp to valid range
        fair_prob = max(0.01, min(0.99, fair_prob))
        
        return fair_prob
    
    def _assess_risks(self, market: Market, order_book: OrderBook) -> List[RiskFlag]:
        """Assess risk factors for the market."""
        risks = []
        
        # Check depth
        total_depth = order_book.bid_depth + order_book.ask_depth
        if total_depth < self.config.min_depth:
            risks.append(RiskFlag.LOW_DEPTH)
        
        # Check spread
        if order_book.spread_bps and order_book.spread_bps > self.config.max_spread_bps:
            risks.append(RiskFlag.WIDE_SPREAD)
        
        # Check resolution time
        hours = market.time_to_resolution
        if hours > self.config.max_resolution_hours:
            risks.append(RiskFlag.LONG_RESOLUTION)
        
        # Check for near-certainty (low edge potential)
        mid = order_book.mid_price
        if mid and (mid > 0.95 or mid < 0.05):
            risks.append(RiskFlag.NEAR_CERTAINTY)
        
        # Check order book imbalance
        imbalance = abs(order_book.imbalance)
        if imbalance > 0.7:
            risks.append(RiskFlag.IMBALANCED_BOOK)
        
        # Volume check (if available)
        if market.volume_24h < 1000:
            risks.append(RiskFlag.LOW_VOLUME)
        
        return risks
    
    def _calculate_kelly(self, fair_prob: float, market_prob: float) -> float:
        """
        Calculate Kelly criterion for optimal bet sizing.
        
        Kelly = (bp - q) / b
        where:
            b = odds received (1/market_prob - 1 for YES bet)
            p = probability of winning (fair_prob)
            q = probability of losing (1 - fair_prob)
        """
        if fair_prob <= market_prob:
            return 0.0  # No edge, no bet
        
        # For binary market:
        # If we buy YES at market_prob, we win (1 - market_prob) if YES
        # We lose market_prob if NO
        
        p = fair_prob
        q = 1 - fair_prob
        b = (1 - market_prob) / market_prob  # Odds
        
        kelly = (b * p - q) / b if b > 0 else 0
        
        # Clamp to reasonable range
        kelly = max(0, min(self.config.max_kelly, kelly))
        
        return kelly
    
    def _calculate_confidence(
        self,
        order_book: OrderBook,
        market: Market,
        risk_flags: List[RiskFlag],
    ) -> float:
        """Calculate confidence in our probability estimate."""
        confidence = 1.0
        
        # Reduce for each risk flag
        confidence -= len(risk_flags) * 0.1
        
        # Adjust for depth
        total_depth = order_book.bid_depth + order_book.ask_depth
        depth_factor = min(1.0, total_depth / self.config.depth_confidence_scale)
        confidence *= depth_factor
        
        # Adjust for spread
        if order_book.spread_bps:
            spread_factor = max(0.5, 1 - order_book.spread_bps / 500)
            confidence *= spread_factor
        
        # Adjust for time to resolution
        hours = market.time_to_resolution
        if hours > 168:  # > 1 week
            confidence *= 0.8
        elif hours > 720:  # > 30 days
            confidence *= 0.6
        
        # Clamp to valid range
        confidence = max(0.1, min(1.0, confidence))
        
        return confidence
    
    def get_tradeable_opportunities(
        self,
        markets: List[Market],
        order_books: Dict[str, OrderBook],
        min_edge: Optional[float] = None,
    ) -> List[ProbabilityEstimate]:
        """
        Scan markets for tradeable opportunities.
        
        Returns list of estimates that pass tradeability criteria.
        """
        min_edge = min_edge or self.config.min_edge_pct / 100
        opportunities = []
        
        for market in markets:
            if not market.is_active:
                continue
            
            token_id = market.yes_token.token_id if market.yes_token else None
            if not token_id or token_id not in order_books:
                continue
            
            order_book = order_books[token_id]
            estimate = self.estimate(market, order_book)
            
            if estimate.is_tradeable and abs(estimate.edge) >= min_edge:
                opportunities.append(estimate)
        
        # Sort by absolute edge
        opportunities.sort(key=lambda x: abs(x.edge), reverse=True)
        
        return opportunities

