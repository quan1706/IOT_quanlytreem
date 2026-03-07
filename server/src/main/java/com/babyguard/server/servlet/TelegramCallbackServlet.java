package com.babyguard.server.servlet;

import com.babyguard.server.service.ESP32Service;
import com.babyguard.server.service.LogService;
import com.babyguard.server.service.TelegramService;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import jakarta.servlet.ServletException;
import jakarta.servlet.annotation.WebServlet;
import jakarta.servlet.http.HttpServlet;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

import java.io.BufferedReader;
import java.io.IOException;

@WebServlet("/telegram/callback")
public class TelegramCallbackServlet extends HttpServlet {
    private final ESP32Service esp32Service = new ESP32Service();
    private final TelegramService telegramService = new TelegramService();

    @Override
    protected void doPost(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {

        StringBuilder buffer = new StringBuilder();
        String line;
        try (BufferedReader reader = request.getReader()) {
            while ((line = reader.readLine()) != null) {
                buffer.append(line);
            }
        }

        String json = buffer.toString();
        LogService.addFormattedLog("Telegram", "Webhook nhận dữ liệu", "Đang xử lý Callback...");

        try {
            JsonObject update = JsonParser.parseString(json).getAsJsonObject();
            if (update.has("callback_query")) {
                JsonObject callbackQuery = update.getAsJsonObject("callback_query");
                String data = callbackQuery.get("data").getAsString();
                String chatId = callbackQuery.getAsJsonObject("message").getAsJsonObject("chat").get("id")
                        .getAsString();

                // Lay ten nguoi dung
                String userName = "Unknown";
                if (callbackQuery.has("from")) {
                    JsonObject from = callbackQuery.getAsJsonObject("from");
                    userName = from.get("first_name").getAsString();
                    if (from.has("last_name")) {
                        userName += " " + from.get("last_name").getAsString();
                    }
                }

                // Tao class rieng de dong goi thong tin (theo yeu cau User)
                com.babyguard.server.model.TelegramAction actionObj = new com.babyguard.server.model.TelegramAction(
                        userName, "Bấm nút [" + data + "]", "Đang xử lý");

                // Ghi log tu class rieng thong qua method moi
                LogService.addActionLog(actionObj);

                // Gui phan hoi ve Telegram cho nguoi dung
                String feedbackMsg = "✅ Đã nhận lệnh: *" + data + "* từ " + userName;
                telegramService.sendMessage(chatId, feedbackMsg);

                // Thuc hien lenh ESP32
                if ("phat_nhac".equals(data)) {
                    esp32Service.sendCommand("phat_nhac");
                } else if ("ru_vong".equals(data)) {
                    esp32Service.sendCommand("ru_vong");
                } else if ("dung".equals(data)) {
                    esp32Service.sendCommand("dung");
                } else if ("hinh_anh".equals(data)) {
                    esp32Service.requestSnapshot();
                }

                // Cap nhat ket qua vao class rieng va ghi log
                LogService.addFormattedLog(userName, "Hoàn tất xử lý [" + data + "]", "Thành công");
            }
        } catch (Exception e) {
            LogService.addFormattedLog("Server", "Lỗi xử lý Telegram", "LỖI: " + e.getMessage());
        }

        response.setStatus(HttpServletResponse.SC_OK);
    }
}
