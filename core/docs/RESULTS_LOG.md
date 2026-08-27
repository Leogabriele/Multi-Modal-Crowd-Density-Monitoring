# Results Log — IoT Integration Layer (core/)

## What's been tested in this sandbox (verified, real results)

- **Central server logic** (`server.py`):
  - `tier_from_pct()` — boundary conditions tested (30->normal, 60->busy,
    65->busy, 90->critical, 95->critical). All correct.
  - `SharedState` thread-safe read/write — tested, correct.
  - **HTTP API** (`/reading/{zone}`, `/health`) — tested via FastAPI
    TestClient, returns correct JSON matching the underlying state.
  - **Real MQTT publish/subscribe** — a real Mosquitto broker was installed
    and run in this sandbox. Verified: publishing a reading via
    `publish_reading()` and then subscribing separately (simulating what
    the ESP32/ESP8266 firmware would do) correctly receives the latest
    retained value. Tested with two different readings to confirm updates
    propagate correctly, not just the first message.

- **Arduino UNO firmware** (`arduino_uno_actuator.ino`):
  - **Successfully compiled** against the real AVR/Arduino toolchain
    (avr-g++, targeting atmega328p, using the real Arduino core headers)
    with a minimal stub for the Servo library (identical public API:
    `attach()`, `write()`, so no behavioral risk from the stub). Zero
    errors, one unrelated compiler warning about optimization flags.
  - This confirms: syntax is correct, Arduino API usage is correct, the
    serial-parsing logic (`TIER:<value>` protocol) and control flow are
    structurally sound.
  - **NOT tested:** actual behavior on real hardware (servo movement,
    buzzer timing) — needs your physical UNO + servo + buzzer.

- **Alexa Skill Lambda function** (`lambda_function.py`):
  - `build_density_speech()` — tested for all three tiers (normal/busy/
    critical) plus the server-unreachable case. All produce correct,
    natural-sounding speech text.
  - **Found and fixed a real bug** during testing: `CatchAllExceptionHandler`
    didn't inherit from the SDK's required `AbstractExceptionHandler` base
    class, which would have crashed skill initialization. Fixed and
    re-verified.
  - Full skill builds successfully with all 5 handlers registered
    (Launch, GetDensity, Help, Cancel/Stop, SessionEnded, exception
    handler) — confirmed via `sb.create()`.
  - **NOT tested:** actual voice recognition, AWS Lambda deployment, or
    the live network call to your server — these need your own Amazon
    Developer + AWS accounts (see docs/ALEXA_SKILL_SETUP.md).

## What could NOT be tested in this sandbox (be aware before assuming it works)

- **ESP32 bridge firmware** (`esp32_bridge.ino`) — written and manually
  reviewed for correctness, but NOT compile-tested. The ESP32 Arduino core
  requires a large SDK (via Boards Manager) not available as a simple
  package install here. **You must verify this compiles in the real
  Arduino IDE with the ESP32 board package installed before relying on it.**
- **ESP8266 indicator firmware** (`esp8266_indicator.ino`) — same
  situation. I attempted a real compile using the actual ESP8266 Arduino
  core (cloned from GitHub) and a real xtensa-lx106 GCC toolchain, but hit
  a missing lwIP networking stack dependency (part of a larger SDK bundle
  not practical to replicate outside the official Boards Manager install).
  **Verify compilation in the real Arduino IDE before relying on it.**
- Physical wiring/behavior of all firmware — inherently needs your actual
  hardware.

## Recommended verification order when you get to your hardware

1. Flash Arduino UNO first (already compile-verified here) — confirm servo
   + buzzer respond to manually-typed serial commands
   (e.g. via Arduino IDE's Serial Monitor, type `TIER:critical` and press
   enter, confirm gate closes + buzzer sounds).
2. Flash ESP8266 — confirm it connects to WiFi and MQTT, and the LED
   responds when you manually publish to `crowd/zone1/tier` via
   `mosquitto_pub` from your laptop.
3. Flash ESP32 bridge — confirm it forwards MQTT tier updates to the UNO
   over serial (check UNO's actuator responds).
4. Only then wire the full server -> MQTT -> devices pipeline together.

This order isolates failures to one device at a time rather than debugging
everything simultaneously.
