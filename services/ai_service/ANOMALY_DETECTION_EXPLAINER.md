# How anomaly detection works here (plain language)

This note describes the **ideas behind** the numbers—without equations or jargon. It matches what the code does today (K-means and DBSCAN per scope, then a simple combined score).

---

## The situation

Each time someone validates at the gate, we turn that moment into a **short list of measurements**: time of day, how often they usually come, how long since the last visit, and so on. Those measurements are **features**—a snapshot of “what this visit looks like.”

We also keep **past snapshots** that we trust (not ones we already marked as odd). Those act as **“normal for this estate / this lens”** so the current visit is never compared in a vacuum.

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

## Putting scopes together (ensemble)

We compute scores **separately** for each **analysis scope** (visitor-specific, resident-specific, security, estate-wide—whatever the pipeline is configured to run). Each scope gets its own small set of features and its own detector outputs.

Today we **average** those scope-level results into one **final score**. That average is a placeholder until a weighted or learned combination is configured.

---

## When we call it “anomalous”

The **final score** is compared to a **threshold** (configurable). If the score is **at or above** that bar, we mark the visit as **anomalous** for reporting and store that flag with the engineered features so future runs don’t treat this visit as “normal history” by mistake.

At persistence time, the service also writes a prediction payload to db-service as
`{"result": <analysis output>}` and tags it with a prediction type enum
(`VisitorAnomalyRealtime` or `ResidentAnomalyRealtime`).

---

## What’s not here yet

**LFOA** (another ensemble idea from the design doc) is **stubbed**—the hooks exist, but it does not contribute to the score yet.

---

## Related code

| Idea              | Where to look |
|-------------------|---------------|
| K-means scoring   | `app/pipeline/anomaly_models/kmeans_model.py` |
| DBSCAN scoring    | `app/pipeline/anomaly_models/dbscan_model.py` |
| Running both      | `app/pipeline/analysis_manager.py` (`run_models`) |
| Scope combination | `ensemble_score` in the same file |
| End-to-end flow   | `app/pipeline/anomaly_orchestration.py` |
