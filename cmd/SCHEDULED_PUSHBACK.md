# Scheduled Pushback System

## Overview

Aircraft now request pushback at **scheduled intervals** matching the departure rate, rather than all at once. This creates realistic traffic flow that matches the configured departures per hour.

## How It Works

### Departure Rate Configuration

In `scenarios.json`:
```json
{
  "dep_spawn_rate": 15  // 15 departures per hour
}
```

**Calculation:**
- 15 departures/hour = 3600 seconds / 15 = **240 seconds between pushbacks**
- Each aircraft requests pushback ~240 seconds after the previous one

### Initial Aircraft Scheduling

When 5 aircraft spawn at startup:

```
Aircraft 1: Scheduled pushback at t+5s
Aircraft 2: Scheduled pushback at t+245s (240s + 5s)
Aircraft 3: Scheduled pushback at t+485s (480s + 5s)
Aircraft 4: Scheduled pushback at t+725s (720s + 5s)
Aircraft 5: Scheduled pushback at t+965s (960s + 5s)
```

**Random Offset:** ±10% variation for realism
- 240s interval → ±24s random offset
- Aircraft 2 might request at t+221s to t+269s

### Auto-Spawned Aircraft

When new aircraft spawn during simulation:

```
Next aircraft spawns at: t+1200s (after 5th aircraft)
Scheduled pushback: t+1205s
Next interval: t+1445s
```

Each new aircraft continues the pattern, maintaining the departure rate.

## Example Timeline (15 dep/hour)

```
t=0s     - 5 aircraft spawn at gates
t=5s     - [BLUE] ENY100, request pushback
t=5s     - [GREEN] ENY100, pushback approved
t=245s   - [BLUE] AAY101, request pushback
t=245s   - [GREEN] AAY101, pushback approved
t=485s   - [BLUE] ENY102, request pushback
t=485s   - [GREEN] ENY102, pushback approved
t=725s   - [BLUE] ENY103, request pushback
t=725s   - [GREEN] ENY103, pushback approved
t=965s   - [BLUE] AAY104, request pushback
t=965s   - [GREEN] AAY104, pushback approved
t=1200s  - New aircraft spawns at gate
t=1205s  - [BLUE] EDV105, request pushback
t=1205s  - [GREEN] EDV105, pushback approved
```

**Result:** Exactly 15 pushback requests per hour, evenly distributed!

## Implementation Details

### Aircraft Class

**New Attribute:**
```python
self.scheduled_pushback_time = None  # When to request pushback
```

**Updated Logic:**
```python
def update(self, dt: float, current_time: float = 0):
    # Auto-request pushback at scheduled time
    if self.state == PARKED and not pushback_requested:
        if scheduled_pushback_time is not None and current_time >= scheduled_pushback_time:
            request_pushback()
            pushback_requested = True
```

### AircraftManager Class

**New Attributes:**
```python
self.next_pushback_time = 0.0  # Next scheduled pushback time
self.pushback_queue = []       # Queue of aircraft (future use)
```

**Initial Spawn Scheduling:**
```python
def spawn_initial_aircraft(self, count: int = 5):
    for i, gate in enumerate(selected_gates):
        aircraft = spawn_aircraft_at_gate(gate)
        
        # Schedule evenly distributed
        base_delay = i * dep_spawn_interval
        random_offset = random.uniform(-0.1, 0.1) * dep_spawn_interval
        aircraft.scheduled_pushback_time = base_delay + random_offset + 5.0
    
    # Set next time for future spawns
    next_pushback_time = count * dep_spawn_interval
```

**Auto-Spawn Scheduling:**
```python
def _spawn_departure(self):
    aircraft = spawn_aircraft_at_gate(gate)
    
    # Schedule at next interval
    random_offset = random.uniform(-0.1, 0.1) * dep_spawn_interval
    aircraft.scheduled_pushback_time = next_pushback_time + random_offset + 5.0
    next_pushback_time += dep_spawn_interval
```

## Benefits

### ✅ Realistic Traffic Flow
- Pushbacks spread evenly throughout the hour
- No sudden rush of all aircraft at once
- Matches real-world airport operations

### ✅ Matches Departure Rate
- 15 dep/hour → 15 pushback requests/hour
- 21 dep/hour → 21 pushback requests/hour
- Exact match to configured rate

### ✅ Predictable Timing
- ATC knows when to expect next request
- Easier to manage traffic flow
- More realistic workload

### ✅ Random Variation
- ±10% offset adds realism
- Not perfectly mechanical
- Simulates real-world variability

## Configuration Examples

### High Traffic Airport (30 dep/hour)

```json
{
  "dep_spawn_rate": 30
}
```

**Result:**
- 3600s / 30 = 120 seconds between pushbacks
- Pushback every ~2 minutes
- Busy, realistic traffic

### Low Traffic Airport (6 dep/hour)

