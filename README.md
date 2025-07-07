# Sleep Doc+

A comprehensive sleep monitoring and ambient environment control system that uses mmWave radar technology for contactless vital sign monitoring.

![Sleep Doc+ Logo](assets/logo.png)

## Overview

Sleep Doc+ is an integrated system that combines:

- **Contactless vital sign monitoring** using mmWave radar technology (Joybien BM502)
- **Environmental sensing** with temperature, humidity, and pressure monitoring
- **Ambient light and sound control** for creating optimal sleep conditions
- **Mobile app interface** built with Flutter for remote monitoring and control
- **Data logging and analysis** for tracking sleep patterns and environmental conditions

## Features

- **Contactless Vital Signs Monitoring**
  - Heart rate detection (40-90 BPM)
  - Breathing rate monitoring (12-20 BrPM)
  - No wearables required - works through bedding

- **Environmental Monitoring**
  - Temperature tracking
  - Humidity levels
  - Atmospheric pressure

- **Ambient Control**
  - Customizable LED lighting with multiple modes
  - Binaural beats audio for sleep assistance
  - Adjustable brightness settings

- **Mobile App**
  - Real-time vital signs display
  - Environmental data visualization
  - Remote control of ambient settings
  - QR code scanning for easy connection

## System Architecture

The Sleep Doc+ system consists of:

1. **Hardware Components**
   - Raspberry Pi (central controller)
   - Joybien BM502 mmWave radar sensor
   - BME280 environmental sensor
   - WS2812 LED strips for ambient lighting
   - I2S audio output for binaural beats

2. **Backend Services**
   - Python-based data collection and processing
   - Flask API server for mobile app communication
   - Real-time data logging system

3. **Mobile Application**
   - Flutter-based cross-platform app
   - Real-time data visualization
   - Remote control interface

## Installation

### Hardware Setup

1. Connect the BM502 mmWave radar to USB port
2. Connect environmental sensors to I2C pins
3. Connect LED strip to GPIO 18
4. Connect audio output to I2S pins or aux port

### Software Setup

1. Clone the repository:
   ```
   git clone https://github.com/SaiChirag24/Sleep_Doc_plus.git
   cd sleep-doc-plus
   ```

2. Install required Python packages:
   ```
   pip install customtkinter smbus2 adafruit-circuitpython-apds9960 rpi_ws281x pygame flask qrcode
   ```

3. Download the mmWave radar SDK:
   ```
   git clone https://github.com/bigheadG/mmWave.git
   cp -r mmWave /path/to/VSD_GUI/
   ```

4. Start the system:
   ```
   python gui3.py
   ```

### Mobile App Setup

1. Install Flutter (if not already installed)
2. Navigate to the Flutter app directory:
   ```
   cd sleep_doc_flutter2
   ```
3. Install dependencies:
   ```
   flutter pub get
   ```
4. Build and run the app:
   ```
   flutter run
   ```

## Usage

1. Start the backend system on your Raspberry Pi
2. Launch the Sleep Doc+ mobile app
3. Scan the QR code displayed on the Raspberry Pi to connect
4. Monitor vital signs and environmental data in real-time
5. Control ambient lighting and sound settings as desired

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| No data from radar | Sensor not connected or wrong port | Reconnect USB, run `dmesg` to confirm port |
| Data stuck | Sensor hung or UART buffer full | Restart Raspberry Pi or power-cycle sensor |
| Fake vitals shown | `radar_available = False` | Check wiring, serial port, or firmware |
| No audio through aux port | Wrong default audio device | Use `amixer cset numid=3 1` to force headphone jack |
| Flutter app not connecting | IP address issues | Use QR code to scan the correct IP |

## Data Analysis

The system logs vital sign and environmental data to CSV files in the `Data_collected/` directory. Use the included `analysis.py` script to analyze sleep patterns and environmental conditions.

## License

[Include your license information here]

## Acknowledgments

- mmWave radar integration based on [Joybien's mmWave SDK](https://github.com/bigheadG/mmWave)
- Flutter app developed using [Flutter framework](https://flutter.dev/)
