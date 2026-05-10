# Aircraft System Documentation

## Overview
The aircraft system manages spawning, movement, state tracking, and rendering of aircraft in the simulation.

## Architecture

### Core Components

**1. Aircraft Class** (`src/core/aircraft.py`)
- Represents individual aircraft with properties and state
- Handles movement and state transitions
- Manages ATC clearances

**2. AircraftManager Class** (`src/core/aircraft.py`)
- Manages all aircraft in the simulation
- Handles spawning at gates
- Updates all aircraft each frame
- Provides lookup by callsign or flight number

**3. Integration** (`src/rendering/simulation.py`)
- Aircraft manager initialized with airport data
- Aircraft updated in `update()` method
- Aircraft rendered in `render_aircraft()` method

## Aircraft Properties

### Basic Info
- `flight_number`: Just the number (e.g., "123")
- `aircraft_type`: ICAO type code (e.g., "B738", "E170")
- `airline`: Airline ICAO code (e.g., "AAY", "ENY")
- `position`: (latitude, longitude) tuple
- `heading`: Direction in degrees (0-360)
- `gate`: Assigned gate name

### State Machine
- `STATE_PARKED`: At gate, engines off
- `STATE_PUSHBACK`: Pushing back from gate
- `STATE_TAXI`: Taxiing on taxiways
- `STATE_HOLDING`: Stopped, holding position
- `STATE_TAKEOFF`: Taking off
- `STATE_LANDING`: Landing
- `STATE_DEPARTED`: Left the airport

### Movement
- `speed`: Current speed in knots
- `target_position`: Next waypoint
- `route`: List of waypoints to follow

### ATC Clearances
- `cleared_to_pushback`: Boolean
- `cleared_to_taxi`: Boolean
- `taxi_destination`: Where to taxi to
- `taxi_via`: List of taxiways to use
- `hold_short`: Runway to hold short of

## Visual Representation

### Aircraft Icon
- **Shape**: Triangle pointing in heading direction
- **Size**: 12 pixels
- **Color**: Airline-specific colors:
  - AAY (Allegiant): Red (255, 0, 0)
  - ENY (Envoy): Blue (0, 100, 200)
  - EDV (Endeavor): Dark Red (200, 0, 0)
  - SKW (SkyWest): Light Blue (0, 150, 200)
  - Private: Green (100, 255, 100)
  - Default: Yellow (255, 255, 0)
- **Outline**: White border

### Labels
- **Callsign**: Yellow text above aircraft (e.g., "AAY123")
- **State**: Gray text below aircraft (e.g., "PARKED", "TAXI")
- **Background**: Semi-transparent black for readability

## Aircraft Types Database

### Categories
- **Small**: C172, C182, HDJT, P28A, C25C
- **Medium**: E170, CRJ7, CRJ9, B712, B38M, A319, A320

### Type Info
Each type has:
- `name`: Full aircraft name
- `category`: Size category

## Spawning System

### Initial Spawn
- `spawn_initial_aircraft(count)`: Spawns aircraft at random gates
- Default: 5 aircraft at startup
- Selects gates based on airline assignments
- Assigns appropriate aircraft types for each airline

### Gate Assignment
- Reads gate data from `scenarios.json`
- Uses gate position, heading, and airline
- Generates sequential flight numbers (100, 101, 102...)

## Movement System

### Update Loop
- Called every frame with delta time (dt)
- Updates position based on state and speed
- Handles state transitions

### Pushback
- Moves backwards from gate
- Speed: 0-5 knots
- Direction: Opposite of gate heading

### Taxi
- Follows waypoints in route
- Speed: Up to 15 knots
- Automatically transitions to HOLDING when route complete

## Integration with ATC Commands

The aircraft system is designed to work with ATC commands:

### Command Processing
Commands can reference aircraft by flight number:
- `123 pa` → Find aircraft "123", execute pushback
- `456 t02ua` → Find aircraft "456", taxi to runway 02 via U, A

### Lookup Methods
- `get_aircraft_by_callsign("AAY123")`: Full callsign
- `get_aircraft_by_flight_number("123")`: Just number

## Usage Examples

### Spawn Aircraft
```python
# In SimulationScreen.__init__
self.aircraft_manager = AircraftManager(self.airport_data)
self.aircraft_manager.spawn_initial_aircraft(5)
```

### Update Aircraft
```python
# In SimulationScreen.update(dt)
if self.aircraft_manager:
    self.aircraft_manager.update(dt)
```

### Render Aircraft
```python
# In SimulationScreen.render()
if self.aircraft_manager:
    self.render_aircraft()
```

### Find Aircraft
```python
# Find by flight number
aircraft = self.aircraft_manager.get_aircraft_by_flight_number("123")

# Find by full callsign
aircraft = self.aircraft_manager.get_aircraft_by_callsign("AAY123")
```

### Issue Clearances
```python
aircraft.clear_pushback()
aircraft.clear_taxi("02", ["U", "A"])
aircraft.hold_short_of("02")
```

## Next Steps

To fully integrate with ATC commands:

1. **Connect Commands to Aircraft**
   - Modify `cmd_pa()`, `cmd_taxi()`, etc. in `commands.py`
   - Look up aircraft by flight number
   - Call aircraft methods (e.g., `aircraft.clear_pushback()`)

2. **Add Waypoint System**
   - Parse taxiway routes
   - Convert taxiway letters to coordinates
   - Build waypoint list for aircraft

3. **Add Collision Detection**
   - Check aircraft proximity
   - Prevent overlapping
   - Auto-hold when traffic ahead

4. **Add Click Selection**
   - Click aircraft to select
   - Show detailed info panel
   - Issue commands to selected aircraft

## File Structure

```
src/
├── core/
│   └── aircraft.py          # Aircraft and AircraftManager classes
├── atc/
│   └── commands.py          # ATC command processor
└── rendering/
    └── simulation.py        # Main simulation screen with rendering
```

## Configuration

Aircraft assignments are defined in `scenarios.json`:

```json
"aircraft": [
  {"Private": ["C172", "C182", "HDJT", "P28A", "C25C"]},
  {"ENY": ["E170", "CRJ7", "CRJ9"]},
  {"EDV": ["B712", "CRJ7", "CRJ9"]},
  {"SKW": ["E170", "CRJ7"]},
  {"AAY": ["B38M", "A319", "A320"]}
]
```

Gates specify which airline uses them:

```json
"gates": [
  {
    "name": "Gate 1",
    "position": {"x": 37.239410, "y": -93.395600},
    "degrees": 298,
    "airline": "ENY",
    "aircraft_type": "small, medium"
  }
]
```
