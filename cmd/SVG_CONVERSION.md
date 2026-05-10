# SVG to PNG Conversion Guide

The simulation uses PNG images for icons because pygame doesn't natively support SVG files.

## Quick Start

### Option 1: Automatic Conversion (Recommended)

1. Install cairosvg:
   ```bash
   pip install cairosvg
   ```

2. Run the converter:
   ```bash
   python convert_svg_to_png.py
   ```

### Option 2: Online Conversion

1. Go to https://convertio.co/svg-png/ or https://cloudconvert.com/svg-to-png
2. Upload these files:
   - `data/images/airplane_icon_norm.svg`
   - `data/images/settings-icon.svg`
3. Download the PNG versions
4. Save them as:
   - `data/images/airplane_icon_norm.png`
   - `data/images/settings-icon.png`

### Option 3: Image Editing Software

**Using Inkscape (Free):**
1. Open the SVG file
2. File → Export PNG Image
3. Set width/height to 64px
4. Export

**Using GIMP (Free):**
1. Open the SVG file
2. Set import size to 64x64
3. File → Export As → PNG

**Using Adobe Illustrator:**
1. Open the SVG file
2. File → Export → Export As
3. Choose PNG format
4. Set resolution to 64x64

## Files to Convert

| SVG File | PNG Output | Used For |
|----------|------------|----------|
| `airplane_icon_norm.svg` | `airplane_icon_norm.png` | Aircraft icons on map |
| `settings-icon.svg` | `settings-icon.png` | Settings gear in top menu |

## Fallback Behavior

If PNG files are not found, the simulation will:
- **Aircraft**: Use simple white triangle shape
- **Settings**: Draw gear icon programmatically using circles

The simulation will work without conversion, but PNG icons look more professional!
