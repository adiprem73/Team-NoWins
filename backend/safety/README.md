# 🛡️ Adaptive Safety Intelligence Service

> Part of **Awaas AI** · runs on **port 8006**

An **independent twin** of the [Pattern Recognition service](../patterns/README.md).
It reuses the same deterministic pattern engine, then adds **one powerful new
idea**: *who is home, and how vulnerable are they?* Every anomaly is re-read
through a vulnerability lens, producing a live **safety score** and emergency
detection for vulnerable people living alone — elderly, children, pregnant, or
unwell family members.

```
Events → Pattern Engine → Anomalies (+ safety detectors)
   → Safety Overlay (vulnerability escalation) → Safety Assessment
   → [ LLM Narrator → caring Alexa voice ]
```

---

## 1 · What makes it different from Patterns

The whole event → pattern → anomaly pipeline is identical. Safety adds:

| Addition | File | Role |
|----------|------|------|
| **Person profiles** | [`models/safety.py`](models/safety.py) | who lives here + their vulnerability level |
| **Safety overlay** | [`context_builder/safety_overlay.py`](context_builder/safety_overlay.py) | escalate severity by vulnerability → score + status |
| **Profile service** | [`logic/profile_service.py`](logic/profile_service.py) | CRUD for person profiles |
| **Safety detectors** | [`context_builder/anomaly.py`](context_builder/anomaly.py) | 4 extra people-centric detectors |

> The **same** open door is `low` severity with a fit adult home — but `critical`
> for an elderly person alone. Still **deterministic and explainable**: the LLM
> only phrases the result, it never decides what is true.

---

## 2 · Vulnerability weights ([`app/config.py`](app/config.py))

| Person | Weight | | Person | Weight |
|--------|:------:|---|--------|:------:|
| Normal adult | ×1.0 | | Pregnant | ×1.8 |
| Child | ×1.7 | | Elderly | ×2.0 |
| Unwell | ×1.8 | | Capable adult present | ×0.6 *(mitigates)* |

- **Most-vulnerable wins** — the home's factor is the max over who's home.
- **Supervised mitigation** — a capable NORMAL adult present multiplies the factor by `0.6`.
- **Vulnerable-alone** — a non-normal person home with no capable adult → every concern fully escalated.

Escalated rank = `round(base_rank × factor)`, clamped to `[0, 4]` → mapped to
`low / medium / high / critical`.

---

## 3 · Detectors

The 5 pattern detectors (`device_left_on`, `duration_exceeded`,
`device_active_too_long`, `missed_routine`, `unexpected_activity`) **plus** four
safety-specific ones:

| Detector | Fires when |
|----------|-----------|
| `inactivity` / `missed_arrival` / `missed_medicine` | an elderly activity ping, expected arrival, or medicine confirmation is absent |
| `unsafe_at_night` | a door/window is open during the night window (22:00–06:00) |
| `global_inactivity` | no activity of *any* kind for 4 h (warn) / 8 h (emergency) while someone's home |
| `health_alert` / `sos` | a wearable vital is out of range, or a panic/fall SOS fires → instant **Emergency** |

---

## 4 · Safety score & status ([`context_builder/safety_overlay.py`](context_builder/safety_overlay.py))

Starts at **100**, deducts per escalated anomaly:

| Severity | Penalty | | Status | Condition |
|----------|:-------:|---|--------|-----------|
| low | −4 | | 🟢 **Safe** | ≥ 60, no high/critical |
| medium | −12 | | 🟡 **Inactive** | only inactivity-type anomalies |
| high | −28 | | 🟠 **Needs Attention** | < 60 or any high/critical |
| critical | −55 | | 🔴 **Emergency** | SOS / health / global-inactivity / score < 25 |

---

## 5 · DynamoDB tables

The safety engine uses its **own** tables so its data never touches the patterns
feature (names overridable via env — see [`app/config.py`](app/config.py)):

| Table | Keys | Holds |
|-------|------|-------|
| `Safety_Events` | PK `household_id`, SK `{ISO-timestamp}#{event_id}` | event log |
| `Safety_HouseholdState` | PK `household_id` | live snapshot |
| `Safety_Patterns` | PK `household_id`, SK `pattern_id` | learned patterns |
| `Safety_Profiles` | PK `household_id`, SK `person_id` | person profiles + vulnerability |

---

## 6 · API specification

| Method | Path | Purpose |
|--------|------|---------|
| `GET`  | `/safety/{household_id}?at=HH:MM` | **Full dashboard payload** — context + safety assessment + profiles + state + timeline + patterns. |
| `GET`  | `/context/{household_id}` | Build the context object (with safety overlay). |
| `POST` | `/context/{household_id}/evaluate` | "What-if" — evaluate a supplied state against learned patterns. |
| `POST` | `/context/narrate` | Narrate a context into one spoken Alexa line. |
| `POST` | `/context/narrate/each` | Narrate **each** concern individually, most-severe first. |
| `POST` | `/admin/seed/{household_id}?scenario=` | Seed 30 days of history + a today scenario. |
| `POST` | `/admin/profiles/{household_id}?preset=` | Swap who's home (vulnerability preset). |
| `GET`  | `/admin/scenarios` | List demo scenarios + presets. |
| `GET`  | `/health` | Liveness. |

### Demo scenarios (`/admin/seed`)
`normal` · `inactivity` · `gas` · `window_night` · `health` · `sos`
*(combine with commas, e.g. `gas,window_night`)*

### Who's-home presets (`/admin/profiles`)
`elderly` · `child_alone` · `pregnant_alone` · `unwell_alone` · `mixed_support`

---

## 7 · Local development

Run from the `backend/` directory:

```bash
cd backend
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

# 1) Start DynamoDB Local (or: moto_server -p 8100)
docker run -p 8100:8000 amazon/dynamodb-local
#    then set DYNAMODB_ENDPOINT_URL=http://localhost:8100 in backend/.env

# 2) Run the API (tables auto-create on startup)
uvicorn safety.app.main:app --reload --port 8006
# open http://localhost:8006/docs

# 3) Seed the elderly household + a scenario, then view the dashboard
curl -X POST "http://localhost:8006/admin/seed/E001?scenario=window_night"
curl "http://localhost:8006/safety/E001"
```

### Run the tests (no AWS needed — uses in-memory moto DynamoDB)
```bash
cd backend && pytest safety/
```

---

## 8 · TLS note (corporate proxies)

Outbound LLM calls (Groq / Bedrock) use a scoped OS-trust-store SSL context via
`truststore`, so the narrator still reaches the LLM behind a TLS-intercepting
proxy. If the LLM is unreachable, narration falls back to a deterministic
template — the dashboard never blocks. See [`logic/narrator.py`](logic/narrator.py).

> 📊 For the underlying deterministic engine, see the
> [Pattern Recognition service](../patterns/README.md).