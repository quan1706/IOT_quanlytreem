"""
Package serverToClients
=======================
Tập trung mọi tác vụ giao tiếp từ Server -> Clients (Dashboard, ESP32).
Telegram đã được tách sang core.telegram package.

Usage:
    from core.serverToClients import DashboardUpdater, ESP32Commander
"""
from .dashboard_updater import DashboardUpdater, DASHBOARD_STATE
from .esp32_commander import ESP32Commander
from .ai_processor import AIProcessor
from .baby_actions import BabyCareAction

__all__ = [
    "DashboardUpdater",
    "DASHBOARD_STATE",
    "ESP32Commander",
    "AIProcessor",
    "BabyCareAction",
]

