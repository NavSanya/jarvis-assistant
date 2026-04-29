const recordButton = document.getElementById("recordButton");
const stopButton = document.getElementById("stopButton");
const sendTextButton = document.getElementById("sendTextButton");
const clearConversationButton = document.getElementById("clearConversationButton");
const sessionIdInput = document.getElementById("sessionId");
const transcriptOverrideInput = document.getElementById("transcriptOverride");
const wellnessHeartRateInput = document.getElementById("wellnessHeartRate");
const wellnessStressLevelSelect = document.getElementById("wellnessStressLevel");
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
const moodTitle = document.getElementById("moodTitle");
const moodSummary = document.getElementById("moodSummary");
const moodCore = document.getElementById("moodCore");

let mediaRecorder = null;
let mediaStream = null;
let recordedChunks = [];
let audioContext = null;
let wakeRecognition = null;
let wakeListeningActive = false;
let shouldWakeListen = true;

const WAKE_PHRASE = "hey jayjay";

const EMOTION_UI = {
  neutral: {
    label: "Neutral",
    summary: "Steady baseline mode with balanced tone and visuals.",
  },
  calm: {
    label: "Calm",
    summary: "Cooling the interface and slowing the pulse for a grounded response.",
  },
  happy: {
    label: "Happy",
    summary: "Brightening the console to match an upbeat, positive interaction.",
  },
  excited: {
    label: "Excited",
    summary: "Lifting the energy with brighter color and faster waveform motion.",
  },
  surprised: {
    label: "Surprised",
    summary: "Adding a sharper pulse to reflect elevated energy and attention.",
  },
  sad: {
    label: "Sad",
    summary: "Softening the palette for a gentler, more supportive response style.",
  },
  fear: {
    label: "Stressed / Anxious",
    summary: "Warming the console and intensifying the pulse to flag stress signals.",
  },
  angry: {
    label: "Angry",
    summary: "Shifting to a hotter alert state with stronger contrast and motion.",
  },
};

function applyPlaybackRate() {
  assistantAudio.playbackRate = Number(playbackSpeedSelect.value || "1.25");
}

function getWellnessSignal() {
  const heartRateRaw = wellnessHeartRateInput.value.trim();
  const stressLevel = wellnessStressLevelSelect.value.trim();
  const heartRate = heartRateRaw ? Number.parseInt(heartRateRaw, 10) : null;

  if (!heartRate && !stressLevel) {
    return null;
  }

  return {
    heart_rate: Number.isNaN(heartRate) ? null : heartRate,
    stress_level: stressLevel || null,
    source: "manual_demo",
  };
}

function normalizeSpeech(text) {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function heardWakePhrase(text) {
  const normalized = normalizeSpeech(text);
  return normalized.includes(WAKE_PHRASE) || normalized.includes("hey jay jay");
}

function getAudioContext() {
  if (!audioContext) {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) {
      return null;
    }
    audioContext = new AudioContextClass();
  }
  return audioContext;
}

async function playCue(frequencies, durationMs = 140, gapMs = 45) {
  const context = getAudioContext();
  if (!context) {
    return;
  }

  if (context.state === "suspended") {
    await context.resume();
  }

  let startAt = context.currentTime;

  frequencies.forEach((frequency) => {
    const oscillator = context.createOscillator();
    const gainNode = context.createGain();
    const durationSeconds = durationMs / 1000;

    oscillator.type = "sine";
    oscillator.frequency.setValueAtTime(frequency, startAt);

    gainNode.gain.setValueAtTime(0.0001, startAt);
    gainNode.gain.exponentialRampToValueAtTime(0.08, startAt + 0.02);
    gainNode.gain.exponentialRampToValueAtTime(
      0.0001,
      startAt + durationSeconds,
    );

    oscillator.connect(gainNode);
    gainNode.connect(context.destination);
    oscillator.start(startAt);
    oscillator.stop(startAt + durationSeconds);

    startAt += durationSeconds + gapMs / 1000;
  });
}

function setStatus(message) {
  statusEl.textContent = message;
}

function setBusy(isBusy) {
  recordButton.disabled = isBusy || mediaRecorder !== null;
  stopButton.disabled = mediaRecorder === null;
  sendTextButton.disabled = isBusy;
  clearConversationButton.disabled = isBusy || mediaRecorder !== null;
}

