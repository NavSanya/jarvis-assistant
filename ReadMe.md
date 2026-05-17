# Jarvis Assistant Starter

A FastAPI-based voice assistant starter with:

- speech-to-text with Whisper
- hybrid emotion detection from audio + transcript cues
- persona-aware response guidance from a prebuilt corpus lookup
- emotionally guided LLM responses with Groq or AWS Bedrock
- ETL-style prompt templates with runtime context injection
- browser-based conversation console
- text-to-speech with Coqui
- SQLAlchemy-backed conversation storage

```text
Microphone/Text -> Python backend -> emotion detection -> persona guidance lookup -> LLM orchestration -> TTS -> browser playback
```

## What This App Does

The current app is a browser-driven Jarvis demo that supports:

- voice turns from the browser microphone
- text turns from the browser UI
- emotion-aware responses
- persona-aware response style using `persona_id + detected_emotion`
- simulated wellness inputs for demo purposes
- assistant audio playback when TTS is available
- recent conversation history in the UI
- a wake phrase for hands-free recording

Current wake phrase:

- `Hey JayJay`
- `Hey Jay Jay`

Current startup behavior:

- chat history is cleared every time the app reboots

## Stack

- Backend: FastAPI
- LLM: Groq or AWS Bedrock
- STT: Whisper
- Optional Voice Understanding: SenseVoice
- TTS: Coqui TTS
- Emotion: Hugging Face audio classification plus transcript cues
- Database: SQLAlchemy async with MySQL target and SQLite fallback
- Frontend: HTML, CSS, JavaScript

## Project Layout

```text
jarvis-assistant/
├── corpus/
│   ├── descriptors.csv
│   ├── personas.json
│   └── persona_guidance.json
├── app/
│   ├── api.py
│   ├── config.py
│   ├── db.py
│   ├── models.py
│   ├── schemas.py
│   ├── services/
│   │   ├── emotion.py
│   │   ├── llm.py
│   │   ├── memory.py
│   │   ├── orchestrator.py
│   │   ├── rag.py
│   │   ├── sensevoice.py
│   │   ├── stt.py
│   │   └── tts.py
│   └── static/
│       ├── app.js
│       ├── index.html
│       └── styles.css
├── demo/
│   ├── README.md
│   ├── scenarios.json
│   └── audio/
│       ├── stressed_focus.wav
│       ├── excited_win.wav
│       ├── sad_support.wav
│       └── remember_preference.wav
├── scripts/
│   ├── build_persona_cache.py
│   ├── generate_demo_assets.py
│   ├── run_demo_scenarios.py
│   └── run_full_tests.py
├── prompts/
│   ├── jarvis_chat.txt
│   └── persona_composition.txt
├── wiki/
│   └── Progress-Log.md
├── main.py
├── requirements.txt
├── requirements-voice.txt
└── ReadMe.md
```

## Before You Start

Recommended Python version:

- `Python 3.11` or `Python 3.12`

Important notes:

- `ffmpeg` is needed for real Whisper transcription
- Coqui TTS may not be available on Python `3.14`
- if MySQL is unavailable, the app can fall back to SQLite
- do not leave `WHISPER_DEVICE=` or `COQUI_DEVICE=` blank in `.env`

## Setup

1. Create and activate a virtual environment.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies.

```bash
python3 -m pip install -r requirements.txt
```

3. If you want the full voice stack, also install the optional voice requirements.

```bash
python3 -m pip install -r requirements-voice.txt
```

4. Create your environment file.

```bash
cp .env.example .env
```

5. Configure your provider settings in `.env`.

For Groq:

```env
LLM_PROVIDER=groq
GROQ_API_KEY=your_key_here
```

For Bedrock:

```env
LLM_PROVIDER=bedrock
BEDROCK_MODEL_ID=us.anthropic.claude-haiku-4-5-20251001-v1:0
BEDROCK_REGION=us-west-2
AWS_PROFILE_NAME=your_profile_if_needed
```

For local smoke tests without an external LLM:

```env
LLM_PROVIDER=local
```

Local mode returns deterministic test replies. Use Groq or Bedrock for real assistant
quality.

