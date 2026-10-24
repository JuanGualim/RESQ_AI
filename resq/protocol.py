"""Protocol constants from docs/protocol.md (rule IDs P1-P8). Change both together."""
from __future__ import annotations

# P1. Source reliability
SOURCE_WEIGHTS = {"brigade": 0.9, "official": 0.7, "social_media": 0.3}
RECENCY_HALF_LIFE_H = 2.0
UNCERTAIN_BELOW = 0.6
COORDINATOR_SOURCE = "coordinator"

# P2. Passability by verified status
PASSABLE_ALL = {"open", "damaged"}
PASSABLE_FORD_ONLY = {"passable_4x4", "flooded", "uncertain"}
IMPASSABLE = {"closed", "blocked"}

# P3. Risk index
RISK_WEIGHTS = {"exposure": 0.30, "vulnerability": 0.25, "dependents": 0.20, "isolation": 0.15, "reported_need": 0.10}
ELEVATION_STEPS = [(15, 1.0), (25, 0.8), (50, 0.5), (100, 0.25)]  # (max elevation_m, factor)
ELEVATION_DEFAULT = 0.1
RAIN_24H_STEPS = [(100, 1.0), (50, 0.8), (20, 0.5)]  # (min mm, factor)
RAIN_DEFAULT = 0.3
DEPENDENTS_FULL_AT_PCT = 55
ISOLATION_NONE, ISOLATION_FORD_ONLY, ISOLATION_FULL = 0.0, 0.6, 1.0
REPORTED_NEED = {"isolated": 1.0, "evacuating": 1.0, "needs_aid": 0.7, "stable": 0.0}
RISK_LEVELS = [(0.60, "critical"), (0.45, "high"), (0.30, "medium")]  # (min score, level)
RISK_LEVEL_DEFAULT = "low"

# P4. Needs per community
COVERED_SHARE = {"critical": 1.0, "high": 0.6, "medium": 0.3, "low": 0.0}
FAMILY_SIZE = 5
MEDICAL_PEOPLE_PER_KIT_HIGH, MEDICAL_PEOPLE_PER_KIT_LOW = 50, 100
MEDICAL_ELDERLY_PCT = 10
STABLE_NEED_FACTOR = 0.5

# P5. Allocation priority
RESOURCE_PRIORITY = ["water_20l", "food_kit", "medical_kit", "hygiene_kit", "blanket"]
CRITICAL_MIN_SHARE = 0.5
CRITICAL_ESSENTIALS = ["water_20l", "food_kit"]

# P6. Vehicles
MAX_TRIPS_PER_VEHICLE = 2

# P7. Shelters
SHELTER_FULL_AT = 0.95

# P8. Review and escalation
MAX_CRITIC_ROUNDS = 3
ESCALATE_BELOW_CONFIDENCE = 0.5
