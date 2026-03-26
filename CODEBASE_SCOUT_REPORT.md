# Codebase Scout Report: Baby Cry Detector & Smart Soother

## Project Overview
Baby Cry Detector & Smart Soother is an IoT system designed to detect infant crying and automatically respond with soothing actions. The system consists of hardware (ESP32-CAM with sensors/AI) that detects crying and sends alerts to a backend server, which then notifies caregivers via Telegram and allows them to trigger soothing actions remotely.

## Technology Stack
- **Language**: Python 3.10+ 
- **Web Framework**: aiohttp (HTTP/WebSocket server)
- **AI/ML**: 
  - Speech Recognition: FunASR, Silero VAD, Groq Whisper
  - LLMs: Gemini (Google), Groq LLMs (Llama, etc.), OpenAI (fallback)
  - TTS: EdgeTTS (Microsoft)
  - Vision: Gemini for pose detection (prone/supine)
- **Communication**: 
  - Telegram Bot API for user interface
  - HTTP/JSON for ESP32-server communication
  - WebSocket for real-time dashboard updates
- **Dependencies**: See requirements.txt (torch, torchaudio, numpy, funasr, silero_vad, openai, google-generativeai, edge_tts, websockets, httpx, aiohttp, cozepy, mem0ai, powermem, mcp, etc.)
- **Configuration**: YAML-based (config.yaml with override via data/.config.yaml)

