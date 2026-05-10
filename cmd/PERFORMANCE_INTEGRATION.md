# Aircraft Performance Integration

## ✅ What Was Integrated

Your performance data from `aircraft.json` is now fully integrated into the aircraft system! Here's what's being used:

### Current Performance Parameters

| Parameter | JSON Field | Usage |
|-----------|------------|-------|
| **Taxi Speed** | `taxi_speed_kt` | Maximum taxi speed in knots |
| **Taxi Acceleration** | `taxi_accel_m_s2` | Acceleration during taxi (m/s²) |
| **Taxi Braking** | `taxi_brake_m_s2` | Deceleration during braking (m/s²) |
| **Turn Rate** | `turn_rate_deg_s` | Maximum turn rate (degrees/second) |
| **Cruise Speed** | `cruise_speed_kt` | Used to calculate rotation speed for takeoff |
| **Climb Rate** | `climb_rate_fpm` | Rate of climb after takeoff (feet/minute) |
| **Service Ceiling** | `service_ceiling_ft` | Used to calculate initial climb altitude |

### How It Works

**1. Aircraft Initialization (`aircraft.py` lines 100-124)**
- Loads performance database from `aircraft.json` on first use
- Looks up aircraft type (e.g., "B738", "A320", "C172")
- Applies performance parameters with realistic variation (±10-15%)
- Falls back to safe defaults if aircraft type not found

**2. Taxi Operations**
```python
# Each aircraft now taxis at its realistic speed
B738:  ~22 kts with 0.7 m/s² acceleration, 12°/s turns
C172:  ~12 kts with 1.2 m/s² acceleration, 16°/s turns
B77W:  ~20 kts with 0.6 m/s² acceleration, 10°/s turns
```

**3. Takeoff Performance**
- **Rotation Speed (V_r)**: Calculated from cruise speed
  - Large jets (cruise > 400 kts): ~35% of cruise speed
  - Smaller aircraft: ~50% of cruise speed
- **Climb Rate**: Uses `climb_rate_fpm` from database
- **Initial Altitude**: 7.5% of service ceiling (min 3000 ft)

**4. Acceleration Scaling**
- Taxi: Base acceleration from database
- Takeoff roll: 3x taxi acceleration (realistic thrust settings)

## 📋 Recommended Additions

To make your simulation even more realistic, consider adding these parameters:

### Landing Performance
```json
{
  "icao_code": "B738",
  "landing_speed_kt": 130,           // Approach speed (V_ref)
  "landing_decel_m_s2": 2.5,         // Braking deceleration on landing
  "landing_roll_distance_m": 1800,   // Typical landing roll distance
}
```

### Weight & Configuration
```json
{
  "icao_code": "B738",
  "mtow_kg": 79015,                  // Already have this! ✓
  "typical_taxi_weight_kg": 70000,   // Affects acceleration
  "wing_loading_kg_m2": 650          // Affects takeoff/landing
}
```

### Engine Performance
```json
{
  "icao_code": "B738",
  "thrust_per_engine_kn": 121,       // Static thrust
  "engine_spool_time_s": 8,          // Time to full power
  "reverse_thrust_available": true    // For landing
}
```

### Noise & Wake
```json
{
  "icao_code": "B738",
  "wake_turbulence_category": "M",   // Heavy/Medium/Light
  "noise_category": 3,                // For noise abatement
  "separation_required_nm": 3.0       // Wake separation
}
```

### Ground Maneuvering
```json
{
  "icao_code": "B738",
  "nose_wheel_steering_angle": 70,   // Max steering angle
  "turning_radius_m": 25,             // Minimum turn radius
  "wingspan_clearance_m": 18          // Required clearance
}
```

## 🎯 Priority Recommendations

**High Priority** (would improve realism immediately):
1. ✅ **Taxi performance** - Already done!
2. ✅ **Takeoff performance** - Already done!
3. `landing_speed_kt` - For approach speeds
4. `landing_decel_m_s2` - For landing rollout
5. `wake_turbulence_category` - For ATC separation

**Medium Priority** (nice to have):
- `thrust_per_engine_kn` - For more accurate acceleration
- `turning_radius_m` - For taxi path validation
- `landing_roll_distance_m` - For exit selection

**Low Priority** (future enhancements):
- Detailed engine spool times
- Wing loading calculations
- Noise categories

## 🔍 Testing Your Performance Data

Run the simulator and watch for these log messages:
```
[EDV7] Performance: 22.1 kts, accel=1.42 kts/s, turn=12.3°/s
[EDV7] Takeoff performance: V_r=158 kts, initial climb to 3075 ft
```

This confirms your performance data is being loaded and applied correctly!

## 📝 Example: Full Performance Profile

Here's what a complete aircraft profile could look like:

```json
{
  "icao_code": "B738",
  "name": "Boeing 737-800",
  
  // Existing data (already in your JSON)
  "cruise_speed_kt": 450,
  "climb_rate_fpm": 2900,
  "service_ceiling_ft": 41000,
  "mtow_kg": 79015,
  
  // Taxi performance (already added!)
  "taxi_speed_kt": 22,
  "taxi_accel_m_s2": 0.7,
  "taxi_brake_m_s2": 1.3,
  "turn_rate_deg_s": 12,
  
  // Landing performance (recommended)
  "landing_speed_kt": 130,
  "landing_decel_m_s2": 2.5,
  
  // Additional details (optional)
  "wake_category": "M",
  "thrust_per_engine_kn": 121
}
```

## 🚀 What Happens Now

1. **Every aircraft spawns** with type-specific performance
2. **Small GA aircraft** taxi slower, turn sharper (C172: 12 kts, 16°/s)
3. **Large jets** taxi faster, turn wider (B77W: 20 kts, 10°/s)  
4. **Takeoff speeds** match real-world values (~150 kts for B738, ~60 kts for C172)
5. **Climb rates** are aircraft-specific (2900 fpm for B738 vs higher for fighters)

Your simulator is now much more realistic! Each aircraft type behaves uniquely based on its actual performance characteristics.
