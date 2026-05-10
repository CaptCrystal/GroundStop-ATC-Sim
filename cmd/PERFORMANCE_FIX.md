# Performance Fix - GeoJSON Rendering Freeze

## Problem
The simulation was freezing when trying to render GeoJSON files because:

1. **SGF.geojson has 10,346+ features** - way too many to render in real-time
2. Each feature requires coordinate projection calculations
3. No performance limits were in place
4. The rendering loop was trying to process all features every frame
5. **CRITICAL: Scenario manager was being called 60 times per second** inside the render loop
6. **CRITICAL: Scale multiplier of 100,000 created coordinates in the billions** causing pygame to hang

## Solution Applied

### Changes to `src/rendering/simulation.py`:

1. **CRITICAL FIX: Moved scenario manager call to initialization** (lines 100-132)
   - Was being called every frame (60 FPS) causing massive overhead
   - Now called once during `__init__`
   - Caches center coordinates and bounds

2. **Added feature limit** (line 206): Maximum 500 features rendered per frame

3. **Added error handling** (lines 215-222): Skip problematic features instead of crashing

4. **Added performance warnings** (lines 69-71): Console warnings for large files

5. **Added debug display** (lines 226-237): Shows how many features are being rendered

6. **Added loading state tracking** (lines 38-39): Better state management

7. **Added viewport data caching** (lines 42-46): Calculate once, use many times

8. **CRITICAL FIX: Removed 100,000x scale multiplier** (line 232)
   - Was creating coordinate values in the billions
   - Pygame can't handle coordinates beyond ~32,000 pixels
   - Now uses proper pixels-per-degree scaling

9. **Added coordinate clamping** (lines 391-392): Prevents extreme values from reaching pygame

10. **Added scale debug output** (lines 235-237): Shows actual scale values being used

### What You'll See Now:

**In the console:**
```
Loading GeoJSON: data/airports/test.geojson
Loaded GeoJSON with 1 features
First feature type: Polygon
First feature properties: {}
GeoJSON loading complete
Calculating viewport data...
Using airport coordinates: 37.241121, -93.391115
GeoJSON bounds: lon=[-93.400727, -93.380062], lat=[37.235577, 37.255373]
Viewport data calculation complete
SimulationScreen initialization complete
Scale debug: scale_x=90000.00, scale_y=85000.00, final_scale=85000.00, zoom=1.00
```

**On screen:**
- Top-right corner shows: "Rendering X/Y features"
- Warning message if file has > 500 features: "Limited to 500 for performance"
- The simulation will no longer freeze
- You can pan and zoom smoothly

## Recommendations

### For Better Performance:

1. **Simplify your GeoJSON files**:
   - Use tools like [mapshaper.org](https://mapshaper.org) to reduce feature count
   - Remove unnecessary detail
   - Combine similar features

2. **Create separate GeoJSON files**:
   - `SGF_Runway.geojson` - Just runways (high priority)
   - `SGF_Taxiways.geojson` - Just taxiways
   - `SGF_Buildings.geojson` - Buildings and terminals
   - Load only what you need per scenario

3. **Filter by zoom level**:
   - Show detailed features only when zoomed in
   - Show simplified features when zoomed out

### Adjusting the Feature Limit:

In `src/rendering/simulation.py` line 206, you can change:
```python
max_features = 500  # Increase or decrease based on your needs
```

- **Lower (100-300)**: Better performance, less detail
- **Higher (1000+)**: More detail, may cause lag on slower systems

## Testing

Run the simulation and check:
- ✅ No freezing on startup
- ✅ Can see airport features
- ✅ Can pan and zoom smoothly
- ✅ Debug info shows in top-right corner
