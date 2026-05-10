"""
Virtual Tower Controller
Automated tower controller that manages departures and arrivals
"""
import logging
from typing import List, Optional, Dict

logger = logging.getLogger('TowerController')

class VirtualTowerController:
    """Virtual tower controller that manages runway operations"""
    
    def __init__(self, airport_code: str, radio_callback=None, weather_panel=None):
        self.airport_code = airport_code
        self.radio_callback = radio_callback
        self.departure_runways = []  # Active departure runways
        self.arrival_runways = []  # Active arrival runways
        self.departure_queue = []  # Aircraft waiting for departure
        self.arrival_queue = []  # Aircraft on approach
        
        # Track clearance states for each aircraft
        self.lineup_clearances = {}  # {callsign: {'time': float, 'runway': str}}
        self.takeoff_clearances = {}  # {callsign: {'time': float, 'runway': str}}
        self.holding_short_aircraft = []  # Aircraft holding short of runways
        
        logger.info(f"[TOWER] Virtual Tower Controller initialized for {airport_code}")
        
        # Sync runways from weather panel on startup if provided
        if weather_panel:
            self.sync_runways_from_weather_panel(weather_panel)
            logger.info(f"[TOWER] Runways synced on startup")
    
    def set_departure_runways(self, runways: List[str]):
        """Set active departure runways
        
        Args:
            runways: List of runway identifiers (e.g., ["02", "20"])
        """
        self.departure_runways = runways.copy()
        logger.info(f"[TOWER] Departure runways set: {', '.join(runways) if runways else 'None'}")
    
    def set_arrival_runways(self, runways: List[str]):
        """Set active arrival runways
        
        Args:
            runways: List of runway identifiers (e.g., ["02", "20"])
        """
        self.arrival_runways = runways.copy()
        logger.info(f"[TOWER] Arrival runways set: {', '.join(runways) if runways else 'None'}")
    
    def sync_runways_from_weather_panel(self, weather_panel):
        """Sync runway configuration from weather panel
        
        Args:
            weather_panel: WeatherPanel instance with runway configuration
        """
        if hasattr(weather_panel, 'departure_runways'):
            self.departure_runways = weather_panel.departure_runways.copy()
        if hasattr(weather_panel, 'arrival_runways'):
            self.arrival_runways = weather_panel.arrival_runways.copy()
        
        logger.info(f"[TOWER] Synced runways from weather panel:")
        logger.info(f"[TOWER]   Departures: {', '.join(self.departure_runways) if self.departure_runways else 'None'}")
        logger.info(f"[TOWER]   Arrivals: {', '.join(self.arrival_runways) if self.arrival_runways else 'None'}")
    
    def handoff_from_ground(self, aircraft):
        """Receive handoff from ground control
        
        Args:
            aircraft: Aircraft object being handed off
        """
        # Determine what the aircraft needs based on flight type
        if aircraft.flight_type == "departure":
            # Add to departure queue if not already there
            if aircraft not in self.departure_queue:
                self.departure_queue.append(aircraft)
                logger.info(f"[TOWER] {aircraft.get_callsign()} handed off from ground for departure")
                
                # Determine which runway to use based on expected runway or active departure runways
                assigned_runway = None
                if hasattr(aircraft, 'expected_runway') and aircraft.expected_runway:
                    assigned_runway = aircraft.expected_runway
                elif self.departure_runways:
                    # Assign first available departure runway
                    assigned_runway = self.departure_runways[0]
                    aircraft.expected_runway = assigned_runway
                    logger.info(f"[TOWER] Assigned runway {assigned_runway} to {aircraft.get_callsign()}")
                
                # Acknowledge handoff with runway information
                # Note: Tower transmissions are on different frequency - don't send to ground radio callback
                # if self.radio_callback and assigned_runway:
                #     self.radio_callback(
                #         f"{aircraft.get_callsign()}, tower, runway {assigned_runway} in sight, hold short",
                #         is_atc=True
                #     )
                # elif self.radio_callback:
                #     self.radio_callback(
                #         f"{aircraft.get_callsign()}, tower, hold short",
                #         is_atc=True
                #     )
                pass  # Tower frequency - separate from ground
        elif aircraft.flight_type == "arrival":
            # Add to arrival queue if not already there
            if aircraft not in self.arrival_queue:
                self.arrival_queue.append(aircraft)
                logger.info(f"[TOWER] {aircraft.get_callsign()} on approach for arrival")
                
                # Determine which runway to use for landing
                assigned_runway = None
                if hasattr(aircraft, 'expected_runway') and aircraft.expected_runway:
                    assigned_runway = aircraft.expected_runway
                elif self.arrival_runways:
                    # Assign first available arrival runway
                    assigned_runway = self.arrival_runways[0]
                    aircraft.expected_runway = assigned_runway
                    logger.info(f"[TOWER] Assigned runway {assigned_runway} to {aircraft.get_callsign()} for landing")
                
                # Acknowledge handoff with landing clearance
                # Note: Tower transmissions are on different frequency - don't send to ground radio callback
                # if self.radio_callback and assigned_runway:
                #     self.radio_callback(
                #         f"{aircraft.get_callsign()}, tower, runway {assigned_runway}, cleared to land",
                #         is_atc=True
                #     )
                # elif self.radio_callback:
                #     self.radio_callback(
                #         f"{aircraft.get_callsign()}, tower, continue approach",
                #         is_atc=True
                #     )
                pass  # Tower frequency - separate from ground
        else:
            # Unknown flight type - log warning
            logger.warning(f"[TOWER] {aircraft.get_callsign()} handed off with unknown flight type: {aircraft.flight_type}")
    
    def update(self, aircraft_manager, dt: float):
        """Update tower operations - manage departures and arrivals
        
        Args:
            aircraft_manager: AircraftManager instance
            dt: Delta time
        """
        # Auto-handoff departures that reach hold short but aren't handed off yet
        for aircraft in aircraft_manager.aircraft:
            if (aircraft.flight_type == "departure" and 
                not aircraft.handed_off_to_tower and 
                aircraft.hold_short and 
                aircraft.state == aircraft.STATE_HOLDING):
                self.handoff_from_ground(aircraft)
                logger.info(f"[TOWER] Auto-handoff: {aircraft.get_callsign()} at hold short runway {aircraft.hold_short}")
        
        # Process departure queue
        for aircraft in self.departure_queue[:]:
            if not hasattr(aircraft, 'handed_off_to_tower') or not aircraft.handed_off_to_tower:
                continue
            
            callsign = aircraft.get_callsign()
            
            # Check aircraft state and issue appropriate clearances
            if aircraft.state == aircraft.STATE_HOLDING:
                # Aircraft is holding - check what clearance is needed
                if callsign not in self.lineup_clearances and aircraft.hold_short:
                    # Aircraft is holding short - issue lineup clearance
                    self._issue_lineup_clearance(aircraft, aircraft_manager)
                elif callsign in self.lineup_clearances and callsign not in self.takeoff_clearances:
                    # Aircraft has lined up and is holding in position - check for takeoff clearance
                    # Only issue takeoff when lineup is COMPLETE (position + heading aligned)
                    lineup_complete = getattr(aircraft, 'lineup_complete', False)
                    
                    if lineup_complete:
                        logger.info(f"[TOWER] {callsign} lineup complete, issuing takeoff clearance")
                        self._issue_takeoff_clearance(aircraft, aircraft_manager)
                    else:
                        # Check if still aligning heading
                        aligning = getattr(aircraft, 'aligning_for_takeoff', False)
                        if aligning:
                            logger.debug(f"[TOWER] {callsign} aligning heading for takeoff...")
                        else:
                            logger.debug(f"[TOWER] {callsign} waiting for lineup completion...")
            
            elif aircraft.state == aircraft.STATE_TAXI:
                # Aircraft is taxiing to lineup position after clearance
                if callsign in self.lineup_clearances:
                    # Just log - wait for aircraft to complete lineup and transition to HOLDING
                    # Don't issue takeoff clearance while still taxiing
                    logger.debug(f"[TOWER] {callsign} taxiing to lineup position, waiting for lineup completion...")
            
            # Remove from queue if departed
            if aircraft.state == aircraft.STATE_DEPARTED:
                self.departure_queue.remove(aircraft)
                # Clean up clearance tracking
                self.lineup_clearances.pop(callsign, None)
                self.takeoff_clearances.pop(callsign, None)
                logger.info(f"[TOWER] {callsign} departed, switching to departure frequency")
                
                # Tower frequency - don't send to ground radio
                # if self.radio_callback:
                #     self.radio_callback(
                #         f"{callsign}, contact departure, good day",
                #         is_atc=True
                #     )
                pass  # Tower frequency - separate from ground
        
        # Process arrival queue - remove arrivals that have cleared the runway
        for aircraft in self.arrival_queue[:]:
            callsign = aircraft.get_callsign()
            
            # Remove from queue if no longer on approach/landing (cleared runway)
            # Arrivals switch to ground frequency after clearing runway
            if aircraft.state not in [aircraft.STATE_APPROACH, aircraft.STATE_LANDING]:
                self.arrival_queue.remove(aircraft)
                logger.info(f"[TOWER] {callsign} cleared runway, switching to ground frequency")
        
        # Clean up holding short list
        self._cleanup_holding_short(aircraft_manager)
    
    def get_status(self) -> Dict:
        """Get current tower status
        
        Returns:
            Dictionary with tower status information
        """
        return {
            'airport': self.airport_code,
            'departure_runways': self.departure_runways,
            'arrival_runways': self.arrival_runways,
            'departures_in_queue': len(self.departure_queue),
            'arrivals_in_queue': len(self.arrival_queue),
            'departure_callsigns': [ac.get_callsign() for ac in self.departure_queue],
            'arrival_callsigns': [ac.get_callsign() for ac in self.arrival_queue]
        }
    
    def get_debug_info(self) -> str:
        """Get detailed debug information about tower operations
        
        Returns:
            Formatted debug string
        """
        status = self.get_status()
        
        dep_rwys = ', '.join(status['departure_runways']) if status['departure_runways'] else 'None'
        arr_rwys = ', '.join(status['arrival_runways']) if status['arrival_runways'] else 'None'
        
        debug_lines = [
            f"╔═══════════════════════════════════════════╗",
            f"║  VIRTUAL TOWER - {self.airport_code}",
            f"╠═══════════════════════════════════════════╣",
            f"║  Departure Runways: {dep_rwys}",
            f"║  Arrival Runways: {arr_rwys}",
            f"║",
            f"║  DEPARTURES ({status['departures_in_queue']}):",
        ]
        
        for aircraft in self.departure_queue:
            state_info = f"{aircraft.state}"
            if hasattr(aircraft, 'last_known_surface') and aircraft.last_known_surface:
                state_info += f" on {aircraft.last_known_surface}"
            
            cleared_info = ""
            if hasattr(aircraft, 'tower_cleared_to_lineup') and aircraft.tower_cleared_to_lineup:
                cleared_info += " [LINEUP✓]"
            if hasattr(aircraft, 'tower_cleared_for_takeoff') and aircraft.tower_cleared_for_takeoff:
                cleared_info += " [TAKEOFF✓]"
            
            debug_lines.append(f"║    • {aircraft.get_callsign()}: {state_info}{cleared_info}")
        
        if not self.departure_queue:
            debug_lines.append(f"║    (none)")
        
        debug_lines.append(f"║")
        debug_lines.append(f"║  ARRIVALS ({status['arrivals_in_queue']}):")
        
        for aircraft in self.arrival_queue:
            debug_lines.append(f"║    • {aircraft.get_callsign()}: {aircraft.state}")
        
        if not self.arrival_queue:
            debug_lines.append(f"║    (none)")
        
        debug_lines.append(f"╚═══════════════════════════════════════════╝")
        
        return "\n".join(debug_lines)
    
    def print_debug_info(self):
        """Print debug information to console"""
        print(self.get_debug_info())
        logger.info(f"\n{self.get_debug_info()}")
    
    def _issue_lineup_clearance(self, aircraft, aircraft_manager):
        """Issue lineup clearance to aircraft holding short
        
        Args:
            aircraft: Aircraft object
            aircraft_manager: AircraftManager instance
        """
        callsign = aircraft.get_callsign()
        runway = aircraft.hold_short
        
        if not runway:
            logger.warning(f"[TOWER] {callsign} has no hold_short runway set")
            return
        
        # Wait a few seconds after handoff before clearing (realistic delay)
        if not hasattr(aircraft, 'tower_handoff_time'):
            aircraft.tower_handoff_time = getattr(aircraft, 'current_sim_time', 0.0)
            logger.debug(f"[TOWER] {callsign}: Recording handoff time")
            return
        
        time_since_handoff = getattr(aircraft, 'current_sim_time', 0.0) - aircraft.tower_handoff_time
        if time_since_handoff < 2.0:  # Wait 2 seconds before clearing
            logger.debug(f"[TOWER] {callsign}: Waiting {2.0 - time_since_handoff:.1f}s before lineup clearance")
            return
        
        # Check for arriving aircraft (within 1.5nm)
        arriving_aircraft = aircraft._check_for_arrivals(aircraft_manager)
        
        if arriving_aircraft:
            # Arrivals have priority - wait
            logger.info(f"[TOWER] {callsign}: ⏸️ HOLDING - Arrival traffic {arriving_aircraft.get_callsign()} on final")
            return
        
        # Issue lineup clearance
        logger.info(f"[TOWER] {callsign}: 🛫 LINEUP CLEARANCE - Runway {runway}")
        
        # Radio transmission - Tower frequency, don't send to ground radio
        # if self.radio_callback:
        #     self.radio_callback(f"{callsign}, Runway {runway}, line up and wait", is_atc=True)
        pass  # Tower frequency - separate from ground
        
        # Call aircraft method to execute lineup
        aircraft.execute_lineup_clearance(runway)
        
        # Track that we've issued this clearance
        import time
        self.lineup_clearances[callsign] = {
            'time': time.time(),
            'runway': runway
        }
    
    def _issue_takeoff_clearance(self, aircraft, aircraft_manager):
        """Issue takeoff clearance to aircraft in position
        
        Args:
            aircraft: Aircraft object
            aircraft_manager: AircraftManager instance
        """
        callsign = aircraft.get_callsign()
        
        # Final check for arrivals before takeoff clearance (within 1.5nm)
        arriving_aircraft = aircraft._check_for_arrivals(aircraft_manager)
        
        if arriving_aircraft:
            logger.info(f"[TOWER] {callsign}: ⏸️ HOLDING in position - Arrival traffic {arriving_aircraft.get_callsign()} on final")
            return
        
        logger.info(f"[TOWER] {callsign}: ✈️ Issuing TAKEOFF clearance")
        
        # Call aircraft method to execute takeoff
        aircraft._clear_for_takeoff()
        
        # Track that we've issued this clearance
        import time
        self.takeoff_clearances[callsign] = {
            'time': time.time(),
            'runway': getattr(aircraft, 'expected_runway', 'unknown')
        }
    
    def _is_aircraft_on_runway(self, aircraft):
        """Check if aircraft is on the runway polygon
        
        Args:
            aircraft: Aircraft object
            
        Returns:
            bool: True if aircraft is on runway, False otherwise
        """
        if not hasattr(aircraft, 'airport_data') or not aircraft.airport_data:
            return False
        
        lat, lon = aircraft.position
        runways = aircraft.airport_data.get('runways', [])
        
        for runway in runways:
            # Check if inside runway polygon
            if aircraft._is_inside_runway_polygon(lat, lon, runway):
                return True
        
        return False
    
    def aircraft_holding_short(self, aircraft):
        """Handle aircraft holding short of runway - give clearance to contact ground
        
        Args:
            aircraft: Aircraft object that is holding short
        """
        callsign = aircraft.get_callsign()
        
        # Add to holding short list
        if aircraft not in self.holding_short_aircraft:
            self.holding_short_aircraft.append(aircraft)
            logger.info(f"[TOWER] {callsign} holding short of runway {aircraft.expected_runway}")
        
        # Give clearance to contact ground after a short delay
        import time
        import random
        
        # Schedule tower clearance to contact ground
        if self.radio_callback:
            # Tower: "Callsign, contact ground 121.9"
            clearance_delay = random.uniform(1.0, 3.0)  # 1-3 second delay
            clearance_text = f"{callsign}, contact ground on 121.9, good day"
            self.radio_callback(clearance_text, is_atc=True, delay=clearance_delay, frequency='tower')
            
            logger.info(f"[TOWER] {callsign} cleared to contact ground")
    
    def _cleanup_holding_short(self, aircraft_manager):
        """Clean up holding short list - remove aircraft no longer holding"""
        for aircraft in aircraft_manager.aircraft:
            callsign = aircraft.get_callsign()
            if aircraft in self.holding_short_aircraft and aircraft.state != 'holding':
                self.holding_short_aircraft.remove(aircraft)
                logger.debug(f"[TOWER] {callsign} no longer holding short")
