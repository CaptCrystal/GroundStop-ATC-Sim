"""
Scenario management system for loading and managing airport scenarios
"""
import json
import os
from typing import Dict, List, Optional


class Scenario:
    """Represents a single scenario configuration"""
    
    def __init__(self, data: Dict):
        self.id = data.get("id")
        self.name = data.get("name")
        self.airport_code = data.get("airport_code")
        self.airport_name = data.get("airport_name")
        self.city = data.get("city", "")
        self.country = data.get("country", "")
        self.description = data.get("description")
        self.difficulty = data.get("difficulty")
        self.duration_minutes = data.get("duration_minutes")
        
        # Support both single file and multiple files
        self.geojson_file = data.get("geojson_file")
        self.geojson_files = data.get("geojson_files", [])
        
        # If geojson_files is empty but geojson_file exists, use single file
        if not self.geojson_files and self.geojson_file:
            self.geojson_files = [self.geojson_file]
        
        self.thumbnail = data.get("thumbnail")
        self.diagram = data.get("diagram")
        self.initial_conditions = data.get("initial_conditions", {})
        self.objectives = data.get("objectives", [])
        self.tags = data.get("tags", [])
    
    def get_geojson_path(self) -> Optional[str]:
        """Get the full path to the GeoJSON file (returns first file if multiple)"""
        if self.geojson_files:
            return os.path.abspath(self.geojson_files[0])
        return None
    
    def get_geojson_paths(self) -> List[str]:
        """Get the full paths to all GeoJSON files"""
        return [os.path.abspath(f) for f in self.geojson_files]
    
    def get_thumbnail_path(self) -> Optional[str]:
        """Get the full path to the thumbnail image"""
        if self.thumbnail and os.path.exists(self.thumbnail):
            return os.path.abspath(self.thumbnail)
        return None
    
    def has_geojson(self) -> bool:
        """Check if at least one GeoJSON file exists"""
        paths = self.get_geojson_paths()
        return len(paths) > 0 and any(os.path.exists(p) for p in paths)
    
    def get_initial_time(self) -> str:
        """Get the initial time of day"""
        return self.initial_conditions.get("time_of_day", "12:00")
    
    def get_weather(self) -> str:
        """Get the weather condition"""
        return self.initial_conditions.get("weather", "clear")
    
    def get_active_runways(self) -> List[str]:
        """Get list of active runways"""
        return self.initial_conditions.get("active_runways", [])
    
    def get_wind_info(self) -> Dict:
        """Get wind information"""
        return self.initial_conditions.get("wind", {"direction": 0, "speed_knots": 0})
    
    def get_spawn_rate(self) -> int:
        """Get aircraft spawn rate"""
        return self.initial_conditions.get("spawn_rate", 10)
    
    def get_initial_aircraft_count(self) -> int:
        """Get initial number of aircraft"""
        return self.initial_conditions.get("initial_aircraft_count", 5)
    
    def get_diagram_path(self) -> Optional[str]:
        """Get the full path to the airport diagram"""
        if self.diagram and os.path.exists(self.diagram):
            return os.path.abspath(self.diagram)
        return None
    
    def __repr__(self):
        return f"<Scenario {self.id}: {self.name}>"


