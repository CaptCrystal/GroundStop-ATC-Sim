#!/usr/bin/env python3
"""
Analyze arrival logs to debug runway exit issues
"""

import json
import os
from datetime import datetime

def analyze_arrivals():
    """Analyze the arrivals.log file to identify issues"""
    log_file = "logs/arrivals.log"
    
    if not os.path.exists(log_file):
        print(f"❌ No arrival log found at {log_file}")
        print("Run the simulation first to generate arrival logs.")
        return
    
    print(f"📊 Analyzing arrival log: {log_file}")
    print("=" * 60)
    
    # Read all log entries
    entries = []
    with open(log_file, 'r') as f:
        for line in f:
            try:
                entry = json.loads(line.strip())
                entries.append(entry)
            except json.JSONDecodeError:
                continue
    
    if not entries:
        print("❌ No valid log entries found")
        return
    
    # Group by callsign
    by_callsign = {}
    for entry in entries:
        callsign = entry['callsign']
        if callsign not in by_callsign:
            by_callsign[callsign] = []
        by_callsign[callsign].append(entry)
    
    print(f"📈 Total aircraft: {len(by_callsign)}")
    print(f"📝 Total events: {len(entries)}")
    print()
    
    # Analyze each aircraft
    problem_aircraft = []
    
    for callsign, events in by_callsign.items():
        print(f"✈️  {callsign} ({events[0]['aircraft_type']})")
        
        # Sort events by timestamp
        events.sort(key=lambda x: x['timestamp'])
        
        # Track key events
        landing_start = None
        exit_search = None
        exit_found = None
        no_exit = None
        holdshort = None
        
        for event in events:
            event_type = event['event']
            timestamp = event['timestamp']
            
            if event_type == 'LANDING_START':
                landing_start = event
                print(f"   🛬 Landed at {event['data']['runway']} (speed: {event['data']['speed']:.1f} kts)")
            
            elif event_type == 'EXIT_SEARCH_START':
                exit_search = event
                distance = event['data']['distance']
                print(f"   🔍 Started exit search at {distance:.0f}m")
            
            elif event_type == 'EXIT_FOUND':
                exit_found = event
                taxiway = event['data']['taxiway']
                distance = event['data']['distance_ahead']
                print(f"   ✅ Found exit: {taxiway} ({distance:.0f}m ahead)")
            
            elif event_type == 'NO_EXIT_FOUND':
                no_exit = event
                distance = event['data']['landing_distance']
                checked = event['data']['taxiways_checked']
                intersections = event['data'].get('intersections_found', 0)
                print(f"   ❌ No exit found at {distance:.0f}m (checked {checked} taxiways, {intersections} intersections)")
            
            elif event_type == 'HOLDING_SHORT':
                holdshort = event
                runway = event['data']['runway']
                taxiway = event['data']['taxiway']
                total_dist = event['data']['total_distance']
                print(f"   🛑 Holding short of {runway} at {taxiway} (total: {total_dist:.0f}m)")
        
        # Identify problems
        problems = []
        
        if landing_start and not exit_search:
            problems.append("Never started exit search")
        
        if exit_search and not exit_found and not no_exit:
            problems.append("Exit search incomplete")
        
        if exit_search and not exit_found and no_exit:
            problems.append("No suitable exit found")
        
        if exit_found and not holdshort:
            problems.append("Found exit but didn't reach hold short")
        
        if problems:
            problem_aircraft.append((callsign, problems))
            print(f"   ⚠️  ISSUES: {', '.join(problems)}")
        
        print()
    
    # Summary
    print("=" * 60)
    print("🚨 PROBLEM SUMMARY")
    print("=" * 60)
    
    if problem_aircraft:
        print(f"❌ {len(problem_aircraft)} aircraft had issues:")
        for callsign, problems in problem_aircraft:
            print(f"   • {callsign}: {', '.join(problems)}")
    else:
        print("✅ All aircraft completed arrival procedure successfully!")
    
    print()
    print("📋 Common issues to check:")
    print("   • Airport data missing taxiways")
    print("   • Taxiway geometry not intersecting runway")
    print("   • Detection range too small")
    print("   • Aircraft stopping before exit search starts")

if __name__ == "__main__":
    analyze_arrivals()
