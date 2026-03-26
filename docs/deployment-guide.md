# Deployment Guide

## Runtime Targets
- Local Windows execution via `run_server.bat`.
- Local or containerized Linux execution via Docker.

## Prerequisites
- Python 3.10 recommended.
- FFmpeg installed if audio features are needed.
- `libopus` available on target platform for Opus features.
- Network reachability between backend and ESP32 devices.

## Required Secrets
- Telegram bot token.
- Telegram chat id.
- Groq API key.
- Gemini API key.
- Any optional provider keys in plugins.

## Important Security Step
- Rotate every credential currently committed in `server/config.yaml` before any real deployment.
- Move secrets into `server/data/.config.yaml` or external secret management.

## Local Setup
1. Create `server/data/.config.yaml`.
2. Override sensitive keys and environment-specific values there.
3. Install Python dependencies from `server/requirements.txt`.
4. Start with `run_server.bat` or `python app.py` from `server/`.

## Minimal Config Areas To Override
- `telegram.bot_token`
- `telegram.chat_id`
- `server.websocket` / `server.vision_explain`
- `ASR.GroqASR.api_key`
- `LLM.GroqLLM.api_key`
- `LLM.GeminiLLM.api_key`
- any plugin API keys

## Local Run
```bash
cd server
python app.py
```

## Docker Run
```bash
docker compose up --build
```

## Exposed Ports
- `8000`: WebSocket server.
- `8003`: HTTP server and dashboard.

## Persistent Paths
- `server/data/`: runtime JSON data.
- `server/tmp/`: logs and temporary outputs.

## Health Checks
- Open dashboard on `http://<host>:8003/`.
- Confirm WebSocket endpoint is reachable on `ws://<host>:8000/xiaozhi/v1/`.
- Verify Telegram bot responds to `/start`.
- Confirm ESP32 can connect and send test telemetry.

## Common Failure Modes
- Missing `server/data/.config.yaml` causes startup failure.
- Missing FFmpeg or `libopus` disables some audio flows.
- Invalid API keys break Telegram, ASR, LLM, or pose analysis.
- Firewall or NAT blocks ESP32 connectivity.
