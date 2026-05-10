# Realistic Turn Physics Implementation

## Overview

Aircraft now use **realistic turn physics** that prevent them from running off taxiways during turns. The system dynamically adjusts speed and turn rate based on turn severity.

## Key Improvements

### 1. **Dynamic Speed Reduction Based on Turn Angle**

Aircraft automatically slow down before and during turns:

| Turn Angle | Speed Reduction | Typical Speed | Use Case |
|------------|----------------|---------------|----------|
| **90°+** | 85% reduction | ~3 knots | U-turns, very tight corners |
| **70-90°** | 75% reduction | ~5 knots | Sharp taxiway turns |
| **45-70°** | 60% reduction | ~7 knots | Medium-sharp turns |
| **30-45°** | 45% reduction | ~10 knots | Standard taxiway turns |
| **15-30°** | 30% reduction | ~13 knots | Gentle curves |
| **5-15°** | 15% reduction | ~15 knots | Slight adjustments |
| **<5°** | No reduction | ~18 knots | Straight taxi |

### 2. **Look-Ahead Turn Anticipation**

Aircraft detect upcoming turns and begin slowing down in advance:

```python
# Example: 90° turn ahead
if distance_to_turn < 30m and upcoming_turn_angle > 90°:
    target_speed = max_taxi_speed * 0.10  # Slow to 2 knots
```

**Anticipation Distances:**
- 90°+ turns: Start slowing 30m before
- 70-90° turns: Start slowing 40m before
- 45-70° turns: Start slowing 50m before
- 30-45° turns: Start slowing 60m before
- 15-30° turns: Start slowing 70m before

### 3. **Variable Turn Rate**

Turn rate adjusts based on both speed and turn severity:

```python
# Slower speeds allow tighter angular rotation
# But sharper turns reduce turn rate for control

Turn Rate = Base Rate × Turn Severity Multiplier × (1 / Speed Factor)
```

**Turn Severity Multipliers:**
- 90°+ turns: 0.4× (very slow, controlled turn)
- 60-90° turns: 0.6× (reduced turn rate)
- 30-60° turns: 0.8× (moderate turn rate)
- <30° turns: 1.0× (normal turn rate)

### 4. **Overshoot Prevention**

When within 5 meters of a waypoint, movement is reduced by 50% if the aircraft would overshoot:

```python
if new_distance > distance and distance < 5m:
    move_distance *= 0.5  # Prevent overshoot
```

This prevents aircraft from "sliding" past waypoints during tight turns.

## Physics Model

### Turn Radius Calculation

While we don't explicitly calculate turn radius in the code (for performance), the speed reductions are based on realistic turn radius requirements:

```
Turn Radius (meters) ≈ (Speed in m/s)² / (g × tan(bank_angle))

For ground operations:
- Bank angle is limited (~5-10° max)
- Speed must reduce for tighter turns
- Slower speed = smaller turn radius
```

### Speed-Turn Relationship

```
90° turn at 18 knots → ~50m radius → Runs off taxiway ❌
90° turn at 3 knots → ~8m radius → Stays on centerline ✅
```

## Realistic Behavior Examples

### Example 1: Sharp 90° Turn
```
Approaching turn:
- Distance: 50m → Speed: 18 knots (normal)
- Distance: 30m → Speed: 3 knots (slowing)
- At turn: Speed: 2 knots, Turn rate: 5°/sec
- Result: Smooth, controlled turn on centerline
```

### Example 2: Gentle 20° Curve
```
Approaching curve:
- Distance: 100m → Speed: 18 knots
- Distance: 70m → Speed: 13 knots (slight reduction)
- At curve: Speed: 13 knots, Turn rate: 12°/sec
- Result: Smooth, flowing curve
```

### Example 3: Straight Taxiway
```
No turns ahead:
- Speed: 18 knots (max taxi speed)
- Turn rate: N/A (heading stable)
- Result: Efficient straight-line taxi
```

## Benefits

### Before (Old System)
- ❌ Aircraft maintained high speed through turns
- ❌ Wide turn radius caused taxiway departures
- ❌ Unrealistic "sliding" through corners
- ❌ No anticipation of upcoming turns

### After (New System)
- ✅ Speed automatically reduces for turns
- ✅ Tight turn radius keeps aircraft on centerline
- ✅ Realistic deceleration before turns
- ✅ Look-ahead prevents late braking
- ✅ Smooth, controlled movements

## Technical Details

### Movement Calculation

```python
# Convert speed (knots) to distance (degrees)
move_distance = (speed_knots × 0.514444 m/s × dt) / 111000 m/degree

# Apply movement in current heading direction
new_lat = lat + move_distance × cos(heading)
new_lon = lon + move_distance × sin(heading)
```

### Turn Rate Calculation

```python
# Base turn rate (12°/sec max)
base_rate = 12.0

# Adjust for turn severity
severity_multiplier = 0.4 to 1.0 (based on angle)

# Adjust for speed (slower = can turn faster)
speed_factor = speed / max_speed  # 0.3 to 1.0
turn_rate = base_rate × severity_multiplier × (1 / speed_factor)
```

### Smooth Interpolation

Near the target heading, smooth interpolation prevents oscillation:

```python
if abs(heading_diff) < max_turn_this_frame:
    heading = heading + (heading_diff × 0.4)  # 40% interpolation
```

## Configuration

Key parameters in `Aircraft.__init__`:

```python
self.max_taxi_speed = 18.0  # knots (realistic taxi speed)
self.max_turn_rate = 12.0   # degrees/second (realistic turn rate)
self.acceleration = 2.5     # knots/second
self.deceleration = 3.5     # knots/second
```

## Future Enhancements

- [ ] **Surface-specific speeds**: Slower on ramps, faster on straight taxiways
- [ ] **Weather effects**: Reduced speeds on wet/icy surfaces
- [ ] **Aircraft-specific turn performance**: Heavy aircraft turn slower
- [ ] **Pilot skill variation**: Some pilots turn more conservatively
- [ ] **Turn radius visualization**: Show turn circle in debug mode

## Testing

To verify turn physics:

1. **Watch sharp turns**: Aircraft should slow to ~3 knots for 90° turns
2. **Check centerline tracking**: Aircraft should stay on taxiway centerline
3. **Observe anticipation**: Speed reduction should start before the turn
4. **Monitor logs**: Look for speed changes as aircraft approach turns

## Conclusion

The new turn physics system creates **realistic, safe taxi operations** where aircraft intelligently manage their speed and turn rate to stay on the taxiway centerline, just like real pilots do.
