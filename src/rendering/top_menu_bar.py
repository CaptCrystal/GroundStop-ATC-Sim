"""
Top Menu Bar
Handles rendering and interaction for the top menu bar with icons
"""
import pygame
import os
import json
import webbrowser

# -----------------------------------------------------------------------------
# Custom UI: one theme + one layout for menu bar and all dropdown panels
# -----------------------------------------------------------------------------

# Layout (all margins/padding in one place)
PAD = 16
PAD_SM = 10
PAD_XS = 6
TITLE_H = 28
ROW_H = 24
SECTION_GAP = 14
SEP_H = 1
RADIUS = 6
RADIUS_SM = 4
ICON_SIZE = 28
SLIDER_H = 6
TOGGLE_W = 44
TOGGLE_H = 22
TOGGLE_R = 11
BTN_H = 38
TOOLTIP_PAD = 8

# Colors: single dark palette (no mixed hues)
THEME = {
    "bg_bar": (24, 26, 30),
    "bg_panel": (28, 30, 35),
    "bg_control": (38, 40, 46),
    "bg_control_hover": (46, 48, 54),
    "border": (55, 58, 65),
    "border_subtle": (45, 48, 54),
    "text": (235, 238, 242),
    "text_secondary": (165, 170, 178),
    "text_muted": (115, 120, 128),
    "separator": (48, 51, 58),
    "icon_bg": (32, 34, 40),
    "icon_bg_hover": (44, 46, 52),
    "icon_bg_active": (50, 52, 58),
    "icon_bg_pause": (58, 38, 38),
    "icon_bg_actions": (52, 46, 36),
    "icon_bg_discord": (48, 52, 72),
    "slider_track": (42, 44, 50),
    "slider_fill": (72, 76, 84),
    "slider_handle": (165, 168, 175),
    "toggle_off": (42, 44, 50),
    "toggle_on": (42, 72, 52),
    "toggle_knob": (220, 222, 228),
    "btn": (38, 40, 46),
    "btn_border": (55, 58, 65),
    "btn_emergency": (72, 42, 42),
    "btn_emergency_border": (100, 58, 58),
    "btn_resume": (38, 58, 46),
    "btn_resume_border": (55, 82, 62),
    "btn_resume_text": (160, 200, 170),
    "btn_active": (58, 52, 40),
    "btn_active_border": (90, 82, 62),
    "badge_bg": (38, 36, 34),
    "badge_emergency": (220, 100, 100),
    "badge_warning": (220, 175, 95),
    "section": (100, 104, 112),
    "tooltip_bg": (36, 38, 42),
    "tooltip_border": (60, 63, 70),
    "tooltip_text": (245, 247, 250),


    "tooltip_shadow": (12, 12, 14),
    # Radii (int pixels)
    "radius_small": 4,
    "panel_radius": 6,
    # Panel styling (controller/actions)
    "panel_bg": (28, 30, 35),
    "panel_border": (55, 58, 65),
    "text_title": (240, 243, 248),
    "text_label": (165, 170, 178),
    "text_dim": (115, 120, 128),
    "section_header": (100, 104, 112),
    # Action button variants
    "btn_bg": (38, 40, 46),
    "btn_emergency_bg": (72, 42, 42),
    "btn_emergency_inactive_bg": (48, 38, 38),
    "btn_emergency_border": (100, 58, 58),
    "btn_emergency_inactive_border": (65, 50, 50),
    "btn_resume_bg": (38, 58, 46),
    "btn_resume_border": (55, 82, 62),
    "btn_active_bg": (58, 52, 40),
    "btn_active_border": (90, 82, 62),
}


