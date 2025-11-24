import asyncio
import json
import logging
import numpy as np
import audioop
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from RealtimeSTT import AudioToTextRecorder
import aiohttp
import gc

app = FastAPI()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gateway")

# --- CORS ---
origins = [
    "https://frontend-test-zeta-eight.vercel.app",
    "http://localhost:3000"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CONFIGURATION ---
RECORDER_CONFIG = {
    'spinner': False,
    'use_microphone': False,
    'model': 'tiny.en',
    'realtime_model_type': 'tiny.en',
    'language': 'en',
    'compute_type': 'int8',
    'silero_sensitivity': 0.6,
    'webrtc_sensitivity': 3,
    'post_speech_silence_duration': 0.7,
    'min_length_of_recording': 0.2,
    'min_gap_between_recordings': 0,
    'enable_realtime_transcription': True,
    'realtime_processing_pause': 0.1, 
    
    # 2. Increase batch size slightly to process more audio per run
    'realtime_batch_size': 4,
    
    # 3. Reduce beam size for realtime (Tiny doesn't need 5 beams, 1 is faster)
    'beam_size_realtime': 1,
}

class Session:
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.loop = asyncio.get_running_loop()
        self.audio_buffer = bytearray()
        self.http_client = aiohttp.ClientSession()
        self.resample_state = None 
        self.recorder = None

    async def initialize(self):
        """Async initialization to avoid blocking the websocket accept"""
        print("Initializing Recorder...", flush=True)
        # Run blocking init in a separate thread to keep the websocket alive
        self.recorder = await asyncio.to_thread(self._create_recorder)
        print("Recorder Ready!", flush=True)
        # Tell the frontend we are actually ready
        await self.websocket.send_json({'type': 'status', 'text': 'ready'})

    def _create_recorder(self):
        return AudioToTextRecorder(
            **RECORDER_CONFIG,
            on_realtime_transcription_stabilized=self._on_realtime,
            on_recording_start=self._on_recording_start,
            on_recording_stop=self._on_sentence_end
        )

    def _on_recording_start(self):
        print(">> VAD STARTED", flush=True)

    def _on_realtime(self, text):
        asyncio.run_coroutine_threadsafe(
            self.websocket.send_json({'type': 'realtime', 'text': text}),
            self.loop
        )

    def _on_sentence_end(self):
        print("<< VAD STOPPED", flush=True)
        asyncio.run_coroutine_threadsafe(self._process_full_sentence(), self.loop)

    async def _process_full_sentence(self):
        if len(self.audio_buffer) == 0: return
        
        data_to_send = self.audio_buffer[:]
        self.audio_buffer = bytearray()

        try:
            form_data = aiohttp.FormData()
            form_data.add_field('file', data_to_send, filename='audio.pcm', content_type='application/octet-stream')
            
            print("Sending to Worker...", flush=True)
            async with self.http_client.post("http://worker:8000/transcribe", data=form_data) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    print(f"Worker: {result['text']}", flush=True)
                    await self.websocket.send_json({'type': 'fullSentence', 'text': result['text']})
                else:
                    logger.error(f"Worker failed: {resp.status}")
        except Exception as e:
            logger.error(f"Worker Connection Error: {e}")

    async def process_packet(self, data):
        if not self.recorder: return # Ignore packets if recorder isn't ready yet

        try:
            metadata_length = int.from_bytes(data[:4], byteorder='little')
            metadata_json = data[4:4+metadata_length].decode('utf-8')
            metadata = json.loads(metadata_json)
            chunk_bytes = data[4+metadata_length:]
            
            current_rate = metadata['sampleRate']
            target_rate = 16000
            
            if current_rate != target_rate:
                resampled_chunk, self.resample_state = audioop.ratecv(
                    chunk_bytes, 2, 1, current_rate, target_rate, self.resample_state
                )
            else:
                resampled_chunk = chunk_bytes

            # DEBUG LOGGING
            rms = audioop.rms(resampled_chunk, 2)
            if rms > 500: print("#", end="", flush=True)
            else: print(".", end="", flush=True)

            self.recorder.feed_audio(resampled_chunk)
            self.audio_buffer.extend(resampled_chunk)
            
        except Exception as e:
            logger.error(f"Packet Error: {e}")

    async def close(self):
        print("\nClosing Session", flush=True)
        if self.recorder:
            self.recorder.shutdown()
        if self.http_client:
            await self.http_client.close()
        gc.collect()

@app.websocket("/ws/transcribe")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    session = Session(websocket)
    
    # Initialize the heavy model
    await session.initialize()
    
    try:
        while True:
            data = await websocket.receive_bytes()
            await session.process_packet(data)
    except WebSocketDisconnect:
        pass
    finally:
        await session.close()
