# How anomaly detection works here (plain language)

This note describes the **ideas behind** the numbers—without equations or jargon. It matches what the code does today: **K-means**, **DBSCAN**, and **LOF** run per analysis scope, then scores are combined into one final result.

---

## The situation

Each time someone validates at the gate, we turn that moment into a **short list of measurements**: time of day, how often they usually come, how long since the last visit, and so on. Those measurements are **features**—a snapshot of “what this visit looks like.”

We also keep **past snapshots** that we trust (not ones we already marked as odd). Those are loaded from the **feature store** (`core.logfeatureengineering`) for prior log ids in the same scope slice—not every raw visit in the 30-day window, only visits that already ran `/analyze` and were stored as non-anomalous. They act as **“normal for this estate / this lens”** so the current visit is never compared in a vacuum.

**Thin history:** Some scopes have very few prior records (e.g. `visitor_specific` only matches the same visitor name, so a second-ever visit by that person yields one prior id). Detectors must tolerate that; LOF uses a distance fallback when fewer than two stored vectors exist.

---

## K-means–style distance (“how far from the usual bunch?”)

Imagine past visits as dots on a map where each axis is one measurement. **K-means** draws a small number of **centres** through the past dots—like finding a few “typical neighbourhoods” where most normal activity sits.

The current visit is one more dot. We look at **how far** it sits from the nearest centre, compared to how far past visits were from their nearest centres. If today’s visit is **much farther** than most historical visits, that suggests **unusual**—and the model returns a higher score (capped so it stays in a 0–1 band).

**Intuition:** “Does this visit land in the same ballpark as what we’ve seen before, or is it an outlier in distance?”

---

## DBSCAN-style “inside the crowd or outside?”

**DBSCAN** groups nearby dots into **clusters** and labels sparse dots as **noise** (not part of any tight group). We run it on past visits **plus** the current visit together.

- If the **current visit** gets treated like **noise**—not comfortably inside any cluster—it scores **high** (we read that as unusual).
- If it sits **inside** a cluster with everyone else, the score stays **low**, with a small adjustment only when there is also scattered “noise” elsewhere in the history.

**Intuition:** “Is this visit standing with the crowd, or standing alone on the fringe?”

---

## LOF — Local Outlier Factor (“how odd compared to neighbours?”)

**LOF** looks at each visit’s **immediate neighbourhood** (its nearest past visits in feature space) and compares **how dense** that neighbourhood is to the density around those neighbours.

- If the current visit is **much sparser** than its neighbours expect, LOF treats it as an **outlier** and the score is **high**.
- If it fits the local pattern, the score stays **low**.

We fit LOF on **past visits only** (`novelty=True`), then score the current visit against that reference—same “normal history first” idea as K-means. With only **one** stored historical vector, LOF cannot run in the usual way; the implementation falls back to a simple distance ratio against that single reference.

**Intuition:** “Among visits like the ones nearby, does this one still look like it belongs?”

**Transparency id:** `lof-neighbors-v1` (output key `lof` in `model_outputs`).

---

## Putting scopes together (ensemble)

Scoring happens in **two layers** today:

1. **Per scope:** K-means, DBSCAN, and LOF each return a score in `[0, 1]`. These are **averaged** into one scope score (`score_from_model_outputs` in `analysis_manager.py`).
2. **Across scopes:** Each scope (visitor-specific, resident-specific, security, estate-wide—for visitor anomaly type) gets its own scope score. Those scope scores are **averaged** into the **final score** (`ensemble_score`).

That double average is a **placeholder**. See TODOs below for weighting and scope eligibility rules.

Check `transparency.scopes[].model_outputs.historical_reference_count` to see how many stored vectors each scope had when detectors ran.

---

## When we call it “anomalous”

The **final score** is compared to a **threshold** (configurable via `ENSEMBLE_ANOMALOUS_SCORE_THRESHOLD`). If the score is **at or above** that bar, we mark the visit as **anomalous** for reporting and store that flag with the engineered features so future runs don’t treat this visit as “normal history” by mistake.

At persistence time, the service also writes a prediction payload to db-service as
`{"result": <analysis output>}` and tags it with a prediction type enum
(`VisitorAnomalyRealtime` or `ResidentAnomalyRealtime`).

---

## TODOs

- [ ] **Thin-scope handling:** Scopes with too few historical records (e.g. `visitor_specific` with only one prior visit in the feature store) should be **ignored or weighted down** in the final ensemble so they do not skew the global score or trigger false positives.
- [ ] **Ensemble weights:** Define the **weight mechanism** for combining scope scores and/or per-detector scores (replace the current unweighted mean in `ensemble_score` and `score_from_model_outputs`).
- [ ] **Notifications and admin override:** Link anomaly detection to the **notification pipeline** (alert admins/security on high scores) and allow admins to **reclassify** an instance—mark a flagged visit as false positive or confirm true positive—so human feedback can update stored `is_anomalous` and future reference cohorts.

---

## What’s not here yet

Pub/Sub triggers and incremental feature counters on the anomaly path are still **not** wired.

---

## Related code

| Idea              | Where to look |
|-------------------|---------------|
| K-means scoring   | `app/pipeline/anomaly_models/kmeans_model.py` |
| DBSCAN scoring    | `app/pipeline/anomaly_models/dbscan_model.py` |
| LOF scoring       | `app/pipeline/anomaly_models/lof_model.py` |
| Running detectors | `app/pipeline/analysis_manager.py` (`run_models`) |
| Per-scope + final combine | `score_from_model_outputs`, `ensemble_score` in the same file |
| Historical vectors | `app/domain/log_feature_store.py`, `batch_lookup_engineered_features` |
| End-to-end flow   | `app/pipeline/anomaly_orchestration.py` |
