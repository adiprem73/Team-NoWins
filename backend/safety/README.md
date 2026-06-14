# Context-Aware Smart Home Intelligence Platform

A containerised service that turns raw household device events into an
**AI-ready context object**. The system learns behaviour patterns
**deterministically** (no LLM) and produces the structured context that the
MoodSense orchestrator hands to **Amazon Bedrock** for reasoning.

```
Device Events → ALB → ECS (FastAPI) → DynamoDB Events
       → Pattern Extraction (in-process scheduler) → DynamoDB Patterns
       → Household State (DynamoDB) → Context Builder → Context Object
       → [ Orchestrator → Amazon Bedrock ]
```

---

## 1. Architecture

| Concern | Service | Why |
|---|---|---|
| Ingest / read API | **ALB + ECS (FastAPI/uvicorn)** | One containerised ASGI app behind the shared load balancer. |
| Event store | **DynamoDB** `SmartHome_Events` | Append-only, time-ordered per household. |
| Live snapshot | **DynamoDB** `SmartHome_HouseholdState` | One mutable doc per home. |
| Learned patterns | **DynamoDB** `SmartHome_Patterns` | Deterministic engine output. |
| Scheduled learning | **In-process scheduler** | Re-runs the extraction job on a fixed interval inside the service. |
| Reasoning | **Amazon Bedrock** (via orchestrator) | Consumes the context object. |

### Core philosophy
Pattern discovery is **deterministic and explainable**:
`Events → Pattern Extraction → Household Knowledge → Context Builder → Bedrock`.
We never ask an LLM to *discover* patterns.

---

## 2. DynamoDB table designs

**`SmartHome_Events`** — PK `household_id` (HASH), `sk` (RANGE = `"{ISO-timestamp}#{event_id}"`).
The composite sort key keeps events naturally time-ordered *and* unique, so
"last 30 days for H001" is a single efficient `Query`.

**`SmartHome_HouseholdState`** — PK `household_id`. One item per home holding
`people_home`, `active_devices`, `device_on_since`.

**`SmartHome_Patterns`** — PK `household_id` (HASH), `pattern_id` (RANGE).
Stores time / sequence / duration patterns with confidence + support.

All tables use **on-demand (PAY_PER_REQUEST)** billing — ideal for spiky IoT
traffic with zero capacity planning.

---

## 3. Folder structure

```
backend/
├── app/                 # FastAPI app + config + DI
│   ├── config.py        # env-driven settings
│   └── main.py          # app factory + in-process extraction scheduler
├── models/              # Pydantic models (events, state, patterns, context)
├── routes/              # FastAPI routers (events, state, patterns, context)
├── services/            # Business logic over DynamoDB + engine + builder
├── pattern_engine/      # Deterministic extractors (time/sequence/duration)
├── context_builder/     # Context assembly + anomaly detection
├── dynamodb/            # boto3 resource + table schemas
├── scripts/             # create_tables.py, seed_data.py
├── tests/               # pytest suite + sample_data.py
├── Dockerfile           # container image (ECS task)
├── docker-compose.yml   # DynamoDB Local
└── requirements.txt
```

---

## 4. API specification

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/events` | Ingest one event; updates live state. |
| `GET`  | `/events?household_id=&since=&limit=` | Query events (chronological). |
| `GET`  | `/state/{household_id}` | Current household snapshot. |
| `POST` | `/patterns/{household_id}/extract` | Run extraction now. |
| `GET`  | `/patterns/{household_id}` | List learned patterns. |
| `GET`  | `/context/{household_id}` | **Build the AI-ready context object.** |
| `GET`  | `/health` | Liveness. |

Interactive docs at `/docs` (Swagger) when running locally.

### Example: ingest
```bash
curl -X POST localhost:8080/events -H 'Content-Type: application/json' -d '{
  "household_id": "H001",
  "device_id": "son_room_fan",
  "device_type": "fan",
  "room": "son_room",
  "action": "OFF",
  "triggered_by": "son"
}'
```

### Example: context object (departure anomaly)
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

## 5. Pattern extraction algorithms (deterministic)

* **Time-based** — group `(device, action)`, cluster time-of-day into 30-min
  buckets, take the dominant bucket, score by support × consistency.
* **Sequence-based** — slice the timeline into sessions (events within 10 min),
  count repeated `device:action` signatures across days (captures the
  "son leaves for college" routine).
* **Duration-based** — pair each ON with the next OFF to learn typical runtime
  (e.g. water motor ≈ 15 min) and its variance.

**Confidence** = `support_score × consistency_score`, both in `[0,1]`
(`pattern_engine/confidence.py`). No randomness, fully reproducible.

### Anomaly detection (`context_builder/anomaly.py`)
* `device_left_on` — active device past its learned OFF time + grace window.
* `duration_exceeded` — running > `usual × 2` (water-motor example).

---

## 6. Local development setup

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 1) Start DynamoDB Local
docker compose up -d

# 2) Configure environment
cp .env.example .env          # DYNAMODB_ENDPOINT_URL=http://localhost:8000

# 3) Create tables + seed 30 days of data and extract patterns
python scripts/create_tables.py
python scripts/seed_data.py

# 4) Run the API
uvicorn app.main:app --reload --port 8080
# open http://localhost:8080/docs

# 5) See the context object (departure anomaly demo)
curl localhost:8080/context/H001
```

### Run tests (no AWS needed — uses moto in-memory DynamoDB)
```bash
pytest
```

---

## 7. AWS deployment (ECS + ALB)

The service ships as a container ([`Dockerfile`](Dockerfile)) and runs as an
ECS task behind the shared Application Load Balancer — the same deployment
model as every other backend service in the platform.

```bash
cd backend
docker build -t smarthome-patterns .
# push to ECR, then run as an ECS service behind the ALB at path /patterns/*
```

Provision once (via the platform IaC):
* 3 DynamoDB tables (on-demand),
* an **ECS service** running this image, fronted by the **ALB** (target group
  routed on `/patterns/*`),
* the deterministic extraction job runs **in-process** on a fixed interval —
  enable it by setting `SCHEDULED_HOUSEHOLD_IDS` (and optionally
  `EXTRACTION_INTERVAL_HOURS`) on the task.

After deploy, the ALB host is your REST endpoint:
```bash
curl "$ALB_URL/patterns/context/H001"
```

Seed data by POSTing events to `$ALB_URL/patterns/events`, then trigger
extraction on demand:
```bash
curl -X POST "$ALB_URL/patterns/H001/extract"
```

---

## 8. What's intentionally NOT built

* **Amazon Bedrock reasoning / proactive suggestions** — this service stops once
  the `ContextObject` is generated and validated. That object is the documented
  hand-off boundary consumed by the MoodSense orchestrator.
