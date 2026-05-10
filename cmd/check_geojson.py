import json

with open('data/airports/SGF.geojson', 'r') as f:
    data = json.load(f)

print(f"Total features: {len(data['features'])}")
print("\nFirst 5 features:")
for i, feature in enumerate(data['features'][:5]):
    geom_type = feature['geometry']['type']
    props = feature.get('properties', {})
    coords = feature['geometry']['coordinates']
    
    print(f"\nFeature {i}:")
    print(f"  Type: {geom_type}")
    print(f"  Properties: {props}")
    
    if geom_type == 'LineString' and len(coords) > 0:
        print(f"  Coords sample: {coords[0]}")
    elif geom_type == 'Polygon' and len(coords) > 0 and len(coords[0]) > 0:
        print(f"  Coords sample: {coords[0][0]}")
