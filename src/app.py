from flask import Flask, render_template
import whisper

app = Flask(__name__)

model = whisper.load_model("base")

@app.route('/')
def index():
    return render_template('index.html')


