from flask import Flask, render_template
from flask_sock import Sock
from RealtimeSTT import AudioToTextRecorder

app = Flask(__name__)
sock = Sock(app)

# This callback function will be passed to the recorder
def send_transcription_to_client(text, websocket):
    """Callback to send transcription text over the WebSocket."""
    print(f"Sending to client: {text}")
    try:
        # This will send the cumulative transcription
        websocket.send(text) 
    except Exception as e:
        print(f"Error sending to websocket: {e}")

@app.route('/')
def index():
    """Serves the main HTML page."""
    return render_template('index2.html')

@sock.route('/mic')
def mic(ws):
    """Handles the WebSocket connection for a single client."""
    print("WebSocket connection established.")
    
    # 1. Create a callback that includes the websocket
    #    We need a wrapper function to pass the 'ws' object.
    def on_stabilized_text(text):
        send_transcription_to_client(text, ws)

    # 2. Correctly initialize the recorder
    recorder = AudioToTextRecorder(
        # CRITICAL: Tell the recorder to accept audio from feed_audio()
        use_microphone=False, 
        
        # CRITICAL: Enable real-time mode to get access to the callbacks
        enable_realtime_transcription=True,
        
        # CRITICAL: This is the correct callback for "end-of-sentence"
        on_realtime_transcription_stabilized=on_stabilized_text,
        
        # Optional: Use a smaller, faster model for real-time
        realtime_model_type="tiny.en", 
        
        # Optional: Set language if you know it
        language="en"
    )

    try:
        while True:
            # Receive raw audio data (bytes) from the client
            data = ws.receive()
            if data:
                # 3. Feed the audio from the browser into the recorder
                recorder.feed_audio(data)
                
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        print("WebSocket connection closed.")
        recorder.stop()
