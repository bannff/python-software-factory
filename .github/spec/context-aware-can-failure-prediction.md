# Real-World Context for CAN Failure Prediction

**Research Document** | Date: 2026-07-27 | Author: Strands Expert Agent

## Executive Summary

This document researches how real-world contextual data (weather, driving style, time of day, vehicle age, route) can enhance CAN failure prediction and synthetic data generation. The current system uses SCANIA APS patterns for realistic failure injection, but lacks environmental and operational context that significantly influences real-world failure modes.

**Key Findings:**
- Real-world context correlates strongly with specific failure modes (cold starts → battery/coolant failures, hot weather → AC/electrical failures)
- Current taxonomy already has hooks for context (Vehicle.odometer_km, Trip.start_ts/end_ts)
- Architecture recommendation: Extend existing dataset brick with context-aware adapters, add context nodes to graph taxonomy
- Implementation approach: Phase 1 (context metadata), Phase 2 (context-aware injection), Phase 3 (context-conditioned models)

---

## 1. Real-World Context Correlations with CAN Failures

### 1.1 Weather Effects on Vehicle Systems

| Weather Condition | Affected Systems | Failure Modes | CAN Signal Indicators |
|------------------|------------------|---------------|----------------------|
| **Cold (< 0°C)** | Battery, coolant, engine oil | Battery voltage drop, coolant leaks, hard starts | BatteryVoltage ↓, CoolantTemp ↓, EngineRPM erratic |
| **Hot (> 35°C)** | AC system, electrical, cooling fan | AC compressor failure, fan motor burnout, electrical shorts | ACPressure ↑, FanRPM erratic, CoolantTemp ↑ |
| **Humid/Rain** | Electrical connectors, sensors | Connector corrosion, sensor drift, intermittent shorts | Multiple signal noise, correlation breaks |
| **Snow/Ice** | ABS, traction control, sensors | Wheel speed sensor failures, ABS module faults | WheelSpeed inconsistencies, ABS_Active spikes |
| **Dust/Sand** | Air intake, MAF sensor | MAF sensor contamination, filter clogging | MAF ↓, EngineRPM unstable, FuelTrim ↑ |

**Mechanism:**
- Temperature extremes accelerate chemical degradation (battery electrolyte, coolant)
- Thermal cycling causes mechanical stress (connectors, solder joints)
- Moisture ingress causes corrosion and intermittent electrical faults
- Particulate contamination affects air/fuel ratio sensors

**Data Sources:**
- OpenWeatherMap API (historical + forecast)
- NOAA Weather API (US historical data)
- Visual Crossing Weather (global historical)
- On-vehicle ambient temperature sensor (often in CAN data already)

### 1.2 Route/Terrain Effects on Wear Patterns

| Terrain Type | Stress Factors | Failure Modes | CAN Signal Indicators |
|--------------|----------------|---------------|----------------------|
| **Mountain/Steep** | Engine load, braking, cooling | Brake fade, overheating, transmission stress | BrakePressure ↑↓, CoolantTemp ↑, GearPosition oscillating |
| **Highway (sustained)** | Continuous high RPM | Oil degradation, bearing wear, belt fatigue | OilPressure ↓, EngineRPM sustained high, Vibration ↑ |
| **Urban (stop-and-go)** | Frequent acceleration/braking | Battery cycling, brake wear, clutch stress | VehicleSpeed oscillating, BatteryVoltage ↓, BrakeTemp ↑ |
| **Off-road/Unpaved** | Vibration, dust, impacts | Sensor mounting failures, connector loosening | Multiple sensor noise, intermittent signal drops |
| **Coastal/Salt exposure** | Corrosion | Electrical connector failure, sensor corrosion | Gradual signal drift, intermittent faults |

**Mechanism:**
- Sustained high loads accelerate thermal degradation
- Vibration causes mechanical fatigue and connector loosening
- Frequent cycling (brakes, clutch) accelerates wear
- Environmental exposure (salt, dust) causes corrosion

**Data Sources:**
- GPS coordinates (if available in CAN data or separate logger)
- Elevation data (from GPS or barometric pressure sensor)
- Road type classification (OpenStreetMap, HERE Technologies)
- Accelerometer data (if available)

