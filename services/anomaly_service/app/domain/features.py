"""
Feature keys from the design doc (temporal, visitor, resident, security, relationship).

Values are string identifiers for configs and feature-store rows — not computed here.
"""

# Temporal (examples)
HOUR_OF_DAY = "hour_of_day"
DAY_OF_WEEK = "day_of_week"
IS_WEEKEND = "is_weekend"
VISIT_HOUR_BUCKET = "visit_hour_bucket"
TIME_SINCE_LAST_VISIT = "time_since_last_visit"
RESIDENT_TIME_SINCE_LAST_VISIT = "resident_time_since_last_visit"
VISIT_INTERARRIVAL_TIME = "visit_interarrival_time"
NIGHT_VISIT_FLAG = "night_visit_flag"

# Visitor-level
VISITOR_TOTAL_VISITS = "visitor_total_visits"
VISITOR_WEEKLY_FREQUENCY = "visitor_weekly_frequency"

# Resident-level
RESIDENT_TOTAL_VISITORS = "resident_total_visitors"
RESIDENT_VISIT_FREQUENCY = "resident_visit_frequency"

# Security / guard
GUARD_TOTAL_VALIDATIONS = "guard_total_validations"
GUARD_NIGHT_VALIDATIONS = "guard_night_validations"

# Relationship
RELATIONSHIP_FREQUENCY = "relationship_frequency"
RELATIONSHIP_TRANSITION = "relationship_transition"
