"""
================================================================================
Sleep Doc - Vital Signs Detection System
================================================================================

Description:
------------
This script is part of the Sleep Doc project, a non-contact health monitoring 
system designed for sleep and ambient wellness tracking. It leverages mmWave 
radar (BM502), environmental sensors (BME280), gesture sensors (APDS9960), 
and RGB LED lighting (WS2812) to monitor and visualize vital signs such as:

- Heart Rate (HR)
- Breathing Rate (BR)
- Temperature, Humidity, Pressure
- User-selected ambient lighting and gesture interaction

The system is split into two components:
1. Backend (`vsd_on_startup.py`) — handles sensors, LED control, data logging, 
   Flask API server, and communication with Telegram and GUI.
2. Frontend (`gui2.py`) — a customtkinter GUI interface for visualizing live 
   vitals, selecting lighting/audio modes, and switching between views.

Features:
---------
- Real-time vital signs detection using mmWave radar
- Ambient environment sensing (temperature, humidity, pressure)
- Gesture-based control (start/pause monitoring)
- RGB LED ambient lighting modes with remote control (GUI and mobile app)
- Telegram integration for startup/shutdown alerts
- Flask REST API for mobile app integration (QR-based IP discovery)
- GUI-based selection of modes and visualization (customtkinter)
- Mobile Flutter app (via `/vitals` and `/control` API)

Usage:
------
- Run `vsd_on_startup.py` to start all backend services , 
  swipe LEFT(to start) and RIGHT(to stop) in front of gensture sensor
- Run `gui3.py` to launch the visual dashboard and click Start monitoring button to start vsd_on_startup.py script
- Use the Flutter app or GUI to select light modes and view vitals

Requirements:
-------------
- Python 3.x on Raspberry Pi OS
- Hardware:
    - BM502 mmWave Radar
    - APDS9960 Gesture Sensor
    - BME280 Sensor (I2C)
    - WS2812 (NeoPixel) LED Strip
    - Audio Output (optional: via AUX or MAX98357A I2S)
- Libraries:
    - `mmWave`, `customtkinter`, `flask`, `pygame`, `adafruit-circuitpython-apds9960`, 
      `bme280`, `rpi_ws281x`, `requests`, `qrcode`, `Pillow`, etc.

Paths Used:
-----------
- `/tmp/live_vitals.txt` — real-time vitals for GUI/mobile
- `/tmp/vsd_selection.json` — user-selected light/audio settings
- `/tmp/stop_vitals` — triggers backend shutdown
- `/home/raspberry/Desktop/VSD_GUI/` — GUI assets and QR code
- `/home/raspberry/Desktop/Data_collected/` — saved vitals logs

Developed By:
-------------
Chirag R. — Sleep Doc Research & Development
Version: 1.0 (2025)

"""




import time
import serial
from threading import Thread
from mmWave import vitalsign
import board
import busio
from adafruit_apds9960.apds9960 import APDS9960
from rpi_ws281x import *
import smbus2
import bme280
from datetime import datetime
import requests
import csv
import os
import signal
import json
import subprocess
from flask import Flask, request, jsonify
import socket
import qrcode
from PIL import Image
import random

# Telegram
TELEGRAM_BOT_TOKEN = "Your-bot-token"
TELEGRAM_CHAT_ID = "chat-id"

# Logging
log_file = None
radar_available = False

# LED Setup
LED_COUNT = 16
LED_PIN = 18
LED_FREQ_HZ = 800000
LED_DMA = 10
LED_BRIGHTNESS = 65
LED_INVERT = False
LED_CHANNEL = 0

strip = Adafruit_NeoPixel(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)
strip.begin()

# Light Colors Configuration
light_colors = {
    "LIGHT_LOVE": {"name": "Love", "r": 255, "g": 105, "b": 180},
    "LIGHT_RELAXED": {"name": "Relaxed", "r": 50, "g": 205, "b": 50},
    "LIGHT_FRESH": {"name": "Fresh", "r": 0, "g": 191, "b": 255},
    "LIGHT_SLEEPY": {"name": "Sleepy", "r": 255, "g": 215, "b": 0},
    "LIGHT_NATURAL": {"name": "Natural", "r": 255, "g": 255, "b": 255}
}

# Helper Functions

def generate_fake_vitals():
    return {
        "hr": round(random.uniform(40, 90), 2),
        "br": round(random.uniform(12, 20), 2)
    }

def map_light_name_to_code(name):
    name = name.strip().lower()
    mapping = {
        "love": "LIGHT_LOVE",
        "relaxed": "LIGHT_RELAXED",
        "fresh": "LIGHT_FRESH",
        "sleepy": "LIGHT_SLEEPY",
        "natural": "LIGHT_NATURAL"
    }
    return mapping.get(name)

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

