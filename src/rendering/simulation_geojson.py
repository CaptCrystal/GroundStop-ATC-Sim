"""
GeoJSON rendering mixin for SimulationScreen
"""
import pygame
import json
import os
import math


class GeoJSONMixin:
    """Mixin providing GeoJSON loading and rendering methods for SimulationScreen."""

    def load_geojson(self):
        """Load all airport GeoJSON files and merge them. Uses airport_data.geojson_files when available (correct for both new and saved load).
        If geojson_files is a dict, each key has { location, priority, color }: lower priority = rendered first (underneath), higher last (on top)."""
        # Build list of (path, priority, color). Priority: lower = draw first (bottom), higher = draw last (top).
        geojson_specs = []  # list of (path, priority int, color str or None)
        gf = self.airport_data.get('geojson_files') if self.airport_data else None

        if gf is not None:
            if isinstance(gf, dict):
                for _key, spec in gf.items():
                    if not isinstance(spec, dict):
                        continue
                    loc = spec.get('location')
                    if not loc:
                        continue
                    path = os.path.abspath(loc)
                    # Support both "priority" and "piority" typo
                    prio = spec.get('priority', spec.get('piority', 0))
                    prio = int(prio) if prio is not None else 0
                    color = spec.get('color')
                    geojson_specs.append((path, prio, color))
                print(f"Using GeoJSON from airport data (dict): {len(geojson_specs)} file(s) with priority/color")
            else:
                for p in gf:
                    geojson_specs.append((os.path.abspath(p), 0, None))
                print(f"Using GeoJSON paths from airport data: {len(geojson_specs)} file(s)")
        elif self.scenario:
            paths = self.scenario.get_geojson_paths()
            geojson_specs = [(p, 0, None) for p in paths]
        elif self.save_data:
            metadata = self.save_data.get('metadata', {})
            airport_code = metadata.get('airport_code', 'UNKNOWN')
            geojson_specs = [
                (os.path.abspath(f"data/airports/{airport_code}/{airport_code}_Runway.geojson"), 0, None),
                (os.path.abspath(f"data/airports/{airport_code}/{airport_code}_Taxiways.geojson"), 0, None),
            ]
            print(f"Fallback GeoJSON paths for {airport_code} (airport_data may not have geojson_files)")

        # Check if we should include helpfiles
        show_helpfiles = self.top_menu_bar.show_helpfiles if hasattr(self, 'top_menu_bar') else True
        if show_helpfiles and self.airport_data:
            helpfiles = self.airport_data.get('geojson_helpfiles', [])
            if helpfiles:
                for f in helpfiles:
                    geojson_specs.append((os.path.abspath(f), 0, None))
                print(f"Including {len(helpfiles)} helpfile(s)")

        if not geojson_specs:
            print("No GeoJSON files specified")
            self.geojson_data = None
            return

        try:
            print(f"Loading {len(geojson_specs)} GeoJSON file(s)...")
            self.geojson_loading = True

            merged_data = {
                "type": "FeatureCollection",
                "features": []
            }

            for geojson_path, layer_priority, layer_color in geojson_specs:
                if os.path.exists(geojson_path):
                    print(f"  Loading: {geojson_path} (priority={layer_priority}, color={layer_color or 'default'})")
                    with open(geojson_path, 'r') as f:
                        data = json.load(f)

                    if data and 'features' in data:
                        for feat in data['features']:
                            # Tag feature with layer priority and color for sorting/rendering
                            feat = dict(feat)
                            feat['_layer_priority'] = layer_priority
                            feat['_layer_color'] = layer_color
                            merged_data['features'].append(feat)
                        print(f"    Added {len(data['features'])} features")
                else:
                    print(f"  WARNING: File not found: {geojson_path}")

            self.geojson_data = merged_data

            # Debug info
            if self.geojson_data and 'features' in self.geojson_data:
                feature_count = len(self.geojson_data['features'])
                print(f"Total loaded features: {feature_count}")

                # Warn if too many features
                if feature_count > 1000:
                    print(f"WARNING: Large GeoJSON with {feature_count} features may cause performance issues")
                    print("Consider simplifying the GeoJSON or filtering features")

                # Show first feature for debugging
                if feature_count > 0:
                    first = self.geojson_data['features'][0]
                    print(f"First feature type: {first.get('geometry', {}).get('type', 'unknown')}")
                    print(f"First feature properties: {first.get('properties', {})}")
            else:
                print("GeoJSON loaded but no features found")

            self.geojson_loaded = True
            self.geojson_loading = False
            print("GeoJSON loading complete")
        except Exception as e:
            print(f"Error loading GeoJSON: {e}")
            import traceback
            traceback.print_exc()
            self.geojson_data = None
            self.geojson_loading = False

    def calculate_viewport_data(self):
        """Calculate and cache center coordinates and bounds (called once at init)"""
        print("Calculating viewport data...")

        # Try to get airport coordinates from scenario manager
        try:
            from src.core.scenario_manager import get_scenario_manager
            manager = get_scenario_manager()
            airport = manager.get_airport_by_code(self.scenario.airport_code)

            if airport and hasattr(airport, 'coordinates'):
                self.center_lat = airport.coordinates['lat']
                self.center_lon = airport.coordinates['lon']
                print(f"Using airport coordinates: {self.center_lat}, {self.center_lon}")
        except Exception as e:
            print(f"Could not get airport coordinates: {e}")

        # Calculate bounds from GeoJSON
        if self.geojson_data:
            self.bounds = self.get_geojson_bounds()
            if self.bounds:
                min_lon, min_lat, max_lon, max_lat = self.bounds
                print(f"GeoJSON bounds: lon=[{min_lon:.6f}, {max_lon:.6f}], lat=[{min_lat:.6f}, {max_lat:.6f}]")

                # If we don't have center from airport, calculate from bounds
                if self.center_lat is None or self.center_lon is None:
                    self.center_lon = (min_lon + max_lon) / 2
                    self.center_lat = (min_lat + max_lat) / 2
                    print(f"Using calculated center: {self.center_lat}, {self.center_lon}")
            else:
                print("WARNING: Could not calculate bounds from GeoJSON")

        print("Viewport data calculation complete")

    def get_scale(self):
        """Calculate the current scale factor for rendering"""
        if not self.bounds or self.center_lat is None:
            return 1.0

        min_lon, min_lat, max_lon, max_lat = self.bounds
        lon_range = max_lon - min_lon
        lat_range = max_lat - min_lat

        if lon_range == 0 or lat_range == 0:
            return 1.0

        padding = 100
        lat_correction = math.cos(math.radians(self.center_lat))
        lon_range_corrected = lon_range * lat_correction

        scale_x = (self.width - padding * 2) / lon_range_corrected
        scale_y = (self.height - padding * 2) / lat_range

        return min(scale_x, scale_y) * self.zoom

    def render_geojson(self):
        """Render the GeoJSON airport layout"""
        if not self.geojson_data or 'features' not in self.geojson_data:
            return

        # Use cached center coordinates and bounds (calculated once at init)
        if self.center_lat is None or self.center_lon is None:
            # Use fallback coordinates from airport data or save data
            if self.airport_data:
                self.center_lat = self.airport_data.get('lat', 37.241121)
                self.center_lon = self.airport_data.get('lon', -93.391115)
            elif self.save_data:
                metadata = self.save_data.get('metadata', {})
                # Use known coordinates for KSGF as fallback
                self.center_lat = 37.241121
                self.center_lon = -93.391115
            else:
                # Default fallback
                self.center_lat = 37.241121
                self.center_lon = -93.391115
            print(f"Using fallback coordinates: {self.center_lat}, {self.center_lon}")

        if not self.bounds:
            print("ERROR: No bounds available")
            return

        center_lat = self.center_lat
        center_lon = self.center_lon
        min_lon, min_lat, max_lon, max_lat = self.bounds
        lon_range = max_lon - min_lon
        lat_range = max_lat - min_lat

        if lon_range == 0 or lat_range == 0:
            print(f"Invalid range: lon={lon_range}, lat={lat_range}")
            return

        # Get scale
        scale = self.get_scale()

        # Debug scale calculation (only print once per second to avoid spam)
        if not hasattr(self, '_last_scale_debug') or pygame.time.get_ticks() - self._last_scale_debug > 1000:
            lat_correction = math.cos(math.radians(self.center_lat))
            lon_range_corrected = lon_range * lat_correction
            scale_x = (self.width - 200) / lon_range_corrected
            scale_y = (self.height - 200) / lat_range
            self._last_scale_debug = pygame.time.get_ticks()

        # Draw each feature (with performance limit)
        feature_count = 0
        max_features = 500  # Limit features to prevent freeze

        total_features = len(self.geojson_data['features'])

        # Update instance variables for HUD
        self.total_features = total_features

        # Sort by layer priority first (lower = draw first/underneath), then by feature zIndex
        def _sort_key(f):
            layer_prio = f.get('_layer_priority', 0)
            if layer_prio is None:
                layer_prio = 0
            z = f.get('properties', {}).get('zIndex', 0)
            z = z if z is not None else 0
            return (layer_prio, z)
        sorted_features = sorted(
            self.geojson_data['features'],
            key=_sort_key
        )

        for i, feature in enumerate(sorted_features):
            if feature_count >= max_features:
                break

            # Only render features that might be visible
            try:
                self.render_feature(feature, center_lon, center_lat, scale)
                feature_count += 1
            except Exception as e:
                # Skip problematic features
                if i < 5:  # Only print errors for first few features
                    print(f"Error rendering feature {i}: {e}")
                continue

        # Update rendered feature count for HUD
        self.rendered_features = feature_count

    def render_feature(self, feature, center_lon, center_lat, scale):
        """Render a single GeoJSON feature"""
        if 'geometry' not in feature or 'type' not in feature['geometry']:
            return

        geometry = feature['geometry']
        properties = feature.get('properties', {})

        # Layer color from geojson_files config (priority/color per file) - used when no fillColor in feature
        layer_color = feature.get('_layer_color')

        # Check for style properties (both in nested 'style' object and directly in properties)
        style = properties.get('style', {})
        fill_color = None
        stroke_color = None
        fill_opacity = 1.0
        stroke_width = 0  # No borders by default; GeoJSON can set weight if outline wanted

        # Check for fillColor directly in properties first (common format)
        if 'fillColor' in properties:
            fill_color = self.parse_color(properties['fillColor'])
        elif style and 'fillColor' in style:
            fill_color = self.parse_color(style['fillColor'])

        # Check for stroke/outline color
        if 'color' in properties:
            stroke_color = self.parse_color(properties['color'])
        elif style and 'color' in style:
            stroke_color = self.parse_color(style['color'])

        # Check for opacity
        if 'fillOpacity' in properties:
            fill_opacity = float(properties['fillOpacity'])
        elif style and 'fillOpacity' in style:
            fill_opacity = float(style['fillOpacity'])

        # Check for stroke width
        if 'weight' in properties:
            stroke_width = int(properties['weight'])
        elif style and 'weight' in style:
            stroke_width = int(style['weight'])

        # Use layer color from geojson_files config when feature has no fillColor
        if fill_color is None and layer_color:
            fill_color = self.parse_color(layer_color)

        # Get feature type from properties if available
        feature_type = ''
        runway_name = ''
        if properties:
            feature_type = properties.get('aeroway',
                          properties.get('type',
                          properties.get('highway',
                          properties.get('area', '')))).lower()
            # Get runway name/reference for active runway highlighting
            runway_name = properties.get('ref', properties.get('name', ''))

        # Determine colors (use style if available, otherwise use defaults)
        if fill_color is None:
            # If no style, use geometry type and size to determine color
            if not feature_type:
                geom_type = geometry['type']
                if geom_type == 'Polygon' or geom_type == 'MultiPolygon':
                    # Analyze polygon to determine if runway or apron
                    coords = geometry['coordinates'][0] if geom_type == 'Polygon' else geometry['coordinates'][0][0]
                    if len(coords) >= 4:
                        # Calculate rough dimensions
                        lons = [c[0] for c in coords]
                        lats = [c[1] for c in coords]
                        width = max(lons) - min(lons)
                        height = max(lats) - min(lats)
                        aspect_ratio = max(width, height) / (min(width, height) + 0.0001)

                        if aspect_ratio > 5:
                            fill_color = self.runway_color
                        else:
                            fill_color = self.apron_color
                    else:
                        fill_color = self.apron_color
                elif geom_type == 'LineString':
                    fill_color = self.taxiway_color
                else:
                    fill_color = self.default_color
            else:
                # Choose color based on feature type from properties
                if 'runway' in feature_type:
                    # Check if this runway is active
                    is_active_runway = False
                    if runway_name and self.asde_config['active_runways']:
                        # Check if runway name matches any active runway
                        for active_rwy in self.asde_config['active_runways']:
                            if active_rwy in runway_name or runway_name in active_rwy:
                                is_active_runway = True
                                break

                    # Highlight active runways with green tint
                    if is_active_runway:
                        fill_color = (20, 80, 40)  # Dark green for active runways
                    else:
                        fill_color = self.runway_color
                elif 'taxiway' in feature_type:
                    fill_color = self.taxiway_color
                elif 'apron' in feature_type or 'parking' in feature_type:
                    fill_color = self.apron_color
                elif 'building' in feature_type or 'terminal' in feature_type:
                    fill_color = self.building_color
                elif 'grass' in feature_type or 'aerodrome' in feature_type:
                    fill_color = self.grass_color
                else:
                    fill_color = self.default_color

        # Apply opacity to fill color
        if fill_opacity < 1.0:
            fill_color = self.apply_opacity(fill_color, fill_opacity)

        # Render based on geometry type
        if geometry['type'] == 'LineString':
            line_color = stroke_color if stroke_color else fill_color
            line_width = max(1, stroke_width)  # LineStrings need visible width (no border = polygon only)
            self.render_linestring(geometry['coordinates'], center_lon, center_lat, scale, line_color, line_width)
        elif geometry['type'] == 'Polygon':
            self.render_polygon(geometry['coordinates'], center_lon, center_lat, scale, fill_color, stroke_color, stroke_width)
        elif geometry['type'] == 'MultiPolygon':
            for polygon_coords in geometry['coordinates']:
                self.render_polygon(polygon_coords, center_lon, center_lat, scale, fill_color, stroke_color, stroke_width)

    def render_linestring(self, coordinates, center_lon, center_lat, scale, color, width=2):
        """Render a LineString"""
        points = []
        for coord in coordinates:
            if len(coord) >= 2:
                lon, lat = coord[0], coord[1]
                # Skip invalid coordinates
                if lon == 0.0 and lat == 0.0:
                    continue
                x, y = self.project_point(lon, lat, center_lon, center_lat, scale)
                points.append((x, y))

        if len(points) >= 2:
            try:
                # Use provided width, scaled by zoom
                line_width = max(1, min(10, int(width * self.zoom)))
                pygame.draw.lines(self.screen, color, False, points, line_width)
            except:
                pass  # Skip if points are invalid

    def render_polygon(self, coordinates, center_lon, center_lat, scale, fill_color, stroke_color=None, stroke_width=2):
        """Render a Polygon with support for holes (inner rings)"""
        if len(coordinates) == 0:
            return

        # Outer ring (first coordinate array)
        outer_points = []
        for coord in coordinates[0]:
            lon, lat = coord[0], coord[1]
            x, y = self.project_point(lon, lat, center_lon, center_lat, scale)
            outer_points.append((x, y))

        if len(outer_points) >= 3:
            try:
                # Fill outer polygon
                pygame.draw.polygon(self.screen, fill_color, outer_points)

                # Draw holes (inner rings) by filling them with background color
                # In GeoJSON, coordinates[1:] are the holes
                if len(coordinates) > 1:
                    for hole_coords in coordinates[1:]:
                        hole_points = []
                        for coord in hole_coords:
                            lon, lat = coord[0], coord[1]
                            x, y = self.project_point(lon, lat, center_lon, center_lat, scale)
                            hole_points.append((x, y))

                        if len(hole_points) >= 3:
                            # Fill hole with background color to "cut it out"
                            pygame.draw.polygon(self.screen, self.bg_color, hole_points)

                # Draw outline only if stroke color and width explicitly provided (otherwise no borders)
                if stroke_color and stroke_width > 0:
                    outline_width = max(1, min(10, int(stroke_width * self.zoom)))
                    pygame.draw.polygon(self.screen, stroke_color, outer_points, outline_width)
                    if len(coordinates) > 1:
                        for hole_coords in coordinates[1:]:
                            hole_points = []
                            for coord in hole_coords:
                                lon, lat = coord[0], coord[1]
                                x, y = self.project_point(lon, lat, center_lon, center_lat, scale)
                                hole_points.append((x, y))
                            if len(hole_points) >= 3:
                                pygame.draw.polygon(self.screen, stroke_color, hole_points, outline_width)
            except:
                pass  # Skip if polygon is invalid

    def parse_color(self, color_str):
        """Parse a color string (hex or named) to RGB tuple"""
        if isinstance(color_str, str):
            # Handle hex colors
            if color_str.startswith('#'):
                color_str = color_str.lstrip('#')
                if len(color_str) == 6:
                    r = int(color_str[0:2], 16)
                    g = int(color_str[2:4], 16)
                    b = int(color_str[4:6], 16)
                    return (r, g, b)
            # Handle named colors (basic set)
            color_map = {
                'black': (0, 0, 0),
                'white': (255, 255, 255),
                'red': (255, 0, 0),
                'green': (0, 255, 0),
                'blue': (0, 0, 255),
                'gray': (128, 128, 128),
                'grey': (128, 128, 128),
            }
            return color_map.get(color_str.lower(), (128, 128, 128))
        return (128, 128, 128)

    def apply_opacity(self, color, opacity):
        """Apply opacity to a color by blending with background"""
        # Blend with background color
        bg = self.bg_color
        r = int(color[0] * opacity + bg[0] * (1 - opacity))
        g = int(color[1] * opacity + bg[1] * (1 - opacity))
        b = int(color[2] * opacity + bg[2] * (1 - opacity))
        return (r, g, b)

    def project_point(self, lon, lat, center_lon, center_lat, scale):
        """Project lat/lon to screen coordinates with proper aspect ratio"""
        # Equirectangular projection with latitude correction
        lat_correction = math.cos(math.radians(center_lat))

        # Apply the same scale to both axes, with latitude correction for longitude
        x = (lon - center_lon) * lat_correction * scale + self.width / 2 + self.camera_x
        y = -(lat - center_lat) * scale + self.height / 2 + self.camera_y  # Negative because screen Y is inverted

        # Clamp to reasonable values to prevent pygame from hanging
        # Pygame can't handle coordinates beyond ~32000 pixels
        x = max(-10000, min(10000, x))
        y = max(-10000, min(10000, y))

        return int(x), int(y)

    def get_geojson_bounds(self):
        """Calculate bounding box of GeoJSON data"""
        if not self.geojson_data or 'features' not in self.geojson_data:
            return None

        min_lon = float('inf')
        min_lat = float('inf')
        max_lon = float('-inf')
        max_lat = float('-inf')

        for feature in self.geojson_data['features']:
            if 'geometry' not in feature:
                continue

            coords = self.extract_coordinates(feature['geometry'])
            for lon, lat in coords:
                min_lon = min(min_lon, lon)
                max_lon = max(max_lon, lon)
                min_lat = min(min_lat, lat)
                max_lat = max(max_lat, lat)

        if min_lon == float('inf'):
            return None

        return (min_lon, min_lat, max_lon, max_lat)

    def extract_coordinates(self, geometry):
        """Extract all coordinates from a geometry"""
        coords = []

        if geometry['type'] == 'Point':
            coords.append((geometry['coordinates'][0], geometry['coordinates'][1]))
        elif geometry['type'] == 'LineString':
            for coord in geometry['coordinates']:
                coords.append((coord[0], coord[1]))
        elif geometry['type'] == 'Polygon':
            for ring in geometry['coordinates']:
                for coord in ring:
                    coords.append((coord[0], coord[1]))
        elif geometry['type'] == 'MultiPolygon':
            for polygon in geometry['coordinates']:
                for ring in polygon:
                    for coord in ring:
                        coords.append((coord[0], coord[1]))

        return coords

    def render_no_data(self):
        """Render message when no GeoJSON data available"""
        msg1 = self.title_font.render("No airport data available", True, self.text_color)
        msg2 = self.info_font.render(f"Expected file: {self.scenario.geojson_file}", True, (150, 150, 150))

        msg1_rect = msg1.get_rect(center=(self.width // 2, self.height // 2 - 20))
        msg2_rect = msg2.get_rect(center=(self.width // 2, self.height // 2 + 20))

        self.screen.blit(msg1, msg1_rect)
        self.screen.blit(msg2, msg2_rect)
