package com.babyguard.server.ai;

import com.babyguard.server.config.Config;
import java.util.Arrays;

public class AIController {
    private final LLMProvider llmProvider;

    public AIController() {
        this.llmProvider = new GroqProvider();
    }

    public String analyzeIntent(String userText) {
        ChatMessage systemMsg = new ChatMessage("system",
                "Bạn là trợ lý AI cho hệ thống Baby Monitor thông minh. " +
                        "Nhiệm vụ của bạn là phân tích ý định (intent) của người dùng từ tin nhắn tiếng Việt. " +
                        "Các nhãn lệnh hợp lệ: \n" +
                        "- phat_nhac: Bật nhạc, phát nhạc ru bé, play music.\n" +
                        "- ru_vong: Bật võng, đưa nôi, swing.\n" +
                        "- dung: Dừng tất cả, tắt nhạc, dừng võng, stop.\n" +
                        "- hinh_anh: Xem camera, chụp ảnh bé, take photo.\n" +
                        "Quy tắc:\n" +
                        "1. Chỉ trả về DUY NHẤT mã lệnh (ví dụ: phat_nhac) hoặc 'none' nếu không rõ ràng.\n" +
                        "2. Không giải thích, không thêm văn bản thừa.");

        ChatMessage userMsg = new ChatMessage("user", userText);

        ChatRequest request = new ChatRequest(
                Config.GROQ_MODEL,
                Arrays.asList(systemMsg, userMsg));

        String result = llmProvider.call(request);
        return "none".equalsIgnoreCase(result) ? null : result.toLowerCase();
    }
}
