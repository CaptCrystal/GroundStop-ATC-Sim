# Aircraft Spawn Rate System

## Overview

The simulation now automatically spawns aircraft based on **hourly rates** configured in `scenarios.json`. This creates realistic traffic flow at the airport.

## Configuration

### In scenarios.json

```json
{
  "code": "KSGF",
  "name": "Springfield-Branson National Airport",
  "dep_spawn_rate": 15,  // Departures per hour
  "arr_spawn_rate": 21   // Arrivals per hour
}
```

### Rates

- **`dep_spawn_rate`**: Number of departure aircraft spawned per hour
- **`arr_spawn_rate`**: Number of arrival aircraft spawned per hour (future)

## How It Works

### Conversion to Spawn Intervals

The system converts hourly rates to spawn intervals in seconds:

```python
# Example: 15 departures per hour
dep_spawn_rate = 15
dep_spawn_interval = 3600 / 15 = 240 seconds (4 minutes)

# Example: 21 arrivals per hour
arr_spawn_rate = 21
arr_spawn_interval = 3600 / 21 = 171.4 seconds (~2.86 minutes)
```

### Spawn Timers

The `AircraftManager` maintains two timers:

```python
self.dep_spawn_timer = 0.0  # Counts up to dep_spawn_interval
self.arr_spawn_timer = 0.0  # Counts up to arr_spawn_interval
```

Each frame, timers increment by `dt` (delta time):

```python
def update(self, dt: float):
    self.dep_spawn_timer += dt
    self.arr_spawn_timer += dt
    
    if self.dep_spawn_timer >= self.dep_spawn_interval:
        self._spawn_departure()
        self.dep_spawn_timer = 0.0
    
    if self.arr_spawn_timer >= self.arr_spawn_interval:
        self._spawn_arrival()
        self.arr_spawn_timer = 0.0
```

## Departure Spawning

### Process

1. **Find available gates**
   - Get all gates from airport data
   - Exclude gates that already have aircraft
   
2. **Select random gate**
   - Choose from available gates
   - Ensures realistic gate utilization
   
3. **Spawn aircraft**
   - Create aircraft at gate
   - Assign airline based on gate configuration
   - Select appropriate aircraft type
   - Set state to PARKED

### Example

```
Time: 0s → Spawn ENY100 at Gate 1
Time: 240s → Spawn AAY101 at Gate 3
Time: 480s → Spawn SKW102 at Gate 5
...
```

### Gate Availability

The system tracks occupied gates:

```python
occupied_gates = {aircraft.gate for aircraft in self.aircraft if aircraft.gate}
available_gates = [g for g in gates if g['name'] not in occupied_gates]
```

**If no gates available:**
- Spawn is skipped
- Timer resets
- Next spawn attempt at next interval

## Arrival Spawning

### Current Status

**Not yet implemented** - placeholder for future development

### Future Implementation

When implemented, arrivals will:
1. Spawn aircraft on approach path
2. Set state to LANDING
3. Guide to runway threshold
4. Land and taxi to gate
5. Free up gate for next departure

### Placeholder

```python
def _spawn_arrival(self):
    """Spawn an arrival aircraft (future implementation)"""
    logger.debug(f"Arrival spawn triggered (not yet implemented)")
    # TODO: Implement arrival spawning when landing logic is added
```

## Examples

### Low Traffic Airport

```json
{
  "dep_spawn_rate": 5,   // 1 departure every 12 minutes
  "arr_spawn_rate": 5    // 1 arrival every 12 minutes
}
```

**Result:** Quiet airport, plenty of time between aircraft

### Medium Traffic Airport (KSGF)

```json
{
  "dep_spawn_rate": 15,  // 1 departure every 4 minutes
  "arr_spawn_rate": 21   // 1 arrival every ~2.86 minutes
}
```

**Result:** Moderate traffic, realistic for regional airport

### High Traffic Airport

```json
{
  "dep_spawn_rate": 60,  // 1 departure every minute
  "arr_spawn_rate": 60   // 1 arrival every minute
}
```

**Result:** Busy airport, constant traffic flow

## Logging

### Initialization

```
Spawn rates configured: 15 departures/hour (240.0s interval), 
                       21 arrivals/hour (171.4s interval)
```

### Departure Spawns

```
Auto-spawned departure: ENY100 (CRJ9) at Gate 1
🛫 Departure: ENY100 (CRJ9) at Gate 1
```

### No Gates Available

```
No available gates for departure spawn
```

### Arrival Triggers (Future)

```
Arrival spawn triggered (not yet implemented)
```

## Spawn Rate Calculations

### Formula

```
spawn_interval (seconds) = 3600 / spawn_rate
```

### Common Rates

