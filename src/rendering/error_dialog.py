"""
Stylish error dialog for crash handling
"""
import pygame
import traceback
from typing import Optional

# Try to import pyperclip, use fallback if not available
try:
    import pyperclip
    CLIPBOARD_AVAILABLE = True
except ImportError:
    CLIPBOARD_AVAILABLE = False


class ErrorDialog:
    """Modern error dialog with copy functionality"""
    
    def __init__(self, screen: pygame.Surface, error_message: str, traceback_text: str):
        self.screen = screen
        self.error_message = error_message
        self.traceback_text = traceback_text
        self.running = True
        
        # Colors - Modern dark theme
        self.bg_overlay = (0, 0, 0, 200)  # Semi-transparent black
        self.dialog_bg = (30, 30, 35)
        self.header_bg = (200, 50, 50)  # Red header
        self.button_bg = (60, 60, 70)
        self.button_hover = (80, 80, 90)
        self.button_copy_bg = (50, 120, 200)
        self.button_copy_hover = (70, 140, 220)
        self.text_color = (240, 240, 240)
        self.error_text_color = (255, 200, 200)
        self.border_color = (100, 100, 110)
        
        # Fonts
        try:
            self.title_font = pygame.font.Font(None, 48)
            self.message_font = pygame.font.Font(None, 28)
            self.traceback_font = pygame.font.Font(None, 20)
            self.button_font = pygame.font.Font(None, 32)
        except:
            self.title_font = pygame.font.SysFont('Arial', 48, bold=True)
            self.message_font = pygame.font.SysFont('Arial', 28)
            self.traceback_font = pygame.font.SysFont('Courier New', 20)
            self.button_font = pygame.font.SysFont('Arial', 32, bold=True)
        
        # Dialog dimensions
        screen_width, screen_height = screen.get_size()
        self.dialog_width = min(900, screen_width - 100)
        self.dialog_height = min(700, screen_height - 100)
        self.dialog_x = (screen_width - self.dialog_width) // 2
        self.dialog_y = (screen_height - self.dialog_height) // 2
        
        # Button dimensions
        self.button_width = 200
        self.button_height = 60
        self.button_spacing = 20
        
        # OK button (right)
        self.ok_button = pygame.Rect(
            self.dialog_x + self.dialog_width - self.button_width - 30,
            self.dialog_y + self.dialog_height - self.button_height - 30,
            self.button_width,
            self.button_height
        )
        
        # Copy button (left of OK)
        self.copy_button = pygame.Rect(
            self.ok_button.x - self.button_width - self.button_spacing,
            self.ok_button.y,
            self.button_width,
            self.button_height
        )
        
        self.ok_hovered = False
        self.copy_hovered = False
        self.copied = False
        
    def handle_event(self, event: pygame.event.Event) -> bool:
        """Handle events. Returns True if dialog should close."""
        if event.type == pygame.MOUSEMOTION:
            mouse_pos = event.pos
            self.ok_hovered = self.ok_button.collidepoint(mouse_pos)
            self.copy_hovered = self.copy_button.collidepoint(mouse_pos)
            
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:  # Left click
                mouse_pos = event.pos
                
                if self.ok_button.collidepoint(mouse_pos):
                    return True  # Close dialog
                    
                elif self.copy_button.collidepoint(mouse_pos):
                    # Copy error to clipboard
                    full_error = f"{self.error_message}\n\n{self.traceback_text}"
                    if CLIPBOARD_AVAILABLE:
                        try:
                            pyperclip.copy(full_error)
                            self.copied = True
                        except:
                            self.copied = False
                    else:
                        # Fallback: print to console
                        print("\n" + "="*60)
                        print("ERROR DETAILS (pyperclip not available):")
                        print("="*60)
                        print(full_error)
                        print("="*60 + "\n")
                        self.copied = True
                        
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE or event.key == pygame.K_RETURN:
                return True  # Close on ESC or Enter
                
        return False
    
    def draw(self):
        """Draw the error dialog"""
        # Semi-transparent overlay
        overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        overlay.fill(self.bg_overlay)
        self.screen.blit(overlay, (0, 0))
        
        # Main dialog background
        dialog_rect = pygame.Rect(self.dialog_x, self.dialog_y, self.dialog_width, self.dialog_height)
        pygame.draw.rect(self.screen, self.dialog_bg, dialog_rect)
        pygame.draw.rect(self.screen, self.border_color, dialog_rect, 2)
        
        # Header with error icon
        header_height = 80
        header_rect = pygame.Rect(self.dialog_x, self.dialog_y, self.dialog_width, header_height)
        pygame.draw.rect(self.screen, self.header_bg, header_rect)
        
        # Error icon (⚠)
        icon_text = self.title_font.render("⚠", True, (255, 255, 255))
        icon_x = self.dialog_x + 30
        icon_y = self.dialog_y + (header_height - icon_text.get_height()) // 2
        self.screen.blit(icon_text, (icon_x, icon_y))
        
        # Title
        title_text = self.title_font.render("Application Error", True, (255, 255, 255))
        title_x = icon_x + icon_text.get_width() + 20
        title_y = self.dialog_y + (header_height - title_text.get_height()) // 2
        self.screen.blit(title_text, (title_x, title_y))
        
        # Error message
        message_y = self.dialog_y + header_height + 30
        message_text = self.message_font.render(self.error_message, True, self.error_text_color)
        self.screen.blit(message_text, (self.dialog_x + 30, message_y))
        
        # Traceback box
        traceback_y = message_y + 60
        traceback_height = self.dialog_height - header_height - 200
        traceback_rect = pygame.Rect(
            self.dialog_x + 20,
            traceback_y,
            self.dialog_width - 40,
            traceback_height
        )
        pygame.draw.rect(self.screen, (20, 20, 25), traceback_rect)
        pygame.draw.rect(self.screen, self.border_color, traceback_rect, 1)
        
        # Render traceback (with scrolling if needed)
        lines = self.traceback_text.split('\n')
        line_height = 22
        y_offset = traceback_y + 10
        max_lines = (traceback_height - 20) // line_height
        
        # Show last lines if too many
        display_lines = lines[-max_lines:] if len(lines) > max_lines else lines
        
        for line in display_lines:
            if y_offset + line_height > traceback_y + traceback_height - 10:
                break
            # Truncate long lines
            if len(line) > 100:
                line = line[:97] + "..."
            line_surface = self.traceback_font.render(line, True, self.text_color)
            self.screen.blit(line_surface, (self.dialog_x + 30, y_offset))
            y_offset += line_height
        
        # Copy button
        copy_color = self.button_copy_hover if self.copy_hovered else self.button_copy_bg
        pygame.draw.rect(self.screen, copy_color, self.copy_button, border_radius=8)
        pygame.draw.rect(self.screen, self.border_color, self.copy_button, 2, border_radius=8)
        
        copy_text = "Copied!" if self.copied else "Copy Error"
        copy_surface = self.button_font.render(copy_text, True, self.text_color)
        copy_text_x = self.copy_button.x + (self.copy_button.width - copy_surface.get_width()) // 2
        copy_text_y = self.copy_button.y + (self.copy_button.height - copy_surface.get_height()) // 2
        self.screen.blit(copy_surface, (copy_text_x, copy_text_y))
        
        # OK button
        ok_color = self.button_hover if self.ok_hovered else self.button_bg
        pygame.draw.rect(self.screen, ok_color, self.ok_button, border_radius=8)
        pygame.draw.rect(self.screen, self.border_color, self.ok_button, 2, border_radius=8)
        
        ok_surface = self.button_font.render("OK", True, self.text_color)
        ok_text_x = self.ok_button.x + (self.ok_button.width - ok_surface.get_width()) // 2
        ok_text_y = self.ok_button.y + (self.ok_button.height - ok_surface.get_height()) // 2
        self.screen.blit(ok_surface, (ok_text_x, ok_text_y))
        
        pygame.display.flip()
    
    def run(self):
        """Run the error dialog event loop"""
        clock = pygame.time.Clock()
        
        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    
                if self.handle_event(event):
                    self.running = False
            
            self.draw()
            clock.tick(60)


def show_error_dialog(screen: pygame.Surface, exception: Exception):
    """Show error dialog for an exception"""
    error_message = f"{type(exception).__name__}: {str(exception)}"
    traceback_text = traceback.format_exc()
    
    dialog = ErrorDialog(screen, error_message, traceback_text)
    dialog.run()
