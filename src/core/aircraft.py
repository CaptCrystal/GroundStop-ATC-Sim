"""
Aircraft management system
Handles aircraft spawning, state, and movement
"""
import random
import math
import logging
import re
import time
import string
import json
from typing import Dict, List, Optional, Tuple
from .location_awareness import LocationAwareness
from .airport_graph import AirportGraph
from src.core import atis_state, radio_hold
from src.atc.tower_controller import VirtualTowerController
from src.utils.geometry import point_in_polygon, closest_point_on_polygon, distance_to_polygon_edge

# Set up logging - use INFO level for performance (DEBUG is too verbose)
logging.basicConfig(
    level=logging.INFO,  # Changed from DEBUG to INFO for better performance
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('aircraft_debug.log', mode='w', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('Aircraft')
logger.setLevel(logging.INFO)  # Ensure logger uses INFO level

class Aircraft(LocationAwareness):
    """Represents a single aircraft with location awareness"""
    
    # Aircraft states
    STATE_PARKED = "parked"
    STATE_PUSHBACK = "pushback"
    STATE_TAXI = "taxi"
    STATE_HOLDING = "holding"
    STATE_TAKEOFF = "takeoff"
    STATE_APPROACH = "approach"  # On final approach, descending to runway
    STATE_LANDING = "landing"  # Touchdown and rollout on runway
    STATE_DEPARTED = "departed"
    
    # Load aircraft performance database
    _performance_data = None
    
    @classmethod
    def _load_performance_data(cls):
        """Load aircraft performance data from aircraft.json"""
        if cls._performance_data is None:
            try:
                with open('aircraft.json', 'r') as f:
                    aircraft_list = json.load(f)
                cls._performance_data = {ac['icao_code']: ac for ac in aircraft_list}
                logger.info(f"Loaded performance data for {len(cls._performance_data)} aircraft types")
            except Exception as e:
                logger.error(f"Failed to load aircraft performance data: {e}")
                cls._performance_data = {}
        return cls._performance_data
    
    def __init__(self, flight_number: str, aircraft_type: str, airline: str, 
                 position: Tuple[float, float], heading: float, gate: Optional[str] = None,
                 airport_data: Optional[Dict] = None, radio_callback=None, 
                 departure_route: Optional[Dict] = None, flight_type: str = "departure",
                 tts_voice: Optional[str] = None, aircraft_manager=None):
        # Initialize location awareness
        LocationAwareness.__init__(self)
        
        self.flight_number = flight_number
        self.aircraft_type = aircraft_type
        self.airline = airline
        self.flight_type = flight_type  # "departure" or "arrival"
        self.departure_route = departure_route  # Contains destination, exit, route, altitude
        self.position = position  # (lat, lon)
        self.initial_position = (position[0], position[1], heading)  # Store gate position with heading
        self.heading = heading  # degrees
        self.gate = gate
        self.airport_data = airport_data
        self.radio_callback = radio_callback  # Callback for radio transmissions
        self.aircraft_manager = aircraft_manager  # Reference to manager for action state checks
        self.handed_off_to_tower = False  # Track if aircraft has been handed off to tower
        self.tts_voice = tts_voice  # Voice to use for TTS announcements
        self.beacon = None  # Beacon code (squawk code) - will be assigned by AircraftManager
        self.cid = None  # Controller ID - will be assigned by AircraftManager
        
        # Mode C Squawk System
        self.squawking_mode_c = False  # Whether aircraft is currently squawking Mode C
        self.current_squawk_code = None  # Current squawk code being transmitted (may be incorrect)
        self.correct_squawk_code = None  # The correct squawk code that should be entered
        self.mode_c_delay = random.uniform(3.0, 8.0)  # Delay in seconds before Mode C activates (3-8 seconds)
        self.mode_c_activation_time = None  # When Mode C will activate (set after spawn)
        self.squawk_code_entry_delay = random.uniform(2.0, 5.0)  # Additional delay before correct code is entered
        self.squawk_code_entry_time = None  # When correct code will be entered
        self.rare_no_mode_c = random.random() < 0.05  # 5% chance aircraft calls without Mode C (very rare)
        self.atc_assigned_squawk = False  # True when ATC set squawk via sqXXXX; skip auto-correct
        self.atc_squawk_standby = False  # True when ATC said sqc standby; skip auto-activate Mode C
        
        self.state = self.STATE_PARKED
        self.speed = 0.0  # knots
        self.altitude = 0.0  # feet MSL (0 = on ground)
        self.target_altitude = 0.0  # Target altitude for approach/climb
        self.target_position = None
        self.target_heading = None
        self.route = []  # List of waypoints
        self.current_taxiway_index = 0  # Track which taxiway we're on in the route
        
        # Debug logging throttle
        self.last_waypoint_log_time = 0  # Throttle waypoint reached logs
        
        # Departure information
        self.exit_fix = None
        self.destination = None
        if departure_route:
            self.exit_fix = departure_route.get('exit', '')
            self.destination = departure_route.get('destination', '')
            logger.info(f"[{self.get_callsign()}] Assigned route: {self.destination} via {self.exit_fix} - {departure_route.get('route', 'N/A')}")
        
        # Data tag position (numpad direction: 8=N, 6=E, 2=S, 4=W, 9=NE, 3=SE, 1=SW, 7=NW)
        self.tag_direction = 8  # Default: North (above aircraft)
        
        # Sticky data tag anchor - stores the world position and pixel offset for the tag
        # The tag stays anchored until the aircraft moves outside the invisible bounding box
        self.tag_anchor_world_pos = None  # (lat, lon) aircraft world position when tag was anchored
        self.tag_anchor_offset = None  # (dx, dy) pixel offset from aircraft to tag when anchored
        
        # Load aircraft-specific performance data
        perf_db = self._load_performance_data()
        perf = perf_db.get(aircraft_type, {})
        
        # Physics parameters - from aircraft performance database
        # Add slight variation per aircraft for human-like behavior
        speed_variation = random.uniform(0.90, 1.10)
        accel_variation = random.uniform(0.85, 1.15)
        
        # Taxi performance (from aircraft.json)
        self.max_taxi_speed = perf.get('taxi_speed_kt', 20.0) * speed_variation  # knots
        self.acceleration = perf.get('taxi_accel_m_s2', 0.7) * accel_variation * 1.94384  # m/s² to knots/s
        self.deceleration = perf.get('taxi_brake_m_s2', 1.2) * accel_variation * 1.94384  # m/s² to knots/s
        self.max_turn_rate = perf.get('turn_rate_deg_s', 12.0)  # degrees per second
        self.target_speed = 0.0  # Target speed for smooth acceleration
        
        # Landing performance (from aircraft.json)
        self.landing_speed = perf.get('landing_speed_kt', 130.0)  # knots
        self.landing_deceleration = perf.get('landing_decel_m_s2', 1.8) * 1.94384  # m/s² to knots/s
        
        # Wake turbulence category (from aircraft.json)
        self.wake_category = perf.get('wake_turbulence_category', 'M')  # L, M, or H
        
        # Store full performance data for other uses
        self.performance = perf
        
        # Log performance parameters
        if perf:
            logger.info(f"[{self.get_callsign()}] Performance: {self.max_taxi_speed:.1f} kts, "
                       f"accel={self.acceleration:.2f} kts/s, turn={self.max_turn_rate:.1f}°/s, "
                       f"wake={self.wake_category}")
        else:
            logger.warning(f"[{self.get_callsign()}] No performance data for {aircraft_type}, using defaults")
        
        # Smooth interpolation for visual movement
        self.visual_position = list(position)  # Smoothed position for rendering
        self.visual_heading = heading  # Smoothed heading for rendering
        self.position_smoothing = 0.45  # Higher = smoother but more lag (increased for more fluid motion)
        self.heading_smoothing = 0.35  # Smooth heading changes for natural-looking turns
        
        # Human-like speed variation during taxi
        self.speed_variation_timer = 0.0
        self.speed_variation_factor = 1.0
        
        # ATC clearances
        self.cleared_to_pushback = False
        self.cleared_to_taxi = False
        self.taxi_destination = None
        self.taxi_via = []
        self.hold_short = None
        self.cleared_runways = []  # List of runways cleared to cross
        self.holding_short_runway = None  # Track which runway we're holding short of
        self.expected_runway = None  # Runway aircraft should expect for departure/arrival
        self.last_known_surface = None  # Track current surface (runway, taxiway, ramp) for tower clearances
        
        # Timing
        self.pushback_start_time = 0
        self.pushback_target = None  # Target position for pushback
        self.pushback_target_heading = None  # Target heading after pushback
        self.pushback_waypoints = []  # List of waypoints for pushback path
        self.pushback_waypoint_index = 0  # Current waypoint index in pushback path
        self.spawn_time = 0  # Time when aircraft spawned
        self.pushback_requested = False
        self.taxi_requested = False
        self.scheduled_pushback_time = None  # When aircraft should request pushback
        
        # Radio readback delay (2-4 seconds for realism)
        self.pending_radio_transmissions = []  # List of (time_to_send, message, is_atc) tuples
        self.pending_actions = []  # List of (time_to_execute, action_callback) tuples
        
        # Visual
        self.color = self._get_airline_color(airline)
        
        # Identify if this is a general aviation aircraft
        self.is_general_aviation = (airline == 'N')
        
        # Logging
        logger.info(f"[{self.get_callsign()}] Aircraft created at gate {gate}")
        logger.debug(f"[{self.get_callsign()}] Position: {position}, Heading: {heading}°")
        logger.debug(f"[{self.get_callsign()}] Type: {aircraft_type}, Airline: {airline}")
        
        # Note: Airport graph will be set by AircraftManager after creation
    
    def _get_airline_color(self, airline: str) -> Tuple[int, int, int]:
        """Get color for airline"""
        colors = {
            'AAY': (255, 0, 0),      # Allegiant - Red
            'ENY': (0, 100, 200),    # Envoy - Blue
            'EDV': (200, 0, 0),      # Endeavor - Dark Red
            'SKW': (0, 150, 200),    # SkyWest - Light Blue
            'Private': (100, 255, 100)  # Private - Green
        }
        return colors.get(airline, (255, 255, 0))  # Default yellow
    
    def update(self, dt: float, current_time: float):
        """Update aircraft state"""
        # Store current simulation time for radio scheduling
        self.current_sim_time = current_time
        
        # Handle Mode C squawk activation and code entry
        if self.mode_c_activation_time is None:
            # Set activation time on first update (after spawn)
            self.mode_c_activation_time = current_time + self.mode_c_delay
            self.squawk_code_entry_time = self.mode_c_activation_time + self.squawk_code_entry_delay
        
        # Check if Mode C should activate (skip when ATC commanded squawk standby via sqc)
        if not self.squawking_mode_c and not getattr(self, "atc_squawk_standby", False) and current_time >= self.mode_c_activation_time:
            self.squawking_mode_c = True
            # Always start with a random incorrect code (4 digits, each 0-7, octal)
            correct_str = str(self.correct_squawk_code).zfill(4) if self.correct_squawk_code else ""
            wrong_code = ""
            for _ in range(4):
                wrong_code += str(random.randint(0, 7))
            # Ensure it's different from the correct code
            max_attempts = 50
            while wrong_code == correct_str and max_attempts > 0:
                wrong_code = ""
                for _ in range(4):
                    wrong_code += str(random.randint(0, 7))
                max_attempts -= 1
            self.current_squawk_code = wrong_code
        
        # Check if correct code should be entered (skip when ATC explicitly assigned squawk via sqXXXX, or controller edited BCN on strip)
        if not getattr(self, "atc_assigned_squawk", False) and not getattr(self, "editor_bcn_override", False):
            correct_code_str = self.correct_squawk_code if self.correct_squawk_code else None
            if self.squawking_mode_c and self.current_squawk_code != correct_code_str and current_time >= self.squawk_code_entry_time:
                if self.correct_squawk_code:
                    self.current_squawk_code = self.correct_squawk_code  # Already a string
        
        # Update location awareness (skip for departed aircraft to save performance)
        if self.state != self.STATE_DEPARTED:
            self.update_location_awareness()
        
        # Process pending radio transmissions
        self._process_pending_radio(current_time)
        
        # Process pending actions (commands that execute after readback)
        self._process_pending_actions(current_time)
        
        # Auto-request pushback after spawn delay (skip for GA aircraft)
        # Only request if squawking Mode C with correct code
        # Check for ground stop / gate hold before allowing pushback request
        if self.state == self.STATE_PARKED and not self.pushback_requested:
            if self.scheduled_pushback_time and current_time >= self.scheduled_pushback_time:
                # Check for ATC action restrictions
                if self.aircraft_manager:
                    if self.aircraft_manager.ground_stop_active or self.aircraft_manager.emergency_stop_active:
                        # Ground stop - delay pushback indefinitely
                        return
                    if self.aircraft_manager.gate_hold_active:
                        # Gate hold - delay pushback indefinitely
                        return
                    if self.aircraft_manager.gdp_active and self.aircraft_manager.gdp_delay_minutes > 0:
                        # GDP - add delay to scheduled time (convert minutes to seconds)
                        gdp_delay = self.aircraft_manager.gdp_delay_minutes * 60
                        if current_time < self.scheduled_pushback_time + gdp_delay:
                            return
                
                # Check if can make radio call before requesting
                if self._can_make_radio_call():
                    if self.is_general_aviation:
                        # GA aircraft skip pushback and go directly to taxi
                        logger.info(f"[{self.get_callsign()}] GA aircraft ready to taxi (no pushback needed)")
                        self.pushback_requested = True  # Mark as done
                        
                        # Check if in GA apron - if so, can move autonomously
                        if self.is_in_ga_apron():
                            logger.info(f"[{self.get_callsign()}] GA aircraft in apron - autonomous movement enabled")
                            self.state = self.STATE_TAXI  # Go directly to taxi state
                            self.cleared_to_taxi = True  # Auto-clear for GA in apron
                            # Set random destination within apron
                            self.target_position = self.get_ga_apron_random_destination()
                            if self.target_position:
                                logger.info(f"[{self.get_callsign()}] Moving to random position in GA apron")
                        else:
                            # Not in GA apron, need ATC clearance
                            self.state = self.STATE_HOLDING
                            self.holding_start_time = current_time
                            self.taxi_request_delay = random.uniform(5, 15)
                            logger.info(f"[{self.get_callsign()}] Will request taxi in {self.taxi_request_delay:.1f}s")
                    else:
                        self.request_pushback()
                        self.pushback_requested = True
        
        # Auto-request taxi after pushback complete (or immediately for GA)
        if self.state == self.STATE_HOLDING and not self.taxi_requested and (self.cleared_to_pushback or self.is_general_aviation):
            # Request taxi to a random runway after 10-30 seconds (engine start, checks, etc.)
            if not hasattr(self, 'holding_start_time'):
                self.holding_start_time = current_time
                # Generate random delay for this specific aircraft (10-30 seconds)
                self.taxi_request_delay = random.uniform(10, 30)
                logger.info(f"[{self.get_callsign()}] Will request taxi in {self.taxi_request_delay:.1f}s")
            elif current_time - self.holding_start_time > self.taxi_request_delay:
                self._auto_request_taxi()
                self.taxi_requested = True
        
        # Check for emergency stop - freeze all ground movement
        if self.aircraft_manager and self.aircraft_manager.emergency_stop_active:
            if self.state in [self.STATE_PUSHBACK, self.STATE_TAXI]:
                # Emergency stop - don't update movement, aircraft freezes in place
                self.speed = 0
                return
        
        if self.state == self.STATE_PUSHBACK:
            self._update_pushback(dt)
        elif self.state == self.STATE_TAXI:
            self._update_taxi(dt)
        elif self.state == self.STATE_TAKEOFF:
            self._update_takeoff(dt)
        elif self.state == self.STATE_DEPARTED:
            self._update_departed(dt)
        elif self.state == self.STATE_APPROACH:
            self._update_approach(dt)
        elif self.state == self.STATE_LANDING:
            self._update_landing(dt)
        elif self.state == self.STATE_HOLDING:
            # Aircraft is holding - tower controller will manage clearances
            # For arrivals holding short, automatically give ground clearance after a delay
            if hasattr(self, 'holding_short_time'):
                # Check if enough time has passed for tower to give clearance
                if time.time() - self.holding_short_time > 3.0:  # 3 seconds delay
                    self.contact_ground_clearance_received()
                    if hasattr(self, 'holding_short_time'):
                        delattr(self, 'holding_short_time')
            else:
                # Set the holding short time when first entering holding state after landing
                if hasattr(self, 'expected_runway') and self.expected_runway:
                    self.holding_short_time = time.time()
                    logger.info(f"[{self.get_callsign()}] Holding short, waiting for tower clearance")
            
            # Check if aircraft is aligning heading for takeoff
            if hasattr(self, 'aligning_for_takeoff') and self.aligning_for_takeoff:
                if hasattr(self, 'target_heading'):
                    heading_diff = self._angle_difference(self.heading, self.target_heading)
                    
                    if abs(heading_diff) > 0.5:
                        # Continue rotating to target heading
                        turn_rate = 15.0  # degrees per second - slower rotation while stationary
                        max_turn = turn_rate * dt
                        
                        if abs(heading_diff) < max_turn:
                            self.heading = self.target_heading
                        else:
                            if heading_diff > 0:
                                self.heading = (self.heading + max_turn) % 360
                            else:
                                self.heading = (self.heading - max_turn) % 360
                        
                        # Update visual heading smoothly
                        heading_diff_visual = self._angle_difference(self.visual_heading, self.heading)
                        self.visual_heading = (self.visual_heading + heading_diff_visual * self.heading_smoothing) % 360
                        
                        logger.debug(f"[{self.get_callsign()}] Rotating: {self.heading:.1f}° (target: {self.target_heading:.1f}°)")
                    else:
                        # Heading aligned
                        self.heading = self.target_heading
                        self.visual_heading = self.target_heading
                        self.aligning_for_takeoff = False
                        self.lineup_complete = True
                        logger.info(f"[{self.get_callsign()}] ✅ HEADING ALIGNED - Lineup complete, ready for takeoff")
                        logger.info(f"[{self.get_callsign()}]   Final heading: {self.heading:.1f}°")
        elif self.state == self.STATE_PARKED:
            # Aircraft is parked, no movement
            pass
    
    def _process_pending_radio(self, current_time: float):
        """Process and send pending radio transmissions"""
        # Safety release: if the exchange lock somehow outlasts its timeout, clear it.
        if radio_hold.exchange_locked and current_time > radio_hold.hold_until:
            radio_hold.exchange_locked   = False
            radio_hold.priority_callsign = None
            radio_hold.hold_until        = 0.0

        # Block non-priority aircraft while an exchange is in progress or
        # while the controller is transmitting (hold_until in the future).
        is_priority = (self.get_callsign() == radio_hold.priority_callsign)
        if not is_priority:
            if radio_hold.exchange_locked:
                return
            if current_time < radio_hold.hold_until:
                return

        # Check if any transmissions are ready to send
        ready_to_send = [t for t in self.pending_radio_transmissions if t[0] <= current_time]

        for transmission in ready_to_send:
            if len(transmission) == 4:
                _, message, is_atc, frequency = transmission
            else:
                # Backward compatibility - old format without frequency
                _, message, is_atc = transmission
                frequency = None
            if self.radio_callback:
                self.radio_callback(message, is_atc=is_atc, callsign=self.get_callsign(), frequency=frequency)
            self.pending_radio_transmissions.remove(transmission)
    
    def _process_pending_actions(self, current_time: float):
        """Process and execute pending actions (commands that execute after readback)"""
        ready_to_execute = [a for a in self.pending_actions if a[0] <= current_time]
        
        for action in ready_to_execute:
            _, action_callback = action
            action_callback()  # Execute the action
            self.pending_actions.remove(action)
    
    # Phonetic alphabet for readbacks
    _PHONETICS = {
        'A': 'Alpha', 'B': 'Bravo', 'C': 'Charlie', 'D': 'Delta',
        'E': 'Echo', 'F': 'Foxtrot', 'G': 'Golf', 'H': 'Hotel',
        'I': 'India', 'J': 'Juliet', 'K': 'Kilo', 'L': 'Lima',
        'M': 'Mike', 'N': 'November', 'O': 'Oscar', 'P': 'Papa',
        'Q': 'Quebec', 'R': 'Romeo', 'S': 'Sierra', 'T': 'Tango',
        'U': 'Uniform', 'V': 'Victor', 'W': 'Whiskey', 'X': 'X-ray',
        'Y': 'Yankee', 'Z': 'Zulu',
    }

    def _phonetic(self, letter: str) -> str:
        """Convert single taxiway letter to phonetic word."""
        return self._PHONETICS.get(letter.upper(), letter.upper())

    def _via_phonetic(self, via: list) -> str:
        """Convert list of taxiway letters to space-separated phonetic string."""
        return ' '.join(self._phonetic(l) for l in via)

    def _generate_realistic_readback(self, clearance_type: str, details: Dict = None, include_callsign: bool = True) -> str:
        """Generate a realistic ATC readback message

        Args:
            clearance_type: Type of clearance (pushback, taxi, cross, hold, contact_tower,
                            expect_runway, follow_traffic, give_way, hold_short_taxiway, ...)
            details: Dictionary with details like runway, taxiways, destination, etc.
            include_callsign: Whether to include callsign (False for combined commands)

        Returns:
            str: Realistic readback message
        """
        if details is None:
            details = {}

        callsign = self.get_callsign() if include_callsign else ""
        callsign_suffix = f", {callsign}" if include_callsign else ""

        if clearance_type == "pushback":
            variations = [
                f"pushback approved{callsign_suffix}",
                f"push approved{callsign_suffix}",
                f"cleared to push{callsign_suffix}",
                f"pushing back{callsign_suffix}",
            ]
            return random.choice(variations)

        elif clearance_type == "taxi":
            destination = details.get('destination', '')
            via = details.get('via', [])

            if via:
                via_ph = self._via_phonetic(via)
                # ~35% chance of directional callouts when 2+ taxiways
                use_directional = random.random() < 0.35 and len(via) >= 2
                if use_directional:
                    directional_parts = []
                    for i, letter in enumerate(via):
                        ph = self._phonetic(letter)
                        if i == 0:
                            turn = random.choice(["right turn", "left turn"])
                            directional_parts.append(f"{turn} {ph}")
                        else:
                            turn = random.choice(["right", "left", ""])
                            directional_parts.append(f"{turn} {ph}".strip() if turn else ph)
                    dir_str = ', '.join(directional_parts)
                    if destination == "parking":
                        variations = [
                            f"taxi to parking via {dir_str}{callsign_suffix}",
                            f"parking via {dir_str}{callsign_suffix}",
                        ]
                    else:
                        variations = [
                            f"{destination} via {dir_str}{callsign_suffix}",
                            f"taxi {destination} via {dir_str}{callsign_suffix}",
                        ]
                else:
                    if destination == "parking":
                        variations = [
                            f"taxi to parking via {via_ph}{callsign_suffix}",
                            f"parking via {via_ph}{callsign_suffix}",
                            f"to the ramp via {via_ph}{callsign_suffix}",
                        ]
                    else:
                        variations = [
                            f"{destination} via {via_ph}{callsign_suffix}",
                            f"taxi to {destination} via {via_ph}{callsign_suffix}",
                            f"cleared to {destination} via {via_ph}{callsign_suffix}",
                        ]
            else:
                if destination == "parking":
                    variations = [f"taxi to parking{callsign_suffix}", f"to parking{callsign_suffix}"]
                else:
                    variations = [
                        f"{destination}{callsign_suffix}",
                        f"taxi to {destination}{callsign_suffix}",
                    ]
            return random.choice(variations)

        elif clearance_type == "cross":
            runway = details.get('runway', '')
            variations = [
                f"cross runway {runway}{callsign_suffix}",
                f"crossing runway {runway}{callsign_suffix}",
                f"cleared to cross runway {runway}{callsign_suffix}",
            ]
            return random.choice(variations)

        elif clearance_type == "hold":
            runway = details.get('runway', '')
            if runway:
                variations = [
                    f"hold short runway {runway}{callsign_suffix}",
                    f"holding short runway {runway}{callsign_suffix}",
                    f"hold short of runway {runway}{callsign_suffix}",
                ]
            else:
                variations = [
                    f"holding position{callsign_suffix}",
                    f"hold position{callsign_suffix}",
                    f"holding short{callsign_suffix}",
                ]
            return random.choice(variations)

        elif clearance_type == "hold_short_taxiway":
            taxiway = details.get('taxiway', '')
            twy_ph = self._phonetic(taxiway) if taxiway else "taxiway"
            variations = [
                f"hold short of {twy_ph}{callsign_suffix}",
                f"holding short of {twy_ph}{callsign_suffix}",
                f"hold short {twy_ph}{callsign_suffix}",
            ]
            return random.choice(variations)

        elif clearance_type == "follow_traffic":
            traffic = details.get('traffic', 'traffic ahead')
            variations = [
                f"following traffic{callsign_suffix}",
                f"traffic in sight, following{callsign_suffix}",
                f"we have the traffic, following{callsign_suffix}",
                f"following {traffic}{callsign_suffix}",
            ]
            return random.choice(variations)

        elif clearance_type == "give_way":
            taxiway = details.get('taxiway', '')
            twy_ph = self._phonetic(taxiway) if taxiway else ""
            if twy_ph:
                variations = [
                    f"giving way on {twy_ph}{callsign_suffix}",
                    f"holding for traffic on {twy_ph}{callsign_suffix}",
                    f"give way on {twy_ph}{callsign_suffix}",
                ]
            else:
                variations = [
                    f"giving way{callsign_suffix}",
                    f"holding for crossing traffic{callsign_suffix}",
                ]
            return random.choice(variations)

        elif clearance_type == "contact_tower":
            variations = [
                f"contact tower{callsign_suffix}",
                f"switching to tower{callsign_suffix}",
                f"tower, good day{callsign_suffix}",
                f"going to tower{callsign_suffix}",
            ]
            return random.choice(variations)

        elif clearance_type == "expect_runway":
            runway = details.get('runway', '')
            variations = [
                f"expect runway {runway}{callsign_suffix}",
                f"runway {runway}{callsign_suffix}",
                f"plan on runway {runway}{callsign_suffix}",
                f"we'll take runway {runway}{callsign_suffix}",
            ]
            return random.choice(variations)

        elif clearance_type == "ready_to_taxi":
            info = atis_state.current_atis_letter or random.choice(["alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel"])
            variations = [
                f"{callsign}, ready for taxi",
                f"{callsign}, request taxi",
                f"{callsign}, ready to go",
                f"Ground, {callsign}, request taxi",
                f"Ground, {callsign}, pushback complete, ready for taxi",
                f"{callsign}, off the block, ready to taxi with {info}",
                f"Ground, {callsign}, clear of the gate, request taxi",
                f"{callsign}, ready to taxi with information {info}",
                f"Ground, {callsign}, we're ready, request taxi with {info}",
            ]
            return random.choice(variations)

        elif clearance_type == "request_pushback":
            gate_str = details.get('gate', '')
            info = atis_state.current_atis_letter or random.choice(["alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel"])
            if gate_str:
                variations = [
                    f"{callsign} at {gate_str}, request pushback",
                    f"{callsign}, request pushback",
                    f"{callsign} at {gate_str}, ready for pushback",
                    f"Ground, {callsign} at {gate_str}, request push and start",
                    f"{callsign}, {gate_str}, request pushback and start",
                    f"Ground, {callsign} at {gate_str}, ready to push",
                    f"Ground, {callsign}, gate {gate_str}, request pushback with {info}",
                    f"{callsign} at {gate_str}, with {info}, request pushback",
                    f"Ground, {callsign}, holding at {gate_str}, request pushback",
                    f"{callsign} at gate {gate_str}, ready to push, with {info}",
                    f"Ground, {callsign} at {gate_str}, push and start request",
                    f"{callsign}, gate {gate_str}, requesting push and start",
                ]
            else:
                variations = [
                    f"{callsign}, request pushback",
                    f"{callsign}, ready for pushback",
                    f"Ground, {callsign}, request push and start",
                    f"{callsign}, request pushback and start",
                    f"Ground, {callsign}, request pushback with {info}",
                    f"{callsign}, with {info}, request pushback",
                    f"Ground, {callsign}, push and start request",
                ]
            return random.choice(variations)

        elif clearance_type == "clear_of_runway":
            runway = details.get('runway', '')
            variations = [
                f"{callsign}, clear of runway {runway}",
                f"{callsign}, clear of runway {runway}",
                f"Ground, {callsign}, clear of runway {runway}",
                f"{callsign}, off runway {runway}",
                f"Ground, {callsign}, off {runway}, request taxi to gate",
                f"{callsign}, clear of {runway}",
                f"Ground, {callsign}, runway {runway} clear, need taxi",
                f"{callsign}, vacated runway {runway}",
                f"Ground, {callsign}, we're clear of {runway}, looking for parking",
                f"Ground, {callsign}, clear of the active, runway {runway}",
            ]
            return random.choice(variations)

        elif clearance_type == "request_taxi_to_gate":
            gate = details.get('gate', '')
            variations = [
                f"{callsign}, request taxi to gate {gate}",
                f"{callsign}, taxi to gate {gate}",
                f"{callsign}, gate {gate} please",
                f"Ground, {callsign}, gate {gate}",
                f"{callsign}, request gate {gate}",
                f"Ground, {callsign}, clear of the runway, request taxi to gate {gate}",
                f"Ground, {callsign}, looking for gate {gate}",
            ]
            return random.choice(variations)
        
        # Default fallback
        return f"{callsign}"
    
    def _schedule_radio(self, message: str, is_atc: bool = False, delay: float = None, frequency: str = None):
        """Schedule a radio transmission to be sent after a delay
        
        Args:
            message: The message to transmit
            is_atc: Whether this is an ATC transmission (False for pilot)
            delay: Delay in seconds (0 for instant readback if not specified)
            frequency: Frequency type ('ground' or 'tower'), defaults based on flight_type
        
        Returns:
            float: The time when the transmission will be sent
        """
        if delay is None:
            delay = random.uniform(0.5, 2.0)  # Realistic readback delay (0.5-2 seconds)
        
        # Default frequency based on flight type
        if frequency is None:
            if self.flight_type == "arrival":
                # Arrivals use tower frequency during approach/landing, ground after clearing runway
                frequency = 'tower' if self.state in [self.STATE_APPROACH, self.STATE_LANDING] else 'ground'
            else:
                frequency = 'ground'
        
        # Use simulation time instead of wall clock time
        send_time = getattr(self, 'current_sim_time', 0.0) + delay
        self.pending_radio_transmissions.append((send_time, message, is_atc, frequency))
        if delay > 0:
            logger.debug(f"[{self.get_callsign()}] Scheduled radio transmission in {delay:.1f}s on {frequency}: {message}")
        return send_time
    
    def _schedule_action(self, action_callback, delay: float = None):
        """Schedule an action to execute after a delay
        
        Args:
            action_callback: Function to call when action executes
            delay: Delay in seconds (random 3-5 seconds if not specified)
        """
        if delay is None:
            delay = random.uniform(3.0, 5.0)  # Realistic delay for action execution
        
        execute_time = getattr(self, 'current_sim_time', 0.0) + delay
        self.pending_actions.append((execute_time, action_callback))
        logger.debug(f"[{self.get_callsign()}] Scheduled action in {delay:.1f}s")
    
    def _update_pushback(self, dt):
        """Update pushback movement - smooth, realistic pushback to ramp line"""
        #logger.debug(f"[{self.get_callsign()}] _update_pushback called, dt={dt:.3f}")
        
        # Initialize pushback target if not set
        if self.pushback_target is None:
            logger.debug(f"[{self.get_callsign()}] Getting pushback target...")
            self.pushback_target = self._get_pushback_target()
            if self.pushback_target:
                logger.info(f"[{self.get_callsign()}] Pushback target: {self.pushback_target}")
                logger.debug(f"[{self.get_callsign()}] Distance to pushback spot: {self._distance(self.position, self.pushback_target):.6f}°")
                
                # Initialize smooth movement parameters
                self.pushback_speed = 0.0  # Start from rest
                self.pushback_max_speed = random.uniform(1.8, 2.2)  # Variable max speed for realism
                self.pushback_acceleration = 0.5  # m/s² - smooth acceleration
                self.pushback_deceleration_distance = self._calculate_deceleration_distance()
                
                # Smooth the waypoint path to eliminate sharp corners
                if self.pushback_waypoints:
                    self.pushback_waypoints = self._smooth_pushback_path(self.pushback_waypoints)
            else:
                logger.error(f"[{self.get_callsign()}] ERROR: Failed to get pushback target!")
                return
        
        # Move towards pushback target
        lat, lon = self.position
        target_lat, target_lon = self.pushback_target
        initial_lat, initial_lon, initial_heading = self.initial_position
        
        # Calculate total pushback distance (from gate to spot) - do this once
        if not hasattr(self, 'pushback_total_distance'):
            self.pushback_total_distance = math.sqrt((target_lat - initial_lat)**2 + (target_lon - initial_lon)**2)
            self.pushback_distance_traveled = 0.0
            logger.debug(f"[{self.get_callsign()}] Total pushback distance: {self.pushback_total_distance:.6f}° (~{self.pushback_total_distance * 111000:.1f}m)")
        
        # Calculate distance remaining to target
        dlat = target_lat - lat
        dlon = target_lon - lon
        distance_remaining = math.sqrt(dlat**2 + dlon**2)
        
        # Check if waypoint reached
        waypoint_threshold = 0.00001  # Close enough threshold
        if distance_remaining < waypoint_threshold:
            # If using waypoint path, advance to next waypoint
            if self.pushback_waypoints and self.pushback_waypoint_index < len(self.pushback_waypoints) - 1:
                self.pushback_waypoint_index += 1
                self.pushback_target = self.pushback_waypoints[self.pushback_waypoint_index]
                logger.debug(f"[{self.get_callsign()}] Reached pushback waypoint {self.pushback_waypoint_index}/{len(self.pushback_waypoints)}")
                # Reset speed for smooth transition to next waypoint
                self.pushback_speed *= 0.7  # Slight speed reduction for waypoint transition
                return  # Continue to next waypoint
            else:
                # Final waypoint reached or no waypoints - pushback complete
                if self.pushback_target_heading is not None:
                    self.heading = self.pushback_target_heading
                logger.info(f"[{self.get_callsign()}] Pushback complete, rotated to heading {self.heading:.0f}°, now HOLDING")
                logger.debug(f"[{self.get_callsign()}] Final position: {self.position}")
                self.state = self.STATE_HOLDING
                self.speed = 0
                return
        
        # Smooth acceleration and deceleration
        distance_remaining_m = distance_remaining * 111000  # Convert to meters
        
        if distance_remaining_m < self.pushback_deceleration_distance:
            # Decelerate smoothly as we approach target
            target_speed = math.sqrt(2 * self.pushback_acceleration * distance_remaining_m)
            target_speed = min(target_speed, self.pushback_max_speed)
        else:
            # Accelerate to max speed
            target_speed = self.pushback_max_speed
        
        # Smooth speed changes (avoid instant speed changes)
        speed_change_rate = 2.0  # m/s² - maximum rate of speed change
        if self.pushback_speed < target_speed:
            self.pushback_speed = min(self.pushback_speed + speed_change_rate * dt, target_speed)
        elif self.pushback_speed > target_speed:
            self.pushback_speed = max(self.pushback_speed - speed_change_rate * dt, target_speed)
        
        # Add subtle speed variation for realism
        speed_variation = math.sin(time.time() * 2.0) * 0.1 + 1.0
        actual_speed = self.pushback_speed * speed_variation
        
        # Convert: m/s → degrees
        move_distance = (actual_speed * dt) / 111000.0  # Convert to degrees
        
        # Don't overshoot
        if move_distance > distance_remaining:
            move_distance = distance_remaining
        
        # Calculate direction to target
        direction_to_target = math.atan2(dlon, dlat)
        
        # Smooth heading changes for waypoint paths
        if self.pushback_waypoints:
            # Calculate desired heading to move toward waypoint (backwards)
            desired_movement_direction = direction_to_target
            desired_heading = (math.degrees(desired_movement_direction) + 180) % 360
            
            # Smooth heading transition
            heading_diff = self._angle_difference(self.heading, desired_heading)
            max_turn_rate = 30  # degrees per second - smooth turn rate
            
            if abs(heading_diff) > max_turn_rate * dt:
                # Turn smoothly toward desired heading
                turn_direction = 1 if heading_diff > 0 else -1
                self.heading = (self.heading + turn_direction * max_turn_rate * dt) % 360
            else:
                # Close enough, snap to desired heading
                self.heading = desired_heading
            
            # Move backward in current heading direction
            movement_direction = math.radians(self.heading + 180)
        else:
            # Original two-phase pushback with smooth transitions
            straight_distance = self.pushback_total_distance * 0.75
            
            if self.pushback_distance_traveled < straight_distance:
                # Phase 1: Straight pushback along gate centerline
                self.heading = initial_heading
                movement_direction = math.radians(self.heading + 180)
            else:
                # Phase 2: Smooth arc toward pushback spot while rotating
                arc_distance_traveled = self.pushback_distance_traveled - straight_distance
                arc_total_distance = self.pushback_total_distance - straight_distance
                arc_progress = arc_distance_traveled / arc_total_distance if arc_total_distance > 0 else 1.0
                
                # Smooth easing function for more natural movement
                eased_progress = self._smooth_ease(arc_progress)
                
                # Calculate target heading for final position
                if self.pushback_target_heading is not None:
                    target_hdg = self.pushback_target_heading
                else:
                    target_hdg = (math.degrees(direction_to_target) + 180) % 360
                
                # Smoothly interpolate heading during arc
                heading_diff = self._angle_difference(initial_heading, target_hdg)
                self.heading = (initial_heading + heading_diff * eased_progress) % 360
                
                # Move backward in current heading direction
                movement_direction = math.radians(self.heading + 180)
        
        # Apply movement
        new_lat = lat + math.cos(movement_direction) * move_distance
        new_lon = lon + math.sin(movement_direction) * move_distance
        self.position = (new_lat, new_lon)
        
        self.visual_position[0] += (new_lat - self.visual_position[0]) * self.position_smoothing
        self.visual_position[1] += (new_lon - self.visual_position[1]) * self.position_smoothing
        
        # Smooth visual heading interpolation
        heading_diff_visual = self._angle_difference(self.visual_heading, self.heading)
        self.visual_heading = (self.visual_heading + heading_diff_visual * self.heading_smoothing) % 360
        
        # Track distance traveled
        self.pushback_distance_traveled += move_distance
    
    def _calculate_deceleration_distance(self):
        """Calculate distance needed for smooth deceleration"""
        # Distance = v²/(2a) where v is max speed and a is acceleration
        return (self.pushback_max_speed ** 2) / (2 * self.pushback_acceleration)
    
    def _smooth_ease(self, t):
        """Smooth easing function for natural movement (0 to 1)"""
        # Use cubic easing for smooth acceleration and deceleration
        return t * t * (3.0 - 2.0 * t)
    
    def _smooth_pushback_path(self, waypoints):
        """Smooth pushback path by adding intermediate points at sharp corners"""
        if len(waypoints) < 3:
            return waypoints  # No corners to smooth
        
        smoothed_path = [waypoints[0]]  # Keep first point
        
        for i in range(1, len(waypoints) - 1):
            prev_point = waypoints[i - 1]
            current_point = waypoints[i]
            next_point = waypoints[i + 1]
            
            # Calculate angles at current point
            angle_in = math.atan2(current_point[0] - prev_point[0], current_point[1] - prev_point[1])
            angle_out = math.atan2(next_point[0] - current_point[0], next_point[1] - current_point[1])
            
            # Calculate angle difference
            angle_diff = abs(angle_in - angle_out)
            # Normalize to [0, π]
            if angle_diff > math.pi:
                angle_diff = 2 * math.pi - angle_diff
            
            # If angle is sharp (more than 25 degrees), add smoothing points
            if angle_diff > math.radians(10):
                # Calculate smoothing radius based on angle sharpness
                smoothing_radius = min(0.00005, 0.00002 * (angle_diff / math.radians(90)))
                
                # Add intermediate points to create rounded corner
                num_intermediate = min(3, max(2, int(angle_diff / math.radians(20))))
                
                for j in range(1, num_intermediate + 1):
                    t = j / (num_intermediate + 1)
                    
                    # Use quadratic Bezier curve for smooth corner
                    # Control point is offset from the corner
                    control_offset = smoothing_radius * 0.5
                    
                    # Calculate control point (perpendicular to angle bisector)
                    angle_bisector = (angle_in + angle_out) / 2
                    control_lat = current_point[0] + math.cos(angle_bisector + math.pi/2) * control_offset
                    control_lon = current_point[1] + math.sin(angle_bisector + math.pi/2) * control_offset
                    
                    # Quadratic Bezier interpolation
                    smooth_point = (
                        (1-t)**2 * prev_point[0] + 2*(1-t)*t * control_lat + t**2 * next_point[0],
                        (1-t)**2 * prev_point[1] + 2*(1-t)*t * control_lon + t**2 * next_point[1]
                    )
                    
                    smoothed_path.append(smooth_point)
            else:
                # Angle is not sharp enough to need smoothing
                smoothed_path.append(current_point)
        
        smoothed_path.append(waypoints[-1])  # Keep last point
        return smoothed_path
    
    def _get_pushback_target(self) -> Tuple[float, float]:
        """Get pushback target position from pushback points or spots data"""
        if not self.airport_data or not self.gate:
            return self._calculate_simple_pushback_target()
        
        # Find the gate data
        gate_data = None
        for gate in self.airport_data.get('gates', []):
            if gate.get('name') == self.gate:
                gate_data = gate
                break
        
        if not gate_data:
            return self._calculate_simple_pushback_target()
        
        # Check for pushback_points first (new method with waypoint path)
        pushback_points = gate_data.get('pusback_points')  # Note: typo in JSON "pusback" not "pushback"
        if pushback_points and len(pushback_points) > 0:
            # Recursively extract all valid point dicts from potentially mixed structure
            all_points = []
            
            def extract_points(data):
                """Recursively extract point dicts from nested structure"""
                if isinstance(data, dict) and 'x' in data and 'y' in data:
                    # This is a point dict
                    all_points.append(data)
                elif isinstance(data, list):
                    # This is a list, recurse into it
                    for item in data:
                        extract_points(item)
            
            extract_points(pushback_points)
            
            if all_points and len(all_points) > 0:
                # Store the full path for the aircraft to follow
                self.pushback_waypoints = [(p.get('x'), p.get('y')) for p in all_points if p.get('x') and p.get('y')]
                self.pushback_waypoint_index = 0
                
                # Return the first waypoint as initial target
                if self.pushback_waypoints:
                    logger.info(f"[{self.get_callsign()}] Using pushback waypoint path with {len(self.pushback_waypoints)} points")
                    return self.pushback_waypoints[0]
        
        # Fallback to pushback spot (old method)
        pushback_spot_name = gate_data.get('pushback_spot')
        if not pushback_spot_name:
            return self._get_pushback_target_from_ramp()
        
        # Find the pushback spot
        pushback_spots = self.airport_data.get('pushback_spots', [])
        for spot in pushback_spots:
            if spot.get('pushback_spot') == pushback_spot_name:
                points = spot.get('points', [])
                if points and len(points) > 0:
                    point = points[0]
                    target_lat = point.get('x')
                    target_lon = point.get('y')
                    target_heading = spot.get('Degrees')
                    
                    if target_lat and target_lon:
                        # Store target heading for rotation after pushback
                        self.pushback_target_heading = target_heading
                        logger.info(f"[{self.get_callsign()}] Pushback to spot {pushback_spot_name}, heading {target_heading}°")
                        return (target_lat, target_lon)
        
        # Fallback if spot not found
        return self._get_pushback_target_from_ramp()
    
    def _get_pushback_target_from_ramp(self) -> Tuple[float, float]:
        """Fallback: Get pushback target from ramp data (old method)"""
        if not self.airport_data or not self.gate:
            return self._calculate_simple_pushback_target()
        
        # Try to find the ramp this gate connects to
        gate_data = None
        for gate in self.airport_data.get('gates', []):
            if gate.get('name') == self.gate:
                gate_data = gate
                break
        
        if not gate_data:
            return self._calculate_simple_pushback_target()
        
        ramp_name = gate_data.get('connects_to')
        if not ramp_name:
            return self._calculate_simple_pushback_target()
        
        # Find the ramp
        main_ramp = None
        for ramp in self.airport_data.get('ramps', []):
            if ramp.get('ramp') == ramp_name:
                main_ramp = ramp
                break
        
        if not main_ramp:
            return None
        
        points = main_ramp.get('points', [])
        if len(points) < 2:
            return None
        
        # Find nearest point on ramp line to current position
        lat, lon = self.position
        min_dist = float('inf')
        nearest_point = None
        
        for point in points:
            p_lat = point.get('x')
            p_lon = point.get('y')
            if p_lat and p_lon:
                dist = math.sqrt((p_lat - lat)**2 + (p_lon - lon)**2)
                if dist < min_dist:
                    min_dist = dist
                    nearest_point = (p_lat, p_lon)
        
        return nearest_point
    
    def _calculate_simple_pushback_target(self) -> Tuple[float, float]:
        """Calculate simple pushback target (backwards from gate)"""
        # Push back 50 meters (roughly 0.00045 degrees)
        pushback_distance = 0.00045
        rad = math.radians(self.heading + 180)  # Opposite direction
        
        lat, lon = self.initial_position
        target_lat = lat + pushback_distance * math.cos(rad)
        target_lon = lon + pushback_distance * math.sin(rad)
        
        return (target_lat, target_lon)
    
    def _update_taxi(self, dt: float):
        """Update taxi movement - follow pre-built route with realistic physics and turn radius"""
        # GA aircraft: Check and constrain to apron boundaries (throttled for performance)
        if self.is_general_aviation and self.is_in_ga_apron():
            # Only check boundaries every 0.5 seconds to reduce overhead
            if not hasattr(self, '_last_boundary_check'):
                self._last_boundary_check = 0
            
            current_time = time.time()
            if current_time - self._last_boundary_check > 0.5:
                self.constrain_to_ga_apron()
                self._last_boundary_check = current_time
            
            # If GA aircraft reaches destination in apron, pick new random destination
            if self.target_position:
                lat, lon = self.position
                target_lat, target_lon = self.target_position
                distance = math.sqrt((target_lat - lat)**2 + (target_lon - lon)**2)
                
                # If within 5 meters of target
                if distance < 0.000045:
                    logger.info(f"[{self.get_callsign()}] GA aircraft reached destination in apron")
                    # Wait a bit, then pick new destination
                    if random.random() < 0.3:  # 30% chance to pick new destination each update
                        new_dest = self.get_ga_apron_random_destination()
                        if new_dest:
                            self.target_position = new_dest
                            logger.info(f"[{self.get_callsign()}] GA aircraft moving to new position in apron")
        
        # Clear any runway clearances if not currently cleared to lineup
        # This prevents aircraft from having old clearances from previous sessions
        # Only keep clearances if we've been explicitly cleared to lineup by tower
        if self.cleared_runways and not hasattr(self, 'tower_cleared_to_lineup'):
            logger.info(f"[{self.get_callsign()}] Clearing stale runway clearances: {self.cleared_runways}")
            self.cleared_runways = []
        
        # Check if aircraft has lineup clearance and should switch to direct lineup upon runway entry
        if hasattr(self, 'tower_cleared_to_lineup') and self.tower_cleared_to_lineup:
            if hasattr(self, 'lineup_target_position') and not hasattr(self, '_switched_to_lineup'):
                # Check if we've entered the runway polygon
                lat, lon = self.position
                if self.airport_data:
                    runways = self.airport_data.get('runways', [])
                    for runway in runways:
                        # Check if inside runway polygon
                        if self._is_inside_runway_polygon(lat, lon, runway):
                            runway_name = runway.get('name', '')
                            logger.info(f"[{self.get_callsign()}] 🛬 ENTERED RUNWAY POLYGON: {runway_name}")
                            logger.info(f"[{self.get_callsign()}] Switching to direct lineup mode")
                            
                            # Clear taxiway route and go direct to lineup position
                            self.route = []
                            self.taxi_via = None
                            self.target_position = self.lineup_target_position
                            
                            # Start rotating to runway heading
                            if hasattr(self, 'lineup_runway_heading'):
                                self.target_heading = self.lineup_runway_heading
                                logger.info(f"[{self.get_callsign()}] 🧭 Rotating to runway heading: {self.lineup_runway_heading}°")
                            
                            # Mark that we've switched to prevent repeated switching
                            self._switched_to_lineup = True
                            
                            logger.info(f"[{self.get_callsign()}] 🎯 Direct to lineup: {self.lineup_target_position}")
                            break
        
        if self.target_position:
            # Calculate direction to target
            lat, lon = self.position
            target_lat, target_lon = self.target_position
            
            dlat = target_lat - lat
            dlon = target_lon - lon
            distance = math.sqrt(dlat**2 + dlon**2)
            distance_meters = distance * 111000.0  # Convert to meters for turn calculations
            
            # Progressive hold short braking — start decelerating ~90 m out,
            # come to rest ~18 m before the bar (realistic hold short position).
            if self.airport_data:
                _hs = self._check_holdshort_approach()
                if _hs is not None:
                    _hs_dist, _hs_runway = _hs
                    _STOP_DIST   = 18.0   # metres — realistic stop before markings
                    _BRAKE_START = 90.0   # metres — begin slowing down

                    if _hs_dist <= _STOP_DIST:
                        # At hold short position — decelerate to a full stop
                        self.target_speed = 0.0
                        self.speed = max(0.0, self.speed - self.deceleration * dt * 2.5)
                        if self.speed < 0.3:
                            self.speed = 0.0

                        if self.state != self.STATE_HOLDING:
                            if self.holding_short_runway != _hs_runway:
                                self.hold_short = _hs_runway
                                self.holding_short_runway = _hs_runway
                                self.cleared_runways = []
                                logger.warning(
                                    f"[{self.get_callsign()}] ✋ HOLDING SHORT of runway {_hs_runway}"
                                )
                            self.state = self.STATE_HOLDING
                        return

                    elif _hs_dist <= _BRAKE_START:
                        # Braking zone — limit target speed proportionally to distance remaining
                        _hs_factor = (_hs_dist - _STOP_DIST) / (_BRAKE_START - _STOP_DIST)
                        _hs_brake = self.max_taxi_speed * _hs_factor * 0.65
                        self.target_speed = min(self.target_speed, _hs_brake)
                        # Fall through to normal movement — do NOT return
            
            # Check for taxiway intersections during movement
            if hasattr(self, 'taxi_via') and self.taxi_via and self.airport_data:
                self._check_and_switch_taxiway()
            
            # Determine if we're in lineup mode (going direct to lineup position)
            in_lineup_mode = (hasattr(self, '_switched_to_lineup') and self._switched_to_lineup)
            
            # PREDICTIVE STEERING: Look ahead on the path to calculate smooth target heading
            # Instead of aiming directly at next waypoint, we aim at a "carrot" point ahead
            # This creates smooth, natural curves like a real pilot following a path
            # DISABLE for lineup mode to ensure precise positioning
            
            if in_lineup_mode:
                # Direct steering to lineup position - no predictive carrot
                target_heading = math.degrees(math.atan2(dlon, dlat)) % 360
            else:
                # Calculate look-ahead distance based on speed (faster = look further ahead)
                # This gives the aircraft time to anticipate and smoothly enter turns
                look_ahead_distance = max(0.00015, (self.speed / self.max_taxi_speed) * 0.0003)  # 15-30m ahead
                
                # Find the "carrot" point: a point on our path that's look_ahead_distance away
                carrot_lat, carrot_lon = self._calculate_carrot_point(lat, lon, look_ahead_distance)
                
                # Calculate target heading toward the carrot point (not just next waypoint)
                carrot_dlat = carrot_lat - lat
                carrot_dlon = carrot_lon - lon
                target_heading = math.degrees(math.atan2(carrot_dlon, carrot_dlat)) % 360
            
            # Waypoint reached check - use dynamic threshold based on speed
            # Faster aircraft need larger threshold to avoid overshooting
            # Use smaller threshold in lineup mode for precise positioning
            if in_lineup_mode:
                waypoint_threshold = 0.00003  # ~3.3 meters - very precise for lineup
            else:
                base_threshold = 0.00005  # ~5.5 meters
                speed_factor = max(0.5, self.speed / self.max_taxi_speed)
                waypoint_threshold = base_threshold * (1.0 + speed_factor)
            
            # Check if waypoint reached
            if distance < waypoint_threshold:
                if self.route:
                    # Throttle logging to once per second
                    current_time = time.time()
                    if current_time - self.last_waypoint_log_time >= 1.0:
                        logger.debug(f"[{self.get_callsign()}] Reached waypoint {self.target_position}")
                        self.last_waypoint_log_time = current_time
                    
                    self.target_position = self.route.pop(0)
                    logger.debug(f"[{self.get_callsign()}] Next waypoint: {self.target_position}, {len(self.route)} remaining")
                else:
                    # Route complete - check if arrival at gate or departure at runway
                    if self.state != self.STATE_HOLDING:
                        # Check if this is an arrival reaching its gate
                        if self.flight_type == "arrival" and self.gate and self.taxi_destination and "gate" in self.taxi_destination.lower():
                            # Arrival reached gate - park the aircraft
                            self.state = self.STATE_PARKED
                            self.target_speed = 0
                            self.speed = 0
                            self.cleared_to_taxi = False
                            logger.info(f"[{self.get_callsign()}] 🅿️ ARRIVED at gate {self.gate}")
                            
                            # Radio call
                            if self.radio_callback:
                                self._schedule_radio(
                                    f"{self.get_callsign()}, at gate {self.gate}",
                                    is_atc=False,
                                    delay=random.uniform(1, 2),
                                    frequency='ground'
                                )
                            return
                        
                        # Transition to HOLDING first
                        self.state = self.STATE_HOLDING
                        self.target_speed = 0
                        self.speed = 0  # Stop immediately
                        logger.info(f"[{self.get_callsign()}] State changed to HOLDING")
                        
                        # Check if this is lineup completion
                        if in_lineup_mode:
                            logger.info(f"[{self.get_callsign()}] At lineup position")
                            logger.info(f"[{self.get_callsign()}]   Position: {self.position}")
                            logger.info(f"[{self.get_callsign()}]   Heading: {self.heading:.1f}°")
                            
                            # Check if heading is aligned with runway before marking complete
                            if hasattr(self, 'lineup_runway_heading'):
                                heading_diff = abs(self._angle_difference(self.heading, self.lineup_runway_heading))
                                if heading_diff > 5.0:  # Not aligned yet
                                    logger.info(f"[{self.get_callsign()}] ⏳ Aligning heading to runway: {self.heading:.1f}° -> {self.lineup_runway_heading:.1f}° (diff: {heading_diff:.1f}°)")
                                    # Set flag to continue rotating in HOLDING state
                                    self.aligning_for_takeoff = True
                                    self.target_heading = self.lineup_runway_heading
                                    return
                            
                            # Heading is aligned, lineup complete
                            logger.info(f"[{self.get_callsign()}] ✅ LINEUP COMPLETE - Ready for takeoff")
                            self.lineup_complete = True
                        else:
                            logger.info(f"[{self.get_callsign()}] Route complete, now HOLDING")
                    return
            
            # Realistic speed control with look-ahead for upcoming turns
            heading_diff = self._angle_difference(self.heading, target_heading)
            
            # Look ahead to next waypoint to anticipate turns
            upcoming_turn_angle = 0
            distance_to_turn = float('inf')
            if self.route and len(self.route) > 0:
                next_waypoint = self.route[0]
                next_lat, next_lon = next_waypoint
                current_target_lat, current_target_lon = self.target_position
                
                # Calculate angle change at next waypoint
                current_direction = math.degrees(math.atan2(current_target_lon - lon, current_target_lat - lat)) % 360
                next_direction = math.degrees(math.atan2(next_lon - current_target_lat, next_lat - current_target_lat)) % 360
                upcoming_turn_angle = abs(self._angle_difference(current_direction, next_direction))
                
                # Calculate distance to the turn point
                distance_to_turn = distance_meters
            
            # Human-like speed variation (pilots don't maintain perfectly constant speed)
            self.speed_variation_timer += dt
            if self.speed_variation_timer > random.uniform(3.0, 8.0):
                # Randomly vary speed slightly every few seconds
                self.speed_variation_factor = random.uniform(0.92, 1.08)
                self.speed_variation_timer = 0.0
            
            # Calculate target speed based on current turn angle, upcoming turn, and distance
            # Use realistic turn radius calculations
            max_turn = max(abs(heading_diff), upcoming_turn_angle)
            
            # Calculate required turn radius for current speed (in meters)
            # Formula: radius = velocity^2 / (g * tan(bank_angle))
            # For ground ops, we use a simplified model based on turn rate
            # Tighter turns require slower speeds to maintain centerline
            
            # Determine target speed based on turn severity and distance to turn
            if max_turn > 90:  # Very sharp / U-turn
                self.target_speed = self.max_taxi_speed * 0.22
                if distance_to_turn < 30 and upcoming_turn_angle > 90:
                    self.target_speed = self.max_taxi_speed * 0.18
            elif max_turn > 70:  # Sharp turn (70-90°)
                self.target_speed = self.max_taxi_speed * 0.35
                if distance_to_turn < 40 and upcoming_turn_angle > 70:
                    self.target_speed = self.max_taxi_speed * 0.30
            elif max_turn > 45:  # Medium turn (45-70°)
                self.target_speed = self.max_taxi_speed * 0.48
                if distance_to_turn < 50 and upcoming_turn_angle > 45:
                    self.target_speed = self.max_taxi_speed * 0.43
            elif max_turn > 15:  # Slight-to-moderate turn (15-45°)
                self.target_speed = self.max_taxi_speed * 0.62
                if len(self.route) > 2:
                    upcoming_turn_angle = self._calculate_turn_angle(self.route[1], self.route[2])
                    distance_to_turn = self._calculate_distance(lat, lon, self.route[1][0], self.route[1][1]) * 111000
                    if distance_to_turn < 70 and upcoming_turn_angle > 15:
                        self.target_speed = self.max_taxi_speed * 0.68
            elif max_turn > 5:  # Gentle curve (5-15°)
                self.target_speed = self.max_taxi_speed * 0.85
            elif distance_meters < 10:  # Very close to waypoint
                self.target_speed = self.max_taxi_speed * 0.65
            else:  # Straight taxi
                self.target_speed = self.max_taxi_speed + 3
            
            # Apply human-like speed variation
            self.target_speed *= self.speed_variation_factor

            # Anticipatory braking for final waypoint — coast to a stop rather
            # than arriving at full speed.  Only active on the last segment
            # (self.route is empty) so intermediate waypoints are unaffected.
            if not self.route and distance_meters < 45.0:
                _dest_factor = max(0.08, distance_meters / 45.0)
                self.target_speed = min(self.target_speed, self.max_taxi_speed * _dest_factor * 0.75)

            # ── Ground conflict separation ──────────────────────────────────
            # Hold behind any aircraft that is directly ahead on the taxiway.
            # < 30 m  → hard brake to a stop
            # 30–70 m → proportional slow-down
            _traffic_dist = self._get_traffic_ahead_distance()
            if _traffic_dist is not None:
                if _traffic_dist < 30.0:
                    self.target_speed = 0.0
                    # Apply braking directly so we stop before reaching the aircraft
                    self.speed = max(0.0, self.speed - self.deceleration * dt)
                elif _traffic_dist < 70.0:
                    _factor = (_traffic_dist - 30.0) / 40.0  # 0 at 30 m → 1 at 70 m
                    self.target_speed = min(
                        self.target_speed,
                        self.max_taxi_speed * _factor * 0.55,
                    )
            # ───────────────────────────────────────────────────────────────

            # Smooth acceleration/deceleration with realistic engine spool-up.
            # Slower smoothing from a standstill — aircraft don't jump to speed instantly.
            speed_diff = self.target_speed - self.speed
            if abs(speed_diff) > 0.01:
                if self.speed < 2.0:
                    smoothing_factor = 0.05   # Gradual roll-out from a stop
                elif self.speed < 5.0:
                    smoothing_factor = 0.10   # Building speed
                else:
                    smoothing_factor = 0.15   # Normal cruise response
                self.speed += speed_diff * smoothing_factor
            else:
                self.speed = self.target_speed
            
            # PREDICTIVE TURNING: Start turning early based on upcoming path curvature
            # This makes the aircraft anticipate turns rather than react to waypoints
            
            # Calculate path curvature (how much the path is curving ahead)
            path_curvature = self._calculate_path_curvature(lat, lon)
            
            # Adjust heading response based on path curvature
            # More curvature = more aggressive steering to stay on path
            curvature_factor = 1.0 + (path_curvature * 0.5)  # Up to 50% more responsive in curves
            
            # Smooth, continuous turning - aircraft turns while moving
            if abs(heading_diff) > 0.5:  # Only turn if difference is significant
                # Calculate smooth turn rate that maintains forward motion
                # Turn rate is constant regardless of speed for smooth visual appearance
                
                # Base turn rate - smooth and continuous
                turn_severity = abs(heading_diff)
                if turn_severity > 90:
                    # Very sharp turn - still turn smoothly but slower
                    turn_rate_multiplier = 0.7
                elif turn_severity > 45:
                    # Sharp turn - moderate turn rate
                    turn_rate_multiplier = 0.85
                else:
                    # Normal turn - full turn rate
                    turn_rate_multiplier = 1.0
                
                # Calculate final turn rate (degrees per second)
                # Use constant turn rate for smooth visual appearance
                base_turn_rate = self.max_turn_rate * turn_rate_multiplier
                max_turn_this_frame = base_turn_rate * dt
                
                # Apply curvature factor for more responsive steering in curves
                max_turn_this_frame *= curvature_factor
                
                if abs(heading_diff) < max_turn_this_frame:
                    # Close to target - use smooth interpolation to prevent oscillation
                    heading_smoothing = 0.5  # Smooth final approach to target heading
                    self.heading = (self.heading + heading_diff * heading_smoothing) % 360
                else:
                    # Turn towards target heading at calculated rate
                    if heading_diff > 0:
                        self.heading = (self.heading + max_turn_this_frame) % 360
                    else:
                        self.heading = (self.heading - max_turn_this_frame) % 360
            
            # REALISTIC MOVEMENT: Aircraft can ONLY move forward in their heading direction
            # They cannot move sideways - steering is done by rotating first, then moving forward
            # This creates realistic curved paths with proper turn radius
            # Convert speed (knots) to movement distance (degrees)
            # 1 knot = 0.514444 m/s, 1 degree ≈ 111000 m
            move_distance = (self.speed * 0.514444 * dt) / 111000.0
            
            if move_distance > 0:
                # Move FORWARD in the current heading direction only (no sideways movement)
                rad = math.radians(self.heading)
                new_lat = lat + move_distance * math.cos(rad)
                new_lon = lon + move_distance * math.sin(rad)
                
                # Smooth visual position interpolation for rendering
                # This eliminates jerky movement by gradually moving towards actual position
                self.visual_position[0] += (new_lat - self.visual_position[0]) * self.position_smoothing
                self.visual_position[1] += (new_lon - self.visual_position[1]) * self.position_smoothing
                
                # Smooth visual heading interpolation
                heading_diff_visual = self._angle_difference(self.visual_heading, self.heading)
                self.visual_heading = (self.visual_heading + heading_diff_visual * self.heading_smoothing) % 360
                
                # Validate new position doesn't overshoot target by too much
                # This prevents aircraft from running off taxiway during sharp turns
                new_dlat = target_lat - new_lat
                new_dlon = target_lon - new_lon
                new_distance = math.sqrt(new_dlat**2 + new_dlon**2)
                
                # If we're about to overshoot significantly, slow down movement
                if new_distance > distance and distance < 0.00005:  # Within 5m of waypoint
                    # Reduce movement to prevent overshoot
                    move_distance *= 0.5
                    new_lat = lat + move_distance * math.cos(rad)
                    new_lon = lon + move_distance * math.sin(rad)
                
                self.position = (new_lat, new_lon)
                
                # Update current surface detection for tower clearances
                self._update_current_surface()
        else:
            # No target, stop
            self.state = self.STATE_HOLDING
            self.speed = 0
    
    def _is_inside_runway_polygon(self, lat, lon, runway) -> bool:
        """Check if a point is inside the runway polygon using ray casting algorithm"""
        runway_polygon = runway.get('runway_polygon', [])
        if not runway_polygon or len(runway_polygon) == 0:
            return False
        
        # Get the polygon points (first element of runway_polygon array)
        polygon = runway_polygon[0] if isinstance(runway_polygon[0], list) else runway_polygon
        if len(polygon) < 3:
            return False
        
        # Ray casting algorithm
        inside = False
        n = len(polygon)
        
        for i in range(n):
            j = (i + 1) % n
            xi, yi = polygon[i]['x'], polygon[i]['y']
            xj, yj = polygon[j]['x'], polygon[j]['y']
            
            if ((yi > lon) != (yj > lon)) and (lat < (xj - xi) * (lon - yi) / (yj - yi) + xi):
                inside = not inside
                  
        # Debug logging for cleared aircraft
        if inside and hasattr(self, 'tower_cleared_to_lineup') and self.tower_cleared_to_lineup:
            runway_name = runway.get('name', '')
            logger.debug(f"[{self.get_callsign()}] Inside runway polygon: {runway_name}")
        
        return inside
    
    def _update_current_surface(self):
        """Detect and update what surface the aircraft is currently on (runway, taxiway, ramp)"""
        if not self.airport_data:
            return
        
        lat, lon = self.position
        
        # Check if on runway (priority check)
        runways = self.airport_data.get('runways', [])
        for runway in runways:
            runway_name = runway.get('name', '')
            
            # First try polygon check if available
            if self._is_inside_runway_polygon(lat, lon, runway):
                # Determine which runway end
                if hasattr(self, 'expected_runway') and self.expected_runway:
                    runway_end = self.expected_runway
                else:
                    runway_end = runway_name.split('/')[0] if '/' in runway_name else runway_name
                
                self.last_known_surface = f"Runway {runway_end}"
                return
            
            # Fallback to centerline distance check
            points = runway.get('points', [])
            if len(points) >= 2:
                # Check if aircraft is near runway centerline
                p1_lat, p1_lon = points[0].get('x'), points[0].get('y')
                p2_lat, p2_lon = points[1].get('x'), points[1].get('y')
                
                if p1_lat and p1_lon and p2_lat and p2_lon:
                    # Calculate distance from point to line segment
                    dist = self._point_to_line_distance(lat, lon, p1_lat, p1_lon, p2_lat, p2_lon)
                    
                    # If within runway width (~50m = 0.00045 degrees), consider on runway
                    if dist < 0.00045:
                        # Determine which runway end (02, 20, 14, 32, etc.)
                        if hasattr(self, 'expected_runway') and self.expected_runway:
                            runway_end = self.expected_runway
                        else:
                            runway_end = runway_name.split('/')[0] if '/' in runway_name else runway_name
                        
                        self.last_known_surface = f"Runway {runway_end}"
                        return
        
        # Check if on taxiway
        taxiways = self.airport_data.get('taxiways', [])
        for taxiway in taxiways:
            taxiway_name = taxiway.get('taxiway', '')
            points = taxiway.get('points', [])
            
            if len(points) >= 2:
                # Check each segment of the taxiway
                for i in range(len(points) - 1):
                    p1 = points[i]
                    p2 = points[i + 1]
                    p1_lat, p1_lon = p1.get('x'), p1.get('y')
                    p2_lat, p2_lon = p2.get('x'), p2.get('y')
                    
                    if p1_lat and p1_lon and p2_lat and p2_lon:
                        dist = self._point_to_line_distance(lat, lon, p1_lat, p1_lon, p2_lat, p2_lon)
                        
                        # If within taxiway width (~25m = 0.000225 degrees)
                        if dist < 0.000225:
                            self.last_known_surface = f"Taxiway {taxiway_name}"
                            return
        
        # Default to ramp if not on runway or taxiway
        self.last_known_surface = "Ramp"
    
    def _point_to_line_distance(self, px, py, x1, y1, x2, y2):
        """Calculate perpendicular distance from point (px, py) to line segment (x1,y1)-(x2,y2)"""
        # Vector from line start to point
        dx = x2 - x1
        dy = y2 - y1
        
        if dx == 0 and dy == 0:
            # Line segment is a point
            return math.sqrt((px - x1)**2 + (py - y1)**2)
        
        # Parameter t for projection onto line
        t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
        
        # Closest point on line segment
        closest_x = x1 + t * dx
        closest_y = y1 + t * dy
        
        # Distance from point to closest point
        return math.sqrt((px - closest_x)**2 + (py - closest_y)**2)
    
    def _update_takeoff(self, dt: float):
        """Update aircraft during takeoff roll and initial climb"""
        # Log takeoff progress every second
        if not hasattr(self, '_last_takeoff_log_time'):
            self._last_takeoff_log_time = 0
        
        current_time = time.time()
        if current_time - self._last_takeoff_log_time >= 1.0:
            logger.info(f"[{self.get_callsign()}] Takeoff roll: speed={self.speed:.1f} kts, alt={self.altitude:.0f} ft, pos={self.position}")
            self._last_takeoff_log_time = current_time
        
        # Store runway heading at start of takeoff if not already stored
        if not hasattr(self, '_takeoff_heading'):
            # Use lineup runway heading if available, otherwise use current heading
            if hasattr(self, 'lineup_runway_heading') and self.lineup_runway_heading is not None:
                self._takeoff_heading = self.lineup_runway_heading
            else:
                self._takeoff_heading = self.heading
            logger.info(f"[{self.get_callsign()}] Takeoff heading set to: {self._takeoff_heading:.1f}°")
        
        # Accelerate to takeoff speed using aircraft-specific acceleration
        # Takeoff acceleration is much higher - about 6x taxi acceleration for realistic performance
        takeoff_accel = self.acceleration * 6.0
        if self.speed < self.target_speed:
            self.speed += takeoff_accel * dt
            if self.speed > self.target_speed:
                self.speed = self.target_speed
        
        # Rotate and climb at V_r (rotation speed = 90% of target_speed)
        v_rotate = self.target_speed * 0.90
        if self.speed > v_rotate:
            # Rotate and climb using aircraft-specific climb rate
            # Use climb_rate from performance data, or calculate from service ceiling
            climb_rate = self.performance.get('climb_rate_fpm', 2000)  # feet per minute
            self.altitude += (climb_rate / 60.0) * dt  # Convert to feet per second
            
            # Check if reached initial climb altitude
            if self.altitude >= self.target_altitude:
                self.altitude = self.target_altitude
                self.state = self.STATE_DEPARTED
                logger.info(f"[{self.get_callsign()}] Airborne, climbing to {self.target_altitude:.0f} feet")
                
                # Clear any navigation targets - aircraft should fly straight ahead
                self.target_position = None
                self.route = []
                self.taxi_via = None
                
                # Transmit departure message - Tower frequency, don't send to ground radio
                # if self.radio_callback:
                #     departure_msg = f"{self.get_callsign()}, airborne, switching to departure"
                #     self.radio_callback(departure_msg, is_atc=False)
                
                # Remove aircraft after departure (simulate handoff to departure control)
                return
        
        # Keep heading locked to takeoff heading - fly straight, don't recalculate
        self.heading = self._takeoff_heading
        
        # Move forward along takeoff heading (straight ahead)
        move_distance = (self.speed * 0.514444 * dt) / 111000.0  # Convert knots to degrees
        rad = math.radians(self.heading)
        lat, lon = self.position
        # Correct for longitude compression at this latitude
        lon_correction = math.cos(math.radians(lat))
        new_lat = lat + move_distance * math.cos(rad)
        new_lon = lon + move_distance * math.sin(rad) / lon_correction
        self.position = (new_lat, new_lon)
        
        # CRITICAL: Update visual position for rendering
        # Without this, aircraft appears frozen on screen during takeoff
        self.visual_position[0] += (new_lat - self.visual_position[0]) * self.position_smoothing
        self.visual_position[1] += (new_lon - self.visual_position[1]) * self.position_smoothing
        
        # Keep visual heading locked to takeoff heading - no deviation during departure
        self.visual_heading = self.heading
    
    def _update_departed(self, dt: float):
        """Update aircraft after departure - continue flying straight ahead"""
        # Ensure we have a heading to fly
        if not hasattr(self, '_takeoff_heading'):
            # Fallback to current heading if takeoff heading wasn't set
            self._takeoff_heading = self.heading
        
        # Keep heading locked - fly straight ahead
        self.heading = self._takeoff_heading
        
        # Continue climbing if not at cruise altitude
        if self.altitude < self.target_altitude:
            climb_rate = self.performance.get('climb_rate_fpm', 2000)  # feet per minute
            self.altitude += (climb_rate / 60.0) * dt  # Convert to feet per second
            if self.altitude > self.target_altitude:
                self.altitude = self.target_altitude
        
        # Continue accelerating to cruise speed
        cruise_speed = self.performance.get('cruise_speed_kt', 450)
        if self.speed < cruise_speed:
            takeoff_accel = self.acceleration * 6.0
            self.speed += takeoff_accel * dt
            if self.speed > cruise_speed:
                self.speed = cruise_speed
        
        # Move forward along heading (straight ahead)
        move_distance = (self.speed * 0.514444 * dt) / 111000.0  # Convert knots to degrees
        rad = math.radians(self.heading)
        lat, lon = self.position
        # Correct for longitude compression at this latitude
        lon_correction = math.cos(math.radians(lat))
        new_lat = lat + move_distance * math.cos(rad)
        new_lon = lon + move_distance * math.sin(rad) / lon_correction
        self.position = (new_lat, new_lon)
        
        # Update visual position
        self.visual_position[0] += (new_lat - self.visual_position[0]) * self.position_smoothing
        self.visual_position[1] += (new_lon - self.visual_position[1]) * self.position_smoothing
        
        # Keep visual heading locked
        self.visual_heading = self.heading
    
    def _update_approach(self, dt: float):
        """Update aircraft on final approach - fly towards touchdown point and descend"""
        if not self.target_position:
            # No target, something went wrong
            logger.error(f"[{self.get_callsign()}] No target position during approach!")
            return
        
        lat, lon = self.position
        target_lat, target_lon = self.target_position
        
        # Calculate distance to touchdown point (with longitude compression)
        lon_correction = math.cos(math.radians(lat))
        dlat = target_lat - lat
        dlon = target_lon - lon
        dlat_m = dlat * 111000.0
        dlon_m = dlon * 111000.0 * lon_correction
        distance_meters = math.sqrt(dlat_m**2 + dlon_m**2)

        # Steer directly toward the touchdown point so that imprecise spawn
        # locations don't cause the aircraft to fly past without touching down.
        if distance_meters > 1.0:
            self.heading = math.degrees(math.atan2(dlon * lon_correction, dlat)) % 360

        # Maintain approach speed based on aircraft type
        # GA aircraft (wake category L) use much lower speeds
        # Commercial aircraft use 130+ knots
        base_landing_speed = getattr(self, 'landing_speed', 130.0)
        
        # Calculate distance-based speed reduction for realistic landing
        if self.wake_category == 'L':
            # GA aircraft - lower speeds throughout approach
            if distance_meters > 500:
                approach_speed = base_landing_speed + 10.0  # ~65-70 kts for GA
            else:
                approach_speed = base_landing_speed + 5.0  # ~60-65 kts near touchdown
        else:
            # Commercial aircraft - higher speeds
            if distance_meters > 1000:  # More than 1000m out
                approach_speed = max(base_landing_speed + 20.0, 140.0)  # ~140-150 kts
            elif distance_meters > 500:  # 500-1000m out
                approach_speed = max(base_landing_speed + 10.0, 135.0)  # ~135-140 kts
            else:  # Within 500m, reduce to threshold crossing speed
                approach_speed = max(base_landing_speed, 130.0)  # ~130 kts at touchdown
        
        self.speed = approach_speed
        
        # Descend at standard 3-degree glideslope
        # At 3 miles (3 NM = ~18,000 feet horizontal), altitude should be ~1,000 feet
        # Descent rate: approximately 700 feet per minute at 140 knots
        descent_rate = 700.0 / 60.0  # feet per second
        
        if self.altitude > 50.0:  # Still above ground (50 feet threshold for touchdown)
            self.altitude = max(0.0, self.altitude - descent_rate * dt)
        
        # Check if we've reached the touchdown point
        # Touchdown only at the defined touchdown point (not altitude-based)
        touchdown_threshold_meters = 15.0  # Slightly larger threshold for reliable detection
        
        if distance_meters < touchdown_threshold_meters:
            # Touchdown! Transition to landing rollout
            # Snap position to exact touchdown point for accuracy
            self.position = (target_lat, target_lon)
            self.landing_touchdown_position = (target_lat, target_lon)  # Store for taxiway exit routing
            self.landing_runway_heading = self.heading  # Store runway heading - fly straight
            logger.info(f"[{self.get_callsign()}] Touchdown on runway {self.expected_runway} at defined touchdown point ({target_lat:.6f}, {target_lon:.6f}) at {self.speed:.0f} knots")
            self.state = self.STATE_LANDING
            self.altitude = 0.0
            # Speed at touchdown is current speed (should be ~120 knots)
            
            # Radio call on tower frequency (arrivals use tower during landing)
            if self.radio_callback:
                self._schedule_radio(
                    f"{self.get_callsign()}, runway {self.expected_runway}",
                    is_atc=False,
                    delay=random.uniform(1, 2),
                    frequency='tower'
                )
            return
        
        # Move aircraft along heading
        move_distance = (self.speed * 0.514444 * dt) / 111000.0
        rad = math.radians(self.heading)
        new_lat = lat + move_distance * math.cos(rad)
        new_lon = lon + move_distance * math.sin(rad) / lon_correction
        self.position = (new_lat, new_lon)

        # Update visual position for rendering
        self.visual_position[0] += (new_lat - self.visual_position[0]) * self.position_smoothing
        self.visual_position[1] += (new_lon - self.visual_position[1]) * self.position_smoothing
        self.visual_heading = self.heading
    
    def _update_landing(self, dt: float):
        """Update landing rollout - decelerate along runway centerline and exit at taxiway.

        _target_exit is a 3-tuple: (taxiway_letter, exit_point_on_taxiway, exit_fwd_m)
        where exit_fwd_m is the forward distance along the runway heading from touchdown.
        Exit is triggered when landing_distance_traveled reaches exit_fwd_m — this way
        the lateral position of the taxiway point doesn't matter; we exit at the right
        spot on the runway regardless.
        """
        if not hasattr(self, 'landing_phase'):
            self.landing_phase = 'rollout'
            self.landing_touchdown_position = self.position
            self.landing_distance_traveled = 0.0
            self.landing_runway_heading = self.heading
            self._target_exit = None  # (taxiway_letter, exit_point, exit_fwd_m)
            logger.info(f"[{self.get_callsign()}] Landing rollout started")

        lat, lon = self.position
        td_lat, td_lon = self.landing_touchdown_position
        heading_rad = math.radians(self.landing_runway_heading)

        # Landing distance = forward projection along runway heading (not Euclidean)
        # This stays accurate even if we were slightly off centerline before snapping
        dlat_td = lat - td_lat
        dlon_td = lon - td_lon
        self.landing_distance_traveled = (
            dlat_td * math.cos(heading_rad) + dlon_td * math.sin(heading_rad)
        ) * 111000.0

        # Get performance data
        perf_db = self._load_performance_data()
        perf_data = perf_db.get(self.aircraft_type, {})
        landing_decel = perf_data.get('landing_decel_m_s2', 2.0)
        landing_decel_knots_per_sec = landing_decel * 1.94384

        # --- Scout for an exit every frame until committed ---
        # Start scanning immediately after touchdown so the full runway length is
        # available for physics-based deceleration planning.
        if self._target_exit is None:
            exit_result = self._find_nearby_taxiway_exit()
            if exit_result:
                taxiway_letter, exit_point = exit_result
                # Compute how far along the runway heading the exit sits from touchdown
                ex_lat, ex_lon = exit_point
                d_lat = ex_lat - td_lat
                d_lon = ex_lon - td_lon
                exit_fwd_m = (
                    d_lat * math.cos(heading_rad) + d_lon * math.sin(heading_rad)
                ) * 111000.0
                # Must be ahead of current position; clamp so we always get some rollout
                exit_fwd_m = max(exit_fwd_m, self.landing_distance_traveled + 30.0)
                self._target_exit = (taxiway_letter, exit_point, exit_fwd_m)
                logger.info(
                    f"[{self.get_callsign()}] Committed to exit {taxiway_letter} "
                    f"at {exit_fwd_m:.0f}m down runway "
                    f"({exit_fwd_m - self.landing_distance_traveled:.0f}m ahead)"
                )

        # --- Turn off: trigger when forward progress reaches exit's runway position ---
        if self._target_exit:
            taxiway_letter, exit_point, exit_fwd_m = self._target_exit
            remaining_m = exit_fwd_m - self.landing_distance_traveled

            # If we've overshot by more than 60 m the committed exit is behind us;
            # drop it and let the scanner find the next available one.
            if remaining_m < -60.0:
                logger.warning(
                    f"[{self.get_callsign()}] Overshot exit {taxiway_letter} by "
                    f"{-remaining_m:.0f}m — scanning for next exit"
                )
                self._target_exit = None

            elif remaining_m <= 30.0:
                # Clamp speed so the aircraft doesn't enter the taxiway at runway speed.
                self.speed = min(self.speed, 45.0)
                logger.info(
                    f"[{self.get_callsign()}] Exiting runway {self.expected_runway} "
                    f"onto taxiway {taxiway_letter} at {self.landing_distance_traveled:.0f}m "
                    f"({self.speed:.0f} kts)"
                )
                self._start_arrival_taxi_to_gate(exit_point=exit_point)
                return

        # --- Deceleration ---
        # Physics-based: compute the braking needed to reach exit speed exactly at
        # the exit point, capped by the aircraft's actual max landing deceleration.
        runway_length = self._get_runway_length() or 2000.0
        exit_speed_kts = 30.0  # Target turnoff speed

        if self._target_exit:
            taxiway_letter, exit_point, exit_fwd_m = self._target_exit
            remaining_m = max(1.0, exit_fwd_m - self.landing_distance_traveled)

            # Required decel to arrive at exit_speed at the exit point
            v_ms = self.speed * 0.514444
            v_exit_ms = exit_speed_kts * 0.514444
            if v_ms > v_exit_ms:
                a_required = (v_ms ** 2 - v_exit_ms ** 2) / (2.0 * remaining_m)
            else:
                a_required = 0.0
            a_applied = min(a_required, landing_decel)
            decel_rate = a_applied * 1.94384
            target_speed = exit_speed_kts

        elif self.landing_distance_traveled > runway_length * 0.80:
            # No exit found and near end of runway — full emergency braking
            target_speed = 0.0
            decel_rate = landing_decel_knots_per_sec * 1.5
        else:
            # No exit identified yet — gentle braking to stay at safe speed
            target_speed = 80.0
            decel_rate = landing_decel_knots_per_sec * 0.5

        if self.speed > target_speed:
            self.speed = max(target_speed, self.speed - decel_rate * dt)
        elif self.speed <= 0.0 and self._target_exit is None:
            self.speed = 0.0
            self.state = self.STATE_HOLDING
            logger.info(f"[{self.get_callsign()}] Stopped on runway {self.expected_runway}, awaiting instructions")
            return

        # Keep heading locked to runway
        self.heading = self.landing_runway_heading

        # Move forward
        if self.speed > 0:
            move_distance = (self.speed * 0.514444 * dt) / 111000.0
            rad = math.radians(self.heading)
            lat, lon = self.position
            lon_correction = math.cos(math.radians(lat))
            new_lat = lat + move_distance * math.cos(rad)
            new_lon = lon + move_distance * math.sin(rad) / lon_correction

            # Snap to runway centerline to prevent drift
            runway_points = self._get_runway_points()
            if runway_points and len(runway_points) >= 2:
                best_cp = None
                best_dist = float('inf')
                for i in range(len(runway_points) - 1):
                    cp = self._closest_point_on_segment(
                        (new_lat, new_lon), runway_points[i], runway_points[i + 1]
                    )
                    d = self._distance((new_lat, new_lon), cp)
                    if d < best_dist:
                        best_dist = d
                        best_cp = cp
                if best_cp is not None and best_dist * 111000 < 100:
                    new_lat, new_lon = best_cp

            self.position = (new_lat, new_lon)

            if hasattr(self, 'visual_position'):
                self.visual_position[0] += (new_lat - self.visual_position[0]) * self.position_smoothing
                self.visual_position[1] += (new_lon - self.visual_position[1]) * self.position_smoothing
            else:
                self.visual_position = [new_lat, new_lon]
            self.visual_heading = self.heading
    
    def _find_nearby_taxiway_exit(self) -> Optional[Tuple[str, Tuple[float, float]]]:
        """Lateral radar scan — find the earliest taxiway that passes within 80m
        of the runway path ahead of the aircraft.

        Returns (taxiway_name, exit_point_on_taxiway) where exit_point_on_taxiway is
        the taxiway sample point closest to the runway centerline at the crossing.
        The caller uses the forward projection of that point to decide WHEN to turn off,
        so the lateral offset of the taxiway geometry from the centerline doesn't matter.
        """
        if not self.airport_data:
            return None

        lat, lon = self.position
        heading_rad = math.radians(self.heading)
        td_lat, td_lon = self.landing_touchdown_position if hasattr(self, 'landing_touchdown_position') else (lat, lon)

        # Forward lookahead scales with speed so we commit well in advance.
        # Minimum 1000 m so exits near the end of a long runway are always found.
        lookahead_m = max(1000.0, min(3000.0, self.speed * 18.0))
        # How far left/right of centreline we'll detect a taxiway.
        # 55 m covers runway half-width + typical taxiway offset at most airports.
        lateral_limit_m = 55.0

        best_fwd_m = float('inf')   # forward distance from current position to exit
        best_taxiway = None
        best_exit_point = None

        # ── Method 1: explicit runway_exits in JSON ──────────────────────────────
        runway_exits = self.airport_data.get('runway_exits', [])
        expected_rwy = getattr(self, 'expected_runway', None)
        if expected_rwy and runway_exits:
            for rexit in runway_exits:
                if rexit.get('runway') != expected_rwy:
                    continue
                pt = rexit.get('exit_point') or rexit.get('point')
                if not pt:
                    continue
                ex_lat = float(pt.get('x', pt[0] if isinstance(pt, (list, tuple)) else 0))
                ex_lon = float(pt.get('y', pt[1] if isinstance(pt, (list, tuple)) else 0))
                taxiway_letter = rexit.get('taxiway', '')
                if not taxiway_letter:
                    continue
                dlat = ex_lat - lat
                dlon = ex_lon - lon
                # Forward distance from current position to this exit
                fwd_m = (dlat * math.cos(heading_rad) + dlon * math.sin(heading_rad)) * 111000.0
                if 0.0 <= fwd_m <= lookahead_m and fwd_m < best_fwd_m:
                    best_fwd_m = fwd_m
                    best_taxiway = taxiway_letter
                    best_exit_point = (ex_lat, ex_lon)

        if best_taxiway:
            logger.info(
                f"[{self.get_callsign()}] runway_exits hit: {best_taxiway} "
                f"at {best_fwd_m:.0f}m ahead"
            )
            return (best_taxiway, best_exit_point)

        # ── Method 2: lateral radar scan across all taxiway segments ─────────────
        # For every taxiway segment we densely sample points along it.
        # A point "hits" if it is:
        #   • forward of the aircraft (fwd_m > 0) and within lookahead
        #   • within lateral_limit_m of the runway centreline (left OR right)
        # We pick the earliest exit (smallest fwd_m across segments).
        # Within each segment we use the sample closest to the centreline (minimum
        # lateral offset) so we target the actual runway/taxiway crossing, not a
        # point that merely happens to be forward of the aircraft.
        # cos(lat) correction is applied to longitude so lat_m is accurate at all
        # latitudes (without it, east-west distances are overestimated and valid
        # exits near N/S runways are rejected as "too far").
        lon_scale = math.cos(math.radians(lat))
        taxiways = self.airport_data.get('taxiways', [])
        for taxiway in taxiways:
            taxiway_letter = taxiway.get('taxiway', '')
            points = taxiway.get('points', [])
            if not points or len(points) < 2:
                continue
            for i in range(len(points) - 1):
                p1_lat = points[i].get('x')
                p1_lon = points[i].get('y')
                p2_lat = points[i + 1].get('x')
                p2_lon = points[i + 1].get('y')
                if None in (p1_lat, p1_lon, p2_lat, p2_lon):
                    continue
                # Sample 12 evenly-spaced points along the segment.
                # Track the best candidate for THIS segment: the qualifying point
                # with the smallest lateral distance (closest to runway centreline).
                seg_best_lat_m  = float('inf')
                seg_best_fwd_m  = float('inf')
                seg_best_pt     = None
                for step in range(13):
                    t = step / 12.0
                    pt_lat = p1_lat + t * (p2_lat - p1_lat)
                    pt_lon = p1_lon + t * (p2_lon - p1_lon)
                    dlat   = pt_lat - lat
                    dlon   = pt_lon - lon
                    # Apply cos(lat) to longitude so distances are in true metres
                    dlat_m = dlat * 111000.0
                    dlon_m = dlon * 111000.0 * lon_scale
                    # Forward component (along runway heading)
                    fwd_m = dlat_m * math.cos(heading_rad) + dlon_m * math.sin(heading_rad)
                    # Lateral component (perpendicular to runway heading)
                    lat_m = abs(-dlat_m * math.sin(heading_rad) + dlon_m * math.cos(heading_rad))
                    if 5.0 <= fwd_m <= lookahead_m and lat_m <= lateral_limit_m:
                        # Prefer the crossing point (min lateral) over the first-
                        # forward point so the exit location is accurate.
                        if lat_m < seg_best_lat_m:
                            seg_best_lat_m = lat_m
                            seg_best_fwd_m = fwd_m
                            seg_best_pt    = (pt_lat, pt_lon)
                # Keep the earliest crossing across all taxiway segments
                if seg_best_pt is not None and seg_best_fwd_m < best_fwd_m:
                    best_fwd_m    = seg_best_fwd_m
                    best_taxiway  = taxiway_letter
                    best_exit_point = seg_best_pt

        if best_taxiway:
            logger.info(
                f"[{self.get_callsign()}] radar scan hit: taxiway {best_taxiway} "
                f"at {best_fwd_m:.0f}m ahead (lateral scan)"
            )
            return (best_taxiway, best_exit_point)

        logger.warning(
            f"[{self.get_callsign()}] No taxiway exit found at "
            f"{self.landing_distance_traveled:.0f}m (lookahead {lookahead_m:.0f}m, "
            f"lateral ±{lateral_limit_m:.0f}m)"
        )
        return None
    
    def _find_line_segment_intersection(self, point: Tuple[float, float], heading_rad: float,
                                         seg_start: Tuple[float, float], seg_end: Tuple[float, float]) -> Optional[Tuple[float, float]]:
        """Find intersection between a ray from point in direction heading_rad and a line segment
        
        Args:
            point: Starting point of the ray
            heading_rad: Direction of the ray in radians
            seg_start: Start of the line segment
            seg_end: End of the line segment
            
        Returns:
            Intersection point or None if no intersection
        """
        px, py = point
        sx, sy = seg_start
        ex, ey = seg_end
        
        # Direction vector of the ray
        dx = math.cos(heading_rad)
        dy = math.sin(heading_rad)
        
        # Direction vector of the segment
        seg_dx = ex - sx
        seg_dy = ey - sy
        
        # Cross product to check if parallel
        cross = dx * seg_dy - dy * seg_dx
        
        if abs(cross) < 1e-10:
            # Lines are parallel
            return None
        
        # Calculate intersection parameters
        t = ((sx - px) * seg_dy - (sy - py) * seg_dx) / cross
        u = ((sx - px) * dy - (sy - py) * dx) / cross
        
        # Check if intersection is ahead of us (t > 0) and on the segment (0 <= u <= 1)
        if t > 0 and 0 <= u <= 1:
            int_x = px + t * dx
            int_y = py + t * dy
            return (int_x, int_y)
        
        return None
    
    def _closest_point_on_segment(self, point: Tuple[float, float], seg_start: Tuple[float, float], seg_end: Tuple[float, float]) -> Optional[Tuple[float, float]]:
        """Find the closest point on a line segment to a given point"""
        px, py = point
        sx, sy = seg_start
        ex, ey = seg_end
        
        # Vector from segment start to end
        dx = ex - sx
        dy = ey - sy
        
        # If segment is degenerate (zero length), return start point
        if dx == 0 and dy == 0:
            return seg_start
        
        # Vector from segment start to point
        px_rel = px - sx
        py_rel = py - sy
        
        # Project point onto segment
        t = (px_rel * dx + py_rel * dy) / (dx * dx + dy * dy)
        
        # Clamp to segment bounds
        t = max(0.0, min(1.0, t))
        
        # Return closest point on segment
        return (sx + t * dx, sy + t * dy)
    
    def _calculate_taxiway_turn_angle(self, taxiway_letter: str, exit_point: Tuple[float, float]) -> float:
        """Calculate the turn angle required to exit onto a taxiway
        
        Args:
            taxiway_letter: The taxiway identifier
            exit_point: The intersection point where we'll turn
            
        Returns:
            Turn angle in degrees (0-180)
        """
        if not self.airport_data or not taxiway_letter:
            return 90.0  # Default to 90 degrees if unknown
        
        taxiways = self.airport_data.get('taxiways', [])
        
        for taxiway in taxiways:
            if taxiway.get('taxiway', '').upper() == taxiway_letter.upper():
                points = taxiway.get('points', [])
                
                if len(points) < 2:
                    continue
                
                # Convert points to tuples
                taxiway_points = []
                for point in points:
                    tx_lat = point.get('x')
                    tx_lon = point.get('y')
                    if tx_lat and tx_lon:
                        taxiway_points.append((tx_lat, tx_lon))
                
                if len(taxiway_points) < 2:
                    continue
                
                # Find the segment closest to the exit point
                exit_lat, exit_lon = exit_point
                closest_segment_idx = 0
                closest_dist = float('inf')
                
                for i in range(len(taxiway_points) - 1):
                    p1 = taxiway_points[i]
                    p2 = taxiway_points[i + 1]
                    closest_point = self._closest_point_on_segment(exit_point, p1, p2)
                    if closest_point:
                        dist = self._distance(exit_point, closest_point)
                        if dist < closest_dist:
                            closest_dist = dist
                            closest_segment_idx = i
                
                # Get the taxiway direction at the exit point
                p1 = taxiway_points[closest_segment_idx]
                p2 = taxiway_points[closest_segment_idx + 1]
                
                # Calculate taxiway heading
                dlat = p2[0] - p1[0]
                dlon = p2[1] - p1[1]
                taxiway_heading = math.degrees(math.atan2(dlon, dlat)) % 360
                
                # Also check opposite direction
                taxiway_heading_opposite = (taxiway_heading + 180) % 360
                
                # Calculate turn angle from current runway heading
                runway_heading = self.heading
                
                # Get the smaller angle between runway heading and taxiway heading
                angle1 = abs(self._angle_difference(runway_heading, taxiway_heading))
                angle2 = abs(self._angle_difference(runway_heading, taxiway_heading_opposite))
                
                turn_angle = min(angle1, angle2)
                
                logger.debug(f"[{self.get_callsign()}] Taxiway {taxiway_letter} heading: {taxiway_heading:.0f}°, runway heading: {runway_heading:.0f}°, turn angle: {turn_angle:.0f}°")
                
                return turn_angle
        
        return 90.0  # Default if taxiway not found
    
    def _get_taxiway_exit_route(self, taxiway_letter: str, exit_point: Tuple[float, float] = None) -> List[Tuple[float, float]]:
        """Get a route of waypoints along the taxiway for the aircraft to follow,
        from the exit point (or current position) along the taxiway away from the runway.
        """
        if not self.airport_data:
            logger.warning(f"[ARRIVAL LOG] {self.get_callsign()} - No airport data for exit route")
            return []
        
        lat, lon = self.position
        use_point = exit_point if exit_point else (lat, lon)
        taxiways = self.airport_data.get('taxiways', [])
        taxiway_points = None
        for tw in taxiways:
            if (tw.get('taxiway') or '').upper() == (taxiway_letter or '').upper():
                pts = tw.get('points', [])
                taxiway_points = [(float(p.get('x')), float(p.get('y'))) for p in pts if p.get('x') is not None and p.get('y') is not None]
                break
        if not taxiway_points or len(taxiway_points) < 2:
            return []
        
        insertion_point = None
        closest_idx = 0
        closest_dist = float('inf')
        for i in range(len(taxiway_points) - 1):
            cp = self._closest_point_on_segment(use_point, taxiway_points[i], taxiway_points[i + 1])
            d = self._distance(use_point, cp)
            if d < closest_dist:
                closest_dist = d
                insertion_point = cp
                closest_idx = i
        if insertion_point is None:
            insertion_point = use_point
            for i, pt in enumerate(taxiway_points):
                d = self._distance(use_point, pt)
                if d < closest_dist:
                    closest_dist = d
                    closest_idx = i
        
        runway_pos = self.landing_touchdown_position if hasattr(self, 'landing_touchdown_position') else self.position
        dist_to_start = self._distance(taxiway_points[0], runway_pos)
        dist_to_end = self._distance(taxiway_points[-1], runway_pos)
        route = [insertion_point]
        if dist_to_end > dist_to_start:
            route.extend(taxiway_points[closest_idx + 1:])
        else:
            route.extend(reversed(taxiway_points[:closest_idx + 1]))
        logger.info(f"[{self.get_callsign()}] Exit route for taxiway {taxiway_letter}: {len(route)} waypoints")
        return route
    
    def _find_and_assign_gate(self):
        """Find and assign an available gate for the aircraft"""
        if not self.airport_data or not hasattr(self, 'aircraft_manager'):
            return
        
        gates = self.airport_data.get('gates', [])
        if not gates:
            return
        
        # Get list of occupied gates from other aircraft
        occupied_gates = set()
        if hasattr(self.aircraft_manager, 'get_all_aircraft'):
            for aircraft in self.aircraft_manager.get_all_aircraft():
                if hasattr(aircraft, 'gate') and aircraft.gate and aircraft != self:
                    occupied_gates.add(aircraft.gate)
        holdshort_bars = self.airport_data.get('holdshort_bars', [])
        if not holdshort_bars:
            return self.landing_distance_traveled > 1000.0
        
        lat, lon = self.position
        
        for bar in holdshort_bars:
            runway = bar.get('runway', '')
            # Only check hold short for our runway
            if runway != self.expected_runway:
                continue
            
            points = bar.get('points', [])
            if len(points) >= 2:
                p1_lat = points[0].get('x')
                p1_lon = points[0].get('y')
                p2_lat = points[1].get('x')
                p2_lon = points[1].get('y')
                
                if p1_lat and p1_lon and p2_lat and p2_lon:
                    # Check if we're past the hold short line
                    # Calculate if we've crossed it based on heading direction
                    distance_to_bar = self._distance_to_line_segment(
                        (lat, lon), (p1_lat, p1_lon), (p2_lat, p2_lon)
                    )
                    
                    # If we're more than 30m past the hold short, we've cleared it
                    past_threshold = 30.0 / 111000.0  # 30 meters in degrees
                    if distance_to_bar > past_threshold:
                        return True
        
        return False
    
    def _get_runway_length(self) -> Optional[float]:
        """Get the length of the current runway in meters"""
        if not self.expected_runway or not self.airport_data:
            return None
        
        # Find the runway data
        runways = self.airport_data.get('runways', [])
        for runway in runways:
            runway_name = runway.get('name', '')
            # Check if our runway is in this runway definition (e.g., "02/20")
            if self.expected_runway in runway_name.split('/'):
                # Get runway points to calculate length
                points = runway.get('points', [])
                if len(points) >= 2:
                    # Calculate distance between first and last point
                    first = points[0]
                    last = points[-1]
                    
                    dlat = last['x'] - first['x']
                    dlon = last['y'] - first['y']
                    distance_degrees = math.sqrt(dlat**2 + dlon**2)
                    distance_meters = distance_degrees * 111000.0  # Convert to meters
                    
                    return distance_meters
        
        return None
    
    def _get_runway_points(self) -> Optional[list]:
        """Get the centerline points for the current runway"""
        if not self.expected_runway or not self.airport_data:
            return None
        
        # Find the runway data
        runways = self.airport_data.get('runways', [])
        for runway in runways:
            runway_name = runway.get('name', '')
            # Check if our runway is in this runway definition (e.g., "02/20")
            if self.expected_runway in runway_name.split('/'):
                # Get runway points
                points = runway.get('points', [])
                if len(points) >= 2:
                    # Convert to list of (lat, lon) tuples
                    runway_points = [(p['x'], p['y']) for p in points]
                    
                    # Determine which direction to use based on runway number
                    # If expected_runway is the first part (e.g., "02" in "02/20"), use as-is
                    # If it's the second part (e.g., "20" in "02/20"), reverse the points
                    runway_parts = runway_name.split('/')
                    if len(runway_parts) == 2 and self.expected_runway == runway_parts[1]:
                        # Reverse for opposite direction
                        runway_points = list(reversed(runway_points))
                    
                    return runway_points
        
        return None
    
    def _angle_difference(self, angle1, angle2):
        """Calculate shortest difference between two angles"""
        diff = (angle2 - angle1) % 360
        if diff > 180:
            diff -= 360
        return diff
    
    def _start_arrival_taxi_to_gate(self, exit_point=None):
        """Start taxi to gate for arrival aircraft after clearing runway.

        exit_point: if provided, inserted as the first waypoint so the aircraft
        physically drives from the runway centerline to the taxiway (no teleport).
        """
        if not self.gate or not self.airport_data:
            logger.warning(f"[{self.get_callsign()}] Cannot taxi to gate - no gate assigned or no airport data")
            return
        
        logger.info(f"[{self.get_callsign()}] Starting taxi to gate {self.gate}")
        
        # Find gate position
        gates = self.airport_data.get('gates', [])
        gate_data = None
        for g in gates:
            if g.get('name') == self.gate:
                gate_data = g
                break
        
        if not gate_data or 'position' not in gate_data:
            logger.warning(f"[{self.get_callsign()}] Gate {self.gate} not found in airport data")
            return
        
        gate_pos = gate_data['position']
        gate_lat = gate_pos.get('x')
        gate_lon = gate_pos.get('y')
        
        if not gate_lat or not gate_lon:
            logger.warning(f"[{self.get_callsign()}] Invalid gate position for {self.gate}")
            return
        
        # Build route to gate
        self.taxi_destination = f"gate {self.gate}"
        self.cleared_to_taxi = True
        self.state = self.STATE_TAXI

        # Initial ground contact call after clearing runway
        if self.radio_callback:
            runway = getattr(self, 'expected_runway', '')
            msg = self._generate_realistic_readback(
                'clear_of_runway', {'runway': runway}
            )
            self._schedule_radio(
                msg,
                is_atc=False,
                delay=random.uniform(3.0, 7.0),
                frequency='ground',
            )

        route = None
        connects_to = gate_data.get('connects_to', '')
        
        # Redundant routing: graph path-to-ramp -> graph path-to-gate -> legacy -> direct
        # Start pathfinding from the taxiway exit point (already off the runway
        # centerline) so the graph search roots near actual taxiway nodes.
        # Falling back to self.position only when no exit_point is available.
        path_start = exit_point if exit_point else self.position
        if self.airport_graph:
            taxiway_info = self.airport_graph.find_closest_taxiway(path_start)
            if taxiway_info:
                taxiway_name, _closest_pt, dist = taxiway_info
                logger.info(f"[{self.get_callsign()}] Near taxiway {taxiway_name} (dist: {dist * 111000:.1f}m)")
            route = self.airport_graph.find_path_to_ramp(path_start, connects_to)
            if route:
                logger.info(f"[{self.get_callsign()}] Using graph path-to-ramp with {len(route)} waypoints")
            if not route:
                gate_surface = f"Gate {self.gate}"
                route = self.airport_graph.find_path(path_start, gate_surface, None)
                if route:
                    logger.info(f"[{self.get_callsign()}] Using graph path-to-gate with {len(route)} waypoints")
        if not route:
            route = self._build_arrival_taxi_route(gate_lat, gate_lon, gate_data)
        
        if route:
            if route[-1] != (gate_lat, gate_lon):
                route.append((gate_lat, gate_lon))
            # Do NOT prepend the raw taxiway sample as a waypoint — it is
            # off the runway centerline and would steer the aircraft through
            # the grass to reach it.  exit_point was already used above as
            # path_start so the graph search roots near the correct taxiway.
            route = self._optimize_taxi_route(route)
            self.route = route
            self.target_position = self.route.pop(0)
            logger.info(f"[{self.get_callsign()}] Arrival taxi route built with {len(self.route) + 1} waypoints to {self.gate}")
        else:
            self.route = [(gate_lat, gate_lon)]
            self.target_position = self.route.pop(0)
            logger.warning(f"[{self.get_callsign()}] Using direct route to gate (all pathfinding failed)")
    
    def _build_arrival_taxi_route(self, gate_lat: float, gate_lon: float, gate_data: dict) -> List[Tuple[float, float]]:
        """Build a taxi route from current position to gate for arrivals
        
        Args:
            gate_lat: Gate latitude
            gate_lon: Gate longitude
            gate_data: Gate configuration data
            
        Returns:
            List of waypoints to follow
        """
        route = []
        current_pos = self.position
        
        # Get ramps data
        ramps = self.airport_data.get('ramps', [])
        taxiways = self.airport_data.get('taxiways', [])
        
        # Find the ramp that connects to this gate
        connects_to = gate_data.get('connects_to', '')
        
        # Find the target ramp
        target_ramp = None
        for ramp in ramps:
            ramp_name = ramp.get('name') or ramp.get('ramp')
            if ramp_name == connects_to:
                target_ramp = ramp
                break
        
        # Get ramp entry point (closest ramp point to current position)
        ramp_entry_point = None
        if target_ramp:
            ramp_points = target_ramp.get('points', [])
            if ramp_points:
                ramp_coords = [(p['x'], p['y']) for p in ramp_points if 'x' in p and 'y' in p]
                if ramp_coords:
                    # Find closest ramp point to current position
                    min_dist = float('inf')
                    for coord in ramp_coords:
                        dist = self._distance(current_pos, coord)
                        if dist < min_dist:
                            min_dist = dist
                            ramp_entry_point = coord
        
        # Find taxiway path from current position to ramp entry
        # Look for taxiways that connect current position to ramp
        if ramp_entry_point:
            # Find taxiways that pass near the ramp entry point
            connecting_taxiways = []
            for taxiway in taxiways:
                points = taxiway.get('points', [])
                taxiway_coords = [(p['x'], p['y']) for p in points if 'x' in p and 'y' in p]
                
                for coord in taxiway_coords:
                    dist_to_ramp = self._distance(coord, ramp_entry_point)
                    if dist_to_ramp < 0.001:  # ~111 meters
                        connecting_taxiways.append({
                            'taxiway': taxiway.get('taxiway', ''),
                            'points': taxiway_coords,
                            'connect_point': coord,
                            'dist_to_ramp': dist_to_ramp
                        })
                        break
            
            # Sort by distance to ramp
            connecting_taxiways.sort(key=lambda x: x['dist_to_ramp'])
            
            # Find the best path through taxiways
            if connecting_taxiways:
                best_taxiway = connecting_taxiways[0]
                taxiway_points = best_taxiway['points']
                
                # Find closest point on this taxiway to current position
                closest_idx = 0
                min_dist = float('inf')
                for i, coord in enumerate(taxiway_points):
                    dist = self._distance(current_pos, coord)
                    if dist < min_dist:
                        min_dist = dist
                        closest_idx = i
                
                # Find closest point to ramp entry
                ramp_idx = 0
                min_dist = float('inf')
                for i, coord in enumerate(taxiway_points):
                    dist = self._distance(coord, ramp_entry_point)
                    if dist < min_dist:
                        min_dist = dist
                        ramp_idx = i
                
                # Add taxiway points from current position toward ramp
                if closest_idx <= ramp_idx:
                    route.extend(taxiway_points[closest_idx:ramp_idx + 1])
                else:
                    route.extend(reversed(taxiway_points[ramp_idx:closest_idx + 1]))
                
                logger.info(f"[{self.get_callsign()}] Using taxiway {best_taxiway['taxiway']} to reach ramp")
        
        # Add ramp points from entry to gate
        if target_ramp:
            ramp_points = target_ramp.get('points', [])
            if ramp_points:
                ramp_coords = [(p['x'], p['y']) for p in ramp_points if 'x' in p and 'y' in p]
                
                if ramp_coords:
                    # Find closest ramp point to last route point (or current pos)
                    last_pos = route[-1] if route else current_pos
                    closest_ramp_idx = 0
                    min_dist = float('inf')
                    for i, coord in enumerate(ramp_coords):
                        dist = self._distance(last_pos, coord)
                        if dist < min_dist:
                            min_dist = dist
                            closest_ramp_idx = i
                    
                    # Find closest ramp point to gate
                    closest_to_gate_idx = 0
                    min_dist = float('inf')
                    for i, coord in enumerate(ramp_coords):
                        dist = self._distance((gate_lat, gate_lon), coord)
                        if dist < min_dist:
                            min_dist = dist
                            closest_to_gate_idx = i
                    
                    # Add ramp points from entry toward gate
                    if closest_ramp_idx <= closest_to_gate_idx:
                        route.extend(ramp_coords[closest_ramp_idx:closest_to_gate_idx + 1])
                    else:
                        route.extend(reversed(ramp_coords[closest_to_gate_idx:closest_ramp_idx + 1]))
        
        # Add gate position as final waypoint
        route.append((gate_lat, gate_lon))
        
        # Clean up route - remove duplicates and points too close together
        cleaned_route = []
        for point in route:
            if not cleaned_route:
                cleaned_route.append(point)
            else:
                dist = self._distance(cleaned_route[-1], point)
                if dist > 0.00002:  # ~2 meters
                    cleaned_route.append(point)
        
        return cleaned_route
    
    def _log_arrival_event(self, event_type, data):
        """Log arrival events to dedicated log file
        
        Args:
            event_type: Type of event (LANDING_START, EXIT_FOUND, etc.)
            data: Dictionary with event data
        """
        import os
        import json
        from datetime import datetime
        
        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        log_file = os.path.join(log_dir, "arrivals.log")
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        
        log_entry = {
            "timestamp": timestamp,
            "callsign": self.get_callsign(),
            "flight_number": getattr(self, 'flight_number', 'Unknown'),
            "aircraft_type": self.aircraft_type,
            "event": event_type,
            "data": data
        }
        
        try:
            with open(log_file, 'a') as f:
                f.write(json.dumps(log_entry) + '\n')
        except Exception as e:
            logger.error(f"Failed to write arrival log: {e}")
    
    def _calculate_distance(self, lat1, lon1, lat2, lon2):
        """Calculate distance between two points in degrees"""
        import math
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        return math.sqrt(dlat**2 + dlon**2)
    
    def _calculate_turn_angle(self, waypoint1, waypoint2):
        """Calculate the turn angle between two waypoints"""
        import math
        lat1, lon1 = waypoint1
        lat2, lon2 = waypoint2
        
        # Calculate bearing to each waypoint from current position
        current_lat, current_lon = self.position
        
        # Bearing to waypoint1
        dlat1 = lat1 - current_lat
        dlon1 = lon1 - current_lon
        bearing1 = math.degrees(math.atan2(dlon1, dlat1)) % 360
        
        # Bearing to waypoint2
        dlat2 = lat2 - current_lat
        dlon2 = lon2 - current_lon
        bearing2 = math.degrees(math.atan2(dlon2, dlat2)) % 360
        
        # Calculate angle difference
        angle_diff = abs(bearing2 - bearing1)
        if angle_diff > 180:
            angle_diff = 360 - angle_diff
        
        return angle_diff
    
    def _get_traffic_ahead_distance(self) -> Optional[float]:
        """Return distance in metres to the nearest ground aircraft directly ahead, or None.

        'Directly ahead' means within 80 m and within ±55° of the current heading.
        Used for ground-conflict separation so trailing aircraft hold behind stopped traffic.
        """
        manager = self.aircraft_manager
        if not manager:
            return None

        LOOKAHEAD_M     = 80.0
        LOOKAHEAD_DEG   = LOOKAHEAD_M / 111000.0
        CONE_HALF_ANGLE = 55.0

        lat, lon = self.position
        best: Optional[float] = None

        aircraft_dict = getattr(manager, 'aircraft', {})
        others = aircraft_dict.values() if isinstance(aircraft_dict, dict) else aircraft_dict

        for other in others:
            if other is self:
                continue
            # Skip airborne / parked-at-gate aircraft
            if other.state in (self.STATE_PARKED, self.STATE_DEPARTED, self.STATE_APPROACH):
                continue

            o_lat, o_lon = other.position
            dlat = o_lat - lat
            dlon = o_lon - lon

            # Quick bounding-box cull before the sqrt
            if abs(dlat) > LOOKAHEAD_DEG or abs(dlon) > LOOKAHEAD_DEG:
                continue

            dist_m = math.sqrt(dlat * dlat + dlon * dlon) * 111000.0
            if dist_m > LOOKAHEAD_M:
                continue

            bearing = math.degrees(math.atan2(dlon, dlat)) % 360
            angle_diff = abs(((bearing - self.heading) + 180) % 360 - 180)
            if angle_diff <= CONE_HALF_ANGLE:
                if best is None or dist_m < best:
                    best = dist_m

        return best

    def _check_holdshort_approach(self):
        """Check if aircraft is approaching an uncleared hold short bar.

        Returns (distance_metres, runway) for the nearest uncleared bar being
        approached within 100 m, or None if no such bar exists.
        Used by _update_taxi() for progressive braking.
        """
        holdshort_bars = self.airport_data.get('holdshort_bars', [])
        if not holdshort_bars:
            return None

        lat, lon = self.position
        DETECT_DEG = 0.00090  # ~100 m look-ahead

        closest_dist_m = float('inf')
        closest_runway = None

        for bar in holdshort_bars:
            runway = bar.get('runway', '')
            points = bar.get('points', [])

            # Arrivals never hold short of their own landing runway
            if self.flight_type == 'arrival' and runway == self.expected_runway:
                continue
            # Skip bars we're cleared to cross
            if runway in self.cleared_runways:
                continue

            if len(points) >= 2:
                p1 = (points[0].get('x'), points[0].get('y'))
                p2 = (points[1].get('x'), points[1].get('y'))
                if None in (*p1, *p2):
                    continue

                dist_deg = self._distance_to_line_segment((lat, lon), p1, p2)
                if dist_deg >= DETECT_DEG:
                    continue

                dist_m = dist_deg * 111000.0
                # Within 25 m: count regardless of speed (prevents overshoot at slow speed).
                # Beyond 25 m: require the aircraft to actually be heading toward the bar.
                if dist_m < 25.0 or self._is_approaching_line((lat, lon), p1, p2):
                    if dist_m < closest_dist_m:
                        closest_dist_m = dist_m
                        closest_runway = runway

        return (closest_dist_m, closest_runway) if closest_runway is not None else None

    def _check_holdshort_bars(self) -> bool:
        """Check if aircraft is approaching a hold short bar and needs to stop

        Returns:
            True if aircraft must hold (stop), False otherwise
        """
        holdshort_bars = self.airport_data.get('holdshort_bars', [])
        if not holdshort_bars:
            logger.debug(f"[{self.get_callsign()}] No holdshort bars in airport data")
            return False
        
        lat, lon = self.position
        #logger.debug(f"[{self.get_callsign()}] Checking {len(holdshort_bars)} hold short bars at position ({lat:.6f}, {lon:.6f})")
        
        for bar in holdshort_bars:
            runway = bar.get('runway', '')
            points = bar.get('points', [])

            # Arrivals never hold short of the runway they just landed on
            if self.flight_type == 'arrival' and runway == self.expected_runway:
                continue

            # Check if we have clearance for this runway
            # If cleared, we can cross but still need to check distance
            has_clearance = runway in self.cleared_runways
            
            if len(points) >= 2:
                # Get the two endpoints of the hold short bar
                p1_lat = points[0].get('x')
                p1_lon = points[0].get('y')
                p2_lat = points[1].get('x')
                p2_lon = points[1].get('y')
                
                if p1_lat and p1_lon and p2_lat and p2_lon:
                    # Calculate distance from aircraft to the hold short line
                    # Using perpendicular distance to line segment
                    distance_to_bar = self._distance_to_line_segment(
                        (lat, lon), (p1_lat, p1_lon), (p2_lat, p2_lon)
                    )
                    
                    # Hold short threshold - stop if within 40 meters (~0.00036 degrees)
                    # Smaller radius ensures aircraft must be pointing at runway to trigger
                    hold_threshold = 0.00036
                    
                    if distance_to_bar < hold_threshold:
                        # Check if we're approaching the bar (not already past it)
                        if self._is_approaching_line((lat, lon), (p1_lat, p1_lon), (p2_lat, p2_lon)):
                            # If we have clearance, we can cross - don't stop
                            if has_clearance:
                                logger.debug(f"[{self.get_callsign()}] Crossing hold short for runway {runway} - cleared")
                                continue
                            
                            # No clearance - must stop
                            # Only log and radio once per hold short event
                            if self.holding_short_runway != runway:
                                logger.warning(f"[{self.get_callsign()}] HOLDING SHORT of runway {runway} - no clearance")
                                
                                # Set hold short restriction
                                self.hold_short = runway
                                self.holding_short_runway = runway
                                
                                logger.info(f"[{self.get_callsign()}] ✋ STOPPED at hold short runway {runway} - waiting for tower clearance")
                            return True
        
        return False
    
    def _distance_to_line_segment(self, point, line_start, line_end):
        """Calculate perpendicular distance from point to line segment"""
        px, py = point
        x1, y1 = line_start
        x2, y2 = line_end
        
        # Calculate line segment length squared
        line_len_sq = (x2 - x1)**2 + (y2 - y1)**2
        
        if line_len_sq == 0:
            # Line segment is a point
            return math.sqrt((px - x1)**2 + (py - y1)**2)
        
        # Calculate projection of point onto line (parameterized as t)
        t = max(0, min(1, ((px - x1) * (x2 - x1) + (py - y1) * (y2 - y1)) / line_len_sq))
        
        # Find closest point on line segment
        closest_x = x1 + t * (x2 - x1)
        closest_y = y1 + t * (y2 - y1)
        
        # Return distance to closest point
        return math.sqrt((px - closest_x)**2 + (py - closest_y)**2)
    
    def _is_approaching_line(self, point, line_start, line_end):
        """Check if aircraft is approaching the line (not already past it)"""
        # Use heading to determine if we're approaching
        # If we're moving toward the line, we're approaching
        px, py = point
        x1, y1 = line_start
        x2, y2 = line_end
        
        # Calculate vector from aircraft to closest point on line
        line_len_sq = (x2 - x1)**2 + (y2 - y1)**2
        if line_len_sq == 0:
            return True
        
        t = max(0, min(1, ((px - x1) * (x2 - x1) + (py - y1) * (y2 - y1)) / line_len_sq))
        closest_x = x1 + t * (x2 - x1)
        closest_y = y1 + t * (y2 - y1)
        
        # Vector from aircraft to line
        to_line_x = closest_x - px
        to_line_y = closest_y - py
        
        # Aircraft's heading vector
        heading_rad = math.radians(self.heading)
        heading_x = math.cos(heading_rad)
        heading_y = math.sin(heading_rad)
        
        # Dot product: if positive, we're heading toward the line
        dot_product = (heading_x * to_line_x) + (heading_y * to_line_y)
        
        # If dot product is positive and we're moving, we're approaching
        return dot_product > 0 and self.speed > 0.5
    
    def request_pushback(self):
        """Aircraft requests pushback clearance - waits for ATC approval"""
        # Cannot call if not squawking Mode C with correct code
        if not self._can_make_radio_call():
            return
        
        if self.radio_callback:
            gate_str = self.gate if self.gate else ""
            readback = self._generate_realistic_readback("request_pushback", {"gate": gate_str})
            self.radio_callback(readback, is_atc=False, callsign=self.get_callsign())
        # Don't auto-approve - ATC must manually approve with 'pa' command
    
    def _can_make_radio_call(self):
        """Check if aircraft can make radio calls (must be squawking Mode C with correct code)."""
        # Must be squawking Mode C
        if not self.squawking_mode_c:
            return False
        
        # Must have a squawk code (pilot is transmitting something)
        if not self.current_squawk_code:
            return False
        
        # If controller edited the strip BCN (editor_bcn_override), pilot doesn't know—they're still
        # squawking the code they were given, so they can still call up.
        if getattr(self, "editor_bcn_override", False):
            return True
        
        # Otherwise require squawk to match flight plan (correct code)
        if not self.correct_squawk_code:
            return False
        current_code_str = str(self.current_squawk_code).zfill(4)
        correct_code_str = str(self.correct_squawk_code).zfill(4)
        if current_code_str != correct_code_str:
            return False
        
        return True
    
    def clear_pushback(self, send_radio=False, skip_readback=False):
        """Clear aircraft for pushback"""
        logger.info(f"[{self.get_callsign()}] PUSHBACK CLEARANCE RECEIVED")
        
        # Schedule realistic readback transmission (skip if part of combined command)
        if not skip_readback and self._can_make_radio_call():
            readback = self._generate_realistic_readback("pushback")
            self._schedule_radio(readback, is_atc=False)
        
        # Schedule actual pushback to start after realistic delay (3-5 seconds)
        def execute_pushback():
            logger.info(f"[{self.get_callsign()}] Starting pushback - State changing from {self.state} to PUSHBACK")
            self.cleared_to_pushback = True
            self.state = self.STATE_PUSHBACK
            logger.debug(f"[{self.get_callsign()}] State is now: {self.state}")
        
        # Use default delay (3-5 seconds) for action
        self._schedule_action(execute_pushback)
    
    def request_taxi(self, destination: str = None):
        """Aircraft requests taxi clearance
        
        Args:
            destination: Optional destination (not typically mentioned by pilots)
        """
        # Cannot call if not squawking Mode C with correct code
        if not self._can_make_radio_call():
            return
        
        if self.radio_callback:
            # Aircraft don't mention runway in taxi request - they expect the active runway
            # or the runway ATC told them to expect
            readback = self._generate_realistic_readback("ready_to_taxi")
            self.radio_callback(readback, is_atc=False, callsign=self.get_callsign())
    
    def clear_taxi(self, destination: str, via: List[str] = None, send_radio=False, skip_readback=False):
        """Clear aircraft to taxi
        
        Args:
            destination: Taxi destination (e.g., "runway 02")
            via: List of taxiway letters to use
            send_radio: Legacy parameter (unused)
            skip_readback: If True, skip the readback (used for combined commands)
        """
        logger.info(f"[{self.get_callsign()}] === TAXI CLEARANCE ISSUED ===")
        logger.info(f"[{self.get_callsign()}] Destination: {destination}")
        logger.info(f"[{self.get_callsign()}] Via taxiways: {via or []}")
        logger.debug(f"[{self.get_callsign()}] Current position: {self.position}")
        logger.info(f"[{self.get_callsign()}] Current location: {self.get_current_location_description()}")
        
        # Schedule realistic readback transmission (skip if part of combined command)
        if not skip_readback:
            readback = self._generate_realistic_readback("taxi", {
                "destination": destination,
                "via": via
            })
            self._schedule_radio(readback, is_atc=False)
        
        # Schedule actual taxi to start after realistic delay (3-5 seconds)
        def execute_taxi():
            logger.info(f"[{self.get_callsign()}] Starting taxi movement")
            self.cleared_to_taxi = True
            self.taxi_destination = destination
            self.taxi_via = via or []
            self.current_taxiway_index = 0  # Reset to first taxiway
            self.state = self.STATE_TAXI
            
            # Redundant route build: graph (with via) -> legacy via -> graph to runway -> direct
            logger.info(f"[{self.get_callsign()}] Building taxi route...")
            self.route = []
            if self.airport_graph and via:
                self.route = self.get_route_to_surface(destination, via)
                if self.route:
                    logger.info(f"[{self.get_callsign()}] Graph route (via) built with {len(self.route)} waypoints")
            if not self.route:
                self.route = self._build_taxi_route(via or [])
                if self.route:
                    logger.info(f"[{self.get_callsign()}] Legacy taxi route built with {len(self.route)} waypoints")
            if not self.route and self.airport_graph and destination:
                # Fallback: path directly to runway/threshold surface
                rwy_surface = f"Runway {destination}" if not destination.startswith("Runway") else destination
                self.route = self.airport_graph.find_path(self.position, rwy_surface, None)
                if self.route:
                    logger.info(f"[{self.get_callsign()}] Graph direct-to-runway route with {len(self.route)} waypoints")
            if self.route:
                self.route = self._optimize_taxi_route(self.route)
            if not self.route and self.airport_data:
                # Last resort: direct to first runway threshold we can find
                runways = self.airport_data.get('runways', [])
                for rwy in runways:
                    pts = rwy.get('points', [])
                    if pts and (destination in (rwy.get('name') or '')):
                        p = pts[0]
                        if p.get('x') is not None and p.get('y') is not None:
                            self.route = [(p['x'], p['y'])]
                            logger.warning(f"[{self.get_callsign()}] Using direct-to-threshold fallback")
                            break
            
            if self.route:
                self.target_position = self.route.pop(0)
                logger.info(f"[{self.get_callsign()}] First target: {self.target_position}, {len(self.route)} waypoints left")
            else:
                logger.warning(f"[{self.get_callsign()}] No route built; holding.")
        
        # Use default delay (3-5 seconds) for action
        self._schedule_action(execute_taxi)
    
    def _optimize_taxi_route(self, route: List[Tuple[float, float]], 
                             min_segment_deg: float = 0.00008,
                             colinear_angle_deg: float = 5.0) -> List[Tuple[float, float]]:
        """Remove redundant waypoints: duplicates, near-duplicates, and colinear midpoints.
        Keeps route shape but reduces waypoint count for smoother taxi."""
        if not route or len(route) <= 2:
            return list(route)
        out = [route[0]]
        for i in range(1, len(route) - 1):
            prev = out[-1]
            curr = route[i]
            nxt = route[i + 1]
            dist_prev = self._distance(prev, curr)
            dist_next = self._distance(curr, nxt)
            if dist_prev < 0.00002:
                continue
            if dist_prev < min_segment_deg and dist_next < min_segment_deg:
                continue
            # Drop colinear midpoint: if angle at curr is ~180°, skip curr
            d1_lat = curr[0] - prev[0]
            d1_lon = curr[1] - prev[1]
            d2_lat = nxt[0] - curr[0]
            d2_lon = nxt[1] - curr[1]
            cross = d1_lat * d2_lon - d1_lon * d2_lat
            dot = d1_lat * d2_lat + d1_lon * d2_lon
            len1 = math.sqrt(d1_lat*d1_lat + d1_lon*d1_lon) or 1e-10
            len2 = math.sqrt(d2_lat*d2_lat + d2_lon*d2_lon) or 1e-10
            angle_deg = abs(math.degrees(math.atan2(abs(cross), dot))) if (len1 * len2) else 0
            if angle_deg < colinear_angle_deg:
                continue
            out.append(curr)
        out.append(route[-1])
        return out
    
    def _build_taxi_route(self, via_taxiways: List[str]) -> List[Tuple[float, float]]:
        """Build waypoint route from taxiway letters with ramp line and runway-aware logic"""
        if not self.airport_data or not via_taxiways:
            return []
        
        taxiways = self.airport_data.get('taxiways', [])
        ramps = self.airport_data.get('ramps', [])
        route = []
        current_pos = self.position
        
        logger.info(f"[{self.get_callsign()}] Building route for taxiways: {via_taxiways}")
        logger.info(f"[{self.get_callsign()}] Destination: {self.taxi_destination}")
        
        # Step 1: Add ramp line to first taxiway entry point
        route = self._add_ramp_to_taxiway_path(current_pos, via_taxiways[0], ramps, taxiways)
        if not route:
            logger.warning(f"[{self.get_callsign()}] Could not build ramp path")
            route = [current_pos]
        
        # Step 2: Add each taxiway in sequence with intelligent direction
        for i, taxiway_letter in enumerate(via_taxiways):
            logger.debug(f"[{self.get_callsign()}] Processing taxiway {i+1}/{len(via_taxiways)}: {taxiway_letter}")
            
            # Find taxiway by letter
            taxiway_data = None
            for taxiway in taxiways:
                if taxiway.get('taxiway', '').upper() == taxiway_letter.upper():
                    taxiway_data = taxiway
                    break
            
            if not taxiway_data:
                logger.warning(f"[{self.get_callsign()}] Taxiway {taxiway_letter} not found in airport data")
                continue
            
            points = taxiway_data.get('points', [])
            if not points:
                continue
            
            # Convert points to tuples
            taxiway_points = []
            for point in points:
                lat = point.get('x')
                lon = point.get('y')
                if lat and lon:
                    taxiway_points.append((lat, lon))
            
            if not taxiway_points:
                continue
            
            # Find closest point on this taxiway to current route end
            last_route_point = route[-1] if route else current_pos
            min_dist = float('inf')
            closest_index = 0
            for idx, point in enumerate(taxiway_points):
                dist = self._distance(last_route_point, point)
                if dist < min_dist:
                    min_dist = dist
                    closest_index = idx
            
            logger.debug(f"[{self.get_callsign()}] Closest point on {taxiway_letter}: index {closest_index}/{len(taxiway_points)}, distance {min_dist:.6f}° (~{min_dist * 111000:.1f}m)")
            
            # Add waypoints based on direction toward runway/next taxiway
            waypoints_to_add = self._get_taxiway_waypoints_toward_destination(
                taxiway_points,
                closest_index,
                taxiway_letter,
                via_taxiways,
                i,
                taxiways
            )
            route.extend(waypoints_to_add)
            logger.debug(f"[{self.get_callsign()}] Added {len(waypoints_to_add)} waypoints from {taxiway_letter}")
        
        # Remove duplicate consecutive waypoints and smooth the route
        cleaned_route = []
        for i, point in enumerate(route):
            if not cleaned_route:
                # Always add first point
                cleaned_route.append(point)
            else:
                dist = self._distance(cleaned_route[-1], point)
                if dist > 0.000001:  # ~0.1m threshold
                    cleaned_route.append(point)
                else:
                    logger.debug(f"[{self.get_callsign()}] Skipped duplicate waypoint at {dist * 111000:.1f}m")
        
        cleaned_route = self._optimize_taxi_route(cleaned_route)
        logger.info(f"[{self.get_callsign()}] Cleaned route: {len(route)} → {len(cleaned_route)} waypoints")
        return cleaned_route
    
    def _add_ramp_to_taxiway_path(self, start_pos: Tuple[float, float], first_taxiway: str, 
                                    ramps: List[Dict], taxiways: List[Dict]) -> List[Tuple[float, float]]:
        """Build path from current position along ramp line to first taxiway entry"""
        route = []
        
        # Get ramp points
        ramp_points = []
        for ramp in ramps:
            if ramp.get('ramp') == 'main_ramp':
                for point in ramp.get('points', []):
                    lat = point.get('x')
                    lon = point.get('y')
                    if lat and lon:
                        ramp_points.append((lat, lon))
                break
        
        if not ramp_points:
            logger.warning(f"[{self.get_callsign()}] No ramp points found")
            return [start_pos]
        
        # Find first taxiway entry point
        first_taxiway_data = None
        for taxiway in taxiways:
            if taxiway.get('taxiway', '').upper() == first_taxiway.upper():
                first_taxiway_data = taxiway
                break
        
        if not first_taxiway_data:
            logger.warning(f"[{self.get_callsign()}] First taxiway {first_taxiway} not found")
            return [start_pos]
        
        # Get first taxiway points
        taxiway_points = []
        for point in first_taxiway_data.get('points', []):
            lat = point.get('x')
            lon = point.get('y')
            if lat and lon:
                taxiway_points.append((lat, lon))
        
        if not taxiway_points:
            return [start_pos]
        
        # Find closest ramp point to current position
        min_dist = float('inf')
        start_ramp_idx = 0
        for idx, point in enumerate(ramp_points):
            dist = self._distance(start_pos, point)
            if dist < min_dist:
                min_dist = dist
                start_ramp_idx = idx
        
        # Find closest ramp point to first taxiway
        min_dist = float('inf')
        end_ramp_idx = 0
        for idx, ramp_point in enumerate(ramp_points):
            for taxiway_point in taxiway_points:
                dist = self._distance(ramp_point, taxiway_point)
                if dist < min_dist:
                    min_dist = dist
                    end_ramp_idx = idx
        
        logger.info(f"[{self.get_callsign()}] Ramp path: point {start_ramp_idx} → {end_ramp_idx}")
        
        # Add ramp points from start to taxiway entry
        if start_ramp_idx <= end_ramp_idx:
            route.extend(ramp_points[start_ramp_idx:end_ramp_idx + 1])
        else:
            route.extend(reversed(ramp_points[end_ramp_idx:start_ramp_idx + 1]))
        
        logger.info(f"[{self.get_callsign()}] Added {len(route)} ramp waypoints")
        return route
    
    def _get_taxiway_waypoints_toward_destination(self, taxiway_points: List[Tuple[float, float]],
                                                   closest_index: int, taxiway_letter: str,
                                                   via_taxiways: List[str], current_idx: int,
                                                   taxiways: List[Dict]) -> List[Tuple[float, float]]:
        """Get waypoints from taxiway in direction toward destination using runway awareness"""
        
        # Get runway location if destination is a runway
        runway_location = self._get_runway_location()
        
        # If last taxiway, use runway location to determine direction
        if current_idx == len(via_taxiways) - 1:
            if runway_location:
                first_point = taxiway_points[0]
                last_point = taxiway_points[-1]
                
                dist_first_to_runway = self._distance(first_point, runway_location)
                dist_last_to_runway = self._distance(last_point, runway_location)
                
                logger.debug(f"[{self.get_callsign()}] Distance from {taxiway_letter} first to runway: {dist_first_to_runway:.6f}° (~{dist_first_to_runway * 111000:.1f}m)")
                logger.debug(f"[{self.get_callsign()}] Distance from {taxiway_letter} last to runway: {dist_last_to_runway:.6f}° (~{dist_last_to_runway * 111000:.1f}m)")
                
                if closest_index < len(taxiway_points) / 2:
                    # Near start
                    if dist_last_to_runway < dist_first_to_runway:
                        logger.info(f"[{self.get_callsign()}] Last taxiway - going FORWARD toward runway {self.taxi_destination}")
                        return taxiway_points[closest_index:]
                    else:
                        logger.info(f"[{self.get_callsign()}] Last taxiway - going BACKWARD toward runway {self.taxi_destination}")
                        return list(reversed(taxiway_points[:closest_index + 1]))
                else:
                    # Near end
                    if dist_first_to_runway < dist_last_to_runway:
                        logger.info(f"[{self.get_callsign()}] Last taxiway - going BACKWARD toward runway {self.taxi_destination}")
                        return list(reversed(taxiway_points[:closest_index + 1]))
                    else:
                        logger.info(f"[{self.get_callsign()}] Last taxiway - going FORWARD toward runway {self.taxi_destination}")
                        return taxiway_points[closest_index:]
            else:
                logger.info(f"[{self.get_callsign()}] Last taxiway - adding from closest to end")
                return taxiway_points[closest_index:]
        
        # Get next taxiway
        next_taxiway_letter = via_taxiways[current_idx + 1]
        next_taxiway_data = None
        for tw in taxiways:
            if tw.get('taxiway', '').upper() == next_taxiway_letter.upper():
                next_taxiway_data = tw
                break
        
        if not next_taxiway_data:
            logger.warning(f"[{self.get_callsign()}] Next taxiway {next_taxiway_letter} not found")
            return taxiway_points[closest_index:]
        
        # Get next taxiway points
        next_points = []
        for point in next_taxiway_data.get('points', []):
            lat = point.get('x')
            lon = point.get('y')
            if lat and lon:
                next_points.append((lat, lon))
        
        if not next_points:
            return taxiway_points[closest_index:]
        
        # Check which direction gets closer to next taxiway (and ultimately runway)
        first_point = taxiway_points[0]
        last_point = taxiway_points[-1]
        
        # Find minimum distance from each end to ANY point on next taxiway
        dist_first_to_next = min(self._distance(first_point, np) for np in next_points)
        dist_last_to_next = min(self._distance(last_point, np) for np in next_points)
        
        # Also consider runway location for better decision making
        if runway_location:
            dist_first_to_runway = self._distance(first_point, runway_location)
            dist_last_to_runway = self._distance(last_point, runway_location)
            
            logger.debug(f"[{self.get_callsign()}] Distance from {taxiway_letter} first to {next_taxiway_letter}: {dist_first_to_next:.6f}° (~{dist_first_to_next * 111000:.1f}m)")
            logger.debug(f"[{self.get_callsign()}] Distance from {taxiway_letter} last to {next_taxiway_letter}: {dist_last_to_next:.6f}° (~{dist_last_to_next * 111000:.1f}m)")
            logger.debug(f"[{self.get_callsign()}] Distance from {taxiway_letter} first to runway: {dist_first_to_runway:.6f}° (~{dist_first_to_runway * 111000:.1f}m)")
            logger.debug(f"[{self.get_callsign()}] Distance from {taxiway_letter} last to runway: {dist_last_to_runway:.6f}° (~{dist_last_to_runway * 111000:.1f}m)")
            
            # Prefer direction that gets closer to both next taxiway AND runway
            # Weight: 70% next taxiway, 30% runway
            score_forward = (0.7 * dist_last_to_next) + (0.3 * dist_last_to_runway)
            score_backward = (0.7 * dist_first_to_next) + (0.3 * dist_first_to_runway)
        else:
            logger.debug(f"[{self.get_callsign()}] Distance from {taxiway_letter} first to {next_taxiway_letter}: {dist_first_to_next:.6f}° (~{dist_first_to_next * 111000:.1f}m)")
            logger.debug(f"[{self.get_callsign()}] Distance from {taxiway_letter} last to {next_taxiway_letter}: {dist_last_to_next:.6f}° (~{dist_last_to_next * 111000:.1f}m)")
            
            score_forward = dist_last_to_next
            score_backward = dist_first_to_next
        
        # Determine direction based on scores
        if closest_index < len(taxiway_points) / 2:
            # We're near the start
            if score_forward < score_backward:
                # Go forward
                logger.info(f"[{self.get_callsign()}] Going FORWARD on {taxiway_letter} toward {next_taxiway_letter} (score: {score_forward:.6f})")
                return taxiway_points[closest_index:]
            else:
                # Go backward
                logger.info(f"[{self.get_callsign()}] Going BACKWARD on {taxiway_letter} toward {next_taxiway_letter} (score: {score_backward:.6f})")
                return list(reversed(taxiway_points[:closest_index + 1]))
        else:
            # We're near the end
            if score_backward < score_forward:
                # Go backward
                logger.info(f"[{self.get_callsign()}] Going BACKWARD on {taxiway_letter} toward {next_taxiway_letter} (score: {score_backward:.6f})")
                return list(reversed(taxiway_points[:closest_index + 1]))
            else:
                # Go forward
                logger.info(f"[{self.get_callsign()}] Going FORWARD on {taxiway_letter} toward {next_taxiway_letter} (score: {score_forward:.6f})")
                return taxiway_points[closest_index:]
    
    def _get_runway_location(self) -> Tuple[float, float]:
        """Get the location of the destination runway"""
        if not self.taxi_destination or not self.airport_data:
            return None
        
        # Check if destination is a runway (starts with "runway")
        if not self.taxi_destination.lower().startswith("runway"):
            return None
        
        # Extract runway number (e.g., "runway 02" -> "02")
        runway_parts = self.taxi_destination.split()
        if len(runway_parts) < 2:
            return None
        
        runway_number = runway_parts[1]
        
        # Get runway definitions from airport data
        runway_definitions = self.airport_data.get('runway_definition', [])
        for runway_def in runway_definitions:
            if runway_def.get('name') == runway_number:
                locations = runway_def.get('location', [])
                if locations:
                    first_loc = locations[0]
                    lat = first_loc.get('x')
                    lon = first_loc.get('y')
                    if lat and lon:
                        logger.debug(f"[{self.get_callsign()}] Found runway {runway_number} at ({lat}, {lon})")
                        return (lat, lon)
        
        logger.warning(f"[{self.get_callsign()}] Runway {runway_number} location not found in runway_definition")
        return None
    
    def _distance(self, pos1: Tuple[float, float], pos2: Tuple[float, float]) -> float:
        """Calculate distance between two positions"""
        lat1, lon1 = pos1
        lat2, lon2 = pos2
        return math.sqrt((lat2 - lat1)**2 + (lon2 - lon1)**2)
    
    def _check_and_switch_taxiway(self):
        """Check if we're crossing a taxiway intersection and need to switch"""
        if not self.taxi_via or self.current_taxiway_index >= len(self.taxi_via) - 1:
            return  # No more taxiways to switch to
        
        # Get next taxiway we should be turning onto
        next_taxiway_letter = self.taxi_via[self.current_taxiway_index + 1]
        
        # Find next taxiway data
        taxiways = self.airport_data.get('taxiways', [])
        next_taxiway_data = None
        for tw in taxiways:
            if tw.get('taxiway', '').upper() == next_taxiway_letter.upper():
                next_taxiway_data = tw
                break
        
        if not next_taxiway_data:
            return
        
        # Get next taxiway points
        next_points = []
        for point in next_taxiway_data.get('points', []):
            lat = point.get('x')
            lon = point.get('y')
            if lat and lon:
                next_points.append((lat, lon))
        
        if not next_points:
            return
        
        # Check if we're close to ANY point on the next taxiway (intersection detection)
        current_pos = self.position
        min_dist_to_next = min(self._distance(current_pos, np) for np in next_points)
        
        # If we're within 50m (~0.00045°) of the next taxiway, we're at the intersection
        intersection_threshold = 0.00045
        if min_dist_to_next < intersection_threshold:
            logger.info(f"[{self.get_callsign()}] 🔄 INTERSECTION DETECTED! Switching to taxiway {next_taxiway_letter}")
            logger.debug(f"[{self.get_callsign()}] Distance to {next_taxiway_letter}: {min_dist_to_next:.6f}° (~{min_dist_to_next * 111000:.1f}m)")
            
            # Find closest point on next taxiway
            min_dist = float('inf')
            closest_index = 0
            for idx, point in enumerate(next_points):
                dist = self._distance(current_pos, point)
                if dist < min_dist:
                    min_dist = dist
                    closest_index = idx
            
            # Build new route from this point
            self.current_taxiway_index += 1
            remaining_taxiways = self.taxi_via[self.current_taxiway_index:]
            
            logger.info(f"[{self.get_callsign()}] Rebuilding route from {next_taxiway_letter} for: {remaining_taxiways}")
            
            # Get waypoints for remaining taxiways
            new_route = []
            for i, taxiway_letter in enumerate(remaining_taxiways):
                # Find taxiway data
                taxiway_data = None
                for tw in taxiways:
                    if tw.get('taxiway', '').upper() == taxiway_letter.upper():
                        taxiway_data = tw
                        break
                
                if not taxiway_data:
                    continue
                
                # Get taxiway points
                taxiway_points = []
                for point in taxiway_data.get('points', []):
                    lat = point.get('x')
                    lon = point.get('y')
                    if lat and lon:
                        taxiway_points.append((lat, lon))
                
                if not taxiway_points:
                    continue
                
                # For first taxiway (the one we just switched to), start from closest point
                if i == 0:
                    # Determine direction using same logic as before
                    waypoints_to_add = self._get_taxiway_waypoints_toward_destination(
                        taxiway_points,
                        closest_index,
                        taxiway_letter,
                        remaining_taxiways,
                        i,
                        taxiways
                    )
                    new_route.extend(waypoints_to_add)
                else:
                    # For subsequent taxiways, find closest point and determine direction
                    last_route_point = new_route[-1] if new_route else current_pos
                    min_dist = float('inf')
                    closest_idx = 0
                    for idx, point in enumerate(taxiway_points):
                        dist = self._distance(last_route_point, point)
                        if dist < min_dist:
                            min_dist = dist
                            closest_idx = idx
                    
                    waypoints_to_add = self._get_taxiway_waypoints_toward_destination(
                        taxiway_points,
                        closest_idx,
                        taxiway_letter,
                        remaining_taxiways,
                        i,
                        taxiways
                    )
                    new_route.extend(waypoints_to_add)
            
            # Update route and target
            if new_route:
                self.route = new_route
                self.target_position = self.route.pop(0)
                logger.info(f"[{self.get_callsign()}] New route: {len(new_route)} waypoints, next target: {self.target_position}")
    
    def hold_short_of(self, runway: str):
        """Instruct aircraft to hold short"""
        self.hold_short = runway
        self.state = self.STATE_HOLDING
        self.speed = 0
    
    def handoff_to_tower(self, tower_controller=None):
        """Hand off aircraft to tower controller
        
        Ground hands off BEFORE hold short line.
        Tower then:
        1. Checks for arriving aircraft
        2. Clears to cross hold short line when safe
        3. Instructs line up and wait
        4. Clears for takeoff when runway is clear
        
        Args:
            tower_controller: VirtualTowerController instance (optional, will be retrieved from airport_graph if not provided)
        """
        if self.handed_off_to_tower:
            return  # Already handed off
        
        self.handed_off_to_tower = True
        
        # Notify tower controller if available
        if tower_controller:
            tower_controller.handoff_from_ground(self)
        
        if self.flight_type == "departure":
            # Departure aircraft - tower will handle crossing and takeoff
            logger.info(f"[{self.get_callsign()}] Handed off to tower for departure")
            
            # Tower will monitor and clear when ready (happens in update loop)
            # Aircraft should be holding short at this point
            logger.info(f"[{self.get_callsign()}] Tower monitoring, will clear to cross hold short when safe")
        else:
            # Arrival aircraft - tower handles landing
            logger.info(f"[{self.get_callsign()}] Handed off to tower for landing")
    
    def _check_and_clear_for_departure(self, aircraft_manager):
        """Tower checks for arrivals and clears aircraft through departure sequence
        
        Sequence:
        1. Check for arriving aircraft on final (within 1.5nm)
        2. If departing from this runway: skip cross clearance, just line up and wait
        3. If crossing runway: give cross clearance first, then line up and wait
        4. Clear for takeoff when runway is clear (no arrivals within 1.5nm)
        """
        # Debug: Entry conditions
        if not self.handed_off_to_tower:
            logger.debug(f"[TOWER DEBUG] {self.get_callsign()}: Not handed off to tower yet")
            return
        
        if self.flight_type != "departure":
            logger.debug(f"[TOWER DEBUG] {self.get_callsign()}: Not a departure (type: {self.flight_type})")
            return
        
        # Check if holding
        if self.state != self.STATE_HOLDING:
            logger.debug(f"[TOWER DEBUG] {self.get_callsign()}: Not holding (state: {self.state})")
            return
        
        logger.debug(f"[TOWER DEBUG] {self.get_callsign()}: Tower monitoring departure sequence")
        
        # Step 1: If not yet cleared to lineup, check hold short and clear
        if not hasattr(self, 'tower_cleared_to_lineup'):
            logger.debug(f"[TOWER DEBUG] {self.get_callsign()}: Step 1 - Checking for lineup clearance")
            
            # Must have hold short restriction to proceed
            if not self.hold_short:
                logger.debug(f"[TOWER DEBUG] {self.get_callsign()}: No hold short restriction set")
                return
            
            # Wait a few seconds after handoff before clearing (realistic delay)
            if not hasattr(self, 'tower_handoff_time'):
                self.tower_handoff_time = getattr(self, 'current_sim_time', 0.0)
                logger.debug(f"[TOWER DEBUG] {self.get_callsign()}: Recording handoff time")
            
            time_since_handoff = getattr(self, 'current_sim_time', 0.0) - self.tower_handoff_time
            if time_since_handoff < 3.0:  # Wait 3 seconds before clearing
                logger.debug(f"[TOWER DEBUG] {self.get_callsign()}: Waiting {3.0 - time_since_handoff:.1f}s before lineup clearance")
                return
            
            logger.debug(f"[TOWER DEBUG] {self.get_callsign()}: Holding short of runway {self.hold_short}")
            
            # Check for arriving aircraft (within 1.5nm)
            arriving_aircraft = self._check_for_arrivals(aircraft_manager)
            
            if arriving_aircraft:
                # Arrivals have priority - wait
                logger.info(f"[TOWER DEBUG] {self.get_callsign()}: ⏸️ HOLDING - Arrival traffic {arriving_aircraft.get_callsign()} on final")
                return
            
            logger.debug(f"[TOWER DEBUG] {self.get_callsign()}: ✅ No arrival traffic detected")
            
            # Check if departing from this runway (expected runway matches hold short runway)
            departing_from_runway = (hasattr(self, 'expected_runway') and 
                                    self.expected_runway and 
                                    self.hold_short and 
                                    self.expected_runway == self.hold_short)
            
            logger.info(f"[TOWER DEBUG] {self.get_callsign()}: Expected RWY: {getattr(self, 'expected_runway', 'None')}, Hold Short: {self.hold_short}, Departing from RWY: {departing_from_runway}")
            
            # Clear to lineup (skip cross clearance if departing from this runway)
            if departing_from_runway:
                logger.info(f"[TOWER DEBUG] {self.get_callsign()}: 🛫 Issuing LINEUP clearance (departing from runway)")
            else:
                logger.info(f"[TOWER DEBUG] {self.get_callsign()}: ➡️ Issuing CROSS & LINEUP clearance")
            
            self._clear_to_lineup(needs_cross_clearance=not departing_from_runway)
            return
        
        # Step 2: Already cleared to lineup, check if on runway for takeoff clearance
        logger.debug(f"[TOWER DEBUG] {self.get_callsign()}: Step 2 - Already cleared to lineup, checking position")
        
        if hasattr(self, 'last_known_surface'):
            logger.debug(f"[TOWER DEBUG] {self.get_callsign()}: Current surface: {self.last_known_surface}")
        else:
            logger.debug(f"[TOWER DEBUG] {self.get_callsign()}: ⚠️ No surface detection available")
        
        # Check if aircraft is on runway OR if aircraft has reached its lineup waypoint
        on_runway = (hasattr(self, 'last_known_surface') and self.last_known_surface and "runway" in self.last_known_surface.lower())
        
        # Also consider aircraft "in position" if it has no more waypoints and is cleared to lineup
        in_position = (not self.route and not self.target_position and hasattr(self, 'tower_cleared_to_lineup'))
        
        if on_runway or in_position:
            # On runway or in position, ready for takeoff
            if on_runway:
                logger.info(f"[TOWER DEBUG] {self.get_callsign()}: ✈️ Aircraft on {self.last_known_surface}")
            else:
                logger.info(f"[TOWER DEBUG] {self.get_callsign()}: ✈️ Aircraft in position for takeoff")
            
            if not hasattr(self, 'tower_cleared_for_takeoff'):
                logger.debug(f"[TOWER DEBUG] {self.get_callsign()}: Checking for arrivals before takeoff clearance...")
                
                # Final check for arrivals before takeoff clearance (within 1.5nm)
                arriving_aircraft = self._check_for_arrivals(aircraft_manager)
                
                if not arriving_aircraft:
                    logger.info(f"[TOWER DEBUG] {self.get_callsign()}: 🚀 CLEARED FOR TAKEOFF - Runway clear")
                    self._clear_for_takeoff()
                else:
                    logger.info(f"[TOWER DEBUG] {self.get_callsign()}: ⏸️ HOLDING on runway - Arrival {arriving_aircraft.get_callsign()} on final")
            else:
                logger.debug(f"[TOWER DEBUG] {self.get_callsign()}: Already cleared for takeoff")
        else:
            # Not on runway yet, still taxiing to lineup position
            if hasattr(self, 'last_known_surface'):
                logger.debug(f"[TOWER DEBUG] {self.get_callsign()}: ⏳ Taxiing to lineup position, currently on {self.last_known_surface}")
            else:
                logger.debug(f"[TOWER DEBUG] {self.get_callsign()}: ⏳ Taxiing to lineup position (surface unknown)")
    
    def _get_runway_heading(self, runway: str) -> Optional[float]:
        """Get runway heading from airport data
        
        Args:
            runway: Runway identifier (e.g., "02", "20")
            
        Returns:
            Runway heading in degrees, or None if not found
        """
        if not self.airport_data:
            return None
        
        # Check runway_definition for direction
        runway_definitions = self.airport_data.get('runway_definition', [])
        for rwy_def in runway_definitions:
            if rwy_def.get('name') == runway:
                # Check for direction field
                direction = rwy_def.get('direction')
                if direction:
                    try:
                        # Convert direction string to float (e.g., "021" -> 21.0)
                        return float(direction)
                    except (ValueError, TypeError):
                        logger.warning(f"[{self.get_callsign()}] Invalid direction format for runway {runway}: {direction}")
                
                # Fallback: calculate from runway number (e.g., "02" -> 20 degrees)
                try:
                    runway_num = int(runway)
                    return runway_num * 10.0
                except (ValueError, TypeError):
                    logger.warning(f"[{self.get_callsign()}] Could not parse runway number: {runway}")
        
        # Final fallback: use runway number
        try:
            runway_num = int(runway)
            return runway_num * 10.0
        except (ValueError, TypeError):
            return None
    
    def _check_for_arrivals(self, aircraft_manager):
        """Check if any aircraft are on final approach within 1.5nm"""
        if not aircraft_manager:
            return None
        
        # Get expected runway
        runway = self.hold_short or self.expected_runway
        if not runway:
            return None
        
        # Optimized: Only check arrival aircraft, skip departures
        # Also cache check results to avoid checking every frame
        if not hasattr(self, '_last_arrival_check_time'):
            self._last_arrival_check_time = 0.0
            self._cached_arrival_result = None
        
        # Only check every 0.5 seconds to reduce CPU usage
        current_time = getattr(self, 'current_sim_time', 0.0)
        if current_time - self._last_arrival_check_time < 0.5:
            return self._cached_arrival_result
        
        self._last_arrival_check_time = current_time
        
        # Check only arrival aircraft (much faster than checking all)
        for aircraft in aircraft_manager.aircraft:
            if aircraft == self:
                continue
            
            # Quick filter: only check arrivals
            if aircraft.flight_type != "arrival":
                continue
            
            # Check if arrival on same runway
            if aircraft.expected_runway == runway:
                # Check if on approach or landing
                if aircraft.state in [self.STATE_APPROACH, self.STATE_LANDING]:
                    # Check distance (1.5nm = ~2778 meters, simplified check using altitude)
                    # Below 750ft = within 1.5nm on final (assuming 3-degree glideslope)
                    if aircraft.altitude < 750:
                        self._cached_arrival_result = aircraft
                        logger.debug(f"[{self.get_callsign()}] Tower: Holding for arrival {aircraft.get_callsign()} within 1.5nm")
                        return aircraft
        
        self._cached_arrival_result = None
        return None
    
    def execute_lineup_clearance(self, runway):
        """Execute lineup clearance - follow taxiway until runway entry, then go direct to lineup
        
        Args:
            runway: Runway identifier (e.g., "02")
        """
        import math
        
        logger.info(f"[{self.get_callsign()}] ✈️ EXECUTING LINEUP CLEARANCE for runway {runway}")
        
        # Set clearance flags
        self.tower_cleared_to_lineup = True
        self.lineup_runway = runway  # Store which runway we're lining up on
        
        # Clear hold short restriction
        if runway and runway not in self.cleared_runways:
            self.cleared_runways.append(runway)
        self.hold_short = None
        
        # Get runway heading
        runway_heading = self._get_runway_heading(runway)
        if runway_heading is None:
            logger.error(f"[{self.get_callsign()}] Cannot get heading for runway {runway}")
            return
        
        # Store runway heading for later use
        self.lineup_runway_heading = runway_heading
        
        # Get lineup position from airport data
        lineup_position = None
        if self.airport_data:
            for rwy_def in self.airport_data.get('runway_definition', []):
                if rwy_def.get('name') == runway:
                    lineup_data = rwy_def.get('lineup', [])
                    if lineup_data and len(lineup_data) > 0:
                        lineup_position = (lineup_data[0]['x'], lineup_data[0]['y'])
                        logger.info(f"[{self.get_callsign()}] Found lineup position: {lineup_position}")
                        break
        
        if not lineup_position:
            logger.error(f"[{self.get_callsign()}] No lineup position defined for runway {runway}")
            return
        
        # Store lineup position for later use
        self.lineup_target_position = lineup_position
        
        # KEEP existing taxiway route - don't clear it!
        # Just add the lineup position at the end if we don't have a route
        if not self.route and not self.target_position:
            # No existing route, go direct
            self.target_position = lineup_position
            logger.info(f"[{self.get_callsign()}] No existing route - going direct to lineup")
        else:
            # Keep following current route/target
            # We'll switch to lineup position when we enter the runway polygon
            logger.info(f"[{self.get_callsign()}] Keeping existing route - will switch to lineup upon runway entry")
            logger.info(f"[{self.get_callsign()}]   Current target: {self.target_position}")
            logger.info(f"[{self.get_callsign()}]   Remaining waypoints: {len(self.route)}")
        
        # Set movement parameters
        self.target_speed = self.max_taxi_speed
        if self.speed < 1.0:
            self.speed = 5.0  # Start with immediate movement if stopped
        
        # Ensure we're in TAXI state
        self.state = self.STATE_TAXI
        
        lat, lon = self.position
        dist_to_lineup = math.sqrt((lineup_position[0] - lat)**2 + (lineup_position[1] - lon)**2) * 111000
        
        logger.info(f"[{self.get_callsign()}] 🎯 LINEUP CLEARANCE EXECUTED:")
        logger.info(f"[{self.get_callsign()}]   Current: ({lat:.6f}, {lon:.6f})")
        logger.info(f"[{self.get_callsign()}]   Lineup Target: {lineup_position}")
        logger.info(f"[{self.get_callsign()}]   Distance: {dist_to_lineup:.1f}m")
        logger.info(f"[{self.get_callsign()}]   Runway Heading: {runway_heading}°")
        logger.info(f"[{self.get_callsign()}]   Speed: {self.speed:.1f} kts -> {self.target_speed:.1f} kts")
        logger.info(f"[{self.get_callsign()}]   State: {self.state}")
    
    def _clear_for_takeoff(self):
        """Tower clears aircraft for takeoff"""
        self.tower_cleared_for_takeoff = True
        
        logger.info(f"[{self.get_callsign()}] Tower: Cleared for takeoff")
        
        # Tower frequency - don't send to ground radio
        # if self.radio_callback:
        #     self.radio_callback(f"{self.get_callsign()}, cleared for takeoff", is_atc=True)
        
        # Short delay then initiate takeoff
        def initiate():
            self._initiate_takeoff()
        
        self._schedule_action(initiate, delay=random.uniform(2, 4))
    
    def _initiate_takeoff(self):
        """Begin takeoff roll"""
        logger.info(f"[{self.get_callsign()}] 🚀 INITIATING TAKEOFF from state: {self.state}")
        logger.info(f"[{self.get_callsign()}]   Current speed: {self.speed:.1f} kts")
        logger.info(f"[{self.get_callsign()}]   Current heading: {self.heading:.1f}°")
        logger.info(f"[{self.get_callsign()}]   Current position: {self.position}")
        
        # Transition to takeoff state
        self.state = self.STATE_TAKEOFF
        
        # Use aircraft-specific performance for takeoff
        # Rotation speed is typically 1.1-1.2x stall speed, use cruise_speed_kt as reference
        cruise_speed = self.performance.get('cruise_speed_kt', 450)
        # Approximate rotation speed: smaller aircraft ~60% cruise, larger ~35% cruise
        rotation_factor = 0.35 if cruise_speed > 400 else 0.50
        self.target_speed = cruise_speed * rotation_factor  # Rotation/liftoff speed
        
        # Initial climb altitude from performance data
        self.target_altitude = self.performance.get('service_ceiling_ft', 41000) * 0.075  # ~7.5% of service ceiling
        if self.target_altitude < 3000:
            self.target_altitude = 3000  # Minimum 3000 ft
        
        # Give aircraft some initial speed to start the roll
        if self.speed < 5.0:
            self.speed = 10.0  # Start with some initial speed
            logger.info(f"[{self.get_callsign()}] Setting initial takeoff speed: {self.speed:.1f} kts")
        
        logger.info(f"[{self.get_callsign()}] Takeoff performance: V_r={self.target_speed:.0f} kts, "
                   f"initial climb to {self.target_altitude:.0f} ft")
        
        # Clear all runway clearances - aircraft is now departing
        self.cleared_runways = []
        self.hold_short = None
        self.holding_short_runway = None
        logger.info(f"[{self.get_callsign()}] Cleared runway clearances for takeoff")
        
        # Transmit departure message - Tower frequency, don't send to ground radio
        # if self.radio_callback:
        #     departure_msg = f"{self.get_callsign()}, rolling"
        #     self.radio_callback(departure_msg, is_atc=False)
        
        logger.info(f"[{self.get_callsign()}] Beginning takeoff roll")
    
    def get_callsign(self) -> str:
        """Get full callsign (or editor override if set)"""
        override = getattr(self, 'callsign_override', None)
        if override:
            return override
        return f"{self.airline}{self.flight_number}"

    def get_spoken_callsign(self) -> str:
        """Format callsign for natural TTS speech.

        ATC reads 4-digit flight numbers as two pairs and 3-digit as
        single + pair, so Kokoro TTS produces the right cadence:
          EDV3089  →  "EDV 30 89"   → "E-D-V thirty eighty nine"
          ENY895   →  "ENY 8 95"    → "E-N-Y eight ninety five"
          AAL50    →  "AAL 50"      → "A-A-L fifty"
        """
        cs = self.get_callsign()
        m = re.match(r'^([A-Z]+)(\d+)$', cs)
        if not m:
            return cs
        letters, digits = m.group(1), m.group(2)
        pairs: list[str] = []
        d = digits
        while len(d) > 2:
            if len(d) % 2 == 1:      # odd length: take 1 then pairs
                pairs.append(d[0])
                d = d[1:]
            else:
                pairs.append(d[:2])
                d = d[2:]
        if d:
            pairs.append(d)
        return f"{letters} {' '.join(pairs)}"
    
    def get_display_info(self) -> Dict:
        """Get info for display"""
        return {
            'callsign': self.get_callsign(),
            'flight_number': self.flight_number,
            'type': self.aircraft_type,
            'airline': self.airline,
            'state': self.state,
            'speed': round(self.speed, 1),
            'heading': round(self.heading),
            'gate': self.gate
        }

    def get_thinking(self) -> str:
        """Return a human-readable string of what this aircraft is currently doing/thinking"""
        state = self.state
        callsign = self.get_callsign()

        if state == self.STATE_PARKED:
            if not self.cleared_to_pushback and not self.pushback_requested:
                return f"Parked at gate {self.gate or '?'}, waiting to request pushback"
            elif self.pushback_requested and not self.cleared_to_pushback:
                return f"Requested pushback from gate {self.gate or '?'}, awaiting clearance"
            else:
                return f"Parked at gate {self.gate or '?'}"

        elif state == self.STATE_PUSHBACK:
            return f"Pushing back from gate {self.gate or '?'}"

        elif state == self.STATE_HOLDING:
            if self.holding_short_runway:
                return f"Holding short of runway {self.holding_short_runway}"
            elif not self.cleared_to_taxi and not self.taxi_requested:
                if self.flight_type == "arrival":
                    return f"Clear of runway, waiting to request taxi to gate {self.gate or '?'}"
                else:
                    return f"Ready to taxi, preparing taxi request"
            elif self.taxi_requested and not self.cleared_to_taxi:
                dest = self.taxi_destination or (f"runway {self.expected_runway}" if self.expected_runway else "runway")
                return f"Requested taxi to {dest}, awaiting clearance"
            else:
                return "Holding, awaiting instructions"

        elif state == self.STATE_TAXI:
            dest = self.taxi_destination or "destination"
            via = self.taxi_via
            via_str = f" via {', '.join(via)}" if via else ""
            if self.target_position:
                remaining = len(self.route) if self.route else 0
                return f"Taxiing to {dest}{via_str} ({remaining} waypoints remaining)"
            return f"Taxiing to {dest}{via_str}"

        elif state == self.STATE_TAKEOFF:
            rwy = self.expected_runway or "?"
            return f"Taking off on runway {rwy}, speed {self.speed:.0f} kts"

        elif state == self.STATE_APPROACH:
            rwy = self.expected_runway or "?"
            alt = int(self.altitude) if hasattr(self, 'altitude') else 0
            return f"On final approach to runway {rwy}, {alt} ft, {self.speed:.0f} kts"

        elif state == self.STATE_LANDING:
            rwy = self.expected_runway or "?"
            phase = getattr(self, 'landing_phase', 'rollout')
            exit_info = ""
            if hasattr(self, '_target_exit') and self._target_exit:
                tw, _, exit_fwd_m = self._target_exit
                dist = getattr(self, 'landing_distance_traveled', 0)
                remaining_m = exit_fwd_m - dist
                exit_info = f", exit {tw} in {max(0, remaining_m):.0f}m"
            return f"Landing rollout on runway {rwy}{exit_info}, {self.speed:.0f} kts"

        elif state == self.STATE_DEPARTED:
            return f"Departed, handed off to departure"

        return f"State: {state}"
    
    def _auto_request_taxi(self):
        """Automatically request taxi - aircraft expects the active runway or assigned runway
        
        Aircraft will use:
        1. Expected runway assigned by ATC (via "expect runway" command)
        2. Active runway from weather panel
        3. Random runway as fallback
        """
        # Cannot call if not squawking Mode C with correct code
        if not self._can_make_radio_call():
            logger.info(f"[{self.get_callsign()}] Cannot request taxi - not squawking Mode C with correct code")
            return
        
        logger.info(f"[{self.get_callsign()}] Executing _auto_request_taxi")
        
        if not self.airport_data:
            logger.info(f"[{self.get_callsign()}] _auto_request_taxi: No airport data available")
            return
        
        # Determine which runway to expect (stored internally, not mentioned in radio call)
        runway_name = None
        
        # Priority 1: Use runway assigned by ATC
        if self.expected_runway:
            runway_name = self.expected_runway
            logger.info(f"[{self.get_callsign()}] Expecting runway {runway_name} (assigned by ATC)")
        else:
            # Priority 2: Use active runway from weather panel (would need to be passed from manager)
            # Priority 3: Fallback to random runway
            runways = self.airport_data.get('runways', [])
            if runways:
                runway = random.choice(runways)
                runway_name = runway.get('name', '').split('/')[0]
                logger.info(f"[{self.get_callsign()}] Expecting runway {runway_name} (no ATC assignment)")
        
        # Store expected destination internally (not mentioned in radio call)
        if runway_name:
            self.taxi_destination = f"runway {runway_name}"
        
        # Request taxi without mentioning runway
        self.request_taxi()
        # Don't auto-approve - ATC must manually approve with taxi command
    
    def _calculate_carrot_point(self, current_lat: float, current_lon: float, look_ahead_distance: float) -> Tuple[float, float]:
        """Calculate a 'carrot' point ahead on the path for predictive steering
        
        This point is look_ahead_distance away along the path, allowing the aircraft
        to anticipate turns and follow smooth curves instead of sharp waypoint turns.
        """
        if not self.target_position:
            return (current_lat, current_lon)
        
        # Build a list of points: current position, target, and route waypoints
        path_points = [(current_lat, current_lon), self.target_position]
        if self.route:
            path_points.extend(self.route[:3])  # Look up to 3 waypoints ahead
        
        # Walk along the path until we've traveled look_ahead_distance
        accumulated_distance = 0.0
        for i in range(len(path_points) - 1):
            p1_lat, p1_lon = path_points[i]
            p2_lat, p2_lon = path_points[i + 1]
            
            # Calculate segment length
            dlat = p2_lat - p1_lat
            dlon = p2_lon - p1_lon
            segment_length = math.sqrt(dlat**2 + dlon**2)
            
            if accumulated_distance + segment_length >= look_ahead_distance:
                # Carrot point is on this segment
                remaining = look_ahead_distance - accumulated_distance
                ratio = remaining / segment_length if segment_length > 0 else 0
                
                carrot_lat = p1_lat + dlat * ratio
                carrot_lon = p1_lon + dlon * ratio
                return (carrot_lat, carrot_lon)
            
            accumulated_distance += segment_length
        
        # If we ran out of path, return the last point
        return path_points[-1]
    
    def _calculate_path_curvature(self, current_lat: float, current_lon: float) -> float:
        """Calculate the curvature of the path ahead (0 = straight, 1 = sharp curve)
        
        This helps the aircraft anticipate how aggressively it needs to steer.
        """
        if not self.target_position or not self.route or len(self.route) < 1:
            return 0.0  # No curvature if no path ahead
        
        # Get three points: current position, next waypoint, and waypoint after that
        p1_lat, p1_lon = current_lat, current_lon
        p2_lat, p2_lon = self.target_position
        p3_lat, p3_lon = self.route[0]
        
        # Calculate the angle change between the two segments
        # Segment 1: current -> target
        angle1 = math.atan2(p2_lon - p1_lon, p2_lat - p1_lat)
        # Segment 2: target -> next waypoint
        angle2 = math.atan2(p3_lon - p2_lon, p3_lat - p2_lat)
        
        # Calculate angle difference (how much the path curves)
        angle_diff = abs(self._angle_difference(math.degrees(angle1), math.degrees(angle2)))
        
        # Normalize to 0-1 range (0° = 0, 90°+ = 1)
        curvature = min(1.0, angle_diff / 90.0)
        
        return curvature
    
    def is_in_ga_apron(self) -> bool:
        """
        Check if aircraft is currently within the GA apron polygon
        
        Returns:
            True if aircraft is in GA apron, False otherwise
        """
        if not self.airport_data or not self.is_general_aviation:
            return False
        
        ga_apron_raw = self.airport_data.get('ga_apron', [])
        if not ga_apron_raw or len(ga_apron_raw) < 3:
            return False
        
        # Convert ga_apron to tuple format (lat, lon) if needed
        ga_apron = []
        for point in ga_apron_raw:
            if isinstance(point, dict) and 'x' in point and 'y' in point:
                ga_apron.append((float(point['x']), float(point['y'])))
            elif isinstance(point, (list, tuple)) and len(point) >= 2:
                ga_apron.append((float(point[0]), float(point[1])))
        
        if len(ga_apron) < 3:
            return False
        
        return point_in_polygon(self.position, ga_apron)
    
    def can_move_without_atc(self) -> bool:
        """
        Check if aircraft can move without ATC clearance
        GA aircraft in GA apron can move freely
        
        Returns:
            True if aircraft can move autonomously, False otherwise
        """
        return self.is_general_aviation and self.is_in_ga_apron()
    
    def constrain_to_ga_apron(self) -> bool:
        """
        Check if aircraft is leaving GA apron and constrain it to boundaries
        
        Returns:
            True if aircraft was constrained, False if no action needed
        """
        if not self.is_general_aviation or not self.airport_data:
            return False
        
        ga_apron_raw = self.airport_data.get('ga_apron', [])
        if not ga_apron_raw or len(ga_apron_raw) < 3:
            return False
        
        # Convert ga_apron to tuple format (lat, lon) if needed
        ga_apron = []
        for point in ga_apron_raw:
            if isinstance(point, dict) and 'x' in point and 'y' in point:
                ga_apron.append((float(point['x']), float(point['y'])))
            elif isinstance(point, (list, tuple)) and len(point) >= 2:
                ga_apron.append((float(point[0]), float(point[1])))
        
        if len(ga_apron) < 3:
            return False
        
        # Check if aircraft is outside or very close to edge
        if not point_in_polygon(self.position, ga_apron):
            # Aircraft is outside - move it back to nearest point on boundary
            closest_point = closest_point_on_polygon(self.position, ga_apron)
            logger.warning(f"[{self.get_callsign()}] GA aircraft outside apron, constraining to boundary")
            self.position = closest_point
            self.visual_position = list(closest_point)
            
            # Stop the aircraft
            self.speed = 0
            self.target_speed = 0
            
            return True
        
        # Check if getting too close to edge (within 10 meters)
        edge_distance = distance_to_polygon_edge(self.position, ga_apron)
        # Convert 10 meters to degrees (approximately 0.00009 degrees)
        warning_threshold = 0.00009
        
        if edge_distance < warning_threshold:
            # Slow down near boundary
            self.target_speed = min(self.target_speed, self.max_taxi_speed * 0.3)
            logger.debug(f"[{self.get_callsign()}] GA aircraft near apron edge, reducing speed")
        
        return False
    
    def get_ga_apron_random_destination(self) -> Optional[Tuple[float, float]]:
        """
        Get a random destination within the GA apron for autonomous movement
        
        Returns:
            (lat, lon) tuple of random destination, or None if not applicable
        """
        if not self.is_general_aviation or not self.airport_data:
            return None
        
        ga_apron_raw = self.airport_data.get('ga_apron', [])
        if not ga_apron_raw or len(ga_apron_raw) < 3:
            return None
        
        # Convert ga_apron to tuple format (lat, lon) if needed
        ga_apron = []
        for point in ga_apron_raw:
            if isinstance(point, dict) and 'x' in point and 'y' in point:
                ga_apron.append((float(point['x']), float(point['y'])))
            elif isinstance(point, (list, tuple)) and len(point) >= 2:
                ga_apron.append((float(point[0]), float(point[1])))
        
        if len(ga_apron) < 3:
            return None
        
        # Calculate centroid of polygon
        lat_sum = sum(p[0] for p in ga_apron)
        lon_sum = sum(p[1] for p in ga_apron)
        centroid = (lat_sum / len(ga_apron), lon_sum / len(ga_apron))
        
        # Pick a random point within the polygon (simplified - pick random vertex or near centroid)
        if random.random() < 0.5:
            # Pick random vertex
            return random.choice(ga_apron)
        else:
            # Pick point near centroid with some randomness
            offset_lat = random.uniform(-0.0001, 0.0001)
            offset_lon = random.uniform(-0.0001, 0.0001)
            candidate = (centroid[0] + offset_lat, centroid[1] + offset_lon)
            
            # Verify it's inside the polygon
            if point_in_polygon(candidate, ga_apron):
                return candidate
            else:
                return centroid
    
    def __repr__(self):
        return f"<Aircraft {self.get_callsign()} {self.aircraft_type} @ {self.state}>"
    
    def _find_and_assign_gate(self):
        """Find and assign an available gate for the aircraft"""
        if not self.airport_data or not hasattr(self, 'aircraft_manager'):
            return
        
        gates = self.airport_data.get('gates', [])
        if not gates:
            return
        
        # Get list of occupied gates from other aircraft
        occupied_gates = set()
        if hasattr(self.aircraft_manager, 'get_all_aircraft'):
            for aircraft in self.aircraft_manager.get_all_aircraft():
                if hasattr(aircraft, 'gate') and aircraft.gate and aircraft != self:
                    occupied_gates.add(aircraft.gate)
        
        # Find available gate (prefer commercial gates for commercial aircraft)
        available_gates = []
        for gate in gates:
            gate_name = gate.get('name', '')
            gate_type = gate.get('type', 'commercial')
            
            # Skip occupied gates
            if gate_name in occupied_gates:
                continue
            
            # Prefer commercial gates for commercial aircraft, cargo for cargo, etc.
            if self.aircraft_type.startswith(('C', 'D', 'E', 'F')):  # Commercial aircraft
                if gate_type == 'commercial':
                    available_gates.append((gate_name, gate))
            elif 'cargo' in self.aircraft_type.lower() or 'freight' in self.aircraft_type.lower():
                if gate_type == 'cargo':
                    available_gates.append((gate_name, gate))
            else:  # General aviation
                if gate_type == 'ga' or gate_type == 'general_aviation':
                    available_gates.append((gate_name, gate))
        
        # If no preferred gates available, use any available gate
        if not available_gates:
            for gate in gates:
                gate_name = gate.get('name', '')
                if gate_name not in occupied_gates:
                    available_gates.append((gate_name, gate))
        
        if available_gates:
            # Choose the closest available gate
            lat, lon = self.position
            best_gate = None
            best_distance = float('inf')
            
            for gate_name, gate_data in available_gates:
                gate_lat = gate_data.get('lat')
                gate_lon = gate_data.get('lon')
                if gate_lat and gate_lon:
                    distance = math.sqrt((gate_lat - lat)**2 + (gate_lon - lon)**2)
                    if distance < best_distance:
                        best_distance = distance
                        best_gate = gate_name
            
            if best_gate:
                self.gate = best_gate
                logger.info(f"[{self.get_callsign()}] Assigned to gate {best_gate}")
    
    def _initiate_taxi_to_gate(self):
        """Initiate taxi to assigned gate; redundant: graph path-to-gate -> path-to-ramp -> direct."""
        if not self.gate:
            return
        path = None
        gate_surface = f"Gate {self.gate}"
        current_surface = self.current_surface or (f"Taxiway {self.landing_target_taxiway}" if hasattr(self, 'landing_target_taxiway') else None)
        
        try:
            if self.airport_graph:
                path = self.airport_graph.find_path(self.position, gate_surface, [current_surface] if current_surface else [])
                if path:
                    logger.info(f"[{self.get_callsign()}] Graph path to gate with {len(path)} waypoints")
                if not path:
                    gate_data = next((g for g in (self.airport_data.get('gates') or []) if g.get('name') == self.gate), None)
                    connects_to = (gate_data or {}).get('connects_to', '')
                    path = self.airport_graph.find_path_to_ramp(self.position, connects_to)
                    if path:
                        logger.info(f"[{self.get_callsign()}] Graph path to ramp with {len(path)} waypoints")
            if path:
                path = self._optimize_taxi_route(path)
                gate_pos = next((g.get('position') for g in (self.airport_data.get('gates') or []) if g.get('name') == self.gate), None)
                if gate_pos and path and (path[-1] != (gate_pos.get('x'), gate_pos.get('y'))):
                    path.append((gate_pos['x'], gate_pos['y']))
                self.taxi_path = path
                self.taxi_path_index = 0
                self.taxi_requested = True
                self.cleared_to_taxi = True
                logger.info(f"[{self.get_callsign()}] Taxiing to gate {self.gate} via {len(path)} waypoints")
            else:
                gate_pos = next((g.get('position') for g in (self.airport_data.get('gates') or []) if g.get('name') == self.gate), None)
                if gate_pos and gate_pos.get('x') is not None and gate_pos.get('y') is not None:
                    self.taxi_path = [(gate_pos['x'], gate_pos['y'])]
                    self.taxi_path_index = 0
                    self.taxi_requested = True
                    self.cleared_to_taxi = True
                    logger.warning(f"[{self.get_callsign()}] Using direct-to-gate fallback")
                else:
                    logger.warning(f"[{self.get_callsign()}] No path found to gate {self.gate}")
        except Exception as e:
            logger.error(f"[{self.get_callsign()}] Error initiating taxi to gate: {e}")
    
    def _check_if_past_holdshort(self) -> bool:
        """Check if aircraft has passed the hold short line"""
        # This is a simplified check - in reality would check actual hold short markings
        # For now, use distance traveled from touchdown
        return self.landing_distance_traveled > 1200.0
    
    def contact_ground_clearance_received(self):
        """Handle clearance from tower to contact ground control"""
        logger.info(f"[{self.get_callsign()}] Tower clearance received, contacting ground")
        
        # Find and assign gate if not already assigned
        if not self.gate:
            self._find_and_assign_gate()
        
        # Initiate taxi to gate if we have one
        if self.gate:
            self._initiate_taxi_to_gate()
            # Transition to taxi state
            self.state = self.STATE_TAXI
            self.speed = 15.0  # Start taxi speed
            logger.info(f"[{self.get_callsign()}] Taxiing to gate {self.gate}")
        else:
            logger.warning(f"[{self.get_callsign()}] No gate available, remaining in holding pattern")
        
        # Remove from tower controller's holding short list
        if hasattr(self, 'tower_controller') and self.tower_controller:
            if self in self.tower_controller.holding_short_aircraft:
                self.tower_controller.holding_short_aircraft.remove(self)


class AircraftManager:
    """Manages all aircraft in the simulation"""
    
    def __init__(self, airport_data: Dict, radio_callback=None, weather_panel=None):
        self.airport_data = airport_data
        self.aircraft: List[Aircraft] = []
        self.used_callsigns = set()  # Track used callsigns to avoid duplicates
        self.used_beacons = set()  # Track used beacon codes to avoid duplicates (stored as strings)
        self.used_cids = set()  # Track used controller IDs to avoid duplicates
        self.radio_callback = radio_callback  # Callback for radio transmissions
        self.simulation_time = 0.0  # Track total simulation time
        
        # Initialize airport navigation graph
        try:
            self.airport_graph = AirportGraph(airport_data)
            logger.info(f"Airport navigation graph initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize airport graph: {e}")
            self.airport_graph = None
        
        # Initialize virtual tower controller with weather panel for runway sync
        airport_code = airport_data.get('airport', {}).get('icao', 'UNKNOWN')
        self.tower_controller = VirtualTowerController(airport_code, radio_callback, weather_panel)
        logger.info(f"Virtual Tower Controller initialized for {airport_code}")
        
        # Store reference to weather panel for future updates
        self.weather_panel = weather_panel
        
        # ATC Action states (set by simulation from top menu bar)
        self.ground_stop_active = False
        self.gate_hold_active = False
        self.gdp_active = False
        self.gdp_delay_minutes = 0
        self.emergency_stop_active = False
        self.closed_runways = set()
        self.closed_taxiways = set()
        
        # Spawn rate configuration (aircraft per hour)
        self.dep_spawn_rate = airport_data.get('dep_spawn_rate', 10)  # Departures per hour
        self.arr_spawn_rate = airport_data.get('arr_spawn_rate', 10)  # Arrivals per hour
        
        # Convert hourly rates to seconds between spawns (used for fallback / initial spread)
        self.dep_spawn_interval = 3600.0 / self.dep_spawn_rate if self.dep_spawn_rate > 0 else float('inf')
        self.arr_spawn_interval = 3600.0 / self.arr_spawn_rate if self.arr_spawn_rate > 0 else float('inf')
        
        # Per-hour spawn schedules: N spawn times in [0, 3600) with peaks/lulls throughout the hour
        self.dep_spawn_schedule: List[float] = []
        self.arr_spawn_schedule: List[float] = []
        self.dep_spawn_schedule_index = 0
        self.arr_spawn_schedule_index = 0
        self._spawn_schedule_hour = -1  # hour we built schedules for; -1 = not built
        
        logger.info(f"Spawn rates configured: {self.dep_spawn_rate} departures/hour, "
                   f"{self.arr_spawn_rate} arrivals/hour (even per-hour schedule, spawn 1 min before call)")
    
    def _build_spawn_schedule(self, rate: int) -> List[float]:
        """Build a per-hour spawn schedule: `rate` call times in [0, 3600), evenly spaced."""
        if rate <= 0:
            return []
        times: List[float] = []
        interval = 3600.0 / rate
        for i in range(rate):
            # Centre of each bucket; small jitter (±5% of interval)
            t = (i + 0.5) * interval + random.uniform(-0.05, 0.05) * interval
            t = max(0.0, min(3599.0, t))
            times.append(t)
        times.sort()
        return times
    
    def _ensure_spawn_schedules_for_hour(self, hour: int) -> None:
        """Build or reuse dep/arr spawn schedules for the given simulation hour."""
        if hour == self._spawn_schedule_hour:
            return
        self._spawn_schedule_hour = hour
        self.dep_spawn_schedule = self._build_spawn_schedule(self.dep_spawn_rate)
        self.arr_spawn_schedule = self._build_spawn_schedule(self.arr_spawn_rate)
        self.dep_spawn_schedule_index = 0
        self.arr_spawn_schedule_index = 0
    
    def spawn_aircraft_at_gate(self, gate_data: Dict) -> Optional[Aircraft]:
        """Spawn an aircraft at a specific gate"""
        gate_name = gate_data.get('name')
        position = gate_data.get('position')
        heading = gate_data.get('degrees', 0)
        airline = gate_data.get('airline', 'Private')
        
        if not position:
            return None
        
        # Get aircraft type for this airline
        aircraft_type = self._get_aircraft_for_airline(airline)
        
        # Generate random flight number (callsign)
        flight_number = self._generate_random_callsign(airline)
        
        # Select departure route for this aircraft
        departure_route = self._select_departure_route(airline)
        
        # Generate unique beacon code and CID
        beacon_code = self._generate_unique_beacon()
        cid = self._generate_unique_cid()
        
        # Create aircraft
        aircraft = Aircraft(
            flight_number=flight_number,
            aircraft_type=aircraft_type,
            airline=airline,
            position=(position['x'], position['y']),
            heading=heading,
            gate=gate_name,
            airport_data=self.airport_data,
            radio_callback=self.radio_callback,
            departure_route=departure_route,
            flight_type="departure",  # Aircraft at gates are departures
            tts_voice=self.assign_tts_voice(flight_number),
            aircraft_manager=self
        )
        
        # Assign beacon code and CID to aircraft
        aircraft.beacon = beacon_code
        aircraft.cid = cid
        
        # Set Mode C squawk system
        aircraft.correct_squawk_code = beacon_code  # The correct code they should enter (as string)
        aircraft.current_squawk_code = None  # Start with no code (unknown status)
        aircraft.squawking_mode_c = False  # Start not squawking Mode C
        
        # Set airport graph for location awareness
        if self.airport_graph:
            aircraft.set_airport_graph(self.airport_graph)
        
        self.aircraft.append(aircraft)
        logger.info(f"[{aircraft.get_callsign()}] Assigned beacon code: {beacon_code}, CID: {cid}")
        return aircraft
    
    def assign_tts_voice(self, callsign: str) -> str:
        """Assign a consistent TTS voice based on a callsign.
        
        Args:
            callsign: The callsign to assign a voice to
            
        Returns:
            str: The name of the voice to use for this callsign
        """
        # Get the list of available voices
        available_voices = [
            "af_heart", "af_alloy", "af_aoede", "af_bella", "af_jessica",
            "af_kore", "af_river", "af_sarah", "am_eric", "am_fenrir",
            "am_liam", "am_michael", "am_onyx", "am_puck"
        ]
        
        # Return default voice if no callsign provided
        if not callsign:
            return "af_heart"
            
        # Generate a consistent index based on the callsign
        voice_index = hash(callsign) % len(available_voices)
        return available_voices[voice_index]
    
    def _generate_unique_beacon(self) -> str:
        """Generate a unique 4-digit beacon code (squawk code) - octal format (0-7 per digit)
        
        Returns:
            str: A unique beacon code as 4-digit string with digits 0-7 (excluding emergency codes)
        """
        max_attempts = 1000
        emergency_codes = ["7700", "7600", "7500"]  # Emergency codes as strings
        
        for _ in range(max_attempts):
            # Generate 4-digit code with each digit 0-7 (octal)
            beacon = ""
            for _ in range(4):
                beacon += str(random.randint(0, 7))
            
            # Don't use emergency codes: 7700 (emergency), 7600 (radio failure), 7500 (hijack)
            if beacon not in self.used_beacons and beacon not in emergency_codes:
                self.used_beacons.add(beacon)
                return beacon
        
        # Fallback: if we somehow run out of codes, reuse (shouldn't happen)
        logger.warning("Warning: Running low on available beacon codes, reusing codes")
        beacon = ""
        for _ in range(4):
            beacon += str(random.randint(0, 7))
        while beacon in emergency_codes:
            beacon = ""
            for _ in range(4):
                beacon += str(random.randint(0, 7))
        return beacon
    
    def _generate_unique_cid(self) -> int:
        """Generate a unique 3-digit controller ID
        
        Returns:
            int: A unique controller ID between 100-999
        """
        max_attempts = 1000
        for _ in range(max_attempts):
            cid = random.randint(100, 999)
            if cid not in self.used_cids:
                self.used_cids.add(cid)
                return cid
        
        # Fallback: if we somehow run out of codes, reuse (shouldn't happen)
        logger.warning("Warning: Running low on available CIDs, reusing codes")
        return random.randint(100, 999)
    
    def _get_aircraft_for_airline(self, airline: str) -> str:
        """Get a random aircraft type for an airline"""
        # Get aircraft types from airport data
        aircraft_list = self.airport_data.get('aircraft', [])
        
        for entry in aircraft_list:
            if isinstance(entry, dict) and airline in entry:
                types = entry[airline]
                return random.choice(types)
        
        # Default to small aircraft
        return 'C172'
    
    def _generate_random_callsign(self, airline: str) -> str:
        """Generate a random callsign based on airline type
        
        Airlines (AAY, ENY, EDV, SKW, etc.): numbers only (1-4 digits)
        General Aviation (N): numbers + letters (1-3 numbers + 1-2 letters)
        """
        is_general_aviation = airline == 'N'
        
        # Keep trying until we get a unique callsign
        max_attempts = 1000
        for _ in range(max_attempts):
            if is_general_aviation:
                # GA: 1-3 numbers followed by 1-2 letters (e.g., N123AB, N45X)
                num_digits = random.randint(1, 3)
                numbers = ''.join(random.choices(string.digits, k=num_digits))
                
                num_letters = random.randint(1, 2)
                letters = ''.join(random.choices(string.ascii_uppercase, k=num_letters))
                
                callsign = numbers + letters
            else:
                # Airlines: 1-4 digit flight numbers (e.g., 123, 4567)
                num_digits = random.randint(2, 4)
                callsign = ''.join(random.choices(string.digits, k=num_digits))
            
            # Check if this callsign is already used
            if callsign not in self.used_callsigns:
                self.used_callsigns.add(callsign)
                return callsign
        
        # Fallback if we somehow can't generate a unique callsign
        if is_general_aviation:
            fallback = f"{random.randint(1, 999)}{random.choice(string.ascii_uppercase)}"
        else:
            fallback = str(random.randint(1, 9999))
        self.used_callsigns.add(fallback)
        return fallback
    
    def _select_departure_route(self, airline: str) -> Optional[Dict]:
        """Select a random departure route for the given airline"""
        departures = self.airport_data.get('departures', [])
        
        if not departures:
            return None
        
        # Filter routes that include this airline
        valid_routes = []
        for route in departures:
            airlines_list = route.get('airlines', [])
            for airline_entry in airlines_list:
                if airline_entry.get('icao') == airline:
                    valid_routes.append(route)
                    break
        
        # If no specific routes for this airline, pick any route
        if not valid_routes:
            valid_routes = departures
        
        # Select random route
        if valid_routes:
            return random.choice(valid_routes)
        
        return None
    
    def spawn_initial_aircraft(self, count: int = 0):
        """Ensure hour-0 spawn schedule; no initial aircraft (all departures from schedule, 1 min before call)."""
        self._ensure_spawn_schedules_for_hour(0)
        self.dep_spawn_schedule_index = 0
    
    def restore_aircraft_from_save(self, aircraft_list: List[Dict], radio_callback=None) -> None:
        """Restore aircraft from a saved simulation. Clears current aircraft and recreates from save list."""
        self.aircraft.clear()
        self.used_beacons.clear()
        self.used_cids.clear()
        self.used_callsigns.clear()
        for info in aircraft_list:
            try:
                flight_number = str(info.get('flight_number', '') or '')
                airline = str(info.get('airline', '') or '')
                callsign = info.get('callsign', '')
                if not flight_number and callsign:
                    if callsign[:1].isalpha() and callsign[1:].isdigit():
                        airline, flight_number = callsign[:3] if len(callsign) > 3 else callsign[:1], callsign[3:] or callsign[1:]
                    else:
                        airline, flight_number = callsign[:2], callsign[2:] or '0'
                aircraft_type = str(info.get('aircraft_type', 'UNKNOWN'))
                pos = info.get('position')
                if not pos or len(pos) < 2:
                    continue
                position = (float(pos[0]), float(pos[1]))
                heading = float(info.get('heading', 0))
                gate = info.get('gate')
                beacon_val = info.get('beacon') or info.get('beacon_code')
                beacon_str = str(beacon_val).zfill(4) if beacon_val is not None else self._generate_unique_beacon()
                cid = info.get('cid')
                if cid is None:
                    cid = self._generate_unique_cid()
                else:
                    cid = int(cid)
                    self.used_cids.add(cid)
                self.used_beacons.add(beacon_str)
                if callsign:
                    self.used_callsigns.add(callsign)
                aircraft = Aircraft(
                    flight_number=flight_number or '0',
                    aircraft_type=aircraft_type,
                    airline=airline or 'N',
                    position=position,
                    heading=heading,
                    gate=gate,
                    airport_data=self.airport_data,
                    radio_callback=radio_callback or self.radio_callback,
                    departure_route=None,
                    flight_type="departure",
                    tts_voice=self.assign_tts_voice(callsign or f"{airline}{flight_number}"),
                    aircraft_manager=self
                )
                aircraft.state = info.get('state', aircraft.STATE_PARKED)
                aircraft.speed = float(info.get('speed', 0))
                aircraft.beacon = beacon_str
                aircraft.cid = cid
                aircraft.destination = info.get('destination')
                aircraft.route = list(info.get('route') or [])
                aircraft.expected_runway = info.get('expected_runway')
                aircraft.show_datatag = bool(info.get('show_datatag', True))
                aircraft.tag_direction = int(info.get('tag_direction', 8))
                aircraft.pushback_requested = bool(info.get('pushback_requested', False))
                aircraft.taxi_requested = bool(info.get('taxi_requested', False))
                aircraft.cleared_to_pushback = bool(info.get('cleared_to_pushback', False))
                aircraft.cleared_to_taxi = bool(info.get('cleared_to_taxi', False))
                if callsign:
                    aircraft.callsign_override = callsign
                if beacon_str:
                    aircraft.correct_squawk_code = beacon_str
                    aircraft.current_squawk_code = beacon_str
                    aircraft.squawking_mode_c = True
                if self.airport_graph:
                    aircraft.set_airport_graph(self.airport_graph)
                self.aircraft.append(aircraft)
            except Exception as e:
                logger.warning(f"Failed to restore aircraft from save: {e}")
                continue
        logger.info(f"Restored {len(self.aircraft)} aircraft from save")
    
    def _spawn_departure(self, scheduled_pushback_at: Optional[float] = None):
        """Spawn a departure at an available gate. Calls for pushback at scheduled time (~1 min after spawn)."""
        gates = self.airport_data.get('gates', [])
        
        occupied_gates = {aircraft.gate for aircraft in self.aircraft if aircraft.gate}
        available_gates = [g for g in gates if 'name' in g and 'position' in g and g['name'] not in occupied_gates]
        
        if not available_gates:
            logger.debug("No available gates for departure spawn")
            return
        
        gate = random.choice(available_gates)
        aircraft = self.spawn_aircraft_at_gate(gate)
        
        if aircraft:
            if scheduled_pushback_at is not None:
                aircraft.scheduled_pushback_time = scheduled_pushback_at
            else:
                aircraft.scheduled_pushback_time = self.simulation_time + 60.0 + random.uniform(0.0, 10.0)
            
            logger.info(f"Auto-spawned departure: {aircraft.get_callsign()} ({aircraft.aircraft_type}) at {gate['name']}")
            logger.info(f"[{aircraft.get_callsign()}] Scheduled pushback at t+{aircraft.scheduled_pushback_time:.1f}s")
            print(f"🛫 Departure: {aircraft.get_callsign()} ({aircraft.aircraft_type}) at {gate['name']}")
    
    def _spawn_arrival(self):
        """Spawn an arrival aircraft on final approach using arrival_procedures from airport data."""
        asde = self.airport_data.get('asde_config', {})
        # Prefer arrival_runways so arrivals only use runways designated for arrivals
        active_runways = asde.get('arrival_runways') or asde.get('active_runways', [])
        if not active_runways:
            logger.warning("No active runways configured for arrivals")
            return

        # Build a lookup of arrival_procedures keyed by runway name
        procedures = self.airport_data.get('arrival_procedures', [])
        proc_by_runway = {p['runway']: p for p in procedures if isinstance(p, dict) and 'runway' in p}

        # Filter to only runways that have a procedure defined; fall back to any active runway
        eligible = [r for r in active_runways if r in proc_by_runway]
        if not eligible:
            eligible = active_runways  # will use fallback geometry below

        arrival_runway = random.choice(eligible)

        # Find runway_definition for this runway (touchdown point + fallback geometry)
        runway_definitions = self.airport_data.get('runway_definition', [])
        threshold_data = next((r for r in runway_definitions if r.get('name') == arrival_runway), None)
        if not threshold_data:
            logger.warning(f"Could not find runway_definition for {arrival_runway}")
            return

        # Resolve touchdown point
        td = threshold_data.get('touchdown_point')
        if td:
            touchdown_lat, touchdown_lon = float(td['x']), float(td['y'])
        else:
            loc = threshold_data.get('location', [])
            if not loc:
                logger.warning(f"No location in runway_definition for {arrival_runway}")
                return
            touchdown_lat, touchdown_lon = float(loc[0]['x']), float(loc[0]['y'])
            logger.info(f"No touchdown_point for runway {arrival_runway}, using threshold")

        # Resolve spawn position, heading, and altitude from procedure or fallback
        proc = proc_by_runway.get(arrival_runway)
        if proc:
            heading = float(proc.get('approach_heading', threshold_data.get('direction', 0)))
            spawn_altitude = float(proc.get('spawn_altitude_ft', 3000.0))
            loc = proc.get('spawn_location', {})
            spawn_lat = loc.get('x')
            spawn_lon = loc.get('y')
            if spawn_lat is not None and spawn_lon is not None:
                spawn_lat, spawn_lon = float(spawn_lat), float(spawn_lon)
                logger.info(f"Using arrival_procedures spawn for {arrival_runway}: "
                            f"({spawn_lat:.4f}, {spawn_lon:.4f}) hdg {heading:.0f} alt {spawn_altitude:.0f}ft")
            else:
                # Procedure exists but no spawn_location — compute 5 NM out
                spawn_lat, spawn_lon = self._compute_approach_spawn(
                    touchdown_lat, touchdown_lon, heading, nm=5.0)
                logger.info(f"Computed 5 NM spawn for {arrival_runway}: ({spawn_lat:.4f}, {spawn_lon:.4f})")
        else:
            # Full fallback: use runway direction and compute 5 NM out
            heading = float(threshold_data.get('direction', 0))
            spawn_altitude = 3000.0
            spawn_lat, spawn_lon = self._compute_approach_spawn(
                touchdown_lat, touchdown_lon, heading, nm=5.0)
            logger.info(f"Fallback spawn for {arrival_runway}: ({spawn_lat:.4f}, {spawn_lon:.4f})")

        # Select random airline (weighted toward commercial)
        airlines = ['AAY', 'ENY', 'EDV', 'SKW']
        airline = random.choice(airlines)

        aircraft_type = self._get_aircraft_for_airline(airline)
        flight_number = self._generate_random_callsign(airline)

        # Assign an available gate, preferring airline-matched gates
        gates = self.airport_data.get('gates', [])
        occupied_gates = {ac.gate for ac in self.aircraft if ac.gate}
        available_gates = [g for g in gates if 'name' in g and g['name'] not in occupied_gates]

        assigned_gate = None
        if available_gates:
            airline_gates = [g for g in available_gates if g.get('airline') == airline]
            gate_data = random.choice(airline_gates if airline_gates else available_gates)
            assigned_gate = gate_data['name']
        elif gates:
            gate_data = random.choice(gates)
            assigned_gate = gate_data.get('name')
            logger.warning(f"All gates occupied, assigning {assigned_gate} (may need to wait)")

        beacon_code = self._generate_unique_beacon()
        cid = self._generate_unique_cid()

        aircraft = Aircraft(
            flight_number=flight_number,
            aircraft_type=aircraft_type,
            airline=airline,
            position=(spawn_lat, spawn_lon),
            heading=heading,
            gate=assigned_gate,
            airport_data=self.airport_data,
            flight_type="arrival",
            radio_callback=self.radio_callback,
            departure_route=None,
            tts_voice=self.assign_tts_voice(flight_number),
            aircraft_manager=self
        )

        aircraft.beacon = beacon_code
        aircraft.cid = cid
        aircraft.correct_squawk_code = beacon_code
        aircraft.current_squawk_code = None
        aircraft.squawking_mode_c = False

        aircraft.state = Aircraft.STATE_APPROACH
        aircraft.speed = 140.0 if aircraft.wake_category != 'L' else 70.0
        aircraft.altitude = spawn_altitude
        aircraft.target_altitude = 0.0
        aircraft.target_position = (touchdown_lat, touchdown_lon)
        aircraft.expected_runway = arrival_runway

        self.aircraft.append(aircraft)
        logger.info(f"[{aircraft.get_callsign()}] Beacon: {beacon_code}, CID: {cid}")

        aircraft.handed_off_to_tower = True
        self.tower_controller.handoff_from_ground(aircraft)

        gate_info = f" to gate {assigned_gate}" if assigned_gate else " to ramp"
        approach_type = proc.get('approach_type', 'visual') if proc else 'visual'
        logger.info(f"Arrival: {aircraft.get_callsign()} ({aircraft.aircraft_type}) "
                    f"{approach_type} approach rwy {arrival_runway}{gate_info}")
        print(f"Arrival: {aircraft.get_callsign()} ({aircraft.aircraft_type}) "
              f"{approach_type} rwy {arrival_runway}{gate_info}")

        if self.radio_callback and assigned_gate:
            self.radio_callback(
                f"{aircraft.get_callsign()}, {arrival_runway} {approach_type} approach, gate {assigned_gate}",
                frequency='tower'
            )

    def _compute_approach_spawn(self, touchdown_lat: float, touchdown_lon: float,
                                approach_heading: float, nm: float = 5.0):
        """Compute a spawn point nm miles behind the touchdown on the approach heading.

        Returns (spawn_lat, spawn_lon).
        """
        dist_deg = (nm * 1852.0) / 111000.0  # convert NM to degrees of latitude
        # Reciprocal heading = where the aircraft comes FROM
        reciprocal_rad = math.radians((approach_heading + 180.0) % 360.0)
        lon_compression = math.cos(math.radians(touchdown_lat))
        spawn_lat = touchdown_lat + dist_deg * math.cos(reciprocal_rad)
        spawn_lon = touchdown_lon + dist_deg * math.sin(reciprocal_rad) / lon_compression
        return spawn_lat, spawn_lon
    
    def update(self, dt: float):
        """Update all aircraft and handle automatic spawning (per-hour schedule)."""
        self.simulation_time += dt
        
        hour = int(self.simulation_time // 3600)
        sec = self.simulation_time % 3600
        hour_base = 3600.0 * hour
        
        self._ensure_spawn_schedules_for_hour(hour)
        
        # Spawn departures 1 min before they call for pushback (schedule = call times)
        while self.dep_spawn_schedule_index < len(self.dep_spawn_schedule):
            call_at = self.dep_spawn_schedule[self.dep_spawn_schedule_index]
            spawn_when = max(0.0, call_at - 60.0)
            if sec < spawn_when:
                break
            scheduled_pushback_at = hour_base + call_at
            self._spawn_departure(scheduled_pushback_at=scheduled_pushback_at)
            self.dep_spawn_schedule_index += 1
        
        # Spawn arrivals at scheduled times (skip entirely when arr_spawn_rate is 0)
        if self.arr_spawn_rate > 0:
            while (self.arr_spawn_schedule_index < len(self.arr_spawn_schedule) and
                   sec >= self.arr_spawn_schedule[self.arr_spawn_schedule_index]):
                self._spawn_arrival()
                self.arr_spawn_schedule_index += 1
        
        # Update all aircraft with current simulation time
        # Also collect aircraft to remove (departed and far away)
        aircraft_to_remove = []
        for aircraft in self.aircraft[:]:  # Use slice copy to avoid modification during iteration
            try:
                aircraft.update(dt, self.simulation_time)
                
                # Remove departed aircraft that have flown far enough away
                if aircraft.state == Aircraft.STATE_DEPARTED:
                    # Check if aircraft is far enough from airport center to remove
                    if hasattr(self, 'airport_data') and self.airport_data:
                        airport_center = self.airport_data.get('airport', {}).get('center', {})
                        if airport_center:
                            center_lat = airport_center.get('lat', 0)
                            center_lon = airport_center.get('lon', 0)
                            if center_lat and center_lon:
                                ac_lat, ac_lon = aircraft.position
                                # Calculate distance in degrees
                                dist = math.sqrt((ac_lat - center_lat)**2 + (ac_lon - center_lon)**2)
                                # Remove if more than ~10 NM away (~0.17 degrees)
                                if dist > 0.17:
                                    aircraft_to_remove.append(aircraft)
                                    logger.debug(f"[{aircraft.get_callsign()}] Removed from simulation (departed and far away)")
            except Exception as e:
                # Catch any errors in aircraft update to prevent crashes
                # Log the error but do not remove the aircraft immediately —
                # removing on exceptions caused aircraft to disappear after pushback.
                logger.error(f"Error updating aircraft {aircraft.get_callsign() if hasattr(aircraft, 'get_callsign') else 'unknown'}: {e}")
                # Keep the aircraft in the simulation; skip removal to allow
                # transient errors to be investigated without losing entities.
                # (Optionally, could mark for later cleanup if persistent failures occur.)
        
        # Remove departed/problematic aircraft
        for aircraft in aircraft_to_remove:
            try:
                self.remove_aircraft(aircraft)
            except Exception as e:
                logger.error(f"Error removing aircraft: {e}")
        
        # Update virtual tower controller (manages all departures and arrivals)
        self.tower_controller.update(self, dt)
    
    def get_aircraft_by_callsign(self, callsign: str) -> Optional[Aircraft]:
        """Find aircraft by callsign"""
        for aircraft in self.aircraft:
            if aircraft.get_callsign().upper() == callsign.upper():
                return aircraft
        return None
    
    def get_aircraft_by_flight_number(self, flight_number: str) -> Optional[Aircraft]:
        """Find aircraft by flight number only"""
        for aircraft in self.aircraft:
            if aircraft.flight_number == flight_number:
                return aircraft
        return None
    
    def get_all_aircraft(self) -> List[Aircraft]:
        """Get all aircraft"""
        return self.aircraft
    
    def remove_aircraft(self, aircraft: Aircraft):
        """Remove aircraft from simulation"""
        if aircraft in self.aircraft:
            # Free up beacon code and CID for reuse
            if aircraft.beacon is not None:
                self.used_beacons.discard(aircraft.beacon)
            if aircraft.cid is not None:
                self.used_cids.discard(aircraft.cid)
            self.aircraft.remove(aircraft)
    
    def __repr__(self):
        return f"<AircraftManager: {len(self.aircraft)} aircraft>"
