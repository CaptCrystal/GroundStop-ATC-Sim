"""
Airport Navigation Graph System
Represents runways and taxiways as a navigable graph for intelligent aircraft routing
"""
import math
import heapq
from typing import Dict, List, Optional, Tuple, Set
import logging

logger = logging.getLogger('AirportGraph')


class NavigationNode:
    """Represents a point in the airport navigation graph"""
    
    def __init__(self, node_id: str, position: Tuple[float, float], node_type: str, name: str = None):
        """
        Args:
            node_id: Unique identifier for this node
            position: (lat, lon) coordinates
            node_type: Type of node ('taxiway', 'runway', 'gate', 'ramp', 'intersection')
            name: Human-readable name (e.g., 'Taxiway A', 'Runway 02')
        """
        self.id = node_id
        self.position = position
        self.type = node_type
        self.name = name or node_id
        self.edges: List['NavigationEdge'] = []  # Outgoing edges
        
    def add_edge(self, edge: 'NavigationEdge'):
        """Add an outgoing edge from this node"""
        self.edges.append(edge)
    
    def __repr__(self):
        return f"<Node {self.name} ({self.type}) at {self.position}>"


class NavigationEdge:
    """Represents a connection between two nodes (a segment of taxiway/runway)"""
    
    def __init__(self, from_node: NavigationNode, to_node: NavigationNode, 
                 edge_type: str, name: str = None, waypoints: List[Tuple[float, float]] = None):
        """
        Args:
            from_node: Starting node
            to_node: Ending node
            edge_type: Type of edge ('taxiway', 'runway', 'ramp')
            name: Name of the taxiway/runway this edge belongs to
            waypoints: Intermediate points along this edge
        """
        self.from_node = from_node
        self.to_node = to_node
        self.type = edge_type
        self.name = name or f"{from_node.id}->{to_node.id}"
        self.waypoints = waypoints or []
        self.distance = self._calculate_distance()
        
    def _calculate_distance(self) -> float:
        """Calculate total distance along this edge"""
        total = 0.0
        points = [self.from_node.position] + self.waypoints + [self.to_node.position]
        for i in range(len(points) - 1):
            lat1, lon1 = points[i]
            lat2, lon2 = points[i + 1]
            total += math.sqrt((lat2 - lat1)**2 + (lon2 - lon1)**2)
        return total
    
    def get_all_waypoints(self) -> List[Tuple[float, float]]:
        """Get all waypoints including start and end nodes"""
        return [self.from_node.position] + self.waypoints + [self.to_node.position]
    
    def __repr__(self):
        return f"<Edge {self.name}: {self.from_node.id} -> {self.to_node.id} ({self.distance:.6f}°)>"


