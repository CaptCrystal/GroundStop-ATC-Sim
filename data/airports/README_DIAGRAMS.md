# Airport Diagram Guide

## Overview

Airport diagrams are automatically displayed in the airport selection menu's details panel when specified in the scenario file.

## Adding Airport Diagrams

### Configuration Method

Airport diagrams are configured in `scenarios.json` using the `diagram` field:

```json
{
  "airports": [
    {
      "code": "KSGF",
      "name": "Springfield-Branson National Airport",
      "diagram": "data/airports/SGF/SGF_diagram.png",
      ...
    }
  ]
}
```

### Recommended Location

**Best practice:** Place diagrams in the airport's folder:
```
data/airports/SGF/SGF_diagram.png
```

This keeps all airport-related files organized together.

## Image Requirements

### Format
- **File type:** PNG (recommended for transparency support)
- **Alternative:** JPG, BMP (also supported by pygame)

### Size Recommendations
- **Ideal width:** 800-1200 pixels
- **Ideal height:** 600-900 pixels
- **Aspect ratio:** Any (will be scaled proportionally)
- **Max display size:** 250px height in menu

### Quality Tips
1. **Use official FAA diagrams** when possible
2. **High contrast** - dark lines on light background work best
3. **Clear labels** - runway numbers and taxiway letters should be readable
4. **Remove clutter** - focus on runways, taxiways, and key features

## Example: Adding KSGF Diagram

1. **Download** the official airport diagram (FAA website)
2. **Save as PNG:** `SGF_diagram.png`
3. **Place in folder:** `data/airports/SGF/SGF_diagram.png`
4. **Add to scenarios.json:**
   ```json
   {
     "code": "KSGF",
     "diagram": "data/airports/SGF/SGF_diagram.png",
     ...
   }
   ```
5. **Done!** The diagram will appear in the menu

## Display Behavior

### Automatic Scaling
- Diagrams are automatically scaled to fit the panel
- Aspect ratio is always preserved
- Images are never upscaled (max 1:1 ratio)
- Centered horizontally in the panel

### Placement
The diagram appears in the details panel:
1. After airport description
2. Before "Initial Conditions" section
3. With a dark background and border
4. Labeled "Airport Diagram"

### Fallback
If no diagram is specified or the file doesn't exist, the section is simply skipped - no error or placeholder shown.

## Obtaining Airport Diagrams

### Official Sources
1. **FAA Digital Products:** https://www.faa.gov/air_traffic/flight_info/aeronav/digital_products/
2. **AirNav.com:** Airport information and diagrams
3. **SkyVector:** Free aeronautical charts

### Creating Custom Diagrams
You can create simplified diagrams showing:
- Runway layout
- Taxiway network
- Gate positions
- Key navigation points

Use tools like:
- Inkscape (free vector graphics)
- GIMP (free image editor)
- Adobe Illustrator/Photoshop

## Troubleshooting

### Diagram Not Showing
1. **Check scenarios.json** - Ensure the `diagram` field is set correctly
2. **Check file path** - Verify the path in scenarios.json matches the actual file location
3. **Check file exists** - Make sure the diagram file actually exists at the specified path
4. **Check file format** - PNG is recommended
5. **Check console** - Look for error messages about loading

### Diagram Too Small/Large
- The system automatically scales to fit
- If too small: Use a higher resolution source image
- If too large: The system will scale down automatically

### Poor Quality
- Use higher resolution source image
- Ensure good contrast
- Consider using vector graphics converted to high-res PNG

## Example Directory Structure

```
data/
├── airports/
│   ├── KSGF/
│   │   ├── KSGF_diagram.png          ← Diagram here
│   │   ├── SGF_Runway.geojson
│   │   ├── SGF_Taxiways.geojson
│   │   └── SGF_Apron.geojson
│   ├── KORD/
│   │   ├── KORD_diagram.png          ← Diagram here
│   │   └── ...
│   └── KLAX/
│       ├── KLAX_diagram.png          ← Diagram here
│       └── ...
└── diagrams/                          ← Alternative location
    ├── KSGF.png
    ├── KORD.png
    └── KLAX.png
```

## Tips for Best Results

1. **Use official diagrams** - Most accurate and professional
2. **Crop appropriately** - Remove unnecessary margins
3. **Optimize file size** - Compress PNG without losing quality
4. **Test in-game** - Check how it looks in the actual menu
5. **Keep updated** - Update diagrams when airport layout changes
