import unittest
from unittest.mock import MagicMock, patch
import sys
from mqtt_reflector import MQTTReflector

# Assuming the main mqtt reflector logic is in mqtt_reflector.py
# and contains a class MQTTReflector with methods: connect, on_message, start, stop

sys.modules['paho'] = MagicMock()  # Mock paho if not installed

with patch.dict('sys.modules', {'paho.mqtt.client': MagicMock()}):

class TestMQTTReflector(unittest.TestCase):
  def setUp(self):
    self.reflector = MQTTReflector('broker.hivemq.com', 1883, 'source/topic', 'target/topic')

  def test_connect_success(self):
    self.reflector.client.connect = MagicMock(return_value=0)
    result = self.reflector.connect()
    self.assertTrue(result)
    self.reflector.client.connect.assert_called_once_with('broker.hivemq.com', 1883, 60)

  def test_connect_failure(self):
    self.reflector.client.connect = MagicMock(side_effect=Exception("Connection failed"))
    result = self.reflector.connect()
    self.assertFalse(result)

  def test_on_message_reflects_payload(self):
    mock_msg = MagicMock()
    mock_msg.payload = b'test message'
    mock_msg.topic = 'source/topic'
    self.reflector.client.publish = MagicMock()
    self.reflector.on_message(None, None, mock_msg)
    self.reflector.client.publish.assert_called_once_with('target/topic', b'test message')

  def test_start_calls_loop_forever(self):
    self.reflector.client.loop_forever = MagicMock()
    self.reflector.start()
    self.reflector.client.loop_forever.assert_called_once()

  def test_stop_disconnects_client(self):
    self.reflector.client.disconnect = MagicMock()
    self.reflector.stop()
    self.reflector.client.disconnect.assert_called_once()

if __name__ == '__main__':
  unittest.main()