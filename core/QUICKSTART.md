# Quickstart — IoT Crowd Density Monitoring System

## 1. Prerequisites

- A trained crowd density model checkpoint (from `modules/crowd_density`
  — train on a real dataset for meaningful results, see that module's docs)
- Mosquitto broker installed (see `server/docs/MQTT_SETUP.md`)
- Python packages: `pip install paho-mqtt fastapi uvicorn opencv-python torch --break-system-packages`

## 2. Start the central server

```bash
cd core/server
python3 server.py --checkpoint ../../modules/crowd_density/models/density_<your_dataset>.pt --camera 0 --capacity 100
```

- `--camera 0` is your default webcam/DSLR-via-capture-card. Try `1`, `2`
  etc. if 0 doesn't pick up the right device.
- `--capacity 100` — set to whatever head count = 100% for your actual
  monitored space.
- This starts both the MQTT publishing loop AND the HTTP API (port 8000
  by default) in one process.

**Verify it's working:**
```bash
curl http://localhost:8000/reading/zone1
```
Should return JSON like `{"count": 12.3, "density_pct": 12.3, "tier": "normal", ...}`

## 3. Flash the hardware (in this order — see core/docs/RESULTS_LOG.md for why)

1. **Arduino UNO** (`firmware/arduino_uno_actuator/`) — already
   compile-verified here. Open in Arduino IDE, select "Arduino Uno" board,
   upload. Test manually via Serial Monitor before connecting to ESP32.
2. **ESP8266** (`firmware/esp8266_indicator/`) — install ESP8266 board
   package in Arduino IDE (Preferences -> Additional Board URLs:
   `http://arduino.esp8266.com/stable/package_esp8266com_index.json`),
   install "PubSubClient" library, fill in your WiFi + broker IP, upload.
3. **ESP32** (`firmware/esp32_bridge/`) — similarly install ESP32 board
   package (`https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json`),
   install "PubSubClient", fill in config, upload. Then wire to UNO per
   the comments at the top of the sketch.

## 4. Set up the Alexa Skill

See `alexa_skill/docs/ALEXA_SKILL_SETUP.md` — needs your own Amazon
Developer + AWS accounts, plus ngrok (or similar) to expose your local
server's HTTP API to the internet during development.

## 5. Full integration test

Once everything's flashed and running:
1. Point your DSLR/webcam at a test area with a few people (or objects
   simulating people).
2. Confirm the server's console prints regular "Published: count=... "
   messages.
3. Confirm the ESP8266's LED changes color as density changes (you can
   force this by manually publishing test values:
   `mosquitto_pub -h <broker_ip> -t crowd/zone1/tier -m critical`)
4. Confirm the ESP32 forwards to the UNO and the servo/buzzer respond.
5. Ask Alexa about the density and confirm it speaks the current reading.

## For your paper

Track actual measurements as you test:
- **End-to-end latency**: time from a person entering frame to the
  ESP8266 LED changing color (camera capture + inference + MQTT + WiFi
  propagation — all adds up, worth measuring and reporting).
- **Alert modality comparison**: how quickly would a person notice a
  visual (LED) vs. physical (gate/buzzer) vs. voice (Alexa, on-demand
  only, not proactive by default) alert? This is your actual research
  contribution — the comparison, not just "it works."

See `core/docs/RESULTS_LOG.md` for exactly what's verified vs. what still
needs testing on your end.
