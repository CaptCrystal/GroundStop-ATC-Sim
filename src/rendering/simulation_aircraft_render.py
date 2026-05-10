"""
Aircraft rendering mixin for SimulationScreen
"""
import pygame
import math
import os


class AircraftRenderMixin:
    """Mixin providing aircraft rendering and caching methods for SimulationScreen."""

    def pre_cache_rendering_data(self):
        """Pre-cache expensive rendering operations during loading screen"""
        try:
            # Cache common text renders
            common_texts = [
                "HOLD", "TAXI", "LINEUP", "CLEARED", "TAKEOFF", "LANDING",
                "GA APRON", "RWY", "TWY", "GATE", "N", "S", "E", "W"
            ]

            for text in common_texts:
                if self.info_font:
                    self.render_cache['font_cache'][text] = self.info_font.render(text, True, (255, 255, 255))

            # Pre-calculate scale for current viewport
            if self.bounds:
                scale = self.get_scale()
                self.render_cache['scale_cache']['default'] = scale
                self.render_cache['last_zoom'] = self.zoom
                self.render_cache['last_camera'] = (self.camera_x, self.camera_y)

            # Pre-render GA apron if available
            if self.airport_data and 'ga_apron' in self.airport_data:
                self._cache_ga_apron_surface()

            # Pre-compute airport element positions
            if self.airport_data:
                self._cache_airport_elements()

            print("Pre-caching complete - rendering optimized")

        except Exception as e:
            print(f"Warning: Pre-caching failed: {e}")
            # Non-critical, continue anyway

    def _cache_ga_apron_surface(self):
        """Pre-render GA apron to a surface for faster drawing"""
        try:
            ga_apron = self.airport_data.get('ga_apron', [])
            if not ga_apron or len(ga_apron) < 3 or not self.bounds:
                return

            scale = self.get_scale()

            # Convert GA apron points to screen coordinates
            screen_points = []
            for point in ga_apron:
                if isinstance(point, dict):
                    lat = point.get('x')
                    lon = point.get('y')
                elif isinstance(point, (list, tuple)) and len(point) >= 2:
                    lat, lon = point[0], point[1]
                else:
                    continue

                if lat and lon:
                    x, y = self.project_point(lon, lat, self.center_lon, self.center_lat, scale)
                    if x is not None and y is not None:
                        screen_points.append((int(x), int(y)))

            if len(screen_points) >= 3:
                # Store the screen points for quick rendering
                self.render_cache['ga_apron_points'] = screen_points

        except Exception as e:
            print(f"Warning: GA apron caching failed: {e}")

    def _cache_airport_elements(self):
        """Pre-compute positions of airport elements for faster rendering"""
        try:
            if not self.bounds:
                return

            scale = self.get_scale()
            cache = {}

            # Cache gate positions
            gates = self.airport_data.get('gates', [])
            gate_positions = []
            for gate in gates:
                position = gate.get('position', {})
                lat = position.get('x')
                lon = position.get('y')
                if lat and lon:
                    x, y = self.project_point(lon, lat, self.center_lon, self.center_lat, scale)
                    if x is not None and y is not None:
                        gate_positions.append({
                            'screen_pos': (x, y),
                            'name': gate.get('name', ''),
                            'heading': gate.get('degrees', 0)
                        })
            cache['gates'] = gate_positions

            # Cache taxiway line segments
            taxiways = self.airport_data.get('taxiways', [])
            taxiway_lines = []
            for taxiway in taxiways:
                points = taxiway.get('points', [])
                if len(points) >= 2:
                    screen_points = []
                    for point in points:
                        lat = point.get('x')
                        lon = point.get('y')
                        if lat and lon:
                            x, y = self.project_point(lon, lat, self.center_lon, self.center_lat, scale)
                            if x is not None and y is not None:
                                screen_points.append((x, y))
                    if len(screen_points) >= 2:
                        taxiway_lines.append({
                            'points': screen_points,
                            'name': taxiway.get('taxiway', '')
                        })
            cache['taxiways'] = taxiway_lines

            self.render_cache['airport_surfaces'] = cache

        except Exception as e:
            print(f"Warning: Airport element caching failed: {e}")

    def invalidate_cache(self):
        """Invalidate render cache when zoom or camera changes significantly"""
        # Check if zoom or camera changed enough to invalidate cache
        if (self.render_cache['last_zoom'] is None or
            abs(self.zoom - self.render_cache['last_zoom']) > 0.1 or
            self.render_cache['last_camera'][0] is None or
            abs(self.camera_x - self.render_cache['last_camera'][0]) > 100 or
            abs(self.camera_y - self.render_cache['last_camera'][1]) > 100):

            # Clear position-dependent caches
            self.render_cache['ga_apron_points'] = None
            self.render_cache['airport_surfaces'] = {}
            self.render_cache['last_zoom'] = self.zoom
            self.render_cache['last_camera'] = (self.camera_x, self.camera_y)

            # Recache if needed
            if self.airport_data:
                if 'ga_apron' in self.airport_data:
                    self._cache_ga_apron_surface()
                self._cache_airport_elements()

    def render_ga_apron(self):
        """Render the GA apron boundary polygon"""
        if not self.airport_data or self.center_lat is None or self.center_lon is None:
            return

        # Use cached screen points if available
        screen_points = self.render_cache.get('ga_apron_points')

        # If cache is invalid or missing, recalculate
        if screen_points is None:
            ga_apron = self.airport_data.get('ga_apron', [])
            if not ga_apron or len(ga_apron) < 3:
                return

            scale = self.get_scale()

            # Convert GA apron points to screen coordinates
            screen_points = []
            for point in ga_apron:
                if isinstance(point, dict):
                    lat = point.get('x')
                    lon = point.get('y')
                elif isinstance(point, (list, tuple)) and len(point) >= 2:
                    lat, lon = point[0], point[1]
                else:
                    continue

                if lat and lon:
                    x, y = self.project_point(lon, lat, self.center_lon, self.center_lat, scale)
                    if x is not None and y is not None:
                        screen_points.append((int(x), int(y)))

            # Cache for next frame
            self.render_cache['ga_apron_points'] = screen_points

        if len(screen_points) >= 3:
            # Draw semi-transparent filled polygon
            ga_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            pygame.draw.polygon(ga_surface, (100, 255, 100, 40), screen_points)  # Light green with transparency
            self.screen.blit(ga_surface, (0, 0))

            # Draw boundary outline
            pygame.draw.polygon(self.screen, (0, 224, 21), screen_points, 2)  # ASDE green outline

            # Draw label at centroid
            if screen_points:
                centroid_x = sum(p[0] for p in screen_points) / len(screen_points)
                centroid_y = sum(p[1] for p in screen_points) / len(screen_points)

                # Use cached text if available
                if "GA APRON" in self.render_cache['font_cache']:
                    label_text = self.render_cache['font_cache']["GA APRON"]
                    # Re-render with correct color if cached version is wrong color
                    if label_text.get_at((0, 0))[:3] != (0, 224, 21):
                        label_text = self.info_font.render("GA APRON", True, (0, 224, 21))
                        self.render_cache['font_cache']["GA APRON_green"] = label_text
                else:
                    label_text = self.info_font.render("GA APRON", True, (0, 224, 21))

                label_rect = label_text.get_rect(center=(int(centroid_x), int(centroid_y)))

                # Draw semi-transparent background for label
                bg_rect = label_rect.inflate(10, 5)
                label_bg = pygame.Surface((bg_rect.width, bg_rect.height), pygame.SRCALPHA)
                label_bg.fill((10, 15, 25, 180))
                self.screen.blit(label_bg, bg_rect)

                # Draw label text
                self.screen.blit(label_text, label_rect)

    def render_aircraft(self):
        """Render all aircraft as sleek white airplane icons"""
        if not self.aircraft_manager or self.center_lat is None or self.center_lon is None:
            return

        scale = self.get_scale()

        for aircraft in self.aircraft_manager.get_all_aircraft():
            # Use visual position for smooth rendering instead of actual position
            # This eliminates jerky coordinate-to-coordinate movement
            if hasattr(aircraft, 'visual_position') and aircraft.visual_position:
                lat, lon = aircraft.visual_position
            else:
                lat, lon = aircraft.position

            x, y = self.project_point(lon, lat, self.center_lon, self.center_lat, scale)

            # Keep floating point precision for smooth movement
            # Don't round - let pygame handle sub-pixel rendering

            if x < 0 or x > self.width or y < 0 or y > self.height:
                continue

            # Calculate icon scale based on zoom level
            # Scale factor reduced to keep icons smaller (0.3x of zoom level)
            icon_scale = self.zoom * 0.5

            # Check if mouse is hovering over this aircraft (for hover circle)
            is_hovered = False
            hover_radius = int(5 * icon_scale)  # Scale hover detection with zoom
            if hasattr(self, 'mouse_pos') and self.mouse_pos:
                mouse_x, mouse_y = self.mouse_pos
                dist_to_mouse = math.sqrt((mouse_x - x)**2 + (mouse_y - y)**2)
                if dist_to_mouse <= hover_radius:
                    is_hovered = True

            # Draw hover circle if mouse is over aircraft (scaled with zoom)
            if is_hovered:
                circle_radius = int(5 * icon_scale)
                pygame.draw.circle(self.screen, (0, 255, 0), (int(x), int(y)), circle_radius, 1)
                if pygame.key.get_pressed()[pygame.K_1]:
                    self.show_aircraft_editor = True
                    self.editor_aircraft = aircraft
                    self.editor_field_values = {}
                    self.editor_edited_fields = set()
                    self.editor_selected_index = 0
                    self.editor_scratch_alternate_time = pygame.time.get_ticks() / 1000.0 + 3.0
                    self.editor_show_scratch_one = True

            # Determine if aircraft should show as unknown
            # Unknown = NOT squawking Mode C (regardless of code)
            is_unknown = False
            if hasattr(aircraft, 'squawking_mode_c'):
                if not aircraft.squawking_mode_c:
                    # Not squawking Mode C - show unknown icon
                    is_unknown = True

            # Draw aircraft using image if available, otherwise fallback to simple shape
            if is_unknown and self.aircraft_unknown_image:
                # Draw unknown icon (cyan pentagon) - rotate to match heading
                target_size = int(20 * icon_scale)
                scaled_image = pygame.transform.smoothscale(self.aircraft_unknown_image, (target_size, target_size))
                # Rotate to match aircraft heading
                heading_to_use = aircraft.visual_heading if hasattr(aircraft, 'visual_heading') else aircraft.heading
                rotated_image = pygame.transform.rotate(scaled_image, -heading_to_use)
                image_rect = rotated_image.get_rect(center=(x, y))
                self.screen.blit(rotated_image, image_rect)
            elif self.aircraft_image:
                # Calculate target size based on zoom
                target_size = int(20 * icon_scale)  # Base size of 40px scaled by zoom

                # First, smoothscale the full-resolution image to target size
                # This preserves quality by downsampling from high resolution
                scaled_image = pygame.transform.smoothscale(self.aircraft_image, (target_size, target_size))

                # Then rotate the scaled image
                # Pygame rotates counter-clockwise, and heading 0° = North (up)
                # So we negate the heading to rotate correctly
                # Use visual heading for smooth rotation
                heading_to_use = aircraft.visual_heading if hasattr(aircraft, 'visual_heading') else aircraft.heading
                rotated_image = pygame.transform.rotate(scaled_image, -heading_to_use)

                # Use floating point center for sub-pixel positioning
                image_rect = rotated_image.get_rect(center=(x, y))
                self.screen.blit(rotated_image, image_rect)
            else:
                # Fallback: simple triangle if image not loaded
                size = 12 * icon_scale
                heading_rad = math.radians(aircraft.heading)
                points = [
                    (x + size * math.sin(heading_rad), y - size * math.cos(heading_rad)),
                    (x + size * math.sin(heading_rad + 2.5), y - size * math.cos(heading_rad + 2.5)),
                    (x + size * math.sin(heading_rad - 2.5), y - size * math.cos(heading_rad - 2.5))
                ]
                pygame.draw.polygon(self.screen, (255, 255, 255), points)

            # Check if datatag and leader line should be shown
            # Show datatag only when squawking Mode C (even with wrong/no code)
            show_datatag = getattr(aircraft, 'show_datatag', True)
            if hasattr(aircraft, 'squawking_mode_c'):
                if not aircraft.squawking_mode_c:
                    show_datatag = False  # Hide datatag when not squawking Mode C

            if show_datatag:
                # Get tag position based on aircraft's tag_direction
                tag_direction = getattr(aircraft, 'tag_direction', 8)  # Default to North
                # Use leader line length from top menu bar if available
                # Leader line should be constant visual length regardless of zoom
                base_leader_distance = self.top_menu_bar.leader_line_length if self.top_menu_bar else 60

                # Sticky data tag logic:
                # Tag and leader line stay centered on aircraft icon until aircraft moves > 10 pixels away
                # We store the anchor screen position (center of icon where tag was anchored)
                sticky_box_radius = 2  # pixels - radius around center where tag stays fixed

                # Check if we need to recenter the tag
                need_recenter = False

                if aircraft.tag_anchor_world_pos is None:
                    # No anchor yet, need to set one at current aircraft center
                    need_recenter = True
                else:
                    # Check if aircraft has moved outside the 10-pixel radius from anchor center
                    # Convert the anchor world position to current screen coordinates
                    anchor_lat, anchor_lon = aircraft.tag_anchor_world_pos
                    anchor_screen_x, anchor_screen_y = self.project_point(anchor_lon, anchor_lat, self.center_lon, self.center_lat, scale)

                    # Calculate distance from anchor center to current aircraft position
                    dx = x - anchor_screen_x
                    dy = y - anchor_screen_y
                    distance = math.sqrt(dx*dx + dy*dy)

                    if distance > sticky_box_radius:
                        need_recenter = True

                if need_recenter:
                    # Recenter: store current world position as new anchor center
                    aircraft.tag_anchor_world_pos = (lat, lon)
                    anchor_center_x = x
                    anchor_center_y = y
                else:
                    # Use the stored anchor center position (convert from world to screen)
                    anchor_lat, anchor_lon = aircraft.tag_anchor_world_pos
                    anchor_center_x, anchor_center_y = self.project_point(anchor_lon, anchor_lat, self.center_lon, self.center_lat, scale)

                # Calculate tag position from anchor center (not current aircraft position)
                tag_offset_x, tag_offset_y = self.get_tag_offset(tag_direction, distance=base_leader_distance)
                tag_x = anchor_center_x + tag_offset_x
                tag_y = anchor_center_y + tag_offset_y

                # Draw aircraft data tag
                # - Mode C + correct code: Full tag = CALLSIGN (line 1) + AIRCRAFT_TYPE (line 2)
                # - Mode C + wrong/no code: Code-only tag = just the squawk code (single line, like first image)
                callsign = aircraft.get_callsign()
                exit_fix = ""
                if hasattr(aircraft, 'exit_fix') and aircraft.exit_fix:
                    exit_fix = aircraft.exit_fix[:3].upper()  # First 3 letters

                # Determine if Mode C + correct code vs Mode C + wrong code
                code_only_tag = False  # Show only squawk code (like first image)
                if hasattr(aircraft, 'squawking_mode_c') and aircraft.squawking_mode_c:
                    has_correct_code = False
                    if hasattr(aircraft, 'current_squawk_code') and aircraft.current_squawk_code:
                        if hasattr(aircraft, 'correct_squawk_code') and aircraft.correct_squawk_code:
                            correct_code_str = str(aircraft.correct_squawk_code).zfill(4)
                            current_code_str = str(aircraft.current_squawk_code).zfill(4)
                            if current_code_str == correct_code_str:
                                has_correct_code = True

                    if not has_correct_code:
                        # Mode C + wrong/no code: Code-only datatag (first image - just squawk code)
                        code_only_tag = True

                if code_only_tag:
                    # Single line: only the squawk code (e.g. "1417")
                    code_text = aircraft.current_squawk_code if (hasattr(aircraft, 'current_squawk_code') and aircraft.current_squawk_code) else "----"
                    label1 = self.tag_font.render(code_text, True, (0, 255, 0))
                    label2 = None  # No second line
                else:
                    # Full tag: CALLSIGN + AIRCRAFT_TYPE (second image)
                    first_line = callsign
                    default_second = f"{aircraft.aircraft_type} {exit_fix}" if exit_fix else f"{aircraft.aircraft_type}"
                    sp1 = (getattr(aircraft, 'scratch_pad_1', None) or '').strip()
                    if sp1:
                        # Alternate bottom line with scratch pad 1 every 3 sec
                        t_sec = pygame.time.get_ticks() // 3000
                        second_line = sp1 if (t_sec % 2 == 1) else default_second
                    else:
                        second_line = default_second
                    label1 = self.tag_font.render(first_line, True, (0, 255, 0))
                    label2 = self.tag_font.render(second_line, True, (0, 255, 0))

                # Check if tag is on left side (positions 7, 4, 1)
                is_left_side = tag_direction in [7, 4, 1]
                margin = 5  # pixels between leader line endpoint and text
                line_spacing = 16  # pixels between first and second line

                if is_left_side:
                    label1_rect = label1.get_rect(right=tag_x - margin, centery=tag_y)
                    if label2:
                        label2_rect = label2.get_rect(right=tag_x - margin, centery=tag_y + line_spacing)
                    else:
                        label2_rect = None
                else:
                    label1_rect = label1.get_rect(left=tag_x + margin, centery=tag_y)
                    if label2:
                        label2_rect = label2.get_rect(left=tag_x + margin, centery=tag_y + line_spacing)
                    else:
                        label2_rect = None

                # Calculate leader line endpoints
                # Start from outside the aircraft icon with a constant gap (not scaled with zoom)
                leader_start_radius = 0.5   # Fixed pixel distance from aircraft center

                # Calculate direction vector from anchor center to tag (not current aircraft position)
                dx = tag_x - anchor_center_x
                dy = tag_y - anchor_center_y
                distance = math.sqrt(dx*dx + dy*dy)

                if distance > 0:
                    # Normalize direction
                    dx_norm = dx / distance
                    dy_norm = dy / distance

                    # Start point: outside the anchor center with gap
                    line_start_x = anchor_center_x + dx_norm * leader_start_radius
                    line_start_y = anchor_center_y + dy_norm * leader_start_radius

                    # End point: attach to appropriate side of text
                    if is_left_side:
                        # Attach to right side of callsign
                        line_end_x = label1_rect.right
                    else:
                        # Attach to left side of callsign (tag anchor)
                        line_end_x = tag_x
                    line_end_y = label1_rect.centery

                    # Draw leader line from aircraft edge to text (thicker for better visibility)
                    pygame.draw.line(self.screen, (0, 255, 0),
                                   (int(line_start_x), int(line_start_y)),
                                   (int(line_end_x), int(line_end_y)), 2)

                # Draw labels
                self.screen.blit(label1, label1_rect)
                if label2 is not None and label2_rect is not None:
                    self.screen.blit(label2, label2_rect)

    def get_aircraft_at_position(self, mouse_pos):
        """Find aircraft at mouse position (with some tolerance)"""
        if not self.aircraft_manager or self.center_lat is None or self.center_lon is None:
            return None

        scale = self.get_scale()
        mouse_x, mouse_y = mouse_pos
        click_tolerance = 20  # pixels

        for aircraft in self.aircraft_manager.get_all_aircraft():
            lat, lon = aircraft.position
            x, y = self.project_point(lon, lat, self.center_lon, self.center_lat, scale)

            # Check if click is within tolerance of aircraft
            distance = math.sqrt((mouse_x - x)**2 + (mouse_y - y)**2)
            if distance <= click_tolerance:
                return aircraft

        return None

    def get_tag_offset(self, direction, distance=60):
        """Get x,y offset for tag based on numpad direction"""
        # Numpad layout: 7 8 9
        #                4   6
        #                1 2 3
        offsets = {
            8: (0, -distance),      # North
            6: (distance, 0),       # East
            2: (0, distance),       # South
            4: (-distance, 0),      # West
            9: (distance * 0.7, -distance * 0.7),   # Northeast
            3: (distance * 0.7, distance * 0.7),    # Southeast
            1: (-distance * 0.7, distance * 0.7),   # Southwest
            7: (-distance * 0.7, -distance * 0.7),  # Northwest
        }
        return offsets.get(direction, (0, -distance))  # Default to North

    def render_aircraft_editor(self):
        """Render the aircraft editor on the left: green font, no background. All fields update in real time from the aircraft."""
        if not self.show_aircraft_editor:
            return

        # Always sync from aircraft every frame so beacon, state, FIX, SP1, SP2 etc. reflect live
        if self.editor_aircraft:
            self._editor_sync_from_aircraft()

        green = (0, 255, 0)
        x_left = 20
        y = 260
        line_height = 22
        field_keys = ['AC', 'BCN', 'CAT', 'TYP', 'FIX', 'SP1', 'SP2']
        labels = ['A/C', 'BCN', 'CAT', 'TYP', 'FIX', 'SP1', 'SP2']

        # Live status line (updates in real time, read-only)
        if self.dev_mode == True:
            sta = self.editor_field_values.get('STA', '')
            self.screen.blit(self.info_font.render(f"STA: {sta}", True, green), (x_left, y))
            y += line_height + 4

        sp1 = self.editor_field_values.get('SP1', '')
        sp2 = self.editor_field_values.get('SP2', '')
        both_scratch = bool(sp1 and sp2)
        if both_scratch:
            t = pygame.time.get_ticks() / 1000.0
            if t >= self.editor_scratch_alternate_time:
                self.editor_scratch_alternate_time = t + 3.0
                self.editor_show_scratch_one = not self.editor_show_scratch_one

        for i, (key, label) in enumerate(zip(field_keys, labels)):
            val = self.editor_field_values.get(key, '')
            if key == 'SP2' and both_scratch:
                continue
            if key == 'SP1' and both_scratch:
                if self.editor_selected_index == 5:
                    display_val, label_show = sp1, 'SP1'
                elif self.editor_selected_index == 6:
                    display_val, label_show = sp2, 'SP2'
                else:
                    display_val = sp1 if self.editor_show_scratch_one else sp2
                    label_show = 'SP1' if self.editor_show_scratch_one else 'SP2'
            else:
                display_val = val
                label_show = label
            is_selected = (i == self.editor_selected_index)
            text = f"{label_show}: {display_val}"
            if is_selected:
                text += "_"
            self.screen.blit(self.info_font.render(text, True, green), (x_left, y))
            y += line_height

    def _editor_sync_from_aircraft(self):
        """Sync editor field values from the current editor aircraft (real-time). Don't overwrite fields with unconfirmed edits."""
        if not self.editor_aircraft:
            return
        ac = self.editor_aircraft
        bcn = ac.beacon or ac.current_squawk_code
        bcn_str = str(bcn).strip() if bcn is not None else ''
        synced = {
            'AC': getattr(ac, 'callsign_override', None) or ac.get_callsign(),
            'BCN': bcn_str,
            'CAT': getattr(ac, 'wake_category', '') or '',
            'TYP': getattr(ac, 'aircraft_type', '') or '',
            'FIX': (ac.exit_fix or '').strip() if ac.exit_fix else '',
            'SP1': (getattr(ac, 'scratch_pad_1', None) or '').strip() if getattr(ac, 'scratch_pad_1', None) else '',
            'SP2': (getattr(ac, 'scratch_pad_2', None) or '').strip() if getattr(ac, 'scratch_pad_2', None) else '',
            'STA': getattr(ac, 'state', '') or '',
        }
        for k in self.editor_edited_fields:
            synced[k] = self.editor_field_values.get(k, synced.get(k, ''))
        self.editor_field_values = synced

    def _editor_apply_to_aircraft(self, key: str, value: str):
        """Apply one editor field value to the aircraft."""
        if not self.editor_aircraft:
            return
        ac = self.editor_aircraft
        if key == 'AC':
            setattr(ac, 'callsign_override', value if value else None)
        elif key == 'BCN':
            # BCN = squawk code assigned to this flight plan (what the strip says). Radar sees
            # current_squawk_code (what the transponder is actually sending). When we change BCN
            # we change the flight plan's code only → radar still sees the old code → mismatch →
            # "that aircraft is just squawking some random code" → code-only datatag (no callsign).
            ac.beacon = value
            if value and len(value) == 4 and value.isdigit():
                ac.correct_squawk_code = value  # flight plan's assigned squawk
                # Do NOT set current_squawk_code; prevent aircraft update from auto-correcting it
                setattr(ac, 'editor_bcn_override', True)
        elif key == 'CAT':
            if value in ('L', 'M', 'H'):
                ac.wake_category = value
        elif key == 'TYP':
            ac.aircraft_type = value
        elif key == 'FIX':
            ac.exit_fix = value or None
        elif key == 'SP1':
            setattr(ac, 'scratch_pad_1', value)
        elif key == 'SP2':
            setattr(ac, 'scratch_pad_2', value)

    def _render_aircraft_paths(self):
        """Render aircraft taxi routes and waypoints"""
        if not self.aircraft_manager or self.center_lat is None:
            return

        scale = self.get_scale()

        # Handle both dict and list formats for aircraft storage
        aircraft_list = self.aircraft_manager.aircraft.values() if isinstance(self.aircraft_manager.aircraft, dict) else self.aircraft_manager.aircraft

        for aircraft in aircraft_list:
            if hasattr(aircraft, 'route') and aircraft.route:
                # Draw route as connected line
                points = []
                for waypoint in aircraft.route:
                    lat, lon = waypoint
                    x, y = self.project_point(lon, lat, self.center_lon, self.center_lat, scale)
                    if x is not None and y is not None:
                        points.append((int(x), int(y)))

                if len(points) > 1:
                    # Draw route line
                    pygame.draw.lines(self.screen, (255, 255, 0), False, points, 2)

                    # Draw waypoint markers
                    for point in points:
                        pygame.draw.circle(self.screen, (255, 200, 0), point, 4)

    def _render_collision_zones(self):
        """Render aircraft collision detection zones"""
        if not self.aircraft_manager or self.center_lat is None:
            return

        scale = self.get_scale()

        # Handle both dict and list formats for aircraft storage
        aircraft_list = self.aircraft_manager.aircraft.values() if isinstance(self.aircraft_manager.aircraft, dict) else self.aircraft_manager.aircraft

        for aircraft in aircraft_list:
            lat, lon = aircraft.position
            x, y = self.project_point(lon, lat, self.center_lon, self.center_lat, scale)

            if x is not None and y is not None:
                # Draw collision radius (approximate)
                collision_radius_meters = 50  # Approximate collision radius
                collision_radius_pixels = collision_radius_meters * scale / 111000

                pygame.draw.circle(self.screen, (255, 100, 100), (int(x), int(y)),
                                 int(collision_radius_pixels), 1)

    def _update_hover_detection(self):
        """Detect which aircraft is being hovered over (dev mode + paused only)"""
        if not self.aircraft_manager or self.center_lat is None or self.center_lon is None:
            self.hovered_aircraft = None
            return

        scale = self.get_scale()
        mouse_x, mouse_y = self.mouse_pos
        hover_radius = 20  # pixels

        # Find closest aircraft to mouse
        closest_aircraft = None
        closest_distance = hover_radius

        for aircraft in self.aircraft_manager.get_all_aircraft():
            lat, lon = aircraft.position
            x, y = self.project_point(lon, lat, self.center_lon, self.center_lat, scale)

            # Calculate distance from mouse to aircraft
            distance = math.sqrt((x - mouse_x)**2 + (y - mouse_y)**2)

            if distance < closest_distance:
                closest_distance = distance
                closest_aircraft = aircraft

        self.hovered_aircraft = closest_aircraft

    def _render_aircraft_info_panel(self, aircraft):
        """Render detailed aircraft information panel (dev mode + paused + hover)"""
        import time

        # Panel dimensions
        panel_width = 350
        panel_height = 280
        panel_x = self.mouse_pos[0] + 20
        panel_y = self.mouse_pos[1] + 20

        # Keep panel on screen
        if panel_x + panel_width > self.width:
            panel_x = self.mouse_pos[0] - panel_width - 20
        if panel_y + panel_height > self.height:
            panel_y = self.height - panel_height - 10

        # Semi-transparent background
        panel_surface = pygame.Surface((panel_width, panel_height))
        panel_surface.set_alpha(240)
        panel_surface.fill((25, 30, 40))

        # Border
        pygame.draw.rect(panel_surface, (100, 180, 255), (0, 0, panel_width, panel_height), 2)

        # Title
        title_text = self.info_font.render(f"Aircraft: {aircraft.get_callsign()}", True, (100, 200, 255))
        panel_surface.blit(title_text, (10, 10))

        # Separator line
        pygame.draw.line(panel_surface, (60, 80, 100), (10, 35), (panel_width - 10, 35), 1)

        # Information lines
        y_offset = 45
        line_height = 20

        info_lines = [
            f"Type: {aircraft.aircraft_type}",
            f"Airline: {aircraft.airline}",
            f"Gate: {aircraft.gate if aircraft.gate else 'N/A'}",
            f"State: {aircraft.state}",
            f"Speed: {aircraft.speed:.1f} kts",
            f"Heading: {aircraft.heading:.0f}°",
            f"Position: {aircraft.position[0]:.6f}, {aircraft.position[1]:.6f}",
            f"Destination: {aircraft.destination if aircraft.destination else 'N/A'}",
            f"Exit Fix: {aircraft.exit_fix if aircraft.exit_fix else 'N/A'}",
            f"Expected Runway: {aircraft.expected_runway if aircraft.expected_runway else 'N/A'}",
            f"Cleared to Pushback: {'Yes' if aircraft.cleared_to_pushback else 'No'}",
            f"Cleared to Taxi: {'Yes' if aircraft.cleared_to_taxi else 'No'}",
            f"Taxi Destination: {aircraft.taxi_destination if aircraft.taxi_destination else 'N/A'}",
            f"TTS Voice: {aircraft.tts_voice}"
        ]

        for line in info_lines:
            text = self.tag_font.render(line, True, (200, 220, 240))
            panel_surface.blit(text, (10, y_offset))
            y_offset += line_height

        self.screen.blit(panel_surface, (panel_x, panel_y))

    def _render_thinking_panel(self):
        """Render the aircraft thinking / AI intent panel (toggle with I key)"""
        if not self.aircraft_manager:
            return
        ac_data = getattr(self.aircraft_manager, 'aircraft', [])
        aircraft_list = list(ac_data.values()) if isinstance(ac_data, dict) else list(ac_data)
        if not aircraft_list:
            return

        # State colors
        STATE_COLORS = {
            'parked':   (120, 120, 180),
            'pushback': (200, 160,  60),
            'holding':  (200, 200,  60),
            'taxi':     (100, 210, 100),
            'takeoff':  (255, 140,  50),
            'approach': ( 80, 180, 255),
            'landing':  (255, 100, 100),
            'departed': (140, 140, 140),
        }

        row_h = 46
        panel_w = 400
        header_h = 28
        panel_h = header_h + len(aircraft_list) * row_h + 10
        panel_x = self.width - panel_w - 6
        panel_y = 60  # below top bar

        # Clamp height to screen
        max_h = self.height - panel_y - 10
        visible_rows = min(len(aircraft_list), max(1, (max_h - header_h - 10) // row_h))
        panel_h = header_h + visible_rows * row_h + 10

        panel_surf = pygame.Surface((panel_w, panel_h))
        panel_surf.set_alpha(230)
        panel_surf.fill((18, 22, 30))
        pygame.draw.rect(panel_surf, (60, 100, 160), (0, 0, panel_w, panel_h), 2)

        # Header
        hdr = self.tag_font.render("AI THINKING  [I to close]", True, (160, 200, 255))
        panel_surf.blit(hdr, (10, 6))
        pygame.draw.line(panel_surf, (50, 80, 110), (0, header_h), (panel_w, header_h), 1)

        y = header_h + 4
        for ac in aircraft_list[:visible_rows]:
            state = getattr(ac, 'state', '?')
            color = STATE_COLORS.get(state, (200, 200, 200))

            # Callsign + type badge
            cs_text = self.info_font.render(ac.get_callsign(), True, color)
            panel_surf.blit(cs_text, (8, y))

            # State badge
            badge_text = self.tag_font.render(state.upper(), True, (20, 20, 30))
            badge_w = len(state) * 7 + 8
            pygame.draw.rect(panel_surf, color, (panel_w - badge_w - 8, y + 1, badge_w, 14))
            panel_surf.blit(badge_text, (panel_w - badge_w - 5, y + 1))

            # Thinking line
            thinking = ac.get_thinking() if hasattr(ac, 'get_thinking') else state
            # Truncate to fit
            max_chars = 52
            if len(thinking) > max_chars:
                thinking = thinking[:max_chars - 1] + "…"
            think_surf = self.tag_font.render(thinking, True, (170, 185, 200))
            panel_surf.blit(think_surf, (8, y + 16))

            # Speed / heading mini-stats
            spd = int(getattr(ac, 'speed', 0))
            hdg = int(getattr(ac, 'heading', 0))
            stats = self.tag_font.render(f"{spd}kt  {hdg:03d}°", True, (100, 120, 140))
            panel_surf.blit(stats, (8, y + 30))

            # Divider
            pygame.draw.line(panel_surf, (35, 45, 60), (4, y + row_h - 2), (panel_w - 4, y + row_h - 2), 1)
            y += row_h

        self.screen.blit(panel_surf, (panel_x, panel_y))
