"""
Geometry utility functions for spatial operations
"""
from typing import Tuple, List


def point_in_polygon(point: Tuple[float, float], polygon: List[Tuple[float, float]]) -> bool:
    """
    Check if a point is inside a polygon using ray casting algorithm
    
    Args:
        point: (lat, lon) coordinates of the point
        polygon: List of (lat, lon) coordinates forming the polygon vertices
    
    Returns:
        True if point is inside polygon, False otherwise
    """
    if not polygon or len(polygon) < 3:
        return False
    
    x, y = point
    n = len(polygon)
    inside = False
    
    p1x, p1y = polygon[0]
    for i in range(1, n + 1):
        p2x, p2y = polygon[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y
    
    return inside


def distance_to_polygon_edge(point: Tuple[float, float], polygon: List[Tuple[float, float]]) -> float:
    """
    Calculate the minimum distance from a point to the nearest edge of a polygon
    
    Args:
        point: (lat, lon) coordinates of the point
        polygon: List of (lat, lon) coordinates forming the polygon vertices
    
    Returns:
        Minimum distance to polygon edge in degrees
    """
    if not polygon or len(polygon) < 2:
        return float('inf')
    
    min_dist = float('inf')
    x, y = point
    
    for i in range(len(polygon)):
        p1 = polygon[i]
        p2 = polygon[(i + 1) % len(polygon)]
        
        # Calculate distance from point to line segment
        dist = _point_to_segment_distance(point, p1, p2)
        min_dist = min(min_dist, dist)
    
    return min_dist


def _point_to_segment_distance(point: Tuple[float, float], 
                                seg_start: Tuple[float, float], 
                                seg_end: Tuple[float, float]) -> float:
    """
    Calculate distance from a point to a line segment
    
    Args:
        point: (lat, lon) coordinates of the point
        seg_start: (lat, lon) coordinates of segment start
        seg_end: (lat, lon) coordinates of segment end
    
    Returns:
        Distance in degrees
    """
    px, py = point
    x1, y1 = seg_start
    x2, y2 = seg_end
    
    # Vector from seg_start to seg_end
    dx = x2 - x1
    dy = y2 - y1
    
    # If segment is a point
    if dx == 0 and dy == 0:
        return _euclidean_distance(point, seg_start)
    
    # Calculate projection parameter
    t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    
    # Find closest point on segment
    closest_x = x1 + t * dx
    closest_y = y1 + t * dy
    
    return _euclidean_distance(point, (closest_x, closest_y))


def _euclidean_distance(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    """Calculate Euclidean distance between two points"""
    return ((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2) ** 0.5


def closest_point_on_polygon(point: Tuple[float, float], 
                             polygon: List[Tuple[float, float]]) -> Tuple[float, float]:
    """
    Find the closest point on a polygon's edge to a given point
    
    Args:
        point: (lat, lon) coordinates of the point
        polygon: List of (lat, lon) coordinates forming the polygon vertices
    
    Returns:
        (lat, lon) coordinates of the closest point on the polygon edge
    """
    if not polygon or len(polygon) < 2:
        return point
    
    min_dist = float('inf')
    closest = point
    
    for i in range(len(polygon)):
        p1 = polygon[i]
        p2 = polygon[(i + 1) % len(polygon)]
        
        # Find closest point on this segment
        candidate = _closest_point_on_segment(point, p1, p2)
        dist = _euclidean_distance(point, candidate)
        
        if dist < min_dist:
            min_dist = dist
            closest = candidate
    
    return closest


def _closest_point_on_segment(point: Tuple[float, float],
                              seg_start: Tuple[float, float],
                              seg_end: Tuple[float, float]) -> Tuple[float, float]:
    """
    Find the closest point on a line segment to a given point
    
    Args:
        point: (lat, lon) coordinates of the point
        seg_start: (lat, lon) coordinates of segment start
        seg_end: (lat, lon) coordinates of segment end
    
    Returns:
        (lat, lon) coordinates of the closest point on the segment
    """
    px, py = point
    x1, y1 = seg_start
    x2, y2 = seg_end
    
    # Vector from seg_start to seg_end
    dx = x2 - x1
    dy = y2 - y1
    
    # If segment is a point
    if dx == 0 and dy == 0:
        return seg_start
    
    # Calculate projection parameter
    t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    
    # Find closest point on segment
    return (x1 + t * dx, y1 + t * dy)