class TopMenuBar:
    """Top menu bar with settings and other icons"""
    
    @property
    def radio_panel(self):
        return self._radio_panel

    @radio_panel.setter
    def radio_panel(self, value):
        print(f"Setting TopMenuBar.radio_panel to {value} (was {self._radio_panel})")
        self._radio_panel = value
        if hasattr(self, '_radio_panel'):
            print(f"Radio panel set to: {self._radio_panel is not None}")

    @property
    def weather_panel(self):
        return self._weather_panel

    @weather_panel.setter
    def weather_panel(self, value):
        print(f"Setting TopMenuBar.weather_panel to {value} (was {self._weather_panel})")
        self._weather_panel = value
        if hasattr(self, '_weather_panel'):
            print(f"Weather panel set to: {self._weather_panel is not None}")
            print(f"Weather panel type: {type(self._weather_panel) if self._weather_panel is not None else 'None'}")

    def __init__(self, width, height=35):
        self.width = width
        self.height = height
        self.show_settings_panel = False
        self.settings_icon = None
        self.weather_icon = None
        self.pause_icon = None
        self.play_icon = None
        self.controller_icon = None
        self.discord_icon = None
        self.radio_icon = None
        
        # Pause state
        self.is_paused = False
        
        # Radio panel reference (set externally)
        self._radio_panel = None
        
        # Simulation screen reference (set externally)
        self.simulation_screen = None
        
        # Hover tracking
        self.hovered_icon = None  # Track which icon is being hovered
        
        # Weather panel reference (set externally)
        self._weather_panel = None
        
        # Leader line length setting
        self.leader_line_length = 60  # Default value
        self.dragging_slider = False
        self.slider_rect = None  # Initialize to None
        
        # Time acceleration setting
        self.time_acceleration = 1.0  # Default 1x speed (range: 1x to 20x)
        self.dragging_time_slider = False
        self.time_slider_rect = None
        
        # Show helpfiles toggle
        self.show_helpfiles = True  # Default value
        self.helpfiles_toggle_rect = None
        self.on_helpfiles_changed = None  # Callback when helpfiles toggle changes
        
        # TTS Audio toggle
        self.enable_tts_audio = True  # Default value - TTS enabled by default
        self.enable_tts_audio_toggle_rect = None
        
        # Past transmissions (command output) toggle
        self.show_past_transmissions = True  # Default on; when off, command output is hidden
        self.show_past_transmissions_toggle_rect = None
        
        #controller menu
        self.show_controller_menu = False
        
        # Actions panel
        self.show_actions_panel = False
        self.actions_icon = None
        self.actions_dropdown_open = None  # Which dropdown is open: 'ground_stop', 'gdp', 'runway', 'taxiway', None
        
        # Active restrictions/actions state
        self.ground_stop_active = False
        self.gdp_active = False
        self.gdp_delay_minutes = 0
        self.gate_hold_active = False
        self.closed_runways = set()  # Set of closed runway names
        self.closed_taxiways = set()  # Set of closed taxiway names
        self.emergency_stop_active = False
        
        # Callback for when actions change (set by simulation)
        self.on_actions_changed = None

        # Voice / STT panel
        self.show_voice_panel = False
        self.voice_commands_enabled = False
        self.ptt_key_code = pygame.K_LSHIFT
        self.mic_device_index = -1
        self.speaker_device_index = -1
        self.ptt_listening = False
        self.mic_icon = None
        self._mic_devices = [(-1, "System Default")]
        self._spk_devices = [(-1, "System Default")]
        # Voice panel click rects (populated during render)
        self.voice_enabled_toggle_rect = None
        self.voice_tts_toggle_rect = None
        self.voice_ptt_btn_rect = None
        self.voice_mic_prev_rect = None
        self.voice_mic_next_rect = None
        self.voice_spk_prev_rect = None
        self.voice_spk_next_rect = None

        # Load settings
        self.load_settings()
        
        # Load icons
        self.load_settings_icon()
        self.load_weather_icon()
        self.load_pause_icon()
        self.load_controller_icon()
        self.load_play_icon()
        self.load_discord_icon()
        self.load_radio_icon()
        self.load_actions_icon()
        self.load_mic_icon()
    
    def load_settings_icon(self):
        """Load settings gear icon"""
        for icon_path in ("data/images/settings_icon.png", "data/images/settings-icon.png"):
            try:
                if os.path.exists(icon_path):
                    original_image = pygame.image.load(icon_path).convert_alpha()
                    self.settings_icon = pygame.transform.scale(original_image, (24, 24))
                    print(f"Loaded settings icon: {icon_path}")
                    return
            except Exception as e:
                print(f"Error loading settings icon: {e}")
        self._create_settings_icon()
        print("Created settings icon programmatically")
            
    def load_weather_icon(self):
        """Load weather icon"""
        icon_path = "data/images/cloude.png"
        
        try:
            if os.path.exists(icon_path):
                original_image = pygame.image.load(icon_path).convert_alpha()
                self.weather_icon = pygame.transform.scale(original_image, (24, 24))
                print(f"Loaded weather icon: {icon_path}")
            else:
                self._create_weather_icon()
                print("Created weather icon programmatically")
        except Exception as e:
            print(f"Error loading weather icon: {e}")
            self._create_weather_icon()
            
    def load_radio_icon(self):
        """Load radio icon"""
        # Try multiple possible paths for the icon
        possible_paths = [
            "data/images/radio-icon.png",
            "data/images/radio_icon.png",
            "data/images/radio.png"
        ]
        
        for icon_path in possible_paths:
            try:
                if os.path.exists(icon_path):
                    original_image = pygame.image.load(icon_path).convert_alpha()
                    self.radio_icon = pygame.transform.scale(original_image, (24, 24))
                    print(f"Loaded radio icon: {icon_path}")
                    return
            except Exception as e:
                print(f"Error loading radio icon from {icon_path}: {e}")
        
        # If we get here, no icon was loaded successfully - create one
        print("No radio icon found, creating default")
        self._create_radio_icon()
    
    def _create_radio_icon(self):
        """Create radio icon surface"""
        surface = pygame.Surface((24, 24), pygame.SRCALPHA)
        # Draw radio/headset icon
        radio_color = (100, 200, 100)
        # Headband
        pygame.draw.arc(surface, radio_color, (6, 4, 12, 12), 3.14, 6.28, 2)
        # Left earpiece
        pygame.draw.rect(surface, radio_color, (4, 12, 4, 8), border_radius=2)
        # Right earpiece
        pygame.draw.rect(surface, radio_color, (16, 12, 4, 8), border_radius=2)
        # Microphone boom
        pygame.draw.line(surface, radio_color, (16, 16), (20, 18), 2)
        self.radio_icon = surface

    def load_mic_icon(self):
        """Load microphone icon (always uses programmatic fallback)."""
        self._create_mic_icon()

    def _create_mic_icon(self):
        """Create microphone icon surface."""
        import math
        surface = pygame.Surface((24, 24), pygame.SRCALPHA)
        c = (100, 200, 255)
        # Mic capsule body
        pygame.draw.rect(surface, c, (9, 2, 6, 12), border_radius=3)
        # Stand arc (lower half ellipse)
        pygame.draw.arc(surface, c, (4, 8, 16, 10), math.pi, 2 * math.pi, 2)
        # Stand pole
        pygame.draw.line(surface, c, (12, 17), (12, 21), 2)
        # Base
        pygame.draw.line(surface, c, (8, 21), (16, 21), 2)
        self.mic_icon = surface

    def _enumerate_audio_devices(self):
        """Query sounddevice for available mic and speaker devices."""
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            self._mic_devices = [(-1, "System Default")] + [
                (i, d["name"][:34]) for i, d in enumerate(devices)
                if d["max_input_channels"] > 0
            ]
            self._spk_devices = [(-1, "System Default")] + [
                (i, d["name"][:34]) for i, d in enumerate(devices)
                if d["max_output_channels"] > 0
            ]
        except Exception:
            self._mic_devices = [(-1, "System Default")]
            self._spk_devices = [(-1, "System Default")]

    def load_actions_icon(self):
        """Load actions icon (tries actions_icon.png and actions-icon.png)"""
        for icon_path in ("data/images/actions_icon.png", "data/images/actions-icon.png"):
            try:
                if os.path.exists(icon_path):
                    original_image = pygame.image.load(icon_path).convert_alpha()
                    self.actions_icon = pygame.transform.scale(original_image, (24, 24))
                    print(f"Loaded actions icon: {icon_path}")
                    return
            except Exception as e:
                print(f"Error loading actions icon from {icon_path}: {e}")
        self._create_actions_icon()
        print("Created actions icon programmatically")
            


    def load_controller_icon(self):
        """Load controller icon (uses radio_icon.png as fallback)"""
        for icon_path in ("data/images/radio_icon.png", "data/images/radio-icon.png"):
            try:
                if os.path.exists(icon_path):
                    original_image = pygame.image.load(icon_path).convert_alpha()
                    self.controller_icon = pygame.transform.scale(original_image, (24, 24))
                    print(f"Loaded controller icon: {icon_path}")
                    return
            except Exception as e:
                print(f"Error loading controller icon: {e}")
        self._create_controller_icon()
        print("Created controller icon programmatically")

    def _create_controller_icon(self):
        """Create a simple controller/headset icon surface"""
        surface = pygame.Surface((24, 24), pygame.SRCALPHA)
        c = (150, 180, 200)
        pygame.draw.arc(surface, c, (6, 4, 12, 12), 3.14, 6.28, 2)
        pygame.draw.rect(surface, c, (4, 12, 4, 8), border_radius=2)
        pygame.draw.rect(surface, c, (16, 12, 4, 8), border_radius=2)
        pygame.draw.line(surface, c, (16, 16), (20, 18), 2)
        self.controller_icon = surface

            
    def load_discord_icon(self):
        icon_path = "data/images/discord_icon.png"
        
        try:
            if os.path.exists(icon_path):
                original_image = pygame.image.load(icon_path).convert_alpha()
                self.discord_icon = pygame.transform.scale(original_image, (24, 24))
                print(f"Loaded discord icon: {icon_path}")
            else:
                self._create_discord_icon()
                print("Created discord icon programmatically")
        except Exception as e:
            print(f"Error loading discord icon: {e}")
            self._create_discord_icon()
            
    def _create_discord_icon(self):
        """Create discord icon surface - simplified Discord logo"""
        surface = pygame.Surface((24, 24), pygame.SRCALPHA)
        # Discord color: blurple
        discord_color = (88, 101, 242)
        
        # Draw simplified Discord "clyde" logo shape
        # Main rounded rectangle body
        pygame.draw.rect(surface, discord_color, (5, 6, 14, 14), border_radius=5)
        
        # Two "eyes" (dots)
        pygame.draw.circle(surface, (255, 255, 255), (9, 12), 2)
        pygame.draw.circle(surface, (255, 255, 255), (15, 12), 2)
        
        # Bottom notch (speech bubble tail)
        pygame.draw.polygon(surface, discord_color, [(10, 20), (14, 20), (12, 22)])
        
        self.discord_icon = surface
            
    def load_settings(self):
        """Load settings from settings.json"""
        try:
            if os.path.exists("settings.json"):
                with open("settings.json", 'r') as f:
                    settings = json.load(f)
                    self.show_helpfiles = settings.get("show_helpfiles", True)
                    self.leader_line_length = settings.get("leader_line_length", 60)
                    self.enable_tts_audio = settings.get("enable_tts", settings.get("enable_tts_audio", True))
                    self.show_past_transmissions = settings.get("show_past_transmissions", True)
                    self.voice_commands_enabled = settings.get("voice_commands_enabled", False)
                    self.ptt_key_code = settings.get("ptt_key_code", pygame.K_LSHIFT)
                    self.mic_device_index = settings.get("mic_device_index", -1)
                    self.speaker_device_index = settings.get("speaker_device_index", -1)
        except Exception as e:
            print(f"Error loading settings: {e}")
    
    def save_settings(self):
        """Save settings to settings.json"""
        try:
            settings = {}
            if os.path.exists("settings.json"):
                with open("settings.json", 'r') as f:
                    settings = json.load(f)
            
            settings["show_helpfiles"] = self.show_helpfiles
            settings["leader_line_length"] = self.leader_line_length
            settings["enable_tts"] = self.enable_tts_audio
            settings["show_past_transmissions"] = self.show_past_transmissions
            settings["voice_commands_enabled"] = self.voice_commands_enabled
            settings["ptt_key_code"] = self.ptt_key_code
            settings["mic_device_index"] = self.mic_device_index
            settings["speaker_device_index"] = self.speaker_device_index
            
            with open("settings.json", 'w') as f:
                json.dump(settings, f, indent=2)
        except Exception as e:
            print(f"Error saving settings: {e}")
    
    def load_pause_icon(self):
        """Load pause icon"""
        for icon_path in ("data/images/pause_icon.png", "data/images/pause-icon.png"):
            try:
                if os.path.exists(icon_path):
                    original_image = pygame.image.load(icon_path).convert_alpha()
                    self.pause_icon = pygame.transform.scale(original_image, (24, 24))
                    print(f"Loaded pause icon: {icon_path}")
                    return
            except Exception as e:
                print(f"Error loading pause icon: {e}")
        self._create_pause_icon()
        print("Created pause icon programmatically")
    
    def load_play_icon(self):
        """Load play icon"""
        for icon_path in ("data/images/play_icon.png", "data/images/play-icon.png"):
            try:
                if os.path.exists(icon_path):
                    original_image = pygame.image.load(icon_path).convert_alpha()
                    self.play_icon = pygame.transform.scale(original_image, (24, 24))
                    print(f"Loaded play icon: {icon_path}")
                    return
            except Exception as e:
                print(f"Error loading play icon: {e}")
        self._create_play_icon()
        print("Created play icon programmatically")
    
    def _create_pause_icon(self):
        """Create pause icon surface"""
        surface = pygame.Surface((24, 24), pygame.SRCALPHA)
        # Draw two vertical bars
        pygame.draw.rect(surface, (200, 200, 200), (6, 4, 4, 16))
        pygame.draw.rect(surface, (200, 200, 200), (14, 4, 4, 16))
        self.pause_icon = surface
    
    def _create_play_icon(self):
        """Create play icon surface"""
        surface = pygame.Surface((24, 24), pygame.SRCALPHA)
        # Draw triangle pointing right
        points = [(7, 4), (7, 20), (19, 12)]
        pygame.draw.polygon(surface, (100, 255, 100), points)
        self.play_icon = surface
    
    def _create_settings_icon(self):
        """Create settings gear icon surface"""
        surface = pygame.Surface((24, 24), pygame.SRCALPHA)
        # Draw gear with center circle and outer ring
        center = (12, 12)
        pygame.draw.circle(surface, (200, 200, 200), center, 9, 2)  # Outer
        pygame.draw.circle(surface, (200, 200, 200), center, 4, 2)  # Inner
        # Draw gear teeth (8 small rectangles around edge)
        for angle in range(0, 360, 45):
            import math
            rad = math.radians(angle)
            x = center[0] + int(10 * math.cos(rad))
            y = center[1] + int(10 * math.sin(rad))
            pygame.draw.circle(surface, (200, 200, 200), (x, y), 2)
        self.settings_icon = surface
    
    def _create_weather_icon(self):
        """Create weather cloud icon surface"""
        surface = pygame.Surface((24, 24), pygame.SRCALPHA)
        # Draw sun in top right
        pygame.draw.circle(surface, (255, 200, 100), (17, 7), 4)
        # Draw cloud (multiple overlapping circles)
        pygame.draw.circle(surface, (200, 200, 200), (9, 14), 5, 2)
        pygame.draw.circle(surface, (200, 200, 200), (15, 14), 4, 2)
        pygame.draw.circle(surface, (200, 200, 200), (12, 11), 4, 2)
        self.weather_icon = surface
    
    def handle_mouse_down(self, pos):
        """Handle mouse button down events
        
        Args:
            pos: (x, y) tuple of mouse position
            
        Returns:
            True if event was handled, False otherwise
        """
        # Check if clicking on helpfiles toggle (only if settings panel is open)
        if self.show_settings_panel and self.helpfiles_toggle_rect is not None and self.helpfiles_toggle_rect.collidepoint(pos):
            self.show_helpfiles = not self.show_helpfiles
            self.save_settings()
            print(f"Show helpfiles toggled: {self.show_helpfiles}")
            # Trigger callback to reload geojson
            if self.on_helpfiles_changed:
                self.on_helpfiles_changed()
            return True
        
        # Check if clicking on leader line slider (only if settings panel is open and slider exists)
        if self.show_settings_panel and self.slider_rect is not None and self.slider_rect.collidepoint(pos):
            self.dragging_slider = True
            self._update_slider_value(pos)
            return True
        
        # Check if clicking on time acceleration slider (only if settings panel is open and slider exists)
        if self.show_settings_panel and self.time_slider_rect is not None and self.time_slider_rect.collidepoint(pos):
            self.dragging_time_slider = True
            self.update_slider_from_drag(pos)
            return True
        
        # Check if clicking on TTS audio toggle (only if settings panel is open)
        if self.show_settings_panel and self.enable_tts_audio_toggle_rect is not None and self.enable_tts_audio_toggle_rect.collidepoint(pos):
            self.enable_tts_audio = not self.enable_tts_audio
            self.save_settings()
            print(f"TTS Audio toggled: {'ENABLED' if self.enable_tts_audio else 'DISABLED'}")
            return True
        
        if self.show_settings_panel and self.show_past_transmissions_toggle_rect is not None and self.show_past_transmissions_toggle_rect.collidepoint(pos):
            self.show_past_transmissions = not self.show_past_transmissions
            self.save_settings()
            print(f"Past transmissions toggled: {'ON' if self.show_past_transmissions else 'OFF'}")
            return True
        
        # Check if clicking on Save Simulation button (only if settings panel is open)
        if self.show_settings_panel and hasattr(self, 'save_sim_button_rect') and self.save_sim_button_rect.collidepoint(pos):
            if self.simulation_screen:
                success = self.simulation_screen.save_simulation()
                if success:
                    print("✓ Simulation saved successfully from settings panel")
                else:
                    print("✗ Failed to save simulation")
            else:
                print("No simulation available to save")
            return True
        
        # Voice / STT interactions (now inside settings panel)
        if self.show_settings_panel:
            if self.voice_enabled_toggle_rect and self.voice_enabled_toggle_rect.collidepoint(pos):
                self.voice_commands_enabled = not self.voice_commands_enabled
                self.save_settings()
                print(f"[Voice] Voice commands: {'ON' if self.voice_commands_enabled else 'OFF'}")
                return True
            if self.voice_tts_toggle_rect and self.voice_tts_toggle_rect.collidepoint(pos):
                self.enable_tts_audio = not self.enable_tts_audio
                self.save_settings()
                print(f"[Voice] TTS audio: {'ON' if self.enable_tts_audio else 'OFF'}")
                return True
            if self.voice_ptt_btn_rect and self.voice_ptt_btn_rect.collidepoint(pos):
                self.ptt_listening = not self.ptt_listening
                print(f"[Voice] PTT listening: {self.ptt_listening}")
                return True
            # Mic device prev/next
            if self.voice_mic_prev_rect and self.voice_mic_prev_rect.collidepoint(pos):
                if self._mic_devices:
                    cur = next((i for i, (idx, _) in enumerate(self._mic_devices)
                                if idx == self.mic_device_index), 0)
                    cur = (cur - 1) % len(self._mic_devices)
                    self.mic_device_index = self._mic_devices[cur][0]
                    self.save_settings()
                return True
            if self.voice_mic_next_rect and self.voice_mic_next_rect.collidepoint(pos):
                if self._mic_devices:
                    cur = next((i for i, (idx, _) in enumerate(self._mic_devices)
                                if idx == self.mic_device_index), 0)
                    cur = (cur + 1) % len(self._mic_devices)
                    self.mic_device_index = self._mic_devices[cur][0]
                    self.save_settings()
                return True
            # Speaker device prev/next
            if self.voice_spk_prev_rect and self.voice_spk_prev_rect.collidepoint(pos):
                if self._spk_devices:
                    cur = next((i for i, (idx, _) in enumerate(self._spk_devices)
                                if idx == self.speaker_device_index), 0)
                    cur = (cur - 1) % len(self._spk_devices)
                    self.speaker_device_index = self._spk_devices[cur][0]
                    self.save_settings()
                return True
            if self.voice_spk_next_rect and self.voice_spk_next_rect.collidepoint(pos):
                if self._spk_devices:
                    cur = next((i for i, (idx, _) in enumerate(self._spk_devices)
                                if idx == self.speaker_device_index), 0)
                    cur = (cur + 1) % len(self._spk_devices)
                    self.speaker_device_index = self._spk_devices[cur][0]
                    self.save_settings()
                return True

        # Handle actions panel clicks
        if self.show_actions_panel and hasattr(self, 'actions_button_rects'):
            for action_id, rect in self.actions_button_rects:
                if rect.collidepoint(pos):
                    self._handle_action_click(action_id)
                    return True
        
        return self.handle_click(pos)
    
    def handle_mouse_up(self, pos):
        """Handle mouse button up events"""
        self.dragging_slider = False
        self.dragging_time_slider = False
    
    def handle_mouse_motion(self, pos):
        """Handle mouse motion events"""
        if self.dragging_slider or self.dragging_time_slider:
            self.update_slider_from_drag(pos)
            return True
        
        # Update hover state for icons
        x, y = pos
        if y <= self.height:
            # Check which icon is being hovered
            iy = (self.height - ICON_SIZE) // 2
            if pygame.Rect(PAD, iy, ICON_SIZE, ICON_SIZE).collidepoint(pos):
                self.hovered_icon = 'discord'
            elif pygame.Rect(self.width - 40, iy, ICON_SIZE, ICON_SIZE).collidepoint(pos):
                self.hovered_icon = 'pause'
            elif pygame.Rect(self.width - 78, iy, ICON_SIZE, ICON_SIZE).collidepoint(pos):
                self.hovered_icon = 'settings'
            elif pygame.Rect(self.width - 143, iy, ICON_SIZE, ICON_SIZE).collidepoint(pos):
                self.hovered_icon = 'weather'
            elif pygame.Rect(self.width - 178, iy, ICON_SIZE, ICON_SIZE).collidepoint(pos):
                self.hovered_icon = 'radio'
            elif pygame.Rect(self.width - 213, iy, ICON_SIZE, ICON_SIZE).collidepoint(pos):
                self.hovered_icon = 'actions'
            else:
                self.hovered_icon = None
        else:
            self.hovered_icon = None
        
        return False
    
    def _update_slider_value(self, pos):
        """Update slider value based on mouse position"""
        if not hasattr(self, 'slider_x_start'):
            return
        
        x, y = pos
        # Calculate position along slider
        slider_pos = max(0, min(self.slider_width, x - self.slider_x_start))
        percent = slider_pos / self.slider_width
        
        # Map to 30-120 range
        self.leader_line_length = 30 + (percent * 90)
    
    def update_slider_from_drag(self, pos):
        """Update slider value based on drag position"""
        if self.dragging_slider:
            x, y = pos
            # Calculate position along slider
            slider_pos = max(0, min(self.slider_width, x - self.slider_x_start))
            percent = slider_pos / self.slider_width
            
            # Map to 30-120 range
            old_length = self.leader_line_length
            self.leader_line_length = 30 + (percent * 90)
            
            # Save to ASDE config if value changed significantly (avoid saving on every pixel)
            if abs(self.leader_line_length - old_length) > 1 and self.simulation_screen:
                self.simulation_screen.update_leader_line_length(self.leader_line_length)
        
        if self.dragging_time_slider:
            x, y = pos
            # Calculate position along time slider
            slider_pos = max(0, min(self.time_slider_width, x - self.time_slider_x_start))
            percent = slider_pos / self.time_slider_width
            
            # Map to 1x-20x range
            self.time_acceleration = 1.0 + (percent * 19.0)
    
    def handle_click(self, pos):
        """Handle mouse clicks on the menu bar
        
        Args:
            pos: (x, y) tuple of mouse position
            
        Returns:
            True if click was handled, False otherwise
        """
        x, y = pos
        
        # Check if click is within menu bar
        if y > 40:
            return False
        
        iy = (self.height - ICON_SIZE) // 2
        pause_icon_rect = pygame.Rect(self.width - 40, iy, ICON_SIZE, ICON_SIZE)
        if pause_icon_rect.collidepoint(pos):
            self.is_paused = not self.is_paused
            print(f"Simulation {'PAUSED' if self.is_paused else 'RESUMED'}")
            return True
        
        settings_icon_rect = pygame.Rect(self.width - 78, iy, ICON_SIZE, ICON_SIZE)
        if settings_icon_rect.collidepoint(pos):
            self.show_settings_panel = not self.show_settings_panel
            if self.show_settings_panel:
                self._enumerate_audio_devices()
            # Close other panels if open
            self.show_actions_panel = False
            if self.weather_panel:
                self.weather_panel.is_open = False
            if hasattr(self, 'radio_panel') and self.radio_panel:
                self.radio_panel.is_open = False
            # Clear slider rect when closing settings panel
            if not self.show_settings_panel:
                self.slider_rect = None
            return True
        
        # Check if weather icon was clicked (left of divider)
        weather_icon_rect = pygame.Rect(self.width - 140, 5, 25, 25)
        if weather_icon_rect.collidepoint(pos):
            try:
                if hasattr(self, 'weather_panel') and self.weather_panel is not None:
                    # Toggle weather panel
                    self.weather_panel.is_open = not self.weather_panel.is_open
                    print(f"Weather panel toggled: {self.weather_panel.is_open}")
                    # Close other panels if open
                    self.show_settings_panel = False
                    self.show_actions_panel = False
                    if hasattr(self, 'radio_panel') and self.radio_panel:
                        self.radio_panel.is_open = False
                    self.slider_rect = None  # Clear slider rect when closing settings
                else:
                    print("Weather panel not properly initialized. Check airport data loading.")
                    print(f"weather_panel attribute exists: {hasattr(self, 'weather_panel')}")
                    print(f"weather_panel value: {getattr(self, 'weather_panel', 'N/A')}")
                return True
            except Exception as e:
                print(f"Error toggling weather panel: {e}")
                return False
        
        radio_icon_rect = pygame.Rect(self.width - 178, iy, ICON_SIZE, ICON_SIZE)
        if radio_icon_rect.collidepoint(pos):
            try:
                if hasattr(self, 'radio_panel') and self.radio_panel is not None:
                    # Toggle radio panel
                    self.radio_panel.is_open = not self.radio_panel.is_open
                    print(f"Radio panel toggled: {self.radio_panel.is_open}")
                    
                    # Close other panels if open
                    self.show_settings_panel = False
                    self.show_actions_panel = False
                    if hasattr(self, 'weather_panel') and self.weather_panel:
                        self.weather_panel.is_open = False
                    self.slider_rect = None
                else:
                    print("Radio panel not properly initialized. Check airport data loading.")
                    print(f"radio_panel attribute exists: {hasattr(self, 'radio_panel')}")
                    print(f"radio_panel value: {getattr(self, 'radio_panel', 'N/A')}")
                    return False  # Don't consume the click if panel isn't ready
                return True
            except Exception as e:
                print(f"Error toggling radio panel: {e}")
                import traceback
                traceback.print_exc()
                return False
        
        # Check if actions icon was clicked (left of radio)
        actions_icon_rect = pygame.Rect(self.width - 210, 5, 25, 25)
        if actions_icon_rect.collidepoint(pos):
            self.show_actions_panel = not self.show_actions_panel
            self.actions_dropdown_open = None  # Reset dropdown state
            # Close other panels
            self.show_settings_panel = False
            self.show_voice_panel = False
            if hasattr(self, 'weather_panel') and self.weather_panel:
                self.weather_panel.is_open = False
            if hasattr(self, 'radio_panel') and self.radio_panel:
                self.radio_panel.is_open = False
            self.slider_rect = None
            print(f"Actions panel toggled: {self.show_actions_panel}")
            return True

        discord_icon_rect = pygame.Rect(PAD, iy, ICON_SIZE, ICON_SIZE)
        if discord_icon_rect.collidepoint(pos):
            self.discord_clicked()
            return True
        
        return False
    
    def discord_clicked(self):
        """Handle click on discord icon"""
        webbrowser.open("https://discord.gg/2WFdnMW7pF")
    
    def render(self, screen, info_font):
        """Render the top menu bar with icons
        
        Args:
            screen: Pygame screen surface
            info_font: Font for rendering text
        """
        bar_rect = pygame.Rect(0, 0, self.width, self.height)
        pygame.draw.rect(screen, THEME["bg_bar"], bar_rect)
        
        pause_icon_x = self.width - 40
        pause_icon_y = (self.height - ICON_SIZE) // 2
        pause_icon_rect = pygame.Rect(pause_icon_x, pause_icon_y, ICON_SIZE, ICON_SIZE)
        pause_bg = THEME["icon_bg_pause"] if self.is_paused else (THEME["icon_bg_hover"] if self.hovered_icon == "pause" else THEME["icon_bg"])
        pygame.draw.rect(screen, pause_bg, pause_icon_rect, border_radius=RADIUS_SM)
        
        icon_x = pause_icon_x + (ICON_SIZE - 24) // 2
        icon_y = pause_icon_y + (ICON_SIZE - 24) // 2
        
        if self.is_paused and self.play_icon:
            # Show play icon when paused
            screen.blit(self.play_icon, (icon_x, icon_y))
        elif not self.is_paused and self.pause_icon:
            # Show pause icon when playing
            screen.blit(self.pause_icon, (icon_x, icon_y))
        
        settings_icon_x = self.width - 78
        settings_icon_y = (self.height - ICON_SIZE) // 2
        settings_icon_rect = pygame.Rect(settings_icon_x, settings_icon_y, ICON_SIZE, ICON_SIZE)
        settings_bg = THEME["icon_bg_active"] if self.show_settings_panel else (THEME["icon_bg_hover"] if self.hovered_icon == "settings" else THEME["icon_bg"])
        pygame.draw.rect(screen, settings_bg, settings_icon_rect, border_radius=RADIUS_SM)
        
        if self.settings_icon:
            icon_x = settings_icon_x + (ICON_SIZE - 24) // 2
            icon_y = settings_icon_y + (ICON_SIZE - 24) // 2
            screen.blit(self.settings_icon, (icon_x, icon_y))
        else:
            center_x = settings_icon_x + ICON_SIZE // 2
            center_y = settings_icon_y + ICON_SIZE // 2
            pygame.draw.circle(screen, THEME["text"], (center_x, center_y), 8, 2)
            for i in range(8):
                angle = i * 45
                rad = angle * 3.14159 / 180
                x = center_x + int(10 * (1 if i % 2 == 0 else 0.7) * pygame.math.Vector2(1, 0).rotate(angle).x)
                y = center_y + int(10 * (1 if i % 2 == 0 else 0.7) * pygame.math.Vector2(1, 0).rotate(angle).y)
                pygame.draw.circle(screen, THEME["text"], (x, y), 2)
        
        divider_x = self.width - 98
        pygame.draw.line(screen, THEME["separator"], (divider_x, PAD_XS), (divider_x, self.height - PAD_XS), 1)
        
        weather_icon_x = self.width - 143
        weather_icon_y = (self.height - ICON_SIZE) // 2
        weather_icon_rect = pygame.Rect(weather_icon_x, weather_icon_y, ICON_SIZE, ICON_SIZE)
        weather_bg = THEME["icon_bg_active"] if (self.weather_panel and self.weather_panel.is_open) else (THEME["icon_bg_hover"] if self.hovered_icon == "weather" else THEME["icon_bg"])
        pygame.draw.rect(screen, weather_bg, weather_icon_rect, border_radius=RADIUS_SM)
        
        if self.weather_icon:
            screen.blit(self.weather_icon, (weather_icon_x + (ICON_SIZE - 24) // 2, weather_icon_y + (ICON_SIZE - 24) // 2))
        else:
            cx, cy = weather_icon_x + ICON_SIZE // 2, weather_icon_y + ICON_SIZE // 2
            pygame.draw.circle(screen, THEME["badge_warning"], (cx + 5, cy - 4), 4)
            pygame.draw.circle(screen, THEME["text"], (cx - 3, cy + 2), 5, 2)
            pygame.draw.circle(screen, THEME["text"], (cx + 3, cy + 2), 4, 2)
        
        radio_icon_x = self.width - 178
        radio_icon_y = (self.height - ICON_SIZE) // 2
        radio_icon_rect = pygame.Rect(radio_icon_x, radio_icon_y, ICON_SIZE, ICON_SIZE)
        radio_bg = THEME["icon_bg_active"] if (self.radio_panel and self.radio_panel.is_open) else (THEME["icon_bg_hover"] if self.hovered_icon == "radio" else THEME["icon_bg"])
        pygame.draw.rect(screen, radio_bg, radio_icon_rect, border_radius=RADIUS_SM)
        
        if self.radio_icon:
            screen.blit(self.radio_icon, (radio_icon_x + (ICON_SIZE - 24) // 2, radio_icon_y + (ICON_SIZE - 24) // 2))
        
        actions_icon_x = self.width - 213
        actions_icon_y = (self.height - ICON_SIZE) // 2
        actions_icon_rect = pygame.Rect(actions_icon_x, actions_icon_y, ICON_SIZE, ICON_SIZE)
        has_active_actions = (self.ground_stop_active or self.gdp_active or self.gate_hold_active or
                              self.emergency_stop_active or len(self.closed_runways) > 0 or len(self.closed_taxiways) > 0)
        actions_bg = THEME["icon_bg_actions"] if (self.show_actions_panel or has_active_actions) else (THEME["icon_bg_hover"] if self.hovered_icon == "actions" else THEME["icon_bg"])
        pygame.draw.rect(screen, actions_bg, actions_icon_rect, border_radius=RADIUS_SM)
        
        if self.actions_icon:
            screen.blit(self.actions_icon, (actions_icon_x + (ICON_SIZE - 24) // 2, actions_icon_y + (ICON_SIZE - 24) // 2))
        
        discord_icon_x = PAD
        discord_icon_y = (self.height - ICON_SIZE) // 2
        discord_icon_rect = pygame.Rect(discord_icon_x, discord_icon_y, ICON_SIZE, ICON_SIZE)
        discord_bg = THEME["icon_bg_discord"] if self.hovered_icon == "discord" else THEME["icon_bg"]
        pygame.draw.rect(screen, discord_bg, discord_icon_rect, border_radius=RADIUS_SM)
        
        if self.discord_icon:
            screen.blit(self.discord_icon, (discord_icon_x + (ICON_SIZE - 24) // 2, discord_icon_y + (ICON_SIZE - 24) // 2))
        
        # === ACTIVE RESTRICTIONS STATUS ===
        active_texts = []
        if self.emergency_stop_active:
            active_texts.append(("EMERGENCY", THEME["badge_emergency"]))
        if self.ground_stop_active and not self.emergency_stop_active:
            active_texts.append(("GS", THEME["badge_warning"]))
        if self.gate_hold_active and not self.emergency_stop_active:
            active_texts.append(("HOLD", THEME["badge_warning"]))
        if self.gdp_active:
            active_texts.append((f"GDP+{self.gdp_delay_minutes}", THEME["badge_warning"]))
        
        if active_texts:
            status_x = discord_icon_x + ICON_SIZE + PAD_XS
            try:
                small_font = pygame.font.Font(None, 13)
            except Exception:
                small_font = info_font
            for text, color in active_texts:
                text_surf = small_font.render(text, True, color)
                tw = text_surf.get_width()
                badge_rect = pygame.Rect(status_x, (self.height - 16) // 2, tw + PAD_XS * 2, 16)
                pygame.draw.rect(screen, THEME["badge_bg"], badge_rect, border_radius=RADIUS_SM)
                screen.blit(text_surf, (status_x + PAD_XS, (self.height - text_surf.get_height()) // 2))
                status_x += tw + PAD_XS * 2 + 6
        
        # Draw settings panel if open
        if self.show_settings_panel:
            self._render_settings_panel(screen, info_font)
        
        # Draw actions panel if open
        if self.show_actions_panel:
            self._render_actions_panel(screen, info_font)

        # Tooltip is drawn by simulation.render() last so it appears above all UI
    
    def _render_settings_panel(self, screen, info_font):
        """Settings panel with consistent padding and theme."""
        panel_width = 292
        panel_height = 670
        panel_x = self.width - panel_width - PAD
        panel_y = self.height + PAD_XS
        
        panel_surface = pygame.Surface((panel_width, panel_height))
        panel_surface.set_alpha(255)
        panel_surface.fill(THEME["bg_panel"])
        pygame.draw.rect(panel_surface, THEME["border"], (0, 0, panel_width, panel_height), 1, border_radius=RADIUS)
        
        y = PAD
        title_text = info_font.render("Settings", True, THEME["text"])
        panel_surface.blit(title_text, (PAD, y))
        y += TITLE_H
        pygame.draw.line(panel_surface, THEME["separator"], (PAD, y), (panel_width - PAD, y), SEP_H)
        y += SECTION_GAP
        
        # Leader Lines
        panel_surface.blit(info_font.render("Leader Lines", True, THEME["text_secondary"]), (PAD, y))
        y += ROW_H
        slider_w = panel_width - PAD * 2 - 44
        slider_x = PAD
        track_rect = pygame.Rect(slider_x, y, slider_w, SLIDER_H)
        pygame.draw.rect(panel_surface, THEME["slider_track"], track_rect, border_radius=3)
        pct = (self.leader_line_length - 30) / 90.0
        hx = slider_x + int(pct * slider_w)
        if hx > slider_x:
            pygame.draw.rect(panel_surface, THEME["slider_fill"], (slider_x, y, hx - slider_x, SLIDER_H), border_radius=3)
        pygame.draw.circle(panel_surface, THEME["slider_handle"], (hx, y + SLIDER_H // 2), 6)
        panel_surface.blit(info_font.render(f"{int(self.leader_line_length)}", True, THEME["text"]), (panel_width - PAD - 36, y - 2))
        self.slider_rect = pygame.Rect(panel_x + slider_x, panel_y + y, slider_w, SLIDER_H + 16)
        self.slider_x_start = panel_x + slider_x
        self.slider_width = slider_w
        y += SLIDER_H + SECTION_GAP
        
        pygame.draw.line(panel_surface, THEME["separator"], (PAD, y), (panel_width - PAD, y), SEP_H)
        y += SECTION_GAP
        
        # Time Speed
        panel_surface.blit(info_font.render("Time Speed", True, THEME["text_secondary"]), (PAD, y))
        y += ROW_H
        time_slider_x = PAD
        time_track = pygame.Rect(time_slider_x, y, slider_w, SLIDER_H)
        pygame.draw.rect(panel_surface, THEME["slider_track"], time_track, border_radius=3)
        tpct = (self.time_acceleration - 1.0) / 19.0
        thx = time_slider_x + int(tpct * slider_w)
        if thx > time_slider_x:
            pygame.draw.rect(panel_surface, THEME["slider_fill"], (time_slider_x, y, thx - time_slider_x, SLIDER_H), border_radius=3)
        pygame.draw.circle(panel_surface, THEME["slider_handle"], (thx, y + SLIDER_H // 2), 6)
        panel_surface.blit(info_font.render(f"{self.time_acceleration:.1f}x", True, THEME["text"]), (panel_width - PAD - 40, y - 2))
        self.time_slider_rect = pygame.Rect(panel_x + time_slider_x, panel_y + y, slider_w, SLIDER_H + 16)
        self.time_slider_x_start = panel_x + time_slider_x
        self.time_slider_width = slider_w
        y += SLIDER_H + SECTION_GAP
        
        pygame.draw.line(panel_surface, THEME["separator"], (PAD, y), (panel_width - PAD, y), SEP_H)
        y += SECTION_GAP
        
        # Toggles
        toggle_x = panel_width - PAD - TOGGLE_W
        panel_surface.blit(info_font.render("Help Files", True, THEME["text_secondary"]), (PAD, y + 2))
        tr = pygame.Rect(toggle_x, y, TOGGLE_W, TOGGLE_H)
        pygame.draw.rect(panel_surface, THEME["toggle_on"] if self.show_helpfiles else THEME["toggle_off"], tr, border_radius=TOGGLE_R)
        kx = toggle_x + TOGGLE_W - TOGGLE_R - 2 if self.show_helpfiles else toggle_x + 2
        pygame.draw.circle(panel_surface, THEME["toggle_knob"], (kx, y + TOGGLE_H // 2), TOGGLE_R - 2)
        self.helpfiles_toggle_rect = pygame.Rect(panel_x + toggle_x, panel_y + y, TOGGLE_W, TOGGLE_H)
        y += TOGGLE_H + PAD_SM
        
        panel_surface.blit(info_font.render("TTS Audio", True, THEME["text_secondary"]), (PAD, y + 2))
        tr2 = pygame.Rect(toggle_x, y, TOGGLE_W, TOGGLE_H)
        pygame.draw.rect(panel_surface, THEME["toggle_on"] if self.enable_tts_audio else THEME["toggle_off"], tr2, border_radius=TOGGLE_R)
        kx2 = toggle_x + TOGGLE_W - TOGGLE_R - 2 if self.enable_tts_audio else toggle_x + 2
        pygame.draw.circle(panel_surface, THEME["toggle_knob"], (kx2, y + TOGGLE_H // 2), TOGGLE_R - 2)
        self.enable_tts_audio_toggle_rect = pygame.Rect(panel_x + toggle_x, panel_y + y, TOGGLE_W, TOGGLE_H)
        y += TOGGLE_H + PAD_SM
        
        panel_surface.blit(info_font.render("Past transmissions", True, THEME["text_secondary"]), (PAD, y + 2))
        tr3 = pygame.Rect(toggle_x, y, TOGGLE_W, TOGGLE_H)
        pygame.draw.rect(panel_surface, THEME["toggle_on"] if self.show_past_transmissions else THEME["toggle_off"], tr3, border_radius=TOGGLE_R)
        kx3 = toggle_x + TOGGLE_W - TOGGLE_R - 2 if self.show_past_transmissions else toggle_x + 2
        pygame.draw.circle(panel_surface, THEME["toggle_knob"], (kx3, y + TOGGLE_H // 2), TOGGLE_R - 2)
        self.show_past_transmissions_toggle_rect = pygame.Rect(panel_x + toggle_x, panel_y + y, TOGGLE_W, TOGGLE_H)
        y += TOGGLE_H + SECTION_GAP

        # ── Voice / STT section ───────────────────────────────────────────────
        pygame.draw.line(panel_surface, THEME["separator"], (PAD, y), (panel_width - PAD, y), SEP_H)
        y += SECTION_GAP
        panel_surface.blit(info_font.render("Voice / STT", True, THEME["text"]), (PAD, y))
        y += TITLE_H
        pygame.draw.line(panel_surface, THEME["separator"], (PAD, y), (panel_width - PAD, y), SEP_H)
        y += SECTION_GAP

        # Voice Commands toggle
        panel_surface.blit(info_font.render("Voice Commands", True, THEME["text_secondary"]), (PAD, y + 2))
        vtr = pygame.Rect(toggle_x, y, TOGGLE_W, TOGGLE_H)
        pygame.draw.rect(panel_surface, THEME["toggle_on"] if self.voice_commands_enabled else THEME["toggle_off"], vtr, border_radius=TOGGLE_R)
        vkx = toggle_x + TOGGLE_W - TOGGLE_R - 2 if self.voice_commands_enabled else toggle_x + 2
        pygame.draw.circle(panel_surface, THEME["toggle_knob"], (vkx, y + TOGGLE_H // 2), TOGGLE_R - 2)
        self.voice_enabled_toggle_rect = pygame.Rect(panel_x + toggle_x, panel_y + y, TOGGLE_W, TOGGLE_H)
        y += TOGGLE_H + SECTION_GAP

        pygame.draw.line(panel_surface, THEME["separator"], (PAD, y), (panel_width - PAD, y), SEP_H)
        y += SECTION_GAP

        # PTT Key
        panel_surface.blit(info_font.render("PTT Key", True, THEME["text_secondary"]), (PAD, y))
        y += ROW_H
        ptt_display = pygame.key.name(self.ptt_key_code).upper() if self.ptt_key_code else "L-SHIFT"
        btn_label = ">> PRESS ANY KEY <<" if self.ptt_listening else ptt_display
        btn_color = (60, 80, 50) if self.ptt_listening else THEME["bg_control"]
        btn_border = (80, 180, 80) if self.ptt_listening else THEME["border"]
        ptt_btn_rect = pygame.Rect(PAD, y, panel_width - PAD * 2, BTN_H)
        pygame.draw.rect(panel_surface, btn_color, ptt_btn_rect, border_radius=RADIUS_SM)
        pygame.draw.rect(panel_surface, btn_border, ptt_btn_rect, 1, border_radius=RADIUS_SM)
        lbl_s = info_font.render(btn_label, True, (120, 255, 120) if self.ptt_listening else THEME["text"])
        panel_surface.blit(lbl_s, lbl_s.get_rect(center=ptt_btn_rect.center))
        self.voice_ptt_btn_rect = pygame.Rect(panel_x + PAD, panel_y + y, panel_width - PAD * 2, BTN_H)
        y += BTN_H + SECTION_GAP

        pygame.draw.line(panel_surface, THEME["separator"], (PAD, y), (panel_width - PAD, y), SEP_H)
        y += SECTION_GAP

        # Mic Input
        ARROW_W = 24
        mic_idx = next((i for i, (idx, _) in enumerate(self._mic_devices) if idx == self.mic_device_index), 0)
        mic_name = self._mic_devices[mic_idx][1] if self._mic_devices else "System Default"
        mic_name = mic_name[:26] + ".." if len(mic_name) > 26 else mic_name
        panel_surface.blit(info_font.render("Mic Input", True, THEME["text_secondary"]), (PAD, y))
        y += ROW_H
        mp_rect = pygame.Rect(PAD, y, ARROW_W, ROW_H)
        pygame.draw.rect(panel_surface, THEME["bg_control"], mp_rect, border_radius=RADIUS_SM)
        panel_surface.blit(info_font.render("<", True, THEME["text"]),
                           info_font.render("<", True, THEME["text"]).get_rect(center=mp_rect.center))
        self.voice_mic_prev_rect = pygame.Rect(panel_x + PAD, panel_y + y, ARROW_W, ROW_H)
        mn_rect = pygame.Rect(panel_width - PAD - ARROW_W, y, ARROW_W, ROW_H)
        pygame.draw.rect(panel_surface, THEME["bg_control"], mn_rect, border_radius=RADIUS_SM)
        panel_surface.blit(info_font.render(">", True, THEME["text"]),
                           info_font.render(">", True, THEME["text"]).get_rect(center=mn_rect.center))
        self.voice_mic_next_rect = pygame.Rect(panel_x + panel_width - PAD - ARROW_W, panel_y + y, ARROW_W, ROW_H)
        mic_s = info_font.render(mic_name, True, THEME["text"])
        panel_surface.blit(mic_s, mic_s.get_rect(midleft=(PAD + ARROW_W + 4, y + ROW_H // 2)))
        y += ROW_H + SECTION_GAP

        pygame.draw.line(panel_surface, THEME["separator"], (PAD, y), (panel_width - PAD, y), SEP_H)
        y += SECTION_GAP

        # Audio Output
        spk_idx = next((i for i, (idx, _) in enumerate(self._spk_devices) if idx == self.speaker_device_index), 0)
        spk_name = self._spk_devices[spk_idx][1] if self._spk_devices else "System Default"
        spk_name = spk_name[:26] + ".." if len(spk_name) > 26 else spk_name
        panel_surface.blit(info_font.render("Audio Output", True, THEME["text_secondary"]), (PAD, y))
        y += ROW_H
        sp_rect = pygame.Rect(PAD, y, ARROW_W, ROW_H)
        pygame.draw.rect(panel_surface, THEME["bg_control"], sp_rect, border_radius=RADIUS_SM)
        panel_surface.blit(info_font.render("<", True, THEME["text"]),
                           info_font.render("<", True, THEME["text"]).get_rect(center=sp_rect.center))
        self.voice_spk_prev_rect = pygame.Rect(panel_x + PAD, panel_y + y, ARROW_W, ROW_H)
        sn_rect = pygame.Rect(panel_width - PAD - ARROW_W, y, ARROW_W, ROW_H)
        pygame.draw.rect(panel_surface, THEME["bg_control"], sn_rect, border_radius=RADIUS_SM)
        panel_surface.blit(info_font.render(">", True, THEME["text"]),
                           info_font.render(">", True, THEME["text"]).get_rect(center=sn_rect.center))
        self.voice_spk_next_rect = pygame.Rect(panel_x + panel_width - PAD - ARROW_W, panel_y + y, ARROW_W, ROW_H)
        spk_s = info_font.render(spk_name, True, THEME["text"])
        panel_surface.blit(spk_s, spk_s.get_rect(midleft=(PAD + ARROW_W + 4, y + ROW_H // 2)))
        y += ROW_H + SECTION_GAP

        # Save button
        btn_w = 100
        btn_h = 32
        save_button_rect = pygame.Rect((panel_width - btn_w) // 2, panel_height - PAD - btn_h, btn_w, btn_h)
        pygame.draw.rect(panel_surface, THEME["btn"], save_button_rect, border_radius=RADIUS_SM)
        pygame.draw.rect(panel_surface, THEME["btn_border"], save_button_rect, 1, border_radius=RADIUS_SM)
        st = info_font.render("Save", True, THEME["text"])
        panel_surface.blit(st, st.get_rect(center=save_button_rect.center))
        self.save_sim_button_rect = pygame.Rect(panel_x + save_button_rect.x, panel_y + save_button_rect.y, btn_w, btn_h)
        
        screen.blit(panel_surface, (panel_x, panel_y))

    def _render_voice_panel(self, screen, info_font):
        """Voice / STT settings panel: PTT key, mic device, speaker device, toggles."""
        panel_width  = 292
        panel_x = self.width - panel_width - PAD
        panel_y = self.height + PAD_XS

        # ── Build content rows ─────────────────────────────────────────────
        ARROW_W = 24
        toggle_x = panel_width - PAD - TOGGLE_W

        # Work out mic / speaker display strings
        mic_idx = next((i for i, (idx, _) in enumerate(self._mic_devices)
                        if idx == self.mic_device_index), 0)
        spk_idx = next((i for i, (idx, _) in enumerate(self._spk_devices)
                        if idx == self.speaker_device_index), 0)
        mic_name = self._mic_devices[mic_idx][1] if self._mic_devices else "System Default"
        spk_name = self._spk_devices[spk_idx][1] if self._spk_devices else "System Default"
        # Truncate long names so they fit the panel
        max_chars = 26
        mic_name = mic_name[:max_chars] + ".." if len(mic_name) > max_chars else mic_name
        spk_name = spk_name[:max_chars] + ".." if len(spk_name) > max_chars else spk_name

        ptt_display = pygame.key.name(self.ptt_key_code).upper() if self.ptt_key_code else "L-SHIFT"

        # ── Calculate panel height ─────────────────────────────────────────
        # title + sep + voice toggle + tts toggle + sep + PTT label + PTT btn
        # + sep + mic label + mic row + sep + spk label + spk row + pad
        panel_height = (PAD + TITLE_H + SECTION_GAP          # header
                        + TOGGLE_H + PAD_SM                   # voice toggle
                        + TOGGLE_H + SECTION_GAP              # tts toggle
                        + SEP_H + SECTION_GAP                 # separator
                        + ROW_H                               # PTT label
                        + BTN_H + SECTION_GAP                 # PTT button
                        + SEP_H + SECTION_GAP                 # separator
                        + ROW_H                               # mic label
                        + ROW_H + SECTION_GAP                 # mic row
                        + SEP_H + SECTION_GAP                 # separator
                        + ROW_H                               # spk label
                        + ROW_H + PAD)                        # spk row + bottom pad

        ps = pygame.Surface((panel_width, panel_height))
        ps.set_alpha(255)
        ps.fill(THEME["bg_panel"])
        pygame.draw.rect(ps, THEME["border"], (0, 0, panel_width, panel_height), 1,
                         border_radius=RADIUS)

        y = PAD
        # Title
        ps.blit(info_font.render("Voice / STT", True, THEME["text"]), (PAD, y))
        y += TITLE_H
        pygame.draw.line(ps, THEME["separator"], (PAD, y), (panel_width - PAD, y), SEP_H)
        y += SECTION_GAP

        # ── Voice Commands toggle ──────────────────────────────────────────
        ps.blit(info_font.render("Voice Commands", True, THEME["text_secondary"]), (PAD, y + 2))
        tr = pygame.Rect(toggle_x, y, TOGGLE_W, TOGGLE_H)
        pygame.draw.rect(ps, THEME["toggle_on"] if self.voice_commands_enabled else THEME["toggle_off"],
                         tr, border_radius=TOGGLE_R)
        kx = toggle_x + TOGGLE_W - TOGGLE_R - 2 if self.voice_commands_enabled else toggle_x + 2
        pygame.draw.circle(ps, THEME["toggle_knob"], (kx, y + TOGGLE_H // 2), TOGGLE_R - 2)
        self.voice_enabled_toggle_rect = pygame.Rect(panel_x + toggle_x, panel_y + y, TOGGLE_W, TOGGLE_H)
        y += TOGGLE_H + PAD_SM

        # ── TTS Audio toggle ───────────────────────────────────────────────
        ps.blit(info_font.render("TTS Audio", True, THEME["text_secondary"]), (PAD, y + 2))
        tr2 = pygame.Rect(toggle_x, y, TOGGLE_W, TOGGLE_H)
        pygame.draw.rect(ps, THEME["toggle_on"] if self.enable_tts_audio else THEME["toggle_off"],
                         tr2, border_radius=TOGGLE_R)
        kx2 = toggle_x + TOGGLE_W - TOGGLE_R - 2 if self.enable_tts_audio else toggle_x + 2
        pygame.draw.circle(ps, THEME["toggle_knob"], (kx2, y + TOGGLE_H // 2), TOGGLE_R - 2)
        self.voice_tts_toggle_rect = pygame.Rect(panel_x + toggle_x, panel_y + y, TOGGLE_W, TOGGLE_H)
        y += TOGGLE_H + SECTION_GAP

        pygame.draw.line(ps, THEME["separator"], (PAD, y), (panel_width - PAD, y), SEP_H)
        y += SECTION_GAP

        # ── PTT Key ────────────────────────────────────────────────────────
        ps.blit(info_font.render("PTT Key", True, THEME["text_secondary"]), (PAD, y))
        y += ROW_H
        btn_label = ">> PRESS ANY KEY <<" if self.ptt_listening else ptt_display
        btn_color = (60, 80, 50) if self.ptt_listening else THEME["bg_control"]
        btn_border = (80, 180, 80) if self.ptt_listening else THEME["border"]
        ptt_btn_rect = pygame.Rect(PAD, y, panel_width - PAD * 2, BTN_H)
        pygame.draw.rect(ps, btn_color, ptt_btn_rect, border_radius=RADIUS_SM)
        pygame.draw.rect(ps, btn_border, ptt_btn_rect, 1, border_radius=RADIUS_SM)
        lbl_s = info_font.render(btn_label, True,
                                 (120, 255, 120) if self.ptt_listening else THEME["text"])
        ps.blit(lbl_s, lbl_s.get_rect(center=ptt_btn_rect.center))
        self.voice_ptt_btn_rect = pygame.Rect(panel_x + PAD, panel_y + y,
                                              panel_width - PAD * 2, BTN_H)
        y += BTN_H + SECTION_GAP

        pygame.draw.line(ps, THEME["separator"], (PAD, y), (panel_width - PAD, y), SEP_H)
        y += SECTION_GAP

        # ── Mic Input ──────────────────────────────────────────────────────
        ps.blit(info_font.render("Mic Input", True, THEME["text_secondary"]), (PAD, y))
        y += ROW_H
        # Prev arrow
        mp_rect = pygame.Rect(PAD, y, ARROW_W, ROW_H)
        pygame.draw.rect(ps, THEME["bg_control"], mp_rect, border_radius=RADIUS_SM)
        ps.blit(info_font.render("<", True, THEME["text"]),
                info_font.render("<", True, THEME["text"]).get_rect(center=mp_rect.center))
        self.voice_mic_prev_rect = pygame.Rect(panel_x + PAD, panel_y + y, ARROW_W, ROW_H)
        # Next arrow
        mn_rect = pygame.Rect(panel_width - PAD - ARROW_W, y, ARROW_W, ROW_H)
        pygame.draw.rect(ps, THEME["bg_control"], mn_rect, border_radius=RADIUS_SM)
        ps.blit(info_font.render(">", True, THEME["text"]),
                info_font.render(">", True, THEME["text"]).get_rect(center=mn_rect.center))
        self.voice_mic_next_rect = pygame.Rect(panel_x + panel_width - PAD - ARROW_W,
                                               panel_y + y, ARROW_W, ROW_H)
        # Name
        name_s = info_font.render(mic_name, True, THEME["text"])
        name_area = pygame.Rect(PAD + ARROW_W + 4, y, panel_width - PAD * 2 - ARROW_W * 2 - 8, ROW_H)
        ps.blit(name_s, name_s.get_rect(midleft=(name_area.x, name_area.centery)))
        y += ROW_H + SECTION_GAP

        pygame.draw.line(ps, THEME["separator"], (PAD, y), (panel_width - PAD, y), SEP_H)
        y += SECTION_GAP

        # ── Audio Output ───────────────────────────────────────────────────
        ps.blit(info_font.render("Audio Output", True, THEME["text_secondary"]), (PAD, y))
        y += ROW_H
        sp_rect = pygame.Rect(PAD, y, ARROW_W, ROW_H)
        pygame.draw.rect(ps, THEME["bg_control"], sp_rect, border_radius=RADIUS_SM)
        ps.blit(info_font.render("<", True, THEME["text"]),
                info_font.render("<", True, THEME["text"]).get_rect(center=sp_rect.center))
        self.voice_spk_prev_rect = pygame.Rect(panel_x + PAD, panel_y + y, ARROW_W, ROW_H)
        sn_rect = pygame.Rect(panel_width - PAD - ARROW_W, y, ARROW_W, ROW_H)
        pygame.draw.rect(ps, THEME["bg_control"], sn_rect, border_radius=RADIUS_SM)
        ps.blit(info_font.render(">", True, THEME["text"]),
                info_font.render(">", True, THEME["text"]).get_rect(center=sn_rect.center))
        self.voice_spk_next_rect = pygame.Rect(panel_x + panel_width - PAD - ARROW_W,
                                               panel_y + y, ARROW_W, ROW_H)
        sname_s = info_font.render(spk_name, True, THEME["text"])
        sname_area = pygame.Rect(PAD + ARROW_W + 4, y, panel_width - PAD * 2 - ARROW_W * 2 - 8, ROW_H)
        ps.blit(sname_s, sname_s.get_rect(midleft=(sname_area.x, sname_area.centery)))

        screen.blit(ps, (panel_x, panel_y))

    def handle_key_for_rebind(self, event):
        """Call from simulation KEYDOWN when ptt_listening is True to capture the new key."""
        if not self.ptt_listening:
            return False
        self.ptt_key_code = event.key
        self.ptt_listening = False
        self.save_settings()
        print(f"[Voice] PTT key rebound to: {pygame.key.name(event.key)}")
        return True

    def _render_tooltip(self, screen, info_font):
        """Render tooltip for hovered icon - clean pill above icon."""
        tooltip_texts = {
            'discord': 'Discord',
            'pause': 'Pause' if not self.is_paused else 'Resume',
            'settings': 'Settings',
            'weather': 'Weather',
            'radio': 'Radio',
            'actions': 'Actions',
            'voice': 'Voice / STT',
        }
        tooltip_text = tooltip_texts.get(self.hovered_icon, '')
        if not tooltip_text:
            return
        
        iy = (self.height - ICON_SIZE) // 2
        icon_positions = {
            'discord': (PAD, iy),
            'pause': (self.width - 40, iy),
            'settings': (self.width - 78, iy),
            'weather': (self.width - 143, iy),
            'radio': (self.width - 178, iy),
            'actions': (self.width - 213, iy),
            'voice': (self.width - 248, iy),
        }
        icon_x, icon_y = icon_positions.get(self.hovered_icon, (0, 0))
        icon_size = ICON_SIZE
        
        try:
            tip_font = pygame.font.SysFont('Segoe UI, Tahoma, Arial, sans-serif', 14)
        except Exception:
            tip_font = pygame.font.Font(None, 20)
        text_surface = tip_font.render(tooltip_text, True, THEME["tooltip_text"])
        text_width, text_height = text_surface.get_size()
        
        pad_h, pad_v = TOOLTIP_PAD, 6
        tw = text_width + pad_h * 2
        th = text_height + pad_v * 2
        rad = THEME["radius_small"]
        shadow_off = 2
        
        tooltip_x = icon_x + (icon_size - tw) // 2
        tooltip_y_above = icon_y - th - 6
        tooltip_y = tooltip_y_above if tooltip_y_above >= 5 else icon_y + icon_size + 6
        tooltip_x = max(5, min(tooltip_x, self.width - tw - 5))
        
        # Shadow (drawn on screen)
        shadow_rect = pygame.Rect(tooltip_x + shadow_off, tooltip_y + shadow_off, tw, th)
        pygame.draw.rect(screen, THEME["tooltip_shadow"], shadow_rect, border_radius=rad + 1)
        
        # Tooltip surface: solid, no alpha
        tooltip_surface = pygame.Surface((tw, th))
        tooltip_surface.fill(THEME["tooltip_bg"])
        pygame.draw.rect(tooltip_surface, THEME["tooltip_border"], (0, 0, tw, th), 1, border_radius=rad)
        text_y = (th - text_height) // 2
        tooltip_surface.blit(text_surface, (pad_h, text_y))
        screen.blit(tooltip_surface, (tooltip_x, tooltip_y))
        
        
    def _render_controller_panel(self, screen, info_font):
        panel_width = 300
        panel_height = 260
        panel_x = self.width - panel_width - 10
        panel_y = self.height + 5
        r = THEME["panel_radius"]
        
        panel_surface = pygame.Surface((panel_width, panel_height))
        panel_surface.set_alpha(252)
        panel_surface.fill(THEME["panel_bg"])
        pygame.draw.rect(panel_surface, THEME["panel_border"], (0, 0, panel_width, panel_height), 1, border_radius=r)
        
        title_text = info_font.render("Controller Panel", True, THEME["text_title"])
        panel_surface.blit(title_text, (10, 10))
        
        self.controller_panel_rect = pygame.Rect(panel_x, panel_y, panel_width, panel_height)
        screen.blit(panel_surface, (panel_x, panel_y))
    
    def _render_actions_panel(self, screen, info_font):
        """Render the ATC Actions panel dropdown"""
        panel_width = 260
        panel_height = 360
        panel_x = self.width - 210
        panel_y = self.height + 5
        r = THEME["panel_radius"]
        
        if panel_x + panel_width > self.width - 10:
            panel_x = self.width - panel_width - 10
        if panel_x < 10:
            panel_x = 10
        
        panel_surface = pygame.Surface((panel_width, panel_height))
        panel_surface.set_alpha(252)
        panel_surface.fill(THEME["panel_bg"])
        pygame.draw.rect(panel_surface, THEME["panel_border"], (0, 0, panel_width, panel_height), 1, border_radius=r)
        
        title_text = info_font.render("ATC Actions", True, THEME["text_title"])
        panel_surface.blit(title_text, (12, 10))
        
        y_offset = 36
        self.actions_button_rects = []
        
        section_text = info_font.render("TRAFFIC MANAGEMENT", True, THEME["section_header"])
        panel_surface.blit(section_text, (12, y_offset))
        y_offset += 20
        
        # Ground Stop button
        y_offset = self._draw_action_button(panel_surface, info_font, panel_x, panel_y,
                                            "ground_stop", "Ground Stop", 
                                            "Stop all departures", 
                                            self.ground_stop_active, y_offset, panel_width)
        
        # Ground Delay Program button
        gdp_desc = f"Delay deps ({self.gdp_delay_minutes}min)" if self.gdp_active else "Delay departures"
        y_offset = self._draw_action_button(panel_surface, info_font, panel_x, panel_y,
                                            "gdp", "Ground Delay Program", 
                                            gdp_desc,
                                            self.gdp_active, y_offset, panel_width)
        
        # Gate Hold button
        y_offset = self._draw_action_button(panel_surface, info_font, panel_x, panel_y,
                                            "gate_hold", "Gate Hold", 
                                            "Hold aircraft at gates",
                                            self.gate_hold_active, y_offset, panel_width)
        
        y_offset += 6
        
        section_text = info_font.render("RUNWAY OPERATIONS", True, THEME["section_header"])
        panel_surface.blit(section_text, (12, y_offset))
        y_offset += 20
        
        # Close Runway button (opens submenu)
        closed_rwy_text = f"({len(self.closed_runways)})" if self.closed_runways else ""
        y_offset = self._draw_action_button(panel_surface, info_font, panel_x, panel_y,
                                            "close_runway", "Close Runway", 
                                            f"Runway closures {closed_rwy_text}",
                                            len(self.closed_runways) > 0, y_offset, panel_width)
        
        # Close Taxiway button
        closed_twy_text = f"({len(self.closed_taxiways)})" if self.closed_taxiways else ""
        y_offset = self._draw_action_button(panel_surface, info_font, panel_x, panel_y,
                                            "close_taxiway", "Close Taxiway", 
                                            f"Taxiway closures {closed_twy_text}",
                                            len(self.closed_taxiways) > 0, y_offset, panel_width)
        
        y_offset += 6
        
        section_text = info_font.render("EMERGENCY", True, THEME["section_header"])
        panel_surface.blit(section_text, (12, y_offset))
        y_offset += 20
        
        # Emergency Stop button
        y_offset = self._draw_action_button(panel_surface, info_font, panel_x, panel_y,
                                            "emergency_stop", "Stop All Movement", 
                                            "Emergency ground stop",
                                            self.emergency_stop_active, y_offset, panel_width,
                                            is_emergency=True)
        
        # Resume Normal Operations button
        has_any_restrictions = (self.ground_stop_active or self.gdp_active or self.gate_hold_active or 
                                self.emergency_stop_active or len(self.closed_runways) > 0 or len(self.closed_taxiways) > 0)
        y_offset = self._draw_action_button(panel_surface, info_font, panel_x, panel_y,
                                            "resume_normal", "Resume Normal Ops", 
                                            "Clear all restrictions",
                                            False, y_offset, panel_width,
                                            is_resume=has_any_restrictions)
        
        # Blit panel surface
        screen.blit(panel_surface, (panel_x, panel_y))
    
    def _draw_action_button(self, surface, font, panel_x, panel_y, action_id, title, description,
                            is_active, y_offset, panel_width, is_emergency=False, is_resume=False):
        """Draw an action button and return the new y_offset"""
        btn_x = 8
        btn_width = panel_width - 16
        btn_height = 36
        rad = THEME["radius_small"]
        
        if is_emergency:
            bg_color = THEME["btn_emergency_bg"] if is_active else THEME["btn_emergency_inactive_bg"]
            border_color = THEME["btn_emergency_border"] if is_active else THEME["btn_emergency_inactive_border"]
        elif is_resume:
            bg_color = THEME["btn_resume_bg"]
            border_color = THEME["btn_resume_border"]
        elif is_active:
            bg_color = THEME["btn_active_bg"]
            border_color = THEME["btn_active_border"]
        else:
            bg_color = THEME["btn_bg"]
            border_color = THEME["btn_border"]
        
        btn_rect = pygame.Rect(btn_x, y_offset, btn_width, btn_height)
        pygame.draw.rect(surface, bg_color, btn_rect, border_radius=rad)
        pygame.draw.rect(surface, border_color, btn_rect, 1, border_radius=rad)
        
        title_color = THEME["text_title"] if is_active else THEME["text_label"]
        if is_resume:
            title_color = THEME["btn_resume_text"]
        title_surf = font.render(title, True, title_color)
        surface.blit(title_surf, (btn_x + 10, y_offset + 5))
        
        try:
            small_font = pygame.font.Font(None, 12)
        except Exception:
            small_font = font
        desc_color = THEME["text_dim"]
        desc_surf = small_font.render(description, True, desc_color)
        surface.blit(desc_surf, (btn_x + 10, y_offset + 21))
        
        if is_active:
            indicator_color = THEME["badge_emergency"] if is_emergency else THEME["badge_warning"]
            pygame.draw.circle(surface, indicator_color, (btn_x + btn_width - 12, y_offset + btn_height // 2), 4)
        
        screen_rect = pygame.Rect(panel_x + btn_x, panel_y + y_offset, btn_width, btn_height)
        self.actions_button_rects.append((action_id, screen_rect))
        
        return y_offset + btn_height + 3
    
    def _handle_action_click(self, action_id):
        """Handle click on an action button"""
        print(f"Action clicked: {action_id}")
        
        announcement = None  # Radio announcement to broadcast
        
        if action_id == "ground_stop":
            self.ground_stop_active = not self.ground_stop_active
            if self.ground_stop_active:
                print("GROUND STOP ACTIVATED - All departures held")
                announcement = "Attention all aircraft, ground stop is now in effect. All departures hold position."
            else:
                print("Ground stop lifted")
                announcement = "Ground stop has been lifted. Normal departure operations resumed."
                
        elif action_id == "gdp":
            self.gdp_active = not self.gdp_active
            if self.gdp_active:
                self.gdp_delay_minutes = 15  # Default 15 minute delay
                print(f"GDP ACTIVATED - {self.gdp_delay_minutes} minute delays")
                announcement = f"Ground delay program in effect. Expect {self.gdp_delay_minutes} minute departure delays."
            else:
                self.gdp_delay_minutes = 0
                print("GDP cancelled")
                announcement = "Ground delay program has been cancelled."
                
        elif action_id == "gate_hold":
            self.gate_hold_active = not self.gate_hold_active
            if self.gate_hold_active:
                print("GATE HOLD ACTIVATED - Aircraft held at gates")
                announcement = "Attention all aircraft, gate hold is in effect. Remain at your gate until further notice."
            else:
                print("Gate hold released")
                announcement = "Gate hold has been released. Normal pushback operations resumed."
                
        elif action_id == "close_runway":
            # TODO: Show runway selection submenu
            print("Runway closure menu - TODO: implement runway selector")
            
        elif action_id == "close_taxiway":
            # TODO: Show taxiway selection submenu
            print("Taxiway closure menu - TODO: implement taxiway selector")
            
        elif action_id == "emergency_stop":
            self.emergency_stop_active = not self.emergency_stop_active
            if self.emergency_stop_active:
                # Also activate ground stop
                self.ground_stop_active = True
                self.gate_hold_active = True
                print("EMERGENCY STOP - All ground movement halted")
                announcement = "ATTENTION ALL AIRCRAFT. STOP. I say again, ALL AIRCRAFT STOP. Emergency ground stop in effect."
            else:
                print("Emergency cleared")
                announcement = "Emergency has been cleared. Resume normal operations with caution."
                
        elif action_id == "resume_normal":
            # Clear all restrictions
            self.ground_stop_active = False
            self.gdp_active = False
            self.gdp_delay_minutes = 0
            self.gate_hold_active = False
            self.emergency_stop_active = False
            self.closed_runways.clear()
            self.closed_taxiways.clear()
            print("ALL RESTRICTIONS CLEARED - Normal operations resumed")
            announcement = "All traffic restrictions have been cleared. Normal operations resumed."
        
        # Notify simulation of changes
        if self.on_actions_changed:
            self.on_actions_changed()
        
        # Broadcast radio announcement if set
        if announcement and self.simulation_screen:
            try:
                if hasattr(self.simulation_screen, 'radio_panel') and self.simulation_screen.radio_panel:
                    # add_transmission(frequency, from_callsign, message, is_atc)
                    self.simulation_screen.radio_panel.add_transmission(
                        "121.9", "GROUND", announcement, is_atc=True
                    )
            except Exception as e:
                print(f"Could not broadcast announcement: {e}")

