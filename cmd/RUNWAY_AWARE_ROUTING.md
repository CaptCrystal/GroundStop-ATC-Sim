# Runway-Aware Taxi Routing

## New Feature: Runway Location Integration

The taxi routing system now uses **runway location data** from `scenarios.json` to make intelligent direction decisions that always move aircraft toward their destination runway.

## Configuration in scenarios.json

```json
{
  "runway_definition": [ 
    {"name": "02", "location": [{"x": 37.235852, "y": -93.389149}]}, 
    {"name": "14", "location": [{"x": 37.255134, "y": -93.400407}]}
  ]
}
```

### Format:
- `name`: Runway identifier (e.g., "02", "14", "20", "32")
- `location`: Array with runway threshold coordinates
  - `x`: Latitude
  - `y`: Longitude

## How It Works

### 1. Runway Location Lookup

When taxi clearance is issued:
```python
# Extract runway from destination
"runway 02" → runway_number = "02"

# Find in runway_definition
runway_location = (37.235852, -93.389149)
```

### 2. Direction Scoring System

For **intermediate taxiways** (not last):
```python
# Calculate distances
dist_to_next_taxiway = distance(taxiway_end, next_taxiway)
dist_to_runway = distance(taxiway_end, runway_location)

# Weighted score: 70% next taxiway, 30% runway
score = (0.7 × dist_to_next) + (0.3 × dist_to_runway)

# Choose direction with LOWER score
```

For **last taxiway**:
```python
# Direct runway distance comparison
dist_first_to_runway = distance(taxiway_first, runway)
dist_last_to_runway = distance(taxiway_last, runway)

# Choose end closer to runway
```

### 3. Smart Decision Making

The system considers:
1. **Next taxiway connection** (70% weight)
2. **Ultimate runway destination** (30% weight)
3. **Aircraft position** on current taxiway

This prevents aircraft from going the wrong way even if it initially connects to the next taxiway.

## Example: Runway 02 vs Runway 14

### Scenario 1: Taxi to Runway 02

```
Command: 102 t02fw
Destination: runway 02
Runway location: (37.235852, -93.389149)

Taxiway F:
  F first → W: 466m, F first → RWY02: 1800m
  F last → W: 388m, F last → RWY02: 1200m
  
  Score forward: (0.7 × 388) + (0.3 × 1200) = 631.6
  Score backward: (0.7 × 466) + (0.3 × 1800) = 866.2
  
  ✅ FORWARD wins (lower score, closer to runway)

Taxiway W (last):
  W first → RWY02: 2000m
  W last → RWY02: 50m
  
  ✅ FORWARD (toward last, which is closer to runway)
```

### Scenario 2: Taxi to Runway 14

```
Command: 102 t14fw
Destination: runway 14
Runway location: (37.255134, -93.400407)

Taxiway F:
  F first → W: 466m, F first → RWY14: 1200m
  F last → W: 388m, F last → RWY14: 1800m
  
  Score forward: (0.7 × 388) + (0.3 × 1800) = 811.6
  Score backward: (0.7 × 466) + (0.3 × 1200) = 686.2
  
  ✅ BACKWARD wins (lower score, closer to runway)

Taxiway W (last):
  W first → RWY14: 50m
  W last → RWY14: 2000m
  
  ✅ BACKWARD (toward first, which is closer to runway)
```

**Result:** Same taxiway route, but aircraft goes in OPPOSITE directions based on destination runway!

## Logging Output

### With Runway Location

```
[ENY102] === TAXI CLEARANCE ISSUED ===
[ENY102] Destination: runway 14
[ENY102] Via taxiways: ['F', 'W']

[ENY102] Found runway 14 at (37.255134, -93.400407)

[ENY102] Processing taxiway 1/2: F
[ENY102] Distance from F first to W: 0.004204° (~466.6m)
[ENY102] Distance from F last to W: 0.003500° (~388.5m)
[ENY102] Distance from F first to runway: 0.010800° (~1198.8m)
[ENY102] Distance from F last to runway: 0.016200° (~1798.2m)
[ENY102] Going BACKWARD on F toward W (score: 0.006562)

[ENY102] Processing taxiway 2/2: W
[ENY102] Distance from W first to runway: 0.000450° (~50.0m)
[ENY102] Distance from W last to runway: 0.018000° (~1998.0m)
[ENY102] Last taxiway - going BACKWARD toward runway runway 14
```

### Without Runway Location (Fallback)

```
[ENY104] === TAXI CLEARANCE ISSUED ===
[ENY104] Destination: taxiway
[ENY104] Via taxiways: ['E', 'U']

[ENY104] Processing taxiway 1/2: E
[ENY104] Distance from E first to U: 0.005319° (~590.4m)
[ENY104] Distance from E last to U: 0.000076° (~8.4m)
[ENY104] Going FORWARD on E toward U (score: 0.000076)

[ENY104] Last taxiway - adding from closest to end
```

## Benefits

### ✅ Runway-Specific Routing
- Same taxiways, different directions based on runway
- Aircraft always move toward their destination
- No more wrong-way taxi

