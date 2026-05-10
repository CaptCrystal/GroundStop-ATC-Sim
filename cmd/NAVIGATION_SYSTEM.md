# Airport Navigation System

## Overview

The new navigation system provides **semantic location awareness** and **intelligent pathfinding** for aircraft. Instead of blindly following waypoint lists, aircraft now understand exactly where they are and can reason about their routes.

## Key Components

### 1. **AirportGraph** (`src/core/airport_graph.py`)

Represents the entire airport surface as a navigable graph structure.

#### Features:
- **Nodes**: Represent key points (taxiway ends, runway thresholds, gates, intersections)
- **Edges**: Represent segments of taxiways, runways, and ramps with waypoints
- **A* Pathfinding**: Finds optimal routes between any two points
- **Surface Mapping**: Maps surface names to their corresponding edges

#### Key Methods:
```python
# Find nearest node to a position
node = graph.find_nearest_node(position, node_type='taxiway')

# Determine current surface
surface = graph.get_current_surface(position)  # Returns "Taxiway A", "Runway 02", etc.

# Find path with optional waypoints
path = graph.find_path(start_pos, "Runway 02", via_surfaces=["Taxiway A", "Taxiway B"])
```

### 2. **LocationAwareness** (`src/core/location_awareness.py`)

Mixin class that provides semantic location understanding to aircraft.

#### Features:
- **Real-time surface tracking**: Aircraft always know what surface they're on
- **Transition detection**: Logs when aircraft move between surfaces
- **Location queries**: Check if on specific taxiway/runway
- **Route validation**: Verify taxi clearances are achievable

#### Key Methods:
```python
# Get current location
location = aircraft.get_current_location_description()  # "on Taxiway A"

# Check surface
if aircraft.is_on_taxiway():
    print("Aircraft is on a taxiway")

# Validate clearance
is_valid, reason = aircraft.validate_taxi_clearance("runway 02", ["A", "B"])

# Get intelligent route
route = aircraft.get_route_to_surface("runway 02", via_surfaces=["A", "B"])
```

### 3. **Enhanced Aircraft Class**

Aircraft now inherits from `LocationAwareness` and uses graph-based navigation.

#### Changes:
- **Dual routing**: Uses graph-based routing when available, falls back to legacy
- **Location updates**: Continuously tracks current surface
- **Intelligent logging**: Reports location in human-readable format

## How It Works

### Graph Construction

When `AircraftManager` initializes:

1. **Parse airport data** (taxiways, runways, ramps, gates)
2. **Create nodes** at key points (ends of taxiways, runway thresholds, gates)
3. **Create edges** connecting nodes with intermediate waypoints
4. **Detect intersections** where taxiways cross
5. **Build surface mapping** for location awareness

### Location Awareness

Every update cycle:

1. **Query graph** for nearest edge to aircraft position
2. **Determine surface name** from edge metadata
3. **Detect transitions** when surface changes
4. **Log movements** for debugging and ATC awareness

### Intelligent Routing

When aircraft receives taxi clearance:

1. **Validate route** using graph pathfinding
2. **Find optimal path** through specified taxiways
3. **Generate waypoints** including all intermediate points
4. **Fallback to legacy** if graph routing fails

## Benefits

### For Aircraft
- ✅ **Know exactly where they are** ("on Taxiway A")
- ✅ **Understand instructions** better (semantic routing)
- ✅ **Detect deviations** from assigned route
- ✅ **Validate clearances** before executing

### For ATC/Simulation
- ✅ **Better logging** with surface names instead of coordinates
- ✅ **Route validation** prevents impossible clearances
- ✅ **Conflict detection** (future: check if surface occupied)
- ✅ **Realistic behavior** based on actual airport layout

### For Debugging
- ✅ **Clear position reports** ("AAY123 on Taxiway B")
- ✅ **Transition tracking** ("Transitioned from Taxiway A to Taxiway B")
- ✅ **Route visualization** (future: display graph in UI)

## Example Usage

### Aircraft Knows Its Location
```python
# Before: Aircraft only knows coordinates
print(aircraft.position)  # (37.239410, -93.395600)

# After: Aircraft knows semantic location
print(aircraft.get_current_location_description())  # "on Taxiway A"
print(aircraft.current_surface)  # "Taxiway A"
print(aircraft.is_on_taxiway())  # True
```

### Intelligent Routing
```python
# ATC: "AAY123, taxi to runway 02 via A, B"
aircraft.clear_taxi("runway 02", via=["A", "B"])

# Aircraft uses graph to find optimal path
# - Validates route is possible
# - Finds shortest path through A and B
# - Generates waypoints automatically
# - Knows when it reaches each taxiway
```

### Route Validation
```python
# Check if route is valid before issuing clearance
is_valid, reason = aircraft.validate_taxi_clearance("runway 02", ["A", "B"])
if not is_valid:
    print(f"Cannot issue clearance: {reason}")
```

## Future Enhancements

### Short-term
- [ ] **Conflict detection**: Check if surface is occupied before clearing
- [ ] **Progressive taxi**: Clear aircraft one taxiway at a time
- [ ] **Hold short automation**: Automatically hold at runway intersections

### Medium-term
- [ ] **Graph visualization**: Display navigation graph in UI
- [ ] **Dynamic routing**: Re-route around blocked taxiways
- [ ] **Traffic flow optimization**: Suggest optimal routes to avoid conflicts

### Long-term
- [ ] **Realistic taxi speeds**: Adjust speed based on surface type
- [ ] **Surface conditions**: Model wet/icy taxiways affecting movement
- [ ] **Construction closures**: Dynamically close/open surfaces

## Migration Guide

### For Existing Code

The new system is **backward compatible**. Aircraft will:
1. Try graph-based routing first
2. Fall back to legacy routing if graph unavailable
3. Continue to work with existing airport data

### Enabling Graph Navigation

Graph navigation is **automatically enabled** when:
- Airport data includes taxiways, runways, and ramps
- `AircraftManager` successfully builds the graph
- Aircraft are spawned through `AircraftManager`

### Debugging

Check logs for:
```
Airport navigation graph initialized successfully
[AAY123] Airport graph set
[AAY123] Using graph-based navigation
[AAY123] Now on Taxiway A
```

If you see:
```
Failed to initialize airport graph: [error]
[AAY123] Using legacy navigation
```

The system falls back to legacy routing.

## Technical Details

### Graph Structure

```
Node (taxiway_A_start)
  ├─ Edge → Node (taxiway_A_end)
  │   └─ Waypoints: [(lat1, lon1), (lat2, lon2), ...]
  └─ Edge → Node (taxiway_B_start) [intersection]

Node (runway_02_threshold)
  └─ Edge → Node (runway_20_threshold)
      └─ Waypoints: [runway centerline points]
```

### A* Pathfinding

- **Heuristic**: Straight-line distance to goal
- **Cost**: Actual distance along edges
- **Result**: Optimal path through graph

### Location Detection

- **Threshold**: 10 meters (~0.0001°)
- **Method**: Distance to nearest edge waypoint
- **Update**: Every simulation frame

## Performance

- **Graph construction**: ~100ms for typical airport
- **Pathfinding**: <10ms for typical route
- **Location update**: <1ms per aircraft per frame

## Conclusion

The new navigation system transforms aircraft from "dumb waypoint followers" into **intelligent agents** that understand their environment and can reason about their routes. This creates more realistic behavior and better debugging capabilities.
