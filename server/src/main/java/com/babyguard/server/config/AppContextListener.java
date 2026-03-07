package com.babyguard.server.config;

import com.babyguard.server.service.LogService;
import jakarta.servlet.ServletContextEvent;
import jakarta.servlet.ServletContextListener;
import jakarta.servlet.annotation.WebListener;
import okhttp3.*;

import java.io.IOException;

@WebListener
public class AppContextListener implements ServletContextListener {

    private final OkHttpClient client = new OkHttpClient();

    @Override
    public void contextInitialized(ServletContextEvent sce) {
        LogService.addLog("[System] Server đang khởi động...");

        if (Config.TELEGRAM_BOT_TOKEN == null || Config.SERVER_URL == null || Config.SERVER_URL.isEmpty()) {
            LogService.addLog("[Webhook] Bỏ qua tự động đăng ký (Thiếu TOKEN hoặc SERVER_URL)");
            return;
        }

        registerWebhook();
    }

    private void registerWebhook() {
        String webhookUrl = Config.SERVER_URL + "/telegram/callback";
        String telegramApiUrl = "https://api.telegram.org/bot" + Config.TELEGRAM_BOT_TOKEN
                + "/setWebhook?url=" + webhookUrl;

        LogService.addLog("[Webhook] Đang tự động đăng ký với Telegram: " + webhookUrl);

        Request request = new Request.Builder()
                .url(telegramApiUrl)
                .get()
                .build();

        client.newCall(request).enqueue(new Callback() {
            @Override
            public void onFailure(Call call, IOException e) {
                LogService.addLog("[Webhook] Đăng ký THẤT BẠI: " + e.getMessage());
            }

            @Override
            public void onResponse(Call call, Response response) throws IOException {
                if (response.isSuccessful()) {
                    LogService.addLog("[Webhook] Đăng ký THÀNH CÔNG!");
                } else {
                    LogService.addLog("[Webhook] Đăng ký THẤT BẠI - Mã: " + response.code());
                }
                response.close();
            }
        });
    }

    @Override
    public void contextDestroyed(ServletContextEvent sce) {
        LogService.addLog("[System] Server đang dừng...");
    }
}
