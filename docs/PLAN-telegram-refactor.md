# Telegram Server Logic Refactoring & Interactivity Plan

## Overview
The current Telegram bot implementation (`server/core/telegram/`) utilizes long-polling and a router to handle slash commands (`/start`, `/status`, `/baby_chart`, etc.) and AI conversational intents. While functional, it relies heavily on users typing commands or interacting via text. The objective of this plan is to consolidate the logic, make it more modular and callable, and significantly improve user interactivity by introducing structured menus (Reply Keyboards and Inline Keyboards) so users can tap to interact instead of typing.

## Project Type
BACKEND

## Success Criteria
1. The bot displays a persistent menu or an interactive inline keyboard for primary categories: 📊 Giám sát (Monitor), 🎛️ Điều khiển (Control), 🤖 AI & Cài đặt (AI & Settings).
2. **Dual Interaction Mode**: When chatting with natural language (e.g., pinging `@bot` in a telegram group), the bot responds to the query AND immediately renders the interactive inline menu below its response.
3. Existing commands (e.g., `/status`, `/baby_chart`, `/mode`, `/help`, `/setkey`, `/bat_quat`, `/tat_quat`, `ru_vong`, `tat_noi`, `dung`) are refactored into callable service functions that can be triggered by text commands, AI intent, or button clicks.
4. Bot commands are registered with Telegram (`setMyCommands`) for auto-completion.
5. No regressions in AI conversational abilities or command execution via ESP32.

## Tech Stack
- **Python 3 / aiohttp:** Existing async bot framework.
- **Telegram Bot API:** Utilizing `ReplyKeyboardMarkup`, `InlineKeyboardMarkup`, and `setMyCommands`.

## File Structure
Changes will be localized to existing files or new modular UI builders:
- `server/core/telegram/router.py`: Refactor text handling, integrate menu routing.
- `server/core/telegram/client.py`: Add `set_my_commands` and support for `ReplyKeyboardMarkup`.
- `server/core/telegram/menu_builder.py` [NEW]: Centralized factory for creating interactive keyboards (Reply & Inline).
- `server/core/telegram/handlers/` [NEW]: (Optional) Move specific logic (commands, callbacks) out of the monolithic router to specific handler modules.

## Task Breakdown

### TS-01: Update Telegram Client to Support Menus and Commands
- **Agent**: `backend-specialist`
- **Skills**: `python-patterns`, `api-patterns`
- **Priority**: P1
- **Dependencies**: None
- **INPUT**: `client.py`.
- **OUTPUT**: Add `set_my_commands` API wrapper in `client.py`. Ensure `send_message` handles both `InlineKeyboardMarkup` and `ReplyKeyboardMarkup` cleanly.
- **VERIFY**: Unit test or script to trigger `set_my_commands` and confirm 200 OK from Telegram API.

### TS-02: Implement Menu Builder (Interactive UI)
- **Agent**: `backend-specialist`
- **Skills**: `python-patterns`
- **Priority**: P1
- **Dependencies**: TS-01
- **INPUT**: `menu_builder.py` (to be created), `alerts.py`.
- **OUTPUT**: Functions to generate:
  1. Main Reply Keyboard / Persistent Inline Menu for categories: 
     - **📊 Giám sát**: Status, Baby Chart (24h/3d/7d), Cry History.
     - **🎛️ Điều khiển**: Quạt (Bật/Tắt), Nôi (Ru/Tắt), Dừng tất cả.
     - **🤖 AI & Cài đặt**: Help, Cài API Token (`/setkey`), Cài Mode (Auto/Manual).
  2. Map legacy hardcoded inline keyboards in `alerts.py` (e.g., AI Confirmations, Token limit, BabyCareAction) to utilize the new centralized Menu Builder.
- **VERIFY**: Run a dummy script to print the JSON output of the keyboards and ensure valid Telegram schema format.

### TS-03: Refactor Router Logic to Modular Handlers & Auto-Menu Attachment
- **Agent**: `backend-specialist`
- **Skills**: `clean-code`, `python-patterns`
- **Priority**: P2
- **Dependencies**: TS-02
- **INPUT**: `router.py`.
- **OUTPUT**: 
  - Extract the large if-else command block in `handle_message` into separate callable functions or a command registry.
  - Map the custom Reply Keyboard texts (e.g., "📊 Trạng thái") to their respective command logic (e.g., `_cmd_status`).
  - **Auto-Menu Logic**: Update `_handle_ai_message` (and general text handlers) to automatically attach the Interactive Inline Keyboard (from TS-02) as `reply_markup` when sending the conversational response back to the user.
- **VERIFY**: Send a text message mimicking a button press to the router and verify it routes to the correct internal handler. Ping the bot with a natural language text and verify the interactive menu is attached to the response.

### TS-04: Wire Up Auto-Complete Commands and Startup
- **Agent**: `backend-specialist`
- **Skills**: `python-patterns`
- **Priority**: P2
- **Dependencies**: TS-03
- **INPUT**: `bot.py`.
- **OUTPUT**: On bot `start()`, automatically call `set_my_commands` with a predefined list of commands (`help`, `status`, `chart`). 
- **VERIFY**: Start the bot server locally, verify terminal logs that commands were successfully registered with Telegram.

## ✅ PHASE X COMPLETE
- Lint: [ ] Pass
- Security: [ ] No critical issues
- Build: [ ] Success
- Date: [Pending]
