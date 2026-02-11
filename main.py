#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vattenprojekt - Pump kontroll med sensorer
Modern GUI för pump-styrning med fukt-, temperatur- och flödesläsning
"""

import tkinter as tk
from tkinter import ttk
import time
import threading

# GPIO Pin definitions
RPWM = 18      # Right PWM
LPWM = 19      # Left PWM
R_EN = 23      # Right Enable
L_EN = 24      # Left Enable
PWM_FREQ = 1000

# Sensor pins
DS18B20_PIN = 4      # Temperature sensor
FLOW_PIN = 17        # Flow sensor
RELAY_PIN = 22       # Relay control

# I2C for ADS1115 (moisture sensors)
I2C_ADDRESS = 0x48

class PumpController:
    def __init__(self, simulate=True):
        """Initialisera pump-kontrollern"""
        self.simulate = simulate
        self.is_running = False
        self.current_speed = 0
        self.timer_running = False
        self.timer_thread = None
        self.update_callback = None
        self.timer_stop_flag = False
        
        if not self.simulate:
            try:
                import RPi.GPIO as GPIO
                self.GPIO = GPIO
                GPIO.setmode(GPIO.BCM)
                GPIO.setwarnings(False)
                
                # Setup pins as outputs
                GPIO.setup(RPWM, GPIO.OUT)
                GPIO.setup(LPWM, GPIO.OUT)
                GPIO.setup(R_EN, GPIO.OUT)
                GPIO.setup(L_EN, GPIO.OUT)
                
                # Setup PWM
                self.pwm_rpwm = GPIO.PWM(RPWM, PWM_FREQ)
                self.pwm_lpwm = GPIO.PWM(LPWM, PWM_FREQ)
                
                # Start PWM at 0% duty cycle
                self.pwm_rpwm.start(0)
                self.pwm_lpwm.start(0)
                
                # Disable pump initially
                GPIO.output(R_EN, GPIO.LOW)
                GPIO.output(L_EN, GPIO.LOW)
                
                print("Pump-kontroller initialiserad (REAL Pi) ✓")
            except ImportError:
                print("RPi.GPIO inte tillgängligt - använder simulering")
                self.simulate = True
        
        if self.simulate:
            print("Pump-kontroller initialiserad (SIMULERING) 🎲")
    
    def start_pump(self, speed=100):
        """Starta pumpen vid angiven hastighet (0-100%)"""
        if self.is_running:
            print("Pumpen kör redan!")
            return
        
        # Begränsa hastighet
        speed = max(0, min(100, speed))
        self.current_speed = speed
        
        if not self.simulate:
            # Enable motor
            self.GPIO.output(R_EN, self.GPIO.HIGH)
            self.GPIO.output(L_EN, self.GPIO.HIGH)
            
            # Set speed via PWM
            self.pwm_rpwm.ChangeDutyCycle(speed)
            self.pwm_lpwm.ChangeDutyCycle(0)
        
        self.is_running = True
        print(f"✓ Pumpen startad (hastighet: {speed}%)")
    
    def stop_pump(self):
        """Stoppa pumpen"""
        if not self.is_running:
            print("Pumpen kör inte redan!")
            return
        
        if not self.simulate:
            # Stop PWM
            self.pwm_rpwm.ChangeDutyCycle(0)
            self.pwm_lpwm.ChangeDutyCycle(0)
            
            # Disable motor
            self.GPIO.output(R_EN, self.GPIO.LOW)
            self.GPIO.output(L_EN, self.GPIO.LOW)
        
        self.is_running = False
        self.current_speed = 0
        print("✓ Pumpen stoppad")
    
    def get_status(self):
        """Hämta status på pumpen"""
        status = "KÖRS" if self.is_running else "STOPPAD"
        print(f"Status: Pumpen är {status}")
    
    def start_timer(self, seconds, speed, update_callback=None):
        """Starta timer som kör pumpen i X sekunder"""
        if self.timer_running:
            print("Timer redan igång!")
            return
        
        self.timer_running = True
        self.timer_stop_flag = False  # Återställ stop-flaggan
        self.update_callback = update_callback
        self.timer_thread = threading.Thread(
            target=self._timer_worker,
            args=(seconds, speed),
            daemon=True
        )
        self.timer_thread.start()
        print(f"⏱️ Timer startat: {seconds}s vid {speed}%")
    
    def _timer_worker(self, seconds, speed):
        """Worker-tråd för timer"""
        self.start_pump(speed)
        
        for remaining in range(seconds, -1, -1):
            if self.timer_stop_flag:  # Kontrollera om vi ska avbryta
                break
            
            if self.update_callback:
                self.update_callback(remaining)
            time.sleep(1)
        
        self.stop_pump()
        self.timer_running = False
        if self.update_callback:
            self.update_callback(0)
        print("⏱️ Timer avslutad")
    
    def stop_timer(self):
        """Stoppa timer om den kör"""
        if self.timer_running:
            self.timer_stop_flag = True  # Sätt flaggan så timer-tråden avbryter
            self.stop_pump()
            self.timer_running = False
            print("⏱️ Timer stoppad")
    
    def cleanup(self):
        """Rensa upp GPIO"""
        print("Rensar upp...")
        self.stop_timer()
        self.stop_pump()
        
        if not self.simulate:
            try:
                self.pwm_rpwm.stop()
                self.pwm_lpwm.stop()
                self.GPIO.cleanup()
                print("GPIO rensat ✓")
            except:
                pass


class SensorReader:
    """Läser från alla sensorer"""
    def __init__(self, simulate=True):
        self.simulate = simulate
        self.moisture = [0, 0, 0, 0]  # 4 fuktsensorer
        self.temperature = 0
        self.flow_count = 0
        
        if not self.simulate:
            try:
                import board
                import busio
                import adafruit_ads1x15.ads1115 as ADS
                from adafruit_ads1x15.analog_in import AnalogIn
                import w1thermsensor
                
                # Setup I2C för ADS1115
                i2c = busio.I2C(board.SCL, board.SDA)
                self.ads = ADS.ADS1115(i2c, address=I2C_ADDRESS)
                
                # Setup moisture channels
                self.moisture_channels = [
                    AnalogIn(self.ads, ADS.P0),  # A0
                    AnalogIn(self.ads, ADS.P1),  # A1
                    AnalogIn(self.ads, ADS.P2),  # A2
                    AnalogIn(self.ads, ADS.P3),  # A3
                ]
                
                # Setup DS18B20
                self.temp_sensor = w1thermsensor.W1ThermSensor()
                
                print("Sensorläsare initialiserad (REAL Pi) ✓")
            except ImportError:
                print("Sensorbibliotek inte tillgängligt - använder simulering")
                self.simulate = True
        
        if self.simulate:
            print("Sensorläsare initialiserad (SIMULERING) 🎲")
    
    def read_moisture(self):
        """Läs alla fuktsensorer (0-1023)"""
        if self.simulate:
            import random
            self.moisture = [random.randint(400, 800) for _ in range(4)]
        else:
            try:
                self.moisture = [int(ch.value / 6.5536) for ch in self.moisture_channels]
            except:
                pass
        return self.moisture
    
    def read_temperature(self):
        """Läs temperatur från DS18B20"""
        if self.simulate:
            import random
            self.temperature = round(20 + random.uniform(-2, 2), 1)
        else:
            try:
                self.temperature = round(self.temp_sensor.get_temperature(), 1)
            except:
                pass
        return self.temperature
    
    def get_moisture_percent(self, sensor_index, dry=1023, wet=400):
        """Konvertera moisture-värde till procent (0-100%)"""
        raw = self.moisture[sensor_index]
        percent = max(0, min(100, int((dry - raw) / (dry - wet) * 100)))
        return percent


def main():
    """Huvudprogram"""
    pump = PumpController(simulate=True)  # Använd simulering på lokaldatorn
    sensors = SensorReader(simulate=True)  # Sensors i simulering-läge
    
    # Skapa GUI
    root = tk.Tk()
    root.title("Pump Kontroll - Vattenprojekt")
    root.geometry("700x1050")
    root.resizable(False, False)
    
    # Ställ in färgtema
    bg_color = "#1e1e2e"
    fg_color = "#ffffff"
    accent_color = "#00d4ff"
    success_color = "#00ff41"
    danger_color = "#ff0055"
    frame_bg = "#2d2d3d"
    
    root.configure(bg=bg_color)
    
    # Style configuration
    style = ttk.Style()
    style.theme_use('clam')
    
    # Konfigurerar styles
    style.configure("TLabelFrame", background=bg_color, foreground=fg_color, borderwidth=2)
    style.configure("TLabelFrame.Label", background=bg_color, foreground=accent_color, font=("Arial", 11, "bold"))
    style.configure("TLabel", background=bg_color, foreground=fg_color)
    style.configure("Title.TLabel", background=bg_color, foreground=accent_color, font=("Arial", 24, "bold"))
    style.configure("Subtitle.TLabel", background=bg_color, foreground="#888888", font=("Arial", 10))
    style.configure("Status.TLabel", background=bg_color, font=("Arial", 13, "bold"))
    
    # Knapp-styles
    style.configure("Start.TButton", font=("Arial", 10, "bold"), padding=10)
    style.configure("Stop.TButton", font=("Arial", 10, "bold"), padding=10)
    style.configure("Timer.TButton", font=("Arial", 9, "bold"), padding=8)
    
    # === DEFINIERAR FUNKTIONER FÖRST ===
    def update_status():
        """Uppdatera status-etiketten"""
        if pump.is_running:
            if pump.current_speed == 100:
                status_label.config(text="🚀 FULLT ÖS", foreground=success_color)
            else:
                status_label.config(text="🟢 KÖRS", foreground=success_color)
            speed_label.config(text=f"Hastighet: {pump.current_speed}%")
        else:
            status_label.config(text="🔴 STOPPAD", foreground=danger_color)
            speed_label.config(text=f"Hastighet: {speed_var.get()}%")
    
    def on_start(speed):
        """Knapp-handler för start"""
        pump.start_pump(speed=speed)
        update_status()
    
    def on_stop():
        """Knapp-handler för stopp"""
        pump.stop_pump()
        update_status()
    
    def on_start_timer(seconds_entry, speed_entry, timer_lbl):
        """Knapp-handler för timer-start"""
        try:
            seconds = int(seconds_entry.get())
            speed = int(speed_entry.get())
            
            if seconds <= 0:
                print("Ange sekunder > 0")
                return
            if speed < 0 or speed > 100:
                print("Hastighet måste vara 0-100%")
                return
            
            # Callback för att uppdatera GUI
            def update_timer_display(remaining):
                if remaining > 0:
                    timer_lbl.config(text=f"⏱️ Timer: {remaining}s", foreground=success_color)
                else:
                    timer_lbl.config(text="⏱️ Timer: Inaktiv", foreground="#888888")
            
            pump.start_timer(seconds, speed, update_callback=update_timer_display)
            timer_lbl.config(text=f"⏱️ Timer: {seconds}s", foreground=success_color)
            update_status()
        
        except ValueError:
            print("Ange giltiga siffror!")
    
    def on_stop_timer():
        """Knapp-handler för timer-stopp"""
        pump.stop_timer()
        update_status()
        timer_label.config(text="⏱️ Timer: Inaktiv", foreground="#888888")
    
    # Titel
    title_frame = tk.Frame(root, bg=bg_color)
    title_frame.pack(pady=20, fill="x")
    
    title_label = ttk.Label(title_frame, text="💧 PUMP KONTROLL", style="Title.TLabel")
    title_label.pack()
    
    # Mode label (Simulering eller Real)
    mode_text = "🎲 SIMULERING (Windows)" if pump.simulate else "🍓 RASPBERRY PI (REAL)"
    mode_label = ttk.Label(root, text=mode_text, style="Subtitle.TLabel")
    mode_label.pack(pady=5)
    
    # === STATUS SEKTION ===
    status_frame = tk.Frame(root, bg=frame_bg, relief="sunken", bd=2)
    status_frame.pack(padx=15, pady=15, fill="x")
    
    status_label = ttk.Label(
        status_frame, 
        text="🔴 STOPPAD", 
        style="Status.TLabel",
        foreground=danger_color,
        background=frame_bg
    )
    status_label.pack(pady=15)
    
    # === HASTIGHETS-SEKTION ===
    speed_frame = ttk.LabelFrame(root, text="⚙️  Hastighets-kontroll", padding=20)
    speed_frame.pack(padx=15, pady=10, fill="x")
    
    # Hastighets-display
    speed_label = ttk.Label(speed_frame, text="Hastighet: 0%", style="TLabel", foreground=accent_color, font=("Arial", 13, "bold"))
    speed_label.pack(pady=10)
    
    # Slider för hastighet
    speed_var = tk.IntVar(value=0)
    speed_slider = ttk.Scale(
        speed_frame, 
        from_=0, 
        to=100, 
        orient="horizontal",
        variable=speed_var,
        command=lambda v: speed_label.config(text=f"Hastighet: {int(float(v))}%")
    )
    speed_slider.pack(pady=10, fill="x")
    
    # Hastighets-knappar
    button_frame_speed = ttk.Frame(speed_frame)
    button_frame_speed.pack(pady=15, fill="x", expand=True)
    
    def create_button(parent, text, command, bg_style="Start.TButton"):
        btn = ttk.Button(parent, text=text, command=command, style=bg_style)
        return btn
    
    start_button = create_button(
        button_frame_speed, 
        "🟢 STARTA", 
        lambda: on_start(speed_var.get()),
        "Start.TButton"
    )
    start_button.pack(side="left", padx=8, expand=True, fill="both")
    
    stop_button = create_button(
        button_frame_speed, 
        "🔴 STOPPA", 
        on_stop,
        "Stop.TButton"
    )
    stop_button.pack(side="left", padx=8, expand=True, fill="both")
    
    # === TIMER-SEKTION ===
    timer_frame = ttk.LabelFrame(root, text="⏱️  Timer-kontroll", padding=20)
    timer_frame.pack(padx=15, pady=10, fill="x")
    
    # Timer-display
    timer_label = ttk.Label(
        timer_frame, 
        text="⏱️ Timer: Inaktiv", 
        style="TLabel",
        foreground="#888888",
        font=("Arial", 13, "bold")
    )
    timer_label.pack(pady=10)
    
    # Timer-input
    timer_input_frame = ttk.Frame(timer_frame)
    timer_input_frame.pack(pady=15, fill="x", expand=True)
    
    ttk.Label(timer_input_frame, text="Sekunder:", style="TLabel").pack(side="left", padx=5)
    timer_seconds = ttk.Entry(timer_input_frame, width=10, font=("Arial", 11))
    timer_seconds.insert(0, "30")
    timer_seconds.pack(side="left", padx=5)
    
    ttk.Label(timer_input_frame, text="Hastighet:", style="TLabel").pack(side="left", padx=5)
    timer_speed = ttk.Entry(timer_input_frame, width=10, font=("Arial", 11))
    timer_speed.insert(0, "100")
    timer_speed.pack(side="left", padx=5)
    
    # Timer-knappar
    button_frame_timer = ttk.Frame(timer_frame)
    button_frame_timer.pack(pady=15, fill="x", expand=True)
    
    start_timer_button = create_button(
        button_frame_timer, 
        "▶️ STARTA TIMER", 
        lambda: on_start_timer(timer_seconds, timer_speed, timer_label),
        "Start.TButton"
    )
    start_timer_button.pack(side="left", padx=8, expand=True, fill="both")
    
    stop_timer_button = create_button(
        button_frame_timer, 
        "⏹️ STOPPA TIMER", 
        on_stop_timer,
        "Stop.TButton"
    )
    stop_timer_button.pack(side="left", padx=8, expand=True, fill="both")
    
    # === SENSOR-SEKTION ===
    sensor_lf = ttk.LabelFrame(root, text="📊 Sensorläsning", padding=15)
    sensor_lf.pack(padx=15, pady=10, fill="x")
    
    # Temperatur
    temp_display = ttk.Label(sensor_lf, text="🌡️ Temperatur: --°C", style="Header.TLabel")
    temp_display.pack(pady=5)
    
    # Fuktsensorer
    moisture_labels = []
    moisture_frame = ttk.Frame(sensor_lf)
    moisture_frame.pack(pady=10, fill="x")
    
    for i in range(4):
        lbl = tk.Label(moisture_frame, text=f"💧 Sensor {i+1}: --%", 
                      bg=bg_color, fg="white", font=("Arial", 10), padx=5)
        lbl.pack(side="left", expand=True, fill="x")
        moisture_labels.append(lbl)
    
    # Updatefunktion för sensorer
    def update_sensors():
        """Läs och uppdatera sensorer varje sekund"""
        sensors.read_moisture()
        temp = sensors.read_temperature()
        temp_display.config(text=f"🌡️ Temperatur: {temp}°C")
        
        for i, lbl in enumerate(moisture_labels):
            percent = sensors.get_moisture_percent(i)
            lbl.config(text=f"💧 Sensor {i+1}: {percent}%")
            
            # Färg baserat på fuktnivå
            if percent < 60:
                lbl.config(bg=danger_color, fg="white")  # Röd om under 60%
            else:
                lbl.config(bg=success_color, fg="black")  # Grön om 60% eller över
        
        root.after(1000, update_sensors)
    
    # Starta sensor-uppdateringar
    update_sensors()
    
    # Info text
    info_label = ttk.Label(
        root, 
        text="Dra slidern för att välja hastighet (0-100%)",
        style="Subtitle.TLabel"
    )
    info_label.pack(pady=10)
    
    def on_closing():
        """Hantera fönster-stängning"""
        print("\nAvslutar...")
        pump.cleanup()
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    
    print("=" * 50)
    print("GUI startar...")
    print("=" * 50)
    
    root.mainloop()


if __name__ == "__main__":
    main()


