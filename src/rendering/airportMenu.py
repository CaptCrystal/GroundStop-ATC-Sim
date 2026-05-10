"""
Airport selection menu - Minimalist design with diagram
"""
import pygame
import os
from src.core.scenario_manager import get_scenario_manager


class AirportCard:
    """Simple airport selection card"""
    
    def __init__(self, x, y, width, height, scenario, font, small_font):
        self.rect = pygame.Rect(x, y, width, height)
        self.scenario = scenario
        self.font = font
        self.small_font = small_font
        self.hovered = False
        self.selected = False
        
        self.bg_normal = (25, 27, 32)
        self.bg_hover = (35, 38, 45)
        self.bg_selected = (40, 60, 80)
        self.text_color = (200, 200, 200)
        self.text_dim = (100, 100, 100)
    
    def handle_event(self, event):
        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1 and self.hovered:
                return True
        return False
    
    def render(self, surface):
        if self.selected:
            bg = self.bg_selected
        elif self.hovered:
            bg = self.bg_hover
        else:
            bg = self.bg_normal
        
        pygame.draw.rect(surface, bg, self.rect)
        
        code = self.font.render(self.scenario.airport_code, True, self.text_color)
        surface.blit(code, (self.rect.x + 18, self.rect.y + 12))
        
        name = self.small_font.render(self.scenario.airport_name, True, self.text_dim)
        surface.blit(name, (self.rect.x + 18, self.rect.y + 45))


class Button:
    """Simple flat button"""
    
    def __init__(self, x, y, width, height, text, font, callback=None):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.font = font
        self.callback = callback
        self.hovered = False
        self.enabled = True
        
        self.color_bg = (30, 32, 36)
        self.color_hover = (45, 48, 54)
        self.color_disabled = (22, 24, 28)
        self.color_text = (200, 200, 200)
        self.color_text_disabled = (80, 80, 80)
    
    def handle_event(self, event):
        if not self.enabled:
            return False
        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1 and self.hovered and self.callback:
                self.callback()
                return True
        return False
    
    def render(self, surface):
        if not self.enabled:
            bg = self.color_disabled
            text_color = self.color_text_disabled
        else:
            bg = self.color_hover if self.hovered else self.color_bg
            text_color = self.color_text
        
        pygame.draw.rect(surface, bg, self.rect)
        
        text_surface = self.font.render(self.text, True, text_color)
        text_rect = text_surface.get_rect(center=self.rect.center)
        surface.blit(text_surface, text_rect)


