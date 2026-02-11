#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vattenprojekt - Pump kontroll
Modern GUI för att starta/stoppa pumpen via BTS7960 motor driver
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

class PumpController:
    def __init__(self, simulate=True):
        """Initialisera pump-kontrollern"""
        self.simulate = simulate
        self.is_running = False
        self.current_speed = 0
        self.timer_running = False
        self.timer_stop_flag = False
        self.update_callback = None
        
        if not self.simulate:
            try:
                import RPi.GPIO as GPIO
                self.GPIO = GPIO
                GPIO.setmode(GPIO.BCM)
                GPIO.setwarnings(False)
                GPIO.setup(RPWM, GPIO.OUT)
                GPIO.setup(LPWM, GPIO.OUT)
                GPIO.setup(R_EN, GPIO.OUT)
                GPIO.setup(L_EN, GPIO.OUT)
                self.pwm_rpwm = GPIO.PWM(RPWM, PWM_FREQ)
                self.pwm_lpwm = GPIO.PWM(LPWM, PWM_FREQ)
                self.pwm_rpwm.start(0)
                self.pwm_lpwm.start(0)
                GPIO.output(R_EN, GPIO.LOW)
                GPIO.output(L_EN, GPIO.LOW)
                print("Pump-kontroller initialiserad (REAL Pi) ✓")
            except ImportError:
                print("RPi.GPIO inte tillgängligt - använder simulering")
                self.simulate = True
        
        if self.simulate:
            print("Pump-kontroller initialiserad (SIMULERING) 🎲")
    
    def start_pump(self, speed=100):
        """Starta pumpen"""
        if self.is_running:
            return
        
        speed = max(0, min(100, speed))
        self.current_speed = speed
        
        if not self.simulate:
            self.GPIO.output(R_EN, self.GPIO.HIGH)
            self.GPIO.output(L_EN, self.GPIO.HIGH)
            self.pwm_rpwm.ChangeDutyCycle(speed)
            self.pwm_lpwm.ChangeDutyCycle(0)
        
        self.is_running = True
        print(f"✓ Pumpen startad ({speed}%)")
    
    def stop_pump(self):
        """Stoppa pumpen"""
        if not self.is_running:
            return
        
        if not self.simulate:
            self.pwm_rpwm.ChangeDutyCycle(0)
            self.pwm_lpwm.ChangeDutyCycle(0)
            self.GPIO.output(R_EN, self.GPIO.LOW)
            self.GPIO.output(L_EN, self.GPIO.LOW)
        
        self.is_running = False
        self.current_speed = 0
        print("✓ Pumpen stoppad")
    
    def start_timer(self, seconds, speed, callback=None):
        """Starta timer"""
        if self.timer_running:
            return
        
        self.timer_running = True
        self.timer_stop_flag = False
        self.update_callback = callback
        thread = threading.Thread(target=self._timer_worker, args=(seconds, speed), daemon=True)
        thread.start()
        print(f"⏱️ Timer startat: {seconds}s vid {speed}%")
    
    def _timer_worker(self, seconds, speed):
        """Timer worker thread"""
        self.start_pump(speed)
        
        for remaining in range(seconds, -1, -1):
            if self.timer_stop_flag:
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
        """Stoppa timer"""
        if self.timer_running:
            self.timer_stop_flag = True
            self.stop_pump()
            self.timer_running = False
            print("⏱️ Timer stoppad")
    
    def cleanup(self):
        """Rensa upp"""
        self.stop_timer()
        self.stop_pump()
        if not self.simulate:
            try:
                self.pwm_rpwm.stop()
                self.pwm_lpwm.stop()
                self.GPIO.cleanup()
            except:
                pass


