# Photogrammetry worker — COLMAP, FFmpeg, Blender, Python tools.
# OpenMVS is optional (not in Debian repos); set PIPELINE_MOCK=true without it.
# For GPU + OpenMVS production build, extend with CUDA base image later.
#
# Build: docker compose build worker
# CLI:   docker compose run --rm worker python3 scan.py --input /input --output /output --mock

FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIPELINE_DATA_DIR=/data/jobs

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    colmap \
    ffmpeg \
    blender \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/python3 /usr/bin/python

COPY requirements-photogrammetry.txt /app/
RUN pip3 install --no-cache-dir -r requirements-photogrammetry.txt

COPY app/ /app/app/
COPY scan.py /app/scan.py

RUN mkdir -p /data/jobs /input /output

VOLUME ["/data/jobs", "/input", "/output"]

CMD ["celery", "-A", "app.workers.celery_app", "worker", "-l", "info", "-Q", "celery", "--concurrency=1"]
