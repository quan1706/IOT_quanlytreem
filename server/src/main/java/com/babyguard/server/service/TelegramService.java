package com.babyguard.server.service;

import com.babyguard.server.config.Config;
import okhttp3.*;
import java.io.IOException;

public class TelegramService {
    private final OkHttpClient client = new OkHttpClient();

    public void sendPhotoWithButtons(byte[] imageBytes, String caption) throws IOException {
        RequestBody requestBody = new MultipartBody.Builder()
                .setType(MultipartBody.FORM)
                .addFormDataPart("chat_id", Config.TELEGRAM_CHAT_ID)
                .addFormDataPart("photo", "baby.jpg",
                        RequestBody.create(imageBytes, MediaType.parse("image/jpeg")))
                .addFormDataPart("caption", caption)
                .addFormDataPart("parse_mode", "Markdown")
                .addFormDataPart("reply_markup", "{\"inline_keyboard\":[" +
                        "[{\"text\":\"🎵 Phát nhạc\",\"callback_data\":\"phat_nhac\"},{\"text\":\"🔄 Ru võng\",\"callback_data\":\"ru_vong\"}],"
                        +
                        "[{\"text\":\"⏹ Dừng\",\"callback_data\":\"dung\"},{\"text\":\"📷 Hình ảnh\",\"callback_data\":\"hinh_anh\"}]"
                        +
                        "]}")
                .build();

        Request request = new Request.Builder()
                .url("https://api.telegram.org/bot" + Config.TELEGRAM_BOT_TOKEN + "/sendPhoto")
                .post(requestBody)
                .build();

        try (Response response = client.newCall(request).execute()) {
            if (!response.isSuccessful()) {
                LogService.addFormattedLog("Server", "Gửi ảnh lên Telegram", "THẤT BẠI - Mã: " + response.code());
                throw new IOException("Unexpected code " + response);
            }
            LogService.addFormattedLog("Server", "Gửi ảnh lên Telegram", "THÀNH CÔNG");
        }
    }

    public void sendMessage(String chatId, String text) {
        RequestBody requestBody = new FormBody.Builder()
                .add("chat_id", chatId)
                .add("text", text)
                .add("parse_mode", "Markdown")
                .build();

        Request request = new Request.Builder()
                .url("https://api.telegram.org/bot" + Config.TELEGRAM_BOT_TOKEN + "/sendMessage")
                .post(requestBody)
                .build();

        client.newCall(request).enqueue(new Callback() {
            @Override
            public void onFailure(Call call, IOException e) {
                LogService.addFormattedLog("Server", "Gửi tin nhắn Telegram", "THẤT BẠI: " + e.getMessage());
            }

            @Override
            public void onResponse(Call call, Response response) throws IOException {
                if (response.isSuccessful()) {
                    LogService.addFormattedLog("Server", "Gửi tin nhắn Telegram", "THÀNH CÔNG");
                }
                response.close();
            }
        });
    }
}
