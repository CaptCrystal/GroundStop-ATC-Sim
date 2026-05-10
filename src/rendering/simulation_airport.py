"""
Airport data and state management mixin for SimulationScreen
"""
import json
import os


class AirportMixin:
    """Mixin providing airport data loading and state management for SimulationScreen."""

    def restore_simulation_state(self):
        """Restore simulation state from saved data (camera, pause, ATC, weather, ASDE). Aircraft restored earlier in init."""
        if not self.save_data:
            return

        try:
            print(" Restoring simulation state from save...")

            sim_state = self.save_data.get('simulation_state', {})
            self.elapsed_time = float(sim_state.get('elapsed_time', 0.0))

            self.camera_x = float(sim_state.get('camera_x', 0))
            self.camera_y = float(sim_state.get('camera_y', 0))
            self.zoom = float(sim_state.get('zoom', 1.0))
            print(f" Camera: x={self.camera_x}, y={self.camera_y}, zoom={self.zoom}")

            if self.top_menu_bar:
                self.top_menu_bar.is_paused = bool(sim_state.get('is_paused', False))
                accel = sim_state.get('time_acceleration', 1.0)
                if hasattr(self.top_menu_bar, 'time_acceleration'):
                    self.top_menu_bar.time_acceleration = float(accel)
                print(f"  Paused={self.top_menu_bar.is_paused}, time_accel={accel}")

            atc_data = self.save_data.get('atc_data', {})
            if atc_data:
                self.last_callsign = atc_data.get('last_callsign', '') or ''
                self.command_history = list(atc_data.get('command_history', []))
                if hasattr(self, 'radio_panel') and self.radio_panel:
                    self.radio_panel.tower_frequency = atc_data.get('tower_frequency', 118.1)
                    self.radio_panel.ground_frequency = atc_data.get('ground_frequency', 121.9)
                print(f" ATC: last_callsign restored, {len(self.command_history)} history entries")

            weather_data = self.save_data.get('weather_data', {})
            if weather_data and self.weather_panel:
                if weather_data.get('metar') is not None:
                    self.weather_panel.current_metar = weather_data.get('metar', '') or ''
                for key in ('temperature', 'wind_speed', 'wind_direction', 'visibility', 'altimeter'):
                    val = weather_data.get(key)
                    if val is not None and hasattr(self.weather_panel, key):
                        setattr(self.weather_panel, key, val)
                print(" Weather data restored")

            asde_saved = self.save_data.get('asde_config', {})
            if asde_saved:
                self.asde_config['departure_runways'] = list(asde_saved.get('departure_runways', []))
                self.asde_config['arrival_runways'] = list(asde_saved.get('arrival_runways', []))
                self.asde_config['active_runways'] = list(asde_saved.get('active_runways', []))
                self.asde_config['leader_line'] = int(asde_saved.get('leader_line', 60))
                self.asde_config['metar_cache'] = asde_saved.get('metar_cache', '') or ''
                if self.weather_panel:
                    self.weather_panel.departure_runways = self.asde_config['departure_runways'].copy()
                    self.weather_panel.arrival_runways = self.asde_config['arrival_runways'].copy()
                    self.weather_panel._update_legacy_active_runways()
                if self.top_menu_bar and hasattr(self.top_menu_bar, 'leader_line_length'):
                    self.top_menu_bar.leader_line_length = self.asde_config['leader_line']
                if self.aircraft_manager and hasattr(self.aircraft_manager, 'tower_controller'):
                    self.aircraft_manager.tower_controller.set_departure_runways(self.asde_config['departure_runways'])
                    self.aircraft_manager.tower_controller.set_arrival_runways(self.asde_config['arrival_runways'])
                print(" ASDE/runway config restored")

            print(" Simulation state restored successfully")

        except Exception as e:
            print(f" Error restoring simulation state: {e}")
            import traceback
            traceback.print_exc()

    def load_settings(self):
        """Load settings from settings file"""
        settings_path = "data/settings.json"
        try:
            if os.path.exists(settings_path):
                with open(settings_path, 'r') as f:
                    return json.load(f)
            else:
                # Create default settings file
                default_settings = {
                    "time_settings": 0,  # Local time by default
                    "sound_enabled": True,
                    "music_volume": 0.7,
                    "sfx_volume": 0.8
                }
                with open(settings_path, 'w') as f:
                    json.dump(default_settings, f, indent=2)
                return default_settings
        except Exception as e:
            print(f"Error loading settings: {e}")
            return {"time_settings": 0}  # Default to Local (index 0)

    def get_time_setting(self):
        """Get time setting as string from settings"""
        time_index = self.settings.get("time_settings", 0)
        # Dropdown options are ["Local", "Zulu"]
        return "local" if time_index == 0 else "zulu"

    def load_airport_data(self):
        """Load airport data (gates, taxiways, runways) from scenarios/{airport_code}.json or save data"""
        # Handle loading from save data vs new scenario
        if self.save_data:
            # Loading from saved simulation
            metadata = self.save_data.get('metadata', {})
            airport_code = metadata.get('airport_code', 'UNKNOWN')
            airport_name = metadata.get('airport_name', 'Unknown Airport')
            print(f"Loading saved simulation: {airport_name} ({airport_code})")
        else:
            # Loading from new scenario
            airport_code = self.scenario.airport_code if self.scenario else 'UNKNOWN'
            airport_name = self.scenario.airport_name if self.scenario else 'Unknown Airport'
            print(f"Starting airport data load for {airport_code}")

        print(f"Top menu bar exists: {hasattr(self, 'top_menu_bar')}")
        print(f"Top menu bar type: {type(self.top_menu_bar) if hasattr(self, 'top_menu_bar') else 'N/A'}")
        try:
            from src.core.scenario_manager import get_scenario_manager
            manager = get_scenario_manager()
            airport = manager.get_airport_by_code(airport_code)

            if airport:
                # Load the full airport data from scenarios/{airport_code}.json
                scenario_file_path = f'scenarios/{airport_code}.json'
                if not os.path.exists(scenario_file_path):
                    print(f"Error: Scenario file not found: {scenario_file_path}")
                    return

                with open(scenario_file_path, 'r') as f:
                    file_data = json.load(f)

                # Unwrap if scenario uses "airports" array (e.g. KSGF.json / sgf-style)
                if 'airports' in file_data and isinstance(file_data['airports'], list) and len(file_data['airports']) > 0:
                    airport_data = file_data['airports'][0]
                else:
                    airport_data = file_data

                self.airport_data = airport_data

                # When loading from save, scenario is None; create a minimal scenario so save_metar_cache/update_runways etc. work
                if self.save_data and not self.scenario:
                    _airport_code = airport_data.get('code', self.save_data.get('metadata', {}).get('airport_code', 'UNKNOWN'))
                    _geojson_files = airport_data.get('geojson_files', [])
                    def _paths(_f):
                        if isinstance(_f, dict):
                            return [os.path.abspath(spec.get('location', '')) for spec in _f.values() if isinstance(spec, dict) and spec.get('location')]
                        return [os.path.abspath(p) for p in (_f or [])]
                    self.scenario = type('Scenario', (), {
                        'airport_code': _airport_code,
                        'airport_name': airport_data.get('name', 'Unknown Airport'),
                        'get_geojson_paths': lambda: _paths(_geojson_files),
                        'initial_conditions': {},
                    })()
                    print(f"Created minimal scenario for save load: {_airport_code}")

                # Convert ga_apron coordinates to floats to prevent type errors
                if 'ga_apron' in airport_data and airport_data['ga_apron']:
                    converted_apron = []
                    for point in airport_data['ga_apron']:
                        if isinstance(point, dict) and 'x' in point and 'y' in point:
                            lat = float(point['x']) if point['x'] is not None else 0.0
                            lon = float(point['y']) if point['y'] is not None else 0.0
                            converted_apron.append({'x': lat, 'y': lon})
                    airport_data['ga_apron'] = converted_apron

                print(f"Loaded airport data for {airport_code}")
                print(f"  Gates: {len(airport_data.get('gates', []))}")
                print(f"  Taxiways: {len(airport_data.get('taxiways', []))}")
                print(f"  Runways: {len(airport_data.get('runways', []))}")

                # Get ICAO code from airport data (ensure it's the correct ICAO)
                airport_icao = airport_data.get('code', airport_code)
                print(f"Initializing panels with ICAO: {airport_icao}")

                # Initialize radio panel first (before aircraft manager)
                from src.rendering.radio_panel import RadioPanel
                print("Initializing radio panel...")
                self.radio_panel = RadioPanel(
                    self.width, self.height,
                    airport_icao,
                    manager  # Pass scenario_manager
                )
                print(f"Radio panel initialized: {self.radio_panel is not None}")

                # Set available runways for radio panel
                runways = [r.get('name', '') for r in airport_data.get('runways', [])]
                self.radio_panel.set_available_runways(runways)

                # Link radio panel to top menu bar
                print("Linking radio panel to top menu bar...")
                self.top_menu_bar.radio_panel = self.radio_panel
                print(f"Top menu bar radio panel set: {hasattr(self.top_menu_bar, 'radio_panel') and self.top_menu_bar.radio_panel is not None}")

                # Initialize weather panel with airport data
                from src.rendering.weather_panel import WeatherPanel
                print("Initializing weather panel...")
                coords = airport_data.get('coordinates', {})
                lat = coords.get('lat', 0)
                lon = coords.get('lon', 0)

                # Get cached METAR if available
                metar_cache = self.asde_config.get('metar_cache', '')

                self.weather_panel = WeatherPanel(
                    self.width, self.height,
                    airport_icao,
                    lat, lon,
                    metar_cache=metar_cache
                )
                print(f"Weather panel initialized: {self.weather_panel is not None}")

                # Set callback to save METAR cache
                self.weather_panel.metar_cache_callback = self.save_metar_cache
                # Set callback to save active runways (legacy)
                self.weather_panel.active_runways_callback = self.update_active_runways
                # Set callback to save runway configuration (departure/arrival)
                self.weather_panel.runway_config_callback = self.update_runway_config
                # Set available runways
                self.weather_panel.set_available_runways(runways)

                # Link weather panel to top menu bar
                print("Linking weather panel to top menu bar...")
                self.top_menu_bar.weather_panel = self.weather_panel
                print(f"Top menu bar weather panel set: {hasattr(self.top_menu_bar, 'weather_panel') and self.top_menu_bar.weather_panel is not None}")

                # Double-check panel links
                if not hasattr(self.top_menu_bar, 'radio_panel') or self.top_menu_bar.radio_panel is None:
                    print("WARNING: Radio panel link failed, re-linking...")
                    self.top_menu_bar.radio_panel = self.radio_panel

                if not hasattr(self.top_menu_bar, 'weather_panel') or self.top_menu_bar.weather_panel is None:
                    print("WARNING: Weather panel link failed, re-linking...")
                    self.top_menu_bar.weather_panel = self.weather_panel

                # Link aircraft manager to radio panel if it exists
                if hasattr(self, 'aircraft_manager') and self.aircraft_manager:
                    self.radio_panel.aircraft_manager = self.aircraft_manager
                    if hasattr(self.aircraft_manager, 'tower_controller'):
                        self.radio_panel.tower_controller = self.aircraft_manager.tower_controller

                # Check for runway configuration from airport menu (takes priority)
                if hasattr(self.scenario, 'initial_conditions'):
                    initial_cond = self.scenario.initial_conditions
                    if 'departure_runways' in initial_cond and 'arrival_runways' in initial_cond:
                        # Use runway configuration from airport menu
                        if self.weather_panel:
                            self.weather_panel.departure_runways = initial_cond['departure_runways'].copy()
                            self.weather_panel.arrival_runways = initial_cond['arrival_runways'].copy()
                            self.weather_panel._update_legacy_active_runways()

                        print(f"Using runway configuration from airport menu:")
                        print(f"  Departure runways: {initial_cond['departure_runways']}")
                        print(f"  Arrival runways: {initial_cond['arrival_runways']}")

                # Load ASDE-X configuration if present (used as fallback)
                if 'asde_config' in airport_data:
                    asde_cfg = airport_data['asde_config']
                    self.asde_config['leader_line'] = asde_cfg.get('leader_line', 60)
                    self.asde_config['active_runways'] = asde_cfg.get('active_runways', [])
                    self.asde_config['departure_runways'] = asde_cfg.get('departure_runways', [])
                    self.asde_config['arrival_runways'] = asde_cfg.get('arrival_runways', [])
                    self.asde_config['metar_cache'] = asde_cfg.get('metar_cache', '')

                    # Override top menu bar leader line length with airport-specific value
                    if self.top_menu_bar:
                        self.top_menu_bar.leader_line_length = self.asde_config['leader_line']

                    # Load runway configuration into weather panel (only if not already set from menu)
                    if self.weather_panel and not (hasattr(self.scenario, 'initial_conditions') and
                                                  'departure_runways' in self.scenario.initial_conditions):
                        self.weather_panel.departure_runways = self.asde_config['departure_runways']
                        self.weather_panel.arrival_runways = self.asde_config['arrival_runways']
                        # Backward compatibility: if no separate configs, use active_runways for both
                        if not self.weather_panel.departure_runways and not self.weather_panel.arrival_runways:
                            self.weather_panel.departure_runways = self.asde_config['active_runways'].copy()
                            self.weather_panel.arrival_runways = self.asde_config['active_runways'].copy()
                        self.weather_panel._update_legacy_active_runways()

                        print(f"Loaded ASDE-X config:")
                        print(f"  Leader line: {self.asde_config['leader_line']}px")
                        print(f"  Departure runways: {self.asde_config['departure_runways']}")
                        print(f"  Arrival runways: {self.asde_config['arrival_runways']}")
                        print(f"  METAR cache: {'Yes' if self.asde_config['metar_cache'] else 'No'}")

                # Sync runway configuration to tower controller
                if self.aircraft_manager and hasattr(self.aircraft_manager, 'tower_controller') and self.weather_panel:
                    self.aircraft_manager.tower_controller.sync_runways_from_weather_panel(self.weather_panel)
        except Exception as e:
            print(f"Error loading airport data: {e}")

    def _get_scenario_file_path(self):
        """Get the path to the scenario-specific JSON file"""
        airport_code = self.scenario.airport_code if self.scenario else 'UNKNOWN'
        return f'scenarios/{airport_code}.json'

    def _get_scenario_asde_config_target(self, file_data):
        """Return the dict that should hold asde_config when saving (handles airports[] wrapper)."""
        if 'airports' in file_data and isinstance(file_data['airports'], list) and len(file_data['airports']) > 0:
            return file_data['airports'][0]
        return file_data

    def save_metar_cache(self, metar_string):
        """Save METAR string to ASDE config in scenario file"""
        try:
            # Update in-memory config
            self.asde_config['metar_cache'] = metar_string

            # Update scenario file (preserve airports[] wrapper if present)
            scenario_file_path = self._get_scenario_file_path()
            with open(scenario_file_path, 'r') as f:
                file_data = json.load(f)
            target = self._get_scenario_asde_config_target(file_data)
            if 'asde_config' not in target:
                target['asde_config'] = {}
            target['asde_config']['metar_cache'] = metar_string
            with open(scenario_file_path, 'w') as f:
                json.dump(file_data, f, indent=2)
            print(f"Saved METAR cache for {self.scenario.airport_code}")
        except Exception as e:
            print(f"Error saving METAR cache: {e}")

    def update_active_runways(self, active_runways):
        """Update active runways in ASDE config and save to scenario file"""
        try:
            # Update in-memory config
            self.asde_config['active_runways'] = active_runways

            # Update scenario file (preserve airports[] wrapper if present)
            scenario_file_path = self._get_scenario_file_path()
            with open(scenario_file_path, 'r') as f:
                file_data = json.load(f)
            target = self._get_scenario_asde_config_target(file_data)
            if 'asde_config' not in target:
                target['asde_config'] = {}
            target['asde_config']['active_runways'] = active_runways
            with open(scenario_file_path, 'w') as f:
                json.dump(file_data, f, indent=2)
            print(f"Updated active runways for {self.scenario.airport_code}: {active_runways}")
        except Exception as e:
            print(f"Error updating active runways: {e}")

    def update_runway_config(self, departure_runways, arrival_runways):
        """Update runway configuration in ASDE config and save to scenario file"""
        try:
            # Update in-memory config
            self.asde_config['departure_runways'] = departure_runways
            self.asde_config['arrival_runways'] = arrival_runways
            # Update legacy active_runways (union of both)
            self.asde_config['active_runways'] = list(set(departure_runways + arrival_runways))

            # Sync to tower controller
            if self.aircraft_manager and hasattr(self.aircraft_manager, 'tower_controller'):
                self.aircraft_manager.tower_controller.set_departure_runways(departure_runways)
                self.aircraft_manager.tower_controller.set_arrival_runways(arrival_runways)

            # Update scenario file (preserve airports[] wrapper if present)
            scenario_file_path = self._get_scenario_file_path()
            with open(scenario_file_path, 'r') as f:
                file_data = json.load(f)
            target = self._get_scenario_asde_config_target(file_data)
            if 'asde_config' not in target:
                target['asde_config'] = {}
            target['asde_config']['departure_runways'] = departure_runways
            target['asde_config']['arrival_runways'] = arrival_runways
            target['asde_config']['active_runways'] = list(set(departure_runways + arrival_runways))
            with open(scenario_file_path, 'w') as f:
                json.dump(file_data, f, indent=2)
            print(f"Updated runway config for {self.scenario.airport_code}:")
            print(f"  Departures: {departure_runways}")
            print(f"  Arrivals: {arrival_runways}")
        except Exception as e:
            print(f"Error updating runway config: {e}")

    def update_leader_line_length(self, length):
        """Update leader line length in ASDE config and save to scenario file"""
        try:
            # Update in-memory config
            self.asde_config['leader_line'] = int(length)

            # Update scenario file (preserve airports[] wrapper if present)
            scenario_file_path = self._get_scenario_file_path()
            with open(scenario_file_path, 'r') as f:
                file_data = json.load(f)
            target = self._get_scenario_asde_config_target(file_data)
            if 'asde_config' not in target:
                target['asde_config'] = {}
            target['asde_config']['leader_line'] = int(length)
            with open(scenario_file_path, 'w') as f:
                json.dump(file_data, f, indent=2)
            print(f"Updated leader line length for {self.scenario.airport_code}: {int(length)}px")
        except Exception as e:
            print(f"Error updating leader line length: {e}")

    def _sync_actions_to_aircraft_manager(self):
        """Sync ATC action states from top menu bar to aircraft manager"""
        if not self.aircraft_manager or not self.top_menu_bar:
            return

        # Sync all action states
        self.aircraft_manager.ground_stop_active = self.top_menu_bar.ground_stop_active
        self.aircraft_manager.gate_hold_active = self.top_menu_bar.gate_hold_active
        self.aircraft_manager.gdp_active = self.top_menu_bar.gdp_active
        self.aircraft_manager.gdp_delay_minutes = self.top_menu_bar.gdp_delay_minutes
        self.aircraft_manager.emergency_stop_active = self.top_menu_bar.emergency_stop_active
        self.aircraft_manager.closed_runways = self.top_menu_bar.closed_runways.copy()
        self.aircraft_manager.closed_taxiways = self.top_menu_bar.closed_taxiways.copy()

        # Log the action change
        active_actions_list = []
        if self.aircraft_manager.ground_stop_active:
            active_actions_list.append("GROUND STOP")
        if self.aircraft_manager.gate_hold_active:
            active_actions_list.append("GATE HOLD")
        if self.aircraft_manager.gdp_active:
            active_actions_list.append(f"GDP ({self.aircraft_manager.gdp_delay_minutes}min)")
        if self.aircraft_manager.emergency_stop_active:
            active_actions_list.append("EMERGENCY STOP")
        if self.aircraft_manager.closed_runways:
            active_actions_list.append(f"RWY CLOSED: {', '.join(self.aircraft_manager.closed_runways)}")
        if self.aircraft_manager.closed_taxiways:
            active_actions_list.append(f"TWY CLOSED: {', '.join(self.aircraft_manager.closed_taxiways)}")

        if active_actions_list:
            print(f"ATC Actions synced: {', '.join(active_actions_list)}")
        else:
            print("ATC Actions synced: Normal operations")

        # Force immediate Discord update when actions change
        try:
            from discord_rich import get_discord_rpc
            discord_rpc = get_discord_rpc()
            if discord_rpc and discord_rpc.connected:
                airport_code = self.airport_data.get('icao', '') if self.airport_data else ''
                aircraft_count = len(self.aircraft_manager.aircraft) if self.aircraft_manager else 0
                active_actions = {
                    'ground_stop': self.top_menu_bar.ground_stop_active,
                    'gate_hold': self.top_menu_bar.gate_hold_active,
                    'gdp': self.top_menu_bar.gdp_active,
                    'gdp_delay': self.top_menu_bar.gdp_delay_minutes,
                    'emergency_stop': self.top_menu_bar.emergency_stop_active
                }
                discord_rpc.set_in_simulation(airport_code, aircraft_count, active_actions)
        except Exception as e:
            pass  # Silently ignore Discord errors

    def save_simulation(self):
        """Manually save the current simulation state"""
        if not self.initialization_complete:
            print("Cannot save: Simulation still initializing")
            return False
        if self.save_manager.save_simulation_state(self):
            print("✓ Simulation saved manually")
            return True
        return False
