"""
Simulation screen - renders airport and handles ground control
"""
import pygame
import json
import os
import time
import math
import re
from datetime import datetime
import random
from src.atc.commands import ATCCommandProcessor
from src.core.aircraft import AircraftManager
from src.rendering import settings
from src.rendering.top_menu_bar import TopMenuBar
from src.rendering.weather_panel import WeatherPanel
from src.rendering.radio_panel import RadioPanel
from src.audio.tts_service import KokoroTTSService
from src.audio.deepgram_stt import DeepgramSTT
from src.atc.voice_parser import VoiceParser
from discord_rich import get_discord_rpc
from src.core.simulation_save import SimulationSaveManager

# Import and re-export FlightPlanPanel so existing callers still work:
#   from src.rendering.simulation import FlightPlanPanel
from src.rendering.flight_plan_panel import FlightPlanPanel
from src.rendering.flight_strips_window import FlightStripsWindow

from src.rendering.simulation_airport import AirportMixin
from src.rendering.simulation_commands import CommandsMixin
from src.rendering.simulation_geojson import GeoJSONMixin
from src.rendering.simulation_aircraft_render import AircraftRenderMixin
from src.rendering.simulation_voice import VoiceMixin
from src.rendering.simulation_ui import UIMixin


class SimulationScreen(
    AirportMixin,
    CommandsMixin,
    GeoJSONMixin,
    AircraftRenderMixin,
    VoiceMixin,
    UIMixin,
):
    """Main simulation screen for airport ground control"""

    def __init__(self, screen, scenario, dev_mode=False, loading_callback=None, app=None, save_data=None):
        self.screen = screen
        self.scenario = scenario
        self.app = app  # Reference to main app for navigation
        self.save_data = save_data  # Saved simulation data
        self.width, self.height = screen.get_size()

        # Store dev mode flag
        self.dev_mode_enabled = dev_mode

        # Loading screen callback
        self.loading_callback = loading_callback

        # Update loading: Fonts
        if self.loading_callback:
            self.loading_callback.update(0.05, "Loading fonts...")
            self.loading_callback.render()

        # Fonts - Load custom DOS font
        custom_font_path = "data/fonts/asdeView_font.ttf"
        try:
            if os.path.exists(custom_font_path):
                self.title_font = pygame.font.Font(custom_font_path, 32)
                self.info_font = pygame.font.Font(custom_font_path, 18)
                self.tag_font = pygame.font.Font(custom_font_path, 16)  # Data tag font - increased for better visibility
                self.weather_font = pygame.font.Font(custom_font_path, 14)  # Weather panel font (2px larger)
                print(f"Loaded custom font: {custom_font_path}")
            else:
                print(f"Custom font not found: {custom_font_path}, using system font")
                self.title_font = pygame.font.SysFont('consolas,monaco,courier new,monospace', 32, bold=True)
                self.info_font = pygame.font.SysFont('consolas,monaco,courier new,monospace', 18)
                self.tag_font = pygame.font.SysFont('consolas,monaco,courier new,monospace', 16)
                self.weather_font = pygame.font.SysFont('consolas,monaco,courier new,monospace', 14)
        except Exception as e:
            print(f"Error loading custom font: {e}, using default")
            self.title_font = pygame.font.Font(None, 32)
            self.info_font = pygame.font.Font(None, 18)
            self.tag_font = pygame.font.Font(None, 16)
            self.weather_font = pygame.font.Font(None, 14)

        # Colors - realistic airport colors
        self.bg_color = (0, 92, 115)  # Blue-teal background (#005c73)
        self.text_color = (255, 255, 255)
        self.runway_color = (30, 30, 35)  # Black/very dark gray for runways
        self.taxiway_color = (80, 85, 90)  # Medium gray for taxiways
        self.apron_color = (140, 145, 150)  # Light gray for aprons/parking
        self.building_color = (100, 80, 70)  # Brown
        self.grass_color = (40, 70, 50)  # Green
        self.default_color = (100, 100, 110)  # Default gray

        # Load GeoJSON (will be loaded after airport_data is initialized)
        self.geojson_data = None
        self.geojson_loading = False
        self.geojson_loaded = False

        # Cache center coordinates and bounds (calculate once, not every frame)
        self.center_lat = None
        self.center_lon = None
        self.bounds = None

        # Camera/viewport settings
        self.camera_x = 0
        self.camera_y = 0
        self.zoom = 1.0

        # Mouse dragging
        self.dragging = False
        self.last_mouse_pos = None

        # HUD tracking variables
        self.rendered_features = 0
        self.total_features = 0
        self.sim_start_time = pygame.time.get_ticks()

        # Performance caching
        self.render_cache = {
            'geojson_surfaces': {},  # Pre-rendered GeoJSON features
            'airport_surfaces': {},  # Pre-rendered airport elements
            'font_cache': {},  # Pre-rendered text
            'ga_apron_surface': None,  # Pre-rendered GA apron
            'scale_cache': {},  # Cached scale calculations
            'last_zoom': None,
            'last_camera': (None, None)
        }

        # Load settings for time display preference
        self.settings = self.load_settings()
        self.time_settings = self.get_time_setting()

        # Help display toggle and scroll
        self.show_help = False
        self.help_scroll_offset = 0

        # Dev mode toggle (can be toggled via hotkey, but starts with command-line flag)
        self.dev_mode = self.dev_mode_enabled

        # Enhanced dev mode features
        self.dev_show_fps = self.dev_mode_enabled
        self.dev_show_aircraft_paths = self.dev_mode_enabled
        self.dev_show_graph_nodes = False
        self.dev_show_collision_zones = False
        self.dev_show_performance_stats = self.dev_mode_enabled
        self.dev_frame_times = []  # For FPS graph
        self.dev_max_frame_samples = 60

        # Exit confirmation dialog
        self.show_exit_confirmation = False

        # Aircraft editor (right-click aircraft: show on left, green font, no bg)
        self.show_aircraft_editor = False
        self.editor_aircraft = None
        self.editor_selected_index = 0  # 0=AC, 1=BCN, 2=CAT, 3=TYP, 4=FIX, 5=SP1, 6=SP2
        self.editor_field_values = {}  # synced from aircraft when opening
        self.editor_edited_fields = set()  # fields with unconfirmed edits; apply on Enter
        self.editor_scratch_alternate_time = 0  # when to flip SP1/SP2 display
        self.editor_show_scratch_one = True   # when both pads set, alternate every 3 sec

        # Top menu bar (create early so weather panel can link to it)
        self.top_menu_bar = TopMenuBar(self.width, height=35)

        self.top_menu_bar.on_helpfiles_changed = self.load_geojson  # Reload geojson when toggle changes
        self.top_menu_bar.simulation_screen = self  # Link back for saving ASDE config
        self.top_menu_bar.on_actions_changed = self._sync_actions_to_aircraft_manager  # Sync ATC actions

        # Weather panel (will be initialized in load_airport_data)
        self.weather_panel = None

        # Radio panel (will be initialized in load_airport_data)
        self.radio_panel = None

        # Flight plan panel
        self.flight_plan_panel = None
        self.selected_aircraft_for_plan = None

        # Flight strips window (separate OS window, toggle with F2)
        self.flight_strips_window = FlightStripsWindow()

        # Pilot transmission TTS service (sherpa-onnx local inference)
        self.tts_service = KokoroTTSService(
            enabled=self.settings.get("enable_tts", True),
            model_dir=self.settings.get("tts_model_dir", ""),
            model_type=self.settings.get("tts_model_type", "kokoro"),
            num_threads=self.settings.get("tts_num_threads", 2),
            speed=self.settings.get("tts_speed", 1.5),
            enable_radio_static=self.settings.get("enable_radio_static", True),
            max_queue=10,
        )

        # Set pause checker for TTS service
        if self.tts_service:
            def check_pause():
                if self.ptt_active:
                    return True
                return self.top_menu_bar.is_paused if self.top_menu_bar else False
            self.tts_service.set_pause_checker(check_pause)

        # ── Voice command system (Deepgram STT) ──────────────────────────────
        deepgram_key = self.settings.get("deepgram_api_key", "")
        voice_commands_enabled = self.settings.get("voice_commands_enabled", False)
        mic_device_idx = self.settings.get("mic_device_index", -1)
        print(f"[VOICE] voice_commands_enabled={voice_commands_enabled}, key present={bool(deepgram_key)}")
        self.voice_enabled = voice_commands_enabled and bool(deepgram_key)
        self.stt = DeepgramSTT(deepgram_key, mic_device=mic_device_idx) if self.voice_enabled else None
        if self.stt:
            print(f"[VOICE] DeepgramSTT created — available={self.stt.available}, mic={mic_device_idx}")
        else:
            print("[VOICE] STT not created (disabled or no key)")
        self.voice_parser = VoiceParser(aircraft_manager=None)  # manager set later
        self.ptt_active = False          # True while SHIFT is held
        self.voice_status = ""           # Message shown in HUD
        self.voice_status_timer = 0.0
        self._ptt_transcribe_thread = None
        self.radio_static_timer = 0.0   # seconds of screen static remaining

        # ASDE-X Configuration
        self.asde_config = {
            'leader_line': 45,  # Default leader line length
            'active_runways': [],  # Currently active runways (legacy)
            'departure_runways': [],  # Active departure runways
            'arrival_runways': [],  # Active arrival runways
            'metar_cache': ''  # Cached METAR data
        }

        # Update loading: Airport data
        if self.loading_callback:
            self.loading_callback.update(0.15, "Loading airport data...")
            self.loading_callback.render()

        # Load airport data for dev mode
        self.airport_data = None
        self.load_airport_data()

        # Update loading: GeoJSON
        if self.loading_callback:
            self.loading_callback.update(0.35, "Loading airport geometry...")
            self.loading_callback.render()

        # Load GeoJSON now that airport_data is available
        self.load_geojson()

        # Update loading: Viewport calculations
        if self.loading_callback:
            self.loading_callback.update(0.50, "Calculating viewport...")
            self.loading_callback.render()

        self.calculate_viewport_data()

        # Update loading: Aircraft system
        if self.loading_callback:
            self.loading_callback.update(0.65, "Initializing aircraft system...")
            self.loading_callback.render()

        # Aircraft management (initialize before command processor)
        self.aircraft_manager = None
        if self.airport_data:
            # Pass weather_panel to AircraftManager so tower controller can sync runways on startup
            self.aircraft_manager = AircraftManager(
                self.airport_data,
                radio_callback=self.handle_radio_transmission,
                weather_panel=self.weather_panel
            )
            # Give voice parser a reference to live aircraft
            self.voice_parser.aircraft_manager = self.aircraft_manager

            # Update loading: Spawning or restoring aircraft
            if self.loading_callback:
                self.loading_callback.update(0.80, "Spawning aircraft...")
                self.loading_callback.render()

            aircraft_data = self.save_data.get('aircraft_data', {}) if self.save_data else {}
            saved_aircraft = aircraft_data.get('aircraft', [])
            if saved_aircraft:
                self.aircraft_manager.restore_aircraft_from_save(saved_aircraft, radio_callback=self.handle_radio_transmission)
                for k, v in aircraft_data.get('spawn_rates', {}).items():
                    if k == 'dep_spawn_rate' and hasattr(self.aircraft_manager, 'dep_spawn_rate'):
                        self.aircraft_manager.dep_spawn_rate = int(v)
                    if k == 'arr_spawn_rate' and hasattr(self.aircraft_manager, 'arr_spawn_rate'):
                        self.aircraft_manager.arr_spawn_rate = int(v)
                if self.aircraft_manager.dep_spawn_rate:
                    self.aircraft_manager.dep_spawn_interval = 3600.0 / self.aircraft_manager.dep_spawn_rate
                if self.aircraft_manager.arr_spawn_rate:
                    self.aircraft_manager.arr_spawn_interval = 3600.0 / self.aircraft_manager.arr_spawn_rate
            else:
                self.aircraft_manager.spawn_initial_aircraft(0)

            # Link aircraft manager and radio callback to weather panel for runway change notifications
            if self.weather_panel:
                self.weather_panel.aircraft_manager = self.aircraft_manager
                self.weather_panel.radio_callback = self.handle_radio_transmission

            # Link aircraft manager and tower controller to radio panel
            if self.radio_panel:
                self.radio_panel.aircraft_manager = self.aircraft_manager
                if hasattr(self.aircraft_manager, 'tower_controller'):
                    self.radio_panel.tower_controller = self.aircraft_manager.tower_controller

        # Update loading: ATC system
        if self.loading_callback:
            self.loading_callback.update(0.90, "Initializing ATC system...")
            self.loading_callback.render()

        # ATC Command system (needs aircraft manager and airport data)
        self.command_processor = ATCCommandProcessor(self.aircraft_manager, self.airport_data)
        self.command_bar_active = False
        self.command_input = ""
        self.command_history = []
        self.command_history_index = -1
        self.command_output = []  # List of (text, color) tuples
        self.max_output_lines = 3
        self.last_callsign = ""  # Store last called callsign for PTT auto-fill
        self.prefilled_callsign = ""  # Store pre-filled callsign for TGT GEN
        self.cursor_position = 0  # Track cursor position for editing

        # Target generation and auto-complete
        self.available_callsigns = []  # Cache of available aircraft callsigns
        self.auto_complete_index = -1  # Index for tab completion
        self.auto_complete_matches = []  # Current matches for auto-complete
        self.last_command_input = ""  # Store input before auto-complete

        # Selected aircraft and tag positioning
        self.selected_aircraft = None
        self.pending_tag_direction = None  # Store numpad direction before aircraft click

        # Hover info for dev mode
        self.hovered_aircraft = None
        self.mouse_pos = (0, 0)

        # Aircraft thinking panel (toggle with I key)
        self.show_thinking_panel = False

        # Multi-coordinate copy mode
        self.multi_copy_mode = False
        self.copied_coordinates = []

        # Save manager for auto-save functionality
        self.save_manager = SimulationSaveManager()
        self.last_auto_save_time = time.time()  # Initialize to current time
        self.auto_save_interval = 300  # Auto-save every 5 minutes (300 seconds)
        self.initialization_complete = False  # Flag to prevent saving during init

        # Update loading: Assets
        if self.loading_callback:
            self.loading_callback.update(0.92, "Loading assets...")
            self.loading_callback.render()

        # Load radio sound
        self.radio_sound = None
        self.load_radio_sound()

        # Load aircraft image
        self.aircraft_image = None
        self.aircraft_unknown_image = None
        self.load_aircraft_image()

        # Update loading: Pre-caching
        if self.loading_callback:
            self.loading_callback.update(0.95, "Pre-caching rendering data...")
            self.loading_callback.render()

        # Pre-cache expensive operations
        self.pre_cache_rendering_data()

        # Final loading step
        if self.loading_callback:
            self.loading_callback.update(1.0, "Ready!")
            self.loading_callback.render()
            pygame.time.wait(200)  # Brief pause to show completion

        print("SimulationScreen initialization complete")

        # Set crosshair cursor for simulation
        pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_CROSSHAIR)

        # Restore saved simulation state if loading from save
        if self.save_data:
            self.restore_simulation_state()

        # Mark initialization as complete - now safe to save
        self.initialization_complete = True

    def update(self, dt):
        """Update simulation state"""
        # Invalidate cache if camera/zoom changed significantly
        self.invalidate_cache()

        # Tick voice status timer (use wall-clock dt, unaffected by time accel)
        if self.voice_status_timer > 0:
            self.voice_status_timer = max(0.0, self.voice_status_timer - dt)
        if self.radio_static_timer > 0:
            self.radio_static_timer = max(0.0, self.radio_static_timer - dt)

        # Track frame time for dev mode performance stats
        if self.dev_mode and self.dev_show_performance_stats:
            self.dev_frame_times.append(dt * 1000)  # Convert to ms
            if len(self.dev_frame_times) > self.dev_max_frame_samples:
                self.dev_frame_times.pop(0)

        # Update hover detection for dev mode
        if self.dev_mode and self.top_menu_bar and self.top_menu_bar.is_paused:
            self._update_hover_detection()
        else:
            self.hovered_aircraft = None

        # Check if simulation is paused
        if self.top_menu_bar and self.top_menu_bar.is_paused:
            # Don't update aircraft or simulation time when paused
            # Still update weather data periodically
            if self.weather_panel:
                self.weather_panel.update_weather()
            return

        # Apply time acceleration from top menu bar
        if self.top_menu_bar and hasattr(self.top_menu_bar, 'time_acceleration'):
            dt = dt * self.top_menu_bar.time_acceleration

        # Update aircraft
        if self.aircraft_manager:
            self.aircraft_manager.update(dt)

            # Update available callsigns periodically (every 5 seconds) for target generation
            import time as time_module
            if not hasattr(self, '_last_callsigns_update_time'):
                self._last_callsigns_update_time = time_module.time()
            if time_module.time() - self._last_callsigns_update_time > 5.0:
                self.update_available_callsigns()
                self._last_callsigns_update_time = time_module.time()

            # Update Discord Rich Presence with aircraft count (throttled to prevent freezes)
            # Only update every 2 seconds to prevent blocking calls from freezing the sim
            import time as time_module
            if not hasattr(self, '_last_discord_update_time'):
                self._last_discord_update_time = time_module.time()
                self._last_discord_aircraft_count = 0
                self._last_discord_airport_code = ""

            current_time = time_module.time()
            aircraft_count = len(self.aircraft_manager.aircraft)
            airport_code = self.airport_data.get('icao', '') if self.airport_data else ''

            # Build active actions dict from top menu bar
            active_actions = None
            if self.top_menu_bar:
                active_actions = {
                    'ground_stop': self.top_menu_bar.ground_stop_active,
                    'gate_hold': self.top_menu_bar.gate_hold_active,
                    'gdp': self.top_menu_bar.gdp_active,
                    'gdp_delay': self.top_menu_bar.gdp_delay_minutes,
                    'emergency_stop': self.top_menu_bar.emergency_stop_active
                }

            # Check if actions changed
            actions_changed = (hasattr(self, '_last_discord_actions') and
                              active_actions != self._last_discord_actions)

            # Only update if enough time has passed AND something changed
            time_since_update = current_time - self._last_discord_update_time
            if time_since_update >= 2.0 or aircraft_count != self._last_discord_aircraft_count or airport_code != self._last_discord_airport_code or actions_changed:
                try:
                    discord_rpc = get_discord_rpc()
                    if discord_rpc and discord_rpc.connected:
                        # Use a timeout or non-blocking approach
                        # If Discord RPC is buggy, this will prevent freezing
                        discord_rpc.set_in_simulation(airport_code, aircraft_count, active_actions)
                        self._last_discord_update_time = current_time
                        self._last_discord_aircraft_count = aircraft_count
                        self._last_discord_airport_code = airport_code
                        self._last_discord_actions = active_actions.copy() if active_actions else None
                except Exception as e:
                    # Silently catch all Discord errors - don't let them affect simulation
                    # Discord is optional and should never crash the sim
                    # If Discord fails, disable it to prevent further freezes
                    try:
                        discord_rpc = get_discord_rpc()
                        if discord_rpc:
                            discord_rpc.connected = False
                            discord_rpc.RPC = None
                    except:
                        pass
                    pass

        # Auto-save functionality (only after initialization is complete)
        import time as time_module
        current_time = time_module.time()
        if self.initialization_complete and (current_time - self.last_auto_save_time >= self.auto_save_interval):
            if self.save_manager.save_simulation_state(self):
                self.last_auto_save_time = current_time
                print("✓ Auto-saved simulation")

        # Update weather data periodically
        if self.weather_panel:
            self.weather_panel.update_weather()

        # Try to process TTS queue when not paused (in case it was waiting)
        if self.tts_service:
            self.tts_service._process_queue()

        # Update flight strips window
        if self.flight_strips_window.is_open:
            airport_code = self.airport_data.get("icao", "") if self.airport_data else ""
            self.flight_strips_window.update(self.aircraft_manager, airport_code)

    def render(self):
        """Render the simulation"""
        # Clear screen
        self.screen.fill(self.bg_color)

        # Draw airport if GeoJSON loaded
        if self.geojson_data:
            self.render_geojson()
        else:
            self.render_no_data()

        # Draw dev mode overlays (gates, taxiways, runways)
        if self.dev_mode and self.airport_data:
            self.render_dev_mode()
            # Draw GA apron boundary in dev mode
            self.render_ga_apron()

        # Draw aircraft
        if self.aircraft_manager:
            self.render_aircraft()


        # Draw HUD
        self.render_hud()

        # Draw top menu bar
        self.render_top_menu_bar()

        # Draw flight plan panel if open
        if self.flight_plan_panel and self.flight_plan_panel.is_open:
            airport_code = self.scenario.airport_code if hasattr(self.scenario, 'airport_code') else None
            self.flight_plan_panel.render(self.screen, self.info_font, self.tag_font, airport_code)

        # Draw weather panel if open
        if self.weather_panel and self.weather_panel.is_open:
            self.weather_panel.render(self.screen, self.info_font, self.weather_font)

        # Draw radio panel if open
        if self.radio_panel and self.radio_panel.is_open:
            self.radio_panel.render(self.screen, self.info_font, self.weather_font)

        # Draw command bar and output
        self.render_command_system()

        # Draw aircraft editor (left side, green font, no bg) when open
        self.render_aircraft_editor()

        # Draw tag positioning indicator
        if self.pending_tag_direction is not None:
            direction_names = {
                8: "NORTH", 6: "EAST", 2: "SOUTH", 4: "WEST",
                9: "NORTHEAST", 3: "SOUTHEAST", 1: "SOUTHWEST", 7: "NORTHWEST"
            }
            direction_text = direction_names.get(self.pending_tag_direction, "UNKNOWN")
            indicator_text = self.info_font.render(f"Tag Direction: {direction_text} - Click aircraft to apply", True, (255, 255, 0))
            self.screen.blit(indicator_text, (self.width // 2 - 200, 50))

        # Draw PAUSED indicator
        if self.top_menu_bar and self.top_menu_bar.is_paused:
            pause_text = self.info_font.render("PAUSED", True, (255, 100, 100))
            text_rect = pause_text.get_rect(center=(self.width // 2, 50))
            # Draw semi-transparent background
            bg_rect = text_rect.inflate(20, 10)
            pause_bg = pygame.Surface((bg_rect.width, bg_rect.height))
            pause_bg.set_alpha(200)
            pause_bg.fill((40, 20, 20))
            self.screen.blit(pause_bg, bg_rect)
            self.screen.blit(pause_text, text_rect)

        # Draw aircraft info panel when hovering in dev mode + paused
        if self.dev_mode and self.top_menu_bar and self.top_menu_bar.is_paused and self.hovered_aircraft:
            self._render_aircraft_info_panel(self.hovered_aircraft)

        # Draw aircraft thinking panel (toggle with I)
        if self.show_thinking_panel:
            self._render_thinking_panel()

        # Draw voice command HUD (PTT indicator + status)
        if self.voice_enabled:
            self._render_voice_hud()

        # Draw coordinate copy feedback
        if hasattr(self, 'copy_feedback') and self.copy_feedback:
            current_time = pygame.time.get_ticks()
            elapsed = current_time - self.copy_feedback['time']

            if elapsed < self.copy_feedback['duration']:
                # Calculate fade out
                alpha = 255 if elapsed < 1500 else int(255 * (1 - (elapsed - 1500) / 500))

                # Create feedback surface
                feedback_text = self.tag_font.render("Copied!", True, (100, 255, 100))
                coord_text = self.tag_font.render(self.copy_feedback['text'], True, (200, 200, 200))

                # Position near click location
                x, y = self.copy_feedback['pos']
                x += 15
                y -= 40

                # Keep on screen
                if x + 200 > self.width:
                    x = self.width - 200
                if y < 0:
                    y = 10

                # Background
                bg_width = max(feedback_text.get_width(), coord_text.get_width()) + 20
                bg_height = 50
                bg_surface = pygame.Surface((bg_width, bg_height))
                bg_surface.set_alpha(alpha)
                bg_surface.fill((30, 40, 30))
                pygame.draw.rect(bg_surface, (100, 255, 100), (0, 0, bg_width, bg_height), 2)

                self.screen.blit(bg_surface, (x, y))

                # Text with alpha
                feedback_text.set_alpha(alpha)
                coord_text.set_alpha(alpha)
                self.screen.blit(feedback_text, (x + 10, y + 5))
                self.screen.blit(coord_text, (x + 10, y + 25))
            else:
                # Clear feedback after duration
                self.copy_feedback = None

        # Draw multi-copy markers
        if hasattr(self, 'multi_copy_markers') and self.multi_copy_markers:
            current_time = pygame.time.get_ticks()
            # Remove old markers (older than 10 seconds or when mode ends)
            if not self.multi_copy_mode:
                self.multi_copy_markers = []
            else:
                self.multi_copy_markers = [m for m in self.multi_copy_markers if current_time - m['time'] < 10000]

                # Draw each marker
                for marker in self.multi_copy_markers:
                    x, y = marker['pos']
                    number = marker['number']

                    # Draw circle
                    pygame.draw.circle(self.screen, (255, 200, 0), (int(x), int(y)), 8, 2)

                    # Draw number
                    number_text = self.tag_font.render(str(number), True, (255, 255, 0))
                    text_rect = number_text.get_rect(center=(int(x), int(y)))
                    self.screen.blit(number_text, text_rect)

        # Draw multi-copy mode indicator
        if self.multi_copy_mode:
            indicator_text = self.info_font.render(
                f"Multi-Copy Mode: {len(self.copied_coordinates)} points | Release Space to copy all",
                True, (255, 200, 0)
            )
            indicator_rect = indicator_text.get_rect(center=(self.width // 2, 80))

            # Background
            bg_rect = indicator_rect.inflate(20, 10)
            bg_surface = pygame.Surface((bg_rect.width, bg_rect.height))
            bg_surface.set_alpha(220)
            bg_surface.fill((60, 50, 20))
            pygame.draw.rect(bg_surface, (255, 200, 0), (0, 0, bg_rect.width, bg_rect.height), 2)

            self.screen.blit(bg_surface, bg_rect)
            self.screen.blit(indicator_text, indicator_rect)

        # Enhanced dev mode overlays
        if self.dev_mode:
            self._render_enhanced_dev_overlays()

        # Menu bar tooltip last so it appears above all other UI (except exit dialog)
        if self.top_menu_bar and self.top_menu_bar.hovered_icon:
            self.top_menu_bar._render_tooltip(self.screen, self.info_font)

        # Exit confirmation dialog (render last so it's on top)
        if self.show_exit_confirmation:
            self._render_exit_confirmation()
