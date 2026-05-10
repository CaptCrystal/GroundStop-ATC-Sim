"""
Settings menu for GroundStop
"""
import pygame
import json
import os


class Slider:
    """A draggable slider for numeric values"""
    
    def __init__(self, x, y, width, label, min_val, max_val, current_val, font):
        self.x = x
        self.y = y
        self.width = width
        self.height = 20
        self.label = label
        self.min_val = min_val
        self.max_val = max_val
        self.current_val = current_val
        self.font = font
        
        self.track_rect = pygame.Rect(x, y, width, 8)
        self.handle_radius = 10
        self.dragging = False
        
        # Colors
        self.track_color = (60, 60, 80)
        self.handle_color = (100, 150, 200)
        self.handle_hover_color = (120, 170, 220)
        self.text_color = (255, 255, 255)
        
        self.hovered = False
    
    def get_handle_x(self):
        """Calculate handle X position based on current value"""
        ratio = (self.current_val - self.min_val) / (self.max_val - self.min_val)
        return self.x + int(ratio * self.width)
    
    def handle_event(self, event):
        """Handle mouse events"""
        handle_x = self.get_handle_x()
        handle_pos = pygame.math.Vector2(handle_x, self.y + 4)
        
        if event.type == pygame.MOUSEMOTION:
            mouse_pos = pygame.math.Vector2(event.pos)
            self.hovered = (mouse_pos - handle_pos).length() < self.handle_radius + 5
            
            if self.dragging:
                # Update value based on mouse position
                ratio = max(0, min(1, (event.pos[0] - self.x) / self.width))
                self.current_val = self.min_val + ratio * (self.max_val - self.min_val)
                return True
        
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1 and self.hovered:
                self.dragging = True
                return True
        
        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:
                self.dragging = False
        
        return False
    
    def render(self, surface):
        """Draw the slider"""
        # Draw label
        label_surface = self.font.render(self.label, True, self.text_color)
        surface.blit(label_surface, (self.x, self.y - 30))
        
        # Draw value
        if isinstance(self.current_val, float):
            value_text = f"{self.current_val:.1f}"
        else:
            value_text = str(int(self.current_val))
        value_surface = self.font.render(value_text, True, self.text_color)
        surface.blit(value_surface, (self.x + self.width + 20, self.y - 8))
        
        # Draw track
        pygame.draw.rect(surface, self.track_color, self.track_rect, border_radius=4)
        
        # Draw handle
        handle_x = self.get_handle_x()
        handle_color = self.handle_hover_color if (self.hovered or self.dragging) else self.handle_color
        pygame.draw.circle(surface, handle_color, (handle_x, self.y + 4), self.handle_radius)
        pygame.draw.circle(surface, (255, 255, 255), (handle_x, self.y + 4), self.handle_radius, 2)


class Toggle:
    """A toggle switch for boolean values"""
    
    def __init__(self, x, y, label, value, font):
        self.x = x
        self.y = y
        self.label = label
        self.value = value
        self.font = font
        
        self.width = 60
        self.height = 30
        self.rect = pygame.Rect(x, y, self.width, self.height)
        self.hovered = False
        
        # Colors
        self.bg_on = (80, 180, 100)
        self.bg_off = (80, 80, 100)
        self.handle_color = (255, 255, 255)
        self.text_color = (255, 255, 255)
    
    def handle_event(self, event):
        """Handle mouse events"""
        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1 and self.hovered:
                self.value = not self.value
                return True
        return False
    
    def render(self, surface):
        """Draw the toggle"""
        # Draw label
        label_surface = self.font.render(self.label, True, self.text_color)
        surface.blit(label_surface, (self.x, self.y - 30))
        
        # Draw background
        bg_color = self.bg_on if self.value else self.bg_off
        pygame.draw.rect(surface, bg_color, self.rect, border_radius=15)
        
        # Draw handle
        handle_x = self.x + self.width - 18 if self.value else self.x + 18
        pygame.draw.circle(surface, self.handle_color, (handle_x, self.y + 15), 12)


