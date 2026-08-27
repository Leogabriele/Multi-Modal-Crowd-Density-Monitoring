# MQTT Broker Setup (Mosquitto)

## Install (free, self-hosted)

**Linux:**
```bash
sudo apt-get update
sudo apt-get install -y mosquitto mosquitto-clients
sudo systemctl enable mosquitto
sudo systemctl start mosquitto
```

**Windows:** download the installer from https://mosquitto.org/download/
and run it — it installs as a Windows service by default.

**macOS:** `brew install mosquitto`

## Verify it's running

```bash
mosquitto_sub -h localhost -p 1883 -t "test/topic" -v &
mosquitto_pub -h localhost -p 1883 -t "test/topic" -m "hello"
```
You should see `test/topic hello` printed.

## Find your machine's local network IP

The ESP32/ESP8266 devices need your broker machine's IP (not `localhost`,
since they're separate physical devices on the same WiFi network):

```bash
# Linux/macOS
ip addr show | grep "inet " | grep -v 127.0.0.1
# or
hostname -I

# Windows
ipconfig
```
Look for something like `192.168.1.XXX` — use this as `MQTT_BROKER_IP` in
both firmware files.

## Firewall note

Mosquitto listens on port 1883 by default. If your firewall blocks it,
either allow port 1883 for local network connections, or (Linux)
`sudo ufw allow 1883`.

## This was tested in the development sandbox

The publish/subscribe pipeline (server -> Mosquitto -> subscriber) was
verified end-to-end here using a real local Mosquitto broker instance —
publishing a reading and confirming a separate subscriber receives the
correct, latest retained value. See core/server/docs/RESULTS_LOG.md.
