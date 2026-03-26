# Project Overview PDR

## Product
Smart Baby Care is an IoT baby monitoring system that detects crying, monitors sleep posture, tracks room conditions, and lets caregivers react through Telegram and a local web dashboard.

## Current Reality
- The repo is not Spring Boot. The running backend is Python + asyncio + aiohttp.
- Main runtime lives in `server/`.
- ESP32 firmware lives in `hardware/esp32/`.
- Documentation in `README.md` is partially outdated and should not be treated as the source of truth.

## Goals
- Detect baby crying and notify caregivers quickly.
- Let caregivers trigger soothing actions remotely.
- Track temperature, humidity, cry history, and pose state.
- Provide simple interfaces through Telegram and browser dashboard.
- Keep the system extensible for more AI and device features.

## Primary Users
- Parents or caregivers using Telegram.
- Operators using the local dashboard.
- Developers maintaining Python backend and ESP32 firmware.

## Core Features
- Cry alert ingestion from ESP32-CAM via HTTP.
- Telegram bot with commands, inline actions, and AI-assisted replies.
- Dashboard with live state, logs, charts, and device controls.
- Pose detection using Gemini vision model.
- Environmental monitoring for temperature and humidity.
- WebSocket channel for device/server communication.

## Main Components
- `server/app.py`: process bootstrap and lifecycle.
- `server/core/http_server.py`: HTTP APIs, dashboard routes, vision routes, Telegram startup.
- `server/core/websocket_server.py`: device WebSocket entrypoint.
- `server/core/telegram/`: Telegram client, router, alerts, bot loop.
- `server/core/serverToClients/`: shared state, AI processor, ESP32 command bridge.
- `hardware/esp32/baby_care_esp32/`: primary ESP32 device firmware.
- `hardware/esp32/baby_care_stream_cam/`: streaming camera firmware.

## Non-Goals
- Cloud-native multi-tenant architecture.
- Strong secret management.
- Production-grade auth hardening.
- Formal database-backed persistence.

## Risks
- Secrets are committed in `server/config.yaml` and must be rotated.
- README and code diverge, which can mislead contributors.
- Shared in-memory state and JSON files limit scalability.
- Device auth and fallback defaults need hardening.

## Success Criteria
- ESP32 can connect and stream data.
- Cry and pose alerts reach Telegram reliably.
- Dashboard reflects near-real-time state.
- Caregivers can trigger commands and see results.
- Basic setup is reproducible from docs.