## Architecture
### Core Components
1. **app.py** - Main application entry point
2. **core/http_server.py** - HTTP/WebSocket server handling all API endpoints
3. **core/telegram/** - Telegram bot implementation with interactive menus
4. **core/serverToClients/** - Inter-client communication layer
   - dashboard_updater.py - Central state management (singleton)
   - esp32_commander.py - Sending commands to ESP32 devices
   - ai_processor.py - AI processing and intent recognition
5. **core/api/** - API endpoint handlers
   - dashboard_handler.py - Dashboard/Web interface APIs
   - pose_handler.py - Baby pose detection using Gemini AI
   - vision_handler.py - Vision explanation via MCP
   - ota_handler.py - Over-the-air update capabilities
6. **core/handle/** - Message handlers for various intents and commands
7. **core/plugins_func/** - Extensible plugin system (music, weather, Home Assistant, etc.)
8. **models/** - AI models (SenseVoiceSmall for ASR, Silero VAD for voice activity)

### Data Flow
1. **Detection**: ESP32-CAM detects crying → sends image to `/api/cry` endpoint
2. **Alerting**: Server processes image → sends Telegram alert with action buttons
3. **Interaction**: User responds via Telegram buttons or text commands
4. **Action**: Server sends command to ESP32 → ESP32 executes action (music, swing, stop)
5. **Monitoring**: Dashboard receives real-time updates via WebSocket/HTTP
6. **AI Processing**: Conversational AI and vision analysis handled by LLM services

## Key Features
- **Cry Detection**: Real-time audio processing with voice activity detection
- **Telegram Interface**: Interactive bot with inline keyboards and persistent menus
- **Baby Pose Detection**: AI-powered detection of dangerous sleeping positions (prone/supine) using Gemini
- **Environmental Monitoring**: Temperature and humidity tracking
- **Voice Control**: Wake-word activation ("xin chào bé", "baby guard")
- **Device Control**: Remote control of connected devices (music players, cradles, fans)
- **Conversational AI**: Natural language interactions for baby care advice
- **OTA Updates**: Over-the-air firmware updates for ESP32 devices
- **Plugin System**: Extensible architecture for adding features (weather, news, time, smart home)
- **Dashboard**: Real-time web interface for monitoring and control

## File Structure
```
IOT_quanlytreem/
├── server/
│   ├── app.py                  # Application entry point
│   ├── config.yaml             # Main configuration
│   ├── requirements.txt        # Python dependencies
│   ├── core/
│   │   ├── http_server.py      # HTTP/WebSocket server
│   │   ├── telegram/           # Telegram bot implementation
│   │   ├── api/                # API handlers
│   │   │   ├── dashboard_handler.py
│   │   │   ├── pose_handler.py
│   │   │   ├── vision_handler.py
│   │   │   └── ota_handler.py
│   │   ├── handle/             # Message handlers
│   │   ├── serverToClients/    # Inter-client communication
│   │   │   ├── dashboard_updater.py  # Central state
│   │   │   ├── esp32_commander.py    # ESP32 communication
│   │   │   └── ai_processor.py       # AI processing
│   │   └── plugins_func/       # Plugin functions (weather, music, HA, etc.)
│   ├── config/                 # Configuration modules
│   ├── data/                   # Data storage (logs, charts, configs)
│   ├── models/                 # AI models (SenseVoiceSmall, Silero VAD)
│   └── tmp/                    # Temporary files and logs
├── hardware/
│   └── esp32/                  # ESP32 firmware source
├── docs/                       # Documentation and plans
└── tools/                      # Utility tools
```

## Configuration Requirements
- **Python 3.10+** (notes indicate 3.13 works with version constraints removed)
- **API Keys Required** for full functionality:
  - Telegram Bot Token (from @BotFather)
  - Groq API Key (for ASR and fast LLM)
  - Google Gemini API Key (for vision and conversational AI)
  - OpenAI API Key (fallback LLM/TTS)
  - Weather API Key (for weather plugin)
- **Network**: ESP32 devices must be reachable from server (same LAN or via port forwarding)
- **Timezone**: Configurable (default UTC+7 for Vietnam)
- **Override Config**: Create `data/.config.yaml` to override settings in `config.yaml`

## APIs and Interfaces
### ESP32 → Server
- `POST /api/cry` - Cry detection with image (multipart/form-data)
- `POST /api/vision/frame` - Regular video frame
- `POST /api/vision/mjpeg_push` - MJPEG stream
- `POST /api/vision/log` - Log messages

### Server → ESP32
- `POST http://<ESP32-IP>/command` - Control commands (JSON: `{"cmd": "<command>"}`)
  - Commands: `phat_nhac` (play music), `ru_vong` (swing cradle), `tat_quat` (fan off), `bat_quat` (fan on), `dung` (stop all)

### Telegram Bot
- Receives callback queries from inline buttons
- Sends photo alerts with action menus
- Processes natural language commands

### Dashboard/Web Interface
- `GET /` - Serve dashboard HTML
- `GET /api/dashboard/state` - Full dashboard state
- `GET /api/dashboard/logs` - System logs
- `GET /api/dashboard/sensors` - Live sensor data (temp, humidity, cry status, pose)
- `GET /api/dashboard/chart?range=1h|5h|24h` - Historical data
- `POST /api/dashboard/command` - Send commands to ESP32
- `POST /api/dashboard/chat` - AI chat interface
- `POST /api/dashboard/mode` - Set operating mode (manual/auto)
- `POST /api/dashboard/apikey` - Update API keys

### MCP (Model Context Protocol)
- `GET/POST /mcp/vision/explain` - Vision explanation endpoint

## Deployment and Runtime
### Startup Methods
- `python app.py` - Direct execution
- `run_server.bat` - Windows batch file

### Ports
- **WebSocket**: Port 8000 (`ws://ip:8000/xiaozhi/v1/`)
- **HTTP**: Port 8003 (`http://ip:8003/`)
- **OTA**: Available at `/xiaozhi/ota/`

### Runtime Processes
The application runs multiple concurrent asyncio tasks:
1. HTTP Server (handles HTTP and WebSocket connections)
2. Telegram Bot (long polling for messages and callbacks)
3. Periodic Pose Check (every 5 minutes - sends `capture_hq` command to ESP32)
4. Garbage Collection Manager (every 5 minutes for memory cleanup)
5. Stdin Monitor (console command processing)

### Logging and Data Persistence
- **Logs**: 
  - `server/tmp/server.log` - Main server log
  - `server/data/system_logs.json` - System activity logs
  - `server/data/ai_logs.json` - AI interaction logs
- **Historical Data**:
  - `server/data/chart_history.json` - Sensor history for charts
  - `server/data/captures/` - Saved image captures
- **State Management**: 
  - Central `DASHBOARD_STATE` singleton in `dashboard_updater.py`
  - In-memory state with periodic persistence to JSON files

## Important Implementation Notes
1. **README Discrepancy**: The README mentions Spring Boot but the actual implementation is entirely in Python
2. **Pose Detection System**: 
   - Uses Gemini AI to detect dangerous sleeping positions (prone/supine)
   - Integrated into both periodic checks and manual triggers
   - Results stored in dashboard state and reflected in Telegram `/status` command
3. **Plugin Architecture**: 
   - Highly extensible system for adding new capabilities
   - Examples: weather, news, time, Home Assistant integration
   - Plugins located in `core/plugins_func/functions/`
4. **Safety Features**:
   - Cry detection cooldown (60 seconds) to prevent alert spam
   - Validation for all incoming data and commands
   - Error handling and fallback mechanisms throughout
5. **Extensibility**:
   - Modular design allows easy addition of new API endpoints
   - Plugin system for feature extension without core modifications
   - Configuration-driven behavior for easy customization

This system represents a sophisticated IoT solution combining edge detection (ESP32), cloud processing (Python server), and user interaction (Telegram) to provide comprehensive baby monitoring and care capabilities.