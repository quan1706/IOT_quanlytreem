from typing import List, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from core.connection import ConnectionHandler
from ..base import IntentProviderBase
from plugins_func.functions.play_music import initialize_music_handler
from config.logger import setup_logging
from core.utils.util import get_system_error_response
import re
import json
import hashlib
import time



TAG = __name__
logger = setup_logging()


class IntentProvider(IntentProviderBase):
    def __init__(self, config):
        super().__init__(config)
        self.llm = None
        self.promot = ""
        # 导入全局缓存管理器
        from core.utils.cache.manager import cache_manager, CacheType

        self.cache_manager = cache_manager
        self.CacheType = CacheType
        self.history_count = 4  # 默认使用最近4条对话记录

    def get_intent_system_prompt(self, functions_list: str) -> str:
        """
        Dựng Prompt hệ thống cho nhận diện ý định chuyên dụng.
        Mục tiêu: Chỉ trả về JSON, không được phép hội thoại.
        """
        functions_desc = "DANH SÁCH CÔNG CỤ KHẢ DỤNG:\n"
        for func in functions_list:
            func_info = func.get("function", {})
            name = func_info.get("name", "")
            desc = func_info.get("description", "")
            params = func_info.get("parameters", {})
            functions_desc += f"- {name}: {desc}\n"
            if params:
                functions_desc += f"  Params: {json.dumps(params)}\n"

        prompt = (
            "Bạn là một bộ máy phân loại ý định (Intent Classifier). Nhiệm vụ của bạn là phân tích câu nói của người dùng và chuyển đổi thành lệnh JSON.\n"
            "【QUY TẮC TỐI THƯỢNG】\n"
            "1. CHỈ TRẢ VỀ JSON. Cấm mọi văn bản giải thích, chào hỏi.\n"
            "2. Nếu là câu hỏi về thời gian, ngày tháng, thời tiết tại địa phương -> Trả về: {\"function_call\": {\"name\": \"result_for_context\"}}\n"
            "3. Nếu là yêu cầu điều khiển (nôi, quạt, nhạc, chụp ảnh) -> Trả về JSON gọi hàm tương ứng.\n"
            "4. Nếu chỉ là trò chuyện bình thường (chào hỏi, tâm sự) -> Trả về: {\"function_call\": {\"name\": \"continue_chat\"}}\n"
            "5. Nếu là yêu cầu thoát/tắt trợ lý -> Trả về gọi hàm 'handle_exit_intent'.\n\n"
            f"{functions_desc}\n\n"
            "【VÍ DỤ】\n"
            "User: Tắt nôi đi\n"
            "Return: {\"function_call\": {\"name\": \"cradle_control\", \"arguments\": {\"action\": \"off\"}}}\n\n"
            "User: Hôm nay mấy giờ rồi?\n"
            "Return: {\"function_call\": {\"name\": \"result_for_context\"}}\n\n"
            "User: Chào em, khỏe không?\n"
            "Return: {\"function_call\": {\"name\": \"continue_chat\"}}\n\n"
            "【CẢNH BÁO】Cấm trả về bất kỳ từ nào ngoài JSON. Chỉ dùng dấu ngoặc kép (\"), KHÔNG dùng dấu ngoặc đơn (') cho các khóa và giá trị. Phá vỡ cấu trúc này sẽ làm hỏng hệ thống."
        )
        return prompt

    def replyResult(self, text: str, original_text: str):
        try:
            llm_result = self.llm.response_no_stream(
                system_prompt=text,
                user_prompt="Dựa vào nội dung trên, hãy trả lời người dùng bằng giọng điệu của một bảo mẫu, ngắn gọn, súc tích và lễ phép. Người dùng hiện đang nói: "
                + original_text,
            )
            return llm_result
        except Exception as e:
            logger.bind(tag=TAG).error(f"Error in generating reply result: {e}")
            return get_system_error_response(self.config)

    async def detect_intent(
        self, conn: "ConnectionHandler", dialogue_history: List[Dict], text: str
    ) -> str:
        if not self.llm:
            raise ValueError("LLM provider not set")
        if conn.func_handler is None:
            return '{"function_call": {"name": "continue_chat"}}'

        # 记录整体开始时间
        total_start_time = time.time()

        # 打印使用的模型信息
        model_info = getattr(self.llm, "model_name", str(self.llm.__class__.__name__))
        logger.bind(tag=TAG).debug(f"Sử dụng mô hình nhận diện ý định: {model_info}")

        # 计算缓存键
        cache_key = hashlib.md5((conn.device_id + text).encode()).hexdigest()

        # 检查缓存
        cached_intent = self.cache_manager.get(self.CacheType.INTENT, cache_key)
        if cached_intent is not None:
            cache_time = time.time() - total_start_time
            logger.bind(tag=TAG).debug(
                f"Sử dụng ý định từ bộ nhớ đệm: {cache_key} -> {cached_intent}, thời gian: {cache_time:.4f} giây"
            )
            return cached_intent

        if self.promot == "":
            functions = conn.func_handler.get_functions()
            if hasattr(conn, "mcp_client"):
                mcp_tools = conn.mcp_client.get_available_tools()
                if mcp_tools is not None and len(mcp_tools) > 0:
                    if functions is None:
                        functions = []
                    functions.extend(mcp_tools)

            self.promot = self.get_intent_system_prompt(functions)

        music_config = initialize_music_handler(conn)
        music_file_names = music_config["music_file_names"]
        prompt_music = f"{self.promot}\n<musicNames>{music_file_names}\n</musicNames>"

        home_assistant_cfg = conn.config["plugins"].get("home_assistant")
        if home_assistant_cfg:
            devices = home_assistant_cfg.get("devices", [])
        else:
            devices = []
        if len(devices) > 0:
            hass_prompt = "\nDưới đây là danh sách các thiết bị thông minh trong nhà (vị trí, tên thiết bị, entity_id), có thể điều khiển qua Home Assistant:\n"
            for device in devices:
                hass_prompt += device + "\n"
            prompt_music += hass_prompt

        logger.bind(tag=TAG).debug(f"User prompt: {prompt_music}")

        # 构建用户对话历史的提示
        msgStr = ""

        # 获取最近的对话历史
        start_idx = max(0, len(dialogue_history) - self.history_count)
        for i in range(start_idx, len(dialogue_history)):
            msgStr += f"{dialogue_history[i].role}: {dialogue_history[i].content}\n"

        msgStr += f"User: {text}\n"
        user_prompt = f"current dialogue:\n{msgStr}"

        # 记录预处理完成时间
        preprocess_time = time.time() - total_start_time
        logger.bind(tag=TAG).debug(f"Thời gian tiền xử lý nhận diện ý định: {preprocess_time:.4f} giây")

        # 使用LLM进行意图识别
        llm_start_time = time.time()
        logger.bind(tag=TAG).debug(f"Bắt đầu gọi LLM nhận diện ý định, mô hình: {model_info}")

        try:
            intent = await self.llm.response_no_stream(
                system_prompt=prompt_music, user_prompt=user_prompt
            )
        except Exception as e:
            logger.bind(tag=TAG).error(f"Error in intent detection LLM call: {e}")
            return '{"function_call": {"name": "continue_chat"}}'

        # 记录LLM调用完成时间
        llm_time = time.time() - llm_start_time
        logger.bind(tag=TAG).debug(
            f"Hoàn thành nhận diện ý định bằng LLM, mô hình: {model_info}, thời gian gọi: {llm_time:.4f} giây"
        )

        # 记录后处理开始时间
        postprocess_start_time = time.time()

        # 清理和解析响应
        intent = intent.strip()
        # 尝试提取JSON部分
        match = re.search(r"\{.*\}", intent, re.DOTALL)
        if match:
            intent = match.group(0)

        # 记录总处理时间
        total_time = time.time() - total_start_time
        logger.bind(tag=TAG).debug(
            f"【Hiệu suất nhận diện ý định】Mô hình: {model_info}, Tổng thời gian: {total_time:.4f} giây, Gọi LLM: {llm_time:.4f} giây, Truy vấn: '{text[:20]}...'"
        )

        # 尝试解析为JSON
        try:
            intent_data = json.loads(intent)
            # 如果包含function_call，则格式化为适合处理的格式
            if "function_call" in intent_data:
                function_data = intent_data["function_call"]
                function_name = function_data.get("name")
                function_args = function_data.get("arguments", {})

                # 记录识别到的function call
                logger.bind(tag=TAG).info(
                    f"LLM nhận diện được ý định: {function_name}, tham số: {function_args}"
                )

                # 处理不同类型的意图
                if function_name == "result_for_context":
                    # 处理基础信息查询，直接从context构建结果
                    logger.bind(tag=TAG).info(
                        "Phát hiện ý định result_for_context, sẽ sử dụng thông tin ngữ cảnh để trả lời"
                    )

                elif function_name == "continue_chat":
                    # 处理普通对话
                    # 保留非工具相关的消息
                    clean_history = [
                        msg
                        for msg in conn.dialogue.dialogue
                        if msg.role not in ["tool", "function"]
                    ]
                    conn.dialogue.dialogue = clean_history

                else:
                    # 处理函数调用
                    logger.bind(tag=TAG).info(f"Phát hiện ý định gọi hàm: {function_name}")

            # 统一缓存处理和返回
            self.cache_manager.set(self.CacheType.INTENT, cache_key, intent)
            postprocess_time = time.time() - postprocess_start_time
            logger.bind(tag=TAG).debug(f"Thời gian hậu xử lý ý định: {postprocess_time:.4f} giây")
            return intent
        except json.JSONDecodeError:
            # 后处理时间
            postprocess_time = time.time() - postprocess_start_time
            logger.bind(tag=TAG).error(
                f"Không thể phân giải JSON ý định: {intent}, thời gian hậu xử lý: {postprocess_time:.4f} giây"
            )
            # 如果解析失败，默认返回继续聊天意图
            return '{"function_call": {"name": "continue_chat"}}'
