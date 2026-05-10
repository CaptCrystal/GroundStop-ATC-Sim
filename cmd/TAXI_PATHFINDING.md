# Taxi Pathfinding System

## Overview
Aircraft now use actual taxiway data to follow realistic paths! Pushback moves to the ramp line, and taxi commands build routes from taxiway coordinates.

## Pushback to Ramp Line

### How It Works
1. **Aircraft starts at gate** - Parked at gate position
2. **Pushback clearance issued** - `100 pa`
3. **Find nearest ramp point** - Searches main_ramp points
4. **Move to ramp** - Aircraft moves to nearest point on ramp line
5. **Stop and hold** - Transitions to HOLDING when reached

### Ramp Detection
```python
def _find_nearest_ramp_point(self):
    # Gets main_ramp from airport data
    # Finds closest point to current position
    # Returns (lat, lon) of nearest ramp point
```

### Fallback
If no ramp data found:
- Uses simple backwards movement
- Pushes back ~50 meters from gate
- Based on gate heading

## Taxi Pathfinding

### Command Format
`[flight_number] t[destination][via_letters]`

**Examples:**
- `100 t02ua` - Taxi to runway 02 via taxiways U and A
- `100 t02uaf` - Taxi to runway 02 via U, A, and F
- `100 tgate5u` - Taxi to gate 5 via U

### Route Building Process

1. **Parse via taxiways** - Extract letters from command (e.g., "ua" → ["U", "A"])
2. **Look up taxiway data** - Find each taxiway in scenarios.json
3. **Extract waypoints** - Get all points from each taxiway
4. **Build route** - Concatenate all waypoints in order
5. **Start movement** - Aircraft follows waypoints

### Taxiway Data Structure
From `scenarios.json`:
```json
{
  "taxiway": "U",
  "points": [
    {"x": 37.253250, "y": -93.380417},
    {"x": 37.253612, "y": -93.380961},
    {"x": 37.253746, "y": -93.381400},
    ...
  ]
}
```

### Route Following
```python
def _update_taxi(self, dt):
    # Move towards current target waypoint
    # When reached, pop next waypoint from route
    # Continue until route is empty
    # Transition to HOLDING when complete
```

## Taxiway Network

### Available Taxiways (KSGF)
- **A** - Runway 02/20 connector
- **B** - Short connector
- **C** - Parallel to runway
- **D** - Main parallel taxiway
- **E** - Apron connector
- **F** - Apron to runway
- **G** - Short segment
- **H** - Connector
- **J** - Short segment
- **M** - Runway connector
- **N** - Main perimeter taxiway
- **R** - Short connector
- **S** - Runway 14/32 connector
- **T** - Short connector
- **U** - Main apron taxiway
- **W** - Perimeter taxiway

### Taxiway Intersections
The taxiways are designed to cross each other, creating a realistic network:
- **U** crosses through the apron area
- **N** runs along the perimeter
- **D** is the main parallel taxiway
- Multiple taxiways connect to runways

## Usage Examples

### Basic Pushback and Taxi
```
> 100 pa
ENY100, pushback approved, advise ready to taxi

(Aircraft pushes to ramp line)

> 100 tu
ENY100, taxi via Uniform

(Aircraft follows taxiway U waypoints)
```

### Multi-Taxiway Route
```
> 100 t02ua
ENY100, taxi to runway 02 via Uniform, Alpha

(Aircraft follows U waypoints, then A waypoints)
```

### Complex Routing
```
> 100 t02uaf
ENY100, taxi to runway 02 via Uniform, Alpha, Foxtrot

(Aircraft follows U → A → F waypoints)
```

## Visual Feedback

### During Pushback
- **State**: "PUSHBACK"
- **Movement**: Towards ramp line
- **Heading**: Updates to face movement direction

### During Taxi
- **State**: "TAXI"
- **Movement**: Follows waypoints
- **Speed**: Up to 15 knots
- **Heading**: Updates to face next waypoint

### At Waypoints
- Aircraft smoothly transitions between waypoints
- No sharp turns (heading updates gradually)
- Stops when route complete

## Technical Details

### Coordinate System
- **Lat/Lon**: All positions in degrees
- **X = Latitude**: North/South
- **Y = Longitude**: East/West
- **Distance Threshold**: 0.00002° (~2 meters)

### Movement Speed
- **Pushback**: 0-5 knots
- **Taxi**: 0-15 knots
- **Acceleration**: 3-5 knots/second

### Waypoint Detection
```python
if distance < 0.00005:  # ~5 meters
    # Move to next waypoint
    if self.route:
        self.target_position = self.route.pop(0)
    else:
        # Route complete
        self.state = STATE_HOLDING
```

## Current Implementation