class Dropdown:
    """A dropdown menu for selecting from options"""
    
    def __init__(self, x, y, width, label, options, current_index, font):
        self.x = x
        self.y = y
        self.width = width
        self.height = 40
        self.label = label
        self.options = options
        self.current_index = current_index
        self.font = font
        
        self.rect = pygame.Rect(x, y, width, self.height)
        self.expanded = False
        self.hovered = False
        self.hovered_option = -1
        
        # Colors
        self.bg_color = (40, 40, 50)
        self.bg_hover = (60, 60, 80)
        self.border_color = (100, 150, 200)
        self.text_color = (255, 255, 255)
    
    def handle_event(self, event):
        """Handle mouse events"""
        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(event.pos)
            
            if self.expanded:
                # Check which option is hovered
                self.hovered_option = -1
                for i in range(len(self.options)):
                    option_rect = pygame.Rect(self.x, self.y + self.height + i * self.height, 
                                             self.width, self.height)
                    if option_rect.collidepoint(event.pos):
                        self.hovered_option = i
                        break
        
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                if self.hovered:
                    self.expanded = not self.expanded
                    return True
                elif self.expanded and self.hovered_option >= 0:
                    self.current_index = self.hovered_option
                    self.expanded = False
                    return True
                else:
                    self.expanded = False
        
        return False
    
    def render(self, surface):
        """Draw the dropdown"""
        # Draw label
        label_surface = self.font.render(self.label, True, self.text_color)
        surface.blit(label_surface, (self.x, self.y - 30))
        
        # Draw main box
        bg_color = self.bg_hover if self.hovered else self.bg_color
        pygame.draw.rect(surface, bg_color, self.rect)
        pygame.draw.rect(surface, self.border_color, self.rect, 2)
        
        # Draw current selection
        current_text = self.font.render(self.options[self.current_index], True, self.text_color)
        text_rect = current_text.get_rect(midleft=(self.x + 10, self.y + self.height // 2))
        surface.blit(current_text, text_rect)
        
        # Draw arrow
        arrow = "▼" if not self.expanded else "▲"
        arrow_surface = self.font.render(arrow, True, self.text_color)
        arrow_rect = arrow_surface.get_rect(midright=(self.x + self.width - 10, self.y + self.height // 2))
        surface.blit(arrow_surface, arrow_rect)
        
        # Draw expanded options
        if self.expanded:
            for i, option in enumerate(self.options):
                option_rect = pygame.Rect(self.x, self.y + self.height + i * self.height, 
                                         self.width, self.height)
                option_bg = self.bg_hover if i == self.hovered_option else self.bg_color
                pygame.draw.rect(surface, option_bg, option_rect)
                pygame.draw.rect(surface, self.border_color, option_rect, 2)
                
                option_text = self.font.render(option, True, self.text_color)
                option_text_rect = option_text.get_rect(midleft=(self.x + 10, option_rect.centery))
                surface.blit(option_text, option_text_rect)


class Button:
    """A clickable button"""
    
    def __init__(self, x, y, width, height, text, font, callback=None):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.font = font
        self.callback = callback
        self.hovered = False
        self.color_normal = (40, 40, 50)
        self.color_hover = (60, 60, 80)
        self.color_text = (255, 255, 255)
        self.border_color = (100, 150, 200)
    
    def handle_event(self, event):
        """Handle mouse events"""
        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1 and self.hovered:
                if self.callback:
                    self.callback()
                return True
        return False
    
    def render(self, surface):
        """Draw the button"""
        color = self.color_hover if self.hovered else self.color_normal
        pygame.draw.rect(surface, color, self.rect)
        pygame.draw.rect(surface, self.border_color, self.rect, 2)
        
        text_surface = self.font.render(self.text, True, self.color_text)
        text_rect = text_surface.get_rect(center=self.rect.center)
        surface.blit(text_surface, text_rect)


class SettingsMenu:
    """Settings menu for configuring simulation parameters"""
    
    def __init__(self, screen, on_back, simulation_screen=None):
        self.screen = screen
        self.on_back = on_back
        self.simulation_screen = simulation_screen  # Reference to current simulation for save functionality
        self.width, self.height = screen.get_size()
        
        # Fonts - Modern tech style with reasonable sizes
        try:
            self.title_font = pygame.font.SysFont('consolas,monaco,courier new,monospace', 42, bold=True)
            self.section_font = pygame.font.SysFont('consolas,monaco,courier new,monospace', 28, bold=True)
            self.label_font = pygame.font.SysFont('consolas,monaco,courier new,monospace', 20)
            self.button_font = pygame.font.SysFont('consolas,monaco,courier new,monospace', 26, bold=True)
        except:
            self.title_font = pygame.font.Font(None, 42)
            self.section_font = pygame.font.Font(None, 28)
            self.label_font = pygame.font.Font(None, 20)
            self.button_font = pygame.font.Font(None, 26)
        
        # Colors
        self.bg_color = (20, 25, 35)
        self.title_color = (100, 180, 255)
        self.section_color = (180, 180, 200)
        
        # Load or create default settings
        self.settings = self.load_settings()
        
        # Organized layout with sections
        # Section cards layout: 2 columns, organized sections
        card_width = 550
        card_height = 0  # Will be calculated
        card_spacing = 30
        card_margin = 50
        start_y = 120
        
        # Calculate positions for section cards
        left_col = card_margin
        right_col = self.width - card_margin - card_width
        
        # Section 1: Simulation Settings (Left, Top)
        sim_y = start_y
        self.sim_sliders = [
            Slider(left_col + 20, sim_y + 60, card_width - 40, "Simulation Speed", 0.5, 5.0, 
                   self.settings.get("sim_speed", 1.0), self.label_font),
            Slider(left_col + 20, sim_y + 120, card_width - 40, "Traffic Density", 1, 10, 
                   self.settings.get("traffic_density", 5), self.label_font),
            Slider(left_col + 20, sim_y + 180, card_width - 40, "Aircraft Spawn Rate", 1, 20, 
                   self.settings.get("spawn_rate", 10), self.label_font),
        ]
        self.sim_dropdown = Dropdown(left_col + 20, sim_y + 240, card_width - 40, "Difficulty",
                                     ["Easy", "Normal", "Hard", "Realistic"], 
                                     self.settings.get("difficulty", 1), self.label_font)
        
        # Section 2: Display Settings (Right, Top)
        display_y = start_y
        self.display_toggles = [
            Toggle(right_col + 20, display_y + 60, "Show Aircraft Labels", 
                   self.settings.get("show_labels", True), self.label_font),
            Toggle(right_col + 20, display_y + 110, "Show Taxiway Names", 
                   self.settings.get("show_taxiways", True), self.label_font),
        ]
        self.display_slider = Slider(right_col + 20, display_y + 180, card_width - 40, "Leader Line Length", 30, 120, 
                                     self.settings.get("leader_line_length", 60), self.label_font)
        
        # Section 3: Audio Settings (Left, Middle)
        audio_y = sim_y + 320
        self.audio_toggles = [
            Toggle(left_col + 20, audio_y + 60, "Radio Audio Effects", 
                   self.settings.get("radio_audio", True), self.label_font),
            Toggle(left_col + 20, audio_y + 110, "Enable TTS", 
                   self.settings.get("enable_tts", True), self.label_font),
            Toggle(left_col + 20, audio_y + 160, "Enable Radio Static", 
                   self.settings.get("enable_radio_static", True), self.label_font),
            Toggle(left_col + 20, audio_y + 210, "Realistic Radio", 
                   self.settings.get("realistic_radio", True), self.label_font),
        ]
        
        # Section 4: Gameplay Settings (Right, Middle)
        gameplay_y = display_y + 320
        self.gameplay_toggle = Toggle(right_col + 20, gameplay_y + 60, "Auto-Pause on Conflict", 
                                      self.settings.get("auto_pause", True), self.label_font)
        self.gameplay_dropdowns = [
            Dropdown(right_col + 20, gameplay_y + 120, card_width - 40, "Weather",
                    ["Clear", "Cloudy", "Rain", "Snow", "Random"], 
                    self.settings.get("weather", 0), self.label_font),
            Dropdown(right_col + 20, gameplay_y + 180, card_width - 40, "Daytime",
                    ["Dawn", "Day", "Dusk", "Night", "Random"], 
                    self.settings.get("time_settings", 1), self.label_font),
        ]
        
        # Store section rectangles for rendering
        self.sections = [
            {'name': 'Simulation', 'rect': pygame.Rect(left_col, sim_y, card_width, 300), 'color': (30, 40, 55)},
            {'name': 'Display', 'rect': pygame.Rect(right_col, display_y, card_width, 300), 'color': (30, 40, 55)},
            {'name': 'Audio', 'rect': pygame.Rect(left_col, audio_y, card_width, 280), 'color': (30, 40, 55)},
            {'name': 'Gameplay', 'rect': pygame.Rect(right_col, gameplay_y, card_width, 260), 'color': (30, 40, 55)},
        ]
        
        # Combine all UI elements for event handling
        self.sliders = self.sim_sliders + [self.display_slider]
        self.toggles = self.display_toggles + self.audio_toggles + [self.gameplay_toggle]
        self.dropdowns = [self.sim_dropdown] + self.gameplay_dropdowns
        
        # Buttons
        button_y = self.height - 100
        button_width = 200
        button_height = 50
        button_spacing = 10
        
        # Calculate button positions
        total_buttons = 3 if self.simulation_screen else 2
        total_width = (button_width * total_buttons) + (button_spacing * (total_buttons - 1))
        start_x = (self.width - total_width) // 2
        
        self.buttons = []
        
        # Add Save Simulation button if simulation screen is available
        if self.simulation_screen:
            self.buttons.append(
                Button(start_x, button_y, button_width, button_height,
                       "Save Sim", self.button_font, self.save_simulation)
            )
            start_x += button_width + button_spacing
        
        # Save and Back buttons
        self.buttons.append(
            Button(start_x, button_y, button_width, button_height,
                   "Save", self.button_font, self.save_and_back)
        )
        start_x += button_width + button_spacing
        
        self.buttons.append(
            Button(start_x, button_y, button_width, button_height,
                   "Back", self.button_font, self.on_back)
        )
    
    def load_settings(self):
        """Load settings from file or return defaults"""
        settings_file = "settings.json"
        if os.path.exists(settings_file):
            try:
                with open(settings_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        
        # Default settings
        return {
            "sim_speed": 1.0,
            "traffic_density": 5,
            "spawn_rate": 10,
            "show_labels": True,
            "show_taxiways": True,
            "realistic_radio": True,
            "radio_audio": True,
            "enable_tts": True,
            "enable_radio_static": True,
            "auto_pause": True,
            "difficulty": 1,
            "weather": 0,
            "time_settings": "zulu",
        }
    
    def save_settings(self):
        """Save current settings to file"""
        # Simulation settings
        self.settings["sim_speed"] = self.sim_sliders[0].current_val
        self.settings["traffic_density"] = int(self.sim_sliders[1].current_val)
        self.settings["spawn_rate"] = int(self.sim_sliders[2].current_val)
        self.settings["difficulty"] = self.sim_dropdown.current_index
        
        # Display settings
        self.settings["show_labels"] = self.display_toggles[0].value
        self.settings["show_taxiways"] = self.display_toggles[1].value
        self.settings["leader_line_length"] = int(self.display_slider.current_val)
        
        # Audio settings
        self.settings["radio_audio"] = self.audio_toggles[0].value
        self.settings["enable_tts"] = self.audio_toggles[1].value
        self.settings["enable_radio_static"] = self.audio_toggles[2].value
        self.settings["realistic_radio"] = self.audio_toggles[3].value
        
        # Gameplay settings
        self.settings["auto_pause"] = self.gameplay_toggle.value
        self.settings["weather"] = self.gameplay_dropdowns[0].current_index
        self.settings["time_settings"] = self.gameplay_dropdowns[1].current_index
        
        try:
            with open("settings.json", 'w') as f:
                json.dump(self.settings, f, indent=2)
            print("Settings saved successfully!")
        except Exception as e:
            print(f"Error saving settings: {e}")
    
    def save_simulation(self):
        """Manually save the current simulation state"""
        if self.simulation_screen:
            success = self.simulation_screen.save_simulation()
            if success:
                # Show success feedback (could add a toast notification here)
                print("✓ Simulation saved successfully from settings")
            else:
                print("✗ Failed to save simulation")
        else:
            print("No simulation available to save")
    
    def save_and_back(self):
        """Save settings and return to main menu"""
        self.save_settings()
        self.on_back()
    
    def handle_event(self, event):
        """Handle input events"""
        for slider in self.sliders:
            slider.handle_event(event)
        
        for toggle in self.toggles:
            toggle.handle_event(event)
        
        for dropdown in self.dropdowns:
            dropdown.handle_event(event)
        
        for button in self.buttons:
            button.handle_event(event)
    
    def update(self, dt):
        """Update settings state"""
        pass
    
    def handle_resize(self, new_size):
        """Handle window resize events"""
        self.width, self.height = new_size
        
        # Recalculate layout positions
        card_width = 550
        card_spacing = 30
        card_margin = 50
        start_y = 120
        
        left_col = card_margin
        right_col = self.width - card_margin - card_width
        
        # Update section rectangles
        sim_y = start_y
        display_y = start_y
        audio_y = start_y + 320
        gameplay_y = start_y + 320
        
        self.sections = [
            {'name': 'Simulation', 'rect': pygame.Rect(left_col, sim_y, card_width, 300), 'color': (30, 40, 55)},
            {'name': 'Display', 'rect': pygame.Rect(right_col, display_y, card_width, 300), 'color': (30, 40, 55)},
            {'name': 'Audio', 'rect': pygame.Rect(left_col, audio_y, card_width, 280), 'color': (30, 40, 55)},
            {'name': 'Gameplay', 'rect': pygame.Rect(right_col, gameplay_y, card_width, 260), 'color': (30, 40, 55)},
        ]
        
        # Update slider positions
        if hasattr(self, 'sim_sliders'):
            self.sim_sliders[0].rect.x = left_col + 20
            self.sim_sliders[0].rect.y = sim_y + 60
            self.sim_sliders[1].rect.x = left_col + 20
            self.sim_sliders[1].rect.y = sim_y + 120
            self.sim_sliders[2].rect.x = left_col + 20
            self.sim_sliders[2].rect.y = sim_y + 180
        
        if hasattr(self, 'display_sliders'):
            self.display_sliders[0].rect.x = right_col + 20
            self.display_sliders[0].rect.y = display_y + 60
            self.display_sliders[1].rect.x = right_col + 20
            self.display_sliders[1].rect.y = display_y + 120
            self.display_sliders[2].rect.x = right_col + 20
            self.display_sliders[2].rect.y = display_y + 180
        
        # Update toggle position
        if hasattr(self, 'gameplay_toggle'):
            self.gameplay_toggle.rect.x = right_col + 20
            self.gameplay_toggle.rect.y = gameplay_y + 60
        
        # Update dropdown positions
        if hasattr(self, 'gameplay_dropdowns'):
            self.gameplay_dropdowns[0].rect.x = right_col + 20
            self.gameplay_dropdowns[0].rect.y = gameplay_y + 120
            self.gameplay_dropdowns[1].rect.x = right_col + 20
            self.gameplay_dropdowns[1].rect.y = gameplay_y + 180
        
        # Update button positions
        button_width = 200
        button_height = 50
        button_y = self.height - 80
        
        if hasattr(self, 'buttons'):
            self.buttons[0].rect.x = (self.width - button_width - 20) // 2
            self.buttons[0].rect.y = button_y
            self.buttons[1].rect.x = (self.width + button_width + 20) // 2
            self.buttons[1].rect.y = button_y

    def render(self):
        """Render the settings menu"""
        # Clear screen
        self.screen.fill(self.bg_color)
        
        # Draw title
        title_text = self.title_font.render("Settings", True, self.title_color)
        title_rect = title_text.get_rect(center=(self.width // 2, 60))
        self.screen.blit(title_text, title_rect)
        
        # Draw section cards with headers
        for section in self.sections:
            # Draw section card background
            card_rect = section['rect']
            pygame.draw.rect(self.screen, section['color'], card_rect, border_radius=8)
            pygame.draw.rect(self.screen, (60, 80, 100), card_rect, 2, border_radius=8)
            
            # Draw section title
            section_title = self.section_font.render(section['name'], True, self.section_color)
            self.screen.blit(section_title, (card_rect.x + 20, card_rect.y + 15))
            
            # Draw subtle divider line
            divider_y = card_rect.y + 50
            pygame.draw.line(self.screen, (60, 70, 85), 
                           (card_rect.x + 15, divider_y), 
                           (card_rect.right - 15, divider_y), 2)
        
        # Draw all UI elements (they're positioned relative to their sections)
        for slider in self.sliders:
            slider.render(self.screen)
        
        for toggle in self.toggles:
            toggle.render(self.screen)
        
        for dropdown in self.dropdowns:
            dropdown.render(self.screen)
        
        # Draw action buttons at bottom
        for button in self.buttons:
            button.render(self.screen)
