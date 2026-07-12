# Temporal Anomaly Detection (Matrix Profile)

Plain-language guide to the `POST /api/v1/temporal-anomaly/analyze/{anomaly_type}`
endpoint. Where the **spatial** anomaly detector looks at *engineered feature
vectors* (K-means / DBSCAN / LOF in feature space), the **temporal** detector
looks at the *shape of activity over time* using the Matrix Profile.

Reference article: [Using the Matrix Profile to Detect Anomalies in Time
Series](https://medium.com/@pw33392/using-the-matrix-profile-to-detect-anomalies-in-time-series-bca14883e0fb)
(Phillip Wenig, 2025).

## The idea in one paragraph

Slide a fixed-length window over a numeric time series. For every window
position, find the most similar other window (its nearest neighbour) using the
**z-normalized Euclidean distance**, and record that smallest distance. The
resulting sequence of distances is the **Matrix Profile**. Windows that look
like other windows have a *small* distance; a window that looks like nothing
else in the series has a *large* distance and is called a **discord** - an
anomaly. The most typical window (smallest distance) is a **motif**.

## What series do we analyse here?

This endpoint is **estate-scoped**, not tied to a single validation code. The
request body carries only an `estate_id`. We fetch the estate's **entire**
visit/access history from `db-service` (paging `visitorlog` / `residentlog`
searches by `estate_id`, with no date window) and turn those rows into a
**daily visit-count series**:

- One bucket per calendar day, from the first event day to the last.
- Each bucket holds the number of visits/accesses that fell on that day.

### The `anomaly_type` path parameter

The temporal endpoint accepts three values, which choose the log tables fed
into the daily series:

- `visitor` - the estate's entire `visitorlog` history.
- `resident` - the estate's entire `residentlog` history.
- `combined` - both `visitorlog` **and** `residentlog` merged into a single
  estate-wide series.

(The spatial endpoint supports only `visitor` / `resident`.)

## How a request is scored

1. Load the estate's entire history for the chosen subject.
2. Build the daily visit-count series over `[first_event_day, last_event_day]`.
3. **History-length check:** if the series spans fewer than
   `3 x TEMPORAL_SUBSEQUENCE_WINDOW_DAYS` days (default `3 x 7 = 21`), return a
   `422` error - there is not enough history for a meaningful comparison.
4. Compute the Matrix Profile with `stumpy.stump(series, m).P_` where
   `m = TEMPORAL_SUBSEQUENCE_WINDOW_DAYS` (a one-week window).
5. Take the **latest subsequence** - the most recent length-`m` window, starting
   at `len(series) - m` - and read its Matrix Profile value.
6. Convert that value into a score in `[0, 1]` by its **percentile rank** among
   all windows: `1.0` means the latest week is the strongest discord (most
   unusual week) in the estate's history. `is_anomalous` is
   `final_score >= TEMPORAL_ANOMALY_SCORE_THRESHOLD` (default `0.5`).

A series that is long enough but too flat (fewer than two non-empty days) is
reported with `computed = false`, `final_score = 0.0`, and
`is_anomalous = false`.

## Why it is unsupervised and not persisted

The Matrix Profile is computed directly from the raw log window each time - it
needs no stored training vectors. Unlike the spatial pipeline (which persists
engineered features and predictions to `core.logfeatureengineering` /
`core.predictionresult`), the temporal endpoint computes and returns results
without writing to `db-service`.

## Key files

| Concern | File |
|---|---|
| Endpoint | `app/api/v1/endpoints/temporal_anomaly.py` |
| Orchestrator | `app/pipeline/temporal_anomaly_orchestration.py` |
| Matrix Profile core | `app/pipeline/matrix_profile.py` |
| Request/response schema | `app/models/temporal_anomaly_schema.py` |
| Config | `TEMPORAL_ANOMALY_SCORE_THRESHOLD`, `TEMPORAL_SUBSEQUENCE_WINDOW_DAYS` in `app/core/config.py` |

## Limitations / future work

- Daily counts and a one-week window (`m = 7`) are sensible defaults; other
  granularities or window sizes may suit different estates.
- Percentile-rank scoring flags the *relatively* most unusual window even in a
  calm series; pair with the threshold and the `computed` flag when consuming.
- Persistence and a `PredictionType` for temporal results would require a
  `db-service` enum migration and are intentionally out of scope here.
