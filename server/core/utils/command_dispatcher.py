from enum import Enum
from typing import Dict, List, Tuple

class CommandType(Enum):
    QUERY = "query"      # Thực thi ngay lập tức, lấy thông tin
    CONTROL = "control"  # Cần nút xác nhận từ người dùng

class CommandDispatcher:
    """
    Quản lý việc ánh xạ giữa AI intent và các lệnh hệ thống.
    """
    
    # Định nghĩa các lệnh hệ thống không nằm trong BabyCareAction (Enum điều khiển thiết bị)
    SYSTEM_COMMANDS: Dict[str, Tuple[CommandType, str]] = {
        "status": (CommandType.QUERY, "Kiểm tra trạng thái hệ thống: pin, kết nối, các chế độ... ⚙️"),
        "baby_chart_1": (CommandType.QUERY, "Xem biểu đồ tiếng khóc trong 24 giờ qua (1 ngày) 📊"),
        "baby_chart_3": (CommandType.QUERY, "Xem biểu đồ tiếng khóc trong 3 ngày vừa qua 📊"),
        "baby_chart_7": (CommandType.QUERY, "Xem biểu đồ tiếng khóc trong 1 tuần qua (7 ngày) 📊"),
        "cry_history_query": (CommandType.QUERY, "Trả lời các câu hỏi về lịch sử bé khóc (vd: 'đêm qua bé khóc mấy lần?', 'lần cuối bé khóc là khi nào?') 👶"),
        "help": (CommandType.QUERY, "Hướng dẫn sử dụng và danh sách các câu lệnh 📚"),
        "welcome": (CommandType.QUERY, "Giới thiệu về hệ thống Smart Baby Care 🍼"),
    }

    @classmethod
    def get_command_description(cls, cmd: str, msg_config: dict = None) -> str:
        """Lấy mô tả của lệnh cho AI."""
        if msg_config:
            desc = msg_config.get("commands", {}).get(cmd, {}).get("desc")
            if desc: return desc
            
        if cmd in cls.SYSTEM_COMMANDS:
            return cls.SYSTEM_COMMANDS[cmd][1]
        return ""

    @classmethod
    def get_command_type(cls, cmd: str) -> CommandType:
        """Xác định loại lệnh."""
        if cmd in cls.SYSTEM_COMMANDS:
            return cls.SYSTEM_COMMANDS[cmd][0]
        # Các lệnh từ BabyCareAction (phat_nhac, ru_vong...) mặc định là CONTROL
        return CommandType.CONTROL

    @classmethod
    def get_all_ai_descriptions(cls, msg_config: dict = None) -> str:
        """Tổng hợp mô tả tất cả các tool cho AI (bao gồm cả control actions)."""
        from core.serverToClients.baby_actions import BabyCareAction
        
        lines = []
        # 1. Các lệnh điều khiển thiết bị (Cần xác nhận)
        lines.append("--- NHÓM ĐIỀU KHIỂN THIẾT BỊ (Cần người dùng xác nhận sau đó):")
        lines.append(BabyCareAction.get_ai_descriptions(msg_config))
        
        # 2. Các lệnh truy vấn thông tin (Thực thi ngay)
        lines.append("\n--- NHÓM TRUY VẤN THÔNG TIN (Thực thi và trả kết quả ngay):")
        for cmd, (ctype, desc) in cls.SYSTEM_COMMANDS.items():
            final_desc = cls.get_command_description(cmd, msg_config)
            lines.append(f"- {cmd}: {final_desc}")
            
        return "\n".join(lines)
