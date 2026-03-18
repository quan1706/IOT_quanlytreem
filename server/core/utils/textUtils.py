import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.connection import ConnectionHandler

TAG = __name__
EMOJI_MAP = {
    "😂": "funny",
    "😭": "crying",
    "😠": "angry",
    "😔": "sad",
    "😍": "loving",
    "😲": "surprised",
    "😱": "shocked",
    "🤔": "thinking",
    "😌": "relaxed",
    "😴": "sleepy",
    "😜": "silly",
    "🙄": "confused",
    "😶": "neutral",
    "🙂": "happy",
    "😆": "laughing",
    "😳": "embarrassed",
    "😉": "winking",
    "😎": "cool",
    "🤤": "delicious",
    "😘": "kissy",
    "😏": "confident",
}
EMOJI_RANGES = [
    (0x1F600, 0x1F64F),
    (0x1F300, 0x1F5FF),
    (0x1F680, 0x1F6FF),
    (0x1F900, 0x1F9FF),
    (0x1FA70, 0x1FAFF),
    (0x2600, 0x26FF),
    (0x2700, 0x27BF),
]


def get_string_no_punctuation_or_emoji(s):
    """Xóa các khoảng trắng, dấu câu và biểu tượng cảm xúc ở đầu và cuối chuỗi"""
    chars = list(s)
    # Xử lý các ký tự ở đầu
    start = 0
    while start < len(chars) and is_punctuation_or_emoji(chars[start]):
        start += 1
    # Xử lý các ký tự ở cuối
    end = len(chars) - 1
    while end >= start and is_punctuation_or_emoji(chars[end]):
        end -= 1
    return "".join(chars[start : end + 1])


def is_punctuation_or_emoji(char):
    """Kiểm tra ký tự có phải là khoảng trắng, dấu câu chỉ định hoặc biểu tượng cảm xúc hay không"""
    # Định nghĩa các dấu câu tiếng Trung và tiếng Anh cần xóa (bao gồm cả toàn chiều rộng/nửa chiều rộng)
    punctuation_set = {
        "，",
        ",",  # Dấu phẩy tiếng Trung + Dấu phẩy tiếng Anh
        "。",
        ".",  # Dấu chấm tiếng Trung + Dấu chấm tiếng Anh
        "！",
        "!",  # Dấu chấm than tiếng Trung + Dấu chấm than tiếng Anh
        "“",
        "”",
        '"',  # Dấu ngoặc kép tiếng Trung + Dấu ngoặc kép tiếng Anh
        "：",
        ":",  # Dấu hai chấm tiếng Trung + Dấu hai chấm tiếng Anh
        "-",
        "－",  # Dấu gạch nối tiếng Anh + Dấu gạch ngang toàn chiều rộng tiếng Trung
        "、",  # Dấu phẩy liệt kê tiếng Trung
        "[",
        "]",  # Dấu ngoặc vuông
        "【",
        "】",  # Dấu ngoặc vuông tiếng Trung
    }
    if char.isspace() or char in punctuation_set:
        return True
    return is_emoji(char)


async def get_emotion(conn: "ConnectionHandler", text):
    """Lấy thông báo cảm xúc từ trong văn bản"""
    emoji = "🙂"
    emotion = "happy"
    for char in text:
        if char in EMOJI_MAP:
            emoji = char
            emotion = EMOJI_MAP[char]
            break
    try:
        await conn.websocket.send(
            json.dumps(
                {
                    "type": "llm",
                    "text": emoji,
                    "emotion": emotion,
                    "session_id": conn.session_id,
                }
            )
        )
    except Exception as e:
        conn.logger.bind(tag=TAG).warning(f"Gửi biểu tượng cảm xúc thất bại, lỗi: {e}")
    return


def is_emoji(char):
    """Kiểm tra ký tự có phải là biểu tượng cảm xúc (emoji) hay không"""
    code_point = ord(char)
    return any(start <= code_point <= end for start, end in EMOJI_RANGES)


def check_emoji(text):
    """Xóa tất cả biểu tượng cảm xúc (emoji) trong văn bản"""
    return "".join(char for char in text if not is_emoji(char) and char != "\n")
