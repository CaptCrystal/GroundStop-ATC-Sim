# GeoJSON Style Support

The simulation now supports custom styling for GeoJSON features using the `style` property.

## Supported Style Properties

### For Polygons and MultiPolygons:

- **`fillColor`**: Fill color (hex format like `#d3d3d3` or named colors)
- **`fillOpacity`**: Fill opacity (0.0 to 1.0, where 0 is transparent and 1 is opaque)
- **`color`**: Stroke/outline color (hex format like `#808080`)
- **`weight`**: Stroke width in pixels (e.g., `2`)

### For LineStrings:

- **`color`**: Line color (hex format or named colors)
- **`weight`**: Line width in pixels

## Example GeoJSON with Styles

### Polygon with Custom Style:
```json
{
  "type": "Feature",
  "properties": {
    "style": {
      "fillColor": "#d3d3d3",
      "fillOpacity": 0.5,
      "color": "#808080",
      "weight": 2
    }
  },
  "geometry": {
    "type": "Polygon",
    "coordinates": [[[lon1, lat1], [lon2, lat2], ...]]
  }
}
```

### LineString with Custom Style:
```json
{
  "type": "Feature",
  "properties": {
    "style": {
      "color": "#ff0000",
      "weight": 3
    }
  },
  "geometry": {
    "type": "LineString",
    "coordinates": [[lon1, lat1], [lon2, lat2], ...]
  }
}
```

## Supported Color Formats

### Hex Colors:
- `#000000` - Black
- `#ffffff` - White
- `#d3d3d3` - Light gray
- `#808080` - Gray
- `#ff0000` - Red
- `#00ff00` - Green
- `#0000ff` - Blue

### Named Colors:
- `black`, `white`, `red`, `green`, `blue`, `gray`, `grey`

## Default Behavior

If no style is provided, the renderer will use default colors based on:

1. **Feature type** (from properties):
   - `aeroway: "runway"` → Dark gray/black
   - `aeroway: "taxiway"` → Medium gray
   - `aeroway: "apron"` → Light gray
   - `building` → Brown
   - `grass` → Green

2. **Geometry analysis** (for polygons without type):
   - Long, narrow polygons (aspect ratio > 5) → Runway color
   - Other polygons → Apron color

3. **Geometry type**:
   - LineStrings → Taxiway color

## Opacity Blending

When `fillOpacity` is less than 1.0, the fill color is blended with the background color:
- `fillOpacity: 1.0` → Fully opaque (default)
- `fillOpacity: 0.5` → 50% transparent
- `fillOpacity: 0.0` → Fully transparent (invisible)

The blending is done with the simulation background color (`#005c73` - blue-teal).

## Example: Airport Runway

```json
{
  "type": "Feature",
  "properties": {
    "aeroway": "runway",
    "ref": "02/20",
    "style": {
      "fillColor": "#1e1e23",
      "fillOpacity": 1.0,
      "color": "#ffffff",
      "weight": 1
    }
  },
  "geometry": {
    "type": "Polygon",
    "coordinates": [...]
  }
}
```

## Example: Taxiway Centerline

```json
{
  "type": "Feature",
  "properties": {
    "aeroway": "taxiway",
    "ref": "A",
    "style": {
      "color": "#ffff00",
      "weight": 2
    }
  },
  "geometry": {
    "type": "LineString",
    "coordinates": [...]
  }
}
```

## Tips

1. **Use semi-transparent fills** for overlapping features
2. **Use contrasting stroke colors** to make features stand out
3. **Adjust weight** based on feature importance (runways = thicker, taxiways = thinner)
4. **Test visibility** at different zoom levels
