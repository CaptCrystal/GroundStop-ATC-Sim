"""
Convert SVG files to PNG for use in pygame
Requires: pip install cairosvg
Alternative: Use an online converter or image editing software
"""

try:
    import cairosvg
    
    # Convert airplane icon
    cairosvg.svg2png(
        url='data/images/airplane_icon_norm.svg',
        write_to='data/images/airplane_icon_norm.png',
        output_width=64,
        output_height=64
    )
    print("✓ Converted airplane_icon_norm.svg to PNG")
    
    # Convert settings icon
    cairosvg.svg2png(
        url='data/images/settings-icon.svg',
        write_to='data/images/settings-icon.png',
        output_width=64,
        output_height=64
    )
    print("✓ Converted settings-icon.svg to PNG")
    
    print("\nAll SVG files converted successfully!")
    print("You can now run the simulation.")
    
except ImportError:
    print("ERROR: cairosvg not installed")
    print("\nOption 1: Install cairosvg")
    print("  pip install cairosvg")
    print("\nOption 2: Convert manually")
    print("  - Use an online converter: https://convertio.co/svg-png/")
    print("  - Or use image editing software (Inkscape, GIMP, etc.)")
    print("\nFiles to convert:")
    print("  1. data/images/airplane_icon_norm.svg → airplane_icon_norm.png")
    print("  2. data/images/settings-icon.svg → settings-icon.png")
    
except Exception as e:
    print(f"ERROR: {e}")
    print("\nTry converting manually using:")
    print("  - Online converter: https://convertio.co/svg-png/")
    print("  - Inkscape: File > Export PNG Image")
    print("  - GIMP: Open SVG, Export as PNG")
