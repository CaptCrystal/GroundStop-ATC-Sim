"""
Commands and event handling mixin for SimulationScreen
"""
import pygame
from src.core import radio_hold as _radio_hold


class CommandsMixin:
    """Mixin providing ATC command handling, event processing, and auto-complete for SimulationScreen."""

    def handle_event(self, event):
        """Handle input events"""
        # Route events to flight strips window (e.g. WINDOWCLOSE)
        if hasattr(self, "flight_strips_window"):
            self.flight_strips_window.handle_event(event)

        # Handle command bar input first if active
        if self.command_bar_active and event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                # Execute command
                self.execute_command(self.command_input)
                self.command_input = ""
                self.command_bar_active = False
                return
            elif event.key == pygame.K_ESCAPE:
                # Cancel command input
                self.command_input = ""
                self.command_bar_active = False
                return
            elif event.key == pygame.K_BACKSPACE:
                # Handle backspace with cursor position
                if self.cursor_position > 0:
                    self.command_input = self.command_input[:self.cursor_position-1] + self.command_input[self.cursor_position:]
                    self.cursor_position -= 1

                    # Clear pre-filled callsign if user backspaces over it
                    if self.prefilled_callsign and not self.command_input.startswith(f"/{self.prefilled_callsign} "):
                        self.prefilled_callsign = ""
                return
            elif event.key == pygame.K_LEFT:
                # Move cursor left
                if self.cursor_position > 0:
                    self.cursor_position -= 1
                return
            elif event.key == pygame.K_RIGHT:
                # Move cursor right
                if self.cursor_position < len(self.command_input):
                    self.cursor_position += 1
                return
            elif event.key == pygame.K_HOME:
                # Move cursor to beginning
                self.cursor_position = 0
                return
            elif event.key == pygame.K_END:
                # Move cursor to end
                self.cursor_position = len(self.command_input)
                return
            elif event.key == pygame.K_TAB:
                # Handle auto-completion
                self.handle_tab_completion()
                return
            elif event.key == pygame.K_UP:
                # Navigate command history up
                if self.command_history:
                    if self.command_history_index < len(self.command_history) - 1:
                        self.command_history_index += 1
                        self.command_input = self.command_history[-(self.command_history_index + 1)]
                return
            elif event.key == pygame.K_DOWN:
                # Navigate command history down
                if self.command_history_index > 0:
                    self.command_history_index -= 1
                    self.command_input = self.command_history[-(self.command_history_index + 1)]
                elif self.command_history_index == 0:
                    self.command_history_index = -1
                    self.command_input = ""
                return
            elif event.key == pygame.K_SEMICOLON:
                # Ignore semicolon in command bar (it's the PTT key)
                return
            elif event.unicode and event.unicode.isprintable():
                # Insert character at cursor position
                old_input = self.command_input
                self.command_input = self.command_input[:self.cursor_position] + event.unicode + self.command_input[self.cursor_position:]
                self.cursor_position += 1

                # Smart callsign replacement with flight number detection
                if self.prefilled_callsign:
                    # Check if user is typing after the slash
                    if self.command_input.startswith('/') and len(self.command_input) > 1:
                        # Extract what user has typed after the slash
                        after_slash = self.command_input[1:].strip()

                        # Check if this doesn't match the pre-filled callsign anymore
                        if not after_slash.startswith(self.prefilled_callsign):
                            # Try to match by flight number (ignoring airline code)
                            if len(after_slash) >= 3:  # Flight numbers are at least 3 digits
                                matched_callsign = self.find_callsign_by_flight_number(after_slash)
                                if matched_callsign:
                                    # Found matching aircraft, replace with full callsign
                                    remaining_text = ""
                                    self.command_input = f"/{matched_callsign} "
                                    self.prefilled_callsign = ""
                                    self.cursor_position = len(self.command_input)
                                else:
                                    # No match found, just use what user typed
                                    self.command_input = "/" + after_slash
                                    self.prefilled_callsign = ""
                                    self.cursor_position = len(self.command_input)
                            else:
                                # Too short for flight number, just replace
                                self.command_input = "/" + after_slash
                                self.prefilled_callsign = ""
                                self.cursor_position = len(self.command_input)

                # Also clear pre-filled callsign if user modifies it in other ways
                elif self.prefilled_callsign and not self.command_input.startswith(f"/{self.prefilled_callsign} "):
                    self.prefilled_callsign = ""
                return
            # Allow numpad keys to work even when command bar is active (don't return)
            # Fall through to handle numpad below

        if event.type == pygame.KEYDOWN:
            # If the voice panel is waiting for a key rebind, capture it first
            if (hasattr(self, 'top_menu_bar') and self.top_menu_bar
                    and self.top_menu_bar.ptt_listening):
                self.top_menu_bar.handle_key_for_rebind(event)
                return

            # Aircraft editor: arrow keys to select field, type to edit
            if self.show_aircraft_editor and self.editor_aircraft:
                field_keys = ['AC', 'BCN', 'CAT', 'TYP', 'FIX', 'SP1', 'SP2']
                if event.key == pygame.K_UP:
                    self.editor_selected_index = (self.editor_selected_index - 1) % len(field_keys)
                    return
                if event.key == pygame.K_DOWN:
                    self.editor_selected_index = (self.editor_selected_index + 1) % len(field_keys)
                    return
                key = field_keys[self.editor_selected_index]
                cur = self.editor_field_values.get(key, '')
                if event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
                    # Confirm edit: apply current field to aircraft and clear edited state for it
                    self._editor_apply_to_aircraft(key, self.editor_field_values.get(key, ''))
                    self.editor_edited_fields.discard(key)
                    return
                if event.key == pygame.K_BACKSPACE:
                    self.editor_field_values[key] = cur[:-1]
                    self.editor_edited_fields.add(key)
                    return
                if event.unicode and event.unicode.isprintable():
                    self.editor_field_values[key] = cur + event.unicode
                    self.editor_edited_fields.add(key)
                    return
            # Check for Space key press to start multi-copy mode
            if event.key == pygame.K_SPACE:
                mods = pygame.key.get_mods()
                if self.dev_mode and (mods & pygame.KMOD_CTRL) and (mods & pygame.KMOD_SHIFT):
                    self.multi_copy_mode = True
                    self.copied_coordinates = []
                    print("Multi-copy mode activated. Click to add coordinates. Release Space to copy all.")
            # Check for Shift+Ctrl+1 for dev mode toggle
            elif event.key == pygame.K_1:
                mods = pygame.key.get_mods()
                if (mods & pygame.KMOD_SHIFT) and (mods & pygame.KMOD_CTRL):
                    self.dev_mode = not self.dev_mode
                    print(f"Dev mode: {'ON' if self.dev_mode else 'OFF'}")
            # Dev mode feature toggles (Ctrl+Shift+2-9)
            elif event.key == pygame.K_2 and self.dev_mode:
                mods = pygame.key.get_mods()
                if (mods & pygame.KMOD_SHIFT) and (mods & pygame.KMOD_CTRL):
                    self.dev_show_fps = not self.dev_show_fps
                    print(f"Dev FPS Display: {'ON' if self.dev_show_fps else 'OFF'}")
            elif event.key == pygame.K_3 and self.dev_mode:
                mods = pygame.key.get_mods()
                if (mods & pygame.KMOD_SHIFT) and (mods & pygame.KMOD_CTRL):
                    self.dev_show_aircraft_paths = not self.dev_show_aircraft_paths
                    print(f"Dev Aircraft Paths: {'ON' if self.dev_show_aircraft_paths else 'OFF'}")
            elif event.key == pygame.K_4 and self.dev_mode:
                mods = pygame.key.get_mods()
                if (mods & pygame.KMOD_SHIFT) and (mods & pygame.KMOD_CTRL):
                    self.dev_show_graph_nodes = not self.dev_show_graph_nodes
                    print(f"Dev Graph Nodes: {'ON' if self.dev_show_graph_nodes else 'OFF'}")
            elif event.key == pygame.K_5 and self.dev_mode:
                mods = pygame.key.get_mods()
                if (mods & pygame.KMOD_SHIFT) and (mods & pygame.KMOD_CTRL):
                    self.dev_show_collision_zones = not self.dev_show_collision_zones
                    print(f"Dev Collision Zones: {'ON' if self.dev_show_collision_zones else 'OFF'}")
            elif event.key == pygame.K_6 and self.dev_mode:
                mods = pygame.key.get_mods()
                if (mods & pygame.KMOD_SHIFT) and (mods & pygame.KMOD_CTRL):
                    self.dev_show_performance_stats = not self.dev_show_performance_stats
                    print(f"Dev Performance Stats: {'ON' if self.dev_show_performance_stats else 'OFF'}")
            elif event.key == pygame.K_F2:
                # F2 — toggle flight strips window
                if hasattr(self, "flight_strips_window"):
                    self.flight_strips_window.toggle()
            elif event.key == pygame.K_i:
                # Press 'I' to toggle aircraft thinking panel
                if not self.command_bar_active:
                    self.show_thinking_panel = not self.show_thinking_panel
            elif event.key == self._get_ptt_key():
                # PTT (Push-To-Talk) for voice commands — key configurable via Voice panel
                if self.voice_enabled and self.stt and not self.command_bar_active:
                    if not self.ptt_active:
                        print("[VOICE] PTT pressed — starting session thread")
                        self.ptt_active = True
                        self._set_voice_status("PTT | RECORDING", 30.0)
                        # Block all aircraft radio calls while controller is transmitting
                        _radio_hold.hold_until = float("inf")
                        _radio_hold.priority_callsign = None
                        # Entire recording runs in background — no main-thread audio
                        ok = self.stt.begin_ptt_session(self._on_voice_transcript)
                        if not ok:
                            print("[VOICE] ERROR: could not start session")
                            self._set_voice_status("PTT | MIC ERROR", 3.0)
                            self.ptt_active = False
            elif event.key == pygame.K_t:
                # Press 'T' to show Tower debug info
                mods = pygame.key.get_mods()
                if (mods & pygame.KMOD_SHIFT) and (mods & pygame.KMOD_CTRL):
                    if self.aircraft_manager and hasattr(self.aircraft_manager, 'tower_controller'):
                        self.aircraft_manager.tower_controller.print_debug_info()
                else:
                    # Just Shift+T for quick tower status
                    if (mods & pygame.KMOD_SHIFT) and self.aircraft_manager and hasattr(self.aircraft_manager, 'tower_controller'):
                        self.aircraft_manager.tower_controller.print_debug_info()
            elif event.key == pygame.K_ESCAPE:
                if self.show_aircraft_editor:
                    self.show_aircraft_editor = False
                    self.editor_aircraft = None
                    self.editor_field_values = {}
                    self.editor_edited_fields = set()
                    return
                # Return to airport menu (only if command bar not active)
                if not self.command_bar_active:
                    if self.show_exit_confirmation:
                        # Cancel confirmation dialog
                        self.show_exit_confirmation = False
                    else:
                        # Show confirmation dialog
                        self.show_exit_confirmation = True
            elif event.key == pygame.K_SEMICOLON or event.unicode == ';':
                # Activate command bar for ATC commands (PTT key: ;)
                if not self.command_bar_active:
                    self.command_bar_active = True
                    # Update available callsigns for target generation
                    self.update_available_callsigns()
                    # Reset auto-complete state
                    self.auto_complete_index = -1
                    self.auto_complete_matches = []

                    # Pre-fill with last callsign if available
                    if self.last_callsign:
                        self.command_input = "/"
                        # Don't show pre-filled callsign, just remember it
                        self.cursor_position = 1
                    else:
                        self.command_input = "/"
                        self.cursor_position = 1
                    self.command_history_index = -1
            elif event.key == pygame.K_UP:
                self.camera_y -= 50
            elif event.key == pygame.K_DOWN:
                self.camera_y += 50
            elif event.key == pygame.K_LEFT:
                self.camera_x -= 50
            elif event.key == pygame.K_RIGHT:
                self.camera_x += 50
            elif event.key == pygame.K_EQUALS or event.key == pygame.K_PLUS:
                self.zoom *= 1.2
            elif event.key == pygame.K_MINUS:
                self.zoom /= 1.2
            # Numpad keys for tag positioning (8=N, 6=E, 2=S, 4=W, 9=NE, 3=SE, 1=SW, 7=NW)
            elif event.key == pygame.K_KP8:
                self.handle_tag_direction(8)  # North
            elif event.key == pygame.K_KP6:
                self.handle_tag_direction(6)  # East
            elif event.key == pygame.K_KP2:
                self.handle_tag_direction(2)  # South
            elif event.key == pygame.K_KP4:
                self.handle_tag_direction(4)  # West
            elif event.key == pygame.K_KP9:
                self.handle_tag_direction(9)  # Northeast
            elif event.key == pygame.K_KP3:
                self.handle_tag_direction(3)  # Southeast
            elif event.key == pygame.K_KP1:
                self.handle_tag_direction(1)  # Southwest
            elif event.key == pygame.K_KP7:
                self.handle_tag_direction(7)  # Northwest

        elif event.type == pygame.KEYUP:
            # Check for Space key release to finalize multi-copy
            if event.key == pygame.K_SPACE and self.multi_copy_mode:
                self._finalize_multi_copy()
            # Shift released — signal the recording thread to stop and transcribe
            elif event.key == self._get_ptt_key() and self.ptt_active:
                self.ptt_active = False
                print("[VOICE] PTT released — signalling stop")
                self._set_voice_status("PTT | TRANSCRIBING...", 10.0)
                self.stt.end_ptt_session()   # just sets an event — never blocks

        # Mouse controls
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:  # left click
                mods = pygame.key.get_mods()
                # Check for Ctrl+Shift+Click in dev mode to copy coordinates (before Shift-drag)
                if self.dev_mode and (mods & pygame.KMOD_CTRL) and (mods & pygame.KMOD_SHIFT):
                    keys = pygame.key.get_pressed()
                    if keys[pygame.K_SPACE]:
                        self._add_coordinate_to_multi_copy(event.pos)
                    else:
                        self._copy_coordinates_at_mouse(event.pos)
                    return
                # Check for Shift+left-click drag (touchpad friendly); don't drag when Ctrl+Shift
                # Also skip drag when Shift is being used as PTT
                ptt_is_shift = self._get_ptt_key() in (pygame.K_LSHIFT, pygame.K_RSHIFT)
                if (mods & pygame.KMOD_SHIFT) and not (self.ptt_active and ptt_is_shift):
                    self.dragging = True
                    self.last_mouse_pos = event.pos
                    return  # Skip other left-click processing when dragging

                # Check if exit confirmation dialog is showing
                if self.show_exit_confirmation:
                    dialog_width = 400
                    dialog_height = 150
                    dialog_x = (self.width - dialog_width) // 2
                    dialog_y = (self.height - dialog_height) // 2

                    # Yes button
                    yes_button_rect = pygame.Rect(dialog_x + 50, dialog_y + 95, 120, 35)
                    if yes_button_rect.collidepoint(event.pos):
                        if self.app:
                            self.app.show_airport_menu()
                        return

                    # No button
                    no_button_rect = pygame.Rect(dialog_x + 230, dialog_y + 95, 120, 35)
                    if no_button_rect.collidepoint(event.pos):
                        self.show_exit_confirmation = False
                        return

                    return  # Don't process other clicks when dialog is showing

                # Check if weather panel was clicked
                if self.weather_panel and self.weather_panel.is_open:
                    panel_x = self.width - self.weather_panel.panel_width - 10
                    panel_y = 45
                    if self.weather_panel.handle_click(event.pos, panel_x, panel_y):
                        return  # Click was handled by weather panel

                # Check if flight plan panel was clicked
                if self.flight_plan_panel and self.flight_plan_panel.is_open:
                    if self.flight_plan_panel.handle_mouse_down(event.pos):
                        return  # Click was handled by flight plan panel

                # Check if radio panel was clicked
                if self.radio_panel and self.radio_panel.is_open:
                    panel_x = self.width - self.radio_panel.panel_width - 10
                    panel_y = 45
                    if self.radio_panel.handle_click(event.pos, panel_x, panel_y):
                        return  # Click was handled by radio panel

                # Check if top menu bar was clicked
                if self.top_menu_bar.handle_mouse_down(event.pos):
                    return  # Click was handled by menu bar
                # Check if help button was clicked
                elif event.pos[1] > self.height - 50:  # Only check help button at bottom
                    help_button_rect = pygame.Rect(self.width - 50, self.height - 50, 20, 20)
                    if help_button_rect.collidepoint(event.pos):
                        self.show_help = not self.show_help
                # Check if aircraft was clicked (for tag positioning, visibility toggle, or flight plan)
                elif self.aircraft_manager:
                    clicked_aircraft = self.get_aircraft_at_position(event.pos)
                    if clicked_aircraft:
                        # Update last_callsign when clicking aircraft for better persistence
                        self.last_callsign = clicked_aircraft.get_callsign()

                        # Check for CTRL+click to open flight plan
                        mods = pygame.key.get_mods()
                        if mods & pygame.KMOD_CTRL:
                            # Open flight plan panel
                            from src.rendering.flight_plan_panel import FlightPlanPanel
                            if self.flight_plan_panel is None:
                                self.flight_plan_panel = FlightPlanPanel(self.width, self.height)
                            self.flight_plan_panel.set_aircraft(clicked_aircraft)
                            return  # Click was handled
                        elif self.pending_tag_direction is not None:
                            # Set tag direction if pending
                            clicked_aircraft.tag_direction = self.pending_tag_direction
                            # Reset tag anchor so it immediately moves to new position
                            clicked_aircraft.tag_anchor_world_pos = None
                            clicked_aircraft.tag_anchor_offset = None
                            self.pending_tag_direction = None
                        else:
                            # Toggle datatag and leader line visibility
                            show_datatag = getattr(clicked_aircraft, 'show_datatag', True)
                            clicked_aircraft.show_datatag = not show_datatag
                        return  # Click was handled
            elif event.button == 3:  # right click
                if self.aircraft_manager:
                    clicked_aircraft = self.get_aircraft_at_position(event.pos)
                    if clicked_aircraft:
                        self.show_aircraft_editor = True
                        self.editor_aircraft = clicked_aircraft
                        self.editor_field_values = {}
                        self.editor_edited_fields = set()
                        self.editor_selected_index = 0
                        self.editor_scratch_alternate_time = pygame.time.get_ticks() / 1000.0 + 3.0
                        self.editor_show_scratch_one = True
                        return
                self.dragging = True
                self.last_mouse_pos = event.pos
            elif event.button == 2:  # middle click - more touchpad friendly
                self.dragging = True
                self.last_mouse_pos = event.pos
            elif event.button == 4:  # Scroll up
                if self.show_help:
                    # Scroll help menu up
                    self.help_scroll_offset = max(0, self.help_scroll_offset - 30)
                else:
                    # Zoom in toward screen center
                    old_zoom = self.zoom
                    self.zoom *= 1.1
                    # Adjust camera to keep center point fixed
                    zoom_factor = self.zoom / old_zoom
                    self.camera_x *= zoom_factor
                    self.camera_y *= zoom_factor
            elif event.button == 5:  # Scroll down
                if self.show_help:
                    # Scroll help menu down
                    self.help_scroll_offset += 30
                else:
                    # Zoom out from screen center
                    old_zoom = self.zoom
                    self.zoom /= 1.1
                    # Adjust camera to keep center point fixed
                    zoom_factor = self.zoom / old_zoom
                    self.camera_x *= zoom_factor
                    self.camera_y *= zoom_factor

        elif event.type == pygame.MOUSEBUTTONUP:
            # Handle flight plan panel mouse up
            if self.flight_plan_panel and self.flight_plan_panel.is_open:
                self.flight_plan_panel.handle_mouse_up()

            if event.button == 3:
                self.dragging = False
                self.last_mouse_pos = None
                pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_CROSSHAIR)  # Keep crosshair
            elif event.button == 2:  # Middle click
                self.dragging = False
                self.last_mouse_pos = None
                pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_CROSSHAIR)  # Keep crosshair

            # Handle mouse up for top menu bar slider
            if self.top_menu_bar:
                self.top_menu_bar.handle_mouse_up(event.pos)

        elif event.type == pygame.MOUSEMOTION:
            # Handle flight plan panel mouse motion for dragging
            if self.flight_plan_panel and self.flight_plan_panel.is_open:
                self.flight_plan_panel.handle_mouse_motion(event.pos)

            # Track mouse position for hover detection
            self.mouse_pos = event.pos

            # Handle slider dragging in top menu bar
            if self.top_menu_bar and self.top_menu_bar.handle_mouse_motion(event.pos):
                return  # Motion was handled by slider

            if self.dragging and self.last_mouse_pos:
                dx = event.pos[0] - self.last_mouse_pos[0]
                dy = event.pos[1] - self.last_mouse_pos[1]
                self.camera_x += dx
                self.camera_y += dy
                self.last_mouse_pos = event.pos

                # Show pan cursor indicator
                pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_CROSSHAIR)  # Keep crosshair

    def execute_command(self, command):
        """Execute an ATC command with smart callsign handling"""
        # Add to command history
        self.command_history.append(command)
        if len(self.command_history) > 20:  # Keep last 20 commands
            self.command_history.pop(0)

        # Handle clear command specially
        cmd_name, args = self.command_processor.parse_command(command)
        if cmd_name == "clear":
            self.command_output.clear()
            return

        # Smart callsign detection
        if command.startswith('/'):
            command_without_slash = command[1:].strip()

            # Check if command starts with a flight number (digits)
            if command_without_slash and command_without_slash[0].isdigit():
                # Extract flight number (digits at the beginning)
                flight_number = ""
                for char in command_without_slash:
                    if char.isdigit():
                        flight_number += char
                    else:
                        break

                if flight_number:
                    # Try to find matching aircraft
                    matched_callsign = self.find_callsign_by_flight_number(flight_number)
                    if matched_callsign:
                        # Replace with full callsign
                        remaining_command = command_without_slash[len(flight_number):].strip()
                        command = f"/{matched_callsign} {remaining_command}"
                    else:
                        # No matching aircraft found, use as-is
                        command = f"/{command_without_slash}"
                else:
                    command = f"/{command_without_slash}"
            elif self.last_callsign and not command_without_slash:
                # Just "/" with no callsign - use last callsign
                command = f"/{self.last_callsign}"
            elif self.last_callsign and ' ' not in command_without_slash and len(command_without_slash) > 0:
                # Single word that's not a flight number - assume it's a command for last aircraft
                command = f"/{self.last_callsign} {command_without_slash}"

        # Execute command using processor
        success = self.command_processor.execute(command, self.add_output)

        # Lock the radio so only the addressed aircraft can read back,
        # and everyone else waits until that readback audio finishes.
        if success:
            # Extract the callsign — first token, strip leading slash
            addressed = command.lstrip('/').split()[0] if command.strip() else None
            if addressed:
                # Resolve short-form (e.g. "123") to full callsign (e.g. "AAL123")
                # so the is_priority check in _process_pending_radio matches get_callsign()
                ac = self.command_processor.find_aircraft(addressed)
                if ac:
                    addressed = ac.get_callsign()
                sim_time = (self.aircraft_manager.simulation_time
                            if self.aircraft_manager else 0.0)
                _radio_hold.priority_callsign = addressed
                _radio_hold.exchange_locked   = True
                _radio_hold.hold_until        = sim_time + 30.0  # safety timeout

    def find_callsign_by_flight_number(self, flight_number):
        """Find aircraft callsign by flight number (ignoring airline code)"""
        if not self.aircraft_manager or not flight_number:
            return None

        # Get all aircraft
        aircraft_list = self.aircraft_manager.get_all_aircraft()

        for aircraft in aircraft_list:
            callsign = aircraft.get_callsign()

            # Extract flight number from callsign (everything after airline code)
            if len(callsign) >= 3:
                # Find where the digits start
                digits_start = 0
                for i, char in enumerate(callsign):
                    if char.isdigit():
                        digits_start = i
                        break

                if digits_start > 0:
                    callsign_flight_number = callsign[digits_start:]

                    # Check if flight number matches (exact match or starts with)
                    if callsign_flight_number == flight_number or callsign_flight_number.startswith(flight_number):
                        return callsign

        return None

    def update_available_callsigns(self):
        """Update the cache of available aircraft callsigns for target generation"""
        if not self.aircraft_manager:
            self.available_callsigns = []
            return

        # Get all aircraft and extract their callsigns/flight numbers
        aircraft_list = self.aircraft_manager.get_all_aircraft()
        self.available_callsigns = []

        for aircraft in aircraft_list:
            callsign = aircraft.get_callsign()
            flight_number = getattr(aircraft, 'flight_number', None)

            # Add both full callsign and flight number if different
            if callsign:
                self.available_callsigns.append(callsign.upper())
            if flight_number and flight_number != callsign:
                self.available_callsigns.append(str(flight_number).upper())

        # Sort for consistent ordering
        self.available_callsigns.sort()

    def get_auto_complete_matches(self, partial_input):
        """Get auto-complete matches for partial input"""
        if not partial_input or not self.available_callsigns:
            return []

        # Extract the callsign part (after slash and any existing text)
        if partial_input.startswith('/'):
            partial = partial_input[1:].strip()
        else:
            partial = partial_input.strip()

        # Find matches
        matches = []
        for callsign in self.available_callsigns:
            if callsign.startswith(partial.upper()):
                matches.append(callsign)

        return matches

    def handle_tab_completion(self):
        """Handle Tab key for auto-completion"""
        if not self.command_bar_active or not self.command_input:
            return

        # Get current matches
        matches = self.get_auto_complete_matches(self.command_input)

        if not matches:
            return

        # If this is a new tab press or input changed, reset index
        if self.auto_complete_index == -1 or self.last_command_input != self.command_input:
            self.auto_complete_matches = matches
            self.auto_complete_index = 0
            self.last_command_input = self.command_input
        else:
            # Cycle through matches
            self.auto_complete_index = (self.auto_complete_index + 1) % len(matches)

        # Apply the selected match
        selected_callsign = self.auto_complete_matches[self.auto_complete_index]
        self.command_input = f"/{selected_callsign} "

    def add_output(self, text, color=(0, 224, 21)):
        """Add text to command output with color (default green for ATC)"""
        self.command_output.append((text, color))
        if len(self.command_output) > self.max_output_lines:
            self.command_output.pop(0)

    def add_aircraft_transmission(self, text):
        """Add aircraft transmission (blue text)"""
        self.add_output(text, color=(100, 180, 255))

    def handle_tag_direction(self, direction):
        """Handle numpad tag direction - set pending for click selection"""
        # Always set pending direction for click selection
        self.pending_tag_direction = direction
