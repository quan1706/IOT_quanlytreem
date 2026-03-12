"""
serverToClients/baby_actions.py

Enum các hành động có thể thực hiện khi bé khóc.
Admin có thể thêm/sửa/xóa hành động tại đây.
AI (AIProcessor) và TelegramAlerts đều dùng chung Enum này để đưa ra gợi ý nhất quán.
"""
from enum import Enum


class BabyCareAction(Enum):
    """
    Danh sách các hành động dỗ bé có thể thực hiện.
    
    Cấu trúc mỗi action:
      value = (callback_data, button_label, description)
        - callback_data : chuỗi gửi về khi người dùng nhấn nút Telegram
        - button_label  : nhãn hiển thị trên nút Telegram
        - description   : mô tả ngắn cho AI sử dụng khi gợi ý
    """
    PLAY_MUSIC  = ("confirm_phat_nhac",  "🎵 Phát nhạc",  "Phát nhạc ru ngủ nhẹ nhàng dỗ bé")
    SWING       = ("confirm_ru_vong",    "🔄 Ru võng",    "Kích hoạt võng rung nhẹ để bé ngủ")
    FAN_ON      = ("confirm_bat_quat",   "🌬️ Bật quạt",    "Bật quạt làm mát phòng cho bé")
    FAN_OFF     = ("confirm_tat_quat",   "🛑 Tắt quạt",    "Tắt quạt khi phòng đã mát")
    SNAPSHOT    = ("confirm_hinh_anh",   "📸 Hình ảnh",   "Chụp ảnh mới từ camera để xem tình trạng bé")
    STOP_ALL    = ("confirm_dung",       "⏹ Dừng",        "Dừng tất cả thiết bị đang hoạt động")

    @property
    def callback_data(self) -> str:
        return self.value[0]

    @property
    def button_label(self) -> str:
        return self.value[1]

    @property
    def description(self) -> str:
        return self.value[2]

    def get_label(self, msg_config: dict) -> str:
        """Lấy label từ config nếu có, ngược lại dùng hardcoded."""
        return msg_config.get("actions", {}).get(self.callback_data, {}).get("label", self.button_label)

    def get_description(self, msg_config: dict) -> str:
        """Lấy description từ config nếu có, ngược lại dùng hardcoded."""
        return msg_config.get("actions", {}).get(self.callback_data, {}).get("desc", self.description)

    @classmethod
    def get_inline_keyboard(cls, cols: int = 2) -> dict:
        """
        Tạo inline_keyboard cho Telegram từ toàn bộ action trong Enum.
        
        Args:
            cols: Số nút mỗi hàng (mặc định 2).
        
        Returns:
            dict: reply_markup dạng inline_keyboard Telegram.
        """
        actions = list(cls)
        rows = []
        for i in range(0, len(actions), cols):
            row = [
                {"text": a.button_label, "callback_data": a.callback_data}
                for a in actions[i:i + cols]
            ]
            rows.append(row)
        return {"inline_keyboard": rows}

    @classmethod
    def get_ai_descriptions(cls, msg_config: dict = None) -> str:
        """
        Trả về danh sách mô tả cho AI sử dụng khi tư vấn hành động.
        """
        if msg_config:
            lines = [f"- {a.callback_data.replace('confirm_', '')}: {a.get_description(msg_config)}" for a in cls]
        else:
            lines = [f"- {a.callback_data.replace('confirm_', '')}: {a.description}" for a in cls]
        return "\n".join(lines)

    @classmethod
    def from_callback(cls, callback_data: str) -> "BabyCareAction | None":
        """Tìm action theo callback_data."""
        for a in cls:
            if a.callback_data == callback_data:
                return a
        return None
