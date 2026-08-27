/*
 * ESP32 MQTT-to-Serial Bridge
 * ---------------------------
 * Role: subscribes to the crowd density MQTT topics and forwards the
 * current "tier" (normal/busy/critical) to an Arduino UNO over serial,
 * since the UNO has no WiFi of its own. This is the standard pattern for
 * bridging non-WiFi microcontrollers into an MQTT-based IoT system.
 *
 * Wiring: ESP32 TX2 (GPIO17) -> Arduino UNO RX (pin 0)
 *         ESP32 RX2 (GPIO16) -> Arduino UNO TX (pin 1)
 *         Common GND between both boards.
 * (Use a second serial port on the ESP32 - Serial2 - so the main Serial
 * stays free for USB debugging output.)
 *
 * Libraries needed (Arduino IDE > Library Manager):
 *   - "PubSubClient" by Nick O'Leary
 *
 * Before flashing: fill in WIFI_SSID, WIFI_PASSWORD, MQTT_BROKER_IP below.
 * MQTT_BROKER_IP is the IP address of the machine running the central
 * server + Mosquitto broker (e.g. your laptop's local network IP).
 */

#include <WiFi.h>
#include <PubSubClient.h>

// ---- CONFIGURE THESE ----
const char* WIFI_SSID = "GABRIEL";
const char* WIFI_PASSWORD = "gabriel12";
const char* MQTT_BROKER_IP = "10.40.102.242";  // your server's local IP
const int   MQTT_BROKER_PORT = 1883;
const char* MQTT_TOPIC_TIER = "crowd/zone1/tier";
// --------------------------

WiFiClient espClient;
PubSubClient mqttClient(espClient);

String lastTierSent = "";

void connectWiFi() {
  Serial.print("Connecting to WiFi");
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println(" connected!");
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());
}

void onMqttMessage(char* topic, byte* payload, unsigned int length) {
  String message;
  for (unsigned int i = 0; i < length; i++) {
    message += (char)payload[i];
  }
  Serial.print("[MQTT] ");
  Serial.print(topic);
  Serial.print(" = ");
  Serial.println(message);

  if (String(topic) == MQTT_TOPIC_TIER) {
    if (message != lastTierSent) {
      // Forward to Arduino UNO over Serial2. Simple one-line protocol:
      // "TIER:<value>\n" -- keep it simple and easy to parse on the UNO side.
      Serial2.print("TIER:");
      Serial2.println(message);
      lastTierSent = message;
      Serial.print("[Bridge] Forwarded to UNO: TIER:");
      Serial.println(message);
    }
  }
}

void connectMqtt() {
  while (!mqttClient.connected()) {
    Serial.print("Connecting to MQTT broker...");
    String clientId = "esp32-bridge-" + String(random(0xffff), HEX);
    if (mqttClient.connect(clientId.c_str())) {
      Serial.println(" connected!");
      mqttClient.subscribe(MQTT_TOPIC_TIER);
      Serial.print("Subscribed to: ");
      Serial.println(MQTT_TOPIC_TIER);
    } else {
      Serial.print("failed, rc=");
      Serial.print(mqttClient.state());
      Serial.println(" retrying in 2s");
      delay(2000);
    }
  }
}

void setup() {
  Serial.begin(115200);           // USB debug output
  Serial2.begin(9600, SERIAL_8N1, 16, 17);  // to Arduino UNO (RX=16, TX=17)

  connectWiFi();
  mqttClient.setServer(MQTT_BROKER_IP, MQTT_BROKER_PORT);
  mqttClient.setCallback(onMqttMessage);
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
  }
  if (!mqttClient.connected()) {
    connectMqtt();
  }
  mqttClient.loop();
}