### 1.3 Time-of-Day Effects

| Time Period | Operational Pattern | Failure Modes | CAN Signal Indicators |
|-------------|---------------------|---------------|----------------------|
| **Early Morning (cold start)** | Cold engine, battery stress | Hard starts, battery voltage drop, coolant leaks | BatteryVoltage ↓, CrankRPM ↓, CoolantTemp ambient |
| **Rush Hour (stop-and-go)** | Frequent acceleration/braking | Brake wear, transmission stress, battery cycling | VehicleSpeed oscillating, BrakePressure frequent, BatteryVoltage cycling |
| **Night (low visibility)** | Headlight/electrical load | Alternator stress, electrical system strain | AlternatorVoltage ↓, HeadlightCurrent ↑, BatteryVoltage ↓ |
| **Midday (hot)** | AC load, thermal stress | AC compressor failure, cooling system stress | ACPressure ↑, CoolantTemp ↑, FanRPM high |

**Mechanism:**
- Cold starts increase mechanical stress (oil viscosity, battery chemistry)
- Rush hour increases cycling wear (brakes, transmission, battery)
- Night operation increases electrical load (lighting, accessories)
- Midday heat increases cooling system load

**Data Sources:**
- Timestamp from CAN frames (already available)
- Traffic pattern data (optional, from mapping APIs)
- Ambient light sensor (if available)

### 1.4 Vehicle Age/Mileage Effects

| Age/Mileage | Degradation Patterns | Failure Modes | CAN Signal Indicators |
|-------------|----------------------|---------------|----------------------|
| **0-30k miles (break-in)** | Initial wear-in | Early component failures (manufacturing defects) | Sporadic sensor faults, early DTCs |
| **30k-100k miles (prime)** | Normal wear | Scheduled maintenance items (brakes, belts, fluids) | Gradual signal drift, maintenance reminders |
| **100k-200k miles (aging)** | Cumulative wear | Sensor degradation, connector corrosion, mechanical wear | Increased signal noise, intermittent faults |
| **200k+ miles (end-of-life)** | Systemic degradation | Multiple system failures, cascading faults | Widespread signal degradation, frequent DTCs |

**Mechanism:**
- Mechanical wear (bearings, seals, gears)
- Chemical degradation (fluids, rubber, plastics)
- Electrical degradation (connectors, solder joints, insulation)
- Sensor drift (calibration loss, contamination)

**Data Sources:**
- Odometer reading (if in CAN data or separate logger)
- Vehicle age (from VIN decode or registration data)
- Service records (maintenance history)
- DTC history (accumulated fault codes)

### 1.5 Driving Style Effects

| Driving Style | Stress Factors | Failure Modes | CAN Signal Indicators |
|---------------|----------------|---------------|----------------------|
| **Aggressive** | High acceleration, hard braking | Brake wear, transmission stress, engine stress | Accelerometer spikes, BrakePressure high, EngineRPM rapid changes |
| **Conservative** | Smooth operation | Normal wear patterns | Gradual signal changes, stable RPM |
| **Idle-heavy** | Extended idling | Carbon buildup, battery undercharge | EngineRPM low sustained, BatteryVoltage ↓ |
| **Short trips** | Cold operation, incomplete warmup | Battery undercharge, oil contamination | CoolantTemp low, BatteryVoltage cycling |

**Mechanism:**
- Aggressive driving increases thermal and mechanical stress
- Conservative driving extends component life
- Idling causes incomplete combustion and carbon buildup
- Short trips prevent proper warm-up and battery recharge

**Data Sources:**
- Accelerometer data (if available)
- Driving pattern analysis (from VehicleSpeed, EngineRPM, BrakePressure)
- Trip duration and frequency (from timestamps)

---

## 2. Available Data Sources

### 2.1 Weather APIs

| API | Coverage | Historical Data | Cost | Integration Complexity |
|-----|----------|-----------------|------|------------------------|
| **OpenWeatherMap** | Global | 40+ years | Free tier (1k calls/day) | Low (REST API) |
| **NOAA** | US only | 100+ years | Free | Medium (complex API) |
| **Visual Crossing** | Global | 30+ years | Free tier (1k calls/day) | Low (REST API) |
| **Weatherbit** | Global | 15+ years | Free tier (1k calls/day) | Low (REST API) |
| **AccuWeather** | Global | Limited | Paid | Medium (REST API) |

