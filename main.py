"""FastAPI application for TransitPulse real-time hazard alerting."""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from classifier import classify_post
from mock_feed import stream_feed
from route_matcher import (
    get_route_zones,
    is_duplicate,
    is_on_route,
    mark_alerted,
)

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── Connected WebSocket clients ──────────────────────────────────────
connected_clients: list[WebSocket] = []


# ── Pydantic models ─────────────────────────────────────────────────
class IngestBody(BaseModel):
    """Schema for the POST /ingest request body."""

    location_zone: str
    text: str


# ── Broadcast helper ─────────────────────────────────────────────────
async def broadcast(message: dict[str, Any]) -> None:
    """Send a JSON message to every connected WebSocket client."""
    disconnected: list[WebSocket] = []
    for ws in connected_clients:
        try:
            await ws.send_json(message)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        connected_clients.remove(ws)


# ── Post processing pipeline ────────────────────────────────────────
async def process_post(post: dict[str, str]) -> None:
    """Classify a post, check route/dedup, and broadcast results."""
    zone = post["location_zone"]
    text = post["text"]

    # Always broadcast ingestion event
    await broadcast({"type": "ingestion", "zone": zone, "text": text})

    result = await classify_post(text)
    if result is None:
        logger.info("Post from %s rejected (low confidence or parse error)", zone)
        return

    if not result.get("is_hazard", False):
        logger.info("Post from %s classified as non-hazard", zone)
        return

    if not is_on_route(zone):
        logger.info("Hazard in %s is off-route — skipping alert", zone)
        return

    category = result.get("category", "Unknown")
    if is_duplicate(zone, category):
        return

    mark_alerted(zone, category)
    alert = _build_alert(zone, category, result, text)
    logger.info("🚨 ALERT broadcast: %s — %s (%s)", zone, category, result.get("severity"))
    await broadcast(alert)


def _build_alert(
    zone: str, category: str, result: dict[str, Any], text: str
) -> dict[str, Any]:
    """Construct the alert payload sent to WebSocket clients."""
    return {
        "type": "alert",
        "zone": zone,
        "category": category,
        "severity": result.get("severity", "MEDIUM"),
        "confidence": round(result.get("confidence", 0.0), 2),
        "reason": f"{category} at {zone}",
        "source_text": text,
        "timestamp": datetime.now().strftime("%H:%M:%S"),
    }


# ── Lifespan (startup / shutdown) ───────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start the mock-feed background task on startup."""
    logger.info("TransitPulse starting — launching feed simulator")
    task = asyncio.create_task(stream_feed(process_post))
    yield
    task.cancel()
    logger.info("TransitPulse shutting down")


# ── FastAPI app ──────────────────────────────────────────────────────
app = FastAPI(title="TransitPulse", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://localhost:8000", "http://127.0.0.1:8000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routes ───────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def serve_dashboard() -> HTMLResponse:
    """Serve the dashboard HTML with the Maps API key injected."""
    html_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    with open(html_path, "r", encoding="utf-8") as fh:
        html = fh.read()
    maps_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
    html = html.replace("__MAPS_KEY__", maps_key)
    return HTMLResponse(content=html)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Simple health probe."""
    return {"status": "ok"}


@app.get("/route")
async def get_route() -> dict[str, list[str]]:
    """Return the user's active route zones."""
    return {"zones": get_route_zones()}


@app.post("/ingest")
async def ingest_post(body: IngestBody) -> dict[str, str]:
    """Manually inject a test post into the processing pipeline."""
    logger.info("Manual ingest: %s — %s", body.location_zone, body.text[:60])
    await process_post({"location_zone": body.location_zone, "text": body.text})
    return {"status": "accepted"}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    """Handle a WebSocket connection for real-time event streaming."""
    await ws.accept()
    connected_clients.append(ws)
    logger.info("WebSocket client connected (%d total)", len(connected_clients))
    try:
        while True:
            await ws.receive_text()  # keep connection alive
    except WebSocketDisconnect:
        connected_clients.remove(ws)
        logger.info("WebSocket client disconnected (%d remaining)", len(connected_clients))
