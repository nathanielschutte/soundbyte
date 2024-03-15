FROM python:3.9.1-slim-buster as soundbyte

RUN apt-get update && apt-get install -y \
    ffmpeg

RUN mkdir -p /var/log/soundbyte

COPY requirements /app/requirements
RUN pip install -r /app/requirements/requirements.txt

COPY *.py /app/
COPY soundbyte.json /app/soundbyte.json
COPY .env /app/.env
COPY config.ini /app/config.ini
COPY docker/docker-entrypoint.sh /app/docker-entrypoint.sh

WORKDIR /app

ENTRYPOINT [ "sh", "docker-entrypoint.sh" ]