class AirportMenu:
    """Minimalist airport selection menu with diagram"""
    
    def __init__(self, screen, app):
        self.screen = screen
        self.app = app
        self.width, self.height = screen.get_size()
        
        # Fonts - larger sizes for readability
        custom_font_path = "data/fonts/asdeView_font.ttf"
        if os.path.exists(custom_font_path):
            self.title_font = pygame.font.Font(custom_font_path, 36)
            self.card_font = pygame.font.Font(custom_font_path, 24)
            self.small_font = pygame.font.Font(custom_font_path, 16)
            self.button_font = pygame.font.Font(custom_font_path, 18)
            self.label_font = pygame.font.Font(custom_font_path, 14)
        else:
            self.title_font = pygame.font.Font(None, 36)
            self.card_font = pygame.font.Font(None, 24)
            self.small_font = pygame.font.Font(None, 16)
            self.button_font = pygame.font.Font(None, 18)
            self.label_font = pygame.font.Font(None, 14)
        
        # Colors
        self.bg_color = (18, 20, 24)
        self.title_color = (255, 255, 255)
        self.text_dim = (100, 100, 100)
        self.panel_bg = (22, 24, 28)
        self.accent_green = (60, 140, 80)
        self.accent_blue = (60, 100, 160)
        
        # Load scenarios
        self.scenario_manager = get_scenario_manager()
        self.scenarios = self.scenario_manager.get_all_scenarios()
        self.selected_scenario = None
        
        # Runway config
        self.departure_runways = []
        self.arrival_runways = []
        self.runway_button_rects = []
        
        # Diagram cache
        self.diagram_cache = {}
        
        # Create cards and buttons
        self._create_cards()
        self._create_buttons()
        
        # METAR
        self.metar_cache = {}
        self.metar_fetch_in_progress = {}
    
    def _create_cards(self):
        self.cards = []
        card_width = 380
        card_height = 80
        card_x = 30
        start_y = 90
        spacing = 12
        
        for i, scenario in enumerate(self.scenarios):
            y = start_y + i * (card_height + spacing)
            card = AirportCard(card_x, y, card_width, card_height, scenario, self.card_font, self.small_font)
            self.cards.append(card)
    
    def _create_buttons(self):
        button_height = 40
        button_y = self.height - 55
        
        self.start_button = Button(self.width - 240, button_y, 100, button_height,
                                   "Start", self.button_font, self.start_simulation)
        self.start_button.enabled = False
        
        self.back_button = Button(self.width - 130, button_y, 100, button_height,
                                  "Back", self.button_font, self.back_to_menu)
    
    def start_simulation(self):
        if self.selected_scenario:
            if not hasattr(self.selected_scenario, 'initial_conditions'):
                self.selected_scenario.initial_conditions = {}
            self.selected_scenario.initial_conditions['departure_runways'] = self.departure_runways.copy()
            self.selected_scenario.initial_conditions['arrival_runways'] = self.arrival_runways.copy()
            self.app.show_simulation(self.selected_scenario)
    
    def back_to_menu(self):
        self.app.show_main_menu()
    
    def handle_event(self, event):
        # Runway button clicks
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for btn_type, runway, rect in self.runway_button_rects:
                if rect.collidepoint(event.pos):
                    if btn_type == 'dep':
                        if runway in self.departure_runways:
                            self.departure_runways.remove(runway)
                        else:
                            self.departure_runways.append(runway)
                    elif btn_type == 'arr':
                        if runway in self.arrival_runways:
                            self.arrival_runways.remove(runway)
                        else:
                            self.arrival_runways.append(runway)
                    return
        
        # Card selection
        for card in self.cards:
            if card.handle_event(event):
                for c in self.cards:
                    c.selected = False
                card.selected = True
                self.selected_scenario = card.scenario
                self.start_button.enabled = True
                self._init_runways()
                self._fetch_metar_async(self.selected_scenario.airport_code)
        
        self.start_button.handle_event(event)
        self.back_button.handle_event(event)
    
    def _init_runways(self):
        self.departure_runways = []
        self.arrival_runways = []
        
        if self.selected_scenario:
            airport = self.scenario_manager.get_airport_by_code(self.selected_scenario.airport_code)
            if airport and hasattr(airport, 'runways') and airport.runways:
                runways = []
                for rwy in airport.runways:
                    name = rwy.get('name', '')
                    if '/' in name:
                        runways.extend(name.split('/'))
                    else:
                        runways.append(name)
                if runways:
                    self.departure_runways = [runways[0]]
                    self.arrival_runways = [runways[0]]
    
    def _load_diagram(self, path):
        if path in self.diagram_cache:
            return self.diagram_cache[path]
        try:
            img = pygame.image.load(path).convert_alpha()
            self.diagram_cache[path] = img
            return img
        except:
            return None
    
    def update(self, dt):
        pass
    
    def render(self):
        self.screen.fill(self.bg_color)
        
        # Title
        title = self.title_font.render("Select Airport", True, self.title_color)
        self.screen.blit(title, (30, 25))
        
        # Cards
        for card in self.cards:
            card.render(self.screen)
        
        # Details panel
        if self.selected_scenario:
            self._render_details()
        
        # Buttons
        self.start_button.render(self.screen)
        self.back_button.render(self.screen)
    
    def _render_details(self):
        # Layout: left side has airport cards, then details panel split 50/50 horizontally
        # Left half = info + runways, Right half = diagram
        panel_x = 430
        panel_y = 25
        panel_w = self.width - panel_x - 25
        panel_h = self.height - panel_y - 70
        
        # Panel background
        pygame.draw.rect(self.screen, self.panel_bg, (panel_x, panel_y, panel_w, panel_h))
        
        # Split horizontally: left 50% = info, right 50% = diagram
        half_w = panel_w // 2
        info_x = panel_x + 20
        diagram_x = panel_x + half_w + 10
        diagram_w = half_w - 30
        diagram_h = panel_h - 40
        
        # === LEFT SIDE: INFO + RUNWAYS ===
        x = info_x
        y = panel_y + 20
        
        # Airport name and code
        name = self.card_font.render(self.selected_scenario.airport_name, True, self.title_color)
        self.screen.blit(name, (x, y))
        
        code = self.small_font.render(self.selected_scenario.airport_code, True, self.text_dim)
        self.screen.blit(code, (x + name.get_width() + 15, y + 6))
        y += 38
        
        # METAR
        metar = self.metar_cache.get(self.selected_scenario.airport_code, "Loading...")
        metar_short = metar[:65] + "..." if len(metar) > 65 else metar
        metar_surf = self.small_font.render(metar_short, True, (140, 140, 140))
        self.screen.blit(metar_surf, (x, y))
        y += 40
        
        # === RUNWAY CONFIGURATION ===
        # Divider line
        pygame.draw.line(self.screen, (40, 42, 48), (x, y), (x + half_w - 40, y), 1)
        y += 18
        
        rwy_title = self.button_font.render("RUNWAY CONFIG", True, self.text_dim)
        self.screen.blit(rwy_title, (x, y))
        y += 35
        
        # Get runways
        available_runways = []
        airport = self.scenario_manager.get_airport_by_code(self.selected_scenario.airport_code)
        if airport and hasattr(airport, 'runways') and airport.runways:
            for rwy in airport.runways:
                rwy_name = rwy.get('name', '')
                if '/' in rwy_name:
                    available_runways.extend(rwy_name.split('/'))
                else:
                    available_runways.append(rwy_name)
        
        self.runway_button_rects = []
        
        # Display runways with larger buttons
        for runway in available_runways:
            # Runway identifier
            rwy_label = self.button_font.render(f"RWY {runway}", True, (200, 200, 200))
            self.screen.blit(rwy_label, (x, y + 8))
            
            btn_x = x + 100
            btn_w = 60
            btn_h = 34
            
            # DEP button - green when active
            dep_rect = pygame.Rect(btn_x, y, btn_w, btn_h)
            dep_active = runway in self.departure_runways
            if dep_active:
                pygame.draw.rect(self.screen, self.accent_green, dep_rect)
                pygame.draw.rect(self.screen, (100, 180, 120), dep_rect, 2)
            else:
                pygame.draw.rect(self.screen, (32, 34, 38), dep_rect)
                pygame.draw.rect(self.screen, (55, 58, 65), dep_rect, 1)
            
            dep_text = self.label_font.render("DEP", True, (255, 255, 255) if dep_active else (90, 90, 90))
            self.screen.blit(dep_text, dep_text.get_rect(center=dep_rect.center))
            self.runway_button_rects.append(('dep', runway, dep_rect))
            
            # ARR button - blue when active
            arr_rect = pygame.Rect(btn_x + btn_w + 10, y, btn_w, btn_h)
            arr_active = runway in self.arrival_runways
            if arr_active:
                pygame.draw.rect(self.screen, self.accent_blue, arr_rect)
                pygame.draw.rect(self.screen, (100, 140, 200), arr_rect, 2)
            else:
                pygame.draw.rect(self.screen, (32, 34, 38), arr_rect)
                pygame.draw.rect(self.screen, (55, 58, 65), arr_rect, 1)
            
            arr_text = self.label_font.render("ARR", True, (255, 255, 255) if arr_active else (90, 90, 90))
            self.screen.blit(arr_text, arr_text.get_rect(center=arr_rect.center))
            self.runway_button_rects.append(('arr', runway, arr_rect))
            
            y += 45
        
        # Show current config summary
        y += 15
        dep_list = ", ".join(self.departure_runways) if self.departure_runways else "None"
        arr_list = ", ".join(self.arrival_runways) if self.arrival_runways else "None"
        summary = self.label_font.render(f"DEP: {dep_list}", True, (130, 130, 130))
        self.screen.blit(summary, (x, y))
        y += 22
        summary2 = self.label_font.render(f"ARR: {arr_list}", True, (130, 130, 130))
        self.screen.blit(summary2, (x, y))
        
        # === RIGHT SIDE: DIAGRAM ===
        # Vertical divider
        pygame.draw.line(self.screen, (40, 42, 48), 
                        (panel_x + half_w, panel_y + 15), 
                        (panel_x + half_w, panel_y + panel_h - 15), 1)
        
        diagram_path = self.selected_scenario.get_diagram_path() if hasattr(self.selected_scenario, 'get_diagram_path') else None
        if diagram_path and os.path.exists(diagram_path):
            diagram = self._load_diagram(diagram_path)
            if diagram:
                # Scale to fit right half
                dw, dh = diagram.get_size()
                max_w = diagram_w
                max_h = diagram_h
                scale = min(max_w / dw, max_h / dh, 1.0)
                new_w, new_h = int(dw * scale), int(dh * scale)
                scaled = pygame.transform.smoothscale(diagram, (new_w, new_h))
                
                # Center in diagram area
                dx = diagram_x + (diagram_w - new_w) // 2
                dy = panel_y + 20 + (diagram_h - new_h) // 2
                self.screen.blit(scaled, (dx, dy))
        else:
            # No diagram placeholder
            no_diag = self.small_font.render("No diagram available", True, self.text_dim)
            self.screen.blit(no_diag, (diagram_x + 20, panel_y + panel_h // 2))
    
    def _fetch_metar_async(self, airport_code):
        import threading
        
        if airport_code in self.metar_fetch_in_progress or airport_code in self.metar_cache:
            return
        
        self.metar_fetch_in_progress[airport_code] = True
        
        def fetch():
            try:
                url = f"https://aviationweather.gov/api/data/metar?ids={airport_code}&format=json"
                try:
                    import requests
                    resp = requests.get(url, timeout=5)
                    if resp.status_code == 200:
                        data = resp.json()
                        if data and len(data) > 0:
                            self.metar_cache[airport_code] = data[0].get('rawOb', 'N/A')
                        else:
                            self.metar_cache[airport_code] = 'N/A'
                except:
                    self.metar_cache[airport_code] = 'N/A'
            finally:
                self.metar_fetch_in_progress.pop(airport_code, None)
        
        threading.Thread(target=fetch, daemon=True).start()
    
    def handle_resize(self, new_size):
        self.width, self.height = new_size
        self._create_cards()
        self._create_buttons()
    
    def handle_display_change(self, new_size, is_fullscreen):
        self.handle_resize(new_size)
