/*
 * Arduino UNO — Physical Crowd-Control Actuator
 * -----------------------------------------------
 * Role: receives "TIER:<value>" messages over Serial (from the ESP32
 * bridge — see esp32_bridge.ino) and drives:
 *   - A servo motor simulating a gate: open when normal/busy, closed (or
 *     partially closed) when critical -- simulating automatic crowd-flow
 *     restriction at capacity.
 *   - A buzzer that sounds briefly when tier first becomes "critical"
 *     (edge-triggered, not continuous, to avoid being obnoxious).
 *
 * Wiring:
 *   Servo signal pin -> D9
 *   Servo power/GND  -> 5V / GND (use external 5V supply if servo draws
 *                        more current than the UNO's onboard regulator
 *                        can safely provide -- check your servo's specs)
 *   Buzzer (+)       -> D8
 *   Buzzer (-)       -> GND
 *   RX (pin 0) <- ESP32 TX2 (GPIO17)
 *   TX (pin 1) -> ESP32 RX2 (GPIO16)
 *   Common GND between UNO and ESP32
 *
 * NOTE: while connected to the ESP32 via the hardware serial pins (0/1),
 * you cannot also have the UNO connected to your laptop via USB serial at
 * the same time for debugging (both use the same UART) -- disconnect the
 * ESP32 wires temporarily if you need to re-flash or debug via USB.
 *
 * Library needed: "Servo" (built into standard Arduino IDE)
 */

#include <Servo.h>

#define SERVO_PIN 9
#define BUZZER_PIN 8

#define GATE_OPEN_ANGLE 90
#define GATE_CLOSED_ANGLE 0

Servo gateServo;
String currentTier = "normal";
String serialBuffer = "";
bool wasCritical = false;

void applyGateForTier(const String& tier) {
  if (tier == "critical") {
    gateServo.write(GATE_CLOSED_ANGLE);
  } else {
    gateServo.write(GATE_OPEN_ANGLE);
  }
}

void soundAlertBuzzer() {
  // Three short beeps -- an audible, non-continuous alert.
  for (int i = 0; i < 3; i++) {
    tone(BUZZER_PIN, 1000, 150);
    delay(200);
  }
}

void handleTierMessage(const String& tier) {
  currentTier = tier;
  applyGateForTier(tier);

  bool isCritical = (tier == "critical");
  if (isCritical && !wasCritical) {
    soundAlertBuzzer();  // only beep on the transition INTO critical
  }
  wasCritical = isCritical;

  Serial.print("[UNO] Tier applied: ");
  Serial.println(tier);
}

void setup() {
  Serial.begin(9600);   // shared with ESP32 bridge connection
  gateServo.attach(SERVO_PIN);
  pinMode(BUZZER_PIN, OUTPUT);
  gateServo.write(GATE_OPEN_ANGLE);  // start open
}

void loop() {
  while (Serial.available() > 0) {
    char c = Serial.read();
    if (c == '\n') {
      serialBuffer.trim();
      // Expected format: "TIER:normal" / "TIER:busy" / "TIER:critical"
      if (serialBuffer.startsWith("TIER:")) {
        String tier = serialBuffer.substring(5);
        handleTierMessage(tier);
      }
      serialBuffer = "";
    } else {
      serialBuffer += c;
    }
  }
}
