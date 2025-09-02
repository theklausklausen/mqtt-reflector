import asyncio
import json
import os

import aiomqtt
import jinja2
import yaml
from glom import glom
from logger import Logger

CONFIG_FILE = '/config/config.yaml'
RECONNECT_MAX = 5
RECONNECT_INTERVAL = 5

class Variable:
    def __init__(self, name, path):
        self.name = name
        self.path = path

class Topic:
    def __init__(self, topic):
        self.in_topic = topic['in']['topic']
        self.out_topic = topic['out']['topic']
        self.template = topic['out']['template'] or None
        self.variables = []
        for v in topic['in']['variables']:
            self.variables.append(Variable(v['name'], v['path']))

class MqttClient:
    def __init__(self):
        self.logger = Logger(__class__.__name__)
        self.host = os.getenv('MQTT_HOST', 'mqtt')
        self.port = int(os.getenv('MQTT_PORT', 1883))
        self.user = os.getenv('MQTT_USER', 'esp')
        self.password = os.getenv('MQTT_PASSWORD', 'esp')
        self.reconnect_ctr = 0
        self.reconnect_state = None
        self.topics = self.parse_config()
        self.client = None
    
    async def run(self):
        task = asyncio.get_event_loop().create_task(self.listen())
        await task
    
    def parse_config(self) -> [Topic]:
        topics = []
        with open(CONFIG_FILE, 'r') as file:
            config = yaml.safe_load(file)
            for topic in config['topics']:
                topics.append(Topic(topic))
        return topics
    
    async def listen(self):
        while self.reconnect_ctr < RECONNECT_MAX:
            try:
                async with aiomqtt.Client(
                    hostname=self.host,
                    port=self.port,
                    identifier='mqtt-reflector',
                    username=self.user,
                    password=self.password
                    ) as client:
                    self.client = client
                    if self.topics is None:
                        self.logger.error_message(f'{__name__}: listen: No topics defined')
                        return
                    for topic in self.topics:
                        self.logger.info_message(f'{__name__}: listen: Subscribing to {topic.in_topic}')
                        await self.client.subscribe(topic.in_topic)
                    self.reconnect_ctr = 0
                    async for message in self.client.messages:
                        topic = self.get_topic_by_in(str(message.topic))
                        if topic is not None:
                            await self.mirror_message(topic, message)
            except Exception as e:
                self.logger.error_message(f'{__name__}: listen: {str(e)}')
                self.reconnect_ctr += 1
                await asyncio.sleep(RECONNECT_INTERVAL)
    
    async def mirror_message(self, topic: Topic, message: aiomqtt.Message):
        self.logger.info_message(f'{__name__}: mirror_message: in {str(message.topic)} {message.payload}')
        vars = self.extract_variables(topic.variables, message.payload) if len(topic.variables) > 0 else {}
        payload = self.render_template(topic.template, vars) if topic.template is not None else message.payload
        self.logger.info_message(f'{__name__}: mirror_message: out {topic.out_topic} {payload}')
        await self.client.publish(topic.out_topic, payload)
    
    def get_topic_by_in(self, in_topic: str) -> Topic:
        for topic in self.topics:
            if topic.in_topic == in_topic:
                return topic
        return None
    
    def extract_variables(self, variables: [Variable], payload: bytes) -> dict:
        vars = {}
        payload = json.loads(payload)
        for variable in variables:
            vars[variable.name] = None
            try:
                vars[variable.name] = glom(payload, variable.path)
                
            except Exception as e:
                self.logger.error_message(f'{__name__}: extract_variables: {str(e)}')
        return vars
    
    def render_template(self, template: str, vars: dict) -> str:
        try:
            template = jinja2.Template(template)
            return template.render(**vars)
        except Exception as e:
            self.logger.error_message(f'{__name__}: render_template: {str(e)}')
            return template

async def run():
    client = MqttClient()
    await client.run()

if __name__ == '__main__':
    Logger('mqtt-reflector').info_message(f'{__name__}: Starting mqtt-reflector')
    asyncio.run(run())