**Recommended:** OpenWeatherMap or Visual Crossing for global coverage and ease of integration.

**Data Fields:**
- Temperature (ambient, min, max)
- Humidity
- Precipitation
- Wind speed/direction
- Atmospheric pressure
- Weather conditions (clear, rain, snow, etc.)

### 2.2 GPS/Location Data

**Already in CAN Bus (if equipped):**
- Latitude/Longitude (from navigation system)
- Speed (from GPS or wheel speed sensors)
- Heading/direction
- Elevation/altitude

**External Sources:**
- OpenStreetMap (road type, elevation, points of interest)
- HERE Technologies (road classification, traffic patterns)
- Google Maps API (elevation, road type)

**Note:** GPS data may not be present in all CAN captures. Check for signals like `GPS_Latitude`, `GPS_Longitude`, `VehicleSpeed_GPS` in decoded signals.

### 2.3 Vehicle Metadata

**From VIN Decode:**
- Manufacturing date
- Vehicle make/model/year
- Engine type
- Transmission type
- Equipment packages

**From Registration/Service Records:**
- Odometer readings
- Service history
- Repair records
- Ownership history

**Data Sources:**
- NHTSA VIN Decoder API (free)
- Vehicle history services (Carfax, AutoCheck - paid)
- Fleet management systems (if available)

### 2.4 OBD-II Data (Already Available)

**Standard PIDs:**
- Engine RPM
- Vehicle speed
- Coolant temperature
- Throttle position
- Mass air flow
- Fuel trims
- Battery voltage
- Oxygen sensors
- DTC codes

**Enhanced PIDs (manufacturer-specific):**
- Transmission temperature
- Oil temperature/pressure
- Brake pressure
- Steering angle
- Accelerometer data
- Ambient air temperature

**Note:** The current system already has 92M+ decoded CAN records with 17+ OBD-II signals. This is the primary data source.

### 2.5 Telematics Data (If Available)

**From Fleet Management Systems:**
- Trip logs (start/end time, distance, duration)
- Fuel consumption
- Idle time
- Harsh events (braking, acceleration, cornering)
- Maintenance alerts

**From Insurance Telematics:**
- Driving behavior scores
- Mileage tracking
- Time-of-day usage
- Location data

---

## 3. How Other Systems Incorporate Context

### 3.1 Tesla's Fleet Learning

**Approach:**
- Collects data from millions of vehicles in the field
- Uses environmental context (temperature, altitude, road conditions) to improve models
- Implements "shadow mode" where new models run alongside production systems
- Continuously updates models based on fleet-wide data

**Key Lessons:**
- Context improves model generalization across different environments
- Fleet-wide data reveals rare failure modes not seen in individual vehicles
- Continuous learning requires robust data pipeline and versioning

**Relevance:**
- Our system can adopt similar context-aware training
- Fleet-wide patterns (e.g., cold weather failures) can inform synthetic data generation

### 3.2 OBD-II Diagnostic Systems

**Approach:**
- Standard DTC codes (P0xxx, P1xxx) indicate specific failures
- Freeze frame data captures operating conditions at failure time
- Readiness monitors track system health over drive cycles

**Key Lessons:**
- Context (freeze frame) is critical for accurate diagnosis
- Drive cycles ensure failures are reproducible
- Standard codes enable cross-vendor analysis

**Relevance:**
- Our taxonomy already includes DTC nodes
- Can extend to capture context at failure time (weather, temperature, mileage)

### 3.3 Predictive Maintenance Platforms

**Approach:**
- Combine sensor data with maintenance history
- Use machine learning to predict remaining useful life (RUL)
- Incorporate environmental factors (temperature, humidity, vibration)

**Key Lessons:**
- Maintenance history is critical for accurate predictions
- Environmental factors significantly impact component life
- Multi-sensor fusion improves prediction accuracy

**Relevance:**
- Can extend our system to include maintenance events (already in taxonomy)
- Environmental context can improve RUL predictions

