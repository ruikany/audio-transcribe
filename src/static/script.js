let mediaRecorder;
let chunks = [];

const recBtn = document.querySelector(".recBtn");
const transcript = document.querySelector(".transcript");
const dlBtn = document.querySelector(".dlBtn");

recBtn.onclick = async () => {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  mediaRecorder = new MediaRecorder(stream);
  mediaRecorder.start();
  recBtn.textContent = "Stop recording";

  mediaRecorder.ondataavailable = (e) => chunks.push(e.data);
};
