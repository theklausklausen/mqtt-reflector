import asyncio
import json
import os

import aiomqtt
import jinja2
import yaml
from glom import glom
from logger import Logger
import re
import random
# kubernetes api client


CONFIG_FILE = '/config/config.yaml'
RECONNECT_MAX = 5
RECONNECT_INTERVAL = 5

config = None
app = None

class Variable:
  def __init__(self, name, path):
    self.name = name
    self.path = path

class Topic:
  def __init__(self, topic):
    self.source = topic['source']
    # self.destination = topic['source']
    self.pattern = topic['replace']['pattern'] or None
    self.replacement = topic['replace']['replacement'] or None
    # if topic['replace'] is not None:
    #   self.destination = re.sub(topic['replace']['search'], topic['replace']['replacement'], self.source)
    self.template = topic['template'] or None
    self.variables = []
    for v in topic['variables']:
        self.variables.append(Variable(v['name'], v['path']))

  def get_destination_topic(self, source_topic: str) -> str:
    if self.pattern is not None and self.replacement is not None:
      return re.sub(self.pattern, self.replacement, source_topic)
    return self.source

class MqttClient:
  def __init__(self, host, port, user, password, identifier):
    self.logger = Logger(__class__.__name__)
    self.host = host
    self.port = port
    self.user = user
    self.password = password
    self.identifier = identifier
    self.reconnect_ctr = 0
    self.reconnect_state = None
    self.topics = self.parse_topics()
    # self.client = None
    
  async def run(self):
    task = asyncio.get_event_loop().create_task(self.listen())
    await task
    
  def parse_topics(self) -> list[Topic]:
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
            identifier=self.identifier or f'mqtt-reflector-{str(random.randint(10_000_000, 99_999_999))}',
            username=self.user,
            password=self.password
            ) as client:
            self.client = client
            if self.topics is None:
              self.logger.error_message(f'{__name__}: listen: No topics defined')
              return
            for topic in self.topics:
              self.logger.info_message(f'{__name__}: listen: Subscribing to {topic.source}')
              await self.client.subscribe(topic.source)
            self.reconnect_ctr = 0
            async for message in self.client.messages:
              topic = self.get_topic_by_in(str(message.topic))
              if topic is not None:
                await self.mirror_message(topic, message)
      except Exception as e:
        self.logger.error_message(f'{__name__}: listen: {str(e)}')
        self.reconnect_ctr += 1
        await asyncio.sleep(RECONNECT_INTERVAL)

  async def publish(self, topic: str, payload: str):
    while self.reconnect_ctr < RECONNECT_MAX:
      try:
        async with aiomqtt.Client(
            hostname=self.host,
            port=self.port,
            identifier=self.identifier,
            username=self.user,
            password=self.password
        ) as client:
          self.client = client
          await self.client.publish(topic, payload)
      except Exception as e:
        self.logger.error_message(f'{__name__}: publish: {str(e)}')
        self.reconnect_ctr += 1
        await asyncio.sleep(RECONNECT_INTERVAL)

  async def mirror_message(self, topic: Topic, message: aiomqtt.Message):
    self.logger.info_message(f'{__name__}: mirror_message: in {app.source.host}{str(message.topic)} {message.payload}')
    vars = self.extract_variables(topic.variables, message.payload) if len(topic.variables) > 0 else {}
    payload = self.render_template(topic.template, vars) if topic.template is not None else message.payload
    self.logger.info_message(f'{__name__}: mirror_message: out {topic.destination} {payload}')
    destination_topic = topic.get_destination_topic(message.topic)
    await self.client.publish(destination_topic, payload)

  def get_topic_by_in(self, source: str) -> Topic:
    for topic in self.topics:
      if topic.source == source:
        return topic
    return None
    
  def extract_variables(self, variables: list[Variable], payload: bytes) -> dict:
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

class App:
  def __init__(self):
    self.logger = Logger(__class__.__name__)
    self.broker = self.parse_broker()
    self.source = MqttClient(
      host=self.broker['source']['host'],
      port=self.broker['source']['port'],
      user=self.broker['source']['username'],
      password=self.broker['source']['password'],
      identifier=self.broker['source']['identifier']
    )
    self.destination = MqttClient(
      host=self.broker['destination']['host'],
      port=self.broker['destination']['port'],
      user=self.broker['destination']['username'],
      password=self.broker['destination']['password'],
      identifier=self.broker['destination']['identifier']
    )

  def parse_broker(self) -> dict:
    with open(CONFIG_FILE, 'r') as file:
      config = yaml.safe_load(file)

    if config['broker']['source']['passwordEnv'] is not None:
      self.logger.info_message(f'Fetching Environment Password for {config["broker"]["source"]["identifier"]} from {config["broker"]["source"]["passwordEnv"]}')
      config['broker']['source']['password'] = os.getenv(config['broker']['source']['passwordEnv'])
    elif config['broker']['source']['passwordSecret'] is not None and config['broker']['source']['passwordKey'] is not None:
      self.logger.info_message("Fetching Kubernetes Password")
    else:
      self.logger.error_message(f'{__name__}: parse_broker: No password source defined for source broker')
      raise ValueError("No password source defined for source broker")
    if config['broker']['identifier'] is None:
      config['broker']['identifier'] = f'{config["name"]}-source'

    if config['broker']['destination'] is None:
      config['broker']['destination'] = config['broker']['source']
      config['broker']['destination']['identifier'] = f'{config["name"]}-destination'
    else:
      if config['broker']['destination']['passwordEnv'] is not None:
        self.logger.info_message(f'Fetching Environment Password for {config["broker"]["destination"]["identifier"]} from {config["broker"]["destination"]["passwordEnv"]}')
        config['broker']['destination']['password'] = os.getenv(config['broker']['destination']['passwordEnv'])
      elif config['broker']['destination']['passwordSecret'] is not None and config['broker']['destination']['passwordKey'] is not None:
        self.logger.info_message("Fetching Kubernetes Password")
      else:
        self.logger.error_message(f'{__name__}: parse_broker: No password source defined for destination broker')
        raise ValueError("No password source defined for destination broker")
    if config['broker']['destination']['identifier'] is None:
      config['broker']['destination']['identifier'] = f'{config["name"]}-destination'

    return config['broker']


async def run():
    app = App()
    await app.source.run()

if __name__ == '__main__':
  Logger('mqtt-reflector').info_message(f'{__name__}: Starting mqtt-reflector')

  asyncio.run(run())