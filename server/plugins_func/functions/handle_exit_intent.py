from plugins_func.register import register_function, ToolType, ActionResponse, Action
from config.logger import setup_logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.connection import ConnectionHandler

TAG = __name__
logger = setup_logging()

handle_exit_intent_function_desc = {
    "type": "function",
    "function": {
        "name": "handle_exit_intent",
        "description": "Được gọi khi người dùng muốn kết thúc hội thoại hoặc thoát hệ thống",
        "parameters": {
            "type": "object",
            "properties": {
                "say_goodbye": {
                    "type": "string",
                    "description": "Lời chào tạm biệt thân thiện để kết thúc hội thoại",
                }
            },
            "required": ["say_goodbye"],
        },
    },
}


@register_function(
    "handle_exit_intent", handle_exit_intent_function_desc, ToolType.SYSTEM_CTL
)
def handle_exit_intent(conn: "ConnectionHandler", say_goodbye: str | None = None):
    # 处理退出意图
    try:
        if say_goodbye is None:
            say_goodbye = "Tạm biệt ba mẹ, chúc bé ngủ ngon và cả nhà vui vẻ nhé!"
        conn.close_after_chat = True
        logger.bind(tag=TAG).info(f"Ý định thoát đã được xử lý: {say_goodbye}")
        return ActionResponse(
            action=Action.RESPONSE, result="Ý định thoát đã được xử lý", response=say_goodbye
        )
    except Exception as e:
        logger.bind(tag=TAG).error(f"处理退出意图错误: {e}")
        return ActionResponse(
            action=Action.NONE, result="退出意图处理失败", response=""
        )
