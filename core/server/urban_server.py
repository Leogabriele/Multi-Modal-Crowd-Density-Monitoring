"""
Urban Monitoring & Multi-Task Cyber-Physical Surveillance Server
---------------------------------------------------------------
Full-Stack Edge Surveillance Engine with:
1. Multi-Backend Vision AI (YOLOv8 ByteTrack + ShanghaiTech Dilated DensityNet + Hybrid)
2. Interactive Dynamic Restricted Zone Customizer (Presets & Live Coordinate Sliders)
3. Closed-Loop Hardware Actuation via MQTT (ESP8266 LED + ESP32/UNO Servo Gate + Buzzer)
4. Innovation 2: Real-time Green CPS & Bandwidth Efficiency Telemetry (99.98% Reduction)
5. Amazon Alexa ASK SDK REST Voice Endpoint (:8000/reading/zone1)
6. Multi-Client MJPEG Streamer & Security Event Logger

Usage:
  # Using YOLOv8 with custom center small zone (Default):
  python urban_server.py --backend yolo --camera 1 --loiter-time 5 --zone-preset center_small

  # Using custom exact bounding box:
  python urban_server.py --backend yolo --camera 1 --zone-bbox 0.35 0.30 0.65 0.70

  # Using Real Crowd Density CNN:
  python urban_server.py --backend density --camera 1
"""

import sys
import os
import threading
import time
import argparse
from datetime import datetime
from collections import deque
from pydantic import BaseModel
from typing import List, Optional

# Include project modules in path
MODULES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "modules"))
sys.path.insert(0, MODULES_DIR)
sys.path.insert(0, os.path.join(MODULES_DIR, "crowd_density"))

import cv2
import numpy as np
import torch
import paho.mqtt.client as mqtt
from fastapi import FastAPI, Body
from fastapi.responses import HTMLResponse, StreamingResponse, Response, JSONResponse
import uvicorn

from vision_detector import VisionDetector
from src.model import density_to_percentage
from edge_efficiency_analyzer import EdgeEfficiencyAnalyzer

# Initialize Green CPS & Bandwidth Efficiency Analyzer
efficiency_analyzer = EdgeEfficiencyAnalyzer(raw_bitrate_mbps=10.0)

# Global detector reference for dynamic API configuration
global_detector = None


# ---------------------------------------------------------------------------
# Shared State & Event Logger (Thread-Safe)
# ---------------------------------------------------------------------------
class SharedState:
    def __init__(self):
        self.lock = threading.Lock()
        self.count = 0.0
        self.density_pct = 0.0
        self.tier = "normal"
        self.animals = 0
        self.vehicles = 0
        self.loitering = 0
        self.active_alert = "none"
        self.fps = 0.0
        self.backend = "yolo"
        self.frame = None
        self.raw_frame = None
        self.events = deque(maxlen=40)
        self.last_update = time.time()

    def update(self, count, density_pct, tier, animals=0, vehicles=0, loitering=0,
               active_alert="none", fps=0.0, backend="yolo", new_events=None):
        with self.lock:
            self.count = count
            self.density_pct = density_pct
            self.tier = tier
            self.animals = animals
            self.vehicles = vehicles
            self.loitering = loitering
            self.active_alert = active_alert
            self.fps = fps
            self.backend = backend
            self.last_update = time.time()
            if new_events:
                for ev in new_events:
                    self.events.appendleft(ev)

    def set_frame(self, frame_jpeg, raw_frame=None):
        with self.lock:
            self.frame = frame_jpeg
            if raw_frame is not None:
                self.raw_frame = raw_frame

    def get_frame(self):
        with self.lock:
            return self.frame

    def get_raw_frame(self):
        with self.lock:
            return self.raw_frame.copy() if self.raw_frame is not None else None

    def snapshot(self):
        with self.lock:
            eff = efficiency_analyzer.get_telemetry()
            zone_cfg = global_detector.get_zone_config() if global_detector else {}
            return {
                "count": round(self.count, 1),
                "density_percentage": round(self.density_pct, 1),
                "density_pct": round(self.density_pct, 1),
                "tier": self.tier,
                "animals": self.animals,
                "vehicles": self.vehicles,
                "loitering": self.loitering,
                "active_alert": self.active_alert,
                "fps": round(self.fps, 1),
                "backend": self.backend,
                "timestamp": self.last_update,
                "efficiency": eff,
                "zone_config": zone_cfg
            }

    def get_events(self):
        with self.lock:
            return list(self.events)


