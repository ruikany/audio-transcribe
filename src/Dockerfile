# Use the R36.3.0 base which is compatible with your R36.4.4 kernel
FROM --platform=linux/arm64 nvcr.io/nvidia/l4t-pytorch:r36.3.0-pth2.3-py3

# Set non-interactive
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies for audio and building
RUN apt-get update && apt-get install -y \
    portaudio19-dev \
    libportaudio2 \
    ffmpeg \
    gcc \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Point to CUDA libraries - critical for the "CTranslate2 CUDA" error
ENV LD_LIBRARY_PATH="/usr/local/cuda/lib64:${LD_LIBRARY_PATH}"

# Install faster-whisper and ctranslate2
# Using these versions ensures compatibility with JetPack 6 CUDA
RUN pip3 install --no-cache-dir faster-whisper==1.0.3 ctranslate2==4.4.0

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Pre-load Silero VAD
RUN python3 -c "import torch; torch.hub.load(repo_or_dir='snakers4/silero-vad', model='silero_vad', force_reload=True)"

COPY server.py .

ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
