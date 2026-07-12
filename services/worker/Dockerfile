# Photogrammetry worker — COLMAP, FFmpeg, Blender, OpenMVS, Python tools.
# Ubuntu 24.04 ships much newer apt packages than 22.04; OpenMVS comes from upstream binaries.
#
# Build: docker compose build worker
# CLI:   docker compose run --rm worker python3 scan.py --input /input --output /output

FROM ubuntu:24.04

ARG OPENMVS_VERSION=2.4.0

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIPELINE_DATA_DIR=/data/jobs \
    QT_QPA_PLATFORM=offscreen \
    PATH="/opt/openmvs:${PATH}"

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    wget \
    unzip \
    ca-certificates \
    colmap \
    ffmpeg \
    blender \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/python3 /usr/bin/python

RUN wget -q "https://github.com/cdcseacave/openMVS/releases/download/v${OPENMVS_VERSION}/OpenMVS_Ubuntu_x64.zip" -O /tmp/openmvs.zip \
    && mkdir -p /opt/openmvs \
    && unzip -q /tmp/openmvs.zip -d /opt/openmvs \
    && rm /tmp/openmvs.zip \
    && chmod +x /opt/openmvs/*

COPY requirements-photogrammetry.txt /app/
RUN pip3 install --no-cache-dir --break-system-packages -r requirements-photogrammetry.txt

COPY app/ /app/app/
COPY scan.py /app/scan.py
COPY services/worker/image-versions.json /etc/image-versions.json

RUN mkdir -p /data/jobs /input /output

VOLUME ["/data/jobs", "/input", "/output"]

CMD ["celery", "-A", "app.workers.celery_app", "worker", "-l", "info", "-Q", "celery", "--concurrency=1"]