### ✅ Working Features
- Pushback to ramp line
- Taxiway lookup by letter
- Waypoint route building
- Sequential waypoint following
- Automatic state transitions
- Realistic movement speeds

### ⚠️ Limitations
- No pathfinding algorithm (uses exact via route)
- No collision detection
- No turn radius limits
- No speed control for turns
- No runway crossing logic

## Example Taxi Routes

### Gate to Runway 02
```
Gate 7 → U → A → Runway 02
Command: 100 t02ua
```

### Gate to Runway 14
```
Gate 7 → U → N → S → Runway 14
Command: 100 t14uns
```

### Around the Airport
```
Gate 7 → U → N → D → Back to apron
Command: 100 tund
```

## Testing

### Test Pushback
1. Start simulation
2. Find aircraft at gate (e.g., ENY100)
3. Issue: `100 pa`
4. Watch aircraft move to ramp line
5. Verify state changes to HOLDING

### Test Taxi
1. After pushback complete
2. Issue: `100 tu`
3. Watch aircraft follow taxiway U
4. Verify waypoints are followed
5. Verify state changes to HOLDING when complete

### Test Multi-Taxiway
1. After pushback
2. Issue: `100 t02ua`
3. Watch aircraft follow U then A
4. Verify smooth transitions
5. Verify heading updates

## Debugging

### Enable Dev Mode
Press `Shift+Ctrl+1` to see:
- Gate positions (green circles)
- Taxiway centerlines (yellow lines)
- Taxiway labels
- Aircraft positions

### Check Route
Aircraft route is stored in `aircraft.route`:
```python
print(f"Route: {aircraft.route}")
print(f"Target: {aircraft.target_position}")
print(f"Via: {aircraft.taxi_via}")
```

### Common Issues

**Aircraft not moving after taxi command?**
- Check if via taxiways are valid
- Verify taxiway data exists in scenarios.json
- Check if route was built (print aircraft.route)

**Aircraft moving wrong direction?**
- Taxiway points may be in reverse order
- Check taxiway point sequence in scenarios.json

**Aircraft stuck at waypoint?**
- Distance threshold may be too small
- Check waypoint coordinates are valid

## Next Steps

### Phase 1: Smart Pathfinding
- [ ] A* algorithm for automatic routing
- [ ] Find shortest path between points
- [ ] Avoid obstacles

### Phase 2: Realistic Movement
- [ ] Turn radius limits
- [ ] Speed reduction for turns
- [ ] Progressive taxi (one segment at a time)

### Phase 3: Traffic Management
- [ ] Collision detection
- [ ] Auto-hold for traffic
- [ ] Runway crossing logic
- [ ] Sequencing

### Phase 4: Advanced Features
- [ ] Hold short lines
- [ ] Progressive taxi instructions
- [ ] Conditional clearances
- [ ] Runway incursion warnings

## Code Structure

### Aircraft Class
```python
class Aircraft:
    def clear_taxi(self, destination, via):
        # Build route from via taxiways
        self.route = self._build_taxi_route(via)
        self.target_position = self.route.pop(0)
        
    def _build_taxi_route(self, via_taxiways):
        # Look up each taxiway
        # Extract waypoints
        # Return concatenated list
        
    def _update_taxi(self, dt):
        # Move towards target waypoint
        # Pop next waypoint when reached
        # Stop when route empty
```

### Command Processor
```python
def cmd_taxi(self, args, cmd_name, output):
    # Parse via letters from command
    via_letters = list(cmd_part[2:].upper())
    
    # Pass to aircraft
    aircraft.clear_taxi(destination, via_letters)
```

## Configuration

### Waypoint Threshold
```python
# In Aircraft._update_taxi
if distance < 0.00005:  # ~5 meters
    # Next waypoint
```

### Ramp Threshold
```python
# In Aircraft._update_pushback
if distance < 0.00002:  # ~2 meters
    # Pushback complete
```

### Taxi Speed
```python
# In Aircraft._update_taxi
target_speed = 15  # knots
```

## Tips

1. **Use Dev Mode**: See taxiways and gates
2. **Plan Routes**: Look at taxiway layout before issuing commands
3. **Sequential Commands**: Pushback → Taxi → Hold
4. **Watch State**: State label shows current phase
5. **Zoom In**: See aircraft following waypoints closely

## Troubleshooting

**Route not building?**
- Check taxiway letters are correct (case-insensitive)
- Verify taxiway exists in scenarios.json
- Print route to debug

**Aircraft going wrong way?**
- Taxiway points define direction
- May need to reverse point order in scenarios.json

**Pushback not working?**
- Check ramp data exists
- Verify main_ramp has points
- Falls back to simple pushback if no ramp

**Aircraft stuck?**
- Check distance threshold
- Verify target position is valid
- May be at waypoint but threshold too small