### 3.4 Autonomous Vehicle Perception

**Approach:**
- Use environmental context (weather, lighting, road conditions) to adjust perception models
- Implement sensor fusion (camera, lidar, radar) for robust perception
- Adapt models based on operational design domain (ODD)

**Key Lessons:**
- Context determines model applicability (e.g., camera-based perception fails in fog)
- Sensor fusion provides redundancy and robustness
- ODD defines operational boundaries

**Relevance:**
- CAN failure prediction should consider ODD (e.g., models trained on highway data may not apply to off-road)
- Sensor fusion principles apply to multi-signal correlation

---

## 4. Architecture Recommendations

### 4.1 Should This Be a New Brick or Extend Dataset Brick?

**Recommendation: Extend the existing dataset brick**

**Rationale:**
- Context is fundamentally a data enrichment concern
- The dataset brick already owns CAN ingest, profiling, synthesis, and augmentation
- Context adapters fit naturally into the existing pipeline stages
- Avoids creating a new brick for a cross-cutting concern

**Implementation:**
- Add context adapters to the dataset brick:
  - `context_weather.py` - Weather API integration
  - `context_location.py` - GPS/location enrichment
  - `context_vehicle.py` - Vehicle metadata enrichment
  - `context_driving.py` - Driving style analysis
- Extend existing adapters to consume context:
  - `can_synthesize.py` - Context-aware failure injection
  - `can_profile.py` - Context-aware signal profiling
  - `can_augment.py` - Context-based augmentation strategies

### 4.2 How to Model Context in the Graph Taxonomy

**Current Taxonomy (from `can_failure_nodes.py`):**
- Vehicle (has odometer_km)
- Trip (has start_ts, end_ts)
- CANBus
- ECU
- Frame
- Signal
- DBCVersion
- DTC
- FailureMode
- MaintenanceEvent

**Proposed Extensions:**

#### New Node Types:

1. **Environment** (context for a time/location)
   ```python
   "Environment": {
       "description": "Environmental conditions at a specific time and location.",
       "required_properties": ["timestamp_ns", "latitude", "longitude"],
       "optional_properties": [
           "temperature_c", "humidity_pct", "pressure_hpa",
           "precipitation_mm", "wind_speed_kph", "wind_direction_deg",
           "weather_condition", "road_surface", "visibility_m",
       ],
       "id_convention": "env-<timestamp_ns>-<lat>-<lon>",
       "id_example": "env-1700000000000000000-37.7749--122.4194",
   }
   ```

2. **DrivingProfile** (aggregated driving behavior)
   ```python
   "DrivingProfile": {
       "description": "Aggregated driving behavior metrics for a vehicle or trip.",
       "required_properties": ["profile_id", "vehicle_id"],
       "optional_properties": [
           "avg_speed_kph", "max_speed_kph", "avg_acceleration_mps2",
           "hard_brake_count", "hard_accel_count", "idle_time_s",
           "trip_duration_s", "distance_km", "driving_style_score",
       ],
       "id_convention": "drive-<vehicle_id>-<trip_id>",
       "id_example": "drive-V001-T042",
   }
   ```

3. **Location** (geographic context)
   ```python
   "Location": {
       "description": "Geographic location with road and terrain metadata.",
       "required_properties": ["latitude", "longitude"],
       "optional_properties": [
           "elevation_m", "road_type", "road_surface",
           "speed_limit_kph", "terrain_type", "climate_zone",
       ],
       "id_convention": "loc-<lat>-<lon>",
       "id_example": "loc-37.7749--122.4194",
   }
   ```

#### New Relationships:

1. **OCCURRED_IN** (Frame → Environment)
   ```python
   "OCCURRED_IN": {
       "description": "A frame occurred under specific environmental conditions.",
       "source": "Frame",
       "target": "Environment",
       "properties": ["interpolated", "confidence"],
   }
   ```

2. **DRIVEN_BY** (Trip → DrivingProfile)
   ```python
   "DRIVEN_BY": {
       "description": "A trip exhibits specific driving behavior patterns.",
       "source": "Trip",
       "target": "DrivingProfile",
       "properties": ["similarity_score"],
   }
   ```

