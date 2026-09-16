# An IoT-Integrated Multi-Modal Crowd Density Monitoring and Alerting System Using Heterogeneous Edge Devices

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![PyTorch CUDA 12.1](https://img.shields.io/badge/PyTorch-CUDA%2012.1-EE4C2C.svg)](https://pytorch.org/)
[![YOLOv8](https://img.shields.io/badge/YOLOv8-ByteTrack-00FFFF.svg)](https://github.com/ultralytics/ultralytics)
[![MQTT](https://img.shields.io/badge/MQTT-Mosquitto%20v2.0-660099.svg)](https://mosquitto.org/)
[![Hardware](https://img.shields.io/badge/Hardware-ESP32%20%7C%20ESP8266%20%7C%20UNO-orange.svg)](https://www.arduino.cc/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **Research Publication Reference:**  
> **Title:** *An IoT-Integrated Multi-Modal Crowd Density Monitoring and Alerting System Using Heterogeneous Edge Devices*  
> **Authors:** **Jegan Nadar** & **Shilpa Gupta**  
> **Affiliation:** Department of Artificial Intelligence and Machine Learning Engineering, SIES Graduate School of Technology, Navi Mumbai, India  
> **Contact:** `jegann@sies.edu.in` | `shilpag@sies.edu.in`

---

## 📄 Abstract & Research Overview
Public-safety monitoring is needed in places such as transport facilities, markets, campuses, **swimming-pool surroundings**, and event spaces. In such settings, detecting a person is only the first step; the observed scene must also be converted into an event that can reach different low-cost devices in time.

This project presents an end-to-end Cyber-Physical System (CPS) integrating **YOLO vision inference with persistent track IDs**, **user-configurable virtual restricted zones**, a **dwell-time rule for loitering detection**, **MQTT publish-subscribe distribution**, and **heterogeneous IoT hardware** (ESP8266, ESP32, Arduino UNO). Because the Arduino UNO has no native WiFi interface, an ESP32 is deployed as a **network-to-UART serial bridge** to trigger physical servo-gate interlocks and audible buzzer alarms.

```
+---------------------------------------------------------------------------------------------------------+
|                                        SYSTEM ARCHITECTURE OVERVIEW                                     |
+---------------------------------------------------------------------------------------------------------+

  [ Camera Input ] (Canon EOS 700D DSLR / Webcam @ 1280x720)
         │
         ▼
  [ Central Edge Server ] (FastAPI + OpenCV + YOLOv8 Tracking + Dilated DensityNet)
         │
         ├───► [ Virtual Zone & Dwell Time Logic ] ──► Loitering Trigger (TL >= 5.0s)
         │
         ├───► [ HTTP REST API (:8000) ] ──────► [ Web Dashboard & Live MJPEG Stream ]
         │                                      └──► [ Amazon Alexa Voice Assistant (ASK SDK) ]
         │
         └───► [ Eclipse Mosquitto MQTT Broker ] (Port 1883)
                     │
                     ├───► [ ESP8266 NodeMCU ] ────────► Tri-Color RGB LED Status
                     │
                     └───► [ ESP32 Bridge ] ───────────► [ Arduino UNO R3 (UART Serial2) ]
                                                               ├──► PWM Servo Gate (0°/90°)
                                                               └──► Audible Alarm Siren (Buzzer)
+---------------------------------------------------------------------------------------------------------+
```

---

## 🔬 Mathematical Formulation & Processing Logic

### 1. Virtual Restricted Zone Membership
For track identity $i$, let $(x_i(t), y_i(t))$ represent its normalized spatial position at time $t$. Given normalized region bounds $(x_1, y_1, x_2, y_2)$, the inside/outside decision $Z_i(t)$ is defined as:

$$Z_i(t) = \begin{cases} 1, & x_1 \le x_i(t) \le x_2, \; y_1 \le y_i(t) \le y_2 \\ 0, & \text{otherwise} \end{cases}$$

### 2. Dwell-Time Accumulation & Loitering Decision
When $Z_i(t) = 1$, the initial entry timestamp is recorded as $s_i$. The accumulated residence time $\Delta_i(t)$ and loitering event decision $L_i(t)$ under threshold $T_L = 5.0\text{s}$ are:

$$\Delta_i(t) = t - s_i$$

$$L_i(t) = Z_i(t) \wedge \left[ \Delta_i(t) \ge T_L \right]$$

### 3. Capacity Density Metric
With $N_t$ active tracked individuals and reference area capacity $C$:

$$D_t = 100 \times \frac{N_t}{C} \%$$

### 4. End-to-End Alert Latency
$$T_{\text{e2e}} = t_{\text{actuation}} - t_{\text{event}}$$

---

## 🔄 Runtime Processing Sequence (Figure 2 in Paper)

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ Camera Frame │ ──► │ YOLO Person  │ ──► │   Track-ID   │ ──► │ Virtual Zone │ ──► │ Dwell-Time / │
│ Acquisition  │     │  Detection   │     │ Association  │     │  Membership  │     │  Loitering   │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘     └──────┬───────┘
                                                                                           │
┌──────────────┐     ┌─────────────────────────────────────────────────────────────────────▼───────┐
│ Multi-Modal  │ ◄── │ Unified Event State: Count + Density Tier + Loitering Threat State          │
│ Distribution │     └─────────────────────────────────────────────────────────────────────────────┘
└──────┬───────┘
       ├──► Web Dashboard Telemetry & Live Video Feed (8.5 - 9.2 FPS)
       ├──► ESP8266 Visual LED Indicator (Green / Yellow / Red)
       ├──► ESP32 -> UART -> Arduino UNO (Physical Servo Gate Closure + Buzzer Siren)
       └──► Amazon Alexa Voice Skill (On-Demand Speech Query)
```

---

## 📊 Experimental Results & Prototype Telemetry

### Table I: Accuracy & Diagnostic Audit
| Operating Condition | Ground Truth (GT) | True Positives (TP) | False Positives (FP) | False Negatives (FN) | Recall | Mean Absolute Error (MAE) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Normal Operation** | 3 | 1 | 0 | 2 | 33.3% | 2.0 |
| **Loitering Event** | 3 | 3 | 0 | 0 | **100.0%** | **0.0** |
| **Zone Configuration** | 3 | 2 | 0 | 1 | 66.7% | 1.0 |
| **Aggregate Metric** | **9** | **6** | **0** | **3** | **66.7%** | **1.0 person/frame** |

* **Snapshot Precision ($Q_p$):** `100.0%`
* **Snapshot Recall ($Q_r$):** `66.7%`
* **Harmonic F1-Score ($Q_f$):** `80.0%`

### Table II: Prototype Runtime Performance
| System State | Detected People | Capacity Density | Frame Rate (FPS) | Active Threat Alert | Hardware Actuator State |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Normal State** | 1 | 2% | **8.7 FPS** | None | Servo: 90° (Open), LED: Green |
| **Loitering Alert** | 3 | 6% | **8.5 FPS** | **🚨 LOITERING (1)** | **Servo: 0° (Closed), Buzzer: Beeping** |
| **Zone Configurator**| 2 | 4% | **9.2 FPS** | None | Dynamic Sliders Active |

---

## 🎯 Virtual Restricted Zone Customizer & Pool Detection

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│ 🎯 VIRTUAL RESTRICTED ZONE CONFIGURATOR (Browser UI at http://localhost:8000/)          │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│ [🏊 Auto-Detect Pool]  [🎯 Center Small 30%]  [📦 Center Medium 50%]  [◀️ Left]  [▶️ Right]│
│                                                                                         │
│  Left Boundary (X1):   [───●──────────] 8%     Top Boundary (Y1):    [──●───────────] 20%│
│  Right Boundary (X2):  [────────●─────] 92%    Bottom Boundary (Y2): [─────────●────]100%│
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

* **Interactive Real-Time Sliders:** Operators can modify boundary limits ($x_1, y_1, x_2, y_2$) dynamically via `POST /zone/config` without restarting server processes.
* **Autonomous Swimming Pool Water Segmentation:** Multi-stage HSV thresholding (Cyan/Azure/Teal) with morphological convex hull clustering to automatically lock onto swimming pools for child/swimmer drowning safety.

---

## 🌿 Green CPS & Edge Transmission Efficiency

| Architectural Paradigm | Transmission Bitrate | 24-Hour Load (100 City Cameras) | Network Carbon Footprint |
| :--- | :---: | :---: | :---: |
| **Centralized Cloud Video (1080p Stream)** | `10.00 Mbps` | **`108.00 TB / day`** | High ($\sim 3.08\text{ kg CO}_2\text{/day}$) |
| **Proposed Edge CPS (Our System)** | **`1.2 – 135 kbps`** | **`~1.2 – 136 GB / day`** | **Near-Zero ($<1.5\text{ g/day}$)** |
| **Relative Conservation** | **`>99.98%` Saved** | **`>8,000x` Less Traffic** | **`99.98%` Energy Reduction** |

---

## 🚀 Quickstart & Reproduction

### 1. Installation
```bash
git clone https://github.com/Leogabriele/Multi-Modal-Crowd-Density-Monitoring.git
cd Multi-Modal-Crowd-Density-Monitoring

# Install PyTorch with CUDA acceleration (NVIDIA RTX 2050 / CUDA 12.1)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
pip install -r core/server/requirements.txt
```

### 2. Start MQTT Broker & Surveillance Server
```powershell
# Terminal 1: Start Mosquitto Broker
net start mosquitto

# Terminal 2: Start Central Server with YOLO & 5s Loitering Timer
cd core/server
python urban_server.py --backend yolo --camera 1 --loiter-time 5

# Terminal 3: Start ngrok for Alexa Voice Skill
ngrok http 8000
```

---

## 📂 Project Directory Layout

```
├── core/
│   ├── alexa_skill/lambda/
│   │   └── lambda_function.py      # AWS Lambda ASK SDK Voice Query Handler
│   ├── firmware/                   # Microcontroller C++/Arduino Firmware
│   │   ├── esp8266_led/            # NodeMCU Wi-Fi MQTT RGB Visual Indicator
│   │   ├── esp32_bridge/           # ESP32 MQTT-to-Serial2 Hardware Bridge
│   │   └── arduino_uno_actuator/   # Arduino UNO Servo Gate & Siren Actuation
│   └── server/
│       ├── urban_server.py         # Main Surveillance Server, Streamer & API
│       └── requirements.txt        # Server Dependencies
├── modules/
│   ├── behavior_analytics.py       # Restricted Zone & Loitering Decision Engine
│   ├── pool_water_segmenter.py     # Automated Swimming Pool Water Body Segmenter
│   ├── edge_efficiency_analyzer.py # Green CPS Bandwidth & Energy Profiler
│   ├── benchmark_bandwidth_efficiency.py # Academic LaTeX Table Generator
│   └── crowd_density/              # Dilated DensityNet & ShanghaiTech CNN
└── README.md
```

---

## 📜 Citation

If you reference or build upon this research, please cite:

```bibtex
@article{nadar2026iot,
  title={An IoT-Integrated Multi-Modal Crowd Density Monitoring and Alerting System Using Heterogeneous Edge Devices},
  author={Nadar, Jegan and Gupta, Shilpa},
  journal={Department of Artificial Intelligence and Machine Learning Engineering, SIES Graduate School of Technology},
  year={2026},
  address={Nerul, Navi Mumbai, India}
}
```

---

## 📄 License
Distributed under the MIT License. See `LICENSE` for more information.
