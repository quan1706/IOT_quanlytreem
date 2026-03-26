# Codebase Summary

## Snapshot
- Repo type: Python backend + ESP32 firmware.
- Backend entrypoint: `server/app.py`.
- Interfaces: WebSocket, HTTP API, Telegram Bot API, browser dashboard.
- Persistence: JSON files under `server/data/` and runtime logs under `server/tmp/`.

## Top-Level Layout
- `server/`: main backend application.
- `hardware/`: ESP32 firmware projects.
- `docs/`: project documentation and implementation plans.
- `tools/`: auxiliary project tooling.

## Backend Layout
- `server/config/`: config loading, logging, prompt assets, Telegram message templates.
- `server/core/api/`: HTTP handlers for dashboard, vision, pose, OTA.
- `server/core/telegram/`: Telegram bot client, routing, alerts, keyboards.
- `server/core/serverToClients/`: shared dashboard state, AI orchestration, command dispatch.
- `server/core/providers/`: AI/ASR/classifier provider implementations.
- `server/core/utils/`: utilities, chart generation, prompts, GC manager, auth helpers.
- `server/plugins_func/`: plugin-based extra functions.
- `server/data/`: JSON data and generated artifacts.
- `server/tmp/`: runtime logs and temporary outputs.

## Runtime Model
- `app.py` loads merged config, starts GC manager, WebSocket server, HTTP server, stdin monitor.
- `SimpleHttpServer` exposes dashboard, cry, vision, and device-related routes.
- `WebSocketServer` accepts device connections and hands them to `ConnectionHandler`.
- Telegram bot is started from the HTTP server lifecycle.
- `DASHBOARD_STATE` acts as shared process-wide state.

## Important APIs
- Device alert ingestion: `POST /api/cry`
- MJPEG ingest: `POST /api/vision/mjpeg_push`
- Frame ingest: `POST /api/vision/frame`
- Pose analysis: `POST /api/vision/pose`
- Dashboard state: `GET /api/dashboard/state`
- Dashboard sensors: `GET /api/dashboard/sensors`
- Dashboard chart: `GET /api/dashboard/chart`
- Dashboard command: `POST /api/dashboard/command`
- Dashboard chat: `POST /api/dashboard/chat`

## Data Files
- `server/data/chart_history.json`: chart history.
- `server/data/ai_logs.json`: append-only AI log lines.
- `server/data/system_logs.json`: current system log snapshot.
- `server/data/cry_data.json`: cry-related data.

## Known Mismatches
- `README.md` still describes a Spring Boot design.
- Actual codebase is Python-only on the server side.
- Some config keys and comments still reflect inherited upstream code.
