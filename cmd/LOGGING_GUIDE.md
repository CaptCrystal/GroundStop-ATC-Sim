# Aircraft Debug Logging Guide

## Overview
Comprehensive logging system tracks all aircraft behavior, state changes, pathfinding decisions, and intersection detection in real-time.

## Log Output

### File Location
**`aircraft_debug.log`** - Created in the project root directory

### Console Output
All logs also print to console for real-time monitoring

## Log Levels

### INFO
- Major state changes
- Command execution
- Route building completion
- Intersection detection
- Direction choices

### DEBUG
- Detailed position data
- Distance calculations
- Waypoint progression
- Route building steps
- Segment analysis

### WARNING
- Missing data
- Failed lookups
- Unexpected conditions

## Log Format

```
YYYY-MM-DD HH:MM:SS,mmm - Aircraft - LEVEL - [CALLSIGN] Message
```

**Example:**
```
2025-11-10 08:51:23,456 - Aircraft - INFO - [ENY100] === TAXI CLEARANCE ISSUED ===
```

## What Gets Logged

### 1. Aircraft Creation
```
[ENY100] Aircraft created at gate Gate 7
[ENY100] Position: (37.239410, -93.395600), Heading: 298°
[ENY100] Type: CRJ9, Airline: ENY
```

### 2. Pushback
```
[ENY100] Pushback target: (37.240123, -93.395789)
[ENY100] Distance to ramp: 0.000823° (~91.5m)
[ENY100] Pushback complete, now HOLDING at ramp
[ENY100] Final position: (37.240125, -93.395791)
```

### 3. Taxi Clearance
```
[ENY100] === TAXI CLEARANCE ISSUED ===
[ENY100] Destination: runway 02
[ENY100] Via taxiways: ['U', 'A']
[ENY100] Current position: (37.240125, -93.395791)
[ENY100] Building taxi route...
```

### 4. Route Building - First Taxiway
```
[ENY100] Processing taxiway 1/2: U
[ENY100] First taxiway - finding entry point
[ENY100] Distance to first point: 0.013125° (~1458.9m)
[ENY100] Distance to last point: 0.004567° (~507.0m)
[ENY100] Reversed taxiway U (closer to end)
[ENY100] Entry point: index 3/9, distance 0.000234° (~26.0m)
[ENY100] Added 6 waypoints from U
```

### 5. Route Building - Subsequent Taxiways
```
[ENY100] Processing taxiway 2/2: A
[ENY100] Subsequent taxiway - connecting to previous route
[ENY100] Last route point: (37.235838, -93.389124)
[ENY100] Distance to A first: 0.008901° (~988.9m)
[ENY100] Distance to A last: 0.002345° (~260.5m)
[ENY100] Reversed taxiway A for better connection
[ENY100] Added 5 waypoints from A
```

### 6. Route Completion
```
[ENY100] Route built with 11 waypoints
[ENY100] First target: (37.253250, -93.380417)
```

### 7. Waypoint Progression
```
[ENY100] Reached waypoint (37.253250, -93.380417)
[ENY100] Next waypoint: (37.253612, -93.380961), 10 remaining
[ENY100] Reached waypoint (37.253612, -93.380961)
[ENY100] Next waypoint: (37.253746, -93.381400), 9 remaining
```

### 8. Intersection Detection
```
[ENY100] *** INTERSECTION DETECTED ***
[ENY100] Crossed taxiway F segment 2
[ENY100] Distance to centerline: 0.000045° (~5.0m)
[ENY100] Segment: (37.243074, -93.394762) → (37.244841, -93.392538)
[ENY100] Aircraft moved: (37.243070, -93.394765) → (37.243075, -93.394760)
```

### 9. Taxiway Switching
```
[ENY100] Switching to taxiway F
[ENY100] Taxiway F has 4 points
[ENY100] Crossed at segment index 2
[ENY100] Next target in route: (37.235838, -93.389124)
[ENY100] Forward direction distance: 0.008234° (~914.6m)
[ENY100] Backward direction distance: 0.003456° (~383.8m)
[ENY100] Chose BACKWARD direction on F
[ENY100] Adding 3 waypoints (reversed)
[ENY100] Route updated: 3 new + 5 old = 8 total waypoints
[ENY100] New target: (37.244841, -93.392538)
```

