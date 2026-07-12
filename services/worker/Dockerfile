# Photogrammetry worker — COLMAP, OpenMVS, FFmpeg, Blender, Python tools
# Build: docker build -f services/worker/Dockerfile -t photogrammetry-worker .

FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIPELINE_DATA_DIR=/data/jobs

WORKDIR /app

# System dependencies + COLMAP (Ubuntu package) + FFmpeg + Blender
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    colmap \
    ffmpeg \
    blender \
    libgl1 \
    libglib2.0-0 \
    git \
    cmake \
    build-essential \
    libboost-all-dev \
    libeigen3-dev \
    libopencv-dev \
    libcgal-dev \
    && rm -rf /var/lib/apt/lists/*

# OpenMVS — build from source (takes time; cached in image layer)
RUN git clone --depth 1 https://github.com/cdcseacave/openMVS.git /tmp/openMVS \
    && cd /tmp/openMVS \
    && mkdir build && cd build \
    && cmake .. -DOpenMVS_USE_CUDA=ON \
    && make -j"$(nproc)" \
    && make install \
    && rm -rf /tmp/openMVS

COPY requirements-photogrammetry.txt /app/
RUN pip3 install --no-cache-dir -r requirements-photogrammetry.txt

COPY app/ /app/app/
COPY scan.py /app/scan.py

RUN mkdir -p /data/jobs /input /output

VOLUME ["/data/jobs", "/input", "/output"]

# CLI: docker run --gpus all -v ./samples:/input -v ./results:/output photogrammetry-worker \
#        python3 scan.py --input /input --output /output
CMD ["python3", "scan.py", "--input", "/input", "--output", "/output"]