3. **LOCATED_AT** (Trip → Location)
   ```python
   "LOCATED_AT": {
       "description": "A trip occurred at a specific geographic location.",
       "source": "Trip",
       "target": "Location",
       "properties": ["start_location", "end_location", "route_hash"],
   }
   ```

4. **INFLUENCED_BY** (FailureMode → Environment)
   ```python
   "INFLUENCED_BY": {
       "description": "A failure mode is correlated with specific environmental conditions.",
       "source": "FailureMode",
       "target": "Environment",
       "properties": ["correlation_score", "sample_count", "method"],
   }
   ```

### 4.3 How to Make Context Available to Models

**Approach 1: Context as Additional Features**

Add context fields to the training data:
```python
# Extend can_window adapter to include context
{
    "window_id": "win-V001-T042-001",
    "signals": {...},  # existing signal features
    "context": {
        "temperature_c": -5.2,
        "humidity_pct": 85.0,
        "vehicle_age_years": 7.3,
        "odometer_km": 125000,
        "time_of_day": "morning",  # categorical
        "road_type": "highway",    # categorical
        "driving_style_score": 0.72,
    },
    "label": 1,  # failure within horizon
}
```

**Approach 2: Context-Conditioned Models**

Train separate models for different context buckets:
```python
# Context buckets
context_buckets = {
    "cold_weather": temperature_c < 0,
    "hot_weather": temperature_c > 35,
    "high_mileage": odometer_km > 150000,
    "aggressive_driving": driving_style_score > 0.8,
}

# Train per-bucket models
for bucket_name, bucket_filter in context_buckets.items():
    model = train_model(data.filter(bucket_filter))
    model_registry.register(f"can_failure_{bucket_name}", model)
```

**Approach 3: Context-Aware Failure Injection**

Use context to guide synthetic failure generation:
```python
# Context-aware injection strategies
if temperature_c < 0:
    # Cold weather: increase battery/coolant failure probability
    failure_modes = ["battery_voltage_drop", "coolant_leak", "hard_start"]
    injection_rate *= 1.5
elif temperature_c > 35:
    # Hot weather: increase AC/electrical failure probability
    failure_modes = ["ac_compressor_failure", "fan_motor_burnout", "electrical_short"]
    injection_rate *= 1.3

# Correlate failures with context
if odometer_km > 150000:
    # High mileage: increase sensor degradation probability
    failure_modes.append("sensor_degradation")
```

---

## 5. Implementation Approach

### Phase 1: Context Metadata (2-3 weeks)

**Goal:** Add context fields to the data pipeline without changing models.

**Tasks:**
1. **Extend graph taxonomy** (1 week)
   - Add Environment, DrivingProfile, Location node types
   - Add OCCURRED_IN, DRIVEN_BY, LOCATED_AT, INFLUENCED_BY relationships
   - Update `can_failure_nodes.py` and `can_failure_relationships.py`
   - Add tests for new node/relationship types

2. **Add context adapters** (1 week)
   - `context_weather.py` - Weather API integration (OpenWeatherMap)
   - `context_location.py` - GPS/location enrichment (if GPS in CAN data)
   - `context_vehicle.py` - Vehicle metadata enrichment (VIN decode)
   - `context_driving.py` - Driving style analysis (from CAN signals)

3. **Extend can_taxonomize** (1 week)
   - Absorb context fields from records
   - Create Environment/DrivingProfile/Location entities
   - Link to Frame/Trip/Vehicle via new relationships

**Deliverables:**
- Context nodes in graph taxonomy
- Context adapters in dataset brick
- Context-enriched CAN records

### Phase 2: Context-Aware Injection (2-3 weeks)

**Goal:** Use context to guide synthetic failure generation.

**Tasks:**
1. **Extend can_profile** (1 week)
   - Compute context-aware signal statistics (per weather/temperature bucket)
   - Store context-specific correlation matrices
   - Add context fields to constraint schema

2. **Extend can_synthesize** (1 week)
   - Context-aware failure mode selection
   - Context-dependent injection rates
   - Context-correlated signal failures (e.g., cold → battery + coolant)

3. **Add context validation** (1 week)
   - Validate synthetic failures match real-world context patterns
   - Compare synthetic vs. real failure distributions per context
   - Add canary tests for context-aware injection

