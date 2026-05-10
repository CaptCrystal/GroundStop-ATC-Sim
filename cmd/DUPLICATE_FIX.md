# Duplicate ATC Command Fix

## Problem

When ATC manually issued commands like `100 pa` or `100 t02ua`, duplicate green ATC messages appeared:

```
[BLUE]  ENY100, request pushback
[GREEN] ENY100, pushback approved         ← From command processor
[GREEN] ENY100, pushback approved         ← Duplicate from aircraft method!
```

## Root Cause

Two sources were sending ATC messages:

1. **Command Processor** (`commands.py`):
   ```python
   def cmd_pa(self, args, output):
       aircraft.clear_pushback()
       output(f"{callsign}, pushback approved")  # ← ATC message
   ```

2. **Aircraft Method** (`aircraft.py`):
   ```python
   def clear_pushback(self):
       if self.radio_callback:
           self.radio_callback(f"{callsign}, pushback approved", is_atc=True)  # ← Duplicate!
   ```

## Solution

Added `send_radio` parameter to control when aircraft methods send radio transmissions:

### Aircraft Methods Updated

```python
def clear_pushback(self, send_radio=False):
    """Clear aircraft for pushback"""
    self.cleared_to_pushback = True
    self.state = self.STATE_PUSHBACK
    # Only send radio if this is an automatic response
    if send_radio and self.radio_callback:
        self.radio_callback(f"{self.get_callsign()}, pushback approved", is_atc=True)

def clear_taxi(self, destination: str, via: List[str] = None, send_radio=False):
    """Clear aircraft to taxi"""
    # ... setup code ...
    # Only send radio if this is an automatic response
    if send_radio and self.radio_callback:
        self.radio_callback(f"{self.get_callsign()}, taxi to {destination} via {via_str}", is_atc=True)
```

### Automatic Requests (send_radio=True)

```python
def request_pushback(self):
    """Aircraft requests pushback clearance"""
    if self.radio_callback:
        self.radio_callback(f"{self.get_callsign()}, request pushback")
    # Auto-approve with radio transmission
    self.clear_pushback(send_radio=True)  # ← Sends green ATC message

def _auto_request_taxi(self):
    """Automatically request taxi to a random runway"""
    destination = f"runway {runway_name}"
    self.request_taxi(destination)
    # Auto-approve with radio transmission
    self.clear_taxi(destination, via=via, send_radio=True)  # ← Sends green ATC message
```

### Manual Commands (send_radio=False)

```python
# In commands.py
def cmd_pa(self, args, output):
    aircraft.clear_pushback()  # ← send_radio defaults to False
    output(f"{callsign}, pushback approved")  # ← Only ATC message

def cmd_taxi(self, args, cmd_name, output):
    aircraft.clear_taxi(destination, via=via)  # ← send_radio defaults to False
    output(f"{callsign}, taxi to {destination} via {via_str}")  # ← Only ATC message
```

## Result

### Automatic Request Flow (No Duplicates)

```
[BLUE]  ENY100, request pushback
[GREEN] ENY100, pushback approved         ← From aircraft.clear_pushback(send_radio=True)

[BLUE]  ENY100, request taxi to runway 02
[GREEN] ENY100, taxi to runway 02 via F, W, U  ← From aircraft.clear_taxi(send_radio=True)
```

### Manual Command Flow (No Duplicates)

```
> 100 pa
[GREEN] ENY100, pushback approved, advise ready to taxi  ← From commands.py output()

> 100 t02fwu
[GREEN] ENY100, taxi to runway 02 via Foxtrot, Whiskey, Uniform  ← From commands.py output()
```

## Benefits

✅ **No duplicate messages** - Each transmission appears once  
✅ **Clean radio traffic** - Easy to follow  
✅ **Automatic + Manual** - Both modes work correctly  
✅ **Backward compatible** - Existing code still works  

## Technical Details

### Parameter Default

```python
def clear_pushback(self, send_radio=False):
                                    ^^^^
                              Defaults to False
```

**Why False?**
- Most calls are from manual ATC commands
- Manual commands already output messages
- Prevents accidental duplicates

### When to Use send_radio=True

Only when aircraft automatically approve their own requests:
- `request_pushback()` → auto-approves with `send_radio=True`
- `_auto_request_taxi()` → auto-approves with `send_radio=True`

### When to Use send_radio=False (default)

When ATC manually issues commands:
- `cmd_pa()` → calls `clear_pushback()` (defaults to False)
- `cmd_taxi()` → calls `clear_taxi()` (defaults to False)

## Summary

**Fixed duplicate ATC transmissions by:**
1. ✅ Added `send_radio` parameter to `clear_pushback()` and `clear_taxi()`
2. ✅ Default `send_radio=False` for manual ATC commands
3. ✅ Use `send_radio=True` only for automatic aircraft requests
4. ✅ Command processor outputs messages, aircraft methods don't duplicate

**Result:** Clean, non-duplicate radio communications! 📻✨