function applyEmotionTheme(emotion) {
  const normalizedEmotion = (emotion || "neutral").toLowerCase();
  const config = EMOTION_UI[normalizedEmotion] || EMOTION_UI.neutral;

  document.body.dataset.emotion = normalizedEmotion;
  moodTitle.textContent = config.label;
  moodSummary.textContent = config.summary;
  moodCore.setAttribute("data-emotion", normalizedEmotion);
}

function scrollHistoryToLatest() {
  historyList.scrollTo({
    top: historyList.scrollHeight,
    behavior: "smooth",
  });
}

function createWakeRecognition() {
  const SpeechRecognitionClass =
    window.SpeechRecognition || window.webkitSpeechRecognition;

  if (!SpeechRecognitionClass) {
    return null;
  }

  const recognition = new SpeechRecognitionClass();
  recognition.continuous = true;
  recognition.interimResults = true;
  recognition.lang = "en-US";

  recognition.onstart = () => {
    wakeListeningActive = true;
    if (!mediaRecorder) {
      setStatus(`Wake listening active. Say "${WAKE_PHRASE}" to begin.`);
    }
  };

  recognition.onresult = async (event) => {
    let transcript = "";
    for (let i = event.resultIndex; i < event.results.length; i += 1) {
      transcript += `${event.results[i][0].transcript} `;
    }

    if (!heardWakePhrase(transcript) || mediaRecorder) {
      return;
    }

    shouldWakeListen = false;
    stopWakeListening();
    playCue([720, 920, 1120], 100, 30).catch(() => {});
    setStatus('Wake phrase heard. Starting voice turn...');
    await startRecording();
  };

  recognition.onerror = (event) => {
    wakeListeningActive = false;

    if (event.error === "not-allowed" || event.error === "service-not-allowed") {
      shouldWakeListen = false;
      setStatus(
        'Microphone access is needed for wake listening. Allow mic access, then use "Start Voice Turn" once to enable it.',
      );
      return;
    }

    if (event.error === "no-speech" || event.error === "aborted") {
      return;
    }

    setStatus(`Wake listening issue: ${event.error}`);
  };

  recognition.onend = () => {
    wakeListeningActive = false;

    if (!shouldWakeListen || mediaRecorder) {
      return;
    }

    window.setTimeout(() => {
      startWakeListening();
    }, 450);
  };

  return recognition;
}

function stopWakeListening() {
  if (!wakeRecognition || !wakeListeningActive) {
    return;
  }

  wakeRecognition.stop();
}

function startWakeListening() {
  if (mediaRecorder) {
    return;
  }

  if (!wakeRecognition) {
    wakeRecognition = createWakeRecognition();
  }

  if (!wakeRecognition) {
    setStatus(
      'Wake listening is not supported in this browser. Use the voice turn button instead.',
    );
    return;
  }

  if (wakeListeningActive) {
    return;
  }

  shouldWakeListen = true;

  try {
    wakeRecognition.start();
  } catch (error) {
    if (!String(error).includes("already started")) {
      setStatus(`Wake listening could not start: ${error.message}`);
    }
  }
}

function renderResponse(payload) {
  transcriptOutput.textContent = payload.transcript || payload.user_message || "No transcript.";
  assistantOutput.textContent = payload.assistant_message || "No assistant response.";
  jsonOutput.textContent = JSON.stringify(payload, null, 2);
  artifactOutput.textContent = payload.audio_path || "No artifact returned.";
  emotionOutput.textContent = payload.emotion_debug
    ? JSON.stringify(payload.emotion_debug, null, 2)
    : `final_emotion: ${payload.detected_emotion || "neutral"}`;

  if (payload.wellness_signal) {
    emotionOutput.textContent += `\n\nwellness_signal:\n${JSON.stringify(payload.wellness_signal, null, 2)}`;
  }

  applyEmotionTheme(payload.detected_emotion);

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
    card.dataset.role = turn.role;

    const meta = document.createElement("div");
    meta.className = "history-meta";
    meta.textContent = turn.role === "assistant" ? "JARVIS" : "YOU";

    const badge = document.createElement("span");
    badge.className = "history-badge";
    badge.textContent = turn.emotion || (turn.role === "assistant" ? "responding" : "speaking");

    const content = document.createElement("p");
    content.className = "history-content";
    content.textContent = turn.content;

    const metaRow = document.createElement("div");
    metaRow.className = "history-meta-row";
    metaRow.append(meta, badge);

    card.append(metaRow, content);
    historyList.appendChild(card);
  });

  scrollHistoryToLatest();
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
  const wellnessSignal = getWellnessSignal();
  if (!message) {
    setStatus("Enter a text message before sending.");
    return;
  }

  setBusy(true);
  setStatus("Sending text turn to /api/chat...");

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: sessionIdInput.value.trim() || "browser-demo",
        message,
        wellness_signal: wellnessSignal,
      }),
    });
    const { ok, payload } = await parseResponse(response);
    if (!ok) {
      throw new Error(buildErrorMessage(payload, "Chat request failed."));
    }
    renderResponse(payload);
    textMessageInput.value = "";
    await loadHistory();
    setStatus("Text turn complete.");
  } catch (error) {
    setStatus(`Chat request failed: ${error.message}`);
  } finally {
    setBusy(false);
  }
}

