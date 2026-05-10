# Dynamic Intersection Detection

## Problem Solved

Aircraft were passing through taxiway intersections without turning, even when the next taxiway in their route crossed their current path. The pre-built route didn't account for taxiways that intersect without sharing exact points.

## Solution: Real-Time Intersection Detection

The system now **continuously checks** during taxi movement if the aircraft is approaching the next taxiway in the route, and **dynamically switches** when an intersection is detected.

## How It Works

### 1. Continuous Monitoring

During every taxi update:
```python
def _update_taxi(self, dt: float):
    # Check for taxiway intersections during movement
    if hasattr(self, 'taxi_via') and self.taxi_via and self.airport_data:
        self._check_and_switch_taxiway()
```

### 2. Intersection Detection Logic

```python
def _check_and_switch_taxiway(self):
    # Get next taxiway we should turn onto
    next_taxiway = taxi_via[current_taxiway_index + 1]
    
    # Check distance to ALL points on next taxiway
    min_dist_to_next = min(distance(current_pos, point) for point in next_taxiway_points)
    
    # If within 50m, we're at the intersection!
    if min_dist_to_next < 0.00045:  # ~50m
        # SWITCH TO NEXT TAXIWAY
        rebuild_route_from_here()
```

### 3. Route Rebuilding

When intersection detected:
```
1. Find closest point on next taxiway
2. Increment current_taxiway_index
3. Get remaining taxiways in route
4. Build new route from current position
5. Update target to first waypoint of new route
```

## Example: FWU Route

### Initial Route
```
Command: 100 tfwu
Route: Gate → Ramp → F → W → U

Initial build:
  Ramp: 4 waypoints
  F: 4 waypoints (toward W)
  W: 3 waypoints (toward U)
  U: 4 waypoints
  Total: 15 waypoints
```

### During Taxi on F

```
Aircraft taxiing on F...
  Current position: (37.243074, -93.394762)
  Current taxiway index: 0 (F)
  Next taxiway: W
  
Checking intersection...
  Distance to W point 0: 466m
  Distance to W point 1: 420m
  Distance to W point 2: 390m
  Distance to W point 3: 388m ← CLOSEST
  
  388m > 50m threshold → Keep going on F
```

### Intersection Detected!

```
Aircraft continues on F...
  Current position: (37.244841, -93.392538)
  
Checking intersection...
  Distance to W point 3: 42m ← UNDER THRESHOLD!
  
🔄 INTERSECTION DETECTED! Switching to taxiway W
  
Actions:
  1. Find closest point on W: index 3
  2. Increment taxiway index: 0 → 1
  3. Remaining taxiways: ['W', 'U']
  4. Rebuild route from W[3] toward U
  5. New route: 7 waypoints
  6. Update target: W[3]
```

## Logging Output

### Normal Taxi (No Intersection Yet)
```
[SKW100] Reached waypoint (37.241698, -93.397146)
[SKW100] Next waypoint: (37.241901, -93.396672), 11 remaining
```

### Intersection Detected
```
[SKW100] 🔄 INTERSECTION DETECTED! Switching to taxiway W
[SKW100] Distance to W: 0.000380° (~42.2m)
[SKW100] Rebuilding route from W for: ['W', 'U']
[SKW100] Going FORWARD on W toward U
[SKW100] Added 3 waypoints from W
[SKW100] Last taxiway - adding from closest to end
[SKW100] Added 4 waypoints from U
[SKW100] New route: 7 waypoints, next target: (37.244841, -93.392538)
```

## Key Features

### ✅ Proximity-Based Detection
- Checks distance to **ALL points** on next taxiway
- Uses 50m threshold (~0.00045°)
- Works even if taxiways don't share exact points

### ✅ Dynamic Route Rebuilding
- Doesn't rely on pre-built route alone
- Adapts to actual aircraft position
- Rebuilds remaining route from intersection

### ✅ Direction Intelligence
- Still uses look-ahead logic for direction
- Ensures aircraft goes toward destination
- Never backtracks unnecessarily

