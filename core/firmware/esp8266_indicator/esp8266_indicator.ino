/*
 * ESP8266 Density Tier LED Indicator
 * -----------------------------------
 *
 * MQTT topic:
 *   crowd/zone1/tier
 *
 * Messages:
 *   normal   -> Green
 *   busy     -> Red + Green
 *   critical -> Red blinking
 *
 * LED wiring:
 *   Red   -> D1 (GPIO5)
 *   Green -> D2 (GPIO4)
 *   Blue  -> D3 (GPIO0) - unused
 *   Common cathode -> GND
 *
 * Required libraries:
 *   - ESP8266WiFi
 *   - PubSubClient
 */

// ==================================================
// LIBRARIES
// ==================================================

#include <ESP8266WiFi.h>
#include <PubSubClient.h>


// ==================================================
// WIFI CONFIGURATION
// ==================================================

const char* WIFI_SSID = "GABRIEL";
const char* WIFI_PASSWORD = "gabriel12";


// ==================================================
// MQTT CONFIGURATION
// ==================================================

const char* MQTT_BROKER_IP = "10.40.102.242";
const int MQTT_BROKER_PORT = 1883;

const char* MQTT_TOPIC_TIER = "crowd/zone1/tier";


// ==================================================
// LED PINS
// ==================================================

#define PIN_RED   5    // D1 = GPIO5
#define PIN_GREEN 4    // D2 = GPIO4
#define PIN_BLUE  0    // D3 = GPIO0 - unused


// ==================================================
// MQTT
// ==================================================

WiFiClient espClient;
PubSubClient mqttClient(espClient);


// ==================================================
// VARIABLES
// ==================================================

String currentTier = "normal";

unsigned long lastBlinkToggle = 0;

bool blinkState = false;


// ==================================================
// LED CONTROL
// ==================================================

void setColor(bool red, bool green) {

  digitalWrite(PIN_RED, red ? HIGH : LOW);
  digitalWrite(PIN_GREEN, green ? HIGH : LOW);

}


// ==================================================
// APPLY DENSITY TIER
// ==================================================

void applyTierSteadyState(const String& tier) {

  if (tier == "normal") {

    // GREEN
    setColor(false, true);

  }

  else if (tier == "busy") {

    // RED + GREEN
    // Produces an orange/yellow-ish color
    setColor(true, true);

  }

  else if (tier == "critical") {

    // RED
    setColor(true, false);

  }

  else {

    Serial.println("[WARNING] Unknown tier received.");

    setColor(false, false);

  }

}


// ==================================================
// CONNECT TO WIFI
// ==================================================

void connectWiFi() {

  Serial.println();
  Serial.println("================================");
  Serial.println("CONNECTING TO WIFI");
  Serial.println("================================");

  Serial.print("SSID: ");
  Serial.println(WIFI_SSID);

  WiFi.mode(WIFI_STA);

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int attempts = 0;

  while (WiFi.status() != WL_CONNECTED) {

    delay(500);

    Serial.print(".");

    attempts++;

    if (attempts >= 60) {

      Serial.println();
      Serial.println("[ERROR] WiFi connection failed.");
      Serial.println("Check your WiFi SSID and password.");

      return;

    }

  }

  Serial.println();
  Serial.println("[OK] WiFi connected!");

  Serial.print("ESP8266 IP address: ");
  Serial.println(WiFi.localIP());

  Serial.print("Gateway: ");
  Serial.println(WiFi.gatewayIP());

  Serial.print("Subnet mask: ");
  Serial.println(WiFi.subnetMask());

}


// ==================================================
// MQTT MESSAGE CALLBACK
// ==================================================

void onMqttMessage(
  char* topic,
  byte* payload,
  unsigned int length
) {

  String message = "";

  for (unsigned int i = 0; i < length; i++) {

    message += (char)payload[i];

  }


  Serial.println();
  Serial.println("================================");
  Serial.println("MQTT MESSAGE RECEIVED");
  Serial.println("================================");

  Serial.print("Topic: ");
  Serial.println(topic);

  Serial.print("Message: ");
  Serial.println(message);


  if (String(topic) == MQTT_TOPIC_TIER) {

    currentTier = message;

    Serial.print("[MQTT] Tier updated to: ");
    Serial.println(currentTier);

    applyTierSteadyState(currentTier);

  }

}


