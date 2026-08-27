"""
Central Server for the Multi-Zone Crowd Density & Urban Monitoring System.

Features:
1. Multi-Backend Vision Inference:
   - YOLOv8 with ByteTrack persistent object tracking.
   - Virtual Restricted Zone & Loitering Detection (triggers alarms on dwell > threshold).
   - Stray Animal Detection & Vehicle Classification.
   - PyTorch DensityNet for dense macro-crowds.
   - Hybrid auto-switching mode.
2. Optimized for DSLR Canon 700D (HDMI / USB Webcam Utility) & standard webcams.
3. MQTT Publisher (Mosquitto) for ESP8266, ESP32, and Arduino UNO actuators.
4. FastAPI REST API for Alexa Voice Skill queries.
5. Live Web Surveillance Visualizer, MJPEG streaming, & Live Event Log at http://localhost:8000/

Usage:
  # Using YOLOv8 with Loitering & Analytics (Default):
  python server.py --backend yolo --camera 1 --loiter-time 5

  # With custom YOLO model:
  python server.py --backend yolo --yolo-model yolov8s.pt --camera 1

  # Disable virtual zones:
  python server.py --backend yolo --no-zones --camera 1
"""

import sys
import os
import threading
import time
import argparse
from datetime import datetime
from collections import deque

# Include project modules in path
MODULES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "modules"))
sys.path.insert(0, MODULES_DIR)
sys.path.insert(0, os.path.join(MODULES_DIR, "crowd_density"))

import cv2
import numpy as np
import torch
import paho.mqtt.client as mqtt
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse, Response, JSONResponse
import uvicorn

from vision_detector import VisionDetector
from src.model import density_to_percentage


# ---------------------------------------------------------------------------
# Shared State & Event Logger (Thread-Safe)
# ---------------------------------------------------------------------------
class SharedState:
    def __init__(self):
        self.lock = threading.Lock()
        self.count = 0.0
        self.density_pct = 0.0
        self.tier = "normal"
        self.animals_count = 0
        self.vehicles_count = 0
        self.loitering_count = 0
        self.active_alert = "none"
        self.fps = 0.0
        self.backend = "yolo"
        self.last_updated = 0.0
        self.latest_frame_jpeg = None
        self.events_log = deque(maxlen=60)  # Store last 60 events

    def update(self, count, density_pct, tier, animals=0, vehicles=0, loitering=0,
               active_alert="none", fps=0.0, backend="yolo", new_events=None):
        with self.lock:
            self.count = count
            self.density_pct = density_pct
            self.tier = tier
            self.animals_count = animals
            self.vehicles_count = vehicles
            self.loitering_count = loitering
            self.active_alert = active_alert
            self.fps = fps
            self.backend = backend
            self.last_updated = time.time()

            if new_events:
                for evt in new_events:
                    evt_time = datetime.now().strftime("%H:%M:%S")
                    evt_record = {
                        "time": evt_time,
                        "type": evt.get("type", "INFO"),
                        "message": evt.get("message", ""),
                    }
                    self.events_log.appendleft(evt_record)

    def set_frame(self, jpeg_bytes):
        with self.lock:
            self.latest_frame_jpeg = jpeg_bytes

    def get_frame(self):
        with self.lock:
            return self.latest_frame_jpeg

    def get_events(self):
        with self.lock:
            return list(self.events_log)

    def snapshot(self):
        with self.lock:
            return {
                "count": round(self.count, 1),
                "density_pct": round(self.density_pct, 1),
                "tier": self.tier,
                "animals": self.animals_count,
                "vehicles": self.vehicles_count,
                "loitering": self.loitering_count,
                "active_alert": self.active_alert,
                "fps": round(self.fps, 1),
                "backend": self.backend,
                "last_updated": self.last_updated,
            }


state = SharedState()


def tier_from_pct(pct, busy_threshold=60, critical_threshold=90):
    if pct >= critical_threshold:
        return "critical"
    elif pct >= busy_threshold:
        return "busy"
    return "normal"


# ---------------------------------------------------------------------------
# MQTT Publisher
# ---------------------------------------------------------------------------
def make_mqtt_client(broker_host, broker_port):
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        client.connect(broker_host, broker_port, keepalive=60)
        client.loop_start()
        print(f"[MQTT] Connected to broker at {broker_host}:{broker_port}")
        return client
    except Exception as e:
        print(f"[MQTT] Warning: Could not connect to MQTT broker ({e}). Running in standalone mode.")
        return None


