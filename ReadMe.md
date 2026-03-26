# Jarvis Assistant Starter

A FastAPI-based voice assistant starter that supports:

- speech-to-text with Whisper
- hybrid emotion detection from audio + transcript cues
- LLM responses with Groq
- MCP tools through the Python SDK
- text-to-speech with Coqui
- browser-based microphone testing UI
- conversation persistence with SQLAlchemy

```text
Microphone -> Python backend -> emotion detection -> agent/model -> MCP tools -> TTS audio output
```

## Features

- `POST /api/chat` for text chat
- `POST /api/voice` for uploaded audio and voice processing
- `GET /api/history/{session_id}` for recent conversation history
- `GET /health` for provider status
- `WS /ws/chat` for a simple websocket chat loop
- browser voice console at `/ui`
- recent session history in the UI
- emotion reasoning metadata in voice responses
- automatic SQLite fallback when MySQL is unavailable

## Stack

- Backend: FastAPI
- LLM: Groq
- STT: Whisper
- TTS: Coqui TTS
- Emotion: Hugging Face audio classification plus transcript cues
- Database: SQLAlchemy async with MySQL target and SQLite fallback
- Tools: MCP Python SDK

## Project Layout

```text
jarvis-assistant/
├── app/
│   ├── api.py
│   ├── config.py
│   ├── db.py
│   ├── mcp_server.py
│   ├── models.py
│   ├── schemas.py
│   ├── services/
│   │   ├── emotion.py
│   │   ├── llm.py
│   │   ├── memory.py
│   │   ├── orchestrator.py
│   │   ├── stt.py
│   │   ├── tools.py
│   │   └── tts.py
│   └── static/
│       ├── app.js
│       ├── index.html
│       └── styles.css
├── scripts/
│   ├── run_full_tests.py
│   └── test_ws.py
├── wiki/
│   └── Progress-Log.md
├── .env.example
├── main.py
├── requirements.txt
└── requirements-voice.txt
```

## Quick Start

Recommended Python version:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload
```

Open:

- Swagger UI: `http://127.0.0.1:8000/docs`
- Browser UI: `http://127.0.0.1:8000/ui`

## Environment Notes

- Set `GROQ_API_KEY` in `.env`
- Install `ffmpeg` locally for real Whisper transcription
- If MySQL is not running, the app falls back to SQLite when `ALLOW_SQLITE_FALLBACK=true`
- Do not leave `WHISPER_DEVICE=` or `COQUI_DEVICE=` blank in `.env`
- On Python `3.14`, Coqui may not be available; Python `3.11` or `3.12` is recommended for full voice output

## Runtime Behavior

- voice responses can use real Whisper transcription when a valid audio file is uploaded
- `transcript_override` bypasses STT intentionally for quick testing
- hybrid emotion inference combines audio tone and transcript cues
- the browser UI auto-plays `.wav` assistant output when available
- if TTS falls back, the UI shows the returned artifact path instead
- assistant playback defaults to `1.25x` in the browser UI

## Example Requests

Text chat:

```bash
curl -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "demo",
    "message": "What time is it? Keep the answer short."
  }'
```

Voice upload with transcript override:

```bash
curl -X POST http://127.0.0.1:8000/api/voice \
  -F "session_id=voice-demo" \
  -F "transcript_override=Please remember I like concise answers." \
  -F "audio=@sample.wav"
```

Real voice transcription:

```bash
curl -X POST http://127.0.0.1:8000/api/voice \
  -F "session_id=voice-demo" \
  -F "audio=@sample.wav"
```

History:

```bash
curl http://127.0.0.1:8000/api/history/demo
```

## Browser UI

The browser voice console at `/ui` supports:

- microphone recording
- direct text chat
- transcript display
- assistant message display
- raw JSON response view
- output artifact display
- emotion debug metadata
- recent session history
- adjustable audio playback speed

## Testing

Quick validation:

```bash
curl http://127.0.0.1:8000/
curl http://127.0.0.1:8000/health
python3 scripts/test_ws.py
python3 scripts/run_full_tests.py
ls generated_audio
```

The full test guide and ongoing verification notes live in [Progress-Log.md](/Users/navsanya/Desktop/Virtual-AI-Assistant/jarvis-assistant/wiki/Progress-Log.md).

## Current Status

Working now:

- Groq responses
- Whisper STT
- hybrid emotion detection
- MCP tool calls
- browser microphone UI
- session history endpoint and panel
- Coqui-backed TTS when available
- SQLite fallback when MySQL is unavailable

Known caveats:

- emotion detection can still be imperfect on nuanced speech
- MySQL is the target backend, but SQLite is still the default local fallback
- websocket support is simple and not full realtime streaming audio

## Roadmap

Recommended next improvements:

- richer MCP tools
- stronger automated API tests
- tighter production logging and error handling
- real MySQL-first deployment setup
- stronger multi-session conversation UX

GROQ Key in oldstuff Readme