const recordButton = document.getElementById("recordButton");
const stopButton = document.getElementById("stopButton");
const sendTextButton = document.getElementById("sendTextButton");
const sessionIdInput = document.getElementById("sessionId");
const transcriptOverrideInput = document.getElementById("transcriptOverride");
const textMessageInput = document.getElementById("textMessage");
const statusEl = document.getElementById("status");
const recordingPreview = document.getElementById("recordingPreview");
const assistantAudio = document.getElementById("assistantAudio");
const playbackSpeedSelect = document.getElementById("playbackSpeed");
const transcriptOutput = document.getElementById("transcriptOutput");
const assistantOutput = document.getElementById("assistantOutput");
const jsonOutput = document.getElementById("jsonOutput");
const artifactOutput = document.getElementById("artifactOutput");
const audioHint = document.getElementById("audioHint");
const emotionOutput = document.getElementById("emotionOutput");
const historyList = document.getElementById("historyList");
const refreshHistoryButton = document.getElementById("refreshHistoryButton");

let mediaRecorder = null;
let mediaStream = null;
let recordedChunks = [];

function applyPlaybackRate() {
  assistantAudio.playbackRate = Number(playbackSpeedSelect.value || "1.25");
}

function setStatus(message) {
  statusEl.textContent = message;
}

function setBusy(isBusy) {
  recordButton.disabled = isBusy || mediaRecorder !== null;
  stopButton.disabled = mediaRecorder === null;
  sendTextButton.disabled = isBusy;
}

function renderResponse(payload) {
  transcriptOutput.textContent = payload.transcript || payload.user_message || "No transcript.";
  assistantOutput.textContent = payload.assistant_message || "No assistant response.";
  jsonOutput.textContent = JSON.stringify(payload, null, 2);
  artifactOutput.textContent = payload.audio_path || "No artifact returned.";
  emotionOutput.textContent = payload.emotion_debug
    ? JSON.stringify(payload.emotion_debug, null, 2)
    : `final_emotion: ${payload.detected_emotion || "neutral"}`;

  if (payload.audio_path && payload.audio_path.endsWith(".wav")) {
    assistantAudio.src = `/${payload.audio_path}`;
    applyPlaybackRate();
    assistantAudio.play().catch(() => {});
    audioHint.textContent = `Playback ready from ${payload.audio_path}`;
  } else {
    assistantAudio.removeAttribute("src");
    assistantAudio.load();
    audioHint.textContent = payload.audio_path
      ? `Speech fallback active. Output was saved as ${payload.audio_path}`
      : "No assistant audio artifact returned.";
  }
}

function renderHistory(historyPayload) {
  historyList.innerHTML = "";

  if (!historyPayload.turns || historyPayload.turns.length === 0) {
    historyList.innerHTML = '<p class="hint">No conversation stored for this session yet.</p>';
    return;
  }

  historyPayload.turns.forEach((turn) => {
    const card = document.createElement("article");
    card.className = "history-item";

    const meta = document.createElement("div");
    meta.className = "history-meta";
    meta.textContent = `${turn.role.toUpperCase()}${turn.emotion ? ` • ${turn.emotion}` : ""}`;

    const content = document.createElement("p");
    content.className = "history-content";
    content.textContent = turn.content;

    card.append(meta, content);
    historyList.appendChild(card);
  });
}

async function loadHistory() {
  const sessionId = sessionIdInput.value.trim() || "browser-demo";
  try {
    const response = await fetch(`/api/history/${encodeURIComponent(sessionId)}`);
    const { ok, payload } = await parseResponse(response);
    if (!ok) {
      throw new Error(buildErrorMessage(payload, "History request failed."));
    }
    renderHistory(payload);
  } catch (error) {
    historyList.innerHTML = `<p class="hint">History request failed: ${error.message}</p>`;
  }
}

async function parseResponse(response) {
  const rawText = await response.text();
  try {
    return {
      ok: response.ok,
      payload: JSON.parse(rawText),
    };
  } catch {
    return {
      ok: response.ok,
      payload: {
        detail: rawText || response.statusText || "Request failed.",
      },
    };
  }
}

function buildErrorMessage(payload, fallbackMessage) {
  if (!payload) {
    return fallbackMessage;
  }

  if (payload.message && payload.detail) {
    return `${payload.detail}: ${payload.message}`;
  }

  return payload.detail || payload.message || fallbackMessage;
}

async function postTextMessage() {
  const message = textMessageInput.value.trim();
  if (!message) {
    setStatus("Enter a text message before sending.");
    return;
  }

  setBusy(true);
  setStatus("Sending text message to /api/chat...");

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: sessionIdInput.value.trim() || "browser-demo",
        message,
      }),
    });
    const { ok, payload } = await parseResponse(response);
    if (!ok) {
      throw new Error(buildErrorMessage(payload, "Chat request failed."));
    }
    renderResponse(payload);
    await loadHistory();
    setStatus("Text response received.");
  } catch (error) {
    setStatus(`Chat request failed: ${error.message}`);
  } finally {
    setBusy(false);
  }
}

async function startRecording() {
  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(mediaStream);
    recordedChunks = [];

    mediaRecorder.addEventListener("dataavailable", (event) => {
      if (event.data.size > 0) {
        recordedChunks.push(event.data);
      }
    });

    mediaRecorder.addEventListener("stop", async () => {
      const blob = new Blob(recordedChunks, { type: "audio/webm" });
      recordingPreview.src = URL.createObjectURL(blob);
      await sendVoice(blob);
      mediaStream.getTracks().forEach((track) => track.stop());
      mediaStream = null;
      mediaRecorder = null;
      setBusy(false);
    });

    mediaRecorder.start();
    setStatus("Recording... click Stop when you're ready.");
    setBusy(false);
    recordButton.disabled = true;
    stopButton.disabled = false;
  } catch (error) {
    setStatus(`Microphone error: ${error.message}`);
    mediaRecorder = null;
    if (mediaStream) {
      mediaStream.getTracks().forEach((track) => track.stop());
      mediaStream = null;
    }
    setBusy(false);
  }
}

function stopRecording() {
  if (!mediaRecorder) {
    return;
  }
  setStatus("Uploading recorded audio...");
  stopButton.disabled = true;
  mediaRecorder.stop();
}

async function sendVoice(blob) {
  const formData = new FormData();
  formData.append("session_id", sessionIdInput.value.trim() || "browser-demo");
  formData.append("audio", blob, "browser-recording.webm");

  const transcriptOverride = transcriptOverrideInput.value.trim();
  if (transcriptOverride) {
    formData.append("transcript_override", transcriptOverride);
  }

  try {
    const response = await fetch("/api/voice", {
      method: "POST",
      body: formData,
    });
    const { ok, payload } = await parseResponse(response);
    if (!ok) {
      throw new Error(buildErrorMessage(payload, "Voice request failed."));
    }
    renderResponse(payload);
    await loadHistory();
    setStatus("Voice response received.");
  } catch (error) {
    setStatus(`Voice request failed: ${error.message}`);
  }
}

recordButton.addEventListener("click", startRecording);
stopButton.addEventListener("click", stopRecording);
sendTextButton.addEventListener("click", postTextMessage);
refreshHistoryButton.addEventListener("click", loadHistory);
playbackSpeedSelect.addEventListener("change", applyPlaybackRate);

applyPlaybackRate();
loadHistory();