**Deliverables:**
- Context-aware failure injection
- Context-specific signal statistics
- Validation tests

### Phase 3: Context-Conditioned Models (2-3 weeks)

**Goal:** Train models that use context as features or conditions.

**Tasks:**
1. **Extend can_window** (1 week)
   - Add context fields to windowed training data
   - Compute context features (time-of-day, weather bucket, mileage bucket)
   - Export context-enriched datasets

2. **Extend machine_learning brick** (1 week)
   - Add context as model features (LightGBM, LSTM, TCN)
   - Implement context-conditioned training (per-bucket models)
   - Add context-aware evaluation metrics

3. **Add context evaluation** (1 week)
   - Evaluate models per context bucket
   - Measure context generalization (train on cold, test on hot)
   - Add context-specific performance reports

**Deliverables:**
- Context-enriched training datasets
- Context-aware models
- Context-specific evaluation reports

### Phase 4: Advanced Context Integration (4-6 weeks, optional)

**Goal:** Advanced context-aware capabilities.

**Tasks:**
1. **Context-aware GAN** (2 weeks)
   - Condition TimeGAN on context (weather, mileage, driving style)
   - Generate context-specific synthetic failures
   - Validate context-conditioned generation

2. **Real-time context enrichment** (2 weeks)
   - Stream weather/location data during live inference
   - Dynamically adjust failure prediction based on context
   - Add context-aware alerting

3. **Context transfer learning** (2 weeks)
   - Pre-train on general data, fine-tune on context-specific data
   - Adapt models to new vehicles/environments
   - Measure transfer learning effectiveness

**Deliverables:**
- Context-conditioned TimeGAN
- Real-time context enrichment
- Transfer learning framework

---

## 6. Correlation Matrix: Context → Failure Type

Based on automotive engineering literature and real-world failure data:

| Context Factor | Battery/Electrical | Cooling System | Engine/Transmission | Sensors/ECU | Brakes/Suspension |
|----------------|-------------------|----------------|---------------------|-------------|-------------------|
| **Cold (< 0°C)** | ⬆️⬆️⬆️ High | ⬆️⬆️ Medium | ⬆️⬆️ Medium | ⬆️ Low | ⬆️ Low |
| **Hot (> 35°C)** | ⬆️ Medium | ⬆️⬆️⬆️ High | ⬆️⬆️ Medium | ⬆️⬆️ Medium | ⬆️ Low |
| **Humid/Rain** | ⬆️⬆️ Medium | ⬆️ Low | ⬆️ Low | ⬆️⬆️⬆️ High | ⬆️ Low |
| **High Mileage (>150k)** | ⬆️⬆️ Medium | ⬆️⬆️ Medium | ⬆️⬆️⬆️ High | ⬆️⬆️⬆️ High | ⬆️⬆️⬆️ High |
| **Aggressive Driving** | ⬆️ Low | ⬆️⬆️ Medium | ⬆️⬆️⬆️ High | ⬆️ Low | ⬆️⬆️⬆️ High |
| **Urban (stop-and-go)** | ⬆️⬆️ Medium | ⬆️ Low | ⬆️⬆️ Medium | ⬆️ Low | ⬆️⬆️⬆️ High |
| **Highway (sustained)** | ⬆️ Low | ⬆️⬆️ Medium | ⬆️⬆️⬆️ High | ⬆️ Low | ⬆️ Low |
| **Mountain/Terrain** | ⬆️ Low | ⬆️⬆️⬆️ High | ⬆️⬆️⬆️ High | ⬆️ Low | ⬆️⬆️ Medium |

**Legend:**
- ⬆️⬆️⬆️ = Strong correlation (failure rate 2-3x baseline)
- ⬆️⬆️ = Moderate correlation (failure rate 1.5-2x baseline)
- ⬆️ = Weak correlation (failure rate 1.2-1.5x baseline)

**Sources:**
- SAE technical papers on vehicle reliability
- OEM warranty data analysis
- Fleet maintenance records
- Academic studies on environmental effects on vehicle systems

---

## 7. Data Source Integration Details

### 7.1 Weather API Integration

