# anomaly-service (draft)

Implements the **Visit Anomaly Detection** slice from the GatePass design doc: modular
pipeline (scope → data → features → analysis → transparency), pluggable per **analysis scope**
(visitor / resident / security / estate-wide).

This package is a **scaffold**: HTTP API + domain enums + ABC-based managers with stub
implementations. ML (K-means, DBSCAN, LFOA ensemble), Pub/Sub, feature store tables, and
incremental counters are **not** wired yet.

**Port:** `9035` (local and intended K8s service port).

**Next steps:** connect to `db-service` / visit log APIs, add Alembic migrations for feature-store
tables, implement incremental aggregates, add GCP Pub/Sub consumer for real-time path.