### ✅ Intelligent Scoring
- Balances immediate connection with ultimate goal
- 70/30 weight prevents local optima
- Considers both next taxiway and runway

### ✅ Fallback Support
- Works without runway_definition (uses old logic)
- Graceful degradation for non-runway destinations
- Backward compatible

### ✅ Real-World Accuracy
- Matches how real ATC routes aircraft
- Different routes for different runways
- Realistic traffic flow

## Configuration Guide

### Adding Runway Definitions

1. **Find runway threshold coordinates** (use GeoJSON or charts)
2. **Add to scenarios.json**:

```json
"runway_definition": [ 
  {"name": "02", "location": [{"x": 37.235852, "y": -93.389149}]}, 
  {"name": "20", "location": [{"x": 37.253510, "y": -93.380312}]},
  {"name": "14", "location": [{"x": 37.255134, "y": -93.400407}]},
  {"name": "32", "location": [{"x": 37.238005, "y": -93.383548}]}
]
```

3. **Use in taxi commands**:
```
102 t02eu    → Routes to runway 02
102 t14fw    → Routes to runway 14
102 t20ua    → Routes to runway 20
102 t32wm    → Routes to runway 32
```

### Adjusting Weights

In `_get_taxiway_waypoints_toward_destination`:

```python
# Current: 70% next taxiway, 30% runway
score_forward = (0.7 * dist_last_to_next) + (0.3 * dist_last_to_runway)

# More runway emphasis (50/50):
score_forward = (0.5 * dist_last_to_next) + (0.5 * dist_last_to_runway)

# Less runway emphasis (90/10):
score_forward = (0.9 * dist_last_to_next) + (0.1 * dist_last_to_runway)
```

## Technical Details

### Runway Location Extraction

```python
def _get_runway_location(self):
    # Check destination format
    if not self.taxi_destination.lower().startswith("runway"):
        return None
    
    # Extract number: "runway 02" → "02"
    runway_number = self.taxi_destination.split()[1]
    
    # Find in runway_definition
    runway_definitions = self.airport_data.get('runway_definition', [])
    for runway_def in runway_definitions:
        if runway_def.get('name') == runway_number:
            location = runway_def.get('location', [])[0]
            return (location['x'], location['y'])
    
    return None
```

### Scoring Algorithm

```python
# For intermediate taxiways
if runway_location:
    dist_first_to_runway = distance(first_point, runway_location)
    dist_last_to_runway = distance(last_point, runway_location)
    
    score_forward = (0.7 * dist_last_to_next) + (0.3 * dist_last_to_runway)
    score_backward = (0.7 * dist_first_to_next) + (0.3 * dist_first_to_runway)
    
    # Choose lower score
    if score_forward < score_backward:
        return FORWARD
    else:
        return BACKWARD
```

### Last Taxiway Logic

```python
# For last taxiway, use direct runway distance
if current_idx == len(via_taxiways) - 1 and runway_location:
    dist_first_to_runway = distance(first_point, runway_location)
    dist_last_to_runway = distance(last_point, runway_location)
    
    # Choose end closer to runway
    if dist_last_to_runway < dist_first_to_runway:
        return FORWARD
    else:
        return BACKWARD
```

## Example Routes

### KSGF Runway 02 (South)

```
Location: (37.235852, -93.389149)

From Gate 1 via EU:
  E: FORWARD (toward U and RWY02)
  U: FORWARD (toward RWY02)
  
From Gate 6 via FWU:
  F: FORWARD (toward W)
  W: FORWARD (toward U and RWY02)
  U: FORWARD (toward RWY02)
```

### KSGF Runway 14 (Northwest)

```
Location: (37.255134, -93.400407)

From Gate 1 via FW:
  F: BACKWARD (toward W and RWY14)
  W: BACKWARD (toward RWY14)
  
From Gate 8 via FW:
  F: FORWARD (toward W)
  W: BACKWARD (toward RWY14)
```

## Troubleshooting

### Runway Not Found

**Log:**
```
[ENY102] Runway 14 location not found in runway_definition
```

**Fix:** Add runway to `runway_definition` in scenarios.json

### Wrong Direction Despite Runway

**Check:**
1. Verify runway coordinates are correct
2. Check weight balance (70/30 default)
3. Ensure runway name matches exactly

### Aircraft Still Going Wrong Way

**Debug:**
```
[ENY102] Distance from F first to runway: X
[ENY102] Distance from F last to runway: Y
[ENY102] Going FORWARD/BACKWARD (score: Z)
```

Verify scores make sense for the geometry.

## Summary

**New Runway-Aware System:**
1. ✅ Reads runway locations from `runway_definition`
2. ✅ Uses weighted scoring (70% next, 30% runway)
3. ✅ Makes runway-specific direction decisions
4. ✅ Works for all runways at any airport
5. ✅ Fallback to old logic if no runway data

**Result:** Aircraft now intelligently route based on their destination runway, choosing the correct direction even on the same taxiways! 🛫✨