Optional settings you may care about:

- `LLM_PROMPT_TEMPLATE_PATH=prompts/jarvis_chat.txt`
- `LLM_TOP_K=100`
- `LLM_TOP_P=0.95`
- `VOICE_UNDERSTANDING_PROVIDER=sensevoice`
- `ALLOW_SQLITE_FALLBACK=true`
- `WHISPER_MODEL_SIZE=base`
- `AUDIO_OUTPUT_DIR=generated_audio`

## Prompts And Context

Jarvis now follows the same simple pattern as the ETL PDF pipeline:

```text
prompt template + runtime context payload + user message -> LLM response
```

The default template lives at `prompts/jarvis_chat.txt`. It uses placeholders:

- `{{CONTEXT}}` or `{{PAYLOAD}}` for the injected JSON context
- `{{USER_MESSAGE}}` for the current user turn

The context payload includes recent conversation history, detected emotion,
persona-specific emotion guidance, user profile metadata, and any simulated wellness
signal. Edit the prompt file to change Jarvis' behavior without touching the Python code.

## Persona Guidance Cache

Jarvis uses a lightweight persona-guidance lookup before the LLM call:

```text
persona_id + detected_emotion -> response guidance
```

The source corpus lives in `corpus/`:

- `descriptors.csv`: descriptor-by-emotion guidance seeded from the research grid
- `personas.json`: six persona definitions and descriptor mixes
- `persona_guidance.json`: generated persona-by-emotion cache used at runtime

If you edit `corpus/descriptors.csv` or `corpus/personas.json`, regenerate the cache:

```bash
python3 scripts/build_persona_cache.py --force
```

Useful options:

- `--persona priya_shah`: rebuild one persona row
- `--emotion fear`: rebuild one emotion column
- `--provider bedrock`: use `prompts/persona_composition.txt` for model-based composition

The default builder uses deterministic local composition so the repo can be rebuilt
without AWS access during demos or tests.

Future expansion can add true vector RAG for larger uploaded documents:

```text
uploaded docs -> chunk -> embed -> vector DB -> retrieve top chunks -> LLM prompt
```

## How To Start The App

1. Activate the virtual environment if it is not already active.

```bash
source .venv/bin/activate
```

2. Start the FastAPI server.

```bash
uvicorn main:app --reload
```

3. Open the app in your browser.

- Browser UI: `http://127.0.0.1:8000/ui`
- Swagger UI: `http://127.0.0.1:8000/docs`
- Health check: `http://127.0.0.1:8000/health`

## First Sanity Checks

Run these after the server starts:

```bash
curl http://127.0.0.1:8000/
curl http://127.0.0.1:8000/health
```

What you want to see:

- `/` returns a simple app-running message
- `/health` returns `status: ok`
- `/health` shows the provider states for `llm`, `stt`, `emotion`, `tts`, and `database`

If you want a broader check, run:

```bash
python3 scripts/run_full_tests.py
```

That script checks:

- root endpoint
- health endpoint
- chat endpoint
- voice endpoint
- websocket endpoint
- generated output artifact
- SQLite persistence when SQLite is active

## Quick Manual API Checks

Text chat:

```bash
curl -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "demo",
    "persona_id": "default_danny",
    "message": "What time is it? Keep the answer short."
  }'
```

Text chat with simulated wellness input:

```bash
curl -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "demo",
    "persona_id": "priya_shah",
    "message": "I am feeling pretty stressed right now.",
    "wellness_signal": {
      "heart_rate": 108,
      "stress_level": "high",
      "source": "manual_demo"
    }
  }'
```

Voice upload with transcript override:

```bash
curl -X POST http://127.0.0.1:8000/api/voice \
  -F "session_id=voice-demo" \
  -F "persona_id=priya_shah" \
  -F "transcript_override=Please remember I like concise answers." \
  -F "wellness_heart_rate=92" \
  -F "wellness_stress_level=moderate" \
  -F "audio=@sample.wav"
```

Read recent history:

```bash
curl http://127.0.0.1:8000/api/history/demo
```

List available personas:

