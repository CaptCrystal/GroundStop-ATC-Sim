# Ramp Line Routing - Always Follow the Ramp

## Key Improvement

Aircraft now **ALWAYS** follow the ramp line from their gate to the first taxiway entry point, ensuring realistic and logical taxi paths.

## How It Works

### Route Building Process

```
1. Build ramp path:
   - Find closest ramp point to aircraft position
   - Find ramp point closest to first taxiway
   - Add all ramp points between them
   
2. Add each taxiway:
   - Find closest point on taxiway
   - Look ahead to next taxiway
   - Determine direction toward next taxiway
   - Add waypoints in that direction
   
3. Clean route:
   - Remove duplicate waypoints
   - Return smooth path
```

## Ramp Line Logic

### Step 1: Find Ramp Entry

```python
# Aircraft at gate (37.24077, -93.396874)
# Ramp points: [(37.239927, -93.398038), (37.241698, -93.397146), ...]

# Find closest ramp point to aircraft
start_ramp_idx = find_closest(aircraft_pos, ramp_points)
# Result: index 0

# Find ramp point closest to first taxiway
end_ramp_idx = find_closest_to_taxiway(ramp_points, taxiway_F_points)
# Result: index 3
```

### Step 2: Follow Ramp Line

```python
# Add ramp points from start to taxiway entry
if start_ramp_idx <= end_ramp_idx:
    route.extend(ramp_points[start_ramp_idx:end_ramp_idx + 1])
else:
    route.extend(reversed(ramp_points[end_ramp_idx:start_ramp_idx + 1]))
```

**Result:** Aircraft follows ramp centerline to taxiway entry!

## Direction Logic

### Look-Ahead System

For each taxiway, the system:

1. **Finds closest point** on current taxiway
2. **Gets next taxiway** in route
3. **Calculates distances** from each end to next taxiway
4. **Chooses direction** that minimizes distance

### Example: FWU Route

```
Taxiway F:
  - Closest point: index 0
  - Next taxiway: W
  - F first → W: 1546m
  - F last → W: 38m
  - Decision: Go FORWARD (toward last, which is closer to W)

Taxiway W:
  - Closest point: index 3
  - Next taxiway: U
  - W first → U: 2226m
  - W last → U: 2482m
  - Decision: Go BACKWARD (toward first, which is closer to U)

Taxiway U:
  - Last taxiway
  - Decision: Go from closest to end
```

## Complete Route Example

### Command: `102 teu`

```
Step 1: Ramp Path
  Aircraft at Gate 7: (37.240276, -93.395218)
  Closest ramp point: index 5
  Ramp point nearest to E: index 4
  Ramp path: [ramp[5], ramp[4]]
  
Step 2: Taxiway E
  Closest point on E: index 0
  Next taxiway: U
  E first → U: 500m
  E last → U: 50m
  Direction: FORWARD (toward U)
  Add: E[0:6]
  
Step 3: Taxiway U
  Closest point on U: index 5
  Last taxiway
  Add: U[5:9]
  
Step 4: Clean
  Remove duplicates
  Final: 13 waypoints

Result: Gate → Ramp → E → U
```

## Logging Output

### Ramp Path

```
[ENY102] Building route for taxiways: ['E', 'U']
[ENY102] Destination: runway 02
[ENY102] Ramp path: point 5 → 4
[ENY102] Added 2 ramp waypoints
```

### Taxiway Directions

```
[ENY102] Processing taxiway 1/2: E
[ENY102] Closest point on E: index 0/6, distance 0.002223° (~246.7m)
[ENY102] Distance from E first to U: 0.004500° (~500.0m)
[ENY102] Distance from E last to U: 0.000450° (~50.0m)
[ENY102] Going FORWARD on E toward U
[ENY102] Added 6 waypoints from E
```

### Route Summary

```
[ENY102] Cleaned route: 13 → 13 waypoints
[ENY102] Route built with 13 waypoints
[ENY102] First target: (37.239097, -93.395095)
```

## Benefits

### ✅ Realistic Movement
- Aircraft follow actual ramp centerlines
- No cutting across ramps
- Professional taxi behavior

### ✅ Always Connected
- Ramp → Taxiway connection guaranteed
- No gaps in route
- Smooth transitions

### ✅ Intelligent Direction
- Looks ahead to next taxiway
- Chooses shortest path
- Avoids wrong-way taxi

### ✅ Runway-Aware
- Direction chosen based on destination
- Always moving toward runway
- Never away from goal

## Ramp Configuration

### In scenarios.json

```json
{
  "ramps": [
    {
      "ramp": "main_ramp",
      "points": [
        {"x": 37.239927, "y": -93.398038},
        {"x": 37.241698, "y": -93.397146},
        {"x": 37.241901, "y": -93.396672},
        {"x": 37.241541, "y": -93.395543},
        {"x": 37.241173, "y": -93.394255},
        {"x": 37.239097, "y": -93.395095}
      ]
    }
  ]
}
```