state = SharedState()


# ---------------------------------------------------------------------------
# Tier Categorization & Hardware MQTT Bridge
# ---------------------------------------------------------------------------
def tier_from_pct(pct, busy_threshold=60.0, critical_threshold=85.0):
    if pct >= critical_threshold:
        return "critical"
    elif pct >= busy_threshold:
        return "busy"
    return "normal"


def make_mqtt_client(broker_host="localhost", broker_port=1883):
    try:
        # Check for paho-mqtt v2 CallbackAPIVersion
        if hasattr(mqtt, "CallbackAPIVersion"):
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id="UrbanMonitoringServer")
        else:
            client = mqtt.Client(client_id="UrbanMonitoringServer")
    except Exception:
        client = mqtt.Client(client_id="UrbanMonitoringServer")
    try:
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
        p1 = f"crowd/{zone}/count:{count:.1f}"
        p2 = f"crowd/{zone}/density_pct:{density_pct:.1f}"
        p3 = f"crowd/{zone}/tier:{tier}"
        p4 = f"crowd/{zone}/alert:{alert}"
        
        mqtt_client.publish(f"crowd/{zone}/count", f"{count:.1f}", retain=True)
        mqtt_client.publish(f"crowd/{zone}/density_pct", f"{density_pct:.1f}", retain=True)
        mqtt_client.publish(f"crowd/{zone}/tier", tier, retain=True)
        mqtt_client.publish(f"crowd/{zone}/alert", alert, retain=True)

        efficiency_analyzer.record_mqtt_publish(p1)
        efficiency_analyzer.record_mqtt_publish(p2)
        efficiency_analyzer.record_mqtt_publish(p3)
        efficiency_analyzer.record_mqtt_publish(p4)

        if animals > 0:
            mqtt_client.publish(f"crowd/{zone}/animals", str(animals), retain=True)
            efficiency_analyzer.record_mqtt_publish(f"crowd/{zone}/animals:{animals}")
        if vehicles > 0:
            mqtt_client.publish(f"crowd/{zone}/vehicles", str(vehicles), retain=True)
            efficiency_analyzer.record_mqtt_publish(f"crowd/{zone}/vehicles:{vehicles}")
    except Exception as e:
        print(f"[MQTT] Publish error: {e}")


# ---------------------------------------------------------------------------
# Camera Ingestion & Analytics Loop
# ---------------------------------------------------------------------------
def open_camera(camera_index):
    """Opens video stream with robust backend auto-detection for Canon EOS Webcam Utility / USB."""
    cap = cv2.VideoCapture(camera_index)
    if cap.isOpened():
        ret, _ = cap.read()
        if ret:
            print(f"[Camera] Opened camera index {camera_index} via default backend")
            return cap
        cap.release()

    if os.name == 'nt':
        try:
            cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
            if cap.isOpened():
                ret, _ = cap.read()
                if ret:
                    print(f"[Camera] Opened camera index {camera_index} via DirectShow (DSHOW)")
                    return cap
                cap.release()
        except Exception:
            pass

    cap = cv2.VideoCapture(camera_index, cv2.CAP_MSMF)
    if cap.isOpened():
        print(f"[Camera] Opened camera index {camera_index} via MediaFoundation (MSMF)")
        return cap

    return None


