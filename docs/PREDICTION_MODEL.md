# Prediction Model Documentation

## Overview

The prediction model uses a **multi-signal analysis** approach to generate short-term price predictions for cryptocurrencies. It combines momentum, derivatives data, and market microstructure to produce probabilistic forecasts.

## Signal Analysis

### 1. Momentum Signal (40% weight)

```python
momentum_z = returns_1h / (volatility + 0.001)
momentum_signal = np.tanh(momentum_z * 0.5)  # [-1, 1]
```

**Logic:**
- Normalize recent returns by current volatility
- Strong moves in low-vol environments = stronger signal
- Weak moves in high-vol environments = weaker signal

### 2. CVD Signal (25% weight)

```python
cvd_normalized = cvd / 5_000_000  # $5M baseline
cvd_signal = np.tanh(cvd_normalized)
```

**Logic:**
- Cumulative Volume Delta measures net buying vs selling
- Positive CVD = buyers dominating = bullish
- Normalized by typical daily CVD range

### 3. Funding Rate Signal (20% weight)

```python
funding_signal = -np.tanh(funding * 200)  # Contrarian!
```

**Logic:**
- **Contrarian indicator**
- High positive funding = longs paying shorts = too bullish = sell signal
- High negative funding = shorts paying longs = too bearish = buy signal

### 4. Open Interest Signal (15% weight)

```python
oi_signal = np.tanh(oi_change * 10)
# Align with momentum direction
if returns_1h > 0:
    score += oi_signal * 0.15
else:
    score += -oi_signal * 0.15
```

**Logic:**
- Rising OI with positive momentum = trend confirmation
- Rising OI with negative momentum = bearish confirmation
- Falling OI = position unwinding

## Probability Calculation

```python
# Combine signals
score = (momentum * 0.4) + (cvd * 0.25) + (funding * 0.2) + (oi * 0.15)

# Convert [-1, 1] score to probability [0.15, 0.85]
p_up = 0.5 + (score * 0.35)
```

**Why 0.15-0.85 range?**
- Markets are inherently unpredictable
- Never claim 100% or 0% probability
- Conservative bounds prevent overconfidence

## Regime Detection

| Regime | Detection Logic |
|--------|-----------------|
| `panic` | returns < -2% AND volatility > 3% |
| `high-vol` | volatility > 4% |
| `trend-up` | p_up > 65% OR (p_up > 55% AND returns > 0) |
| `trend-down` | p_up < 35% OR (p_up < 45% AND returns < 0) |
| `ranging` | default |

## Confidence Levels

```python
prob_strength = abs(p_up - 0.5) * 2  # 0 to 1 scale

# Regime adjustment
if regime == "panic": prob_strength *= 0.4
elif regime == "high-vol": prob_strength *= 0.6
elif regime in ["trend-up", "trend-down"]: prob_strength *= 1.2

# Classification
if prob_strength > 0.25: confidence = "high"
elif prob_strength > 0.12: confidence = "medium"
else: confidence = "low"
```

## Adaptive Calibration

The model learns from its own performance:

### Confidence Boost/Reduction

```python
# If high-confidence predictions are mostly WRONG
if high_accuracy < 0.4:
    confidence_boost = 0.7  # Be more humble

# If low-confidence is more accurate than high
if low_accuracy > high_accuracy + 0.15:
    confidence_boost = 0.85  # Stay humble

# If medium-confidence is working well
if medium_accuracy > 0.7:
    confidence_boost = 1.1  # Slight boost
```

### Direction Bias

```python
# Learn which direction we're better at predicting
if down_accuracy > up_accuracy + 0.15:
    direction_bias = -0.08  # Lean bearish
elif up_accuracy > down_accuracy + 0.15:
    direction_bias = 0.08   # Lean bullish
```

## Volatility Estimation

```python
# Scale hourly volatility to minute horizon
horizon_vol = base_vol * np.sqrt(horizon_minutes / 60)
```

**Square-root of time rule:**
- Volatility scales with √time
- 5-minute volatility ≈ hourly_vol × √(5/60) ≈ hourly_vol × 0.29

## Prediction Cone

The prediction cone shows expected price range:

```python
for each minute in horizon:
    t = minute / (24 * 60)  # Fraction of day
    sqrt_t = np.sqrt(t)
    
    mid_price = current_price * exp(drift * minute)
    vol_band = volatility * sqrt_t * 3
    
    upper_1sigma = current_price * exp(drift + vol_band)
    lower_1sigma = current_price * exp(drift - vol_band)
```

## Validation Process

```
1. Prediction logged with:
   - Entry price
   - P(Up) probability
   - Horizon (minutes)
   - Timestamp

2. After horizon expires:
   - Get current price
   - Calculate actual move %
   - Compare: predicted_up == actual_up?
   - Update accuracy stats
   - Apply adaptive calibration
```

## Performance Metrics

### Accuracy by Confidence

| Confidence | Target Accuracy |
|------------|-----------------|
| High | 70%+ |
| Medium | 55-70% |
| Low | 50-55% |

### Expected Behavior

- **50% accuracy** = Random, useless
- **55% accuracy** = Profitable with good risk management
- **60%+ accuracy** = Strong edge
- **70%+ sustained** = Exceptional (be suspicious!)

## Limitations

1. **Short horizons only**: Model optimized for 1-10 minutes
2. **No external events**: Can't predict news, hacks, regulations
3. **Assumes market efficiency**: Major inefficiencies = model fails
4. **Past != Future**: Historical patterns may not repeat

## Future Improvements

1. [ ] Machine learning models (XGBoost, Neural Networks)
2. [ ] Orderbook depth analysis
3. [ ] Sentiment analysis (Twitter, news)
4. [ ] Cross-asset correlation
5. [ ] Whale wallet tracking

