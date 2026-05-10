"""
Flight plan panel - shows aircraft flight strip information
"""
import pygame
import random


class FlightPlanPanel:
    """Flight plan panel showing aircraft flight strip information"""

    def __init__(self, screen_width, screen_height):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.panel_width = 700
        self.panel_height = 180
        self.is_open = False
        self.aircraft = None

        # Dragging state
        self.dragging = False
        self.drag_offset_x = 0
        self.drag_offset_y = 0

        # Panel position (centered by default, but can be dragged)
        self.panel_x = (self.screen_width - self.panel_width) // 2
        self.panel_y = 100

    def set_aircraft(self, aircraft):
        """Set the aircraft to display"""
        self.aircraft = aircraft
        self.is_open = aircraft is not None

    def handle_mouse_down(self, pos):
        """Handle mouse down events for dragging"""
        if not self.is_open or not self.aircraft:
            return False

        panel_rect = pygame.Rect(self.panel_x, self.panel_y, self.panel_width, self.panel_height)

        if panel_rect.collidepoint(pos):
            # Check for close button (X in top right)
            title_height = 30
            close_rect = pygame.Rect(self.panel_x + self.panel_width - 30, self.panel_y + 5, 25, 25)
            if close_rect.collidepoint(pos):
                self.is_open = False
                self.aircraft = None
                return True

            # Check if clicking on title bar for dragging
            title_rect = pygame.Rect(self.panel_x, self.panel_y, self.panel_width, title_height)
            if title_rect.collidepoint(pos):
                self.dragging = True
                self.drag_offset_x = pos[0] - self.panel_x
                self.drag_offset_y = pos[1] - self.panel_y
                return True

            return True

        # Click outside panel closes it
        self.is_open = False
        self.aircraft = None
        return False

    def handle_mouse_up(self):
        """Handle mouse up events"""
        self.dragging = False

    def handle_mouse_motion(self, pos):
        """Handle mouse motion for dragging"""
        if self.dragging:
            self.panel_x = pos[0] - self.drag_offset_x
            self.panel_y = pos[1] - self.drag_offset_y

            # Keep panel within screen bounds
            self.panel_x = max(0, min(self.panel_x, self.screen_width - self.panel_width))
            self.panel_y = max(0, min(self.panel_y, self.screen_height - self.panel_height))

    def handle_click(self, pos):
        """Handle clicks on the panel (for compatibility)"""
        return self.handle_mouse_down(pos)

    def render(self, screen, info_font, tag_font, airport_code=None):
        """Render the flight plan panel"""
        if not self.is_open or not self.aircraft:
            return

        # Create panel surface
        panel_surface = pygame.Surface((self.panel_width, self.panel_height))
        panel_surface.fill((18, 22, 30))  # Modern dark background

        # Draw border
        pygame.draw.rect(panel_surface, (60, 140, 180), (0, 0, self.panel_width, self.panel_height), 2)

        # Title bar (darker for dragging indication)
        title_height = 30
        title_color = (30, 100, 150) if self.dragging else (25, 35, 50)
        pygame.draw.rect(panel_surface, title_color, (0, 0, self.panel_width, title_height))

        # Get aircraft data
        callsign = self.aircraft.get_callsign()
        aircraft_type = getattr(self.aircraft, 'aircraft_type', 'N/A')
        airline = getattr(self.aircraft, 'airline', '')
        gate = getattr(self.aircraft, 'gate', 'N/A')

        # Get departure route info
        departure_route = getattr(self.aircraft, 'departure_route', None)
        destination = departure_route.get('destination', 'N/A') if departure_route else 'N/A'
        exit_fix = getattr(self.aircraft, 'exit_fix', None) or (departure_route.get('exit', 'N/A') if departure_route else 'N/A')
        route = departure_route.get('route', 'N/A') if departure_route else 'N/A'
        target_altitude = departure_route.get('altitude', 0) if departure_route else 0

        # Current values
        speed = int(getattr(self.aircraft, 'speed', 0))
        altitude = int(getattr(self.aircraft, 'altitude', 0))

        # Use airport code as departure airport (not gate)
        dep_airport = airport_code or 'N/A'

        # Title - format like image: "CALLSIGN - Airport DEST"
        title_text = f"{callsign} - {airport_code or 'N/A'} {destination}"
        title_surface = info_font.render(title_text, True, (200, 220, 255))
        panel_surface.blit(title_surface, (10, 5))

        # Close button
        close_text = info_font.render("X", True, (255, 255, 255))
        panel_surface.blit(close_text, (self.panel_width - 25, 5))

        # Field labels row - match image layout
        y_offset = title_height + 8
        labels = ["CALLSIGN", "CID", "BCN", "TYP", "EQ", "DEP", "DEST", "SPD", "ALT"]
        label_x = 10
        label_spacings = [75, 50, 50, 50, 40, 60, 60, 50, 50]  # Custom spacing to match image

        x_pos = label_x
        for i, label in enumerate(labels):
            label_surface = tag_font.render(label, True, (255, 255, 255))
            panel_surface.blit(label_surface, (x_pos, y_offset))
            if i < len(label_spacings):
                x_pos += label_spacings[i]

        # Field values row - with background boxes like image
        y_offset += 18

        # Get controller ID and beacon code from aircraft
        cid = getattr(self.aircraft, 'cid', None)  # Get CID from aircraft
        if cid is None:
            cid = "---"  # Fallback if CID not assigned
        else:
            cid = str(cid)  # Convert to string for display

        bcn = getattr(self.aircraft, 'beacon', None)  # Get beacon code from aircraft
        if bcn is None:
            bcn = "----"  # Fallback if beacon not assigned
        else:
            bcn = str(bcn)  # Convert to string for display

        values = [
            callsign,  # AID
            cid,  # CID
            bcn,  # BCN
            aircraft_type,  # TYP
            "L",  # EQ (equipment code)
            dep_airport,  # DEP
            destination,  # DEST
            str(speed) if speed > 0 else "---",  # SPD
            f"{altitude:03d}" if altitude > 0 else "---"  # ALT
        ]

        x_pos = label_x
        for i, value in enumerate(values):
            # Draw background box for value
            box_width = label_spacings[i] - 4 if i < len(label_spacings) else 50
            box_height = 18
            pygame.draw.rect(panel_surface, (15, 20, 30), (x_pos, y_offset - 2, box_width, box_height))
            pygame.draw.rect(panel_surface, (50, 70, 90), (x_pos, y_offset - 2, box_width, box_height), 1)

            # Render value text
            value_surface = tag_font.render(str(value), True, (100, 180, 255))
            panel_surface.blit(value_surface, (x_pos + 2, y_offset))

            if i < len(label_spacings):
                x_pos += label_spacings[i]

        # Route field - below main fields
        y_offset += 25
        route_label = tag_font.render("RTE:", True, (255, 255, 255))
        panel_surface.blit(route_label, (10, y_offset))

        # Route value with background box
        route_box_width = self.panel_width - 80
        route_box_height = 18
        pygame.draw.rect(panel_surface, (15, 20, 30), (60, y_offset - 2, route_box_width, route_box_height))
        pygame.draw.rect(panel_surface, (50, 70, 90), (60, y_offset - 2, route_box_width, route_box_height), 1)
        route_value = tag_font.render(str(route), True, (100, 180, 255))
        panel_surface.blit(route_value, (62, y_offset))

        # Remarks field - at bottom
        y_offset += 22
        rmk_label = tag_font.render("RMK:", True, (255, 255, 255))
        panel_surface.blit(rmk_label, (10, y_offset))

        # Remarks value with background box
        rmk_box_width = self.panel_width - 80
        rmk_box_height = 18
        pygame.draw.rect(panel_surface, (15, 20, 30), (60, y_offset - 2, rmk_box_width, rmk_box_height))
        pygame.draw.rect(panel_surface, (50, 70, 90), (60, y_offset - 2, rmk_box_width, rmk_box_height), 1)
        rmk_text = f"Exit: {exit_fix}" if exit_fix != 'N/A' else "N/A"
        rmk_value = tag_font.render(rmk_text, True, (100, 180, 255))
        panel_surface.blit(rmk_value, (62, y_offset))

        # Blit panel to screen
        screen.blit(panel_surface, (self.panel_x, self.panel_y))

    def get_random_cid(self):
        #random
        return random.randint(100, 999)

    def get_random_bcn(self):
        #random 4 digit number
        bcn = random.randint(1000, 7777)

        #dont return 7700 or 6600
        while bcn == 7700 or bcn == 7600 or bcn == 7500:
            bcn = random.randint(1000, 7777)
        return bcn
