import csv
from datetime import datetime
from collections import deque

# Thresholds
MOVING_AVG_WINDOW = 5
AWAKE_HR_THRESHOLD = 80
SLEEP_HR_THRESHOLD = 70
BR_LOW_THRESHOLD = 4
BR_HIGH_THRESHOLD = 20
TEMP_SLEEP_RANGE = (18.0, 27.0)

INPUT_FILE = "/home/raspberry/Desktop/VSD_GUI/data_live.csv"

def detect_sleep_state(hr_window):
    avg_hr = sum(hr_window) / len(hr_window)
    if avg_hr > AWAKE_HR_THRESHOLD:
        return "Awake"
    elif avg_hr < SLEEP_HR_THRESHOLD:
        return "Asleep"
    else:
        return "Uncertain"

def classify_br(br):
    if br < BR_LOW_THRESHOLD:
        return "Abnormally Low"
    elif br > BR_HIGH_THRESHOLD:
        return "Abnormally High"
    else:
        return "Normal"

def classify_temp(temp):
    if TEMP_SLEEP_RANGE[0] <= temp <= TEMP_SLEEP_RANGE[1]:
        return "Comfortable"
    elif temp < TEMP_SLEEP_RANGE[0]:
        return "Too Cold"
    else:
        return "Too Hot"

def process_log_file(file_path):
    hr_window = deque(maxlen=MOVING_AVG_WINDOW)
    stats = {
        "total": 0,
        "asleep": 0,
        "awake": 0,
        "uncertain": 0,
        "br_low": 0,
        "br_high": 0,
        "temp_good": 0,
        "temp_cold": 0,
        "temp_hot": 0,
        "hr_values": [],
        "br_values": [],
        "temp_values": [],
        "humidity_values": [],
        "pressure_values": [],
        "asleep_timestamps": []
    }

    try:
        with open(file_path, 'r') as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) < 6 or row[0].lower() == "timestamp":
                    continue
                try:
                    timestamp = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
                    hr = float(row[1])
                    br = float(row[2])
                    temp = float(row[3])
                    humidity = float(row[4])
                    pressure = float(row[5])

                    stats["total"] += 1
                    stats["hr_values"].append(hr)
                    stats["br_values"].append(br)
                    stats["temp_values"].append(temp)
                    stats["humidity_values"].append(humidity)
                    stats["pressure_values"].append(pressure)

                    hr_window.append(hr)
                    if len(hr_window) == MOVING_AVG_WINDOW:
                        state = detect_sleep_state(hr_window)
                        stats[state.lower()] += 1
                        if state.lower() == "asleep":
                            stats["asleep_timestamps"].append(timestamp)

                    if classify_br(br) == "Abnormally Low":
                        stats["br_low"] += 1
                    elif classify_br(br) == "Abnormally High":
                        stats["br_high"] += 1

                    temp_state = classify_temp(temp)
                    if temp_state == "Comfortable":
                        stats["temp_good"] += 1
                    elif temp_state == "Too Cold":
                        stats["temp_cold"] += 1
                    else:
                        stats["temp_hot"] += 1

                except Exception:
                    continue
    except FileNotFoundError:
        print("❌ File not found:", file_path)
        return None

    return stats

def print_summary(stats):
    if not stats or stats["total"] == 0:
        print("No valid data to analyze.")
        return

    print("\n Sleep Doc Analysis Report")
    print(f"Total Readings: {stats['total']}")

    # Heart Rate
    hr = stats["hr_values"]
    print(f"\n❤️ Heart Rate:")
    print(f" ▸ Highest: {max(hr):.2f} BPM")
    print(f" ▸ Lowest:  {min(hr):.2f} BPM")
    print(f" ▸ Asleep (<{SLEEP_HR_THRESHOLD}): {stats['asleep']}")
    print(f" ▸ Awake  (>{AWAKE_HR_THRESHOLD}): {stats['awake']}")
    print(f" ▸ Uncertain: {stats['uncertain']}")

    # Breathing Rate
    br = stats["br_values"]
    print(f"\n Breathing Rate:")
    print(f" ▸ Highest: {max(br):.2f} BPM")
    print(f" ▸ Lowest:  {min(br):.2f} BPM")
    print(f" ▸ Abnormally Low (<{BR_LOW_THRESHOLD}): {stats['br_low']}")
    print(f" ▸ Abnormally High (>{BR_HIGH_THRESHOLD}): {stats['br_high']}")
    print(f" ▸ Normal: {stats['total'] - stats['br_low'] - stats['br_high']}")

    # Temperature
    temp = stats["temp_values"]
    print(f"\n🌡️ Temperature:")
    print(f" ▸ Max: {max(temp):.2f} °C")
    print(f" ▸ Min: {min(temp):.2f} °C")
    print(f" ▸ Avg: {sum(temp)/len(temp):.2f} °C")
    print(f" ▸ Comfortable: {stats['temp_good']}")
    print(f" ▸ Too Cold:    {stats['temp_cold']}")
    print(f" ▸ Too Hot:     {stats['temp_hot']}")

    # Humidity
    humidity = stats["humidity_values"]
    print(f"\n Humidity Avg: {sum(humidity)/len(humidity):.2f} %")

    # Pressure
    pressure = stats["pressure_values"]
    print(f" Pressure Avg: {sum(pressure)/len(pressure):.2f} hPa")

    # Sleep Duration
    timestamps = stats["asleep_timestamps"]
    if timestamps:
        duration = (timestamps[-1] - timestamps[0]).total_seconds() / 60  # minutes
        print(f"\n Estimated Sleep Duration: {duration:.1f} minutes")
    else:
        print("\n Estimated Sleep Duration: Not enough data")

    print("\n✅ End of Report\n")

# ==== Run ===stats = process_log_file(INPUT_FILE)
print_summary(stats)
