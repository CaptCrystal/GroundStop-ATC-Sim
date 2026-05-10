"""
Test script for scenario manager
"""
from src.core.scenario_manager import get_scenario_manager


def main():
    print("=" * 60)
    print("AsdeSim Scenario Manager Test")
    print("=" * 60)
    
    # Get the scenario manager
    manager = get_scenario_manager()
    
    print(f"\n{manager}")
    print(f"Version: {manager.get_version()}")
    
    # List all scenarios
    print("\n" + "=" * 60)
    print("ALL SCENARIOS")
    print("=" * 60)
    for scenario in manager.get_all_scenarios():
        print(f"\n{scenario.name}")
        print(f"  ID: {scenario.id}")
        print(f"  Airport: {scenario.airport_code} - {scenario.airport_name}")
        print(f"  Difficulty: {scenario.difficulty}")
        print(f"  Duration: {scenario.duration_minutes} minutes")
        print(f"  Description: {scenario.description}")
        print(f"  GeoJSON: {scenario.geojson_file}")
        print(f"  Tags: {', '.join(scenario.tags)}")
    
    # List all airports
    print("\n" + "=" * 60)
    print("ALL AIRPORTS")
    print("=" * 60)
    for airport in manager.get_all_airports():
        print(f"\n{airport.code} - {airport.name}")
        print(f"  Location: {airport.city}, {airport.country}")
        print(f"  Elevation: {airport.elevation_ft} ft")
        print(f"  Coordinates: {airport.coordinates['lat']}, {airport.coordinates['lon']}")
        print(f"  Runways: {airport.get_runway_count()}")
        longest = airport.get_longest_runway()
        if longest:
            print(f"  Longest: {longest['name']} ({longest['length_ft']} ft)")
    
    # Test filtering
    print("\n" + "=" * 60)
    print("DIFFICULTY FILTERING")
    print("=" * 60)
    for difficulty in manager.get_difficulties():
        scenarios = manager.get_scenarios_by_difficulty(difficulty)
        print(f"{difficulty.upper()}: {len(scenarios)} scenarios")
    
    # Test search
    print("\n" + "=" * 60)
    print("SEARCH TEST: 'rush'")
    print("=" * 60)
    results = manager.search_scenarios("rush")
    for scenario in results:
        print(f"  - {scenario.name}")
    
    # Test specific scenario
    print("\n" + "=" * 60)
    print("SPECIFIC SCENARIO: kjfk_rush_hour")
    print("=" * 60)
    scenario = manager.get_scenario_by_id("kjfk_rush_hour")
    if scenario:
        print(f"Name: {scenario.name}")
        print(f"Time: {scenario.get_initial_time()}")
        print(f"Weather: {scenario.get_weather()}")
        print(f"Active Runways: {', '.join(scenario.get_active_runways())}")
        wind = scenario.get_wind_info()
        print(f"Wind: {wind['direction']}° at {wind['speed_knots']} knots")
        print(f"Initial Aircraft: {scenario.get_initial_aircraft_count()}")
        print(f"Spawn Rate: {scenario.get_spawn_rate()}/hour")
        print(f"\nObjectives:")
        for i, obj in enumerate(scenario.objectives, 1):
            print(f"  {i}. {obj}")
    
    print("\n" + "=" * 60)
    print("Test Complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
