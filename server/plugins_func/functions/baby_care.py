from plugins_func.register import register_function, ToolType, ActionResponse, Action
from core.serverToClients.esp32_commander import ESP32Commander
import asyncio

TAG = "BabyCareTools"

# 1. Định nghĩa công cụ Kiểm tra dáng bé
get_baby_pose_desc = {
    "type": "function",
    "function": {
        "name": "get_baby_pose",
        "description": "Chụp ảnh và phân tích tư thế nằm của bé (sấp hay ngửa).",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
}

@register_function("get_baby_pose", get_baby_pose_desc, ToolType.IOT_CTL)
def get_baby_pose(conn, **kwargs):
    try:
        # Gửi lệnh chụp ảnh đến ESP32
        asyncio.create_task(ESP32Commander().execute_command("capture_pose"))
        return ActionResponse(
            action=Action.RESPONSE, 
            result="Đã gửi lệnh chụp ảnh", 
            response="Dạ, ba mẹ đợi em một chút, em đang xem bé qua camera đây ạ!"
        )
    except Exception as e:
        return ActionResponse(action=Action.ERROR, response=f"Lỗi khi chụp ảnh: {str(e)}")

# 2. Định nghĩa công cụ Điều khiển Nôi
cradle_control_desc = {
    "type": "function",
    "function": {
        "name": "cradle_control",
        "description": "Điều khiển tắt nôi / bật nôi (ru võng). Chấp nhận: 'tắt đôi', 'dừng nuôi', 'tắt nuôi'.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["on", "off"],
                    "description": "Bật/Ru em ('on'), Tắt/Dừng/Yên ('off')."
                }
            },
            "required": ["action"],
        },
    },
}

@register_function("cradle_control", cradle_control_desc, ToolType.IOT_CTL)
def cradle_control(conn, action: str, **kwargs):
    cmd = "ru_vong" if action == "on" else "tat_noi"
    msg = "Dạ, em đang bật nôi cho bé rồi ạ!" if action == "on" else "Dạ, em đã tắt nôi rồi ạ."
    try:
        asyncio.create_task(ESP32Commander().execute_command(cmd))
        return ActionResponse(action=Action.RESPONSE, result=f"Đã thực hiện {cmd}", response=msg)
    except Exception as e:
        return ActionResponse(action=Action.ERROR, response=f"Lỗi điều khiển nôi: {str(e)}")

# 3. Định nghĩa công cụ Điều khiển Quạt
fan_control_desc = {
    "type": "function",
    "function": {
        "name": "fan_control",
        "description": "Điều khiển bật quạt / tắt quạt. Chấp nhận: 'bật hoạt', 'tắt hoạt'.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["on", "off"],
                    "description": "Bật/Mở ('on'), Tắt/Ngừng ('off')."
                }
            },
            "required": ["action"],
        },
    },
}

@register_function("fan_control", fan_control_desc, ToolType.IOT_CTL)
def fan_control(conn, action: str, **kwargs):
    cmd = "bat_quat" if action == "on" else "tat_quat"
    msg = "Dạ, em đã bật quạt cho bé mát rồi ạ!" if action == "on" else "Dạ, em đã tắt quạt rồi ạ."
    try:
        asyncio.create_task(ESP32Commander().execute_command(cmd))
        return ActionResponse(action=Action.RESPONSE, result=f"Đã thực hiện {cmd}", response=msg)
    except Exception as e:
        return ActionResponse(action=Action.ERROR, response=f"Lỗi điều khiển quạt: {str(e)}")
