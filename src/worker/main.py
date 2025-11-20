from fastapi import FastAPI, UploadFile, File
from faster_whisper import WhisperModel
import numpy as np
import logging

app = FastAPI()
logging.basicConfig(level=logging.INFO)
print("Loading Large Model...")
model = WhisperModel("large-v2", device="cuda", compute_type="int8_float16")
print("Model Loaded.")

@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    # Read raw PCM bytes (we assume Gateway sent 16k s16le PCM)
    audio_bytes = await file.read()
    
    # Convert bytes to float32 array (required by faster-whisper)
    audio_np = np.frombuffer(audio_bytes, dtype=np.int16).flatten().astype(np.float32) / 32768.0
    
    # Run Inference
    segments, info = model.transcribe(audio_np, beam_size=5)
    
    text = " ".join([segment.text for segment in segments])
    logging.info(f"Transcribed: {text}")
    
    return {"text": text.strip()}