```bash
curl http://127.0.0.1:8000/api/personas
```

Clear a session manually:

```bash
curl -X DELETE http://127.0.0.1:8000/api/history/demo
```

## How To Use The Browser App

Open:

- `http://127.0.0.1:8000/ui`

The main areas of the UI are:

- `Emotion Monitor`
- `Session ID` and `Transcript Override`
- `Simulated Heart Rate` and `Simulated Stress Level`
- voice and text controls
- recorded clip and assistant output players
- conversation thread
- transcript, assistant reply, emotion details, output artifact, and raw JSON panels

The browser UI currently uses the default persona. API callers can pass `persona_id`
directly to `/api/chat` or `/api/voice`.

## What To Do When Using The App

### Basic Demo Flow

1. Open `/ui`.
2. Allow microphone access if the browser asks.
3. Keep the default `Session ID` or set your own.
4. Choose a simulated heart rate and stress level if you want the wellness demo active.
5. Start a voice turn in one of two ways:
   - say `Hey JayJay`
   - click `Start Voice Turn`
6. Speak your message.
7. Click `End Voice Turn` when you finish speaking.
8. Wait for the assistant response and audio output.
9. Watch the `Emotion Monitor`, `Conversation Thread`, and `Emotion Details` panels update.

### Text-Only Flow

1. Open `/ui`.
2. Type a message into `Text Message`.
3. Optionally set simulated heart rate and stress level.
4. Click `Send Text Turn`.
5. Review the assistant reply, raw JSON, and conversation thread.

### Quick Testing Flow Without Real STT

Use `Transcript Override` when you want to test the rest of the pipeline quickly without depending on Whisper transcription quality.

Example:

- set `Transcript Override` to `I am overwhelmed and need help focusing`
- click `Start Voice Turn`
- record any short clip
- click `End Voice Turn`

The app will use your override text as the transcript.

## What Each UI Control Means

- `Session ID`: groups conversation turns together
- `Transcript Override`: bypasses STT for faster testing
- `Simulated Heart Rate`: demo-only heart rate signal
- `Simulated Stress Level`: demo-only stress signal
- `Start Voice Turn`: starts recording manually
- `End Voice Turn`: stops recording and uploads the clip
- `Send Text Turn`: sends the text box content to `/api/chat`
- `New Conversation`: clears the current session history
- `Refresh History`: reloads recent turns for the active session
- `Playback Speed`: controls assistant audio playback speed

## What To Expect While The App Is Running

- the page tries to enable wake listening automatically
- the status line tells you whether wake listening is active
- the wake phrase is `Hey JayJay`
- if wake listening is unsupported, the manual voice button still works
- assistant audio auto-plays when a real `.wav` file is generated
- if TTS falls back, you may get a text artifact path instead of audio playback
- conversation history appears in the thread panel
- emotion details appear in the diagnostics cards
- app reboot clears stored chat history

## Sanity Check Checklist For Demo Day

Before demoing, confirm:

- `.venv` is active
- `uvicorn main:app --reload` starts cleanly
- `/health` returns `status: ok`
- your selected LLM provider is configured
- microphone permission is allowed in the browser
- `/ui` loads without missing styles or script errors
- text chat works
- voice upload works
- `Transcript Override` works
- the `Emotion Monitor` changes when different moods are tested
- `Conversation Thread` updates after each turn
- assistant audio plays, or fallback artifact output is shown

## Suggested Demo Scenarios

You can use the bundled demo kit for these scenarios:

```bash
python3 scripts/generate_demo_assets.py
python3 scripts/run_demo_scenarios.py
```

Useful demo kit files:

- `demo/scenarios.json`
- `demo/audio/stressed_focus.wav`
- `demo/audio/excited_win.wav`
- `demo/audio/sad_support.wav`
- `demo/audio/remember_preference.wav`
- `demo/README.md`

### Stressed user

- heart rate: `108`
- stress level: `high`
- message: `I have too much to do and I cannot focus.`

### Excited user

- heart rate: `96`
- stress level: `low`
- message: `I just finished my project and I am really excited.`

### Sad user