### 10. Route Completion
```
[ENY100] Route complete, now HOLDING
[ENY100] Final position: (37.246360, -93.389585)
```

## Key Metrics Logged

### Distance Calculations
- **Degrees**: Raw coordinate difference
- **Meters**: Approximate real-world distance (degrees × 111,000)

### Waypoint Counts
- Points added per taxiway
- Total route length
- Remaining waypoints

### Direction Decisions
- Distance to forward direction
- Distance to backward direction
- Chosen direction with reasoning

### Intersection Detection
- Distance to taxiway centerline
- Segment coordinates
- Aircraft movement vector

## Reading the Logs

### Successful Taxi Example
```
[ENY100] === TAXI CLEARANCE ISSUED ===
[ENY100] Via taxiways: ['U', 'F']
[ENY100] Building taxi route...
[ENY100] Entry point: index 3/9, distance 0.000234° (~26.0m)
[ENY100] Added 6 waypoints from U
[ENY100] Added 4 waypoints from F
[ENY100] Route built with 10 waypoints
[ENY100] First target: (37.253250, -93.380417)
... (waypoint progression)
[ENY100] *** INTERSECTION DETECTED ***
[ENY100] Crossed taxiway F segment 2
[ENY100] Chose BACKWARD direction on F
[ENY100] Route updated: 3 new + 0 old = 3 total waypoints
... (more waypoint progression)
[ENY100] Route complete, now HOLDING
```

### Problem Diagnosis

**Aircraft not moving?**
```
[ENY100] Route built with 0 waypoints  ← No route!
[ENY100] No route built!
```

**Wrong direction?**
```
[ENY100] Distance to first point: 0.001234° (~137.0m)
[ENY100] Distance to last point: 0.008901° (~988.9m)
[ENY100] Reversed taxiway U (closer to end)  ← Check if this is correct
```

**Not detecting intersection?**
```
[ENY100] Distance to centerline: 0.000234° (~26.0m)  ← Too far! (threshold is 0.00010°)
```

**Intersection detected but not switching?**
```
[ENY100] *** INTERSECTION DETECTED ***
[ENY100] Could not find crossed segment in taxiway F  ← Segment mismatch
```

## Debugging Workflow

### 1. Check Aircraft Creation
Look for:
```
[ENY100] Aircraft created at gate Gate 7
[ENY100] Position: ...
```

### 2. Check Pushback
Look for:
```
[ENY100] Pushback target: ...
[ENY100] Pushback complete, now HOLDING at ramp
```

### 3. Check Taxi Clearance
Look for:
```
[ENY100] === TAXI CLEARANCE ISSUED ===
[ENY100] Via taxiways: ['U', 'A']
```

### 4. Check Route Building
Look for:
```
[ENY100] Entry point: index X/Y, distance Z
[ENY100] Added N waypoints from U
[ENY100] Route built with N waypoints
```

### 5. Check Movement
Look for:
```
[ENY100] Reached waypoint ...
[ENY100] Next waypoint: ..., N remaining
```

### 6. Check Intersections
Look for:
```
[ENY100] *** INTERSECTION DETECTED ***
[ENY100] Crossed taxiway F segment N
```

### 7. Check Switching
Look for:
```
[ENY100] Switching to taxiway F
[ENY100] Chose FORWARD/BACKWARD direction on F
[ENY100] Route updated: ...
```

## Common Issues

### Issue: No Route Built
**Log:**
```
[ENY100] Route built with 0 waypoints
```
**Cause:** Taxiway not found or no points
**Fix:** Check taxiway letters match scenarios.json

### Issue: Aircraft Goes Wrong Way
**Log:**
```
[ENY100] Reversed taxiway U (closer to end)
[ENY100] Entry point: index 8/9, distance 0.000123°
```
**Cause:** Entry point at wrong end
**Fix:** Check taxiway point order in scenarios.json