def camera_loop(detector, camera_index, capacity, zone, mqtt_client,
                busy_threshold=60.0, critical_threshold=85.0,
                width=1280, height=720, publish_interval=1.0):
    cap = open_camera(camera_index)
    if cap is None or not cap.isOpened():
        print(f"[Camera] Error: Could not open camera {camera_index}. Check USB connection.")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

    fps_start_time = time.time()
    frame_count = 0
    current_fps = 0.0
    last_publish = 0.0

    print(f"[Camera] Stream initialized: {width}x{height} | Capacity: {capacity} | Zone: {zone}")

    while True:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.05)
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

        # Draw real-time HUD telemetry on video frame
        h, w, _ = annotated_frame.shape
        hud_bg = np.zeros((70, w, 3), dtype=np.uint8)
        
        if loitering > 0:
            badge_color = (0, 0, 220)
            badge_text = "🚨 LOITERING"
        elif tier == "critical":
            badge_color = (0, 0, 220)
            badge_text = "CRITICAL"
        elif tier == "busy":
            badge_color = (0, 165, 255)
            badge_text = "BUSY"
        else:
            badge_color = (0, 180, 0)
            badge_text = "NORMAL"

        cv2.rectangle(hud_bg, (15, 12), (150, 58), badge_color, -1)
        cv2.putText(hud_bg, badge_text, (25, 43), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        info_text = f"People: {count:.0f} ({pct:.0f}%) | Animals: {animals} | Vehicles: {vehicles} | FPS: {current_fps:.1f}"
        cv2.putText(hud_bg, info_text, (170, 43), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (240, 240, 240), 2)

        annotated_frame = np.vstack([hud_bg, annotated_frame])

        # Encode JPEG for live MJPEG streaming
        _, jpeg = cv2.imencode('.jpg', annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
        state.set_frame(jpeg.tobytes(), raw_frame=frame)

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


class ZoneConfigModel(BaseModel):
    preset: Optional[str] = None
    bbox: Optional[List[float]] = None


@app.get("/reading/{zone}")
def get_reading(zone: str):
    """Alexa Voice Skill and REST clients query this endpoint."""
    return state.snapshot()


@app.get("/telemetry/efficiency")
def get_efficiency_telemetry():
    """Returns Green CPS edge bandwidth & energy conservation metrics."""
    return efficiency_analyzer.get_telemetry()


@app.get("/zone/config")
def get_zone_config():
    """Returns current restricted zone configuration."""
    if global_detector:
        return global_detector.get_zone_config()
    return {}


@app.post("/zone/config")
def set_zone_config(config: ZoneConfigModel):
    """Dynamically updates restricted zone preset or bbox without restarting server."""
    if global_detector:
        if config.preset:
            global_detector.set_zone_preset(config.preset)
        elif config.bbox and len(config.bbox) == 4:
            global_detector.set_zone_bbox(config.bbox)
        return {"status": "success", "zone": global_detector.get_zone_config()}
    return {"status": "error", "message": "Detector not initialized"}


@app.post("/zone/auto_pool")
def auto_detect_pool_endpoint():
    """Automatically analyzes live camera feed to detect and restrict swimming pool water boundary."""
    if global_detector:
        raw_f = state.get_raw_frame()
        if raw_f is not None:
            res = global_detector.auto_detect_pool_zone(raw_f)
            if res.get("detected"):
                state.events.appendleft({
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "type": "zone",
                    "message": "🏊 Swimming pool automatically identified and set as Restricted Safety Zone."
                })
            return res
        return {"status": "waiting_for_frame", "detected": False, "message": "Camera frame not ready yet"}
    return {"status": "error", "detected": False, "message": "Detector not initialized"}


@app.get("/health")
def health():
    return {"status": "ok", "backend": state.backend}


@app.get("/events")
def get_events():
    """Returns list of recent security events."""
    return JSONResponse(content=state.get_events())


@app.get("/latest_frame.jpg")
def latest_frame():
    """Returns most recent annotated frame as a single JPEG."""
    frame_bytes = state.get_frame()
    if frame_bytes is None:
        blank = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(blank, "Waiting for camera...", (180, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        _, jpeg = cv2.imencode(".jpg", blank)
        frame_bytes = jpeg.tobytes()
    return Response(content=frame_bytes, media_type="image/jpeg")


def generate_frames():
    """MJPEG streaming generator."""
    while True:
        frame_bytes = state.get_frame()
        if frame_bytes is not None:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        time.sleep(0.04)


@app.get("/video_feed")
def video_feed():
    """MJPEG Live video feed for web dashboard."""
    return StreamingResponse(
        generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
def web_dashboard():
    """Real-time browser surveillance dashboard with Dynamic Zone Configurator & Green CPS."""
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Urban Monitoring Live Surveillance & Zone Configurator</title>
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
            .card { background: #1e222d; border-radius: 12px; padding: 18px; border: 1px solid #334155; margin-bottom: 16px; }
            .video-container { border-radius: 8px; overflow: hidden; background: #000; display: flex; justify-content: center; align-items: center; min-height: 480px; }
            .video-container img { width: 100%; height: auto; display: block; object-fit: contain; }
            .stats-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 16px; }
            .stat-box { background: #11141c; padding: 14px; border-radius: 8px; border: 1px solid #283347; text-align: center; }
            .stat-value { font-size: 28px; font-weight: 800; color: #f8fafc; }
            .stat-label { font-size: 12px; color: #94a3b8; text-transform: uppercase; margin-top: 3px; }
            .status-row { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #283347; font-size: 13px; }
            .status-row:last-child { border-bottom: none; }
            .status-val { font-weight: 600; color: #cbd5e1; }
            .btn-group { display: flex; flex-wrap: wrap; gap: 8px; margin: 10px 0; }
            .btn { background: #334155; color: #f8fafc; border: 1px solid #475569; padding: 8px 14px; border-radius: 6px; cursor: pointer; font-size: 12px; font-weight: 600; transition: all 0.2s; }
            .btn:hover { background: #38bdf8; color: #0f172a; border-color: #38bdf8; }
            .btn.active { background: #0284c7; border-color: #38bdf8; color: #fff; }
            .slider-group { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 10px; }
            .slider-item { background: #11141c; padding: 10px; border-radius: 6px; border: 1px solid #283347; font-size: 12px; }
            .slider-item label { display: flex; justify-content: space-between; color: #94a3b8; margin-bottom: 4px; }
            .slider-item input[type="range"] { width: 100%; accent-color: #38bdf8; cursor: pointer; }
            .green-title { color: #4ade80; font-size: 14px; font-weight: 700; margin-bottom: 8px; display: flex; align-items: center; gap: 6px; }
            .progress-bar-bg { background: #1e293b; height: 10px; border-radius: 5px; overflow: hidden; margin: 8px 0; }
            .progress-bar-fill { background: #22c55e; height: 100%; width: 99.98%; transition: width 0.4s; }
            .events-box { max-height: 200px; overflow-y: auto; background: #11141c; border-radius: 8px; border: 1px solid #283347; padding: 10px; font-size: 12px; font-family: monospace; }
            .event-item { padding: 6px 8px; border-bottom: 1px solid #1e293b; display: flex; gap: 8px; align-items: center; }
            .event-item:last-child { border-bottom: none; }
            .event-time { color: #64748b; font-weight: bold; }
            .event-alert { color: #f87171; background: rgba(220,38,38,0.1); border-left: 3px solid #ef4444; border-radius: 4px; }
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <h1>📷 Urban Monitoring System — Live Surveillance</h1>
                <div id="tier-badge" class="badge badge-normal">NORMAL</div>
            </header>
            <div class="grid">
                <div>
                    <div class="card">
                        <div class="video-container">
                            <img id="live-stream" src="/video_feed" alt="Live Camera Feed (Canon 700D)" />
                        </div>
                    </div>
                    <!-- Dynamic Restricted Zone Customizer -->
                    <div class="card">
                        <h2 style="font-size: 15px; color: #38bdf8; margin-bottom: 8px;">🎯 VIRTUAL RESTRICTED ZONE CONFIGURATOR</h2>
                        <p style="font-size: 13px; color: #94a3b8;">
                            Select a preset or adjust the coordinate sliders to set your exact monitored restriction area:
                        </p>
                        <div class="btn-group">
                            <button class="btn" style="background: #0891b2; border-color: #06b6d4; color: #fff; font-weight: 700;" onclick="autoDetectPool()">🏊 Auto-Detect Swimming Pool</button>
                            <button class="btn" onclick="applyPreset('center_small')">🎯 Center Small (30%)</button>
                            <button class="btn" onclick="applyPreset('center_medium')">📦 Center Medium (50%)</button>
                            <button class="btn" onclick="applyPreset('left_half')">◀️ Left Area</button>
                            <button class="btn" onclick="applyPreset('right_half')">▶️ Right Area</button>
                            <button class="btn" onclick="applyPreset('doorway')">🚪 Doorway / Bottom</button>
                        </div>
                        <div class="slider-group">
                            <div class="slider-item">
                                <label><span>Left (X1)</span><span id="val-x1">30%</span></label>
                                <input id="slide-x1" type="range" min="0" max="80" value="30" oninput="onSliderChange()">
                            </div>
                            <div class="slider-item">
                                <label><span>Top (Y1)</span><span id="val-y1">20%</span></label>
                                <input id="slide-y1" type="range" min="0" max="80" value="20" oninput="onSliderChange()">
                            </div>
                            <div class="slider-item">
                                <label><span>Right (X2)</span><span id="val-x2">70%</span></label>
                                <input id="slide-x2" type="range" min="20" max="100" value="70" oninput="onSliderChange()">
                            </div>
                            <div class="slider-item">
                                <label><span>Bottom (Y2)</span><span id="val-y2">80%</span></label>
                                <input id="slide-y2" type="range" min="20" max="100" value="80" oninput="onSliderChange()">
                            </div>
                        </div>
                    </div>
                    <!-- Innovation 2: Green CPS & Bandwidth Conservation Telemetry Card -->
                    <div class="card">
                        <div class="green-title">🌿 GREEN CYBER-PHYSICAL SYSTEM (CPS) & BANDWIDTH EFFICIENCY</div>
                        <div class="stats-grid">
                            <div class="stat-box" style="border-color: #22c55e;">
                                <div id="eff-reduction" class="stat-value" style="color: #4ade80;">99.98%</div>
                                <div class="stat-label">Bandwidth Reduction</div>
                            </div>
                            <div class="stat-box">
                                <div id="eff-rate" class="stat-value" style="color: #38bdf8;">1.2 kbps</div>
                                <div class="stat-label">Edge Payload Rate</div>
                            </div>
                            <div class="stat-box">
                                <div id="eff-saved-mb" class="stat-value" style="color: #facc15;">0.0 MB</div>
                                <div class="stat-label">Video Traffic Avoided</div>
                            </div>
                            <div class="stat-box">
                                <div id="eff-co2" class="stat-value" style="color: #4ade80;">0.0 g</div>
                                <div class="stat-label">CO2 Emission Saved</div>
                            </div>
                        </div>
                        <div class="progress-bar-bg">
                            <div id="eff-bar" class="progress-bar-fill" style="width: 99.98%;"></div>
                        </div>
                        <div class="status-row"><span>Baseline Cloud Video Stream</span><span class="status-val">10.0 Mbps (720p/1080p)</span></div>
                        <div class="status-row"><span>City-Scale Load (100 Cams/24h)</span><span id="eff-scale" class="status-val" style="color: #4ade80;">108.0 TB ➔ 1.2 GB</span></div>
                    </div>
                </div>
                <div>
                    <div class="card">
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
                        <div class="status-row"><span>Hardware Actuators</span><span class="status-val" style="color: #4ade80;">ESP32 / UNO / Servo Active</span></div>
                        <div class="status-row"><span>Alexa Skill API</span><span class="status-val" style="color: #4ade80;">Online (:8000)</span></div>
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
                setInterval(() => {
                    img.src = '/latest_frame.jpg?t=' + new Date().getTime();
                }, 100);
            }

            async function autoDetectPool() {
                try {
                    const res = await fetch('/zone/auto_pool', { method: 'POST' });
                    const data = await res.json();
                    if (data.detected && data.bbox) {
                        updateSlidersFromBbox(data.bbox);
                        alert('🏊 Swimming pool detected and locked as Restricted Safety Zone at: ' + JSON.stringify(data.bbox));
                    } else {
                        alert('⚠️ No swimming pool water body detected in current camera view. You can adjust the sliders manually.');
                    }
                } catch (e) {
                    console.error("Pool detection failed:", e);
                }
            }

            async function applyPreset(presetName) {
                try {
                    const res = await fetch('/zone/config', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ preset: presetName })
                    });
                    if (res.ok) {
                        const data = await res.json();
                        updateSlidersFromBbox(data.zone.bbox);
                    }
                } catch (e) {
                    console.error("Preset apply failed:", e);
                }
            }

            let sliderTimeout = null;
            function onSliderChange() {
                let x1 = parseFloat(document.getElementById('slide-x1').value) / 100.0;
                let y1 = parseFloat(document.getElementById('slide-y1').value) / 100.0;
                let x2 = parseFloat(document.getElementById('slide-x2').value) / 100.0;
                let y2 = parseFloat(document.getElementById('slide-y2').value) / 100.0;

                if (x1 >= x2) x2 = Math.min(1.0, x1 + 0.1);
                if (y1 >= y2) y2 = Math.min(1.0, y1 + 0.1);

                document.getElementById('val-x1').innerText = Math.round(x1 * 100) + '%';
                document.getElementById('val-y1').innerText = Math.round(y1 * 100) + '%';
                document.getElementById('val-x2').innerText = Math.round(x2 * 100) + '%';
                document.getElementById('val-y2').innerText = Math.round(y2 * 100) + '%';

                clearTimeout(sliderTimeout);
                sliderTimeout = setTimeout(async () => {
                    await fetch('/zone/config', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ bbox: [x1, y1, x2, y2] })
                    });
                }, 150);
            }

            function updateSlidersFromBbox(bbox) {
                if (!bbox || bbox.length !== 4) return;
                document.getElementById('slide-x1').value = Math.round(bbox[0] * 100);
                document.getElementById('slide-y1').value = Math.round(bbox[1] * 100);
                document.getElementById('slide-x2').value = Math.round(bbox[2] * 100);
                document.getElementById('slide-y2').value = Math.round(bbox[3] * 100);

                document.getElementById('val-x1').innerText = Math.round(bbox[0] * 100) + '%';
                document.getElementById('val-y1').innerText = Math.round(bbox[1] * 100) + '%';
                document.getElementById('val-x2').innerText = Math.round(bbox[2] * 100) + '%';
                document.getElementById('val-y2').innerText = Math.round(bbox[3] * 100) + '%';
            }

            async function updateTelemetry() {
                try {
                    const res = await fetch('/reading/zone1');
                    if (res.ok) {
                        const data = await res.json();
                        document.getElementById('stat-count').innerText = Math.round(data.count);
                        document.getElementById('stat-pct').innerText = Math.round(data.density_percentage) + '%';
                        document.getElementById('stat-animals').innerText = data.animals || 0;
                        document.getElementById('stat-vehicles').innerText = data.vehicles || 0;
                        document.getElementById('tel-fps').innerText = data.fps || '0.0';
                        document.getElementById('tel-backend').innerText = data.backend || 'YOLO';

                        const alertEl = document.getElementById('tel-alert');
                        if (data.loitering > 0) {
                            alertEl.innerText = '🚨 LOITERING (' + data.loitering + ')';
                            alertEl.style.color = '#f87171';
                        } else if (data.active_alert === 'stray_animal') {
                            alertEl.innerText = '🐾 Stray Animal';
                            alertEl.style.color = '#fb923c';
                        } else {
                            alertEl.innerText = 'None';
                            alertEl.style.color = '#4ade80';
                        }

                        const badge = document.getElementById('tier-badge');
                        if (data.loitering > 0) {
                            badge.className = 'badge badge-alert';
                            badge.innerText = '🚨 LOITERING ALERT';
                        } else {
                            badge.className = 'badge badge-' + (data.tier || 'normal');
                            badge.innerText = (data.tier || 'normal').toUpperCase();
                        }

                        if (data.efficiency) {
                            const eff = data.efficiency;
                            document.getElementById('eff-reduction').innerText = eff.bandwidth_reduction_pct + '%';
                            document.getElementById('eff-rate').innerText = eff.edge_kbps + ' kbps';
                            document.getElementById('eff-saved-mb').innerText = eff.total_video_avoided_mb + ' MB';
                            document.getElementById('eff-co2').innerText = eff.co2_saved_grams + ' g';
                            document.getElementById('eff-bar').style.width = eff.bandwidth_reduction_pct + '%';
                            if (eff.city_100cam_video_tb_24h && eff.city_100cam_edge_gb_24h) {
                                document.getElementById('eff-scale').innerText = eff.city_100cam_video_tb_24h + ' TB ➔ ' + eff.city_100cam_edge_gb_24h + ' GB';
                            }
                        }
                    }
                } catch (e) {
                    console.error("Telemetry update failed:", e);
                }
            }

            async function updateEvents() {
                try {
                    const res = await fetch('/events');
                    if (res.ok) {
                        const events = await res.json();
                        const box = document.getElementById('events-list');
                        if (events && events.length > 0) {
                            box.innerHTML = events.map(ev => {
                                let cls = 'event-item';
                                if (ev.type === 'loitering') cls += ' event-alert';
                                return `<div class="${cls}"><span class="event-time">[${ev.time}]</span><span>${ev.message}</span></div>`;
                            }).join('');
                        }
                    }
                } catch (e) {
                    console.error("Events update failed:", e);
                }
            }

            setInterval(updateTelemetry, 500);
            setInterval(updateEvents, 1500);
            updateTelemetry();
            updateEvents();

            // Fetch initial zone config for sliders
            fetch('/zone/config').then(r => r.json()).then(d => {
                if (d && d.bbox) updateSlidersFromBbox(d.bbox);
            });
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
    parser.add_argument("--auto-pool", action="store_true",
                        help="Automatically scan and lock onto swimming pool water body as restricted zone")
    parser.add_argument("--zone-preset", default="center_small",
                        choices=["center_small", "center_medium", "left_half", "right_half", "doorway"],
                        help="Restricted zone preset (default: center_small ~30%)")
    parser.add_argument("--zone-bbox", nargs=4, type=float, default=None,
                        help="Custom zone bounding box: xmin ymin xmax ymax in normalized coords (0.0 to 1.0)")
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

    # Auto-resolve DensityNet checkpoint if not explicitly specified
    checkpoint_path = args.checkpoint
    if not checkpoint_path:
        candidates = [
            os.path.join(MODULES_DIR, "crowd_density", "models", "best_density_shanghaitech_part_b.pt"),
            os.path.join(MODULES_DIR, "crowd_density", "models", "density_shanghaitech_part_b.pt"),
            os.path.join(MODULES_DIR, "crowd_density", "models", "best_density_synthetic_density.pt"),
            os.path.join(MODULES_DIR, "crowd_density", "models", "density_synthetic_density.pt"),
        ]
        for cand in candidates:
            if os.path.exists(cand):
                checkpoint_path = cand
                break

    # Initialize Vision Detector with Multi-Task Modules
    detector = VisionDetector(
        backend=args.backend,
        checkpoint=checkpoint_path,
        yolo_model=args.yolo_model,
        conf_threshold=args.conf,
        enable_zones=not args.no_zones,
        loiter_time=args.loiter_time,
        zone_bbox=args.zone_bbox,
        zone_preset=args.zone_preset if args.zone_bbox is None else None,
        auto_pool=args.auto_pool
    )
    global_detector = detector

    # Initialize MQTT Client
    mqtt_client = make_mqtt_client(args.mqtt_host, args.mqtt_port)

    # Launch Camera + Inference loop
    cam_thread = threading.Thread(
        target=camera_loop,
        args=(detector, args.camera, args.capacity, args.zone, mqtt_client),
        kwargs={
            "width": args.width,
            "height": args.height,
            "busy_threshold": 60.0,
            "critical_threshold": 85.0,
            "publish_interval": 0.5
        },
        daemon=True
    )
    cam_thread.start()

    print("\n" + "=" * 66)
    print("🚀 Urban Monitoring Multi-Task Surveillance Server is LIVE!")
    print(f"   • Dashboard:     http://localhost:{args.api_port}/")
    print(f"   • Video Feed:    http://localhost:{args.api_port}/video_feed")
    print(f"   • Alexa API:     http://localhost:{args.api_port}/reading/{args.zone}")
    print(f"   • Efficiency API:http://localhost:{args.api_port}/telemetry/efficiency")
    print(f"   • Security Log:  http://localhost:{args.api_port}/events")
    print(f"   • Virtual Zones: {'ENABLED (' + str(detector.get_zone_config().get('bbox')) + ')' if not args.no_zones else 'DISABLED'}")
    print(f"   • Backend:       {args.backend.upper()} ({args.yolo_model if args.backend == 'yolo' else 'DensityNet'})")
    print(f"   • Camera:        Device index {args.camera} ({args.width}x{args.height})")
    print("=" * 66 + "\n")

    # Start FastAPI server
    uvicorn.run(app, host="0.0.0.0", port=args.api_port, log_level="warning")
