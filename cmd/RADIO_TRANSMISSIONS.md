# Aircraft Radio Transmissions

## New Feature: Automatic Radio Communications

Aircraft now automatically request pushback and taxi clearances with **color-coded radio transmissions**:
- **Blue text** = Aircraft transmissions
- **Green text** = ATC responses

## How It Works

### 1. Automatic Pushback Requests

After spawning at a gate, aircraft automatically request pushback after 5-15 seconds:

```
[BLUE] ENY100, request pushback
[GREEN] ENY100, pushback approved
```

### 2. Automatic Taxi Requests

After pushback completes, aircraft request taxi to a random runway after 2-5 seconds:

```
[BLUE] ENY100, request taxi to runway 02
[GREEN] ENY100, taxi to runway 02 via F, W, U
```

### 3. Manual ATC Commands

You can still manually issue commands via the command bar:

```
> 100 pa
[GREEN] ENY100, pushback approved

> 100 t02fwu
[GREEN] ENY100, taxi to runway 02 via F, W, U
```

## Visual Display

Radio transmissions appear in the command output area (bottom left) with color coding:

```
┌─────────────────────────────────────────┐
│ [BLUE] SKW101, request pushback       │
│ [GREEN] SKW101, pushback approved      │
│ [BLUE] SKW101, request taxi to rwy 20 │
└─────────────────────────────────────────┘
┌─────────────────────────────────────────┐
│ Press / for ATC command                 │
└─────────────────────────────────────────┘
```

## Implementation Details

### Aircraft Class

**New Methods:**
- `request_pushback()` - Aircraft requests pushback clearance
- `request_taxi(destination)` - Aircraft requests taxi clearance
- `_auto_request_taxi()` - Automatically picks random runway and requests taxi

**New Attributes:**
- `radio_callback` - Callback function for radio transmissions
- `spawn_time` - Time when aircraft spawned
- `pushback_requested` - Flag to prevent duplicate requests
- `taxi_requested` - Flag to prevent duplicate requests
- `holding_start_time` - Time when aircraft entered holding state

**Update Logic:**
```python
def update(self, dt: float, current_time: float = 0):
    # Auto-request pushback after 5-15 seconds
    if self.state == PARKED and not pushback_requested:
        if current_time - spawn_time > random(5, 15):
            request_pushback()
    
    # Auto-request taxi after pushback complete
    if self.state == HOLDING and not taxi_requested:
        if current_time - holding_start_time > random(2, 5):
            _auto_request_taxi()
```

### AircraftManager Class

**New Attributes:**
- `radio_callback` - Callback passed to all aircraft
- `simulation_time` - Total simulation time for timing aircraft requests

**Changes:**
- Passes `radio_callback` to all spawned aircraft
- Tracks `simulation_time` and passes to aircraft updates

### SimulationScreen Class

**New Methods:**
- `add_aircraft_transmission(text)` - Add blue aircraft transmission
- `handle_radio_transmission(text, is_atc=False)` - Route transmissions by type

**Updated Methods:**
- `add_output(text, color=(0, 224, 21))` - Now supports color parameter
- Command output now stores `(text, color)` tuples instead of just text

**Color Rendering:**
```python
for item in command_output:
    text, color = item if isinstance(item, tuple) else (item, (0, 224, 21))
    output_text = font.render(text, True, color)
```

## Color Codes

```python
# Aircraft transmissions (blue)
AIRCRAFT_COLOR = (100, 180, 255)

# ATC transmissions (green)
ATC_COLOR = (0, 224, 21)
```

## Example Timeline

```
Time 0:00 - Aircraft spawns at gate
Time 0:08 - [BLUE] ENY100, request pushback
Time 0:08 - [GREEN] ENY100, pushback approved
Time 0:08 - Aircraft begins pushback
Time 0:24 - Pushback complete, aircraft holding
Time 0:27 - [BLUE] ENY100, request taxi to runway 14
Time 0:27 - [GREEN] ENY100, taxi to runway 14 via F, W
Time 0:27 - Aircraft begins taxi
```

## Automatic Runway Selection

Aircraft automatically select a random runway from available runways:

```python
def _auto_request_taxi(self):
    runways = airport_data.get('runways', [])
    runway = random.choice(runways)
    runway_name = runway.get('name', '').split('/')[0]  # "02/20" → "02"
    request_taxi(f"runway {runway_name}")
```