// ==================================================
// MQTT CONNECTION
// ==================================================

void connectMqtt() {

  Serial.println();
  Serial.println("================================");
  Serial.println("NETWORK DEBUG");
  Serial.println("================================");

  Serial.print("WiFi status: ");
  Serial.println(WiFi.status());

  Serial.print("ESP8266 IP: ");
  Serial.println(WiFi.localIP());

  Serial.print("Gateway: ");
  Serial.println(WiFi.gatewayIP());

  Serial.print("Subnet: ");
  Serial.println(WiFi.subnetMask());

  Serial.print("MQTT broker IP: ");
  Serial.println(MQTT_BROKER_IP);

  Serial.print("MQTT broker port: ");
  Serial.println(MQTT_BROKER_PORT);

  Serial.println();
  Serial.println("Connecting to MQTT broker...");


  while (!mqttClient.connected()) {

    String clientId =
      "esp8266-indicator-" +
      String(random(0xffff), HEX);


    Serial.print("Client ID: ");
    Serial.println(clientId);


    if (mqttClient.connect(clientId.c_str())) {

      Serial.println("[OK] MQTT connected!");


      Serial.print("Subscribing to: ");
      Serial.println(MQTT_TOPIC_TIER);


      if (mqttClient.subscribe(MQTT_TOPIC_TIER)) {

        Serial.println("[OK] MQTT subscription successful!");

      }

      else {

        Serial.println("[ERROR] MQTT subscription failed!");

      }

    }

    else {

      Serial.print("[ERROR] MQTT connection failed. rc=");
      Serial.println(mqttClient.state());

      Serial.println("Retrying in 2 seconds...");

      delay(2000);

    }

  }

}


// ==================================================
// SETUP
// ==================================================

void setup() {

  Serial.begin(115200);

  delay(1000);


  Serial.println();
  Serial.println();
  Serial.println("========================================");
  Serial.println("ESP8266 DENSITY TIER INDICATOR");
  Serial.println("========================================");


  // Configure LED pins
  pinMode(PIN_RED, OUTPUT);
  pinMode(PIN_GREEN, OUTPUT);
  pinMode(PIN_BLUE, OUTPUT);


  // Turn LEDs OFF initially
  setColor(false, false);


  // Connect to WiFi
  connectWiFi();


  // Stop here if WiFi failed
  if (WiFi.status() != WL_CONNECTED) {

    Serial.println();
    Serial.println("[ERROR] ESP8266 is not connected to WiFi.");
    Serial.println("Restart after checking WiFi settings.");

    return;

  }


  // ==================================================
  // MQTT CONFIGURATION
  // ==================================================

  Serial.println();
  Serial.println("================================");
  Serial.println("MQTT CONFIGURATION");
  Serial.println("================================");

  Serial.print("Broker IP: ");
  Serial.println(MQTT_BROKER_IP);

  Serial.print("Broker port: ");
  Serial.println(MQTT_BROKER_PORT);

  Serial.print("Topic: ");
  Serial.println(MQTT_TOPIC_TIER);


  mqttClient.setServer(
    MQTT_BROKER_IP,
    MQTT_BROKER_PORT
  );


  // IMPORTANT:
  // This connects incoming MQTT messages
  // to onMqttMessage().
  mqttClient.setCallback(onMqttMessage);


  Serial.println();
  Serial.println("[OK] MQTT configuration complete.");

}


// ==================================================
// MAIN LOOP
// ==================================================

void loop() {

  // --------------------------------------------------
  // CHECK WIFI
  // --------------------------------------------------

  if (WiFi.status() != WL_CONNECTED) {

    Serial.println("[WARNING] WiFi disconnected.");

    connectWiFi();

  }


  // --------------------------------------------------
  // CHECK MQTT
  // --------------------------------------------------

  if (!mqttClient.connected()) {

    connectMqtt();

  }


  // Process MQTT messages
  mqttClient.loop();


  // --------------------------------------------------
  // CRITICAL = BLINK RED
  // --------------------------------------------------

  if (currentTier == "critical") {

    unsigned long now = millis();


    if (now - lastBlinkToggle >= 400) {

      blinkState = !blinkState;


      if (blinkState) {

        // RED ON
        setColor(true, false);

      }

      else {

        // RED OFF
        setColor(false, false);

      }


      lastBlinkToggle = now;

    }

  }

}
