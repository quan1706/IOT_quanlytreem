import json
from config.logger import setup_logging
from core.utils.ai_provider import AIProvider

TAG = "AIProcessor"

class AIProcessor:
    """
    Xử lý các tác vụ liên quan đến LLM (Groq) để phân tích ngôn ngữ tự nhiên
    và đưa ra gợi ý hành động.
    """
    @staticmethod
    def _load_prompt(filename, **kwargs):
        """Tải prompt từ file markdown và apply các biến (nếu có)."""
        import os
        # Đường dẫn tuyệt đối đến thư mục prompts
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        prompt_path = os.path.join(base_dir, "config", "prompts", filename)
        
        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                content = f.read()
            if kwargs:
                return content.format(**kwargs)
            return content
        except Exception as e:
            setup_logging().bind(tag=TAG).error(f"Lỗi tải prompt {filename}: {e}")
            return ""

    @staticmethod
    async def analyze_intent_conversational(text, api_key, history=None, msg_config=None):
        """
        Phân tích ý định của người dùng và trả về phản hồi tự nhiên kèm danh sách mã lệnh.
        Hỗ trợ nhiều lệnh cùng lúc (vd: 'cả 2' → ['phat_nhac', 'ru_vong']).
        history: list[dict] dạng [{"role":..., "content":...}]
        """
        if not api_key:
            return None

        from core.utils.command_dispatcher import CommandDispatcher
        from core.serverToClients.baby_actions import BabyCareAction

        # Lấy danh sách hành động tổng hợp (Control + Query)
        action_descriptions = CommandDispatcher.get_all_ai_descriptions(msg_config)
        # Lấy callback_data của STOP_ALL để biết lệnh "dừng"
        stop_action = BabyCareAction.STOP_ALL.callback_data.replace("confirm_", "")

        prompt = AIProcessor._load_prompt(
            "intent_analysis.md",
            action_descriptions=action_descriptions,
            stop_action=stop_action
        )

        messages = [{"role": "system", "content": prompt}]
        if history:
            messages.extend(history[-6:])  # Giữ tối đa 6 tin nhắn gần nhất
        messages.append({"role": "user", "content": text})

        content, error = await AIProvider.call_llm(
            api_key=api_key,
            messages=messages,
            response_format={"type": "json_object"}
        )

        if content:
            try:
                result = json.loads(content)
                # Hỗ trợ cả format cũ (action) và mới (actions)
                actions = result.get("actions") or ([result["action"]] if "action" in result else [])
                reply = result.get("reply", "")

                # Lọc bỏ "none"
                valid_actions = [a for a in actions if a != "none"]
                if valid_actions:
                    return {"actions": valid_actions, "reply": reply}
            except Exception as e:
                setup_logging().bind(tag=TAG).error(f"Lỗi parse JSON từ AI: {e}")
        
        return None

    @staticmethod
    async def chat_conversational(text, api_key):
        """
        Chat bình thường nếu AI không nhận diện được hành động cụ thể.
        """
        if not api_key:
            return None

        prompt = AIProcessor._load_prompt("chat_conversational.md")
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": text},
        ]
        
        content, error = await AIProvider.call_llm(api_key, messages, max_tokens=150)
        return content

    @staticmethod
    async def execute_confirmed_action(command, chat_id, notifier, msg_config=None):
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
            label = action_obj.get_label(msg_config) if action_obj and msg_config else (action_obj.button_label if action_obj else cmd)
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
    async def cancel_suggested_action(command, chat_id, notifier, msg_config=None):
        """Hủy bỏ hành động AI gợi ý."""
        from core.serverToClients.dashboard_updater import DASHBOARD_STATE
        
        for l in reversed(DASHBOARD_STATE.get("ai_logs", [])):
            if l["action"] == command and l["status"] == "suggested":
                l["status"] = "cancelled"
                break
        
        msg = msg_config.get("callback", {}).get("ai_cancelled", "❌ *Đã hủy lệnh gợi ý từ AI.*") if msg_config else "❌ *Đã hủy lệnh gợi ý từ AI.*"
        await notifier.send_message(chat_id, msg)

    @staticmethod
    async def summarize_baby_condition(api_key, cry_data_summary, days):
        """
        Sử dụng AI để tóm tắt và đánh giá tình trạng của bé dựa trên dữ liệu tiếng khóc.
        cry_data_summary: chuỗi văn bản tóm tắt các điểm dữ liệu (VD: mốc thời gian, cường độ).
        """
        if not api_key:
            return "Trợ lý AI chưa sẵn sàng (thiếu API Key)."
        
        period_text = f"{days} ngày qua" if days > 1 else "24 giờ qua"
        prompt = AIProcessor._load_prompt(
            "baby_condition_summary.md",
            period_text=period_text,
            cry_data_summary=cry_data_summary
        )

        messages = [{"role": "system", "content": prompt}]
        content, error = await AIProvider.call_llm(api_key, messages, max_tokens=300)
        return content or "AI bận, không thể đưa ra đánh giá lúc này."

    @staticmethod
    async def answer_history_question(api_key, question, cry_data_summary):
        """
        Sử dụng AI để trả lời câu hỏi cụ thể của người dùng dựa trên dữ liệu lịch sử.
        """
        if not api_key:
            return "Trợ lý AI chưa sẵn sàng (thiếu API Key)."

        prompt = AIProcessor._load_prompt(
            "history_query.md",
            question=question,
            cry_data_summary=cry_data_summary
        )

        messages = [{"role": "system", "content": prompt}]
        content, error = await AIProvider.call_llm(api_key, messages, max_tokens=200)
        return content or "AI bận, không thể trả lời lúc này."
