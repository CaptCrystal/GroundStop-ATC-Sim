# AsdeSim Scenarios Documentation

## Overview

The `scenarios.json` file defines all available scenarios, airports, and their configurations for the AsdeSim simulator.

## File Structure

### Scenarios

Each scenario contains:

- **id**: Unique identifier (e.g., `"kjfk_rush_hour"`)
- **name**: Display name (e.g., `"JFK - Morning Rush Hour"`)
- **airport_code**: ICAO airport code (e.g., `"KJFK"`)
- **airport_name**: Full airport name
- **description**: Scenario description
- **difficulty**: `"easy"`, `"normal"`, `"hard"`, `"realistic"`, or `"custom"`
- **duration_minutes**: Expected scenario duration
- **geojson_file**: Path to airport GeoJSON file (relative to project root)
- **thumbnail**: Path to thumbnail image
- **initial_conditions**: Starting conditions
  - `time_of_day`: 24-hour format (e.g., `"07:00"`)
  - `weather`: `"clear"`, `"cloudy"`, `"rain"`, `"snow"`, `"fog"`
  - `active_runways`: Array of active runway identifiers
  - `wind`: Direction (degrees) and speed (knots)
  - `initial_aircraft_count`: Number of aircraft at start
  - `spawn_rate`: Aircraft per hour
- **objectives**: Array of scenario objectives
- **tags**: Array of tags for filtering/searching

### Airports

Each airport contains:

- **code**: ICAO airport code
- **name**: Full airport name
- **city**: City location
- **country**: Country
- **geojson_file**: Path to GeoJSON file
- **runways**: Array of runway data
  - `name`: Runway identifier (e.g., `"04L/22R"`)
  - `length_ft`: Length in feet
  - `width_ft`: Width in feet
- **elevation_ft**: Airport elevation
- **coordinates**: Latitude and longitude

## Adding New Scenarios

1. Create a GeoJSON file for the airport (if not exists)
2. Add airport to the `airports` array
3. Create scenario entry in `scenarios` array
4. Update `metadata.total_scenarios` and `metadata.total_airports`

### Example Scenario

```json
{
  "id": "example_scenario",
  "name": "Example Airport - Test Scenario",
  "airport_code": "KEXM",
  "airport_name": "Example International Airport",
  "description": "A test scenario for demonstration purposes.",
  "difficulty": "normal",
  "duration_minutes": 30,
  "geojson_file": "data/airports/kexm.geojson",
  "thumbnail": "data/thumbnails/kexm.png",
  "initial_conditions": {
    "time_of_day": "12:00",
    "weather": "clear",
    "active_runways": ["09", "27"],
    "wind": {
      "direction": 90,
      "speed_knots": 10
    },
    "initial_aircraft_count": 8,
    "spawn_rate": 12
  },
  "objectives": [
    "Complete 30 taxi clearances",
    "Maintain safety standards"
  ],
  "tags": ["training", "normal"]
}
```

## GeoJSON Format

Airport GeoJSON files should follow this structure:

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "LineString",
        "coordinates": [[lon1, lat1], [lon2, lat2]]
      },
      "properties": {
        "type": "runway",
        "name": "09/27",
        "heading": 90,
        "length_ft": 10000
      }
    },
    {
      "type": "Feature",
      "geometry": {
        "type": "LineString",
        "coordinates": [[lon1, lat1], [lon2, lat2]]
      },
      "properties": {
        "type": "taxiway",
        "name": "A"
      }
    },
    {
      "type": "Feature",
      "geometry": {
        "type": "Point",
        "coordinates": [lon, lat]
      },
      "properties": {
        "type": "gate",
        "stand_number": "A1"
      }
    }
  ]
}
```

## Feature Types

### Runways
- **Type**: `LineString`
- **Properties**: `type: "runway"`, `name`, `heading`, `length_ft`

### Taxiways
- **Type**: `LineString`
- **Properties**: `type: "taxiway"`, `name`

### Gates/Stands
- **Type**: `Point`
- **Properties**: `type: "gate"`, `stand_number`

### Hold-Short Lines
- **Type**: `Point`
- **Properties**: `type: "hold_short"`, `runway`

### Aprons
- **Type**: `Polygon`
- **Properties**: `type: "apron"`, `name`

## Using the Scenario Manager

```python
from src.core.scenario_manager import get_scenario_manager

# Get the global scenario manager
manager = get_scenario_manager()

# Get all scenarios
all_scenarios = manager.get_all_scenarios()

# Get a specific scenario
scenario = manager.get_scenario_by_id("kjfk_rush_hour")

# Filter by difficulty
hard_scenarios = manager.get_scenarios_by_difficulty("hard")

# Filter by airport
jfk_scenarios = manager.get_scenarios_by_airport("KJFK")

# Search scenarios
results = manager.search_scenarios("rush hour")

# Get airport info
airport = manager.get_airport_by_code("KJFK")
```

## Difficulty Levels

- **Easy**: Light traffic, simple layouts, clear weather
- **Normal**: Moderate traffic, standard operations
- **Hard**: Heavy traffic, complex routing, challenging conditions
- **Realistic**: Maximum realism with real-world procedures
- **Custom**: User-defined parameters

## Tags

Common tags for filtering:
- `training`, `tutorial`
- `departure`, `arrival`, `mixed-ops`
- `high-traffic`, `low-visibility`
- `weather`, `fog`, `rain`, `snow`
- `night`, `cargo`
- `realistic`, `challenging`
- `freeplay`, `sandbox`, `custom`
