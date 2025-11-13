// only support for web speech api on chrome and safari
//
// performance tests:
// web speech api processLocally = true vs false. only supported on desktop chrome, edge, opera
// whisper-ai model hosted somewhere not good because slow batch processing, if cut audio in many pieces will lose context of the sentence, cannot infer correctly
// wasm with transformers.js download model on browser, same problems as whisper
// vosk = streaming model
// realtimeSTT = vad + chunking to faster-whisper

let rec = false; // is currently recording?

const recBtn = document.querySelector(".recBtn");
const transcript = document.querySelector(".transcript");
const dlBtn = document.querySelector(".dlBtn");

window.SpeechRecognition =
  window.SpeechRecognition || window.webkitSpeechRecognition;

if (window.SpeechRecognition) {
  const recognition = new SpeechRecognition();
  recognition.interimResults = true;
  recognition.lang = "en-US";
  recBtn.onclick = () => {
    if (rec) {
      recognition.stop();
      return;
    }

    SpeechRecognition.available({
      langs: ["en-US"],
      processLocally: true,
    })
      .then((result) => {
        if (result === "available") {
          //recognition.processLocally = true;
          recognition.start();
          rec = true;
          recBtn.textContent = "Stop Recording";
        } else if (result === "downloadable") {
          transcript.textContent = `en-US language pack is downloading...`;
          SpeechRecognition.install({
            langs: ["en-US"],
            processLocally: true,
          }).then((installResult) => {
            if (installResult) {
              transcript.textContent = `en-US language pack downloaded. Please click 'Start recording' again.`;
            } else {
              transcript.textContent = `en-US language pack failed to download`;
            }
          });
        } else {
          transcript.textContent = `Local 'en-US' not available`;
        }
      })
      .catch((e) => {
        transcript.textContent = `Error checking availability: ${e.message}`;
        console.error(e);
      });
  };

  recognition.onend = () => {
    rec = false;
    recBtn.textContent = "Start Recording";
    console.log("Speech recognition finished.");
  };

  recognition.onresult = (event) => {
    let interimTranscript = "";
    let finalTranscript = "";

    for (let i = event.resultIndex; i < event.results.length; ++i) {
      if (event.results[i].isFinal) {
        finalTranscript += event.results[i][0].transcript;
      } else {
        interimTranscript += event.results[i][0].transcript;
      }
    }
    transcript.textContent = finalTranscript + interimTranscript;
  };

  recognition.onerror = (event) => {
    console.error("Speech recognition error", event.error);
    transcript.textContent = "Error: " + event.error;
  };
} else {
  recBtn.textContent = "Not Supported";
  recBtn.disabled = true;
  transcript.textContent = "Sorry, please use Chrome or Safari";
}
