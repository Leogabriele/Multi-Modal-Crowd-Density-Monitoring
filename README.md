# Urban Monitoring System — Multi-Task Live Camera Analytics

A modular real-time video analytics platform. Each detection capability is
a self-contained module sharing a common live-camera-feed pattern, so new
modules can be added without restructuring existing ones.

## Modules

| Module | Status | What it does |
|---|---|---|
| `crowd_density` | **Built & tested** | Estimates head count + density % from a live feed via density-map regression |
| `iot_integration` | **Built & partially tested** | MQTT server, ESP32/ESP8266/Arduino firmware, Alexa voice skill — see `core/docs/RESULTS_LOG.md` for exactly what's verified |
| `suspicious_behavior` | Planned | Detects specific observable anomalous behaviors (fighting, loitering, abandoned objects) — see note below on scope |
| `stray_animal_detection` | Planned | Detects stray dogs/cats via object detection |
| `wrong_way_vehicle` | Planned | Detects vehicles traveling against expected flow direction |
| `vehicle_classification` | Planned | Classifies vehicles: car / truck / bike |

Additional modules discussed and worth considering later: illegal parking
detection, fire/smoke detection, abandoned object detection, queue-length
analytics, traffic-signal violation detection.

## Important scope note on "crime suspicion"

The original idea included detecting "someone suspected to do crime."
Computer vision cannot reliably infer criminal *intent* — there is no valid
visual signal for it, and systems that attempt this (predictive policing
tools) have a well-documented history of false positives and bias. This
system instead detects **specific, observable behaviors** (fighting,
loitering in restricted zones, abandoned objects) under the
`suspicious_behavior` module — scientifically defensible and something you
can present honestly in a thesis or application.

## Why modular

Each module in `modules/<name>/` is a self-contained project (own src,
scripts, configs, data, models) so you can develop and evaluate them
independently. Once individually working, they'll share a common live
multi-camera pipeline (planned: `core/`) that runs several modules on the
same feed simultaneously.

## Ethics — read before pointing any of this at a real camera feed

This system is designed to observe **real people and vehicles in real
places**. That is a materially different situation from the crowd-anomaly
thesis project (which mostly uses existing public benchmark datasets).
**Read `docs/ETHICS.md` before running any module on a live feed pointed at
a real public or semi-public space.** Short version: crowd density module
outputs an aggregate count/percentage and does not need to identify
individuals — keep it that way. Modules that would need to identify or
track specific people (most of the "planned" modules above) raise real
GDPR / consent questions that need to be resolved before deployment, not
after.

## Getting started

See `modules/crowd_density/QUICKSTART.md` for the crowd density model.
See `core/QUICKSTART.md` for the full IoT integration layer (MQTT server,
ESP32/ESP8266/Arduino firmware, Alexa Skill).

## Publication angle

This system combines edge AI (crowd density), IoT device orchestration
(heterogeneous ESP32/ESP8266/Arduino), and a voice/HCI layer (Alexa) — a
genuine systems-integration contribution suitable for IoT/smart-cities
conference venues, distinct from (and complementary to) a pure computer-
vision paper on the density model alone. See `core/QUICKSTART.md`'s final
section for what to actually measure/report (end-to-end latency, alert
modality comparison) to make this a real research contribution rather than
just a working demo.