async function clearConversation() {
  const sessionId = sessionIdInput.value.trim() || "browser-demo";

  setBusy(true);
  setStatus("Clearing conversation history...");

  try {
    const response = await fetch(`/api/history/${encodeURIComponent(sessionId)}`, {
      method: "DELETE",
    });
    const { ok, payload } = await parseResponse(response);
    if (!ok) {
      throw new Error(buildErrorMessage(payload, "Clear conversation request failed."));
    }

    transcriptOutput.textContent = "No transcript yet.";
    assistantOutput.textContent = "No assistant response yet.";
    jsonOutput.textContent = "No response yet.";
    artifactOutput.textContent = "No artifact yet.";
    emotionOutput.textContent = "No emotion metadata yet.";
    audioHint.textContent = "Assistant audio will appear here when a real `.wav` response is generated.";
    assistantAudio.removeAttribute("src");
    assistantAudio.load();
    applyEmotionTheme("neutral");
    await loadHistory();
    setStatus(`Started a new conversation for session ${sessionId}.`);
  } catch (error) {
    setStatus(`Clear conversation failed: ${error.message}`);
  } finally {
    setBusy(false);
  }
}

async function startRecording() {
  try {
    shouldWakeListen = false;
    stopWakeListening();
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
    playCue([660, 880]).catch(() => {});
    setStatus("Listening for your turn. Click End Voice Turn when you're done speaking.");
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
  playCue([540, 380], 120, 35).catch(() => {});
  setStatus("Ending turn and uploading audio...");
  stopButton.disabled = true;
  mediaRecorder.stop();
}

async function sendVoice(blob) {
  const formData = new FormData();
  const wellnessSignal = getWellnessSignal();
  formData.append("session_id", sessionIdInput.value.trim() || "browser-demo");
  formData.append("audio", blob, "browser-recording.webm");

  const transcriptOverride = transcriptOverrideInput.value.trim();
  if (transcriptOverride) {
    formData.append("transcript_override", transcriptOverride);
  }

  if (wellnessSignal?.heart_rate) {
    formData.append("wellness_heart_rate", String(wellnessSignal.heart_rate));
  }

  if (wellnessSignal?.stress_level) {
    formData.append("wellness_stress_level", wellnessSignal.stress_level);
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
    setStatus("Voice turn complete.");
  } catch (error) {
    setStatus(`Voice request failed: ${error.message}`);
  } finally {
    shouldWakeListen = true;
    window.setTimeout(() => {
      startWakeListening();
    }, 600);
  }
}

recordButton.addEventListener("click", startRecording);
stopButton.addEventListener("click", stopRecording);
sendTextButton.addEventListener("click", postTextMessage);
clearConversationButton.addEventListener("click", clearConversation);
refreshHistoryButton.addEventListener("click", loadHistory);
playbackSpeedSelect.addEventListener("change", applyPlaybackRate);
textMessageInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    if (!sendTextButton.disabled) {
      postTextMessage();
    }
  }
});
sessionIdInput.addEventListener("change", loadHistory);
sessionIdInput.addEventListener("blur", loadHistory);

applyPlaybackRate();
applyEmotionTheme("neutral");
loadHistory();
window.setTimeout(() => {
  startWakeListening();
}, 500);
