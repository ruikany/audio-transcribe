from flask import Flask, render_template
from flask_sock import Sock
from RealtimeSTT import AudioToTextRecorder
import logging

app = Flask(__name__)
sock = Sock(app)

# --- NEW VAD Callbacks ---
def vad_start():
    print(">>> VAD START <<< (Speech detected)")

def vad_stop():
    print("<<< VAD STOP >>> (Silence detected)")

# --- Transcription Callbacks (no change) ---
def send_stabilized_text(text, websocket):
    print(f"✅ STABILIZED: {text}")
    try:
        websocket.send(f"FINAL: {text}")
    except Exception as e:
        print(f"Error sending stabilized text: {e}")

def send_interim_text(text, websocket):
    print(f"🔄 INTERIM: {text}")
    try:
        websocket.send(f"INTERIM: {text}")
    except Exception as e:
        print(f"Error sending interim text: {e}")

@app.route('/')
def index():
    return render_template('index2.html')

@sock.route('/mic')
def mic(ws):
    print("WebSocket connection established.")
    
    # --- Callbacks (no change) ---
    def vad_start():
        print(">>> VAD START <<< (Speech detected)")

    def vad_stop():
        print("<<< VAD STOP >>> (Silence detected)")

    def send_stabilized_text(text, websocket):
        print(f"✅ STABILIZED: {text}")
        try:
            websocket.send(f"FINAL: {text}")
        except Exception as e:
            print(f"Error sending stabilized text: {e}")

    def send_interim_text(text, websocket):
        print(f"🔄 INTERIM: {text}")
        try:
            websocket.send(f"INTERIM: {text}")
        except Exception as e:
            print(f"Error sending interim text: {e}")

    def on_stabilized(text):
        send_stabilized_text(text, ws)
        
    def on_interim(text):
        send_interim_text(text, ws)

    # --- Initialize the recorder WITH VAD FILTER DISABLED ---
    recorder = AudioToTextRecorder(
        use_microphone=False, 
        enable_realtime_transcription=True,
        on_realtime_transcription_stabilized=on_stabilized, 
        on_realtime_transcription_update=on_interim, 
        realtime_model_type="tiny.en",
        
        on_vad_start=vad_start,
        on_vad_stop=vad_stop,
        
        webrtc_sensitivity=0, # Most sensitive
        silero_sensitivity=1.0, # Most sensitive
        
        # ----------------------------------------------------
        # ⬇️ THIS IS THE NEW LINE ⬇️
        # Disable the extra VAD filter from faster_whisper
        faster_whisper_vad_filter=False,
        # ----------------------------------------------------
        
        level=logging.DEBUG 
    )

    try:
        while True:
            data = ws.receive()
            if data:
                print(f"Received {len(data)} bytes...") # Shortened this log
                recorder.feed_audio(data)
                
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        print("WebSocket connection closed.")
        recorder.stop()
