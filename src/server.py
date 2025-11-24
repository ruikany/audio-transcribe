import asyncio
import logging
import json
import threading
import numpy as np
from scipy.signal import resample
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from RealtimeSTT import AudioToTextRecorder

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("stt-server")
app = FastAPI(title="Realtime STT API")

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
    'model': 'large-v2',
    'language': 'en',
    'silero_sensitivity': 0.4,
    'webrtc_sensitivity': 2,
    'post_speech_silence_duration': 0.7,
    'min_length_of_recording': 0,
    'min_gap_between_recordings': 0,
    'enable_realtime_transcription': True,
    'realtime_processing_pause': 0,
    'realtime_model_type': 'tiny.en',
}

TARGET_SAMPLE_RATE = 16000

class STTManager:
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.loop = asyncio.get_running_loop()
        self.recorder = None
        self.is_running = False
        self.transcription_thread = None

    def _text_detected(self, text):
        asyncio.run_coroutine_threadsafe(
            self.websocket.send_json({'type': 'realtime', 'text': text}),
            self.loop
        )

    def _full_sentence_detected(self, text):
        asyncio.run_coroutine_threadsafe(
            self.websocket.send_json({'type': 'fullSentence', 'text': text}),
            self.loop
        )

    def _transcription_loop(self):
        logger.info("Transcription loop started.")
        while self.is_running and self.recorder:
            try:
                text = self.recorder.text()
                if text:
                    logger.info(f"Sentence detected: {text}")
                    self._full_sentence_detected(text)
            except Exception as e:
                logger.error(f"Error in transcription loop: {e}")
                break
        logger.info("Transcription loop stopped.")

    async def start(self):
        config = RECORDER_CONFIG.copy()
        config['on_realtime_transcription_stabilized'] = self._text_detected
        
        logger.info("Loading model...")
        self.recorder = AudioToTextRecorder(**config)
        logger.info("Model loaded.")

        # start polling thread
        self.is_running = True
        self.transcription_thread = threading.Thread(target=self._transcription_loop, daemon=True)
        self.transcription_thread.start()

    def process_audio(self, audio_data, sample_rate):
        """Resample and feed audio to recorder"""
        if not self.recorder:
            return

        try:
            audio_np = np.frombuffer(audio_data, dtype=np.int16)
            if sample_rate != TARGET_SAMPLE_RATE:
                num_samples = int(len(audio_np) * TARGET_SAMPLE_RATE / sample_rate)
                resampled = resample(audio_np, num_samples)
                final_audio = resampled.astype(np.int16).tobytes()
            else:
                final_audio = audio_data
            self.recorder.feed_audio(final_audio)
        except Exception as e:
            logger.error(f"Processing error: {e}")

    def shutdown(self):
        self.is_running = False
        if self.recorder:
            self.recorder.shutdown()
            self.recorder = None
        if self.transcription_thread:
            self.transcription_thread.join(timeout=2.0)


@app.websocket("/ws/transcribe")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("Client connected")
    
    manager = STTManager(websocket)
    
    try:
        await manager.start()
        await websocket.send_json({'type': 'status', 'text': 'ready'})
        
        while True:
            # Receive raw binary message
            message = await websocket.receive_bytes()
            
            # --- PARSE PROTOCOL ---
            metadata_length = int.from_bytes(message[:4], byteorder='little')
            metadata_json = message[4:4+metadata_length].decode('utf-8')
            metadata = json.loads(metadata_json)
            sample_rate = metadata.get('sampleRate', 44100)
            chunk = message[4+metadata_length:]
            
            # Process in thread to avoid blocking event loop
            await asyncio.to_thread(manager.process_audio, chunk, sample_rate)

    except WebSocketDisconnect:
        logger.info("Client disconnected")
    except Exception as e:
        logger.error(f"Connection error: {e}")
    finally:
        manager.shutdown()
