# AsdeSim - Airport Ground Control Simulator

A realistic airport surface detection equipment and ground control simulator using real-world airport data from GeoJSON files.

## Features

- **Realistic Airport Layouts**: Import real-world airport data via GeoJSON
- **Ground Control Simulation**: Manage aircraft taxiing, runway crossings, and gate assignments
- **Standard ATC Phraseology**: Authentic air traffic control communications
- **Pathfinding**: Intelligent routing through taxiway networks
- **Conflict Detection**: Prevent runway incursions and aircraft conflicts

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

## Project Structure

```
AsdeSim/
├── src/
│   ├── core/          # Core simulation logic
│   ├── atc/           # Air traffic control systems
│   ├── rendering/     # Pygame rendering and UI
│   └── utils/         # Utilities (GeoJSON parsing, coordinates)
├── data/
│   └── airports/      # Airport GeoJSON files
├── main.py            # Entry point
└── requirements.txt   # Python dependencies
```

## GeoJSON Airport Format

Airport data should be in GeoJSON format with the following feature types:

- **Runways**: LineString with properties `name`, `heading`, `length`
- **Taxiways**: LineString with property `name`
- **Gates**: Point features with property `stand_number`
- **Hold-short lines**: Point features at runway intersections

## Development Status

🚧 **Alpha** - Core features in development

## License

MIT License