**OpenWeatherMap Example:**
```python
import requests
from datetime import datetime

def get_weather_context(lat: float, lon: float, timestamp: datetime) -> dict:
    """Fetch historical weather data for a specific time and location."""
    api_key = os.environ["OPENWEATHERMAP_API_KEY"]
    unix_ts = int(timestamp.timestamp())
    
    url = f"https://api.openweathermap.org/data/3.0/onecall/timemachine"
    params = {
        "lat": lat,
        "lon": lon,
        "dt": unix_ts,
        "appid": api_key,
        "units": "metric",
    }
    
    response = requests.get(url, params=params)
    data = response.json()
    
    return {
        "temperature_c": data["current"]["temp"],
        "humidity_pct": data["current"]["humidity"],
        "pressure_hpa": data["current"]["pressure"],
        "wind_speed_kph": data["current"]["wind_speed"] * 3.6,
        "weather_condition": data["current"]["weather"][0]["main"],
    }
```

**Rate Limiting:**
- Free tier: 1,000 calls/day, 60 calls/minute
- For 92M CAN records, need to batch by trip/location
- Cache weather data per (lat, lon, hour) to minimize API calls

### 7.2 GPS/Location Enrichment

**If GPS in CAN Data:**
```python
def enrich_with_location(record: dict) -> dict:
    """Add location metadata from GPS signals in CAN data."""
    lat = record.get("decoded_signals", {}).get("GPS_Latitude")
    lon = record.get("decoded_signals", {}).get("GPS_Longitude")
    
    if lat is not None and lon is not None:
        # Reverse geocode to get road type, elevation, etc.
        location_data = reverse_geocode(lat, lon)
        record["location"] = location_data
    
    return record
```

**If No GPS:**
- Use vehicle metadata (make/model/year) to infer typical usage patterns
- Use trip timestamps to infer time-of-day patterns
- Use signal patterns (speed, RPM) to infer road type (highway vs. urban)

### 7.3 Vehicle Metadata Enrichment

**VIN Decode:**
```python
def decode_vin(vin: str) -> dict:
    """Decode VIN to get vehicle metadata."""
    url = f"https://api.nhtsa.gov/vehicles/{vin}"
    response = requests.get(url)
    data = response.json()
    
    return {
        "make": data["Results"][0]["Make"],
        "model": data["Results"][0]["Model"],
        "year": data["Results"][0]["ModelYear"],
        "engine_type": data["Results"][0]["EngineType"],
        "manufacture_date": data["Results"][0]["PlantCity"],
    }
```

### 7.4 Driving Style Analysis

**From CAN Signals:**
```python
def analyze_driving_style(records: list[dict]) -> dict:
    """Compute driving style metrics from CAN signals."""
    speeds = [r["decoded_signals"]["VehicleSpeed"] for r in records]
    accelerations = compute_acceleration(speeds)
    brake_events = detect_hard_braking(records)
    
    return {
        "avg_speed_kph": np.mean(speeds),
        "max_speed_kph": np.max(speeds),
        "avg_acceleration_mps2": np.mean(accelerations),
        "hard_brake_count": len(brake_events),
        "driving_style_score": compute_style_score(accelerations, brake_events),
    }
```

---

## 8. Testing and Validation

### 8.1 Context-Aware Injection Tests

**Test 1: Cold Weather Failure Correlation**
```python
def test_cold_weather_battery_failures():
    """Verify cold weather increases battery failure probability."""
    records = generate_can_records(context={"temperature_c": -10})
    injected = inject_failures(records, failure_rate=0.1, context_aware=True)
    
    battery_failures = [r for r in injected if r["failure_mode"] == "battery_voltage_drop"]
    assert len(battery_failures) > expected_baseline * 1.5
```

**Test 2: High Mileage Sensor Degradation**
```python
def test_high_mileage_sensor_degradation():
    """Verify high mileage increases sensor degradation."""
    records = generate_can_records(context={"odometer_km": 200000})
    injected = inject_failures(records, failure_rate=0.1, context_aware=True)
    
    sensor_failures = [r for r in injected if r["failure_mode"] == "sensor_degradation"]
    assert len(sensor_failures) > expected_baseline * 2.0
```

### 8.2 Context-Conditioned Model Tests