class AirportGraph:
    """Navigation graph representing the entire airport surface"""
    
    def __init__(self, airport_data: Dict):
        """
        Build navigation graph from airport data
        
        Args:
            airport_data: Airport configuration dictionary
        """
        self.airport_data = airport_data
        self.nodes: Dict[str, NavigationNode] = {}
        self.edges: List[NavigationEdge] = []
        
        # Surface name to edges mapping for location awareness
        self.surface_edges: Dict[str, List[NavigationEdge]] = {}
        
        # Build the graph
        self._build_graph()
        
        logger.info(f"Airport graph built: {len(self.nodes)} nodes, {len(self.edges)} edges")
    
    def _build_graph(self):
        """Build the navigation graph from airport data"""
        # Build taxiway network
        self._build_taxiway_network()
        
        # Build runway network
        self._build_runway_network()
        
        # Build ramp/apron network
        self._build_ramp_network()
        
        # Connect gates to ramps
        self._connect_gates_to_network()
        
        # Find and create intersection nodes
        self._create_intersections()
    
    def _build_taxiway_network(self):
        """Build nodes and edges for taxiways - one node per point so crossings become connectable."""
        taxiways = self.airport_data.get('taxiways', [])
        
        for taxiway in taxiways:
            taxiway_name = taxiway.get('taxiway', '')
            points = taxiway.get('points', [])
            
            if not points or not taxiway_name:
                continue
            
            coords = []
            for point in points:
                x = point.get('x')
                y = point.get('y')
                if x is not None and y is not None:
                    coords.append((x, y))
            
            if len(coords) < 2:
                continue
            
            # Create a node at every point so intersections (nearby points from different taxiways) link
            taxiway_nodes = []
            for i, pos in enumerate(coords):
                node_id = f"taxiway_{taxiway_name}_{i}"
                node = NavigationNode(
                    node_id,
                    pos,
                    'taxiway',
                    f"Taxiway {taxiway_name}"
                )
                self.nodes[node_id] = node
                taxiway_nodes.append(node)
            
            # Edges between consecutive nodes (bidirectional)
            if taxiway_name not in self.surface_edges:
                self.surface_edges[taxiway_name] = []
            for i in range(len(taxiway_nodes) - 1):
                n1, n2 = taxiway_nodes[i], taxiway_nodes[i + 1]
                fwd = NavigationEdge(n1, n2, 'taxiway', f"Taxiway {taxiway_name}", [])
                rev = NavigationEdge(n2, n1, 'taxiway', f"Taxiway {taxiway_name}", [])
                n1.add_edge(fwd)
                n2.add_edge(rev)
                self.edges.extend([fwd, rev])
                self.surface_edges[taxiway_name].extend([fwd, rev])
            
            logger.debug(f"Built taxiway {taxiway_name}: {len(coords)} nodes, {len(coords)-1} segments")
    
    def _build_runway_network(self):
        """Build nodes and edges for runways"""
        runways = self.airport_data.get('runways', [])
        runway_definitions = self.airport_data.get('runway_definition', [])
        
        for runway in runways:
            runway_name = runway.get('name', '')  # e.g., "02/20"
            points = runway.get('points', [])
            
            if not points or not runway_name:
                continue
            
            # Convert points
            coords = []
            for point in points:
                x = point.get('x')
                y = point.get('y')
                if x is not None and y is not None:
                    coords.append((x, y))
            
            if len(coords) < 2:
                continue
            
            # Split runway name (e.g., "02/20" -> ["02", "20"])
            runway_numbers = runway_name.split('/')
            
            if len(runway_numbers) == 2:
                # Create nodes for each runway end
                rwy1, rwy2 = runway_numbers
                
                # Find touchdown points from runway definitions
                td1 = self._find_touchdown_point(rwy1, runway_definitions)
                td2 = self._find_touchdown_point(rwy2, runway_definitions)
                
                node1_id = f"runway_{rwy1}_threshold"
                node2_id = f"runway_{rwy2}_threshold"
                
                node1 = NavigationNode(node1_id, coords[0], 'runway', f"Runway {rwy1}")
                node2 = NavigationNode(node2_id, coords[-1], 'runway', f"Runway {rwy2}")
                
                self.nodes[node1_id] = node1
                self.nodes[node2_id] = node2
                
                # Create runway edges (bidirectional for taxiing, but typically one-way for takeoff)
                waypoints = coords[1:-1] if len(coords) > 2 else []
                
                edge1 = NavigationEdge(node1, node2, 'runway', f"Runway {rwy1}", waypoints)
                edge2 = NavigationEdge(node2, node1, 'runway', f"Runway {rwy2}", list(reversed(waypoints)))
                
                node1.add_edge(edge1)
                node2.add_edge(edge2)
                self.edges.extend([edge1, edge2])
                
                # Track by surface name
                self.surface_edges[f"Runway {rwy1}"] = [edge1]
                self.surface_edges[f"Runway {rwy2}"] = [edge2]
                
                logger.debug(f"Built runway {runway_name}: {len(coords)} points")
    
    def _find_touchdown_point(self, runway_number: str, runway_definitions: List[Dict]) -> Optional[Tuple[float, float]]:
        """Find touchdown point for a runway from definitions"""
        for rwy_def in runway_definitions:
            if rwy_def.get('name') == runway_number:
                td = rwy_def.get('touchdown_point')
                if td:
                    x = td.get('x')
                    y = td.get('y')
                    if x is not None and y is not None:
                        return (x, y)
        return None
    
    def _build_ramp_network(self):
        """Build nodes and edges for ramps - one node per point so ramp-taxiway junctions connect."""
        ramps = self.airport_data.get('ramps', [])
        
        for ramp in ramps:
            ramp_name = ramp.get('ramp', '')
            points = ramp.get('points', [])
            
            if not points or not ramp_name:
                continue
            
            coords = []
            for point in points:
                x = point.get('x')
                y = point.get('y')
                if x is not None and y is not None:
                    coords.append((x, y))
            
            if len(coords) < 2:
                continue
            
            ramp_nodes = []
            for i, pos in enumerate(coords):
                node_id = f"ramp_{ramp_name}_{i}"
                node = NavigationNode(node_id, pos, 'ramp', f"Ramp {ramp_name}")
                self.nodes[node_id] = node
                ramp_nodes.append(node)
            
            self.surface_edges[ramp_name] = []
            for i in range(len(ramp_nodes) - 1):
                n1, n2 = ramp_nodes[i], ramp_nodes[i + 1]
                fwd = NavigationEdge(n1, n2, 'ramp', f"Ramp {ramp_name}", [])
                rev = NavigationEdge(n2, n1, 'ramp', f"Ramp {ramp_name}", [])
                n1.add_edge(fwd)
                n2.add_edge(rev)
                self.edges.extend([fwd, rev])
                self.surface_edges[ramp_name].extend([fwd, rev])
            
            logger.debug(f"Built ramp {ramp_name}: {len(coords)} nodes")
    
    def _connect_gates_to_network(self):
        """Create nodes for gates and connect them to the ramp network"""
        gates = self.airport_data.get('gates', [])
        
        for gate in gates:
            gate_name = gate.get('name', '')
            position = gate.get('position')
            connects_to = gate.get('connects_to')
            
            if not position or not gate_name:
                continue
            
            x = position.get('x')
            y = position.get('y')
            if x is None or y is None:
                continue
            
            gate_pos = (x, y)
            
            # Create gate node
            gate_node_id = f"gate_{gate_name}"
            gate_node = NavigationNode(gate_node_id, gate_pos, 'gate', gate_name)
            self.nodes[gate_node_id] = gate_node
            
            # Find closest ramp node to connect to
            if connects_to:
                closest_ramp_node = self._find_closest_node_by_surface(gate_pos, connects_to, 'ramp')
                if closest_ramp_node:
                    # Create bidirectional connection
                    gate_to_ramp = NavigationEdge(gate_node, closest_ramp_node, 'ramp', f"{gate_name} to {connects_to}")
                    ramp_to_gate = NavigationEdge(closest_ramp_node, gate_node, 'ramp', f"{connects_to} to {gate_name}")
                    
                    gate_node.add_edge(gate_to_ramp)
                    closest_ramp_node.add_edge(ramp_to_gate)
                    self.edges.extend([gate_to_ramp, ramp_to_gate])
                    
                    logger.debug(f"Connected {gate_name} to {closest_ramp_node.name}")
    
    def _find_closest_node_by_surface(self, position: Tuple[float, float], 
                                     surface_name: str, node_type: str) -> Optional[NavigationNode]:
        """Find the closest node of a specific type on a named surface"""
        min_dist = float('inf')
        closest_node = None
        
        for node in self.nodes.values():
            if node.type == node_type and surface_name.lower() in node.name.lower():
                dist = self._distance(position, node.position)
                if dist < min_dist:
                    min_dist = dist
                    closest_node = node
        
        return closest_node
    
    def _create_intersections(self):
        """Link taxiway, ramp, and runway nodes that are close (real-world intersections)."""
        taxiway_nodes = [n for n in self.nodes.values() if n.type == 'taxiway']
        ramp_nodes = [n for n in self.nodes.values() if n.type == 'ramp']
        runway_nodes = [n for n in self.nodes.values() if n.type == 'runway']
        # ~35m: enough to connect crossing taxiways and ramp/taxiway junctions
        intersection_threshold = 0.00032
        
        def link_bidirectional(a, b, label):
            if self._distance(a.position, b.position) >= intersection_threshold:
                return
            e1 = NavigationEdge(a, b, 'intersection', label)
            e2 = NavigationEdge(b, a, 'intersection', label)
            a.add_edge(e1)
            b.add_edge(e2)
            self.edges.extend([e1, e2])
        
        # Taxiway–taxiway (only link if different taxiway names to avoid self-loops)
        for i, n1 in enumerate(taxiway_nodes):
            for n2 in taxiway_nodes[i + 1:]:
                if n1.id == n2.id:
                    continue
                # Different taxiway if node ids differ (e.g. taxiway_A_0 vs taxiway_N_5)
                twy1 = n1.id.split('_')[1] if '_' in n1.id else ''
                twy2 = n2.id.split('_')[1] if '_' in n2.id else ''
                if twy1 != twy2:
                    link_bidirectional(n1, n2, f"Intersection {twy1}-{twy2}")
        
        # Taxiway–ramp
        for tn in taxiway_nodes:
            for rn in ramp_nodes:
                link_bidirectional(tn, rn, f"Taxiway-Ramp")
        
        # Taxiway–runway (so aircraft can path to/from runway thresholds)
        for tn in taxiway_nodes:
            for rn in runway_nodes:
                link_bidirectional(tn, rn, "Taxiway-Runway")
        
        logger.debug(f"Intersections: taxiway-taxiway, taxiway-ramp, taxiway-runway linked within {intersection_threshold}°")
    
    def _distance(self, pos1: Tuple[float, float], pos2: Tuple[float, float]) -> float:
        """Calculate distance between two positions"""
        lat1, lon1 = pos1
        lat2, lon2 = pos2
        return math.sqrt((lat2 - lat1)**2 + (lon2 - lon1)**2)
    
    def find_closest_taxiway(self, position: Tuple[float, float]) -> Optional[Tuple[str, Tuple[float, float], float]]:
        """
        Find the closest taxiway to a position
        
        Args:
            position: Current position (lat, lon)
            
        Returns:
            Tuple of (taxiway_name, closest_point, distance) or None
        """
        taxiways = self.airport_data.get('taxiways', [])
        
        best_taxiway = None
        best_point = None
        min_dist = float('inf')
        
        for taxiway in taxiways:
            taxiway_name = taxiway.get('taxiway', '')
            points = taxiway.get('points', [])
            
            if not points or not taxiway_name:
                continue
            
            # Check distance to each segment of the taxiway
            coords = [(p.get('x'), p.get('y')) for p in points if p.get('x') and p.get('y')]
            
            for i in range(len(coords) - 1):
                p1 = coords[i]
                p2 = coords[i + 1]
                
                # Find closest point on this segment
                closest = self._closest_point_on_segment(position, p1, p2)
                dist = self._distance(position, closest)
                
                if dist < min_dist:
                    min_dist = dist
                    best_taxiway = taxiway_name
                    best_point = closest
        
        if best_taxiway:
            return (best_taxiway, best_point, min_dist)
        return None
    
    def _closest_point_on_segment(self, point: Tuple[float, float], 
                                   seg_start: Tuple[float, float], 
                                   seg_end: Tuple[float, float]) -> Tuple[float, float]:
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
        
        # Project point onto segment
        t = ((px - sx) * dx + (py - sy) * dy) / (dx * dx + dy * dy)
        
        # Clamp to segment bounds
        t = max(0.0, min(1.0, t))
        
        return (sx + t * dx, sy + t * dy)
    
    def find_path_to_ramp(self, position: Tuple[float, float], ramp_name: str = None) -> Optional[List[Tuple[float, float]]]:
        """
        Find a path from current position to a ramp area
        
        Args:
            position: Current position
            ramp_name: Optional specific ramp name (e.g., 'main_ramp')
            
        Returns:
            List of waypoints to follow
        """
        # Find closest taxiway to current position
        taxiway_info = self.find_closest_taxiway(position)
        if not taxiway_info:
            return None
        
        current_taxiway, closest_point, _ = taxiway_info
        
        # Find ramp nodes
        ramp_nodes = [n for n in self.nodes.values() if n.type == 'ramp']
        if ramp_name:
            ramp_nodes = [n for n in ramp_nodes if ramp_name.lower() in n.name.lower()]
        
        if not ramp_nodes:
            return None
        
        # Find closest ramp node
        closest_ramp = None
        min_dist = float('inf')
        for node in ramp_nodes:
            dist = self._distance(position, node.position)
            if dist < min_dist:
                min_dist = dist
                closest_ramp = node
        
        if not closest_ramp:
            return None
        
        # Find path from closest taxiway node to ramp
        start_node = self.find_nearest_node(position, 'taxiway')
        if not start_node:
            start_node = self.find_nearest_node(position)
        
        if start_node:
            path = self._astar_path(start_node, closest_ramp)
            if path:
                # Prepend closest point on taxiway
                return [closest_point] + path
        
        return None
    
    def find_nearest_node(self, position: Tuple[float, float], node_type: str = None) -> Optional[NavigationNode]:
        """Find the nearest node to a position, optionally filtered by type"""
        min_dist = float('inf')
        nearest = None
        
        for node in self.nodes.values():
            if node_type and node.type != node_type:
                continue
            
            dist = self._distance(position, node.position)
            if dist < min_dist:
                min_dist = dist
                nearest = node
        
        return nearest
    
    def find_nearest_edge(self, position: Tuple[float, float]) -> Optional[NavigationEdge]:
        """Find the nearest edge (surface segment) to a position"""
        min_dist = float('inf')
        nearest_edge = None
        
        for edge in self.edges:
            # Check distance to all waypoints on this edge
            all_points = edge.get_all_waypoints()
            for point in all_points:
                dist = self._distance(position, point)
                if dist < min_dist:
                    min_dist = dist
                    nearest_edge = edge
        
        return nearest_edge
    
    def get_current_surface(self, position: Tuple[float, float], threshold: float = 0.0001) -> Optional[str]:
        """
        Determine which surface (taxiway/runway/ramp) the aircraft is currently on
        
        Args:
            position: Current aircraft position
            threshold: Distance threshold for being "on" a surface (~10 meters)
        
        Returns:
            Surface name (e.g., "Taxiway A", "Runway 02") or None
        """
        nearest_edge = self.find_nearest_edge(position)
        
        if nearest_edge:
            # Check if we're actually close enough to be "on" this surface
            min_dist = float('inf')
            for point in nearest_edge.get_all_waypoints():
                dist = self._distance(position, point)
                min_dist = min(min_dist, dist)
            
            if min_dist <= threshold:
                return nearest_edge.name
        
        return None
    
    def find_path(self, start_pos: Tuple[float, float], end_surface: str, 
                  via_surfaces: List[str] = None) -> Optional[List[Tuple[float, float]]]:
        """
        Find a path from start position to end surface, optionally via specific surfaces
        
        Args:
            start_pos: Starting position (lat, lon)
            end_surface: Destination surface name (e.g., "Runway 02", "Gate 5")
            via_surfaces: Optional list of surfaces to route through
        
        Returns:
            List of waypoints forming the path, or None if no path found
        """
        # Find start and end nodes
        start_node = self.find_nearest_node(start_pos)
        end_node = self._find_node_by_surface_name(end_surface)
        
        if not start_node or not end_node:
            logger.warning(f"Could not find nodes for pathfinding: start={start_node}, end={end_node}")
            return None
        
        # If via_surfaces specified, find path through those surfaces
        if via_surfaces:
            return self._find_path_via_surfaces(start_node, end_node, via_surfaces)
        else:
            # Use A* to find shortest path
            return self._astar_path(start_node, end_node)
    
    def _find_node_by_surface_name(self, surface_name: str) -> Optional[NavigationNode]:
        """Find a node by surface name (e.g., 'Runway 02', 'Gate 5')"""
        # Normalize the surface name
        surface_lower = surface_name.lower()
        
        for node in self.nodes.values():
            if surface_lower in node.name.lower():
                return node
        
        return None
    
    def _find_path_via_surfaces(self, start_node: NavigationNode, end_node: NavigationNode,
                                via_surfaces: List[str]) -> Optional[List[Tuple[float, float]]]:
        """Find path that goes through specific surfaces in order"""
        full_path = []
        current_node = start_node
        
        # Route through each via surface
        for surface_name in via_surfaces:
            via_node = self._find_node_by_surface_name(surface_name)
            if not via_node:
                logger.warning(f"Could not find node for surface: {surface_name}")
                continue
            
            # Find path from current to via node
            segment = self._astar_path(current_node, via_node)
            if segment:
                full_path.extend(segment)
                current_node = via_node
            else:
                logger.warning(f"No path found from {current_node.name} to {surface_name}")
                return None
        
        # Final segment to destination
        final_segment = self._astar_path(current_node, end_node)
        if final_segment:
            full_path.extend(final_segment)
        else:
            logger.warning(f"No path found from {current_node.name} to {end_node.name}")
            return None
        
        return full_path
    
    def _astar_path(self, start_node: NavigationNode, end_node: NavigationNode) -> Optional[List[Tuple[float, float]]]:
        """
        A* pathfinding algorithm to find shortest path between two nodes
        
        Returns:
            List of waypoints including all intermediate points
        """
        # Priority queue: (f_score, node)
        open_set = [(0, start_node.id)]
        came_from: Dict[str, Tuple[NavigationNode, NavigationEdge]] = {}
        
        g_score: Dict[str, float] = {start_node.id: 0}
        f_score: Dict[str, float] = {start_node.id: self._distance(start_node.position, end_node.position)}
        
        while open_set:
            _, current_id = heapq.heappop(open_set)
            current_node = self.nodes[current_id]
            
            if current_node.id == end_node.id:
                # Reconstruct path
                return self._reconstruct_path(came_from, current_node)
            
            for edge in current_node.edges:
                neighbor = edge.to_node
                tentative_g_score = g_score[current_id] + edge.distance
                
                if neighbor.id not in g_score or tentative_g_score < g_score[neighbor.id]:
                    came_from[neighbor.id] = (current_node, edge)
                    g_score[neighbor.id] = tentative_g_score
                    f_score[neighbor.id] = tentative_g_score + self._distance(neighbor.position, end_node.position)
                    heapq.heappush(open_set, (f_score[neighbor.id], neighbor.id))
        
        return None  # No path found
    
    def _reconstruct_path(self, came_from: Dict[str, Tuple[NavigationNode, NavigationEdge]], 
                         current_node: NavigationNode) -> List[Tuple[float, float]]:
        """Reconstruct the path from A* came_from dict, including all waypoints"""
        path = []
        
        # Build path backwards
        path_edges = []
        current_id = current_node.id
        
        while current_id in came_from:
            prev_node, edge = came_from[current_id]
            path_edges.insert(0, edge)
            current_id = prev_node.id
        
        # Convert edges to waypoints
        for edge in path_edges:
            waypoints = edge.get_all_waypoints()
            # Skip first point if it's the same as the last point we added
            if path and waypoints and self._distance(path[-1], waypoints[0]) < 0.000001:
                waypoints = waypoints[1:]
            path.extend(waypoints)
        
        return path
