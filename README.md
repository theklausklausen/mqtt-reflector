# MQTT Reflector

> [!WARNING]  
> I wasn’t aware of the [Mosquitto MQTT bridge capabilities](http://www.steves-internet-guide.com/mosquitto-bridge-configuration/), which makes parts of this approach somewhat obsolete.  
> However, this method can still be useful in cases where:
> 1. One or both MQTT servers cannot connect outside their network.  
> 2. Topic or payload transformation is required.


MQTT Reflector is a Python-based service for mirroring and transforming MQTT messages between brokers. It is designed for flexible deployment in Kubernetes via Helm and supports dynamic topic mapping and payload templating.

## Features

- Mirror messages between source and destination MQTT brokers
- Topic transformation using regex patterns
- Payload transformation using Jinja2 templates and variable extraction
- Kubernetes-native configuration with support for secrets and environment variables
- Helm chart for easy deployment and configuration
- Docker support for local development and production

## Project Structure

```bash
.
├── config/ # Configuration files (YAML) 
├── docker/ # Docker and Compose files 
├── helm/ # Helm chart for Kubernetes deployment 
├── src/ # Python source code 
│  ├── mqtt-reflector.py # Main application logic 
│  ├── logger.py # Logging utility  
│  └── tests/ # Unit tests 
├── workspace.env # Encrypted environment variables 
├── Makefile # Common development commands 
└── README.md # This file
```

## Getting Started

### Prerequisites

- Python 3.9+
- Docker & Docker Compose
- (Optional) Kubernetes cluster & Helm

### Configuration

Edit [`config/config.yaml`](config/config.yaml) to define brokers and topic mappings. Secrets and passwords can be provided via environment variables or Kubernetes secrets.

Example broker config:

```yaml
broker:
  source:
    host: src-mqtt
    port: 1883
    username: mqtt
    passwordEnv: MQTT-SRC
    identifier: mqtt-reflector
  destination:
    host: dst-mqtt
    port: 1883
    username: mqtt
    passwordEnv: MQTT-DST
    identifier: mqtt-reflector
```  

### Local Development

1. Build and start services:

```bash
make up-build
```

2. (TODO:) The reflector will run in a container, connecting to local MQTT brokers.
Running Tests
Unit tests are located in `src/tests/unittest.py`:

```bash
python3 -m unittest 
```

Kubernetes Deployment

1. Package and deploy with Helm:

```bash
helm install mqtt-reflector ./helm/mqtt-reflector
```

2. Customize values in helm/mqtt-reflector/values.yaml as needed.

### Usage

- Install Helm chart `helm repo add mqtt-reflector https://theklausklausen.github.io/mqtt-reflector/`
- The service subscribes to configured source topics, transforms topics and payloads as specified, and republishes to destination topics.
- Topic and payload transformation is defined in the config file using regex and Jinja2 templates.

### Environment Variables

Sensitive values (e.g., passwords) should be provided via environment variables or Kubernetes secrets. See workspace.env for an example (encrypted).

### Development Commands

make up — Start services
make down — Stop services
make lint — Run code and YAML linter
make helm_render — Render Helm templates

## License

MIT License