class Airport:
    """Represents an airport with its metadata"""
    
    def __init__(self, data: Dict):
        self.code = data.get("code")
        self.name = data.get("name")
        self.city = data.get("city")
        self.country = data.get("country")
        
        # Support both single file and multiple files
        self.geojson_file = data.get("geojson_file")
        self.geojson_files = data.get("geojson_files", [])
        
        # If geojson_files is empty but geojson_file exists, use single file
        if not self.geojson_files and self.geojson_file:
            self.geojson_files = [self.geojson_file]
        
        # Airport diagram
        self.diagram = data.get("diagram")
        
        # Airport infrastructure
        self.runways = data.get("runways", [])
        self.gates = data.get("gates", [])
        self.taxiways = data.get("taxiways", [])
        self.ramps = data.get("ramps", [])
        
        # GA apron - non-controlled movement area for general aviation
        ga_apron_data = data.get("ga_apron", [])
        self.ga_apron = []
        if ga_apron_data:
            # Convert from dict format to tuple format (lat, lon)
            for point in ga_apron_data:
                if isinstance(point, dict) and 'x' in point and 'y' in point:
                    # Ensure values are floats, not strings
                    lat = float(point['x']) if point['x'] is not None else 0.0
                    lon = float(point['y']) if point['y'] is not None else 0.0
                    self.ga_apron.append((lat, lon))
                elif isinstance(point, (list, tuple)) and len(point) >= 2:
                    lat = float(point[0]) if point[0] is not None else 0.0
                    lon = float(point[1]) if point[1] is not None else 0.0
                    self.ga_apron.append((lat, lon))
        
        # Aircraft assignments
        self.aircraft = data.get("aircraft", [])
        
        # Controllers
        self.controllers = data.get("controllers", [])
        
        # Extract frequencies from controllers
        self.ground_freq = ""
        self.tower_freq = ""
        for controller in self.controllers:
            name = controller.get("name", "").lower()
            frequency = controller.get("frequency", "")
            if name == "ground":
                self.ground_freq = frequency
            elif name == "tower":
                self.tower_freq = frequency
        
        # Location data
        self.elevation_ft = data.get("elevation_ft", 0)
        self.coordinates = data.get("coordinates", {"lat": 0, "lon": 0})
    
    def get_geojson_path(self) -> Optional[str]:
        """Get the full path to the GeoJSON file (returns first file if multiple)"""
        if self.geojson_files:
            return os.path.abspath(self.geojson_files[0])
        return None
    
    def get_geojson_paths(self) -> List[str]:
        """Get the full paths to all GeoJSON files"""
        return [os.path.abspath(f) for f in self.geojson_files]
    
    def has_geojson(self) -> bool:
        """Check if at least one GeoJSON file exists"""
        paths = self.get_geojson_paths()
        return len(paths) > 0 and any(os.path.exists(p) for p in paths)
    
    def get_runway_count(self) -> int:
        """Get the number of runways"""
        return len(self.runways)
    
    def get_longest_runway(self) -> Optional[Dict]:
        """Get the longest runway"""
        if not self.runways:
            return None
        return max(self.runways, key=lambda r: r.get("length_ft", 0))
    
    def get_diagram_path(self) -> Optional[str]:
        """Get the full path to the airport diagram"""
        if self.diagram and os.path.exists(self.diagram):
            return os.path.abspath(self.diagram)
        return None
    
    def __repr__(self):
        return f"<Airport {self.code}: {self.name}>"