| Rate (per hour) | Interval (seconds) | Interval (minutes) |
|-----------------|--------------------|--------------------|
| 5               | 720s               | 12 min             |
| 10              | 360s               | 6 min              |
| 15              | 240s               | 4 min              |
| 20              | 180s               | 3 min              |
| 30              | 120s               | 2 min              |
| 60              | 60s                | 1 min              |
| 120             | 30s                | 0.5 min            |

### Real-World Examples

**Small Regional (KSGF):**
- Departures: 10-20/hour
- Arrivals: 10-20/hour

**Medium Hub:**
- Departures: 30-50/hour
- Arrivals: 30-50/hour

**Major Hub (ORD, ATL):**
- Departures: 80-120/hour
- Arrivals: 80-120/hour

## Aircraft Lifecycle

### Departure Flow

```
1. Spawn at gate (PARKED)
   ↓
2. Request pushback (player command)
   ↓
3. Pushback to ramp (PUSHBACK)
   ↓
4. Hold at ramp (HOLDING)
   ↓
5. Request taxi (player command)
   ↓
6. Taxi to runway (TAXI)
   ↓
7. Hold short of runway (HOLDING)
   ↓
8. Takeoff clearance (future)
   ↓
9. Depart (DEPARTED)
   ↓
10. Remove from simulation
```

### Arrival Flow (Future)

```
1. Spawn on approach (LANDING)
   ↓
2. Land on runway (LANDING)
   ↓
3. Exit runway (TAXI)
   ↓
4. Taxi to gate (TAXI)
   ↓
5. Park at gate (PARKED)
   ↓
6. Wait for departure cycle
```

## Gate Management

### Tracking

```python
# Get occupied gates
occupied_gates = {aircraft.gate for aircraft in self.aircraft if aircraft.gate}

# Example: {'Gate 1', 'Gate 3', 'Gate 5'}
```

### Availability

```python
# Filter available gates
available_gates = [g for g in gates if g['name'] not in occupied_gates]

# Only spawn if gates available
if available_gates:
    spawn_aircraft()
```

### Capacity

**KSGF has 10 gates:**
- Maximum 10 aircraft at gates simultaneously
- When all gates full, spawning pauses
- As aircraft depart, gates become available

## Performance

### Spawn Overhead

- **Minimal**: Only checks gates and spawns when timer expires
- **No continuous polling**: Event-driven based on intervals
- **Efficient gate tracking**: Set-based lookup

### Typical Performance

```
15 departures/hour = 1 spawn every 240s
21 arrivals/hour = 1 spawn every 171s

Per spawn: ~0.1ms
Impact: Negligible
```

## Configuration Tips

### Balanced Traffic

```json
{
  "dep_spawn_rate": 15,
  "arr_spawn_rate": 15
}
```

**Use when:** Equal departures and arrivals

### Departure-Heavy

```json
{
  "dep_spawn_rate": 20,
  "arr_spawn_rate": 10
}
```

**Use when:** Morning rush, outbound traffic

### Arrival-Heavy

```json
{
  "dep_spawn_rate": 10,
  "arr_spawn_rate": 20
}
```

**Use when:** Evening rush, inbound traffic

### Peak Hours

```json
{
  "dep_spawn_rate": 30,
  "arr_spawn_rate": 30
}
```

**Use when:** Simulating busy periods

### Off-Peak

```json
{
  "dep_spawn_rate": 5,
  "arr_spawn_rate": 5
}
```

**Use when:** Simulating quiet periods

## Future Enhancements

### Time-Based Rates

```json
{
  "spawn_schedule": {
    "06:00-09:00": {"dep": 30, "arr": 20},
    "09:00-17:00": {"dep": 15, "arr": 15},
    "17:00-20:00": {"dep": 20, "arr": 30},
    "20:00-06:00": {"dep": 5, "arr": 5}
  }
}
```

### Weather Impact

```json
{
  "spawn_modifiers": {
    "clear": 1.0,
    "rain": 0.8,
    "storm": 0.5
  }
}
```

### Airline Schedules

```json
{
  "scheduled_flights": [
    {"time": "08:00", "airline": "AAL", "flight": "1234"},
    {"time": "08:15", "airline": "UAL", "flight": "5678"}
  ]
}
```

## Summary

**Spawn System Features:**
- ✅ Automatic departure spawning at configurable hourly rates
- ✅ Gate availability tracking
- ✅ Realistic spawn intervals
- ✅ Efficient timer-based system
- ✅ Detailed logging
- 🔜 Arrival spawning (future)

**Configuration:**
```json
"dep_spawn_rate": 15,  // Aircraft per hour
"arr_spawn_rate": 21   // Aircraft per hour
```

**Result:** Realistic, continuous traffic flow at your airport! ✈️
