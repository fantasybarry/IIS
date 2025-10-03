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
    
    