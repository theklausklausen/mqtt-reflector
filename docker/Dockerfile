ARG BASE_IMG=repo.kk.int/infra-images/python-base:latest
FROM ${BASE_IMG} AS development
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ARG USER=bot
RUN mkdir -p /app/src
WORKDIR /app
COPY docker/requirements.txt /app/
COPY src/* /app/src/
COPY config/config.yaml /config/config.yaml
RUN pip install --upgrade pip && \
    pip install -r /app/requirements.txt && \
    pip install debugpy
USER $USER
CMD [ "python3", "-m", "debugpy", "--listen", "0.0.0.0:9229", "/app/src/mqtt-reflector.py"]

FROM ${BASE_IMG} AS production
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ARG USER=bot
RUN mkdir -p /app/src
WORKDIR /app
COPY docker/requirements.txt /app/
COPY src/* /app/src/
RUN pip install --upgrade pip && \
    pip install -r requirements.txt
# USER $USER
CMD [ "python3", "/app/src/mqtt-reflector.py"]