def publish_reading(mqtt_client, zone, count, density_pct, tier, animals=0, vehicles=0, alert="none"):
    if mqtt_client is None:
        return
    try:
        mqtt_client.publish(f"crowd/{zone}/count", f"{count:.1f}", retain=True)
        mqtt_client.publish(f"crowd/{zone}/density_pct", f"{density_pct:.1f}", retain=True)
        mqtt_client.publish(f"crowd/{zone}/tier", tier, retain=True)
        mqtt_client.publish(f"crowd/{zone}/alert", alert, retain=True)
        if animals > 0:
            mqtt_client.publish(f"crowd/{zone}/animals", str(animals), retain=True)
        if vehicles > 0:
            mqtt_client.publish(f"crowd/{zone}/vehicles", str(vehicles), retain=True)
    except Exception as e:
        print(f"[MQTT] Publish error: {e}")


# ---------------------------------------------------------------------------
# Camera Ingestion & Analytics Loop
# ---------------------------------------------------------------------------
def open_camera(camera_index):
    """
    Opens video stream with robust backend auto-detection for Canon EOS Webcam Utility / Capture Cards / Webcams.
    """
    # 1. Try standard default backend (best for EOS Webcam Utility / USB)
    cap = cv2.VideoCapture(camera_index)
    if cap.isOpened():
        ret, _ = cap.read()
        if ret:
            print(f"[Camera] Opened camera index {camera_index} via default backend")
            return cap
        cap.release()

    # 2. Try DirectShow backend (best for hardware HDMI capture dongles)
    if os.name == 'nt':
        try:
            cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
            if cap.isOpened():
                print(f"[Camera] Opened camera index {camera_index} via DirectShow (DSHOW)")
                return cap
        except Exception:
            pass
    
    # Fallback to standard
    cap = cv2.VideoCapture(camera_index)
    if cap.isOpened():
        return cap
    
    raise RuntimeError(f"Could not open camera index {camera_index}. Check camera/USB connection.")


