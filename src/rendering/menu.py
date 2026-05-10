"""
Main menu for GroundStop - Minimalist design
"""
import pygame
import os
import webbrowser
from src.core.simulation_save import SimulationSaveManager


class Button:
    """Simple flat button"""

    def __init__(self, x, y, width, height, text, font, callback=None):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.font = font
        self.callback = callback
        self.hovered = False

        # Simple colors
        self.color_bg = (30, 32, 36)
        self.color_hover = (45, 48, 54)
        self.color_text = (200, 200, 200)
        self.color_text_hover = (255, 255, 255)

    def handle_event(self, event):
        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1 and self.hovered and self.callback:
                self.callback()
                return True
        return False

    def update(self, dt):
        pass

    def render(self, surface):
        bg = self.color_hover if self.hovered else self.color_bg
        text_color = self.color_text_hover if self.hovered else self.color_text
        
        pygame.draw.rect(surface, bg, self.rect)
        
        text_surface = self.font.render(self.text, True, text_color)
        text_rect = text_surface.get_rect(center=self.rect.center)
        surface.blit(text_surface, text_rect)


class MainMenu:
    """Minimalist main menu"""

    def __init__(self, screen, app):
        self.screen = screen
        self.app = app
        self.width, self.height = screen.get_size()

        # Fonts
        custom_font_path = "data/fonts/asdeView_font.ttf"
        if os.path.exists(custom_font_path):
            self.title_font = pygame.font.Font(custom_font_path, 48)
            self.subtitle_font = pygame.font.Font(custom_font_path, 16)
            self.button_font = pygame.font.Font(custom_font_path, 18)
            self.small_font = pygame.font.Font(custom_font_path, 12)
        else:
            self.title_font = pygame.font.Font(None, 48)
            self.subtitle_font = pygame.font.Font(None, 16)
            self.button_font = pygame.font.Font(None, 18)
            self.small_font = pygame.font.Font(None, 12)

        # Colors
        self.bg_color = (18, 20, 24)
        self.title_color = (255, 255, 255)
        self.subtitle_color = (120, 120, 120)

        # Save manager
        self.save_manager = SimulationSaveManager()

        # Create buttons
        self._create_buttons()

    def _create_buttons(self):
        self.buttons = []
        button_width = 200
        button_height = 40
        button_x = (self.width - button_width) // 2
        start_y = self.height // 2
        spacing = 50

        idx = 0
        
        # Resume button if save exists
        if self.save_manager.has_saved_simulation():
            self.buttons.append(Button(button_x, start_y + spacing * idx, button_width, button_height,
                                       "Resume", self.button_font, self.continue_simulation))
            idx += 1

        # New Simulation
        self.buttons.append(Button(button_x, start_y + spacing * idx, button_width, button_height,
                                   "New Simulation", self.button_font, self.new_simulation))
        idx += 1

        # Settings
        self.buttons.append(Button(button_x, start_y + spacing * idx, button_width, button_height,
                                   "Settings", self.button_font, self.settings))
        idx += 1

        # Exit
        self.buttons.append(Button(button_x, start_y + spacing * idx, button_width, button_height,
                                   "Exit", self.button_font, self.exit_game))

    def continue_simulation(self):
        save_data = self.save_manager.load_simulation_state()
        if save_data:
            self.app.continue_simulation(save_data)

    def new_simulation(self):
        self.app.show_airport_menu()

    def settings(self):
        self.app.show_settings()

    def exit_game(self):
        pygame.event.post(pygame.event.Event(pygame.QUIT))

    def handle_event(self, event):
        for button in self.buttons:
            button.handle_event(event)

    def update(self, dt):
        for button in self.buttons:
            button.update(dt)

    def handle_resize(self, new_size):
        self.width, self.height = new_size
        self._create_buttons()

    def render(self):
        self.screen.fill(self.bg_color)

        center_x = self.width // 2

        # Title
        title = self.title_font.render("GroundStop", True, self.title_color)
        title_rect = title.get_rect(center=(center_x, self.height // 2 - 120))
        self.screen.blit(title, title_rect)

        # Subtitle
        subtitle = self.subtitle_font.render("Airport Ground Control Simulator", True, self.subtitle_color)
        subtitle_rect = subtitle.get_rect(center=(center_x, self.height // 2 - 80))
        self.screen.blit(subtitle, subtitle_rect)

        # Buttons
        for button in self.buttons:
            button.render(self.screen)

        # Version
        version = self.small_font.render("v0.1.0", True, (60, 60, 60))
        self.screen.blit(version, (10, self.height - 20))