def main():
    """Huvudprogram"""
    pump = PumpController(simulate=True)
    
    root = tk.Tk()
    root.title("Pump Kontroll - Vattenprojekt")
    root.geometry("700x900")
    root.resizable(False, False)
    
    # Färgschema
    bg_dark = "#1e1e2e"
    bg_frame = "#2d2d3d"
    accent = "#00d4ff"
    success = "#00ff41"
    danger = "#ff0055"
    
    root.configure(bg=bg_dark)
    
    # Style setup
    style = ttk.Style()
    style.theme_use('clam')
    style.configure("TLabelFrame", background=bg_dark, foreground=accent)
    style.configure("TLabelFrame.Label", background=bg_dark, foreground=accent, font=("Arial", 12, "bold"))
    style.configure("TLabel", background=bg_dark, foreground="white")
    style.configure("Title.TLabel", background=bg_dark, foreground=accent, font=("Arial", 26, "bold"))
    style.configure("Header.TLabel", background=bg_dark, foreground=accent, font=("Arial", 13, "bold"))
    style.configure("Info.TLabel", background=bg_dark, foreground="#888888", font=("Arial", 10))
    
    # == TITEL ==
    title = ttk.Label(root, text="💧 PUMP KONTROLL", style="Title.TLabel")
    title.pack(pady=20)
    
    mode = ttk.Label(root, text="🎲 SIMULERING (Windows)" if pump.simulate else "🍓 RASPBERRY PI", style="Info.TLabel")
    mode.pack(pady=5)
    
    # == STATUS ==
    status_frame = tk.Frame(root, bg=bg_frame, relief="sunken", bd=2, height=50)
    status_frame.pack(padx=15, pady=15, fill="x")
    
    status_label = tk.Label(status_frame, text="🔴 STOPPAD", font=("Arial", 18, "bold"), 
                            bg=bg_frame, fg=danger)
    status_label.pack(pady=15)
    
    # == HASTIGHETS-SEKTION ==
    speed_lf = ttk.LabelFrame(root, text="⚙️  Hastighets-kontroll", padding=15)
    speed_lf.pack(padx=15, pady=10, fill="x")
    
    speed_display = ttk.Label(speed_lf, text="Hastighet: 0%", style="Header.TLabel")
    speed_display.pack(pady=10)
    
    speed_var = tk.IntVar(value=0)
    speed_scale = ttk.Scale(speed_lf, from_=0, to=100, orient="horizontal", variable=speed_var)
    speed_scale.pack(pady=10, fill="x")
    
    def update_speed_display(val):
        speed_display.config(text=f"Hastighet: {int(float(val))}%")
    
    speed_scale.config(command=update_speed_display)
    
    # Start/Stop buttons
    btn_frame1 = tk.Frame(speed_lf, bg=bg_dark)
    btn_frame1.pack(pady=15, fill="x")
    
    def start_pump_clicked():
        pump.start_pump(speed=speed_var.get())
        update_status()
    
    def stop_pump_clicked():
        pump.stop_pump()
        update_status()
    
    def update_status():
        if pump.is_running:
            status_label.config(text="🟢 KÖRS", fg=success)
            speed_display.config(text=f"Hastighet: {pump.current_speed}%")
        else:
            status_label.config(text="🔴 STOPPAD", fg=danger)
            speed_display.config(text=f"Hastighet: {speed_var.get()}%")
    
    start_btn = tk.Button(btn_frame1, text="🟢 STARTA", command=start_pump_clicked, 
                          font=("Arial", 11, "bold"), bg=success, fg="black", padx=20, pady=10)
    start_btn.pack(side="left", padx=8, expand=True, fill="both")
    
    stop_btn = tk.Button(btn_frame1, text="🔴 STOPPA", command=stop_pump_clicked, 
                         font=("Arial", 11, "bold"), bg=danger, fg="white", padx=20, pady=10)
    stop_btn.pack(side="left", padx=8, expand=True, fill="both")
    
    # == TIMER-SEKTION ==
    timer_lf = ttk.LabelFrame(root, text="⏱️  Timer-kontroll", padding=15)
    timer_lf.pack(padx=15, pady=10, fill="x")
    
    timer_display = tk.Label(timer_lf, text="⏱️ Timer: Inaktiv", font=("Arial", 15, "bold"), 
                             bg=bg_dark, fg="#888888")
    timer_display.pack(pady=10)
    
    # Timer input
    input_frame = tk.Frame(timer_lf, bg=bg_dark)
    input_frame.pack(pady=10, fill="x")
    
    tk.Label(input_frame, text="Sekunder:", bg=bg_dark, fg="white", font=("Arial", 10)).pack(side="left", padx=5)
    timer_sec = tk.Entry(input_frame, width=8, font=("Arial", 11))
    timer_sec.insert(0, "30")
    timer_sec.pack(side="left", padx=5)
    
    tk.Label(input_frame, text="Hastighet:", bg=bg_dark, fg="white", font=("Arial", 10)).pack(side="left", padx=5)
    timer_speed = tk.Entry(input_frame, width=8, font=("Arial", 11))
    timer_speed.insert(0, "100")
    timer_speed.pack(side="left", padx=5)
    
    # Timer buttons
    btn_frame2 = tk.Frame(timer_lf, bg=bg_dark)
    btn_frame2.pack(pady=15, fill="x")
    
    def timer_callback(remaining):
        if remaining > 0:
            timer_display.config(text=f"⏱️ Timer: {remaining}s", fg=success)
        else:
            timer_display.config(text="⏱️ Timer: Inaktiv", fg="#888888")
    
    def start_timer_clicked():
        try:
            sec = int(timer_sec.get())
            spd = int(timer_speed.get())
            if sec <= 0 or spd < 0 or spd > 100:
                print("Ogiltiga värden!")
                return
            pump.start_timer(sec, spd, callback=timer_callback)
            timer_display.config(text=f"⏱️ Timer: {sec}s", fg=success)
        except ValueError:
            print("Ange giltiga siffror!")
    
    def stop_timer_clicked():
        pump.stop_timer()
        timer_display.config(text="⏱️ Timer: Inaktiv", fg="#888888")
        update_status()
    
    start_timer_btn = tk.Button(btn_frame2, text="▶️ STARTA TIMER", command=start_timer_clicked, 
                                font=("Arial", 11, "bold"), bg=success, fg="black", padx=20, pady=10)
    start_timer_btn.pack(side="left", padx=8, expand=True, fill="both")
    
    stop_timer_btn = tk.Button(btn_frame2, text="⏹️ STOPPA TIMER", command=stop_timer_clicked, 
                               font=("Arial", 11, "bold"), bg=danger, fg="white", padx=20, pady=10)
    stop_timer_btn.pack(side="left", padx=8, expand=True, fill="both")
    
    # Info
    info = ttk.Label(root, text="Dra slidern för att välja hastighet", style="Info.TLabel")
    info.pack(pady=15)
    
    def on_closing():
        pump.cleanup()
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    
    print("=" * 50)
    print("GUI startar...")
    print("=" * 50)
    
    root.mainloop()


if __name__ == "__main__":
    main()
