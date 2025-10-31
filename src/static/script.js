let mediaRecorder;
let chunks = [];
let rec = false;
let audioStream;

const recBtn = document.querySelector(".recBtn");
const transcript = document.querySelector(".transcript");
const dlBtn = document.querySelector(".dlBtn");

recBtn.onclick = async () => {
  if (!rec) {
    try {
      audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorder = new MediaRecorder(audioStream, {
        mimeType: "audio/webm;codecs=opus",
      });
      chunks = [];

      // set up event handlers here — after recorder is created
      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunks.push(e.data);
      };

      mediaRecorder.onstop = async () => {
        const blob = new Blob(chunks, { type: "audio/webm" });
        console.log("Recorded blob size:", blob.size);
        const formData = new FormData();
        formData.append("audio", blob, "recording.webm");

        try {
          const res = await fetch("/transcribe", {
            method: "POST",
            body: formData,
          });

          const data = await res.json();
          if (data.text) {
            transcript.textContent = data.text;
            dlBtn.style.display = "inline-block";
            dlBtn.onclick = () => {
              window.location.href = data.file_url;
            };
          } else {
            transcript.textContent = "transcription failed";
          }
        } catch (e) {
          console.error("upload audio failed", e);
          transcript.textContent = "processing audio failed";
        }
      };

      mediaRecorder.start();
      rec = true;
      recBtn.textContent = "Stop recording";
    } catch (e) {
      console.error("microphone access failed", e);
    }
  } else {
    rec = false;
    mediaRecorder.stop();
    recBtn.textContent = "Start recording";

    // stop all audio tracks
    audioStream.getTracks().forEach((track) => track.stop());
  }
};