**Example:**
- KSGF has runways: "02/20" and "14/32"
- Aircraft randomly picks: "02", "20", "14", or "32"
- Requests: "runway 02", "runway 20", "runway 14", or "runway 32"

## Benefits

### ✅ Realistic Radio Communications
- Aircraft proactively request clearances
- ATC responds with proper phraseology
- Color-coded for easy identification

### ✅ Automatic Operations
- No manual intervention needed for basic operations
- Aircraft follow realistic timing patterns
- Random delays add realism

### ✅ Visual Clarity
- Blue = Pilot transmissions
- Green = ATC transmissions
- Easy to follow radio traffic

### ✅ Manual Override
- ATC can still issue commands manually
- Manual commands trigger ATC responses
- Full control when needed

## Future Enhancements

### Planned Features:
1. **Readback confirmations** - Aircraft read back clearances
2. **Contact tower** - Aircraft request frequency changes
3. **Ready for departure** - Aircraft report ready at runway
4. **Takeoff clearance** - ATC clears for takeoff
5. **Landing clearance** - ATC clears to land
6. **Taxi instructions** - More detailed taxi routing

### Example Future Transmissions:
```
[BLUE] ENY100, request pushback
[GREEN] ENY100, pushback approved, face south
[BLUE] Pushback approved, face south, ENY100

[BLUE] ENY100, ready to taxi
[GREEN] ENY100, taxi to runway 02 via F, W, U
[BLUE] Taxi to runway 02 via F, W, U, ENY100

[BLUE] ENY100, holding short runway 02
[GREEN] ENY100, cross runway 02, contact tower 118.3
[BLUE] Cross runway 02, contact tower 118.3, ENY100

[BLUE] Tower, ENY100 with you, ready for departure
[GREEN] ENY100, runway 02, cleared for takeoff
[BLUE] Runway 02, cleared for takeoff, ENY100
```

## Configuration

### Timing Adjustments

In `Aircraft.update()`:

```python
# Current: 5-15 seconds for pushback request
if current_time - spawn_time > random.uniform(5, 15):

# Faster (2-8 seconds):
if current_time - spawn_time > random.uniform(2, 8):

# Slower (10-30 seconds):
if current_time - spawn_time > random.uniform(10, 30):
```

```python
# Current: 2-5 seconds for taxi request
if current_time - holding_start_time > random.uniform(2, 5):

# Faster (1-3 seconds):
if current_time - holding_start_time > random.uniform(1, 3):

# Slower (5-10 seconds):
if current_time - holding_start_time > random.uniform(5, 10):
```

### Color Customization

In `SimulationScreen`:

```python
# Current colors
AIRCRAFT_COLOR = (100, 180, 255)  # Light blue
ATC_COLOR = (0, 224, 21)          # Green

# Alternative colors
AIRCRAFT_COLOR = (135, 206, 250)  # Sky blue
ATC_COLOR = (50, 205, 50)         # Lime green

AIRCRAFT_COLOR = (70, 130, 180)   # Steel blue
ATC_COLOR = (0, 255, 127)         # Spring green
```

## Troubleshooting

### No Radio Transmissions Appearing

**Check:**
1. Aircraft manager has radio callback set
2. Simulation screen `handle_radio_transmission` is wired
3. Command output is rendering

### Aircraft Not Requesting Clearances

**Check:**
1. Aircraft `spawn_time` is being set
2. Simulation time is advancing
3. Random delay has elapsed
4. Flags (`pushback_requested`, `taxi_requested`) are working

### Wrong Colors

**Check:**
1. `is_atc` parameter is being passed correctly
2. Color tuples in `handle_radio_transmission`
3. Rendering code handles tuple format

## Summary

**New Radio System:**
1. ✅ Aircraft automatically request pushback (5-15s after spawn)
2. ✅ Aircraft automatically request taxi (2-5s after pushback)
3. ✅ Blue text for aircraft transmissions
4. ✅ Green text for ATC responses
5. ✅ Realistic timing with random delays
6. ✅ Automatic runway selection
7. ✅ Manual ATC override available

**Result:** Realistic, color-coded radio communications that bring the simulation to life! 📻✈️
