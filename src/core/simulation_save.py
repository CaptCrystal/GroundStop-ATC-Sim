"""
Simulation save/load system for persisting and restoring simulation state
"""

import json
import os
import time
from datetime import datetime
from typing import Dict, Any, Optional


class SimulationSaveManager:
    """Manages saving and loading simulation state to/from JSON files"""
    
    def __init__(self, save_dir="data/saves"):
        self.save_dir = save_dir
        self.current_save_file = os.path.join(save_dir, "current_simulation.json")
        self.ensure_save_directory()
    
    def ensure_save_directory(self):
        """Create save directory if it doesn't exist"""
        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir, exist_ok=True)
    
    def save_simulation_state(self, simulation_screen) -> bool:
        """
        Save current simulation state to JSON file
        
        Args:
            simulation_screen: The SimulationScreen instance to save
            
        Returns:
            bool: True if save successful, False otherwise
        """
        try:
            if not simulation_screen or not simulation_screen.aircraft_manager:
                print("Cannot save: No active simulation")
                return False
            
            # Extract airport information from multiple sources
            airport_code = 'UNKNOWN'
            airport_name = 'Unknown Airport'
            
            # Try scenario first
            if hasattr(simulation_screen, 'scenario') and simulation_screen.scenario:
                airport_code = getattr(simulation_screen.scenario, 'airport_code', 'UNKNOWN')
                airport_name = getattr(simulation_screen.scenario, 'airport_name', 'Unknown Airport')
            
            # Fallback to airport_data
            if airport_code == 'UNKNOWN' and hasattr(simulation_screen, 'airport_data') and simulation_screen.airport_data:
                airport_code = simulation_screen.airport_data.get('code', 'UNKNOWN')
                airport_name = simulation_screen.airport_data.get('name', 'Unknown Airport')
            
            # Gather simulation data
            save_data = {
                "metadata": {
                    "timestamp": time.time(),
                    "datetime": datetime.utcnow().isoformat() + "Z",
                    "version": "1.0",
                    "airport_code": airport_code,
                    "airport_name": airport_name
                },
                "simulation_state": {
                    "elapsed_time": getattr(simulation_screen, 'elapsed_time', 0.0),
                    "is_paused": simulation_screen.top_menu_bar.is_paused if simulation_screen.top_menu_bar else False,
                    "time_acceleration": getattr(simulation_screen.top_menu_bar, 'time_acceleration', 1.0) if simulation_screen.top_menu_bar else 1.0,
                    "camera_x": getattr(simulation_screen, 'camera_x', 0),
                    "camera_y": getattr(simulation_screen, 'camera_y', 0),
                    "zoom": getattr(simulation_screen, 'zoom', 1.0)
                },
                "aircraft_data": self._extract_aircraft_data(simulation_screen.aircraft_manager),
                "atc_data": self._extract_atc_data(simulation_screen),
                "weather_data": self._extract_weather_data(simulation_screen),
                "asde_config": self._extract_asde_config(simulation_screen)
            }
            
            # Write to file
            with open(self.current_save_file, 'w') as f:
                json.dump(save_data, f, indent=2)
            
            print(f"✓ Simulation saved to {self.current_save_file}")
            return True
            
        except Exception as e:
            print(f"✗ Failed to save simulation: {e}")
            return False
    
    def load_simulation_state(self) -> Optional[Dict[str, Any]]:
        """
        Load simulation state from JSON file
        
        Returns:
            Dict containing saved simulation data, or None if no save exists
        """
        try:
            if not os.path.exists(self.current_save_file):
                print("No saved simulation found")
                return None
            
            with open(self.current_save_file, 'r') as f:
                save_data = json.load(f)
            
            # Validate save data structure
            if not self._validate_save_data(save_data):
                print("Invalid save data format")
                return None
            
            print(f"✓ Loaded simulation save from {save_data['metadata']['datetime']}")
            return save_data
            
        except Exception as e:
            print(f"✗ Failed to load simulation: {e}")
            return None
    
    def has_saved_simulation(self) -> bool:
        """Check if a saved simulation exists"""
        return os.path.exists(self.current_save_file)
    
    def get_save_info(self) -> Optional[Dict[str, str]]:
        """Get information about the saved simulation without loading full data"""
        try:
            if not self.has_saved_simulation():
                return None
            
            with open(self.current_save_file, 'r') as f:
                save_data = json.load(f)
            
            metadata = save_data.get('metadata', {})
            sim_state = save_data.get('simulation_state', {})
            aircraft_data = save_data.get('aircraft_data', {})
            
            return {
                'airport_code': metadata.get('airport_code', 'UNKNOWN'),
                'airport_name': metadata.get('airport_name', 'Unknown Airport'),
                'datetime': metadata.get('datetime', 'Unknown time'),
                'elapsed_time': sim_state.get('elapsed_time', 0),
                'aircraft_count': len(aircraft_data.get('aircraft', [])),
                'is_paused': sim_state.get('is_paused', False)
            }
            
        except Exception as e:
            print(f"Error reading save info: {e}")
            return None
    
    def _extract_aircraft_data(self, aircraft_manager) -> Dict[str, Any]:
        """Extract aircraft data for saving"""
        aircraft_data = {
            'aircraft': [],
            'spawn_rates': {},
            'next_pushback_times': {}
        }
        
        try:
            # Extract spawn rates (per-hour)
            if hasattr(aircraft_manager, 'dep_spawn_rate'):
                aircraft_data['spawn_rates']['dep_spawn_rate'] = aircraft_manager.dep_spawn_rate
            if hasattr(aircraft_manager, 'arr_spawn_rate'):
                aircraft_data['spawn_rates']['arr_spawn_rate'] = aircraft_manager.arr_spawn_rate
            
            # Extract aircraft data
            for aircraft in aircraft_manager.get_all_aircraft():
                aircraft_info = {
                    'callsign': aircraft.get_callsign(),
                    'flight_number': getattr(aircraft, 'flight_number', None),
                    'aircraft_type': getattr(aircraft, 'aircraft_type', 'UNKNOWN'),
                    'airline': getattr(aircraft, 'airline', ''),
                    'state': aircraft.state,
                    'position': list(aircraft.position) if hasattr(aircraft, 'position') else None,
                    'heading': getattr(aircraft, 'heading', 0),
                    'speed': getattr(aircraft, 'speed', 0),
                    'gate': getattr(aircraft, 'gate', None),
                    'beacon': getattr(aircraft, 'beacon', None) or getattr(aircraft, 'current_squawk_code', None),
                    'cid': getattr(aircraft, 'cid', None),
                    'destination': getattr(aircraft, 'destination', None),
                    'route': getattr(aircraft, 'route', None),
                    'expected_runway': getattr(aircraft, 'expected_runway', None),
                    'show_datatag': getattr(aircraft, 'show_datatag', True),
                    'tag_direction': getattr(aircraft, 'tag_direction', None),
                    'pushback_requested': getattr(aircraft, 'pushback_requested', False),
                    'taxi_requested': getattr(aircraft, 'taxi_requested', False),
                    'cleared_to_pushback': getattr(aircraft, 'cleared_to_pushback', False),
                    'cleared_to_taxi': getattr(aircraft, 'cleared_to_taxi', False)
                }
                aircraft_data['aircraft'].append(aircraft_info)
            
        except Exception as e:
            print(f"Error extracting aircraft data: {e}")
        
        return aircraft_data
    
    def _extract_atc_data(self, simulation_screen) -> Dict[str, Any]:
        """Extract ATC system data for saving"""
        atc_data = {
            'command_history': getattr(simulation_screen, 'command_history', []),
            'last_callsign': getattr(simulation_screen, 'last_callsign', ''),
            'tower_frequency': getattr(simulation_screen, 'tower_frequency', 118.1),
            'ground_frequency': getattr(simulation_screen, 'ground_frequency', 121.9)
        }
        
        return atc_data
    
    def _extract_weather_data(self, simulation_screen) -> Dict[str, Any]:
        """Extract weather data for saving"""
        weather_data = {}
        
        try:
            if hasattr(simulation_screen, 'weather_panel') and simulation_screen.weather_panel:
                weather_data = {
                    'metar': getattr(simulation_screen.weather_panel, 'current_metar', ''),
                    'temperature': getattr(simulation_screen.weather_panel, 'temperature', None),
                    'wind_speed': getattr(simulation_screen.weather_panel, 'wind_speed', None),
                    'wind_direction': getattr(simulation_screen.weather_panel, 'wind_direction', None),
                    'visibility': getattr(simulation_screen.weather_panel, 'visibility', None),
                    'altimeter': getattr(simulation_screen.weather_panel, 'altimeter', None)
                }
        except Exception as e:
            print(f"Error extracting weather data: {e}")
        
        return weather_data
    
    def _extract_asde_config(self, simulation_screen) -> Dict[str, Any]:
        """Extract ASDE/runway config for saving so load can restore departure/arrival runways"""
        out = {}
        try:
            asde = getattr(simulation_screen, 'asde_config', None)
            if asde:
                out = {
                    'departure_runways': list(asde.get('departure_runways', [])),
                    'arrival_runways': list(asde.get('arrival_runways', [])),
                    'active_runways': list(asde.get('active_runways', [])),
                    'leader_line': asde.get('leader_line', 60),
                    'metar_cache': asde.get('metar_cache', ''),
                }
        except Exception as e:
            print(f"Error extracting asde config: {e}")
        return out
    
    def _validate_save_data(self, save_data: Dict[str, Any]) -> bool:
        """Validate that save data has required structure"""
        required_sections = ['metadata', 'simulation_state', 'aircraft_data']
        
        for section in required_sections:
            if section not in save_data:
                return False
        
        # Check metadata
        metadata = save_data['metadata']
        if not all(key in metadata for key in ['timestamp', 'version']):
            return False
        
        return True
    
    def delete_save(self) -> bool:
        """Delete the current save file"""
        try:
            if os.path.exists(self.current_save_file):
                os.remove(self.current_save_file)
                print("✓ Save file deleted")
                return True
            return False
        except Exception as e:
            print(f"✗ Failed to delete save file: {e}")
            return False