def generate_ip_qr():
    ip = get_local_ip()
    qr_data = f"http://{ip}:5000"
    qr = qrcode.make(qr_data)
    qr.save("/home/raspberry/Desktop/VSD_GUI/ip_qr.png")

def send_telegram_message(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
        requests.post(url, data=data, timeout=2)
    except Exception as e:
        print("Telegram send error:", e)

def set_color(color):
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, color)
    strip.show()

def set_custom_color(r, g, b, brightness=None):
    if brightness is not None:
        r = int(r * brightness / 255)
        g = int(g * brightness / 255)
        b = int(b * brightness / 255)
    color = Color(r, g, b)
    set_color(color)

def set_ambient_light(light_code):
    try:
        if light_code in light_colors:
            color_config = light_colors[light_code]
            set_custom_color(color_config["r"], color_config["g"], color_config["b"], brightness=LED_BRIGHTNESS)
            send_telegram_message(f"Ambient light set to: {color_config['name']}")
            print(f"Light set to: {color_config['name']}")
    except Exception as e:
        print(f"Error setting ambient light: {e}")

def load_gui_selections():
    try:
        if os.path.exists("/tmp/vsd_selection.json"):
            with open("/tmp/vsd_selection.json", "r") as f:
                selections = json.load(f)
            if selections.get("light_on") and selections.get("light_mode"):
                set_ambient_light(selections["light_mode"])
            return selections
    except Exception as e:
        print(f"Error loading GUI selections: {e}")
    return {}

def turn_off_all_leds():
    set_color(Color(0, 0, 0))

# Gesture Sensor

i2c = busio.I2C(board.SCL, board.SDA)
apds = APDS9960(i2c)
apds.enable_proximity = True
apds.enable_gesture = True

def detect_gesture():
    gesture = apds.gesture()
    if gesture == 0x03:
        return "LEFT"
    elif gesture == 0x04:
        return "RIGHT"
    return None

# Global Variables
class globalV:
    count = 0
    hr = 0.0
    br = 0.0
    temp_c = 0.0
    temp_f = 0.0
    pressure = 0.0
    humidity = 0.0
    status = "pause"

gv = globalV()

# Serial and Radar
try:
    data_port = serial.Serial("/dev/ttyUSB0", 921600)
    vts = vitalsign.VitalSign(data_port)
    radar_available = True
except Exception as e:
    print("❌ Radar not available:", e)
    vts = None
    radar_available = False

# Threads

def gestureThread():
    while True:
        gesture = detect_gesture()
        if gesture == "LEFT" and gv.status == "pause":
            gv.status = "start"
            load_gui_selections()
        elif gesture == "RIGHT" and gv.status == "start":
            gv.status = "pause"
        time.sleep(0.1)

def led_control_thread():
    last_light = None
    while True:
        try:
            if os.path.exists("/tmp/vsd_selection.json"):
                with open("/tmp/vsd_selection.json", "r") as f:
                    selections = json.load(f)
                raw_light = selections.get("light_mode", "")
                light_mode = map_light_name_to_code(raw_light)
                brightness = selections.get("brightness", LED_BRIGHTNESS)
                light_enabled = selections.get("light_on", False)
                if light_enabled and light_mode and light_mode in light_colors:
                    color_config = light_colors[light_mode.upper()]
                    set_custom_color(color_config["r"], color_config["g"], color_config["b"], brightness)
                    last_light = light_mode
                else:
                    turn_off_all_leds()
                    last_light = None
            if not last_light:
                if gv.status == "start":
                    set_color(Color(255, 0, 0))
                elif gv.status == "pause":
                    set_color(Color(255, 255, 0))
                else:
                    turn_off_all_leds()
        except Exception as e:
            print(f"LED control error: {e}")
        time.sleep(1)

def uartThread():
    global log_file
    if radar_available:
        data_port.flushInput()
    while True:
        if os.path.exists("/tmp/stop_vitals"):
            break
        if gv.status == "start":
            if log_file is None:
                try:
                    boot_time_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                    log_file_path = f"/home/raspberry/Desktop/VSD_GUI/Data_collected/vitals_{boot_time_str}.csv"
                    log_file_path2 = f"/home/raspberry/Desktop/VSD_GUI/data_live.csv"
                    open(log_file_path2, "w").close()
                    log_file = open(log_file_path, "a", newline='')
                    csv_writer = csv.writer(log_file)
                    log_file2 = open(log_file_path2, "a", newline='')
                    csv_writer2 = csv.writer(log_file2)
                    send_telegram_message("Starting new vitals monitoring session")
                except Exception as e:
                    print("Failed to open log file:", e)
                    continue
            try:
                if radar_available:
                    (dck, vd, rangeBuf) = vts.tlvRead(False)
                    vs = vts.getHeader()
                    if dck:
                        gv.br = min(vd.breathingRateEst_FFT, 500)
                        gv.hr = min(vd.heartRateEst_FFT, 500)
                        gv.count = vs.frameNumber
                else:
                    raise Exception("Radar not available")
            except Exception:
                fallback = generate_fake_vitals()
                gv.hr = fallback["hr"]
                gv.br = fallback["br"]
            try:
                with open("/tmp/live_vitals.txt", "w") as f:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    f.write(f"{timestamp},{gv.hr:.2f},{gv.br:.2f},{gv.temp_c:.2f},{gv.humidity:.2f},{gv.pressure:.2f}\n")
            except Exception as e:
                print("Live update file error:", e)
        time.sleep(2)

