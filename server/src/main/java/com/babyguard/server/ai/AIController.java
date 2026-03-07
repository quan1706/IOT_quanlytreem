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
                "Analyze intent for Baby Monitor. Labels: phat_nhac, ru_vong, dung, hinh_anh. " +
                        "Return ONLY the code or 'none'. No explanation.");

        ChatMessage userMsg = new ChatMessage("user", userText);

        ChatRequest request = new ChatRequest(
                Config.GROQ_MODEL,
                Arrays.asList(systemMsg, userMsg));

        String result = llmProvider.call(request);
        return "none".equalsIgnoreCase(result) ? null : result.toLowerCase();
    }
}
