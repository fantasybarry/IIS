import numpy as np
import json
import time
import sqlite3
from datetime import datetime
from gpiozero import InputDevice
try:
    import adafruit_bmp280
    import board
except ImportError:
    print("Warning: Adafruit libraries not available. Some sensors may not work.")
    adafruit_bmp280 = None
    board = None

class dataCollector():
    def __init__(self, configFile="Data/waveLengths.json"):
        self.config = self.load_config(configFile)
        if not self.config:
            raise ValueError("Failed to load configuration file")
        
        self.sensors = {}
        self.active_regions = None
        self.data_history = []
        
        # Database setup
        self.db_path = "sensor_data.db"
        self.init_database()
        
        # Initialize sensors based on config
        self.initialize_sensors()
        
        # Change to match the location's pressure (hPa) at sea level
        self.sea_level_pressure = 1013.25

        if self.config.get("mqtt", {}).get("enabled", False):
            try:
                from tools.transmitter import MQTTTransmitter
                self.mqtt_transmitter = MQTTTransmitter(self.config["mqtt"])
                if self.mqtt_transmitter.connect():
                    print("✅ MQTT transmitter connected")
                else:
                    print("❌ MQTT connection failed - data will be queued")
            except ImportError:
                print("Warning: paho-mqtt not installed. Install with: pip install paho-mqtt")
                self.mqtt_transmitter = None
            except ConnectionError:
                print("Failed to connect to the target host. Check the host config")
            except Exception as e:
                print(f"MQTT Setup error: {e}")
                self.mqtt_transmitter = None
        else:
            self.mqtt_transmitter = None
        
    def load_config(self, path):
        """ Load Json file for Configuration """
        try:
            with open(path, 'r') as f:
                collConfig = json.load(f)
            print("Configuration Json file loaded successfully: ", collConfig)
            return collConfig
        except FileNotFoundError:
            print("Error: File not found")
            return None
    
    def init_database(self):
        """Initialize SQLite database for storing sensor data"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sensor_readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                sensor_type TEXT,
                measurement_type TEXT,
                value REAL,
                x_position REAL,
                y_position REAL,
                z_position REAL
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def initialize_sensors(self):
        """Dynamic Sensor initialization based on config"""
        for sensor_type, params in self.config["sensors_definition"].items():
            try:
                if sensor_type == "bmp280" and board and adafruit_bmp280:
                    i2c = board.I2C()
                    address = int(params["pins"]["i2c_address"], 16)
                    sensor = adafruit_bmp280.Adafruit_BMP280_I2C(i2c, address=address)
                    self.sensors[sensor_type] = sensor
                    print(f"Initialized {sensor_type} sensor")
                elif sensor_type == "ir_obstacle":
                    gpio_pin = params["pins"]["gpio"]
                    sensor = InputDevice(gpio_pin)
                    self.sensors[sensor_type] = sensor
                    print(f"Initialized {sensor_type} sensor on GPIO {gpio_pin}")
            except Exception as e:
                print(f"Failed to initialize {sensor_type}: {e}")
    
    def collect_all_data(self):
        """Collect data from all initialized sensors"""
        readings = []
        timestamp = datetime.now().isoformat()
        
        for sensor_type, sensor in self.sensors.items():
            try:
                sensor_config = self.config["sensors_definition"][sensor_type]
                position = self.config["mapping"]["sensor_positions"][sensor_type]
                
                if sensor_type == "bmp280":
                    data = {
                        "temperature": sensor.temperature,
                        "pressure": sensor.pressure,
                        "altitude": sensor.altitude
                    }
                elif sensor_type == "ir_obstacle":
                    data = {
                        "obstacle_detected": not sensor.is_active  # Inverted logic
                    }
                
                # Store each measurement
                for measurement, value in data.items():
                    reading = {
                        "timestamp": timestamp,
                        "sensor_type": sensor_type,
                        "measurement_type": measurement,
                        "value": float(value) if isinstance(value, (int, float)) else int(value),
                        "x_position": position["x"],
                        "y_position": position["y"],
                        "z_position": position["z"]
                    }
                    readings.append(reading)
                    
            except Exception as e:
                print(f"Error reading from {sensor_type}: {e}")
        
        # Store in database
        self.store_readings(readings)
        return readings
    
    def store_readings(self, readings):
        """Store sensor readings in database"""
        conn = sqlite3.connect(self.db_path)
        
        # Transmit via MQTT if enabled
        if self.mqtt_transmitter:
            try:
                success_count = self.mqtt_transmitter.transmit_batch(readings)
                if success_count > 0:
                    print(f"📡 Transmitted {success_count}/{len(readings)} readings via MQTT")
            except Exception as e:
                print(f"MQTT transmitted error: {e}")
                
        cursor = conn.cursor()
        
        for reading in readings:
            cursor.execute('''
                INSERT INTO sensor_readings 
                (timestamp, sensor_type, measurement_type, value, x_position, y_position, z_position)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                reading["timestamp"],
                reading["sensor_type"],
                reading["measurement_type"],
                reading["value"],
                reading["x_position"],
                reading["y_position"],
                reading["z_position"]
            ))
        
        conn.commit()
        conn.close()
    
    def get_recent_data(self, hours=1):
        """Get recent sensor data for visualization"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM sensor_readings 
            WHERE datetime(timestamp) > datetime('now', '-{} hours')
            ORDER BY timestamp DESC
        '''.format(hours))
        
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(zip(columns, row)) for row in rows]
    
    def start_continuous_collection(self, interval=5):
        """Start continuous data collection"""
        print(f"Starting continuous data collection every {interval} seconds...")
        try:
            while True:
                readings = self.collect_all_data()
                print(f"Collected {len(readings)} readings at {datetime.now()}")
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\nStopping data collection...")
            
        
        