class ScenarioManager:
    """Manages loading and accessing scenarios and airports"""
    
    def __init__(self, scenarios_file: str = None):
        self.scenarios_file = scenarios_file
        self.scenarios: List[Scenario] = []
        self.airports: List[Airport] = []
        self.metadata: Dict = {}
        
        self.load_scenarios()
    
    def load_scenarios(self) -> bool:
        """Load airports from individual scenario files in scenarios/ directory"""
        scenarios_dir = "scenarios"
        if not os.path.exists(scenarios_dir):
            print(f"Warning: Scenarios directory not found: {scenarios_dir}")
            return False
        
        try:
            # Load all JSON files from scenarios directory
            scenario_files = [f for f in os.listdir(scenarios_dir) if f.endswith('.json')]
            
            if not scenario_files:
                print(f"Warning: No scenario files found in {scenarios_dir}")
                return False
            
            # Load each scenario file as an airport
            for filename in scenario_files:
                file_path = os.path.join(scenarios_dir, filename)
                try:
                    with open(file_path, 'r') as f:
                        file_data = json.load(f)
                    
                    # Handle both formats: direct airport data or wrapped in "airports" array
                    if 'airports' in file_data and isinstance(file_data['airports'], list):
                        # Extract first airport from array
                        airport_data = file_data['airports'][0]
                    else:
                        # Direct airport data
                        airport_data = file_data
                    
                    # Create Airport object from the data
                    airport = Airport(airport_data)
                    self.airports.append(airport)
                    
                    # Always create a freeplay scenario for each airport
                    # Extract airport code from filename if not in data (e.g., KSGF.json -> KSGF)
                    airport_code = airport.code
                    if not airport_code:
                        airport_code = filename.replace('.json', '').upper()
                    
                    airport_name = airport.name or airport_code
                    
                    scenario_data = {
                        "id": f"{airport_code.lower()}_freeplay",
                        "name": airport_name,
                        "airport_code": airport_code,
                        "airport_name": airport_name,
                        "city": airport.city or "",
                        "country": airport.country or "USA",
                        "description": f"Manage ground operations at {airport_name}. Handle arrivals, departures, and ground traffic.",
                        "difficulty": "custom",
                        "duration_minutes": 0,  # Unlimited (freeplay)
                        "geojson_files": airport.geojson_files if airport.geojson_files else [],
                        "diagram": airport.diagram,  # Include diagram from airport
                        "initial_conditions": {
                            "time_of_day": "12:00",
                            "weather": "clear",
                            "active_runways": [airport.runways[0]["name"]] if airport.runways and len(airport.runways) > 0 else [],
                            "wind": {"direction": 0, "speed_knots": 5},
                            "initial_aircraft_count": 0,  # No initial aircraft (spawns only)
                            "spawn_rate": 10
                        },
                        "objectives": [],
                        "tags": ["freeplay"]
                    }
                    self.scenarios.append(Scenario(scenario_data))
                    print(f"Created freeplay scenario for {airport_code}: {airport_name}")
                    
                except Exception as e:
                    print(f"Error loading scenario file {filename}: {e}")
                    continue
            
            print(f"Loaded {len(self.scenarios)} scenarios and {len(self.airports)} airports from {scenarios_dir}")
            return True
            
        except Exception as e:
            print(f"Error loading scenarios: {e}")
            return False
    
    def get_scenario_by_id(self, scenario_id: str) -> Optional[Scenario]:
        """Get a scenario by its ID"""
        for scenario in self.scenarios:
            if scenario.id == scenario_id:
                return scenario
        return None
    
    def get_scenarios_by_difficulty(self, difficulty: str) -> List[Scenario]:
        """Get all scenarios of a specific difficulty"""
        return [s for s in self.scenarios if s.difficulty == difficulty]
    
    def get_scenarios_by_airport(self, airport_code: str) -> List[Scenario]:
        """Get all scenarios for a specific airport"""
        return [s for s in self.scenarios if s.airport_code == airport_code]
    
    def get_scenarios_by_tag(self, tag: str) -> List[Scenario]:
        """Get all scenarios with a specific tag"""
        return [s for s in self.scenarios if tag in s.tags]
    
    def get_airport_by_code(self, code: str) -> Optional[Airport]:
        """Get an airport by its ICAO code"""
        for airport in self.airports:
            if airport.code == code:
                return airport
        return None
    
    def get_all_scenarios(self) -> List[Scenario]:
        """Get all available scenarios"""
        return self.scenarios
    
    def get_all_airports(self) -> List[Airport]:
        """Get all available airports"""
        return self.airports
    
    def get_available_scenarios(self) -> List[Scenario]:
        """Get scenarios that have their GeoJSON files available"""
        return [s for s in self.scenarios if s.has_geojson() or s.geojson_file is None]
    
    def get_difficulties(self) -> List[str]:
        """Get list of unique difficulty levels"""
        difficulties = set(s.difficulty for s in self.scenarios)
        # Sort in logical order
        order = ["easy", "normal", "hard", "realistic", "custom"]
        return [d for d in order if d in difficulties]
    
    def get_tags(self) -> List[str]:
        """Get list of all unique tags"""
        tags = set()
        for scenario in self.scenarios:
            tags.update(scenario.tags)
        return sorted(list(tags))
    
    def search_scenarios(self, query: str) -> List[Scenario]:
        """Search scenarios by name, description, or airport"""
        query = query.lower()
        results = []
        
        for scenario in self.scenarios:
            if (query in scenario.name.lower() or
                query in scenario.description.lower() or
                query in scenario.airport_code.lower() or
                query in scenario.airport_name.lower()):
                results.append(scenario)
        
        return results
    
    def get_version(self) -> str:
        """Get the scenarios file version"""
        return self.metadata.get("version", "unknown")
    
    def __repr__(self):
        return f"<ScenarioManager: {len(self.scenarios)} scenarios, {len(self.airports)} airports>"


# Global instance
_scenario_manager = None

def get_scenario_manager() -> ScenarioManager:
    """Get or create the global scenario manager instance"""
    global _scenario_manager
    if _scenario_manager is None:
        _scenario_manager = ScenarioManager()
    return _scenario_manager
