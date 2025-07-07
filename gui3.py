# GUI for Sleep Doc start the script and start monitoring(swipe LEFT on gesture sensor to see vitals)
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, filedialog
from PIL import Image, ImageTk, ImageDraw, ImageFont
import os, subprocess, signal, sys
import json
import requests
from datetime import datetime, timedelta
import threading
import time
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
import csv
import glob
import socket

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

vitals_process = None
monitoring = False


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

# --- Load Icon Function ---
def load_icon(path, size, fallback_text="IMG"):
    try:
        image = Image.open(path).resize(size, Image.LANCZOS)
        return ctk.CTkImage(light_image=image, dark_image=image, size=size)
    except:
        placeholder = Image.new('RGBA', size, (64, 64, 64, 255))
        d = ImageDraw.Draw(placeholder)
        try:
            font = ImageFont.truetype("arial.ttf", size=size[0] // 5)
        except:
            font = None
        d.text((size[0] // 4, size[1] // 4), fallback_text, fill=(255, 255, 255), font=font)
        return ctk.CTkImage(light_image=placeholder, dark_image=placeholder, size=size)

# --- Create Binaural Beat Icons ---
def create_binaural_icon(freq_text, size=(40, 40)):
    img = Image.new('RGBA', size, (0, 120, 200, 200))
    d = ImageDraw.Draw(img)
    
    # Draw wave pattern
    width, height = size
    for i in range(0, width, 4):
        wave_height = int(height/4 * (1 + 0.5 * (i % 20) / 10))
        d.line([(i, height//2 - wave_height//2), (i, height//2 + wave_height//2)], 
               fill=(255, 255, 255, 200), width=2)
    
    # Add frequency text
    try:
        font = ImageFont.truetype("arial.ttf", 8)
    except:
        font = None
    d.text((2, height-12), freq_text, fill=(255, 255, 255), font=font)
    
    return ctk.CTkImage(light_image=img, dark_image=img, size=size)

    
# --- Create Light Color Icon ---
def create_light_icon(color_hex, size=(50, 50)):
    img = Image.new('RGBA', size, (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    
    # Draw light bulb shape
    center_x, center_y = size[0]//2, size[1]//2
    
    # Bulb body
    d.ellipse([center_x-15, center_y-20, center_x+15, center_y+10], 
              fill=color_hex, outline='white', width=2)
    
    # Base
    d.rectangle([center_x-8, center_y+8, center_x+8, center_y+15], 
                fill='gray', outline='white', width=1)
    
    # Light rays
    for angle in [0, 45, 90, 135, 180, 225, 270, 315]:
        import math
        rad = math.radians(angle)
        x1 = center_x + 20 * math.cos(rad)
        y1 = center_y + 20 * math.sin(rad)
        x2 = center_x + 25 * math.cos(rad)
        y2 = center_y + 25 * math.sin(rad)
        d.line([(x1, y1), (x2, y2)], fill='yellow', width=2)
    
    return ctk.CTkImage(light_image=img, dark_image=img, size=size)

# --- Splash Screen ---
class SplashScreen(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.overrideredirect(True)
        self.geometry("800x480")
        self.configure(fg_color="black")

        logo = load_icon("assets/logo.png", (500, 300))
        ctk.CTkLabel(self, image=logo, text="", fg_color="transparent").place(relx=0.5, rely=0.5, anchor="center")

        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width / 2) - (800 / 2)
        y = (screen_height / 2) - (480 / 2)
        self.geometry(f'+{int(x)}+{int(y)}')

        self.after(3000, self.start_main)

    def start_main(self):
        self.destroy()
        app = SleepDocApp()
        app.mainloop()



# --- Main App ---
class SleepDocApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        hostname = socket.gethostname()
        self.local_ip = get_local_ip()
        self.base_url = f"http://{self.local_ip}:5000"
        self.attributes("-fullscreen", True)
        self.config(cursor="none")
        self.bind_all("<Control-Alt-e>", self.secret_exit)  # ✅ Correct place
        self.secret_tap_count = 0
        self.last_tap_time = time.time()
        self.bind("<Button-1>", self.handle_secret_click)
        self.update_control_state()

        self.title("Sleep Doc+")
        self.geometry("750x470")
        self.resizable(False,False)
        self.configure(fg_color="#0f0f23")
        self.protocol("WM_DELETE_WINDOW", self.exit_app)

        # Modern fonts
        self.ctk_font_title = ctk.CTkFont(family="Segoe UI", size=28, weight="bold")
        self.ctk_font_subtitle = ctk.CTkFont(family="Segoe UI", size=20, weight="bold")
        self.ctk_font_data = ctk.CTkFont(family="Segoe UI", size=32, weight="bold")
        self.ctk_font_medium = ctk.CTkFont(family="Segoe UI", size=16, weight="normal")
        self.ctk_font_small = ctk.CTkFont(family="Segoe UI", size=12, weight="normal")
        self.ctk_font_button = ctk.CTkFont(family="Segoe UI", size=14, weight="bold")
        self.ctk_font_tiny = ctk.CTkFont(family="Segoe UI", size=12, weight="normal")
        self.ctk_font_datetime = ctk.CTkFont(family="Segoe UI", size=14, weight="bold")

        self.hr_data = []
        self.br_data = []
        self.time_data = []
        self.hr = self.br = self.temp = self.hum = self.press = "--"
        self.selected_sound = None
        self.selected_light = None
        self.current_page = "home"
        self.weather_data = {"temp": "--", "condition": "--", "humidity": "--"}
        self.qr_code_image = None
        self.wifi_networks = []
        self.selected_wifi = None
        
        # Binaural beats data with icons
        self.binaural_beats = [
            {"name": "Headache Relief", "freq": "0.5 Hz", "code": "BB_HEADACHE", "icon": create_binaural_icon("0.5Hz")},
            {"name": "Sleep Aid", "freq": "1.5 Hz", "code": "BB_INSOMNIA", "icon": create_binaural_icon("1.5Hz")},
            {"name": "Deep Relaxation", "freq": "2.5 Hz", "code": "BB_RELAXATION", "icon": create_binaural_icon("2.5Hz")},
            {"name": "Anxiety Relief", "freq": "3.5 Hz", "code": "BB_ANXIETY", "icon": create_binaural_icon("3.5Hz")},
            {"name": "Meditation", "freq": "4.5 Hz", "code": "BB_MEDITATION", "icon": create_binaural_icon("4.5Hz")},
            {"name": "Intuition", "freq": "5.5 Hz", "code": "BB_INTUITION", "icon": create_binaural_icon("5.5Hz")},
            {"name": "Creativity", "freq": "7.5 Hz", "code": "BB_CREATIVITY", "icon": create_binaural_icon("7.5Hz")},
            {"name": "Energy Boost", "freq": "8 Hz", "code": "BB_ENERGY", "icon": create_binaural_icon("8Hz")},
            {"name": "Love & Peace", "freq": "10.5 Hz", "code": "BB_LOVE", "icon": create_binaural_icon("10.5Hz")}
        ]
        
        # Light colors with icons
        self.light_colors = [
            {"name": "Love", "color": "#FF69B4", "code": "love", "icon": create_light_icon("#FF69B4")},
            {"name": "Relaxed", "color": "#32CD32", "code": "relaxed", "icon": create_light_icon("#32CD32")},
            {"name": "Fresh", "color": "#00BFFF", "code": "fresh", "icon": create_light_icon("#00BFFF")},
            {"name": "Sleepy", "color": "#FFD700", "code": "sleepy", "icon": create_light_icon("#FFD700")},
            {"name": "Natural", "color": "#FFFFFF", "code": "natural", "icon": create_light_icon("#FFFFFF")}
        ]
        
        self.build_gui()
        self.start_datetime_update()
        self.start_realtime_data_update()

    def build_gui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Top header with date/time
        self.header_frame = ctk.CTkFrame(self, height=60, fg_color="#16213e", corner_radius=0)
        self.header_frame.grid(row=0, column=0, columnspan=2, sticky="ew")
        self.header_frame.grid_propagate(False)
        self.header_frame.grid_columnconfigure(1, weight=1)
        
        # Date and Time
        self.datetime_label = ctk.CTkLabel(self.header_frame, text="", font=self.ctk_font_datetime, text_color="#4da6ff")
        self.datetime_label.grid(row=0, column=0, padx=20, pady=15, sticky="w")

        # Left Sidebar
        self.left_container = ctk.CTkFrame(self, width=70, fg_color="#1e2749", corner_radius=0)
        self.left_container.grid(row=1, column=0, sticky="ns")
        self.left_container.grid_propagate(False)
        self.left_container.grid_columnconfigure(0, weight=1)
        
        self.left_scrollable = ctk.CTkScrollableFrame(
                        self.left_container, 
                        fg_color="#1e2749",
                        scrollbar_fg_color="#2d3748",
                        scrollbar_button_color="#4a5568"
        )
        self.left_scrollable.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Navigation buttons with better styling
        nav_buttons = [
            ("Home", self.show_home),
            ("Connect to Phone", self.show_connect_phone),
            ("WiFi Setup", self.show_wifi_setup),
            ("Binaural Beats", self.show_binaural),
            ("Ambient Light", self.show_light),
            ("Real-time Analysis", self.show_analysis),
            ("Data Storage", self.show_data_storage)
        ]
        
        for text, command in nav_buttons:
            btn = ctk.CTkButton(self.left_scrollable, text=text, command=command,
                               height=45, font=self.ctk_font_button,
                               fg_color="#2d3748", hover_color="#4a5568",
                               corner_radius=8)
            btn.pack(pady=6, padx=10, fill="x")
              
        # Main content
        self.main = ctk.CTkFrame(self, fg_color="transparent")
        self.main.grid(row=1, column=1, sticky="nsew")
        self.main.grid_columnconfigure(0, weight=1)
        self.main.grid_rowconfigure(0, weight=1)

        self.container = ctk.CTkFrame(self.main, fg_color="transparent")
        self.container.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)

        # Create all frames as scrollable
        self.home_frame = ctk.CTkScrollableFrame(self.container, fg_color="transparent")
        self.binaural_frame = ctk.CTkScrollableFrame(self.container, fg_color="transparent")
        self.light_frame = ctk.CTkScrollableFrame(self.container, fg_color="transparent")
        self.analysis_frame = ctk.CTkScrollableFrame(self.container, fg_color="transparent")
        self.data_storage_frame = ctk.CTkScrollableFrame(self.container, fg_color="transparent")
        self.phone_connect_frame = ctk.CTkScrollableFrame(self.container, fg_color="transparent")
        self.wifi_setup_frame = ctk.CTkScrollableFrame(self.container, fg_color="transparent")
        

        self.build_home(self.home_frame)
        self.build_binaural(self.binaural_frame)
        self.build_light(self.light_frame)
        self.build_analysis(self.analysis_frame)
        self.build_data_storage(self.data_storage_frame)
        self.build_phone_connect(self.phone_connect_frame)
        self.build_wifi_setup(self.wifi_setup_frame)


        self.show_home()

    def start_datetime_update(self):
        """Start the date/time update loop"""
        self.update_datetime()

    def update_datetime(self):
        """Update date and time display"""
        now = datetime.now()
        date_str = now.strftime("%A, %B %d, %Y")
        time_str = now.strftime("%I:%M:%S %p")
        self.datetime_label.configure(text=f"{date_str} • {time_str}")
        
        # Schedule next update
        self.after(1000, self.update_datetime)

    def start_realtime_data_update(self):
        """Start real-time data updates"""
        self.update_realtime_data()

    def update_realtime_data(self):
        try:
            url = f"http://{self.local_ip}:5000/vitals"
            response = requests.get(url, timeout=2)

            if response.status_code == 200:
                vitals = response.json()

                hr = float(vitals.get("heart_rate") or 0)
                br = float(vitals.get("breathing_rate") or 0)
                temp = float(vitals.get("temperature") or 0)
                hum = float(vitals.get("humidity") or 0)
                press = float(vitals.get("pressure") or 0)

                # Only update GUI if values are non-zero
                if hr > 0:
                    self.hr = hr
                    self.hr_label.configure(text=f"HR: {self.hr:.1f}")
                if br > 0:
                    self.br = br
                    self.br_label.configure(text=f"BR: {self.br:.1f}")
                if temp > 0:
                    self.temp = temp
                    self.temp_label.configure(text=f"Temp: {self.temp:.1f}°C")
                if hum > 0:
                    self.hum = hum
                    self.hum_label.configure(text=f"Humidity: {self.hum:.1f}%")
                if press > 0:
                    self.press = press
                    self.press_label.configure(text=f"Pressure: {self.press:.1f} hPa")

            else:
                print("Vitals fetch failed:", response.status_code)

        except Exception as e:
            print("Vitals update error:", e)

        # Schedule next update
        self.after(2000, self.update_realtime_data)




    def build_home(self, frame):
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(1, weight=1)

        title_label = ctk.CTkLabel(frame, text="Sleep Doc+ Dashboard", font=self.ctk_font_title, text_color="#4da6ff")
        title_label.grid(row=0, column=0, pady=(20, 10))

        vitals_frame = ctk.CTkFrame(frame, fg_color="#1e2749", corner_radius=15)
        vitals_frame.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")
        vitals_frame.grid_columnconfigure((0, 1), weight=1)
        vitals_frame.grid_rowconfigure((0, 1), weight=1)

        # HR Dial
        self.hr_label = ctk.CTkLabel(vitals_frame, text="HR: --", font=self.ctk_font_data, text_color="#ff5555")
        self.hr_label.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")

        # BR Dial
        self.br_label = ctk.CTkLabel(vitals_frame, text="BR: --", font=self.ctk_font_data, text_color="#55ff99")
        self.br_label.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")

        # Environmental data
        self.temp_label = ctk.CTkLabel(vitals_frame, text="Temp: --", font=self.ctk_font_medium, text_color="white")
        self.temp_label.grid(row=1, column=0, padx=10, pady=(5, 20), sticky="w")

        self.hum_label = ctk.CTkLabel(vitals_frame, text="Humidity: --", font=self.ctk_font_medium, text_color="white")
        self.hum_label.grid(row=1, column=1, padx=10, pady=(5, 20), sticky="w")

        self.press_label = ctk.CTkLabel(vitals_frame, text="Pressure: --", font=self.ctk_font_medium, text_color="white")
        self.press_label.grid(row=2, column=0, columnspan=2, pady=(0, 20), sticky="n")

        # Monitor Button - centered with better styling
        self.monitor_btn = ctk.CTkButton(frame, text="Start Monitoring", font=self.ctk_font_subtitle, 
                                       command=self.toggle_monitoring, width=300, height=60,
                                       fg_color="#2d7dd2", hover_color="#1e5f99", corner_radius=30)
        self.monitor_btn.grid(row=3, column=0, columnspan=2, pady=40)

    def build_binaural(self, frame):
        frame.grid_columnconfigure(0, weight=1)

        title_label = ctk.CTkLabel(
            frame,
            text="Binaural Beats Therapy",
            font=self.ctk_font_title,
            text_color="#4da6ff"
        )
        title_label.grid(row=0, column=0, pady=20)

        # Container for buttons
        beats_container = ctk.CTkFrame(frame, fg_color="transparent")
        beats_container.grid(row=1, column=0, sticky="ew", padx=20, pady=10)

        # Configure 2 columns
        for col in range(2):
            beats_container.grid_columnconfigure(col, weight=1)

        for i, beat in enumerate(self.binaural_beats):
            row = i // 2
            col = i % 2

            btn = ctk.CTkButton(
                beats_container,
                text=f"{beat['name']}\n{beat['freq']}",
                # image=beat['icon'],  # Optional: if icon is working and visible
                compound="top",
                width=250,
                height=100,
                font=self.ctk_font_medium,
                corner_radius=15,
                fg_color="#2d3748",
                hover_color="#4a5568",
                text_color="white",
                command=lambda b=beat: self.select_binaural(b)
            )
            btn.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")

        # Selected binaural beat display
        self.selected_binaural_frame = ctk.CTkFrame(frame, fg_color="#1e2749", corner_radius=15)
        self.selected_binaural_frame.grid(row=2, column=0, pady=20, padx=40, sticky="ew")

        self.selected_binaural_label = ctk.CTkLabel(
            self.selected_binaural_frame,
            text="No binaural beat selected",
            font=self.ctk_font_medium,
            text_color="#888888"
        )
        self.selected_binaural_label.pack(pady=20)

        # Play / Stop buttons
        control_frame = ctk.CTkFrame(frame, fg_color="transparent")
        control_frame.grid(row=3, column=0, pady=20)

        self.play_binaural_btn = ctk.CTkButton(
            control_frame,
            text="▶️ Play",
            command=self.play_binaural,
            width=120,
            height=45,
            state="disabled",
            corner_radius=20
        )
        self.play_binaural_btn.pack(side="left", padx=10)

        self.stop_binaural_btn = ctk.CTkButton(
            control_frame,
            text="Stop",
            command=self.stop_binaural,
            width=120,
            height=45,
            state="disabled",
            corner_radius=20
        )
        self.stop_binaural_btn.pack(side="left", padx=10)


    def build_light(self, frame):
        frame.grid_columnconfigure(0, weight=1)
        
        title_label = ctk.CTkLabel(frame, text="Ambient Light Therapy", 
                                  font=self.ctk_font_title, text_color="#4da6ff")
        title_label.grid(row=0, column=0, pady=20)
        
        # Light color selection
        light_frame = ctk.CTkFrame(frame, fg_color="transparent")
        light_frame.grid(row=1, column=0, pady=20, padx=40, sticky="ew")
        light_frame.grid_columnconfigure(0, weight=1)
        light_frame.grid_columnconfigure(1, weight=1)
        light_frame.grid_columnconfigure(2, weight=1)
        
        for i, light in enumerate(self.light_colors):
            row = i // 3
            col = i % 3
            
            btn = ctk.CTkButton(light_frame, text=light['name'], image=light['icon'],
                               compound="top", width=200, height=100,
                               font=self.ctk_font_medium, corner_radius=15,
                               fg_color="#2d3748", hover_color="#4a5568",
                               command=lambda l=light: self.select_light(l))
            btn.grid(row=row, column=col, padx=10, pady=10)
        
        # Selected light display
        self.selected_light_frame = ctk.CTkFrame(frame, fg_color="#1e2749", corner_radius=15)
        self.selected_light_frame.grid(row=2, column=0, pady=20, padx=40, sticky="ew")
        
        self.selected_light_label = ctk.CTkLabel(self.selected_light_frame, 
                                                text="No light color selected", 
                                                font=self.ctk_font_medium, text_color="#888888")
        self.selected_light_label.pack(pady=20)
        
        # Brightness control
        brightness_frame = ctk.CTkFrame(frame, fg_color="#1e2749", corner_radius=15)
        brightness_frame.grid(row=3, column=0, pady=20, padx=40, sticky="ew")
        
        ctk.CTkLabel(brightness_frame, text="Brightness Control", 
                    font=self.ctk_font_medium).pack(pady=(15, 5))
        
        self.brightness_slider = ctk.CTkSlider(brightness_frame, from_=0, to=100, 
                                              number_of_steps=100, width=400,
                                              command=self.adjust_brightness)
        self.brightness_slider.pack(pady=10)
        self.brightness_slider.set(50)
        
        self.brightness_value_label = ctk.CTkLabel(brightness_frame, text="50%", 
                                                  font=self.ctk_font_small)
        self.brightness_value_label.pack(pady=(0, 15))
        
        # Control buttons
        control_frame = ctk.CTkFrame(frame, fg_color="transparent")
        control_frame.grid(row=4, column=0, pady=20)
        
        self.turn_on_light_btn = ctk.CTkButton(control_frame, text="Turn On", 
                                              command=self.turn_on_light, width=120, height=45,
                                              state="disabled", corner_radius=20)
        self.turn_on_light_btn.pack(side="left", padx=10)
        
        self.turn_off_light_btn = ctk.CTkButton(control_frame, text="Turn Off", 
                                               command=self.turn_off_light, width=120, height=45,
                                               state="disabled", corner_radius=20)
        self.turn_off_light_btn.pack(side="left", padx=10)

    def write_control_settings(self):
        try:
            control_data = {
                "audio_enabled": bool(getattr(self, "audio_enabled", False)),
                "binaural_mode": self.selected_sound["name"] if hasattr(self, "selected_sound") and self.selected_sound else None,
                "light_enabled": bool(getattr(self, "light_enabled", False)),
                "light_mode": self.selected_light["name"] if hasattr(self, "selected_light") and self.selected_light else None,
                "brightness": int(self.brightness_slider.get()) if hasattr(self, "brightness_slider") else 100
            }

            with open("/tmp/vsd_command.json", "w") as f:
                json.dump(control_data, f, indent=2)

            print("📤 GUI wrote control settings:", control_data)

        except Exception as e:
            print(f"❌ Error writing control settings: {e}")
            
        

    def send_control_settings(self):
        data = {
            "light_on": self.selected_light is not None,
            "light_mode": self.selected_light["code"] if self.selected_light else "",
            "brightness": int(self.brightness_slider.get()) if hasattr(self, "brightness_slider") else 100,
            "audio_on": self.selected_sound is not None,
            "audio_mode": self.selected_sound["name"] if self.selected_sound else ""
        }

        try:
            ip = self.local_ip
            response = requests.post(f"http://{self.local_ip}:5000/control", json=data, timeout=2)
            if response.status_code == 200:
                print("✅ Control settings sent:", data)
            else:
                print(f"❌ Failed to send control settings: {response.status_code}")
        except Exception as e:
            print(f"❌ Error sending control settings: {e}")


    def build_analysis(self, frame):
        frame.grid_columnconfigure(0, weight=1)
        
        title_label = ctk.CTkLabel(frame, text="Real-time Sleep Analysis", 
                                  font=self.ctk_font_title, text_color="#4da6ff")
        title_label.grid(row=0, column=0, pady=20)
        
        # Current vitals display
        current_vitals_frame = ctk.CTkFrame(frame, fg_color="#1e2749", corner_radius=15)
        current_vitals_frame.grid(row=1, column=0, pady=20, padx=40, sticky="ew")
        
        ctk.CTkLabel(current_vitals_frame, text="Current Vitals", 
                    font=self.ctk_font_subtitle).pack(pady=(15, 10))
        
        self.current_vitals_text = ctk.CTkTextbox(current_vitals_frame, height=100, width=600)
        self.current_vitals_text.pack(pady=10, padx=20, fill="x")
        
        # Health insights
        insights_frame = ctk.CTkFrame(frame, fg_color="#1e2749", corner_radius=15)
        insights_frame.grid(row=2, column=0, pady=20, padx=40, sticky="ew")
        
        ctk.CTkLabel(insights_frame, text="Health Insights", 
                    font=self.ctk_font_subtitle).pack(pady=(15, 10))
        
        self.health_insights_text = ctk.CTkTextbox(insights_frame, height=150, width=600)
        self.health_insights_text.pack(pady=10, padx=20, fill="x")
        
        # Trend analysis
        trend_frame = ctk.CTkFrame(frame, fg_color="#1e2749", corner_radius=15)
        trend_frame.grid(row=3, column=0, pady=20, padx=40, sticky="ew")
        
        ctk.CTkLabel(trend_frame, text="Trend Analysis", 
                    font=self.ctk_font_subtitle).pack(pady=(15, 10))
        
        self.trend_analysis_text = ctk.CTkTextbox(trend_frame, height=150, width=600)
        self.trend_analysis_text.pack(pady=10, padx=20, fill="x")
        
        # Recommendations
        recommendations_frame = ctk.CTkFrame(frame, fg_color="#1e2749", corner_radius=15)
        recommendations_frame.grid(row=4, column=0, pady=20, padx=40, sticky="ew")
        
        ctk.CTkLabel(recommendations_frame, text="Recommendations", 
                    font=self.ctk_font_subtitle).pack(pady=(15, 10))
        
        self.recommendations_text = ctk.CTkTextbox(recommendations_frame, height=120, width=600)
        self.recommendations_text.pack(pady=10, padx=20, fill="x")

    def build_data_storage(self, frame):
        frame.grid_columnconfigure(0, weight=1)
        
        title_label = ctk.CTkLabel(frame, text="Data Storage & File Management", 
                                  font=self.ctk_font_title, text_color="#4da6ff")
        title_label.grid(row=0, column=0, pady=20)
        
        # Storage info
        storage_frame = ctk.CTkFrame(frame, fg_color="#1e2749", corner_radius=15)
        storage_frame.grid(row=1, column=0, pady=20, padx=40, sticky="ew")
        
        storage_info = self.get_storage_info()
        storage_text = f"""Storage Information:
        
• Total Data Files: {storage_info['total_files']} files
• Storage Used: {storage_info['used_space']} MB
• Available Space: {storage_info['free_space']} MB
• Directory: /home/raspberry/Desktop/VSD_GUI/Data_collected/
        
Data is automatically saved every 2 seconds during monitoring"""
        
        ctk.CTkLabel(storage_frame, text=storage_text, font=self.ctk_font_small,justify="left").pack(pady=10, padx=20, fill="x")
        
        # File operations
        operations_frame = ctk.CTkFrame(frame, fg_color="transparent")
        operations_frame.grid(row=2, column=0, pady=20, padx=40, sticky="ew")
        
        # File list with scrollable view
        self.file_listbox_frame = ctk.CTkFrame(frame, fg_color="#1e2749", corner_radius=15)
        self.file_listbox_frame.grid(row=3, column=0, pady=20, padx=40, sticky="ew")
        self.file_listbox_frame.grid_columnconfigure(0, weight=1)
        self.file_listbox_frame.grid_rowconfigure(1, weight=1)
        
        ctk.CTkLabel(self.file_listbox_frame, text="Data Files", 
                    font=self.ctk_font_subtitle).grid(row=0, column=0, pady=(15, 5))
        
        # Create scrollable frame for files
        self.files_scroll_frame = ctk.CTkScrollableFrame(self.file_listbox_frame, 
                                                        height=300, fg_color="transparent")
        self.files_scroll_frame.grid(row=1, column=0, pady=10, padx=20, sticky="ew")
        self.files_scroll_frame.grid_columnconfigure(0, weight=1)
        
        # File operation buttons
        file_buttons_frame = ctk.CTkFrame(frame, fg_color="transparent")
        file_buttons_frame.grid(row=4, column=0, pady=20)
        
        self.refresh_files_btn = ctk.CTkButton(file_buttons_frame, text="Refresh Files",
                                              command=self.refresh_file_list,
                                              width=150, height=40, corner_radius=20)
        self.refresh_files_btn.pack(side="left", padx=10)
        
        self.delete_all_btn = ctk.CTkButton(file_buttons_frame, text="Delete All Files",
                                           command=self.delete_all_files,
                                           width=150, height=40, corner_radius=20,
                                           fg_color="#dc3545", hover_color="#c82333")
        self.delete_all_btn.pack(side="left", padx=10)
        
        # File viewer
        self.file_viewer_frame = ctk.CTkFrame(frame, fg_color="#1e2749", corner_radius=15)
        self.file_viewer_frame.grid(row=5, column=0, pady=20, padx=40, sticky="ew")
        
        ctk.CTkLabel(self.file_viewer_frame, text="File Viewer", 
                    font=self.ctk_font_subtitle).pack(pady=(15, 5))
        
        self.file_content_text = ctk.CTkTextbox(self.file_viewer_frame, height=200, width=800)
        self.file_content_text.pack(pady=10, padx=20, fill="both", expand=True)
        
        # Initially load file list
        self.refresh_file_list()

    def update_control_state(self):
        control_path = "/tmp/vsd_command.json"
        try:
            if os.path.exists(control_path):
                with open(control_path, "r") as f:
                    data = json.load(f)
                print("Control read by GUI:", data)

                # Only update if not already selected in GUI
                if data.get("audio_on") and data.get("audio_mode"):
                    if not hasattr(self, 'selected_sound') or self.selected_sound["name"] != data["binaural_mode"]:
                        match = [b for b in self.binaural_beats if b["name"] == data["binaural_mode"]]
                        if match:
                            self.select_binaural(match[0], write=False)  # Don't write back

                if data.get("light_on") and data.get("light_mode"):
                    if not hasattr(self, 'selected_light') or self.selected_light["name"] != data["light_mode"]:
                        match = [l for l in self.light_colors if l["name"] == data["light_mode"]]
                        if match:
                            self.select_light(match[0], write=False)

                if "brightness" in data and hasattr(self, "brightness_slider"):
                    current = int(self.brightness_slider.get())
                    new = int(data["brightness"])
                    if current != new:
                        self.brightness_slider.set(new)

        except Exception as e:
            print(f"❌ Error reading control settings: {e}")

        self.after(2000, self.update_control_state)



    def build_phone_connect(self, frame):
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure((1, 2, 3), weight=1)

        title_label = ctk.CTkLabel(
            frame,
            text="Connect Your Phone",
            font=self.ctk_font_title,
            text_color="#4da6ff"
        )
        title_label.grid(row=0, column=0, pady=(20, 10), padx=20, sticky="n")

        instructions_frame = ctk.CTkFrame(frame, fg_color="#1e2749", corner_radius=15)
        instructions_frame.grid(row=1, column=0, pady=10, padx=40, sticky="ew")

        instructions_text = (
            "Instructions:\n"
            "1. Ensure your phone is connected to the same WiFi\n"
            "2. Open your phone's camera app\n"
            "3. Scan the QR code below\n"
            "4. Open the link that appears\n"
            "5. You can now control Sleep Doc from your phone!\n\n"
            "Note: The QR code contains IP address for remote access."
        )

        instructions_label = ctk.CTkLabel(
            instructions_frame,
            text=instructions_text,
            font=self.ctk_font_small,
            justify="left",
            text_color="white",
            wraplength=500
        )
        instructions_label.grid(row=0, column=0, padx=20, pady=20, sticky="w")

        self.qr_frame = ctk.CTkFrame(frame, fg_color="#1e2749", corner_radius=15)
        self.qr_frame.grid(row=2, column=0, pady=10, padx=40, sticky="ew")
        self.qr_frame.grid_columnconfigure(0, weight=1)

        qr_title=ctk.CTkLabel(
            self.qr_frame,
            text="QR Code",
            font=self.ctk_font_subtitle,
            text_color="white"
        )
        qr_title.grid(row=0, column=0, pady=(15, 5), sticky="n")

        self.qr_label = ctk.CTkLabel(
            self.qr_frame,
            text="Loading QR Code...",
            font=self.ctk_font_medium,
            text_color="#888888"
        )
        self.qr_label.grid(row=1, column=0, pady=10, sticky="n")
        

        self.load_qr_code()

        qr_buttons_frame = ctk.CTkFrame(frame, fg_color="transparent")
        qr_buttons_frame.grid(row=3, column=0, pady=20)

        self.refresh_qr_btn = ctk.CTkButton(
            qr_buttons_frame,
            text="Refresh QR Code",
            command=self.refresh_qr_code,
            width=180,
            height=45,
            corner_radius=20
        )
        self.refresh_qr_btn.pack(side="left", padx=10)

        self.show_ip_btn = ctk.CTkButton(
            qr_buttons_frame,
            text="Show IP Address",
            command=self.show_current_ip,
            width=180,
            height=45,
            corner_radius=20
        )
        self.show_ip_btn.pack(side="left", padx=10)

        
    def build_wifi_setup(self, frame):
        frame.grid_columnconfigure(0, weight=1)
        title_label = ctk.CTkLabel(frame, text="WiFi Network Setup", 
                              font=self.ctk_font_title, text_color="#4da6ff")
        title_label.grid(row=0, column=0, pady=20)
        self.wifi_status_frame = ctk.CTkFrame(frame, fg_color="#1e2749", corner_radius=15)
        self.wifi_status_frame.grid(row=1, column=0, pady=20, padx=40, sticky="ew")
        ctk.CTkLabel(self.wifi_status_frame, text="Current WiFi Status", 
                font=self.ctk_font_subtitle).pack(pady=(15, 5))
                
        self.wifi_status_label = ctk.CTkLabel(self.wifi_status_frame, text="Checking connection...", 
                                         font=self.ctk_font_medium)
        self.wifi_status_label.pack(pady=10)
        
        networks_frame = ctk.CTkFrame(frame, fg_color="#1e2749", corner_radius=15)
        networks_frame.grid(row=2, column=0, pady=20, padx=40, sticky="ew")
        networks_frame.grid_columnconfigure(0, weight=1)
        networks_frame.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(networks_frame, text="Available WiFi Networks", 
                font=self.ctk_font_subtitle).grid(row=0, column=0, pady=(15, 5))
                
        self.networks_scroll_frame = ctk.CTkScrollableFrame(networks_frame, 
                                                       height=200, fg_color="transparent")
        self.networks_scroll_frame.grid(row=1, column=0, pady=10, padx=20, sticky="ew")
        self.networks_scroll_frame.grid_columnconfigure(0, weight=1)
        wifi_controls_frame = ctk.CTkFrame(frame, fg_color="transparent")
        wifi_controls_frame.grid(row=3, column=0, pady=20)
        self.scan_wifi_btn = ctk.CTkButton(wifi_controls_frame, text="🔍 Scan Networks",
                                      command=self.scan_wifi_networks,
                                      width=150, height=45, corner_radius=20)
                                      
        self.scan_wifi_btn.pack(side="left", padx=10)
        self.hotspot_btn = ctk.CTkButton(wifi_controls_frame, text="📶 Create Hotspot",
                                    command=self.create_hotspot,
                                    width=150, height=45, corner_radius=20,
                                    fg_color="#ff6b6b", hover_color="#ff5252")
        self.hotspot_btn.pack(side="left", padx=10)
        self.wifi_form_frame = ctk.CTkFrame(frame, fg_color="#1e2749", corner_radius=15)
        self.wifi_form_frame.grid(row=4, column=0, pady=20, padx=40, sticky="ew")
        
        ctk.CTkLabel(self.wifi_form_frame, text="Connect to WiFi Network", 
                font=self.ctk_font_subtitle).pack(pady=(15, 10))
                
        ctk.CTkLabel(self.wifi_form_frame, text="Network Name (SSID):", 
                font=self.ctk_font_medium).pack(pady=(10, 5))
                
        self.wifi_ssid_entry = ctk.CTkEntry(self.wifi_form_frame, width=400, height=35)
        self.wifi_ssid_entry.pack(pady=5)
        
        ctk.CTkLabel(self.wifi_form_frame, text="Password:", 
                font=self.ctk_font_medium).pack(pady=(10, 5))
        self.wifi_password_entry = ctk.CTkEntry(self.wifi_form_frame, width=400, height=35, show="*")
        self.wifi_password_entry.pack(pady=5)
        self.connect_wifi_btn = ctk.CTkButton(self.wifi_form_frame, text="🔗 Connect to WiFi",
                                         command=self.connect_to_wifi,
                                         width=200, height=45, corner_radius=20)
        self.connect_wifi_btn.pack(pady=20)
        self.update_wifi_status()
        self.scan_wifi_networks()
        

    def get_storage_info(self):
        """Get storage information"""
        try:
            data_dir = "/home/raspberry/Desktop/VSD_GUI/Data_collected/"
            if not os.path.exists(data_dir):
                os.makedirs(data_dir, exist_ok=True)
            
            # Count files
            csv_files = glob.glob(os.path.join(data_dir, "*.csv"))
            total_files = len(csv_files)
            
            # Calculate used space
            used_space = 0
            for file_path in csv_files:
                try:
                    used_space += os.path.getsize(file_path)
                except:
                    pass
            used_space_mb = used_space / (1024 * 1024)
            
            # Get available space
            import shutil
            total, used, free = shutil.disk_usage(data_dir)
            free_space_mb = free / (1024 * 1024)
            
            return {
                "total_files": total_files,
                "used_space": f"{used_space_mb:.2f}",
                "free_space": f"{free_space_mb:.0f}"
            }
        except Exception as e:
            print(f"Error getting storage info: {e}")
            return {"total_files": 0, "used_space": "0.00", "free_space": "Unknown"}

    def refresh_file_list(self):
        """Refresh the file list display"""
        try:
            # Clear existing file widgets
            for widget in self.files_scroll_frame.winfo_children():
                widget.destroy()
            
            data_dir = "/home/raspberry/Desktop/VSD_GUI/Data_collected/"
            if not os.path.exists(data_dir):
                os.makedirs(data_dir, exist_ok=True)
                
            csv_files = glob.glob(os.path.join(data_dir, "*.csv"))
            csv_files.sort(key=os.path.getmtime, reverse=True)  # Sort by modification time
            
            if not csv_files:
                no_files_label = ctk.CTkLabel(self.files_scroll_frame, 
                                             text="No data files found", 
                                             font=self.ctk_font_medium, 
                                             text_color="#888888")
                no_files_label.pack(pady=20)
                return
            
            # Create file entries
            for i, file_path in enumerate(csv_files):
                file_name = os.path.basename(file_path)
                file_size = os.path.getsize(file_path) / 1024  # Size in KB
                file_date = datetime.fromtimestamp(os.path.getmtime(file_path))
                
                # File entry frame
                file_frame = ctk.CTkFrame(self.files_scroll_frame, fg_color="#2d3748", corner_radius=10)
                file_frame.pack(fill="x", pady=5, padx=10)
                file_frame.grid_columnconfigure(1, weight=1)
                
                # File icon
                file_icon = ctk.CTkLabel(file_frame, text=">", font=self.ctk_font_medium)
                file_icon.grid(row=0, column=0, padx=10, pady=10)
                
                # File info
                file_info = f"{file_name}\n{file_size:.1f} KB • {file_date.strftime('%Y-%m-%d %H:%M')}"
                file_info_label = ctk.CTkLabel(file_frame, text=file_info, 
                                              font=self.ctk_font_small, justify="left")
                file_info_label.grid(row=0, column=1, padx=10, pady=10, sticky="w")
                
                # View button
                view_btn = ctk.CTkButton(file_frame, text="View", width=80, height=30,
                                        command=lambda fp=file_path: self.view_file(fp))
                view_btn.grid(row=0, column=2, padx=5, pady=10)
                
                # Delete button
                delete_btn = ctk.CTkButton(file_frame, text="X", width=40, height=30,
                                          fg_color="#dc3545", hover_color="#c82333",
                                          command=lambda fp=file_path: self.delete_file(fp))
                delete_btn.grid(row=0, column=3, padx=5, pady=10)
            
            # Update storage info
            storage_info = self.get_storage_info()
            print(f"Files refreshed: {storage_info['total_files']} files found")
            
        except Exception as e:
            print(f"Error refreshing file list: {e}")
            messagebox.showerror("Error", f"Failed to refresh file list: {e}")

    def view_file(self, file_path):
        """View file contents"""
        try:
            with open(file_path, 'r') as file:
                content = file.read()
                
            # Clear and display content
            self.file_content_text.delete("1.0", "end")
            
            # Show first 50 lines to avoid overwhelming the display
            lines = content.split('\n')
            if len(lines) > 50:
                display_content = '\n'.join(lines[:50]) + f"\n\n... (showing first 50 lines of {len(lines)} total lines)"
            else:
                display_content = content
                
            self.file_content_text.insert("1.0", display_content)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to read file: {e}")

    def delete_file(self, file_path):
        """Delete a specific file"""
        try:
            file_name = os.path.basename(file_path)
            if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete '{file_name}'?"):
                os.remove(file_path)
                messagebox.showinfo("Success", f"File '{file_name}' deleted successfully!")
                self.refresh_file_list()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete file: {e}")

    def delete_all_files(self):
        """Delete all data files"""
        try:
            data_dir = "/home/raspberry/Desktop/VSD_GUI/Data_collected/"
            csv_files = glob.glob(os.path.join(data_dir, "*.csv"))
            
            if not csv_files:
                messagebox.showinfo("Info", "No files to delete!")
                return
                
            if messagebox.askyesno("Confirm Delete All", 
                                  f"Are you sure you want to delete ALL {len(csv_files)} data files?\n\nThis action cannot be undone!"):
                deleted_count = 0
                for file_path in csv_files:
                    try:
                        os.remove(file_path)
                        deleted_count += 1
                    except Exception as e:
                        print(f"Error deleting {file_path}: {e}")
                
                messagebox.showinfo("Success", f"Deleted {deleted_count} files successfully!")
                self.refresh_file_list()
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete files: {e}")

    def update_analysis_display(self):
        """Update the real-time analysis display with current data"""
        try:
            # Current vitals
            current_vitals = f"""Real-time Vitals (Updated: {datetime.now().strftime('%H:%M:%S')}):
            
Heart Rate: {self.hr} bpm
Breathing Rate: {self.br} rpm
Temperature: {self.temp}°C
Humidity: {self.hum}%
Pressure: {self.press} hPa

Status: {"Monitoring Active" if monitoring else "Monitoring Paused"}"""
            
            self.current_vitals_text.delete("1.0", "end")
            self.current_vitals_text.insert("1.0", current_vitals)
            
            # Health insights based on current values
            insights = self.generate_health_insights()
            self.health_insights_text.delete("1.0", "end")
            self.health_insights_text.insert("1.0", insights)
            
            # Trend analysis
            trend_analysis = self.generate_trend_analysis()
            self.trend_analysis_text.delete("1.0", "end")
            self.trend_analysis_text.insert("1.0", trend_analysis)
            
            # Recommendations
            recommendations = self.generate_recommendations()
            self.recommendations_text.delete("1.0", "end")
            self.recommendations_text.insert("1.0", recommendations)
            
        except Exception as e:
            print(f"Error updating analysis display: {e}")

    def generate_health_insights(self):
        """Generate health insights based on current data"""
        try:
            insights = []
            current_time = datetime.now().strftime('%H:%M:%S')
            
            # Heart rate analysis
            if isinstance(self.hr, (int, float)) and self.hr > 0:
                if self.hr > 100:
                    insights.append("Elevated heart rate detected - may indicate stress or activity")
                elif self.hr < 60:
                    insights.append("Low resting heart rate - could indicate good fitness or relaxation")
                elif 60 <= self.hr <= 100:
                    insights.append("Heart rate is within normal resting range")
                else:
                    insights.append("Heart rate reading seems unusual")
            
            # Breathing rate analysis
            if isinstance(self.br, (int, float)) and self.br > 0:
                if self.br > 20:
                    insights.append("Rapid breathing detected - check for anxiety or discomfort")
                elif self.br < 12:
                    insights.append("Slow, deep breathing - indicates relaxation")
                elif 12 <= self.br <= 20:
                    insights.append("Breathing rate is normal")
            
            # Environmental analysis
            if isinstance(self.temp, (int, float)) and self.temp > 0:
                if self.temp > 26:
                    insights.append("Room temperature is warm - may affect sleep quality")
                elif self.temp < 18:
                    insights.append("Room temperature is cool - consider warming")
                else:
                    insights.append("Room temperature is comfortable for sleep")
            
            if isinstance(self.hum, (int, float)) and self.hum > 0:
                if self.hum > 60:
                    insights.append("High humidity detected - may cause discomfort")
                elif self.hum < 30:
                    insights.append("Low humidity - consider using a humidifier")
                else:
                    insights.append("Humidity levels are optimal")
            
            if not insights:
                insights.append("Waiting for stable readings to generate insights...")
            
            return f"Health Analysis ({current_time}):\n\n" + "\n\n".join(insights)
            
        except Exception as e:
            return f"Error generating insights: {e}"

    def generate_trend_analysis(self):
        """Generate trend analysis"""
        try:
            # Simple trend analysis based on recent data
            trend_text = f"""Trend Analysis (Last 60 seconds):

Heart Rate Trends:
• Current: {self.hr} bpm
• Pattern: {"Stable" if isinstance(self.hr, (int, float)) and 60 <= self.hr <= 100 else "Monitoring"}

Breathing Rate Trends:
• Current: {self.br} rpm  
• Pattern: {"Normal rhythm" if isinstance(self.br, (int, float)) and 12 <= self.br <= 20 else "Observing"}

Environmental Trends:
• Temperature: {self.temp}°C
• Humidity: {self.hum}%
• Pressure: {self.press} hPa

Overall Status:
{"System is collecting baseline data for trend analysis..." if not monitoring else "Active monitoring - trends will develop over time"}"""

            return trend_text
            
        except Exception as e:
            return f"Error generating trend analysis: {e}"

    def generate_recommendations(self):
        """Generate personalized recommendations"""
        try:
            recommendations = []
            
            # Based on heart rate
            if isinstance(self.hr, (int, float)) and self.hr > 100:
                recommendations.append("Try deep breathing exercises to lower heart rate")
                recommendations.append("Consider meditation or relaxation techniques")
            
            # Based on breathing rate
            if isinstance(self.br, (int, float)) and self.br > 20:
                recommendations.append("Practice slow, controlled breathing (4-7-8 technique)")
            
            # Environmental recommendations
            if isinstance(self.temp, (int, float)) and self.temp > 26:
                recommendations.append("❄️ Consider lowering room temperature for better sleep")
            elif isinstance(self.temp, (int, float)) and self.temp < 18:
                recommendations.append("Room may be too cool - consider warming")
            
            if isinstance(self.hum, (int, float)):
                if self.hum > 60:
                    recommendations.append("Use dehumidifier to reduce moisture")
                elif self.hum < 30:
                    recommendations.append("Use humidifier to increase moisture")
            
            # General recommendations
            if monitoring:
                recommendations.append("Continue monitoring for optimal health insights")
            else:
                recommendations.append("▶️ Start monitoring to receive personalized recommendations")
            
            # Binaural beats recommendations
            if self.selected_sound:
                recommendations.append(f"Currently using: {self.selected_sound['name']} therapy")
            else:
                recommendations.append("Try binaural beats for relaxation and focus")
            
            # Light therapy recommendations
            if self.selected_light:
                recommendations.append(f"Ambient lighting: {self.selected_light['name']} mode active")
            else:
                recommendations.append("Consider ambient light therapy for mood enhancement")
            
            if not recommendations:
                recommendations.append("Continue monitoring for personalized recommendations")
            
            return "Personalized Recommendations:\n\n• " + "\n• ".join(recommendations)
            
        except Exception as e:
            return f"Error generating recommendations: {e}"

    # Navigation methods
    def show_home(self):
        self.hide_all_frames()
        self.home_frame.grid(row=0, column=0, sticky="nsew")
        self.current_page = "home"

    def show_binaural(self):
        self.hide_all_frames()
        self.binaural_frame.grid(row=0, column=0, sticky="nsew")
        self.current_page = "binaural"

    def show_light(self):
        self.hide_all_frames()
        self.light_frame.grid(row=0, column=0, sticky="nsew")
        self.current_page = "light"

    def show_analysis(self):
        self.hide_all_frames()
        self.analysis_frame.grid(row=0, column=0, sticky="nsew")
        self.current_page = "analysis"
        # Update analysis immediately when showing
        self.update_analysis_display()

    def show_data_storage(self):
        self.hide_all_frames()
        self.data_storage_frame.grid(row=0, column=0, sticky="nsew")
        self.current_page = "data_storage"
        # Refresh file list when showing data storage
        self.refresh_file_list()
    
    def show_connect_phone(self):
        self.hide_all_frames()
        self.phone_connect_frame.grid(row=0, column=0, sticky="nsew")
        self.current_page = "phone_connect"
        self.load_qr_code()
        
    def show_wifi_setup(self):
        self.hide_all_frames()
        self.wifi_setup_frame.grid(row=0, column=0, sticky="nsew")
        self.current_page = "wifi_setup"
        self.update_wifi_status()

    def hide_all_frames(self):
        """Hide all content frames"""
        for frame in [self.home_frame,self.phone_connect_frame, self.wifi_setup_frame,
                        self.binaural_frame, self.light_frame, 
                     self.analysis_frame, self.data_storage_frame]:
            frame.grid_remove()

    # Binaural beats methods
    def select_binaural(self, beat,write=True):
        """Select a binaural beat"""
        self.selected_sound = beat
        self.audio_enabled = True
        self.selected_binaural_label.configure(
            text=f"Selected: {beat['name']} ({beat['freq']})",
            text_color="#4da6ff"
        )
        self.play_binaural_btn.configure(state="normal")
        self.stop_binaural_btn.configure(state="normal")
        self.send_control_settings() 
        if write:
            self.write_control_settings()
        # Save selection for the analysis script
        try:
            selections = {}
            if os.path.exists("/tmp/vsd_selection.json"):
                with open("/tmp/vsd_selection.json", "r") as f:
                    selections = json.load(f)
            
            selections["sound"] = beat["code"]
            
            with open("/tmp/vsd_selection.json", "w") as f:
                json.dump(selections, f)
                
        except Exception as e:
            print(f"Error saving binaural selection: {e}")

    def play_binaural(self):
        """Play selected binaural beat"""
        if self.selected_sound:
            messagebox.showinfo("Binaural Beats", 
                              f"Playing {self.selected_sound['name']} ({self.selected_sound['freq']})")
            self.write_control_settings()

    def stop_binaural(self):
        """Stop binaural beat playback"""
        messagebox.showinfo("Binaural Beats", "Binaural beat playback stopped")
        self.write_control_settings()

    # Light therapy methods
    def select_light(self, light, write=True):
        """Select a light color"""
        self.selected_light = light
        self.selected_light_label.configure(
            text=f"Selected: {light['name']} Light",
            text_color=light['color']
        )
        self.turn_on_light_btn.configure(state="normal")
        self.turn_off_light_btn.configure(state="normal")
        self.send_control_settings()

        if write:
            self.write_control_settings()

        # Save selection for the analysis script (app format)
        try:
            selections = {}
            if os.path.exists("/tmp/vsd_selection.json"):
                with open("/tmp/vsd_selection.json", "r") as f:
                    selections = json.load(f)

            selections["light_on"] = True
            selections["light_mode"] = light["name"]
            selections["brightness"] = int(self.brightness_slider.get())

            with open("/tmp/vsd_selection.json", "w") as f:
                json.dump(selections, f)

        except Exception as e:
            print(f"Error saving light selection: {e}")


    def adjust_brightness(self, value):
        """Adjust brightness slider"""
        brightness = int(value)
        self.brightness_value_label.configure(text=f"{brightness}%")
        self.send_control_settings()
        self.write_control_settings()

        # Save brightness in app format
        try:
            selections = {}
            if os.path.exists("/tmp/vsd_selection.json"):
                with open("/tmp/vsd_selection.json", "r") as f:
                    selections = json.load(f)

            selections["brightness"] = brightness

            with open("/tmp/vsd_selection.json", "w") as f:
                json.dump(selections, f)

        except Exception as e:
            print(f"Error saving brightness: {e}")


    def turn_on_light(self):
        """Turn on ambient light"""
        if self.selected_light:
            brightness = int(self.brightness_slider.get())
            messagebox.showinfo("Ambient Light", 
                              f"{self.selected_light['name']} light turned on at {brightness}% brightness")
            self.write_control_settings()

    def turn_off_light(self):
        """Turn off ambient light"""
        try:
            if os.path.exists("/tmp/vsd_selection.json"):
                with open("/tmp/vsd_selection.json", "r") as f:
                    selections = json.load(f)

                selections["light_on"] = False
                selections["light_mode"] = ""

                with open("/tmp/vsd_selection.json", "w") as f:
                    json.dump(selections, f)

            messagebox.showinfo("Ambient Light", "Ambient light turned off")
            self.write_control_settings()

        except Exception as e:
            print(f"Error turning off light: {e}")


    
    # Monitoring methods
    def toggle_monitoring(self):
        """Toggle monitoring state"""
        global monitoring, vitals_process
        
        if not monitoring:
            # Start monitoring
            try:
                # Remove stop file if exists
                if os.path.exists("/tmp/stop_vitals"):
                    os.remove("/tmp/stop_vitals")
                
                # Start the vitals script
                vitals_process = subprocess.Popen(["sudo",
                    "python3", "/home/raspberry/Desktop/VSD_GUI/vsd_on_startup.py"
                ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                monitoring = True
                self.monitor_btn.configure(text="Stop Monitoring", fg_color="#dc3545", hover_color="#c82333")
                messagebox.showinfo("Monitoring", "Vitals monitoring started!")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to start monitoring: {e}")
        else:
            # Stop monitoring
            try:
                # Create stop file
                with open("/tmp/stop_vitals", "w") as f:
                    f.write("stop")
                
                # Terminate process if running
                if vitals_process and vitals_process.poll() is None:
                    vitals_process.terminate()
                    vitals_process.wait(timeout=5)
                
                monitoring = False
                self.monitor_btn.configure(text="▶️ Start Monitoring", fg_color="#2d7dd2", hover_color="#1e5f99")
                messagebox.showinfo("Monitoring", "Vitals monitoring stopped!")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to stop monitoring: {e}")

    def exit_app(self):
        """Clean exit of the application"""
        global vitals_process
        
        try:
            # Stop monitoring if running
            if monitoring:
                with open("/tmp/stop_vitals", "w") as f:
                    f.write("stop")
                
                if vitals_process and vitals_process.poll() is None:
                    vitals_process.terminate()
                    vitals_process.wait(timeout=5)
            
            # Clean up temp files
            temp_files = ["/tmp/stop_vitals", "/tmp/live_vitals.txt", "/tmp/vsd_selection.json"]
            for temp_file in temp_files:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                    
        except Exception as e:
            print(f"Error during cleanup: {e}")
        
        self.destroy()

    def handle_secret_click(self, event=None):
        """Detect 5 secret taps to unlock fullscreen"""
        now = time.time()

        # Reset tap count if too much delay between taps
        if now - self.last_tap_time > 3:
            self.secret_tap_count = 0

        self.last_tap_time = now
        self.secret_tap_count += 1
        print(f"Secret tap {self.secret_tap_count}/5")

        if self.secret_tap_count >= 10:
            self.secret_tap_count = 0
            self.attributes("-fullscreen", False)
            self.config(cursor="arrow")
            
            if messagebox.askyesno("Unlock", "Do you want to exit Sleep Doc?"):
                self.exit_app()
            else:
                # Return to fullscreen and hide cursor
                self.attributes("-fullscreen", True)
                self.config(cursor="none")


    def secret_exit(self, event=None):
        """Unlock fullscreen and optionally exit with secret key combo"""
        self.attributes("-fullscreen", False)
        self.config(cursor="arrow")
        if messagebox.askyesno("Exit", "Do you want to close Sleep Doc?"):
            self.exit_app()
            
        # Phone Connection Methods
    def load_qr_code(self):
        """Load and display QR code for phone connection"""
        try:
            qr_path = "/tmp/ip_qr.png"
            if os.path.exists(qr_path):
                # Load QR code image
                qr_image = Image.open(qr_path)
                qr_image = qr_image.resize((300, 300), Image.LANCZOS)
                qr_ctk_image = ctk.CTkImage(light_image=qr_image, dark_image=qr_image, size=(300, 300))
                
                self.qr_label.configure(image=qr_ctk_image, text="")
                self.qr_code_image = qr_ctk_image
            else:
                self.qr_label.configure(text="QR Code not found\nTry refreshing", image=None)
                self.generate_qr_code()
        except Exception as e:
            print(f"Error loading QR code: {e}")
            self.qr_label.configure(text="Error loading QR code\nTry refreshing", image=None)

    def refresh_qr_code(self):
        """Refresh QR code by regenerating it"""
        try:
            self.qr_label.configure(text="Generating QR Code...", image=None)
            self.after(100, self.generate_qr_code)  # Small delay for UI update
        except Exception as e:
            messagebox.showerror("Error", f"Failed to refresh QR code: {e}")

    def generate_qr_code(self):
        """Generate QR code with current IP address"""
        try:
            # Get current IP address
            import socket
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            
            # If that doesn't work, try alternative method
            if local_ip.startswith("127."):
                import subprocess
                result = subprocess.run(['hostname', '-I'], capture_output=True, text=True)
                local_ip = result.stdout.split()[0] if result.stdout else "192.168.1.100"
            
            # Create QR code URL
            qr_url = f"http://{local_ip}:5000"
            
            # Generate QR code using Python
            try:
                import qrcode
                qr = qrcode.QRCode(version=1, box_size=10, border=5)
                qr.add_data(qr_url)
                qr.make(fit=True)
                
                qr_img = qr.make_image(fill_color="black", back_color="white")
                qr_img.save("/tmp/ip_qr.png")
                
                # Load the generated QR code
                self.load_qr_code()
                
            except ImportError:
                self.qr_label.configure(text=f"Connect to:\n{qr_url}\n\nInstall 'qrcode' package\nfor QR code display", image=None)
                
        except Exception as e:
            print(f"Error generating QR code: {e}")
            self.qr_label.configure(text="Error generating QR code", image=None)

    def show_current_ip(self):
        """Show current IP address in a popup"""
        try:
            import socket
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            
            if local_ip.startswith("127."):
                import subprocess
                result = subprocess.run(['hostname', '-I'], capture_output=True, text=True)
                local_ip = result.stdout.split()[0] if result.stdout else "Not connected"
            
            messagebox.showinfo("IP Address", f"Raspberry Pi IP Address:\n{local_ip}\n\nConnect to: http://{local_ip}:5000")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to get IP address: {e}")

    # WiFi Setup Methods
    def update_wifi_status(self):
        """Update current WiFi connection status"""
        try:
            result = subprocess.run(['iwconfig'], capture_output=True, text=True)
            if 'ESSID:' in result.stdout and 'ESSID:off' not in result.stdout:
                for line in result.stdout.split('\n'):
                    if 'ESSID:' in line:
                        ssid = line.split('ESSID:')[1].split()[0].strip('"')
                        self.wifi_status_label.configure(text=f"✅ Connected to: {ssid}", text_color="#4da6ff")
                        break
            else:
                self.wifi_status_label.configure(text="❌ Not connected to WiFi", text_color="#ff6b6b")
        except Exception as e:
            self.wifi_status_label.configure(text="Unable to check WiFi status", text_color="#888888")
            print(f"Error checking WiFi status: {e}")

    def scan_wifi_networks(self):
        """Scan for available WiFi networks"""
        try:
            self.scan_wifi_btn.configure(text="Scanning...", state="disabled")
            for widget in self.networks_scroll_frame.winfo_children():
                widget.destroy()
            result = subprocess.run(['sudo', 'iwlist', 'scan'], capture_output=True, text=True)
            networks = []
            current_network = {}
            for line in result.stdout.split('\n'):
                line = line.strip()
                if 'Cell' in line and 'Address:' in line:
                    if current_network:
                        networks.append(current_network)
                    current_network = {}
                elif 'ESSID:' in line:
                    ssid = line.split('ESSID:')[1].strip('"')
                    if ssid and ssid != '':
                        current_network['ssid'] = ssid
                elif 'Quality=' in line:
                    quality = line.split('Quality=')[1].split()[0]
                    current_network['quality'] = quality
                elif 'Encryption key:' in line:
                    encrypted = 'on' in line.lower()
                    current_network['encrypted'] = encrypted
            if current_network:
                networks.append(current_network)
            if networks:
                for i, network in enumerate(networks):
                    if 'ssid' in network:
                        self.create_network_widget(network, i)
            else:
                no_networks_label = ctk.CTkLabel(self.networks_scroll_frame, 
                    text="No networks found", font=self.ctk_font_medium, text_color="#888888")
                no_networks_label.pack(pady=20)
            self.scan_wifi_btn.configure(text="🔍 Scan Networks", state="normal")
        except Exception as e:
            print(f"Error scanning WiFi: {e}")
            error_label = ctk.CTkLabel(self.networks_scroll_frame, 
                text=f"Scan failed: {str(e)}", font=self.ctk_font_small, text_color="#ff6b6b")
            error_label.pack(pady=10)
            self.scan_wifi_btn.configure(text="🔍 Scan Networks", state="normal")

    def create_network_widget(self, network, index):
        """Create widget for WiFi network"""
        network_frame = ctk.CTkFrame(self.networks_scroll_frame, fg_color="#2d3748", corner_radius=10)
        network_frame.pack(fill="x", pady=5, padx=10)
        network_frame.grid_columnconfigure(1, weight=1)
        icon = "🔒" if network.get('encrypted', True) else "📶"
        icon_label = ctk.CTkLabel(network_frame, text=icon, font=self.ctk_font_medium)
        icon_label.grid(row=0, column=0, padx=10, pady=10)
        ssid = network.get('ssid', 'Unknown')
        quality = network.get('quality', 'Unknown')
        info_text = f"{ssid}\nSignal: {quality}"
        info_label = ctk.CTkLabel(network_frame, text=info_text, font=self.ctk_font_small, justify="left")
        info_label.grid(row=0, column=1, padx=10, pady=10, sticky="w")
        select_btn = ctk.CTkButton(network_frame, text="Select", width=80, height=30,
            command=lambda: self.select_wifi_network(ssid))
        select_btn.grid(row=0, column=2, padx=5, pady=10)

    def select_wifi_network(self, ssid):
        """Select a WiFi network"""
        self.wifi_ssid_entry.delete(0, "end")
        self.wifi_ssid_entry.insert(0, ssid)
        self.selected_wifi = ssid

    def connect_to_wifi(self):
        """Connect to selected WiFi network"""
        ssid = self.wifi_ssid_entry.get().strip()
        password = self.wifi_password_entry.get().strip()
        if not ssid:
            messagebox.showerror("Error", "Please enter a network name (SSID)")
            return
        try:
            self.connect_wifi_btn.configure(text="Connecting...", state="disabled")
            config = f'''network={{
    ssid="{ssid}"
    psk="{password}"
    key_mgmt=WPA-PSK
}}'''
            with open("/tmp/wifi_config.conf", "w") as f:
                f.write(config)
            subprocess.run(['sudo', 'wpa_cli', '-i', 'wlan0', 'add_network'], check=True)
            subprocess.run(['sudo', 'wpa_cli', '-i', 'wlan0', 'set_network', '0', 'ssid', f'"{ssid}"'], check=True)
            if password:
                subprocess.run(['sudo', 'wpa_cli', '-i', 'wlan0', 'set_network', '0', 'psk', f'"{password}"'], check=True)
            else:
                subprocess.run(['sudo', 'wpa_cli', '-i', 'wlan0', 'set_network', '0', 'key_mgmt', 'NONE'], check=True)
            subprocess.run(['sudo', 'wpa_cli', '-i', 'wlan0', 'enable_network', '0'], check=True)
            subprocess.run(['sudo', 'wpa_cli', '-i', 'wlan0', 'save_config'], check=True)
            time.sleep(3)
            self.update_wifi_status()
            messagebox.showinfo("Success", f"Attempting to connect to {ssid}.\nCheck status above.")
            self.wifi_password_entry.delete(0, "end")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to connect to WiFi: {e}")
        finally:
            self.connect_wifi_btn.configure(text="Connect to WiFi", state="normal")

    def create_hotspot(self):
        """Create WiFi hotspot for configuration"""
        if messagebox.askyesno("Create Hotspot", "This will create a WiFi hotspot named 'SleepDoc-Setup'.\n\nPassword: sleepdoc123\n\nContinue?"):
            try:
                self.hotspot_btn.configure(text="Creating...", state="disabled")
                hotspot_script = '''#!/bin/bash
sudo systemctl stop hostapd
sudo systemctl stop dnsmasq
cat << EOF | sudo tee /etc/hostapd/hostapd.conf
interface=wlan0
driver=nl80211
ssid=SleepDoc-Setup
hw_mode=g
channel=7
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=sleepdoc123
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
EOF
cat << EOF | sudo tee /etc/dnsmasq.conf
interface=wlan0
dhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,24h
EOF
sudo ifconfig wlan0 192.168.4.1
sudo systemctl start hostapd
sudo systemctl start dnsmasq
echo "Hotspot created successfully"
'''
                with open("/tmp/create_hotspot.sh", "w") as f:
                    f.write(hotspot_script)
                os.chmod("/tmp/create_hotspot.sh", 0o755)
                result = subprocess.run(['sudo', 'bash', '/tmp/create_hotspot.sh'], capture_output=True, text=True, timeout=30)
                if result.returncode == 0:
                    messagebox.showinfo("Hotspot Created", "WiFi Hotspot 'SleepDoc-Setup' is now active!\n\nConnect your phone to this network with password: sleepdoc123\nThen go to http://192.168.4.1:5000 in your browser")
                else:
                    messagebox.showerror("Error", f"Failed to create hotspot:\n{result.stderr}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create hotspot: {e}")
            finally:
                self.hotspot_btn.configure(text="📶 Create Hotspot", state="normal")

     
     

# --- Run Application ---
if __name__ == "__main__":
    # Show splash screen first
    splash = SplashScreen()
    splash.mainloop()
