import uuid
import re
from typing import List, Dict
from datetime import datetime


class Message:
    def __init__(
        self,
        role: str,
        content: str = None,
        uniq_id: str = None,
        tool_calls=None,
        tool_call_id=None,
    ):
        self.uniq_id = uniq_id if uniq_id is not None else str(uuid.uuid4())
        self.role = role
        self.content = content
        self.tool_calls = tool_calls
        self.tool_call_id = tool_call_id


class Dialogue:
    def __init__(self):
        self.dialogue: List[Message] = []
        # Lấy thời gian hiện tại
        self.current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def put(self, message: Message):
        self.dialogue.append(message)

    def getMessages(self, m, dialogue):
        if m.tool_calls is not None:
            dialogue.append({"role": m.role, "tool_calls": m.tool_calls})
        elif m.role == "tool":
            dialogue.append(
                {
                    "role": m.role,
                    "tool_call_id": (
                        str(uuid.uuid4()) if m.tool_call_id is None else m.tool_call_id
                    ),
                    "content": m.content,
                }
            )
        else:
            dialogue.append({"role": m.role, "content": m.content})

    def get_llm_dialogue(self) -> List[Dict[str, str]]:
        # Gọi trực tiếp get_llm_dialogue_with_memory, truyền None làm memory_str
        # Điều này đảm bảo chức năng người nói có hiệu lực trong mọi đường dẫn gọi
        return self.get_llm_dialogue_with_memory(None, None)

    def update_system_message(self, new_content: str):
        """Cập nhật hoặc thêm tin nhắn hệ thống"""
        # Tìm tin nhắn hệ thống đầu tiên        system_msg = next((msg for msg in self.dialogue if msg.role == "system"), None)
        if system_msg:
            system_msg.content = new_content
        else:
            self.put(Message(role="system", content=new_content))

    def get_llm_dialogue_with_memory(
        self, memory_str: str = None, voiceprint_config: dict = None
    ) -> List[Dict[str, str]]:
        # Xây dựng hội thoại
        dialogue = []

        # Thêm thông báo hệ thống và bộ nhớ
        system_message = next(
            (msg for msg in self.dialogue if msg.role == "system"), None
        )

        if system_message:
            # Thông báo hệ thống cơ sở
            enhanced_system_prompt = system_message.content
            # Thay thế trình giữ chỗ thời gian
            enhanced_system_prompt = enhanced_system_prompt.replace(
                "{{current_time}}", datetime.now().strftime("%H:%M")
            )
 
            # Thêm mô tả cá nhân hóa cho người nói
            try:
                speakers = voiceprint_config.get("speakers", [])
                if speakers:
                    enhanced_system_prompt += "\n\n<speakers_info>"
                    for speaker_str in speakers:
                        try:
                            parts = speaker_str.split(",", 2)
                            if len(parts) >= 2:
                                name = parts[1].strip()
                                # Nếu mô tả trống, thì để là ""
                                description = (
                                    parts[2].strip() if len(parts) >= 3 else ""
                                )
                                enhanced_system_prompt += f"\n- {name}: {description}"
                        except:
                            pass
                    enhanced_system_prompt += "\n\n</speakers_info>"
            except:
                # Bỏ qua lỗi khi đọc cấu hình thất bại, không ảnh hưởng đến các chức năng khác
                pass
 
            # Sử dụng các biểu thức chính quy để khớp với thẻ <memory>, không quan tâm nội dung ở giữa là gì
            if memory_str is not None:
                enhanced_system_prompt = re.sub(
                    r"<memory>.*?</memory>",
                    f"<memory>\n{memory_str}\n</memory>",
                    enhanced_system_prompt,
                    flags=re.DOTALL,
                )
            dialogue.append({"role": "system", "content": enhanced_system_prompt})

        # Thêm cuộc đối thoại giữa người dùng và trợ lý
        for m in self.dialogue:
            if m.role != "system":  # Bỏ qua tin nhắn hệ thống gốc
                self.getMessages(m, dialogue)

        return dialogue
