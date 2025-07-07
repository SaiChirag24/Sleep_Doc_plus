 Sleep Doc: Vital Signs Detection & Sleep Monitoring System
 Folder: VSD_GUI/
 
 
Overview:
Sleep Doc is a Raspberry Pi–based non-contact health and sleep monitoring system that uses mmWave radar, 
gesture sensing, RGB ambient lighting, environmental data, and a mobile Flutter app for visualization and control.

The system includes a GUI for real-time vitals, a backend for monitoring and LED control, 
sleep state analysis, and REST APIs to connect with a mobile app. All session data is saved for post-analysis.


Project Structure:
VSD_GUI/
│
├── vsd_on_startup.py           # Main backend script (sensors, LED, REST API, logging)
├── gui3.py                     # CustomTkinter GUI (vitals + lighting/audio controls)
├── analysis.py                 # Analysis script to evaluate collected vitals data
├── ip_qr.png                   # QR code to connect the mobile app (based on Pi's IP)
├── data_live.csv               # Continuously updated vitals log for real-time GUI/app use
│
├── Data_collected/             # Archived session logs (each session logs to a new .csv file)
│     └── vitals_YYYY-MM-DD_HH-MM-SS.csv
│
├── assets/
│     └── logo.png              # Logo used in GUI splash screen
│
└── sleep_doc_flutter2/         # Flutter mobile app source code (version 1)


Getting Started:
1. Hardware Required

Raspberry Pi 3/4 with Raspberry Pi OS

BM502 mmWave radar sensor (connected via UART)

BME280 sensor for temperature, humidity, and pressure

APDS9960 gesture sensor for start/pause control

WS2812 RGB LED strip for ambient lighting (GPIO18)

(Optional) AUX or I2S speaker (for future sound features)

(Optional) Touchscreen for GUI


Software Setup
Install dependencies:

sudo pip3 install flask pygame adafruit-circuitpython-apds9960 bme280 rpi_ws281x qrcode pillow


Component Guide
vsd_on_startup.py:

This is the main backend script. It handles:
Vitals collection via mmWave radar
Temperature, humidity, and pressure via BME280
Gesture-based control (LEFT to start, RIGHT to pause)
LED light mode control (via /tmp/vsd_selection.json)
Real-time vitals output to /tmp/live_vitals.txt
Telegram notifications on startup/shutdown
REST API (/vitals, /control) for mobile app
QR code generation (ip_qr.png) for app pairing
It also logs each session to Data_collected/vitals_<timestamp>.csv.



gui3.py

This is the CustomTkinter GUI for:
Viewing HR, BR, temperature, humidity, pressure
Selecting light mode and toggling monitoring
Navigating between Dashboard and Analysis
When you press "Start Monitoring", it writes settings to /tmp/vsd_selection.json which are picked up by the backend.


analysis.py

Offline analysis script to process past logs (data_live.csv or any .csv in Data_collected/):
Calculates:
Sleep duration
Awake/Asleep/Uncertain states
Abnormal breathing counts
Comfortable vs. extreme temperatures
Outputs a summary report in the console
Run with:
python3 analysis.py


sleep_doc_flutter2/

Full source of the Sleep Doc Mobile App (v1) built in Flutter. The app:
Scans QR (ip_qr.png) to connect to Pi's REST API
Displays live HR, BR, temperature, etc.
Sends control settings (light mode, brightness) to backend
To build the app:

cd sleep_doc_flutter2
flutter pub get
flutter run

Ensure Pi and mobile are on the same Wi-Fi network.


File Descriptions:

| File / Path               | Description                                                              |
| ------------------------- | ------------------------------------------------------------------------ |
| `data_live.csv`           | Continuously updated live vitals for GUI + app                           |
| `Data_collected/`         | Saved session logs (with timestamp in filename)                          |
| `/tmp/vsd_selection.json` | JSON with current light mode, brightness, and light\_on (set by GUI/App) |
| `/tmp/live_vitals.txt`    | Single-line vitals used by Flask API and GUI                             |
| `/tmp/stop_vitals`        | If present, the backend will terminate safely                            |


Usage Instructions

To run and see vitals on terminal and send data over WiFi.
Run the backend alone:
sudo python3 vsd_on_startup.py

For complete GUI+Backend+APP integrated.
Start GUI:
python3 gui3.py

View IP QR
The ip_qr.png is generated at startup. Scan it in the Flutter app.

App Control
Use the app to view vitals and control lights remotely.

Session Logs
Every session’s vitals are saved in Data_collected/.

Run Analysis 
python3 analysis.py

Telegram Integration(Optional - If not needed comment out the line)
You’ll get messages on system start/shutdown (if connected to the internet).
Make sure to configure your own TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in vsd_on_startup.py.

ERROR HANDLING:
Read the Error_Handling.txt

Developed By
Chirag R.
Version 1.0 – June 2025
This is an academic and prototype-level health monitoring solution, not a certified medical device.

