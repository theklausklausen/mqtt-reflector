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
    self.logger: Logger = Logger(__class__.__name__)
    self.source: str = topic['source']
    self.pattern: str = None
    self.replacement: str = None
    if 'replace' in topic and topic['replace'] is not None:
      self.pattern = topic['replace']['pattern'] if 'pattern' in topic['replace'] else None
      self.replacement = topic['replace']['replacement'] if 'replacement' in topic['replace'] else None
    self.template: str = topic['template'] if 'template' in topic else None
    self.variables: list[Variable] = []
    if 'variables' in topic and topic['variables'] is not None:
      for v in topic['variables']:
          self.variables.append(Variable(v['name'], v['path']))

  def get_destination_topic(self, source_topic: str) -> str:
    if self.pattern is not None and self.replacement is not None:
      self.logger.info_message(f'{__name__}: get_destination_topic: Transforming {source_topic} using pattern {self.pattern} and replacement {self.replacement}')
      return re.sub(self.pattern, self.replacement, source_topic)
    self.logger.info_message(f'{__name__}: get_destination_topic: No transformation for {source_topic}')
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
        self.logger.info_message(f'{__name__}: parse_topics: Added topic {topic["source"]}')
    return topics
    
  async def listen(self):
    self.logger.info_message(f'{__name__}: listen: host {self.host} port {self.port} user {self.user} identifier {self.identifier}')
    while self.reconnect_ctr < RECONNECT_MAX:
      try:
        async with aiomqtt.Client(
            hostname=self.host,
            port=self.port,
            identifier=self.identifier or f'mqtt-rtopicseflector-{str(random.randint(10_000_000, 99_999_999))}',
            username=self.user,
            password=self.password
            ) as client:
            self.client = client
            self.logger.info_message(f'{__name__}: listen: Connected to {app.source.host}:{app.source.port}')
            if self.topics is None:
              self.logger.error_message(f'{__name__}: listen: No topics defined')
              return
            for topic in self.topics:
              self.logger.info_message(f'{__name__}: listen: Subscribing to {topic.source}')
              await self.client.subscribe(topic.source)
              self.logger.info_message(f'{__name__}: listen: Subscribed to {topic.source}')
            self.reconnect_ctr = 0
            async for message in self.client.messages:
              topic = self.get_topic_by_in(str(message.topic))
              self.logger.info_message(f'{__name__}: listen: Received message on {app.source.host}:{app.source.port} topic {message.topic} payload {message.payload}')
              if topic is not None:
                await self.mirror_message(topic, message)
      except Exception as e:
        self.logger.error_message(f'{__name__}: listen: {str(e)}')
        self.reconnect_ctr += 1
        await asyncio.sleep(RECONNECT_INTERVAL)

  async def publish(self, topic: str, payload: str):
    self.logger.info_message(f'{__name__}: publish: host {self.host} port {self.port} user {self.user} identifier {self.identifier}')
    while self.reconnect_ctr < RECONNECT_MAX:
      try:
        self.logger.info_message(f'{__name__}: publish: Publishing to {app.destination.host}:{app.destination.port} topic {topic} payload {payload}')
        async with aiomqtt.Client(
            hostname=self.host,
            port=self.port,
            identifier=self.identifier,
            username=self.user,
            password=self.password
        ) as client:
          self.client = client
          await self.client.publish(topic, payload)
        return
      except Exception as e:
        self.logger.error_message(f'{__name__}: publish: {str(e)}')
        self.reconnect_ctr += 1
        await asyncio.sleep(RECONNECT_INTERVAL)

  async def mirror_message(self, topic: Topic, message: aiomqtt.Message):
    self.logger.info_message(f'{__name__}: mirror_message: in {str(message.topic)} {message.payload}')
    self.logger.info_message(f'{__name__}: mirror_message: variables: {topic.variables}')
    vars = self.extract_variables(topic.variables, message.payload) if len(topic.variables) > 0 else {}
    payload = self.render_template(topic.template, vars) if topic.template is not None else message.payload
    destination_topic = topic.get_destination_topic(message.topic.value)
    self.logger.info_message(f'{__name__}: mirror_message: out {destination_topic} {payload}')
    await app.destination.publish(destination_topic, payload)

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

    self.validate_broker(config['broker']['source'])
    config['broker']['source']['password'] = self.get_password(config['broker']['source'])
    if config['broker']['source']['identifier'] is None:
      config['broker']['source']['identifier'] = f'{config["name"]}-source'

    if 'destination' not in config['broker']:
      self.logger.info_message('No destination broker defined, using source broker settings')
      config['broker']['destination'] = config['broker']['source']
      config['broker']['destination']['identifier'] = f'{config["name"]}-destination'
    else:
      self.validate_broker(config['broker']['destination'])
      config['broker']['destination']['password'] = self.get_password(config['broker']['destination'])
    if config['broker']['destination']['identifier'] is None:
      config['broker']['destination']['identifier'] = f'{config["name"]}-destination'

    return config['broker']

  def validate_broker(self, broker: dict) -> bool:
    required_keys = ['host', 'port', 'username']
    for key in required_keys:
      if key not in broker or broker[key] is None:
        self.logger.error_message(f'{__name__}: validate_broker: Missing required key {key} in broker configuration')
        return False
    if 'passwordEnv' not in broker and ('passwordSecret' not in broker or 'passwordKey' not in broker):
      self.logger.error_message(f'{__name__}: validate_broker: No password source defined for broker {broker["identifier"]}')
      return False
    return True

  def get_password_from_env(self, env_var: str, host: str) -> str:
    self.logger.info_message(f'Fetching Environment Password from {env_var} for {host}')
    return os.getenv(env_var)

  def get_password_from_k8s_secret(self, secret_name: str, key: str, host: str) -> str:
    self.logger.info_message(f'Fetching Kubernetes Password from secret {secret_name} key {key} for {host}')
    from kubernetes import client, config as k8s_config
    try:
      k8s_config.load_incluster_config()
    except:
      k8s_config.load_kube_config()
    v1 = client.CoreV1Api()
    namespace = self.get_current_namespace()
    secret = v1.read_namespaced_secret(secret_name, namespace)
    if key in secret.data:
      import base64
      return base64.b64decode(secret.data[key]).decode('utf-8')
    else:
      self.logger.error_message(f'{__name__}: get_password_from_k8s_secret: Key {key} not found in secret {secret_name}')
      raise ValueError(f'Key {key} not found in secret {secret_name}')

  def get_current_namespace(self) -> str:
    try:
        with open("/var/run/secrets/kubernetes.io/serviceaccount/namespace", "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return "default"

  def get_password(self, broker: dict) -> str:
    if 'passwordEnv' in broker and broker['passwordEnv'] is not None and broker['passwordEnv'] != '':
      if broker['passwordEnv'] is not None:
        return self.get_password_from_env(broker['passwordEnv'], broker['host'])
    elif 'passwordSecret' in broker and 'passwordKey' in broker:
      if broker['passwordSecret'] is not None and broker['passwordKey'] is not None:
        return self.get_password_from_k8s_secret(broker['passwordSecret'], broker['passwordKey'], broker['host'])
    else:
      self.logger.error_message(f'{__name__}: get_password: No password source defined for broker {broker["identifier"]}')
      raise ValueError("No password source defined for broker")

async def run():
  global app
  app = App()
  await app.source.run()

if __name__ == '__main__':
  Logger('mqtt-reflector').info_message(f'{__name__}: Starting mqtt-reflector')

  asyncio.run(run())