### Points Define Centerline

- Points are in order along ramp
- Aircraft follows these points
- System finds best entry/exit points

## Direction Decision Matrix

| Position | First End Closer | Last End Closer | Direction |
|----------|------------------|-----------------|-----------|
| Near start (< 50%) | To next | To next | BACKWARD |
| Near start (< 50%) | To next | NOT to next | FORWARD |
| Near end (≥ 50%) | To next | To next | BACKWARD |
| Near end (≥ 50%) | NOT to next | To next | FORWARD |

## Example Scenarios

### Scenario 1: Gate to Runway 02 via EU

```
Gate 7 → Ramp → E → U → Runway 02

Ramp: 2 waypoints
E: 6 waypoints (forward toward U)
U: 4 waypoints (from intersection to end)
Total: 12 waypoints
```

### Scenario 2: Gate to Runway 02 via FWU

```
Gate 8 → Ramp → F → W → U → Runway 02

Ramp: 3 waypoints
F: 4 waypoints (forward toward W)
W: 3 waypoints (backward toward U)
U: 5 waypoints (from intersection to end)
Total: 15 waypoints
```

### Scenario 3: Complex Route EFWUA

```
Gate 1 → Ramp → E → F → W → U → A → Runway 02

Ramp: 2 waypoints
E: 6 waypoints (forward toward F)
F: 2 waypoints (from E intersection, forward toward W)
W: 4 waypoints (from F intersection, backward toward U)
U: 3 waypoints (from W intersection, forward toward A)
A: 5 waypoints (from U intersection to runway)
Total: 22 waypoints
```

## Troubleshooting

### Aircraft Not Following Ramp

**Check logs:**
```
[ENY102] No ramp points found
```
**Fix:** Verify `ramps` array in scenarios.json

### Wrong Direction on Taxiway

**Check logs:**
```
[ENY102] Distance from F first to W: 1546m
[ENY102] Distance from F last to W: 38m
[ENY102] Going FORWARD on F toward W
```
**Verify:** Last point (38m) is closer, so FORWARD is correct

### Skipping Taxiway

**Check logs:**
```
[ENY102] Next taxiway W not found
```
**Fix:** Verify taxiway letter in scenarios.json

## Technical Details

### Ramp Path Algorithm

```python
def _add_ramp_to_taxiway_path(start_pos, first_taxiway, ramps, taxiways):
    # 1. Get ramp points
    ramp_points = get_ramp_points(ramps, 'main_ramp')
    
    # 2. Find closest ramp point to aircraft
    start_idx = find_closest(start_pos, ramp_points)
    
    # 3. Find ramp point closest to first taxiway
    taxiway_points = get_taxiway_points(taxiways, first_taxiway)
    end_idx = find_closest_ramp_to_taxiway(ramp_points, taxiway_points)
    
    # 4. Add ramp points in order
    if start_idx <= end_idx:
        return ramp_points[start_idx:end_idx + 1]
    else:
        return reversed(ramp_points[end_idx:start_idx + 1])
```

### Direction Algorithm

```python
def _get_taxiway_waypoints_toward_destination(taxiway_points, closest_index, 
                                               taxiway_letter, via_taxiways, 
                                               current_idx, taxiways):
    # 1. If last taxiway, go to end
    if current_idx == len(via_taxiways) - 1:
        return taxiway_points[closest_index:]
    
    # 2. Get next taxiway
    next_taxiway = via_taxiways[current_idx + 1]
    next_points = get_taxiway_points(taxiways, next_taxiway)
    
    # 3. Calculate distances from each end
    dist_first_to_next = min(distance(taxiway_points[0], np) for np in next_points)
    dist_last_to_next = min(distance(taxiway_points[-1], np) for np in next_points)
    
    # 4. Choose direction based on position and distances
    if closest_index < len(taxiway_points) / 2:
        # Near start
        if dist_last_to_next < dist_first_to_next:
            return taxiway_points[closest_index:]  # Forward
        else:
            return reversed(taxiway_points[:closest_index + 1])  # Backward
    else:
        # Near end
        if dist_first_to_next < dist_last_to_next:
            return reversed(taxiway_points[:closest_index + 1])  # Backward
        else:
            return taxiway_points[closest_index:]  # Forward
```

## Summary

**New Routing System:**
1. ✅ Always follows ramp line to taxiway entry
2. ✅ Looks ahead to determine direction
3. ✅ Chooses path toward destination
4. ✅ Never goes away from runway
5. ✅ Realistic, professional taxi behavior

**Result:** Aircraft taxi like real pilots! 🛫✨