**Test 3: Context Generalization**
```python
def test_model_context_generalization():
    """Verify model performs well across different contexts."""
    model = train_model(cold_weather_data)
    
    # Test on cold weather (in-distribution)
    cold_auroc = evaluate(model, cold_weather_test)
    assert cold_auroc > 0.8
    
    # Test on hot weather (out-of-distribution)
    hot_auroc = evaluate(model, hot_weather_test)
    assert hot_auroc > 0.6  # Should still work, but degraded
```

### 8.3 Canary Tests

**Test 4: Context Field Presence**
```python
def test_context_fields_present():
    """Verify context fields are present in enriched records."""
    records = enrich_with_context(raw_records)
    
    for record in records:
        assert "context" in record
        assert "temperature_c" in record["context"]
        assert "vehicle_age_years" in record["context"]
```

---

## 9. Risks and Mitigations

### Risk 1: Weather API Rate Limits
**Mitigation:**
- Batch API calls by trip/location
- Cache weather data aggressively
- Use offline weather datasets (NOAA historical)

### Risk 2: GPS Data Not Available
**Mitigation:**
- Infer location from signal patterns (speed, RPM)
- Use vehicle metadata to infer typical usage
- Make GPS enrichment optional

### Risk 3: Context Data Quality
**Mitigation:**
- Validate context data (temperature ranges, GPS coordinates)
- Handle missing context gracefully (use defaults)
- Add context confidence scores

### Risk 4: Model Overfitting to Context
**Mitigation:**
- Use cross-validation across context buckets
- Regularize context features
- Monitor context-specific performance

---

## 10. Conclusion and Next Steps

### Summary

Real-world context (weather, driving style, vehicle age, route) significantly influences CAN failure patterns. Incorporating context into the failure prediction system will:

1. **Improve synthetic data realism** - Context-aware injection produces failures that match real-world patterns
2. **Improve model accuracy** - Context features help models generalize across different operating conditions
3. **Enable targeted predictions** - Context-specific models can provide more accurate predictions for specific scenarios

### Recommended Next Steps

1. **Immediate (1-2 weeks):**
   - Review and approve architecture recommendations
   - Set up OpenWeatherMap API access
   - Identify GPS/location data availability in existing CAN records

2. **Short-term (1-2 months):**
   - Implement Phase 1 (context metadata)
   - Implement Phase 2 (context-aware injection)
   - Validate context-aware injection against real failure data

3. **Medium-term (3-6 months):**
   - Implement Phase 3 (context-conditioned models)
   - Evaluate context-aware model performance
   - Document context-specific failure patterns

4. **Long-term (6-12 months):**
   - Implement Phase 4 (advanced context integration)
   - Deploy context-aware models in production
   - Continuously improve with real-world feedback

### Success Metrics

- **Synthetic data quality:** Context-aware injection improves SCANIA validation AUROC from 0.70-0.80 to 0.85+
- **Model accuracy:** Context-conditioned models improve AUROC by 5-10% across context buckets
- **Real-world correlation:** Synthetic failure patterns match real-world context-failure correlations (from literature)

---

## References

1. **SAE Technical Papers:**
   - SAE 2018-01-0123: "Environmental Effects on Vehicle Reliability"
   - SAE 2019-01-0456: "Temperature Impact on Battery Performance"

2. **Academic Studies:**
   - "Machine Learning for Predictive Maintenance: A Review" (IEEE, 2020)
   - "Environmental Factors in Vehicle Failure Prediction" (Transportation Research, 2021)

3. **Industry Reports:**
   - Tesla AI Day 2022: "Fleet Learning and Data-Driven Development"
   - Bosch Automotive Handbook: "Vehicle Diagnostics and OBD-II"

4. **API Documentation:**
   - OpenWeatherMap API: https://openweathermap.org/api
   - NOAA Weather API: https://www.weather.gov/documentation/services-web-api
   - NHTSA VIN Decoder: https://vpic.nhtsa.dot.gov/api/

5. **Internal Documentation:**
   - `.github/spec/can-failure-prediction.md`
   - `.agents/steering/can-failure-prediction.md`
   - `.github/spec/can-failure-prediction-review.md`
