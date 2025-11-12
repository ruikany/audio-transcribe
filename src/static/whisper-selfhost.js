const recBtn = document.querySelector(".recBtn");
const transcript = document.querySelector(".transcript");
const dlBtn = document.querySelector(".dlBtn");

let rec = false; // is currently recording?
let chunks = []; // to store recorded audio data
let audioStream; // MediaStream stream that captures mic input
let mediaRecorder; // obj that encodes audioStream into media format

recBtn.onclick = () => (rec ? stopRecording() : startRecording());

function stopRecording() {
  if (mediaRecorder && rec) {
    mediaRecorder.stop();
    audioStream.getTracks().forEach((track) => track.stop());
    rec = false;
    recBtn.textContent = "Start Recording";
  }
}

async function startRecording() {
  try {
    audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(audioStream, {
      mimeType: "audio/webm;codecs=opus",
    });
    chunks = [];

    // callbacks
    mediaRecorder.ondataavailable = handleData;
    mediaRecorder.onstop = handleStop;

    mediaRecorder.start();
    rec = true;
    recBtn.textContent = "Stop Recording";
  } catch (e) {
    console.error("error accessing microphone: ", e);
  }
}

function handleData(e) {
  if (e.data.size > 0) chunks.push(e.data);
}

async function handleStop() {
  const blob = new Blob(chunks, { type: "audio/webm" });
  console.log(blob.size);

  transcript.textContent = "Processing transcription...";
  try {
    const data = await uploadAudio(blob);
    console.log(data);
    if (data.text) {
      transcript.textContent = data.text;
      dlBtn.style.display = "inline-block";
      dlBtn.onclick = () => {
        window.location.href = data.file_url;
      };
    } else {
      transcript.textContent = "No voice detected, please try again";
    }
  } catch (e) {
    console.error("transcription failed: ", e);
    transcript.textContent = "transcription failed";
  }
}

async function uploadAudio(blob) {
  const formData = new FormData();
  formData.append("audio", blob, "recording.webm");

  const res = await fetch("/transcribe", { method: "POST", body: formData });
  if (!res.ok) throw new Error("UploadAudio failed");
  return await res.json();
}
