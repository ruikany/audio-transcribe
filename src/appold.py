# from flask import Flask, render_template, request, send_file, jsonify
# import whisper
# import os
# import tempfile
#
# app = Flask(__name__)
#
# #model = whisper.load_model("base")
#
# @app.route('/')
# def index():
#     return render_template('index.html')

# @app.route('/transcribe', methods=['POST'])
# def transcribe():
#     print(request)
#     print(request.files)
#     if 'audio' not in request.files:
#         return jsonify({ 'error': 'No audio file received' }), 400
#     audio_file = request.files['audio']
#
#
#     # temp store  audio file
#     with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as temp:
#         audio_file.save(temp.name)
#         temp.flush()
#
#         result = model.transcribe(temp.name)
#         text = result["text"]
#
#         os.unlink(temp.name)
#
#     # temp store transcript text
#     txt_path = tempfile.NamedTemporaryFile(delete=False, suffix=".txt").name
#     with open(txt_path, 'w', encoding='utf-8') as f:
#         f.write(str(text))
#
#     return jsonify({ 'text': text, 'file_url': f"/download?path={txt_path}" })
#
# @app.route('/download')
# def download():
#     path = request.args.get('path')
#     return send_file(str(path), as_attachment=True, download_name='transcription.txt')

# if __name__ == '__main__':
#     app.run(debug=True)
#
