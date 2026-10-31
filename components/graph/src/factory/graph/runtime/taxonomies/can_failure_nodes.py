"""CAN failure-prediction taxonomy node definitions.

Pure data matching ``mcp/docs_taxonomy_ext.py::EXT_NODE_TYPES``.
"""

from __future__ import annotations

CAN_FAILURE_NODE_TYPES: dict = {
    "Vehicle": {
        "description": (
            "A physical vehicle / fleet asset that emits CAN traffic. "
            "Anchor for HAS_ECU, PART_OF_TRIP, and PRECEDES_FAILURE edges."
        ),
        "required_properties": ["vehicle_id", "make", "model", "year"],
        "optional_properties": ["vin", "fleet_id", "odometer_km", "created_at"],
        "id_convention": "vehicle-<vehicle_id>",
        "id_example": "vehicle-V001",
    },
    "Trip": {
        "description": (
            "A contiguous operational slice (drive, ignition cycle, or "
            "maintenance window) bounded by start_ts / end_ts. Episode "
            "boundary for downstream windowing and label assignment."
        ),
        "required_properties": ["trip_id", "vehicle_id", "start_ts", "end_ts"],
        "optional_properties": [
            "odometer_km", "dbc_version", "label_source",
            "label_confidence", "taxonomy_version",
        ],
        "id_convention": "trip-<vehicle_id>-<trip_id>",
        "id_example": "trip-V001-T042",
    },
    "CANBus": {
        "description": (
            "A physical CAN bus / channel on a vehicle. One vehicle may "
            "have multiple buses (powertrain, chassis, body, diag)."
        ),
        "required_properties": ["bus_name", "channel", "baud_rate"],
        "optional_properties": ["bit_timing", "termination", "fd_capable"],
        "id_convention": "canbus-<vehicle_id>-<bus_name>",
        "id_example": "canbus-V001-powertrain",
    },
    "ECU": {
        "description": (
            "An Electronic Control Unit on a CAN bus. The atomic "
            "transmitter / receiver of frames. firmware_version is "
            "required for DBC drift detection."
        ),
        "required_properties": ["ecu_id", "bus_name", "firmware_version"],
        "optional_properties": ["part_number", "supplier", "diagnostic_addr"],
        "id_convention": "ecu-<vehicle_id>-<ecu_id>",
        "id_example": "ecu-V001-ECM",
    },
    "Frame": {
        "description": (
            "A raw Classical CAN or CAN FD frame event. The transport-"
            "level record; decoded signals are enrichment (DBC-dependent)."
        ),
        "required_properties": [
            "timestamp_ns", "arbitration_id", "is_extended", "is_fd",
            "dlc", "frame_type",
        ],
        "optional_properties": [
            "data_bytes", "error_state", "ack_seen", "source_ecu",
            "capture_source", "bus_name", "vehicle_id", "trip_id",
        ],
        "id_convention": "frame-<canonical-frame-sha256>-<duplicate-ordinal>",
        "id_example": "frame-0123456789abcdef-0",
    },
    "Signal": {
        "description": (
            "A DBC-decoded physical signal (RPM, coolant_temp, etc.). "
            "Defined by a DBCVersion node; physical units + bounds are "
            "the agentic labeling input."
        ),
        "required_properties": [
            "signal_name", "unit", "min_value", "max_value",
        ],
        "optional_properties": [
            "resolution", "offset", "length_bits", "byte_order",
        ],
        "id_convention": "signal-<dbc_sha256>-<message_identity>-<signal_name>",
        "id_example": "signal-0123456789abcdef-msg-s-2c1-coolant-temp",
    },
    "DBCVersion": {
        "description": (
            "A pinned DBC file version. Anchors the Frame -> Signal "
            "decode graph. Frozen taxonomy snapshots reference one."
        ),
        "required_properties": ["definition_id", "catalog_id", "dbc_version",
            "checksum_sha256", "source_uri", "artifact_uri", "source_kind",
            "spdx_license", "retrieved_at", "created_at", "parser_name",
            "parser_version", "validation_status"],
        "optional_properties": ["vehicle_make", "vehicle_model"],
        "id_convention": "dbc-<lowercase_sha256>",
        "id_example": "dbc-0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    },
    "DTC": {
        "description": (
            "A Diagnostic Trouble Code emitted by an ECU. FailureMode "
            "correlation anchor; OBD-II P-codes plus vendor extensions."
        ),
        "required_properties": ["dtc_code", "description", "severity"],
        "optional_properties": [
            "system", "subsystem", "first_seen_ts", "last_seen_ts",
            "occurrence_count",
        ],
        "id_convention": "dtc-<dtc_code>",
        "id_example": "dtc-P1234",
    },
    "FailureMode": {
        "description": (
            "A named failure mode class (coolant_leak, battery_degradation, "
            "sensor_stuck, etc.). The supervised-learning label space."
        ),
        "required_properties": ["mode_name", "category"],
        "optional_properties": [
            "symptoms", "typical_lead_time_minutes", "severity",
            "description",
        ],
        "id_convention": "failure-<category>-<mode_name>",
        "id_example": "failure-coolant-coolant_leak",
    },
    "MaintenanceEvent": {
        "description": (
            "A logged maintenance action that may have repaired or "
            "caused a failure. Closes the loop from FailureMode back "
            "to Vehicle via REPAIRED_BY."
        ),
        "required_properties": ["event_id", "vehicle_id", "performed_at", "action_type"],
        "optional_properties": [
            "technician", "parts_replaced", "downtime_hours",
            "odometer_km", "notes",
        ],
        "id_convention": "maint-<vehicle_id>-<event_id>",
        "id_example": "maint-V001-M0099",
    },
    # --- Context extension (bd:python-factory-ctx1) -------------------------
    # New node types follow the same shape contract (description /
    # required_properties / optional_properties / id_convention /
    # id_example) but use a compact single-line format to keep the
    # file under the 200 LOC tenet while still being unambiguous.
    "WeatherSnapshot": {
        "description": "Point-in-time atmospheric observation: temperature, humidity, precipitation, and weather code. Anchors OCCURS_DURING edges from Frame.",
        "required_properties": ["timestamp_ns", "latitude", "longitude", "temperature_c", "humidity_pct", "precipitation_mm", "weather_code"],
        "optional_properties": ["wind_speed_kph", "pressure_hpa", "wind_direction_deg", "visibility_m", "source"],
        "id_convention": "weather-<timestamp_ns>-<lat>-<lon>",
        "id_example": "weather-1700000000000000000-37.7749--122.4194",
    },
    "Location": {
        "description": "Geographic coordinate with road/terrain metadata. Frame-level anchor for LOCATED_AT edges.",
        "required_properties": ["latitude", "longitude"],
        "optional_properties": ["altitude_m", "road_type", "road_surface", "speed_limit_kph", "terrain_type", "heading_deg"],
        "id_convention": "loc-<lat>-<lon>",
        "id_example": "loc-37.7749--122.4194",
    },
    "Route": {
        "description": "A path through space with start/end coords, distance, elevation profile, and road-type composition. Trip-level anchor for TRAVERSES.",
        "required_properties": ["route_id", "start_lat", "start_lon", "end_lat", "end_lon", "distance_km"],
        "optional_properties": ["elevation_profile", "road_types", "terrain_summary", "avg_speed_kph", "duration_s", "polyline_hash"],
        "id_convention": "route-<route_id>",
        "id_example": "route-R001",
    },
    "DrivingProfile": {
        "description": "Aggregated driving-behavior metrics: aggressiveness score, average speed, hard accelerations, and idle percentage.",
        "required_properties": ["profile_id", "vehicle_id", "aggressiveness_score", "avg_speed_kph"],
        "optional_properties": ["hard_accels", "hard_brakes", "idle_pct", "max_speed_kph", "max_accel_mps2", "window_start_ts", "window_end_ts", "sample_count"],
        "id_convention": "drive-<vehicle_id>-<profile_id>",
        "id_example": "drive-V001-P042",
    },
    "EnvironmentalContext": {
        "description": "Join node that consolidates weather, location, driving, and vehicle slices active during a trip. Source of INFLUENCES edges to FailureMode.",
        "required_properties": ["context_id", "trip_id", "captured_at"],
        "optional_properties": ["weather_snapshot_id", "location_id", "route_id", "driving_profile_id", "vehicle_metadata_id", "time_of_day", "climate_zone"],
        "id_convention": "ctx-<vehicle_id>-<trip_id>",
        "id_example": "ctx-V001-T042",
    },
    "VehicleMetadata": {
        "description": "Static and slowly-changing vehicle facts: odometer, battery health, last service date, and DTC history.",
        "required_properties": ["metadata_id", "vehicle_id", "odometer_km", "last_service_date"],
        "optional_properties": ["battery_health_pct", "dtc_history", "manufacture_date", "vin", "age_years", "service_record_count"],
        "id_convention": "vmeta-<vehicle_id>",
        "id_example": "vmeta-V001",
    },
}

__all__ = ["CAN_FAILURE_NODE_TYPES"]
