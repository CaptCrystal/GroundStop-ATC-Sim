"""
Location Awareness System for Aircraft
Provides semantic understanding of aircraft position on airport surfaces
"""
import logging
from typing import Optional, Tuple
from .airport_graph import AirportGraph

logger = logging.getLogger('LocationAwareness')


class LocationAwareness:
    """
    Mixin class that provides location awareness capabilities to aircraft
    Allows aircraft to know exactly where they are (taxiway, runway, etc.)
    """
    
    def __init__(self):
        """Initialize location awareness"""
        self.current_surface = None  # Current surface name (e.g., "Taxiway A")
        self.current_surface_type = None  # Type: 'taxiway', 'runway', 'ramp', 'gate'
        self.last_known_surface = None  # Previous surface for transition detection
        self.airport_graph: Optional[AirportGraph] = None
        
    def set_airport_graph(self, graph: AirportGraph):
        """Set the airport navigation graph"""
        self.airport_graph = graph
        logger.debug(f"[{self.get_callsign()}] Airport graph set")
    
    def update_location_awareness(self):
        """
        Update aircraft's awareness of its current location
        Should be called every update cycle
        """
        if not self.airport_graph:
            return
        
        # Determine current surface
        surface_name = self.airport_graph.get_current_surface(self.position)
        
        if surface_name != self.current_surface:
            # Surface changed
            self.last_known_surface = self.current_surface
            self.current_surface = surface_name
            
            if surface_name:
                # Determine surface type from name
                if 'taxiway' in surface_name.lower():
                    self.current_surface_type = 'taxiway'
                elif 'runway' in surface_name.lower():
                    self.current_surface_type = 'runway'
                elif 'ramp' in surface_name.lower():
                    self.current_surface_type = 'ramp'
                elif 'gate' in surface_name.lower():
                    self.current_surface_type = 'gate'
                else:
                    self.current_surface_type = 'unknown'
                
                # Log surface transition (only at INFO level, not DEBUG)
                # Reduced logging frequency for performance
                if self.last_known_surface:
                    logger.debug(f"[{self.get_callsign()}] Transitioned from {self.last_known_surface} to {surface_name}")
                else:
                    logger.debug(f"[{self.get_callsign()}] Now on {surface_name}")
            else:
                self.current_surface_type = None
                if self.last_known_surface:
                    logger.debug(f"[{self.get_callsign()}] Lost surface awareness (was on {self.last_known_surface})")
    
    def get_current_location_description(self) -> str:
        """
        Get a human-readable description of current location
        
        Returns:
            String like "on Taxiway A" or "at Gate 5" or "unknown location"
        """
        if not self.current_surface:
            return "unknown location"
        
        if self.current_surface_type == 'gate':
            return f"at {self.current_surface}"
        elif self.current_surface_type in ['taxiway', 'runway', 'ramp']:
            return f"on {self.current_surface}"
        else:
            return f"at {self.current_surface}"
    
    def is_on_surface(self, surface_name: str) -> bool:
        """
        Check if aircraft is currently on a specific surface
        
        Args:
            surface_name: Name to check (case-insensitive, partial match)
        
        Returns:
            True if on the specified surface
        """
        if not self.current_surface:
            return False
        
        return surface_name.lower() in self.current_surface.lower()
    
    def is_on_taxiway(self) -> bool:
        """Check if aircraft is on any taxiway"""
        return self.current_surface_type == 'taxiway'
    
    def is_on_runway(self) -> bool:
        """Check if aircraft is on any runway"""
        return self.current_surface_type == 'runway'
    
    def is_on_ramp(self) -> bool:
        """Check if aircraft is on a ramp/apron"""
        return self.current_surface_type == 'ramp'
    
    def is_at_gate(self) -> bool:
        """Check if aircraft is at a gate"""
        return self.current_surface_type == 'gate'
    
    def get_distance_to_surface(self, surface_name: str) -> Optional[float]:
        """
        Calculate distance to a named surface
        
        Args:
            surface_name: Target surface name
        
        Returns:
            Distance in degrees, or None if surface not found
        """
        if not self.airport_graph:
            return None
        
        # Find node for the target surface
        target_node = self.airport_graph._find_node_by_surface_name(surface_name)
        if not target_node:
            return None
        
        # Calculate distance
        return self.airport_graph._distance(self.position, target_node.position)
    
    def can_reach_surface(self, surface_name: str, via_surfaces: list = None) -> bool:
        """
        Check if aircraft can reach a surface (pathfinding check)
        
        Args:
            surface_name: Target surface name
            via_surfaces: Optional list of intermediate surfaces
        
        Returns:
            True if a path exists
        """
        if not self.airport_graph:
            return False
        
        path = self.airport_graph.find_path(self.position, surface_name, via_surfaces)
        return path is not None
    
    def get_route_to_surface(self, surface_name: str, via_surfaces: list = None) -> Optional[list]:
        """
        Get a route (list of waypoints) to a target surface
        
        Args:
            surface_name: Target surface name
            via_surfaces: Optional list of intermediate surfaces to route through
        
        Returns:
            List of (lat, lon) waypoints, or None if no route found
        """
        if not self.airport_graph:
            return None
        
        return self.airport_graph.find_path(self.position, surface_name, via_surfaces)
    
    def validate_taxi_clearance(self, destination: str, via: list) -> Tuple[bool, str]:
        """
        Validate that a taxi clearance is achievable from current position
        
        Args:
            destination: Destination surface name
            via: List of intermediate surfaces
        
        Returns:
            (is_valid, reason) tuple
        """
        if not self.airport_graph:
            return (False, "No airport graph available")
        
        # Check if we can reach the destination via the specified route
        if not self.can_reach_surface(destination, via):
            return (False, f"No valid route to {destination} via {via}")
        
        # Additional validation could be added here:
        # - Check if surfaces are in logical order
        # - Check if aircraft has clearance for runways on route
        # - Check for conflicts with other aircraft
        
        return (True, "Route is valid")
    
    def get_next_expected_surface(self, via_surfaces: list, current_index: int) -> Optional[str]:
        """
        Get the next surface aircraft should be transitioning to
        
        Args:
            via_surfaces: List of surfaces in the route
            current_index: Current index in the route
        
        Returns:
            Name of next surface, or None if at end
        """
        if not via_surfaces or current_index >= len(via_surfaces) - 1:
            return None
        
        return via_surfaces[current_index + 1]
    
    def detect_surface_deviation(self, expected_surfaces: list) -> bool:
        """
        Detect if aircraft has deviated from expected route
        
        Args:
            expected_surfaces: List of surfaces aircraft should be on
        
        Returns:
            True if aircraft is not on any expected surface
        """
        if not self.current_surface or not expected_surfaces:
            return False
        
        # Check if current surface matches any expected surface
        for expected in expected_surfaces:
            if expected.lower() in self.current_surface.lower():
                return False
        
        return True  # Not on any expected surface
    
    def get_callsign(self) -> str:
        """Get aircraft callsign - to be overridden by Aircraft class"""
        return "UNKNOWN"
