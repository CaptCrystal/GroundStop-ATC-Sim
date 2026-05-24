"""
UI rendering mixin for SimulationScreen
"""
import pygame
import math
import os
from datetime import datetime


class UIMixin:
    """Mixin providing HUD, help panel, menus, and UI utility methods for SimulationScreen."""

    def render_hud(self):
        """Render heads-up display"""

        # Airport code - handle both new scenarios and loaded saves
        if self.scenario:
            airport_code = self.scenario.airport_code
        elif self.save_data:
            metadata = self.save_data.get('metadata', {})
            airport_code = metadata.get('airport_code', 'UNKNOWN')
        else:
            airport_code = 'UNKNOWN'

        # Offset HUD content below top-menu-bar
        _top_offset = (self.top_menu_bar.height if self.top_menu_bar else 35) + 4
        airport_text = self.title_font.render(airport_code, True, (200, 210, 230))
        self.screen.blit(airport_text, (20, _top_offset))

        # Airport controllers
        if self.airport_data and 'controllers' in self.airport_data:
            controllers = self.airport_data.get('controllers', [])
            y_offset = _top_offset + 45
            for controller in controllers:
                name = controller.get('name', '')
                frequency = controller.get('frequency', '')
                if name and frequency:
                    controller_text = self.info_font.render(f"{name}: {frequency}", True, (0, 224, 21))
                    self.screen.blit(controller_text, (20, y_offset))
                    y_offset += 25

        # Time display - show actual current time (below both bars)
        _time_y = _top_offset
        if self.time_settings == "zulu":
            current_time = datetime.utcnow()
            time_str = current_time.strftime("%H%M")
            time_text = self.info_font.render(f"{time_str}z", True, (0, 224, 21))
            self.screen.blit(time_text, (self.width - 300, _time_y))
        else:
            current_time = datetime.now()
            time_str = current_time.strftime("%H:%M")
            time_text = self.info_font.render(f"{time_str} Local", True, (0, 224, 21))
            self.screen.blit(time_text, (self.width - 300, _time_y))

        # Time acceleration indicator (only show if not 1x)
        if self.top_menu_bar and hasattr(self.top_menu_bar, 'time_acceleration'):
            time_accel = self.top_menu_bar.time_acceleration
            if abs(time_accel - 1.0) > 0.01:
                accel_color = (255, 200, 100)
                accel_text = self.info_font.render(f"Time: {time_accel:.1f}x", True, accel_color)
                self.screen.blit(accel_text, (self.width - 300, _time_y + 18))

        # Help button icon
        help_button_icon = pygame.image.load("data/images/help-button-icon.png")
        help_button_icon = pygame.transform.scale(help_button_icon, (20, 20))
        self.screen.blit(help_button_icon, (self.width - 50, self.height - 50))

        # Display help panel if toggled on
        if self.show_help:
            self.render_help_panel()

    def render_help_panel(self):
        """Render scrollable help panel with background"""
        # Panel dimensions and position
        panel_width = 600
        panel_height = self.height - 100
        panel_x = (self.width - panel_width) // 1
        panel_y = 50

        # Create semi-transparent background
        panel_surface = pygame.Surface((panel_width, panel_height))
        panel_surface.set_alpha(245)
        panel_surface.fill((18, 22, 30))  # Modern dark background

        # Draw border
        pygame.draw.rect(panel_surface, (60, 140, 180), (0, 0, panel_width, panel_height), 3)

        # Title bar
        title_height = 50
        pygame.draw.rect(panel_surface, (30, 100, 150), (0, 0, panel_width, title_height))
        pygame.draw.line(panel_surface, (60, 140, 180), (0, title_height), (panel_width, title_height), 2)

        title_text = self.title_font.render("Help & Controls", True, (220, 240, 255))
        title_rect = title_text.get_rect(center=(panel_width // 2, title_height // 2))
        panel_surface.blit(title_text, title_rect)

        # Help content
        help_content = [
            ("NAVIGATION", True),
            ("ESC", "Return to menu"),
            ("Right Click + Drag", "Pan camera view"),
            ("Mouse Wheel", "Zoom in/out"),
            ("Arrow Keys", "Move camera (50px)"),
            ("+/=", "Zoom in"),
            ("-", "Zoom out"),
            ("", False),
            ("ATC COMMANDS", True),
            ("/", "Activate command bar"),
            ("Format", "[number] [command]"),
            ("123 pa", "Pushback approved"),
            ("123 t02ua", "Taxi to 02 via U A"),
            ("123 h02", "Hold short runway 2"),
            ("123 c02", "Cross runway 2"),
            ("123 to", "Contact tower"),
            ("123 h", "Hold position"),
            ("help", "Show commands"),
            ("clear", "Clear output"),
            ("Up/Down Arrows", "Navigate history (20 cmds)"),
            ("", False),
            ("DISPLAY", True),
            ("Time Display", "Shows current time (Zulu/Local)"),
            ("Airport Code", "Current airport identifier"),
            ("Controllers", "ATC frequencies"),
            ("", False),
            ("DEVELOPER", True),
            ("Shift+Ctrl+1", "Toggle dev mode (gates/taxiways)"),
            ("", False),
            ("DATA TAG POSITIONING", True),
            ("Numpad 8/6/2/4", "Set direction N/E/S/W"),
            ("Numpad 9/7/3/1", "Set direction diagonally"),
            ("Click Aircraft", "Apply direction"),
            ("", False),
            ("HELP MENU", True),
            ("Click Help Icon", "Toggle this help panel"),
            ("Mouse Wheel", "Scroll through help content"),
        ]

        # Content area
        content_y = title_height + 20
        line_height = 25
        padding_x = 20

        # Calculate max scroll based on content
        total_content_height = len(help_content) * line_height
        max_scroll = max(0, total_content_height - (panel_height - title_height - 40))
        self.help_scroll_offset = min(self.help_scroll_offset, max_scroll)

        # Render content with scroll offset
        y_offset = content_y - self.help_scroll_offset

        for item in help_content:
            if y_offset > title_height and y_offset < panel_height - 10:
                if isinstance(item, tuple) and len(item) == 2:
                    if item[1] == True:  # Section header
                        header_text = self.info_font.render(item[0], True, (100, 200, 255))
                        panel_surface.blit(header_text, (padding_x, y_offset))
                    elif item[1] == False:  # Empty line
                        pass
                    else:  # Key-value pair
                        key_text = self.info_font.render(f"{item[0]}:", True, (150, 200, 150))
                        value_text = self.info_font.render(item[1], True, (200, 210, 220))
                        panel_surface.blit(key_text, (padding_x, y_offset))
                        panel_surface.blit(value_text, (padding_x + 200, y_offset))

            y_offset += line_height

        # Scroll indicator
        if max_scroll > 0:
            scroll_bar_height = max(30, (panel_height - title_height) * (panel_height - title_height) // total_content_height)
            scroll_bar_y = title_height + (self.help_scroll_offset / max_scroll) * (panel_height - title_height - scroll_bar_height)
            pygame.draw.rect(panel_surface, (100, 140, 180), (panel_width - 10, scroll_bar_y, 6, scroll_bar_height), border_radius=3)

        # Blit panel to screen
        self.screen.blit(panel_surface, (panel_x, panel_y))

    def render_top_menu_bar(self):
        """Render the top menu bar with icons."""
        self.top_menu_bar.render(self.screen, self.info_font)

    def _render_radio_static(self):
        """Overlay a brief noise effect on the radar when an aircraft is transmitting."""
        import random
        # Fade alpha down as timer runs out for a smooth tail-off
        STATIC_DURATION = 0.6  # seconds (must match value set in play_radio_sound)
        frac = min(1.0, self.radio_static_timer / STATIC_DURATION)
        alpha = int(frac * 55)  # max 55/255 — subtle, not blinding

        noise = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        # Scatter random bright speckles across the radar area
        top_offset = getattr(self.top_menu_bar, 'height', 35) if self.top_menu_bar else 35
        num_dots = int(frac * 600)
        for _ in range(num_dots):
            x = random.randint(0, self.width - 1)
            y = random.randint(top_offset, self.height - 1)
            brightness = random.randint(160, 255)
            dot_alpha = random.randint(80, 160)
            noise.set_at((x, y), (brightness, brightness, brightness, dot_alpha))
        # Thin horizontal scanline bands for extra CRT feel
        for y in range(top_offset, self.height, random.randint(6, 14)):
            band_alpha = random.randint(0, alpha)
            pygame.draw.line(noise, (200, 220, 200, band_alpha), (0, y), (self.width, y))
        self.screen.blit(noise, (0, 0))

    def render_command_system(self):
        """Render the ATC command bar and output"""
        # Smaller bar on left side
        bar_width = 500
        bar_x = 10
        margin = 8

        # Command output area (above command bar) - only if setting enabled; dimmer when on
        show_output = self.top_menu_bar and self.top_menu_bar.show_past_transmissions
        if show_output and self.command_output:
            output_height = 25
            output_y_start = self.height - 60 - (len(self.command_output) * output_height)
            n = len(self.command_output)
            for i, item in enumerate(self.command_output):
                output_y = output_y_start + (i * output_height)
                # Older lines more faded: newest (last index) = less dim, oldest = most dim
                fade = (i + 1) / n  # 1/n .. 1 so oldest = 1/n, newest = 1
                alpha_bg = int(80 + 60 * fade)  # 80–140 alpha for background
                color_scale = 0.35 + 0.45 * fade  # dim text: ~35% to ~80% brightness
                text, color = item if isinstance(item, tuple) else (item, (0, 224, 21))
                dimmed = tuple(max(0, min(255, int(c * color_scale))) for c in color)
                output_bg = pygame.Surface((bar_width, output_height - 3), pygame.SRCALPHA)
                output_bg.fill((20, 25, 35, alpha_bg))
                self.screen.blit(output_bg, (bar_x, output_y))
                output_text = self.info_font.render(text, True, dimmed)
                self.screen.blit(output_text, (bar_x + margin, output_y + 3))

        # Command bar (always visible at bottom right)
        bar_height = 40
        bar_y = self.height - bar_height - 10

        # Command bar background
        bar_bg = pygame.Surface((bar_width, bar_height), pygame.SRCALPHA)
        if self.command_bar_active:
            bar_bg.fill((30, 40, 60, 240))
            border_color = (100, 180, 255)
        else:
            bar_bg.fill((20, 25, 35, 200))
            border_color = (60, 70, 90)

        self.screen.blit(bar_bg, (bar_x, bar_y))

        # Border
        pygame.draw.rect(self.screen, border_color,
                        (bar_x, bar_y, bar_width, bar_height), 2, border_radius=5)

        # Prompt and input text
        if self.command_bar_active:
            # Render command input with grayed out pre-filled callsign
            if self.prefilled_callsign and self.command_input.startswith(f"/{self.prefilled_callsign} "):
                # Split into pre-filled part and user input
                prefix_len = len(f"/{self.prefilled_callsign} ")
                prefix_text = self.command_input[:prefix_len]
                user_text = self.command_input[prefix_len:]

                # Render prefix in gray
                prefix_surface = self.info_font.render(prefix_text, True, (120, 130, 140))
                self.screen.blit(prefix_surface, (bar_x + margin, bar_y + 12))

                # Render user input in white
                user_surface = self.info_font.render(user_text, True, (255, 255, 255))
                prefix_width = prefix_surface.get_width()
                self.screen.blit(user_surface, (bar_x + margin + prefix_width, bar_y + 12))

                # Blinking cursor at correct position
                if (pygame.time.get_ticks() // 500) % 2 == 0:
                    cursor_x = bar_x + margin
                    if self.cursor_position <= prefix_len:
                        # Cursor in gray area - show after prefix
                        cursor_x += prefix_width
                    else:
                        # Cursor in user input area
                        cursor_text = user_text[:self.cursor_position - prefix_len]
                        cursor_surface = self.info_font.render(cursor_text, True, (255, 255, 255))
                        cursor_x += prefix_width + cursor_surface.get_width()

                    cursor_y = bar_y + 12
                    self.screen.blit(self.info_font.render("|", True, (255, 255, 255)), (cursor_x, cursor_y))
            else:
                # Normal rendering (no pre-filled callsign or user has edited it)
                cursor = "|" if (pygame.time.get_ticks() // 500) % 2 == 0 else ""
                display_text = self.command_input + cursor
                text_color = (255, 255, 255)
                command_text = self.info_font.render(display_text, True, text_color)
                self.screen.blit(command_text, (bar_x + margin, bar_y + 12))
        else:
            display_text = "Press ; for ATC command"
            text_color = (150, 160, 180)
            command_text = self.info_font.render(display_text, True, text_color)
            self.screen.blit(command_text, (bar_x + margin, bar_y + 12))

    def render_dev_mode(self):
        """Render dev mode overlays: gates, taxiways, and runways"""
        if not self.airport_data or self.center_lat is None or self.center_lon is None:
            return

        # Get the same scale used for GeoJSON rendering
        if not self.bounds:
            return

        # Get scale
        scale = self.get_scale()

        # Draw taxiways
        taxiways = self.airport_data.get('taxiways', [])
        for taxiway in taxiways:
            points = taxiway.get('points', [])
            if len(points) >= 2:
                screen_points = []
                for point in points:
                    lat = point.get('x')  # x is latitude
                    lon = point.get('y')  # y is longitude
                    if lat and lon:
                        x, y = self.project_point(lon, lat, self.center_lon, self.center_lat, scale)
                        screen_points.append((x, y))

                if len(screen_points) >= 2:
                    # Draw taxiway line in yellow
                    pygame.draw.lines(self.screen, (255, 255, 0), False, screen_points, 3)

                    # Draw taxiway label
                    if screen_points:
                        mid_point = screen_points[len(screen_points) // 2]
                        label = taxiway.get('taxiway', '')
                        if label:
                            label_text = self.info_font.render(label, True, (255, 255, 0))
                            self.screen.blit(label_text, (mid_point[0] + 5, mid_point[1] - 10))

        # Draw ramps
        ramps = self.airport_data.get('ramps', [])
        for ramp in ramps:
            points = ramp.get('points', [])
            if len(points) >= 2:
                screen_points = []
                for point in points:
                    lat = point.get('x')  # x is latitude
                    lon = point.get('y')  # y is longitude
                    if lat and lon:
                        x, y = self.project_point(lon, lat, self.center_lon, self.center_lat, scale)
                        screen_points.append((x, y))

                if len(screen_points) >= 2:
                    # Draw ramp line in yellow
                    pygame.draw.lines(self.screen, (255, 255, 0), False, screen_points, 3)

                    # Draw ramp label
                    if screen_points:
                        mid_point = screen_points[len(screen_points) // 2]
                        label = ramp.get('ramp', '')
                        if label:
                            label_text = self.info_font.render(label, True, (255, 255, 0))
                            self.screen.blit(label_text, (mid_point[0] + 5, mid_point[1] - 10))

        # Draw runways
        runways = self.airport_data.get('runways', [])
        for runway in runways:
            points = runway.get('points', [])
            if len(points) >= 2:
                screen_points = []
                for point in points:
                    lat = point.get('x')  # x is latitude
                    lon = point.get('y')  # y is longitude
                    if lat and lon:
                        x, y = self.project_point(lon, lat, self.center_lon, self.center_lat, scale)
                        screen_points.append((x, y))

                if len(screen_points) >= 2:
                    # Draw runway line in red
                    pygame.draw.lines(self.screen, (255, 0, 0), False, screen_points, 3)

                    # Draw runway label
                    if screen_points:
                        mid_point = screen_points[len(screen_points) // 2]
                        label = runway.get('name', '')
                        if label:
                            label_text = self.info_font.render(label, True, (255, 0, 0))
                            self.screen.blit(label_text, (mid_point[0] + 5, mid_point[1] - 10))

            # Draw runway polygon if available
            runway_polygon = runway.get('runway_polygon', [])
            if runway_polygon and len(runway_polygon) > 0:
                # Get the polygon points (first element of runway_polygon array)
                polygon = runway_polygon[0] if isinstance(runway_polygon[0], list) else runway_polygon
                if len(polygon) >= 3:
                    polygon_screen_points = []
                    for point in polygon:
                        lat = point.get('x')
                        lon = point.get('y')
                        if lat and lon:
                            x, y = self.project_point(lon, lat, self.center_lon, self.center_lat, scale)
                            polygon_screen_points.append((x, y))

                    if len(polygon_screen_points) >= 3:
                        # Draw filled polygon with transparency (cyan with alpha)
                        polygon_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
                        pygame.draw.polygon(polygon_surface, (0, 255, 255, 60), polygon_screen_points)
                        self.screen.blit(polygon_surface, (0, 0))

                        # Draw polygon outline in bright cyan
                        pygame.draw.polygon(self.screen, (0, 255, 255), polygon_screen_points, 2)

                        # Draw label
                        if polygon_screen_points:
                            center_x = sum(p[0] for p in polygon_screen_points) / len(polygon_screen_points)
                            center_y = sum(p[1] for p in polygon_screen_points) / len(polygon_screen_points)
                            label_text = self.info_font.render("RWY POLYGON", True, (0, 255, 255))
                            self.screen.blit(label_text, (center_x - 40, center_y))

        # Draw runway exits (arrival turn-off points)
        runway_exits = self.airport_data.get('runway_exits', [])
        for rexit in runway_exits:
            pt = rexit.get('exit_point') or rexit.get('point')
            if not pt:
                continue
            lat = pt.get('x') if isinstance(pt, dict) else (pt[0] if isinstance(pt, (list, tuple)) else None)
            lon = pt.get('y') if isinstance(pt, dict) else (pt[1] if isinstance(pt, (list, tuple)) else None)
            if lat is None or lon is None:
                continue
            x, y = self.project_point(lon, lat, self.center_lon, self.center_lat, scale)
            rwy = rexit.get('runway', '')
            twy = rexit.get('taxiway', '')
            pygame.draw.circle(self.screen, (0, 255, 0), (int(x), int(y)), 8, 2)
            pygame.draw.line(self.screen, (0, 255, 0), (x - 12, y), (x + 12, y), 2)
            pygame.draw.line(self.screen, (0, 255, 0), (x, y - 12), (x, y + 12), 2)
            label_text = self.info_font.render(f"{rwy}→{twy}", True, (0, 255, 0))
            self.screen.blit(label_text, (int(x) + 10, int(y) - 8))

        # Draw arrival spawn points and approach heading arrows from arrival_procedures
        arrival_procedures = self.airport_data.get('arrival_procedures', [])
        if not arrival_procedures:
            arrivals_config = self.airport_data.get('arrivals_config', {})
            if isinstance(arrivals_config, dict):
                runway_cfg = arrivals_config.get('runway')
                if isinstance(runway_cfg, dict):
                    arrival_procedures = [{
                        'runway': runway_cfg.get('runway_name') or runway_cfg.get('runway', ''),
                        'spawn_location': runway_cfg.get('spawn_location'),
                        'approach_heading': runway_cfg.get('direction'),
                        'approach_type': arrivals_config.get('approach_type', 'visual')
                    }]

        for proc in arrival_procedures:
            if not isinstance(proc, dict):
                continue
            loc = proc.get('spawn_location')
            rwy_name = proc.get('runway', '')
            approach_type = proc.get('approach_type', '')
            heading_val = proc.get('approach_heading')
            if not loc or heading_val is None:
                continue
            lat = loc.get('x')
            lon = loc.get('y')
            if lat is None or lon is None:
                continue
            x, y = self.project_point(lon, lat, self.center_lon, self.center_lat, scale)
            color = (255, 165, 0)  # Orange
            pygame.draw.circle(self.screen, color, (int(x), int(y)), 10, 2)
            pygame.draw.line(self.screen, color, (x - 12, y), (x + 12, y), 2)
            pygame.draw.line(self.screen, color, (x, y - 12), (x, y + 12), 2)
            # Arrow pointing in the approach direction (toward runway)
            try:
                heading_deg = float(heading_val)
                arrow_len = 35
                rad = math.radians(heading_deg)
                dx = math.sin(rad) * arrow_len
                dy = -math.cos(rad) * arrow_len
                end_x, end_y = x + dx, y + dy
                pygame.draw.line(self.screen, color, (x, y), (end_x, end_y), 3)
                arrow_size = 8
                left_rad = rad - math.radians(150)
                right_rad = rad + math.radians(150)
                lx = end_x + arrow_size * math.sin(left_rad)
                ly = end_y - arrow_size * math.cos(left_rad)
                rx = end_x + arrow_size * math.sin(right_rad)
                ry = end_y - arrow_size * math.cos(right_rad)
                pygame.draw.line(self.screen, color, (end_x, end_y), (lx, ly), 2)
                pygame.draw.line(self.screen, color, (end_x, end_y), (rx, ry), 2)
            except (TypeError, ValueError):
                pass
            label = f"Arrival {rwy_name} {approach_type} ({heading_val}°)"
            label_text = self.info_font.render(label, True, color)
            self.screen.blit(label_text, (int(x) + 12, int(y) - 8))

        # Draw lineup positions from runway_definition
        runway_definitions = self.airport_data.get('runway_definition', [])
        for rwy_def in runway_definitions:
            lineup_data = rwy_def.get('lineup', [])
            runway_name = rwy_def.get('name', '')
            if lineup_data and len(lineup_data) > 0:
                for lineup_point in lineup_data:
                    lat = lineup_point.get('x')
                    lon = lineup_point.get('y')
                    if lat and lon:
                        x, y = self.project_point(lon, lat, self.center_lon, self.center_lat, scale)

                        # Draw lineup position as magenta circle with crosshair
                        pygame.draw.circle(self.screen, (255, 0, 255), (int(x), int(y)), 10, 3)
                        pygame.draw.line(self.screen, (255, 0, 255), (x - 15, y), (x + 15, y), 2)
                        pygame.draw.line(self.screen, (255, 0, 255), (x, y - 15), (x, y + 15), 2)

                        # Draw label
                        label_text = self.info_font.render(f"LINEUP {runway_name}", True, (255, 0, 255))
                        self.screen.blit(label_text, (x + 15, y - 10))

        # Draw pushback spots
        pushback_spots = self.airport_data.get('pushback_spots', [])
        for spot in pushback_spots:
            points = spot.get('points', [])
            if points and len(points) > 0:
                point = points[0]
                lat = point.get('x')
                lon = point.get('y')
                heading = spot.get('Degrees', 0)
                spot_name = spot.get('pushback_spot', '')

                if lat and lon:
                    x, y = self.project_point(lon, lat, self.center_lon, self.center_lat, scale)

                    # Draw pushback spot as cyan circle
                    pygame.draw.circle(self.screen, (0, 255, 255), (int(x), int(y)), 8, 2)

                    # Draw heading indicator (small arrow)
                    arrow_length = 15
                    rad = math.radians(heading)
                    end_x = x + arrow_length * math.sin(rad)
                    end_y = y - arrow_length * math.cos(rad)
                    pygame.draw.line(self.screen, (0, 255, 255), (x, y), (end_x, end_y), 2)

                    # Draw arrowhead
                    arrow_size = 5
                    left_rad = rad - math.radians(150)
                    right_rad = rad + math.radians(150)
                    left_x = end_x + arrow_size * math.sin(left_rad)
                    left_y = end_y - arrow_size * math.cos(left_rad)
                    right_x = end_x + arrow_size * math.sin(right_rad)
                    right_y = end_y - arrow_size * math.cos(right_rad)
                    pygame.draw.line(self.screen, (0, 255, 255), (end_x, end_y), (left_x, left_y), 2)
                    pygame.draw.line(self.screen, (0, 255, 255), (end_x, end_y), (right_x, right_y), 2)

                    # Draw label
                    label_text = self.info_font.render(spot_name, True, (0, 255, 255))
                    self.screen.blit(label_text, (x + 10, y - 5))

        # Draw pushback points (waypoint paths from gates)
        gates = self.airport_data.get('gates', [])
        for gate in gates:
            pushback_points = gate.get('pusback_points')  # Note: typo in JSON
            if pushback_points and len(pushback_points) > 0:
                # pushback_points can be nested in various ways, flatten to get the actual points
                all_points = []

                def extract_points(data):
                    """Recursively extract point dicts from nested structure"""
                    if isinstance(data, dict) and 'x' in data and 'y' in data:
                        all_points.append(data)
                    elif isinstance(data, list):
                        for item in data:
                            extract_points(item)

                extract_points(pushback_points)

                if len(all_points) > 1:
                    screen_points = []
                    for point in all_points:
                        lat = point.get('x')
                        lon = point.get('y')

                        if lat is not None and lon is not None:
                            try:
                                x, y = self.project_point(lon, lat, self.center_lon, self.center_lat, scale)
                                screen_points.append((x, y))
                            except (TypeError, ValueError):
                                continue

                    if len(screen_points) >= 2:
                        # Draw pushback path as magenta dashed line
                        for i in range(len(screen_points) - 1):
                            x1, y1 = screen_points[i]
                            x2, y2 = screen_points[i + 1]

                            # Draw dashed line
                            dx = x2 - x1
                            dy = y2 - y1
                            distance = math.sqrt(dx*dx + dy*dy)
                            if distance > 0:
                                dash_length = 5
                                gap_length = 3
                                num_dashes = int(distance / (dash_length + gap_length))

                                for j in range(num_dashes):
                                    t1 = j * (dash_length + gap_length) / distance
                                    t2 = min((j * (dash_length + gap_length) + dash_length) / distance, 1.0)
                                    dash_x1 = x1 + dx * t1
                                    dash_y1 = y1 + dy * t1
                                    dash_x2 = x1 + dx * t2
                                    dash_y2 = y1 + dy * t2
                                    pygame.draw.line(self.screen, (255, 0, 255),
                                                   (int(dash_x1), int(dash_y1)),
                                                   (int(dash_x2), int(dash_y2)), 2)

                        # Draw waypoint markers
                        for i, (x, y) in enumerate(screen_points):
                            pygame.draw.circle(self.screen, (255, 0, 255), (int(x), int(y)), 4, 2)
                            # Label first and last waypoints
                            if i == 0:
                                label_text = self.info_font.render(f"{gate.get('name', '')} Start", True, (255, 0, 255))
                                self.screen.blit(label_text, (x + 5, y - 15))
                            elif i == len(screen_points) - 1:
                                label_text = self.info_font.render("End", True, (255, 0, 255))
                                self.screen.blit(label_text, (x + 5, y - 15))

        # Draw hold short bars
        holdshort_bars = self.airport_data.get('holdshort_bars', [])
        for bar in holdshort_bars:
            points = bar.get('points', [])
            runway = bar.get('runway', '')
            if len(points) >= 2:
                screen_points = []
                for point in points:
                    lat = point.get('x')  # x is latitude
                    lon = point.get('y')  # y is longitude
                    if lat and lon:
                        x, y = self.project_point(lon, lat, self.center_lon, self.center_lat, scale)
                        screen_points.append((x, y))

                if len(screen_points) >= 2:
                    # Draw hold short bar as thick red dashed line
                    x1, y1 = screen_points[0]
                    x2, y2 = screen_points[1]

                    # Calculate line segments for dashed effect
                    line_length = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)

                    # Skip if line is too short (avoid division by zero)
                    if line_length < 1:
                        continue

                    dash_length = 10
                    gap_length = 5
                    num_dashes = int(line_length / (dash_length + gap_length))

                    dx = (x2 - x1) / line_length
                    dy = (y2 - y1) / line_length

                    for i in range(num_dashes + 1):
                        start_dist = i * (dash_length + gap_length)
                        end_dist = start_dist + dash_length

                        if start_dist < line_length:
                            start_x = x1 + dx * start_dist
                            start_y = y1 + dy * start_dist
                            end_x = x1 + dx * min(end_dist, line_length)
                            end_y = y1 + dy * min(end_dist, line_length)

                            pygame.draw.line(self.screen, (255, 0, 0),
                                           (int(start_x), int(start_y)),
                                           (int(end_x), int(end_y)), 4)

                    # Draw label for the hold short bar
                    mid_x = (x1 + x2) / 2
                    mid_y = (y1 + y2) / 2
                    label_text = self.info_font.render(f"HOLD RWY {runway}", True, (255, 0, 0))
                    self.screen.blit(label_text, (mid_x + 5, mid_y - 20))

        # Draw gates
        gates = self.airport_data.get('gates', [])
        for gate in gates:
            position = gate.get('position', {})
            lat = position.get('x')  # x is latitude
            lon = position.get('y')  # y is longitude
            degrees = gate.get('degrees', 0)
            name = gate.get('name', '')
            aircraft_type = gate.get('aircraft_type', '')

            if lat and lon:
                x, y = self.project_point(lon, lat, self.center_lon, self.center_lat, scale)

                # Draw gate position as a circle
                pygame.draw.circle(self.screen, (0, 255, 0), (x, y), 8, 2)

                # Draw direction indicator (nose direction)
                # Convert degrees to radians (0° = North, clockwise)
                angle_rad = math.radians(degrees - 90)  # Adjust for screen coordinates
                line_length = 20
                end_x = x + int(line_length * math.cos(angle_rad))
                end_y = y + int(line_length * math.sin(angle_rad))
                pygame.draw.line(self.screen, (0, 255, 0), (x, y), (end_x, end_y), 2)

                # Draw arrow head
                arrow_size = 8
                arrow_angle1 = angle_rad + math.radians(150)
                arrow_angle2 = angle_rad - math.radians(150)
                arrow_x1 = end_x + int(arrow_size * math.cos(arrow_angle1))
                arrow_y1 = end_y + int(arrow_size * math.sin(arrow_angle1))
                arrow_x2 = end_x + int(arrow_size * math.cos(arrow_angle2))
                arrow_y2 = end_y + int(arrow_size * math.sin(arrow_angle2))
                pygame.draw.line(self.screen, (0, 255, 0), (end_x, end_y), (arrow_x1, arrow_y1), 2)
                pygame.draw.line(self.screen, (0, 255, 0), (end_x, end_y), (arrow_x2, arrow_y2), 2)

                # Draw gate label
                label_text = self.info_font.render(name, True, (0, 255, 0))
                self.screen.blit(label_text, (x + 12, y - 8))

                # Draw aircraft type below
                if aircraft_type:
                    type_text = self.info_font.render(f"({aircraft_type})", True, (150, 255, 150))
                    self.screen.blit(type_text, (x + 12, y + 8))

        # Draw dev mode indicator
        dev_text = self.title_font.render("DEV MODE", True, (255, 0, 0))
        self.screen.blit(dev_text, (self.width // 2 - 80, 45))

    def _render_exit_confirmation(self):
        """Render exit confirmation dialog"""
        # Semi-transparent overlay
        overlay = pygame.Surface((self.width, self.height))
        overlay.set_alpha(180)
        overlay.fill((0, 0, 0))
        self.screen.blit(overlay, (0, 0))

        # Dialog box
        dialog_width = 400
        dialog_height = 150
        dialog_x = (self.width - dialog_width) // 2
        dialog_y = (self.height - dialog_height) // 2

        # Dialog background
        dialog_surface = pygame.Surface((dialog_width, dialog_height))
        dialog_surface.fill((25, 30, 35))
        pygame.draw.rect(dialog_surface, (100, 110, 120), (0, 0, dialog_width, dialog_height), 2)

        # Title
        title_text = self.info_font.render("Exit Simulation?", True, (255, 255, 255))
        title_rect = title_text.get_rect(center=(dialog_width // 2, 30))
        dialog_surface.blit(title_text, title_rect)

        # Message
        msg_text = self.tag_font.render("Return to airport selection menu?", True, (200, 200, 200))
        msg_rect = msg_text.get_rect(center=(dialog_width // 2, 65))
        dialog_surface.blit(msg_text, msg_rect)

        # Yes button
        yes_button_rect = pygame.Rect(50, 95, 120, 35)
        mouse_pos = pygame.mouse.get_pos()
        adjusted_mouse = (mouse_pos[0] - dialog_x, mouse_pos[1] - dialog_y)

        yes_hover = yes_button_rect.collidepoint(adjusted_mouse)
        yes_color = (180, 60, 60) if yes_hover else (140, 50, 50)
        pygame.draw.rect(dialog_surface, yes_color, yes_button_rect, border_radius=4)
        pygame.draw.rect(dialog_surface, (200, 80, 80), yes_button_rect, 2, border_radius=4)

        yes_text = self.tag_font.render("Yes", True, (255, 255, 255))
        yes_text_rect = yes_text.get_rect(center=yes_button_rect.center)
        dialog_surface.blit(yes_text, yes_text_rect)

        # No button
        no_button_rect = pygame.Rect(230, 95, 120, 35)
        no_hover = no_button_rect.collidepoint(adjusted_mouse)
        no_color = (60, 140, 60) if no_hover else (50, 110, 50)
        pygame.draw.rect(dialog_surface, no_color, no_button_rect, border_radius=4)
        pygame.draw.rect(dialog_surface, (80, 180, 80), no_button_rect, 2, border_radius=4)

        no_text = self.tag_font.render("No", True, (255, 255, 255))
        no_text_rect = no_text.get_rect(center=no_button_rect.center)
        dialog_surface.blit(no_text, no_text_rect)

        # Blit dialog to screen
        self.screen.blit(dialog_surface, (dialog_x, dialog_y))

    def _render_enhanced_dev_overlays(self):
        """Render enhanced developer mode overlays"""
        y_offset = 250
        x_offset = 10

        # Dev mode indicator
        dev_text = self.tag_font.render("DEV MODE", True, (255, 100, 100))
        self.screen.blit(dev_text, (x_offset, y_offset))
        y_offset += 25

        # FPS Display
        if self.dev_show_fps and self.dev_frame_times:
            avg_frame_time = sum(self.dev_frame_times) / len(self.dev_frame_times)
            fps = 1000 / avg_frame_time if avg_frame_time > 0 else 0
            fps_text = self.tag_font.render(f"FPS: {fps:.1f}", True, (100, 255, 100))
            self.screen.blit(fps_text, (x_offset, y_offset))
            y_offset += 20

        # Performance Stats
        if self.dev_show_performance_stats and self.dev_frame_times:
            avg_frame_time = sum(self.dev_frame_times) / len(self.dev_frame_times)
            min_frame_time = min(self.dev_frame_times)
            max_frame_time = max(self.dev_frame_times)

            perf_text1 = self.tag_font.render(f"Frame: {avg_frame_time:.2f}ms avg", True, (150, 200, 255))
            perf_text2 = self.tag_font.render(f"Min: {min_frame_time:.2f}ms Max: {max_frame_time:.2f}ms", True, (150, 200, 255))

            self.screen.blit(perf_text1, (x_offset, y_offset))
            y_offset += 20
            self.screen.blit(perf_text2, (x_offset, y_offset))
            y_offset += 20

            # Aircraft count
            if self.aircraft_manager:
                # Handle both dict and list formats
                if isinstance(self.aircraft_manager.aircraft, dict):
                    aircraft_count = len(self.aircraft_manager.aircraft)
                else:
                    aircraft_count = len(self.aircraft_manager.aircraft)
                count_text = self.tag_font.render(f"Aircraft: {aircraft_count}", True, (150, 200, 255))
                self.screen.blit(count_text, (x_offset, y_offset))
                y_offset += 20

            # Memory usage (if available)
            try:
                import psutil
                import os
                process = psutil.Process(os.getpid())
                mem_mb = process.memory_info().rss / 1024 / 1024
                mem_text = self.tag_font.render(f"Memory: {mem_mb:.1f} MB", True, (150, 200, 255))
                self.screen.blit(mem_text, (x_offset, y_offset))
                y_offset += 20
            except:
                pass

        # Aircraft paths
        if self.dev_show_aircraft_paths and self.aircraft_manager:
            self._render_aircraft_paths()

        # Graph nodes
        if self.dev_show_graph_nodes and self.airport_data:
            self._render_graph_nodes()

        # Collision zones
        if self.dev_show_collision_zones and self.aircraft_manager:
            self._render_collision_zones()

        # Hotkey legend
        legend_y = self.height - 300
        legend_texts = [
            "Dev Hotkeys:",
            "Ctrl+Shift+1: Toggle Dev Mode",
            "Ctrl+Shift+2: Toggle FPS",
            "Ctrl+Shift+3: Toggle Aircraft Paths",
            "Ctrl+Shift+4: Toggle Graph Nodes",
            "Ctrl+Shift+5: Toggle Collision Zones",
            "Ctrl+Shift+6: Toggle Performance Stats",
        ]

        for i, text in enumerate(legend_texts):
            color = (255, 255, 100) if i == 0 else (180, 180, 180)
            legend_text = self.tag_font.render(text, True, color)
            self.screen.blit(legend_text, (x_offset, legend_y + i * 18))

    def _render_graph_nodes(self):
        """Render airport graph nodes (taxiway intersections, gates, etc.)"""
        if not hasattr(self.aircraft_manager, 'airport_graph') or not self.aircraft_manager.airport_graph:
            return

        scale = self.get_scale()
        graph = self.aircraft_manager.airport_graph

        # Draw nodes from the custom AirportGraph structure
        for node_id, node in graph.nodes.items():
            if hasattr(node, 'position') and node.position:
                lat, lon = node.position
                x, y = self.project_point(lon, lat, self.center_lon, self.center_lat, scale)
                if x is not None and y is not None:
                    # Color code by node type
                    node_type = node.node_type if hasattr(node, 'node_type') else 'unknown'
                    colors = {
                        'gate': (100, 255, 100),
                        'taxiway': (100, 200, 255),
                        'runway': (255, 100, 100),
                        'ramp': (255, 255, 100),
                        'spot': (255, 150, 255),
                        'waypoint': (150, 150, 255),
                    }
                    color = colors.get(node_type, (200, 200, 200))

                    pygame.draw.circle(self.screen, color, (int(x), int(y)), 5)

                    # Draw node label
                    label = self.tag_font.render(str(node_id), True, color)
                    self.screen.blit(label, (int(x) + 8, int(y) - 8))

        # Draw edges
        for edge in graph.edges:
            if hasattr(edge, 'from_node') and hasattr(edge, 'to_node'):
                from_pos = edge.from_node.position
                to_pos = edge.to_node.position
                if from_pos and to_pos:
                    from_x, from_y = self.project_point(from_pos[1], from_pos[0], self.center_lon, self.center_lat, scale)
                    to_x, to_y = self.project_point(to_pos[1], to_pos[0], self.center_lon, self.center_lat, scale)
                    if from_x is not None and to_x is not None:
                        pygame.draw.line(self.screen, (100, 100, 150),
                                       (int(from_x), int(from_y)),
                                       (int(to_x), int(to_y)), 1)

    def _copy_coordinates_at_mouse(self, mouse_pos):
        """Convert screen position to lat/lon and copy to clipboard in JSON format"""
        coord = self._get_coordinate_at_mouse(mouse_pos)
        if not coord:
            print("Cannot copy coordinates: No map data loaded")
            return

        # Format as JSON
        json_string = f'{{"x": {coord["x"]:.6f}, "y": {coord["y"]:.6f}}}'

        # Copy to clipboard
        try:
            import pyperclip
            pyperclip.copy(json_string)
            print(f"Copied to clipboard: {json_string}")

            # Show visual feedback
            self._show_copy_feedback(mouse_pos, json_string)
        except ImportError:
            # Fallback if pyperclip not available - use tkinter
            try:
                import tkinter as tk
                root = tk.Tk()
                root.withdraw()
                root.clipboard_clear()
                root.clipboard_append(json_string)
                root.update()
                root.destroy()
                print(f"Copied to clipboard: {json_string}")
                self._show_copy_feedback(mouse_pos, json_string)
            except Exception as e:
                print(f"Could not copy to clipboard: {e}")
                print(f"Coordinates: {json_string}")

    def _show_copy_feedback(self, pos, text):
        """Show temporary visual feedback when coordinates are copied"""
        # Store feedback data to be rendered
        if not hasattr(self, 'copy_feedback'):
            self.copy_feedback = None

        self.copy_feedback = {
            'pos': pos,
            'text': text,
            'time': pygame.time.get_ticks(),
            'duration': 2000  # Show for 2 seconds
        }

    def _get_coordinate_at_mouse(self, mouse_pos):
        """Convert screen position to lat/lon and return as dict"""
        if self.center_lat is None or self.center_lon is None:
            return None

        scale = self.get_scale()
        mouse_x, mouse_y = mouse_pos
        lat_correction = math.cos(math.radians(self.center_lat))

        # Reverse the project_point calculation
        # Original: x = (lon - center_lon) * lat_correction * scale + width/2 + camera_x
        # Reverse:  lon = (x - width/2 - camera_x) / (lat_correction * scale) + center_lon
        lon = (mouse_x - self.width / 2 - self.camera_x) / (lat_correction * scale) + self.center_lon

        # Original: y = -(lat - center_lat) * scale + height/2 + camera_y
        # Reverse:  lat = center_lat - (y - height/2 - camera_y) / scale
        lat = self.center_lat - (mouse_y - self.height / 2 - self.camera_y) / scale

        return {"x": lat, "y": lon}

    def _add_coordinate_to_multi_copy(self, mouse_pos):
        """Add a coordinate to the multi-copy list"""
        coord = self._get_coordinate_at_mouse(mouse_pos)
        if coord:
            self.copied_coordinates.append(coord)
            print(f"Added coordinate {len(self.copied_coordinates)}: {{'x': {coord['x']:.6f}, 'y': {coord['y']:.6f}}}")

            # Show visual feedback for each point
            self._show_multi_copy_point(mouse_pos, len(self.copied_coordinates))

    def _finalize_multi_copy(self):
        """Finalize multi-copy mode and copy all coordinates to clipboard"""
        if not self.copied_coordinates:
            print("No coordinates to copy")
            self.multi_copy_mode = False
            return

        # Format as JSON array
        coord_strings = [f'{{"x": {c["x"]:.6f}, "y": {c["y"]:.6f}}}' for c in self.copied_coordinates]
        json_string = "[" + ", ".join(coord_strings) + "]"

        # Copy to clipboard
        try:
            import pyperclip
            pyperclip.copy(json_string)
            print(f"Copied {len(self.copied_coordinates)} coordinates to clipboard:")
            print(json_string)

            # Show feedback
            self._show_copy_feedback((self.width // 2, 100), f"{len(self.copied_coordinates)} coordinates copied!")
        except ImportError:
            try:
                import tkinter as tk
                root = tk.Tk()
                root.withdraw()
                root.clipboard_clear()
                root.clipboard_append(json_string)
                root.update()
                root.destroy()
                print(f"Copied {len(self.copied_coordinates)} coordinates to clipboard:")
                print(json_string)
                self._show_copy_feedback((self.width // 2, 100), f"{len(self.copied_coordinates)} coordinates copied!")
            except Exception as e:
                print(f"Could not copy to clipboard: {e}")
                print(f"Coordinates: {json_string}")

        # Reset multi-copy mode
        self.multi_copy_mode = False
        self.copied_coordinates = []

    def _show_multi_copy_point(self, pos, number):
        """Show a numbered marker at the clicked position"""
        # Store markers to be rendered
        if not hasattr(self, 'multi_copy_markers'):
            self.multi_copy_markers = []

        self.multi_copy_markers.append({
            'pos': pos,
            'number': number,
            'time': pygame.time.get_ticks()
        })

    def handle_display_change(self, new_size, is_fullscreen):
        """Handle display size changes and fullscreen transitions"""
        self.width, self.height = new_size
        if self.dev_mode:
            print(f"Display changed: {new_size[0]}x{new_size[1]}, fullscreen: {is_fullscreen}")

        # Update font sizes if needed for new resolution
        self._update_font_sizes()

        # Update panel positions and sizes
        self._update_panel_positions()

    def handle_resize(self, new_size):
        """Handle window resize events (windowed mode only)"""
        self.width, self.height = new_size
        if self.dev_mode:
            print(f"Window resized: {new_size[0]}x{new_size[1]}")

        # Update panel positions
        self._update_panel_positions()

    def _update_font_sizes(self):
        """Update font sizes based on current display resolution"""
        # This could be implemented to scale fonts based on resolution
        pass

    def _update_panel_positions(self):
        """Update panel positions based on current display size"""
        # Update flight plan panel if it exists
        if self.flight_plan_panel:
            self.flight_plan_panel.screen_width = self.width
            self.flight_plan_panel.screen_height = self.height
            # Center panel if needed
            self.flight_plan_panel.panel_x = (self.width - self.flight_plan_panel.panel_width) // 2
            self.flight_plan_panel.panel_y = 100

    def load_aircraft_image(self):
        """Load aircraft icon images at full resolution for quality scaling"""
        # Try airplane_icon_norm.png first (converted from SVG), then fallback to old aircraft_norm.png
        aircraft_paths = [
            "data/images/aircraft_icon_norm.png",
            "data/images/aircraft_norm.png"
        ]

        try:
            for aircraft_image_path in aircraft_paths:
                if os.path.exists(aircraft_image_path):
                    # Load the original image at FULL resolution
                    # Don't pre-scale - we'll scale it once during rendering for maximum quality
                    self.aircraft_image = pygame.image.load(aircraft_image_path).convert_alpha()
                    print(f"Loaded aircraft image: {aircraft_image_path} at {self.aircraft_image.get_size()}")
                    break

            if not self.aircraft_image:
                print("Aircraft image not found. Checked:")
                for path in aircraft_paths:
                    print(f"  - {path}")
                print("Will use fallback triangle shape")
        except Exception as e:
            print(f"Error loading aircraft image: {e}")
            print("Will use fallback triangle shape")

        # Load unknown aircraft icon
        unknown_image_path = "data/images/aircraft_icon_unknown.png"
        if os.path.exists(unknown_image_path):
            try:
                self.aircraft_unknown_image = pygame.image.load(unknown_image_path).convert_alpha()
                print(f"Loaded unknown aircraft image: {unknown_image_path} at {self.aircraft_unknown_image.get_size()}")
            except Exception as e:
                print(f"Error loading unknown aircraft image: {e}")
                self.aircraft_unknown_image = None
        else:
            print(f"Unknown aircraft image not found: {unknown_image_path}")
            self.aircraft_unknown_image = None
