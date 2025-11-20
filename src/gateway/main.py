import asyncio
import json
import logging
import numpy as np
from scipy.signal import resample
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from RealtimeSTT import AudioToTextRecorder
import aiohttp


app = FastAPI()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gateway")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://frontend-test-zeta-eight.vercel.app/"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

RECORDER_CONFIG = {
    'spinner': False,
    'use_microphone': False,
    'model': 'tiny.en',
    'realtime_model_type': 'tiny.en',
    'language': 'en',
    'silero_sensitivity': 0.4,
    'webrtc_sensitivity': 2,
    'post_speech_silence_duration': 0.7,
    'min_length_of_recording': 0,
    'min_gap_between_recordings': 0,
    'enable_realtime_transcription': True,
}

# Helper function from your original code
def decode_and_resample(audio_data, original_sample_rate, target_sample_rate):
    try:
        audio_np = np.frombuffer(audio_data, dtype=np.int16)
        num_target_samples = int(len(audio_np) * target_sample_rate / original_sample_rate)
        resampled_audio = resample(audio_np, num_target_samples)
        return resampled_audio.astype(np.int16).tobytes()
    except Exception as e:
        return audio_data

class Session:
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.loop = asyncio.get_running_loop()
        self.audio_buffer = bytearray() # We keep our own buffer to send to worker
        self.http_client = aiohttp.ClientSession()
        
        self.recorder = AudioToTextRecorder(
            **RECORDER_CONFIG,
            on_realtime_transcription_stabilized=self._on_realtime,
            on_recording_stop=self._on_sentence_end # <--- Trigger when user stops talking
        )

    def _on_realtime(self, text):
        """Sends the yellow/fast text"""
        asyncio.run_coroutine_threadsafe(
            self.websocket.send_json({'type': 'realtime', 'text': text}),
            self.loop
        )

    def _on_sentence_end(self):
        """VAD detected silence. Offload the buffer to the Worker."""
        # We run this in a background task so we don't block the audio feed
        asyncio.run_coroutine_threadsafe(self._process_full_sentence(), self.loop)


    async def _process_full_sentence(self):
        if len(self.audio_buffer) == 0: return
        data_to_send = self.audio_buffer[:]
        self.audio_buffer = bytearray()

        try:
            form_data = aiohttp.FormData()
            form_data.add_field('file', data_to_send, filename='audio.pcm', content_type='application/octet-stream')
            
            # ASSUMING DOCKER HAS INTERNAL LOAD BALANCE, WILL TEST
            async with self.http_client.post("http://worker:8000/transcribe", data=form_data) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    await self.websocket.send_json({'type': 'fullSentence', 'text': result['text']})
        except Exception as e:
            logger.error(f"Worker Error: {e}")


    async def process_packet(self, data):
        # Your binary unpacking logic
        try:
            metadata_length = int.from_bytes(data[:4], byteorder='little')
            metadata_json = data[4:4+metadata_length].decode('utf-8')
            metadata = json.loads(metadata_json)
            chunk = data[4+metadata_length:]
            
            # Resample to 16k
            resampled = decode_and_resample(chunk, metadata['sampleRate'], 16000)
            
            # 1. Feed to RealtimeSTT (for VAD + Tiny model)
            self.recorder.feed_audio(resampled)
            
            # 2. Append to our buffer (for the Worker)
            self.audio_buffer.extend(resampled)
        except Exception as e:
            logger.error(f"Packet Error: {e}")

    async def close(self):
        self.recorder.shutdown()
        await self.http_client.close()

@app.websocket("/ws/transcribe")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    session = Session(websocket)
    try:
        while True:
            data = await websocket.receive_bytes()
            await session.process_packet(data)
    except WebSocketDisconnect:
        print("Client disconnected")
    finally:
        await session.close()
