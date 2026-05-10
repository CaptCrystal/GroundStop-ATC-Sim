"""
Radio Communications Panel
Displays ground and tower frequencies with transmission log
Includes coordination tab for runway coordination
Clean, minimal design matching weather panel style
"""
import pygame
from datetime import datetime
from typing import List, Dict, Optional


class RadioPanel:
    """Radio communications panel for ground-tower coordination"""
    
    def __init__(self, width, height, airport_code, scenario_manager):
        self.width = width
        self.height = height
        self.airport_code = airport_code
        
        # Panel state
        self.is_open = False
        self.panel_width = 320
        self.panel_height = 450
        
        # Radio frequencies
        airport = scenario_manager.get_airport_by_code(airport_code)
        self.ground_freq = airport.ground_freq if airport else ""
        self.tower_freq = airport.tower_freq if airport else ""
        
        # Communication log
        self.transmissions = []
        self.max_transmissions = 50
        
        # Scroll offset for transmission log
        self.scroll_offset = 0
        
        # References
        self.aircraft_manager = None
        self.tower_controller = None
        
        # Available runways
        self.available_runways = []
        
        # UI state
        self.active_frequency = "ground"
        self.active_tab = "radio"  # "radio" or "coordination"
        
        # Coordination state
        self.selected_aircraft = None
        self.pending_crossings = []  # List of pending runway crossing requests
        
        # Cached geometry
        self.panel_rect = pygame.Rect(0, 0, self.panel_width, self.panel_height)
        self.interactive_regions: Dict[str, list] = {}
        
    def set_available_runways(self, runways: list):
        """Set the list of available runways"""
        self.available_runways = runways
        
    def set_frequency(self, freq_type: str, frequency: str):
        """Set the ground or tower frequency"""
        if freq_type == 'ground':
            self.ground_freq = frequency
        elif freq_type == 'tower':
            self.tower_freq = frequency
            
    def get_active_frequency(self) -> str:
        """Get the currently active frequency"""
        return self.ground_freq if self.active_frequency == 'ground' else self.tower_freq
        
    def add_transmission(self, frequency: str, from_callsign: str, message: str, is_atc: bool = False):
        """Add a transmission to the log"""
        transmission = {
            'time': datetime.now().strftime("%H:%M:%S"),
            'freq': frequency,
            'from': from_callsign,
            'message': message,
            'type': 'atc' if is_atc else 'aircraft'
        }
        
        self.transmissions.append(transmission)
        
        if len(self.transmissions) > self.max_transmissions:
            self.transmissions.pop(0)
        
        self.scroll_offset = 0
    
    def handle_click(self, pos, panel_x, panel_y):
        """Handle mouse clicks on the radio panel"""
        x, y = pos
        
        if self.panel_rect.topleft != (panel_x, panel_y):
            self.panel_rect = pygame.Rect(panel_x, panel_y, self.panel_width, self.panel_height)
        
        if not self.panel_rect.collidepoint(x, y):
            return False
        
        panel_relative_x = x - panel_x
        panel_relative_y = y - panel_y
        
        # Handle tab switching
        for tab_info in self.interactive_regions.get('tabs', []):
            if tab_info['rect'].collidepoint(panel_relative_x, panel_relative_y):
                self.active_tab = tab_info['tab']
                self.selected_aircraft = None  # Reset selection on tab switch
                return True
        
        # Handle frequency switching buttons (radio tab)
        for button_info in self.interactive_regions.get('frequency_buttons', []):
            if button_info['rect'].collidepoint(panel_relative_x, panel_relative_y):
                self.active_frequency = button_info['frequency']
                return True
        
        # Handle aircraft selection (coordination tab)
        for ac_info in self.interactive_regions.get('aircraft_buttons', []):
            if ac_info['rect'].collidepoint(panel_relative_x, panel_relative_y):
                self.selected_aircraft = ac_info['aircraft']
                return True
        
        # Handle runway crossing buttons (coordination tab)
        for rwy_info in self.interactive_regions.get('runway_buttons', []):
            if rwy_info['rect'].collidepoint(panel_relative_x, panel_relative_y):
                if self.selected_aircraft:
                    self._approve_crossing(self.selected_aircraft, rwy_info['runway'])
                    self.selected_aircraft = None
                return True
        
        return True
    
    def _approve_crossing(self, aircraft, runway):
        """Approve runway crossing for an aircraft"""
        if not hasattr(aircraft, 'cleared_runways'):
            aircraft.cleared_runways = []
        if runway not in aircraft.cleared_runways:
            aircraft.cleared_runways.append(runway)
        
        # Clear hold short if applicable
        if hasattr(aircraft, 'hold_short') and aircraft.hold_short == runway:
            aircraft.hold_short = None
        
        # Resume taxi if holding
        if hasattr(aircraft, 'state') and hasattr(aircraft, 'STATE_HOLDING'):
            if aircraft.state == aircraft.STATE_HOLDING:
                if hasattr(aircraft, 'cleared_to_taxi') and aircraft.cleared_to_taxi:
                    aircraft.state = aircraft.STATE_TAXI
        
        # Log the clearance
        callsign = aircraft.get_callsign() if hasattr(aircraft, 'get_callsign') else str(aircraft)
        self.add_transmission(self.ground_freq, "Ground", f"{callsign}, cross runway {runway}", is_atc=True)
    
    def handle_scroll(self, direction: int):
        """Handle scroll wheel for transmission log"""
        max_offset = max(0, len(self.transmissions) * 28 - getattr(self, "log_view_height", 200))
        self.scroll_offset = self.scroll_offset + (direction * 28)
        self.scroll_offset = max(0, min(self.scroll_offset, max_offset))
    
    def render(self, surface, info_font, small_font):
        """Render the radio panel"""
        if not self.is_open:
            return
        
        # Panel position (right side of screen)
        panel_x = self.width - self.panel_width - 10
        panel_y = 45
        
        # Update panel rect
        self.panel_rect = pygame.Rect(panel_x, panel_y, self.panel_width, self.panel_height)
        self.interactive_regions = {
            'tabs': [],
            'frequency_buttons': [],
            'aircraft_buttons': [],
            'runway_buttons': []
        }
        
        # Professional dark background
        panel_surface = pygame.Surface((self.panel_width, self.panel_height))
        panel_surface.set_alpha(252)
        panel_surface.fill((12, 12, 14))
        
        # Subtle border
        pygame.draw.rect(panel_surface, (45, 45, 50), (0, 0, self.panel_width, self.panel_height), 1)
        
        # Margins
        margin = 12
        content_width = self.panel_width - (margin * 2)
        
        # Title - brighter text
        title_text = info_font.render(f"{self.airport_code} - Radio", True, (220, 240, 255))
        panel_surface.blit(title_text, (margin, 10))
        
        y_offset = 38
        
        # === TAB BAR ===
        tab_width = (content_width - 6) // 2
        tab_height = 28
        
        # Radio tab - professional styling
        radio_tab_rect = pygame.Rect(margin, y_offset, tab_width, tab_height)
        if self.active_tab == "radio":
            pygame.draw.rect(panel_surface, (30, 30, 35), radio_tab_rect, border_radius=3)
            radio_color = (180, 180, 180)
        else:
            pygame.draw.rect(panel_surface, (20, 20, 22), radio_tab_rect, border_radius=3)
            radio_color = (90, 90, 90)
        
        radio_tab_text = small_font.render("Radio", True, radio_color)
        panel_surface.blit(radio_tab_text, (radio_tab_rect.centerx - radio_tab_text.get_width() // 2, 
                                            radio_tab_rect.centery - radio_tab_text.get_height() // 2))
        self.interactive_regions['tabs'].append({'rect': radio_tab_rect, 'tab': 'radio'})
        
        # Coordination tab - professional styling
        coord_tab_rect = pygame.Rect(margin + tab_width + 6, y_offset, tab_width, tab_height)
        if self.active_tab == "coordination":
            pygame.draw.rect(panel_surface, (30, 30, 35), coord_tab_rect, border_radius=3)
            coord_color = (180, 180, 180)
        else:
            pygame.draw.rect(panel_surface, (20, 20, 22), coord_tab_rect, border_radius=3)
            coord_color = (90, 90, 90)
        
        coord_tab_text = small_font.render("Coordination", True, coord_color)
        panel_surface.blit(coord_tab_text, (coord_tab_rect.centerx - coord_tab_text.get_width() // 2,
                                            coord_tab_rect.centery - coord_tab_text.get_height() // 2))
        self.interactive_regions['tabs'].append({'rect': coord_tab_rect, 'tab': 'coordination'})
        
        y_offset += tab_height + 12
        
        # Separator below tabs - modern subtle line
        pygame.draw.line(panel_surface, (45, 55, 70), (margin, y_offset - 6), (self.panel_width - margin, y_offset - 6), 1)
        
        # Render active tab content
        if self.active_tab == "radio":
            self._render_radio_tab(panel_surface, info_font, small_font, margin, content_width, y_offset)
        else:
            self._render_coordination_tab(panel_surface, info_font, small_font, margin, content_width, y_offset)
        
        # Blit to screen
        surface.blit(panel_surface, (panel_x, panel_y))
    
    def _render_radio_tab(self, panel_surface, info_font, small_font, margin, content_width, y_offset):
        """Render the radio tab content"""
        # === FREQUENCY SECTION ===
        freq_label = small_font.render("Frequency:", True, (160, 200, 240))
        panel_surface.blit(freq_label, (margin, y_offset))
        y_offset += 22
        
        # Ground frequency button
        ground_rect = pygame.Rect(margin, y_offset, content_width, 32)
        ground_active = self.active_frequency == 'ground'
        
        if ground_active:
            pygame.draw.rect(panel_surface, (30, 45, 35), ground_rect, border_radius=3)
            pygame.draw.rect(panel_surface, (50, 80, 60), ground_rect, 1, border_radius=3)
        else:
            pygame.draw.rect(panel_surface, (20, 20, 22), ground_rect, border_radius=3)
            pygame.draw.rect(panel_surface, (35, 35, 40), ground_rect, 1, border_radius=3)
        
        ground_label = small_font.render("GND", True, (100, 100, 100))
        ground_freq = info_font.render(self.ground_freq, True, (120, 160, 120) if ground_active else (80, 100, 80))
        panel_surface.blit(ground_label, (margin + 10, y_offset + 8))
        panel_surface.blit(ground_freq, (margin + 60, y_offset + 6))
        
        self.interactive_regions['frequency_buttons'].append({
            'rect': ground_rect,
            'frequency': 'ground'
        })
        
        y_offset += 38
        
        # Tower frequency button
        tower_rect = pygame.Rect(margin, y_offset, content_width, 32)
        tower_active = self.active_frequency == 'tower'
        
        if tower_active:
            pygame.draw.rect(panel_surface, (30, 40, 55), tower_rect, border_radius=3)
            pygame.draw.rect(panel_surface, (50, 70, 95), tower_rect, 1, border_radius=3)
        else:
            pygame.draw.rect(panel_surface, (20, 20, 22), tower_rect, border_radius=3)
            pygame.draw.rect(panel_surface, (35, 35, 40), tower_rect, 1, border_radius=3)
        
        tower_label = small_font.render("TWR", True, (100, 100, 100))
        tower_freq = info_font.render(self.tower_freq, True, (100, 130, 160) if tower_active else (70, 90, 110))
        panel_surface.blit(tower_label, (margin + 10, y_offset + 8))
        panel_surface.blit(tower_freq, (margin + 60, y_offset + 6))
        
        self.interactive_regions['frequency_buttons'].append({
            'rect': tower_rect,
            'frequency': 'tower'
        })
        
        y_offset += 44
        
        # Separator - modern subtle line
        pygame.draw.line(panel_surface, (45, 55, 70), (margin, y_offset), (self.panel_width - margin, y_offset), 1)
        y_offset += 12
        
        # === TRANSMISSION LOG ===
        log_label = small_font.render("Transmissions:", True, (160, 200, 240))
        panel_surface.blit(log_label, (margin, y_offset))
        y_offset += 22
        
        # Log area
        log_height = self.panel_height - y_offset - margin
        log_rect = pygame.Rect(margin, y_offset, content_width, log_height)
        self.log_view_height = log_height
        
        pygame.draw.rect(panel_surface, (8, 8, 10), log_rect, border_radius=3)
        pygame.draw.rect(panel_surface, (30, 30, 35), log_rect, 1, border_radius=3)
        
        # Clip to log area
        panel_surface.set_clip(log_rect)
        
        # Filter transmissions by active frequency
        active_freq = self.get_active_frequency()
        filtered = [tx for tx in self.transmissions if tx['freq'] == active_freq]
        
        # Render transmissions (newest at bottom)
        line_height = 28
        y_pos = log_rect.bottom - 8 - self.scroll_offset
        
        for tx in reversed(filtered):
            if y_pos < log_rect.y - line_height:
                break
            if y_pos > log_rect.bottom:
                y_pos -= line_height
                continue
            
            # Time
            time_text = small_font.render(f"[{tx['time']}]", True, (100, 110, 130))
            panel_surface.blit(time_text, (log_rect.x + 6, y_pos - 22))
            
            # Message with color based on type
            color = (0, 224, 21) if tx['type'] == 'atc' else (100, 180, 255)
            msg_text = small_font.render(f"{tx['from']}: {tx['message'][:35]}", True, color)
            panel_surface.blit(msg_text, (log_rect.x + 6, y_pos - 10))
            
            y_pos -= line_height
        
        panel_surface.set_clip(None)
        
        # Scroll indicator
        if filtered:
            total_height = len(filtered) * line_height
            if total_height > log_height:
                visible_ratio = log_height / total_height
                bar_height = max(20, int(log_height * visible_ratio))
                scroll_range = total_height - log_height
                scroll_pos = self.scroll_offset / scroll_range if scroll_range > 0 else 0
                bar_y = log_rect.y + int((log_height - bar_height) * scroll_pos)
                
                bar_rect = pygame.Rect(log_rect.right - 5, bar_y, 3, bar_height)
                pygame.draw.rect(panel_surface, (50, 50, 55), bar_rect, border_radius=1)
    
    def _render_coordination_tab(self, panel_surface, info_font, small_font, margin, content_width, y_offset):
        """Render the coordination tab content"""
        # === RUNWAY CROSSING SECTION ===
        section_label = small_font.render("Runway Crossing:", True, (150, 200, 255))
        panel_surface.blit(section_label, (margin, y_offset))
        y_offset += 22
        
        # Instructions
        if self.selected_aircraft:
            callsign = self.selected_aircraft.get_callsign() if hasattr(self.selected_aircraft, 'get_callsign') else "Aircraft"
            hint = small_font.render(f"Select runway for {callsign}", True, (180, 200, 150))
        else:
            hint = small_font.render("Select aircraft, then runway", True, (120, 130, 150))
        panel_surface.blit(hint, (margin, y_offset))
        y_offset += 24
        
        # === TAXIING AIRCRAFT LIST ===
        aircraft_label = small_font.render("Taxiing Aircraft:", True, (150, 200, 255))
        panel_surface.blit(aircraft_label, (margin, y_offset))
        y_offset += 20
        
        # Get taxiing aircraft
        taxiing = []
        if self.aircraft_manager:
            for ac in self.aircraft_manager.aircraft:
                if hasattr(ac, 'state'):
                    if ac.state in ['taxi', 'TAXI', ac.STATE_TAXI if hasattr(ac, 'STATE_TAXI') else None,
                                    'holding', 'HOLDING', ac.STATE_HOLDING if hasattr(ac, 'STATE_HOLDING') else None]:
                        taxiing.append(ac)
        
        if taxiing:
            for i, ac in enumerate(taxiing[:6]):  # Max 6 aircraft
                ac_rect = pygame.Rect(margin, y_offset, content_width, 26)
                
                if ac == self.selected_aircraft:
                    pygame.draw.rect(panel_surface, (30, 40, 35), ac_rect, border_radius=3)
                    pygame.draw.rect(panel_surface, (50, 70, 55), ac_rect, 1, border_radius=3)
                    text_color = (150, 180, 150)
                else:
                    pygame.draw.rect(panel_surface, (20, 22, 25), ac_rect, border_radius=3)
                    pygame.draw.rect(panel_surface, (35, 38, 42), ac_rect, 1, border_radius=3)
                    text_color = (120, 120, 120)
                
                callsign = ac.get_callsign() if hasattr(ac, 'get_callsign') else str(ac)
                ac_text = small_font.render(callsign, True, text_color)
                panel_surface.blit(ac_text, (ac_rect.x + 10, ac_rect.centery - ac_text.get_height() // 2))
                
                self.interactive_regions['aircraft_buttons'].append({
                    'rect': ac_rect,
                    'aircraft': ac
                })
                
                y_offset += 30
        else:
            no_ac = small_font.render("No aircraft taxiing", True, (100, 100, 100))
            panel_surface.blit(no_ac, (margin, y_offset))
            y_offset += 24
        
        y_offset += 10
        
        # Separator - modern subtle line
        pygame.draw.line(panel_surface, (45, 55, 70), (margin, y_offset), (self.panel_width - margin, y_offset), 1)
        y_offset += 12
        
        # === RUNWAY BUTTONS ===
        runway_label = small_font.render("Cross Runway:", True, (150, 200, 255))
        panel_surface.blit(runway_label, (margin, y_offset))
        y_offset += 22
        
        if self.available_runways:
            # Parse runway pairs
            runways = []
            for rwy in self.available_runways:
                if '/' in str(rwy):
                    runways.extend(str(rwy).split('/'))
                else:
                    runways.append(str(rwy))
            
            # Remove duplicates while preserving order
            seen = set()
            unique_runways = []
            for r in runways:
                if r not in seen:
                    seen.add(r)
                    unique_runways.append(r)
            
            # Render runway buttons in a grid (2 columns)
            col_width = (content_width - 8) // 2
            for i, rwy in enumerate(unique_runways[:8]):  # Max 8 runways
                col = i % 2
                row = i // 2
                
                rwy_rect = pygame.Rect(margin + col * (col_width + 8), y_offset + row * 34, col_width, 28)
                
                # Highlight if aircraft is selected
                if self.selected_aircraft:
                    pygame.draw.rect(panel_surface, (30, 35, 45), rwy_rect, border_radius=3)
                    pygame.draw.rect(panel_surface, (50, 60, 75), rwy_rect, 1, border_radius=3)
                    text_color = (140, 150, 170)
                else:
                    pygame.draw.rect(panel_surface, (20, 22, 25), rwy_rect, border_radius=3)
                    pygame.draw.rect(panel_surface, (35, 38, 42), rwy_rect, 1, border_radius=3)
                    text_color = (70, 75, 85)
                
                rwy_text = small_font.render(f"RWY {rwy}", True, text_color)
                panel_surface.blit(rwy_text, (rwy_rect.centerx - rwy_text.get_width() // 2,
                                              rwy_rect.centery - rwy_text.get_height() // 2))
                
                self.interactive_regions['runway_buttons'].append({
                    'rect': rwy_rect,
                    'runway': rwy
                })
        else:
            no_rwy = small_font.render("No runways configured", True, (100, 100, 100))
            panel_surface.blit(no_rwy, (margin, y_offset))
