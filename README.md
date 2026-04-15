# TransitPulse 🚨⚡

**Hyper-local hazard and delay alert prototype for urban commuters.**

TransitPulse ingests a simulated stream of geo-tagged social media posts, classifies traffic hazards using AI (Groq LLM with keyword fallback), cross-references them against your active commute route in Bengaluru, and pushes real-time alerts to a live dashboard via WebSocket — complete with screen-shaking animations, sound alerts, and a dark-themed interactive map.

---

## ✨ Features

### AI-Powered Classification
- **Primary:** Groq API (`llama-3.1-8b-instant`) for intelligent hazard detection
- **Fallback:** Keyword-matching classifier when no API key is provided
- Categories: Flood, Accident, Obstruction, Protest, HazMat, Traffic
- Confidence threshold (0.6) to filter uncertain results

### Real-Time Dashboard
- **Dark-themed Leaflet.js map** (CartoDB Dark Matter tiles) — no API key needed
- **Live WebSocket feed** with ingestion cards and color-coded alert cards
- **Route markers** for 5 Bengaluru zones with pulsing red hazard circles on alert
- **Scanning line animation** across the map for a live-monitoring feel

### Alert Effects
- 🫨 **Screen shake** on HIGH severity alerts
- 🔴 **Red flash overlay** across the entire screen
- 🚨 **Toast notification** sliding in from the top
- 🔊 **Alert sound** (toggle on/off) — dual-tone siren for HIGH, gentle beep for others
- 💥 **Slam animation** on HIGH alert cards with red glow
- 🔲 **Border flash** on the app frame for all alerts

### Smart Backend
- **Continuous feed loop** — 12 simulated posts cycle every ~40s with randomized delays
- **Dedup cache** — suppresses repeat zone+category alerts within a 45s cooldown
- **Route filtering** — only alerts for the 5 on-route zones are broadcast
- **Manual injection** via `POST /ingest` for testing custom scenarios

---

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11+, FastAPI (async) |
| AI | Groq API (`llama-3.1-8b-instant`) + keyword fallback |
| Maps | Leaflet.js + CartoDB Dark Matter (free, no key needed) |
| Real-time | Native WebSocket (FastAPI) |
| Frontend | Vanilla HTML/CSS/JS (single `index.html`) |
| Testing | pytest + pytest-asyncio (30 tests) |
| Config | python-dotenv for secrets |

---

## 🚀 Setup

```bash
# 1. Clone and enter the project
cd transitpulse

# 2. Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment (optional)
cp .env.example .env
# Edit .env to add API keys — the prototype works fully without them
```

## ▶️ Run

```bash
uvicorn main:app --reload
```

Open **http://localhost:8000** in your browser.

## 🧪 Run Tests

```bash
pytest tests/ -v
```

All 30 tests cover:
- Classifier (Groq mock, keyword fallback, confidence threshold, markdown stripping)
- Route matcher (zone matching, dedup cache, cache expiry)
- API endpoints (health, route, ingest validation)

---

## 🔑 API Keys (Optional)

| Key | Purpose | Required? |
|---|---|---|
| `GROQ_API_KEY` | AI hazard classification via Llama 3.1 | No — falls back to keyword matching |
| `GOOGLE_MAPS_API_KEY` | Not used (Leaflet.js replaces Google Maps) | No |

The prototype is **fully functional without any API keys**.

---

## 📡 API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Dashboard (HTML with injected config) |
| `GET` | `/health` | Health check → `{"status": "ok"}` |
| `GET` | `/route` | User's route zones → `{"zones": [...]}` |
| `POST` | `/ingest` | Manually inject a test post |
| `WebSocket` | `/ws` | Real-time event stream |

### Manual Post Injection
```bash
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{"location_zone": "Silk Board Junction", "text": "Heavy flooding at the junction"}'
```

---

## 🏗 Architecture

```
                          ┌─────────────────┐
                          │   mock_feed.py   │  12 simulated posts
                          │  (continuous)    │  looping every ~40s
                          └────────┬────────┘
                                   │ async callback
                          ┌────────▼────────┐
                          │    main.py       │  FastAPI app
                          │  (pipeline)      │  lifespan + WebSocket
                          └──┬─────────┬────┘
                             │         │
                    ┌────────▼──┐  ┌───▼──────────┐
                    │classifier │  │route_matcher  │
                    │   .py     │  │    .py        │
                    └────┬──────┘  └───┬──────────┘
                         │             │
                  Groq API (opt)   5 zones + dedup
                         │             │
                    ┌────▼─────────────▼────┐
                    │   WebSocket broadcast  │
                    └────────────┬───────────┘
                                 │
                    ┌────────────▼───────────┐
                    │  static/index.html     │
                    │  Leaflet map + feed    │
                    │  shake/flash/sound     │
                    └────────────────────────┘
```

---

## 📁 Project Structure

```
transitpulse/
├── main.py               # FastAPI app, WebSocket, lifespan feed
├── classifier.py          # Groq API + keyword fallback
├── route_matcher.py       # Zone matching + dedup cache
├── mock_feed.py           # Continuous simulated feed
├── static/
│   └── index.html         # Live dashboard (Leaflet + effects)
├── tests/
│   ├── __init__.py
│   ├── test_classifier.py   # 10 tests
│   ├── test_route_matcher.py # 10 tests
│   └── test_api.py           # 5 tests
├── .env.example
├── requirements.txt
└── README.md
```

---

## 🚫 What This Is NOT

- No user authentication
- No persistent database (in-memory state only)
- No real social media API integration (simulated feed)
- No mobile app
- No deployment config (Docker, CI/CD)
- No multi-user route management

This is a **focused functional prototype** that runs with a single `uvicorn main:app --reload` command.

---

## 📜 License

MIT
