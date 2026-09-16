# Multi-Modal Cyber-Physical Crowd Density & Urban Surveillance System

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![PyTorch CUDA 12.1](https://img.shields.io/badge/PyTorch-CUDA%2012.1-EE4C2C.svg)](https://pytorch.org/)
[![YOLOv8](https://img.shields.io/badge/YOLOv8-ByteTrack-00FFFF.svg)](https://github.com/ultralytics/ultralytics)
[![MQTT](https://img.shields.io/badge/MQTT-Mosquitto%20v2.0-660099.svg)](https://mosquitto.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An end-to-end, edge-to-cloud **Cyber-Physical System (CPS)** for real-time crowd density estimation, spatial hazard zoning, and closed-loop microcontroller actuation. Built for academic research in intelligent transportation systems, smart cities, and edge AI surveillance.

---

## 🏛️ System Architecture

```
                                      ┌──────────────────────────────────────────────┐
                                      │        AMAZON ALEXA CLOUD / ASK SDK          │
                                      │ (Voice Query: "How busy is zone one?")       │
                                      └──────────────────────▲───────────────────────┘
                                                             │ HTTPS (ngrok tunnel)
                                                             │
 ┌───────────────────────────┐         ┌─────────────────────▼────────────────────────┐
 │   CANON EOS 700D DSLR     │  USB    │       EDGE VISION INFERENCE SERVER           │
 │ (🎥 720p/1080p DirectShow)├────────►│ • YOLOv8 Multi-Object Persistent ByteTrack  │
 └───────────────────────────┘         │ • Dilated DensityNet (ShanghaiTech Part B)   │
                                       │ • HSV Swimming Pool Water Body Segmentation  │
                                       │ • Green CPS Energy & Bandwidth Profiler      │
                                       │ • Web Visualizer (:8000) & Security Event Log│
                                       └─────────────────────┬────────────────────────┘
                                                             │ MQTT Pub/Sub (Port 1883)
                                                             │
                        ┌────────────────────────────────────┴────────────────────────────────────┐
                        ▼                                                                         ▼
           ┌─────────────────────────┐                                               ┌─────────────────────────┐
           │     ESP8266 NodeMCU     │                                               │       ESP32 Bridge      │
           │  • Wi-Fi MQTT Client    │                                               │  • Wi-Fi MQTT Client    │
           │  • Tri-Color RGB LED    │                                               │  • Hardware UART Bridge │
           │    (Green/Yellow/Red)   │                                               └────────────┬────────────┘
           └─────────────────────────┘                                                            │ UART Serial2 (9600 baud)
                                                                                                  ▼
                                                                                     ┌─────────────────────────┐
                                                                                     │    ARDUINO UNO R3       │
                                                                                     │  • PWM Servo Gate (0-90)│
                                                                                     │  • Audio Buzzer Siren   │
                                                                                     └─────────────────────────┘
```

---

## 🌟 Key Research & Engineering Innovations

### 1. Dual-Paradigm Multi-Scale Vision AI
* **Micro-Surveillance (1–30 People):** Ultralytics YOLOv8 with ByteTrack persistent identity association for dwell-time tracking, loitering alarms, stray animals (dogs/cats), and vehicle classification (cars, trucks, buses, motorcycles, bicycles).
* **Macro-Surveillance (30–500+ People):** Custom `LightDensityNet` utilizing dilated convolutional layers trained on the **ShanghaiTech Part B** crowd counting benchmark (88,272 ground-truth heads across 716 images).
* **Automated Water & Pool Hazard Segmentation:** Autonomous HSV color-space and morphological convex contour extraction to automatically detect swimming pools and enforce water-safety loitering boundaries.

### 2. Closed-Loop Hardware Interlock (Edge Actuation)
* Real-time threat escalation: When density exceeds critical capacity or a loitering timer expires (>5.0s), the system issues a `TIER:critical` command via MQTT.
* The ESP32 forwards this state to an **Arduino UNO R3**, causing an automatic **Servo Gate Closure (0°)** and sounding an **Audible Alarm Siren**.

### 3. Green Cyber-Physical Systems (CPS) Bandwidth Conservation
* Quantitatively analyzes edge-to-MQTT metadata transmission against centralized 1080p raw video streaming.
* Achieves **>99.98% network bandwidth reduction** (~1.2 kbps vs. 10.0 Mbps) and avoids **>98% of network transmission carbon footprint**.

### 4. Cloud Voice Assistance (Amazon Alexa ASK SDK)
* Custom Alexa Skill deployed via AWS Lambda connecting to the local server over secure tunneling to query live crowd counts, capacity percentages, and loitering status.

---

## 📊 Academic Benchmarks (NVIDIA GeForce RTX 2050 GPU)

| Metric | Measured Result | Benchmark Significance |
| :--- | :---: | :--- |
| **Inference Latency** | **5.01 ms** (~**199.5 FPS**) | Real-time edge processing capability |
| **Model Footprint** | **2.01 MB** (526,881 params) | Green AI / Ultra-lightweight edge deployment |
| **Crowd Dataset** | **ShanghaiTech Part B** | 716 high-resolution street images (88,272 heads) |
| **Network Conservation** | **99.98%** Bandwidth Saved | Reduces city-scale load from 108 TB/day to 1.2 GB/day |
| **Hardware Bridge** | **< 12 ms** Latency | Sub-frame latency from threat detection to servo actuation |

---

## 🚀 Quickstart Guide

### 1. Clone & Install Dependencies
```bash
git clone https://github.com/Leogabriele/Multi-Modal-Crowd-Density-Monitoring.git
cd Multi-Modal-Crowd-Density-Monitoring

# Install PyTorch with CUDA acceleration
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
pip install -r core/server/requirements.txt
```

### 2. Start Mosquitto MQTT Broker
```bash
net start mosquitto
# or: mosquitto -v -p 1883
```

### 3. Launch Surveillance Server
```bash
cd core/server

# Mode 1: YOLO Tracking + Loitering + Behavior Analytics (Default)
python urban_server.py --backend yolo --camera 1 --loiter-time 5

# Mode 2: Automated Swimming Pool Detection & Safety Zoning
python urban_server.py --backend yolo --camera 1 --auto-pool --loiter-time 5

# Mode 3: Real Crowd Density CNN (ShanghaiTech Trained)
python urban_server.py --backend density --camera 1

# Mode 4: Dual-Paradigm Hybrid Mode
python urban_server.py --backend hybrid --camera 1 --loiter-time 5
```

### 4. Access Live Dashboard & Telemetry
Open **`http://localhost:8000/`** in your browser to access:
* Live Video Feed with visual bounding boxes, track IDs, and HUD.
* Dynamic Virtual Zone Configurator (Interactive Sliders & Presets).
* Real-time Green CPS & Bandwidth Conservation Telemetry.
* Security Event Log Ticker.

---

## 📂 Repository Structure

```
├── core/
│   ├── alexa_skill/lambda/     # AWS Lambda ASK SDK Alexa Skill handler
│   ├── firmware/               # Microcontroller firmware (.ino)
│   │   ├── esp8266_led/        # ESP8266 Wi-Fi MQTT RGB indicator
│   │   ├── esp32_bridge/       # ESP32 MQTT-to-Serial bridge
│   │   └── arduino_uno_actuator/ # Arduino UNO Servo gate & Buzzer
│   └── server/
│       ├── urban_server.py     # Main surveillance FastAPI server & streamer
│       └── requirements.txt    # Python dependencies
├── modules/
│   ├── behavior_analytics.py   # Restricted zone & loitering tracker
│   ├── pool_water_segmenter.py # Autonomous swimming pool detector
│   ├── traffic_animal_analytics.py # Stray animals & vehicle classification
│   ├── edge_efficiency_analyzer.py # Green CPS bandwidth & carbon profiler
│   ├── benchmark_bandwidth_efficiency.py # Academic LaTeX table generator
│   └── crowd_density/          # DensityNet training & dataset tools
│       ├── scripts/train.py    # GPU accelerated density training pipeline
│       └── src/model.py        # Dilated CNN architecture
└── README.md
```

---

## 📜 Citation & Research Reference

If you find this project useful in your research, please cite:
```bibtex
@misc{urban_monitoring_cps_2026,
  author = {Gabriel, J.},
  title = {Multi-Modal Cyber-Physical Crowd Density & Urban Surveillance System},
  year = {2026},
  publisher = {GitHub},
  journal = {GitHub repository},
  howpublished = {\url{https://github.com/Leogabriele/Multi-Modal-Crowd-Density-Monitoring}}
}
```

---

## 📄 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
