#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vattenprojekt - Web version
Flask server för pump-kontroll med sensorer
"""

from flask import Flask, render_template, jsonify, request
import threading
import time
from datetime import datetime

# GPIO Pin definitions
RPWM = 18
LPWM = 19
R_EN = 23
L_EN = 24
PWM_FREQ = 1000

DS18B20_PIN = 4
FLOW_PIN = 17
RELAY_PIN = 22
I2C_ADDRESS = 0x48

app = Flask(__name__)

class PumpController:
    def __init__(self, simulate=True):
        self.simulate = simulate
        self.is_running = False
        self.current_speed = 0
        self.timer_running = False
        self.timer_stop_flag = False
        self.timer_remaining = 0
        self.timer_speed = 0
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
                print("✓ Pump controller initialized (REAL Pi)")
            except ImportError:
                print("RPi.GPIO not available - using simulation")
                self.simulate = True
        
        if self.simulate:
            print("✓ Pump controller initialized (SIMULATION)")
    
    def start_pump(self, speed=100):
        if self.is_running:
            return False
        
        speed = max(0, min(100, speed))
        self.current_speed = speed
        
        if not self.simulate:
            self.GPIO.output(R_EN, self.GPIO.HIGH)
            self.GPIO.output(L_EN, self.GPIO.HIGH)
            self.pwm_rpwm.ChangeDutyCycle(speed)
            self.pwm_lpwm.ChangeDutyCycle(0)
        
        self.is_running = True
        print(f"✓ Pump started ({speed}%)")
        return True
    
    def stop_pump(self):
        if not self.is_running:
            return False
        
        if not self.simulate:
            self.pwm_rpwm.ChangeDutyCycle(0)
            self.pwm_lpwm.ChangeDutyCycle(0)
            self.GPIO.output(R_EN, self.GPIO.LOW)
            self.GPIO.output(L_EN, self.GPIO.LOW)
        
        self.is_running = False
        self.current_speed = 0
        print("✓ Pump stopped")
        return True
    
    def start_timer(self, seconds, speed, callback=None):
        if self.timer_running:
            return False
        
        self.timer_running = True
        self.timer_stop_flag = False
        self.timer_remaining = seconds
        self.timer_speed = speed
        self.update_callback = callback
        thread = threading.Thread(target=self._timer_worker, args=(seconds, speed), daemon=True)
        thread.start()
        print(f"⏱️ Timer started: {seconds}s at {speed}%")
        return True
    
    def _timer_worker(self, seconds, speed):
        self.start_pump(speed)
        
        for remaining in range(seconds, -1, -1):
            if self.timer_stop_flag:
                break
            self.timer_remaining = remaining
            if self.update_callback:
                self.update_callback(remaining)
            time.sleep(1)
        
        self.stop_pump()
        self.timer_running = False
        self.timer_remaining = 0
        if self.update_callback:
            self.update_callback(0)
        print("⏱️ Timer finished")
    
    def stop_timer(self):
        if self.timer_running:
            self.timer_stop_flag = True
            self.stop_pump()
            self.timer_running = False
            print("⏱️ Timer stopped")
            return True
        return False
    
    def cleanup(self):
        self.stop_timer()
        self.stop_pump()


class SensorReader:
    def __init__(self, simulate=True):
        self.simulate = simulate
        self.moisture = [0, 0, 0, 0]
        self.temperature = 0
        
        if not self.simulate:
            try:
                import board
                import busio
                import adafruit_ads1x15.ads1115 as ADS
                from adafruit_ads1x15.analog_in import AnalogIn
                import w1thermsensor
                
                i2c = busio.I2C(board.SCL, board.SDA)
                self.ads = ADS.ADS1115(i2c, address=I2C_ADDRESS)
                self.moisture_channels = [
                    AnalogIn(self.ads, ADS.P0),
                    AnalogIn(self.ads, ADS.P1),
                    AnalogIn(self.ads, ADS.P2),
                    AnalogIn(self.ads, ADS.P3),
                ]
                self.temp_sensor = w1thermsensor.W1ThermSensor()
                print("✓ Sensors initialized (REAL Pi)")
            except ImportError:
                print("Sensor libraries not available - using simulation")
                self.simulate = True
        
        if self.simulate:
            print("✓ Sensors initialized (SIMULATION)")
    
    def read_moisture(self):
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
        raw = self.moisture[sensor_index]
        percent = max(0, min(100, int((dry - raw) / (dry - wet) * 100)))
        return percent


# Initialize
pump = PumpController(simulate=True)
sensors = SensorReader(simulate=True)

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status')
def get_status():
    sensors.read_moisture()
    temp = sensors.read_temperature()
    
    return jsonify({
        'pump_running': pump.is_running,
        'pump_speed': pump.current_speed,
        'timer_running': pump.timer_running,
        'timer_remaining': pump.timer_remaining,
        'timer_speed': pump.timer_speed,
        'temperature': temp,
        'moisture': [sensors.get_moisture_percent(i) for i in range(4)]
    })

@app.route('/api/pump/start', methods=['POST'])
def pump_start():
    speed = request.json.get('speed', 100)
    result = pump.start_pump(speed)
    return jsonify({'success': result})

@app.route('/api/pump/stop', methods=['POST'])
def pump_stop():
    result = pump.stop_pump()
    return jsonify({'success': result})

@app.route('/api/timer/start', methods=['POST'])
def timer_start():
    data = request.json
    seconds = int(data.get('seconds', 30))
    speed = int(data.get('speed', 100))
    
    if seconds <= 0 or speed < 0 or speed > 100:
        return jsonify({'success': False, 'error': 'Invalid values'}), 400
    
    result = pump.start_timer(seconds, speed)
    return jsonify({'success': result})

@app.route('/api/timer/stop', methods=['POST'])
def timer_stop():
    result = pump.stop_timer()
    return jsonify({'success': result})

if __name__ == '__main__':
    try:
        print("\n" + "="*50)
        print("💧 PUMP CONTROL - WEB VERSION")
        print("="*50)
        print("Starting web server...")
        print("Open browser: http://localhost:5000")
        print("="*50 + "\n")
        
        app.run(host='0.0.0.0', port=5000, debug=False)
    except KeyboardInterrupt:
        print("\nShutting down...")
        pump.cleanup()