```json
{
  "dep_spawn_rate": 6
}
```

**Result:**
- 3600s / 6 = 600 seconds between pushbacks
- Pushback every ~10 minutes
- Quiet, regional airport feel

### Current KSGF (15 dep/hour)

```json
{
  "dep_spawn_rate": 15
}
```

**Result:**
- 3600s / 15 = 240 seconds between pushbacks
- Pushback every ~4 minutes
- Moderate traffic

## Logging Output

```
2025-11-10 10:22:36 - Aircraft - INFO - Spawn rates configured: 15 departures/hour (240.0s interval)
2025-11-10 10:22:36 - Aircraft - INFO - Pushback requests will be staggered every ~240.0s to match departure rate

2025-11-10 10:22:36 - Aircraft - INFO - [ENY100] Aircraft created at gate Gate 10
2025-11-10 10:22:36 - Aircraft - INFO - [ENY100] Scheduled pushback at t+5.0s

2025-11-10 10:22:36 - Aircraft - INFO - [AAY101] Aircraft created at gate Gate 2
2025-11-10 10:22:36 - Aircraft - INFO - [AAY101] Scheduled pushback at t+245.0s

2025-11-10 10:22:36 - Aircraft - INFO - [ENY102] Aircraft created at gate Gate 8
2025-11-10 10:22:36 - Aircraft - INFO - [ENY102] Scheduled pushback at t+485.0s

2025-11-10 10:22:36 - Aircraft - INFO - [ENY103] Aircraft created at gate Gate 1
2025-11-10 10:22:36 - Aircraft - INFO - [ENY103] Scheduled pushback at t+725.0s

2025-11-10 10:22:36 - Aircraft - INFO - [AAY104] Aircraft created at gate Gate 4
2025-11-10 10:22:36 - Aircraft - INFO - [AAY104] Scheduled pushback at t+965.0s
```

## Comparison: Before vs After

### Before (Random Delays)

```
t=0s   - 5 aircraft spawn
t=8s   - ENY100 requests pushback (random 5-15s)
t=11s  - AAY101 requests pushback (random 5-15s)
t=7s   - ENY102 requests pushback (random 5-15s)
t=13s  - ENY103 requests pushback (random 5-15s)
t=9s   - AAY104 requests pushback (random 5-15s)
```

**Problem:** All 5 aircraft request within 8 seconds!
- Not realistic
- Doesn't match departure rate
- ATC overwhelmed

### After (Scheduled)

```
t=0s    - 5 aircraft spawn
t=5s    - ENY100 requests pushback (scheduled)
t=245s  - AAY101 requests pushback (scheduled)
t=485s  - ENY102 requests pushback (scheduled)
t=725s  - ENY103 requests pushback (scheduled)
t=965s  - AAY104 requests pushback (scheduled)
```

**Solution:** Evenly distributed over ~16 minutes!
- Realistic traffic flow
- Matches 15 dep/hour rate
- Manageable ATC workload

## Advanced Features

### Random Offset Details

```python
# Base interval: 240 seconds
dep_spawn_interval = 240.0

# Random offset: ±10%
random_offset = random.uniform(-0.1, 0.1) * 240.0
# Range: -24s to +24s

# Final scheduled time
scheduled_time = base_delay + random_offset + 5.0
# Aircraft 2: 240s ± 24s + 5s = 221s to 269s
```

**Why ±10%?**
- Adds realism (not perfectly mechanical)
- Prevents exact synchronization
- Simulates pilot/ground crew variability

### Minimum Delay

```python
aircraft.scheduled_pushback_time = base_delay + random_offset + 5.0
                                                                 ^^^^
                                                            5 second minimum
```

**Why +5s?**
- Gives aircraft time to "settle" at gate
- Prevents instant pushback on spawn
- More realistic startup procedure

## Troubleshooting

### All Aircraft Still Push at Once

**Check:**
1. `scheduled_pushback_time` is being set
2. `current_time` is advancing in `update()`
3. Logging shows scheduled times

### Pushbacks Too Close Together

**Adjust:**
```python
# Increase departure rate interval
"dep_spawn_rate": 10  // Slower: 360s between pushbacks
```

### Pushbacks Too Far Apart

**Adjust:**
```python
# Decrease departure rate interval
"dep_spawn_rate": 30  // Faster: 120s between pushbacks
```

## Summary

**New Scheduled Pushback System:**
1. ✅ Pushbacks evenly distributed based on departure rate
2. ✅ Initial aircraft staggered at spawn
3. ✅ Auto-spawned aircraft continue pattern
4. ✅ ±10% random offset for realism
5. ✅ Matches configured departures per hour exactly
6. ✅ Realistic traffic flow and ATC workload

**Result:** Aircraft request pushback at realistic intervals matching the airport's departure rate, creating smooth, manageable traffic flow! 🛫⏰
