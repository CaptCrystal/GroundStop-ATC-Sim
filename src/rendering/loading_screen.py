"""
Stylish loading screen for AsdeSim
Shows progress during scenario initialization
"""
import pygame
import math


class LoadingScreen:
    """Modern loading screen with progress tracking"""
    
    def __init__(self, screen):
        self.screen = screen
        self.width, self.height = screen.get_size()
        
        # Load custom font
        custom_font_path = "data/fonts/asdeView_font.ttf"
        try:
            if pygame.font.get_init():
                self.title_font = pygame.font.Font(custom_font_path, 48)
                self.subtitle_font = pygame.font.Font(custom_font_path, 24)
                self.status_font = pygame.font.Font(custom_font_path, 18)
            else:
                pygame.font.init()
                self.title_font = pygame.font.Font(custom_font_path, 48)
                self.subtitle_font = pygame.font.Font(custom_font_path, 24)
                self.status_font = pygame.font.Font(custom_font_path, 18)
        except:
            self.title_font = pygame.font.Font(None, 48)
            self.subtitle_font = pygame.font.Font(None, 24)
            self.status_font = pygame.font.Font(None, 18)
        
        # Colors
        self.bg_color = (10, 15, 25)  # Dark blue-black
        self.accent_color = (0, 224, 21)  # Bright green (ASDE green)
        self.secondary_color = (0, 150, 200)  # Blue
        self.text_color = (220, 230, 240)
        self.dim_text_color = (120, 130, 140)
        
        # Progress tracking
        self.progress = 0.0  # 0.0 to 1.0
        self.status_text = "Initializing..."
        self.substatus_text = ""
        
        # Animation
        self.animation_time = 0
        self.spinner_angle = 0
        
    def update(self, progress, status_text, substatus_text=""):
        """Update loading progress and status
        
        Args:
            progress: Float from 0.0 to 1.0
            status_text: Main status message
            substatus_text: Optional detailed status
        """
        self.progress = max(0.0, min(1.0, progress))
        self.status_text = status_text
        self.substatus_text = substatus_text
        
    def handle_resize(self, new_size):
        """Handle window resize events"""
        self.width, self.height = new_size

    def render(self):
        """Render the loading screen"""
        # Clear screen with dark background
        self.screen.fill(self.bg_color)
        
        # Update animation
        self.spinner_angle = (self.spinner_angle + 5) % 360
        
        # Center position
        center_x = self.width // 2
        center_y = self.height // 2
        
        # Draw title
        title_text = self.title_font.render("GroundStop", True, self.text_color)
        title_rect = title_text.get_rect(center=(center_x, center_y - 80))
        self.screen.blit(title_text, title_rect)
        
        # Draw progress bar
        bar_width = 400
        bar_height = 6
        bar_x = center_x - bar_width // 2
        bar_y = center_y
        
        # Progress bar background
        bg_rect = pygame.Rect(bar_x, bar_y, bar_width, bar_height)
        pygame.draw.rect(self.screen, (40, 45, 55), bg_rect, border_radius=3)
        
        # Progress bar fill
        if self.progress > 0:
            fill_width = int(bar_width * self.progress)
            fill_rect = pygame.Rect(bar_x, bar_y, fill_width, bar_height)
            pygame.draw.rect(self.screen, self.accent_color, fill_rect, border_radius=3)
        
        # Status text
        status_text = self.status_font.render(self.status_text, True, self.dim_text_color)
        status_rect = status_text.get_rect(center=(center_x, bar_y + 35))
        self.screen.blit(status_text, status_rect)
        
        # Update display
        pygame.display.flip()
        
        # Process events to keep window responsive
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                import sys
                sys.exit()