### ✅ Taxiway Tracking
- `current_taxiway_index` tracks progress
- Prevents re-detecting same intersection
- Resets on new taxi clearance

## Technical Details

### Intersection Threshold

```python
intersection_threshold = 0.00045  # degrees
# At 37° latitude: ~50 meters
# Calculation: 0.00045° × 111,000m/° × cos(37°) ≈ 40-50m
```

### Distance Calculation

```python
def _distance(pos1, pos2):
    lat1, lon1 = pos1
    lat2, lon2 = pos2
    return math.sqrt((lat2 - lat1)**2 + (lon2 - lon1)**2)
```

### Taxiway Index Management

```python
# On taxi clearance
self.current_taxiway_index = 0  # Start at first taxiway

# On intersection detection
self.current_taxiway_index += 1  # Move to next taxiway

# Check if more taxiways remain
if self.current_taxiway_index >= len(self.taxi_via) - 1:
    return  # No more switches needed
```

## Example Scenarios

### Scenario 1: Simple Turn (FW)

```
Route: F → W
Position on F: (37.244841, -93.392538)

Check distance to W:
  Min distance: 42m
  
✅ INTERSECTION! Switch to W
  Rebuild: ['W']
  New route: 3 waypoints on W
```

### Scenario 2: Multi-Turn (FWU)

```
Route: F → W → U

On F:
  Check W: 42m → SWITCH to W
  Index: 0 → 1
  Remaining: ['W', 'U']
  
On W:
  Check U: 8m → SWITCH to U
  Index: 1 → 2
  Remaining: ['U']
  
On U:
  No more taxiways
  Continue to end
```

### Scenario 3: Long Route (EFWUA)

```
Route: E → F → W → U → A

Intersections detected:
  1. E → F at (37.241904, -93.393169)
  2. F → W at (37.244841, -93.392538)
  3. W → U at (37.240964, -93.390184)
  4. U → A at (37.236611, -93.390969)
  
Each time:
  - Detect proximity
  - Switch taxiway
  - Rebuild remaining route
  - Continue toward runway
```

## Benefits

### 🎯 Accurate Turns
- Aircraft turn at actual intersections
- No overshooting or missing turns
- Works with any taxiway geometry

### 🔄 Dynamic Adaptation
- Responds to actual position
- Not locked into pre-built route
- Handles unexpected situations

### 🧠 Intelligent Routing
- Still uses direction logic
- Always moves toward destination
- Combines pre-planning with real-time adjustment

### 📊 Clear Logging
- Shows when intersections detected
- Logs distance to next taxiway
- Tracks route rebuilding

## Configuration

### Adjust Intersection Sensitivity

```python
# In _check_and_switch_taxiway():
intersection_threshold = 0.00045  # ~50m

# Tighter detection (30m):
intersection_threshold = 0.00027

# Looser detection (100m):
intersection_threshold = 0.00090
```

### Disable Intersection Detection

```python
# In _update_taxi():
# Comment out this line:
# self._check_and_switch_taxiway()
```

## Troubleshooting

### Aircraft Not Turning

**Check logs:**
```
[SKW100] Distance to W: 0.000380° (~42.2m)
```

If distance never gets below 50m, taxiways may not actually intersect.

### Aircraft Turning Too Early

**Reduce threshold:**
```python
intersection_threshold = 0.00027  # 30m instead of 50m
```

### Aircraft Turning Too Late

**Increase threshold:**
```python
intersection_threshold = 0.00090  # 100m instead of 50m
```

### Multiple Switches at Same Intersection

Check that `current_taxiway_index` is incrementing:
```
[SKW100] Rebuilding route from W for: ['W', 'U']
```

Should only happen once per intersection.

## Summary

**New System:**
1. ✅ Continuously monitors position during taxi
2. ✅ Detects proximity to next taxiway (50m threshold)
3. ✅ Dynamically switches and rebuilds route
4. ✅ Works with any taxiway geometry
5. ✅ Combines pre-planning with real-time adaptation

**Result:** Aircraft now turn at intersections even when taxiways don't share exact points! 🛫✨
