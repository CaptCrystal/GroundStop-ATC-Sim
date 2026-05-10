"""
Weather Panel
Displays real-time weather, time, and allows runway configuration
"""
import pygame
import threading
from datetime import datetime

from src.core import atis_state

# Optional dependencies: if `requests` or `pytz` aren't installed in the
# environment, provide small, safe fallbacks so the app can run.
try:
    import requests  # type: ignore
except Exception:
    # Project contains a local `requests.py` shim that uses urllib; import that.
    import requests  # noqa: E402

try:
    import pytz
except Exception:
    # Minimal pytz-like fallback using stdlib timezone.utc
    from datetime import timezone as _tz

    class _PytzFallback:
        UTC = _tz.utc

        def timezone(self, name):
            return _tz.utc

    pytz = _PytzFallback()


class WeatherPanel:
    """Weather and airport configuration panel"""
    
    def __init__(self, width, height, airport_code, airport_lat, airport_lon, metar_cache=''):
        self.width = width
        self.height = height
        self.airport_code = airport_code
        self.airport_lat = airport_lat
        self.airport_lon = airport_lon
        
        # Panel state
        self.is_open = False
        self.panel_width = 350
        self.panel_height = 400  # Compact merged runway layout

        # ATIS state
        self.atis_letter = None   # e.g. "charlie"
        self.atis_text   = None   # full ATIS string
        self.last_atis_update = 0
        self.atis_update_interval = 1800  # re-fetch every 30 min
        
        print(f"WeatherPanel initialized for {airport_code} at ({airport_lat}, {airport_lon})")
        
        # Weather data
        self.weather_data = None
        self.last_weather_update = 0
        self.weather_update_interval = 600  # Update every 10 minutes
        self.metar_cache = metar_cache  # Cached METAR string
        self.metar_cache_callback = None  # Callback to save METAR to config
        
        # Time zone
        self.timezone = self._get_timezone()
        
        # Active runways (will be loaded from scenario)
        self.available_runways = []
        self.active_runways = []  # Legacy - kept for compatibility
        
        # Separate departure and arrival runways
        self.departure_runways = []  # Active departure runways
        self.arrival_runways = []    # Active arrival runways
        
        # Callbacks for runway changes
        self.aircraft_manager = None
        self.radio_callback = None
        self.runway_config_callback = None  # Callback to save runway config to ASDE
        
        # Fetch initial weather (force first update)
        self.update_weather(force=True)
    
    def _get_timezone(self):
        """Get timezone for airport based on coordinates"""
        try:
            from timezonefinder import TimezoneFinder
            tf = TimezoneFinder()
            tz_name = tf.timezone_at(lat=self.airport_lat, lng=self.airport_lon)
            return pytz.timezone(tz_name) if tz_name else pytz.UTC
        except:
            # Fallback to UTC if timezonefinder not available
            print("TimezoneFinder not available, using UTC")
            return pytz.UTC
    
    def get_local_time(self):
        """Get current local time at airport"""
        utc_now = datetime.now(pytz.UTC)
        local_time = utc_now.astimezone(self.timezone)
        return local_time
    
    def update_weather(self, force=False):
        """Fetch real-time METAR data from Aviation Weather API
        
        Args:
            force: If True, fetch weather regardless of update interval
        """
        current_time = pygame.time.get_ticks() / 1000
        
        # Only update if enough time has passed (unless forced)
        if not force and current_time - self.last_weather_update < self.weather_update_interval:
            return
        
        # Validate ICAO code
        if not self.airport_code or len(self.airport_code) != 4:
            print(f"Invalid ICAO code: {self.airport_code}")
            return
        
        try:
            # Using Aviation Weather Center API (free, no API key required)
            url = f"https://aviationweather.gov/api/data/metar?ids={self.airport_code}&format=json"
            print(f"Fetching METAR from: {url}")
            
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data and len(data) > 0:
                    self.weather_data = data[0]  # Get first METAR from JSON array
                    self.last_weather_update = current_time
                    
                    # Verify we got data for the correct airport
                    metar_icao = self.weather_data.get('icaoId', '')
                    if metar_icao == self.airport_code:
                        print(f"✓ METAR updated for {self.airport_code}: {self.weather_data.get('rawOb', 'N/A')}")
                    else:
                        print(f"⚠ METAR ICAO mismatch: requested {self.airport_code}, got {metar_icao}")
                else:
                    print(f"No METAR data available for {self.airport_code}")
            else:
                print(f"Weather API error: {response.status_code}")
        except Exception as e:
            print(f"Failed to fetch METAR: {e}")

        # Kick off ATIS fetch in background
        self._maybe_fetch_atis()

    def _maybe_fetch_atis(self, force=False):
        """Trigger a background ATIS fetch if the cache is stale."""
        current_time = pygame.time.get_ticks() / 1000
        if not force and current_time - self.last_atis_update < self.atis_update_interval:
            return
        if not self.airport_code or len(self.airport_code) != 4:
            return
        t = threading.Thread(target=self._fetch_atis, daemon=True, name="ATIS-Fetch")
        t.start()

    def _fetch_atis(self):
        """Fetch D-ATIS from datis.clowd.io and update shared atis_state."""
        import json as _json
        import urllib.request as _req
        import urllib.error as _uerr

        url = f"https://datis.clowd.io/api/{self.airport_code}"
        try:
            print(f"[ATIS] Fetching from {url}")
            with _req.urlopen(url, timeout=8) as resp:
                data = _json.loads(resp.read().decode("utf-8"))

            # datis.clowd.io returns a list of objects, each may have a "combined" key
            # or separate "dep"/"arr" keys, plus an "airport" key.
            # We want the info letter out of the text.
            if not data:
                print("[ATIS] Empty response")
                return

            # Try "combined" first, then "dep", then "arr"
            entry = data[0] if isinstance(data, list) else data
            text = (entry.get("combined") or
                    entry.get("dep") or
                    entry.get("arr") or "")

            if not text:
                print("[ATIS] No ATIS text in response")
                return

            # Extract info letter — appears as "INFORMATION <LETTER>" in the text
            import re
            m = re.search(r"\bINFORMATION\s+([A-Z])\b", text, re.IGNORECASE)
            letter = m.group(1).lower() if m else None

            self.atis_letter = letter
            self.atis_text   = text
            self.last_atis_update = pygame.time.get_ticks() / 1000

            # Write to shared module so aircraft can read it
            atis_state.current_atis_letter = letter
            atis_state.current_atis_text   = text

            print(f"[ATIS] Updated — info {letter.upper() if letter else '?'}: {text[:80]}…")

        except _uerr.HTTPError as e:
            print(f"[ATIS] HTTP {e.code}: {e.reason}")
        except Exception as e:
            print(f"[ATIS] Fetch failed: {e}")

    def set_available_runways(self, runways):
        """Set available runways from scenario data
        
        Args:
            runways: List of runway names (e.g., ["02/20", "14/32"])
        """
        self.available_runways = []
        for runway in runways:
            # Split runway pairs (e.g., "02/20" -> ["02", "20"])
            if '/' in runway:
                parts = runway.split('/')
                self.available_runways.extend(parts)
            else:
                self.available_runways.append(runway)
        
        # Set initial active runways (first runway of each pair)
        if not self.active_runways and self.available_runways:
            self.active_runways = [self.available_runways[0]]
    
    def toggle_departure_runway(self, runway):
        """Toggle a departure runway on/off"""
        if runway in self.departure_runways:
            self.departure_runways.remove(runway)
        else:
            self.departure_runways.append(runway)
        
        # Update legacy active_runways for compatibility
        self._update_legacy_active_runways()
        
        # Save to ASDE config
        if self.runway_config_callback:
            self.runway_config_callback(self.departure_runways, self.arrival_runways)
    
    def toggle_arrival_runway(self, runway):
        """Toggle an arrival runway on/off"""
        if runway in self.arrival_runways:
            self.arrival_runways.remove(runway)
        else:
            self.arrival_runways.append(runway)
        
        # Update legacy active_runways for compatibility
        self._update_legacy_active_runways()
        
        # Save to ASDE config
        if self.runway_config_callback:
            self.runway_config_callback(self.departure_runways, self.arrival_runways)
    
    def _update_legacy_active_runways(self):
        """Update legacy active_runways list (union of departure and arrival)"""
        self.active_runways = list(set(self.departure_runways + self.arrival_runways))
    
    def toggle_runway(self, runway):
        """Toggle runway active status and notify aircraft"""
        was_active = runway in self.active_runways
        
        if was_active:
            self.active_runways.remove(runway)
            status = "INACTIVE"
        else:
            self.active_runways.append(runway)
            status = "ACTIVE"
        
        # Notify aircraft of runway configuration change
        self._notify_aircraft_runway_change(runway, not was_active)
        
        # Send radio message about runway change
        if self.radio_callback:
            if not was_active:
                self.radio_callback(f"ATIS: Runway {runway} now in use for departures", is_atc=True)
            else:
                self.radio_callback(f"ATIS: Runway {runway} no longer in use", is_atc=True)
        
        # Save active runways to ASDE config (if callback is set)
        if hasattr(self, 'active_runways_callback') and self.active_runways_callback:
            self.active_runways_callback(self.active_runways)
    
    def _notify_aircraft_runway_change(self, runway, is_now_active):
        """Notify aircraft when runway configuration changes
        
        Args:
            runway: Runway that changed (e.g., "02", "20")
            is_now_active: True if runway is now active, False if deactivated
        """
        if not self.aircraft_manager:
            return
        
        # Update aircraft that are expecting this runway or need to know about changes
        for aircraft in self.aircraft_manager.aircraft:
            # Skip departed aircraft
            if aircraft.state == aircraft.STATE_DEPARTED:
                continue
            
            # If runway became active and aircraft has no expected runway, assign it
            if is_now_active and not aircraft.expected_runway:
                # Only assign to parked or holding aircraft
                if aircraft.state in [aircraft.STATE_PARKED, aircraft.STATE_HOLDING]:
                    aircraft.expected_runway = runway
                    print(f"[{aircraft.get_callsign()}] Auto-assigned expected runway {runway} (runway activated)")
            
            # If aircraft's expected runway was deactivated, update them
            elif not is_now_active and aircraft.expected_runway == runway:
                # Find an alternative active runway
                if self.active_runways:
                    new_runway = self.active_runways[0]
                    aircraft.expected_runway = new_runway
                    print(f"[{aircraft.get_callsign()}] Expected runway changed from {runway} to {new_runway} (runway deactivated)")
                    
                    # Notify aircraft via radio
                    if aircraft.radio_callback:
                        aircraft._schedule_radio(
                            f"Expect runway {new_runway}, {aircraft.get_callsign()}", 
                            is_atc=False
                        )
                else:
                    aircraft.expected_runway = None
                    print(f"[{aircraft.get_callsign()}] Expected runway cleared (no active runways)")
    
    def _calculate_runway_section_y(self):
        """Calculate Y position where runway section starts
        This ensures click detection and rendering use the same coordinates
        """
        y_offset = 40  # Start after title
        y_offset += 45  # Time section
        y_offset += 25  # Weather label
        
        # Weather data section (METAR format with wrapping)
        if self.weather_data:
            # Estimate METAR lines (typically 2-3 lines when wrapped)
            raw_metar = self.weather_data.get('rawOb', '')
            # Rough estimate: ~40 chars per line at 14px font with 240px width
            metar_lines = max(1, len(raw_metar) // 40 + 1)
            y_offset += metar_lines * 16  # METAR lines
            y_offset += 8  # Extra space after METAR
        else:
            y_offset += 20  # 1 line "Loading METAR..."
        
        y_offset += 20  # Gap before runway section

        # ATIS section
        if self.atis_letter:
            y_offset += 18  # "ATIS" label
            y_offset += 28  # big letter badge
            if self.atis_text:
                # estimate wrapped lines at ~42 chars per line, max 4 lines shown
                atis_lines = min(4, max(1, len(self.atis_text) // 42 + 1))
                y_offset += atis_lines * 14
            y_offset += 14  # gap after ATIS block

        y_offset += 22  # "Active Runways:" label
        y_offset += 28  # Column headers (DEP/ARR)

        return y_offset
    
    def _calculate_arrival_section_y(self):
        """Calculate Y position where arrival runway section starts"""
        y_offset = self._calculate_runway_section_y()
        # Add space for departure runways
        num_runways = len(self.available_runways)
        y_offset += (num_runways * 28) + 30  # Runways + gap + label (compact)
        return y_offset
    
    def handle_click(self, pos, panel_x, panel_y):
        """Handle clicks within the weather panel
        
        Args:
            pos: (x, y) mouse position
            panel_x: Panel x position on screen
            panel_y: Panel y position on screen
            
        Returns:
            True if click was handled
        """
        if not self.is_open:
            return False
        
        x, y = pos
        
        # Check if click is within panel bounds
        if not (panel_x <= x <= panel_x + self.panel_width and 
                panel_y <= y <= panel_y + self.panel_height):
            return False
        
        # Convert screen coordinates to panel-relative coordinates
        panel_relative_x = x - panel_x
        panel_relative_y = y - panel_y
        
        # Check runway toggle buttons (merged DEP/ARR interface)
        runway_section_y = self._calculate_runway_section_y()
        for i, runway in enumerate(self.available_runways):
            # DEP button
            dep_button_x = 95
            button_y = runway_section_y + (i * 32)
            button_width = 50
            button_height = 25
            
            if (dep_button_x <= panel_relative_x <= dep_button_x + button_width and
                button_y <= panel_relative_y <= button_y + button_height):
                self.toggle_departure_runway(runway)
                print(f"Toggled departure runway {runway}: {'ACTIVE' if runway in self.departure_runways else 'INACTIVE'}")
                return True
            
            # ARR button
            arr_button_x = 150
            if (arr_button_x <= panel_relative_x <= arr_button_x + button_width and
                button_y <= panel_relative_y <= button_y + button_height):
                self.toggle_arrival_runway(runway)
                print(f"Toggled arrival runway {runway}: {'ACTIVE' if runway in self.arrival_runways else 'INACTIVE'}")
                return True
        
        return True
    
    def render(self, screen, info_font, small_font):
        """Render the weather panel
        
        Args:
            screen: Pygame screen surface
            info_font: Font for main text
            small_font: Font for small text
        """
        if not self.is_open:
            return
        
        # Panel position (right side of screen)
        panel_x = self.width - self.panel_width - 10
        panel_y = 45  # Below top menu bar

        # Recalculate panel height to accommodate ATIS section
        base_height = 400
        if self.atis_letter:
            atis_extra = 18 + 34 + 8  # label + badge + gap
            if self.atis_text:
                lines = min(4, max(1, len(self.atis_text) // 42 + 1))
                atis_extra += lines * 14 + 14
            base_height += atis_extra
        self.panel_height = base_height

        # Professional dark background
        panel_surface = pygame.Surface((self.panel_width, self.panel_height))
        panel_surface.set_alpha(252)
        panel_surface.fill((12, 12, 14))
        
        # Subtle border
        pygame.draw.rect(panel_surface, (45, 45, 50), (0, 0, self.panel_width, self.panel_height), 1)
        
        # Title
        title_text = info_font.render(f"{self.airport_code} Weather", True, (180, 180, 180))
        panel_surface.blit(title_text, (10, 10))
        
        y_offset = 40
        
        # === TIME SECTION (COMPACT) ===
        local_time = self.get_local_time()
        time_str = local_time.strftime("%H:%M Local")
        zulu_str = datetime.now(pytz.UTC).strftime("%H:%MZ")
        
        time_label = small_font.render("Time:", True, (160, 200, 240))
        panel_surface.blit(time_label, (10, y_offset))
        
        local_text = small_font.render(time_str, True, (200, 220, 255))
        panel_surface.blit(local_text, (60, y_offset))
        
        zulu_text = small_font.render(zulu_str, True, (180, 180, 180))
        panel_surface.blit(zulu_text, (60, y_offset + 16))
        
        y_offset += 45
        
        # === WEATHER SECTION (COMPACT) ===
        weather_label = small_font.render("Weather:", True, (160, 200, 240))
        panel_surface.blit(weather_label, (10, y_offset))
        y_offset += 25
        
        if self.weather_data:
            # Raw METAR (wrap if too long)
            raw_metar = self.weather_data.get('rawOb', 'N/A')
            
            # Word wrap METAR to fit panel width
            max_width = self.panel_width - 40  # Leave margins
            words = raw_metar.split()
            lines = []
            current_line = []
            
            for word in words:
                test_line = ' '.join(current_line + [word])
                test_surface = small_font.render(test_line, True, (200, 220, 255))
                if test_surface.get_width() <= max_width:
                    current_line.append(word)
                else:
                    if current_line:
                        lines.append(' '.join(current_line))
                        current_line = [word]
                    else:
                        lines.append(word)
            
            if current_line:
                lines.append(' '.join(current_line))
            
            # Render wrapped METAR lines (compact)
            for line in lines:
                metar_text = small_font.render(line, True, (200, 220, 255))
                panel_surface.blit(metar_text, (15, y_offset))
                y_offset += 16  # Line spacing (compact)
            
            y_offset += 8  # Extra space after METAR
        else:
            no_data_text = small_font.render("Loading METAR...", True, (150, 150, 150))
            panel_surface.blit(no_data_text, (15, y_offset))
            y_offset += 20
        
        y_offset += 20  # Gap before runway section

        # === ATIS SECTION ===
        if self.atis_letter:
            # Section label
            atis_label = small_font.render("ATIS:", True, (160, 200, 240))
            panel_surface.blit(atis_label, (10, y_offset))
            y_offset += 18

            # Large info letter badge
            letter_upper = self.atis_letter.upper()
            try:
                badge_font = pygame.font.SysFont("Courier New", 22, bold=True)
            except Exception:
                badge_font = small_font
            badge_surf = badge_font.render(f"INFO {letter_upper}", True, (255, 220, 80))
            badge_bg = pygame.Rect(10, y_offset, badge_surf.get_width() + 12, badge_surf.get_height() + 6)
            pygame.draw.rect(panel_surface, (50, 45, 20), badge_bg, border_radius=4)
            pygame.draw.rect(panel_surface, (120, 100, 30), badge_bg, 1, border_radius=4)
            panel_surface.blit(badge_surf, (badge_bg.x + 6, badge_bg.y + 3))
            y_offset += badge_bg.height + 4

            # Scrollable ATIS text (first 4 wrapped lines)
            if self.atis_text:
                max_width = self.panel_width - 30
                words = self.atis_text.split()
                atis_lines = []
                cur = []
                for w in words:
                    test = ' '.join(cur + [w])
                    if small_font.render(test, True, (0,0,0)).get_width() <= max_width:
                        cur.append(w)
                    else:
                        if cur:
                            atis_lines.append(' '.join(cur))
                        cur = [w]
                if cur:
                    atis_lines.append(' '.join(cur))
                for line in atis_lines[:4]:
                    t = small_font.render(line, True, (190, 190, 160))
                    panel_surface.blit(t, (10, y_offset))
                    y_offset += 14
                if len(atis_lines) > 4:
                    more = small_font.render("…", True, (120, 120, 100))
                    panel_surface.blit(more, (10, y_offset))
                    y_offset += 14

            y_offset += 8  # gap after ATIS block

        # === MERGED RUNWAY CONFIGURATION ===
        runway_label = small_font.render("Active Runways:", True, (150, 200, 255))
        panel_surface.blit(runway_label, (10, y_offset))
        y_offset += 22  # Space after label
        
        # Column headers with background boxes
        header_y = y_offset
        
        # DEP header
        dep_header_rect = pygame.Rect(95, header_y, 50, 18)
        pygame.draw.rect(panel_surface, (25, 25, 28), dep_header_rect, border_radius=2)
        dep_header = small_font.render("DEP", True, (100, 100, 100))
        panel_surface.blit(dep_header, (107, header_y + 2))
        
        # ARR header
        arr_header_rect = pygame.Rect(150, header_y, 50, 18)
        pygame.draw.rect(panel_surface, (25, 25, 28), arr_header_rect, border_radius=2)
        arr_header = small_font.render("ARR", True, (100, 100, 100))
        panel_surface.blit(arr_header, (162, header_y + 2))
        
        y_offset += 28  # Space after headers
        runway_section_y = y_offset
        
        if self.available_runways:
            for i, runway in enumerate(self.available_runways):
                button_y = runway_section_y + (i * 32)
                
                # Runway label
                runway_text = small_font.render(f"RWY {runway}", True, (255, 255, 255))
                panel_surface.blit(runway_text, (15, button_y + 5))
                
                # DEP button (Departure - Green theme)
                dep_active = runway in self.departure_runways
                dep_button_x = 95
                button_width = 50
                button_height = 25
                
                # Professional color scheme
                dep_color = (35, 70, 45) if dep_active else (25, 25, 28)
                pygame.draw.rect(panel_surface, dep_color, 
                               (dep_button_x, button_y, button_width, button_height), 
                               border_radius=3)
                dep_border = (60, 100, 70) if dep_active else (40, 40, 45)
                pygame.draw.rect(panel_surface, dep_border, 
                               (dep_button_x, button_y, button_width, button_height), 
                               1, border_radius=3)
                
                # DEP status text
                dep_text = small_font.render("DEP", True, 
                                            (220, 255, 220) if dep_active else (100, 105, 110))
                text_rect = dep_text.get_rect(center=(dep_button_x + button_width // 2, button_y + button_height // 2))
                panel_surface.blit(dep_text, text_rect)
                
                # ARR button (Arrival - Blue theme)
                arr_active = runway in self.arrival_runways
                arr_button_x = 150
                
                # Professional color scheme
                arr_color = (35, 55, 75) if arr_active else (25, 25, 28)
                pygame.draw.rect(panel_surface, arr_color, 
                               (arr_button_x, button_y, button_width, button_height), 
                               border_radius=3)
                arr_border = (60, 85, 110) if arr_active else (40, 40, 45)
                pygame.draw.rect(panel_surface, arr_border, 
                               (arr_button_x, button_y, button_width, button_height), 
                               1, border_radius=3)
                
                # ARR status text
                arr_text = small_font.render("ARR", True, 
                                            (200, 230, 255) if arr_active else (100, 105, 110))
                text_rect = arr_text.get_rect(center=(arr_button_x + button_width // 2, button_y + button_height // 2))
                panel_surface.blit(arr_text, text_rect)
        else:
            no_runways_text = small_font.render("No runways configured", True, (150, 150, 150))
            panel_surface.blit(no_runways_text, (15, y_offset + 40))
        
        # Blit panel to screen
        screen.blit(panel_surface, (panel_x, panel_y))
        
        return panel_x, panel_y
