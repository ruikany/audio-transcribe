import asyncio
import logging
import json
import threading
import queue
import numpy as np
from scipy import signal
import webrtcvad
import time
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from faster_whisper import WhisperModel

# --- CONFIGURATION ---
FAST_MODEL_NAME = "tiny.en" 
ACCURATE_MODEL_NAME = "large-v2" 
TARGET_SAMPLE_RATE = 16000
PREVIEW_INTERVAL_MS = 500

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("stt-server")

app = FastAPI()

fast_queue = queue.Queue()
accurate_queue = queue.Queue()

class Scheduler:
    def schedule_fast(self, audio, ws, is_final=False):
        fast_queue.put((audio, ws, False))
        
    def schedule_accurate(self, audio, ws, is_final=True):
        accurate_queue.put((audio, ws, True))

scheduler = Scheduler()


class GPUWorker:
    def __init__(self, model_name, queue_source):
        self.q = queue_source
        self.model_name = model_name
        self.model = None
        self.running = True
        self.main_loop = None
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def set_loop(self, loop):
        self.main_loop = loop

    def _loop(self):
        self.model = WhisperModel(self.model_name, device="cuda", compute_type="int8")
        logger.info(f"{self.model_name} Ready.")
        
        while self.running:
            try:
                job = self.q.get(timeout=1.0)
            except queue.Empty:
                continue

            audio_data, websocket, is_final = job
            
            try:
                segments, _ = self.model.transcribe(
                    audio_data, beam_size=1, language="en", vad_filter=False
                )
                text = " ".join([s.text for s in segments]).strip()

                if text and self.main_loop:
                    msg_type = "fullSentence" if is_final else "realtime"
                    asyncio.run_coroutine_threadsafe(
                        websocket.send_json({"type": msg_type, "text": text}),
                        self.main_loop
                    )
            except Exception as e:
                logger.error(f"Worker Error: {e}")
            finally:
                self.q.task_done()

fast_workers = [GPUWorker(FAST_MODEL_NAME, fast_queue) for _ in range(3)]
accurate_worker = GPUWorker(ACCURATE_MODEL_NAME, accurate_queue)

class SessionHandler:
    def __init__(self, websocket):
        self.websocket = websocket
        self.vad = webrtcvad.Vad(3)
        self.raw_buffer = bytearray()
        self.speech_buffer = [] 
        self.num_samples_in_buffer = 0
        self.is_speaking = False
        self.silence_frames = 0
        self.last_preview_time = 0

    def process_packet(self, data):
        try:
            meta_len = int.from_bytes(data[:4], byteorder='little')
            metadata_json = data[4 : 4 + meta_len].decode('utf-8')
            metadata = json.loads(metadata_json)
            chunk_data = data[4 + meta_len:]

            input_rate = metadata.get('sampleRate', 48000)
            audio_16k_bytes = self._resample(chunk_data, input_rate)
            self._process_vad(audio_16k_bytes)

        except Exception as e:
            logger.error(f"Packet Error: {e}")

    def _resample(self, chunk_bytes, input_rate):
        audio_np = np.frombuffer(chunk_bytes, dtype=np.int16)
        if input_rate == TARGET_SAMPLE_RATE:
            return audio_np.tobytes()
        num_samples = int(len(audio_np) * TARGET_SAMPLE_RATE / input_rate)
        resampled = signal.resample(audio_np, num_samples)
        return resampled.astype(np.int16).tobytes()

    def _process_vad(self, audio_bytes):
        self.raw_buffer.extend(audio_bytes)
        FRAME_SIZE = 960 
        
        while len(self.raw_buffer) >= FRAME_SIZE:
            frame = self.raw_buffer[:FRAME_SIZE]
            del self.raw_buffer[:FRAME_SIZE]
            
            is_speech = self.vad.is_speech(frame, TARGET_SAMPLE_RATE)
            frame_np = np.frombuffer(frame, dtype=np.int16)
            frame_float = frame_np.astype(np.float32) / 32768.0

            if is_speech:
                self.is_speaking = True
                self.silence_frames = 0
                self.speech_buffer.append(frame_float)
                self.num_samples_in_buffer += len(frame_float)
                self._try_send_preview()
            else:
                if self.is_speaking:
                    self.speech_buffer.append(frame_float)
                    self.num_samples_in_buffer += len(frame_float)
                    self.silence_frames += 1
                    if self.silence_frames > 15: 
                        self._flush_sentence()

    def _try_send_preview(self):
        now = time.time() * 1000
        if now - self.last_preview_time > PREVIEW_INTERVAL_MS:
            if self.num_samples_in_buffer > 4000: 
                full_audio = np.concatenate(self.speech_buffer)
                scheduler.schedule_fast(full_audio, self.websocket, is_final=False)
                self.last_preview_time = now

    def _flush_sentence(self):
        if self.speech_buffer:
            full_audio = np.concatenate(self.speech_buffer)
            scheduler.schedule_accurate(full_audio, self.websocket, is_final=True)
        
        self.speech_buffer = []
        self.num_samples_in_buffer = 0
        self.is_speaking = False
        self.silence_frames = 0


@app.on_event("startup")
async def startup_event():
    loop = asyncio.get_running_loop()
    for w in fast_workers:
        w.set_loop(loop)
    accurate_worker.set_loop(loop)

@app.websocket("/ws/transcribe")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    await websocket.send_json({'type': 'status', 'text': 'ready'})
    session = SessionHandler(websocket)
    try:
        while True:
            data = await websocket.receive_bytes()
            await asyncio.to_thread(session.process_packet, data)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"Connection Error: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
