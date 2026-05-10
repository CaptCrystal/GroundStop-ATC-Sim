# Aircraft Control System

## Overview
ATC commands now actually control aircraft! Issue pushback and taxi clearances to move aircraft around the airport.

## How It Works

### Command Flow
1. User types command (e.g., `100 pa`)
2. Command processor finds aircraft by flight number
3. Command validates aircraft state
4. Aircraft state changes and movement begins
5. Visual feedback shows aircraft moving

### Integration
- **Command Processor** → Has reference to Aircraft Manager
- **Aircraft Manager** → Manages all aircraft
- **Individual Aircraft** → Updates position and state each frame

## Commands

### Pushback Approved (`pa`)

**Usage:** `[flight_number] pa`

**Example:** `100 pa`

**What it does:**
1. Finds aircraft by flight number
2. Checks if aircraft is PARKED
3. Changes state to PUSHBACK
4. Aircraft moves backwards for 8 seconds
5. Automatically transitions to HOLDING when complete

**Output:** `"ENY100, pushback approved, advise ready to taxi"`

**State Checks:**
- ✅ PARKED → PUSHBACK (allowed)
- ❌ Already moving → "unable, already [state]"

### Taxi Clearance (`t[destination][via]`)

**Usage:** `[flight_number] t[destination][via letters]`

**Examples:**
- `100 t02ua` - Taxi to runway 02 via Uniform, Alpha
- `100 tgate5` - Taxi to gate 5
- `100 t02` - Taxi to runway 02

**What it does:**
1. Finds aircraft by flight number
2. Checks if aircraft can taxi (must be PUSHBACK or HOLDING)
3. Parses destination and via routing
4. Changes state to TAXI
5. Sets taxi destination and via taxiways
6. Aircraft begins moving (waypoint system coming soon)

**Output:** `"ENY100, taxi to runway 02 via Uniform, Alpha"`

**State Checks:**
- ❌ PARKED → "unable, request pushback first"
- ✅ PUSHBACK/HOLDING → TAXI (allowed)
- ❌ Already TAXI → "already taxiing"

## Aircraft States

### State Machine
```
PARKED
  ↓ (pushback clearance)
PUSHBACK (8 seconds)
  ↓ (automatic)
HOLDING
  ↓ (taxi clearance)
TAXI
  ↓ (reaches destination)
HOLDING
```

### State Descriptions

**PARKED**
- At gate, engines off
- Waiting for pushback clearance
- No movement

**PUSHBACK**
- Pushing back from gate
- Moves backwards at 0-5 knots
- Duration: 8 seconds
- Auto-transitions to HOLDING

**HOLDING**
- Stopped, engines running
- Ready for taxi clearance
- No movement

**TAXI**
- Moving on taxiways
- Speed: up to 15 knots
- Follows waypoints (basic implementation)

## Visual Feedback

### Aircraft Display
- **Triangle Icon**: Points in heading direction
- **Callsign Label**: Yellow text above aircraft
- **State Label**: Gray text below aircraft showing current state

### State Colors
Aircraft color indicates airline:
- **Red**: AAY (Allegiant)
- **Blue**: ENY (Envoy)
- **Dark Red**: EDV (Endeavor)
- **Light Blue**: SKW (SkyWest)
- **Green**: Private

### Movement
- **Pushback**: Aircraft moves backwards from gate
- **Taxi**: Aircraft moves forward (basic movement, waypoints coming)

## Testing Commands

### Basic Workflow
1. **Start simulation** - 5 aircraft spawn at gates
2. **Identify aircraft** - Look for callsigns (e.g., ENY100, AAY101)
3. **Issue pushback** - Type `100 pa` (use just the number)
4. **Watch movement** - Aircraft pushes back for 8 seconds
5. **Issue taxi** - Type `100 t02ua` after pushback completes
6. **Watch taxi** - Aircraft state changes to TAXI

### Example Session
```
Press / to activate command bar

> 100 pa
ENY100, pushback approved, advise ready to taxi

(wait 8 seconds - aircraft pushes back)

> 100 t02ua
ENY100, taxi to runway 02 via Uniform, Alpha

(aircraft begins taxiing)
```

