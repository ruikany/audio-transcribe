import asyncio
import json
import logging
import torch
import gc
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from RealtimeSTT import AudioToTextRecorder

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("stt-server")

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

RECORDER_CONFIG = {
    'spinner': False,
    'use_microphone': False,
    'model': 'medium.en',
    'language': 'en',
    'compute_type': 'int8',
    'silero_sensitivity': 0.6,
    'webrtc_sensitivity': 3,
    'post_speech_silence_duration': 0.7,
    'min_length_of_recording': 0.2,
    'min_gap_between_recordings': 0,
    
    'enable_realtime_transcription': False, 
}

class TranscriptionSession:
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.loop = asyncio.get_running_loop()
        self.recorder = None

    async def initialize(self):
        if torch.cuda.is_available():
            vram = torch.cuda.get_device_properties(0).total_memory / 1024**3
            logger.info(f"✅ CUDA: {torch.cuda.get_device_name(0)} ({vram:.2f} GB)")
        
        self.recorder = await asyncio.to_thread(self._create_recorder)

    def _create_recorder(self):
        return AudioToTextRecorder(**RECORDER_CONFIG)

    async def process_packet(self, data):
        if not self.recorder: return
        try:
            metadata_length = int.from_bytes(data[:4], byteorder='little')
            chunk_bytes = data[4+metadata_length:]
            
            self.recorder.feed_audio(chunk_bytes)
            
            full_text = self.recorder.text()
            if full_text:
                await self.websocket.send_json({'type': 'fullSentence', 'text': full_text})
                
        except Exception as e:
            logger.error(f"Error: {e}")

    async def close(self):
        if self.recorder:
            self.recorder.shutdown()
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

@app.websocket("/ws/transcribe")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    session = TranscriptionSession(websocket)
    await session.initialize()
    await websocket.send_json({'type': 'status', 'text': 'ready'})
    try:
        while True:
            data = await websocket.receive_bytes()
            await session.process_packet(data)
    except WebSocketDisconnect:
        logger.info("Client disconnected")
    finally:
        await session.close()
