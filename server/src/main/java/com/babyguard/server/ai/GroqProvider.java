package com.babyguard.server.ai;

import com.babyguard.server.config.Config;
import com.babyguard.server.service.LogService;
import com.google.gson.Gson;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import okhttp3.*;

import java.io.IOException;

public class GroqProvider implements LLMProvider {
    private final OkHttpClient client = new OkHttpClient();
    private final Gson gson = new Gson();
    private static final String API_URL = "https://api.groq.com/openai/v1/chat/completions";

    @Override
    public String call(ChatRequest chatRequest) {
        if (Config.GROQ_API_KEY == null || Config.GROQ_API_KEY.isEmpty()) {
            return "none";
        }

        String jsonRequest = gson.toJson(chatRequest);
        LogService.addLog("[Groq] SEND JSON: " + jsonRequest);

        RequestBody body = RequestBody.create(
                jsonRequest,
                MediaType.parse("application/json"));

        Request request = new Request.Builder()
                .url(API_URL)
                .addHeader("Authorization", "Bearer " + Config.GROQ_API_KEY)
                .post(body)
                .build();

        try (Response response = client.newCall(request).execute()) {
            if (response.isSuccessful() && response.body() != null) {
                String responseBody = response.body().string();
                LogService.addLog("[Groq] RECV JSON: " + responseBody);
                JsonObject jsonResponse = JsonParser.parseString(responseBody).getAsJsonObject();
                return jsonResponse.getAsJsonArray("choices")
                        .get(0).getAsJsonObject()
                        .getAsJsonObject("message")
                        .get("content").getAsString().trim();
            }
        } catch (IOException e) {
            LogService.addLog("[GroqProvider] Error: " + e.getMessage());
        }
        return "none";
    }
}
