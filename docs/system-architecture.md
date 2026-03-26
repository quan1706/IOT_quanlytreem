# System Architecture

## High-Level Flow
1. ESP32 device captures audio, sensor, and control events.
2. ESP32 connects to backend over WebSocket and uses HTTP for image-related routes.
3. Python backend processes events, updates shared state, and triggers AI or alerts.
4. Telegram bot and web dashboard expose controls and status to caregivers.
5. Backend can issue commands back to ESP32 devices.

## Main Runtime Services

### 1. Bootstrap Layer
- File: `server/app.py`
- Responsibilities:
  - Load config.
  - Resolve auth key.
  - Start GC manager.
  - Start WebSocket server.
  - Start HTTP server.
  - Keep process alive until shutdown.

### 2. WebSocket Layer
- File: `server/core/websocket_server.py`
- Responsibilities:
  - Accept device connections.
  - Parse `device-id`, `client-id`, and auth token.
  - Create `ConnectionHandler` per device session.
  - Hold shared AI/VAD/ASR/intent modules.

### 3. HTTP Layer
- File: `server/core/http_server.py`
- Responsibilities:
  - Handle cry alert uploads.
  - Handle frame and MJPEG ingest.
  - Serve dashboard routes.
  - Wire pose checks and Telegram bot startup.
  - Broadcast live frames to dashboard viewers.

### 4. Dashboard State Layer
- File: `server/core/serverToClients/dashboard_updater.py`
- Responsibilities:
  - Maintain `DASHBOARD_STATE`.
  - Track cry history, action logs, AI logs, sensor state, and pose.
  - Persist selected state to JSON files.

### 5. Telegram Layer
- Files: `server/core/telegram/*.py`
- Responsibilities:
  - Long-poll Telegram updates.
  - Route commands and callback buttons.
  - Send alerts, charts, confirmations, and voice replies.
  - Bridge caregiver actions to backend command execution.

### 6. AI Layer
- Key files:
  - `server/core/serverToClients/ai_processor.py`
  - `server/core/api/pose_handler.py`
  - `server/core/providers/`
- Responsibilities:
  - Intent parsing for chat.
  - Pose analysis from image uploads.
  - Speech recognition and text-to-speech.
  - Conversational responses and chart summaries.

## Interfaces

### Device -> Backend
- WebSocket for streaming audio/control session traffic.
- HTTP multipart for cry images and pose images.
- HTTP MJPEG/frame push for live camera stream.

### Backend -> User
- Telegram messages, callback actions, charts, voice replies.
- Browser dashboard HTML + JSON APIs.

### Backend -> Device
- Command dispatch through ESP32 command bridge.

## State and Persistence
- Shared runtime state is process-local and mutable.
- Long-term persistence is JSON-file based, not database-based.
- Restart may lose in-memory session state and chat history.

## Architecture Constraints
- Single-process design.
- Tight coupling around global state.
- Async tasks created ad hoc from handlers.
- No formal message broker.

## Key Risks
- Secret exposure in config.
- Shared state bottlenecks.
- Limited auth hardening for device connections.
- Outdated architectural docs in `README.md`.