- heart rate: `74`
- stress level: `moderate`
- message: `I have been feeling down today and I need encouragement.`

### Preference test

- message: `Remember that I like short answers.`

Then follow with:

- `What should I do next?`

## Demo Kit Workflow

If you want a repeatable presentation flow without improvising each request:

1. Start the app with `uvicorn main:app --reload`.
2. Generate the demo assets if needed.
3. Run all bundled scenarios with `python3 scripts/run_demo_scenarios.py`.
4. Use the same values in the browser UI if you want to reenact a scenario visually.

Generate or regenerate the demo files:

```bash
python3 scripts/generate_demo_assets.py
```

Run every bundled scenario:

```bash
python3 scripts/run_demo_scenarios.py
```

Run one scenario only:

```bash
python3 scripts/run_demo_scenarios.py --scenario stressed_focus
```

The runner posts to `/api/voice` using:

- a bundled `.wav` file
- `transcript_override`
- `wellness_heart_rate`
- `wellness_stress_level`

This gives you a consistent prerecorded-style API demo even if you do not want to rely on live speech during rehearsal.

## Troubleshooting

### The app starts, but voice recording does not work

Check:

- browser microphone permission
- whether your browser supports speech recognition wake listening
- whether manual recording works with `Start Voice Turn`

### Wake phrase does not trigger recording

Things to know:

- the wake phrase is `Hey JayJay`
- some browsers do not support the wake-listening API well
- microphone access must be granted first
- if wake listening fails, use `Start Voice Turn`

### The assistant replies, but no audio plays

Possible causes:

- Coqui TTS is unavailable
- the app returned a text artifact instead of a `.wav`
- playback was blocked by the browser until user interaction

Check:

- `/health` for the `tts` provider status
- the `Output Artifact` panel
- the `generated_audio/` directory

### Whisper transcription is unreliable during testing

Use:

- `Transcript Override`

Also confirm:

- `ffmpeg` is installed
- your microphone clip is being uploaded correctly

### MySQL is down locally

The app can fall back to SQLite when:

- `ALLOW_SQLITE_FALLBACK=true`

Check `/health` to confirm which database is active.

### Old conversation history disappeared after restart

That is expected right now.

Current behavior:

- all chat history is cleared on app reboot

## Runtime Behavior Summary

- real audio can go through Whisper transcription
- `Transcript Override` bypasses STT intentionally for testing
- hybrid emotion inference combines audio and text cues
- persona guidance is retrieved from `corpus/persona_guidance.json`
- simulated wellness signals can influence response style
- recent session history is shown in the browser UI
- assistant playback defaults to `1.25x`
- TTS may fall back to text output if Coqui is unavailable

## Useful Commands

Start server:

```bash
uvicorn main:app --reload
```

Start server in local LLM mode for offline smoke tests:

```bash
LLM_PROVIDER=local uvicorn main:app --reload
```

Compile-check a few key files:

```bash
python3 -m py_compile app/api.py app/db.py app/services/llm.py app/services/orchestrator.py
```

Run the full test script:

```bash
python3 scripts/run_full_tests.py
```

Rebuild persona guidance:

```bash
python3 scripts/build_persona_cache.py --force
```

Generate demo assets:

```bash
python3 scripts/generate_demo_assets.py
```

Run demo scenarios:

```bash
python3 scripts/run_demo_scenarios.py
```

Inspect generated artifacts:

```bash
ls generated_audio
```

## Current Status

Working now:

- Groq responses
- AWS Bedrock responses
- Whisper STT
- hybrid emotion detection
- wake phrase browser flow
- manual browser voice turns
- text chat
- simulated wellness input
- session history endpoint and UI panel
- Coqui-backed TTS when available
- SQLite fallback when MySQL is unavailable

Known caveats:

- emotion detection can still be imperfect on nuanced speech
- wake listening depends on browser support
- websocket support is simple and not full realtime streaming audio
- TTS availability depends on the local Python environment

## Notes

The ongoing verification log lives in [Progress-Log.md](/Users/navsanya/Desktop/jarvis-assistant/wiki/Progress-Log.md).