### Issue: Intersection Not Detected
**Log:**
```
(No intersection logs)
```
**Cause:** Distance > 0.00010° (10m threshold)
**Fix:** Aircraft not close enough to centerline

### Issue: Wrong Direction After Intersection
**Log:**
```
[ENY100] Forward direction distance: 0.001234°
[ENY100] Backward direction distance: 0.008901°
[ENY100] Chose FORWARD direction on F
```
**Cause:** Logic chose closer direction
**Fix:** Check if next target is correct

## Performance Monitoring

### Waypoint Efficiency
```
[ENY100] Route built with 11 waypoints
[ENY100] Reached waypoint ... (11 times)
[ENY100] Route complete
```
**Good:** All waypoints reached

### Intersection Efficiency
```
[ENY100] *** INTERSECTION DETECTED ***
[ENY100] Switching to taxiway F
[ENY100] Route updated: 3 new + 5 old = 8 total waypoints
```
**Good:** Smooth transition, route extended

## Tips

1. **Filter by callsign**: Search log for `[ENY100]` to track one aircraft
2. **Look for patterns**: Multiple intersections should show smooth transitions
3. **Check distances**: Should decrease as aircraft approaches waypoints
4. **Verify directions**: Forward/backward choices should make sense
5. **Monitor route length**: Should decrease as waypoints are reached

## Example Full Session

```
2025-11-10 08:51:23,456 - Aircraft - INFO - [ENY100] Aircraft created at gate Gate 7
2025-11-10 08:51:23,457 - Aircraft - DEBUG - [ENY100] Position: (37.239410, -93.395600), Heading: 298°
2025-11-10 08:51:30,123 - Aircraft - INFO - [ENY100] Pushback target: (37.240123, -93.395789)
2025-11-10 08:51:38,456 - Aircraft - INFO - [ENY100] Pushback complete, now HOLDING at ramp
2025-11-10 08:51:45,789 - Aircraft - INFO - [ENY100] === TAXI CLEARANCE ISSUED ===
2025-11-10 08:51:45,790 - Aircraft - INFO - [ENY100] Via taxiways: ['U', 'F']
2025-11-10 08:51:45,791 - Aircraft - INFO - [ENY100] Building taxi route...
2025-11-10 08:51:45,792 - Aircraft - INFO - [ENY100] Entry point: index 3/9, distance 0.000234° (~26.0m)
2025-11-10 08:51:45,793 - Aircraft - INFO - [ENY100] Route built with 10 waypoints
2025-11-10 08:51:46,123 - Aircraft - DEBUG - [ENY100] Reached waypoint (37.253250, -93.380417)
2025-11-10 08:51:52,456 - Aircraft - INFO - [ENY100] *** INTERSECTION DETECTED ***
2025-11-10 08:51:52,457 - Aircraft - INFO - [ENY100] Crossed taxiway F segment 2
2025-11-10 08:51:52,458 - Aircraft - INFO - [ENY100] Switching to taxiway F
2025-11-10 08:51:52,459 - Aircraft - INFO - [ENY100] Chose BACKWARD direction on F
2025-11-10 08:51:52,460 - Aircraft - INFO - [ENY100] Route updated: 3 new + 0 old = 3 total waypoints
2025-11-10 08:51:58,789 - Aircraft - INFO - [ENY100] Route complete, now HOLDING
```

## Log File Management

### File Location
- **Path**: `aircraft_debug.log` in project root
- **Mode**: Write (overwrites on each run)
- **Encoding**: UTF-8

### File Size
- Typical: 10-50 KB per minute of simulation
- Large airports: Up to 100 KB per minute
- Recommend clearing between sessions

### Viewing
- **Text editor**: Any editor (VSCode, Notepad++, etc.)
- **Tail**: `Get-Content aircraft_debug.log -Wait` (PowerShell)
- **Search**: Use editor's find function for callsigns
