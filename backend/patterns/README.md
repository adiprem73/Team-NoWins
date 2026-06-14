# 📊 Pattern Recognition Service

> Part of **Awaas AI** · runs on **port 8003**

A FastAPI microservice that turns raw household device events into an
**AI-ready context object**. It learns behaviour patterns **deterministically**
(no ML, no LLM) and produces the structured context that the Awaas orchestrator
and LLM narrator turn into natural Alexa-style suggestions.

```
Device Events → DynamoDB Events
   → Pattern Extraction (in-process scheduler) → DynamoDB Patterns
   → Household State (DynamoDB) → Context Builder → Context Object
   → [ LLM Narrator → Alexa voice ]
```

---

## 1 · Core philosophy

Pattern discovery is **deterministic and explainable**:

```
Events → Pattern Extraction → Household Knowledge → Context Builder → LLM (phrasing only)
```

We never ask an LLM to *discover* patterns — it only phrases the already-computed
`ContextObject`.

---

## 2 · DynamoDB tables

| Table | Keys | Holds |
|-------|------|-------|
| `SmartHome_Events` | PK `household_id`, SK `{ISO-timestamp}#{event_id}` | append-only, time-ordered event log |
| `SmartHome_HouseholdState` | PK `household_id` | live snapshot: `people_home`, `active_devices`, `device_on_since` |
| `SmartHome_Patterns` | PK `household_id`, SK `pattern_id` | learned time / sequence / duration patterns + confidence |

All tables use **on-demand (PAY_PER_REQUEST)** billing. Table names are
overridable via environment variables (see [`app/config.py`](app/config.py)).

---

## 3 · Folder structure

```
patterns/
├── app/                 # FastAPI factory + config + in-process scheduler
│   ├── config.py        #   env-driven settings
│   └── main.py          #   create_app() + _extraction_scheduler()
├── models/              # Pydantic models (events, state, patterns, context)
├── routes/              # FastAPI routers (events, state, patterns, context, admin)
├── logic/               # Business logic: event/state/pattern/context services + narrator
├── pattern_engine/      # Deterministic extractors (time / sequence / duration / confidence)
├── context_builder/     # Anomaly detection + context assembly
├── dynamodb/            # boto3 resource + table schemas
├── scripts/             # create_tables.py, seed_data.py, demo scenarios
└── tests/               # pytest suite (uses in-memory moto DynamoDB)
```

---

## 4 · API specification

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/events` | Ingest one event; updates live state. |
| `GET`  | `/events?household_id=&since=&limit=` | Query events (chronological). |
| `GET`  | `/state/{household_id}` | Current household snapshot. |
| `POST` | `/patterns/{household_id}/extract` | Run pattern extraction now. |
| `GET`  | `/patterns/{household_id}` | List learned patterns. |
| `GET`  | `/context/{household_id}` | **Build the AI-ready context object.** |
| `GET`  | `/health` | Liveness. |

Interactive Swagger docs at `/docs` when running locally.

### Example — ingest an event
```bash
curl -X POST localhost:8003/events -H 'Content-Type: application/json' -d '{
  "household_id": "H001",
  "device_id": "son_room_fan",
  "device_type": "fan",
  "room": "son_room",
  "action": "OFF",
  "triggered_by": "son"
}'
```

### Example — context object (departure anomaly)
```json
{
  "context_type": "departure_anomaly",
  "current_time": "11:00",
  "people_home": { "father": true, "mother": false, "son": false },
  "active_devices": ["son_room_fan", "son_room_light"],
  "relevant_patterns": [
    { "pattern_id": "SEQ#001", "description": "Departure routine: home secured / devices switched off", "confidence": 0.95 }
  ],
  "anomalies": [
    { "type": "device_left_on", "device": "son_room_fan", "severity": "high" }
  ]
}
```

---

## 5 · Pattern extraction (deterministic)

| Extractor | Learns | Example |
|-----------|--------|---------|
| **Time-based** | clusters event time-of-day into 30-min buckets, takes the dominant bucket | *"living-room light ON around 19:00"* |
| **Sequence-based** | repeated `device:action` chains within a 10-min session | *"door OPEN → fan OFF → light OFF"* |
| **Duration-based** | pairs each ON with the next OFF | *"water motor runs ~15 min"* |

**Confidence** = `support × consistency`, both in `[0,1]`
([`pattern_engine/confidence.py`](pattern_engine/confidence.py)). A pattern is
kept only if it occurs **≥ 3 times** *and* scores **≥ 0.6**.

### Anomaly detection ([`context_builder/anomaly.py`](context_builder/anomaly.py))

| Detector | Fires when |
|----------|-----------|
| `device_left_on` | active device past its learned OFF time + 60-min grace |
| `duration_exceeded` | running longer than `usual × 2.0` |
| `device_active_too_long` | absolute 12-hour safety-net (no duration pattern) |
| `missed_routine` | a high-confidence ON routine's window passed without happening |
| `unexpected_activity` | entry/activity far outside the learned schedule |

---

## 6 · Local development

Run from the `backend/` directory (so the `patterns` package imports resolve):

```bash
cd backend
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

# 1) Start DynamoDB Local (or: moto_server -p 8100)
docker run -p 8100:8000 amazon/dynamodb-local

# 2) Point at it (in backend/.env)
#    DYNAMODB_ENDPOINT_URL=http://localhost:8100

# 3) Create tables + seed 30 days of data and extract patterns
python patterns/scripts/create_tables.py
python patterns/scripts/seed_data.py

# 4) Run the API
uvicorn patterns.app.main:app --reload --port 8003
# open http://localhost:8003/docs

# 5) See the context object
curl localhost:8003/context/H001
```

### Run the tests (no AWS needed — uses in-memory moto DynamoDB)
```bash
cd backend && pytest patterns/
```

---

## 7 · Configuration knobs ([`app/config.py`](app/config.py))

| Setting | Default | Purpose |
|---------|:-------:|---------|
| `analysis_window_days` | 30 | days of history analysed |
| `time_bucket_minutes` | 30 | clustering granularity |
| `min_pattern_occurrences` | 3 | minimum repeats to learn a pattern |
| `min_confidence` | 0.6 | threshold to accept a pattern |
| `departure_grace_minutes` | 60 | how long past schedule before flagging |
| `duration_anomaly_factor` | 2.0 | multiple of usual duration that triggers an alert |
| `max_continuous_active_minutes` | 720 | absolute 12-hour safety-net |
| `scheduled_household_ids` | *(empty)* | households the in-process scheduler re-learns |
| `extraction_interval_hours` | 24 | how often the scheduler runs |

---

## 8 · The boundary

This service stops once the `ContextObject` is generated and validated. That
object is the documented hand-off to the **LLM narrator** (Bedrock → Groq →
deterministic template) which only *phrases* the result — see
[`logic/narrator.py`](logic/narrator.py).

> 🛡️ For the vulnerability-aware sibling of this engine, see the
> [Adaptive Safety service](../safety/README.md).