# MoodSense AI — Smart Alexa Environment Controller

An AI-powered system that detects user mood and cognitive load through speech analysis, behavioral patterns, and device usage history — then automatically adjusts smart home devices to create an optimal environment.

## Architecture

Microservices connected through an API Gateway with load-balanced routing:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         FRONTEND (React Dashboard)                           │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    API GATEWAY (port 8000)                                    │
│              Path-based routing / Load balancer                               │
├────────────┬────────────┬────────────────┬──────────────┬───────────────────┤
│ /mood/*    │/behavior/* │  /patterns/*   │  /devices/*  │  /orchestrate/*   │
└─────┬──────┴─────┬──────┴───────┬────────┴───────┬──────┴─────────┬─────────┘
      │            │              │                │                │
      ▼            ▼              ▼                ▼                ▼
┌──────────┐ ┌──────────┐ ┌──────────────┐ ┌──────────┐  ┌──────────────────┐
│  Mood    │ │ Behavior │ │   Pattern    │ │  Device  │  │  Orchestrator    │
│ Service  │ │ Service  │ │   Service    │ │  Service │  │  (The Brain)     │
│ :8001    │ │ :8002    │ │   :8003      │ │  :8004   │  │  :8005           │
│          │ │          │ │              │ │          │  │                  │
│ Voxtral  │ │ Scroll/  │ │ Time-based   │ │ Mood→    │  │ Calls all svcs   │
│ Bedrock  │ │ Tap/Idle │ │ Sequences    │ │ Light/   │  │ via HTTP, feeds  │
│ Analysis │ │ Analysis │ │ Duration     │ │ Music/   │  │ everything to    │
│          │ │          │ │ Anomalies    │ │ Notif    │  │ Voxtral LLM for  │
└──────────┘ └──────────┘ │ DynamoDB     │ └──────────┘  │ reasoned actions │
                          └──────────────┘               └──────────────────┘
```

## Features

### 1. Voice-Based Mood Detection (Mood Service)
- Records audio from user speaking to Alexa
- Sends to **Voxtral Small 24B** (AWS Bedrock) for multimodal analysis
- Detects: tone, pace, pitch, sentiment → mood classification
- 9 mood states: calm, happy, stressed, anxious, frustrated, sad, energetic, tired, neutral

### 2. Behavioral Cognitive Load Detection (Behavior Service)
- Tracks real-time interaction patterns from Alexa-connected devices
- Fast/aggressive scrolling → frustration indicator
- Rapid tapping → impatience/agitation
- Prolonged idle → fatigue/distraction
- Erratic swiping → overwhelm
- Outputs: cognitive load level (low/moderate/high/overloaded) + agitation score

### 3. Time-Based Pattern Recognition (Pattern Service)
- Learns device usage patterns deterministically (no ML)
- **Time-based**: "Living room light turns ON around 19:00" (clustered by 30-min buckets)
- **Sequence-based**: "Son leaves → fan OFF → light OFF" (departure routines)
- **Duration-based**: "Water motor runs ~15 minutes" (normal runtime)
- **Anomaly detection**: Devices left on, exceeded duration, missed routines
- Confidence scoring: support × consistency, fully explainable

### 4. LLM-Powered Action Engine (Orchestrator)
- Receives ALL three signal types together
- Voxtral reasons holistically about the user's state
- Handles contradictions: "User says 'I'm fine' but behavior shows agitation → adjust for stress"
- Considers pattern context: "Son left but fan is still on → should I turn it off?"
- Falls back to preset-based logic when LLM is unavailable

### 5. Smart Device Control (Device Service)
- Maps mood + cognitive load → environment adjustments
- Lights: color, brightness, color temperature
- Music: genre, volume
- Notifications: normal / reduced / DND
- 9 mood presets + cognitive load overrides

## Tech Stack

| Layer | Technology |
|-------|-----------|
| AI Model | Voxtral Small 24B 2507 (AWS Bedrock) |
| Backend | FastAPI (Python) — 5 microservices + gateway |
| Database | DynamoDB (device events, patterns, state) |
| Frontend | React + Vite + Tailwind CSS |
| Infra | Docker Compose, AWS (Bedrock, DynamoDB, IoT) |
| Communication | HTTP (inter-service), WebSocket (real-time) |

## Project Structure

```
├── backend/
│   ├── gateway/main.py                 # API Gateway — routes to services
│   ├── services/
│   │   ├── mood/                       # Port 8001
│   │   │   ├── main.py                 # Mood analysis endpoints
│   │   │   ├── bedrock_client.py       # Voxtral Bedrock integration
│   │   │   └── models.py              
│   │   ├── behavior/                   # Port 8002
│   │   │   ├── main.py                 # Behavior analysis endpoints
│   │   │   ├── engine.py               # Signal processing algorithm
│   │   │   └── models.py              
│   │   ├── patterns/                   # Port 8003
│   │   │   ├── main.py                 # Pattern CRUD + context endpoints
│   │   │   ├── engine/                 # Deterministic extractors
│   │   │   │   ├── time_based.py
│   │   │   │   ├── sequence_based.py
│   │   │   │   ├── duration.py
│   │   │   │   └── confidence.py
│   │   │   ├── context_builder.py      # Anomaly detection + context assembly
│   │   │   ├── dynamo.py              # DynamoDB client
│   │   │   ├── services.py            # Business logic
│   │   │   └── models.py             
│   │   ├── devices/                    # Port 8004
│   │   │   ├── main.py                # Device control endpoints
│   │   │   └── controller.py          # Mood→device presets
│   │   └── orchestrator/              # Port 8005
│   │       ├── main.py                # Unified pipeline endpoint
│   │       └── action_engine.py       # LLM-powered reasoning
│   ├── config.py                      # Shared settings
│   └── docker-compose.yml
├── frontend/
│   └── src/
│       ├── pages/Dashboard.jsx        # Real-time monitoring
│       ├── components/
│       │   ├── VoiceInput.jsx         # Mic recording
│       │   ├── BehaviorTracker.jsx    # Interaction monitoring
│       │   ├── MoodIndicator.jsx
│       │   ├── CognitiveLoadMeter.jsx
│       │   └── EnvironmentPanel.jsx
└── docker-compose.yml                 # Full stack orchestration
```

## Getting Started

### Run All Services (Docker)
```bash
docker-compose up --build
```

### Run Individually (Development)
```bash
cd backend

# Terminal 1: Gateway
uvicorn gateway.main:app --reload --port 8000

# Terminal 2: Mood Service
uvicorn services.mood.main:app --reload --port 8001

# Terminal 3: Behavior Service
uvicorn services.behavior.main:app --reload --port 8002

# Terminal 4: Pattern Service (needs DynamoDB Local)
docker run -p 8100:8000 amazon/dynamodb-local
uvicorn services.patterns.main:app --reload --port 8003

# Terminal 5: Device Service
uvicorn services.devices.main:app --reload --port 8004

# Terminal 6: Orchestrator
uvicorn services.orchestrator.main:app --reload --port 8005

# Terminal 7: Frontend
cd ../frontend && npm run dev
```

## API Endpoints

### Via Gateway (http://localhost:8000)

| Method | Path | Service | Description |
|--------|------|---------|-------------|
| POST | `/mood/analyze/audio` | Mood | Analyze audio for mood |
| POST | `/mood/analyze/text` | Mood | Analyze text for mood |
| POST | `/behavior/analyze` | Behavior | Process behavior signals |
| POST | `/patterns/events` | Patterns | Ingest device event |
| GET | `/patterns/context/{id}` | Patterns | Get AI-ready context |
| POST | `/patterns/patterns/{id}/extract` | Patterns | Run pattern extraction |
| POST | `/devices/adjust` | Devices | Compute environment |
| POST | `/orchestrate/process` | Orchestrator | Full pipeline (all signals → LLM → actions) |
| GET | `/services/health` | Gateway | Check all service health |

## Data Flow (Full Pipeline)

```
User speaks to Alexa + interacts with devices
         │                        │
         ▼                        ▼
   Mood Service              Behavior Service
   (Voxtral LLM)            (Algorithm)
   mood: "stressed"         load: "overloaded"
   confidence: 85%          agitation: 93%
         │                        │
         └──────────┬─────────────┘
                    │
         Pattern Service (DynamoDB)
         "son_room_fan usually OFF by 09:00"
         "Anomaly: fan still running!"
                    │
                    ▼
         ┌────────────────────┐
         │  ORCHESTRATOR       │
         │  (Voxtral LLM)     │
         │                    │
         │  Sees: stressed +  │
         │  overloaded +      │
         │  device anomaly    │
         │                    │
         │  Decides:          │
         │  - Dim blue lights │
         │  - Ambient music   │
         │  - Turn off fan    │
         │  - DND mode        │
         └────────┬───────────┘
                  │
                  ▼
         Smart Home Devices
         (Lights, Speaker, Notifications)
```

## Team
Built for HackOn 2026
