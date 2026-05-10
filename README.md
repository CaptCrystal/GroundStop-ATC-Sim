# AsdeSim - Airport Ground Control Simulator

A realistic airport surface detection equipment and ground control simulator using real-world airport data from GeoJSON files.

## Features

### Core Simulation
- **Realistic Airport Layouts**: Import real-world airport data via GeoJSON
- **Automatic Aircraft Spawning**: Configurable departure/arrival spawn rates
- **Intelligent Pathfinding**: Smart routing through taxiway networks with nearest-point detection
- **Realistic Aircraft Physics**: Smooth acceleration, deceleration, and turning
- **Pushback Operations**: Realistic two-phase pushback with arcing maneuvers

### ATC Operations
- **Command Bar System**: Press `/` to enter ATC commands with command history
- **Standard ATC Phraseology**: Authentic air traffic control communications with proper readbacks
- **Hold Short Enforcement**: Automatic runway incursion prevention
- **Runway Crossing Clearances**: Explicit clearance required for runway crossings
- **Radio Communications**: Color-coded ATC (green) and pilot (cyan) transmissions with audio

### Departure Management
- **Automatic Route Assignment**: Aircraft automatically assigned realistic departure routes
- **Exit Fix Display**: Aircraft data tags show destination exit fix
- **Route Database**: Configurable departure routes with airlines, altitudes, and procedures

### Visual Features
- **Modern Aircraft Data Tags**: Two-line display showing callsign + exit fix and aircraft type
- **Real-time Aircraft Rendering**: Rotated aircraft icons with heading indication
- **GeoJSON Rendering**: Runways, taxiways, aprons, and airport features
- **Dev Mode**: Toggle detailed overlays for gates, taxiways, and runways

## Installation

1. Install Python 3.10 or higher
2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Running the Simulator

```bash
python main.py
```

## Controls

- **`/`** - Open ATC command bar
- **Enter** - Execute command
- **ESC** - Cancel command input
- **Up/Down Arrows** - Navigate command history
- **Mouse Wheel** - Zoom in/out
- **Arrow Keys** - Pan view
- **D** - Toggle dev mode overlays

## ATC Commands

### Basic Format
```
[flight_number] [command] [arguments]
```

### Available Commands
- **`pa`** - Pushback approved
  - Example: `100 pa`
- **`t[runway][via]`** - Taxi clearance
  - Example: `100 t02ua` (taxi to runway 02 via U, A)
- **`h[runway]`** - Hold short of runway
  - Example: `100 h02` (hold short runway 02)
- **`c[runway]`** - Cross runway clearance
  - Example: `100 c02` (cross runway 02)
- **`ct`** - Contact tower
  - Example: `100 ct`
- **`help`** - Show available commands
- **`clear`** - Clear command output

## Project Structure

```
AsdeSim/
├── src/
│   ├── core/          # Core simulation logic (aircraft, spawning)
│   ├── atc/           # Air traffic control command system
│   ├── rendering/     # Pygame rendering and UI
│   └── audio/         # Audio system (future)
├── data/
│   ├── airports/      # Airport GeoJSON files
│   ├── audio/         # Sound effects and music
│   ├── fonts/         # Custom fonts
│   └── images/        # Aircraft sprites and UI elements
├── scenarios.json     # Airport and departure route configuration
├── main.py            # Entry point
└── requirements.txt   # Python dependencies
```

## Configuration (scenarios.json)

### Airport Configuration
```json
{
  "airports": [{
    "code": "KSGF",
    "name": "Springfield-Branson National Airport",
    "geojson_files": ["path/to/runway.geojson", "path/to/taxiway.geojson"],
    "gates": [...],
    "taxiways": [...],
    "runways": [...],
    "departures": [...],
    "dep_spawn_rate": 15,
    "arr_spawn_rate": 21
  }]
}
```

### Departure Routes
```json
{
  "airlines": [{"fleet": "default", "icao": "ENY"}],
  "altitude": 35000,
  "destination": "KCLT",
  "route": "SGF V159 DGD BNA VXV COMDY FILPZ4",
  "exit": "SGF"
}
```

### Spawn Rates
- **dep_spawn_rate**: Departures per hour (e.g., 15 = 1 every 4 minutes)
- **arr_spawn_rate**: Arrivals per hour (e.g., 21 = 1 every ~2.9 minutes)

## Aircraft Data Tags

Aircraft display a modern two-line data tag:

**Line 1 (Cyan):** `CALLSIGN EXIT`
- Callsign: Airline code + flight number (e.g., ENY100)
- Exit: First 3 letters of departure exit fix (e.g., SGF)

**Line 2 (Green):** `AIRCRAFT_TYPE`
- Aircraft ICAO type code (e.g., E170, CRJ9, B738)

**Example:**
```
ENY100 SGF  ← Cyan
E170        ← Green
```

## Radio Communications

### Color Coding
- **Green (0, 224, 21)**: ATC transmissions
- **Cyan (0, 255, 255)**: Aircraft transmissions
- **Semi-transparent background**: For readability

### Realistic Phraseology
- **ATC:** "ENY100, pushback approved"
- **Pilot:** "Pushback approved, ENY100"
- **ATC:** "ENY100, taxi runway 02 via Uniform Alpha"
- **Pilot:** "Runway 02 via Uniform Alpha, ENY100"

## Current Features in Development

- ✅ Automatic departure route assignment
- ✅ Hold short enforcement
- ✅ Realistic pushback with arcing
- ✅ Smart taxiway pathfinding
- ✅ ATC command system with history
- ✅ Radio communications with readbacks
- 🚧 Arrival aircraft spawning
- 🚧 Takeoff and landing operations
- 🚧 Conflict detection and resolution
- 🚧 Weather system
- 🚧 Multiple airport support

## Development Status

🚧 **Alpha** - Core features in development

## License

MIT License
