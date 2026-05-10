# Contact Tower Command Fix

## Problems Fixed

1. **`cto` command not working** - Command wasn't routed properly
2. **Hardcoded frequency** - Tower frequency was hardcoded to "118.3"
3. **No airport data** - Command processor didn't have access to scenarios.json

## Solution

### 1. Added `cto` Command Routing

```python
# In commands.py
elif cmd_name == "to" or cmd_name == "cto":
    return self.cmd_contact_tower(args, output_callback)
```

**Now both work:**
- `100 to` → Contact tower
- `100 cto` → Contact tower

### 2. Read Frequency from scenarios.json

```python
def cmd_contact_tower(self, args, output):
    """Contact tower - reads frequency from scenarios.json"""
    # Get tower frequency from airport data
    tower_freq = "118.3"  # Default fallback
    if self.airport_data:
        controllers = self.airport_data.get('controllers', [])
        for controller in controllers:
            if controller.get('name', '').lower() == 'tower':
                tower_freq = controller.get('frequency', '118.3')
                break
    
    output(f"{aircraft.get_callsign()}, contact tower {tower_freq}, good day")
```

### 3. Pass Airport Data to Command Processor

```python
# In simulation.py
self.command_processor = ATCCommandProcessor(self.aircraft_manager, self.airport_data)
```

## Configuration in scenarios.json

```json
{
  "controllers": [
    {
      "name": "Ground",
      "frequency": "121.900"
    },
    {
      "name": "Tower",
      "frequency": "119.900"
    }
  ]
}
```

## Usage

### Command Format

```
[number] cto
[number] to
```

### Examples

```
> 100 cto
[GREEN] ENY100, contact tower 119.900, good day

> 101 to
[GREEN] AAY101, contact tower 119.900, good day
```

## How It Works

1. **Parse command**: `100 cto` → callsign="100", cmd="cto"
2. **Find aircraft**: Look up aircraft by flight number
3. **Read frequency**: Search `controllers` array for "Tower"
4. **Output message**: Use actual frequency from scenarios.json

## Benefits

✅ **`cto` command works** - Both `to` and `cto` route correctly  
✅ **Dynamic frequency** - Reads from scenarios.json  
✅ **Airport-specific** - Each airport can have different frequencies  
✅ **Fallback** - Uses "118.3" if not configured  
✅ **Realistic** - Matches real-world ATC phraseology  

## Different Airports

### KSGF (Springfield)
```json
"controllers": [
  {"name": "Tower", "frequency": "119.900"}
]
```
**Output:** `ENY100, contact tower 119.900, good day`

### KJFK (Example)
```json
"controllers": [
  {"name": "Tower", "frequency": "123.900"}
]
```
**Output:** `AAL100, contact tower 123.900, good day`

### No Configuration (Fallback)
```json
"controllers": []
```
**Output:** `ENY100, contact tower 118.3, good day`

## Technical Details

### Command Processor Constructor

```python
def __init__(self, aircraft_manager=None, airport_data=None):
    self.aircraft_manager = aircraft_manager
    self.airport_data = airport_data  # ← New parameter
```

### Frequency Lookup Logic

```python
# Default frequency
tower_freq = "118.3"

# Try to find Tower controller
if self.airport_data:
    controllers = self.airport_data.get('controllers', [])
    for controller in controllers:
        if controller.get('name', '').lower() == 'tower':
            tower_freq = controller.get('frequency', '118.3')
            break
```

**Case-insensitive:** Matches "Tower", "tower", "TOWER"

### Aircraft Validation

```python
aircraft = self.find_aircraft(callsign)

if not aircraft:
    output(f"Aircraft {callsign} not found")
    return False
```

Ensures aircraft exists before issuing command.

## Future Enhancements

### Multiple Controllers

```json
"controllers": [
  {"name": "Clearance", "frequency": "121.700"},
  {"name": "Ground", "frequency": "121.900"},
  {"name": "Tower", "frequency": "119.900"},
  {"name": "Departure", "frequency": "124.350"},
  {"name": "Approach", "frequency": "125.800"}
]
```

### Additional Commands

```
100 ctg  → Contact ground 121.900
100 ctd  → Contact departure 124.350
100 cta  → Contact approach 125.800
```

### Implementation Example

```python
def cmd_contact_ground(self, args, output):
    """Contact ground"""
    # Find "Ground" in controllers
    ground_freq = "121.9"
    if self.airport_data:
        controllers = self.airport_data.get('controllers', [])
        for controller in controllers:
            if controller.get('name', '').lower() == 'ground':
                ground_freq = controller.get('frequency', '121.9')
                break
    
    output(f"{aircraft.get_callsign()}, contact ground {ground_freq}")
```

## Testing

### Test Commands

```
> 100 cto
Expected: ENY100, contact tower 119.900, good day

> 100 to
Expected: ENY100, contact tower 119.900, good day

> 999 cto
Expected: Aircraft 999 not found
```

### Verify Frequency

1. Check `scenarios.json` for Tower frequency
2. Issue `cto` command
3. Confirm output matches configured frequency

## Summary

**Fixed contact tower command:**
1. ✅ Added `cto` command routing
2. ✅ Reads tower frequency from scenarios.json
3. ✅ Passes airport_data to command processor
4. ✅ Validates aircraft exists
5. ✅ Uses realistic ATC phraseology
6. ✅ Fallback to default frequency

**Result:** `cto` command now works and uses the correct tower frequency from your airport configuration! 📻🗼
