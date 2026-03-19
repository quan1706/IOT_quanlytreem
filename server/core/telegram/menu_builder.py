"""
core/telegram/menu_builder.py

Centralized factory cho Reply và Inline keyboards để tăng tính tương tác của bot.
"""

def get_main_reply_keyboard():
    """Trả về Persistent Reply Keyboard hiển thị dưới ô chat."""
    return {
        "keyboard": [
            [{"text": "📊 Giám sát"}, {"text": "🎛️ Điều khiển"}],
            [{"text": "🤖 AI & Cài đặt"}]
        ],
        "resize_keyboard": True,
        "is_persistent": True
    }

def get_monitor_inline_keyboard():
    """Inline menu cho nhóm Giám sát"""
    return {
        "inline_keyboard": [
            [
                {"text": "📝 Trạng thái chung", "callback_data": "menu_status"},
                {"text": "🕰️ Lịch sử khóc", "callback_data": "menu_cry_history"}
            ],
            [
                {"text": "📈 Biểu đồ 24h", "callback_data": "menu_chart_1"},
                {"text": "📈 Biểu đồ 7 ngày", "callback_data": "menu_chart_7"}
            ],
            [
                {"text": "📊 Biểu đồ Tổng hợp (Khóc & Temp)", "callback_data": "menu_chart_combined"}
            ],
            [
                {"text": "⬅️ Quay lại Menu chính", "callback_data": "menu_start"}
            ]
        ]
    }

def get_control_inline_keyboard():
    """Inline menu cho nhóm Điều khiển ESP32"""
    return {
        "inline_keyboard": [
            [
                {"text": "Bật Quạt 🌬️", "callback_data": "confirm_bat_quat"},
                {"text": "Tắt Quạt 🛑", "callback_data": "confirm_tat_quat"}
            ],
            [
                {"text": "Ru Nôi (Swing) 🛏️", "callback_data": "confirm_ru_vong"},
                {"text": "Dừng Nôi 🛑", "callback_data": "confirm_tat_noi"}
            ],
            [
                {"text": "🛑 DỪNG TẤT CẢ", "callback_data": "confirm_dung"}
            ],
            [
                {"text": "⬅️ Quay lại Menu chính", "callback_data": "menu_start"}
            ]
        ]
    }

def get_settings_inline_keyboard():
    """Inline menu cho cài đặt và AI"""
    return {
        "inline_keyboard": [
            [
                {"text": "🛠️ Cài Mode Auto", "callback_data": "menu_mode_auto"},
                {"text": "🛠️ Cài Mode Manual", "callback_data": "menu_mode_manual"}
            ],
            [
                {"text": "🧪 Dữ liệu mẫu: BẬT", "callback_data": "menu_mock_on"},
                {"text": "🧪 Dữ liệu mẫu: TẮT", "callback_data": "menu_mock_off"}
            ],
            [
                {"text": "🔑 Hướng dẫn Set API Key", "callback_data": "menu_help_setkey"},
                {"text": "📚 Help / Hướng dẫn", "callback_data": "menu_help"}
            ],
            [
                {"text": "⬅️ Quay lại Menu chính", "callback_data": "menu_start"}
            ]
        ]
    }

def get_ai_confirmation_keyboard(intent: str, btn_ok: str = "🚀 Confirm", btn_no: str = "❌ Cancel"):
    """Bàn phím xác nhận AI"""
    return {
        "inline_keyboard": [
            [
                {"text": btn_ok, "callback_data": f"ai_confirm_{intent}"},
                {"text": btn_no, "callback_data": f"ai_cancel_{intent}"}
            ]
        ]
    }

def get_chart_action_keyboard(target: str):
    """Bàn phím dưới biểu đồ để gọi AI nhận xét. target là days (vd: 1, 7) hoặc 'combined'"""
    return {
        "inline_keyboard": [
            [
                {"text": "🔍 Nhận xét từ AI (Tiểu Bảo)", "callback_data": f"menu_ai_analyze_{target}"}
            ]
        ]
    }

def get_token_limit_keyboard(btn_label: str, local_ip: str):
    """Bàn phím cảnh báo token"""
    return {
        "inline_keyboard": [
            [{"text": btn_label, "url": f"http://{local_ip}:8003/"}]
        ]
    }

def get_unified_inline_menu():
    """Inline menu tổng hợp dùng khi chat tự nhiên với AI."""
    return {
        "inline_keyboard": [
            [
                {"text": "📊 Giám sát", "callback_data": "menu_cat_monitor"},
                {"text": "🎛️ Điều khiển", "callback_data": "menu_cat_control"}
            ],
            [
                {"text": "🤖 AI & Cài đặt", "callback_data": "menu_cat_setting"}
            ]
        ]
    }