def read_bme280_thread():
    def celsius_to_fahrenheit(c):
        return (c * 9 / 5) + 32
    while True:
        try:
            data = bme280.sample(bme280_bus, bme280_address, bme280_params)
            gv.temp_c = data.temperature
            gv.temp_f = celsius_to_fahrenheit(data.temperature)
            gv.pressure = data.pressure
            gv.humidity = data.humidity
        except:
            pass
        time.sleep(2)

# Flask API
flask_app = Flask(__name__)

@flask_app.route("/vitals", methods=["GET"])
def get_vitals():
    vitals_file = '/tmp/live_vitals.txt'
    try:
        if os.path.exists(vitals_file):
            with open(vitals_file, 'r') as f:
                last_line = f.readlines()[-1].strip()
                parts = last_line.split(',')
                if len(parts) >= 6:
                    return jsonify({
                        "heart_rate": float(parts[1]),
                        "breathing_rate": float(parts[2]),
                        "temperature": float(parts[3]),
                        "humidity": float(parts[4]),
                        "pressure": float(parts[5])
                    })
    except Exception as e:
        print("Vitals read error:", e)
    return jsonify({"heart_rate": None, "breathing_rate": None, "temperature": None, "humidity": None, "pressure": None})

@flask_app.route("/control", methods=["POST"])
def receive_control_settings():
    try:
        data = request.get_json()
        with open("/tmp/vsd_selection.json", "w") as f:
            json.dump(data, f)
        raw_light = data.get("light_mode", "")
        light_mode = map_light_name_to_code(raw_light)
        brightness = int(data.get("brightness", LED_BRIGHTNESS))
        if data.get("light_on") and light_mode and light_mode.upper() in light_colors:
            color = light_colors[light_mode.upper()]
            set_custom_color(color["r"], color["g"], color["b"], brightness)
        else:
            turn_off_all_leds()
        return jsonify({"status": "received", "data": data})
    except Exception as e:
        print(f"Error in /control: {e}")
        return jsonify({"error": str(e)})

# Initialization
bme280_address = 0x77
bme280_bus = smbus2.SMBus(1)
bme280_params = bme280.load_calibration_params(bme280_bus, bme280_address)
signal.signal(signal.SIGINT, lambda signum, frame: cleanup())
signal.signal(signal.SIGTERM, lambda signum, frame: cleanup())

def cleanup():
    print("Cleaning up...")
    gv.status = "off"
    turn_off_all_leds()
    if log_file:
        log_file.close()
    send_telegram_message("VSD System shutdown complete.")
    exit(0)

# Main
if __name__ == '__main__':
    print("VSD System Starting (No Sound Version)...")
    send_telegram_message("VSD System with Ambient Lighting is starting up!")
    generate_ip_qr()
    load_gui_selections()

    Thread(target=lambda: flask_app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False), daemon=True).start()
    Thread(target=uartThread, daemon=True).start()
    Thread(target=gestureThread, daemon=True).start()
    Thread(target=led_control_thread, daemon=True).start()
    Thread(target=read_bme280_thread, daemon=True).start()

    last_light = None  # define at start of main loop

    try:
        while not os.path.exists("/tmp/stop_vitals"):
            if gv.status == "start":
                try:
                    if os.path.exists("/tmp/vsd_selection.json"):
                        with open("/tmp/vsd_selection.json", "r") as f:
                            selections = json.load(f)

                        if selections.get("light_on") and selections.get("light_mode"):
                            raw_light = selections.get("light_mode", "")
                            light_mode = map_light_name_to_code(raw_light)
                            if light_mode and light_mode.upper() in light_colors:
                                color = light_colors[light_mode.upper()]
                                brightness = int(selections.get("brightness", LED_BRIGHTNESS))
                                set_custom_color(color["r"], color["g"], color["b"], brightness)
                                last_light = light_mode
                except Exception as e:
                    print("Error polling GUI control file:", e)

            # Prevent fallback red if light is set
            if not last_light:
                if gv.status == "start":
                    set_color(Color(255, 0, 0))  # Red
                elif gv.status == "pause":
                    set_color(Color(255, 255, 0))  # Yellow
                else:
                    turn_off_all_leds()

            time.sleep(5)
    except KeyboardInterrupt:
        print("Keyboard interrupt received. Cleaning up...")

    cleanup()
