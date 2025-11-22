FROM python:3.12.3-slim

# 'build-essential' and 'python3-dev' are required to compile C extensions
# 'portaudio19-dev' is required for the microphone/audio interface
#
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    libportaudio2 \
    portaudio19-dev \
    ffmpeg \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --upgrade pip setuptools wheel

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--ws", "websockets"]