def camera_loop(detector: VisionDetector, camera_index, capacity, zone, mqtt_client,
                busy_threshold=60, critical_threshold=90, publish_interval=1.5,
                width=1280, height=720):
    cap = open_camera(camera_index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"[Camera] Stream initialized: {actual_w}x{actual_h} | Capacity: {capacity} | Zone: {zone}")

    last_publish = 0.0
    frame_count = 0
    fps_start_time = time.time()
    current_fps = 0.0

    while True:
        ret, frame = cap.read()
        if not ret:
            print("[Camera] Frame read dropped, retrying in 0.5s...")
            time.sleep(0.5)
            continue

        frame_count += 1
        elapsed = time.time() - fps_start_time
        if elapsed >= 1.0:
            current_fps = frame_count / elapsed
            frame_count = 0
            fps_start_time = time.time()

        # Run vision inference & multi-task analytics
        annotated_frame, count, detections, stats = detector.detect(frame, draw_annotations=True)

        pct = density_to_percentage(torch.tensor([count]), capacity).item()
        tier = tier_from_pct(pct, busy_threshold, critical_threshold)
        animals = stats.get("animals", 0)
        vehicles = stats.get("vehicles", 0)
        loitering = stats.get("loitering_count", 0)
        active_alert = stats.get("active_alert", "none")
        events = stats.get("events", [])
        backend_name = stats.get("backend", detector.backend)

        # 🚨 Automatic Hardware Escalation: Loitering triggers immediate CRITICAL tier
        if loitering > 0:
            tier = "critical"

        # Draw real-time HUD telemetry on the video frame
        h, w, _ = annotated_frame.shape
        hud_bg = np.zeros((70, w, 3), dtype=np.uint8)
        
        # Color badge based on tier or alert
        if loitering > 0:
            badge_color = (0, 0, 220)  # Bright Red
            badge_text = "🚨 LOITERING"
        elif active_alert == "stray_animal":
            badge_color = (255, 140, 0)  # Orange
            badge_text = "🐾 ANIMAL ALERT"
        else:
            badge_color = (0, 180, 0) if tier == "normal" else ((0, 165, 255) if tier == "busy" else (0, 0, 220))
            badge_text = f"{tier.upper()}"

        cv2.rectangle(hud_bg, (0, 0), (w, 70), (25, 25, 25), -1)
        cv2.rectangle(hud_bg, (15, 12), (230, 58), badge_color, -1)
        cv2.putText(hud_bg, badge_text, (25, 44), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 2, cv2.LINE_AA)

        info_text = f"People: {int(count)} ({pct:.0f}%) | Animals: {animals} | Vehicles: {vehicles} | FPS: {current_fps:.1f}"
        cv2.putText(hud_bg, info_text, (250, 43), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (230, 230, 230), 2, cv2.LINE_AA)

        # Combine frame with top HUD
        display_frame = np.vstack([hud_bg, annotated_frame])

        # Encode JPEG for live browser streaming
        ret_enc, jpeg = cv2.imencode(".jpg", display_frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if ret_enc:
            state.set_frame(jpeg.tobytes())

        state.update(count, pct, tier, animals=animals, vehicles=vehicles, loitering=loitering,
                     active_alert=active_alert, fps=current_fps, backend=backend_name, new_events=events)

        now = time.time()
        if now - last_publish >= publish_interval:
            publish_reading(mqtt_client, zone, count, pct, tier, animals=animals, vehicles=vehicles, alert=active_alert)
            log_str = f"[{backend_name.upper()}] Count={count:.0f} | Density={pct:.1f}% | Tier={tier} | Animals={animals} | Vehicles={vehicles}"
            if loitering > 0:
                log_str += f" | 🚨 LOITERING={loitering}"
            print(log_str)
            last_publish = now

        time.sleep(0.01)


# ---------------------------------------------------------------------------
# FastAPI HTTP Server & Web Visualizer
# ---------------------------------------------------------------------------
app = FastAPI(title="Urban Monitoring & Multi-Task Surveillance System")


@app.get("/reading/{zone}")
def get_reading(zone: str):
    """Alexa Voice Skill and REST clients query this endpoint."""
    return state.snapshot()


@app.get("/health")
def health():
    return {"status": "ok", "backend": state.backend}


@app.get("/events")
def get_events():
    """Returns the list of recent security events."""
    return JSONResponse(content=state.get_events())


@app.get("/latest_frame.jpg")
def latest_frame():
    """Returns the most recent annotated frame as a single JPEG."""
    frame_bytes = state.get_frame()
    if frame_bytes is None:
        blank = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(blank, "Waiting for camera...", (180, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        _, jpeg = cv2.imencode(".jpg", blank)
        frame_bytes = jpeg.tobytes()
    return Response(content=frame_bytes, media_type="image/jpeg",
                    headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache"})


def generate_mjpeg_stream():
    """Generator for live MJPEG video stream with standard multipart headers."""
    while True:
        frame_bytes = state.get_frame()
        if frame_bytes is None:
            time.sleep(0.05)
            continue
        yield (b"--frame\r\n"
               b"Content-Type: image/jpeg\r\n"
               b"Content-Length: " + str(len(frame_bytes)).encode() + b"\r\n\r\n"
               + frame_bytes + b"\r\n")
        time.sleep(0.033)


@app.get("/video_feed")
def video_feed():
    """Live MJPEG video streaming route for web browsers."""
    return StreamingResponse(
        generate_mjpeg_stream(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache"}
    )


@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
def web_dashboard():
    """Real-time browser surveillance dashboard."""
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Urban Monitoring Live Surveillance</title>
        <style>
            * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', Roboto, sans-serif; }
            body { background: #0f1117; color: #e2e8f0; min-height: 100vh; padding: 20px; }
            .container { max-width: 1360px; margin: 0 auto; }
            header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; padding-bottom: 16px; border-bottom: 1px solid #1e293b; }
            h1 { font-size: 24px; font-weight: 700; color: #38bdf8; display: flex; align-items: center; gap: 10px; }
            .badge { padding: 5px 14px; border-radius: 9999px; font-size: 13px; font-weight: 700; text-transform: uppercase; }
            .badge-normal { background: #166534; color: #4ade80; }
            .badge-busy { background: #854d0e; color: #facc15; }
            .badge-critical { background: #991b1b; color: #f87171; }
            .badge-alert { background: #dc2626; color: #ffffff; animation: pulse 1s infinite alternate; }
            @keyframes pulse { from { opacity: 0.8; } to { opacity: 1.0; transform: scale(1.03); } }
            .grid { display: grid; grid-template-columns: 2.1fr 1fr; gap: 20px; }
            @media (max-width: 1000px) { .grid { grid-template-columns: 1fr; } }
            .card { background: #1e222d; border-radius: 12px; padding: 18px; border: 1px solid #334155; }
            .video-container { border-radius: 8px; overflow: hidden; background: #000; display: flex; justify-content: center; align-items: center; min-height: 480px; }
            .video-container img { width: 100%; height: auto; display: block; object-fit: contain; }
            .stats-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 16px; }
            .stat-box { background: #11141c; padding: 14px; border-radius: 8px; border: 1px solid #283347; text-align: center; }
            .stat-value { font-size: 28px; font-weight: 800; color: #f8fafc; }
            .stat-label { font-size: 12px; color: #94a3b8; text-transform: uppercase; margin-top: 3px; }
            .status-row { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #283347; font-size: 13px; }
            .status-row:last-child { border-bottom: none; }
            .status-val { font-weight: 600; color: #cbd5e1; }
            .events-box { max-height: 220px; overflow-y: auto; background: #11141c; border-radius: 8px; border: 1px solid #283347; padding: 10px; font-size: 12px; font-family: monospace; }
            .event-item { padding: 6px 8px; border-bottom: 1px solid #1e293b; display: flex; gap: 8px; align-items: center; }
            .event-item:last-child { border-bottom: none; }
            .event-time { color: #64748b; font-weight: bold; }
            .event-alert { color: #f87171; background: rgba(220,38,38,0.1); border-left: 3px solid #ef4444; border-radius: 4px; }
            .event-animal { color: #fb923c; }
            .event-flow { color: #38bdf8; }
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <h1>📷 Urban Monitoring System — Live Surveillance</h1>
                <div id="tier-badge" class="badge badge-normal">NORMAL</div>
            </header>
            <div class="grid">
                <div class="card">
                    <div class="video-container">
                        <img id="live-stream" src="/video_feed" alt="Live Camera Feed (DSLR 700D)" />
                    </div>
                </div>
                <div>
                    <div class="card" style="margin-bottom: 16px;">
                        <h2 style="font-size: 15px; color: #94a3b8; margin-bottom: 12px;">REAL-TIME TELEMETRY</h2>
                        <div class="stats-grid">
                            <div class="stat-box">
                                <div id="stat-count" class="stat-value">0</div>
                                <div class="stat-label">People Active</div>
                            </div>
                            <div class="stat-box">
                                <div id="stat-pct" class="stat-value">0%</div>
                                <div class="stat-label">Capacity Density</div>
                            </div>
                            <div class="stat-box">
                                <div id="stat-animals" class="stat-value">0</div>
                                <div class="stat-label">Stray Animals</div>
                            </div>
                            <div class="stat-box">
                                <div id="stat-vehicles" class="stat-value">0</div>
                                <div class="stat-label">Vehicles</div>
                            </div>
                        </div>
                        <div class="status-row"><span>Inference Engine</span><span id="tel-backend" class="status-val">YOLOv8 + ByteTrack</span></div>
                        <div class="status-row"><span>Camera FPS</span><span id="tel-fps" class="status-val">0.0</span></div>
                        <div class="status-row"><span>Active Alert</span><span id="tel-alert" class="status-val" style="color: #4ade80;">None</span></div>
                        <div class="status-row"><span>Alexa API</span><span class="status-val" style="color: #4ade80;">Active (:8000)</span></div>
                    </div>
                    <div class="card">
                        <h2 style="font-size: 15px; color: #94a3b8; margin-bottom: 12px;">SECURITY EVENT LOG</h2>
                        <div id="events-list" class="events-box">
                            <div class="event-item"><span class="event-time">--:--:--</span><span>Surveillance system initialized.</span></div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        <script>
            const img = document.getElementById('live-stream');
            let usePolling = false;

            img.onerror = function() {
                if (!usePolling) {
                    usePolling = true;
                    pollFrames();
                }
            };

            function pollFrames() {
                if (usePolling) {
                    img.src = '/latest_frame.jpg?t=' + Date.now();
                    setTimeout(pollFrames, 60);
                }
            }

            async function updateStats() {
                try {
                    const res = await fetch('/reading/zone1');
                    if (res.ok) {
                        const data = await res.json();
                        document.getElementById('stat-count').innerText = Math.round(data.count);
                        document.getElementById('stat-pct').innerText = Math.round(data.density_pct) + '%';
                        document.getElementById('stat-animals').innerText = data.animals || 0;
                        document.getElementById('stat-vehicles').innerText = data.vehicles || 0;
                        document.getElementById('tel-fps').innerText = data.fps || '0.0';
                        document.getElementById('tel-backend').innerText = data.backend || 'YOLOv8';
                        
                        const badge = document.getElementById('tier-badge');
                        const alertEl = document.getElementById('tel-alert');

                        if (data.loitering > 0) {
                            badge.innerText = '🚨 LOITERING ALERT';
                            badge.className = 'badge badge-alert';
                            alertEl.innerText = 'Loitering in Restricted Zone';
                            alertEl.style.color = '#f87171';
                        } else if (data.active_alert === 'stray_animal') {
                            badge.innerText = '🐾 STRAY ANIMAL';
                            badge.className = 'badge badge-busy';
                            alertEl.innerText = 'Stray Animal Detected';
                            alertEl.style.color = '#fb923c';
                        } else {
                            badge.innerText = data.tier.toUpperCase();
                            badge.className = 'badge badge-' + data.tier;
                            alertEl.innerText = 'None (Normal)';
                            alertEl.style.color = '#4ade80';
                        }
                    }
                } catch (e) {
                    console.error('Stats fetch error:', e);
                }
            }

            async function updateEvents() {
                try {
                    const res = await fetch('/events');
                    if (res.ok) {
                        const events = await res.json();
                        if (events && events.length > 0) {
                            const list = document.getElementById('events-list');
                            list.innerHTML = events.map(e => {
                                let cls = '';
                                if (e.type.includes('LOITERING') || e.type.includes('ALERT')) cls = 'event-alert';
                                else if (e.type.includes('ANIMAL')) cls = 'event-animal';
                                else if (e.type.includes('VEHICLE')) cls = 'event-flow';
                                return `<div class="event-item ${cls}"><span class="event-time">${e.time}</span><span>${e.message}</span></div>`;
                            }).join('');
                        }
                    }
                } catch (e) {
                    console.error('Events fetch error:', e);
                }
            }

            setInterval(updateStats, 800);
            setInterval(updateEvents, 1200);
            updateStats();
            updateEvents();
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Urban Monitoring & Multi-Task Surveillance Server")
    parser.add_argument("--backend", choices=["yolo", "density", "hybrid"], default="yolo",
                        help="Vision inference backend: 'yolo' (default), 'density', or 'hybrid'")
    parser.add_argument("--yolo-model", default="yolov8n.pt",
                        help="YOLO model weights (e.g. yolov8n.pt, yolov8s.pt, yolov8m.pt)")
    parser.add_argument("--checkpoint", default=None,
                        help="Path to DensityNet checkpoint (.pt) for density/hybrid backends")
    parser.add_argument("--conf", type=float, default=0.35,
                        help="YOLO detection confidence threshold (default: 0.35)")
    parser.add_argument("--no-zones", action="store_true",
                        help="Disable virtual restricted zones")
    parser.add_argument("--loiter-time", type=float, default=5.0,
                        help="Loitering threshold in seconds (default: 5.0s)")
    parser.add_argument("--camera", type=int, default=1,
                        help="Camera device index (default: 1 for Canon 700D, 0 for webcam)")
    parser.add_argument("--capacity", type=int, default=50,
                        help="Monitored area capacity limit")
    parser.add_argument("--zone", default="zone1",
                        help="Monitored zone identifier")
    parser.add_argument("--mqtt-host", default="localhost",
                        help="MQTT broker host IP")
    parser.add_argument("--mqtt-port", type=int, default=1883,
                        help="MQTT broker port")
    parser.add_argument("--api-port", type=int, default=8000,
                        help="FastAPI HTTP API port")
    parser.add_argument("--width", type=int, default=1280,
                        help="Capture resolution width")
    parser.add_argument("--height", type=int, default=720,
                        help="Capture resolution height")
    args = parser.parse_args()

    # Initialize Vision Detector with Multi-Task Modules
    detector = VisionDetector(
        backend=args.backend,
        checkpoint=args.checkpoint,
        yolo_model=args.yolo_model,
        conf_threshold=args.conf,
        enable_zones=not args.no_zones,
        loiter_time=args.loiter_time
    )

    # Initialize MQTT Client
    mqtt_client = make_mqtt_client(args.mqtt_host, args.mqtt_port)

    # Launch Camera + Inference loop
    cam_thread = threading.Thread(
        target=camera_loop,
        args=(detector, args.camera, args.capacity, args.zone, mqtt_client),
        kwargs={
            "width": args.width,
            "height": args.height,
            "publish_interval": 1.5
        },
        daemon=True,
    )
    cam_thread.start()

    print(f"\n==================================================================")
    print(f"🚀 Urban Monitoring Multi-Task Surveillance Server is LIVE!")
    print(f"   • Dashboard:     http://localhost:{args.api_port}/")
    print(f"   • Video Feed:    http://localhost:{args.api_port}/video_feed")
    print(f"   • Alexa API:     http://localhost:{args.api_port}/reading/{args.zone}")
    print(f"   • Security Log:  http://localhost:{args.api_port}/events")
    print(f"   • Virtual Zones: {'ENABLED (Max ' + str(args.loiter_time) + 's)' if not args.no_zones else 'DISABLED'}")
    print(f"   • Backend:       {args.backend.upper()} ({args.yolo_model})")
    print(f"   • Camera:        Device index {args.camera} ({args.width}x{args.height})")
    print(f"==================================================================\n")

    uvicorn.run(app, host="0.0.0.0", port=args.api_port, log_level="warning")