## Error Messages

### Aircraft Not Found
```
> 999 pa
Aircraft 999 not found
```

### Wrong State for Pushback
```
> 100 pa
ENY100, unable, already pushback
```

### Wrong State for Taxi
```
> 100 t02
ENY100, unable, request pushback first
```

## Current Limitations

### Movement
- ✅ Pushback works with realistic timing
- ✅ State transitions work
- ⚠️ Taxi movement is basic (no waypoint routing yet)
- ⚠️ Aircraft don't follow actual taxiway paths yet
- ⚠️ No collision detection

### Routing
- ⚠️ Via routing is parsed but not used for pathfinding
- ⚠️ Destination is set but no waypoints generated
- ⚠️ Aircraft need taxiway coordinate lookup

## Next Steps

### Phase 1: Waypoint System ✅ (Partially)
- [x] Parse taxi commands
- [x] Extract destination and via
- [ ] Convert taxiway letters to coordinates
- [ ] Build waypoint list from taxiway data
- [ ] Aircraft follow waypoints

### Phase 2: Collision Detection
- [ ] Check aircraft proximity
- [ ] Auto-hold when traffic ahead
- [ ] Prevent overlapping

### Phase 3: Advanced Commands
- [ ] Hold short command (h02)
- [ ] Cross runway command (c02)
- [ ] Contact tower command (to)
- [ ] Speed control

### Phase 4: Realism
- [ ] Realistic acceleration/deceleration
- [ ] Turn radius limits
- [ ] Runway incursion warnings
- [ ] Progressive taxi (one segment at a time)

## Code Structure

### Command Processing
```python
# src/atc/commands.py
class ATCCommandProcessor:
    def __init__(self, aircraft_manager):
        self.aircraft_manager = aircraft_manager
    
    def find_aircraft(self, callsign):
        # Finds aircraft by number or full callsign
        
    def cmd_pa(self, args, output):
        # Pushback command
        aircraft = self.find_aircraft(callsign)
        aircraft.clear_pushback()
        
    def cmd_taxi(self, args, cmd_name, output):
        # Taxi command
        aircraft = self.find_aircraft(callsign)
        aircraft.clear_taxi(destination, via)
```

### Aircraft Control
```python
# src/core/aircraft.py
class Aircraft:
    def clear_pushback(self):
        self.state = STATE_PUSHBACK
        
    def clear_taxi(self, destination, via):
        self.state = STATE_TAXI
        self.taxi_destination = destination
        self.taxi_via = via
        
    def update(self, dt):
        if self.state == STATE_PUSHBACK:
            self._update_pushback(dt)
        elif self.state == STATE_TAXI:
            self._update_taxi(dt)
```

## Configuration

### Pushback Settings
```python
# In Aircraft.__init__
self.pushback_duration = 8.0  # seconds
```

### Taxi Settings
```python
# In Aircraft._update_taxi
target_speed = 15  # knots
```

## Tips

1. **Use Flight Numbers**: Just type the number (e.g., `100` not `ENY100`)
2. **Wait for Pushback**: Aircraft must complete pushback before taxi
3. **Watch State Labels**: Shows current aircraft state below icon
4. **Use Dev Mode**: Press Shift+Ctrl+1 to see gates and taxiways
5. **Zoom In**: Use mouse wheel to see aircraft details

## Troubleshooting

**Aircraft not moving after pushback command?**
- Check state label - should show "PUSHBACK"
- Wait 8 seconds for completion
- State should change to "HOLDING"

**Can't issue taxi command?**
- Aircraft must be in HOLDING or PUSHBACK state
- If PARKED, issue pushback first

**Aircraft not found?**
- Check flight number in yellow label above aircraft
- Use just the number (100, 101, etc.)
- Numbers are assigned sequentially starting at 100

**Aircraft moving weird?**
- Pushback moves backwards (normal)
- Taxi movement is basic for now
- Waypoint system coming soon
