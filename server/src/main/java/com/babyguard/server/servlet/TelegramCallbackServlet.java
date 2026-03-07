package com.babyguard.server.servlet;

import com.babyguard.server.config.Config;
import com.babyguard.server.ai.AIController;
import com.babyguard.server.ai.AIChatLog;
import com.babyguard.server.model.TelegramAction;
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

@WebServlet(urlPatterns = "/telegram/callback", loadOnStartup = 1)
public class TelegramCallbackServlet extends HttpServlet {
    private final ESP32Service esp32Service = new ESP32Service();
    private final TelegramService telegramService = new TelegramService();
    private final AIController aiController = new AIController();
    private AIChatLog currentPendingLog = null;

    @Override
    public void init() throws ServletException {
        super.init();
        LogService.addLog("[TelegramServlet] Servlet đã khởi tạo và sẵn sàng tại /telegram/callback");
    }

    @Override
    protected void doGet(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {
        LogService.addLog("[Telegram] Nhận yêu cầu GET kiểm tra từ: " + request.getRemoteAddr());
        response.setContentType("text/plain;charset=UTF-8");
        response.getWriter().write("Telegram Callback Endpoint is ALIVE! Token length: " +
                (Config.TELEGRAM_BOT_TOKEN != null ? Config.TELEGRAM_BOT_TOKEN.length() : "NULL"));
    }

    @Override
    protected void doPost(HttpServletRequest request, HttpServletResponse response)
            throws ServletException, IOException {

        LogService.addLog("[Telegram] Nhận yêu cầu POST từ: " + request.getRemoteAddr());

        StringBuilder buffer = new StringBuilder();
        String line;
        try (BufferedReader reader = request.getReader()) {
            while ((line = reader.readLine()) != null)
                buffer.append(line);
        }

        String json = buffer.toString();
        LogService.addLog("[Telegram] RECV JSON: " + (json.isEmpty() ? "(Empty Body)" : json));
        try {
            if (json == null || json.isEmpty()) {
                response.setStatus(HttpServletResponse.SC_OK);
                return;
            }
            JsonObject update = JsonParser.parseString(json).getAsJsonObject();

            if (update.has("callback_query")) {
                handleCallbackQuery(update.getAsJsonObject("callback_query"));
            } else if (update.has("message")) {
                handleMessage(update.getAsJsonObject("message"));
            }
        } catch (Exception e) {
            LogService.addFormattedLog("Server", "Lỗi xử lý Telegram", "LỖI: " + e.getMessage());
        }
        response.setStatus(HttpServletResponse.SC_OK);
    }

    private void handleCallbackQuery(JsonObject callbackQuery) {
        String data = callbackQuery.get("data").getAsString();
        String chatId = callbackQuery.getAsJsonObject("message").getAsJsonObject("chat").get("id").getAsString();
        String userName = getUserName(callbackQuery.getAsJsonObject("from"));

        if (data.startsWith("confirm_")) {
            String command = data.substring(8);
            if (currentPendingLog != null)
                currentPendingLog.setStatus("Executed");
            executeCommand(command, userName, chatId);
        } else if ("cancel_action".equals(data)) {
            if (currentPendingLog != null)
                currentPendingLog.setStatus("Cancelled");
            telegramService.sendMessage(chatId, "❌ Đã hủy lệnh theo yêu cầu của " + userName);
        } else {
            executeCommand(data, userName, chatId);
        }
    }

    private void handleMessage(JsonObject message) {
        if (!message.has("text"))
            return;

        String text = message.get("text").getAsString();
        String chatId = message.getAsJsonObject("chat").get("id").getAsString();
        String userName = getUserName(message.getAsJsonObject("from"));

        LogService.addLog("[Telegram] Nhận tin nhắn từ: " + userName + " (Type: "
                + message.getAsJsonObject("chat").get("type").getAsString() + ")");
        LogService.addLog("[Telegram] Nội dung: " + text);
        LogService.addLog("[Telegram] Đang kiểm tra mention: @" + Config.BOT_USERNAME);

        if (text.contains("@" + Config.BOT_USERNAME)
                || message.getAsJsonObject("chat").get("type").getAsString().equals("private")) {

            String commandText = text.replace("@" + Config.BOT_USERNAME, "").trim();
            LogService.addLog("[Telegram] Command sau khi xử lý: " + commandText);

            String actionCode = aiController.analyzeIntent(commandText);
            LogService.addLog("[AI] Kết quả phân tích intent: " + actionCode);

            // Ghi nhật ký Chat Monitor
            currentPendingLog = new AIChatLog(userName, commandText, actionCode != null ? actionCode : "none");
            LogService.addAiChatLog(currentPendingLog);

            if (actionCode != null) {
                String confirmMsg = "🤖 *AI Phân tích:* Bạn muốn tôi thực hiện lệnh `" + actionCode + "` đúng không?";
                LogService.addLog("[Telegram] Gửi tin nhắn xác nhận cho: " + actionCode);
                telegramService.sendMessageWithConfirmation(chatId, confirmMsg, actionCode);
            } else {
                LogService.addLog("[Telegram] AI không hiểu intent, gửi tin nhắn xin lỗi");
                telegramService.sendMessage(chatId, "😅 Xin lỗi " + userName + ", tôi không hiểu lệnh đó.");
            }
        } else {
            LogService.addLog("[Telegram] Tin nhắn không phải mention bot hoặc chat riêng, bỏ qua.");
        }
    }

    private void executeCommand(String command, String userName, String chatId) {
        TelegramAction actionObj = new TelegramAction(userName, "Lệnh [" + command + "]", "Đang xử lý");
        LogService.addActionLog(actionObj);
        telegramService.sendMessage(chatId, "✅ Đã nhận lệnh: *" + command + "* từ " + userName);

        if ("phat_nhac".equals(command))
            esp32Service.sendCommand("phat_nhac");
        else if ("ru_vong".equals(command))
            esp32Service.sendCommand("ru_vong");
        else if ("dung".equals(command))
            esp32Service.sendCommand("dung");
        else if ("hinh_anh".equals(command))
            esp32Service.requestSnapshot();
    }

    private String getUserName(JsonObject from) {
        if (from == null)
            return "Unknown";
        String name = from.get("first_name").getAsString();
        if (from.has("last_name"))
            name += " " + from.get("last_name").getAsString();
        return name;
    }
}
