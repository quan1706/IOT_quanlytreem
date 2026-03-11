import json
import aiohttp
from config.logger import setup_logging

TAG = "AIProcessor"

class AIProcessor:
    """
    Xử lý các tác vụ liên quan đến LLM (Groq) để phân tích ngôn ngữ tự nhiên
    và đưa ra gợi ý hành động.
    """

    @staticmethod
    async def analyze_intent_conversational(text, api_key, history=None):
        """
        Phân tích ý định của người dùng và trả về phản hồi tự nhiên kèm danh sách mã lệnh.
        Hỗ trợ nhiều lệnh cùng lúc (vd: 'cả 2' → ['phat_nhac', 'ru_vong']).
        history: list[dict] dạng [{"role":..., "content":...}]
        """
        if not api_key:
            return None

        from core.serverToClients.baby_actions import BabyCareAction

        # Lấy danh sách hành động từ Enum → admin sửa enum là AI tự cập nhật
        action_descriptions = BabyCareAction.get_ai_descriptions()
        # Lấy callback_data của STOP_ALL để biết lệnh "dừng"
        stop_action = BabyCareAction.STOP_ALL.callback_data.replace("confirm_", "")

        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        prompt = (
            "Bạn là trợ lý AI 'Tiểu Bảo' cho hệ thống giám sát trẻ em thông minh. "
            "Nhiệm vụ: Phân tích tin nhắn người dùng và đưa ra DANH SÁCH hành động phù hợp. "
            f"Các hành động (action) có thể — lấy từ cấu hình hệ thống:\n{action_descriptions}\n"
            "- none: Nếu không có hành động nào phù hợp.\n\n"
            "QUYẾT ĐỊNH QUAN TRỌNG:\n"
            f"- '{stop_action}' KHÔNG BAO GIỜ được kết hợp với bất kỳ lệnh nào khác. "
            f"Nếu người dùng muốn dừng → chỉ trả về ['{stop_action}'].\n"
            "- Nếu người dùng đồng thời yêu cầu 2 lệnh mâu thuẫn, hãy hỏi lại. "
            "Trong trường hợp này trả về action 'none' và reply là câu hỏi làm rõ.\n"
            "- Chỉ kết hợp các lệnh KHÔNG xung đột.\n\n"
            "Yêu cầu phản hồi:\n"
            "1. Phản hồi bằng tiếng Việt thân thiện, ngắn gọn.\n"
            "2. Trả về kết quả dưới định dạng JSON:\n"
            "{\"actions\": [\"mã_lệnh_1\", \"mã_lệnh_2\"], \"reply\": \"câu_trả_lời_tự_nhiên\"}\n"
            "Lưu ý: mã_lệnh là phần sau 'confirm_' trong callback_data, ví dụ 'confirm_phat_nhac' → 'phat_nhac'.\n"
            "Ví dụ một lệnh: {\"actions\": [\"ru_vong\"], \"reply\": \"Ru võng cho bé ngủ nhé!\"}\n"
            "Ví dụ nhiều lệnh: {\"actions\": [\"phat_nhac\", \"ru_vong\"], \"reply\": \"Vừa mở nhạc vừa ru võng cho bé nhé!\"}\n"
            "Ví dụ không có lệnh: {\"actions\": [\"none\"], \"reply\": \"\"}"
        )

        messages = [{"role": "system", "content": prompt}]
        if history:
            messages.extend(history[-6:])  # Giữ tối đa 6 tin nhắn gần nhất
        messages.append({"role": "user", "content": text})

        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": messages,
            "response_format": {"type": "json_object"}
        }

        logger = setup_logging()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload,
                                        timeout=aiohttp.ClientTimeout(total=15)) as response:
                    if response.status == 200:
                        data = await response.json()
                        content = data["choices"][0]["message"]["content"]
                        result = json.loads(content)

                        # Hỗ trợ cả format cũ (action) và mới (actions)
                        actions = result.get("actions") or ([result["action"]] if "action" in result else [])
                        reply = result.get("reply", "")

                        # Lọc bỏ "none"
                        valid_actions = [a for a in actions if a != "none"]
                        if valid_actions:
                            return {"actions": valid_actions, "reply": reply}
                        return None

                    else:
                        error_data = await response.text()
                        logger.bind(tag=TAG).error(f"Groq API Error: {response.status} - {error_data}")
        except Exception as e:
            logger.bind(tag=TAG).error(f"Lỗi khi gọi Groq AI: {e}")

        return None

    @staticmethod
    async def chat_conversational(text: str, api_key: str):
        """
        Trả lời tự nhiên theo phong cách trò chuyện khi không có intent điều khiển.
        Dùng khi người dùng chào hỏi, hỏi thăm, hoặc hỏi thông tin chung.
        """
        if not api_key:
            return None

        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        prompt = (
            "Bạn là 'Tiểu Bảo' – trợ lý AI chuyên về chăm sóc trẻ em cho hệ thống Smart Baby Care. "
            "Bạn CHỈ tư vấn các chủ đề liên quan đến em bé, trẻ sơ sinh, giấc ngủ, tiếng khóc, sức khỏe bé, "
            "và điều khiển thiết bị chăm sóc bé (nhạc ru, võng, camera). "
            "Nếu người dùng hỏi chủ đề ngoài lề (thời tiết, chính trị, ngoại hình...) hãy trả lời ngắn gọn "
            "theo phong cách thân thiện rồi khéo léo dẫn câu chuyện trở lại chủ đề chăm sóc bé. "
            "Phong cách: ngắn gọn (dưới 3 câu), ấm áp, dùng emoji phù hợp."
        )
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": text},
            ],
            "max_tokens": 150,
        }
        logger = setup_logging()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data["choices"][0]["message"]["content"].strip()
                    else:
                        error = await response.text()
                        logger.bind(tag=TAG).error(f"Groq Chat Error: {response.status} - {error}")
        except Exception as e:
            logger.bind(tag=TAG).error(f"Lỗi chat_conversational: {e}")
        return None

    @staticmethod
    async def execute_confirmed_action(command, chat_id, notifier):
        """Thực thi hành động sau khi người dùng xác nhận. Hỗ trợ nhiều lệnh (command='a+b')."""
        from core.serverToClients import DashboardUpdater, ESP32Commander
        from core.serverToClients.baby_actions import BabyCareAction
        from core.serverToClients.dashboard_updater import DASHBOARD_STATE
        import time

        commands = command.split("+")  # Hỗ trợ multi-action
        commander = ESP32Commander()

        results = []
        payloads = []
        for cmd in commands:
            success, esp_msg = await commander.execute_command(cmd)

            # Cập nhật log AI sang confirmed
            for l in reversed(DASHBOARD_STATE.get("ai_logs", [])):
                if cmd in l.get("action", "") and l["status"] == "suggested":
                    l["status"] = "confirmed"
                    break

            DashboardUpdater.add_action_log(
                action=cmd,
                source="telegram_ai",
                result="Thành công" if success else "Chờ kết nối ESP32",
            )

            payload = {
                "cmd": cmd,
                "source": "telegram_ai",
                "time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                "status": "dispatched" if success else "queued"
            }
            payloads.append(payload)
            # Lấy label từ BabyCareAction enum (tìm theo "confirm_<cmd>")
            action_obj = BabyCareAction.from_callback(f"confirm_{cmd}")
            label = action_obj.button_label if action_obj else cmd
            results.append(f"• {label}")

        # Reply Telegram tổng hợp
        labels_text = "\n".join(results)
        payloads_text = "\n".join(json.dumps(p, ensure_ascii=False) for p in payloads)
        reply = (
            f"✅ *Đã thực thi {len(commands)} lệnh:*\n{labels_text}\n\n"
            f"📦 *JSON gửi đến ESP32:*\n`{payloads_text}`"
        )
        await notifier.send_message(chat_id, reply)


    @staticmethod
    async def cancel_suggested_action(command, chat_id, notifier):
        """Hủy bỏ hành động AI gợi ý."""
        from core.serverToClients.dashboard_updater import DASHBOARD_STATE
        
        for l in reversed(DASHBOARD_STATE.get("ai_logs", [])):
            if l["action"] == command and l["status"] == "suggested":
                l["status"] = "cancelled"
                break
        
        await notifier.send_message(chat_id, "❌ *Đã hủy lệnh gợi ý từ AI.*")
