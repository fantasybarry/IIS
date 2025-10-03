import paho.mqtt.client as mqtt
import json
import time
import threading
from queue import Queue
from datetime import datetime
import logging

class MQTTTransmitter:
    def __init__(self, config):
        self.config = config
        self.client = mqtt.Client()
        self.connected = False
        self.offline_queue = Queue()
        self.max_queue_size = 1000

        # Setup logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

        # Setup callbacks
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_publish = self._on_publish

        # Connection Settings
        self.broker_host = config.get("host", "localhost")
        self.broker_port = config.get("port", 1883)
        self.username = config.get("username")
        self.password = config.get("password")
        self.base_topic = config.get("base_topic", "sensors")
        self.device_id = config.get("device_id", "sensor_device_1")

        if self.username and self.password:
            self.client.username_pw_set(self.username, self.password)
        
    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.connected = True
            self.logger.info(f"Connected to MQTT broker at {self.broker_host}:{self.broker_port}")
            # Process any queued messages
            self._process_offline_queue()
        else:
            self.connected = False
            self.logger.error(f"Failed to connect to MQTT broker. Return code: {rc}")

    def _on_disconnect(self, client, userdata, rc):
        self.connected = False
        self.logger.warning("Disconnected from MQTT broker")

    def _on_publish(self, client, userdata, mid):
        self.logger.debug(f"Message {mid} published successfully!")

    def connect(self):

        try:
            self.client.connect(self.broker_host, self.broker_port, 60)
            self.client.loop_start()

            # Wait for connection with timeout
            timeout = 10
            start_time = time.time()
            while not self.connected and (time.time() - start_time) < timeout:
                time.sleep(0.1)

            return self.connected
        
        except Exception as e:
            self.logger.error(f"Error connecting to MQTT broker: {e}")
            return False
        
    def disconnect(self):
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
        
    def transmit_reading(self, reading):
        if not self._queue_if_offline(reading):
            return self._send_reading(reading)
        return True
    
    def transmit_batch(self, readings):
        success_count = 0
        for reading in readings:
            if self.transmit_reading(reading):
                success_count += 1
        return success_count
    
    def _send_reading(self, reading):
        try:
            # Create topic structure: base_topic/device_id/sensor_type/measurement_type
            topic = f"{self.base_topic}/{self.device_id}/{reading['sensor_type']}/{reading['measurement_type']}"

            # prepare payload
            payload = {
                "timestamp": reading["timestamp"],
                "value": reading["value"],
                "position": {
                    "x": reading["x_position"],
                    "y": reading["y_position"],
                    "z": reading["z_position"]
                },
                "device_id": self.device_id,
                "sensor_type": reading["sensor_type"],
                "measurement_type": reading["measurement_type"]
            }

            # Publish Message
            result = self.client.publish(topic, json.dumps(payload), qos=1)

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                self.logger.debug(f"Sent Reading: {reading['sensor_type']}.{reading['measurement_type']} = {reading['value']}")
                return True
            else:
                self.logger.error(f"Failed to publish message. Return code: {result.rc}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error sending reading: {e}")
            return False

    
    def _queue_if_offline(self, reading):
        if not self.connected:
            if self.offline_queue.qsize() < self.max_queue_size:
                self.offline_queue.put(reading)
                self.logger.info(f"Queued reading offlien. Queue size: {self.offline_queue.qsize()}")
                return True
            else:
                self.logger.warning("Offine queue full. Dropping oldest messages.")
                # Remove oldest message to make room
                try:
                    self.offline_queue.get_nowait()
                    self.offline_queue.put(reading)
                except:
                    pass
                return True
        return False

    def _process_offline_queue(self):
        self.logger.info(f"Processing {self.offline_queue.qsize()} queued messages")
        processed = 0

        while not self.offline_queue.empty() and self.connected:
            try:
                reading = self.offline_queue.get_nowait()
                if self._send_reading(reading):
                    processed += 1
                else:
                    # Put it back if sending failed
                    self.offline_queue.put(reading)
                    break
            except:
                break
        
        self.logger.info(f"Processed {processed} queued messages")

    
    def get_status(self):
        return {
            "connected": self.connected,
            "broker": f"{self.broker_host}:{self.broker_port}",
            "queue_size": self.offline_queue.qsize(),
            "device_id": self.device_id
        }
    